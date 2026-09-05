#!/usr/bin/env python3
"""day_trader_pro/tests/test_cache_window.py — v1.0
v1.0  2026-09-05 — dtp r290 / S3.21. THE FORWARD SCAN AND THE ET-DAY FILTER,
ON THE PATH REPORTS ACTUALLY TAKE.

🔴 THE DEFECT. `WarehouseCache.load` listed only the requested `dt=` partitions
and filtered nothing afterwards. A DERIVED partition carries the **PUSH day**,
not the row's ET day (C.9 — it is why the coverage report grades those streams
`pusher` grain), so the method was wrong in BOTH directions: a row whose session
was in range but which pushed the next morning was never read, and a row pushed
inside the range whose own day fell before it was read anyway. Neither consumer
compensated — `collect()` takes `dates` and does not filter on them,
`screen_plan_gates` bounds by strategy and symbol.

🔑 AND `load_derived` HAS DONE IT CORRECTLY SINCE r184. It has no production
callers (S3.11), so the right behaviour sat on the road with no traffic while
every real report used the wrong one. The checker that would have caught this —
`tests/test_fit_readiness_s3.py`, whose case C is a forward-scan POSITIVE
CONTROL — has been raising a TypeError before its first assertion for just as
long (RPT.14). **A positive control that cannot execute is not a control.**

⚠️ SO EVERY CASE HERE DRIVES `cache.load` AND COUNTS ROWS IN SQLITE. Nothing
touches `load_derived`; testing the dead path is what let this live for months.
"""
import io
import json
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
FAILED = []
ET = ZoneInfo("America/New_York")


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        FAILED.append(name)


class _S3:
    def __init__(self, store):
        self.store = store

    def get_paginator(self, _op):
        outer = self

        class _P:
            def paginate(self, **kw):
                pre = kw.get("Prefix", "")
                yield {"Contents": [{"Key": k, "Size": 1}
                                    for k in sorted(outer.store) if k.startswith(pre)]}
        return _P()

    def get_object(self, Bucket=None, Key=None):
        return {"Body": io.BytesIO(json.dumps(self.store[Key]).encode())}


def _ts(day: str, hhmm: str = "14:00") -> float:
    """An epoch that genuinely belongs to `day` in ET."""
    return datetime.strptime(f"{day} {hhmm}", "%Y-%m-%d %H:%M").replace(
        tzinfo=ET).timestamp()


def _obj(rows, pushed="2026-09-03T20:00:00Z"):
    return {"pushed_at_utc": pushed, "record": rows}


NEED = ["_rid", "ts_epoch", "strategy", "check_name", "verdict", "value",
        "direction"]


def _row(day, name):
    return {"ts_epoch": _ts(day), "strategy": "orb", "direction": "long",
            "check_name": name, "verdict": "PASS", "value": 1.0, "_rid": 1}


