#!/usr/bin/env python3
"""day_trader_pro/tests/screen_plan_gates.py — v1.0
v1.0  2026-09-04 — dtp r270. EVERY RUNG, PASS **AND** FAIL, FROM S3.

🔴 WHY THIS EXISTS. `gate_disposition` records only the rung that REFUSED, so
the fit report's "where the refusals land" is a ranking among refusals — not a
failure RATE. I read 41% there as "geometry refuses 41% of the time" and it did
not: on 2026-09-03 `geometry` passed 761/761 on QQQ and 846/934 on SPX. A share
of refusals and a failure rate are different numbers and only one of them tells
you what is blocking a trade.

🔑 `plan_check` HAS BOTH ARMS, and r126b already pushes it to S3 — *"the only
record of the decision… the fit needs weeks."* So this runs with the FLEET DOWN
and reads whatever the warehouse holds, rather than needing boxes up.

⚠️ WHAT TO LOOK FOR: a rung at 100% FAIL. That is what `age` (761/761) and
`wing_r_best` (761/761) did to the sweep on 09-03, and both were fixed at r230
and r234. A rung near 100% that is NOT one of those is a blocker nobody has
found yet.

⚠️ AND EVERY SESSION BEFORE 2026-09-05 PREDATES r230-r234. This report tells
you what blocked a strategy THEN. It cannot tell you whether it fires now.

usage:  python3 tests/screen_plan_gates.py --from 2026-08-31 --to 2026-09-04
        python3 tests/screen_plan_gates.py --strat SweepCreditSpread
        (no --strat = every strategy, ranked by how blocked it is)
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)

import report_prompt as RP                                    # noqa: E402
import warehouse_cache as WCACHE                              # noqa: E402

ET = ZoneInfo("America/New_York")
# ⚠️ NO `symbol` HERE — `cache.load` injects it, and listing it again is a
# `duplicate column name` at table-create time. Caught on the first smoke run.
NEED = ["_rid", "ts_epoch", "strategy", "check_name", "verdict", "value"]


def main(argv):
    ap = argparse.ArgumentParser(description="plan_check rungs, pass and fail")
    ap.add_argument("--from", dest="d0")
    ap.add_argument("--to", dest="d1")
    ap.add_argument("--strat", dest="strat", default=None)
    ap.add_argument("--sym", dest="sym", default=None)
    a = ap.parse_args(argv[1:])
    t0 = datetime.now(ET)
    dates = RP.ask_dates(a.d0, a.d1)

    cache = WCACHE.WarehouseCache("plangates")
    try:
        n = cache.load("plan_check", dates, NEED)
    except Exception as exc:                                  # noqa: BLE001
        # ⚠️ AN UNREACHABLE BUCKET AND A SESSION WITH NO EVALUATIONS MUST NEVER
        # RENDER THE SAME. Say which, by name, and stop.
        print(f"SOURCE: s3 [plan_check] — 🔴 UNREADABLE: "
              f"{type(exc).__name__}: {exc}")
        return 1
    print(f"SOURCE: s3 [plan_check] — {n:,} row(s) over {len(dates)} date(s)")
    if not n:
        print("  🔴 NO ROWS. That is an ABSENT MEASUREMENT, not a null result —")
        print("     the boxes purge and rebuild their derived stores, so an")
        print("     older range may simply not be in the warehouse. Widen the")
        print("     range or check coverage before reading anything into it.")
        return 0

    where, args = [], []
    if a.strat:
        where.append("strategy = ?")
        args.append(a.strat)
    if a.sym:
        where.append("symbol = ?")
        args.append(a.sym)
    sql = ('SELECT strategy, check_name, verdict, COUNT(*) c,'
           ' MIN(value) lo, MAX(value) hi FROM plan_check')
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " GROUP BY strategy, check_name, verdict"

    # rung -> {verdict: (count, lo, hi)}
    book = defaultdict(lambda: defaultdict(dict))
    for r in cache.query(sql, args):
        book[r["strategy"]][r["check_name"]][str(r["verdict"] or "?")] = (
            r["c"], r["lo"], r["hi"])

    print()
    print("=" * 74)
    print(f"  PLAN GATES — pass AND fail   ({dates[0]} → {dates[-1]})")
    print("=" * 74)
    print("  A rung at 100% FAIL is a BLOCKER. A rung that never fails is not")
    print("  evidence of anything — it is a gate the tape never tested.")
    print()

    for strat in sorted(book, key=lambda s: -_blocked_score(book[s])):
        rows = book[strat]
        fired = _blocked_score(rows)
        print("─" * 74)
        print(f"  {strat}" + ("   🔴 has a 100%-FAIL rung" if fired >= 1.0 else ""))
        print("─" * 74)
        print(f"    {'rung':<22} {'pass':>8} {'fail':>8} {'fail%':>7}"
              f"  {'fail range':>22}")
        for rung in sorted(rows, key=lambda k: -_fail_rate(rows[k])):
            p = rows[rung].get("PASS", (0, None, None))[0]
            f, lo, hi = rows[rung].get("FAIL", (0, None, None))
            tot = p + f
            if not tot:
                continue
            rate = f / tot
            rng = (f"{lo:.4g} .. {hi:.4g}" if f and lo is not None else "")
            mark = " 🔴" if rate >= 0.999 else ""
            print(f"    {rung:<22} {p:>8,} {f:>8,} {rate:>6.0%}"
                  f"  {rng:>22}{mark}")
        print()

    print("=" * 74)
    print(f"  {(datetime.now(ET) - t0).total_seconds():.0f}s")
    print("  ⚠️ EVERY SESSION BEFORE 2026-09-05 PREDATES r230-r234. This says")
    print("     what blocked a strategy THEN, not whether it fires now.")
    return 0


def _fail_rate(v) -> float:
    p = v.get("PASS", (0,))[0]
    f = v.get("FAIL", (0,))[0]
    return (f / (p + f)) if (p + f) else 0.0


def _blocked_score(rows) -> float:
    """The worst rung's fail rate — what actually decides whether it can fire."""
    return max((_fail_rate(v) for v in rows.values()), default=0.0)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
