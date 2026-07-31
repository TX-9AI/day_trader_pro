#!/usr/bin/env python3
"""
tests/gate_ledger.py — v1.1 — 2026-07-31
v1.1 — ORBStrategy excluded from both blocked populations. v1.0 counted it, and
       on the first real run ORB was +$3,343 of a +$4,196 "blocked" total — a
       verdict dominated by trades the gate cannot refuse. ORB short-circuits to
       _grade_orb before either gate exists (E exempt by construction per defect
       V; F counter-only). Removing it changes E's fit population from
       net +$4,196 to net +$853, and separates cleanly per strategy.

THE WOULD-HAVE-BLOCKED LEDGER for gates E (VWAP) and F (MIN_RRR).

Both gates shipped 2026-07-31 DEFAULT OFF, as log-only counters, under the house
rule that evidence decides. This is the evidence. It answers one question per
gate: **of the trades this gate would have refused, what did they actually
make?** A gate that removes net-negative trades earns its default; a gate that
removes net-positive trades is a tax on the strategy it guards.

HOW IT JOINS
    signal_journal `scored` events carry vwap + price_vs_vwap (since 07-18) and
    rrr (since 07-31, via N.2). trades.db carries the outcome. The documented
    join key is `ts_et`: events within the same second for the same
    symbol/strategy are the same signal — the loop is single-threaded per box,
    one signal per tick. Entry timestamps are matched within a tolerance because
    the trade row is written after the fill, not at the score.

WHY THE VERDICT IS SPLIT PER STRATEGY, NOT JUST PER GATE
    E applies to exactly two strategies, and they relate to VWAP OPPOSITELY.
    Continuation is trend-following: misalignment is genuine evidence the entry
    is wrong-sided, which is the case E was reasoned from. **SweepReversal is a
    FADE** — a low sweep produces a LONG while price is still under VWAP, and
    the strategy treats VWAP recovery as a confluence BONUS, not a requirement.
    So valid sweep longs are misaligned BY DESIGN.

    Sweep is the fleet's highest-volume strategy (985 lifetime trades) and among
    its best. A pooled "ship it" driven by continuation's numbers would turn on a
    gate that guts it. Three outcomes, decided explicitly:
      both net-negative              -> ship ON for both
      continuation neg, sweep pos    -> EXEMPT SWEEP the way ORB is exempt
      both positive                  -> stays OFF; the counter is the finding

FIT / HOLDOUT
    A gate fitted and accepted on the same sessions is fitted to noise. Sessions
    are split deterministically (sha1 of the date, 30% held out) so the split is
    reproducible across runs and machines rather than depending on when you ran
    it. **Ship-ON bar: the blocked population must be net-negative on the
    HOLDOUT**, not merely on the fit.

READ THE COVERAGE LINE FIRST
    `rrr` only began being journaled on 2026-07-31 (N.2). Every scored event
    before that has NO rrr, so F's ledger is near-empty by construction and will
    stay thin until several sessions accumulate. The tool says so loudly rather
    than reporting a two-trade verdict as if it meant something — that failure
    mode has cost this project real hours already.

USAGE
    python3 tests/gate_ledger.py
    python3 tests/gate_ledger.py --since 2026-07-18 --min-n 20

Read-only. Touches no live system.
"""

import argparse
import collections
import glob
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOURNAL_ROOT = os.environ.get("DTP_JOURNAL_ROOT", os.path.join(REPO, "signal_journal"))
TRADES_ROOT = os.environ.get("DTP_TRADES_ROOT", os.path.join(REPO, "trades"))

HOLDOUT_FRACTION = 0.30
JOIN_TOLERANCE_S = 90          # score -> fill; generous, the loop is 15s/tick


def is_holdout(date_str: str) -> bool:
    """Deterministic 30% session holdout.

    sha1 of the date rather than random or modulo-index: reproducible on any
    machine, on any run, and not correlated with weekday (a modulo split would
    systematically hold out the same weekday, and Mondays are not Fridays).
    """
    h = int(hashlib.sha1(date_str.encode()).hexdigest()[:8], 16)
    return (h % 100) < int(HOLDOUT_FRACTION * 100)


