#!/usr/bin/env python3
"""
day_trader_pro/tests/check_fleet_reconcile.py  v1.1
v1.1  2026-09-10  dtp r349 - R7 and R8 for the timer quiesce. The reconcile
      raced `s3-push.timer` box by box and every loser exited 0 in silence, so
      the tool could only say NO ANSWER and the fleet went unreconciled for
      three nights. R7 pins the order - stop, reconcile, start - and R8 pins
      that the re-arm survives an exception, because a tool that disarms a
      timer and dies leaves the box with no pusher at all.
v1.0  2026-09-09  dtp r325 / S3.24 — the land gate for tools/fleet_reconcile.py.

Six checks, EXECUTED rather than grepped (WA §21): the defect class this tool
is exposed to is a call that never happens or happens against the wrong
interpreter, and neither is visible in source text.

  R1  the remote command runs /usr/bin/python3, never the venv
  R2  the timeout is >= 900s and reads DTP_RECONCILE_TIMEOUT
  R3  parse_reset returns the count on a real line and None on anything else
  R4  --dry-run runs NO ssh at all
  R5  a silent box is reported and makes the exit code non-zero
  R6  the tool holds no reconcile logic of its own (no boto3, no bucket LIST)
  R7  the push timer is STOPPED before the first reconcile and STARTED again
      after the last — the race that produced "NO ANSWER" on every box
  R8  the re-arm runs even when a reconcile raises (a tool that disarms a
      timer and dies leaves the box with no pusher)

⚠️ A MISSING MODULE IS A NAMED FAILURE, not a traceback. A checker that dies
with an ImportError looks like a broken environment, which is the one shape
that teaches an operator to skip a red run.
"""

import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

FAILS = []


def check(name, ok, detail=""):
    print("  {:<4} {}  {}".format(name, "PASS" if ok else "FAIL", detail))
    if not ok:
        FAILS.append(name)


def _stub_deps():
    """config/fleet/ssh_util stubs so this runs with no AWS and no fleet."""
    if "config" not in sys.modules:
        c = types.ModuleType("config")
        c.INSTALL_DIR = "~/options-trader"
        c.SSH_CONNECT_TIMEOUT = 12
        c.UNIVERSE = ["UNH"]
        sys.modules["config"] = c


def main():
    _stub_deps()
    try:
        import tools.fleet_reconcile as fr
    except Exception as exc:                                    # noqa: BLE001
        print("  FAIL  tools/fleet_reconcile.py did not import: {}".format(exc))
        return 1

    src = open(os.path.join(REPO, "tools", "fleet_reconcile.py")).read()

    # R1 — the interpreter. The venv has no boto3 (audit F1, and the operator
    # hit the same ModuleNotFoundError by hand on 2026-09-09).
    check("R1", "/usr/bin/python3" in fr.REMOTE_CMD
          and "venv/bin/python" not in fr.REMOTE_CMD,
          "REMOTE_CMD={}".format(fr.REMOTE_CMD))

    # R2 — the cushion. fleet._exec is 22s; a prefix walk is minutes.
    check("R2", fr.RECONCILE_TIMEOUT_S >= 900
          and "DTP_RECONCILE_TIMEOUT" in src,
          "timeout={}s".format(fr.RECONCILE_TIMEOUT_S))

    # R3 — silence is not zero.
    good = "reconcile: 19 prefix counter(s) reset to the S3 truth"
    check("R3", fr.parse_reset(good) == 19
          and fr.parse_reset("") is None
          and fr.parse_reset("ssh timeout") is None
          and fr.parse_reset("reconcile: 0 prefix counter(s) reset") == 0,
          "19 / None / None / 0")

    # R4 — a dry run touches nothing.
    calls = []

    def spy(ip, cmd, timeout=None):
        calls.append(ip)
        return 0, good, ""

    fr.targets = lambda only=None: [("UNH", "10.0.0.1")]
    fr.run(dry=True, runner=spy, out=lambda *_a, **_k: None)
    check("R4", calls == [], "ssh calls during dry-run: {}".format(len(calls)))

    # R5 — a box that says nothing is named and fails the run.
    lines = []

    def mute(ip, cmd, timeout=None):
        return 255, "", "ssh timeout"

    ok, silent = fr.run(runner=mute, out=lines.append)
    joined = "\n".join(lines)
    check("R5", ok == [] and silent == ["UNH"] and "NO ANSWER" in joined,
          "answered={} silent={}".format(ok, silent))

    # R6 — thin caller. Two implementations of one count is the drift this
    # repo keeps finding; the flag lives in otv4 and stays there.
    banned = [w for w in ("import boto3", "list_objects", "boto3.client")
              if w in src]
    check("R6", not banned, "found: {}".format(banned) if banned else "none")

    # R7 — order matters: stop, reconcile, start.
    seq = []

    def trace(ip, cmd, timeout=None):
        if "stop s3-push.timer" in cmd:
            seq.append("stop")
        elif "start s3-push.timer" in cmd:
            seq.append("start")
        else:
            seq.append("recon")
        return 0, good, ""

    fr.targets = lambda only=None: [("UNH", "10.0.0.1"), ("QQQ", "10.0.0.2")]
    fr.run(runner=trace, out=lambda *_a, **_k: None)
    first_recon = seq.index("recon") if "recon" in seq else -1
    check("R7", seq.count("stop") == 2 and seq.count("start") == 2
          and first_recon > 0 and seq[:2] == ["stop", "stop"]
          and seq[-2:] == ["start", "start"],
          "sequence {}".format(seq))

    # R8 — the re-arm must survive an exception mid-reconcile.
    def boom(ip, cmd, timeout=None):
        if "s3-push.timer" in cmd:
            seq2.append("start" if "start" in cmd else "stop")
            return 0, "", ""
        raise RuntimeError("ssh blew up mid-reconcile")

    seq2 = []
    try:
        fr.run(runner=boom, out=lambda *_a, **_k: None)
    except Exception:                                           # noqa: BLE001
        pass
    check("R8", seq2.count("start") == 2,
          "re-armed {} time(s) after a raise".format(seq2.count("start")))

    print("")
    if FAILS:
        print("FAILED: {}".format(", ".join(FAILS)))
        return 1
    print("ALL PASS (8)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
