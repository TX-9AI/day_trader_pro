#!/usr/bin/env python3
# day_trader_pro/tests/test_fit_rungs.py — v1.0
# v1.0 (2026-09-04) — dtp r267. TWO THINGS THE FIT REPORT GOT WRONG, both
#      visible in the 08-31..09-04 run and neither a data problem.
#
# 🔴 (1) ONE STRATEGY, TWO ROWS. otv4 stamped the raw `_safe_strategy` label
# on `strategy_note` while plans and gates used the class name, so the report
# showed "ORB" with 78 fired / ZERO declined and "ORBStrategy" with zero fired
# / 4,260 declined. NEITHER arm could ever be fittable, and the report said
# NOT READY for both, for opposite reasons.
#
# 🔴 (2) `manage` IS NOT AN ENTRY RUNG. It is the management path declining to
# act on an OPEN position, and it held 70% of the butterfly's refusals, 89% of
# the runaway's, and 100% of two others. The verdict then read "one rung
# dominates, so there is no surface to fit" — a true sentence about the wrong
# population, while the butterfly's real entry story sat underneath it.
"""Selftest for fit_readiness's label canonicalisation and rung split."""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FAILED = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        FAILED.append(name)


def main():
    import fit_readiness as F

    # ══ A1 — the alias merges the two ORB rows ════════════════════════════
    check("A1 ORB canonicalises to ORBStrategy", F.canon("ORB") == "ORBStrategy")
    check("A1b SweepForLeg2 -> SweepCreditSpread (r160's ruling)",
          F.canon("SweepForLeg2") == "SweepCreditSpread")
    check("A1c a name with no alias is unchanged",
          F.canon("RunawayContinuation") == "RunawayContinuation")
    # ⚠️ None must not become the string "None" and silently form a strategy.
    check("A1d an empty strategy stays empty", F.canon(None) == "")

    # ══ B1 — management is excluded from the ENTRY distribution ═══════════
    # The runaway's real shape: 1,461 manage against 189 entry refusals.
    rungs = Counter({"manage": 1461, "entry_window": 167, "contract": 12,
                     "stop_distance": 10})
    ent = F.entry_rungs(rungs)
    check("B1 manage is not an entry rung", "manage" not in ent)
    check("B1b and the entry rungs survive intact",
          sum(ent.values()) == 189 and len(ent) == 3, str(dict(ent)))

    # ══ B2 — THE VERDICT CHANGES, WHICH IS THE POINT ══════════════════════
    # 🔴 With manage included, the top rung is 89% and the verdict is "one rung
    # dominates". Over entry rungs the top is 167/189 = 88% — still dominant
    # here, but now that is a TRUE statement about `entry_window`, which is a
    # gate you can act on, rather than about a management tick you cannot.
    rec = {"fired": 202, "declined": 37412, "rungs": rungs}
    v, why = F.verdict(rec)
    check("B2 the verdict names an ENTRY rung, never 'manage'",
          "manage" not in why, why[:70])

    # ══ B3 — a strategy whose refusals are ALL management ═════════════════
    # IronCondorStrategy was 1,385 rungs, every one `manage`. Reporting that as
    # a dominant entry rung was the clearest case of the wrong population.
    rec2 = {"fired": 0, "declined": 1385, "rungs": Counter({"manage": 1385})}
    check("B3 an all-management strategy has NO entry rungs",
          F.entry_rungs(rec2["rungs"]) == {})

    print()
    if FAILED:
        print(f"RED — {len(FAILED)} failed: {', '.join(FAILED)}")
        return 1
    print("GREEN — 8 checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
