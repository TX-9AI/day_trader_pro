#!/usr/bin/env python3
"""tests/check_report_width.py  v1.0
RPT.34 — THE TRADE REPORT FITS A PHONE: NO LINE WIDER THAN 74.

v1.0  2026-10-04  dtp r472. Operator: "can you fix the text wrapping in report
      47?" 133 of 258 lines of `trade_report.py` ran past its own 74-wide `=`
      rule, and Termius wrapped them mid-column.

Runs the REAL trade_report.py as the menu does (a subprocess, so the CLI's
stdout wrapper is in force) over a scratch bundle built to hit the widest
cases: a 30-character setup type and exit reason, a one-trade bucket averaging
-2,047.50, a 152-minute hold, a thin-basis R, and a five-figure loss.

  W1  it runs (rc 0) and prints the BY STRATEGY table
  W2  NO output line is wider than 74 characters
  W3  every table row ends in SEVEN separate numeric cells (N, WIN%, NET $,
      R, AVG $, HOLD, FEES) — wide values never fuse into one token
  W4  the numbers are the report's own: the -2,047.50 bucket prints NET
      -2048 and AVG -2047.5, the 152-minute hold prints 152.7

Run:  python3 tests/check_report_width.py
"""
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIDTH = 74
PROBLEMS = []
DAY = "2026-09-15"


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  — {detail}"))
    if not ok:
        PROBLEMS.append(name)


def row(tid, strat, setup, reason, pnl, exit_t="10:15:00", stop=0.8, n=1, prem=1.0):
    return {"trade_id": tid, "symbol": "NVDA", "box": "NVDA", "lineage": "OTV4",
            "strategy": strat, "setup_type": setup, "setup_grade": "UNGRADED",
            "status": "closed", "entry_time": f"{DAY} 09:45:00",
            "exit_time": f"{DAY} {exit_t}", "paper_trade": 1,
            "entry_premium": prem, "exit_premium": 1.2, "contracts": n,
            "stop_premium": stop, "pnl_usd": pnl, "exit_reason": reason,
            "option_side": "call"}


ROWS = (
    [row(f"a{i}", "RunawayContinuation", "runaway_continuation_relaxed",
         "orb_trail_stop pnl=12.0%", 140.0) for i in range(4)]
    + [row("b0", "ORBStrategy", "a_setup_type_thirty_chars_long",
           "an_exit_reason_thirty_chars_xx", -2047.50, n=50, prem=2.0)]
    + [row("c0", "GEXPinButterfly", "gex_pin_butterfly", "hard_close",
           300.0, exit_t="12:17:42")]
    + [row(f"d{i}", "TrendCreditSpread", "trend_credit_short", "tcs_stop_15%_of_credit",
           -14000.0, stop=None, n=40, prem=3.0) for i in range(8)]
)


def main():
    print("check_report_width")
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, f"fleet_trades_{DAY}.json"), "w") as fh:
            json.dump({"date": DAY, "trades": ROWS}, fh)
        r = subprocess.run([sys.executable, os.path.join(ROOT, "trade_report.py"),
                            "--no-json", "--bundles-dir", d],
                           capture_output=True, text=True, timeout=300, cwd=ROOT)
    out = r.stdout
    check("W1 runs and prints BY STRATEGY", r.returncode == 0 and "BY STRATEGY" in out,
          f"rc={r.returncode} stderr={r.stderr[-300:]!r}")

    long_lines = [ln for ln in out.splitlines() if len(ln) > WIDTH]
    check(f"W2 no line wider than {WIDTH}", not long_lines,
          f"{len(long_lines)} over, widest {max(map(len, long_lines)) if long_lines else 0}: "
          f"{long_lines[0][:90]!r}" if long_lines else "")

    num = re.compile(r"^[~+-]?\d+(\.\d+)?%?$|^-$|^n/a\*?$")
    bad, rows, in_table = [], [], False
    for ln in out.splitlines():
        if re.search(r"\bN\s+WIN%", ln):
            in_table = True
            continue
        if in_table and not ln.strip():
            in_table = False
            continue
        if in_table and ln.startswith("  "):
            rows.append(ln)
            cells = ln.split()[-7:]
            if len(ln.split()) < 8 or not all(num.match(c.rstrip("*")) for c in cells):
                bad.append(ln)
    check("W3 every table row ends in seven separate numeric cells",
          rows and not bad, f"{len(bad)} of {len(rows)} rows fused/short: {bad[:1]!r}")

    orb = next((ln for ln in out.splitlines()
                if ln.strip().startswith("OTV4/ORBS")), "")
    hold = next((ln for ln in out.splitlines()
                 if ln.strip().startswith("hard_close")), "")
    check("W4 the report's own numbers: NET -2048 and AVG -2047.5 for the one-trade "
          "bucket, HOLD 152.7",
          " -2048 " in orb and " -2047.5 " in orb and " 152.7 " in hold,
          f"orb={orb!r} hold={hold!r}")

    print()
    if PROBLEMS:
        print(f"RED — {len(PROBLEMS)} failed: {', '.join(p.split()[0] for p in PROBLEMS)}")
        return 1
    print("GREEN — every check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
