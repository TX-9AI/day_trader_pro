#!/usr/bin/env python3
"""day_trader_pro/tests/calibrate_trend_strength.py — v1.1
v1.1  2026-09-03 — dtp r258. 🔴 THE ORB ANCHOR IS GONE, AND IT WAS CAUSING A
      MemoryError. Finding the break bar meant querying EVERY candle for the
      symbol since the range began — no lower bound, thousands of rows per
      trade, past the cache's 2,000-row refusal. It cost the operator TWELVE
      MINUTES across two runs. The window is now a BOUNDED lookback from the
      fill, which fixes the query and the measure at once, and 10/20/30 bars
      are swept in ONE pass because each run costs ~6 minutes.
DOES THE TREND STRENGTH METER DISCRIMINATE? Read-only calibration.

v1.0  2026-09-03 — dtp r257.

🔑 IT IMPORTS THE REAL METER. `analysis/trend_strength.measure` is a pure
function of bars, and its `_rows` helper accepts a DataFrame OR sqlite rows for
exactly this reason: if the calibrator reimplemented the maths it would be
scoring a different function than the one that trades, and a threshold set here
would not mean the same thing live. One implementation, two callers.

🔴 THE OUTCOME IS THE ONE A STOP CANNOT MANUFACTURE — the same variable RPT.A
settled on: did the entry go 5% in profit at any point (MFE against premium,
signed by structure). Not P&L. Whether it STAYED there is a different question.

🔑 EVERY COMPONENT IS SCORED SEPARATELY, not just the composite. A composite
that separates tells you nothing about WHICH part did the work, and the weights
(0.35/0.30/0.20/0.15) are a declared PRIOR that this tool exists to move. If
`acceptance` carries everything and `pace` is noise, the weights should say so.

⚠️ AUC, AND THE NOISE FLOOR PRINTED BESIDE IT. In `screen_entry_vectors`'s own
fixture a vector of pure uniform noise reached AUC 0.69 on 30 against 30. Any
figure in the mid-0.6s at this sample size is a reason to look, never to act.
The window matters as much as the number, so BOTH are reported.

⚠️ THE WINDOW IS A BOUNDED LOOKBACK FROM THE FILL — the N closed 1m bars before
entry — and SEVERAL LENGTHS ARE SWEPT IN ONE PASS. There is NO ORB anchor:
the opening range is the highest-volume fifteen minutes of the day and an
afternoon tape does not inherit from it, so anchoring a momentum measure there
imports a correlation that is not present. Trades whose window is shorter than
the meter's floor are reported UNREADABLE and excluded, never scored as weak.

⚠️ `entry_time` IS STORED UTC (trade_logger says so three times). Parsed as UTC
here — reading it as ET was a four-hour error in the sweep forensics that made
one stale evaluation look like a constant across seventeen trades.

Usage:
    python3 tests/calibrate_trend_strength.py --from 2026-08-25 --to 2026-09-02
    python3 tests/calibrate_trend_strength.py ... --type RunawayContinuation
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)

import report_prompt as RP                                    # noqa: E402
import warehouse_cache as WCACHE                              # noqa: E402
from progress import Bar                                      # noqa: E402

ET = ZoneInfo("US/Eastern")
UTC = ZoneInfo("UTC")

# ⚠️ THE METER LIVES IN otv4. Located rather than reimplemented; if it cannot
# be found this FAILS LOUDLY, because a calibration that silently falls back to
# a local copy of the maths is worse than none — it would set a threshold for a
# function that does not trade.
_CANDS = [os.path.expanduser("~/options-trader-v4"),
          os.path.expanduser("~/options_trader_v4"),
          os.path.join(_root, "..", "options-trader-v4"),
          os.environ.get("OTV4_ROOT", "")]
_measure = None
for _c in _CANDS:
    if _c and os.path.exists(os.path.join(_c, "analysis", "trend_strength.py")):
        sys.path.insert(0, _c)
        from analysis.trend_strength import measure as _measure  # noqa: E402
        break
if _measure is None:
    raise SystemExit(
        "  CANNOT FIND options_trader_v4/analysis/trend_strength.py. The "
        "calibration must score the SAME function that trades; set OTV4_ROOT.")

COMPONENTS = ("score", "efficiency", "acceptance", "shallowness", "pace")


def _utc(ts):
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(ts)[:19], f).replace(tzinfo=UTC)
        except (ValueError, TypeError):
            continue
    return None


def _auc(a, b):
    """P(a random value from `a` exceeds one from `b`). 0.50 = nothing."""
    if len(a) < 3 or len(b) < 3:
        return None
    pairs = sorted([(v, 1) for v in a] + [(v, 0) for v in b],
                   key=lambda p: p[0])
    ranks, i = {}, 0
    while i < len(pairs):
        j = i
        while j + 1 < len(pairs) and pairs[j + 1][0] == pairs[i][0]:
            j += 1
        r = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[k] = r
        i = j + 1
    rs = sum(ranks[k] for k, (_v, g) in enumerate(pairs) if g == 1)
    return (rs - len(a) * (len(a) + 1) / 2.0) / (len(a) * len(b))


def _med(v):
    s = sorted(v)
    return s[len(s) // 2] if s else float("nan")


def main(argv):
    ap = argparse.ArgumentParser(description="calibrate the trend meter")
    ap.add_argument("--from", dest="d0")
    ap.add_argument("--to", dest="d1")
    ap.add_argument("--type", dest="typ")
    ap.add_argument("--green", type=float, default=0.05)
    a = ap.parse_args(argv[1:])
    t0 = datetime.now(ET)
    dates = RP.ask_dates(a.d0, a.d1)

    cache = WCACHE.WarehouseCache("trendcal")
    try:
        cache.load("trades", dates,
                   RP.COLS + ["option_side"], datatype="trades")
        cache.conn.execute("CREATE INDEX IF NOT EXISTS ix_tr "
                           "ON trades(strategy, status)")
        cache.conn.commit()
        syms = sorted({r["symbol"] for r in cache.query(
            'SELECT DISTINCT symbol FROM "trades" WHERE status = ?',
            ("closed",))})
        if not syms:
            print("  no closed trades in range")
            return 0
        # ⚠️ SCOPED (dtp r253): 1m bars for these symbols only. Unscoped this
        # queued 48,305 GETs for ~39 MB.
        cache.load("candles", dates, ["interval", "ts_epoch_ms",
                                      "open", "high", "low", "close"],
                   datatype="candles", syms=syms, part="interval=1m")
        cache.index("candles", "symbol", "interval")

        counts = RP.type_counts(cache, "mfe_premium")
        while True:
            chosen = RP.choose_type(counts, a.typ)
            if chosen is RP.QUIT:
                return 0
            _render(cache, dates, chosen, a.green, t0)
            if a.typ:
                return 0
    finally:
        cache.close()


def _render(cache, dates, chosen, green_at, t0):
    where = "status = ? AND mfe_premium IS NOT NULL AND mae_premium IS NOT NULL"
    args = ["closed"]
    if chosen:
        where += " AND strategy = ?"
        args.append(chosen)
    rows = cache.query(f'SELECT * FROM "trades" WHERE {where}'
                       f' ORDER BY entry_time', tuple(args))
    out, w = [], None
    out = []
    w = out.append
    label = chosen or "ALL strategies"
    w(f"TREND STRENGTH CALIBRATION — {dates[0]} .. {dates[-1]} ET — {label}")
    w("=" * 70)
    w(f"GREEN = the entry went {green_at:.0%} in profit at some point.")
    w("Window = the ORB break bar through the fill — what a gate would see.")
    w("")
    if not rows:
        w("  no closed trades with excursion telemetry for this selection")
        return _emit(out, dates, label, t0)

    # 🔴 r258 — THE WINDOW IS A LOOKBACK FROM THE FILL, NOT AN ORB LEG.
    # Operator, 2026-09-03: *"I'm apprehensive about marrying the trend meter
    # to the ORB structure — the ORB range is defined by the highest volume
    # period of the day and is not indicative of the remainder of it, and an
    # afternoon of chop isn't preceded by a strong or weak ORB range. They're
    # uncorrelated."* Both objections are right, and the ORB was only ever
    # SCAFFOLDING here — `orb_range_high` was the one anchor already on the
    # trade row. The meter itself has no concept of an opening range;
    # `measure(bars, direction)` is a pure function of a window.
    # 🔴 AND THE ORB ANCHOR CAUSED A MemoryError THAT COST THE OPERATOR TWELVE
    # MINUTES ACROSS TWO RUNS. Finding "the first close beyond the boundary"
    # meant querying EVERY bar for that symbol since the range began — no lower
    # bound, thousands of rows per trade, straight past the cache's 2,000-row
    # refusal. A bounded lookback fixes the window and the query at once.
    # 🔑 SEVERAL WINDOWS IN ONE PASS, because each run costs ~6 minutes of RTH
    # attention and re-running to try 20 bars instead of 10 is not a cost worth
    # paying. If strength separates at ANY window that is the signal; the leg
    # definition can be argued afterwards.
    WINDOWS = (10, 20, 30)
    bar = Bar("measuring", len(rows) * len(WINDOWS))
    by_win = {w: {"green": [], "other": [], "short": 0} for w in WINDOWS}
    scored_any = 0
    for r in rows:
        e = r["entry_premium"] or 0
        mfe, mae = r["mfe_premium"], r["mae_premium"]
        if not e or mfe is None or mae is None:
            for _wl in WINDOWS:
                bar.step()
            continue
        side = str(r["option_side"] or "").lower()
        direction = "long" if side.startswith("c") else "short"
        ets = _utc(r["entry_time"])
        if not ets:
            for _wl in WINDOWS:
                bar.step()
            continue
        # 🔴 SIGNED BY STRUCTURE (r214/r219): a credit vertical's favourable
        # extreme is the LOW mark, because mfe_premium is the HIGHEST seen.
        credit = (r["credit_received"] or 0) > 0
        fav = ((e - mae) / e) if credit else ((mfe - e) / e)
        is_green = fav >= green_at
        end_ms = int(ets.timestamp() * 1000)
        # ⚠️ NOT `w` — that is the report writer (`w = out.append`), and
        # shadowing it here clobbered the writer mid-function.
        for wl in WINDOWS:
            bar.step()
            # ⚠️ BOUNDED BOTH ENDS. `w + 5` minutes of slack absorbs gaps in
            # the 1m series without unbounding the query.
            start_ms = end_ms - (wl + 5) * 60_000
            bars = cache.query(
                'SELECT open, high, low, close FROM "candles"'
                ' WHERE symbol = ? AND interval = ? '
                ' AND ts_epoch_ms BETWEEN ? AND ?'
                ' ORDER BY ts_epoch_ms',
                (r["symbol"], "1m", start_ms, end_ms), max_rows=200)
            win = [dict(x) for x in bars][-wl:]
            ts = _measure(win, direction)
            if not ts.ok:
                by_win[wl]["short"] += 1
                continue
            by_win[wl]["green" if is_green else "other"].append(ts)
            scored_any += 1
    bar.done(f"{scored_any:,} readings")

    w(f"  {len(rows):,} closed trades   {len(WINDOWS)} window(s) swept")
    w("  ⚠️ WINDOW = the N closed 1m bars BEFORE the fill. No ORB anchor —")
    w("     the opening range is a 15-minute artefact and an afternoon tape")
    w("     does not inherit from it.")
    w("")
    for wlen in WINDOWS:
        g, o, sh = (by_win[wlen]["green"], by_win[wlen]["other"],
                    by_win[wlen]["short"])
        small = min(len(g), len(o))
        w(f"  ── {wlen}-BAR WINDOW ──  green {len(g)}  never-green {len(o)}"
          f"  unreadable {sh}   limiting {small}")
        if small < 10:
            w("     too few to rank at this window")
            w("")
            continue
        w(f"     {'component':<14} {'AUC':>6} {'med green':>11} {'med other':>11}")
        for c in COMPONENTS:
            gv = [getattr(x, c) for x in g if getattr(x, c) is not None]
            ov = [getattr(x, c) for x in o if getattr(x, c) is not None]
            auc = _auc(gv, ov)
            if auc is None:
                continue
            w(f"     {c:<14} {auc:>6.2f} {_med(gv):>11.3f} {_med(ov):>11.3f}")
        w("")
    green = by_win[WINDOWS[-1]]["green"]
    other = by_win[WINDOWS[-1]]["other"]
    no_read = by_win[WINDOWS[-1]]["short"]
    no_orb = 0
    n = len(green) + len(other)
    w(f"  {len(rows):,} closed trades   {n:,} measured")
    w(f"  no ORB boundary on the row : {no_orb:,}")
    w(f"  window too short to read   : {no_read:,}"
      f"   (excluded, NOT scored weak)")
    w("")
    w(f"  GREEN (>= {green_at:.0%})  : {len(green):,}")
    w(f"  never green         : {len(other):,}")
    small = min(len(green), len(other))
    w(f"  limiting class      : {small:,}")
    if small < 10:
        w("  ⚠️ TOO FEW TO RANK. Widen the range or pick ALL.")
        return _emit(out, dates, label, t0)
    w("")
    w(f"  {'component':<14} {'AUC':>6} {'med green':>11} {'med other':>11}"
      f" {'weight':>8}")
    w("  " + "-" * 56)
    weights = {"score": None, "efficiency": 0.35, "acceptance": 0.30,
               "shallowness": 0.20, "pace": 0.15}
    for c in COMPONENTS:
        g = [getattr(x, c) for x in green if getattr(x, c) is not None]
        o = [getattr(x, c) for x in other if getattr(x, c) is not None]
        auc = _auc(g, o)
        if auc is None:
            continue
        wt = weights.get(c)
        w(f"  {c:<14} {auc:>6.2f} {_med(g):>11.3f} {_med(o):>11.3f}"
          f" {('—' if wt is None else f'{wt:.2f}'):>8}")
    w("")
    # ⚠️ THE NOISE FLOOR, PRINTED BESIDE THE RESULT. Without it a 0.62 reads as
    # a finding.
    w(f"  ⚠️ NOISE FLOOR AT THIS SAMPLE: pure uniform noise reached AUC 0.69")
    w(f"     on 30 v 30 in screen_entry_vectors' own fixture. With a limiting")
    w(f"     class of {small}, treat anything under ~0.65 as unproven.")
    w("")
    # a candidate threshold sweep, on the composite only
    w("  IF A GATE WERE SET ON THE COMPOSITE  (kept / green-rate)")
    w("  " + "-" * 56)
    allts = [(x, True) for x in green] + [(x, False) for x in other]
    w(f"  {'threshold':>10} {'kept':>7} {'of total':>9} {'green rate':>11}")
    for th in (0.0, 0.30, 0.40, 0.50, 0.60, 0.70):
        kept = [(x, g) for x, g in allts if (x.score or 0) >= th]
        if not kept:
            continue
        gr = sum(1 for _x, g in kept if g) / len(kept)
        w(f"  {th:>10.2f} {len(kept):>7} {len(kept)/len(allts):>8.0%}"
          f" {gr:>10.0%}")
    w("")
    w("  ⚠️ A THRESHOLD THAT LIFTS THE GREEN RATE BY REFUSING ALMOST")
    w("     EVERYTHING IS NOT A GATE, IT IS A HALT. Read the kept column")
    w("     first: RTH windows are the scarce resource, and a gate that")
    w("     takes three trades a week cannot be evaluated before go-live.")
    return _emit(out, dates, label, t0)


def _emit(out, dates, label, t0):
    text = "\n".join(out) + "\n"
    slug = (label or "all").replace(" ", "_").lower()
    path = WCACHE.report_path(
        f"trend_calibration_{dates[0]}_{dates[-1]}_{slug}.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)
    print(f"wrote {path}   "
          f"({(datetime.now(ET) - t0).total_seconds():.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
