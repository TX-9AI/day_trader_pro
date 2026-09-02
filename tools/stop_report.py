#!/usr/bin/env python3
# day_trader_pro/tools/stop_report.py — v1.1
# v1.1 (2026-09-02) — dtp r247. The menu LOOPS off one pull: several cuts from
#   one S3 read, `q` to quit.
# v1.0 (2026-09-01) — dtp r244. WAS THE STOP IN THE RIGHT PLACE?
#
# The companion to entry_report.py, on the operator's request, with the same
# prompts, the same numbered type menu and a progress bar on both halves.
#
# 🔑 THE ENTRY REPORT ASKS WHAT THE ENTRY OFFERED. THIS ASKS WHAT THE STOP
#   TOOK. They are separable precisely because MAE and MFE are recorded: the
#   heat a WINNER survived is the strongest evidence there is about where a
#   stop belongs. If winners routinely took more heat than the stop allows,
#   the stop is converting winners into losers and the fleet's win rate is an
#   artefact of stop placement rather than of selection.
#
# 🔴 AND THIS FLEET HAS ALREADY PAID FOR THAT ONCE. On 2026-09-01 five GEX pin
#   butterflies fired at 12:00:00 and three were stopped out INSIDE THE SAME
#   MINUTE — META on a 25% floor worth 4.3 CENTS, CRM 5.3, MU 7.0. They were
#   not stopped by price; they were stopped by their own marks, because a
#   percentage stop on a small debit is smaller than the structure's own
#   spread. Panel 3 below is that question asked of every strategy at once:
#   how does the stop distance compare to what it costs to trade the thing.
#
# ⚠️ CREDIT VERTICALS ARE SIGNED THE OTHER WAY (r214). They profit as the mark
#   FALLS, so their adverse excursion is the HIGH mark. Getting this backwards
#   would report every sweep and TCS stop as perfectly placed.
#
# ⚠️ CLI ONLY — no menu item (r242).
#   Run:  python3 tools/stop_report.py
#         python3 tools/stop_report.py --from 2026-08-25 --to 2026-09-01 \
#                 --type TrendCreditSpread
"""Stop placement judged against the heat winners actually survived."""

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
    ap = argparse.ArgumentParser(description="stop placement vs survived heat")
    ap.add_argument("--from", dest="d0")
    ap.add_argument("--to", dest="d1")
    ap.add_argument("--type", dest="typ")
    a = ap.parse_args(argv[1:])
    t0 = datetime.now(ET)
    dates = RP.ask_dates(a.d0, a.d1)

    cache = WCACHE.WarehouseCache("stoprep")
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

    where = 'status = ? AND mae_premium IS NOT NULL'
    args = ["closed"]
    if chosen:
        where += " AND strategy = ?"
        args.append(chosen)
    rows = cache.query(f'SELECT * FROM "trades" WHERE {where}'
                       f' ORDER BY entry_time', tuple(args))

    out = []
    w = out.append
    label = chosen or "ALL types"
    w(f"STOP PLACEMENT — {dates[0]} .. {dates[-1]} ET — {label}")
    w("=" * 66)
    w(f"source: s3 raw/trades  ·  {cache.objects:,} objects"
      f"  ·  {cache.rows:,} rows  ·  {cache.bytes_seen / 1e6:.0f} MB")
    w("")
    if not rows:
        w("  no closed trades with excursion telemetry in this range")
        _emit(out, dates, label, t0)

    bar = Bar("scoring stops", len(rows))
    scored = []
    for r in rows:
        bar.step()
        e = r["entry_premium"] or 0
        mae, mfe = r["mae_premium"], r["mfe_premium"]
        if not e or mae is None or mfe is None:
            continue
        credit = (r["credit_received"] or 0) > 0
        # adverse excursion as a fraction of premium at risk
        adv = ((mfe - e) / e) if credit else ((e - mae) / e)
        fav = ((e - mae) / e) if credit else ((mfe - e) / e)
        reason = (r["exit_reason"] or "")
        stopped = reason.startswith("hard_stop") or "stop" in reason
        scored.append({"adv": adv, "fav": fav,
                       "won": (r["pnl_usd"] or 0) > 0,
                       "stopped": stopped, "reason": reason,
                       "entry": e, "pnl": r["pnl_usd"] or 0,
                       "sym": r["symbol"], "strat": r["strategy"]})
    bar.done(f"{len(scored):,} scored")

    wins = [s for s in scored if s["won"]]
    losses = [s for s in scored if not s["won"]]

    def _q(vals, p):
        v = sorted(vals)
        return v[min(len(v) - 1, int(p * (len(v) - 1)))] if v else float("nan")

    # ══ 1. THE HEAT WINNERS SURVIVED ═════════════════════════════════
    # 🔴 THE CENTRAL NUMBER. If the 90th percentile of winners' adverse
    # excursion exceeds the stop, then roughly one winner in ten is being
    # cut before it works — and those losses are attributed to selection.
    w("1. HEAT THE WINNERS SURVIVED  (adverse excursion / premium)")
    w("   a stop inside these numbers converts winners into losers")
    w("-" * 66)
    if wins:
        w(f"  winners  n={len(wins):>5}   median {_q([s['adv'] for s in wins], .5):>6.0%}"
          f"   p75 {_q([s['adv'] for s in wins], .75):>6.0%}"
          f"   p90 {_q([s['adv'] for s in wins], .90):>6.0%}"
          f"   max {_q([s['adv'] for s in wins], 1.0):>6.0%}")
    if losses:
        w(f"  losers   n={len(losses):>5}   median {_q([s['adv'] for s in losses], .5):>6.0%}"
          f"   p75 {_q([s['adv'] for s in losses], .75):>6.0%}"
          f"   p90 {_q([s['adv'] for s in losses], .90):>6.0%}"
          f"   max {_q([s['adv'] for s in losses], 1.0):>6.0%}")
    w("")
    if wins and losses:
        sep = _q([s['adv'] for s in losses], .5) - _q([s['adv'] for s in wins], .5)
        if abs(sep) < 0.03:
            w("  ⚠️ WINNERS AND LOSERS TOOK THE SAME HEAT (medians within 3pts).")
            w("     Adverse excursion does not separate them here, so a stop")
            w("     placed on it cannot either — it will cut both alike.")
        else:
            w(f"  losers took {sep:+.0%} more heat than winners at the median.")
    w("")

    # ══ 2. WHAT ACTUALLY ENDED THE TRADE ════════════════════════════
    w("2. WHAT ENDED THE TRADE")
    w("-" * 66)
    reasons = {}
    for s in scored:
        k = (s["reason"].split()[0] if s["reason"] else "(none)")[:22]
        d = reasons.setdefault(k, {"n": 0, "won": 0, "pnl": 0.0})
        d["n"] += 1
        d["won"] += 1 if s["won"] else 0
        d["pnl"] += s["pnl"]
    w(f"  {'reason':<24} {'n':>6} {'win%':>6} {'net':>12}")
    for k in sorted(reasons, key=lambda x: -reasons[x]["n"]):
        d = reasons[k]
        w(f"  {k:<24} {d['n']:>6,} {d['won'] / d['n']:>5.0%} "
          f"{RP.money(d['pnl']):>12}")
    w("")

    # ══ 3. WAS THE STOP EVER BIGGER THAN THE NOISE? ═════════════════
    # 🔴 THE 2026-09-01 BUTTERFLY FAILURE, ASKED OF EVERYTHING. A 25% stop
    # on a $0.17 debit is 4.3 cents. Any structure whose stop distance is
    # small in absolute terms is stopped by its own quote, not by price.
    w("3. THE STOP IN CENTS, NOT PERCENT")
    w("   25% of a $0.17 debit is 4.3c — smaller than the spread it")
    w("   trades in. Percentage stops hide this; absolute ones cannot.")
    w("-" * 66)
    buckets = ((0, 0.25, "under $0.25"), (0.25, 0.75, "$0.25-0.75"),
               (0.75, 1.50, "$0.75-1.50"), (1.50, 9e9, "over $1.50"))
    w(f"  {'entry premium':<16} {'n':>6} {'win%':>6} "
      f"{'25% stop =':>12} {'med heat':>9}")
    for lo, hi, lab in buckets:
        g = [s for s in scored if lo <= s["entry"] < hi]
        if not g:
            continue
        mid = sum(s["entry"] for s in g) / len(g)
        wr = sum(1 for s in g if s["won"]) / len(g)
        w(f"  {lab:<16} {len(g):>6,} {wr:>5.0%} "
          f"{f'{mid * 0.25:.3f}':>12} "
          f"{_q([s['adv'] for s in g], .5):>8.0%}")
    w("")
    w("⚠️ THIS JUDGES PLACEMENT, NOT POLICY. Whether a structure should")
    w("   carry a percentage stop AT ALL is a different question — r208")
    w("   concluded a cheap high-R fly cannot, and that the debit is the")
    w("   risk. This report tells you where the heat was; it does not")
    w("   tell you a stop belongs there.")
    _emit(out, dates, label, t0)


def _emit(out, dates, label, t0):
    text = "\n".join(out) + "\n"
    slug = (label or "all").replace(" ", "_").lower()
    path = WCACHE.report_path(f"stop_placement_{dates[0]}_{dates[-1]}_{slug}.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)
    print(f"wrote {path}   "
          f"({(datetime.now(ET) - t0).total_seconds():.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
