#!/usr/bin/env python3
# day_trader_pro/warehouse_cache.py — v1.6
# v1.6 (2026-09-05) — dtp r290 / S3.21. 🔴 THIS METHOD READ THE WRONG ROWS IN
#   BOTH DIRECTIONS, AND HAD SINCE IT WAS WRITTEN. It listed only the requested
#   `dt=` partitions and filtered nothing afterwards — but a DERIVED partition
#   carries the PUSH day, not the row's ET day (C.9). So a row whose session was
#   in range but which pushed the next morning was NEVER READ, and a row pushed
#   inside the range whose own day fell before it was read anyway. Neither
#   consumer compensated: `collect()` takes `dates` and does not filter on them,
#   `screen_plan_gates` bounds by strategy and symbol.
#   🔑 `load_derived` HAS DONE THIS CORRECTLY SINCE r184 — scan a forward window,
#   keep rows whose OWN timestamp lands in range — and it has no production
#   callers (S3.11). The correct behaviour sat on the dead road while every real
#   report used this one, which is the same finding as S3.11 one layer down.
#   ⚠️ THE FILTER IS PER ROW IN PYTHON, NOT AN SQL OFFSET. `_et_offset()` applies
#   TODAY's UTC offset to every row — right for eight months, an hour wrong for
#   four, the exact DST trap its own docstring warns about. `ettime.et_day`
#   converts each epoch on its own terms, at insert, so memory stays O(one
#   object) and the row count stays honest.
#   ⚠️ FORWARD SCANNING IS DERIVED-ONLY. A raw stream like `candles` is
#   partitioned by the day it describes, so scanning forward there would pull in
#   genuinely later sessions.
# v1.5 (2026-09-05) — dtp r286 / S3.11. 🔴 THE CDC COLLAPSE NOW RUNS HERE,
#   WHERE THE DATA ACTUALLY COMES FROM. `warehouse_reader.load_derived` has
#   carried the natural-key collapse since r276 and HAS NO PRODUCTION CALLERS:
#   its only references outside its own definition are three test files and one
#   `fit_readiness` docstring describing an architecture that changed. Every
#   report reaches the warehouse through THIS method, which streamed the raw
#   objects uncollapsed — a correct fix on a road nobody drives, which is r230's
#   shape, and `test_natural_key` stayed green the whole time because it calls
#   `load_derived` directly.
#   🔑 O(ONE OBJECT) IS PRESERVED: sqlite dedupes on disk through a UNIQUE index
#   on the natural key, so nothing accumulates in Python — this class's entire
#   reason for existing after r242's OOM. The winner rule is `load_derived`'s
#   rather than a new one: a later push replaces an earlier one for the same
#   key, because these are CDC rows and the last state written is the true one.
#   🔴 AND IT REFUSES A PARTIAL KEY. `load()` keeps only the columns a caller
#   asks for, and collapsing on a SUBSET of a primary key folds genuinely
#   distinct rows together — silently, and in the direction that makes a report
#   look tidier. Measured: `fit_readiness` requested `plan_ledger` without
#   `plan_id`, which IS that table's whole key. A table whose key does not
#   survive the projection loads UNCOLLAPSED and `collapse_note()` says so.
#   ⚠️ WHICH IS WHY THE NOTE EXISTS AT ALL: a report must not describe a
#   collapse it did not get. fit_readiness printed "N after collapse by
#   (_rid, ts)" while its rows came from here and were never collapsed — the
#   number was real and the sentence was false, and the sentence is the worse
#   half.
# v1.4 (2026-09-02) — dtp r253. 🔴 `load()` IGNORED EVERY PARTITION BELOW THE
#   DATE. Keys are raw/<datatype>/dt=<day>/sym=<SYM>/[interval=<iv>/]file and
#   this listed only down to dt=, so the sweep forensics report queued 48,305
#   GETs for ~39 MB — 798 bytes an object, a thirty-minute run that was pure
#   round-trip latency. `syms=` and `part=` scope the prefix; `keep=` filters
#   rows at insert so a report does not write 3.3M rows to read eight.
# v1.3 (2026-09-02) — dtp r246. 🔴 `record` IS A DICT FOR SOME STREAMS AND A
#   LIST FOR OTHERS, and assuming a list gave a SILENT ZERO: raw/trades
#   pushes ONE TRADE PER OBJECT as a dict, so entry_report fetched 1,595
#   objects and inserted 0 rows, then said "no closed trades with excursion
#   telemetry in range" — a defect wearing the costume of a finding.
# v1.2 (2026-09-01) — r242. 🔴 `query()` WAS fetchall AND THE CACHE OOM'D
#   ANYWAY — on the analysis side, after the streaming fetch had worked. It
#   now REFUSES a result above MAX_ROWS and names the two ways out (GROUP BY,
#   or .iter()), rather than dying four frames later in the caller. Adds
#   iter(), index() and et_offset_hours() so aggregating in SQL is the easy
#   path rather than the disciplined one.
#   ⚠️ AND load() REFUSES AN EMPTY DATE LIST. A reversed range (END before
#   START) raised IndexError on `dates[-1]` four frames below the caller; a
#   library that depends on every caller validating for it is a guard that
#   works only when someone remembers it.
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
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

