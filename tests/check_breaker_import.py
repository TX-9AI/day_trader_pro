#!/usr/bin/env python3
"""
day_trader_pro/tests/check_breaker_import.py — v1.0
v1.0  2026-11-23  dtp r580 / BRK.1 — new. review_kit's breaker read failed headless on 2026-11-23 ("breaker events NOT
      READ ... AttributeError: module 'config' has no attribute 'WAREHOUSE_BUCKET"): cmd_trades imports fees_bridge
      first, which puts ~/OTV5/tests on sys.path, and ~/OTV5/tests/fees.py puts ~/OTV5 at sys.path[0], so
      warehouse_reader's `import config` found ~/OTV5/config.py. check_as_cash passes breaker_of= and never imports
      warehouse_reader, so it could not see this. This gate runs the REAL import order in a fresh interpreter: review_kit,
      then fees_bridge (as cmd_trades does), then review_kit.breaker_from_warehouse with a stub S3 (a fake boto3 module;
      nothing reaches AWS).

  B1  hermetic: a fake control tree whose tests/fees.py puts the tree first on sys.path and whose config.py has no
      WAREHOUSE_BUCKET; the breaker read returns the stub's record and lists dtp's bucket (config.WAREHOUSE_BUCKET)
  B2  the same against the real ~/OTV5 (skipped, and said so, when ~/OTV5/tests/fees.py is absent)
  B3  warehouse_reader.config is the config.py beside warehouse_reader in both runs
BORN RED on 613fb1d (r579): B1 and B2 raise AttributeError (WAREHOUSE_BUCKET) at the import.

Run:  python3 tests/check_breaker_import.py
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILS, RAN = [], []

CHILD = r'''
import json, os, sys, types
root = sys.argv[1]
calls = []
rec = {"record": {"event_time": "2026-11-23T15:10:00-05:00", "reason": "daily_cap_would_pop",
                  "session_losses": 3, "notes": "stub"}}
class Body:
    def read(self):
        return json.dumps(rec).encode()
class Pager:
    def paginate(self, Bucket, Prefix):
        calls.append(Bucket)
        if "dt=2026-11-23/" in Prefix:
            return [{"Contents": [{"Key": Prefix + "sym=QQQ/part-0.json", "Size": 10}]}]
        return [{"Contents": []}]
class S3:
    def get_paginator(self, name):
        return Pager()
    def get_object(self, Bucket, Key):
        return {"Body": Body()}
fake = types.ModuleType("boto3")
fake.client = lambda *a, **k: S3()
sys.modules["boto3"] = fake
sys.path.insert(0, os.path.join(root, "tools"))
import review_kit                     # the script
import fees_bridge                    # cmd_trades' first import (fee_of is None in a real run)
out = review_kit.breaker_from_warehouse("2026-11-23")
import warehouse_reader as wr
print(json.dumps({"n": len(out), "reason": out[0].get("reason") if out else None, "box": out[0].get("box") if out else None,
                  "buckets": sorted(set(calls)), "config": os.path.abspath(wr.config.__file__),
                  "fees": fees_bridge.available()}))
'''


def ck(n, ok, msg=""):
    RAN.append(n)
    print(f"  {n:<3} {'PASS' if ok else 'FAIL'}  {msg if not ok else ''}")
    if not ok:
        FAILS.append(n)


def run(control_repo):
    env = dict(os.environ, DTP_CONTROL_REPO=control_repo, PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, "-c", CHILD, ROOT], capture_output=True, text=True, timeout=120,
                       env=env, cwd=tempfile.gettempdir())
    last = (p.stdout.strip().splitlines() or [""])[-1]
    try:
        return json.loads(last), p
    except ValueError:
        return None, p


def main():
    sys.path.insert(0, ROOT)
    import config
    bucket = config.WAREHOUSE_BUCKET
    want_cfg = os.path.join(ROOT, "config.py")

    with tempfile.TemporaryDirectory(prefix="brk_imp_") as fake:
        os.makedirs(os.path.join(fake, "tests"))
        with open(os.path.join(fake, "config.py"), "w") as fh:
            fh.write("DATA_DIR = '/nonexistent'\n")              # another tree's config: no WAREHOUSE_BUCKET
        with open(os.path.join(fake, "tests", "fees.py"), "w") as fh:
            fh.write("import os, sys\nsys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))\n"
                     "import config  # noqa\n")
        r1, p1 = run(fake)
    ok1 = bool(r1) and r1["n"] == 1 and r1["reason"] == "daily_cap_would_pop" and r1["box"] == "QQQ" \
        and r1["buckets"] == [bucket]
    ck("B1", ok1, f"{r1} {p1.stderr.strip().splitlines()[-1:] if p1.stderr else ''}")

    real = os.path.expanduser("~/OTV5")
    r2 = None
    if os.path.isfile(os.path.join(real, "tests", "fees.py")):
        r2, p2 = run(real)
        ok2 = bool(r2) and r2["n"] == 1 and r2["buckets"] == [bucket] and r2["fees"] is True
        ck("B2", ok2, f"{r2} {p2.stderr.strip().splitlines()[-1:] if p2.stderr else ''}")
    else:
        print("  B2  SKIP  ~/OTV5/tests/fees.py absent")
    ck("B3", bool(r1) and r1["config"] == want_cfg and (r2 is None or r2["config"] == want_cfg),
       f"{r1 and r1['config']} {r2 and r2['config']}")

    print()
    if FAILS:
        print(f"FAILED: {' '.join(FAILS)}")
        return 1
    print(f"ALL {len(RAN)} PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
