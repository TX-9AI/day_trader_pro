#!/usr/bin/env python3
"""day_trader_pro/tests/screen_plan_gates.py — v1.1
v1.1  2026-09-04 — dtp r271. PER-TICK: DID ANY SINGLE EVALUATION CLEAR EVERY
      GATE? The per-rung panel below cannot answer that and I over-read it —
      "wing_r_best passed 3,436 times" and "age passed 14,850 times" are counts
      across DIFFERENT ticks, so no combination of them says whether one
      evaluation ever had everything green at once. That is the only question
      that explains ZERO trades.
      🔑 GROUPED ON (ts_epoch, symbol, strategy, direction) — plan_check's own
      primary key. `direction` is in it because a long and a short plan can be
      evaluated in the same millisecond, and merging them would invent
      co-occurring failures that never happened on one plan.
      🔑 AND IT NAMES THE SOLE FAILING RUNG on ticks that were ONE gate short —
      the actionable number, because a rung failing 94% of the time may never
      be the ONLY thing in the way while a 30% rung might be, every time.
      ⚠️ `plan_tick` ANSWERS IT DIRECTLY TOO: a TAKE with no trade behind it
      means the refusal is DOWNSTREAM of the plan, in `_can_open_credit_spread`
      or `has_blocking_position`, neither of which writes a rung.
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
NEED = ["_rid", "ts_epoch", "strategy", "check_name", "verdict", "value",
        "direction"]
# ⚠️ dtp-r271 — `direction` IS PART OF THE TICK KEY. plan_check's primary key is
# (ts_epoch, symbol, strategy, direction, check_name), so grouping without it
# would merge a long plan and a short plan evaluated in the same millisecond
# into one tick and invent failures that never co-occurred.
TICK_KEY = "ts_epoch, symbol, strategy, direction"
NEED_TICK = ["_rid", "ts_epoch", "strategy", "verdict", "direction", "r_now"]


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

    _per_tick(cache, a, dates)

    print("=" * 74)
    print(f"  {(datetime.now(ET) - t0).total_seconds():.0f}s")
    print("  ⚠️ EVERY SESSION BEFORE 2026-09-05 PREDATES r230-r234. This says")
    print("     what blocked a strategy THEN, not whether it fires now.")
    return 0


def _per_tick(cache, a, dates) -> None:
    """The question the per-rung view CANNOT answer.

    🔴 dtp-r271 — PER-RUNG COUNTS ARE ACROSS DIFFERENT TICKS. "wing_r_best
    passed 3,436 times" and "age passed 14,850 times" say nothing about whether
    those were the SAME ticks, so no combination of them tells you whether any
    single evaluation ever had every gate green at once. That is the only
    question that explains zero trades, and it is answered by grouping on the
    tick key rather than on the rung.
    ⚠️ AND `plan_tick` ANSWERS IT DIRECTLY. It records one verdict per tick, so
    a TAKE with no trade behind it means the refusal is DOWNSTREAM of the plan —
    in `_can_open_credit_spread` or `has_blocking_position`, neither of which
    writes a rung. A DECLINE means the plan itself never qualified.
    """
    try:
        n = cache.load("plan_tick", dates, NEED_TICK)
    except Exception:                                          # noqa: BLE001
        n = 0
    print("=" * 74)
    print("  PER-TICK — did any single evaluation clear EVERY gate?")
    print("=" * 74)

    where = " WHERE strategy = ?" if a.strat else ""
    args = [a.strat] if a.strat else []
    if a.sym:
        where = (where + " AND symbol = ?") if where else " WHERE symbol = ?"
        args.append(a.sym)

    # ── how many rungs failed on each tick ────────────────────────────────
    sql = (f"SELECT strategy, nf, COUNT(*) c FROM (SELECT strategy,"
           f" SUM(CASE WHEN verdict='FAIL' THEN 1 ELSE 0 END) nf"
           f" FROM plan_check{where} GROUP BY {TICK_KEY}) GROUP BY 1,2")
    dist = defaultdict(dict)
    for r in cache.query(sql, args):
        dist[r["strategy"]][int(r["nf"])] = r["c"]

    for strat in sorted(dist):
        d = dist[strat]
        clean = d.get(0, 0)
        one_ = d.get(1, 0)
        tot = sum(d.values())
        print()
        print("─" * 74)
        print(f"  {strat}")
        print("─" * 74)
        print(f"    ticks evaluated        {tot:>9,}")
        print(f"    EVERY gate passed      {clean:>9,}"
              + ("   🔴 the plan qualified — anything refusing it is DOWNSTREAM"
                 if clean else "   (never — the block is IN the gates)"))
        print(f"    exactly one gate short {one_:>9,}"
              + ("   <- the cheapest thing to move" if one_ else ""))
        for k in sorted(x for x in d if x >= 2)[:3]:
            print(f"    {k} gates short          {d[k]:>9,}")

        # ── WHICH rung, on the ticks that were one away ───────────────────
        # 🔑 THE ACTIONABLE NUMBER. A rung with a 94% failure rate may never be
        # the ONLY thing standing in the way; a rung with a 30% rate might be,
        # every time. Only this join can tell them apart.
        if one_:
            q = (f"SELECT pc.check_name k, COUNT(*) c FROM plan_check pc JOIN"
                 f" (SELECT {TICK_KEY} FROM plan_check{where} GROUP BY"
                 f" {TICK_KEY} HAVING SUM(CASE WHEN verdict='FAIL' THEN 1 ELSE 0"
                 f" END)=1) s ON pc.ts_epoch=s.ts_epoch AND pc.symbol=s.symbol"
                 f" AND pc.strategy=s.strategy AND pc.direction=s.direction"
                 f" WHERE pc.verdict='FAIL' AND pc.strategy=?"
                 f" GROUP BY 1 ORDER BY 2 DESC LIMIT 6")
            print("    the ONLY failing rung on those ticks:")
            for r in cache.query(q, args + [strat]):
                print(f"      {r['k']:<24} {r['c']:>9,}"
                      f"  {r['c']/one_:>5.0%} of them")

    # ── and the plan's own verdict, which needs no inference ──────────────
    if n:
        print()
        print("─" * 74)
        print("  plan_tick VERDICTS (the plan's own answer, per tick)")
        print("─" * 74)
        vs = (f"SELECT strategy, verdict, COUNT(*) c FROM plan_tick{where}"
              f" GROUP BY 1,2 ORDER BY 1,3 DESC")
        for r in cache.query(vs, args):
            mark = "  🔴 TAKE with no trade => refused DOWNSTREAM" \
                if str(r["verdict"]).upper() == "TAKE" else ""
            print(f"    {r['strategy']:<24} {str(r['verdict']):<10}"
                  f" {r['c']:>9,}{mark}")
    else:
        print()
        print("  ⚠️ plan_tick unavailable for this range — the per-rung and")
        print("     per-tick panels above still stand; only the plan's own")
        print("     verdict is missing. ABSENT, not zero.")


def _fail_rate(v) -> float:
    p = v.get("PASS", (0,))[0]
    f = v.get("FAIL", (0,))[0]
    return (f / (p + f)) if (p + f) else 0.0


def _blocked_score(rows) -> float:
    """The worst rung's fail rate — what actually decides whether it can fire."""
    return max((_fail_rate(v) for v in rows.values()), default=0.0)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
