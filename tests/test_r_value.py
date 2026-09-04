#!/usr/bin/env python3
# day_trader_pro/tests/test_r_value.py — v1.0
# v1.0 (2026-09-04) — dtp r268. R AND CAPITAL AT RISK, one definition for both
#      reports. Operator, 2026-09-04: the roll-up wants an R value and the
#      per-trade list wants R plus the capital that was at risk.
#
# 🔴 THE DENOMINATOR IS THE STRUCTURE'S MAX LOSS, NOT THE STOP'S. Stops run
# 15-27% depending on strategy and exit reason, so measuring against them would
# give a different denominator per row and make the column incomparable across
# strategies. Max loss is the same question for every trade.
"""Selftest for capital_at_risk / r_value and the widened trade line."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FAILED = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        FAILED.append(name)


def main():
    import trade_report as T

    # ══ D1 — a DEBIT risks the premium paid ═══════════════════════════════
    # MU 2026-09-04: 27 contracts at 2.75, +$1,080.
    d = {"contracts": 27, "entry_premium": 2.75, "pnl_usd": 1080.0,
         "spread_width": 0}
    check("D1 debit risk is premium x contracts x 100",
          T.capital_at_risk(d) == 7425.0, str(T.capital_at_risk(d)))
    check("D1b and R is P&L over that", abs(T.r_value(d) - 0.1454) < 0.001)

    # ══ D2 — a CREDIT VERTICAL risks (width - credit) ═════════════════════
    # 🔴 The case a single formula gets wrong. UNH TCS: 2 spreads, $0.79 credit
    # on $4.00 of width — risk is $642, NOT the $158 of credit received.
    c = {"contracts": 2, "entry_premium": 0.79, "pnl_usd": -2.0,
         "spread_width": 4.0}
    check("D2 credit risk is (width - credit) x contracts x 100",
          abs(T.capital_at_risk(c) - 642.0) < 0.01, str(T.capital_at_risk(c)))

    # ══ D3 — UNPRICEABLE IS None, NEVER ZERO ══════════════════════════════
    # ⚠️ A zero denominator would render as an infinite R, and an unknown risk
    # is not a free trade.
    for bad in ({"contracts": 0, "entry_premium": 2.0},
                {"contracts": 5, "entry_premium": 0},
                {"contracts": 5, "entry_premium": None}):
        if T.capital_at_risk(bad) is not None:
            check("D3 an unpriceable trade returns None", False, str(bad))
            break
    else:
        check("D3 an unpriceable trade returns None", True)
    check("D3b and its R is None too, not 0.0",
          T.r_value({"contracts": 0, "entry_premium": 2.0, "pnl_usd": 5}) is None)

    # ══ D4 — a width SMALLER than the premium is a debit, not a credit ════
    # ⚠️ A butterfly carries a spread_width and pays a DEBIT. Keying on
    # "has a width" would flip its sign; the test is width > premium.
    b = {"contracts": 4, "entry_premium": 1.10, "pnl_usd": 692.0,
         "spread_width": 1.0}
    # ⚠️ TOLERANCE, NOT EQUALITY — 1.10 * 4 * 100 is 440.00000000000006 in
    # binary floating point. An exact-equality assertion on money is a check
    # that fails for arithmetic reasons rather than behavioural ones.
    check("D4 width <= premium is treated as a debit",
          abs(T.capital_at_risk(b) - 440.0) < 0.01, str(T.capital_at_risk(b)))

    # ══ D5 — the money format is always five characters ═══════════════════
    # The column budget depends on it: the line went 45 -> 62 and a sixth
    # character would push the widest table in the report.
    for v in (34750, 7425, 675, 0.4, None):
        s = T._money(v)
        if len(s) != 5:
            check("D5 _money is always 5 chars", False, f"{v!r} -> {s!r}")
            break
    else:
        check("D5 _money is always 5 chars", True)

    print()
    if FAILED:
        print(f"RED — {len(FAILED)} failed: {', '.join(FAILED)}")
        return 1
    print("GREEN — 7 checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
