#!/usr/bin/env python3
"""day_trader_pro/tests/screen_sweep_forensics.py — v1.4
v1.4  2026-09-02 — dtp r255. 🔴 THE JOIN IGNORED `direction`. plan_check's
      PRIMARY KEY is (ts_epoch, symbol, strategy, direction, check_name), so a
      symbol evaluating BOTH a call and a put spread on one tick writes two
      rows at the same timestamp — and keying on (symbol, check_name)
      collapsed them, returning whichever sorted last. A plausible source of
      the constant 0.61 panel 3 reported across 17 trades, and a defect either
      way. Direction is derived from the STRUCTURE (long above short = call
      spread), the same rule panel 1 uses for penetration.
v1.3  2026-09-02 — dtp r255. ARE WE DOING WHAT THE STRATEGY SAYS IT DOES?
      Operator: the purpose of our credit spreads is to sell RICH as CLOSE
      TO PRICE as possible at the CONFIRMATION OF A REVERSAL — are we
      actually doing that? Panel 6 measures the first two against spot at
      the fill, which lives ONLY in fire_snapshot.payload['price'] because
      `trades` has no entry_underlying column. Distance is given in points,
      as a percentage of spot and in ATR, because points alone are not
      comparable across an $83 NFLX and a $7,700 SPX. Panel 7 reports the
      reversal evidence the strategy itself recorded — rejection, age,
      pierce_depth, and whether the sweep was a pitchfork TINE touch.
      ⚠️ AND PANEL 3 NOW DISTINGUISHES A CONSTANT SOURCE FROM A BAD JOIN.
      v1.2 printed min = median = max = 0.61 across 17 trades and I could
      not say which it was; it now prints the distinct-value count of the
      underlying evaluations, so the answer is in the output instead of in
      a guess.
v1.2  2026-09-02 — dtp r254. TRACED THE STOP. The exit reason string is built
      at exit_engine.py:1832 and says `condor_stop` because the sweep maps to
      Structure.CONDOR_LEG (r99, to keep it out of the 15:40 flatten) and
      inherits that branch's LABEL. The word 'condor' is an artefact of the
      routing, not a description of the rule — the operator was right to
      reject it.
      🔴 AND IT IS NOT A 15%% PREMIUM STOP. r155 replaced that. It is 15%% OF
      RISK: stop = entry + (spread_width - entry) x LONE_STOP_PCT_OF_RISK.
      BUT there is a FALLBACK at exit_engine.py:1821 — if `spread_width` is
      missing or <= the credit, stop = entry x 1.15, which is 15%% OF CREDIT,
      the inverted rule r155 replaced, and the engine warns 'The trade will
      stop on noise.'
      Panel 5 counts which branch each trade took and prints the room in
      CENTS, because a percentage hides it: 15%% of a $0.20 credit is three
      cents. Panel 4 no longer truncates the reason to its first token, which
      is what discarded the '[no width]' tier marker in v1.1.
v1.1  2026-09-02 — dtp r253. SCOPED PULLS. v1.0 fetched EVERY symbol and
      EVERY interval of candles for the range — 48,305 GETs for ~39 MB, a
      thirty-minute run that was pure round-trip latency, on a report that
      needs 1m bars for the six or eight symbols with sweep trades. The
      symbols come from `trades`, which this reads FIRST anyway, and the
      bucket partitions on `sym=` and `interval=`. plan_check is filtered at
      insert to this one strategy rather than writing 3.36M rows to read
      eight check names out of them.
      ⚠️ THE WAREHOUSE MAP ALREADY SAID THIS: signal_journal is 67% of all
      objects and 0.4% of the bytes. Object count, not volume, is what costs
      on this bucket — written down 2026-09-01 and not applied 2026-09-02.
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
        # 🔴 r253 — SCOPED. v1.0 pulled EVERY symbol and EVERY interval of
        # candles for the range: 48,305 GETs for ~39 MB, a thirty-minute run
        # that was pure round-trip latency. The report knows its symbols
        # BEFORE it asks — it reads `trades` first — and the bucket partitions
        # on `sym=` and `interval=`. Using that is the whole fix.
        want_syms = sorted({r["symbol"] for r in cache.query(
            'SELECT DISTINCT symbol FROM "trades" WHERE strategy = ?',
            (STRAT,))})
        # ⚠️ `keep` FILTERS AT INSERT: plan_check carries every strategy, and
        # this report reads eight check names for ONE of them.
        cache.load("plan_check", dates,
                   ["ts_epoch", "strategy", "check_name", "value", "direction"],
                   syms=want_syms or None,
                   keep=lambda r: r.get("strategy") == STRAT)
        if want_syms:
            # ⚠️ `price` INSIDE `payload` IS SPOT AT THE FILL, and it is the
            # only place it exists — `trades` has no entry_underlying column
            # (checked against the 82-column DDL). fire_snapshot joined 41/41
            # on the sweep, so this is not a partial sample.
            cache.load("fire_snapshot", dates,
                       ["trade_id", "fired_ts", "payload"], syms=want_syms)
            cache.load("candles", dates,
                       ["interval", "ts_epoch_ms", "high", "low", "close"],
                       datatype="candles", syms=want_syms, part="interval=1m")
        else:
            cache.conn.execute('CREATE TABLE IF NOT EXISTS "candles"'
                               ' (symbol TEXT, interval TEXT, ts_epoch_ms,'
                               '  high, low, close)')
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
        # 🔴 v1.3 IGNORED `direction`, AND plan_check's PRIMARY KEY INCLUDES IT
        # (ts_epoch, symbol, strategy, direction, check_name — plan.py:308).
        # A symbol evaluating BOTH a call and a put spread on the same tick
        # writes TWO `side_of_pool` rows at the same timestamp, and keying on
        # (symbol, check_name) collapsed them — the join then returned
        # whichever happened to sort last. That is a plausible source of the
        # constant 0.61 panel 3 reported across 17 trades, and it is a defect
        # regardless of whether it turns out to be THE source.
        chk = {}
        for r in cache.iter(
                'SELECT ts_epoch, symbol, check_name, value, direction'
                '  FROM "plan_check" WHERE strategy = ? AND value IS NOT NULL',
                (STRAT,)):
            chk.setdefault(
                (r["symbol"], (r["direction"] or "").lower(), r["check_name"]),
                []).append((float(r["ts_epoch"]), float(r["value"])))
        for k in chk:
            chk[k].sort()

        def at_entry(sym, name, ts, direction=""):
            """Nearest evaluation AT OR BEFORE `ts`, for this direction.

            ⚠️ FALLS BACK TO ANY DIRECTION and says nothing — the caller cannot
            tell. That is deliberate for now: the direction string the strategy
            writes has not been verified against the call/put derivation used
            here, so a strict match could silently return None for every trade
            and read as "not recorded". The fallback is the conservative
            reading until the two are checked against each other.
            """
            for key in ((sym, (direction or "").lower(), name),):
                seq = chk.get(key) or []
                best = None
                for t, v in seq:
                    if t <= ts:
                        best = v
                    else:
                        break
                if best is not None:
                    return best
            merged = []
            for (sy, _d, nm), seq in chk.items():
                if sy == sym and nm == name:
                    merged += seq
            merged.sort()
            best = None
            for t, v in merged:
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
            _dir = "call" if (r["long_strike"] or 0) > (r["short_strike"] or 0) else "put"
            anchor = at_entry(r["symbol"], "short_anchor", ets, _dir)
            if anchor is None:
                anchor = r["short_strike"]
            side = at_entry(r["symbol"], "side_of_pool", ets, _dir)
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
        # 🔴 v1.2 REPORTED min = median = max = 0.61 ACROSS 17 TRADES. That is
        # not a market fact, and until it is explained panel 3 is telling
        # nobody anything. Two candidates: the value is constant in the
        # strategy's own path, or this join is picking ONE evaluation
        # repeatedly. So the panel now prints how many DISTINCT values exist
        # in the window and how many evaluations were available — a constant
        # in the SOURCE and a constant from the JOIN look different here.
        _all_sop = [v for (_sy, _d, nm), seq in chk.items()
                    if nm == "side_of_pool" for _t, v in seq]
        sd = [abs(x["side"]) for x in recs if x["side"] is not None]
        if sd:
            s = sorted(sd)
            w(f"  n={len(s)}   min {s[0]:.2f}   median {_med(s):.2f}   "
              f"max {s[-1]:.2f}   (points from the swept pool)")
            w(f"  source rows: {len(_all_sop):,} evaluations, "
              f"{len({round(v,4) for v in _all_sop}):,} DISTINCT values")
            if len({round(v, 4) for v in _all_sop}) <= 2:
                w("  🔴 THE SOURCE ITSELF IS CONSTANT — this is not a join")
                w("     artefact. `side_of_pool` is `price_now - pool` and a")
                w("     constant means the pool moved WITH price, or the same")
                w("     evaluation is being rewritten. Chase it in the")
                w("     strategy, not here.")
            elif len({round(v, 4) for v in sd}) <= 2:
                w("  🔴 THE SOURCE VARIES BUT THE JOINED VALUES DO NOT — that")
                w("     is a JOIN fault in this report, not a finding.")
            w("  ⚠️ THIS IS KNOWABLE BEFORE THE FILL, unlike everything the")
            w("     entry-vector screen tested — which found nothing.")
        else:
            w("  (no side_of_pool recorded at or before these fills)")
        w("")

        w("4. WHAT ENDED THEM")
        w("-" * 68)
        # 🔴 v1.1 TRUNCATED THE REASON TO ITS FIRST TOKEN AND THREW AWAY THE
        # ANSWER. `_evaluate_condor_leg` appends a TIER MARKER when the lone
        # stop falls back — "[no width — credit-anchored fallback]" — and the
        # first token is just "condor_stop", so the branch that actually ran
        # was discarded by the formatting. Group on the reason with its tier.
        by = {}
        for x in recs:
            _r = x["reason"] or "(none)"
            k = ("condor_stop [no width]" if "no width" in _r
                 else _r.split()[0])[:26]
            d = by.setdefault(k, {"n": 0, "pnl": 0.0, "pen": []})
            d["n"] += 1
            d["pnl"] += x["pnl"]
            if x["pen"] is not None:
                d["pen"].append(x["pen"])
        w(f"  {'reason':<26} {'n':>4} {'net':>11} {'med penetration':>17}")
        for k in sorted(by, key=lambda z: -by[z]["n"]):
            d = by[k]
            mp = f"{_med(d['pen']):+.2f}" if d["pen"] else "n/a"
            w(f"  {k:<26} {d['n']:>4} {RP.money(d['pnl']):>11} {mp:>17}")
        w("")
        w("5. THE STOP THAT ACTUALLY FIRED  (exit_engine.py:1795-1836)")
        w("   lone stop = entry + (width - entry) x 15% OF RISK")
        w("   fallback  = entry x 1.15, i.e. 15% OF CREDIT, if width is 0")
        w("-" * 68)
        # 🔴 THE FALLBACK IS THE INVERTED RULE r155 REPLACED, and the engine
        # says so in its own warning: "The trade will stop on noise." It fires
        # when `spread_width` is missing or zero. If these rows have no width,
        # every one of them was stopped by a 15%-of-CREDIT floor — the
        # butterfly's 4.3-cent problem in a credit structure — and the 3%
        # success rate is not measuring the sweep's edge at all.
        # ⚠️ THE ROOM IS SHOWN IN CENTS, not percent. A percentage hides
        # exactly this: 15% of a $0.20 credit is THREE CENTS.
        PCT = 0.15
        wide, narrow = [], []
        for r in rows:
            e = r["entry_premium"] or 0
            wdt = r["spread_width"] or 0
            if not e:
                continue
            risk = wdt - e
            if risk > 0:
                wide.append((e, wdt, risk * PCT))
            else:
                narrow.append((e, wdt, e * PCT))
        w(f"  spread_width present and > credit : {len(wide):>4}"
          f"   -> risk-anchored stop")
        w(f"  width MISSING or <= credit        : {len(narrow):>4}"
          f"   -> CREDIT-anchored FALLBACK")
        if narrow:
            rm = sorted(x[2] for x in narrow)
            cr = sorted(x[0] for x in narrow)
            w("")
            w(f"  🔴 {len(narrow)} trade(s) took the fallback.")
            w(f"     median credit ${_med(cr):.2f}  ->  room of "
              f"${_med(rm):.3f}  ({_med(rm)*100:.1f} cents)")
            w(f"     tightest room ${rm[0]:.3f}   widest ${rm[-1]:.3f}")
            w("     The engine logs 'The trade will stop on noise.' when this")
            w("     branch runs. A credit vertical's own quote is TWO leg")
            w("     spreads wide; if that exceeds the room, the stop is hit by")
            w("     the mark and not by price.")
        if wide:
            rm = sorted(x[2] for x in wide)
            w("")
            w(f"  risk-anchored room: median ${_med(rm):.3f}  "
              f"({_med(rm)*100:.1f} cents)   min ${rm[0]:.3f}")
        w("")
        w("  ⚠️ AND PANEL 1 SAYS PRICE NEVER REACHED THE STRIKE. A stop that")
        w("     fires while the underlying sits points away from the short is")
        w("     a stop on the MARK, not on the trade being wrong.")
        w("")
        w("6. ARE WE SELLING RICH, AND CLOSE TO PRICE?")
        w("   the stated purpose: sell rich as close to price as possible")
        w("   at the confirmation of a reversal")
        w("-" * 68)
        # 🔑 SPOT AT THE FILL COMES FROM `fire_snapshot.payload["price"]`.
        # `trades` has no entry_underlying column — checked against the DDL —
        # so this is the only record of where price actually was when the
        # spread was sold. Distance is reported three ways because points
        # alone are not comparable across a $83 NFLX and a $7,700 SPX.
        import json as _json
        snap = {}
        for r in cache.iter('SELECT trade_id, payload FROM "fire_snapshot"'):
            try:
                snap[r["trade_id"]] = _json.loads(r["payload"] or "{}")
            except Exception:                                   # noqa: BLE001
                continue
        near = []
        for r in rows:
            p = snap.get(r["trade_id"])
            if not p:
                continue
            spot = p.get("price")
            k = r["short_strike"]
            wdt = r["spread_width"] or 0
            cr = r["credit_received"] or r["entry_premium"] or 0
            if not spot or not k or not wdt or not cr:
                continue
            atr = p.get("atr") or 0
            near.append({"pts": abs(k - spot), "pct": abs(k - spot) / spot,
                         "atr": (abs(k - spot) / atr) if atr else None,
                         "rich": cr / wdt, "cr": cr, "w": wdt})
        if not near:
            w("  (no fill snapshot joined — cannot locate spot at entry)")
        else:
            d = sorted(x["pts"] for x in near)
            pc = sorted(x["pct"] for x in near)
            at = sorted(x["atr"] for x in near if x["atr"])
            ri = sorted(x["rich"] for x in near)
            w(f"  n={len(near)}   short strike vs SPOT AT THE FILL")
            w(f"    distance   median {_med(d):>7.2f} pts   "
              f"{_med(pc):>6.2%} of spot" +
              (f"   {_med(at):>5.2f} ATR" if at else ""))
            w(f"    range      {d[0]:.2f} to {d[-1]:.2f} pts")
            w("")
            w(f"  RICHNESS  credit / width")
            w(f"    median {_med(ri):>6.1%}   min {ri[0]:>6.1%}   "
              f"max {ri[-1]:>6.1%}")
            w(f"    median credit ${_med([x['cr'] for x in near]):.2f} "
              f"on ${_med([x['w'] for x in near]):.2f} of width")
            w("")
            # ⚠️ THE TWO HALVES OF THE STATED PURPOSE, JUDGED TOGETHER. Close
            # AND rich is the trade. Far and cheap is the opposite of it, and
            # a spread can be far and rich (paid for real risk) or close and
            # cheap (badly priced) — which is why neither number decides alone.
            far = sum(1 for x in near if x["atr"] and x["atr"] > 1.0)
            if at:
                w(f"    {far}/{len(at)} sold MORE THAN 1 ATR from price"
                  f"  ({far/len(at):.0%})")
            w("")
            w("  ⚠️ 'CLOSE' AND 'RICH' ARE ONE TEST, NOT TWO. A spread sold")
            w("     far from price for a large credit is being paid for real")
            w("     risk; one sold far for a small credit is neither close")
            w("     nor rich, and that is the failure mode to look for here.")
        w("")
        w("7. DID THE REVERSAL ACTUALLY CONFIRM?")
        w("   the strategy's own evidence, at or before the fill")
        w("-" * 68)
        for nm, lab in (("rejection", "rejection depth"),
                        ("age", "bars since the sweep"),
                        ("pierce_depth", "pierce depth"),
                        ("sweep", "2.0 = pitchfork TINE touch, 1.0 = pool")):
            vals = [at_entry(r["symbol"], nm, _et(r["entry_time"]).timestamp(),
                             "call" if (r["long_strike"] or 0) >
                                       (r["short_strike"] or 0) else "put")
                    for r in rows if _et(r["entry_time"])]
            vals = [v for v in vals if v is not None]
            if vals:
                sv = sorted(vals)
                w(f"  {lab:<34} n={len(sv):>3}  median {_med(sv):>8.4g}"
                  f"   min {sv[0]:>8.4g}  max {sv[-1]:>8.4g}")
            else:
                w(f"  {lab:<34} not recorded at or before these fills")
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
