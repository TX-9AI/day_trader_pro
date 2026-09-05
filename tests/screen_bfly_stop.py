#!/usr/bin/env python3
"""day_trader_pro/tests/screen_bfly_stop.py — v1.0
v1.0  2026-09-04 — dtp r274. DID THE BUTTERFLY'S STOP CUT WINNERS OR LIMIT
      LOSERS? Operator, 2026-09-04: *"something about the losing nature of this
      trade doesn't sit well with me because I've seen us hold several all the
      way to the 1545 flatten deep in profit."*

🔴 THE FINDING THAT PROMPTED IT. Every one of the butterfly's 13 losses over
2026-08-31..09-04 is a premium stop — `stop_24%`/`stop_25%`/`stop_26%`, n=13,
-$2,393.50, matching the 13 losers to the dollar. It has never lost to the
market, only to its own stop, at a 16-26 minute hold — while its winners run to
`hard_close` at 289 minutes for +$2,751.

⚠️ WHY THAT IS NOT AUTOMATICALLY A DEFECT. A GEX pin butterfly is worth little
mid-session BY CONSTRUCTION: the wings have not decayed and the body has not
converged, so a -25% mark at minute 17 measures elapsed time, not the thesis.
But a butterfly stopped at -25% might equally have expired WORTHLESS. This
screen is the difference between "the stop destroyed a good trade" and "the
stop limited a bad one", and nothing in the trade breakdown can tell them apart.

🔑 WHAT DECIDES IT: `mfe_premium` — the best mark the position ever reached.
  • MFE ABOVE entry after the stop fired  -> the trade was recovering; the stop
    cut it. `mfe_bars` says WHEN, so a peak after the stop bar is decisive.
  • MFE never above entry                 -> it was falling the whole way and
    the stop did its job.
⚠️ AND THE COMPARISON GROUP IS THE POINT. The same numbers are printed for the
SURVIVORS, because a stopped trade's MFE means nothing without knowing what a
winner's looked like at the same age.

usage:  python3 tests/screen_bfly_stop.py --from 2026-08-31 --to 2026-09-04
        --strat defaults to GEXPinButterfly; pass another to reuse the shape.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)

import report_prompt as RP                                    # noqa: E402
import warehouse_cache as WCACHE                              # noqa: E402

ET = ZoneInfo("America/New_York")


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _q(vals, f):
    s = sorted(vals)
    return s[min(len(s) - 1, int(len(s) * f))] if s else float("nan")


def main(argv):
    ap = argparse.ArgumentParser(description="did the butterfly's stop cut winners?")
    ap.add_argument("--from", dest="d0")
    ap.add_argument("--to", dest="d1")
    ap.add_argument("--strat", dest="strat", default="GEXPinButterfly")
    a = ap.parse_args(argv[1:])
    t0 = datetime.now(ET)
    dates = RP.ask_dates(a.d0, a.d1)

    cache = WCACHE.WarehouseCache("bflystop")
    try:
        n = cache.load("trades", dates, RP.COLS, datatype="trades")
    except Exception as exc:                                  # noqa: BLE001
        print(f"SOURCE: s3 [trades] — 🔴 UNREADABLE: {type(exc).__name__}: {exc}")
        return 1
    print(f"SOURCE: s3 [trades] — {n:,} row(s) over {len(dates)} date(s)")

    rows = cache.query(
        "SELECT symbol, entry_time, entry_premium, exit_premium, contracts,"
        " pnl_usd, exit_reason, mfe_premium, mfe_bars, mae_premium, mae_bars"
        " FROM trades WHERE strategy = ? ORDER BY entry_time", [a.strat])
    if not rows:
        # ⚠️ ABSENT, NOT ZERO. No rows for this strategy in this range is a
        # coverage statement, not a finding about the strategy.
        print(f"  🔴 NO {a.strat} ROWS in this range — that is an ABSENT")
        print("     MEASUREMENT, not a null result. Widen the range.")
        return 0

    stopped, survived = [], []
    for r in rows:
        (stopped if "stop" in str(r["exit_reason"] or "").lower()
         and "trail" not in str(r["exit_reason"] or "").lower()
         else survived).append(r)

    print()
    print("=" * 74)
    print(f"  {a.strat} — DID THE STOP CUT WINNERS OR LIMIT LOSERS?")
    print("=" * 74)
    print(f"  {len(rows)} trade(s):  {len(stopped)} stopped out,"
          f" {len(survived)} reached another exit")
    print()
    print("  MFE is the BEST mark the position ever reached. On a stopped")
    print("  trade, MFE above entry means it was working before it was cut.")
    print()

    for label, group in (("STOPPED OUT", stopped), ("SURVIVED", survived)):
        if not group:
            continue
        print("─" * 74)
        print(f"  {label}  (n={len(group)})")
        print("─" * 74)
        print(f"    {'sym':<5} {'entry':>6} {'exit':>6} {'MFE':>7} {'MFE/entry':>10}"
              f" {'MFEbar':>7} {'MAE':>7} {'pnl':>8}  reason")
        recovered = 0
        ratios = []
        for r in group:
            e = _f(r["entry_premium"]) or 0.0
            mfe = _f(r["mfe_premium"])
            ratio = (mfe / e) if (mfe is not None and e > 0) else None
            if ratio is not None:
                ratios.append(ratio)
                if ratio > 1.0:
                    recovered += 1
            print(f"    {str(r['symbol'])[:5]:<5} {e:>6.2f}"
                  f" {_f(r['exit_premium']) or 0:>6.2f}"
                  f" {(mfe if mfe is not None else float('nan')):>7.2f}"
                  f" {(ratio if ratio is not None else float('nan')):>10.2f}"
                  f" {_f(r['mfe_bars']) or 0:>7.0f}"
                  f" {_f(r['mae_premium']) or 0:>7.2f}"
                  f" {_f(r['pnl_usd']) or 0:>8.0f}  {str(r['exit_reason'])[:22]}")
        if ratios:
            print(f"    MFE/entry   p10 {_q(ratios,.10):.2f}   median"
                  f" {_q(ratios,.50):.2f}   p90 {_q(ratios,.90):.2f}")
            print(f"    🔑 {recovered}/{len(ratios)} ever traded ABOVE their entry")
        print()

    # ── THE VERDICT, STATED IN ONE LINE AND NOT INFERRED BY THE READER ────
    sr = [(_f(r["mfe_premium"]) or 0) / (_f(r["entry_premium"]) or 1)
          for r in stopped if _f(r["entry_premium"])]
    up = sum(1 for x in sr if x > 1.0)
    print("=" * 74)
    if sr and up >= max(1, len(sr) // 2):
        print(f"  🔴 {up} of {len(sr)} STOPPED trades traded ABOVE entry before")
        print("     being cut. The stop is taking trades that were working.")
    elif sr:
        print(f"  ✅ only {up} of {len(sr)} stopped trades ever traded above")
        print("     entry. The stop is limiting losers, not cutting winners.")
    print("  ⚠️ MFE is the best mark REACHED, not a guarantee it would have")
    print("     held to 15:45. It bounds the question, it does not settle it.")
    print(f"  {(datetime.now(ET) - t0).total_seconds():.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
