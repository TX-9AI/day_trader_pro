#!/usr/bin/env python3
# day_trader_pro/tools/bfly_reach_probe.py — v1.1
# v1.1 (2026-09-01) — r242. CLI only; the menu item is removed.
# v1.0 (2026-09-01) — dtp r238. THE SMALL ONE, TO TEST THE THEORY.
#
# Operator, 2026-09-01: "write a small report based on some of the data sets
# that could finish quickly just to test the theory, and make sure it has a
# cleanup function for the stuff we pulled over."
#
# 🔑 IT IS ALSO THE FIRST SLICE OF BFLY.9. The butterfly's reach gate
# (`pin_em_fraction` — the pin's distance as a fraction of the expected move)
# became FOUNDATIONAL at r208 on the operator's ruling, at a bound of 1.00 that
# NOBODY HAS EVER FITTED. `plan_check` records that variable's VALUE on every
# butterfly evaluation, fired or declined, so the distribution is already on
# disk. This reads ONE day so it returns in seconds; the same code over a range
# is the full survey.
#
# ⚠️ ONE DAY OF plan_check IS A SMALL READ ON PURPOSE. `fit_readiness` was
# OOM-killed on a 9-day range (RPT.10). This proves the cache path on a load
# that cannot fail before anything depends on it.
#
# ⚠️ THE CACHE IS DELETED WHATEVER HAPPENS — success, exception, Ctrl-C or
# SIGTERM — and the report is written to reports/ and left there. See
# warehouse_cache.py: `tools/report_parity.py` calls mkdtemp twice and removes
# neither, which is exactly the leak this avoids.
# ⚠️ CLI ONLY — NO MENU ITEM (r242).
#   Run:  python3 tools/bfly_reach_probe.py --date 2026-09-01
"""Butterfly reach distribution for one ET day. Fast, and self-cleaning."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)

import warehouse_cache as WCACHE                          # noqa: E402

ET = ZoneInfo("US/Eastern")
# The r208 bound. Recorded here as what it IS — a carried constant, not a fit.
EM_MAX = 1.00
EM_MIN = 0.30


def main(argv):
    ap = argparse.ArgumentParser(description="butterfly reach, one day")
    ap.add_argument("--date", default=datetime.now(ET).strftime("%Y-%m-%d"))
    ap.add_argument("--keep-cache", action="store_true",
                    help="leave the scratch copy in place (debugging only)")
    a = ap.parse_args(argv[1:])

    started = datetime.now(ET)
    cache = WCACHE.WarehouseCache("bfly")
    try:
        n = cache.load("plan_check", [a.date],
                       ["ts_epoch", "strategy", "check_name", "value", "verdict"])
        rows = cache.query(
            'SELECT symbol, value, verdict FROM "plan_check" '
            ' WHERE strategy = ? AND check_name = ? AND value IS NOT NULL',
            ("GEXPinButterfly", "pin_em_fraction"))
        unreadable = cache.query("SELECT count(*) c FROM _unreadable") \
            if cache.query("SELECT name FROM sqlite_master WHERE name='_unreadable'") else []

        # ── the histogram ────────────────────────────────────────────────
        edges = [(0.0, 0.30), (0.30, 0.60), (0.60, 0.80), (0.80, 1.00),
                 (1.00, 1.30), (1.30, 2.00), (2.00, 9e9)]
        buckets = {e: 0 for e in edges}
        per_sym = {}
        inside = outside = 0
        for r in rows:
            v = float(r["value"])
            for e in edges:
                if e[0] <= v < e[1]:
                    buckets[e] += 1
                    break
            d = per_sym.setdefault(r["symbol"], {"n": 0, "in": 0, "min": v, "max": v})
            d["n"] += 1
            d["min"] = min(d["min"], v)
            d["max"] = max(d["max"], v)
            if EM_MIN <= v <= EM_MAX:
                inside += 1
                d["in"] += 1
            else:
                outside += 1

        out = []
        w = out.append
        w(f"BUTTERFLY REACH — {a.date} ET")
        w("=" * 46)
        # ⚠️ THE SOURCE LINE ALWAYS PRINTS. An unreachable bucket and a session
        # with no evaluations must never render the same (warehouse_reader's
        # WhMeta rule, applied here).
        w(f"source: s3 plan_check  ·  {cache.objects:,} objects  "
          f"·  {cache.rows:,} rows  ·  {cache.bytes_seen / 1e6:.1f} MB")
        if unreadable and unreadable[0]["c"]:
            w(f"⚠️  {unreadable[0]['c']} object(s) UNREADABLE — the sample has holes")
        w("")
        if not rows:
            w("No GEXPinButterfly reach evaluations on this date.")
            w("(the strategy is windowed 12:00-15:30; a day with no pin")
            w(" published records nothing here — that is not an error)")
        else:
            w(f"evaluations: {len(rows):,}   inside the {EM_MIN:.2f}-{EM_MAX:.2f} "
              f"band: {inside:,} ({inside / len(rows):.0%})")
            w("")
            w("  pin distance / expected move")
            top = max(buckets.values()) or 1
            for lo, hi in edges:
                c = buckets[(lo, hi)]
                lab = f"{lo:.2f}-{hi:.2f}" if hi < 9e8 else f"{lo:.2f}+   "
                mark = " <- r208 bound" if hi == EM_MAX else ""
                w(f"  {lab:<11} {c:>6}  {'#' * int(30 * c / top)}{mark}")
            w("")
            w(f"  {'sym':<6} {'evals':>6} {'in band':>8} {'min':>6} {'max':>6}")
            for sym in sorted(per_sym):
                d = per_sym[sym]
                w(f"  {sym:<6} {d['n']:>6} {d['in']:>8} "
                  f"{d['min']:>6.2f} {d['max']:>6.2f}")
            w("")
            w("⚠️ RECORDED, NOT FITTED. EM_MAX 1.00 is a carried constant that")
            w("   has never been tested against outcomes; this shows the")
            w("   DISTRIBUTION the bound sits in, not whether it is right.")
            w("   Joining these to fills is BFLY.9 proper.")

        text = "\n".join(out) + "\n"
        path = WCACHE.report_path(f"bfly_reach_{a.date}.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(text)
        took = (datetime.now(ET) - started).total_seconds()
        print(f"wrote {path}   ({took:.1f}s)")
        return 0
    finally:
        # ⚠️ ALWAYS, and the report is untouched because it lives in reports/.
        if a.keep_cache:
            print(f"cache KEPT at {cache.root} (--keep-cache)")
            if cache.root in WCACHE._ACTIVE:
                WCACHE._ACTIVE.remove(cache.root)
        else:
            cache.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