def main():
    import warehouse_cache as WC
    import warehouse_reader as WR

    DAY = "2026-09-02"
    NEXT = "2026-09-03"
    PREV = "2026-09-01"

    store = {
        # In range, pushed the SAME day — always worked.
        f"raw/derived_plan_check/dt={DAY}/sym=QQQ/a.json": _obj([_row(DAY, "same_day")]),
        # 🔴 In range, pushed the NEXT morning. THE LOSS CASE: filed under
        # dt=2026-09-03 because that is when the pusher ran, so a report for
        # 09-02 never listed the partition it lives in.
        f"raw/derived_plan_check/dt={NEXT}/sym=QQQ/b.json": _obj([_row(DAY, "late_push")]),
        # ⚠️ Pushed inside the forward window but belonging to the PREVIOUS
        # session. THE OVER-INCLUSION CASE: a one-day report carrying the tail
        # of the day before.
        f"raw/derived_plan_check/dt={NEXT}/sym=QQQ/c.json": _obj([_row(PREV, "prev_day")]),
        # And a genuinely later session, which must never be pulled in.
        f"raw/derived_plan_check/dt={NEXT}/sym=QQQ/d.json": _obj([_row(NEXT, "next_day")]),
    }
    WR._client = lambda *a, **k: _S3(store)

    c = WC.WarehouseCache("t_window")
    c.load("plan_check", [DAY], NEED, syms=["QQQ"])
    got = sorted(r["check_name"] for r in
                 c.query('SELECT check_name FROM "plan_check"'))

    # ══ 🔴 W1 — THE POSITIVE CONTROL. Without the forward scan the late push
    # ══      is simply absent, and the report shows a smaller, plausible
    # ══      number with nothing to indicate a hole.
    check("W1 a row pushed the NEXT morning is still read for its own session",
          "late_push" in got, str(got))
    check("W1b ...alongside the one pushed the same day", "same_day" in got)

    # ══ W2 — AND THE WINDOW DOES NOT LEAK IN EITHER DIRECTION ════════════
    # Scanning forward without filtering by the row's own day would drag the
    # previous session's tail and the next session in with it.
    check("W2 a row from the PREVIOUS session is excluded by its own ET day",
          "prev_day" not in got, str(got))
    check("W2b a row from a LATER session is excluded too",
          "next_day" not in got, str(got))
    check("W2c so the range holds exactly its own two rows",
          got == ["late_push", "same_day"], str(got))

    # ══ 🔴 W3 — DST. `_et_offset()` APPLIES TODAY'S OFFSET TO EVERY ROW ═══
    # — right for eight months, an hour wrong for four, which is the trap its
    # own docstring warns about one level up. A row at 00:30 UTC on 2026-11-03
    # is still 2026-11-02 in ET; a filter using September's offset would place
    # it on the wrong day. Converting per row on its own terms is exact.
    NOV, NOV_NEXT = "2026-11-02", "2026-11-03"
    late_nov = datetime(2026, 11, 3, 0, 30, tzinfo=ZoneInfo("UTC")).timestamp()
    store2 = {
        f"raw/derived_plan_check/dt={NOV_NEXT}/sym=QQQ/e.json": _obj(
            [dict(_row(NOV, "across_dst"), ts_epoch=late_nov)]),
    }
    WR._client = lambda *a, **k: _S3(store2)
    c2 = WC.WarehouseCache("t_dst")
    c2.load("plan_check", [NOV], NEED, syms=["QQQ"])
    n2 = c2.query('SELECT COUNT(*) n FROM "plan_check"')[0]["n"]
    check("W3 a row at 00:30 UTC belongs to the previous ET day, across a DST "
          "boundary", n2 == 1,
          f"{n2} — ET day was {__import__('ettime').et_day(late_nov)}")

    # ══ W4 — RAW STREAMS DO NOT SCAN FORWARD ═════════════════════════════
    # ⚠️ `candles`, `ohlc` and friends are partitioned by the day they DESCRIBE,
    # so a forward scan there would pull genuinely later sessions in. The
    # window is a derived-only correction.
    store3 = {
        f"raw/candles/dt={DAY}/sym=QQQ/f.json": _obj([{"c": 1, "ts_epoch": _ts(DAY)}]),
        f"raw/candles/dt={NEXT}/sym=QQQ/g.json": _obj([{"c": 2, "ts_epoch": _ts(NEXT)}]),
    }
    WR._client = lambda *a, **k: _S3(store3)
    c3 = WC.WarehouseCache("t_raw")
    c3.load("candles", [DAY], ["c", "ts_epoch"], datatype="candles", syms=["QQQ"])
    n3 = c3.query('SELECT COUNT(*) n FROM "candles"')[0]["n"]
    check("W4 a RAW stream is not forward-scanned", n3 == 1, f"{n3}")

    print()
    if FAILED:
        print(f"RED — {len(FAILED)} failed: {', '.join(FAILED)}")
        return 1
    print("GREEN — 8 checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
