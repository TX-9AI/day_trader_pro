#!/usr/bin/env python3
"""
day_trader_pro/s3_sweep.py  v1.1
Control-side warehouse hygiene. Lists first, deletes only when told twice.

v1.1  2026-08-23  AUDIT F2 + F10 — the third guard bug, and a fourth list.
  F2: the legacy-hash rule is self-verifying ONLY for streams whose key is
      sha256(canon(record)). Whole-file streams (ohlc, eod, liquidity_ledger)
      key on sha256(raw bytes) and store `record` as the file TEXT, so the
      recompute NEVER matches: `--dups --datatype ohlc --apply` would have
      classified 100% of the OHLC archive as legacy and deleted it with the
      panel guard OFF. Proven in sandbox against the real push-side helpers.
      `--datatype` is now restricted to the record-hashed streams, and the
      sweep REFUSES if every checked object reads legacy — a rule that proves
      every object superseded has proven itself wrong.
  F10: PANEL was a fourth hand-copied list that tests/test_panel_mirror.py
      did not pin. A symbol added to selector.PANEL but not here would have
      been CULLED. It now reads selector.PANEL; the literal is the fallback
      only if the import fails, and says so.

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
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config                                                   # noqa: E402

BUCKET = os.environ.get("OT_S3_BUCKET", "vertigo-warehouse-tx9ai")
PREFIX = "raw"

# 🔴 THE 15 SYMBOLS THE FLEET ACTUALLY RUNS. Any key naming one of these is
# UNTOUCHABLE by this tool, whatever the flags say.
# v1.1 — ONE LIST. selector.PANEL is the commit that defines the fleet; this
# file must not carry its own copy (r82's failure class: two state holders,
# one meaning). The literal survives only as a fallback if the import fails.
try:
    import selector as _sel                                     # noqa: E402
    PANEL = set(s.upper() for s in _sel.PANEL)
    if not PANEL:
        raise ImportError("selector.PANEL is empty")
except Exception as _exc:                                       # noqa: BLE001
    print(f"  ⚠️ selector.PANEL unavailable ({_exc}) — using the built-in "
          f"fallback list. Do NOT --apply a culled sweep in this state.")
    PANEL = {"NVDA", "SPX", "PLTR", "MU", "QQQ", "GOOGL", "AMZN", "AVGO",
             "TSLA", "META", "NFLX", "CRM", "UNH", "CVX", "AMD"}

# v1.1 — F2. The legacy rule holds only where the push side keyed the object
# on sha256(canon(record)). Whole-file streams key on the raw bytes and store
# the text, so the recompute can never match and EVERY object reads legacy.
RECORD_HASHED_DATATYPES = {"chain_snapshots", "trades", "circuit_breaker",
                           "signal_journal", "shadow", "candles"}

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


def _iter_keys(s3, prefix: str, quiet: bool = False):
    """Page through a prefix, SAYING SO while it happens.

    🔴 THE METER WENT ON THE DELETE LOOP AND NOT ON THE SCAN, WHICH IS THE PART
    THAT TAKES MINUTES. A full-bucket walk is ~900 sequential LIST calls with
    nothing on screen, so a working scan and a hung one look identical — the
    operator hit Ctrl-C on a healthy run because there was no way to tell.
    ⚠️ SAME LESSON, SECOND PLACE: the fix belongs on EVERY long loop, not on
    the one that happened to get complained about first.
    """
    tok, n, pages = None, 0, 0
    t0 = time.time()
    while True:
        kw = {"Bucket": BUCKET, "Prefix": prefix, "MaxKeys": 1000}
        if tok:
            kw["ContinuationToken"] = tok
        r = s3.list_objects_v2(**kw)
        pages += 1
        for o in r.get("Contents", []):
            n += 1
            yield o["Key"], o.get("Size", 0)
        if not quiet and (pages % 10 == 0):
            el = time.time() - t0
            sys.stdout.write(f"\r  scanning {prefix} — {n:,} objects, "
                             f"{pages} page(s), {el:.0f}s      ")
            sys.stdout.flush()
        if not r.get("IsTruncated"):
            if not quiet and pages >= 10:
                sys.stdout.write(f"\r  scanned {prefix} — {n:,} objects in "
                                 f"{time.time() - t0:.0f}s              \n")
                sys.stdout.flush()
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
    # ⚠️ THIS IS THE SLOWEST PATH IN THE FILE — one GET per object to recompute
    # the hash, not one LIST per thousand. On 40k chain snapshots that is 40k
    # round trips, so it needs its own meter even more than the scan does.
    t0 = time.time()
    for key, _size in _iter_keys(s3, base, quiet=True):
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
        if checked % 250 == 0:
            el = time.time() - t0
            sys.stdout.write(f"\r  checked {checked:,} object(s), "
                             f"{len(stale):,} legacy, {checked / max(el, 1):.0f}/s      ")
            sys.stdout.flush()
    print(f"\r  checked {checked:,} object(s) under {base} — "
          f"{len(stale):,} legacy            ")
    # v1.1 — F2. If the rule condemns EVERYTHING it checked, the rule is
    # wrong for this stream, not the stream. Refuse rather than return a
    # delete list that is the whole archive.
    if checked and len(stale) == checked:
        print(f"  🔴 REFUSING: all {checked:,} checked object(s) read LEGACY — "
              f"that is the signature of a key basis this rule does not "
              f"understand, not of duplicates. Nothing returned.")
        return []
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


# ⚠️ A MANIFEST WITHOUT PROVENANCE IS AMBIGUOUS, AND IT BIT ON 2026-08-25.
# The dead-stream rule deletes by PREFIX — `raw/shadow/` is dead whatever
# symbol is in the path — but `--from-manifest` re-applied the SYMBOL guard and
# refused 359,123 shadow keys because they sit under sym=QQQ, sym=NVDA and the
# rest. Half the purge silently did not happen.
# 🔑 THE RULE TRAVELS WITH THE LIST. The header records which sweep produced
# the manifest, so the delete applies the guard that rule actually needs
# instead of guessing — and a hand-edited manifest with no header gets the
# SAFE default, not the permissive one.
MANIFEST_HEADER = "# vertigo-s3-sweep rule="


def write_manifest(keys: list, path: str, rule: str = "symbol") -> str:
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
        fh.write(f"{MANIFEST_HEADER}{rule}\n")
        for k in keys:
            fh.write(k + "\n")
    print(f"\n  manifest written: {path}  ({len(keys):,} keys)")
    return path


def delete_from_manifest(s3, path: str, apply: bool) -> int:
    """Delete exactly what the manifest lists — re-checking the guard."""
    lines = [l.rstrip("\n") for l in open(path)]
    rule = "symbol"                       # ⚠️ SAFE DEFAULT when unstated.
    for l in lines:
        if l.startswith(MANIFEST_HEADER):
            rule = l[len(MANIFEST_HEADER):].strip() or "symbol"
    keys = [l.strip() for l in lines if l.strip() and not l.startswith("#")]
    # ⚠️ THE GUARD STILL RUNS for symbol-scoped rules — a manifest is a file
    # and a file can be edited. It is skipped ONLY for prefix rules, where the
    # key was selected because of WHERE it lives, not who owns it.
    guard = (rule != "prefix")
    print(f"  manifest holds {len(keys):,} key(s)   rule={rule}   "
          f"panel-guard={'ON' if guard else 'OFF (prefix rule)'}")
    return delete(s3, keys, apply, guard_panel=guard)


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
    # ⚠️ A SAMPLE IS NOT A REVIEW. Printing 25 keys of a 359,000-key list is
    # neither — the MANIFEST is the review surface, and a per-prefix breakdown
    # says more about what is about to go than any 25 paths could.
    from collections import Counter
    by_pfx = Counter("/".join(k.split("/")[:2]) for k in keys)
    print(f"\n  {len(keys):,} object(s) would be deleted:")
    for pfx, n in by_pfx.most_common():
        print(f"     {pfx + '/':<28} {n:>9,}")
    print(f"     {'sample':<28} {keys[0]}")

    if not apply:
        print("\n  DRY RUN — nothing deleted. Re-run with --apply.")
        return 0

    # ⚠️ PROGRESS, BECAUSE SILENCE MEANS TWO THINGS. A delete loop that prints
    # nothing between batches looks IDENTICAL whether it is working or wedged —
    # and at 1,000 keys per call a 500k purge is 500 round trips with nothing
    # on screen. The operator asked mid-run whether it had stalled and there
    # was no way to tell. `warehouse_cost.py` already counts its LIST pages for
    # exactly this reason; this is that habit, carried across.
    done, total = 0, len(keys)
    t0 = time.time()
    for i in range(0, total, 1000):
        batch = [{"Key": k} for k in keys[i:i + 1000]]
        r = s3.delete_objects(Bucket=BUCKET, Delete={"Objects": batch})
        done += len(r.get("Deleted", []))
        for err in r.get("Errors", []):
            print(f"  ! {err.get('Key')}: {err.get('Message')}")
        el = time.time() - t0
        rate = done / el if el > 0 else 0
        eta = (total - done) / rate if rate > 0 else 0
        # \r keeps it to one line; the final newline comes from the summary.
        sys.stdout.write(f"\r  deleted {done:,}/{total:,} "
                         f"({100.0 * done / total:.0f}%)  "
                         f"{rate:,.0f}/s  eta {eta / 60:.1f} min      ")
        sys.stdout.flush()
    print(f"\n\n  deleted {done:,} object(s) in {(time.time() - t0) / 60:.1f} min.")
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
            write_manifest(keys, a.manifest, rule="prefix")
        else:
            delete(s3, keys, a.apply, guard_panel=False)
        return 0

    if a.dups:
        if a.datatype not in RECORD_HASHED_DATATYPES:
            print(f"  🔴 REFUSING --dups on '{a.datatype}': the legacy-hash rule "
                  f"is only self-verifying for {sorted(RECORD_HASHED_DATATYPES)}. "
                  f"Whole-file streams key on raw bytes and would read 100% legacy.")
            return 2
        pfx = f"dt={a.dt}/" if a.dt else ""
        print(f"LEGACY-HASH SWEEP — {a.datatype} {pfx or '(all dates)'}")
        print("  keeping any object whose key == sha256(canon(record))[:16]")
        stale = find_legacy(s3, a.datatype, pfx)
        # ⚠️ --manifest WAS IGNORED HERE. It was wired into the culled and
        # dead-stream branches and not this one, so a 35-minute scan (one GET
        # per object) printed its result and threw the list away. The SLOWEST
        # sweep was the one that could not save its work.
        if a.manifest:
            write_manifest(stale, a.manifest, rule="prefix")
        else:
            # ⚠️ guard OFF here, and ONLY here: every key in `stale` was proven
            # superseded by recomputing the sha of its own record, so the
            # symbol it belongs to is irrelevant — and the duplicates are ON
            # panel boxes.
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
            write_manifest(keys, a.manifest, rule="symbol")
        else:
            delete(s3, keys, a.apply)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
