#!/usr/bin/env python3
# day_trader_pro/tools/bfly_pin_study.py — v1.2
# v1.2 (2026-09-01) — r243. 🔴 PANEL 2's med/p90 WERE POOLED ACROSS THE RANGE.
#   The panel is titled "within each day" and its n/min/max/in-band came from
#   GROUP BY d,b — but `_pct` filtered by BUCKET ONLY, so both days printed
#   IDENTICAL medians to the decimal (12:00 1.37, 13:00 1.72, 14:00 2.17,
#   15:00 2.51 on 08-31 AND 09-01). Exactly the cross-day confound the panel
#   exists to remove. `_pct` now takes the day. Proven by the run, not by
#   reading: two different days cannot share four medians to two decimals.
# v1.1 (2026-09-01) — r242. 🔴 OOM-KILLED ON THE FIRST REAL RUN, AFTER BOTH
#   S3 LOADS SUCCEEDED. The cache streamed 907,167 plan_check and 7,794,684
#   surface_series rows to disk exactly as designed — and then every panel
#   called `cache.query(...)`, which is fetchall, and materialised them all
#   as Python objects. The OOM moved from the FETCH to the ANALYSIS and I did
#   not see it because I was looking at the half I had fixed. Six minutes of
#   S3 reads thrown away at the last step.
#   🔑 EVERY PANEL NOW AGGREGATES IN SQL. sqlite groups millions of rows into
#   seven buckets; Python will not hold millions of dicts. Quantiles come
#   from ORDER BY ... LIMIT 1 OFFSET k, which returns ONE row. Measured after
#   the change: 278 MB peak on 2,000,000 rows, most of it the test fixture.
#   ⚠️ The ET hour bucket takes its offset from the tz database, never a
#   hardcoded '-4 hours' — that is EDT and has been found wrong twice here.
#   ⚠️ CLI only; the menu item is removed (r242).
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
# ⚠️ CLI ONLY — NO MENU ITEM (r242). A study is run once to answer a
#   question and then argued about; it belongs where it can take real
#   arguments and be re-run over a different range without a prompt.
#   Run:  python3 tools/bfly_pin_study.py --from 2026-08-29 --to 2026-09-01
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


def _day(off):
    """The ET date of a ts_epoch, as SQL."""
    return f"date(datetime(ts_epoch, 'unixepoch', '{off}'))"


def _grp(off):
    """The ET hour bucket, as SQL. ⚠️ The offset comes from the tz database
    (cache.et_offset_hours), never a hardcoded '-4 hours' — that is EDT and has
    already been found wrong twice in this codebase (r125, dtp r236)."""
    return f"strftime('%H:00', datetime(ts_epoch, 'unixepoch', '{off}'))"


def _pct(cache, table, grp, bucket, off, q, strat, col="value", day=None,
         check=None):
    """One quantile inside one bucket, by OFFSET — exact, and it returns ONE
    row. sqlite has no median; pulling the column into Python to sort it is
    what OOM'd the first cut on 7.8M rows."""
    # 🔴 THE `day` ARGUMENT WAS MISSING AND THE FIRST RUN PROVED IT. Panel 2 is
    # titled "within each day", its count/min/max/in-band came from GROUP BY
    # d,b — and med/p90 came from here, filtered by BUCKET ONLY. So both days
    # printed IDENTICAL medians to the decimal (12:00 med 1.37 on 08-31 and on
    # 09-01, 13:00 1.72, 14:00 2.17, 15:00 2.51). Pooled across the range,
    # which is exactly the cross-day confound the panel exists to remove.
    where = f"{grp} = ?"
    args = [bucket]
    if day is not None:
        where += f" AND {_day(off)} = ?"
        args.append(day)
    if strat:
        where += " AND strategy = ? AND check_name = ?"
        args += [strat, check or "pin_em_fraction"]
    n = cache.query(f'SELECT COUNT(*) n FROM "{table}" WHERE {where}'
                    f' AND {col} IS NOT NULL', tuple(args))[0]["n"]
    if not n:
        return None
    k = min(n - 1, int(q * (n - 1)))
    r = cache.query(f'SELECT {col} v FROM "{table}" WHERE {where}'
                    f' AND {col} IS NOT NULL ORDER BY {col} LIMIT 1 OFFSET {k}',
                    tuple(args))
    return float(r[0]["v"]) if r else None


