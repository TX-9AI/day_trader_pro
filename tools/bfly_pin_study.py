#!/usr/bin/env python3
# day_trader_pro/tools/bfly_pin_study.py — v1.0
# v1.0 (2026-09-01) — dtp r241. BFLY.9/BFLY.10 — AN OVERVIEW, NOT A VERDICT.
#
# Operator, 2026-09-01: "build it to give a good overview of the subject matter,
# I'm curious to know if anything jumps out."
#
# 🔑 EXPLORATORY ON PURPOSE. It bins nothing into pass/fail and fits nothing. It
#   reports WHICH GATE IS BINDING, how the reach fraction moves ACROSS THE
#   SESSION, and what charm is doing at the same hours — because the open
#   question is whether `pin_em_fraction`'s bound is wrong or whether the METRIC
#   is, and a report that pre-committed to either could not tell you.
#
# 🔴 THE CROSS-DAY CONFOUND IS WHY TIME-OF-DAY IS BUCKETED WITHIN EACH DATE.
#   Comparing 08-31's 09:45 fires against 09-01's noon fires attributes a
#   day-to-day difference to the clock; that was my error earlier and this
#   avoids repeating it.
#
# ⚠️ EM SHRINKS WITH sqrt(SESSION REMAINING) — `session_fraction_remaining`'s own
#   docstring, and the bug r125 chased. So `pin_em_fraction` has a denominator
#   that collapses into the close: a pin 1.0 EM away at noon is ~2.6 EM away at
#   15:25 with price never moving. The by-hour panel is the direct look at that.
#
# ⚠️ GEX ON surface_series WAS NULL FOR 1.49M ROWS (r140 — `compute_gex()`
#   returns a GEXSnapshot OBJECT and the writer coerced it to float). r140
#   landed 2026-08-26 and the warehouse holds surface_series from 08-29, so
#   every row here should be post-fix — but "the code is fixed" and "the column
#   is populated" are DIFFERENT CLAIMS, so the run counts non-NULLs and says so.
#
# ⚠️ SELF-CLEANING: the S3 scratch copy is removed on every exit path; only the
#   report is left, in reports/.
"""Butterfly pin study: which gate binds, reach vs clock, charm vs clock."""

from __future__ import annotations

import argparse
import os
import statistics as st
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)

import warehouse_cache as WCACHE                              # noqa: E402

