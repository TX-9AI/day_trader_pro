#!/usr/bin/env python3
# day_trader_pro/tests/test_eod_excursion_source.py — v1.0
# v1.0 (2026-08-29) — r186 / dtp r227. Proves S3.3.
#
# 🔴 THE CLAIM UNDER TEST IS NOT "the flag was added". It is that the NIGHTLY
#   EXCURSION PHASE HAD NO SOURCE AT ALL. `install_eod_v2.sh` disables
#   `dtp-harvest.timer`, so `trades/<date>/` stops being populated; and
#   `eod_analysis._consolidate` writes its bundle to `reports/warehouse/`, not
#   to the repo-root `reports/`. Case A builds exactly that world — the
#   warehouse bundle present, both of the old sources absent — and asserts the
#   report the chain actually ran EXITS NON-ZERO on it.
#
# ⚠️ SO CASE A IS THE BORN-RED, AND IT STAYS RED FOREVER. It is not asserting a
#   bug we fixed; it is pinning the reason the flag has to be there. If someone
#   removes `--bundles-dir` from the phase, case B goes red and case A explains
#   why. A test that only checked the new path would pass just as happily
#   against a chain reading nothing.
#
# ⚠️ A PLAIN SCRIPT WITH AN EXIT CODE, NOT PYTEST — day_trader_pro's venv has
#   no pytest, and a check that goes red on ENVIRONMENT rather than CONTENT
#   teaches the operator to ignore reds.
#
# Run:  python3 tests/test_eod_excursion_source.py

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

DAY = "2026-08-25"


def trade(tid, sym, strat, entry, exitp, mfe, mae, reason):
    """A closed row with the telemetry columns excursion_report needs.

    ⚠️ THE COLUMN IS `pnl_usd`, NOT `pnl`, and `usable()` silently drops any row
    missing it — the first draft of this fixture used `pnl` and the report came
    back "0 trade(s) with telemetry" while exiting 0. A fixture too thin for the
    thing it measures is its own failure class in this repo.
    """
    return {
        "trade_id": tid, "symbol": sym, "box": sym, "strategy": strat,
        "status": "closed", "entry_time": f"{DAY} 09:45:00",
        "exit_time": f"{DAY} 10:15:00", "mode": "paper",
        "entry_premium": entry, "exit_premium": exitp,
        "max_premium_seen": mfe, "min_premium_seen": mae,
        "contracts": 1, "pnl_usd": (exitp - entry) * 100.0,
        "paper_trade": 1,
        "exit_reason": reason, "setup_type": strat, "option_type": "call",
    }


ROWS = [
    trade("t1", "NVDA", "ORBStrategy", 1.00, 1.80, 2.10, 0.85, "orb_trail_stop"),
    trade("t2", "QQQ", "ORBStrategy", 0.80, 0.60, 1.05, 0.55, "orb_structure_stop"),
    trade("t3", "AMD", "RunawayContinuation", 0.40, 0.10, 0.52, 0.09, "max_loss_floor"),
]


def build_sandbox(d):
    """A control checkout with ONLY the warehouse bundle populated."""
    for f in ("excursion_report.py", "config.py", "consolidate_trades.py",
              "warehouse_reader.py"):
        shutil.copy(os.path.join(ROOT, f), os.path.join(d, f))
    os.makedirs(os.path.join(d, "reports", "warehouse"))
    os.makedirs(os.path.join(d, "trades"))          # exists, but EMPTY
    bundle = {"date": DAY, "generated_utc": f"{DAY}T20:05:00Z", "trades": ROWS}
    with open(os.path.join(d, "reports", "warehouse",
                           f"fleet_trades_{DAY}.json"), "w") as fh:
        json.dump(bundle, fh)
    return d


def run(d, *extra):
    return subprocess.run(
        [sys.executable, "excursion_report.py", "--date", DAY] + list(extra),
        cwd=d, capture_output=True, text=True, timeout=300)


def main():
    problems = []
    with tempfile.TemporaryDirectory() as d:
        build_sandbox(d)

        # ── A. the world the nightly chain was actually in ─────────────────
        a = run(d)
        if a.returncode == 0:
            problems.append(
                "A: excursion_report SUCCEEDED with no per-box DBs and no root "
                "bundle. The premise of this fix is that it cannot — if that "
                "changed, S3.3's reasoning needs re-reading, not this test "
                "silencing.")
        elif "nothing collected for that day" not in (a.stderr or ""):
            problems.append("A: exited %d but not for the expected reason: %s"
                            % (a.returncode, (a.stderr or "").strip()[:120]))

        # ── B. the same tree, pointed at the bundle CONSOLIDATE writes ─────
        wh = os.path.join(d, "reports", "warehouse")
        b = run(d, "--bundles-dir", wh)
        if b.returncode != 0:
            problems.append("B: --bundles-dir run failed rc=%d %s"
                            % (b.returncode, (b.stderr or "").strip()[:160]))
        out = os.path.join(d, "reports", f"excursions_{DAY}_bundle_warehouse.txt")
        if not os.path.exists(out):
            problems.append("B: expected %s — the filename the phase now "
                            "advertises" % os.path.basename(out))
        else:
            text = open(out, encoding="utf-8").read()
            # It must actually REPORT ON THE TRADES, not merely write a file.
            # An empty report written successfully is the failure this whole
            # workstream exists to stop.
            if "3 trade(s) with telemetry" not in text:
                problems.append("B: the report does not cover all 3 rows: %s"
                                % text.splitlines()[0][:120])
            if "WAREHOUSE" not in text:
                problems.append("B: the report does not name its SOURCE as the "
                                "warehouse — provenance is not optional")
            for reason in ("orb_trail_stop", "max_loss_floor"):
                if reason not in text:
                    problems.append("B: exit reason %s missing from the report"
                                    % reason)

        # ── C. the absolute path is what the phase uses ────────────────────
        # A relative --bundles-dir resolves against the CWD, which is why the
        # phase passes warehouse_reader.WAREHOUSE_OUT rather than a literal.
        import warehouse_reader as wr
        if not os.path.isabs(wr.WAREHOUSE_OUT):
            problems.append("C: WAREHOUSE_OUT is not absolute (%s) — the phase "
                            "depends on it being so" % wr.WAREHOUSE_OUT)
        if os.path.basename(os.path.normpath(wr.WAREHOUSE_OUT)) != "warehouse":
            problems.append("C: WAREHOUSE_OUT's basename is the filename tag "
                            "the phase logs; it is %r, not 'warehouse'"
                            % os.path.basename(os.path.normpath(wr.WAREHOUSE_OUT)))

        # ── D. a missing bundle must be a CONSOLIDATE message ──────────────
        os.remove(os.path.join(wh, f"fleet_trades_{DAY}.json"))
        dd = run(d, "--bundles-dir", wh)
        if dd.returncode == 0:
            problems.append("D: an absent bundle did not fail — the phase's "
                            "existence check would then be the only guard")

    if problems:
        print("PROBLEMS (%d):" % len(problems))
        for p in problems:
            print("  ✗ " + p)
        print("\nFAIL")
        return 1
    print("  A no DBs, no root bundle -> rc=1  (the nightly chain's real world)")
    print("  B --bundles-dir warehouse -> rc=0, 3 trades, SOURCE named")
    print("  C WAREHOUSE_OUT is absolute and tagged 'warehouse'")
    print("  D an absent bundle still fails, so the phase's check is a second net")
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
