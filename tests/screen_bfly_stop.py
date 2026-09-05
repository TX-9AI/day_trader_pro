#!/usr/bin/env python3
"""day_trader_pro/tests/screen_bfly_stop.py — v1.1
v1.1  2026-09-04 — dtp r275. TWO FAULTS IN THE r274 CUT, BOTH MINE.
      (1) NO STATUS FILTER — it reported 419 GEXPinButterfly trades where there
      are 20, because ~399 unclosed rows with pnl 0 and exit_reason None sat in
      the SURVIVED group. Now keyed on a CLOSING FACT (a non-empty exit_reason)
      rather than a status spelling, and the count is labelled CLOSED so it
      cannot recur silently.
      (2) THE VERDICT READ THE MFE RATIO AND IGNORED `mfe_bars`. It printed
      "the stop is taking trades that were working" when the column beside it
      said the opposite: winners peaked at bar 141-305, stopped trades at a
      MEDIAN OF BAR 5.5. The operator was one step from removing a stop on the
      strength of that line.
      🔑 THE BAR FLOOR COMES FROM THE WINNERS, NOT FROM ME — a trade "was
      working" if it traded above entry AND peaked no earlier than the earliest
      winner in THIS sample. Hard-coding a threshold would be a number I chose.
      ⚠️ AND A RANGE WITH NO WINNERS SAYS SO rather than defaulting: absent is
      not evidence either way.
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
        # 🔴 dtp-r275 — CLOSED ROWS ONLY. The r274 cut had no status filter and
        # reported 419 GEXPinButterfly "trades" when there are 20: ~399 rows
        # with exit_premium 0.00, pnl 0 and exit_reason None are unclosed or
        # non-terminal. `RP.COLS` has carried `status` the whole time and the
        # screen never used it. The 13 stopped and 7 real winners were correct
        # and the quantiles were computed off real rows, so the FINDING stood —
        # but the counts were junk, and the next reader would have no narration
        # to save them.
        # ⚠️ KEYED ON A CLOSING FACT, NOT ON A STATUS SPELLING. A row with an
        # exit reason and an exit premium is a closed trade whatever the status
        # column happens to say, and this project has been bitten twice this
        # week by a value that was renamed underneath a name check.
        "SELECT symbol, entry_time, entry_premium, exit_premium, contracts,"
        " pnl_usd, exit_reason, mfe_premium, mfe_bars, mae_premium, mae_bars,"
        " status FROM trades WHERE strategy = ?"
        " AND exit_reason IS NOT NULL AND TRIM(exit_reason) <> ''"
        " ORDER BY entry_time", [a.strat])
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
    print(f"  {len(rows)} CLOSED trade(s):  {len(stopped)} stopped out,"
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
    # 🔴 dtp-r275 — THE VERDICT READS `mfe_bars` TOO, AND THE r274 LINE WAS
    # WRONG WITHOUT IT. It printed "the stop is taking trades that were
    # working" off the MFE ratio alone. The column beside it said otherwise:
    # winners peaked at bar 141-305, the stopped trades at a MEDIAN OF BAR 5.5
    # — ten of twelve within 15 bars at 1.03-1.49x and then faded. That is a
    # pop on entry noise, not a trade working toward the pin, and the operator
    # was one step from removing a stop on the strength of it.
    # 🔑 THE TEST IS THE WINNERS' OWN SHAPE, NOT A CONSTANT. A trade "was
    # working" if it traded above entry AND peaked no earlier than the winners
    # in THIS sample do. Hard-coding a bar threshold would be a number I chose;
    # the survivors define it.
    def _ratio(r):
        e = _f(r["entry_premium"])
        m = _f(r["mfe_premium"])
        return (m / e) if (e and m is not None) else None
    win_bars = sorted(_f(r["mfe_bars"]) or 0 for r in survived
                      if _ratio(r) and _ratio(r) > 1.0)
    floor_bar = win_bars[0] if win_bars else None
    sr = [(_ratio(r), _f(r["mfe_bars"]) or 0) for r in stopped
          if _ratio(r) is not None]
    up = sum(1 for x, _b in sr if x > 1.0)
    shape = sum(1 for x, b in sr
                if x > 1.0 and floor_bar is not None and b >= floor_bar)
    print("=" * 74)
    if not sr:
        print("  no stopped trade carried a readable MFE — nothing to judge.")
    elif floor_bar is None:
        print(f"  {up} of {len(sr)} stopped trades traded above entry, but NO")
        print("  survivor won in this range, so there is no shape to compare")
        print("  against. ABSENT, not evidence either way.")
    else:
        print(f"  {up} of {len(sr)} stopped trades traded ABOVE entry —")
        print(f"  but only {shape} peaked at or after bar {floor_bar:.0f}, which is the")
        print(f"  EARLIEST any winner in this sample peaked.")
        if shape >= max(1, len(sr) // 2):
            print("  🔴 the stop is cutting trades with the winners' shape.")
        else:
            print(f"  ✅ the other {up - shape} popped early and faded — a stop cutting")
            print("     an entry blip, not a trade that was working.")
    print("  ⚠️ MFE is the best mark REACHED, not a guarantee it would have")
    print("     held to 15:45. It bounds the question, it does not settle it.")
    print(f"  {(datetime.now(ET) - t0).total_seconds():.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
