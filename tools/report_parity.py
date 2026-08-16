#!/usr/bin/env python3
# day_trader_pro/tools/report_parity.py — v1.2
# v1.2 (2026-08-16) — DIAGNOSE, don't just DETECT. v1.1 correctly isolated the
#      warehouse question but then reported "section differs: dedup" and left
#      the operator to go find out why. A difference you cannot act on is only
#      half an answer. Now prints the actual VALUES for the small diagnostic
#      sections (scope, dedup, overall) and, for report 40, the source LINE
#      containing the divergent figure from both files.
# v1.1 (2026-08-16) — 🔴 v1.0's FIRST REAL RUN REPORTED A DIVERGENCE IT HAD
#      MANUFACTURED ITSELF. Three defects, all mine:
#      (1) REPORT 41 IS CROSS-DAY. The local run globs every bundle in reports/
#          (~25 sessions); the warehouse run globbed reports/warehouse/, which
#          held ONE date because only one had been rebuilt. It compared 25 days
#          against 1 and called the difference a warehouse problem. Now the
#          local side is restricted to EXACTLY the dates present on the
#          warehouse side, so the comparison is apples to apples.
#      (2) REPORT 40 CHANGED TWO VARIABLES AT ONCE. Without --bundles-dir it
#          reads the per-box DBs; with it, a bundle. So "local vs warehouse"
#          was really "DBs vs bundle" AND "local vs warehouse" together, and a
#          difference could not be attributed. Now three-way: DB-direct,
#          local-bundle, warehouse-bundle — which separates a pre-existing
#          local property from the actual warehouse question.
#      (3) The noise filter popped "generated", but the key is "generated_utc",
#          so a wall-clock timestamp counted as a real difference.
#      A test that manufactures its own failure is worse than no test: it burns
#      the operator's attention and makes a real divergence indistinguishable.
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


