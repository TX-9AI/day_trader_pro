#!/usr/bin/env python3
"""day_trader_pro/tests/screen_hold.py — v1.0
DID THE MOVE WARRANT HOLDING THROUGH THE WHOLE CLUSTER?

v1.0  2026-09-03 — dtp r263. Read-only.

🔑 THE OPERATOR'S QUESTION, 2026-09-03: *"regardless of whether the cluster
started out negative or positive, did the entirety of the move warrant holding
it until the last exit of the cluster?"* So NO TRIM here — every cluster is
measured whole, from its FIRST entry to its LAST exit, however it opened. That
is deliberately different from `screen_clusters`, where trimming leading losers
made "the first entry won" true by construction.

🔴 WHAT THIS CANNOT DO, AND WHY. The trades in a cluster are DIFFERENT
CONTRACTS at different strikes, so a held position's option P&L cannot be
reconstructed from the trade rows: the first trade's `mfe_premium` stops at its
own exit, and `quote_series` — the only per-contract price history — is 46 GB.
So this measures the UNDERLYING, which answers the question that actually
matters: did the move CONTINUE through the cluster, or did it round-trip? A
move that continued warranted holding; one that round-tripped did not, whatever
the sequence of trades happened to net.

🔑 THE THREE NUMBERS PER MOVE:
  · MFE  — how far the underlying travelled in favour, first entry to last exit
  · NET  — where it actually finished at the last exit
  · GIVEBACK — 1 - NET/MFE. Near 0 the move held its gains and holding was
    right; near 1 it round-tripped and the sequence of stops was the better
    trade.
Reported in ATR so a $713 QQQ and a $7,700 SPX are comparable, with the ATR
taken from BEFORE the first entry — an ATR over the move itself is inflated by
the travel it is normalising.

⚠️ AND THE SEQUENCE P&L SITS BESIDE IT, because the comparison is the point: a
move that gave everything back while the TRADES made money is the case where
the stops earned their keep, and it is the case MOM.1 must not break.

Usage:
    python3 tests/screen_hold.py --from 2026-08-25 --to 2026-09-03
    python3 tests/screen_hold.py ... --type RunawayContinuation
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

GAP_MIN = 10            # matches screen_clusters' primary gap
# ⚠️ A PRIOR, NOT A FIT: below ~0.5 ATR ordinary bar overlap in a rising tape
# would split one advance into a dozen "legs".
LEG_PULLBACK = 0.5
ATR_BARS = 10


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


def _q(v, p):
    s = sorted(v)
    return s[min(len(s) - 1, int(p * (len(s) - 1)))] if s else float("nan")


def main(argv):
    ap = argparse.ArgumentParser(description="did the move warrant holding")
    ap.add_argument("--from", dest="d0")
    ap.add_argument("--to", dest="d1")
    ap.add_argument("--type", dest="typ")
    a = ap.parse_args(argv[1:])
    t0 = datetime.now(ET)
    dates = RP.ask_dates(a.d0, a.d1)

    cache = WCACHE.WarehouseCache("hold")
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
        cache.load("candles", dates, ["interval", "ts_epoch_ms", "high", "low"],
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
    w(f"HOLD THE WHOLE MOVE? — {dates[0]} .. {dates[-1]} ET — {label}")
    w("=" * 72)
    w("NO TRIM: every cluster measured whole, first entry to last exit,")
    w("however it opened. Underlying only — the trades are different")
    w("contracts, so a held option's P&L cannot be reconstructed here.")
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
        w("  nothing to measure")
        return _emit(out, dates, label, t0)

    by = {}
    for t in trades:
        by.setdefault((t["sym"], t["dir"]), []).append(t)
    clusters = []
    for _k, v in by.items():
        v.sort(key=lambda x: x["e"])
        cur = [v[0]]
        for x in v[1:]:
            if (x["e"] - cur[-1]["e"]) / 60.0 <= GAP_MIN:
                cur.append(x)
            else:
                clusters.append(cur)
                cur = [x]
        clusters.append(cur)
    clusters = [c for c in clusters if len(c) > 1]
    clusters.sort(key=lambda c: c[0]["e"])

    bar = Bar("measuring moves", len(clusters))
    recs, skipped = [], 0
    for c in clusters:
        bar.step()
        sym = c[0]["sym"]
        long_side = c[0]["dir"] == "long"
        s_ms = int(c[0]["e"] * 1000)
        e_ms = int(max(x["x"] for x in c) * 1000)
        pre = cache.query(
            'SELECT high, low FROM "candles" WHERE symbol = ? AND interval = ?'
            ' AND ts_epoch_ms BETWEEN ? AND ? ORDER BY ts_epoch_ms',
            (sym, "1m", s_ms - (ATR_BARS + 5) * 60_000, s_ms), max_rows=100)
        pre = [dict(x) for x in pre]
        if len(pre) < 3:
            skipped += 1
            continue
        atr = sum((b["high"] - b["low"]) for b in pre
                  if b["high"] is not None and b["low"] is not None) / len(pre)
        if atr <= 0:
            skipped += 1
            continue
        path = cache.query(
            'SELECT ts_epoch_ms, high, low FROM "candles" WHERE symbol = ?'
            ' AND interval = ? AND ts_epoch_ms BETWEEN ? AND ?'
            ' ORDER BY ts_epoch_ms', (sym, "1m", s_ms, e_ms), max_rows=400)
        path = [dict(x) for x in path]
        if len(path) < 2:
            skipped += 1
            continue
        start = (path[0]["low"] + path[0]["high"]) / 2.0
        # 🔑 THE SHAPE, NOT JUST THE ENDPOINTS. Operator, 2026-09-03: "I'm
        # trying to find out if the momentum PERSISTED, or if it STALLED AND
        # STARTED AGAIN, or STALLED AND GAVE BACK." MFE and NET cannot tell
        # the first two apart — both finish high. So the path is walked:
        #   · LEGS      — how many separate advances, a new extreme after a
        #                 pullback deeper than LEG_PULLBACK ATR
        #   · MFE_AT    — where in the window the best point occurred, as a
        #                 fraction. Late = it was still going. Early = it made
        #                 its money and then did something else.
        #   · STALL     — share of bars making no new extreme
        # ⚠️ A PULLBACK THRESHOLD IS A JUDGEMENT and 0.5 ATR is a prior: below
        # it, ordinary bar overlap would split one advance into a dozen legs.
        prog, best, worst_since, legs, stalled = [], None, 0.0, 1, 0
        for idx, b in enumerate(path):
            ext = b["high"] if long_side else b["low"]
            if best is None:
                best = ext
                prog.append(idx)
                continue
            better = (ext > best) if long_side else (ext < best)
            if better:
                # a new extreme AFTER a real pullback starts a fresh leg
                if worst_since >= LEG_PULLBACK * atr:
                    legs += 1
                best = ext
                worst_since = 0.0
                prog.append(idx)
            else:
                stalled += 1
                back = (best - b["low"]) if long_side else (b["high"] - best)
                worst_since = max(worst_since, back)
        mfe_at = (prog[-1] / max(1, len(path) - 1)) if prog else 0.0
        stall_frac = stalled / len(path)
        # ⚠️ MFE AND NET IN THE MOVE'S OWN DIRECTION. A short move's favourable
        # travel is DOWN; sharing one formula would report every short as a
        # round-trip.
        if long_side:
            mfe = max(x["high"] for x in path) - start
            net = ((path[-1]["high"] + path[-1]["low"]) / 2.0) - start
        else:
            mfe = start - min(x["low"] for x in path)
            net = start - ((path[-1]["high"] + path[-1]["low"]) / 2.0)
        seq = sum(x["pnl"] for x in c)
        # ⚠️ GIVEBACK IS UNDEFINED WHEN THE MOVE NEVER WENT FAVOURABLE — None,
        # not 1.0, because "it never went our way" and "it went our way and
        # handed it all back" are different failures.
        give = (1.0 - net / mfe) if mfe > 0 else None
        # ── the three shapes the operator named ─────────────────────────
        # PERSISTED       — best point late in the window, little giveback
        # STALLED+RESUMED — more than one leg, best point still late
        # STALLED+GAVE    — best point early, giveback large
        if give is None:
            shape = "never went"
        elif mfe_at >= 0.75 and give <= 0.33:
            shape = "PERSISTED" if legs == 1 else "RESUMED"
        elif give >= 0.67:
            shape = "GAVE BACK"
        elif legs > 1:
            shape = "RESUMED"
        else:
            shape = "PARTIAL"
        recs.append({"sym": sym, "when": c[0]["when"], "n": len(c),
                     "mfe": mfe / atr, "net": net / atr,
                     "give": give, "seq": seq, "legs": legs,
                     "mfe_at": mfe_at, "stall": stall_frac, "shape": shape,
                     "mins": (e_ms - s_ms) / 60_000})
    bar.done(f"{len(recs)} moves")

    if not recs:
        w("  no multi-entry moves measurable")
        return _emit(out, dates, label, t0)
    w(f"  {len(clusters)} multi-entry moves   {len(recs)} measured   "
      f"{skipped} lacked bars")
    w("")

    # ══ 1. DID THE MOVE HOLD ITS GAINS? ═════════════════════════════════
    w("1. WHAT SHAPE WAS THE MOVE?")
    w("   PERSISTED = one advance, still going at the last exit")
    w("   RESUMED   = stalled, then made new ground again")
    w("   GAVE BACK = made its money early, handed most of it back")
    w("-" * 72)
    order = ("PERSISTED", "RESUMED", "PARTIAL", "GAVE BACK", "never went")
    w(f"  {'shape':<14}{'moves':>7}{'entries':>9}{'sequence P&L':>15}"
      f"{'med MFE':>9}{'med legs':>10}")
    for sh in order:
        g = [x for x in recs if x["shape"] == sh]
        if not g:
            continue
        w(f"  {sh:<14}{len(g):>7}{sum(x['n'] for x in g):>9}"
          f"{RP.money(sum(x['seq'] for x in g)):>15}"
          f"{_med([x['mfe'] for x in g]):>9.2f}"
          f"{_med([x['legs'] for x in g]):>10.0f}")
    w("")
    # 🔑 THE COMPARISON THAT DECIDES MOM.1: a PERSISTED or RESUMED move
    # warranted holding. A GAVE BACK move that still netted POSITIVE is where
    # the stops earned their keep — and the case MOM.1 must not break.
    keep = [x for x in recs if x["shape"] in ("PERSISTED", "RESUMED")]
    gave = [x for x in recs if x["shape"] == "GAVE BACK"]
    w(f"  worth holding (PERSISTED + RESUMED): {len(keep)} of {len(recs)}"
      f"  ({len(keep)/len(recs):.0%})   {sum(x['n'] for x in keep)} entries"
      f"   {RP.money(sum(x['seq'] for x in keep))}")
    if gave:
        gp = [x for x in gave if x["seq"] > 0]
        w(f"  gave it back: {len(gave)}   of which {len(gp)} STILL netted"
          f" positive ({RP.money(sum(x['seq'] for x in gp))})")
        w("     ⚠️ those are the moves where the stops earned their keep.")
    w("")

    w("2. THE NUMBERS BEHIND THE SHAPES")
    w("-" * 72)
    w(f"  {'':<26}{'median':>10}{'p25':>10}{'p75':>10}")
    for lab, key, fmt in (("MFE (ATR)", "mfe", "{:>10.2f}"),
                          ("NET at last exit (ATR)", "net", "{:>10.2f}"),
                          ("legs (advances)", "legs", "{:>10.0f}"),
                          ("best point, thru window", "mfe_at", "{:>10.0%}"),
                          ("bars making no new high", "stall", "{:>10.0%}")):
        v = [x[key] for x in recs]
        w(f"  {lab:<26}" + fmt.format(_med(v)) + fmt.format(_q(v, .25))
          + fmt.format(_q(v, .75)))
    gv = [x["give"] for x in recs if x["give"] is not None]
    if gv:
        w(f"  {'GIVEBACK (1 - net/mfe)':<26}{_med(gv):>10.0%}"
          f"{_q(gv,.25):>10.0%}{_q(gv,.75):>10.0%}")
    w("")
    # ⚠️ DOES ENTRY COUNT TRACK THE SHAPE? If the big clusters are the moves
    # that persisted, the re-entries were reading the tape correctly and the
    # fix is to hold rather than to refuse.
    w("  entries per move, by shape:")
    for sh in order:
        g = [x for x in recs if x["shape"] == sh]
        if g:
            w(f"    {sh:<14}median {_med([x['n'] for x in g]):>4.0f} entries"
              f"   over {_med([x['mins'] for x in g]):>4.0f} min")
    w("")

    w("3. EVERY MULTI-ENTRY MOVE, WHOLE (no trim)")
    w("-" * 72)
    w(f"  {'sym':<6}{'opened':<13}{'n':>3}{'min':>5}{'MFE':>6}{'NET':>6}"
      f"{'give':>6}{'legs':>5}{'peak':>6}  {'shape':<11}{'sequence':>10}")
    for x in sorted(recs, key=lambda z: -abs(z["seq"]))[:25]:
        g = " n/a" if x["give"] is None else f"{x['give']:>4.0%}"
        w(f"  {x['sym']:<6}{x['when']:<13}{x['n']:>3}{x['mins']:>5.0f}"
          f"{x['mfe']:>6.2f}{x['net']:>6.2f}{g:>6}{x['legs']:>5}"
          f"{x['mfe_at']:>6.0%}  {x['shape']:<11}"
          f"{RP.money(x['seq']):>10}")
    w("")
    w("⚠️ UNDERLYING ONLY. The cluster's trades are DIFFERENT CONTRACTS, so a")
    w("   held position's option P&L is not reconstructible from these rows —")
    w("   `quote_series` is 46 GB and the first trade's mfe_premium stops at")
    w("   its own exit. MFE/NET answer whether the MOVE warranted holding;")
    w("   what a single contract would have paid is a separate question.")
    return _emit(out, dates, label, t0)


def _emit(out, dates, label, t0):
    text = "\n".join(out) + "\n"
    slug = (label or "all").replace(" ", "_").lower()
    path = WCACHE.report_path(f"hold_{dates[0]}_{dates[-1]}_{slug}.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)
    print(f"wrote {path}   ({(datetime.now(ET) - t0).total_seconds():.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
