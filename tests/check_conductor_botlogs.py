#!/usr/bin/env python3
"""
day_trader_pro/tests/check_conductor_botlogs.py — v1.1
v1.1  2026-11-22  dtp r576 / BOXF.1 (control's half of OTV5 r148) — NEW L7: the box command also keeps the day's
      "[flags]" start lines (OTV5 r148 logs one at every bot start: the box's effective saved settings, its file hash and
      the commit), a WARNING one with its REFUSED tail included, and still drops another day's [flags] line and a line
      that only mentions flags; the ssh budget and bounds are unchanged (L2). BORN RED on f28f5b7 (r575, v2.18).
v1.0  2026-11-22  dtp r572 / RECAP.2 — new. eod_conductor_v2 v2.18 copies each box's day of ERROR / CRITICAL /
      Traceback lines and restart markers to control (~/reviews/daily_brief/botlogs/<date>/<SYM>.txt) before the stop,
      so the 17:00 daily recap can read them with every box stopped. Nothing here touches a box: the box command runs
      under bash on a fake HOME, and ssh_map, the fleet and ec2ops are stand-ins.

  L1  the box command parses as bash and, on a fake bot.log, keeps exactly the day's ERROR and CRITICAL lines, the
      Traceback after one (its frames included) and the restart markers (STARTED / STOPPED alert lines); another day's
      error, INFO and WARNING lines are dropped; a token and a Bearer value are redacted
  L2  bounded: a 20,000-line error log yields at most BOTLOG_MAX_LINES bot.log lines and BOTLOG_MAX_BYTES bytes, the
      filter carries its own timeout, and the ssh budget per box is BOTLOG_BOX_S
  L3  copy_botlogs writes one file per box under <dir>/<SYM>.txt (header + the box's lines); an unanswered box gets
      a one-line NOT READ file; a dry run copies nothing
  L4  THE STOP NEVER WAITS ON IT: with a copy that hangs 20 s, takedown() reaches ec2ops.stop within BOTLOG_JOIN_S
      (+2 s) of the capture wait, and the hung box's file is simply not written yet; takedown() with no handle (the
      gates, fleet_reconcile) copies nothing
  L5  the order: _run_close starts the copy over every box the close saw (HELD included) before takedown(), which joins
      it after the capture wait and before ec2ops.stop
  L7  the day's "[flags]" start lines are kept (INFO and WARNING, the REFUSED tail with them); another day's [flags]
      line and an INFO line that merely mentions flags are dropped
  L6  it never reads an env file, a credential or a unit's Environment: the command reads bot.log* and the unit's
      systemd lifecycle lines only (no printenv, env, /proc, .env, systemctl show/cat, /etc/systemd)
BORN RED on b02c6b9 (r571): eod_conductor_v2 v2.17 has no botlog_cmd / copy_botlogs.

Run:  python3 tests/check_conductor_botlogs.py
"""
import io
import os
import shutil
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


LOG = """2026-11-19 15:00:00 [ERROR] main: yesterday's error
2026-11-20 09:30:01 [INFO ] alerts: ALERT: \U0001F680 OptionsBot [PAPER] STARTED | QQQ | service restart
2026-11-20 09:31:00 [INFO ] main: an ordinary line
2026-11-20 09:32:00 [ERROR] main: boom refresh_token=abc123secret and Bearer xyz.789
Traceback (most recent call last):
  File "main.py", line 1, in <module>
ValueError: bad
2026-11-20 09:33:00 [WARNING] main: a warning only
2026-11-20 10:00:00 [CRITICAL] risk: daily loss limit
2026-11-20 15:59:00 [INFO ] alerts: ALERT: \U0001F534 OptionsBot STOPPED | systemctl stop/restart
"""


def run_box(cmd, home):
    return subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=60,
                          env={"HOME": home, "PATH": "/usr/bin:/bin"})


