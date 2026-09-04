#!/usr/bin/env python3
# day_trader_pro/tests/test_plan_gates.py — v1.0
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

    print()
    if FAILED:
        print(f"RED — {len(FAILED)} failed: {', '.join(FAILED)}")
        return 1
    print("GREEN — 6 checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
