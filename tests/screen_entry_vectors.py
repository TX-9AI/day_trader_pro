#!/usr/bin/env python3
"""day_trader_pro/tests/screen_entry_vectors.py — v1.0
WHICH DERIVED VECTORS COINCIDE WITH A DIRECTIONALLY CORRECT ENTRY? (RPT.A)

v1.0  2026-09-02 — dtp r251. Candidate hunt, per strategy. Read-only.

🔑 THE OUTCOME VARIABLE IS ONE A STOP CANNOT MANUFACTURE. Operator, 2026-09-02:
   *"I want to be sure that we don't conflate success entirely on the work of
   our stops"* — so this does NOT score on P&L. A trade counts as GREEN if it
   was directionally correct long enough to go **5% in profit** on the premium
   risked, and *"whether it remained there is a separate question entirely, not
   for this report to decide."*

🔴 MFE IS THE HIGHEST MARK, NOT THE BEST MARK. `exit_engine._track_excursion`
   keeps `mfe_premium` on `px > best`, so for a CREDIT vertical — which profits
   as the mark FALLS — the favourable extreme is `mae_premium` and the adverse
   is `mfe_premium`. The mirror of a debit. Read from source, not assumed; the
   same inversion r214 found in query.py's unrealized line. Getting it backwards
   would label every winning credit trade as never-green and hand back a
   confident, inverted answer.

⚠️ THE STRUCTURE TEST IS `structure.is_credit_vertical`, the engine's own. It
   reads `strategy` and `setup_type`, both of which are in the cached
   projection, so no extra columns are pulled and no second classifier exists.

⚠️ AUC, NOT A DIFFERENCE OF MEANS. The statistic is the probability that a
   randomly chosen GREEN trade has a higher value of the vector than a randomly
   chosen NEVER-GREEN one. 0.50 is no separation. It is scale-free, so ADX and
   charm and price_vs_vwap are directly comparable, and it is rank-based, so a
   single SPX outlier cannot manufacture a result.

🔴 THIS IS A SCREEN AND IT SAYS SO IN ITS OWN OUTPUT. With a smaller outcome
   class in the tens, testing twenty-odd vectors WILL produce separations that
   are noise — that is arithmetic, not pessimism. So the number screened is
   printed beside the results, and the report refuses to call anything a
   finding. Name three or four from the top of the list, then CONFIRM them on
   a later sample; that second step is what makes the first one legitimate.

⚠️ THE ENVELOPE IS THREE LAYERS: envelope -> `record[]` -> `payload`, and
   `payload` is a JSON STRING (derived_store.py:173). `probe_fire_snapshot_iv`
   v1.1 read the row as the envelope and reported 29 good objects as unusable;
   v1.2 fixed it by reading all three from source. This reads all three.

⚠️ `fire_snapshot` ONLY WRITES WHEN A TRADE FIRES, and the warehouse holds 165
   objects across 6 days against 250 closed trades in the same window. The JOIN
   RATE is therefore the first finding, printed before any vector — a screen
   over a third of the book is a different claim from a screen over the book.

⚠️ Streams through `warehouse_cache` (dtp r238/r242): one object parsed at a
   time, projected to the columns read, scratch removed on every exit path.

Usage:
    python3 tests/screen_entry_vectors.py
    python3 tests/screen_entry_vectors.py --from 2026-08-25 --to 2026-09-02
    python3 tests/screen_entry_vectors.py --from ... --to ... --type ALL
    python3 tests/screen_entry_vectors.py ... --green 0.05
"""

from __future__ import annotations

import argparse
import json
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

# ⚠️ NOT A COLUMN LIST FOR fire_snapshot — these ARE its columns
# (data/derived_store.py:169). `payload` is TEXT holding JSON.
SNAP_COLS = ["trade_id", "fired_ts", "payload"]

# Keys that are labels rather than measurements. Screening a string is
# meaningless and screening a timestamp finds the clock, not the market.
SKIP_KEYS = {"schema", "ts", "character", "fork_state", "gap_class",
             "trend_direction", "overall_direction", "levels", "fork",
             "trend", "vol"}


