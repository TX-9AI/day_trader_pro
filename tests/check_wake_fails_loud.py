#!/usr/bin/env python3
"""
day_trader_pro/tests/check_wake_fails_loud.py  v1.0
v1.0  2026-10-25  OPS.16 — A FAILED `fleet.py update --wake` FAILS, NAMED, WITH A NON-ZERO EXIT.

  W1  ec2ops.start raises        -> rc 1, the box named under `WAKE FAILED`
  W2  the registry has no id     -> rc 1, named
  W3  start issued, box never comes up (SSH wait times out) -> rc 1, named
  W4  partial: two asked, one comes up -> the one deploys, the other is named, rc 1
  W5  control: the wake works, the box comes up and deploys -> rc 0, no WAKE FAILED
  W6  control: no --wake, a stopped box is skipped as before -> rc 0
  W7  _wake() returns False on a failed wake and True when the start was issued

The REAL cmd_update / _wake / _wait_running_and_ssh are driven; only the edges are fakes:
get_fleet (the fleet's states), _exec (ssh), instance_registry.discover, ec2ops.start, and
time.sleep. config.MOCK_AWS is forced off so the real wake path runs. Nothing reaches AWS or a box.

BORN RED on dtp 4fec59e: W1 W2 W3 W4 W7
"""
import contextlib
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("OT_FLEET_POWER_LOG", os.devnull)

import config      # noqa: E402
import ec2ops      # noqa: E402
import fleet       # noqa: E402
import instance_registry  # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print("  {:<3} {}  {}".format(name, "PASS" if ok else "FAIL", detail))
    if not ok:
        FAILS.append(name)


class World:
    """states: {sym: state before}; comes_up: syms that become running after a start."""

    def __init__(self, states, comes_up=(), start_raises=False, ids=True):
        self.states = dict(states)
        self.comes_up = set(comes_up)
        self.start_raises = start_raises
        self.ids = ids
        self.deployed = []
        self.started = False

    def get_fleet(self, only=None):
        return [(s, "10.0.0.%d" % i, st) for i, (s, st) in enumerate(sorted(self.states.items()), 1)
                if not only or s in only]

    def discover(self, symbols):
        return ({s: ({"instance_id": "i-%s" % s.lower()} if self.ids else {}) for s in symbols}, None)

    def start(self, ids):
        if self.start_raises:
            raise RuntimeError("You must specify a region.")
        self.started = True
        for s in self.comes_up:
            self.states[s] = "running"

    def _exec(self, s, ip, cmd, timeout=None):
        if "push.sh --deploy" in cmd:
            self.deployed.append(s)
        return 0, "OK", ""


def drive(world, wake=True):
    saved = (fleet.get_fleet, fleet._exec, instance_registry.discover, ec2ops.start, fleet.time.sleep,
             fleet._wait_running_and_ssh, config.MOCK_AWS)
    real_wait = fleet._wait_running_and_ssh
    try:
        fleet.get_fleet = world.get_fleet
        fleet._exec = world._exec
        instance_registry.discover = world.discover
        ec2ops.start = world.start
        fleet.time.sleep = lambda *_: None
        fleet._wait_running_and_ssh = lambda only=None: real_wait(only, timeout=0.05, interval=0)
        config.MOCK_AWS = False
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = fleet.cmd_update(only=None, restart=True, wake=wake)
        return rc, buf.getvalue()
    finally:
        (fleet.get_fleet, fleet._exec, instance_registry.discover, ec2ops.start, fleet.time.sleep,
         fleet._wait_running_and_ssh, config.MOCK_AWS) = saved


def named(out, sym):
    return any("WAKE FAILED" in ln and sym in ln for ln in out.splitlines())


def main():
    w = World({"AMD": "stopped"}, start_raises=True)
    rc, out = drive(w)
    check("W1", rc == 1 and named(out, "AMD"), "rc={} tail={!r}".format(rc, out.strip().splitlines()[-1:]))

    w = World({"AMD": "stopped"}, ids=False)
    rc, out = drive(w)
    check("W2", rc == 1 and named(out, "AMD"), "rc={} tail={!r}".format(rc, out.strip().splitlines()[-1:]))

    w = World({"AMD": "stopped"}, comes_up=())
    rc, out = drive(w)
    check("W3", rc == 1 and named(out, "AMD") and w.started, "rc={} started={} tail={!r}".format(
        rc, w.started, out.strip().splitlines()[-1:]))

    w = World({"AMD": "stopped", "NVDA": "stopped"}, comes_up=("NVDA",))
    rc, out = drive(w)
    check("W4", rc == 1 and w.deployed == ["NVDA"] and named(out, "AMD") and not named(out, "NVDA"),
          "rc={} deployed={} tail={!r}".format(rc, w.deployed, out.strip().splitlines()[-1:]))

    w = World({"AMD": "stopped", "SPY": "running"}, comes_up=("AMD",))
    rc, out = drive(w)
    check("W5", rc == 0 and sorted(w.deployed) == ["AMD", "SPY"] and "WAKE FAILED" not in out,
          "rc={} deployed={}".format(rc, w.deployed))

    w = World({"AMD": "stopped", "SPY": "running"})
    rc, out = drive(w, wake=False)
    check("W6", rc == 0 and w.deployed == ["SPY"] and "skipped" in out and "WAKE FAILED" not in out,
          "rc={} deployed={}".format(rc, w.deployed))

    saved = (instance_registry.discover, ec2ops.start, config.MOCK_AWS)
    try:
        config.MOCK_AWS = False
        bad = World({"AMD": "stopped"}, start_raises=True)
        instance_registry.discover, ec2ops.start = bad.discover, bad.start
        with contextlib.redirect_stdout(io.StringIO()):
            r_bad = fleet._wake([("AMD", None, "stopped")])
        good = World({"AMD": "stopped"}, comes_up=("AMD",))
        instance_registry.discover, ec2ops.start = good.discover, good.start
        with contextlib.redirect_stdout(io.StringIO()):
            r_good = fleet._wake([("AMD", None, "stopped")])
    finally:
        instance_registry.discover, ec2ops.start, config.MOCK_AWS = saved
    check("W7", r_bad is False and r_good is True, "failed={!r} issued={!r}".format(r_bad, r_good))

    print("")
    if FAILS:
        print("FAILED: {}".format(", ".join(FAILS)))
        return 1
    print("ALL PASS (7)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
