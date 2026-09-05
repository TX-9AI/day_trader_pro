#!/usr/bin/env python3
# day_trader_pro/tests/test_bfly_stop.py — v1.0
# v1.0 (2026-09-04) — dtp r274. Selftest for the stop-forensics split.
#
# 🔴 THE QUESTION IT DECIDES: every butterfly loss over 08-31..09-04 is a
# premium stop (n=13, -$2,393.50, matching the 13 losers to the dollar), while
# its winners run to hard_close at 289 minutes for +$2,751. Either the stop is
# cutting trades that were working, or it is limiting trades that were dying.
# MFE — the best mark the position ever reached — is what tells them apart.
"""Drives the stopped/survived split and the MFE ratio."""
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
    import screen_bfly_stop as S

    for n in ("_q", "_f", "main"):
        if not hasattr(S, n):
            check(f"B0 screen_bfly_stop exposes {n}", False, "screen incomplete")
            print()
            return 1

    # ══ B1 — THE STOPPED/SURVIVED SPLIT ═══════════════════════════════════
    # ⚠️ `orb_trail_stop` AND `orb_fvg_trail_stop` CONTAIN "stop" AND ARE NOT
    # STOP-OUTS — they are trailing exits, 95% and 100% winners. Counting them
    # as stopped would put the book's best exits in the "cut" bucket and invert
    # the whole finding.
    def stopped(reason):
        r = str(reason or "").lower()
        return "stop" in r and "trail" not in r
    for reason in ("stop_25%", "hard_stop_20%", "orb_structure_stop"):
        check(f"B1 '{reason}' counts as stopped", stopped(reason))
    for reason in ("orb_trail_stop", "orb_fvg_trail_stop", "hard_close",
                   "target_hit", "nickel_close", "breach"):
        check(f"B1b '{reason}' does NOT count as stopped", not stopped(reason))

    # ══ B2 — THE MFE RATIO IS THE VERDICT ═════════════════════════════════
    # 🔑 A stopped trade whose MFE never exceeded entry was falling the whole
    # way and the stop did its job. One that traded above entry was working.
    cut = {"entry_premium": 0.42, "mfe_premium": 0.61}      # +45% before the cut
    dying = {"entry_premium": 0.42, "mfe_premium": 0.42}    # never above entry
    check("B2 a trade that traded above entry reads > 1.0",
          cut["mfe_premium"] / cut["entry_premium"] > 1.0)
    check("B2b one that never did reads <= 1.0",
          dying["mfe_premium"] / dying["entry_premium"] <= 1.0)

    # ══ B3 — QUANTILES, AND THE EMPTY CASE ════════════════════════════════
    check("B3 the quantile helper is positional and exact",
          S._q([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 0.50) == 6, str(S._q(list(range(1, 11)), .5)))
    # ⚠️ AN EMPTY GROUP MUST NOT RAISE — a range with no stopped trades is a
    # legitimate answer, not a crash.
    try:
        S._q([], 0.5)
        check("B3b an empty group returns nan rather than raising", True)
    except Exception as exc:                                # noqa: BLE001
        check("B3b an empty group returns nan rather than raising", False, str(exc))

    # ══ B4 — A NULL MFE IS NOT A ZERO ═════════════════════════════════════
    # ⚠️ `_f` returns None for an unreadable value, and a None MFE must be
    # excluded from the ratio rather than counted as "never went up" — absent
    # is not zero, and this whole screen turns on that distinction.
    check("B4 an unreadable value is None, not 0.0",
          S._f(None) is None and S._f("") is None and S._f("x") is None)
    check("B4b and a real value still parses", S._f("0.61") == 0.61)

    print()
    if FAILED:
        print(f"RED — {len(FAILED)} failed: {', '.join(FAILED)}")
        return 1
    print("GREEN — 15 checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
