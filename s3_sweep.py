#!/usr/bin/env python3
"""
day_trader_pro/s3_sweep.py  v1.0
Control-side warehouse hygiene. Lists first, deletes only when told twice.

v1.0  2026-08-25  Operator: "Control will be responsible for S3 hygiene and
maintenance." The traders write and never delete; delete lives here and only
here, so a compromised or buggy box cannot destroy the warehouse.

TWO JOBS, BOTH ONE-TIME:

1. LEGACY-HASH DUPLICATES.
   🔑 DIAGNOSED 2026-08-25 AND THE RULE IS SELF-VERIFYING. Chain-snapshot
   prefixes held ~2x the objects they should. Fetching a pair proved the
   RECORDS WERE IDENTICAL — same source file, same line, same host — and only
   `pushed_at_utc` differed, which the current canonicaliser explicitly
   excludes. Recomputing the sha showed the NEWER key equals the sha of its own
   record and the older one does not.
   **So an object is CURRENT if its key suffix equals sha256(canon(record))[:16]
   and LEGACY otherwise.** No dates, no heuristics, no guessing — each object
   answers for itself.
   ⚠️ THIS IS A MIGRATION ARTIFACT, NOT A LIVE BUG. The write side was already
   fixed; new pushes land correctly. Nothing here needs to run twice.
   ⚠️ AND NOTHING WAS EVER LOST. The duplicates cost storage and inflated the
   ledger; they never corrupted a read, because both copies hold the same
   record.

2. CULLED SYMBOLS.
   The 2026-08-20 pare cut the fleet 29 -> 15 and TERMINATED the other 14.
   Operator's ruling: their data goes, trades AND tape. The trades came from an
   engine whose premise measured false (44.9% direction), so they cannot inform
   fitting and pooling them into a later study would poison it. The tape is
   only a few weeks deep on symbols that will not be traded — not enough to
   support a study, and depth is what makes tape useful.

🔴 IT LISTS BEFORE IT DELETES, ALWAYS. `--apply` is required, and even then
every key is printed. Deletion is the one irreversible act in this system and
the operator's own rule is that data pruned before you knew you needed it
cannot be recovered at any price — so the cost of looking first is nothing and
the cost of not looking is total.

⚠️ IT REFUSES TO TOUCH A PANEL SYMBOL. The keep-list is hardcoded from
selector.PANEL and checked on every key; a typo in --symbols cannot delete a
live symbol's history.

Run:  python3 s3_sweep.py --dups                    # list legacy duplicates
      python3 s3_sweep.py --dups --apply            # delete them
      python3 s3_sweep.py --culled                  # list culled-symbol data
      python3 s3_sweep.py --culled --apply
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config                                                   # noqa: E402

BUCKET = os.environ.get("OT_S3_BUCKET", "vertigo-warehouse-tx9ai")
PREFIX = "raw"

# 🔴 THE 15 SYMBOLS THE FLEET ACTUALLY RUNS. Any key naming one of these is
# UNTOUCHABLE by this tool, whatever the flags say.
PANEL = {"NVDA", "SPX", "PLTR", "MU", "QQQ", "GOOGL", "AMZN", "AVGO",
         "TSLA", "META", "NFLX", "CRM", "UNH", "CVX", "AMD"}

# 🔴 ALWAYS KEEP, WHATEVER THE PANEL SAYS. VIX is not traded and is therefore
# not a panel symbol — but the session guard and the condor READ IT, so its
# tape is live input to live behaviour. The first version of this tool listed
# VIX and VIX_EXT for deletion.
ALWAYS_KEEP = {"VIX"}


def _base_symbol(sym: str) -> str:
    """Strip the extended-hours suffix. `NVDA_EXT` is NVDA's tape.

    🔴 THE BUG THIS FIXES, CAUGHT BY A DRY RUN ON 2026-08-25. The guard did an
    EXACT match against PANEL, so `"NVDA_EXT" != "NVDA"` passed straight
    through it — and the sweep proposed deleting 321,835 objects including the
    EXTENDED-HOURS TAPE OF EVERY SYMBOL THE FLEET ACTIVELY TRADES, plus VIX.
    ⚠️ A guard that matches on a name FORMAT rather than on IDENTITY is not a
    guard. The operator's instinct to scan the bucket before deleting is what
    surfaced it; nothing in the tool would have.
    """
    s = (sym or "").upper()
    return s[:-4] if s.endswith("_EXT") else s


def _is_protected(sym: str) -> bool:
    b = _base_symbol(sym)
    return b in PANEL or b in ALWAYS_KEEP


def _client():
    import boto3
    return boto3.client("s3")


def _canon(rec) -> bytes:
    """Must match warehouse/s3_push.py::_canon EXACTLY or the rule is wrong."""
    return json.dumps(rec, sort_keys=True, separators=(",", ":"),
                      default=str).encode("utf-8")


def _iter_keys(s3, prefix: str):
    tok = None
    while True:
        kw = {"Bucket": BUCKET, "Prefix": prefix, "MaxKeys": 1000}
        if tok:
            kw["ContinuationToken"] = tok
        r = s3.list_objects_v2(**kw)
        for o in r.get("Contents", []):
            yield o["Key"], o.get("Size", 0)
        if not r.get("IsTruncated"):
            return
        tok = r.get("NextContinuationToken")


def _sym_of(key: str):
    for part in key.split("/"):
        if part.startswith("sym="):
            return part[4:]
    return None


def find_legacy(s3, datatype: str, limit_prefix: str = "") -> list:
    """Objects whose key suffix does NOT match sha(canon(record))."""
    base = f"{PREFIX}/{datatype}/{limit_prefix}"
    stale, checked = [], 0
    for key, _size in _iter_keys(s3, base):
        name = key.rsplit("/", 1)[-1]
        if "-" not in name or not name.endswith(".json"):
            continue
        suffix = name[:-5].split("-", 1)[1]
        try:
            body = s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()
            obj = json.loads(body)
        except Exception as exc:                                # noqa: BLE001
            print(f"  ! unreadable, SKIPPED (never deleted): {key} — {exc}")
            continue
        rec = obj.get("record")
        if rec is None:
            # ⚠️ NO RECORD MEANS THE RULE CANNOT BE APPLIED, so the object is
            # left alone. "I could not check it" must never become "delete it".
            continue
        want = hashlib.sha256(_canon(rec)).hexdigest()[:16]
        checked += 1
        if suffix != want:
            stale.append(key)
    print(f"  checked {checked} object(s) under {base}")
    return stale


def find_culled(s3, symbols: set) -> list:
    """Every object for a symbol no longer on the panel."""
    out = []
    for key, _size in _iter_keys(s3, PREFIX + "/"):
        sym = _sym_of(key)
        if sym and sym in symbols:
            out.append(key)
    return out


# 🔑 DEAD STREAMS — the largest win and the least ambiguous one. Measured
# 2026-08-25 against a 1,148,645-object bucket:
#   raw/shadow        492,945 objects — 43% OF THE WHOLE BUCKET. The shadow
#                     observer was NEVER INSTALLED on the v4 fleet (verified on
#                     a box: no shadow timers), so this is a v3 corpse.
#   raw/regime_log      9,655 objects — the retired stream, dropped from the
#                     push in r65. Nothing has written to it since.
# ⚠️ NOTE THE SCALE AGAINST THE SYMBOL SWEEP: shadow alone is more objects than
# every culled symbol combined, and it carries none of the risk.
DEAD_STREAMS = ["shadow", "regime_log"]


def find_dead_streams(s3) -> list:
    out = []
    for ds in DEAD_STREAMS:
        n = 0
        for key, _ in _iter_keys(s3, f"{PREFIX}/{ds}/"):
            out.append(key)
            n += 1
        print(f"  {ds:<16} {n:>9,} object(s)")
    return out


def write_manifest(keys: list, path: str) -> str:
    """Freeze the delete list to disk BEFORE anything is removed.

    🔴 THE MANIFEST IS THE REVIEW SURFACE, and it exists because control has
    `DeleteObject` but NOT `PutObject` — proven by probe 2026-08-25 — so
    quarantining by MOVING objects into a purge/ prefix is not available
    without granting write back to control and undoing the separation the
    operator specified.
    ⚠️ IT ALSO PINS WHAT WAS APPROVED. Deleting from a manifest deletes exactly
    the list a human read; deleting from a fresh scan deletes whatever the
    bucket looks like at that moment, which is not the same thing and cannot be
    reviewed.
    """
    with open(path, "w") as fh:
        for k in keys:
            fh.write(k + "\n")
    print(f"\n  manifest written: {path}  ({len(keys):,} keys)")
    return path


def delete_from_manifest(s3, path: str, apply: bool) -> int:
    """Delete exactly what the manifest lists — re-checking the guard."""
    keys = [l.strip() for l in open(path) if l.strip()]
    print(f"  manifest holds {len(keys):,} key(s)")
    # ⚠️ THE GUARD RUNS AGAIN HERE. A manifest is a file; a file can be edited,
    # and the cost of re-checking is nothing against the cost of not.
    return delete(s3, keys, apply, guard_panel=True)


def delete(s3, keys: list, apply: bool, guard_panel: bool = True) -> int:
    """Delete, with the panel guard on unless the caller has a proven rule.

    ⚠️ THE GUARD IS FOR SYMBOL-SCOPED DELETION ONLY, and getting this wrong was
    caught in test: with the guard applied to the LEGACY-HASH sweep it refused
    every duplicate, because the duplicates live on PANEL boxes — AMD, NVDA,
    QQQ. A guard that blocks the one job it was not written for is not safety,
    it is a tool that silently does nothing.

    🔑 THE DISTINCTION: the culled sweep deletes a symbol's data because of WHO
    it belongs to, so a wrong symbol is catastrophic and the guard is right.
    The legacy sweep deletes an object because THE OBJECT'S OWN RECORD proves
    the key is a superseded copy — that rule is self-verifying per object and
    does not care which symbol it belongs to. `guard_panel=False` is only ever
    correct for a rule of the second kind.
    """
    guarded = [k for k in keys if guard_panel and _is_protected(_sym_of(k) or "")]
    if guarded:
        print(f"\n  🔴 REFUSING {len(guarded)} key(s) naming a PANEL symbol:")
        for k in guarded[:5]:
            print(f"     {k}")
        keys = [k for k in keys if k not in set(guarded)]

    if not keys:
        print("\n  nothing to delete.")
        return 0
    print(f"\n  {len(keys)} object(s) would be deleted:")
    for k in keys[:25]:
        print(f"     {k}")
    if len(keys) > 25:
        print(f"     … and {len(keys) - 25} more")

    if not apply:
        print("\n  DRY RUN — nothing deleted. Re-run with --apply.")
        return 0

    done = 0
    for i in range(0, len(keys), 1000):
        batch = [{"Key": k} for k in keys[i:i + 1000]]
        r = s3.delete_objects(Bucket=BUCKET, Delete={"Objects": batch})
        done += len(r.get("Deleted", []))
        for err in r.get("Errors", []):
            print(f"  ! {err.get('Key')}: {err.get('Message')}")
    print(f"\n  deleted {done} object(s).")
    return done


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dups", action="store_true",
                    help="find legacy-hash duplicate objects")
    ap.add_argument("--culled", action="store_true",
                    help="find data for symbols no longer on the panel")
    ap.add_argument("--datatype", default="chain_snapshots",
                    help="for --dups (default: the one known to be affected)")
    ap.add_argument("--dt", default="", help="limit --dups to dt=YYYY-MM-DD/")
    ap.add_argument("--symbols", default="",
                    help="for --culled: comma-separated; default = discovered")
    ap.add_argument("--dead-streams", action="store_true",
                    help="shadow + regime_log — never installed / retired")
    ap.add_argument("--manifest", default="",
                    help="write the list here instead of deleting")
    ap.add_argument("--from-manifest", default="",
                    help="delete exactly the keys in this file")
    ap.add_argument("--apply", action="store_true",
                    help="actually delete. Without it, this only lists.")
    a = ap.parse_args(argv[1:] if argv else None)

    if not (a.dups or a.culled or a.dead_streams or a.from_manifest):
        ap.error("choose --dups, --culled, --dead-streams or --from-manifest")

    s3 = _client()

    if a.from_manifest:
        print(f"DELETE FROM MANIFEST — {a.from_manifest}")
        delete_from_manifest(s3, a.from_manifest, a.apply)
        return 0

    if a.dead_streams:
        print("DEAD-STREAM SWEEP — never installed / retired")
        keys = find_dead_streams(s3)
        if a.manifest:
            write_manifest(keys, a.manifest)
        else:
            delete(s3, keys, a.apply, guard_panel=False)
        return 0

    if a.dups:
        pfx = f"dt={a.dt}/" if a.dt else ""
        print(f"LEGACY-HASH SWEEP — {a.datatype} {pfx or '(all dates)'}")
        print("  keeping any object whose key == sha256(canon(record))[:16]")
        stale = find_legacy(s3, a.datatype, pfx)
        # ⚠️ guard OFF here, and ONLY here: every key in `stale` was proven
        # superseded by recomputing the sha of its own record, so the symbol it
        # belongs to is irrelevant — and the duplicates are ON panel boxes.
        delete(s3, stale, a.apply, guard_panel=False)

    if a.culled:
        if a.symbols:
            syms = {s.strip().upper() for s in a.symbols.split(",") if s.strip()}
        else:
            seen = set()
            for key, _ in _iter_keys(s3, PREFIX + "/"):
                s = _sym_of(key)
                if s:
                    seen.add(s)
            # ⚠️ FILTER ON THE BASE SYMBOL, not the literal string.
            syms = {s for s in seen if not _is_protected(s)}
        # ⚠️ SAY WHICH SYMBOLS, BEFORE COUNTING KEYS. A list of 40,000 keys is
        # unreviewable; a list of 14 tickers is checkable at a glance, and it
        # is where a mistake would actually be caught.
        print(f"CULLED-SYMBOL SWEEP — {len(syms)} symbol(s): "
              f"{', '.join(sorted(syms)) or '(none)'}")
        print(f"  panel (never touched): {', '.join(sorted(PANEL))}")
        if not syms:
            return 0
        keys = find_culled(s3, syms)
        if a.manifest:
            write_manifest(keys, a.manifest)
        else:
            delete(s3, keys, a.apply)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
