#!/usr/bin/env python3
"""
day_trader_pro/tests/check_control_repo.py  v1.0
v1.0  2026-10-25  CTL.1 — THE WAKE'S PARITY LINE COMPARES THE FLEET TO ORIGIN THROUGH ~/OTV5.

  C1  with DTP_CONTROL_REPO unset, orchestrator.CONTROL_REPO is ~/OTV5
  C2  the real _fleet_parity, HOME holding an OTV5 checkout, asks THAT checkout's origin and reads "vs origin"
  C3  a box behind origin is flagged BEHIND/AHEAD (the drift consensus cannot see when every box is behind)
  C4  DTP_CONTROL_REPO still overrides the default
  C5  the default is not a retired trading tree (options-trader-v3 / options-trader-v4)

Fakes only: HOME is a temp dir, fleet.get_fleet / ssh_util.ssh_run / subprocess.run are stubs, so no
box, no ssh and no network (`git ls-remote` is never really run).

BORN RED on dtp 4fec59e: C1 C2 C3 C5
"""
import contextlib
import importlib
import io
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
FAILS = []


def check(name, ok, detail=""):
    print("  {:<3} {}  {}".format(name, "PASS" if ok else "FAIL", detail))
    if not ok:
        FAILS.append(name)


def load(env_value=None):
    saved = os.environ.pop("DTP_CONTROL_REPO", None)
    if env_value is not None:
        os.environ["DTP_CONTROL_REPO"] = env_value
    try:
        import orchestrator
        return importlib.reload(orchestrator)
    finally:
        os.environ.pop("DTP_CONTROL_REPO", None)
        if saved is not None:
            os.environ["DTP_CONTROL_REPO"] = saved


def parity(orch, home):
    import config
    import fleet
    import ssh_util
    calls = []
    origin = "aaaaaaa" + "0" * 33
    heads = {"10.0.0.1": "aaaaaaa", "10.0.0.2": "bbbbbbb", "10.0.0.3": "bbbbbbb"}

    def fake_run(argv, **kw):
        calls.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, stdout=origin + "\tHEAD\n", stderr="")

    saved = (fleet.get_fleet, ssh_util.ssh_run, subprocess.run, config.MOCK_AWS, os.environ.get("HOME"))
    try:
        fleet.get_fleet = lambda only=None: [("AMD", "10.0.0.1", "running"), ("NVDA", "10.0.0.2", "running"),
                                             ("SPY", "10.0.0.3", "running")]
        ssh_util.ssh_run = lambda ip, cmd, timeout=None, **k: (0, heads[ip] + "1" * 33 + "\n", "")
        subprocess.run = fake_run
        config.MOCK_AWS = False
        os.environ["HOME"] = home
        with contextlib.redirect_stdout(io.StringIO()):
            line = orch._fleet_parity({"AMD": "i-1", "NVDA": "i-2", "SPY": "i-3"},
                                      {"i-1": True, "i-2": True, "i-3": True})
    finally:
        fleet.get_fleet, ssh_util.ssh_run, subprocess.run, config.MOCK_AWS = saved[:4]
        if saved[4] is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = saved[4]
    return line, calls


def main():
    orch = load()
    check("C1", orch.CONTROL_REPO == "~/OTV5", "default={!r}".format(orch.CONTROL_REPO))

    home = tempfile.mkdtemp(prefix="ctlrepo_")
    os.makedirs(os.path.join(home, "OTV5", ".git"))
    line, calls = parity(orch, home)
    asked = [c for c in calls if c[:1] == ["git"] and "ls-remote" in c]
    want = os.path.join(home, "OTV5")
    check("C2", bool(asked) and asked[0][2] == want and "vs origin" in line,
          "git calls={} line={!r}".format(asked, line.splitlines()[0] if line else ""))
    check("C3", "BEHIND/AHEAD" in line and "NVDA" in line and "SPY" in line, "line={!r}".format(line))

    orch2 = load("/srv/elsewhere")
    check("C4", orch2.CONTROL_REPO == "/srv/elsewhere", "override={!r}".format(orch2.CONTROL_REPO))
    load()                                      # leave the module at its default

    import shutil
    shutil.rmtree(home, ignore_errors=True)
    retired = any(t in orch.CONTROL_REPO for t in ("options-trader-v3", "options-trader-v4"))
    check("C5", not retired, "default={!r}".format(orch.CONTROL_REPO))

    print("")
    if FAILS:
        print("FAILED: {}".format(", ".join(FAILS)))
        return 1
    print("ALL PASS (5)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
