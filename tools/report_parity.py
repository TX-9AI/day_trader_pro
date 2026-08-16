#!/usr/bin/env python3
# day_trader_pro/tools/report_parity.py — v1.0
# v1.0 (2026-08-16) — WH.11's actual gate. Runs reports 40 and 41 from BOTH
#      sources and diffs their OUTPUTS. Bundle equivalence was necessary and
#      never sufficient: two identical inputs can still produce different
#      reports if a report reaches past the bundle for anything.
"""
Report parity — local pipeline vs warehouse, compared on OUTPUT.

WHY OUTPUT AND NOT INPUT
    `warehouse_reader --all` already shows 19 of 25 dates reproducing the
    control bundle exactly. That establishes the BUNDLES agree. It does not
    establish that the REPORTS agree, because:
      * report 40 normally reads the per-box DBs and only falls back to a
        bundle, so it had never been exercised against the warehouse at all;
      * report 41 pools EVERY bundle it can glob, so its answer depends on the
        set of files present, not just their contents.
    Severing the dual write on bundle equivalence alone would be trusting a
    proxy for the thing we actually care about.

WHAT IT COMPARES, AND WHAT IT IGNORES
    Numbers, not bytes. Generation timestamps, source labels and file paths
    differ BY DESIGN between the two runs, so a byte diff would be red every
    time — the CV.1 failure, where a canary that always fails teaches you to
    ignore it. This extracts the figures and compares those.

USAGE
  python3 tools/report_parity.py --date 2026-08-14
  python3 tools/report_parity.py --since 2026-08-04 --to 2026-08-14
  python3 tools/report_parity.py --date 2026-08-14 --keep   # leave outputs in place
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import config  # noqa: E402

PY = sys.executable
WAREHOUSE_DIR = os.path.join(config.REPORTS_DIR, "warehouse")

# Lines whose difference is expected and meaningless.
_NOISE = re.compile(
    r"(generated|written|source|SOURCE|reports/|\.json|\.txt|\.db|"
    r"\d{4}-\d\d-\d\dT\d\d:\d\d)", re.I)
# Any number, including negatives and decimals.
_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def run(cmd, label):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ! {label} exited {r.returncode}")
        tail = (r.stderr or r.stdout).strip().splitlines()[-3:]
        for t in tail:
            print(f"      {t}")
    return r.returncode == 0


def numbers_of(path):
    """Every number in a text report, with the noise lines dropped."""
    if not os.path.exists(path):
        return None
    out = []
    for line in open(path, encoding="utf-8", errors="replace"):
        if _NOISE.search(line):
            continue
        out.extend(_NUM.findall(line))
    return out


def compare_excursions(day, keep):
    """Report 40 from both sources, compared on the numbers it prints."""
    local = os.path.join(config.REPORTS_DIR, f"excursions_{day}.txt")
    ware = os.path.join(config.REPORTS_DIR, f"excursions_{day}_warehouse.txt")

    ok_l = run([PY, "excursion_report.py", "--date", day], "40 local")
    ok_w = run([PY, "excursion_report.py", "--date", day,
                "--bundles-dir", WAREHOUSE_DIR], "40 warehouse")
    if not (ok_l and ok_w):
        return None

    a, b = numbers_of(local), numbers_of(ware)
    if a is None or b is None:
        print(f"  40 {day}: one side produced no file "
              f"(local={a is not None}, warehouse={b is not None})")
        return False
    same = a == b
    print(f"  40 {day}: {'MATCH' if same else 'DIFF '} "
          f"({len(a)} vs {len(b)} figures)")
    if not same:
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y:
                print(f"      first divergence at figure {i}: "
                      f"local {x} vs warehouse {y}")
                break
        if len(a) != len(b):
            print(f"      and the reports differ in LENGTH — "
                  f"{len(a)} vs {len(b)} figures, so the shapes differ too")
    if not keep and os.path.exists(ware):
        os.remove(ware)
    return same


def compare_breakdown(keep):
    """Report 41 from both sources. Cross-day, so it runs once, not per date."""
    ok_l = run([PY, "trade_report.py"], "41 local")
    ok_w = run([PY, "trade_report.py", "--bundles-dir", WAREHOUSE_DIR],
               "41 warehouse")
    if not (ok_l and ok_w):
        return None

    def newest(tag):
        pat = re.compile(r"^trade_report_%s\d{4}-\d\d-\d\d\.json$" % tag)
        hits = [f for f in os.listdir(config.REPORTS_DIR) if pat.match(f)]
        if not hits:
            return None
        hits.sort(key=lambda f: os.path.getmtime(
            os.path.join(config.REPORTS_DIR, f)))
        return os.path.join(config.REPORTS_DIR, hits[-1])

    pl, pw = newest(""), newest("warehouse_")
    if not pl or not pw:
        print(f"  41: missing an output (local={bool(pl)}, warehouse={bool(pw)})")
        return False
    a = json.load(open(pl))
    b = json.load(open(pw))
    for d in (a, b):
        d.pop("source", None)
        d.pop("generated", None)
    same = a == b
    print(f"  41: {'MATCH' if same else 'DIFF '}  "
          f"local={os.path.basename(pl)} warehouse={os.path.basename(pw)}")
    if not same:
        for k in sorted(set(a) | set(b)):
            if a.get(k) != b.get(k):
                print(f"      section differs: {k}")
    if not keep and os.path.exists(pw):
        os.remove(pw)
    return same


def main(argv):
    p = argparse.ArgumentParser(description="report parity: local vs warehouse")
    p.add_argument("--date")
    p.add_argument("--since")
    p.add_argument("--to")
    p.add_argument("--keep", action="store_true",
                   help="leave the warehouse-sourced outputs on disk")
    p.add_argument("--skip-rebuild", action="store_true",
                   help="assume reports/warehouse/ is already populated")
    a = p.parse_args(argv)

    if a.date:
        days = [a.date]
    elif a.since:
        d0 = date.fromisoformat(a.since)
        d1 = date.fromisoformat(a.to) if a.to else date.today()
        days = []
        while d0 <= d1:
            if d0.weekday() < 5:
                days.append(d0.isoformat())
            d0 += timedelta(days=1)
    else:
        p.error("need --date or --since")

    os.makedirs(WAREHOUSE_DIR, exist_ok=True)
    if not a.skip_rebuild:
        print(f"\n  rebuilding {len(days)} bundle(s) from S3 -> {WAREHOUSE_DIR}")
        for d in days:
            run([PY, "warehouse_reader.py", "--date", d], f"reader {d}")

    print("\n  report 40 — excursions (MFE/MAE)")
    r40 = [compare_excursions(d, a.keep) for d in days]

    print("\n  report 41 — trade breakdown (cross-day)")
    r41 = compare_breakdown(a.keep)

    ok40 = [x for x in r40 if x is not None]
    bad = [d for d, x in zip(days, r40) if x is False]
    print()
    print(f"  40: {sum(1 for x in ok40 if x)}/{len(ok40)} date(s) match"
          + (f" — DIFF on {', '.join(bad)}" if bad else ""))
    print(f"  41: {'MATCH' if r41 else 'DIFF' if r41 is False else 'not run'}")
    clean = bool(ok40) and all(ok40) and r41 is True
    print()
    if clean:
        print("  ✅ REPORT PARITY — both reports agree across both sources.")
        print("     This is WH.11's gate. OT_EOD_PULL=0 is now defensible.")
    else:
        print("  ❌ NOT AT PARITY — do NOT sever. Investigate the diffs above.")
        print("     A divergence here is information, not a setback: it means")
        print("     a report reaches past the bundle for something.")
    return 0 if clean else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