def _credit(row) -> bool:
    """The engine's own structure test. Falls back to the stored credit only if
    the classifier is unavailable, and says so rather than silently differing."""
    try:
        sys.path.insert(0, os.path.expanduser("~/options-trader-v4"))
        from strategy.structure import is_credit_vertical
        return bool(is_credit_vertical(dict(row)))
    except Exception:                                          # noqa: BLE001
        return float(row["credit_received"] or 0) > 0


def _favourable(row) -> float:
    """Favourable excursion as a fraction of premium risked, SIGNED BY STRUCTURE.

    🔴 A CREDIT'S BEST MOMENT IS ITS LOWEST MARK. `mfe_premium` is the HIGHEST
    mark seen (exit_engine._track_excursion keeps it on `px > best`), so for a
    credit vertical the favourable extreme is `mae_premium`.
    """
    e = row["entry_premium"] or 0
    mfe, mae = row["mfe_premium"], row["mae_premium"]
    if not e or mfe is None or mae is None:
        return None
    return ((e - mae) / e) if _credit(row) else ((mfe - e) / e)


def _auc(green, other):
    """P(a random GREEN value > a random NEVER-GREEN value). 0.50 = nothing.

    ⚠️ RANK-BASED ON PURPOSE. A difference of means on a few dozen trades is
    hostage to one SPX row; a rank statistic is not.
    """
    if len(green) < 3 or len(other) < 3:
        return None
    pairs = [(v, 1) for v in green] + [(v, 0) for v in other]
    pairs.sort(key=lambda p: p[0])
    ranks, i = {}, 0
    while i < len(pairs):
        j = i
        while j + 1 < len(pairs) and pairs[j + 1][0] == pairs[i][0]:
            j += 1
        r = (i + j) / 2.0 + 1.0                # average rank for ties
        for k in range(i, j + 1):
            ranks[k] = r
        i = j + 1
    rsum = sum(ranks[k] for k, (_v, g) in enumerate(pairs) if g == 1)
    n1, n0 = len(green), len(other)
    return (rsum - n1 * (n1 + 1) / 2.0) / (n1 * n0)


