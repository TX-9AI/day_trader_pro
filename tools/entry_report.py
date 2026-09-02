#!/usr/bin/env python3
# day_trader_pro/tools/entry_report.py — v1.1
# v1.1 (2026-09-02) — dtp r247. The menu LOOPS off one pull, and 🔴 PANEL 3 IS
#   REMOVED as near-tautological: it reported 0% win rate for fav-first and
#   56% for heat-first on RunawayContinuation, which is mostly definitional
#   because a winner's favourable peak IS its exit and a loser's adverse peak
#   is its. Replaced with the same data stated descriptively, no win rate.
# v1.0 (2026-09-01) — dtp r244. WHAT SEPARATES A GOOD ENTRY FROM A BAD ONE.
#
# Operator, 2026-09-01: we have a hundred trend credit spread trades, possibly
# more; the entries are relaxed, which is fine, we're getting good data — but
# is there a clear picture yet of what separates a good entry from a bad one?
#
# 🔴 JUDGING AN ENTRY BY REALISED P&L MEASURES THE EXIT TOO, and that is the
#   whole reason this report exists separately. A good entry stopped out by the
#   25 percent floor on quote noise reads as a bad entry; a mediocre one that
#   ran because the exit held reads as a good one. NF.1 already names those as
#   two populations. EXCURSION isolates the entry: MFE is what the entry
#   OFFERED before anything was decided about it, MAE is the heat it took
#   first. Both are per-trade columns on `trades` (mfe_premium, mfe_bars,
#   mae_premium, mae_bars) — no reconstruction needed.
#
# 🔑 THE FIRST FINDING IS THE SAMPLE, and the menu prints it. The operator
#   estimated ~100 TrendCreditSpread trades; his 09-01 QQQ board showed ONE on
#   that box. What limits the analysis is not the trade count but the SMALLER
#   OUTCOME CLASS — 100 trades at 45% is 45 wins, and the standard is 10-20
#   events per candidate variable, so 45 wins supports three or four
#   candidates. `fire_snapshot` carries dozens. Screening dozens against 45
#   events finds separations reliably, and they are noise.
#   So this report does NOT screen. It reports the excursion distributions and
#   the never-favourable split, and stops. The candidates are chosen by the
#   operator BEFORE looking; that is what makes a hundred trades informative
#   rather than a fishing licence.
#
# ⚠️ CLI ONLY — no menu item (r242). Progress on BOTH halves (r244 Bar).
#   Run:  python3 tools/entry_report.py
#         python3 tools/entry_report.py --from 2026-08-25 --to 2026-09-01 \
#                 --type TrendCreditSpread
"""Entry quality by excursion, not by realised P&L."""

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
from progress import Bar                                      # noqa: E402

ET = ZoneInfo("US/Eastern")

def main(argv):
    ap = argparse.ArgumentParser(description="entry quality by excursion")
    ap.add_argument("--from", dest="d0")
    ap.add_argument("--to", dest="d1")
    ap.add_argument("--type", dest="typ")
    a = ap.parse_args(argv[1:])
    t0 = datetime.now(ET)
    dates = RP.ask_dates(a.d0, a.d1)

    cache = WCACHE.WarehouseCache("entryrep")
    try:
        RP.load_trades(cache, dates)
        counts = RP.type_counts(cache, "mfe_premium" if "entry" in __file__ else "mae_premium")
        # ⚠️ THE PULL HAPPENS ONCE AND THE MENU LOOPS. Operator,
        # 2026-09-02: return to the numbered menu to do another
        # selection without re-running the report. A 49-second S3 read
        # should not be repeated to look at a second strategy, and the
        # cache is already on disk.
        while True:
            chosen = RP.choose_type(counts, a.typ)
            if chosen is RP.QUIT:
                return 0
            _render(cache, dates, chosen, t0)
            if a.typ:
                return 0
    finally:
        cache.close()


