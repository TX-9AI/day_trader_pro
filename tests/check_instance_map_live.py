#!/usr/bin/env python3
"""
tests/check_instance_map_live.py  v1.0
v1.0  2026-10-25  dtp r509 / OPS.74 — "Instance map" (devtools 1) READS EC2 LIVE.
      It printed the cache's saved state (all fourteen "stopped", saved 10-04)
      while Fleet ping reached 14/14. The operator: "I always assumed it was
      checking live, anything other than that makes no sense".

  Driven with a FAKE EC2 and a FAKE cache file (no AWS call is made):
  L1  show asks EC2: a box the cache saved "stopped" prints "running", headed LIVE
  L2  drift is FLAGGED: + in EC2 not in the map, ~ ID changed, - in the map not in EC2
  L3  show never writes the cache (Reconcile accepts drift, show only reports it)
  L4  a pinned box keeps its pinned ID and its state is read live by that ID
  L5  EC2 unreadable -> the cache is printed headed CACHED with its age, never LIVE
  L6  the running count is printed

  BORN RED on dtp 142e7ca: L1 L2 L4 L5 L6 (show printed the cache's saved state).

Run:  cd ~/day_trader_pro && python3 tests/check_instance_map_live.py
"""
import contextlib
import io
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_fails = []


def ck(tag, ok, msg=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {tag}  {msg}")
    if not ok:
        _fails.append(tag)


CACHE = {"updated_at": "2026-10-04T02:32:47+00:00", "instances": {
    "AMD":  {"instance_id": "i-amd", "state": "stopped", "pinned": False},
    "META": {"instance_id": "i-meta-old", "state": "stopped", "pinned": False},
    "GONE": {"instance_id": "i-gone", "state": "stopped", "pinned": False},
    "PIN":  {"instance_id": "i-pin", "state": "stopped", "pinned": True}}}
LIVE = {
    "AMD":  {"instance_id": "i-amd", "state": "running", "pinned": False},
    "META": {"instance_id": "i-meta-new", "state": "running", "pinned": False},
    "NEW":  {"instance_id": "i-new", "state": "stopped", "pinned": False},
    "PIN2": {"instance_id": "i-pin", "state": "running", "pinned": False}}


def _show(ir):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        ir._cmd_show()
    return buf.getvalue()


def main():
    import config
    import ec2ops
    import instance_registry as ir

    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "instance_map.json")
    with open(path, "w") as fh:
        json.dump(CACHE, fh)
    before = open(path).read()
    real = (config.INSTANCE_MAP_PATH, ec2ops.describe_by_tag)
    config.INSTANCE_MAP_PATH = path
    calls = []

    def fake(*a, **k):
        calls.append(1)
        return {s: dict(r) for s, r in LIVE.items()}
    ec2ops.describe_by_tag = fake
    try:
        out = _show(ir)
        rows = {l.split()[0]: l.split() for l in out.splitlines()
                if l.split() and l.split()[0] in ("AMD", "META", "NEW", "PIN")}
        ck("L1", bool(calls) and "LIVE" in out and rows.get("AMD", [""] * 3)[2] == "running",
           "AMD prints running from EC2, headed LIVE")
        ck("L2", "+ NEW" in out and "~ META" in out and "- GONE" in out,
           "drift flagged + NEW, ~ META, - GONE")
        ck("L3", open(path).read() == before, "the cache file is unchanged")
        ck("L4", rows.get("PIN", [""] * 4)[1:3] == ["i-pin", "running"],
           "PIN keeps i-pin, state running read live by ID")
        ck("L6", "4/5 running" in out, "running count printed")

        def boom(*a, **k):
            raise RuntimeError("no creds")
        ec2ops.describe_by_tag = boom
        out2 = _show(ir)
        ck("L5", "CACHED" in out2 and "LIVE" not in out2 and " ago" in out2,
           "EC2 down -> CACHED with age, never LIVE")
    finally:
        config.INSTANCE_MAP_PATH, ec2ops.describe_by_tag = real

    print("FAIL: " + " ".join(_fails) if _fails else "ALL PASS")
    return 1 if _fails else 0


if __name__ == "__main__":
    sys.exit(main())
