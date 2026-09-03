#!/usr/bin/env python3
"""day_trader_pro/tests/screen_reach.py — v1.1
v1.1  2026-09-03 — dtp r261. 🔴 v1.0 MEASURED REACH ENTRY-TO-EXIT AND THE MEDIAN
      RUNAWAY HOLD IS THREE MINUTES, so "the underlying travelled 0.99 ATR"
      measured three minutes of tape rather than the tape's capacity — a
      measurement truncated by the very early exits MOM.1 exists to fix. It
      could not distinguish "the strike was 6 ATR too far" from "the strike was
      fine and we left after 3 minutes", and those have OPPOSITE fixes. Reach is
      now measured over FIXED HORIZONS (5/15/30/60 min) with the exit reach kept
      alongside: the GAP between them is the answer.
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
# 🔑 FIXED HORIZONS, IN MINUTES. The tape's capacity, not our participation.
HORIZONS = (5, 15, 30, 60)
HOLD_CAP_MIN = 90


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
        e_ms = int(ets.timestamp() * 1000)
        # 🔴 r261 — REACH IS MEASURED OVER FIXED HORIZONS, NOT TO THE EXIT.
        # v1.0 ran entry -> exit, and the median runaway hold is THREE MINUTES
        # — so "the underlying travelled 0.99 ATR" measured three minutes of
        # tape, not what the tape was capable of. That is circular: the
        # measurement was truncated by the very early exits MOM.1 exists to
        # fix, and it could not tell "the strike was 6 ATR too far" from "the
        # strike was fine and we left after 3 minutes". Those have OPPOSITE
        # fixes.
        # 🔑 A FIXED HORIZON MEASURES THE TAPE'S CAPACITY instead of our
        # participation in it, and the exit horizon is kept alongside so the
        # gap between them IS the answer.
        exit_ms = int(xts.timestamp() * 1000) if xts else None
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
        dist = (k - spot) if long_side else (spot - k)
        far_ms = e_ms + max(HORIZONS) * 60_000
        post = cache.query(
            'SELECT ts_epoch_ms, high, low FROM "candles" WHERE symbol = ?'
            ' AND interval = ? AND ts_epoch_ms BETWEEN ? AND ?'
            ' ORDER BY ts_epoch_ms', (r["symbol"], "1m", e_ms, far_ms),
            max_rows=400)
        post = [dict(x) for x in post]
        if not post:
            no_bars += 1
            continue

        def _reach_to(cut_ms):
            sl = [x for x in post if x["ts_epoch_ms"] <= cut_ms]
            if not sl:
                return None
            return ((max(x["high"] for x in sl) - spot) if long_side
                    else (spot - min(x["low"] for x in sl)))

        rec = {"dist": dist, "atr": atr, "dist_atr": dist / atr,
               "trig": (ts.acc_recent if ts.ok else None),
               "score": (ts.score if ts.ok else None),
               "pnl": r["pnl_usd"] or 0, "sym": r["symbol"],
               "held_min": (None if exit_ms is None
                            else (exit_ms - e_ms) / 60_000)}
        for h in HORIZONS:
            rr = _reach_to(e_ms + h * 60_000)
            rec[f"reach_{h}"] = (None if rr is None else rr / atr)
        # ⚠️ THE EXIT REACH IS KEPT TOO. The GAP between what the tape offered
        # and what we stayed for is the whole question.
        rec["reach_exit"] = (None if exit_ms is None
                             else (lambda v: None if v is None else v / atr)(
                                 _reach_to(exit_ms)))
        rec["reach_atr"] = rec.get(f"reach_{HORIZONS[-1]}")
        rec["reached"] = (rec["reach_atr"] is not None
                          and rec["reach_atr"] >= rec["dist_atr"])
        recs.append(rec)
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
    # ══ THE QUESTION THE v1.0 RUN COULD NOT ANSWER ══════════════════════
    # 🔴 v1.0 MEASURED REACH ENTRY-TO-EXIT, AND THE MEDIAN HOLD IS 3 MINUTES.
    # So "the underlying travelled 0.99 ATR" measured three minutes of tape,
    # truncated by the very early exits MOM.1 exists to fix. It could not tell
    # "the strike was 6 ATR too far" from "the strike was fine and we left
    # after 3 minutes" — and those have OPPOSITE fixes.
    w("1. HOW FAR DID THE TAPE GO — AND HOW FAR DID WE STAY FOR?")
    w("   fixed horizons measure the tape; the exit column is us.")
    w("-" * 70)
    held = [x["held_min"] for x in recs if x["held_min"] is not None]
    if held:
        w(f"  median hold: {_med(held):.0f} min   p75 {_q(held,.75):.0f}"
          f"   p90 {_q(held,.90):.0f}")
    w("")
    w(f"  {'reach (ATR)':<20}{'median':>10}{'p75':>10}{'p90':>10}{'max':>10}"
      f"{'reached':>10}")
    ex = [x["reach_exit"] for x in recs if x["reach_exit"] is not None]
    if ex:
        n_ex = sum(1 for x in recs if x["reach_exit"] is not None
                   and x["reach_exit"] >= x["dist_atr"])
        w(f"  {'at our EXIT':<20}{_med(ex):>10.2f}{_q(ex,.75):>10.2f}"
          f"{_q(ex,.90):>10.2f}{_q(ex,1.0):>10.2f}"
          f"{n_ex/len(ex):>9.0%}")
    for h in HORIZONS:
        v = [x[f"reach_{h}"] for x in recs if x.get(f"reach_{h}") is not None]
        if not v:
            continue
        nr = sum(1 for x in recs if x.get(f"reach_{h}") is not None
                 and x[f"reach_{h}"] >= x["dist_atr"])
        w(f"  {f'+{h} min':<20}{_med(v):>10.2f}{_q(v,.75):>10.2f}"
          f"{_q(v,.90):>10.2f}{_q(v,1.0):>10.2f}{nr/len(v):>9.0%}")
    w("")
    d = [x["dist_atr"] for x in recs]
    w(f"  {'strike distance':<20}{_med(d):>10.2f}{_q(d,.75):>10.2f}"
      f"{_q(d,.90):>10.2f}{_q(d,1.0):>10.2f}")
    w("")
    # 🔑 THE GAP IS THE ANSWER. If +60 reaches far more often than the exit
    # does, the HOLD is the problem and the strikes were defensible. If even
    # +60 barely reaches, the STRIKES are too far and no hold fixes it.
    if ex:
        far = [x[f"reach_{HORIZONS[-1]}"] for x in recs
               if x.get(f"reach_{HORIZONS[-1]}") is not None]
        w(f"  🔑 the tape offered a median {_med(far):.2f} ATR over "
          f"{HORIZONS[-1]} min; we stayed for {_med(ex):.2f} ATR "
          f"({_med(ex)/_med(far):.0%} of it).")
        w("     If the +60 reached-rate is far above the exit rate, the HOLD")
        w("     is the problem and the strikes were defensible. If even +60")
        w("     barely reaches, the STRIKES are too far and no hold fixes it.")
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
