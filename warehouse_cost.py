#!/usr/bin/env python3
# day_trader_pro/warehouse_cost.py — v1.1
# v1.1 (2026-08-16) — IT PRINTED NOTHING FOR TWO MINUTES. A full LIST of ~130k
#      objects is 130+ paginated API calls, and --versions does a SECOND full
#      pass, so it was working the whole time — but it said so nowhere. That is
#      the SAME silent-long-operation failure as the emergency stop, committed
#      one day after fixing it. Now prints a running count per page to stderr,
#      says up front what it is about to do, and handles Ctrl-C cleanly.
#      --quiet restores the silent behaviour for scripted use.
# v1.0 (2026-08-16) — WH.9a. Measures what the warehouse ACTUALLY holds and what
#      it actually costs, so the compaction/Athena decision rests on numbers off
#      the bucket rather than on my estimates. Read-only: LIST only, no GET, no
#      write, no delete.
"""
Warehouse inventory and cost report.

WHY THIS EXISTS
    The compaction-vs-Athena recommendation was built on ESTIMATES — object
    counts times typical sizes. Estimates are fine for a recommendation and
    useless for a billing decision. This reads the real bucket.

WHAT IT MEASURES, AND WHY EACH ONE
    * bytes and objects per top-level prefix — tells you which stream would
      actually benefit from compaction, rather than assuming it is the one with
      the most OBJECTS (signal_journal) when it may be the one with the most
      BYTES (chain_snapshots).
    * NONCURRENT versions separately. Versioning is on and there is no
      lifecycle rule, so old versions accumulate with nobody deciding. This is
      the ONLY line item here that can grow silently, and it is the one real
      billing-surprise vector in the current setup.
    * distinct `dt=` partitions — turns totals into a per-DAY rate measured
      from the bucket, so the annual projection is arithmetic rather than a
      guess.
    * Athena scan cost per prefix, at $5/TB, for a query that reads the whole
      prefix. That is the WORST case (no `dt=` filter); a partitioned query
      scans a fraction.

PRICING is us-east-2 standard, hard-coded below and dated. AWS changes prices;
if these drift the numbers drift with them, so they are stated rather than
buried.

CLI
  python3 warehouse_cost.py              # summary
  python3 warehouse_cost.py --versions   # + noncurrent version accounting (slower)
  python3 warehouse_cost.py --json       # machine-readable
"""

import argparse
import json
import os
import sys
from collections import defaultdict

import boto3

BUCKET = os.environ.get("OT_S3_BUCKET", "vertigo-warehouse-tx9ai")
REGION = os.environ.get("OT_S3_REGION", "us-east-2")

# us-east-2 standard, quoted 2026-08-16.
PRICE_STORAGE_GB_MO = 0.023
PRICE_PUT_PER_1K = 0.005
PRICE_GET_PER_1K = 0.0004
PRICE_ATHENA_TB = 5.00

GB = float(2 ** 30)


def _client():
    return boto3.client("s3", region_name=REGION)


def _tick(msg, quiet):
    """Progress to STDERR so --json stays machine-readable."""
    if not quiet:
        sys.stderr.write("\r  " + msg + " " * 12)
        sys.stderr.flush()


def scan_current(s3, bucket=BUCKET, quiet=False):
    """Per-prefix object counts, bytes, and the distinct dt= days seen."""
    per = defaultdict(lambda: {"objects": 0, "bytes": 0, "days": set()})
    total = {"objects": 0, "bytes": 0}
    pg = s3.get_paginator("list_objects_v2")
    pages = 0
    for page in pg.paginate(Bucket=bucket):
        pages += 1
        if pages % 5 == 0:
            _tick(f"listing… {total['objects']:,} objects "
                  f"({total['bytes'] / GB:.2f} GB) across {pages} page(s)", quiet)
        for o in page.get("Contents", []) or []:
            key, size = o["Key"], int(o.get("Size", 0) or 0)
            parts = key.split("/")
            # raw/<datatype>/dt=<date>/...
            name = "/".join(parts[:2]) if len(parts) > 1 else parts[0]
            rec = per[name]
            rec["objects"] += 1
            rec["bytes"] += size
            for p in parts:
                if p.startswith("dt="):
                    rec["days"].add(p[3:])
                    break
            total["objects"] += 1
            total["bytes"] += size
    _tick(f"listed {total['objects']:,} objects in {pages} page(s)", quiet)
    if not quiet:
        sys.stderr.write("\n")
    return per, total


