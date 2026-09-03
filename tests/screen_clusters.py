#!/usr/bin/env python3
"""day_trader_pro/tests/screen_clusters.py — v1.0
183 TRADES ARE NOT 183 OBSERVATIONS. THEY ARE A HANDFUL OF MOVES.

v1.0  2026-09-03 — dtp r262. Read-only. Trades pull only — no candles, so it
runs in about a minute rather than six.

🔴 EVERY STATISTIC SO FAR TREATED RE-ENTRIES AS INDEPENDENT SAMPLES AND THEY
ARE NOT. Measured on 2026-09-03: **87% of runaway trades (26 of 30) were part
of a multi-entry cluster**, and thirty trades formed just EIGHT clusters — of
which two made the day and two lost it. An AUC computed across 183 rows is
really an AUC across ~40 moves with the big ones counted ten times each.

🔑 THE OPERATOR'S RULING, 2026-09-03: group the cluster into a single trade,
and *"if one of those big moves was preceded by a losing trade, drop that one
and start with the first trade of the move that was profitable, because that's
the info we're looking for."* So each cluster is trimmed of leading losers and
the FIRST WINNER is treated as the move's opening entry.

🔑 WHAT ONE DAY ALREADY SUGGESTS, AND WHY IT NEEDS THIS STUDY. On 2026-09-03
every first-entry-of-cluster won — SIX FOR SIX, avg +$495 — while re-entries
split entirely by regime: 2W/5L and −$1,114 before 11:00, 12W/3L and +$6,320
from 11:00. If that holds, **the trigger is already good and the RE-ENTRY
decision is what is broken.** But 6/6 on one day is exactly the kind of number
that does not survive 183 trades, so this treats it as a HYPOTHESIS.

⚠️ CLUSTERING IS A JUDGEMENT AND THE GAP IS SWEPT, not picked. A move is one
symbol, one direction, with no more than `gap` minutes of quiet between
entries; too tight splits one move into several, too loose merges two. Several
gaps are reported so the finding can be checked against the choice.

⚠️ DIRECTION COMES FROM `option_side` — a call is a long move, a put a short
one — the same derivation r223 used, because `direction` on the row is the
OptionsSignal default for anything that does not set it.

Usage:
    python3 tests/screen_clusters.py --from 2026-08-25 --to 2026-09-03
    python3 tests/screen_clusters.py ... --type RunawayContinuation
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

ET = ZoneInfo("US/Eastern")
UTC = ZoneInfo("UTC")

GAPS = (5, 10, 20)          # minutes of quiet that end a move
PRIMARY_GAP = 10


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


def _stat(v):
    if not v:
        return "n=0"
    w = [x for x in v if x > 0]
    return (f"n={len(v):>3}  {len(w)}W/{len(v)-len(w)}L "
            f"({len(w)/len(v):>4.0%})  net {RP.money(sum(v)):>10}  "
            f"avg {RP.money(sum(v)/len(v)):>8}")


def _cluster(trades, gap_min):
    """One symbol, one direction, no more than `gap_min` of quiet between."""
    by = {}
    for t in trades:
        by.setdefault((t["sym"], t["dir"]), []).append(t)
    out = []
    for key, v in by.items():
        v.sort(key=lambda x: x["ts"])
        cur = [v[0]]
        for x in v[1:]:
            if (x["ts"] - cur[-1]["ts"]) / 60.0 <= gap_min:
                cur.append(x)
            else:
                out.append(cur)
                cur = [x]
        out.append(cur)
    out.sort(key=lambda c: c[0]["ts"])
    return out


def _trim(c):
    """Drop leading losers — the move starts at its first WINNER.

    🔑 OPERATOR: "that's the info that we're looking for." A losing entry
    before the move began is not the move's opening conditions; it is a
    premature guess at them, and averaging it in describes the wrong moment.
    ⚠️ A CLUSTER THAT NEVER WINS TRIMS TO NOTHING and is reported as such
    rather than dropped silently — "the move never started" is a real
    observation about that cluster.
    """
    i = 0
    while i < len(c) and (c[i]["pnl"] or 0) <= 0:
        i += 1
    return c[i:], i


def main(argv):
    ap = argparse.ArgumentParser(description="cluster trades into moves")
    ap.add_argument("--from", dest="d0")
    ap.add_argument("--to", dest="d1")
    ap.add_argument("--type", dest="typ")
    a = ap.parse_args(argv[1:])
    t0 = datetime.now(ET)
    dates = RP.ask_dates(a.d0, a.d1)

    cache = WCACHE.WarehouseCache("clusters")
    try:
        cache.load("trades", dates, RP.COLS + ["option_side"],
                   datatype="trades")
        cache.conn.execute("CREATE INDEX IF NOT EXISTS ix_tr "
                           "ON trades(strategy, status)")
        cache.conn.commit()
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
    w(f"MOVES, NOT TRADES — {dates[0]} .. {dates[-1]} ET — {label}")
    w("=" * 70)
    w("A cluster is one symbol, one direction, with no long gap between")
    w("entries. Leading LOSERS are trimmed: the move starts at its first")
    w("winner, which is where its opening conditions actually are.")
    w("")

    trades = []
    for r in rows:
        ts = _utc(r["entry_time"])
        side = str(r["option_side"] or "").lower()
        if not ts or not side:
            continue
        trades.append({"ts": ts.timestamp(), "sym": r["symbol"],
                       "dir": "long" if side.startswith("c") else "short",
                       "pnl": r["pnl_usd"] or 0.0,
                       "when": ts.astimezone(ET).strftime("%m-%d %H:%M")})
    if not trades:
        w("  nothing to cluster")
        return _emit(out, dates, label, t0)

    # ── THE GAP IS SWEPT, NOT PICKED ────────────────────────────────────
    w("1. HOW MANY MOVES ARE THESE TRADES, REALLY?")
    w("-" * 70)
    w(f"  {'gap':>5}{'clusters':>10}{'multi':>8}{'in multi':>10}"
      f"{'largest':>9}{'median n':>10}")
    for g in GAPS:
        cs = _cluster(trades, g)
        multi = [c for c in cs if len(c) > 1]
        inm = sum(len(c) for c in multi)
        w(f"  {g:>5}{len(cs):>10}{len(multi):>8}"
          f"{inm/len(trades):>9.0%}{max(len(c) for c in cs):>9}"
          f"{_med([len(c) for c in cs]):>10.0f}")
    w("")
    w(f"  ⚠️ AT {PRIMARY_GAP} MIN, {len(trades):,} TRADES ARE "
      f"{len(_cluster(trades, PRIMARY_GAP)):,} MOVES. Every AUC computed so")
    w("     far treated re-entries as independent samples; they are not.")
    w("")

    cs = _cluster(trades, PRIMARY_GAP)

    # ── FIRST ENTRY vs RE-ENTRY ─────────────────────────────────────────
    # 🔴 THE HYPOTHESIS FROM 2026-09-03: every first-of-cluster won (6/6) while
    # re-entries split by regime. If it holds, the TRIGGER is fine and the
    # RE-ENTRY decision is the defect.
    w("2. THE FIRST ENTRY OF A MOVE vs EVERY RE-ENTRY AFTER IT")
    w("   (after trimming leading losers)")
    w("-" * 70)
    firsts, rests, dead, trimmed_ct = [], [], 0, 0
    for c in cs:
        t, dropped = _trim(c)
        trimmed_ct += dropped
        if not t:
            dead += 1
            continue
        firsts.append(t[0]["pnl"])
        rests += [x["pnl"] for x in t[1:]]
    w(f"  FIRST of each move   {_stat(firsts)}")
    w(f"  every RE-ENTRY       {_stat(rests)}")
    w("")
    w(f"  {trimmed_ct:,} leading loser(s) trimmed;  {dead:,} cluster(s) never "
      f"produced a winner")
    if firsts and rests:
        fw = sum(1 for x in firsts if x > 0) / len(firsts)
        rw = sum(1 for x in rests if x > 0) / len(rests)
        w(f"  first-entry win rate {fw:.0%} vs re-entry {rw:.0%}"
          f"   ({fw-rw:+.0%})")
    w("")

    # ── DOES THE FIRST ENTRY PREDICT THE MOVE? ──────────────────────────
    # 🔑 THE DESIGN QUESTION. If the first entry going green predicts the
    # cluster's total, ONE HELD POSITION captures it. If the first is a coin
    # flip and the money is in re-entry seven, holding from the first entry
    # would have been stopped out before the move began — and that changes the
    # whole design.
    w("3. DOES THE FIRST ENTRY PREDICT THE REST OF THE MOVE?")
    w("-" * 70)
    won_first, lost_first = [], []
    for c in cs:
        t, _d = _trim(c)
        if len(t) < 2:
            continue
        rest = sum(x["pnl"] for x in t[1:])
        (won_first if t[0]["pnl"] > 0 else lost_first).append(rest)
    w(f"  move opened GREEN -> the rest netted   {_stat(won_first)}")
    w(f"  move opened RED   -> the rest netted   {_stat(lost_first)}")
    w("  (after trimming, an opening RED can only occur if the cluster's")
    w("   first winner was itself followed by losses — see the note above)")
    w("")

    # ── SIZE vs OUTCOME ─────────────────────────────────────────────────
    w("4. CLUSTER SIZE vs WHAT THE MOVE PAID")
    w("-" * 70)
    w(f"  {'entries':>8}{'moves':>7}{'net':>12}{'avg/move':>12}"
      f"{'win rate':>10}")
    buckets = ((1, 1), (2, 3), (4, 6), (7, 99))
    for lo, hi in buckets:
        sel = [c for c in cs if lo <= len(_trim(c)[0]) <= hi]
        if not sel:
            continue
        nets = [sum(x["pnl"] for x in _trim(c)[0]) for c in sel]
        wins = sum(1 for n in nets if n > 0)
        lab = f"{lo}" if lo == hi else f"{lo}-{hi if hi < 99 else '+'}"
        w(f"  {lab:>8}{len(sel):>7}{RP.money(sum(nets)):>12}"
          f"{RP.money(sum(nets)/len(sel)):>12}{wins/len(sel):>10.0%}")
    w("")

    # ── THE MOVES THEMSELVES ────────────────────────────────────────────
    w("5. EVERY MULTI-ENTRY MOVE")
    w("-" * 70)
    multi = [c for c in cs if len(_trim(c)[0]) > 1]
    multi.sort(key=lambda c: -abs(sum(x["pnl"] for x in _trim(c)[0])))
    w(f"  {'sym':<6}{'opened':<13}{'n':>3}{'net':>11}   entries")
    for c in multi[:20]:
        t, _d = _trim(c)
        net = sum(x["pnl"] for x in t)
        seq = " ".join(f"{x['pnl']:+.0f}" for x in t[:10])
        w(f"  {t[0]['sym']:<6}{t[0]['when']:<13}{len(t):>3}"
          f"{RP.money(net):>11}   {seq}")
    if len(multi) > 20:
        w(f"  ... and {len(multi)-20} more")
    w("")
    w("⚠️ THE CLUSTER BOUNDARY IS A JUDGEMENT. Panel 1 sweeps it so the")
    w("   findings can be checked against the choice; if they only hold at")
    w("   one gap they are about the gap, not about the market.")
    return _emit(out, dates, label, t0)


def _emit(out, dates, label, t0):
    text = "\n".join(out) + "\n"
    slug = (label or "all").replace(" ", "_").lower()
    path = WCACHE.report_path(f"clusters_{dates[0]}_{dates[-1]}_{slug}.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)
    print(f"wrote {path}   ({(datetime.now(ET) - t0).total_seconds():.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
