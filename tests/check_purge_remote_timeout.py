#!/usr/bin/env python3
"""
day_trader_pro/tests/check_purge_remote_timeout.py  v1.0
v1.0  2026-10-25  S3.19 — THE BOX'S PURGE DIES AT ITS BUDGET EVEN WHEN THE ssh CLIENT IS ALREADY GONE.

  T1  the remote command purge_verified() hands ssh_map carries `timeout --kill-after=N <budget>` around python3,
      with <budget> == the timeout the ssh client is given (VERIFY_TIMEOUT_S)
  T2  EXECUTED: the client is killed mid-run (what an ssh timeout does) and a purge that IGNORES SIGTERM is still
      dead by budget + kill-after - the S3.19 orphan cannot outlive its budget
  T3  EXECUTED: a purge that overruns and honours SIGTERM ends `rc=124`; one that ignores it ends `rc=137`
  T4  EXECUTED: a purge inside its budget is untouched - its own output and `rc=0`
  T5  purge_verified names a box whose result is rc=124 as TIMED OUT in the log

The real purge_verified() is driven with a fake ssh_util.ssh_map that records the command; the command is then
run by bash with HOME pointing at a temp dir whose ~/options-trader/warehouse/retention_purge.py is a fake.
DTP_VERIFY_TIMEOUT=2 keeps it short; the purge-debt file is redirected to temp. No box, no ssh, no Telegram.

BORN RED on dtp 4fec59e: T1 T2 T3 T5
"""
import contextlib
import io
import os
import re
import signal
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["DTP_VERIFY_TIMEOUT"] = "2"
import eod_conductor_v2 as C  # noqa: E402

FAILS = []
PIDS = []
DIRS = []


def check(name, ok, detail=""):
    print("  {:<3} {}  {}".format(name, "PASS" if ok else "FAIL", detail))
    if not ok:
        FAILS.append(name)


FAKE = """import os, signal, sys, time
open(os.path.expanduser('~/purge.pid'), 'w').write(str(os.getpid()))
if os.environ.get('FAKE_IGNORE_TERM') == '1':
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
print('deleted prints 10', flush=True)
time.sleep(float(os.environ.get('FAKE_SLEEP', '120')))
print('reclaim OK', flush=True)
"""


def captured(results=None):
    seen = {}

    def fake_map(targets, command, timeout=None, **kw):
        seen["cmd"], seen["timeout"] = command, timeout
        return results or {k: (0, "rc=0", "") for k, _ip in targets}
    saved = (C.ssh_util.ssh_map, C.fleet.get_fleet, C._notify, C.PURGE_DEBT_PATH)
    d = tempfile.mkdtemp(prefix="purgeto_")
    DIRS.append(d)
    try:
        C.ssh_util.ssh_map = fake_map
        C.fleet.get_fleet = lambda only=None: [("AMD", "10.0.0.1", "running")]
        C._notify = lambda *_: None
        C.PURGE_DEBT_PATH = os.path.join(d, "purge_debt.json")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            C.purge_verified(["AMD"], dry=False)
    finally:
        C.ssh_util.ssh_map, C.fleet.get_fleet, C._notify, C.PURGE_DEBT_PATH = saved
    return seen, buf.getvalue()


def world(cmd):
    home = tempfile.mkdtemp(prefix="purgehome_")
    DIRS.append(home)
    os.makedirs(os.path.join(home, "options-trader", "warehouse"))
    open(os.path.join(home, "options-trader", "warehouse", "retention_purge.py"), "w").write(FAKE)
    return home, cmd.replace("/tmp/retention_purge.out", os.path.join(home, "purge.out"))


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:                                        # a zombie is dead for our purpose
        return open("/proc/%d/stat" % pid).read().split(")")[-1].split()[0] != "Z"
    except OSError:
        return False


def pid_of(home, wait=5.0):
    f = os.path.join(home, "purge.pid")
    t = time.time() + wait
    while time.time() < t:
        if os.path.exists(f) and open(f).read().strip():
            pid = int(open(f).read())
            PIDS.append(pid)
            return pid
        time.sleep(0.05)
    return None


def run(cmd, limit, **fake_env):
    home, c = world(cmd)
    env = dict(os.environ, HOME=home, **fake_env)
    p = subprocess.Popen(["bash", "-c", c], env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         text=True, start_new_session=True)
    try:
        out, _ = p.communicate(timeout=limit)
    except subprocess.TimeoutExpired:            # no remote budget: the purge would run on
        pid_of(home, wait=0.1)
        os.killpg(p.pid, signal.SIGKILL)
        p.communicate()
        return "(still running after %ds)" % limit
    return out.strip()


def main():
    seen, _ = captured()
    cmd = seen.get("cmd", "")
    m = re.search(r"timeout --kill-after=(\d+) (\d+) python3 warehouse/retention_purge\.py", cmd)
    check("T1", bool(m) and int(m.group(2)) == seen.get("timeout") == C.VERIFY_TIMEOUT_S,
          "remote={} ssh timeout={} cmd={!r}".format(m.groups() if m else None, seen.get("timeout"), cmd[:110]))
    kill_after = int(m.group(1)) if m else 10

    # T2 — the client dies (ssh timeout), the box's purge must not live on
    home, c = world(cmd)
    env = dict(os.environ, HOME=home, FAKE_IGNORE_TERM="1")
    client = subprocess.Popen(["bash", "-c", c], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    pid = pid_of(home)
    client.kill()
    client.wait()
    deadline = time.time() + C.VERIFY_TIMEOUT_S + kill_after + 4
    while pid and alive(pid) and time.time() < deadline:
        time.sleep(0.2)
    check("T2", pid is not None and not alive(pid),
          "client killed; orphaned purge pid={} still alive after {}s={}".format(
              pid, C.VERIFY_TIMEOUT_S + kill_after + 4, bool(pid and alive(pid))))

    limit = C.VERIFY_TIMEOUT_S + kill_after + 4
    out_term = run(cmd, limit)
    out_kill = run(cmd, limit, FAKE_IGNORE_TERM="1")
    check("T3", out_term.endswith("rc=124") and out_kill.endswith("rc=137"),
          "TERM -> {!r}  KILL -> {!r}".format(out_term[-8:], out_kill[-8:]))
    out_ok = run(cmd, limit, FAKE_SLEEP="0.1")
    check("T4", out_ok.endswith("rc=0") and "reclaim OK" in out_ok, "fast purge -> {!r}".format(out_ok[-30:]))

    _, log = captured({"AMD": (0, "deleted prints 10\nrc=124", "")})
    check("T5", "TIMED OUT" in log and "AMD" in log, "log={!r}".format(log.strip().splitlines()[-1:]))

    print("")
    if FAILS:
        print("FAILED: {}".format(", ".join(FAILS)))
        return 1
    print("ALL PASS (5)")
    return 0


if __name__ == "__main__":
    try:
        rc = main()
    finally:
        for p in PIDS:                           # never leave a fake purge behind, red or green
            try:
                os.kill(p, signal.SIGKILL)
            except Exception:                    # noqa: BLE001
                pass
        import shutil
        for d in DIRS:
            shutil.rmtree(d, ignore_errors=True)
    sys.exit(rc)
