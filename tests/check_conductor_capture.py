#!/usr/bin/env python3
"""
day_trader_pro/tests/check_conductor_capture.py — v1.0
v1.0  2026-11-08  dtp r543 / CAP.6 — new. eod_conductor_v2 v2.15 starts OTV5's capture_all candles-recent from
      stop_services, in the same ssh command that stops optionsbot and candle-feed (measured 11-08: with candle-feed up,
      10 of 13 boxes were refused at the TastyTrade user-session limit; with both stopped, 13 of 13 pulled).

  K1  the real stop_services sends ONE command per verified box: the stop of optionsbot + candle-feed comes BEFORE the
      capture start in it
  K2  the capture is detached (setsid nohup, the whole background list's stdin/stdout/stderr redirected, its own output
      appended to a log) and bounded
      (timeout 300 with --kill-after), so the purge and the halt never wait for it
  K3  verified boxes only: stop_services([]) sends nothing; a dry run sends nothing and says it would start the capture
  K4  the command parses as bash (bash -n) and returns while a slow capture is still running (a fake capture_all that
      sleeps 30 s; the command must come back in under 10 s and leave its log line)
BORN RED on 9f21f26 (r542): stop_services started no capture.

Run:  python3 tests/check_conductor_capture.py
"""
import io
import os
import subprocess
import sys
import tempfile
import time
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
FAILS, RAN = [], []


def ck(n, ok, msg=""):
    RAN.append(n)
    print(f"  {n:<3} {'PASS' if ok else 'FAIL'}  {msg if not ok else ''}")
    if not ok:
        FAILS.append(n)


def main():
    import eod_conductor_v2 as C
    sent = []
    C.fleet.get_fleet = lambda syms: [(s, "10.0.0.%d" % i, "running") for i, s in enumerate(syms)]
    C.ssh_util.ssh_run = lambda ip, cmd, timeout=None: (sent.append((ip, cmd)) or (0, "STOPPED inactive inactive", ""))
    buf = io.StringIO()
    with redirect_stdout(buf):
        C.stop_services(["AMD", "NVDA"], False)
    cmds = [c for _ip, c in sent]
    k1 = (len(cmds) == 2 and all("capture_all.py candles-recent" in c for c in cmds)
          and all(c.index("systemctl stop optionsbot candle-feed") < c.index("capture_all.py candles-recent")
                  for c in cmds))
    ck("K1", k1, repr(cmds[:1]))
    c0 = cmds[0] if cmds else ""
    k2 = all(t in c0 for t in ("setsid nohup", "timeout --kill-after=10 300", ") < /dev/null > /dev/null 2>&1 &",
                               ">> logs/capture_all.log"))
    ck("K2", k2, c0)
    sent.clear()
    with redirect_stdout(buf):
        C.stop_services([], False)
        out_dry = io.StringIO()
        with redirect_stdout(out_dry):
            C.stop_services(["AMD"], True)
    ck("K3", sent == [] and "start capture_all candles-recent" in out_dry.getvalue(), out_dry.getvalue())

    # K4 — a real bash run against a fake tree whose capture_all sleeps
    home = tempfile.mkdtemp(prefix="check_conductor_capture_")
    tree = os.path.join(home, "options-trader")
    os.makedirs(os.path.join(tree, "tools"))
    os.makedirs(os.path.join(tree, "venv", "bin"))
    with open(os.path.join(tree, "venv", "bin", "python"), "w") as fh:
        fh.write("#!/bin/bash\necho fake-capture $@; sleep 30\n")
    os.chmod(os.path.join(tree, "venv", "bin", "python"), 0o755)
    open(os.path.join(tree, "tools", "capture_all.py"), "w").write("")
    parse = subprocess.run(["bash", "-n", "-c", C.CAPTURE_CMD], capture_output=True, text=True)
    t0 = time.time()
    try:
        p = subprocess.run(["bash", "-c", C.CAPTURE_CMD], capture_output=True, text=True, timeout=15,
                           env=dict(os.environ, HOME=home))
    except subprocess.TimeoutExpired:
        p = subprocess.CompletedProcess([], 124, "", "the command waited for the capture")
    took = time.time() - t0
    time.sleep(1)
    log = os.path.join(tree, "logs", "capture_all.log")
    logged = open(log).read() if os.path.exists(log) else ""
    subprocess.run(["pkill", "-f", os.path.join(tree, "venv", "bin", "python")], capture_output=True)
    ck("K4", parse.returncode == 0 and p.returncode == 0 and took < 10 and "CAPTURE started" in p.stdout
       and "fake-capture tools/capture_all.py candles-recent" in logged,
       f"parse={parse.returncode} rc={p.returncode} took={took:.1f}s out={p.stdout!r} log={logged!r}")

    print()
    if FAILS:
        print("RED — %s" % ", ".join(FAILS))
        return 1
    print("GREEN — %d checks" % len(RAN))
    return 0


if __name__ == "__main__":
    sys.exit(main())
