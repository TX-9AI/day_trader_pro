#!/usr/bin/env python3
# day_trader_pro/tests/test_trade_report_dedup.py — v1.0
# v1.0 (2026-08-29) — r190 / dtp r231. Proves S3.6.
#
# 🔴 THE CLAIM IS NOT "the shim was deleted". Deleting it would have been
#   trivial and untestable. The claim is that the silent correction became a
#   LOUD DETECTOR, because the two conditions that can still produce a
#   duplicate — a legacy cumulative bundle in the glob, or two bundles covering
#   one date — are real problems that v1.9 and earlier absorbed without a word.
#
# 🔑 CASE C IS THE ONE THAT WOULD CATCH A REGRESSION NOBODY MEANT. The two
#   copies of the duplicated trade carry DIFFERENT P&L, so a silent re-dedup
#   that picked the other row, or a double-count that summed both, changes the
#   headline net and this case names which happened.
#
# ⚠️ A PLAIN SCRIPT WITH AN EXIT CODE, NOT PYTEST.
#
# Run:  python3 tests/test_trade_report_dedup.py

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

D1 = "2026-08-26"
D2 = "2026-08-27"


def t(tid, day, pnl):
    return {"trade_id": tid, "symbol": "NVDA", "box": "NVDA",
            "strategy": "ORBStrategy", "setup_type": "ORB Long",
            "status": "closed", "entry_time": f"{day} 09:45:00",
            "exit_time": f"{day} 10:15:00", "paper_trade": 1,
            "entry_premium": 1.0, "exit_premium": 1.2, "contracts": 1,
            "pnl_usd": pnl, "exit_reason": "orb_trail_stop",
            "max_premium_seen": 1.4, "min_premium_seen": 0.9}


def sandbox(d, cumulative):
    for f in ("trade_report.py", "config.py"):
        shutil.copy(os.path.join(ROOT, f), os.path.join(d, f))
    wh = os.path.join(d, "reports", "warehouse")
    os.makedirs(wh)
    b1 = [t("a1", D1, 100.0), t("dup", D1, 100.0)]
    # The later bundle repeats `dup` with a DIFFERENT pnl — a cumulative
    # archive is exactly this shape.
    b2 = [t("b1", D2, 50.0)] + ([t("dup", D1, 999.0)] if cumulative else [])
    for day, rows in ((D1, b1), (D2, b2)):
        with open(os.path.join(wh, f"fleet_trades_{day}.json"), "w") as fh:
            json.dump({"date": day, "trades": rows}, fh)
    return d


def run(d):
    return subprocess.run([sys.executable, "trade_report.py", "--no-json",
                           "--all-history"],
                          cwd=d, capture_output=True, text=True, timeout=300)


def net_of(out):
    m = re.search(r"net ([+-][\d,.]+)", out)
    return float(m.group(1).replace(",", "")) if m else None


def main():
    p = []

    # ── A. the clean case stays quiet ──────────────────────────────────────
    with tempfile.TemporaryDirectory() as d:
        sandbox(d, cumulative=False)
        a = run(d)
        if "DUPLICATE" in a.stdout:
            p.append("A: a clean set of one-day bundles reported duplicates — "
                     "a detector that cries wolf is worse than none")
        if "de-duplicated by trade_id" in a.stdout:
            p.append("A: the line still advertises de-duplication as a feature")
        if "3 unique trade(s)" not in a.stdout:
            p.append("A: expected 3 trades from the clean set; got %s"
                     % [l for l in a.stdout.splitlines() if "unique" in l])
        clean_net = net_of(a.stdout)

    # ── B/C. a cumulative bundle is DETECTED, NAMED, and counted once ──────
    with tempfile.TemporaryDirectory() as d:
        sandbox(d, cumulative=True)
        b = run(d)
        if "DUPLICATE" not in b.stdout:
            p.append("B: a repeated trade_id across bundles was absorbed "
                     "silently — that is the v1.9 behaviour this replaces")
        if "dup" not in b.stdout:
            p.append("B: the duplicate was reported but not NAMED by trade_id")
        if f"fleet_trades_{D1}.json" not in b.stdout or \
           f"fleet_trades_{D2}.json" not in b.stdout:
            p.append("B: the report does not name BOTH files — 'there is a "
                     "duplicate somewhere' is not actionable")
        if "4 unique trade(s)" in b.stdout:
            p.append("C: the duplicate was COUNTED TWICE")
        if "3 unique trade(s)" not in b.stdout:
            p.append("C: expected 3 unique trades after collapse; got %s"
                     % [l for l in b.stdout.splitlines() if "unique" in l])
        # 🔑 FIRST WINS, by sorted filename. The kept row is the $100 one from
        # the D1 bundle, not the $999 one from D2. If the net moves, some other
        # rule silently picked a different row.
        dup_net = net_of(b.stdout)
        if clean_net is not None and dup_net is not None and \
                abs(dup_net - clean_net) > 1e-6:
            p.append("C: the kept row changed — net %s with the cumulative "
                     "bundle vs %s without. First-wins is not holding."
                     % (dup_net, clean_net))

    # ── D. the old tie-break helper is GONE, not merely unused ─────────────
    # Shape of a DEFINITION, never a mention (WA §20): the changelog above
    # names `_filled()` while explaining its removal, and a bare string match
    # would go red on that prose.
    src = open(os.path.join(ROOT, "trade_report.py"), encoding="utf-8").read()
    if re.search(r"^def _filled\(", src, re.M):
        p.append("D: _filled() is still defined — an orphaned tie-break helper "
                 "is what the next person re-wires when they need 'a way to "
                 "pick between two rows'")
    if re.search(r"^\s+.*_filled\(", src, re.M):
        p.append("D: something still CALLS _filled()")

    # ── E. load_trades returns the duplicate list, so callers cannot ignore
    #      it by accident ─────────────────────────────────────────────────
    sys.path.insert(0, ROOT)
    import trade_report as tr
    with tempfile.TemporaryDirectory() as d:
        sandbox(d, cumulative=True)
        wh = os.path.join(d, "reports", "warehouse")
        res = tr.load_trades(None, None, bundles_dir=wh)
        if not isinstance(res, tuple) or len(res) != 4:
            p.append("E: load_trades must return 4 values including the "
                     "duplicate list; got %d" % (len(res) if isinstance(res, tuple) else -1))
        elif not res[3]:
            p.append("E: load_trades reported no duplicates on a cumulative set")

    if p:
        print("PROBLEMS (%d):" % len(p))
        for x in p:
            print("  ✗ " + x)
        print("\nFAIL")
        return 1
    print("  A clean one-day bundles -> silent, 3 trades, no dedup claim")
    print("  B a cumulative bundle -> DUPLICATE reported, named, both files cited")
    print("  C counted once, and first-wins holds (net unchanged)")
    print("  D _filled() is gone, defined nowhere and called nowhere")
    print("  E load_trades hands the duplicate list back to its caller")
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
