#!/usr/bin/env python3
# day_trader_pro/warehouse_cache.py — v1.1
# v1.1 (2026-09-01) — r240. Progress via progress.Ticker. The total is
#   counted across ALL requested dates before any fetch, so a multi-day read
#   shows one honest percentage instead of restarting at 0% each day and
#   looking stuck once per date.
# v1.0 (2026-09-01) — dtp r238. FETCH ONCE, QUERY MANY, LEAVE NOTHING BEHIND.
#
# 🔴 WHY THIS EXISTS. Menu 55 (fit readiness) was OOM-KILLED on a 2026-08-24
#   to 09-01 range (RPT.10). The cause is structural, not a tuning problem:
#   `warehouse_reader.read_prefix` downloads every object in a partition and
#   returns them as a fully materialised list, and `load_derived` then holds a
#   dict spanning the WHOLE range plus a forward window, then builds a second
#   list. Peak memory is parsed-objects + dict + list, all alive at once.
#   ⚠️ AND PYTHON OBJECTS ARE ~4.4x THE JSON THEY CAME FROM — measured: a
#   plan_tick row is 368 bytes on the wire and 1,634 as a dict. `surface_series`
#   alone is 0.55 GB of JSON per box and 2.4 GB resident; fleet-wide that is
#   8 GB on disk and ~36 GB in memory. Nothing survives that.
#
# 🔑 THE OPERATOR'S DESIGN, AND IT IS BETTER THAN STREAM-AND-FOLD. Streaming
#   fixes the memory but re-downloads on every question, and a survey is never
#   one question — BFLY.9 is "how many wings qualified", then "at what leg
#   spread", then "which symbols never qualify". Materialising to a local file
#   decouples FETCH from ANALYSIS: pay S3 once, iterate locally.
#   · SQLite, not a text dump, so the second question is a `SELECT` on an index
#     rather than another full parse. Control already uses sqlite everywhere;
#     no new dependency, no Parquet, no DuckDB.
#   · PROJECTED AT CACHE TIME. Only the columns the caller asks for are kept,
#     so the cache is a fraction of the raw bytes and the memory ceiling is ONE
#     OBJECT regardless of how many days are requested.
#
# ⚠️ CLEANUP IS NOT OPTIONAL AND NOT ON THE HAPPY PATH ONLY. Operator: the
#   temp file goes and "just leaves the report in the folder behind". §27 —
#   delivery scaffolding that must be remembered never gets removed, and this
#   repo already has the proof: `tools/report_parity.py` calls `mkdtemp` TWICE
#   and never removes either directory, so every parity run leaks. So cleanup
#   here runs from a context manager AND an atexit hook AND on SIGINT/SIGTERM,
#   and it refuses to touch anything outside the directory it created.
#
# ⚠️ NEVER /tmp BY ASSUMPTION. On many Ubuntu images /tmp is tmpfs — RAM with a
#   filesystem in front of it — and writing the cache there puts the OOM back
#   wearing a different hat. The directory is chosen by CHECKING, not by
#   convention, and the choice is reported.
"""Local, disposable S3 cache for warehouse reports."""

from __future__ import annotations

import atexit
import json
import os
import shutil
import signal
import sqlite3
import sys
import tempfile

import config
import warehouse_reader as WR

_ACTIVE: list = []          # dirs to remove if we die unexpectedly


def _is_ram_backed(path: str) -> bool:
    """True when `path` lives on tmpfs/ramfs — i.e. writing there uses RAM.

    ⚠️ THE GUARANTEE IS NARROWER THAN "FAILS TOWARD RAM", and the first draft
    of this docstring claimed more than the code does — caught by its own test.
    What is true: if /proc/mounts cannot be READ, or no mount matches at all,
    it returns True (assume RAM). What is NOT true is that an unknown path
    returns True — a path under `/` resolves to `/`'s filesystem, which is
    disk, and reporting that correctly is the right answer rather than a
    failure. The caller also creates the directory before asking, so the
    "unknown path" case does not arise in practice.
    """
    try:
        with open("/proc/mounts", encoding="utf-8") as fh:
            mounts = [ln.split() for ln in fh if ln.strip()]
    except Exception:                                           # noqa: BLE001
        return True
    best, fstype = "", ""
    real = os.path.realpath(path)
    for m in mounts:
        if len(m) < 3:
            continue
        mp = m[1]
        if (real == mp or real.startswith(mp.rstrip("/") + "/")) and len(mp) > len(best):
            best, fstype = mp, m[2]
    return fstype in ("tmpfs", "ramfs") or not fstype


def choose_scratch() -> str:
    """A writable, DISK-backed directory for the cache.

    Order: $DTP_CACHE_DIR, then the repo's own var/, then /var/tmp, then
    $HOME, then /tmp as a last resort. The first three are disk on every image
    this fleet runs; /tmp is checked and only used if it is not tmpfs.
    """
    cands = [os.environ.get("DTP_CACHE_DIR"),
             os.path.join(config.BASE_DIR, "var"),
             "/var/tmp", os.path.expanduser("~"), tempfile.gettempdir()]
    for c in cands:
        if not c:
            continue
        try:
            os.makedirs(c, exist_ok=True)
            if not os.access(c, os.W_OK):
                continue
            if _is_ram_backed(c):
                continue
            return c
        except Exception:                                       # noqa: BLE001
            continue
    # Nothing disk-backed is writable. Say so rather than silently using RAM.
    raise RuntimeError("no writable disk-backed scratch directory found "
                       "(set DTP_CACHE_DIR)")


