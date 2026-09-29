#!/usr/bin/env python3
"""tests/check_stream_lineage.py — v1.0
A STREAM ONE ENGINE DOES NOT PRODUCE IS "NOT USED" ON ITS BOXES, NOT A GAP.

v1.0  2026-09-29 — dtp r453 / OPS.60. The streams board graded `eod` and
      `liquidity_ledger` EVERY, so AAL and SOFI (the OTV4TEST engine) read MISS
      on both every night, 0 objects ever. Neither is produced by that engine:
      liquidity_ledger's writer was retired at OTV4TEST r122 (derived_level_ledger
      replaced it), and `eod` is a per-box file the close no longer needs — the
      conductor's P&L headline reads every box's trades from S3 (pnl_s3), and did
      report AAL and SOFI on 2026-09-28. Operator: "Instead of a failure, have it
      report as not used." Keyed on the LINEAGE in strategy_registry, not on a
      box list, because more test boxes may follow and a hardcoded list rots.

  L1a/b AAL/SOFI absent from eod / liquidity_ledger -> OK, both named NOT USED
  L2  CONTROL: a MAIN box absent from eod is still a GAP naming it (unchanged)
  L3  derived_level_event (the TEST level event log) is declared, not UNDECLARED
  L4  a box newly declared TEST in the registry is NOT USED with no policy edit

Drives the real check_streams against the FakeS3 from test_stream_coverage.
Run:  python3 tests/check_stream_lineage.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
FAILED = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not ok else ""))
    if not ok:
        FAILED.append(name.split()[0])


def main():
    import warehouse_coverage as wc
    import strategy_registry as sr
    from test_stream_coverage import FakeS3

    DAY = "2026-09-28"                       # a Monday, after COLLECTION_START
    want = ["SPX", "QQQ", "AAL", "SOFI"]

    def full(*syms):
        return {DAY: {s: 3 for s in syms}}
    bucket = {
        "signal_journal":       full("SPX", "QQQ", "AAL", "SOFI"),   # all four live
        "derived_level_ledger": full("SPX", "QQQ", "AAL", "SOFI"),
        "derived_level_event":  full("AAL", "SOFI"),
        "eod":                  full("SPX", "QQQ"),
        "liquidity_ledger":     full("SPX", "QQQ"),
    }
    by = {r["stream"]: r for r in wc.check_streams(FakeS3(bucket), DAY, want)["rows"]}

    for tag, s in (("L1a", "eod"), ("L1b", "liquidity_ledger")):
        r = by.get(s, {})
        check(f"{tag} {s}: TEST boxes absent -> OK, named NOT USED",
              r.get("verdict") == "OK" and not r.get("missing")
              and sorted(r.get("not_used", [])) == ["AAL", "SOFI"],
              f"verdict={r.get('verdict')} missing={r.get('missing')} not_used={r.get('not_used')}")

    b2 = dict(bucket, eod=full("SPX"))       # QQQ (MAIN) did not push eod
    r2 = {r["stream"]: r for r in wc.check_streams(FakeS3(b2), DAY, want)["rows"]}.get("eod", {})
    check("L2 CONTROL: a MAIN box absent from eod is still a GAP naming it",
          r2.get("verdict") == "GAP" and "QQQ" in (r2.get("missing") or []),
          f"{r2.get('verdict')} {r2.get('missing')}")

    r3 = by.get("derived_level_event", {})
    check("L3 derived_level_event is declared, not UNDECLARED",
          r3.get("verdict") not in (None, "UNDECLARED"), f"{r3.get('verdict')}")

    old = sr.TEST_BOXES
    try:
        sr.TEST_BOXES = tuple(old) + ("XYZ",)
        b4 = {k: ({DAY: {**v[DAY], "XYZ": 3}} if k in ("signal_journal", "derived_level_ledger") else v)
              for k, v in bucket.items()}
        r4 = {r["stream"]: r for r in wc.check_streams(FakeS3(b4), DAY, want + ["XYZ"])["rows"]}.get("eod", {})
        check("L4 a box newly declared TEST is NOT USED with no policy edit",
              r4.get("verdict") == "OK" and "XYZ" in (r4.get("not_used") or []),
              f"{r4.get('verdict')} missing={r4.get('missing')} not_used={r4.get('not_used')}")
    finally:
        sr.TEST_BOXES = old

    print("GREEN" if not FAILED else f"RED — {len(FAILED)} failed: {', '.join(FAILED)}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
