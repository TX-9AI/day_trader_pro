#!/usr/bin/env python3
# day_trader_pro/tests/test_warehouse_cache.py — v1.2
# v1.2 (2026-09-02) — dtp r246. C9/C9b: `record` is a DICT for raw/trades and
#   a LIST for the derived tables, and assuming a list gave a silent zero.
# v1.1 (2026-09-01) — r242. C7/C7b/C8: query() refuses an oversized result
#   and names the way out, iter() and GROUP BY both work, and an empty date
#   range is refused by name. The cache OOM'd on the ANALYSIS side after the
#   streaming fetch had worked — a streaming cache with an unbounded read is
#   not a streaming cache.
# v1.0 (2026-09-01) — dtp r238. THE CACHE CLEANS UP, ALWAYS.
#
# 🔴 THE LEAK THIS EXISTS TO PREVENT IS ALREADY IN THE REPO. `tools/report_parity.py`
#   calls `tempfile.mkdtemp` TWICE and removes neither directory, so every parity
#   run leaves scratch behind. §27's rule, in the operator's words: the temp file
#   goes and "just leaves the report in the folder behind".
#
# ⚠️ CLEANUP ON THE HAPPY PATH IS THE EASY HALF. C2 and C3 are the ones that
#   matter: an exception and an outright SIGTERM. A cleanup that only runs when
#   nothing went wrong is a cleanup that runs when it is not needed.

import io
import os
import signal
import subprocess
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)

_fails = []


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + (f"   [{detail}]" if detail else ""))
    if not ok:
        _fails.append(name)