def _sweep(*_a):
    for d in list(_ACTIVE):
        shutil.rmtree(d, ignore_errors=True)
        try:
            _ACTIVE.remove(d)
        except ValueError:
            pass


atexit.register(_sweep)
for _sig in (signal.SIGINT, signal.SIGTERM):
    try:
        _prev = signal.getsignal(_sig)

        def _handler(s, f, _prev=_prev):
            _sweep()
            if callable(_prev):
                _prev(s, f)
            else:
                raise KeyboardInterrupt if s == signal.SIGINT else SystemExit(1)
        signal.signal(_sig, _handler)
    except Exception:                                           # noqa: BLE001
        pass


class WarehouseCache:
    """A disposable SQLite mirror of the columns one report needs.

    Use as a context manager. The directory is removed on exit — success,
    exception, Ctrl-C or SIGTERM alike — and the report it produced is
    untouched, because the report is written elsewhere (config.REPORTS_DIR).
    """

    def __init__(self, label: str = "wh"):
        self.root = tempfile.mkdtemp(prefix=f"{label}_", dir=choose_scratch())
        _ACTIVE.append(self.root)
        self.path = os.path.join(self.root, "cache.db")
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.objects = 0
        self.rows = 0
        self.bytes_seen = 0

    # ── lifecycle ──────────────────────────────────────────────────────
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def close(self):
        try:
            self.conn.close()
        except Exception:                                       # noqa: BLE001
            pass
        shutil.rmtree(self.root, ignore_errors=True)
        if self.root in _ACTIVE:
            _ACTIVE.remove(self.root)

    # ── fill ───────────────────────────────────────────────────────────
    def load(self, table: str, dates, columns, s3=None, datatype=None) -> int:
        """Stream `raw/<datatype>/dt=<d>/` for each date, keeping `columns`.

        🔑 ONE OBJECT IS PARSED AT A TIME AND DISCARDED. Nothing accumulates in
        Python: rows go straight into sqlite and the parsed envelope is
        released before the next key is fetched. Memory is O(one object), not
        O(range).
        ⚠️ AND THE PROJECTION HAPPENS HERE, not at query time — a row with 40
        columns costs 3 when the report needs 3.
        """
        s3 = s3 or WR._client()
        dt = datatype or f"derived_{table}"
        cols = list(columns)
        ddl = ", ".join(f'"{c}"' for c in cols)
        self.conn.execute(f'CREATE TABLE IF NOT EXISTS "{table}" '
                          f'(symbol TEXT, {ddl})')
        ins = (f'INSERT INTO "{table}" (symbol, {ddl}) '
               f'VALUES ({",".join("?" * (len(cols) + 1))})')
        from progress import Ticker
        n = 0
        pg = s3.get_paginator("list_objects_v2")
        # ⚠️ THE TOTAL IS COUNTED FIRST, ACROSS ALL DATES, so a multi-day read
        # shows one honest percentage instead of restarting at 0% each day and
        # looking stuck. Listing is cheap relative to the GETs.
        plan = []
        for d in dates:
            for page in pg.paginate(Bucket=WR.BUCKET,
                                    Prefix=f"{WR.PREFIX}/{dt}/dt={d}/"):
                for o in page.get("Contents", []) or []:
                    plan.append((o["Key"], int(o.get("Size", 0) or 0)))
        tk = Ticker(f"{dt} {dates[0]}..{dates[-1]}", total=len(plan))
        for d in dates:
            pfx = f"{WR.PREFIX}/{dt}/dt={d}/"
            keys = [(k, sz) for k, sz in plan if k.startswith(pfx)]
            for key, size in keys:
                try:
                    body = s3.get_object(Bucket=WR.BUCKET, Key=key)["Body"].read()
                except Exception:                               # noqa: BLE001
                    # ⚠️ NAMED, NEVER SILENT — an unreadable object is a hole in
                    # the sample and the report must be able to say so.
                    self.conn.execute(
                        "CREATE TABLE IF NOT EXISTS _unreadable (key TEXT)")
                    self.conn.execute("INSERT INTO _unreadable VALUES (?)", (key,))
                    continue
                self.objects += 1
                self.bytes_seen += size
                env = json.loads(body)
                sym = env.get("symbol") or WR._sym_of(key)
                batch = [tuple([sym] + [r.get(c) for c in cols])
                         for r in (env.get("record") or [])
                         if isinstance(r, dict)]
                if batch:
                    self.conn.executemany(ins, batch)
                    n += len(batch)
                del env, body, batch          # explicit: nothing carries over
                tk.step(1, size)
            self.conn.commit()
        tk.done(f"{n:,} rows")
        self.rows += n
        return n

    def query(self, sql, args=()):
        return self.conn.execute(sql, args).fetchall()


def report_path(name: str) -> str:
    """Where a finished report goes — and it is NEVER the cache directory."""
    os.makedirs(config.REPORTS_DIR, exist_ok=True)
    return os.path.join(config.REPORTS_DIR, name)
