#!/usr/bin/env python3
"""
day_trader_pro/tests/check_fleet_reconcile.py  v1.0
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

    print("")
    if FAILS:
        print("FAILED: {}".format(", ".join(FAILS)))
        return 1
    print("ALL PASS (6)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