def _first_diff(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return f"figure {i}: {x} vs {y}"
    if len(a) != len(b):
        return f"length {len(a)} vs {len(b)}"
    return None


def _locate(path, index):
    """The source line holding the Nth non-noise figure — 'figure 36' alone is
    not actionable, and chasing it by hand is exactly the friction that stops
    a divergence from being investigated."""
    if not os.path.exists(path):
        return "(missing)"
    seen = 0
    for line in open(path, encoding="utf-8", errors="replace"):
        if _NOISE.search(line):
            continue
        hits = _NUM.findall(line)
        if seen <= index < seen + len(hits):
            return line.rstrip()[:160]
        seen += len(hits)
    return "(past end)"


def compare_excursions(day, keep):
    """Report 40 THREE ways, so a difference can be attributed.

    Without --bundles-dir this report reads the per-box DBs; with it, a bundle.
    Running it once each way changes TWO variables at the same time and the
    result cannot be interpreted. The three runs separate them:

      DB-direct  vs local-bundle      -> a property of the LOCAL pipeline
      local-bundle vs warehouse-bundle -> the warehouse question, the only one
                                          that gates severing
    """
    p_db = os.path.join(config.REPORTS_DIR, f"excursions_{day}.txt")
    _lb_tag = os.path.basename(os.path.normpath(config.REPORTS_DIR))
    _wb_tag = os.path.basename(os.path.normpath(WAREHOUSE_DIR))
    p_lb = os.path.join(config.REPORTS_DIR, f"excursions_{day}_bundle_{_lb_tag}.txt")
    p_wb = os.path.join(config.REPORTS_DIR, f"excursions_{day}_bundle_{_wb_tag}.txt")

    import shutil
    ok = run([PY, "excursion_report.py", "--date", day], "40 DB-direct")
    if ok and os.path.exists(p_db):
        shutil.copy(p_db, p_db + ".dbrun")
    ok_lb = run([PY, "excursion_report.py", "--date", day,
                 "--bundles-dir", config.REPORTS_DIR], "40 local-bundle")
    ok_wb = run([PY, "excursion_report.py", "--date", day,
                 "--bundles-dir", WAREHOUSE_DIR], "40 warehouse-bundle")
    if not (ok and ok_lb and ok_wb):
        return None

    n_db = numbers_of(p_db + ".dbrun")
    n_lb = numbers_of(p_lb)
    n_wb = numbers_of(p_wb)
    if n_lb is None or n_wb is None:
        print(f"  40 {day}: a run produced no file")
        return False

    d_local = _first_diff(n_db, n_lb) if n_db is not None else "n/a"
    d_ware = _first_diff(n_lb, n_wb)
    print(f"  40 {day}: DB-vs-localbundle {'same' if d_local is None else d_local}"
          f"   |   localbundle-vs-WAREHOUSE "
          f"{'MATCH' if d_ware is None else 'DIFF ' + d_ware}")
    if d_ware and d_ware.startswith("figure "):
        idx = int(d_ware.split()[1].rstrip(":"))
        print(f"      local bundle : {_locate(p_lb, idx)}")
        print(f"      warehouse    : {_locate(p_wb, idx)}")
    if d_local is not None and d_local != "n/a" and d_ware is None:
        print("      → the warehouse reproduces the local BUNDLE exactly; the "
              "difference is DB-vs-bundle and predates the warehouse")
    if not keep:
        for f_ in (p_lb, p_wb, p_db + ".dbrun"):
            if os.path.exists(f_):
                os.remove(f_)
    return d_ware is None


def _fair_local_dir(warehouse_dir):
    """A local-bundle directory holding EXACTLY the dates the warehouse has.

    Report 41 pools every bundle it can glob, so its answer is a function of
    the date SET, not just the contents. Comparing a 25-session local run with
    a 1-session warehouse run is not a comparison; it is two different
    questions.
    """
    import shutil
    import tempfile
    dates = []
    for f in os.listdir(warehouse_dir):
        m = re.match(r"fleet_trades_(\d{4}-\d\d-\d\d)\.json$", f)
        if m:
            dates.append(m.group(1))
    tmp = tempfile.mkdtemp(prefix="parity_local_")
    missing = []
    for d in sorted(dates):
        src = os.path.join(config.REPORTS_DIR, f"fleet_trades_{d}.json")
        if os.path.exists(src):
            shutil.copy(src, os.path.join(tmp, f"fleet_trades_{d}.json"))
        else:
            missing.append(d)
    return tmp, sorted(dates), missing


def compare_breakdown(keep):
    """Report 41 from both sources, over the SAME date set."""
    fair_dir, dates, missing = _fair_local_dir(WAREHOUSE_DIR)
    if not dates:
        print("  41: reports/warehouse/ is empty — rebuild some dates first")
        return None
    print(f"  41: comparing over {len(dates)} shared date(s): "
          f"{dates[0]} .. {dates[-1]}")
    if missing:
        print(f"      ⚠️ no LOCAL bundle for {', '.join(missing)} — "
              f"those dates are in the warehouse only")
    ok_l = run([PY, "trade_report.py", "--bundles-dir", fair_dir], "41 local")
    ok_w = run([PY, "trade_report.py", "--bundles-dir", WAREHOUSE_DIR],
               "41 warehouse")
    if not (ok_l and ok_w):
        return None

    del fair_dir

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
        for k in ("source", "generated", "generated_utc"):
            d.pop(k, None)
        # scope.sessions is the DATE SET, which is the thing we equalised above;
        # if it still differs the equalisation failed and that is worth seeing,
        # so it is compared rather than dropped.
    same = a == b
    print(f"  41: {'MATCH' if same else 'DIFF '}  "
          f"local={os.path.basename(pl)} warehouse={os.path.basename(pw)}")
    if not same:
        # scope/dedup are small and are where a set-vs-content problem shows
        # itself, so print them rather than naming them.
        for k in ("scope", "dedup"):
            if a.get(k) != b.get(k):
                print(f"      {k}:")
                print(f"        local     {json.dumps(a.get(k), default=str)[:300]}")
                print(f"        warehouse {json.dumps(b.get(k), default=str)[:300]}")
        ov_a, ov_b = a.get("overall") or {}, b.get("overall") or {}
        if ov_a != ov_b and isinstance(ov_a, dict) and isinstance(ov_b, dict):
            print("      overall — differing keys:")
            for k in sorted(set(ov_a) | set(ov_b)):
                if ov_a.get(k) != ov_b.get(k):
                    print(f"        {k}: local {ov_a.get(k)!r} vs "
                          f"warehouse {ov_b.get(k)!r}")
        rest = [k for k in sorted(set(a) | set(b))
                if a.get(k) != b.get(k) and k not in ("scope", "dedup", "overall")]
        if rest:
            print(f"      also differing (derived from the above): "
                  f"{', '.join(rest)}")
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
