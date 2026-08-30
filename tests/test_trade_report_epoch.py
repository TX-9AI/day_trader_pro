#!/usr/bin/env python3
# day_trader_pro/tests/test_trade_report_epoch.py — v1.0
# v1.0 (2026-08-29) — r187 / dtp r228. Proves S3.5.
#
# 🔑 CASE B IS THE ONE THAT MATTERS AND IT IS NOT ABOUT A FLAG. The fixture
#   holds six trades from 2026-08-14 (old engines) and five from 2026-08-26,
#   with OPPOSITE P&L signs. Under the old default they pooled into one table
#   and the headline net was a number describing no system that has ever
#   existed. The case asserts the default answer now covers the v4 rows ONLY,
#   and — just as important — that the exclusion is PRINTED. A filter you
#   cannot see is how you end up arguing about a number that was never in the
#   sample, which has already happened once on this project.
#
# ⚠️ CASE A PINS THE SOURCE, NOT THE FLAG. The old default globbed the repo
#   root, a directory nothing writes any more (C.12). The case puts DIFFERENT
#   trades in each location and asserts the default reads the warehouse — a
#   test that only checked "--bundles-dir works" would pass just as happily
#   against a default still pointing at the dead folder.
#
# ⚠️ A PLAIN SCRIPT WITH AN EXIT CODE, NOT PYTEST.
#
# Run:  python3 tests/test_trade_report_epoch.py

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

OLD_DAY = "2026-08-14"      # pre-epoch: the retired engines
NEW_DAY = "2026-08-26"      # post-epoch: v4
EPOCH = "2026-08-25"


def t(tid, day, strat, setup, reason, pnl):
    return {"trade_id": tid, "symbol": "NVDA", "box": "NVDA",
            "strategy": strat, "setup_type": setup, "setup_grade": "UNGRADED",
            "status": "closed", "entry_time": f"{day} 09:45:00",
            "exit_time": f"{day} 10:15:00", "paper_trade": 1,
            "entry_premium": 1.0, "exit_premium": 1.2, "contracts": 1,
            "pnl_usd": pnl, "exit_reason": reason,
            "max_premium_seen": 1.4, "min_premium_seen": 0.9}


# Opposite signs, so a contaminated pool is arithmetically obvious.
OLD = [t(f"o{i}", OLD_DAY, "ContinuationStrategy", "cont", "bos_exit", -90.0)
       for i in range(6)]
NEW = [t(f"n{i}", NEW_DAY, "ORBStrategy", "ORB Long", "orb_trail_stop", 140.0)
       for i in range(5)]
# A decoy in the DEAD root folder. If the default still globs there, this
# strategy name shows up in the output and case A goes red.
DECOY = [t(f"d{i}", NEW_DAY, "DECOY_ROOT_BUNDLE", "decoy", "stop_hit", 1.0)
         for i in range(4)]


def sandbox(d):
    for f in ("trade_report.py", "config.py"):
        shutil.copy(os.path.join(ROOT, f), os.path.join(d, f))
    os.makedirs(os.path.join(d, "reports", "warehouse"))
    for day, rows in ((OLD_DAY, OLD), (NEW_DAY, NEW)):
        with open(os.path.join(d, "reports", "warehouse",
                               f"fleet_trades_{day}.json"), "w") as fh:
            json.dump({"date": day, "trades": rows}, fh)
    with open(os.path.join(d, "reports", f"fleet_trades_{NEW_DAY}.json"), "w") as fh:
        json.dump({"date": NEW_DAY, "trades": DECOY}, fh)
    return d


def run(d, *a):
    return subprocess.run([sys.executable, "trade_report.py", "--no-json"] + list(a),
                          cwd=d, capture_output=True, text=True, timeout=300)


def main():
    p = []
    with tempfile.TemporaryDirectory() as d:
        sandbox(d)

        # ── A. the default source is the warehouse, not the dead root ──────
        a = run(d)
        if "DECOY_ROOT_BUNDLE" in a.stdout:
            p.append("A: the default read the repo-root bundles — nothing "
                     "writes that folder any more (C.12)")
        if "reports/warehouse" not in a.stdout:
            p.append("A: the SOURCE line does not name the directory read: %s"
                     % a.stdout.splitlines()[:1])

        # ── B. the epoch floor is applied AND printed ──────────────────────
        if "5 unique trade(s)" not in a.stdout:
            p.append("B: expected the 5 post-epoch trades only; got %s"
                     % [l for l in a.stdout.splitlines() if "unique" in l])
        if OLD_DAY in a.stdout:
            p.append("B: a pre-epoch session appears in the default run")
        if "6 closed trade(s) EXCLUDED as pre-epoch" not in a.stdout:
            p.append("B: the exclusion was applied but NOT PRINTED — a filter "
                     "you cannot see is the whole failure mode")
        if EPOCH not in a.stdout:
            p.append("B: the WINDOW line does not name the epoch")

        # ── C. --all-history restores the pool, and says so ────────────────
        c = run(d, "--all-history")
        if "11 unique trade(s)" not in c.stdout:
            p.append("C: --all-history did not restore all 11 trades")
        if "NO EPOCH FLOOR" not in c.stdout:
            p.append("C: --all-history does not announce that the floor is off")

        # ── D. a --since EARLIER than the epoch is flagged, not silent ─────
        dd = run(d, "--since", "2026-08-01")
        if "EARLIER THAN THE ENGINE EPOCH" not in dd.stdout:
            p.append("D: --since 2026-08-01 pooled v3 and v4 without a flag")
        if "11 unique trade(s)" not in dd.stdout:
            p.append("D: an explicit early --since must still be HONOURED, "
                     "not overridden — the operator can ask for archaeology")

        # ── E. BY SETUP GRADE is gone, and its absence is explained ────────
        for out in (a.stdout, c.stdout):
            if "BY SETUP GRADE\n" in out:
                p.append("E: the dead setup_grade dimension is still rendered")
            if "no BY SETUP GRADE section" not in out:
                p.append("E: the section vanished with no explanation — an "
                         "unexplained absence reads as an oversight and gets "
                         "re-added")

        # ── F. an explicit --bundles-dir still overrides ───────────────────
        f = run(d, "--bundles-dir", os.path.join(d, "reports"), "--all-history")
        if "DECOY_ROOT_BUNDLE" not in f.stdout:
            p.append("F: --bundles-dir no longer reaches the legacy root path")

    if p:
        print("PROBLEMS (%d):" % len(p))
        for x in p:
            print("  ✗ " + x)
        print("\nFAIL")
        return 1
    print("  A default source is reports/warehouse (root decoy not read)")
    print("  B epoch floor applied AND the 6 exclusions printed")
    print("  C --all-history restores 11 and announces the floor is off")
    print("  D --since before the epoch is honoured but flagged red")
    print("  E BY SETUP GRADE removed, its absence stated")
    print("  F --bundles-dir still overrides to the legacy path")
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
