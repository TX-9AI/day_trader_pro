"""
day_trader_pro/tests/test_trade_report.py — v1.0 — 2026-08-03

Guards the v1.4 additions. Both exist because a number rendered cleanly while
meaning something else: an exit reason's cumulative N that was really one
session, and a "runners cut early" verdict computed over flicker exits.

Run:
  cd ~/day_trader_pro && PYTHONPATH=. ~/options-trader-v3/venv/bin/python \
      -m pytest tests/test_trade_report.py -q
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import trade_report as tr  # noqa: E402


def t(reason, date, pnl=10.0, hold=8.0):
    return {"exit_reason": reason, "_date": date, "pnl_usd": pnl,
            "_hold": hold, "entry_premium": 1.0,
            "max_premium_seen": 1.3, "min_premium_seen": 0.9}


# ── exit concentration ──────────────────────────────────────────────────────

def test_single_session_exit_is_flagged():
    """The bos_exit shape: every trade on one date across a nine-day window."""
    trades = [t("bos_exit pnl=-9.0%", "2026-08-03") for _ in range(21)]
    trades += [t("continuation_trail", f"2026-07-{d:02d}") for d in range(24, 32)]
    conc = tr.exit_concentration(trades, min_n=8)
    assert conc["bos_exit"]["single_session"] is True
    assert conc["bos_exit"]["sessions"] == 1
    assert conc["bos_exit"]["top_share"] == 1.0
    assert conc["continuation_trail"]["single_session"] is False


def test_spread_exit_is_not_flagged():
    trades = [t("continuation_trail", f"2026-07-{d:02d}") for d in range(24, 32)
              for _ in range(6)]
    conc = tr.exit_concentration(trades, min_n=8)
    assert conc["continuation_trail"]["sessions"] == 8
    assert conc["continuation_trail"]["single_session"] is False


def test_thin_reason_is_never_called_single_session():
    """n below the floor is underpowered, not a finding."""
    trades = [t("condor_tp", "2026-08-03") for _ in range(3)]
    conc = tr.exit_concentration(trades, min_n=8)
    assert conc["condor_tp"]["top_share"] == 1.0
    assert conc["condor_tp"]["single_session"] is False


def test_normalises_the_pnl_suffix_so_one_reason_is_one_row():
    trades = [t("bos_exit pnl=-9.0%", "2026-08-03"),
              t("bos_exit pnl=+2.0%", "2026-08-03")]
    conc = tr.exit_concentration(trades, min_n=8)
    assert list(conc) == ["bos_exit"] and conc["bos_exit"]["n"] == 2


# ── sub-minute contamination of the hold ratio ─────────────────────────────

def test_flicker_rows_are_counted_and_ratio_reported_both_ways():
    """44 of 88 rows on 2026-08-03 were sub-minute flicker, p25 12 seconds."""
    trades = [t("flip_exit (SOME_LABEL)", "2026-08-03", pnl=-1.0, hold=0.2)
              for _ in range(20)]
    trades += [t("flip_exit (SOME_LABEL)", "2026-08-03", pnl=1.0, hold=0.2)
               for _ in range(20)]
    trades += [t("continuation_trail", "2026-08-03", pnl=50.0, hold=30.0)
               for _ in range(10)]
    trades += [t("max_loss_floor_25pct", "2026-08-03", pnl=-25.0, hold=10.0)
               for _ in range(10)]
    eb = tr.exit_behaviour(trades)
    assert eb["sub_minute_rows"] == 40
    assert eb["sub_minute_share"] == 0.667
    assert eb["winner_loser_hold_ratio_ex_submin"] == 3.0, \
        "excluding flicker, winners are held 3x longer than losers"
    assert eb["winner_loser_hold_ratio"] != \
        eb["winner_loser_hold_ratio_ex_submin"], \
        "the two ratios must be distinguishable or the fix is cosmetic"


def test_clean_sample_reports_zero_sub_minute():
    trades = [t("continuation_trail", "2026-08-03", pnl=50.0, hold=30.0)
              for _ in range(10)]
    trades += [t("max_loss_floor_25pct", "2026-08-03", pnl=-25.0, hold=10.0)
               for _ in range(10)]
    eb = tr.exit_behaviour(trades)
    assert eb["sub_minute_rows"] == 0
    assert eb["sub_minute_share"] == 0.0
    assert eb["winner_loser_hold_ratio"] == \
        eb["winner_loser_hold_ratio_ex_submin"]


def test_original_ratio_and_flag_survive_unchanged():
    """v1.4 adds a second reading; it must not silently redefine the first."""
    trades = [t("bos_exit", "2026-08-03", pnl=5.0, hold=5.0) for _ in range(5)]
    trades += [t("bos_exit", "2026-08-03", pnl=-5.0, hold=5.0) for _ in range(5)]
    eb = tr.exit_behaviour(trades)
    assert eb["winner_loser_hold_ratio"] == 1.0
    assert eb["flag_runners_cut_early"] is True


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