_ET = ZoneInfo("US/Eastern")

import config
import ettime                                            # noqa: E402
import warehouse_reader as WR


def _collapsible(table, cols):
    """The natural key for `table` IF every column of it survives the
    projection, else () — meaning load uncollapsed and say so.

    🔴 NEVER A PARTIAL KEY. `cache.load` keeps only the columns a caller asks
    for, and collapsing on a subset of a primary key folds genuinely DISTINCT
    rows together — silently, and in the direction that makes a report look
    tidier. Measured 2026-09-05: `fit_readiness` requests `plan_ledger` without
    `plan_id`, whose key IS `plan_id`; collapsing that on what it does have
    would have merged every plan in the range.
    ⚠️ `symbol` IS ALWAYS AVAILABLE because `load` injects it, so it counts as
    present even though no caller lists it.
    """
    nat = WR.DERIVED_NATURAL_KEY.get(table)
    if not nat:
        return ()
    have = set(cols) | {"symbol"}
    return tuple(nat) if all(c in have for c in nat) else ()

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
        # r286 — {table: natural-key tuple that ran, or () if it could not}.
        # A report asks `collapse_note()` rather than describing a rule it
        # assumes; that assumption is exactly what went wrong in fit_readiness.
        self.collapsed: dict = {}
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
    def collapse_note(self, table: str) -> str:
        """One line naming which rule ran for `table`, for a report banner.

        ⚠️ A REPORT MUST NOT DESCRIBE A COLLAPSE IT DID NOT GET. `fit_readiness`
        printed "N after collapse by (_rid, ts)" while its rows came from this
        class, which collapsed nothing — the number was real and the sentence
        was false. Callers ask here instead of asserting.
        """
        nat = self.collapsed.get(table)
        if nat is None:
            return "not loaded"
        if not nat:
            return ("NOT COLLAPSED — the projection is missing part of this "
                    "table's primary key; counts may include CDC duplicates")
        return "collapsed on " + ", ".join(nat)

    def load(self, table: str, dates, columns, s3=None, datatype=None,
             syms=None, part=None, keep=None, forward=None) -> int:
        # ⚠️ AN EMPTY DATE LIST IS A LEGITIMATE INPUT, NOT A CRASH SITE. A
        # reversed range (END before START) produced one, and this raised
        # IndexError on `dates[-1]` four frames below the caller. A library
        # that depends on every caller validating for it is a guard that works
        # only when someone remembers it.
        if not dates:
            raise ValueError("no dates requested — check that END is not "
                             "earlier than START")
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

        # ── 🔴 r290 / S3.21 — SCAN FORWARD, KEEP BY THE ROW'S OWN ET DAY ────
        # This method listed ONLY the requested `dt=` partitions and filtered
        # nothing afterwards, and BOTH halves of that are wrong because a
        # DERIVED partition is stamped with the PUSH day, not the row's ET day
        # (C.9 — it is why the coverage report grades these streams `pusher`).
        #   · a row whose ET day is in range but which pushed the next morning
        #     was NEVER READ — silently, and the report showed a smaller,
        #     plausible number with nothing to indicate a hole;
        #   · a row pushed inside the range whose ET day falls BEFORE it was
        #     read anyway, so a one-day report could carry the previous
        #     session's tail.
        # Wrong in both directions, and neither consumer compensated:
        # `collect()` takes `dates` and does not filter on them, and
        # `screen_plan_gates` bounds by strategy and symbol, not by day.
        # 🔑 `load_derived` HAS DONE THIS CORRECTLY SINCE r184 — scan a forward
        # window, then keep rows whose OWN timestamp lands in range. It has no
        # production callers (S3.11), so the correct behaviour sat on the dead
        # road while every real report used this one.
        fwd = WR.DERIVED_FORWARD_DAYS if forward is None else int(forward)
        # ⚠️ ONLY FOR DERIVED STREAMS. A raw stream like `candles` or `ohlc` is
        # partitioned by the day it describes, so a forward scan there would
        # pull genuinely later sessions in.
        if not dt.startswith("derived_"):
            fwd = 0
        scan = list(dates)
        if fwd:
            _last = datetime.strptime(dates[-1], "%Y-%m-%d")
            scan += [(_last + timedelta(days=i + 1)).date().isoformat()
                     for i in range(fwd)]
        ts_col = WR.DERIVED_TS_COL.get(table, WR.DEFAULT_TS_COL)
        want_days = set(dates)
        # ⚠️ FILTERED PER ROW IN PYTHON, NOT BY AN SQL OFFSET. `_et_offset()`
        # applies TODAY's UTC offset to every row, which is right for eight
        # months and an hour wrong for four — the same DST trap its own
        # docstring warns about, one level up. `ettime.et_day` converts each
        # epoch on its own terms, and doing it at INSERT keeps memory at
        # O(one object) and keeps the row count honest.
        def _in_range(r):
            if not fwd or ts_col not in r:
                return True
            return ettime.et_day(r.get(ts_col)) in want_days
        cols = list(columns)
        ddl = ", ".join(f'"{c}"' for c in cols)
        self.conn.execute(f'CREATE TABLE IF NOT EXISTS "{table}" '
                          f'(symbol TEXT, {ddl})')
        # ── 🔴 r286 / S3.11 — THE CDC COLLAPSE RUNS HERE, WHERE THE DATA
        # ACTUALLY COMES FROM. `warehouse_reader.load_derived` carries the
        # natural-key collapse from r276 and HAS NO PRODUCTION CALLERS: every
        # report reaches the warehouse through this method, which streamed the
        # raw objects uncollapsed. A correct fix on a road nobody drives — the
        # r230 shape — and `test_natural_key` stayed green throughout because
        # it calls `load_derived` directly.
        # 🔑 O(ONE OBJECT) IS PRESERVED. sqlite dedupes on disk through a
        # UNIQUE index; nothing accumulates in Python, which is this class's
        # whole reason for existing (r242's OOM).
        # ⚠️ AND THE WINNER RULE IS `load_derived`'s, NOT A NEW ONE: a later
        # push replaces an earlier one for the same key, because these are CDC
        # rows and the last state written is the true one.
        nat = _collapsible(table, cols)
        if nat:
            self.conn.execute(
                f'CREATE UNIQUE INDEX IF NOT EXISTS "ux_{table}" '
                f'ON "{table}" ({", ".join(chr(34) + c + chr(34) for c in nat)})')
            ins = (f'INSERT OR REPLACE INTO "{table}" (symbol, {ddl}) '
                   f'VALUES ({",".join("?" * (len(cols) + 1))})')
        else:
            ins = (f'INSERT INTO "{table}" (symbol, {ddl}) '
                   f'VALUES ({",".join("?" * (len(cols) + 1))})')
        self.collapsed[table] = nat
        # 🔴 r286 — THE RETURN VALUE MUST BE WHAT THE TABLE HOLDS, NOT WHAT WAS
        # ATTEMPTED. With the collapse in place `n` counted INSERTS, so a load
        # of four objects carrying two logical rows returned 4 — and every
        # caller prints that number next to "collapsed on ...", which is the
        # same false sentence r286 exists to remove. Caught by this revision's
        # own checker showing 2 rows in the table and 4 in the ticker.
        try:
            before = self.conn.execute(
                f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        except Exception:                                      # noqa: BLE001
            before = 0
        from progress import Ticker
        n = 0
        pg = s3.get_paginator("list_objects_v2")
        # ⚠️ THE TOTAL IS COUNTED FIRST, ACROSS ALL DATES, so a multi-day read
        # shows one honest percentage instead of restarting at 0% each day and
        # looking stuck. Listing is cheap relative to the GETs.
        # 🔴 r253 — THE BUCKET PARTITIONS ON MORE THAN THE DATE AND THIS DID
        # NOT USE IT. The key layout is
        #   raw/<datatype>/dt=<day>/sym=<SYM>/[interval=<iv>/]<file>.json
        # and this listed `raw/<dt>/dt=<d>/` and fetched EVERYTHING under it.
        # Measured 2026-09-02: the sweep forensics report needed 1m bars for
        # the six or eight symbols that have sweep trades and instead queued
        # **48,305 GETs for ~39 MB** — 798 bytes an object, a THIRTY-MINUTE
        # run dominated entirely by round trips.
        # 🔑 LATENCY, NOT VOLUME, IS WHAT COSTS HERE, and the warehouse map
        # already said so: signal_journal is 67% of all objects and 0.4% of
        # the bytes. I wrote that down yesterday and did not apply it.
        # ⚠️ SCOPING THE PREFIX IS THE WHOLE FIX. A caller that knows its
        # symbols — and a report always does, because it reads `trades` first —
        # lists only those partitions.
        prefixes = []
        # ⚠️ THE LISTING WALKS `scan`, NOT `dates`. A first cut changed only the
        # FETCH loop and left this on `dates`, so the forward partitions were
        # never listed and the fix did nothing — the checker showed identical
        # failures before and after, which is exactly what a fix applied to the
        # wrong half looks like.
        for d in scan:
            base = f"{WR.PREFIX}/{dt}/dt={d}/"
            if syms:
                for sy in syms:
                    p2 = f"{base}sym={sy}/"
                    prefixes.append(p2 + (f"{part}/" if part else ""))
            else:
                prefixes.append(base + (f"*/{part}/" if part else ""))
        plan = []
        for pfx in prefixes:
            # ⚠️ A WILDCARD IS NOT A LIST OPERATION. S3 has no globbing, so a
            # partition segment below an UNSCOPED symbol has to be filtered
            # after listing rather than in the Prefix. Naming the symbols is
            # what makes it cheap; `part` alone only avoids the fetch.
            if "*" in pfx:
                listing, want = pfx.split("*/", 1)[0], pfx.split("*/", 1)[1]
            else:
                listing, want = pfx, None
            for page in pg.paginate(Bucket=WR.BUCKET, Prefix=listing):
                for o in page.get("Contents", []) or []:
                    k = o["Key"]
                    if want and want not in k:
                        continue
                    plan.append((k, int(o.get("Size", 0) or 0)))
        tk = Ticker(f"{dt} {dates[0]}..{dates[-1]}", total=len(plan))
        for d in scan:
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
                # 🔴 r246 — `record` IS NOT ALWAYS A LIST, AND ASSUMING IT WAS
                # PRODUCED A SILENT ZERO. The derived tables push a LIST of
                # rows per object; `trade_envelope` (s3_push.py:596) pushes ONE
                # TRADE as a DICT — one object per trade. Iterating a dict
                # yields its KEYS, so `isinstance(r, dict)` was False for every
                # one and the batch came out empty: entry_report fetched 1,595
                # objects, 5 MB, and inserted 0 ROWS, then reported "no closed
                # trades with excursion telemetry in range" — which reads as a
                # finding about the data rather than a defect in the reader.
                # ⚠️ THE WORST KIND OF BUG THIS PROJECT HAS: an empty result
                # that looks like an answer. The row count in the ticker is
                # what exposed it — 1,595 objects and 0 rows cannot both be
                # right, and without that number on screen it would have stood.
                rec = env.get("record")
                if isinstance(rec, dict):
                    rec = [rec]
                elif not isinstance(rec, list):
                    rec = []
                # ⚠️ `keep` FILTERS AT INSERT, NOT AT QUERY. It does not reduce
                # the download — the object is already here — but it stops a
                # report writing 3.3M rows to read eight check names out of
                # them, which is the write, the index and the memory.
                batch = [tuple([sym] + [r.get(c) for c in cols])
                         for r in rec
                         if isinstance(r, dict) and (keep is None or keep(r))
                         and _in_range(r)]
                if batch:
                    self.conn.executemany(ins, batch)
                    n += len(batch)
                del env, body, batch          # explicit: nothing carries over
                tk.step(1, size)
            self.conn.commit()
        if nat:
            # Re-count rather than track: INSERT OR REPLACE gives no signal
            # about which rows merged, and a running estimate would be a second
            # number to keep true.
            after = self.conn.execute(
                f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            n = after - before
        tk.done(f"{n:,} rows")
        self.rows += n
        return n

    # ── read ───────────────────────────────────────────────────────────
    # 🔴 r242 — `query()` IS fetchall AND THAT IS HOW THIS OOM'D ANYWAY.
    # The cache streamed 7.8M surface_series rows to disk exactly as designed,
    # and then `bfly_pin_study` called `query("SELECT ts_epoch, charm ...")`,
    # materialising every one of them as a Python object in a single list. The
    # OOM moved from the FETCH to the ANALYSIS and I did not see it because I
    # was looking at the half I had fixed. Six minutes of S3 reads thrown away
    # at the last step.
    # 🔑 THE RULE THIS ENFORCES: AGGREGATE IN SQL, RETURN ROWS YOU CAN COUNT.
    # sqlite will happily group 7.8M rows into seven buckets; Python will not
    # hold 7.8M dicts. `query()` now REFUSES a result set above `max_rows`
    # rather than dying four frames later, and names the two ways out.
    MAX_ROWS = 200_000

    def query(self, sql, args=(), max_rows=None):
        """Fetch a BOUNDED result. Raises rather than exhausting memory."""
        cap = self.MAX_ROWS if max_rows is None else max_rows
        cur = self.conn.execute(sql, args)
        rows = cur.fetchmany(cap + 1)
        if len(rows) > cap:
            raise MemoryError(
                f"query returned more than {cap:,} rows. Aggregate in SQL "
                f"(GROUP BY) or stream with .iter() — materialising a large "
                f"result is what the cache exists to avoid.\n  {sql[:120]}")
        return rows

    def iter(self, sql, args=(), chunk=10_000):
        """Stream a result set. Nothing accumulates."""
        cur = self.conn.execute(sql, args)
        while True:
            batch = cur.fetchmany(chunk)
            if not batch:
                return
            for r in batch:
                yield r

    def index(self, table, *cols):
        """Index the cache for aggregation. Cheap and worth it every time."""
        name = "ix_%s_%s" % (table, "_".join(cols))
        self.conn.execute(f'CREATE INDEX IF NOT EXISTS "{name}" '
                          f'ON "{table}" ({",".join(cols)})')
        self.conn.commit()

    def et_offset_hours(self):
        """The ET offset as an sqlite modifier, for GROUP BY on ts_epoch.

        ⚠️ NOT A HARDCODED '-4 hours'. That is EDT — right for eight months and
        silently wrong for four — and it has already been found and fixed twice
        in this codebase (r125's sensors, dtp r236's standings)."""
        off = datetime.now(_ET).utcoffset()
        return f"{int(off.total_seconds() // 3600)} hours"


def report_path(name: str) -> str:
    """Where a finished report goes — and it is NEVER the cache directory."""
    os.makedirs(config.REPORTS_DIR, exist_ok=True)
    return os.path.join(config.REPORTS_DIR, name)