def main():
    import warehouse_cache as WC
    import config

    # ── C1 — scratch is DISK-backed, never tmpfs ────────────────────────
    # 🔑 On many Ubuntu images /tmp is tmpfs — RAM with a filesystem in front
    # of it — so caching there puts the OOM back wearing a different hat.
    scratch = WC.choose_scratch()
    check("C1 the scratch directory is disk-backed",
          os.path.isdir(scratch) and not WC._is_ram_backed(scratch), scratch)

    # ── C1b — the detector's REAL guarantee, re-derived ─────────────────
    # 🔴 THIS ASSERTED THAT AN UNKNOWN PATH READS AS RAM, AND IT DOES NOT — a
    # path under `/` resolves to `/`'s filesystem, which is disk, and saying so
    # is correct rather than a failure. The claim was in the code's docstring
    # too; the test caught the DOCSTRING, which is the good direction for that
    # to go. What the code actually guarantees is the case that matters: if
    # /proc/mounts is unreadable it assumes RAM, because choosing disk when
    # unsure is free and choosing RAM when unsure is the OOM being avoided.
    _real_open = open
    try:
        import builtins
        def _no_mounts(path, *a, **k):
            if str(path) == "/proc/mounts":
                raise OSError("unreadable")
            return _real_open(path, *a, **k)
        builtins.open = _no_mounts
        blind = WC._is_ram_backed(scratch)
    finally:
        builtins.open = _real_open
    check("C1b an unreadable /proc/mounts is treated as RAM-backed", blind)

    # ⚠️ AND A REAL tmpfs IS DETECTED. /dev/shm is tmpfs on every Linux this
    # fleet runs; without this C1 could pass by never detecting anything.
    check("C1c a genuine tmpfs is detected as RAM-backed",
          WC._is_ram_backed("/dev/shm") if os.path.isdir("/dev/shm") else True,
          "/dev/shm")

    # ── C2 — removed on a normal exit ───────────────────────────────────
    with WC.WarehouseCache("t") as c:
        root_ok, path = c.root, c.path
        c.conn.execute("CREATE TABLE t (a)")
        alive = os.path.isdir(root_ok)
    check("C2 the cache exists during the run and is gone after",
          alive and not os.path.isdir(root_ok))

    # ── C3 — removed when the body RAISES ───────────────────────────────
    try:
        with WC.WarehouseCache("t") as c:
            root_exc = c.root
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    check("C3 an exception still removes the cache",
          not os.path.isdir(root_exc))

    # ── C4 — removed on SIGTERM, from OUTSIDE the process ───────────────
    # 🔴 THE CASE A `finally` DOES NOT COVER. A killed report must not leave
    # gigabytes behind, and the boxes have already hit 100% disk once (r162).
    prog = ("import sys,time;sys.path.insert(0,%r);"
            "import warehouse_cache as W;c=W.WarehouseCache('kill');"
            "print(c.root,flush=True);time.sleep(30)" % _root)
    p = subprocess.Popen([sys.executable, "-c", prog],
                         stdout=subprocess.PIPE, text=True)
    root_kill = p.stdout.readline().strip()
    made = os.path.isdir(root_kill)
    p.send_signal(signal.SIGTERM)
    p.wait(timeout=15)
    check("C4 SIGTERM removes the cache",
          made and not os.path.isdir(root_kill), root_kill)

    # ── C5 — the REPORT is never inside the cache ───────────────────────
    # ⚠️ THE OTHER HALF OF THE RULE. Cleanup that took the deliverable with it
    # would be worse than a leak.
    rp = WC.report_path("x.txt")
    check("C5 reports are written under reports/, not the scratch dir",
          rp.startswith(config.REPORTS_DIR) and "reports" in rp
          and not rp.startswith(scratch), rp)

    # ── C6 — the probe writes there and nowhere else ────────────────────
    src = open(os.path.join(_root, "tools", "bfly_reach_probe.py"),
               encoding="utf-8").read()
    check("C6 the probe writes via report_path and closes in a finally",
          "report_path(" in src and "finally:" in src and "cache.close()" in src)

    # ── C7 — query() REFUSES a result it cannot hold ────────────────────
    # 🔴 THE CACHE OOM'D ANYWAY, ON THE ANALYSIS SIDE. It streamed 7.8M rows to
    # disk exactly as designed and then `bfly_pin_study` fetchall'd them back
    # into Python. Six minutes of S3 reads thrown away at the last step. A
    # streaming cache with an unbounded read is not a streaming cache.
    with WC.WarehouseCache("t") as c:
        c.conn.execute("CREATE TABLE big (a)")
        c.conn.executemany("INSERT INTO big VALUES (?)",
                           [(i,) for i in range(3000)])
        try:
            c.query("SELECT a FROM big", max_rows=100)
            refused = False
        except MemoryError as exc:
            refused = "GROUP BY" in str(exc) and ".iter()" in str(exc)
        check("C7 query() refuses an oversized result and names the way out",
              refused)

        # ⚠️ AND THE WAY OUT ACTUALLY WORKS — a check that only proves the
        # refusal would leave the caller with no path.
        n = sum(1 for _ in c.iter("SELECT a FROM big"))
        agg = c.query("SELECT COUNT(*) n FROM big")[0]["n"]
        check("C7b iter() streams it and GROUP BY aggregates it",
              n == 3000 and agg == 3000, f"iter={n} agg={agg}")

    # ── C8 — an empty date list is refused, not an IndexError ───────────
    # A reversed range produced one and it surfaced four frames below the
    # caller, inside the library.
    with WC.WarehouseCache("t") as c:
        try:
            c.load("x", [], ["a"])
            ok = False
        except ValueError as exc:
            ok = "END" in str(exc)
        except IndexError:
            ok = False
        check("C8 load() names an empty date range instead of IndexError", ok)

    # ── C9 — `record` MAY BE A DICT OR A LIST ───────────────────────────
    # 🔴 THE SILENT ZERO. The derived tables push a LIST of rows per object;
    # `trade_envelope` pushes ONE TRADE as a DICT. Iterating a dict yields its
    # KEYS, so the isinstance filter dropped every row: entry_report fetched
    # 1,595 objects, 5 MB, inserted 0 ROWS, and reported "no closed trades with
    # excursion telemetry in range" — a defect wearing the costume of a
    # finding, which is the worst shape a bug takes in this project.
    # ⚠️ WHAT EXPOSED IT WAS THE ROW COUNT IN THE TICKER. 1,595 objects and 0
    # rows cannot both be right; without that number on screen it would have
    # stood as an answer about the data.
    import json as _json
    import warehouse_reader as _WR

    class _B:
        def __init__(s, b): s.b = b
        def read(s): return s.b

    class _P:
        def __init__(s, st): s.st = st
        def paginate(s, Bucket=None, Prefix=None):
            yield {"Contents": [{"Key": k, "Size": len(v)}
                                for k, v in s.st.items() if k.startswith(Prefix)]}

    class _S3:
        def __init__(s, st): s.st = st
        def get_paginator(s, _): return _P(s.st)
        def get_object(s, Bucket=None, Key=None): return {"Body": _B(s.st[Key])}

    store = {
        "raw/trades/dt=2026-08-31/sym=QQQ/a.json": _json.dumps(
            {"symbol": "QQQ", "record": {"trade_id": "t1"}}).encode(),
        "raw/derived_x/dt=2026-08-31/sym=QQQ/c.json": _json.dumps(
            {"symbol": "QQQ", "record": [{"trade_id": "d1"},
                                         {"trade_id": "d2"}]}).encode(),
    }
    _real = _WR._client
    _WR._client = lambda *a, **k: _S3(store)
    WC.WR._client = lambda *a, **k: _S3(store)
    try:
        import contextlib as _c
        with WC.WarehouseCache("t") as c:
            with _c.redirect_stderr(io.StringIO()):
                n_dict = c.load("trades", ["2026-08-31"], ["trade_id"],
                                datatype="trades")
                n_list = c.load("x", ["2026-08-31"], ["trade_id"])
            check("C9 a dict-shaped record loads as one row",
                  n_dict == 1, f"got {n_dict}")
            check("C9b a list-shaped record still loads every row",
                  n_list == 2, f"got {n_list}")
    finally:
        _WR._client = _real
        WC.WR._client = _real

    print()
    if _fails:
        print(f"FAILED {len(_fails)}: " + ", ".join(_fails))
        return 1
    print("test_warehouse_cache: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
