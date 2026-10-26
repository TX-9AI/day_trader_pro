#!/usr/bin/env python3
"""
day_trader_pro/tests/check_otv5_paths.py  v1.0
v1.0  2026-10-25  (OTV5 paths) — CONTROL READS THE FLEET'S TRADING CODE FROM ~/OTV5, NOT THE RETIRED ~/options-trader-v4.

  Q1  fees_bridge imports the fee model from ~/OTV5/tests (HOME holds both trees; each fee model is a fake that
      names itself), and trade_fee() answers through it
  Q2  fees_bridge honours DTP_CONTROL_REPO, the one name orchestrator's parity line uses for the same checkout
  Q3  tools/check_market_calendar.py D5 diffs dtp's closures against ~/OTV5/utils/market_calendar.py: with a
      matching OTV5 list and a DIVERGENT otv4 list it passes, naming OTV5
  Q4  ...and with the divergence planted in the OTV5 list instead, D5 FAILS (it really reads OTV5)

HOME is a temp dir in every subprocess; no real checkout is read for the verdicts.

BORN RED on dtp 4fec59e: Q1 Q2 Q3 Q4
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILS = []
FAKE_FEES = '''class Unpriced: pass
class _R:
    total = {total}
def fees_for(row): return _R()
def total_fees_usd(rows): return {{"total_fees": {total}, "unpriced": 0}}
'''


def check(name, ok, detail=""):
    print("  {:<3} {}  {}".format(name, "PASS" if ok else "FAIL", detail))
    if not ok:
        FAILS.append(name)


def put(path, body):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write(body)


def py(code, home, **extra):
    env = {k: v for k, v in os.environ.items() if k not in ("DTP_CONTROL_REPO", "DTP_OTV4_DIR")}
    env.update(HOME=home, **extra)
    return subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)


def calendar_source():
    real = os.path.expanduser("~/OTV5/utils/market_calendar.py")
    if os.path.exists(real):
        return open(real).read()
    return None


def main():
    home = tempfile.mkdtemp(prefix="otv5paths_")
    try:
        put(os.path.join(home, "OTV5", "tests", "fees.py"), FAKE_FEES.format(total=5.0))
        put(os.path.join(home, "options-trader-v4", "tests", "fees.py"), FAKE_FEES.format(total=4.0))
        put(os.path.join(home, "elsewhere", "tests", "fees.py"), FAKE_FEES.format(total=7.0))
        code = ("import fees_bridge as f; print(f._fees.__file__ if f._fees else f.FEES_ERR); "
                "print(f.trade_fee({}))")
        r = py(code, home)
        lines = r.stdout.strip().splitlines()
        check("Q1", len(lines) == 2 and lines[0].startswith(os.path.join(home, "OTV5")) and lines[1] == "5.0",
              "imported={!r}".format(lines or r.stderr.strip()[-120:]))
        r = py(code, home, DTP_CONTROL_REPO=os.path.join(home, "elsewhere"))
        lines = r.stdout.strip().splitlines()
        check("Q2", len(lines) == 2 and lines[1] == "7.0", "DTP_CONTROL_REPO -> {!r}".format(lines))

        src = calendar_source()
        if src is None:
            check("Q3", False, "no ~/OTV5/utils/market_calendar.py on this host to build the fixture from")
            check("Q4", False, "(same)")
        else:
            bad = re.sub(r"(US_MARKET_HOLIDAYS = \{)", r'\1\n    "2031-02-12",', src, count=1)
            assert bad != src, "fixture anchor missing"
            o5 = os.path.join(home, "OTV5", "utils", "market_calendar.py")
            o4 = os.path.join(home, "options-trader-v4", "utils", "market_calendar.py")
            put(o5, src)
            put(o4, bad)
            run = lambda: subprocess.run([sys.executable, "tools/check_market_calendar.py"], cwd=ROOT,
                                         env={**{k: v for k, v in os.environ.items()
                                                 if k not in ("DTP_CONTROL_REPO", "DTP_OTV4_DIR")}, "HOME": home},
                                         capture_output=True, text=True, timeout=300)
            a = run()
            d5 = [l for l in a.stdout.splitlines() if "D5" in l]
            check("Q3", any("PASS" in l and "OTV5" in l for l in d5), "D5={!r}".format(d5))
            put(o5, bad)
            put(o4, src)
            b = run()
            d5b = [l for l in b.stdout.splitlines() if "D5" in l]
            check("Q4", any("FAIL" in l for l in d5b) and b.returncode != 0, "D5={!r}".format(d5b))
    finally:
        shutil.rmtree(home, ignore_errors=True)

    print("")
    if FAILS:
        print("FAILED: {}".format(", ".join(FAILS)))
        return 1
    print("ALL PASS (4)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
