#!/usr/bin/env python3
# day_trader_pro/warehouse_coverage.py — v1.0
# v1.0 (2026-08-18) — VIX COVERAGE IN THE WAREHOUSE, BEFORE THE SEVER.
#      Once S3 becomes the official store, the control-side copy stops being
#      written and anything absent from the bucket is GONE. VIX is the highest
#      exposure in that transition for one structural reason: every box logs it
#      but `s3_push.push_candles` skips it unless `me == "SPX"` ("SPX owns
#      VIX"), so VIX has ONE writer. Any day SPX does not run, or its candles
#      stage fails, VIX simply does not land — and nothing reports it, because
#      the other 28 boxes skipping VIX is the normal, correct behaviour.
#      This is LIST-only and read-only: no GetObject, no writes, no box access.
#      It answers three questions per date, from the bucket alone:
#        1. did VIX 1m land, and how many objects
#        2. did VIX 1d land
#        3. did SPX push its OWN candles that day
#      (3) is what separates the two diagnoses that must never be confused:
#        · SPX pushed its own candles but no VIX  -> A PUSH DEFECT. Data that
#          existed on the box was not warehoused. Actionable now.
#        · SPX pushed nothing at all              -> SPX WAS DOWN. Explained,
#          still a gap, and the argument for a fallback VIX writer.
#      Deliberately NOT a full multi-stream coverage report. EXPECTED_STREAMS
#      is a table so adding one is a one-line edit, but this ships answering
#      the question that was asked.
"""
Usage (control box, from ~/day_trader_pro):

  python3 warehouse_coverage.py                     # last 10 sessions
  python3 warehouse_coverage.py --since 2026-08-13  # explicit start
  python3 warehouse_coverage.py --date 2026-08-18   # one day
  python3 warehouse_coverage.py --json out.json     # machine-readable

Exit status: 0 = every checked date has VIX 1m. 1 = at least one date is
missing it. Never raises on an empty bucket — a missing stream is the finding,
not an error, and a tool must not throw when the thing it measures is fixed.
"""

import argparse
import json
import os
import sys
from datetime import date as _date, timedelta

import boto3

import config  # noqa: F401  (kept for path/env parity with the other tools)

BUCKET = os.environ.get("OT_S3_BUCKET", "vertigo-warehouse-tx9ai")
REGION = os.environ.get("OT_S3_REGION", "us-east-2")
PREFIX = os.environ.get("OT_S3_PREFIX", "raw")

# The one stream this tool exists for. A dict, not a hardcode, so extending the
# check to another single-writer stream is one line — but see the header: this
# ships scoped to the question asked.
EXPECTED_STREAMS = {
    "VIX_1m": ("candles", "VIX", "1m"),
    "VIX_1d": ("candles", "VIX", "1d"),
}
OWNER = "SPX"          # the only box permitted to push VIX (s3_push.push_candles)


def _log(tag, msg):
    print(f"[{tag:<9}] {msg}")


def _client():
    return boto3.client("s3", region_name=REGION)


def _count(s3, prefix):
    """Objects under a prefix. LIST only — never fetches a body."""
    n = 0
    pg = s3.get_paginator("list_objects_v2")
    for page in pg.paginate(Bucket=BUCKET, Prefix=prefix):
        n += len(page.get("Contents", []) or [])
    return n


def _dt_days(s3, datatype):
    """Every dt= partition present under raw/<datatype>/."""
    days = set()
    pg = s3.get_paginator("list_objects_v2")
    for page in pg.paginate(Bucket=BUCKET, Prefix=f"{PREFIX}/{datatype}/",
                            Delimiter="/"):
        for cp in page.get("CommonPrefixes", []) or []:
            part = cp["Prefix"].rstrip("/").split("/")[-1]
            if part.startswith("dt="):
                days.add(part[3:])
    return sorted(days)


def check_date(s3, day):
    """One date's verdict. Pure lookup — no side effects."""
    row = {"date": day}
    for name, (datatype, sym, interval) in EXPECTED_STREAMS.items():
        row[name] = _count(
            s3, f"{PREFIX}/{datatype}/dt={day}/sym={sym}/interval={interval}/")
    row["owner_candles"] = _count(
        s3, f"{PREFIX}/{datatype}/dt={day}/sym={OWNER}/")
    if row["VIX_1m"] > 0:
        row["verdict"] = "OK"
    elif row["owner_candles"] > 0:
        row["verdict"] = "PUSH_DEFECT"      # SPX pushed candles, VIX missing
    else:
        row["verdict"] = "OWNER_DOWN"       # SPX pushed nothing that day
    return row


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="VIX coverage in the S3 warehouse (read-only, LIST only)")
    ap.add_argument("--date", default=None, help="check a single YYYY-MM-DD")
    ap.add_argument("--since", default=None, help="check every dt= from this date")
    ap.add_argument("--last", type=int, default=10,
                    help="if neither --date nor --since: the N most recent dt= "
                         "partitions present in the bucket (default 10)")
    ap.add_argument("--json", default="", help="also write the rows to this path")
    args = ap.parse_args(argv)

    try:
        s3 = _client()
        present = _dt_days(s3, "candles")
    except Exception as exc:                                   # noqa: BLE001
        _log("COVERAGE", f"cannot list the bucket: {exc}")
        return 2

    if not present:
        _log("COVERAGE", f"no candle partitions under s3://{BUCKET}/{PREFIX}/candles/")
        return 1

    if args.date:
        days = [args.date]
    elif args.since:
        days = [d for d in present if d >= args.since]
    else:
        days = present[-args.last:]

    rows = [check_date(s3, d) for d in days]
    missing = [r for r in rows if r["verdict"] != "OK"]

    _log("COVERAGE", f"s3://{BUCKET}/{PREFIX}/candles/ — {len(rows)} date(s) checked")
    for r in rows:
        mark = {"OK": "✅", "PUSH_DEFECT": "🔴", "OWNER_DOWN": "⚠️"}[r["verdict"]]
        _log("COVERAGE",
             f"  {mark} {r['date']}  VIX 1m={r['VIX_1m']:<4} 1d={r['VIX_1d']:<3} "
             f"{OWNER} candles={r['owner_candles']:<4} {r['verdict']}")

    if missing:
        defects = [r["date"] for r in missing if r["verdict"] == "PUSH_DEFECT"]
        downs = [r["date"] for r in missing if r["verdict"] == "OWNER_DOWN"]
        if defects:
            _log("COVERAGE", f"🔴 PUSH DEFECT on {len(defects)}: {', '.join(defects)} "
                             f"— {OWNER} warehoused its own candles but no VIX. "
                             f"The data existed on the box and did not land.")
        if downs:
            _log("COVERAGE", f"⚠️ {OWNER} pushed nothing on {len(downs)}: "
                             f"{', '.join(downs)} — VIX has a single writer, so "
                             f"those days have no VIX anywhere once control is severed.")
    else:
        _log("COVERAGE", "✅ every checked date has VIX 1m in the warehouse")

    if args.json:
        try:
            with open(args.json, "w", encoding="utf-8") as fh:
                json.dump({"bucket": BUCKET, "owner": OWNER, "rows": rows}, fh,
                          indent=2)
            _log("COVERAGE", f"wrote {args.json}")
        except Exception as exc:                               # noqa: BLE001
            _log("COVERAGE", f"could not write {args.json}: {exc}")

    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
