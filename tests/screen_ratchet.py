#!/usr/bin/env python3
"""day_trader_pro/tests/screen_ratchet.py — v1.0
REPLAY THE RATCHET: would it keep the entries that paid?

v1.0  2026-09-03 — dtp r264. Read-only.

🔑 THE RULE, IN THE OPERATOR'S WORDS (2026-09-03): *"every time the trade stops
out, if we have a one minute candle close above where our trade closed it
enters again"* — refined to *"it would have to open higher than the last one's
PEAK for a long"*, and *"what ends it is no qualifying candle closes allowing a
re-entry."* So:
  · a re-entry needs a 1m CLOSE above the highest point reached by any prior
    leg of this move (below, for a put)
  · the reference only ever RISES — it is a ratchet, not a moving average of
    recent exits. Keying it to the last EXIT would let every loss LOWER the
    bar, so a fading tape would chase price down and re-entry would stay
    permanently easy. That is precisely the META failure.
  · the move ends by ATTRITION. No qualifying close, no re-entry, no move.
    Nothing else needs to end it, and the strategy's own entry window bounds
    the rest.

🔑 WHY A CLOSE AND NOT A TOUCH: "wicks are tests & closes are acceptance." A
wick above the prior peak re-arms you into the fade.

🔴 WHY THIS REPLAY EXISTS RATHER THAN AN ARITHMETIC ESTIMATE. `screen_hold`
showed the two populations separate on LEG COUNT — RESUMED 14 moves / 4 median
legs / +$14,559 against GAVE BACK 16 moves / 1 median leg / −$7,625 — and legs
are what the ratchet counts. But approximating "entries allowed = min(entries,
legs)" truncates NVDA from 10 entries to 5 on a move that made $1,520, and in
the sequence +135 +121 −300 +119 +279 +156 +178 +63 −252 +1020 the LAST entry
made $1,020. **Whether the refused entries are the profitable ones is the only
question that matters, and a leg count cannot answer it.** So the rule is
replayed at each entry's actual timestamp against the actual bars.

⚠️ THE FIRST ENTRY OF A MOVE IS NEVER REFUSED. The ratchet governs RE-entry;
what triggers the opening entry is a separate question this does not touch.

⚠️ AND THE COMPARISON IS PER-ENTRY P&L, NOT A SIMULATION. Refusing an entry
removes exactly that trade's realised P&L. It does NOT model what a held
position would have done instead — the trades are different contracts and that
is `screen_hold`'s stated limit. This answers "which entries would the rule
have kept", nothing more.

Usage:
    python3 tests/screen_ratchet.py --from 2026-08-25 --to 2026-09-03
    python3 tests/screen_ratchet.py ... --type RunawayContinuation
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

GAP_MIN = 10


def _utc(ts):
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(ts)[:19], f).replace(tzinfo=UTC)
        except (ValueError, TypeError):
            continue
    return None


def _med(v):
    s = sorted(v)
    return s[len(s) // 2] if s else float("nan")


def main(argv):
    ap = argparse.ArgumentParser(description="replay the re-entry ratchet")
    ap.add_argument("--from", dest="d0")
    ap.add_argument("--to", dest="d1")
    ap.add_argument("--type", dest="typ")
    a = ap.parse_args(argv[1:])
    t0 = datetime.now(ET)
    dates = RP.ask_dates(a.d0, a.d1)

    cache = WCACHE.WarehouseCache("ratchet")
    try:
        cache.load("trades", dates, RP.COLS + ["option_side"],
                   datatype="trades")
        cache.conn.execute("CREATE INDEX IF NOT EXISTS ix_tr "
                           "ON trades(strategy, status)")
        cache.conn.commit()
        syms = sorted({r["symbol"] for r in cache.query(
            'SELECT DISTINCT symbol FROM "trades" WHERE status = ?',
            ("closed",))})
        if not syms:
            print("  no closed trades")
            return 0
        cache.load("candles", dates,
                   ["interval", "ts_epoch_ms", "high", "low", "close"],
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
    where = "status = ?"
    args = ["closed"]
    if chosen:
        where += " AND strategy = ?"
        args.append(chosen)
    rows = cache.query(f'SELECT * FROM "trades" WHERE {where}', tuple(args))
    out = []
    w = out.append
    label = chosen or "ALL strategies"
    w(f"RATCHET REPLAY — {dates[0]} .. {dates[-1]} ET — {label}")
    w("=" * 74)
    w("RE-ENTRY NEEDS A NEW HIGHER HIGH — a 1m CLOSE above the running")
    w("high of the move so far (a lower low, for a put).")
    w("The move ends when no qualifying close arrives. First entries are")
    w("never refused — the ratchet governs RE-entry only.")
    w("")

    trades = []
    for r in rows:
        e, x = _utc(r["entry_time"]), _utc(r["exit_time"])
        side = str(r["option_side"] or "").lower()
        if not e or not side:
            continue
        trades.append({"e": e.timestamp(),
                       "x": (x.timestamp() if x else e.timestamp()),
                       "sym": r["symbol"],
                       "dir": "long" if side.startswith("c") else "short",
                       "pnl": r["pnl_usd"] or 0.0,
                       "when": e.astimezone(ET).strftime("%m-%d %H:%M")})
    if not trades:
        w("  nothing to replay")
        return _emit(out, dates, label, t0)

    by = {}
    for t in trades:
        by.setdefault((t["sym"], t["dir"]), []).append(t)
    clusters = []
    for _k, v in by.items():
        v.sort(key=lambda z: z["e"])
        cur = [v[0]]
        for x in v[1:]:
            if (x["e"] - cur[-1]["e"]) / 60.0 <= GAP_MIN:
                cur.append(x)
            else:
                clusters.append(cur)
                cur = [x]
        clusters.append(cur)
    clusters.sort(key=lambda c: c[0]["e"])

    bar = Bar("replaying", len(clusters))
    recs, skipped = [], 0
    for c in clusters:
        bar.step()
        sym, long_side = c[0]["sym"], c[0]["dir"] == "long"
        s_ms = int(c[0]["e"] * 1000)
        e_ms = int(max(x["x"] for x in c) * 1000) + 60_000
        bars = cache.query(
            'SELECT ts_epoch_ms, high, low, close FROM "candles"'
            ' WHERE symbol = ? AND interval = ? AND ts_epoch_ms BETWEEN ? AND ?'
            ' ORDER BY ts_epoch_ms', (sym, "1m", s_ms, e_ms), max_rows=500)
        bars = [dict(x) for x in bars]
        if not bars:
            skipped += 1
            continue

        # 🔑 THE REPLAY. Walk the move's legs in order. The reference is the
        # highest point reached WHILE A POSITION WAS LIVE, and it only rises.
        # 🔑 SIMPLIFIED TO STRUCTURE, on the operator's ruling: "it can be as
        # simple as a new higher high (go long) or a new lower low (go
        # short)." The reference is the move's RUNNING EXTREME from its first
        # bar — not the peak reached while a position happened to be live.
        # ⚠️ THAT CLOSES A REAL GAP. With a peak-while-live reference the
        # SECOND entry of a move could never be refused, because no leg had
        # established a peak yet — one loss per fading move survived by
        # construction. A running high exists from bar one.
        ref = None
        taken, refused = [], []
        for i, t in enumerate(c):
            here = int(t["e"] * 1000)
            # the running extreme of everything before this entry
            prior = [b for b in bars if b["ts_epoch_ms"] < here]
            if prior:
                ext = (max(b["high"] for b in prior) if long_side
                       else min(b["low"] for b in prior))
                ref = ext if ref is None else (max(ref, ext) if long_side
                                               else min(ref, ext))
            if i == 0:
                taken.append(t)
                continue
            else:
                # ⚠️ A CLOSE, NOT A TOUCH, and it must occur BETWEEN the prior
                # exit and this entry — a close after the fact proves nothing
                # about the decision made at the fill.
                # ⚠️ A CLOSE, NOT A TOUCH — "wicks are tests, closes are
                # acceptance." A wick above the running high re-arms into the
                # fade. And the close must land BETWEEN the prior exit and
                # this entry: a close after the fact proves nothing about the
                # decision made at the fill.
                prev_x = int(c[i - 1]["x"] * 1000)
                window = [b for b in bars
                          if prev_x <= b["ts_epoch_ms"] <= here
                          and b["close"] is not None]
                # ⚠️ THE BAR THAT SETS THE HIGH CANNOT ALSO CLEAR IT. `ref` is
                # the extreme of everything strictly BEFORE this entry, and the
                # qualifying close is compared against the extreme as it stood
                # BEFORE that close — otherwise every new high trivially
                # "closes above" itself.
                prior_ext = None
                ok = False
                for b in window:
                    pe = [z for z in bars if z["ts_epoch_ms"] < b["ts_epoch_ms"]]
                    if not pe:
                        continue
                    prior_ext = (max(z["high"] for z in pe) if long_side
                                 else min(z["low"] for z in pe))
                    if ((b["close"] > prior_ext) if long_side
                            else (b["close"] < prior_ext)):
                        ok = True
                        break
                (taken if ok else refused).append(t)
        recs.append({"sym": sym, "when": c[0]["when"], "n": len(c),
                     "taken": taken, "refused": refused,
                     "actual": sum(x["pnl"] for x in c),
                     "kept": sum(x["pnl"] for x in taken),
                     "cut": sum(x["pnl"] for x in refused)})
    bar.done(f"{len(recs)} moves")

    if not recs:
        w("  nothing measurable")
        return _emit(out, dates, label, t0)

    n_act = sum(x["n"] for x in recs)
    n_kept = sum(len(x["taken"]) for x in recs)
    n_cut = sum(len(x["refused"]) for x in recs)
    w(f"  {len(recs)} moves   {n_act} entries   {skipped} skipped")
    w("")
    w("1. WHAT THE RATCHET WOULD HAVE DONE")
    w("-" * 74)
    w(f"  entries taken   {n_kept:>4}  ({n_kept/n_act:>4.0%})   "
      f"P&L {RP.money(sum(x['kept'] for x in recs)):>10}")
    w(f"  entries REFUSED {n_cut:>4}  ({n_cut/n_act:>4.0%})   "
      f"P&L {RP.money(sum(x['cut'] for x in recs)):>10}"
      f"   <- what we would NOT have made or lost")
    w(f"  actual, all entries         "
      f"P&L {RP.money(sum(x['actual'] for x in recs)):>10}")
    w("")
    cutw = [t for x in recs for t in x["refused"] if t["pnl"] > 0]
    cutl = [t for x in recs for t in x["refused"] if t["pnl"] <= 0]
    w(f"  of the refused: {len(cutw)} winners "
      f"({RP.money(sum(t['pnl'] for t in cutw))}), "
      f"{len(cutl)} losers ({RP.money(sum(t['pnl'] for t in cutl))})")
    kepw = [t for x in recs for t in x["taken"] if t["pnl"] > 0]
    kepl = [t for x in recs for t in x["taken"] if t["pnl"] <= 0]
    if kepw or kepl:
        w(f"  of the kept:    {len(kepw)} winners "
          f"({RP.money(sum(t['pnl'] for t in kepw))}), "
          f"{len(kepl)} losers ({RP.money(sum(t['pnl'] for t in kepl))})")
        w(f"  kept win rate {len(kepw)/(len(kepw)+len(kepl)):.0%} vs actual "
          f"{sum(1 for x in recs for t in x['taken']+x['refused'] if t['pnl']>0)/n_act:.0%}")
    w("")

    # 🔴 THE QUESTION THE LEG-COUNT ESTIMATE COULD NOT ANSWER: does it keep
    # the entries that PAID? A rule that refuses the losers and the winners in
    # equal measure has done nothing but reduce the sample.
    w("2. DID IT KEEP THE ENTRIES THAT PAID?")
    w("-" * 74)
    big = sorted((t for x in recs for t in x["taken"] + x["refused"]),
                 key=lambda t: -t["pnl"])[:10]
    w("  the ten biggest winners, and whether the ratchet keeps them:")
    for t in big:
        keep = any(t in x["taken"] for x in recs)
        w(f"    {t['sym']:<6}{t['when']:<13}{RP.money(t['pnl']):>10}"
          f"   {'KEPT' if keep else 'REFUSED'}")
    w("")

    w("3. EVERY MOVE")
    w("-" * 74)
    w(f"  {'sym':<6}{'opened':<13}{'n':>3}{'kept':>6}{'cut':>5}"
      f"{'actual':>10}{'ratchet':>10}{'delta':>10}")
    for x in sorted(recs, key=lambda z: -abs(z["actual"]))[:25]:
        w(f"  {x['sym']:<6}{x['when']:<13}{x['n']:>3}{len(x['taken']):>6}"
          f"{len(x['refused']):>5}{RP.money(x['actual']):>10}"
          f"{RP.money(x['kept']):>10}"
          f"{RP.money(x['kept']-x['actual']):>10}")
    w("")
    w("⚠️ PER-ENTRY P&L, NOT A SIMULATION. Refusing an entry removes exactly")
    w("   that trade's realised P&L; it does NOT model what a held position")
    w("   would have done instead. This answers which entries the rule keeps.")
    return _emit(out, dates, label, t0)


def _emit(out, dates, label, t0):
    text = "\n".join(out) + "\n"
    slug = (label or "all").replace(" ", "_").lower()
    path = WCACHE.report_path(f"ratchet_{dates[0]}_{dates[-1]}_{slug}.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)
    print(f"wrote {path}   ({(datetime.now(ET) - t0).total_seconds():.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
