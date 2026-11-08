#!/usr/bin/env python3
"""
day_trader_pro/tests/check_botlog_scan.py  v1.1
v1.1  2026-11-08  dtp r526 / SAT.5 — the fixture is stamped in UTC like the fleet's bot.log and the box runs with
      TZ=UTC; B2 counts are keyed by ET day. New:
  B9   the start-up banner (catastrophic_loss_cap=) is a START only, never a cap; a real CAP HIT is a cap
  B10  "refused=False" (a BLIND BARS_STALE field) is a feed line, never a refusal
  B11  the ORB engine's "[orb] ... snapshot is STALE ... re-armed" note is not a feed fault
  B12  lines are keyed by ET day and clock: 03:00 UTC 11-07 is 11-06 22:00 ET (in the window); 04:30 UTC 11-02 is
       11-01 23:30 ET (out); 13:31 UTC 10-30 is 09:31 EDT (DST)
  B13  every refusal class the 11-07 sit-out trace needed is named: commit, sizing:<reason>, entry_end, orb_break,
       gate:<Strategy>@<cond> (a STILL BLOCKED repeat is not counted), afd, park_starved, no_chain,
       pin_exempt_would_refuse, other:<tag>
  B14  each day carries its ET start times; a start inside 09:30-16:00 ET counts start_rth, the 09:15 wake does not
  B15  a saved v1.0 payload re-reads true: its banner "cap" signatures leave the cap column (0) and its engine-note
       "feed" lines leave the feed column
  B16  --by-day prints each box-day's refusal classes and starts
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
    fh.write("2026-10-30 13:15:02 [INFO ] main: Service mode: PAPER | SPX | risk=$500/trade | catastrophic_loss_cap=$2000 realized net\n"
             "2026-11-02 04:30:00 [ERROR] main: 11-01 23:30 ET, out of window\n"
             "2026-11-02 14:15:01 [INFO ] main: Service mode: PAPER | SPX | risk=$500/trade | catastrophic_loss_cap=$2000 realized net\n"
             "2026-11-02 14:41:10 [INFO ] __main__: [pin] REFUSED LiquidityHunt: price 6012.40 is 0.157 EM from pin 6010\n"
             "2026-11-02 14:41:25 [INFO ] __main__: [pin] REFUSED LiquidityHunt: price 6013.10 is 0.161 EM from pin 6010\n")
with open(os.path.join(ot, "bot.log"), "w") as fh:
    fh.write("2026-11-03 15:02:00 [ERROR] execution.exit: LIVE exit 3d320e88: broker session unavailable: timeout\n"
             f"2026-11-03 15:02:01 [ERROR] data.auth: refresh failed {SECRET}\n"
             "2026-11-03 15:05:00 [WARNING] data.market_data: BLIND BARS_STALE | SPX 1m | newest_bar=x age_s=40 limit_s=30 bars=3 refused=False\n"
             "2026-11-03 15:06:00 [ERROR] main: tick raised\n"
             "Traceback (most recent call last):\n"
             '  File "main.py", line 10, in run\n'
             "KeyError: 'flow_imbalance'\n"
             "2026-11-03 15:07:00 [INFO ] __main__: [orb] the tick's ORB snapshot is STALE (ctx=INVALIDATED engine=WAITING_FOR_BREAK) — the engine re-armed\n"
             "2026-11-03 15:30:00 [WARNING] risk.risk_manager: \U0001F6D1 [SPX] DAILY CATASTROPHIC LOSS CAP HIT: day realized $-2100 <= -$2000. Halting NEW entries\n"
             "2026-11-04 14:15:00 [INFO ] main: Service mode: PAPER | SPX | risk=$500/trade | catastrophic_loss_cap=$2000 realized net\n"
             "2026-11-04 16:00:00 [INFO ] main: Service mode: PAPER | SPX | risk=$500/trade | catastrophic_loss_cap=$2000 realized net\n"
             "2026-11-04 17:00:00 [CRITICAL] main: watchdog stall 120s\n"
             "2026-11-05 14:42:00 [INFO ] analysis.commitment: [commit] BLOCKED LiquidityHunt short - the short side is ABANDONED (COMMIT.2; recorded with the would-be order)\n"
             "2026-11-05 14:42:15 [INFO ] analysis.commitment: [commit] BLOCKED LiquidityHunt short - the short side is ABANDONED (COMMIT.2; recorded with the would-be order)\n"
             "2026-11-05 14:43:00 [INFO ] __main__: Sizing rejected: insufficient_capital: need $1340.00/contract, risk=$1050.00\n"
             "2026-11-05 15:47:00 [INFO ] __main__: [observe] LOG-ONLY RunawayContinuation long 1 @ 2.10 stop 1.00 - pin would pass (0.4 EM from 300) - NOT executed (past its entry end; OBS.1)\n"
             "2026-11-05 14:37:00 [INFO ] analysis.orb_engine: ORB break REFUSED: 2026-11-05 09:35: break candle's low 230.1 is outside the range (above 229) — not a valid setup\n"
             "2026-11-05 16:01:00 [INFO ] analysis.gate_report: [gate] PARK BLOCKED at pair_agrees — not this session\n"
             "2026-11-05 16:06:00 [INFO ] analysis.gate_report: [gate] PARK STILL BLOCKED at pair_agrees for 5 min\n"
             "2026-11-05 19:00:00 [INFO ] __main__: [afd] pre-dispatch: long-debit blocked past 14:00 (orb=True runaway=True)\n"
             "2026-11-05 16:01:30 [WARNING] strategy.park_plan: [park] commitment gate STARVED on CVX: no 10:59 bar - no PARK on this equity (fails closed)\n"
             "2026-11-05 15:10:00 [WARNING] __main__: Could not fetch options chain — skipping entry attempt\n"
             "2026-11-05 16:01:40 [INFO ] __main__: [pin] PARK NOT gated (PIN_EXEMPT) — the gate would have REFUSED (0.1 EM)\n"
             "2026-11-05 14:31:00 [INFO ] __main__: [plans] Runaway entry blocked: opening range still forming (<09:35)\n"
             "2026-11-07 03:00:00 [ERROR] main: 11-06 22:00 ET, inside the window\n"
             "2026-11-07 06:00:00 [ERROR] main: 11-07 01:00 ET, out of window\n"
             "2026-11-09 14:15:00 [ERROR] main: next week, out of window\n")
with open(os.path.join(ot, "bot.log.bak"), "w") as fh:
    fh.write("2026-11-03 15:00:00 [CRITICAL] main: FROM THE BAK FILE\n")

env = dict(os.environ, HOME=home, TZ="UTC")


def run_box(argv_cmd):
    r = subprocess.run(argv_cmd, capture_output=True, text=True, env=env, timeout=60)
    line = [l for l in r.stdout.splitlines() if l.startswith("BOTLOG_JSON ")]
    return (json.loads(line[0][12:]) if line else None), r


p, r = run_box([sys.executable, "-c", B.BOX_SCRIPT, "2026-11-02", "2026-11-06"])
days = (p or {}).get("days", {})
want = {"2026-11-02": {"start": 1, "refused:pin": 2},
        "2026-11-03": {"error": 3, "traceback": 1, "feed": 1, "cap": 1},
        "2026-11-04": {"start": 2, "start_rth": 1, "critical": 1},
        "2026-11-05": {"refused:commit": 2, "refused:sizing:insufficient_capital": 1, "refused:entry_end": 1,
                       "refused:orb_break": 1, "refused:gate:PARK@pair_agrees": 1, "refused:afd": 1,
                       "refused:park_starved": 1, "refused:no_chain": 1, "refused:pin_exempt_would_refuse": 1,
                       "refused:other:plans": 1},
        "2026-11-06": {"error": 1}}
ck("B2", days == want, f"per-day counts exact and window-bounded: {json.dumps(days, sort_keys=True)}")

blob = json.dumps(p or {})
ck("B3", p is not None and "eyJhbGci" not in blob and "abcdefghijklmnop" not in blob and "<redacted>" in blob,
   "the refresh-token text never leaves the box; it is replaced by <redacted>")
ck("B4", p is not None and p.get("files") == ["bot.log.1", "bot.log"] and "BAK FILE" not in blob,
   f"files read: {(p or {}).get('files')} (bot.log.bak ignored)")
tb = [s for s in (p or {}).get("sigs", []) if s[0] == "traceback"]
ck("B4b", len(tb) == 1 and tb[0][1].startswith("KeyError"),
   f"a Traceback is signed by its exception line: {tb[0][1] if tb else None}")

# B9-B14 ─────────────────────────────────────────────────────────────────────
capsig = [x for x in (p or {}).get("sigs", []) if x[0] == "cap"]
ck("B9", days.get("2026-11-02", {}).get("cap") is None and days.get("2026-11-04", {}).get("start") == 2
   and len(capsig) == 1 and "CAP HIT" in capsig[0][1],
   f"the banner is a start only; the one cap is the CAP HIT line: {[x[1][:50] for x in capsig]}")
ck("B10", "refused:other:untagged" not in json.dumps(days) and days.get("2026-11-03", {}).get("feed") == 1,
   "refused=False is a feed field, not a refusal")
feedsig = [x[1] for x in (p or {}).get("sigs", []) if x[0] == "feed"]
ck("B11", not any("snapshot is STALE" in f for f in feedsig), f"the engine note is not feed: {feedsig}")
st = (p or {}).get("starts", {})
ck("B12", "2026-11-06" in days and "2026-11-01" not in days and days.get("2026-11-06") == {"error": 1}
   and st.get("2026-11-02") == ["09:15"],
   f"ET keying: 22:00 ET 11-06 in, 23:30 ET 11-01 out, 01:00 ET 11-07 out; 14:15 UTC -> 09:15 ET ({st.get('2026-11-02')})")
ck("B13", days.get("2026-11-05") == want["2026-11-05"], "every sit-out refusal class named; STILL BLOCKED not counted")
ck("B14", st.get("2026-11-04") == ["09:15", "11:00"] and days["2026-11-04"].get("start_rth") == 1
   and "start_rth" not in days.get("2026-11-02", {}),
   f"starts per day {st}; only the 11:00 ET start is inside RTH")
dst_ns = {}
exec(compile(B.BOX_SCRIPT.split("days, sigs, files, starts")[0].replace(
    "FROM, TO = sys.argv[1], sys.argv[2]", "FROM, TO = '', ''"), "box", "exec"), dst_ns)
os.environ["TZ"] = "UTC"
import time as _t
_t.tzset()
ck("B12b", dst_ns["to_et"]("2026-10-30", "13:31:00") == ("2026-10-30", "09:31:00")
   and dst_ns["to_et"]("2026-11-02", "14:31:00") == ("2026-11-02", "09:31:00"),
   "EDT before 11-01 (UTC-4), EST after (UTC-5)")

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

# B15 ────────────────────────────────────────────────────────────────────────
v1 = {"files": ["bot.log"], "days": {"2026-11-02": {"cap": 3, "start": 2, "feed": 5, "refused:other": 3}},
      "sigs": [["cap", "__main__: Service mode: PAPER | SPX | risk=N/trade | catastrophic_loss_cap=N realized net", 2, "", ""],
               ["feed", "__main__: [orb] the tick's ORB snapshot is STALE (ctx=INVALIDATED engine=W) — the engine re-armed", 4, "", ""],
               ["feed", "data.market_data: BLIND BARS_STALE | SPX Nm | age_s=N refused=False", 1, "", ""],
               ["refused:other", "data.market_data: BLIND BARS_STALE | SPX Nm | age_s=N refused=False", 1, "", ""],
               ["refused:other", "__main__: [plans] Runaway entry blocked: opening range still forming", 2, "", ""]]}
u = B.upgrade_v1(v1)
ck("B15", u["cap"] == 0 and u["feed"] == 1 and u["refused:other"] == 2 and u["start"] == 2 and u.get("_v1"),
   f"v1.0 payload re-read: cap {u['cap']} (was 3: the banner, one signature row beyond the saved top 40), feed {u['feed']} (was 5), refusals {u['refused:other']}")

# B16 ────────────────────────────────────────────────────────────────────────
bd = B.by_day({"SPX": p, "NVDA": None})
ck("B16", any("SPX    2026-11-05" in l and "commit 2" in l and "sizing:insufficient_capital 1" in l for l in bd)
   and any(l.startswith("NVDA") and "NOT READ" in l for l in bd)
   and any("2026-11-04  starts 09:15,11:00" in l for l in bd),
   f"--by-day: {len(bd)} lines; SPX 11-05 names commit and sizing; NVDA NOT READ")

print()
if FAILS:
    print(f"FAILED: {', '.join(FAILS)}")
    sys.exit(1)
print(f"ALL PASS ({len(RAN)})")
