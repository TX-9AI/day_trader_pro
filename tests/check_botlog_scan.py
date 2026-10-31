#!/usr/bin/env python3
"""
day_trader_pro/tests/check_botlog_scan.py  v1.0
v1.0  2026-10-31  dtp r520 / SAT.4 — THE SATURDAY BOT-LOG SCAN READS, COUNTS AND REDACTS, AND NOTHING ELSE.

  B1  the box script is read-only: no subprocess, environment, /proc, unit, .env or bootstrap access, no write,
      delete or rename (source of BOX_SCRIPT, the one thing that runs on a box)
  B2  run FOR REAL against a fixture ~/options-trader: per-day ERROR / CRITICAL / Traceback / refusal / feed / cap /
      start counts are exact, and out-of-window lines are not counted
  B3  a token- or secret-shaped string in a log line never reaches the output
  B4  only bot.log and bot.log.1..5 are read (a bot.log.bak beside them is not)
  B5  the shipped transport (echo <b64> | base64 -d | python3 - FROM TO) gives the same answer as B2
  B6  fleet.py's transcript is parsed per box; a box with no BOTLOG_JSON line (rc failure, skipped) is NOT READ,
      never a zero
  B7  a signature present this week and absent from every box last week is NEW; one present both weeks is not
  B8  the tool end to end (--fleet-output) writes botlog.json and prints NOT READ for the silent box
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import botlog_scan as B  # noqa: E402

FAILS, RAN = [], []


def ck(n, ok, msg):
    RAN.append(n)
    print(f"  {n:<4} {'PASS' if ok else 'FAIL'}  {msg}")
    if not ok:
        FAILS.append(n)


# B1 ─────────────────────────────────────────────────────────────────────────
src = B.BOX_SCRIPT
bad = [t for t in B.FORBIDDEN_ON_BOX if t in src]
opens = [l.strip() for l in src.splitlines() if "open(" in l]
ck("B1", not bad and opens and all('"r"' in l for l in opens),
   f"box script read-only: forbidden tokens {bad or 'none'}; every open() is mode \"r\" ({len(opens)})")

# fixture ─────────────────────────────────────────────────────────────────────
home = tempfile.mkdtemp(prefix="chk_botlog_")
ot = os.path.join(home, "options-trader")
os.makedirs(ot)
SECRET = "TT_REFRESH_TOKEN=eyJhbGciOiJIUzI1NiJ9abcdefghijklmnopqrstuvwxyz0123456789"
with open(os.path.join(ot, "bot.log.1"), "w") as fh:
    fh.write("2026-10-30 09:15:02 [INFO ] main: Service mode: PAPER | SPX | risk=$500/trade\n"
             "2026-11-02 09:15:01 [INFO ] main: Service mode: PAPER | SPX | risk=$500/trade\n"
             "2026-11-02 09:41:10 [INFO ] strategy.pin: [pin] REFUSED long: price 6012.40 is 0.157 EM from pin 6010\n"
             "2026-11-02 09:41:25 [INFO ] strategy.pin: [pin] REFUSED long: price 6013.10 is 0.161 EM from pin 6010\n")
with open(os.path.join(ot, "bot.log"), "w") as fh:
    fh.write("2026-11-03 10:02:00 [ERROR] execution.exit: LIVE exit 3d320e88: broker session unavailable: timeout\n"
             f"2026-11-03 10:02:01 [ERROR] data.auth: refresh failed {SECRET}\n"
             "2026-11-03 10:05:00 [WARNING] data.feed: BLIND SPX | quote 31s old | x\n"
             "2026-11-03 10:06:00 [ERROR] main: tick raised\n"
             "Traceback (most recent call last):\n"
             '  File "main.py", line 10, in run\n'
             "KeyError: 'flow_imbalance'\n"
             "2026-11-03 10:30:00 [INFO ] risk.risk_manager: Entry blocked: DAILY CATASTROPHIC LOSS CAP reached — no new entries\n"
             "2026-11-04 09:15:00 [INFO ] main: Service mode: PAPER | SPX | risk=$500/trade\n"
             "2026-11-04 11:00:00 [INFO ] main: Service mode: PAPER | SPX | risk=$500/trade\n"
             "2026-11-04 12:00:00 [CRITICAL] main: watchdog stall 120s\n"
             "2026-11-09 09:15:00 [ERROR] main: next week, out of window\n")
with open(os.path.join(ot, "bot.log.bak"), "w") as fh:
    fh.write("2026-11-03 10:00:00 [CRITICAL] main: FROM THE BAK FILE\n")

env = dict(os.environ, HOME=home)


def run_box(argv_cmd):
    r = subprocess.run(argv_cmd, capture_output=True, text=True, env=env, timeout=60)
    line = [l for l in r.stdout.splitlines() if l.startswith("BOTLOG_JSON ")]
    return (json.loads(line[0][12:]) if line else None), r


p, r = run_box([sys.executable, "-c", B.BOX_SCRIPT, "2026-11-02", "2026-11-06"])
days = (p or {}).get("days", {})
want = {"2026-11-02": {"start": 1, "refused:pin": 2},
        "2026-11-03": {"error": 3, "traceback": 1, "feed": 1, "cap": 1},
        "2026-11-04": {"start": 2, "critical": 1}}
ck("B2", days == want, f"per-day counts exact and window-bounded: {json.dumps(days, sort_keys=True)}")

blob = json.dumps(p or {})
ck("B3", p is not None and "eyJhbGci" not in blob and "abcdefghijklmnop" not in blob and "<redacted>" in blob,
   "the refresh-token text never leaves the box; it is replaced by <redacted>")
ck("B4", p is not None and p.get("files") == ["bot.log.1", "bot.log"] and "BAK FILE" not in blob,
   f"files read: {(p or {}).get('files')} (bot.log.bak ignored)")
tb = [s for s in (p or {}).get("sigs", []) if s[0] == "traceback"]
ck("B4b", len(tb) == 1 and tb[0][1].startswith("KeyError"),
   f"a Traceback is signed by its exception line: {tb[0][1] if tb else None}")

# B5 ─────────────────────────────────────────────────────────────────────────
p5, r5 = run_box(["bash", "-c", B.box_command("2026-11-02", "2026-11-06")])
ck("B5", p5 == p, f"the base64 transport gives the identical payload (rc={r5.returncode})")

# B6 ─────────────────────────────────────────────────────────────────────────
line = "BOTLOG_JSON " + json.dumps(p, sort_keys=True)
transcript = (f"Running on 3 box(es): `echo ...`   [per-box budget 180s]\n\n"
              f"── SPX (10.0.0.1) ─────────────────────────────────\n{line}\n"
              f"── QQQ (10.0.0.2) ─────────────────────────────────\n"
              + "BOTLOG_JSON " + json.dumps({"files": ["bot.log"], "days": {}, "sigs": []}) + "\n"
              f"── NVDA (10.0.0.3) ────────────────────────────────\n🚨 rc=255 ssh timeout\n"
              f"── TSLA (-) · skipped (stopped)\n\nDone. 2/3 succeeded.\n")
boxes = B.parse_fleet_output(transcript)
ck("B6", set(boxes) == {"SPX", "QQQ", "NVDA", "TSLA"} and boxes["NVDA"] is None and boxes["TSLA"] is None
   and boxes["SPX"] == p and boxes["QQQ"]["files"] == ["bot.log"],
   f"per-box parse: read {sorted(k for k, v in boxes.items() if v)}, NOT READ "
   f"{sorted(k for k, v in boxes.items() if v is None)}")

# B7 ─────────────────────────────────────────────────────────────────────────
prior = {"SPX": {"sigs": [["error", "main: tick raised", 4, "", ""]]}}
new = B.diff({"SPX": p}, prior)
new_sigs = {(c, s) for c, s, _b, _n in new}
ck("B7", ("error", "main: tick raised") not in new_sigs and ("critical", "main: watchdog stall Ns") in new_sigs
   and new and new[0][0] in ("critical", "traceback", "error"),
   f"{len(new)} new signature(s); last week's 'tick raised' is not new; the severe ones sort first")

# B8 ─────────────────────────────────────────────────────────────────────────
out = tempfile.mkdtemp(prefix="chk_botlog_out_")
tf = os.path.join(out, "transcript.txt")
open(tf, "w").write(transcript)
r8 = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "botlog_scan.py"), "--from", "2026-11-02",
                     "--to", "2026-11-06", "--out", out, "--fleet-output", tf], capture_output=True, text=True)
j = json.load(open(os.path.join(out, "botlog.json"))) if os.path.exists(os.path.join(out, "botlog.json")) else {}
ck("B8", r8.returncode == 0 and "NVDA" in r8.stdout and "NOT READ" in r8.stdout and "2/4 boxes read" in r8.stdout
   and j.get("boxes", {}).get("SPX") == p,
   f"end to end: rc={r8.returncode}, botlog.json written, the silent boxes named NOT READ")

print()
if FAILS:
    print(f"FAILED: {', '.join(FAILS)}")
    sys.exit(1)
print(f"ALL PASS ({len(RAN)})")