def _pct_all(cache, name, q, strat):
    n = cache.query('SELECT COUNT(*) n FROM "plan_check" WHERE strategy = ?'
                    ' AND check_name = ? AND value IS NOT NULL',
                    (strat, name))[0]["n"]
    if not n:
        return float("nan")
    k = min(n - 1, int(q * (n - 1)))
    r = cache.query('SELECT value v FROM "plan_check" WHERE strategy = ?'
                    ' AND check_name = ? AND value IS NOT NULL'
                    f' ORDER BY value LIMIT 1 OFFSET {k}', (strat, name))
    return float(r[0]["v"]) if r else float("nan")


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

        off = cache.et_offset_hours()
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
        # 🔴 GROUPED IN SQL. The first cut pulled every row into Python and was
        # OOM-KILLED on 7.8M surface rows AFTER both S3 loads had succeeded —
        # the cache streamed to disk exactly as designed and the ANALYSIS threw
        # it away. sqlite groups millions of rows into seven buckets; Python
        # will not hold millions of dicts.
        cache.index("plan_check", "strategy", "check_name")
        cache.index("surface_series", "ts_epoch")
        grp = _grp(off)
        rows2 = cache.query(
            f'SELECT {_day(off)} d, {grp} b, COUNT(*) n,'
            f'       MIN(value) lo, MAX(value) hi,'
            f'       SUM(CASE WHEN value BETWEEN ? AND ? THEN 1 ELSE 0 END) inb'
            f'  FROM "plan_check" WHERE strategy = ? AND check_name = ?'
            f'   AND value IS NOT NULL GROUP BY d, b ORDER BY d, b',
            (EM_MIN, EM_MAX, STRAT, "pin_em_fraction"))
        if not rows2:
            w("  (no reach evaluations recorded in this window)")
        cur_day = None
        for r in rows2:
            if r["d"] != cur_day:
                cur_day = r["d"]
                w(f"  {cur_day}")
                w(f"    {'hour':<8} {'n':>7} {'min':>7} {'med':>7} {'p90':>7} "
                  f"{'max':>8} {'in band':>8}")
            med = _pct(cache, "plan_check", grp, r["b"], off, 0.50, STRAT,
                       day=r["d"])
            p90 = _pct(cache, "plan_check", grp, r["b"], off, 0.90, STRAT,
                       day=r["d"])
            w(f"    {r['b']:<8} {r['n']:>7,} {r['lo']:>7.2f} "
              f"{(med if med is not None else float('nan')):>7.2f} "
              f"{(p90 if p90 is not None else float('nan')):>7.2f} "
              f"{r['hi']:>8.2f} {r['inb'] / r['n']:>7.0%}")
        w("")

        # ══ 3. CHARM ACROSS THE SESSION ═════════════════════════════════
        # 🔴 surface.py: "For 0DTE this is the AFTERNOON, not an enhancement.
        # Charm dominates the final hours — it is the mechanism behind pin."
        # If that holds, |charm| rises into the close. This is the check.
        w("3. |charm| BY HOUR  (surface_series, all strikes)")
        w("   surface.py: charm dominates the final hours and IS the pin")
        w("   mechanism — so this should RISE into the close if that holds")
        w("-" * 62)
        crows = cache.query(
            f'SELECT {grp} b, COUNT(*) n, AVG(ABS(charm)) mean,'
            f'       MAX(ABS(charm)) hi'
            f'  FROM "surface_series" WHERE charm IS NOT NULL'
            f' GROUP BY b ORDER BY b')
        if not crows:
            w("  (no charm rows — surface_series absent for this window)")
        else:
            w(f"    {'hour':<8} {'n':>10} {'mean |charm|':>13} "
              f"{'med':>10} {'max':>10}")
            for r in crows:
                med = _pct(cache, "surface_series", grp, r["b"], off, 0.50,
                           None, col="ABS(charm)")
                w(f"    {r['b']:<8} {r['n']:>10,} {r['mean']:>13.4f} "
                  f"{(med if med is not None else float('nan')):>10.4f} "
                  f"{r['hi']:>10.4f}")
        g = cache.query('SELECT COUNT(*) tot,'
                        ' SUM(CASE WHEN gex IS NULL THEN 1 ELSE 0 END) nulls'
                        '  FROM "surface_series"')[0]
        gex_n, tot = g["tot"] - (g["nulls"] or 0), g["tot"]
        w("")
        # ⚠️ THE VERIFICATION, NOT AN ASSUMPTION. r140 fixed the GEX read on
        # 2026-08-26; "the code is fixed" and "the column is populated" are
        # different claims and only the second one matters here.
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
            a = cache.query(
                'SELECT COUNT(*) n, MIN(value) lo, MAX(value) hi'
                '  FROM "plan_check" WHERE strategy = ? AND check_name = ?'
                '   AND value IS NOT NULL', (STRAT, name))[0]
            if a["n"]:
                med = _pct_all(cache, name, 0.50, STRAT)
                p90 = _pct_all(cache, name, 0.90, STRAT)
                w(f"    {name:<16} n={a['n']:>7,}  min {a['lo']:>7.2f}"
                  f"  med {med:>7.2f}  p90 {p90:>7.2f}  max {a['hi']:>8.2f}")
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
