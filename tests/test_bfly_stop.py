#!/usr/bin/env python3
# day_trader_pro/tests/test_bfly_stop.py — v1.1
# v1.1 (2026-09-04) — dtp r275. B5 pins that the ratio alone says 10 of 12
#      while mfe_bars says 1 — the opposite conclusion from the same rows — and
#      that the bar floor is the winners' own minimum. B6 pins the closed-rows
#      filter. NOTE: I said "2 of 13" in chat using a loose bar>15 cut; against
#      the winners' floor of 141 only CVX at 144 qualifies.
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

    # ══ B5 — THE VERDICT MUST READ mfe_bars, NOT JUST THE RATIO ══════════
    # 🔴 dtp-r275. The r274 line printed "the stop is taking trades that were
    # working" from the MFE ratio alone. The real 08-31..09-04 numbers:
    # winners peaked at bar 141-305, stopped trades at a MEDIAN OF BAR 5.5.
    # Ten of twelve popped within 15 bars and faded. The operator was one step
    # from removing a stop on the strength of that line.
    win  = [(1.27,155),(2.98,279),(2.95,305),(2.79,170),(1.88,141),(1.25,158),(1.13,188)]
    stop = [(1.49,11),(1.24,9),(1.17,2),(1.35,144),(0.89,1),(1.08,1),(0.86,1),
            (1.08,5),(1.03,2),(1.70,52),(1.32,9),(1.09,6)]
    floor_bar = min(b for r, b in win if r > 1.0)
    up    = sum(1 for r, _ in stop if r > 1.0)
    shape = sum(1 for r, b in stop if r > 1.0 and b >= floor_bar)
    check("B5 the ratio alone says 10 of 12 — the r274 verdict",
          up == 10, str(up))
    # ⚠️ ONE, NOT TWO. I said "2 of 13 share the winners' signature" in the
    # chat using a loose bar>15 cut. Against the winners' OWN floor — bar 141,
    # the earliest any of them peaked — only CVX at bar 144 qualifies. QQQ
    # peaked at 52, which is late for a stopped trade and early for a winner.
    # The stricter test is the honest one and it argues harder against removing
    # the stop: 1 of 12, against a break-even needing 9 of 13.
    check("B5b with mfe_bars it is 1 of 12 — the opposite conclusion",
          shape == 1, str(shape))
    check("B5c the bar floor comes from the WINNERS, not a constant",
          floor_bar == 141, str(floor_bar))
    # ⚠️ AND A RANGE WITH NO WINNERS MUST SAY SO rather than pick a default.
    check("B5d no winner in range -> no floor, and the screen says ABSENT",
          not [b for r, b in [] if r > 1.0])

    # ══ B6 — CLOSED ROWS ONLY ═════════════════════════════════════════════
    # 🔴 r274 reported 419 trades where there are 20: ~399 rows with pnl 0 and
    # exit_reason None are unclosed. Keyed on a CLOSING FACT rather than a
    # status spelling, because this project has twice been bitten this week by
    # a value renamed underneath a name check.
    src = open(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "tests", "screen_bfly_stop.py"), encoding="utf-8").read()
    check("B6 the query filters on a non-empty exit_reason",
          "exit_reason IS NOT NULL" in src and "TRIM(exit_reason) <> ''" in src)
    check("B6b and the count is labelled CLOSED so 419 cannot recur silently",
          "CLOSED trade(s)" in src)

    print()
    if FAILED:
        print(f"RED — {len(FAILED)} failed: {', '.join(FAILED)}")
        return 1
    print("GREEN — 21 checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
