#!/usr/bin/env python3
# day_trader_pro/tools/backfill_survey.py — v1.1
# v1.1 (2026-08-16) — `--streams`: the same question for the OTHER streams.
#      The trades survey found the warehouse is the sole copy of 33 closed
#      trades on 2026-07-15. Trades are the one stream that is at least PARTLY
#      reconstructible from bundles — chain snapshots are explicitly NOT
#      reconstructible after the session, so if the same exposure exists there
#      it is worse, not better. This counts local artifacts against warehouse
#      objects per stream per date and says which side is ahead.
# v1.0 (2026-08-16) — READ-ONLY. Counts what a control-side backfill would add
#      to the warehouse, per ET trading day, before anyone grants write access.
"""
Backfill survey — what does control hold that the warehouse does not?

WHY A SURVEY FIRST
    A backfill needs a temporary PutObject grant on the control role, which is
    a permission change to a system whose whole safety story is "control cannot
    write or delete". That grant should be justified by a number, not by a
    guess. If the answer is twelve dates and four hundred trades it is clearly
    worth it; if it is three dates and nine trades it is not.

    This reads. It never writes, anywhere — not to S3, not to reports/, not to
    trades/. Run it as often as you like.

THE TWO LOCAL SOURCES, IN PRIORITY ORDER
    1. `trades/<date>/*_trades_<date>.db` — per-box SQLite, one step from the
       box, which is what raw/ is meant to hold. Present from 2026-07-23 only.
    2. `reports/fleet_trades_<date>.json` — control's own bundle.
       ⚠️ Bundles dated before consolidate_trades v1.2 (2026-07-28) are
       CUMULATIVE: each holds that box's ENTIRE history at harvest time. That
       is the property that forced report 41 to de-duplicate — and it is
       exactly why early history is recoverable at all.

    ⚠️ NO SINGLE CUMULATIVE BUNDLE IS COMPLETE. Harvest only copied DBs from
    boxes that RAN that day, so the box set differs day to day (which is why
    the pre-07-28 counts are not monotonic: 07-13 shows 225, 07-16 shows 111).
    The recoverable set is the UNION across every bundle, keyed by trade_id.

PARTITIONING
    Every trade is counted under ITS OWN `entry_time` converted to the ET
    trading day — never under the filename's date. A cumulative bundle dated
    07-23 contains trades from early July, and filing those under 07-23 would
    be worse than not backfilling them.

USAGE
  python3 tools/backfill_survey.py                 # full survey
  python3 tools/backfill_survey.py --no-s3         # local inventory only
  python3 tools/backfill_survey.py --explain 2026-07-21
"""

import argparse
import glob
import json
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import config  # noqa: E402

TRADES_DIR = os.path.join(ROOT, "trades")
BUCKET = os.environ.get("OT_S3_BUCKET", "vertigo-warehouse-tx9ai")
REGION = os.environ.get("OT_S3_REGION", "us-east-2")
_ET = ZoneInfo("US/Eastern")
_UTC = ZoneInfo("UTC")
_DATE_DIR = __import__("re").compile(r"^\d{4}-\d{2}-\d{2}$")


def et_day(ts):
    """The ET trading day for an ISO timestamp. Matches the pusher's rule."""
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_UTC)
    return dt.astimezone(_ET).date().isoformat()


def from_dbs():
    """{et_day: {trade_id}} from the per-box SQLite snapshots."""
    out = defaultdict(set)
    files = sorted(glob.glob(os.path.join(TRADES_DIR, "*", "*_trades_*.db")))
    for path in files:
        try:
            con = sqlite3.connect("file:%s?mode=ro" % path, uri=True, timeout=5)
            for tid, ts in con.execute("SELECT trade_id, entry_time FROM trades"):
                d = et_day(ts)
                if d and tid is not None:
                    out[d].add(str(tid))
            con.close()
        except Exception as exc:                          # noqa: BLE001
            print(f"  ! unreadable {os.path.basename(path)}: {exc}")
    return out, len(files)


def from_bundles():
    """{et_day: {trade_id}} from every bundle, unioned.

    Cumulative bundles overlap heavily by design; the union is the point.
    """
    out = defaultdict(set)
    files = sorted(glob.glob(os.path.join(config.REPORTS_DIR,
                                          "fleet_trades_*.json")))
    for path in files:
        try:
            with open(path) as fh:
                b = json.load(fh)
        except Exception:
            continue
        for t in b.get("trades", []) or []:
            d = et_day(t.get("entry_time"))
            tid = t.get("trade_id")
            if d and tid is not None:
                out[d].add(str(tid))
    return out, len(files)


def from_s3():
    """{et_day: {trade_id}} already in the warehouse."""
    import boto3
    s3 = boto3.client("s3", region_name=REGION)
    out = defaultdict(set)
    pg = s3.get_paginator("list_objects_v2")
    keys = []
    for page in pg.paginate(Bucket=BUCKET, Prefix="raw/trades/"):
        for o in page.get("Contents", []) or []:
            keys.append(o["Key"])
    sys.stderr.write(f"  reading {len(keys)} warehouse trade object(s)…\n")
    for i, k in enumerate(keys):
        if i and i % 200 == 0:
            sys.stderr.write(f"\r  {i}/{len(keys)}")
            sys.stderr.flush()
        try:
            env = json.loads(s3.get_object(Bucket=BUCKET, Key=k)["Body"].read())
            rec = env.get("record") or {}
            d = et_day(rec.get("entry_time"))
            tid = rec.get("trade_id")
            if d and tid is not None:
                out[d].add(str(tid))
        except Exception:
            continue
    sys.stderr.write("\r" + " " * 40 + "\r")
    return out


