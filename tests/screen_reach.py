#!/usr/bin/env python3
"""day_trader_pro/tests/screen_reach.py — v1.0
HOW FAR DOES THE TAPE TRAVEL, AND WERE OUR STRIKES INSIDE IT? Read-only.

v1.0  2026-09-03 — dtp r260.

🔴 EVERYTHING CALIBRATED SO FAR WAS MEASURED ON *PREMIUM* EXCURSION, WHICH IS
THE MOVE MULTIPLIED BY THE STRIKE WE HAPPENED TO PICK. A far-OTM strike turns a
big move into a huge premium gain and a small move into nothing; a
near-the-money strike does the opposite. So "did it run >= 72.6%" was never a
clean statement about the tape — the strike sits on both sides of it.

🔑 THE CHAIN THE OPERATOR IS BUILDING (2026-09-03): *"if we get the trigger
right that translates to better entries, and better entries require less
management once we can nail down a good strike to a good potential move with a
constricting stop as it exhausts."* Three links, and they need THREE different
measurements:
  · TRIGGER  — "is it moving NOW."  Timing. Premium excursion is a fair proxy
               because a correct direction converts on any strike.
  · STRIKE   — "how far will it TRAVEL."  Magnitude. Must be measured on the
               UNDERLYING, in ATR, or the strike contaminates its own test.
  · STOP     — "has it stopped."  A within-trade question, not this report.
Only the first has been measured. This measures the second.

🔑 THE TWO QUESTIONS, KEPT APART:
  Q1  Does the trigger reading predict how far the UNDERLYING travels?
      Strike-independent, so a real answer either way.
  Q2  Were the strikes we chose INSIDE that travel? If most sat beyond where
      the tape actually went, the delta selector is the binding constraint and
      no trigger improvement fixes it. If most sat comfortably inside,
      distance is not the problem and strength should buy MORE of it.

⚠️ REACH IS FORWARD-LOOKING AND THAT IS FINE HERE — this is a STUDY of what the
tape did, not a gate. The trigger reading is the only thing taken from before
the fill, and it is the only thing a gate could use.

⚠️ ATR COMES FROM THE PRE-FILL WINDOW, never from the post-fill bars: an ATR
computed over the move itself is inflated by the very travel it is normalising.

Usage:
    python3 tests/screen_reach.py --from 2026-08-25 --to 2026-09-03
    python3 tests/screen_reach.py ... --type RunawayContinuation
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
from progress import Bar                                      # noqa: E402

ET = ZoneInfo("US/Eastern")
UTC = ZoneInfo("UTC")

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
    raise SystemExit("  CANNOT FIND options_trader_v4/analysis/trend_strength.py"
                     " — set OTV4_ROOT.")

TRIG_WINDOW = 10        # the shortest window carried the most signal
HOLD_CAP_MIN = 90       # if a trade is still open, cap the forward look


def _utc(ts):
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(ts)[:19], f).replace(tzinfo=UTC)
        except (ValueError, TypeError):
            continue
    return None


def _auc(a, b):
    if len(a) < 3 or len(b) < 3:
        return None
    pairs = sorted([(v, 1) for v in a] + [(v, 0) for v in b], key=lambda p: p[0])
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


def _q(v, p):
    s = sorted(v)
    return s[min(len(s) - 1, int(p * (len(s) - 1)))] if s else float("nan")


def main(argv):
    ap = argparse.ArgumentParser(description="strike reach vs underlying travel")
    ap.add_argument("--from", dest="d0")
    ap.add_argument("--to", dest="d1")
    ap.add_argument("--type", dest="typ")
    a = ap.parse_args(argv[1:])
    t0 = datetime.now(ET)
    dates = RP.ask_dates(a.d0, a.d1)

    cache = WCACHE.WarehouseCache("reach")
    try:
        cache.load("trades", dates,
                   RP.COLS + ["option_side", "strike", "underlying_entry"],
                   datatype="trades")
        cache.conn.execute("CREATE INDEX IF NOT EXISTS ix_tr "
                           "ON trades(strategy, status)")
        cache.conn.commit()
        syms = sorted({r["symbol"] for r in cache.query(
            'SELECT DISTINCT symbol FROM "trades" WHERE status = ?',
            ("closed",))})
        if not syms:
            print("  no closed trades in range")
            return 0
        cache.load("candles", dates,
                   ["interval", "ts_epoch_ms", "open", "high", "low", "close"],
                   datatype="candles", syms=syms, part="interval=1m")
        cache.index("candles", "symbol", "interval")
        counts = RP.type_counts(cache, "mfe_premium")
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
    where = "status = ? AND underlying_entry > 0 AND strike > 0"
    args = ["closed"]
    if chosen:
        where += " AND strategy = ?"
        args.append(chosen)
    rows = cache.query(f'SELECT * FROM "trades" WHERE {where}'
                       f' ORDER BY entry_time', tuple(args))
    out = []
    w = out.append
    label = chosen or "ALL strategies"
    w(f"REACH — {dates[0]} .. {dates[-1]} ET — {label}")
    w("=" * 70)
    w("How far did the UNDERLYING travel after the fill, and was the strike")
    w("we chose inside that travel? Measured on the underlying in ATR, NOT")
    w("on premium — premium excursion is the move x the strike we picked.")
    w("")
    if not rows:
        w("  no closed trades carrying underlying_entry and strike")
        return _emit(out, dates, label, t0)

    bar = Bar("measuring reach", len(rows))
    recs, no_bars = [], 0
    for r in rows:
        bar.step()
        spot = float(r["underlying_entry"] or 0)
        k = float(r["strike"] or 0)
        side = str(r["option_side"] or "").lower()
        long_side = side.startswith("c")
        ets, xts = _utc(r["entry_time"]), _utc(r["exit_time"])
        if not spot or not k or not ets:
            continue
        end = xts or ets
        end_ms = int(max(end.timestamp(),
                         ets.timestamp() + HOLD_CAP_MIN * 60) * 1000) \
            if not xts else int(xts.timestamp() * 1000)
        e_ms = int(ets.timestamp() * 1000)
        # ── ATR from BEFORE the fill ────────────────────────────────────
        pre = cache.query(
            'SELECT high, low, close FROM "candles" WHERE symbol = ?'
            ' AND interval = ? AND ts_epoch_ms BETWEEN ? AND ?'
            ' ORDER BY ts_epoch_ms',
            (r["symbol"], "1m", e_ms - (TRIG_WINDOW + 5) * 60_000, e_ms),
            max_rows=200)
        pre = [dict(x) for x in pre]
        if len(pre) < TRIG_WINDOW:
            no_bars += 1
            continue
        trs, pc = [], None
        for b in pre:
            hi, lo, cl = b["high"], b["low"], b["close"]
            if hi is None or lo is None:
                continue
            trs.append(hi - lo if pc is None
                       else max(hi - lo, abs(hi - pc), abs(lo - pc)))
            pc = cl
        atr = (sum(trs) / len(trs)) if trs else 0.0
        if atr <= 0:
            no_bars += 1
            continue
        # ── the trigger reading, from BEFORE the fill ───────────────────
        ts = _measure(pre[-TRIG_WINDOW:], "long" if long_side else "short")
        # ── REACH: underlying travel AFTER the fill ─────────────────────
        post = cache.query(
            'SELECT high, low FROM "candles" WHERE symbol = ?'
            ' AND interval = ? AND ts_epoch_ms BETWEEN ? AND ?'
            ' ORDER BY ts_epoch_ms', (r["symbol"], "1m", e_ms, end_ms),
            max_rows=400)
        post = [dict(x) for x in post]
        if not post:
            no_bars += 1
            continue
        reach = (max(x["high"] for x in post) - spot) if long_side \
            else (spot - min(x["low"] for x in post))
        dist = (k - spot) if long_side else (spot - k)
        recs.append({
            "reach": reach, "dist": dist, "atr": atr,
            "reach_atr": reach / atr, "dist_atr": dist / atr,
            "reached": reach >= dist,
            "trig": (ts.acc_recent if ts.ok else None),
            "score": (ts.score if ts.ok else None),
            "pnl": r["pnl_usd"] or 0, "sym": r["symbol"]})
    bar.done(f"{len(recs)} measured")

    if not recs:
        w("  nothing measurable")
        return _emit(out, dates, label, t0)
    w(f"  {len(rows):,} rows   {len(recs):,} measured   "
      f"{no_bars:,} lacked bars or ATR")
    w("")

    # ══ Q2 FIRST: WERE THE STRIKES REACHABLE? ═══════════════════════════
    # 🔴 THIS IS THE ONE THAT CAN INVALIDATE THE WHOLE DELTA IDEA. If most
    # strikes sat beyond where the tape actually went, the selector is the
    # binding constraint and no trigger improvement fixes it.
    w("1. WERE THE STRIKES INSIDE THE TAPE'S TRAVEL?")
    w("-" * 70)
    reached = [x for x in recs if x["reached"]]
    w(f"  strike reached by the underlying : {len(reached):,}/{len(recs):,}"
      f"  ({len(reached)/len(recs):.0%})")
    w("")
    w(f"  {'':<22}{'median':>10}{'p75':>10}{'p90':>10}{'max':>10}")
    for lab, key in (("strike distance (ATR)", "dist_atr"),
                     ("underlying reach (ATR)", "reach_atr")):
        v = [x[key] for x in recs]
        w(f"  {lab:<22}{_med(v):>10.2f}{_q(v,.75):>10.2f}"
          f"{_q(v,.90):>10.2f}{_q(v,1.0):>10.2f}")
    w("")
    short = [x for x in recs if not x["reached"]]
    if short:
        gap = [x["dist_atr"] - x["reach_atr"] for x in short]
        w(f"  when it did NOT reach, it fell short by a median "
          f"{_med(gap):.2f} ATR ({len(short):,} trades)")
    w("")

    # ══ Q1: DOES THE TRIGGER PREDICT TRAVEL? ════════════════════════════
    # ⚠️ STRIKE-INDEPENDENT, so this is a real answer either way — unlike the
    # premium-excursion calibration, where the strike sat on both sides.
    w("2. DOES THE TRIGGER PREDICT HOW FAR THE UNDERLYING TRAVELS?")
    w("   trigger = acceptance over the 10 bars BEFORE the fill")
    w("-" * 70)
    trig = [x for x in recs if x["trig"] is not None]
    if len(trig) < 20:
        w("  too few trigger readings")
    else:
        for cut in (0.90, 0.75):
            rs = sorted(x["reach_atr"] for x in trig)
            thr = _q(rs, cut)
            far = [x["trig"] for x in trig if x["reach_atr"] >= thr]
            near = [x["trig"] for x in trig if x["reach_atr"] < thr]
            auc = _auc(far, near)
            if auc is None:
                continue
            w(f"  travelled >= {thr:.2f} ATR (top {1-cut:.0%}): "
              f"n={len(far)}  AUC {auc:.2f}"
              f"   med trigger {_med(far):.3f} vs {_med(near):.3f}")
        w("")
        w("  ⚠️ NOISE FLOOR: pure noise reached 0.69 on 30v30 in")
        w("     screen_entry_vectors' fixture. Read anything under ~0.65 as")
        w("     unproven at this sample.")
    w("")

    # ══ WHAT A BETTER STRIKE WOULD HAVE BEEN ════════════════════════════
    # 🔑 NOT A RECOMMENDATION — a measurement. If the tape routinely travels
    # further than the strike we bought, distance was left on the table; if it
    # routinely falls short, we were buying lottery tickets.
    w("3. THE DISTANCE THE TAPE ACTUALLY OFFERED")
    w("-" * 70)
    ratio = [x["reach_atr"] / x["dist_atr"] for x in recs if x["dist_atr"] > 0]
    if ratio:
        w(f"  reach / strike-distance:  median {_med(ratio):.2f}x"
          f"   p25 {_q(ratio,.25):.2f}x   p75 {_q(ratio,.75):.2f}x")
        w("  1.00x means the tape stopped exactly at the strike.")
        w("  Below 1.00x the strike was never reached; above, there was")
        w("  further to go than we bought.")
    w("")
    w("⚠️ REACH IS FORWARD-LOOKING — this is a STUDY of what the tape did, not")
    w("   a gate. Only the trigger reading comes from before the fill, and it")
    w("   is the only thing a gate could use.")
    return _emit(out, dates, label, t0)


def _emit(out, dates, label, t0):
    text = "\n".join(out) + "\n"
    slug = (label or "all").replace(" ", "_").lower()
    path = WCACHE.report_path(f"reach_{dates[0]}_{dates[-1]}_{slug}.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)
    print(f"wrote {path}   ({(datetime.now(ET) - t0).total_seconds():.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