def scan_versions(s3, bucket=BUCKET, quiet=False):
    """Noncurrent versions and delete markers — the silent-growth line item.

    A SECOND full pass over the bucket, and on a versioned bucket it returns
    every version rather than just the current ones — so it is the slower of
    the two. Skip it with plain `warehouse_cost.py` if you only want sizes.
    """
    cur = {"n": 0, "bytes": 0}
    old = {"n": 0, "bytes": 0}
    marks = 0
    pages = 0
    pg = s3.get_paginator("list_object_versions")
    for page in pg.paginate(Bucket=bucket):
        pages += 1
        if pages % 5 == 0:
            _tick(f"versions… {cur['n'] + old['n']:,} seen across "
                  f"{pages} page(s)", quiet)
        for v in page.get("Versions", []) or []:
            tgt = cur if v.get("IsLatest") else old
            tgt["n"] += 1
            tgt["bytes"] += int(v.get("Size", 0) or 0)
        marks += len(page.get("DeleteMarkers", []) or [])
    _tick(f"versions: {cur['n'] + old['n']:,} in {pages} page(s)", quiet)
    if not quiet:
        sys.stderr.write("\n")
    return cur, old, marks


def report(s3=None, do_versions=False, as_json=False, quiet=False):
    s3 = s3 or _client()
    if not quiet:
        sys.stderr.write(
            f"  scanning s3://{BUCKET} — one LIST pass per 1,000 objects; on a\n"
            f"  ~130k-object bucket expect ~1 min"
            + (", and --versions is a SECOND full pass\n" if do_versions else "\n"))
        sys.stderr.flush()
    per, total = scan_current(s3, quiet=quiet)

    all_days = set()
    for r in per.values():
        all_days |= r["days"]
    ndays = max(1, len(all_days))

    gb = total["bytes"] / GB
    per_day_gb = gb / ndays
    year_gb = per_day_gb * 252            # trading days
    # Storage is billed on the average balance, so a year of linear growth
    # averages half the end-state. Stating that rather than quoting the peak.
    year_end_mo = year_gb * PRICE_STORAGE_GB_MO
    year_avg_mo = (year_gb / 2) * PRICE_STORAGE_GB_MO

    obj_per_day = total["objects"] / ndays
    put_mo = obj_per_day * 21
    put_cost = put_mo / 1000 * PRICE_PUT_PER_1K
    get_cost = put_mo / 1000 * PRICE_GET_PER_1K   # the read-back verify, 1:1

    out = {
        "bucket": BUCKET,
        "objects": total["objects"],
        "gb": round(gb, 4),
        "distinct_days": ndays,
        "per_day": {"objects": round(obj_per_day, 1), "gb": round(per_day_gb, 4)},
        "projected_year": {"gb": round(year_gb, 2),
                           "storage_usd_mo_at_year_end": round(year_end_mo, 2),
                           "storage_usd_mo_year1_avg": round(year_avg_mo, 2)},
        "requests_usd_mo": {"put": round(put_cost, 2), "verify_get": round(get_cost, 2)},
        "prefixes": {},
    }
    for name, r in sorted(per.items(), key=lambda kv: -kv[1]["bytes"]):
        out["prefixes"][name] = {
            "objects": r["objects"],
            "gb": round(r["bytes"] / GB, 4),
            "days": len(r["days"]),
            "avg_kb": round(r["bytes"] / max(1, r["objects"]) / 1024, 1),
            "athena_full_scan_usd": round(r["bytes"] / GB / 1024 * PRICE_ATHENA_TB, 4),
        }

    if do_versions:
        cur, old, marks = scan_versions(s3, quiet=quiet)
        out["versions"] = {
            "current": {"n": cur["n"], "gb": round(cur["bytes"] / GB, 4)},
            "noncurrent": {"n": old["n"], "gb": round(old["bytes"] / GB, 4),
                           "usd_mo": round(old["bytes"] / GB * PRICE_STORAGE_GB_MO, 3)},
            "delete_markers": marks,
        }

    if as_json:
        print(json.dumps(out, indent=2))
        return out

    print()
    print(f"  WAREHOUSE INVENTORY — {BUCKET} ({REGION})")
    print(f"  {'':-<62}")
    print(f"  {out['objects']:,} objects · {out['gb']:.3f} GB · "
          f"{ndays} distinct dt= day(s)")
    print()
    print(f"  {'prefix':<28}{'objects':>9}{'GB':>9}{'avg KB':>9}{'scan $':>9}")
    for name, r in out["prefixes"].items():
        print(f"  {name:<28}{r['objects']:>9,}{r['gb']:>9.3f}"
              f"{r['avg_kb']:>9.1f}{r['athena_full_scan_usd']:>9.3f}")
    print()
    print(f"  measured rate      {out['per_day']['objects']:,.0f} objects/day · "
          f"{out['per_day']['gb']:.3f} GB/day")
    print(f"  projected year     {out['projected_year']['gb']:.1f} GB")
    print(f"  storage $/mo       {out['projected_year']['storage_usd_mo_year1_avg']:.2f}"
          f" (year-1 average) → "
          f"{out['projected_year']['storage_usd_mo_at_year_end']:.2f} (at year end)")
    print(f"  requests $/mo      PUT {out['requests_usd_mo']['put']:.2f} + "
          f"verify-GET {out['requests_usd_mo']['verify_get']:.2f}")
    print(f"  TOTAL $/mo         ~"
          f"{out['projected_year']['storage_usd_mo_year1_avg'] + out['requests_usd_mo']['put'] + out['requests_usd_mo']['verify_get']:.2f}")

    if "versions" in out:
        v = out["versions"]
        print()
        print(f"  versions           current {v['current']['n']:,} "
              f"({v['current']['gb']:.3f} GB) · "
              f"NONCURRENT {v['noncurrent']['n']:,} ({v['noncurrent']['gb']:.3f} GB, "
              f"${v['noncurrent']['usd_mo']:.3f}/mo) · "
              f"{v['delete_markers']:,} delete marker(s)")
        if v["noncurrent"]["n"]:
            print("  ⚠️  noncurrent versions are accumulating with no lifecycle "
                  "rule — this is the one line item that grows unbidden")
    print()
    print("  scan $ = Athena reading that ENTIRE prefix with NO dt= filter,")
    print("  i.e. the worst case. A partitioned query scans a fraction of it.")
    print(f"  prices: ${PRICE_STORAGE_GB_MO}/GB-mo · ${PRICE_PUT_PER_1K}/1k PUT · "
          f"${PRICE_ATHENA_TB}/TB scanned (us-east-2, quoted 2026-08-16)")
    print()
    return out


def main(argv):
    p = argparse.ArgumentParser(description="Warehouse inventory and cost report")
    p.add_argument("--versions", action="store_true",
                   help="also account noncurrent versions (slower, one extra pass)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--quiet", action="store_true", help="no progress output")
    a = p.parse_args(argv[1:])
    try:
        report(do_versions=a.versions, as_json=a.json, quiet=a.quiet or a.json)
        return 0
    except KeyboardInterrupt:
        print("\nwarehouse_cost: interrupted — nothing was written, "
              "the scan is read-only")
        return 130
    except Exception as exc:
        print(f"warehouse_cost: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