def _parse_ts(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None


def load_scored(date):
    """Every `scored` event for a session, flattened to what the gates need."""
    out = []
    for f in sorted(glob.glob(os.path.join(JOURNAL_ROOT, date, "*.jsonl"))):
        sym = os.path.basename(f).split(".")[0]
        try:
            with open(f) as fh:
                for line in fh:
                    line = line.strip()
                    if not line or '"scored"' not in line:
                        continue
                    try:
                        r = json.loads(line)
                    except Exception:                          # noqa: BLE001
                        continue
                    if r.get("event") != "scored":
                        continue
                    sig = r.get("signal") or {}
                    vol = r.get("vol") or {}
                    sc = r.get("score") or {}
                    out.append({
                        "date": date, "symbol": sym,
                        "ts": _parse_ts(r.get("ts_et")),
                        "strategy": sig.get("strategy", ""),
                        "direction": sig.get("direction", ""),
                        "grade": sc.get("grade", ""),
                        "vwap": float(vol.get("vwap") or 0.0),
                        "pvv": vol.get("price_vs_vwap", "NONE"),
                        "rrr": sig.get("rrr"),
                    })
        except Exception:                                       # noqa: BLE001
            continue
    return out


def load_trades(date):
    """Outcomes for a session, keyed for the ts_et join."""
    rows = []
    pat = os.path.join(TRADES_ROOT, date, f"*_trades_{date}.db")
    files = sorted(glob.glob(pat)) or sorted(
        glob.glob(os.path.join(TRADES_ROOT, date, "*trades*.db")))
    for f in files:
        sym = os.path.basename(f).split("_")[0]
        try:
            con = sqlite3.connect(f"file:{f}?mode=ro", uri=True)
            cols = [c[1] for c in con.execute("PRAGMA table_info(trades)")]
            if "entry_time" not in cols:
                con.close()
                continue
            q = ("SELECT entry_time, strategy, setup_type, direction, pnl_usd, "
                 "setup_grade FROM trades WHERE entry_time LIKE ?")
            for et, strat, stype, direction, pnl, grade in con.execute(q, (date[:8] + "%",)):
                t = _parse_ts(et)
                if t is None:
                    continue
                rows.append({"symbol": sym, "ts": t, "strategy": strat or "",
                             "setup_type": stype or "", "direction": direction or "",
                             "pnl": float(pnl or 0.0), "grade": grade or ""})
            con.close()
        except Exception:                                       # noqa: BLE001
            continue
    return rows


def join(scored, trades):
    """Attach the outcome to each scored event that became a trade.

    Same symbol + same strategy + entry within JOIN_TOLERANCE_S of the score.
    Nearest match wins, each trade consumed once — a scored event with no trade
    was declined downstream (sizing, invalid, or a gate) and has no P&L to
    contribute either way.
    """
    by_key = collections.defaultdict(list)
    for t in trades:
        by_key[(t["symbol"], t["strategy"])].append(t)
    used = set()
    for s in scored:
        s["pnl"] = None
        if s["ts"] is None:
            continue
        best, best_d = None, None
        for i, t in enumerate(by_key.get((s["symbol"], s["strategy"]), [])):
            if (s["symbol"], s["strategy"], i) in used:
                continue
            d = abs((t["ts"] - s["ts"]).total_seconds())
            if d <= JOIN_TOLERANCE_S and (best_d is None or d < best_d):
                best, best_d = i, d
        if best is not None:
            used.add((s["symbol"], s["strategy"], best))
            s["pnl"] = by_key[(s["symbol"], s["strategy"])][best]["pnl"]
            s["setup_type"] = by_key[(s["symbol"], s["strategy"])][best]["setup_type"]
    return scored


# Strategies the gates CANNOT touch. ORBStrategy short-circuits to _grade_orb at
# the top of score() and never reaches either gate — it is exempt by
# construction (defect V), not by a flag. A first cut of this ledger omitted the
# check and reported ORB inside E's blocked population: +$3,343 of a +$4,196
# total, dominating a verdict for trades the gate can never refuse. Caught on the
# first real run.
GATE_EXEMPT = {"ORBStrategy"}


def eligible(s, gate):
    """Would this signal even reach the gate?"""
    if s["strategy"] in GATE_EXEMPT:
        return False
    if gate == "F" and s["strategy"] in GATE_EXEMPT:
        return False        # F is counter-only for ORB — never blocks it either
    return True


def e_blocks(s):
    """E's condition, mirroring risk/setup_scorer.py exactly."""
    if not eligible(s, "E"):
        return False
    return (s["vwap"] > 0
            and s["pvv"] in ("ABOVE", "BELOW")
            and s["direction"] in ("long", "short")
            and not ((s["direction"] == "long" and s["pvv"] == "ABOVE")
                     or (s["direction"] == "short" and s["pvv"] == "BELOW")))


def f_blocks(s, floor):
    """F's condition. rrr None is INERT — absence of evidence, not a violation.

    ORB is excluded here too: F ships COUNTER-ONLY for the ORB, logging when a
    confirmed ORB would fail the floor and trading it anyway. Counting those as
    "blocked" would describe a gate that does not exist.
    """
    if not eligible(s, "F"):
        return False
    return s["rrr"] is not None and float(s["rrr"]) < floor


def verdict(rows, label, min_n):
    """One population's verdict. Returns (line, ship_signal)."""
    traded = [r for r in rows if r["pnl"] is not None]
    n = len(traded)
    net = sum(r["pnl"] for r in traded)
    wins = sum(1 for r in traded if r["pnl"] > 0)
    wr = (100.0 * wins / n) if n else 0.0
    if n < min_n:
        return (f"    {label:<26} n={n:<4} net=${net:>10,.2f}  wr={wr:>4.0f}%   "
                f"** THIN (n<{min_n}) — no verdict **"), None
    sig = net < 0
    return (f"    {label:<26} n={n:<4} net=${net:>10,.2f}  wr={wr:>4.0f}%   "
            f"{'blocked pop is NET-NEGATIVE' if sig else 'blocked pop is NET-POSITIVE'}"), sig


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-07-18",
                    help="scored events carry vwap from 07-18; earlier needs replay")
    ap.add_argument("--min-n", type=int, default=20,
                    help="below this, report THIN and refuse a verdict")
    ap.add_argument("--floor", type=float,
                    default=float(os.environ.get("OT_MIN_RRR", "1.3")))
    a = ap.parse_args(argv[1:])

    dates = sorted(d for d in os.listdir(JOURNAL_ROOT)
                   if len(d) == 10 and d >= a.since) if os.path.isdir(JOURNAL_ROOT) else []
    if not dates:
        print(f"no journal sessions under {JOURNAL_ROOT} on/after {a.since}")
        return 2

    allrows = []
    for d in dates:
        sc = join(load_scored(d), load_trades(d))
        allrows += sc

    n_rrr = sum(1 for r in allrows if r["rrr"] is not None)
    fit = [r for r in allrows if not is_holdout(r["date"])]
    hold = [r for r in allrows if is_holdout(r["date"])]

    print("=" * 84)
    print(f"  GATE LEDGER — {len(dates)} sessions ({dates[0]} → {dates[-1]})")
    print("=" * 84)
    print(f"  scored events: {len(allrows)}   joined to a trade: "
          f"{sum(1 for r in allrows if r['pnl'] is not None)}")
    _nh, _nf = len(set(r["date"] for r in hold)), len(set(r["date"] for r in fit))
    _frac = _nh / max(1, _nh + _nf)
    print(f"  fit sessions: {_nf}   holdout: {_nh} "
          f"({_frac:.0%} — target {HOLDOUT_FRACTION:.0%})")
    print(f"  holdout dates: {sorted(set(r['date'] for r in hold))}")
    if abs(_frac - HOLDOUT_FRACTION) > 0.12:
        print(f"  !  holdout fraction is off target — a hash split only converges")
        print(f"     with session count. With {_nh+_nf} sessions this is expected;")
        print(f"     it is NOT a reason to reroll the split (that would be fitting")
        print(f"     the split itself). Weight the verdict by n, not by fraction.")
    print(f"  rrr COVERAGE: {n_rrr}/{len(allrows)} events "
          f"({100.0*n_rrr/max(1,len(allrows)):.1f}%)")
    if n_rrr < len(allrows) * 0.5:
        print("  !! rrr was only journaled from 2026-07-31 (N.2). F's ledger is")
        print("     near-empty BY CONSTRUCTION until sessions accumulate. Do not")
        print("     read a thin F verdict as a real one — carry it forward.")

    for gate, pred in (("E — VWAP", lambda r: e_blocks(r)),
                       ("F — MIN_RRR", lambda r: f_blocks(r, a.floor))):
        print(f"\n{'-'*84}\n  {gate}\n{'-'*84}")
        for pop_name, pop in (("FIT", fit), ("HOLDOUT", hold)):
            blocked = [r for r in pop if pred(r)]
            print(f"  {pop_name}:")
            line, _ = verdict(blocked, "ALL STRATEGIES", a.min_n)
            print(line)
            per = collections.defaultdict(list)
            for r in blocked:
                per[r["strategy"] or "?"].append(r)
            for strat, rows in sorted(per.items(), key=lambda kv: -len(kv[1])):
                line, _ = verdict(rows, f"  {strat}", a.min_n)
                print(line)
        # ship decision reads the HOLDOUT only
        hb = [r for r in hold if pred(r)]
        _, sig = verdict(hb, "x", a.min_n)
        print(f"  -> SHIP-ON BAR (holdout, net-negative required): "
              f"{'MET' if sig else 'NOT MET' if sig is not None else 'NO VERDICT — thin'}")

    print(f"\n  ORBStrategy is EXCLUDED from both populations — it short-circuits")
    print(f"  to _grade_orb and never reaches either gate (E exempt by")
    print(f"  construction, F counter-only). Counting it would describe a gate")
    print(f"  that does not exist.")
    print(f"\n  Decide per strategy, not per gate. If sweep's blocked population is")
    print(f"  net-POSITIVE while continuation's is net-negative, the answer is to")
    print(f"  EXEMPT SWEEP — not to leave the gate off, and not to ship it whole.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