# Local artifact trees, by warehouse prefix. Control only ever held what
# harvest pulled back, so absence here is the interesting direction.
LOCAL_TREES = {
    "chain_snapshots": ("chain_snapshots", "*.jsonl.gz"),
    "signal_journal":  ("signal_journal", "*.jsonl"),
    "shadow":          ("shadow", "*.jsonl"),
    "ohlc":            ("ohlc", "*.csv"),
}


def stream_census():
    """Per stream per date: local files vs warehouse objects. Read-only."""
    import boto3
    s3 = boto3.client("s3", region_name=REGION)
    pg = s3.get_paginator("list_objects_v2")

    print(f"\n  {'stream':<18}{'dates local':>12}{'dates S3':>10}"
          f"{'S3-only dates':>15}")
    for prefix, (subdir, pat) in sorted(LOCAL_TREES.items()):
        local_dates = set()
        base = os.path.join(ROOT, subdir)
        if os.path.isdir(base):
            for d in os.listdir(base):
                if _DATE_DIR.match(d) and glob.glob(os.path.join(base, d, pat)):
                    local_dates.add(d)
        s3_dates = set()
        for page in pg.paginate(Bucket=BUCKET, Prefix=f"raw/{prefix}/",
                                Delimiter="/"):
            for cp in page.get("CommonPrefixes", []) or []:
                part = cp["Prefix"].rstrip("/").split("/")[-1]
                if part.startswith("dt="):
                    s3_dates.add(part[3:])
        only_s3 = sorted(s3_dates - local_dates)
        print(f"  {prefix:<18}{len(local_dates):>12}{len(s3_dates):>10}"
              f"{len(only_s3):>15}"
              + ("   " + ", ".join(only_s3[:4]) + ("…" if len(only_s3) > 4 else "")
                 if only_s3 else ""))
    print("\n  ⚠️ For chain_snapshots an S3-only date is UNRECOVERABLE elsewhere —")
    print("     they are not reconstructible after the session. For the others")
    print("     the box may still hold the file until it is trimmed.\n")


def main(argv):
    p = argparse.ArgumentParser(description="what would a backfill recover?")
    p.add_argument("--no-s3", action="store_true")
    p.add_argument("--explain", metavar="DATE")
    p.add_argument("--streams", action="store_true",
                   help="census the non-trade streams instead")
    a = p.parse_args(argv)

    if a.streams:
        stream_census()
        return 0

    dbs, n_db = from_dbs()
    bun, n_bun = from_bundles()
    print(f"\n  local sources: {n_db} per-box DB(s), {n_bun} bundle(s)")

    local = defaultdict(set)
    for src in (dbs, bun):
        for d, ids in src.items():
            local[d] |= ids

    ware = {} if a.no_s3 else from_s3()

    days = sorted(set(local) | set(ware))
    print(f"\n  {'date':<12}{'DBs':>6}{'bundles':>9}{'local':>7}"
          f"{'S3':>7}{'to add':>8}{'S3-only':>9}")
    add_total = only_s3_total = 0
    for d in days:
        L = local.get(d, set())
        W = ware.get(d, set())
        add = len(L - W)
        onlyw = len(W - L)
        add_total += add
        only_s3_total += onlyw
        flag = ""
        if onlyw:
            flag = "  <- S3 has trades local does NOT"
        print(f"  {d:<12}{len(dbs.get(d, set())):>6}{len(bun.get(d, set())):>9}"
              f"{len(L):>7}{len(W):>7}{add:>8}{onlyw:>9}{flag}")

    print(f"\n  a backfill would ADD {add_total} trade(s) across "
          f"{sum(1 for d in days if local.get(d, set()) - ware.get(d, set()))} date(s)")
    if only_s3_total:
        print(f"  ⚠️ {only_s3_total} trade(s) exist ONLY in S3 — the warehouse is")
        print("     already the sole copy of those. That is the argument for")
        print("     exporting control's data, restated from the other side.")
    print("\n  ⚠️ A backfill needs a TEMPORARY PutObject grant on the control")
    print("     role, used once and revoked. Nothing here has written anything.\n")

    if a.explain:
        d = a.explain
        L, W = local.get(d, set()), ware.get(d, set())
        print(f"  {d}: local {len(L)} · s3 {len(W)}")
        print(f"    only local ({len(L - W)}): {sorted(L - W)[:20]}")
        print(f"    only s3    ({len(W - L)}): {sorted(W - L)[:20]}")
        print(f"    from DBs {len(dbs.get(d, set()))}, "
              f"from bundles {len(bun.get(d, set()))}\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        print("\ninterrupted — read-only, nothing was written")
        sys.exit(130)
    except Exception as exc:                              # noqa: BLE001
        print(f"backfill_survey: {type(exc).__name__}: {str(exc).splitlines()[0][:160]}")
        sys.exit(1)