def main():
    try:
        import eod_conductor_v2 as C
        C.botlog_cmd, C.copy_botlogs, C.finish_botlogs  # noqa: B018
    except (ImportError, AttributeError) as e:
        for n in ("L1", "L2", "L3", "L4", "L5", "L6", "L7"):
            ck(n, False, f"eod_conductor_v2 has no bot-log copy ({e})")
        print("\nRED — " + ", ".join(FAILS))
        return 1
    tmp = tempfile.mkdtemp(prefix="ckbl_")
    try:
        # L1
        home = os.path.join(tmp, "box1")
        os.makedirs(os.path.join(home, "options-trader"))
        open(os.path.join(home, "options-trader", "bot.log"), "w", encoding="utf-8").write(LOG)
        cmd = C.botlog_cmd("2026-11-20")
        r = run_box(cmd, home)
        out = r.stdout
        keep = ["OptionsBot [PAPER] STARTED", "[ERROR] main: boom", "Traceback (most recent call last)",
                'File "main.py", line 1', "ValueError: bad", "[CRITICAL] risk: daily loss limit", "OptionsBot STOPPED"]
        drop = ["yesterday's error", "an ordinary line", "a warning only", "abc123secret", "xyz.789"]
        ck("L1", subprocess.run(["bash", "-n", "-c", cmd]).returncode == 0 and r.returncode == 0
           and all(k in out for k in keep) and not [d for d in drop if d in out]
           and "refresh_token=[REDACTED]" in out and "Bearer [REDACTED]" in out,
           f"kept/dropped wrong: {out!r}")
        # L7 (v1.1) — the [flags] start lines
        home7 = os.path.join(tmp, "box7")
        os.makedirs(os.path.join(home7, "options-trader"))
        open(os.path.join(home7, "options-trader", "bot.log"), "w", encoding="utf-8").write(
            "2026-11-19 09:15:03 [INFO ] __main__: [flags] QQQ source=none (defaults) sha256=- commit=0000000000 "
            "· schema v1: no keys · differs: none\n"
            "2026-11-20 09:15:03 [INFO ] __main__: [flags] QQQ source=none (defaults) sha256=- commit=df5125207e "
            "\u00b7 schema v1: no keys \u00b7 differs: none\n"
            "2026-11-20 09:15:04 [INFO ] main: the flags were read, nothing else\n"
            "2026-11-20 11:02:00 [WARNING] main: [flags] QQQ source=deploy/box_flags/QQQ sha256=0123456789ab "
            "commit=df5125207e \u00b7 ogap=off \u00b7 differs: ogap(off, default on) \u00b7 REFUSED: line 1 "
            "ogap = 'of' is not one of on/off: ogap reads off\n")
        r7 = run_box(cmd, home7).stdout
        ck("L7", "commit=df5125207e \u00b7 schema v1: no keys" in r7 and "REFUSED: line 1 ogap = 'of'" in r7
           and "commit=0000000000" not in r7 and "nothing else" not in r7 and r7.count("[flags]") == 2,
           f"the [flags] lines were not kept as specified: {r7!r}")
        # L2
        home2 = os.path.join(tmp, "box2")
        os.makedirs(os.path.join(home2, "options-trader"))
        with open(os.path.join(home2, "options-trader", "bot.log"), "w") as fh:
            for i in range(20000):
                fh.write(f"2026-11-20 10:{i % 60:02d}:00 [ERROR] main: error number {i} " + "x" * 40 + "\n")
        r2 = run_box(cmd, home2)
        lines = [ln for ln in r2.stdout.splitlines() if "[ERROR]" in ln]
        ck("L2", len(lines) <= C.BOTLOG_MAX_LINES and len(r2.stdout.encode()) <= C.BOTLOG_MAX_BYTES
           and f"timeout {C.BOTLOG_REMOTE_S} " in cmd and f"head -c {C.BOTLOG_MAX_BYTES}" in cmd
           and C.BOTLOG_BOX_S <= 60 and C.BOTLOG_JOIN_S <= 10,
           f"{len(lines)} lines, {len(r2.stdout.encode())} bytes")

        # L3
        C.fleet.get_fleet = lambda syms: [(s, "10.0.0.%d" % i, "running") for i, s in enumerate(syms)]
        sent = []

        def fake_map(targets, command, timeout=None, **_k):
            sent.append((list(targets), command, timeout))
            return {k: ((0, "== bot.log (bot.log)\n2026-11-20 09:32:00 [ERROR] main: boom\n", "") if k != "NVDA"
                        else (255, "", "ssh: connect timed out")) for k, _ip in targets}
        C.ssh_util.ssh_map = fake_map
        od = os.path.join(tmp, "botlogs", "2026-11-20")
        with redirect_stdout(io.StringIO()):
            h = C.copy_botlogs(["AMD", "NVDA"], "2026-11-20", False, out_dir=od)
            done = C.finish_botlogs(h, wait_s=10)
            hd = C.copy_botlogs(["AMD"], "2026-11-20", True, out_dir=os.path.join(tmp, "dry"))
        a = open(os.path.join(od, "AMD.txt")).read() if os.path.exists(os.path.join(od, "AMD.txt")) else ""
        nv = open(os.path.join(od, "NVDA.txt")).read() if os.path.exists(os.path.join(od, "NVDA.txt")) else ""
        ck("L3", done and a.startswith("# AMD 2026-11-20 bot.log extract") and "[ERROR] main: boom" in a
           and nv.startswith("# NVDA 2026-11-20 NOT READ: ssh rc=255") and nv.count("\n") == 1
           and hd is None and not os.path.exists(os.path.join(tmp, "dry")) and sent and sent[0][2] == C.BOTLOG_BOX_S
           and C.BOTLOG_DIR.endswith(os.path.join("reviews", "daily_brief", "botlogs")),
           f"AMD={a[:80]!r} NVDA={nv[:80]!r} dry={hd}")

        # L4 + L5 — the takedown: a hung copy never holds the stop
        order, t = [], {}

        def slow_map(targets, command, timeout=None, **_k):
            order.append("botlog_ssh")
            time.sleep(20)
            return {}
        C.ssh_util.ssh_map = slow_map
        C.BOTLOG_DIR = os.path.join(tmp, "botlogs_td")
        C.stop_services = lambda ok, dry: order.append("services")
        C.purge_verified = lambda ok, dry: order.append("purge")

        def cap(ok, dry):
            order.append("capture_wait")
            t["cap"] = time.monotonic()
            return []
        C.wait_for_capture = cap
        C.instance_registry.discover = lambda ok: ({s: {"instance_id": "i-" + s} for s in ok}, None)

        def stop(ids):
            order.append("ec2_stop")
            t["stop"] = time.monotonic()
        C.ec2ops.stop = stop
        C.ec2ops.wait_state = lambda ids, st: None
        res = {"AMD": {"verdict": "OK", "short": "0", "raw": ""}, "TSLA": {"verdict": "SHORT", "short": "3", "raw": ""}}
        tdir = os.path.join(tmp, "botlogs_td")
        with redirect_stdout(io.StringIO()):
            C.takedown(res, False, True)                    # no handle: no copy (the gates' and fleet_reconcile's call)
            none_copied = "botlog_ssh" not in order
            del order[:]
            h = C.copy_botlogs(list(res), "2026-11-20", False, out_dir=tdir)
            order.append("botlog_start")
            C.takedown(res, False, True, botlogs=h)
        lag = t.get("stop", 99) - t.get("cap", 0)
        ck("L4", "ec2_stop" in order and lag <= C.BOTLOG_JOIN_S + 2 and none_copied
           and not os.path.exists(os.path.join(tdir, "AMD.txt")),
           f"the stop came {lag:.1f}s after the capture wait (cap {C.BOTLOG_JOIN_S}s); order {order}; "
           f"takedown without a handle copied nothing: {none_copied}")
        src = open(os.path.join(ROOT, "eod_conductor_v2.py"), encoding="utf-8").read()
        rc_body = src.split("def _run_close(", 1)[1]
        i_copy = rc_body.find("botlogs = copy_botlogs(list(results), date, dry)")
        i_take = rc_body.find("takedown(results, dry, not a.no_takedown, botlogs=botlogs)")
        td = src.split("def takedown(", 1)[1].split("\ndef ", 1)[0]
        ck("L5", 0 < i_copy < i_take and td.find("stop_services(ok, dry)") < td.find("wait_for_capture(ok, dry)")
           < td.find("finish_botlogs(botlogs)") < td.find("ec2ops.stop(ids)")
           and "list(results)" in rc_body[i_copy - 10:i_copy + 60],
           "the close starts the copy over every box it saw (HELD included) before the takedown, which joins it "
           "after the capture wait and before ec2ops.stop")

        # L6
        bad = [w for w in ("printenv", " env ", "env |", "/proc/", ".env", "systemctl show", "systemctl cat",
                           "/etc/systemd", "Environment", "EnvironmentFile") if w in cmd]
        ck("L6", not bad and "bot.log" in cmd and "journalctl -u optionsbot" in cmd and "grep -E 'systemd" in cmd,
           f"the box command names {bad}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print()
    if FAILS:
        print("RED — %s" % ", ".join(FAILS))
        return 1
    print("GREEN — %d checks" % len(RAN))
    return 0


if __name__ == "__main__":
    sys.exit(main())
