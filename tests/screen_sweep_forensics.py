#!/usr/bin/env python3
"""day_trader_pro/tests/screen_sweep_forensics.py — v1.0
WHY IS THE SWEEP CREDIT SPREAD FAILING? PENETRATION AND ACCEPTANCE.

v1.0  2026-09-02 — dtp r252. Read-only. Descriptive, not comparative.

🔴 A 3% SUCCESS RATE IS NOT BAD LUCK. Operator, 2026-09-02, on the entry-vector
   screen returning 3 GREEN against 38 NEVER GREEN for SweepCreditSpread over
   2026-08-25..09-02: *"a trade with a 3% success rate isn't unlucky — it's
   broken."* So this does NOT compare winners to losers: there are three
   winners and no comparison is possible. It DESCRIBES what the losers did.

🔑 THE TWO QUESTIONS, IN THE OPERATOR'S TERMS. What levels is price closing
   past (ACCEPTANCE), and by how much (PENETRATION DISTANCE)?
   · PENETRATION — the furthest price travelled beyond the short anchor while
     the trade was open, in points and in ATR. Separates "grazed the strike"
     from "went through and kept going".
   · ACCEPTANCE — how many consecutive 1-MINUTE CLOSES sat beyond the level.
     One bar is a wick; five is a regime change. This is why the study reads
     `raw/candles` and not tick samples: `plan_tick.underlying` is a snapshot
     every ~15s and a CLOSE is a different fact from a sample.

⚠️ EVERY FIELD BELOW WAS READ FROM SOURCE, NOT RECALLED:
   · `short_anchor` (plan_check value) — the strike beyond the swept price;
     sweep_credit_spread.py:776 `t.check("short_anchor", _ps, True)`.
   · `side_of_pool` (plan_check value) — `price_now - pool`, the SIGNED
     penetration at evaluation time; sweep_credit_spread.py:739.
   · `rejection` / `pierce_depth` / `age` / `sweep` — same file, and `sweep`
     is 2.0 for a pitchfork TINE touch, 1.0 otherwise (line 704).
   · `trades.short_strike` / `long_strike` / `credit_received` — real columns,
     checked against the DDL (82 columns).
   · candles are `symbol, interval, ts_epoch_ms, open, high, low, close,
     volume` (candle_feed.py:393) and their S3 key carries an EXTRA
     `interval=` partition level, so rows are filtered on the column.

⚠️ ONLY 41 SWEEP TRADES EXIST. Nothing here is a fit and there is no control
   group. It is a description of a failing population, which is what a 3% rate
   warrants before anything is tuned.

⚠️ Streams through warehouse_cache (dtp r238/r242): projected, aggregated in
   SQL where possible, scratch removed on every exit path.

Usage:
    python3 tests/screen_sweep_forensics.py --from 2026-08-25 --to 2026-09-02
    python3 tests/screen_sweep_forensics.py            # prompts for dates
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
STRAT = "SweepCreditSpread"

# ⚠️ The checks this study needs, by the names the strategy actually writes.
WANT = ("short_anchor", "side_of_pool", "rejection", "pierce_depth",
        "age", "sweep", "contract", "atr_pct")


def _et(ts_str):
    """trades.entry_time / exit_time are TEXT. Parsed, never assumed epoch."""
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(ts_str)[:19], f).replace(tzinfo=ET)
        except (ValueError, TypeError):
            continue
    return None


def _med(v):
    s = sorted(v)
    return s[len(s) // 2] if s else float("nan")


def main(argv):
    ap = argparse.ArgumentParser(description="sweep forensics")
    ap.add_argument("--from", dest="d0")
    ap.add_argument("--to", dest="d1")
    a = ap.parse_args(argv[1:])
    t0 = datetime.now(ET)
    dates = RP.ask_dates(a.d0, a.d1)

    cache = WCACHE.WarehouseCache("sweepfx")
    try:
        # ⚠️ THE SHARED PROJECTION DOES NOT CARRY THE STRIKES. `RP.COLS` has
        # eighteen columns and `short_strike` / `long_strike` are not among
        # them — they exist in the DDL (82 columns) but the excursion reports
        # never needed them. This tool does: the SHORT strike is the level, and
        # which side of it a breach comes from is decided by whether the long
        # sits above or below. Loaded explicitly rather than assumed present.
        cache.load("trades", dates,
                   RP.COLS + ["short_strike", "long_strike"],
                   datatype="trades")
        cache.conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_tr ON trades(strategy, status)")
        cache.conn.commit()
        cache.load("plan_check", dates,
                   ["ts_epoch", "strategy", "check_name", "value", "direction"])
        cache.load("candles", dates,
                   ["interval", "ts_epoch_ms", "high", "low", "close"],
                   datatype="candles")
        cache.index("plan_check", "strategy", "check_name")
        cache.index("candles", "symbol", "interval")

        rows = cache.query(
            'SELECT * FROM "trades" WHERE strategy = ? AND status = ?'
            ' ORDER BY entry_time', (STRAT, "closed"))

        out, w = [], None
        out = []
        w = out.append
        w(f"SWEEP FORENSICS — {dates[0]} .. {dates[-1]} ET")
        w("=" * 68)
        w("A 3% success rate is not bad luck. This DESCRIBES the losers;")
        w("with 3 winners there is no comparison to make.")
        w("")
        w(f"source: s3  ·  {cache.objects:,} objects  ·  {cache.rows:,} rows"
          f"  ·  {cache.bytes_seen / 1e6:.0f} MB")
        w("")
        if not rows:
            w(f"  no closed {STRAT} trades in this range")
            return _emit(out, dates, t0)

        # ── the fire-tick checks, nearest evaluation at or before entry ──
        # ⚠️ NEAREST AT-OR-BEFORE, never nearest overall: an evaluation AFTER
        # the fill describes a different market than the one entered.
        chk = {}
        for r in cache.iter(
                'SELECT ts_epoch, symbol, check_name, value FROM "plan_check"'
                ' WHERE strategy = ? AND value IS NOT NULL', (STRAT,)):
            chk.setdefault((r["symbol"], r["check_name"]), []).append(
                (float(r["ts_epoch"]), float(r["value"])))
        for k in chk:
            chk[k].sort()

        def at_entry(sym, name, ts):
            seq = chk.get((sym, name)) or []
            best = None
            for t, v in seq:
                if t <= ts:
                    best = v
                else:
                    break
            return best

        bar = Bar("reconstructing", len(rows))
        recs = []
        for r in rows:
            bar.step()
            e_dt, x_dt = _et(r["entry_time"]), _et(r["exit_time"])
            if not e_dt:
                continue
            ets = e_dt.timestamp()
            xts = x_dt.timestamp() if x_dt else ets + 3600
            anchor = at_entry(r["symbol"], "short_anchor", ets)
            if anchor is None:
                anchor = r["short_strike"]
            side = at_entry(r["symbol"], "side_of_pool", ets)
            # ⚠️ DIRECTION FROM THE STRUCTURE, NOT FROM A GUESS. A CALL spread
            # is breached UPWARD (price rising through the short), a PUT spread
            # DOWNWARD. `long_strike` above `short_strike` means a call spread.
            call = (r["long_strike"] or 0) > (r["short_strike"] or 0)
            bars = cache.query(
                'SELECT ts_epoch_ms, high, low, close FROM "candles"'
                ' WHERE symbol = ? AND interval = ? AND ts_epoch_ms BETWEEN ? AND ?'
                ' ORDER BY ts_epoch_ms',
                (r["symbol"], "1m", int(ets * 1000), int(xts * 1000)),
                max_rows=5000)
            if not bars or anchor is None:
                recs.append({"sym": r["symbol"], "anchor": anchor, "side": side,
                             "pen": None, "acc": None, "bars": 0,
                             "pnl": r["pnl_usd"] or 0, "call": call,
                             "reason": r["exit_reason"] or ""})
                continue
            # PENETRATION: furthest the EXTREME travelled beyond the anchor
            if call:
                pen = max((b["high"] or 0) - anchor for b in bars)
                closes_past = [1 if (b["close"] or 0) > anchor else 0 for b in bars]
            else:
                pen = max(anchor - (b["low"] or 0) for b in bars)
                closes_past = [1 if (b["close"] or 0) < anchor else 0 for b in bars]
            # ACCEPTANCE: the LONGEST RUN of consecutive closes beyond it.
            # 🔑 A RUN, NOT A COUNT. Five scattered closes across an hour is
            # noise; five consecutive is the level failing.
            run = best = 0
            for c in closes_past:
                run = run + 1 if c else 0
                best = max(best, run)
            recs.append({"sym": r["symbol"], "anchor": anchor, "side": side,
                         "pen": pen, "acc": best, "bars": len(bars),
                         "pnl": r["pnl_usd"] or 0, "call": call,
                         "reason": r["exit_reason"] or ""})
        bar.done(f"{len(recs)} trades")

        losers = [x for x in recs if x["pnl"] <= 0]
        winners = [x for x in recs if x["pnl"] > 0]
        w(f"  {len(recs)} closed sweep trades   "
          f"({len(winners)} profitable / {len(losers)} not)")
        nb = [x for x in recs if not x["bars"]]
        if nb:
            w(f"  ⚠️ {len(nb)} had NO 1m candles in the warehouse for their")
            w("     window — penetration and acceptance are unmeasurable for")
            w("     those and they are excluded below, not counted as zero.")
        w("")

        w("1. PENETRATION BEYOND THE SHORT ANCHOR  (points, while open)")
        w("   how far past the strike it sold, price actually went")
        w("-" * 68)
        pen = [x["pen"] for x in recs if x["pen"] is not None]
        if pen:
            s = sorted(pen)
            w(f"  n={len(s)}   min {s[0]:+.2f}   median {_med(s):+.2f}   "
              f"p90 {s[int(0.9*(len(s)-1))]:+.2f}   max {s[-1]:+.2f}")
            through = sum(1 for p in pen if p > 0)
            w(f"  price traded BEYOND the short strike on {through}/{len(pen)}"
              f"  ({through/len(pen):.0%})")
            w("  (a negative figure means it never reached the strike at all)")
        w("")

        w("2. ACCEPTANCE  (longest run of consecutive 1m CLOSES beyond it)")
        w("   1 bar is a wick. 5 consecutive is the level failing.")
        w("-" * 68)
        acc = [x["acc"] for x in recs if x["acc"] is not None]
        if acc:
            buckets = ((0, 0, "never closed past"), (1, 1, "1 bar (wick)"),
                       (2, 4, "2-4 bars"), (5, 9, "5-9 bars"),
                       (10, 10**6, "10+ bars (accepted)"))
            for lo, hi, lab in buckets:
                n = sum(1 for v in acc if lo <= v <= hi)
                if n:
                    w(f"  {lab:<22} {n:>4}  ({n/len(acc):>4.0%})")
        w("")

        w("3. WHERE PRICE SAT WHEN IT FIRED  (side_of_pool = price - pool)")
        w("   the margin the trade was entered with, BEFORE the fill")
        w("-" * 68)
        sd = [abs(x["side"]) for x in recs if x["side"] is not None]
        if sd:
            s = sorted(sd)
            w(f"  n={len(s)}   min {s[0]:.2f}   median {_med(s):.2f}   "
              f"max {s[-1]:.2f}   (points from the swept pool)")
            w("  ⚠️ THIS IS KNOWABLE BEFORE THE FILL, unlike everything the")
            w("     entry-vector screen tested — which found nothing.")
        else:
            w("  (no side_of_pool recorded at or before these fills)")
        w("")

        w("4. WHAT ENDED THEM")
        w("-" * 68)
        by = {}
        for x in recs:
            k = (x["reason"].split()[0] if x["reason"] else "(none)")[:22]
            d = by.setdefault(k, {"n": 0, "pnl": 0.0, "pen": []})
            d["n"] += 1
            d["pnl"] += x["pnl"]
            if x["pen"] is not None:
                d["pen"].append(x["pen"])
        w(f"  {'reason':<24} {'n':>4} {'net':>11} {'med penetration':>17}")
        for k in sorted(by, key=lambda z: -by[z]["n"]):
            d = by[k]
            mp = f"{_med(d['pen']):+.2f}" if d["pen"] else "n/a"
            w(f"  {k:<24} {d['n']:>4} {RP.money(d['pnl']):>11} {mp:>17}")
        w("")
        w("⚠️ NO CONTROL GROUP AND NO FIT. 3 winners cannot anchor a")
        w("   comparison. This says what the failing population DID; whether")
        w("   any of it is selectable is the next question, not this one.")
        return _emit(out, dates, t0)
    finally:
        cache.close()


def _emit(out, dates, t0):
    text = "\n".join(out) + "\n"
    path = WCACHE.report_path(f"sweep_forensics_{dates[0]}_{dates[-1]}.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)
    print(f"wrote {path}   "
          f"({(datetime.now(ET) - t0).total_seconds():.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
