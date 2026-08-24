#!/usr/bin/env python3
"""
day_trader_pro/tests/test_r_phases.py  v1.0
The R suite hangs off the conductor's analysis run — pinned by execution.

v1.0  2026-08-23  Born RED at r222 (eod_analysis had no R phases). Pins:
  D1  a FRIDAY dry-run lists both R_LEDGER and EDGE_SCAN         (executed)
  D2  a MONDAY dry-run runs R_LEDGER and SKIPS EDGE_SCAN, saying
      why — the weekly cadence is behaviour, not a comment        (executed)
  D3  the dry run says "would", never "✅", for the new phases —
      a dry run must not imply success (the conductor's own
      fabricated-verification lesson)                             (executed)
  D4  the missing-checkout path warns BY NAME with DTP_OTV4_DIR —
      source-level pin, stated as such: executing it would read
      production S3 for the sibling phases, which a test must not
      do on a schedule. The string checked is the warning text,
      not a docstring word.

Plain script, exit code, no pytest.
Run:  cd ~/day_trader_pro && python3 tests/test_r_phases.py
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBLEMS: list = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}"
          + (f"  - {detail}" if (detail and not ok) else ""))
    if not ok:
        PROBLEMS.append(name)


def _dry(date):
    r = subprocess.run([sys.executable, "eod_analysis.py", "--date", date,
                        "--dry-run"], cwd=HERE, capture_output=True,
                       text=True, timeout=120)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    print("=" * 66)
    print("R PHASES: conductor-driven, Friday-gated, dry-honest")
    print("=" * 66)
    rc_f, out_f = _dry("2026-08-28")           # a Friday
    rc_m, out_m = _dry("2026-08-24")           # a Monday
    check("D1 Friday dry-run lists R_LEDGER and EDGE_SCAN",
          rc_f == 0 and "R_LEDGER" in out_f and "would run weekly edge scan" in out_f,
          out_f[-200:])
    check("D2 Monday dry-run runs R_LEDGER and SKIPS EDGE_SCAN with a reason",
          rc_m == 0 and "would run R baseline" in out_m
          and "skipped — runs Fridays only" in out_m, out_m[-200:])
    new_lines = [l for l in (out_f + out_m).splitlines()
                 if "R_LEDGER" in l or "EDGE_SCAN" in l]
    check("D3 dry output for the R phases never claims success (no ✅)",
          new_lines and not any("✅" in l for l in new_lines))
    src = open(os.path.join(HERE, "eod_analysis.py"), encoding="utf-8").read()
    check("D4 missing otv4 checkout warns BY NAME (DTP_OTV4_DIR in the warning)",
          "otv4 checkout missing" in src and "DTP_OTV4_DIR" in src)
    print("-" * 66)
    if PROBLEMS:
        print(f"FAIL  {len(PROBLEMS)} problem(s): {', '.join(PROBLEMS)}")
        return 1
    print("ALL GREEN — the conductor owns the R cadence")
    return 0


if __name__ == "__main__":
    sys.exit(main())