def _render(cache, dates, chosen, t0):
    """One selection, rendered off the already-loaded cache.

    ⚠️ EXTRACTED SO THE PULL IS NOT REPEATED. It returns instead of
    raising SystemExit, which is what the single-shot version did —
    raising here would exit the process and defeat the loop.
    """

    where = 'status = ? AND mfe_premium IS NOT NULL'
    args = ["closed"]
    if chosen:
        where += " AND strategy = ?"
        args.append(chosen)
    rows = cache.query(f'SELECT * FROM "trades" WHERE {where}'
                       f' ORDER BY entry_time', tuple(args))

    out, w = [], None
    out = []
    w = out.append
    label = chosen or "ALL types"
    w(f"ENTRY QUALITY — {dates[0]} .. {dates[-1]} ET — {label}")
    w("=" * 66)
    w(f"source: s3 raw/trades  ·  {cache.objects:,} objects"
      f"  ·  {cache.rows:,} rows  ·  {cache.bytes_seen / 1e6:.0f} MB")
    w("")
    if not rows:
        w("  no closed trades with excursion telemetry in this range")
        _emit(out, dates, label, t0)

    bar = Bar("scoring entries", len(rows))
    # 🔑 EXCURSION AS A MULTIPLE OF WHAT WAS RISKED, so a $0.17 fly and a
    # $1.56 ORB are comparable. For a DEBIT the risk is the premium paid.
    # ⚠️ CREDIT VERTICALS ARE SIGNED THE OTHER WAY (r214): they profit as
    # the mark FALLS, so their favourable excursion is the LOW mark, not
    # the high. Getting this wrong would invert every sweep and TCS row.
    scored, never_fav, no_tel = [], 0, 0
    for r in rows:
        bar.step()
        e = r["entry_premium"] or 0
        if not e:
            no_tel += 1
            continue
        credit = (r["credit_received"] or 0) > 0
        mfe, mae = r["mfe_premium"], r["mae_premium"]
        if mfe is None or mae is None:
            no_tel += 1
            continue
        if credit:
            fav, adv = (e - mae) / e, (mfe - e) / e
            fav_bars, adv_bars = r["mae_bars"], r["mfe_bars"]
        else:
            fav, adv = (mfe - e) / e, (e - mae) / e
            fav_bars, adv_bars = r["mfe_bars"], r["mae_bars"]
        # ⚠️ NEVER-FAVOURABLE IS ITS OWN POPULATION (NF.1). A trade that was
        # never once green is a SELECTION failure; one that went green and
        # gave it back is an EXTENSION failure. Averaging them together is
        # what hides both.
        if fav <= 0.02:
            never_fav += 1
        won = (r["pnl_usd"] or 0) > 0
        scored.append({"fav": fav, "adv": adv, "won": won,
                       "fav_bars": fav_bars or 0, "adv_bars": adv_bars or 0,
                       "pnl": r["pnl_usd"] or 0, "sym": r["symbol"],
                       "credit": credit})
    bar.done(f"{len(scored):,} scored")

    n = len(scored)
    wins = [s for s in scored if s["won"]]
    losses = [s for s in scored if not s["won"]]

    def _med(vals):
        v = sorted(vals)
        return v[len(v) // 2] if v else float("nan")

    w(f"  {n:,} trades scored"
      f"   ({len(wins):,} won / {len(losses):,} lost)"
      f"   {no_tel:,} lacked telemetry")
    w("")
    # 🔴 THE LIMIT, STATED BEFORE ANY NUMBERS ARE READ.
    small = min(len(wins), len(losses))
    w(f"  ⚠️ THE LIMITING SAMPLE IS THE SMALLER OUTCOME CLASS: {small}.")
    if small < 30:
        w("     Under ~30 this generates hypotheses and confirms nothing.")
    w(f"     At 10-20 events per variable that supports about "
      f"{max(1, small // 15)} candidate(s) — chosen BEFORE looking.")
    w("")

    w("1. WHAT THE ENTRY OFFERED  (favourable excursion / premium risked)")
    w("-" * 66)
    w(f"  {'':<10} {'n':>6} {'med fav':>9} {'med adv':>9} "
      f"{'fav bars':>9} {'adv bars':>9}")
    for lab, grp in (("won", wins), ("lost", losses), ("all", scored)):
        if not grp:
            continue
        w(f"  {lab:<10} {len(grp):>6,} "
          f"{_med([g['fav'] for g in grp]):>8.0%} "
          f"{_med([g['adv'] for g in grp]):>8.0%} "
          f"{_med([g['fav_bars'] for g in grp]):>9.0f} "
          f"{_med([g['adv_bars'] for g in grp]):>9.0f}")
    w("")

    w("2. THE TWO POPULATIONS  (NF.1)")
    w("-" * 66)
    w(f"  never favourable (peak <= +2% of premium): {never_fav:,}"
      f"  ({never_fav / n:.0%})")
    w(f"  went favourable at some point:             {n - never_fav:,}"
      f"  ({(n - never_fav) / n:.0%})")
    gave_back = [s for s in scored if s["fav"] > 0.02 and not s["won"]]
    w(f"    of which finished as LOSSES:             {len(gave_back):,}"
      f"  ({len(gave_back) / max(1, n - never_fav):.0%} of them)")
    w("")
    w("  A never-favourable trade is a SELECTION problem — the entry was")
    w("  wrong. A gave-it-back trade is an EXTENSION problem — the exit")
    w("  was. They need different fixes and averaging them hides both.")
    w("")

    # 🔴 v1.0's PANEL 3 WAS NEAR-TAUTOLOGICAL AND IS REMOVED. It split on
    # whether the favourable peak came before the worst heat and reported a win
    # rate against it. RunawayContinuation over 2026-08-24..09-01 came back 0%
    # for fav-first and 56% for heat-first — a striking-looking result that is
    # mostly DEFINITIONAL: for a WINNER the favourable peak is essentially the
    # exit, so `mfe_bars` is large by construction; for a LOSER the adverse
    # peak is the exit, so `mae_bars` is. Which came first is largely decided
    # BY the outcome rather than predictive OF it. That is exactly the spurious
    # separation this file's own closing warning describes, built into the file.
    # ⚠️ IT CANNOT BE REPAIRED FROM THESE COLUMNS. "Did it go green early"
    # needs an early-window mark, and `trades` records only the extremes and
    # when they occurred. So the same data is stated descriptively, with no win
    # rate attached — a number nobody can misread as a predictor.
    w("3. THE SHAPE OF THE TRADE  (descriptive — see the caveat)")
    w("-" * 66)
    w(f"  {'':<10} {'n':>6} {'bars to peak':>13} {'bars to worst':>14}")
    for lab, grp in (("won", wins), ("lost", losses)):
        if not grp:
            continue
        w(f"  {lab:<10} {len(grp):>6,} "
          f"{_med([g['fav_bars'] for g in grp]):>13.0f} "
          f"{_med([g['adv_bars'] for g in grp]):>14.0f}")
    w("")
    w("  ⚠️ NO WIN RATE IS SHOWN AGAINST THIS, DELIBERATELY. A winner's")
    w("     favourable peak is essentially its exit and a loser's adverse peak")
    w("     is essentially its exit, so which came first is largely DECIDED BY")
    w("     the outcome. Splitting on it and reporting a win rate produces a")
    w("     strong-looking number that means very little.")
    w("")
    w("⚠️ NO SCREENING IS DONE HERE, DELIBERATELY. `fire_snapshot` carries")
    w("   dozens of derived values; screening dozens against a few dozen")
    w("   events finds separations reliably and they are noise. Name the")
    w("   three or four candidates first, then we test those.")
    _emit(out, dates, label, t0)


def _emit(out, dates, label, t0):
    text = "\n".join(out) + "\n"
    slug = (label or "all").replace(" ", "_").lower()
    path = WCACHE.report_path(f"entry_quality_{dates[0]}_{dates[-1]}_{slug}.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)
    print(f"wrote {path}   "
          f"({(datetime.now(ET) - t0).total_seconds():.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