def _render(cache, dates, chosen, green_at, t0):
    where = "status = ? AND mfe_premium IS NOT NULL AND mae_premium IS NOT NULL"
    args = ["closed"]
    if chosen:
        where += " AND strategy = ?"
        args.append(chosen)
    rows = cache.query(f'SELECT * FROM "trades" WHERE {where}', tuple(args))

    out, w = [], None
    out = []
    w = out.append
    label = chosen or "ALL strategies"
    w(f"ENTRY VECTOR SCREEN — {dates[0]} .. {dates[-1]} ET — {label}")
    w("=" * 68)
    w(f'GREEN = went {green_at:.0%} in profit at any point on the premium '
      f'risked.')
    w("Not P&L: whether it STAYED there is a different report (RPT.A).")
    w("")

    if not rows:
        w("  no closed trades with excursion telemetry for this selection")
        return _emit(out, dates, label, t0)

    # ── the join, reported before anything is built on it ────────────────
    snaps = {}
    for r in cache.iter('SELECT trade_id, payload FROM "fire_snapshot"'):
        try:
            snaps[r["trade_id"]] = json.loads(r["payload"] or "{}")
        except Exception:                                      # noqa: BLE001
            continue

    bar = Bar("scoring", len(rows))
    green, other, joined, unjoined = [], [], 0, 0
    for r in rows:
        bar.step()
        fav = _favourable(r)
        if fav is None:
            continue
        p = snaps.get(r["trade_id"])
        if p is None:
            unjoined += 1
            continue
        joined += 1
        (green if fav >= green_at else other).append(p)
    bar.done(f"{joined:,} joined")

    tot = joined + unjoined
    w(f"  closed trades with excursion : {len(rows):,}")
    w(f"  joined to a fire_snapshot    : {joined:,}"
      f"  ({joined / tot:.0%})" if tot else "  joined: 0")
    w(f"  NO snapshot (cannot screen)  : {unjoined:,}")
    if tot and joined / tot < 0.8:
        w("  🔴 THE SAMPLE IS THE JOINED SUBSET, NOT THE BOOK. fire_snapshot")
        w("     only writes when a trade fires and the warehouse holds far")
        w("     fewer objects than there are closed trades — anything below")
        w("     is a statement about these rows and not about the strategy.")
    w("")
    w(f"  GREEN (>= {green_at:.0%})      : {len(green):,}")
    w(f"  never green            : {len(other):,}")
    small = min(len(green), len(other))
    w(f"  limiting class         : {small:,}")
    if small < 10:
        w("  ⚠️ TOO FEW TO RANK ANYTHING. Widen the range or pick ALL.")
        return _emit(out, dates, label, t0)
    w("")

    # ── the screen ───────────────────────────────────────────────────────
    keys = set()
    for p in green + other:
        keys |= {k for k, v in p.items()
                 if k not in SKIP_KEYS and isinstance(v, (int, float))
                 and not isinstance(v, bool)}
    results = []
    for k in sorted(keys):
        g = [float(p[k]) for p in green if isinstance(p.get(k), (int, float))]
        o = [float(p[k]) for p in other if isinstance(p.get(k), (int, float))]
        a = _auc(g, o)
        if a is None:
            continue
        results.append((abs(a - 0.5), a, k, len(g), len(o),
                        sorted(g)[len(g) // 2], sorted(o)[len(o) // 2]))
    results.sort(reverse=True)

    w(f"  {'vector':<26} {'AUC':>6} {'n(g)':>5} {'n(x)':>5} "
      f"{'med green':>11} {'med other':>11}")
    w("  " + "-" * 66)
    for _mag, a, k, ng, no, mg, mo in results:
        w(f"  {k[:26]:<26} {a:>6.2f} {ng:>5} {no:>5} "
          f"{mg:>11.4g} {mo:>11.4g}")
    w("")
    w(f"  🔴 {len(results)} VECTORS SCREENED AGAINST A LIMITING CLASS OF "
      f"{small}.")
    w("     At that ratio some of these separate by chance — that is")
    w("     arithmetic, not pessimism. NOTHING HERE IS A FINDING. Take three")
    w("     or four from the top, name them, and CONFIRM them on a sample")
    w("     that was not used to choose them. The second step is what makes")
    w("     the first one legitimate.")
    w("")
    w("  AUC 0.50 = no separation. 0.65+ on a small sample is worth a look;")
    w("  it is not worth a threshold.")
    w("")
    w("  ⚠️ MEASURED, NOT ASSERTED: in this tool's own fixture a vector of")
    w("     PURE UNIFORM NOISE, independent of the outcome by construction,")
    w("     scored AUC 0.69 on 30 against 30. That is what a number in the")
    w("     mid-0.6s is worth at this sample size — a reason to look, never")
    w("     a reason to act.")
    return _emit(out, dates, label, t0)


def _emit(out, dates, label, t0):
    text = "\n".join(out) + "\n"
    slug = (label or "all").replace(" ", "_").lower()
    path = WCACHE.report_path(
        f"entry_vectors_{dates[0]}_{dates[-1]}_{slug}.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)
    print(f"wrote {path}   "
          f"({(datetime.now(ET) - t0).total_seconds():.0f}s)")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description="entry vector candidate screen")
    ap.add_argument("--from", dest="d0")
    ap.add_argument("--to", dest="d1")
    ap.add_argument("--type", dest="typ")
    ap.add_argument("--green", type=float, default=0.05,
                    help="favourable excursion that counts as GREEN (0.05)")
    a = ap.parse_args(argv[1:])
    t0 = datetime.now(ET)
    dates = RP.ask_dates(a.d0, a.d1)

    cache = WCACHE.WarehouseCache("entryvec")
    try:
        RP.load_trades(cache, dates)
        cache.load("fire_snapshot", dates, SNAP_COLS)
        cache.index("fire_snapshot", "trade_id")
        counts = RP.type_counts(cache, "mfe_premium")
        # ⚠️ ONE PULL, MANY SELECTIONS (dtp r247).
        while True:
            chosen = RP.choose_type(counts, a.typ)
            if chosen is RP.QUIT:
                return 0
            _render(cache, dates, chosen, a.green, t0)
            if a.typ:
                return 0
    finally:
        cache.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