ET = ZoneInfo("US/Eastern")
STRAT = "GEXPinButterfly"
EM_MIN, EM_MAX = 0.30, 1.00          # r208 bounds — carried, never fitted
BUCKETS = ("09:30", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00")


def _dates(a, b):
    d0 = datetime.strptime(a, "%Y-%m-%d").date()
    d1 = datetime.strptime(b, "%Y-%m-%d").date()
    out = []
    while d0 <= d1:
        out.append(d0.isoformat())
        d0 += timedelta(days=1)
    return out


def _hhmm(ts):
    return datetime.fromtimestamp(float(ts), ET).strftime("%H:%M")


def _bucket(ts):
    t = _hhmm(ts)
    for i in range(len(BUCKETS) - 1):
        if BUCKETS[i] <= t < BUCKETS[i + 1]:
            return f"{BUCKETS[i]}-{BUCKETS[i+1]}"
    return "outside"


def _stats(vals):
    if not vals:
        return None
    v = sorted(vals)
    return {"n": len(v), "min": v[0], "med": st.median(v), "max": v[-1],
            "p90": v[int(0.9 * (len(v) - 1))]}


def main(argv):
    ap = argparse.ArgumentParser(description="butterfly pin study")
    ap.add_argument("--from", dest="d0", required=True)
    ap.add_argument("--to", dest="d1", required=True)
    a = ap.parse_args(argv[1:])
    dates = _dates(a.d0, a.d1)
    started = datetime.now(ET)
    out, w = [], None
    cache = WCACHE.WarehouseCache("bflystudy")
    try:
        # ── the plan's own record of every evaluation ───────────────────
        cache.load("plan_check", dates,
                   ["ts_epoch", "strategy", "check_name", "value", "verdict"])
        # ── the surface, per strike, for charm ──────────────────────────
        cache.load("surface_series", dates,
                   ["ts_epoch", "strike", "charm", "vanna", "gex"],
                   datatype="surface_series")

        out = []
        w = out.append
        w(f"BUTTERFLY PIN STUDY — {dates[0]} .. {dates[-1]} ET")
        w("=" * 62)
        w(f"source: s3  ·  {cache.objects:,} objects  ·  {cache.rows:,} rows"
          f"  ·  {cache.bytes_seen / 1e6:.0f} MB")
        w("")

        # ══ 1. WHICH GATE IS BINDING ════════════════════════════════════
        # 🔑 The first question is not "is 1.00 right" but "does this gate
        # decide anything". A condition that never refuses is not a gate.
        w("1. WHICH CONDITION REFUSES  (per evaluation, all symbols)")
        w("-" * 62)
        rows = cache.query(
            'SELECT check_name, COUNT(*) n,'
            '       SUM(CASE WHEN value IS NULL THEN 1 ELSE 0 END) unmeasured'
            '  FROM "plan_check" WHERE strategy = ?'
            ' GROUP BY check_name ORDER BY n DESC', (STRAT,))
        if not rows:
            w("  no GEXPinButterfly rows in this window")
        else:
            w(f"  {'check':<20} {'evals':>8} {'unmeasured':>11}")
            for r in rows:
                w(f"  {r['check_name'][:20]:<20} {r['n']:>8,} "
                  f"{r['unmeasured']:>11,}")
        w("")

        # ══ 2. REACH ACROSS THE SESSION, WITHIN EACH DAY ════════════════
        w("2. pin_em_fraction BY HOUR, WITHIN EACH DAY")
        w("   (the r208 band is 0.30-1.00; EM shrinks with sqrt(time left),")
        w("    so a CONSTANT pin distance drifts UP this table by itself)")
        w("-" * 62)
        reach = cache.query(
            'SELECT ts_epoch, symbol, value FROM "plan_check"'
            ' WHERE strategy = ? AND check_name = ? AND value IS NOT NULL',
            (STRAT, "pin_em_fraction"))
        by_day = {}
        for r in reach:
            d = datetime.fromtimestamp(float(r["ts_epoch"]), ET).date().isoformat()
            by_day.setdefault(d, {}).setdefault(_bucket(r["ts_epoch"]), []) \
                  .append(float(r["value"]))
        if not by_day:
            w("  (no reach evaluations recorded in this window)")
        for d in sorted(by_day):
            w(f"  {d}")
            w(f"    {'hour':<14} {'n':>6} {'min':>7} {'med':>7} {'p90':>7} "
              f"{'max':>8} {'in band':>8}")
            for b in sorted(by_day[d]):
                v = by_day[d][b]
                s = _stats(v)
                inb = sum(1 for x in v if EM_MIN <= x <= EM_MAX) / len(v)
                w(f"    {b:<14} {s['n']:>6} {s['min']:>7.2f} {s['med']:>7.2f} "
                  f"{s['p90']:>7.2f} {s['max']:>8.2f} {inb:>7.0%}")
        w("")

        # ══ 3. CHARM ACROSS THE SESSION ═════════════════════════════════
        # 🔴 surface.py: "For 0DTE this is the AFTERNOON, not an enhancement.
        # Charm dominates the final hours — it is the mechanism behind pin."
        # If that holds, |charm| rises into the close. This is the check.
        w("3. |charm| BY HOUR  (surface_series, all strikes)")
        w("   surface.py: charm dominates the final hours and IS the pin")
        w("   mechanism — so this should RISE into the close if that holds")
        w("-" * 62)
        srf = cache.query(
            'SELECT ts_epoch, charm, gex FROM "surface_series"'
            ' WHERE charm IS NOT NULL')
        cby = {}
        gex_n = gex_null = 0
        for r in srf:
            cby.setdefault(_bucket(r["ts_epoch"]), []).append(abs(float(r["charm"])))
            if r["gex"] is None:
                gex_null += 1
            else:
                gex_n += 1
        if not cby:
            w("  (no charm rows — surface_series absent for this window)")
        else:
            w(f"    {'hour':<14} {'n':>8} {'med |charm|':>12} {'p90':>10}")
            for b in sorted(cby):
                s = _stats(cby[b])
                w(f"    {b:<14} {s['n']:>8,} {s['med']:>12.4f} {s['p90']:>10.4f}")
        w("")
        # ⚠️ THE VERIFICATION, NOT AN ASSUMPTION. r140 fixed the GEX read on
        # 2026-08-26; "the code is fixed" and "the column is populated" are
        # different claims and only the second one matters here.
        tot = gex_n + gex_null
        if tot:
            w(f"   surface_series.gex populated: {gex_n:,}/{tot:,} "
              f"({gex_n / tot:.0%})  — r140 fixed this on 2026-08-26")
            if gex_n == 0:
                w("   🔴 STILL NULL AFTER r140 — stop and look before using GEX")
        w("")

        # ══ 4. THE STRUCTURE THAT WAS OFFERED ═══════════════════════════
        # The lottery-vs-fortress question in one table: what debit, what R,
        # and could the 25% floor ever have cleared the spread.
        w("4. THE STRUCTURE ON OFFER  (debit, R, stop-vs-spread)")
        w("   r208 requires stop_vs_spread >= 2.0; a 'lottery ticket' fly")
        w("   is exactly the one that CANNOT clear it")
        w("-" * 62)
        for name in ("debit", "r", "stop_vs_spread", "wing_width",
                     "debit_pct_width"):
            v = [float(x["value"]) for x in cache.query(
                'SELECT value FROM "plan_check" WHERE strategy = ?'
                ' AND check_name = ? AND value IS NOT NULL', (STRAT, name))]
            s = _stats(v)
            if s:
                w(f"    {name:<16} n={s['n']:>6,}  min {s['min']:>7.2f}"
                  f"  med {s['med']:>7.2f}  p90 {s['p90']:>7.2f}"
                  f"  max {s['max']:>8.2f}")
            else:
                w(f"    {name:<16} not recorded in this window")
        w("")
        w("⚠️ NOTHING HERE IS FITTED. EM_MAX 1.00 and STOP_VS_SPREAD_MIN 2.0")
        w("   are carried constants. This shows the distributions they sit in.")

        text = "\n".join(out) + "\n"
        path = WCACHE.report_path(f"bfly_pin_study_{dates[0]}_{dates[-1]}.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(text)
        print(f"wrote {path}   "
              f"({(datetime.now(ET) - started).total_seconds():.0f}s)")
        return 0
    finally:
        cache.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
