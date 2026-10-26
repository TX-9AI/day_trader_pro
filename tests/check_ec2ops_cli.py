#!/usr/bin/env python3
"""
day_trader_pro/tests/check_ec2ops_cli.py  v1.0
v1.0  2026-10-25  OPS.30 — `python3 ec2ops.py ...` REFUSES, NAMED, EXIT 2; IT NEVER EXITS 0 SILENT.

  E1  `ec2ops.py --help`             -> rc 2, usage on stderr
  E2  `ec2ops.py start --only AMD`   -> rc 2, says nothing was started, names wake_and_bake.py and fleet.py
  E3  `ec2ops.py` (no arguments)     -> rc 2
  E4  nothing goes to stdout (a pipe reading stdout cannot mistake the refusal for output)
  E5  control: `import ec2ops` is unchanged - silent, start/stop/describe_by_names still exported

Run as a subprocess with DTP_MOCK_AWS=1 and OT_FLEET_POWER_LOG=/dev/null, so even a regression that
called start() could not reach AWS or the operator's ledger.

BORN RED on dtp 4fec59e: E1 E2 E3
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILS = []
ENV = dict(os.environ, DTP_MOCK_AWS="1", OT_FLEET_POWER_LOG=os.devnull)


def check(name, ok, detail=""):
    print("  {:<3} {}  {}".format(name, "PASS" if ok else "FAIL", detail))
    if not ok:
        FAILS.append(name)


def run(*args):
    return subprocess.run([sys.executable, "ec2ops.py"] + list(args), cwd=ROOT, env=ENV,
                          capture_output=True, text=True, timeout=60)


def main():
    a = run("--help")
    check("E1", a.returncode == 2 and "library" in a.stderr, "rc={} stderr={!r}".format(a.returncode, a.stderr[:80]))
    b = run("start", "--only", "AMD")
    check("E2", b.returncode == 2 and "Nothing was started" in b.stderr and "wake_and_bake.py" in b.stderr
          and "fleet.py" in b.stderr, "rc={} stderr={!r}".format(b.returncode, b.stderr[:80]))
    c = run()
    check("E3", c.returncode == 2, "rc={}".format(c.returncode))
    check("E4", a.stdout == b.stdout == c.stdout == "", "stdout={!r}".format(a.stdout + b.stdout + c.stdout))
    d = subprocess.run([sys.executable, "-c", "import ec2ops,sys; sys.exit(0 if all(hasattr(ec2ops, n) for n in "
                        "('start','stop','describe_by_names','describe_by_tag')) else 1)"],
                       cwd=ROOT, env=ENV, capture_output=True, text=True, timeout=60)
    check("E5", d.returncode == 0 and d.stdout == "" and d.stderr == "", "rc={} out={!r} err={!r}".format(
        d.returncode, d.stdout[:60], d.stderr[:60]))
    print("")
    if FAILS:
        print("FAILED: {}".format(", ".join(FAILS)))
        return 1
    print("ALL PASS (5)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
