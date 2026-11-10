#!/usr/bin/env python3
"""
day_trader_pro/tests/check_conductor_capture.py — v1.1
v1.1  2026-11-09  dtp r545 / CAP.7 — the capture never started on 11-09 (its log, capture_all.log, is root-owned: systemd's
      StandardOutput=append: creates it). K2 its own log capture_nightly.log and never capture_all.log, option-candles
      after candles-recent; K4 says "CAPTURE running"; K5 the 11-09 failure reproduced (an unwritable capture_all.log
      no longer matters; an unwritable capture log says "CAPTURE NOT RUNNING"); K6 wait_for_capture waits while a box
      captures, is bounded, counts an unanswered box as done, does nothing dry; K7 the takedown order: services stopped,
      purge, the capture wait, then the machines stopped.
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
    k1 = (len(cmds) == 2 and all("capture_all.py candles-recent" in c and "capture_all.py option-candles" in c
                                  for c in cmds)
          and all(c.index("systemctl stop optionsbot candle-feed") < c.index("capture_all.py candles-recent")
                  < c.index("capture_all.py option-candles") for c in cmds))
    ck("K1", k1, repr(cmds[:1]))
    c0 = cmds[0] if cmds else ""
    k2 = (all(t in c0 for t in ("setsid nohup", "timeout --kill-after=10 300", "timeout --kill-after=10 1500",
                                ") < /dev/null > /dev/null 2>&1 &", ">> logs/capture_nightly.log"))
          and "capture_all.log" not in c0)
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
    log = os.path.join(tree, "logs", "capture_nightly.log")
    logged = open(log).read() if os.path.exists(log) else ""
    subprocess.run(["pkill", "-f", os.path.join(tree, "venv", "bin", "python")], capture_output=True)
    ck("K4", parse.returncode == 0 and p.returncode == 0 and took < 10 and "CAPTURE running" in p.stdout
       and "fake-capture tools/capture_all.py candles-recent" in logged,
       f"parse={parse.returncode} rc={p.returncode} took={took:.1f}s out={p.stdout!r} log={logged!r}")

    def kill_tree(root):
        """every process whose cwd is inside the fake tree (the sh -c wrapper names a relative path)"""
        for pid in os.listdir("/proc"):
            if pid.isdigit():
                try:
                    if os.readlink(f"/proc/{pid}/cwd").startswith(root):
                        os.kill(int(pid), 9)
                except OSError:
                    pass

    kill_tree(tree)
    # K5 — the 11-09 failure: a root-owned capture_all.log (simulated read-only) must not stop the capture; an
    # unwritable capture log must be SAID
    home2 = tempfile.mkdtemp(prefix="check_conductor_capture_")
    tree2 = os.path.join(home2, "options-trader")
    for d in ("tools", os.path.join("venv", "bin"), "logs"):
        os.makedirs(os.path.join(tree2, d), exist_ok=True)
    with open(os.path.join(tree2, "venv", "bin", "python"), "w") as fh:
        fh.write("#!/bin/bash\necho fake-capture $@; sleep 20\n")
    os.chmod(os.path.join(tree2, "venv", "bin", "python"), 0o755)
    open(os.path.join(tree2, "tools", "capture_all.py"), "w").write("")
    ro = os.path.join(tree2, "logs", "capture_all.log")
    open(ro, "w").write("root's\n")
    os.chmod(ro, 0o444)
    env2 = dict(os.environ, HOME=home2)
    a = subprocess.run(["bash", "-c", C.CAPTURE_CMD], capture_output=True, text=True, timeout=15, env=env2)
    kill_tree(tree2)
    time.sleep(0.5)
    nl = os.path.join(tree2, "logs", "capture_nightly.log")
    open(nl, "a").close()
    os.chmod(nl, 0o444)
    b = subprocess.run(["bash", "-c", C.CAPTURE_CMD], capture_output=True, text=True, timeout=15, env=env2)
    kill_tree(tree2)
    ck("K5", "CAPTURE running" in a.stdout and "CAPTURE NOT RUNNING" in b.stdout,
       f"ro_capture_all={a.stdout!r} ro_nightly={b.stdout!r}")

    # K6 — wait_for_capture
    answers, slept, calls = [], [], []

    def fake_map(boxes, cmd, timeout=None, **_k):
        calls.append([s for s, _ip in boxes])
        return answers.pop(0) if answers else {s: (0, "IDLE", "") for s, _ip in boxes}

    C.ssh_util.ssh_map = fake_map
    t = {"now": 0.0}
    clock = lambda: t["now"]

    def sleep(sec):
        slept.append(sec)
        t["now"] += sec
    answers[:] = [{"AMD": (0, "CAPTURING\n", ""), "NVDA": (0, "IDLE\n", "")}, {"AMD": (0, "CAPTURING\n", "")},
                  {"AMD": (0, "IDLE\n", "")}]
    with redirect_stdout(io.StringIO()):
        r_ok = C.wait_for_capture(["AMD", "NVDA"], False, budget=900, poll=30, sleep=sleep, clock=clock)
    shrink = calls[:3] == [["AMD", "NVDA"], ["AMD"], ["AMD"]]
    answers[:] = [{"AMD": (0, "CAPTURING", "")}] * 50
    t["now"] = 0.0
    slept.clear()
    with redirect_stdout(io.StringIO()):
        r_cap = C.wait_for_capture(["AMD"], False, budget=90, poll=30, sleep=sleep, clock=clock)
    answers[:] = [{"AMD": (255, "", "ssh: timeout")}]
    with redirect_stdout(io.StringIO()):
        r_mute = C.wait_for_capture(["AMD"], False, budget=900, poll=30, sleep=sleep, clock=clock)
    calls.clear()
    r_dry = C.wait_for_capture(["AMD"], True, sleep=sleep, clock=clock)
    ck("K6", r_ok == [] and shrink and r_cap == ["AMD"] and sum(slept) <= 90 and r_mute == [] and r_dry == []
       and calls == [] and C.CAPTURE_WAIT_S == 900,
       f"ok={r_ok} shrink={shrink} cap={r_cap} slept={slept} mute={r_mute} dry={r_dry} calls={calls}")

    # K7 — the takedown order
    order = []
    C.stop_services = lambda ok, dry: order.append("services")
    C.purge_verified = lambda ok, dry: order.append("purge")
    C.wait_for_capture = lambda ok, dry: order.append("capture_wait") or []
    C.instance_registry.discover = lambda ok: ({s: {"instance_id": "i-" + s} for s in ok}, None)
    C.ec2ops.stop = lambda ids: order.append("ec2_stop")
    C.ec2ops.wait_state = lambda ids, st: None
    with redirect_stdout(io.StringIO()):
        C.takedown({"AMD": {"verdict": "OK", "short": "0", "raw": ""}}, False, True)
    ck("K7", order == ["services", "purge", "capture_wait", "ec2_stop"], str(order))

    print()
    if FAILS:
        print("RED — %s" % ", ".join(FAILS))
        return 1
    print("GREEN — %d checks" % len(RAN))
    return 0


if __name__ == "__main__":
    sys.exit(main())
