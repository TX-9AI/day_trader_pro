#!/usr/bin/env python3
# day_trader_pro/tests/test_r_value.py — v1.2
# v1.2 (2026-09-26) — dtp r451 / RPT.33. E2 WAS BUILT FROM A BELIEF, NOT FROM A
#      ROW. It asserted winners carry no stop percentage using BARE reasons
#      ("orb_trail_stop", "target_hit"), but every real row carries a suffix —
#      "orb_trail_stop pnl=55.0%" — so the unanchored regex read the P&L as a
#      stop and the check could not see it (§0.4). E4 uses REAL reason strings,
#      copied verbatim from the banked fleet corpus on 2026-09-26, and E1e pins
#      that a real stop reason still resolves to its stop, not its pnl.
# v1.1 (2026-09-04) — dtp r269. MODIFIED R, ON THE STOP THAT ACTUALLY ENDED
#      THE TRADE. E1-E3 added: the exit reason's own percentage is the
#      denominator, a winner has no percentage and must not be given one, and
#      a nonsense percentage is refused. E1c is the one that matters — a
#      stopped trade can report WORSE than -1.00, which is the stop
#      overshooting, and max-loss R hid that completely.
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

    # ══ E1 — THE STOP THAT ACTUALLY ENDED THE TRADE ═══════════════════════
    # 🔴 dtp-r269. Operator: compute R on that, not the entry floor and not max
    # loss. The exit reasons carry the number.
    st = {"contracts": 190, "entry_premium": 0.06, "pnl_usd": -475.0,
          "spread_width": 0, "exit_reason": "hard_stop_20%"}
    check("E1 the exit reason's percentage is read",
          abs(T.stop_pct_from_exit(st) - 0.20) < 1e-9)
    check("E1b risk is that percentage of the premium, not the whole premium",
          abs(T.risk_taken(st) - 228.0) < 0.01, str(T.risk_taken(st)))
    # 🔴 THE FINDING THIS EXISTS TO SURFACE: a stop can overshoot. A 2-cent slip
    # on a 6-cent option IS 33%, so a 20% stop cost 2.08x its intended risk.
    check("E1c an overshooting stop reports worse than -1.00",
          T.modified_r(st) < -2.0, f"{T.modified_r(st):.2f}")
    check("E1d and the basis says the exit stop set it", T._r_basis(st) == "x")

    # ══ E2 — A WINNER HAS NO STOP PERCENTAGE, AND MUST NOT BE GIVEN ONE ═══
    # ⚠️ `target_hit`, `orb_trail_stop`, `hard_close`, `nickel_close` carry no
    # number. Inventing one would make every winner's R a fiction.
    for reason in ("target_hit", "orb_trail_stop", "hard_close", "nickel_close",
                   "orb_structure_stop", "breach"):
        if T.stop_pct_from_exit({"exit_reason": reason}) is not None:
            check("E2 a non-stop exit yields no percentage", False, reason)
            break
    else:
        check("E2 a non-stop exit yields no percentage", True)
    win = {"contracts": 27, "entry_premium": 2.75, "pnl_usd": 1080.0,
           "spread_width": 0, "exit_reason": "orb_trail_stop",
           "stop_premium": 2.06}
    check("E2b a winner falls back to its ENTRY-TIME floor, basis 's'",
          T._r_basis(win) == "s" and abs(T.risk_taken(win) - 1863.0) < 1.0,
          f"{T._r_basis(win)} {T.risk_taken(win):.0f}")
    bare = {"contracts": 50, "entry_premium": 6.95, "pnl_usd": 2500.0,
            "spread_width": 0, "exit_reason": "target_hit"}
    check("E2c with neither recorded it falls back to MAX LOSS, basis 'm'",
          T._r_basis(bare) == "m" and T.risk_taken(bare) == 34750.0)

    # ══ E3 — A NONSENSE PERCENTAGE IS REFUSED ═════════════════════════════
    # ⚠️ 0% and 100%+ are not stops. Either would produce an infinite or
    # inverted R rather than a wrong-but-plausible one.
    check("E3 0% and 100% are rejected",
          T.stop_pct_from_exit({"exit_reason": "hard_stop_0%"}) is None
          and T.stop_pct_from_exit({"exit_reason": "x_100%"}) is None)

    # ══ E4 — REAL REASONS FROM THE CORPUS (r451). A winner's pnl= is NOT a stop ══
    # Copied verbatim from reports/warehouse/fleet_trades_2026-*.json. Each of
    # these read as a STOP before r451, so every such winner scored exactly
    # +1.00R: its own profit divided by itself.
    real_not_stop = (
        "orb_trail_stop pnl=55.0%",
        "orb_fvg_trail_stop pnl=298.1%",
        "target_hit pnl=111.6%",
        "nickel_close pnl=91.8%",
        "breach: 1m close 7630.12 through 7627.87 pnl=-2.0%",
        "structure_stop: 1m close 13.51 through 13.51 pnl=-18.2%",
        "exhaustion: new short extreme on weaker momentum — continuing on fumes pnl=-8.3%",
        "orb_stop_respected: 378.55 is beyond the low stop 378.63 by more than 50% of the 0.12 stop it was sized on",
        "volt_trail_stop: 1m close 13.47 through the 50% lock 13.46 (armed at 0.5R, peak 13.42)",
    )
    wrong = [r for r in real_not_stop if T.stop_pct_from_exit({"exit_reason": r}) is not None]
    check("E4 no real non-stop reason yields a stop percentage", not wrong,
          f"read as a stop: {wrong[:3]}")
    real_stop = {"hard_stop_25% pnl=-25.9%": 0.25, "stop_24% pnl=-27.4%": 0.24,
                 "premium_stop_15% pnl=-22.2%": 0.15}
    bad = {r: T.stop_pct_from_exit({"exit_reason": r}) for r, want in real_stop.items()
           if T.stop_pct_from_exit({"exit_reason": r}) != want}
    check("E1e a real stop reason resolves to its STOP, not its pnl", not bad, f"{bad}")
    tw = {"contracts": 10, "entry_premium": 1.00, "pnl_usd": 550.0, "spread_width": 0,
          "exit_reason": "orb_trail_stop pnl=55.0%", "stop_premium": 0.75}
    check("E4b a real trail-stop winner is measured on its entry floor, not +1.00R",
          T._r_basis(tw) == "s" and abs(T.modified_r(tw) - 2.2) < 1e-9,
          f"basis={T._r_basis(tw)} R={T.modified_r(tw)}")

    print()
    if FAILED:
        print(f"RED — {len(FAILED)} failed: {', '.join(FAILED)}")
        return 1
    print("GREEN — 14 checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
