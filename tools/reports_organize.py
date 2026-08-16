#!/usr/bin/env python3
# day_trader_pro/tools/reports_organize.py — v1.0
# v1.0 (2026-08-16) — give each recurring report type its own flat folder under
#      reports/. COPIES, never moves: the originals stay put so report 41's
#      glob, report 47's replay discovery and the diary keep working untouched.
"""
Organise reports/ by report TYPE. One folder per type, flat inside.

WHAT IT DOES AND DELIBERATELY DOES NOT DO
    * COPIES. `cp`, not `mv` — the operator's call, and it is the right one:
      reports/ is BOTH an output directory AND an input directory, so a move is
      a live edit to three reports' data sources. A copy is additive and
      reversible; removing the root originals is a separate, deliberate step
      taken once the readers have been repointed.
    * NO DATE SUBDIVISION. One folder per type, flat inside — explicit
      instruction. Deeper nesting buys nothing and makes globbing worse.
    * ONE-OFF DIAGNOSTICS STAY AT ROOT. A file whose pattern occurs fewer than
      MIN_RECURRING times is a one-shot, not an automated product.
    * EXISTING DIRECTORIES ARE NEVER TOUCHED — warehouse/ and backtests/ are
      not report files and are skipped by name AND by isdir().

⚠️ THE PART THAT MATTERS LATER
    Three of these types are READ BACK by other reports:
      fleet_trades_*.json   -> report 41's BUNDLE_GLOB, and report 40's fallback
      morning_report_*.json -> report 41's sentiment join
      regime_replay_*.jsonl -> report 47 auto-discovers these
      regime_diary.*        -> the diary viewers
    Copying is harmless. **DELETING the root originals is not** — it would
    silently shorten report 41's cumulative window, which is the exact failure
    the reports/-is-both-input-and-output warning exists for. This script
    prints that list every run so the risk is never out of sight.

USAGE
  python3 tools/reports_organize.py            # dry run, changes nothing
  python3 tools/reports_organize.py --apply    # copy into per-type folders
"""

import argparse
import os
import re
import shutil
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import config  # noqa: E402

REPORTS = config.REPORTS_DIR
MIN_RECURRING = 3          # fewer than this = a one-shot, stays at root
SKIP_DIRS = {"warehouse", "backtests"}

# Types other reports READ. Copying is fine; deleting the originals is not.
CONSUMED_BY_OTHERS = {
    "fleet_trades": "report 41 BUNDLE_GLOB + report 40 fallback",
    "morning_report": "report 41 sentiment join",
    "regime_replay": "report 47 auto-discovery",
    "regime_diary": "the diary viewers",
    "session_labels": "possible analysis input — verify before touching",
    "gap_pct": "possible analysis input — verify before touching",
}

_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_LONGNUM = re.compile(r"\d{6,}")


def stem_of(name):
    """The type name: filename with dates and long numbers stripped.

    `fleet_trades_2026-08-14.json` and `.csv` collapse to `fleet_trades`, so a
    type's formats live together rather than in two folders.
    """
    base = os.path.splitext(name)[0]
    base = _DATE.sub("", base)
    base = _LONGNUM.sub("", base)
    base = re.sub(r"[_-]{2,}", "_", base).strip("_-")
    base = re.sub(r"_(r\d+)$", "", base)          # _r2 re-issues
    return base or "misc"


def classify():
    groups = defaultdict(list)
    for name in sorted(os.listdir(REPORTS)):
        path = os.path.join(REPORTS, name)
        if os.path.isdir(path) or name in SKIP_DIRS or name.startswith("."):
            continue
        groups[stem_of(name)].append(name)
    recurring = {k: v for k, v in groups.items() if len(v) >= MIN_RECURRING}
    oneoff = {k: v for k, v in groups.items() if len(v) < MIN_RECURRING}
    return recurring, oneoff


def main(argv):
    p = argparse.ArgumentParser(description="organise reports/ by type")
    p.add_argument("--apply", action="store_true",
                   help="actually copy (default is a dry run)")
    p.add_argument("--min", type=int, default=MIN_RECURRING,
                   help=f"files needed to count as recurring (default {MIN_RECURRING})")
    a = p.parse_args(argv)
    globals()["MIN_RECURRING"] = a.min

    if not os.path.isdir(REPORTS):
        print(f"no reports dir at {REPORTS}")
        return 2
    recurring, oneoff = classify()

    mode = "APPLY — copying" if a.apply else "DRY RUN — nothing will change"
    print(f"\n  {REPORTS}\n  {mode}\n")
    print(f"  {'type':<26}{'files':>6}   destination")
    total = 0
    for stem in sorted(recurring, key=lambda k: -len(recurring[k])):
        files = recurring[stem]
        total += len(files)
        print(f"  {stem:<26}{len(files):>6}   reports/{stem}/")
    print(f"\n  {len(recurring)} type folder(s), {total} file(s) copied")
    print(f"  {sum(len(v) for v in oneoff.values())} one-off file(s) STAY at root:")
    names = sorted(n for v in oneoff.values() for n in v)
    for i in range(0, len(names), 3):
        print("      " + "  ".join(f"{n:<28}" for n in names[i:i + 3]).rstrip())

    consumed = [s for s in recurring if s in CONSUMED_BY_OTHERS]
    if consumed:
        print("\n  ⚠️  READ BACK BY OTHER REPORTS — copying is safe, deleting the")
        print("      root originals is NOT (it silently shortens 41's window):")
        for s in sorted(consumed):
            print(f"        {s:<20} {CONSUMED_BY_OTHERS[s]}")

    if not a.apply:
        print("\n  dry run — rerun with --apply to copy\n")
        return 0

    copied = skipped = 0
    for stem, files in recurring.items():
        dest = os.path.join(REPORTS, stem)
        os.makedirs(dest, exist_ok=True)
        for name in files:
            src = os.path.join(REPORTS, name)
            dst = os.path.join(dest, name)
            # Never overwrite: a re-run must be a no-op, not a silent rewrite.
            if os.path.exists(dst) and os.path.getsize(dst) == os.path.getsize(src):
                skipped += 1
                continue
            shutil.copy2(src, dst)
            copied += 1
    print(f"\n  copied {copied}, already present {skipped}")
    print("  ⚠️  ORIGINALS ARE STILL AT ROOT and every report still reads them.")
    print("      Nothing has changed behaviourally. Removing the root copies is")
    print("      a separate step, after the readers are repointed.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
