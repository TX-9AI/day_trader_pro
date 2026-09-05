#!/usr/bin/env python3
# day_trader_pro/tests/test_plan_gates.py — v1.3
# v1.3 (2026-09-04) — dtp r273. Q1d RE-DERIVED into Q2. It asserted a Python
#      guard (`len(vals) < 20`) that r273 moved into SQL; Q2 drives the real
#      window query and pins that 1,005 failures return FIVE rows, that a
#      5-failure rung never crosses the wire, and that the median is exact.
# v1.2 (2026-09-04) — dtp r272. Q1 pins the quantiles with two distributions
#      that share a range and give OPPOSITE answers — the case a min/max
#      cannot distinguish and the reason the panel exists.
# v1.1 (2026-09-04) — dtp r271. T1/T2 pin the PER-TICK grouping, including
#      the case that matters: a long and a short plan evaluated in the SAME
#      millisecond must not merge, because plan_check's key includes
#      `direction` and merging them would invent co-occurring failures.
# v1.0 (2026-09-04) — dtp r270. Selftest for screen_plan_gates' arithmetic.
#
# 🔴 THE DISTINCTION THIS SCREEN EXISTS FOR: `gate_disposition` records only
# the rung that REFUSED, so a share of refusals is NOT a failure rate. On
# 2026-09-03 `geometry` was 41% of the sweep's refusals AND passed 761/761 on
# QQQ. Both true, and only the second says whether it blocks anything.
"""Drives _fail_rate and _blocked_score with the corpus's own numbers."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FAILED = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        FAILED.append(name)


def main():
    sys.path.insert(0, os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests"))
    import screen_plan_gates as S

    # ⚠️ NAMED FAILURE, NOT AN AttributeError (r206/r212). At a HEAD without the
    # per-tick panel, T1/T2 would die on one traceback and "the checker
    # crashed" must not look like "the invariant is violated".
    for _n in ("TICK_KEY", "_per_tick"):
        if not hasattr(S, _n):
            check(f"T0 screen_plan_gates exposes {_n}", False,
                  "the per-tick panel is absent — nothing to drive")
            print()
            print("RED — 1 failed: per-tick panel absent")
            return 1

    # QQQ 2026-09-03, the sweep, straight off the plan board.
    rows = {
        "age":         {"FAIL": (761, 33.0, 48.0)},
        "wing_r_best": {"FAIL": (761, 0.0, 0.06)},
        "geometry":    {"PASS": (761, 705.11, 705.11)},
        "side_of_pool": {"PASS": (761, 5.7, 13.05)},
        "wing":        {"PASS": (596, 0, 0), "FAIL": (165, 0, 0)},
    }
    check("G1 a 100%-FAIL rung reads 1.00",
          abs(S._fail_rate(rows["age"]) - 1.0) < 1e-9)
    # 🔴 THE ONE THAT MATTERS: geometry was the TOP refusal in the fit report
    # and its failure rate here is ZERO. A refusal ranking is not a rate.
    check("G2 a rung that never failed reads 0.00 even if it tops a refusal "
          "ranking elsewhere", S._fail_rate(rows["geometry"]) == 0.0)
    check("G3 a mixed rung reads its real share",
          abs(S._fail_rate(rows["wing"]) - 165 / 761) < 1e-6,
          f"{S._fail_rate(rows['wing']):.4f}")
    # ⚠️ THE WORST RUNG DECIDES, not the average. A strategy with one 100%
    # blocker and nine clean gates cannot fire, and an average would hide that.
    check("G4 the blocked score is the WORST rung, not the mean",
          abs(S._blocked_score(rows) - 1.0) < 1e-9)
    check("G4b a strategy with no blocker scores below 1.00",
          S._blocked_score({"a": rows["geometry"], "b": rows["wing"]}) < 1.0)
    # ⚠️ A rung nothing evaluated must not read as passing.
    check("G5 an empty rung is 0.0, not a divide-by-zero",
          S._fail_rate({}) == 0.0 and S._blocked_score({}) == 0.0)

    # ══ T1 — THE PER-TICK SQL, DRIVEN ON A FIXTURE ═══════════════════════
    # 🔴 dtp-r271. Per-rung counts are across DIFFERENT ticks, so no
    # combination of them says whether any single evaluation had every gate
    # green. Only grouping on the tick key answers that.
    import sqlite3
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE plan_check (ts_epoch REAL, symbol TEXT,"
              " strategy TEXT, direction TEXT, check_name TEXT, verdict TEXT)")
    c.executemany("INSERT INTO plan_check VALUES (?,?,?,?,?,?)", [
        (1.0, "QQQ", "S", "put", "age", "PASS"),
        (1.0, "QQQ", "S", "put", "geometry", "PASS"),
        (2.0, "QQQ", "S", "put", "age", "PASS"),
        (2.0, "QQQ", "S", "put", "geometry", "FAIL"),
        (3.0, "QQQ", "S", "put", "age", "FAIL"),
        (3.0, "QQQ", "S", "put", "geometry", "FAIL"),
        # ⚠️ SAME MILLISECOND, OPPOSITE DIRECTION. plan_check's key includes
        # `direction`, so a long and a short plan evaluated in the same tick
        # must NOT merge — grouping without it would invent co-occurring
        # failures that never happened on one plan.
        (3.0, "QQQ", "S", "call", "age", "PASS"),
        (3.0, "QQQ", "S", "call", "geometry", "PASS"),
    ])
    K = S.TICK_KEY
    d = {int(r[1]): r[2] for r in c.execute(
        f"SELECT strategy, nf, COUNT(*) FROM (SELECT strategy,"
        f" SUM(CASE WHEN verdict='FAIL' THEN 1 ELSE 0 END) nf"
        f" FROM plan_check GROUP BY {K}) GROUP BY 1,2")}
    check("T1 a tick with every gate green counts as 0-fail",
          d.get(0) == 2, str(d))
    check("T1b the opposite-direction plan did NOT merge into the same tick",
          d.get(2) == 1 and d.get(0) == 2, str(d))
    only = {r[0]: r[1] for r in c.execute(
        f"SELECT pc.check_name, COUNT(*) FROM plan_check pc JOIN"
        f" (SELECT {K} FROM plan_check GROUP BY {K} HAVING"
        f" SUM(CASE WHEN verdict='FAIL' THEN 1 ELSE 0 END)=1) s"
        f" ON pc.ts_epoch=s.ts_epoch AND pc.symbol=s.symbol"
        f" AND pc.strategy=s.strategy AND pc.direction=s.direction"
        f" WHERE pc.verdict='FAIL' GROUP BY 1")}
    # 🔑 THE ACTIONABLE NUMBER: a rung failing 94% of the time may never be the
    # ONLY thing in the way, and a 30% rung might be, every time.
    check("T2 the sole failing rung on a one-away tick is named",
          only == {"geometry": 1}, str(only))

    # ══ Q1 — THE QUANTILES, WHICH A MIN/MAX CANNOT GIVE ══════════════════
    # 🔴 dtp-r272. Two distributions with the SAME range and opposite answers:
    # r234's bar sits at 0.15 on the old scale, so one of these mostly clears
    # it and the other mostly does not. A min/max reports them identically.
    def q(vals):
        v = sorted(vals)
        return [v[min(len(v) - 1, int(len(v) * f))]
                for f in (0.10, 0.25, 0.50, 0.75, 0.90)]
    low  = [0.0, 0.9841] + [0.02] * 98      # range 0..0.9841, median 0.02
    high = [0.0, 0.9841] + [0.60] * 98      # SAME range, median 0.60
    check("Q1 identical ranges, different medians",
          min(low) == min(high) and max(low) == max(high)
          and q(low)[2] != q(high)[2], f"{q(low)[2]} vs {q(high)[2]}")
    check("Q1b the low distribution stays below r234's 0.15 bar",
          q(low)[2] < 0.15 and q(low)[4] < 0.15, str(q(low)))
    check("Q1c and the high one clears it at every quantile above p10",
          q(high)[2] > 0.15 and q(high)[1] > 0.15, str(q(high)))
    # ══ Q2 — THE QUANTILES ARE COMPUTED IN SQL, AND EXACTLY ══════════════
    # 🔴 dtp-r273. The first cut SELECTed every FAIL value and the warehouse
    # cache refused it at 200,000 rows — correctly: `wing_r_best` alone has
    # 58,205. A window function ranks in sqlite and returns FIVE rows per rung.
    # ⚠️ AND THE 20-FAILURE FLOOR MOVED INTO THE QUERY, so a rung too small to
    # describe never crosses the wire at all.
    import sqlite3
    c2 = sqlite3.connect(":memory:")
    c2.execute("CREATE TABLE plan_check (strategy TEXT, check_name TEXT,"
               " verdict TEXT, value REAL)")
    big = [("S", "wing_r_best", "FAIL", i / 1000.0) for i in range(1000)]
    tiny = [("S", "tiny", "FAIL", 0.5)] * 5
    c2.executemany("INSERT INTO plan_check VALUES (?,?,?,?)", big + tiny)
    Q = ("WITH r AS (SELECT strategy, check_name, value,"
         " ROW_NUMBER() OVER (PARTITION BY strategy, check_name"
         "                    ORDER BY value) rn,"
         " COUNT(*) OVER (PARTITION BY strategy, check_name) n"
         " FROM plan_check WHERE verdict='FAIL' AND value IS NOT NULL)"
         " SELECT strategy, check_name, n, rn, value FROM r"
         " WHERE n >= 20 AND (rn = MAX(1, CAST(n*0.10 AS INTEGER))"
         " OR rn = MAX(1, CAST(n*0.25 AS INTEGER))"
         " OR rn = MAX(1, CAST(n*0.50 AS INTEGER))"
         " OR rn = MAX(1, CAST(n*0.75 AS INTEGER))"
         " OR rn = MAX(1, CAST(n*0.90 AS INTEGER)))"
         " ORDER BY strategy, check_name, rn")
    got = list(c2.execute(Q))
    check("Q2 1,005 failures return 5 rows, not 1,005",
          len(got) == 5, str(len(got)))
    check("Q2b the rung with 5 failures never crosses the wire",
          not any(g[1] == "tiny" for g in got))
    check("Q2c the median is the real median, not an approximation",
          abs(got[2][4] - 0.499) < 0.002, str(got[2][4]))
    check("Q2d and the SCREEN uses this query, not a materialising SELECT",
          "ROW_NUMBER() OVER" in open(os.path.join(
              os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
              "tests", "screen_plan_gates.py"), encoding="utf-8").read())

    print()
    if FAILED:
        print(f"RED — {len(FAILED)} failed: {', '.join(FAILED)}")
        return 1
    print("GREEN — 16 checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
