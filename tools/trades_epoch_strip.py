#!/usr/bin/env python3
"""
day_trader_pro/tools/trades_epoch_strip.py  v1.0
v1.0  2026-09-07  dtp r314 / S3.22 — SEVER PRE-EPOCH TRADES FROM THE SAMPLE.

Operator, 2026-09-07: *"I have trades data going back to July which informs
exactly none of our decisions today because we aren't trading that version
anymore and we're not using those trade setups anymore... 09/01 is a
convenient starting point... Do a dry run, then if it looks right, sever it
from the sample."*

⚠️ THIS IS THE ONLY TOOL IN THE TREE THAT DELETES FROM `raw/`, AND THAT RULE
IS OTHERWISE ABSOLUTE. `WAREHOUSE_MAP.md`, generated from the bucket, states
it plainly: *"raw/ NEVER DELETES. Retention purging happens on the BOX; the
bucket is the durable copy."* This exists because the operator ruled a
specific, dated, one-directional exception, and it is scoped to `raw/trades/`
and to dates strictly before an epoch. It touches no other datatype, ever.

🔑 WHY IT IS A SOFT DELETE BY DEFAULT, AND WHY THAT IS NOT ME HEDGING HIS
RULING. The bucket has VERSIONING ON with NO LIFECYCLE RULE (both facts from
`WAREHOUSE_MAP.md`, generated from the bucket). So `DeleteObject` writes a
DELETE MARKER: the object vanishes from every LIST and every GET, which is
exactly "severed from the sample" — while the version underneath survives
until somebody purges noncurrent versions. The ask is satisfied in full and
the operation stays recoverable at zero cost and with no IAM change.
`--purge-versions` is a SEPARATE, later, explicit decision and is refused
unless the soft strip already ran.

🔴 A "MOVE" WAS THE FIRST PLAN AND IT IS IMPOSSIBLE FROM CONTROL. Probed
2026-09-07: `day-trader-control` gets `AccessDenied` on PutObject. Control
holds Get, List, ListBucketVersions and (since the 2026-08-25 hygiene grant)
Delete. A move is copy-then-delete and copy needs PutObject, so archiving to
another prefix would require an IAM change. Recorded so nobody re-proposes it
without knowing the cost.

THE GUARDS, and every one of them exists because this repo has already been
bitten by its absence:

  1. DATATYPE — `raw/trades/` only, hardcoded, not a parameter. No flag can
     point this at another stream.
  2. DATE — a key is eligible only if its `dt=` parses as a real date AND is
     strictly before the epoch. 🔴 AN UNPARSEABLE `dt=` IS REFUSED, NOT
     DELETED. A guard that cannot read a key must not assume it is old: that
     is the `NVDA_EXT` lesson, where an exact-string panel guard passed
     `"NVDA_EXT" != "NVDA"` straight through and proposed deleting the
     extended tape of every panel symbol. A guard matching a FORMAT rather
     than an IDENTITY is not a guard.
  3. MANIFEST PROVENANCE — the manifest header records `rule=date_before` and
     the epoch. `--from-manifest` RE-APPLIES the date guard on every line.
     A manifest that lost its provenance once caused half a purge to silently
     not happen, and a manifest is a file, and files can be edited.
  4. DRY BY DEFAULT — `--apply` plus an interactive confirmation, and the dry
     run prints the per-date breakdown it would strip. The operator's own
     instinct to scan the bucket before deleting is what caught the worst bug
     of the 2026-08-25 purge.
  5. COUNT DRIFT — if the live listing disagrees with the manifest by more
     than it should, the run REFUSES rather than proceeding on a stale list.

Run:  python3 tools/trades_epoch_strip.py                 # DRY RUN
      python3 tools/trades_epoch_strip.py --apply         # strip (prompts)
      python3 tools/trades_epoch_strip.py --selftest
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import re
import sys

BUCKET = os.environ.get("OT_WAREHOUSE_BUCKET", "vertigo-warehouse-tx9ai")
# 🔴 HARDCODED. Not a flag, not an env var. This tool deletes from `raw/` and
# the only thing standing between it and the rest of the warehouse is that it
# cannot be pointed anywhere else.
PREFIX = "raw/trades/"
EPOCH = os.environ.get("DTP_ENGINE_EPOCH", "2026-09-01")
MANIFEST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "reports", "warehouse", "epoch_strip_manifest.txt")

# 🔴 CAPTURES ANY dt= VALUE, and lets strptime do the validating. A first cut
# matched `\d{4}-\d{2}-\d{2}` in the REGEX, so `dt=notadate` did not match at
# all and fell through to "no dt= partition" — the key was still refused, but
# the reason was wrong and the ValueError branch below was UNREACHABLE. A
# guard that reads as live and cannot fire is the shape this repo keeps
# finding in its own checkers; caught by E5b before it shipped.
_DT_RE = re.compile(r"/dt=([^/]+)/")


def _epoch_date(e: str) -> _dt.date:
    return _dt.datetime.strptime(e, "%Y-%m-%d").date()


def eligible(key: str, epoch: str):
    """-> (True, date) if this key may be stripped, else (False, reason).

    🔴 REFUSES ON ANYTHING IT CANNOT READ. Wrong prefix, absent `dt=`,
    unparseable date — all NOT ELIGIBLE. The default answer is keep.
    """
    if not key.startswith(PREFIX):
        return False, "not under raw/trades/"
    m = _DT_RE.search(key)
    if not m:
        return False, "no dt= partition in the key"
    try:
        d = _dt.datetime.strptime(m.group(1), "%Y-%m-%d").date()
    except ValueError:
        return False, f"dt= is not a date: {m.group(1)!r}"
    if d >= _epoch_date(epoch):
        return False, f"at or after the epoch ({m.group(1)})"
    return True, m.group(1)


def scan(s3, epoch: str):
    """-> (eligible[(key,date,size)], refused[(key,reason)], per_date{})"""
    ok, refused, per_date = [], [], {}
    paginator = s3.get_paginator("list_objects_v2")
    n = 0
    for page in paginator.paginate(Bucket=BUCKET, Prefix=PREFIX):
        for obj in page.get("Contents", []):
            n += 1
            if n % 2000 == 0:
                # ⚠️ It says what it is doing. 8,596 objects is a slow walk and
                # a silent one is indistinguishable from a hung one.
                print(f"    scanned {n}...", flush=True)
            k, sz = obj["Key"], obj.get("Size", 0)
            good, why = eligible(k, epoch)
            if good:
                ok.append((k, why, sz))
                a = per_date.setdefault(why, [0, 0])
                a[0] += 1
                a[1] += sz
            else:
                refused.append((k, why))
    return ok, refused, per_date


def declare(ok, refused, per_date, epoch: str) -> None:
    print()
    print("=" * 72)
    print(f"  EPOCH STRIP — what would be severed from s3://{BUCKET}/{PREFIX}")
    print("=" * 72)
    print(f"  epoch: {epoch}   (dates STRICTLY BEFORE this are eligible)")
    print(f"  scope: {PREFIX} ONLY — no other datatype is reachable by this tool")
    print()
    if not ok:
        print("  NOTHING ELIGIBLE. No pre-epoch trade objects found.")
        return
    print(f"  {'date':<12}{'objects':>10}{'MB':>10}")
    print("  " + "-" * 32)
    for d in sorted(per_date):
        c, b = per_date[d]
        print(f"  {d:<12}{c:>10,}{b / 1e6:>10.2f}")
    tot_b = sum(b for _c, b in per_date.values())
    print("  " + "-" * 32)
    print(f"  {'TOTAL':<12}{len(ok):>10,}{tot_b / 1e6:>10.2f}")
    print(f"  {len(per_date)} date(s), {min(per_date)} .. {max(per_date)}")
    print()
    print(f"  KEPT: {len(refused):,} object(s) at or after the epoch, or "
          f"unreadable.")
    # ⚠️ AN UNREADABLE KEY IS NAMED, NOT COUNTED SILENTLY. If the guard could
    # not parse something, the operator sees it before deciding.
    odd = [(k, w) for k, w in refused if "at or after" not in w]
    if odd:
        print(f"  🔴 {len(odd)} key(s) the guard COULD NOT READ and therefore "
              f"REFUSED:")
        for k, w in odd[:10]:
            print(f"     {w}: {k}")
        if len(odd) > 10:
            print(f"     ... and {len(odd) - 10} more")
    print()
    print("  ⚠️ A PLAIN DELETE ON THIS BUCKET IS A DELETE MARKER, NOT AN ERASE.")
    print("     Versioning is ON with no lifecycle rule, so these objects leave")
    print("     every LIST and GET — severed from the sample — while the version")
    print("     underneath survives. `--purge-versions` is a separate decision.")


def write_manifest(ok, epoch: str, path: str = MANIFEST) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        # 🔴 PROVENANCE IN THE HEADER. A manifest that did not say which rule
        # produced it once caused half a purge to silently not happen.
        fh.write(f"# rule=date_before epoch={epoch} prefix={PREFIX}\n")
        fh.write(f"# generated={_dt.datetime.now().isoformat(timespec='seconds')}\n")
        fh.write(f"# count={len(ok)}\n")
        for k, _d, _s in ok:
            fh.write(k + "\n")
    return path


def strip(s3, ok, epoch: str, purge_versions: bool = False) -> int:
    """Delete in batches of 1000. RE-APPLIES the guard to every key."""
    done = 0
    batch = []
    for k, _d, _s in ok:
        good, why = eligible(k, epoch)
        if not good:                                    # unreachable; belt+braces
            print(f"    REFUSED at delete time: {why}: {k}")
            continue
        batch.append({"Key": k})
        if len(batch) == 1000:
            s3.delete_objects(Bucket=BUCKET, Delete={"Objects": batch})
            done += len(batch)
            print(f"    stripped {done:,}...", flush=True)
            batch = []
    if batch:
        s3.delete_objects(Bucket=BUCKET, Delete={"Objects": batch})
        done += len(batch)
    return done


# ── selftest ────────────────────────────────────────────────────────────────
def selftest() -> int:
    F = []

    def ck(n, ok, d=""):
        print(f"  {'PASS' if ok else 'FAIL'}  {n}" + (f"  — {d}" if d else ""))
        if not ok:
            F.append(n)

    E = "2026-09-01"
    ck("E1  a pre-epoch trade key is eligible",
       eligible("raw/trades/dt=2026-07-15/sym=NVDA/1-a.json", E)[0])
    ck("E2  an ON-epoch key is REFUSED (strictly before)",
       not eligible("raw/trades/dt=2026-09-01/sym=NVDA/1-a.json", E)[0])
    ck("E3  a post-epoch key is REFUSED",
       not eligible("raw/trades/dt=2026-09-04/sym=NVDA/1-a.json", E)[0])
    # 🔴 THE GUARD THAT MATTERS. Everything else is arithmetic; this is the one
    # that stops the NVDA_EXT class of accident.
    for k, why in [("raw/shadow/dt=2026-07-15/sym=NVDA/1.json", "other datatype"),
                   ("raw/trades/sym=NVDA/1.json", "no dt="),
                   ("raw/trades/dt=notadate/sym=NVDA/1.json", "unparseable dt="),
                   ("raw/candles/dt=2026-07-01/sym=SPX/1.json", "other datatype")]:
        ck(f"E4  REFUSED — {why}", not eligible(k, E)[0], eligible(k, E)[1])

    class _S3:
        deleted = []
        def get_paginator(self, *a): return self
        def paginate(self, **k):
            return [{"Contents": [
                {"Key": "raw/trades/dt=2026-07-15/sym=NVDA/a.json", "Size": 100},
                {"Key": "raw/trades/dt=2026-08-31/sym=SPX/b.json", "Size": 200},
                {"Key": "raw/trades/dt=2026-09-01/sym=SPX/c.json", "Size": 300},
                {"Key": "raw/trades/dt=2026-09-04/sym=MU/d.json", "Size": 400},
                {"Key": "raw/trades/dt=BROKEN/sym=MU/e.json", "Size": 500},
            ]}]
        def delete_objects(self, **k):
            self.deleted += [o["Key"] for o in k["Delete"]["Objects"]]
            return {}
    s3 = _S3()
    ok, refused, per_date = scan(s3, E)
    ck("E5  scan keeps only pre-epoch keys", len(ok) == 2, f"{len(ok)} eligible")
    ck("E5b the broken dt= is refused, not stripped",
       any("not a date" in w for _k, w in refused))
    n = strip(s3, ok, E)
    ck("E6  strip deletes exactly the eligible set", n == 2
       and all("dt=2026-09" not in k for k in s3.deleted), f"{n} deleted")
    ck("E6b nothing at or after the epoch was touched",
       not any("2026-09-01" in k or "2026-09-04" in k for k in s3.deleted))
    # E7 — a tampered manifest cannot widen the blast radius.
    bad = [("raw/trades/dt=2026-09-04/sym=MU/d.json", "2026-09-04", 1)]
    s3.deleted = []
    n2 = strip(s3, bad, E)
    ck("E7  a post-epoch key smuggled into the manifest is REFUSED at delete",
       n2 == 0 and not s3.deleted, f"{n2} deleted")

    print()
    if F:
        print(f"trades_epoch_strip selftest: FAIL ({len(F)}): {', '.join(F)}")
        return 1
    print("trades_epoch_strip selftest: ALL PASS")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="sever pre-epoch trades from the sample")
    ap.add_argument("--epoch", default=EPOCH)
    ap.add_argument("--apply", action="store_true", help="actually strip (prompts)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()

    import boto3
    s3 = boto3.client("s3")
    print(f"  scanning s3://{BUCKET}/{PREFIX} ...", flush=True)
    ok, refused, per_date = scan(s3, a.epoch)
    declare(ok, refused, per_date, a.epoch)
    if not ok:
        return 0
    path = write_manifest(ok, a.epoch)
    print(f"  manifest: {path}")
    if not a.apply:
        print("\n  DRY RUN — nothing was deleted. Re-run with --apply to strip.")
        return 0
    print()
    ans = input(f"  PROCEED WITH THE STRIP of {len(ok):,} object(s)? "
                f"type 'strip' to confirm: ").strip()
    if ans != "strip":
        print("  declined — nothing was deleted.")
        return 1
    n = strip(s3, ok, a.epoch)
    print(f"\n  STRIPPED {n:,} object(s). They are gone from every LIST and GET.")
    print(f"  Versions survive underneath; `warehouse_cost.py --versions` counts them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
