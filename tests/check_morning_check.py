#!/usr/bin/env python3
"""
day_trader_pro/tests/check_morning_check.py  v1.0
v1.0  2026-11-08  dtp r539 / TIMER.1 — the morning check (tools/morning_check.py) replaces three session crons.
No box, no Telegram: the fleet, ssh, journal, router and calendar are fakes, except M10-M12, which run the REAL
shipped command lines through bash on this host and a real throwaway git repo.
  M1   the step follows the clock: 09:19 wake, 09:50 hunt, 11:10 park
  M2   wake, all well: rc 0, one "info" line, "all GREEN"
  M3   wake reds: a stopped box, an inactive feed, a code HEAD mismatch, refusals, a TEMP pin, the 09:16 assignment
       NOT WRITTEN and a dead router are each named; rc 1; the line goes out "critical"
  M4   a box behind main by docs only is a note, not a red; a box with a different timer set is named
  M5   hunt: rows and mix counted; a box RED, rows ALL unknown, or no box answering -> critical
  M6   park: PARK_SMA50 split equity / index and HUNT_OR_EM counted again
  M7   not a trading day -> rc 0, nothing posted
  M8   the check itself raising -> rc 2 and a "COULD NOT RUN" critical line (never silent)
  M9   the units: three OnCalendar lines at 09:19 / 09:50 / 11:10 America/New_York, the service runs this tool,
       the installer retires dtp-feed-triage / dtp-regime / dtp-eod-analysis and parses
  M10  the real wake box script, shipped through bash, prints one parseable WAKE_STATUS
  M11  the real OTV5 shadow_rule_status.py, shipped the same way, prints one parseable SHADOW_STATUS
  M12  docs_only_behind on a real repo: docs-only -> True, a code file -> False
  M13  delivery: router alive -> the router outbox only; router dead -> straight to Telegram, marked, never silent
"""
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)
import morning_check as M  # noqa: E402

FAILS, RAN = [], []
TMP = tempfile.mkdtemp(prefix="check_morning_check_")


def ck(n, ok, msg):
    RAN.append(n)
    print(f"  {n:<4} {'PASS' if ok else 'FAIL'}  {msg}")
    if not ok:
        FAILS.append(n)


HEAD = "a" * 40
DAY = "2026-11-09"


def wake_rec(**kw):
    r = {"feed": "active", "bot": "active", "head": HEAD, "refused": 0, "bad502": 0, "pins": 0, "assign_age_s": 300,
         "timers": ["candle-logger.timer", "emergency-watchdog.timer", "midnight-halt.timer"]}
    r.update(kw)
    return r


def fleet_of(states):
    return lambda: [(s, "10.0.0.%d" % i, st) for i, (s, st) in enumerate(sorted(states.items()))]


def mapper(per_box, tag):
    def m(targets, command, timeout=None):
        return {s: (0, "noise\n%s %s\n" % (tag, json.dumps(per_box[s])), "") for s, _ip in targets if s in per_box}
    return m


GOOD_J = "[assign] DXLINK ASSIGNMENT written 14/14 box(es) over 2 node(s) in 1 pass(es): 1.1.1.1 x7, 2.2.2.2 x7"


def run_wake(states, recs, journal=GOOD_J, alive=True, behind=lambda a, b: False):
    posts = []
    rc = M.main(["--step", "wake", "--day", DAY], post_fn=lambda k, t: posts.append((k, t)), route_alive_fn=lambda: True,
                trading_fn=lambda d: True, fleet_fn=fleet_of(states), map_fn=mapper(recs, "WAKE_STATUS"),
                journal_fn=lambda u: journal, alive_fn=lambda: alive, main_head=HEAD, behind_fn=behind,
                report_dir=TMP)
    return rc, posts


# M1
from datetime import datetime  # noqa: E402
steps = [M.pick_step(datetime(2026, 11, 9, h, m)) for h, m in ((9, 19), (9, 50), (11, 10))]
ck("M1", steps == ["wake", "hunt", "park"], "steps %s" % steps)

# M2
st = {"AMD": "running", "SPX": "running", "QQQ": "running"}
rc, posts = run_wake(st, {s: wake_rec() for s in st})
ck("M2", rc == 0 and len(posts) == 1 and posts[0][0] == "info" and "all GREEN" in posts[0][1] and "3/3 up" in posts[0][1],
   "rc %s posts %r" % (rc, posts))

# M3
st3 = {"AMD": "stopped", "SPX": "running", "QQQ": "running", "NVDA": "running", "TSLA": "running"}
recs3 = {"SPX": wake_rec(feed="failed"), "QQQ": wake_rec(head="b" * 40), "NVDA": wake_rec(refused=3),
         "TSLA": wake_rec(pins=1)}
rc, posts = run_wake(st3, recs3, journal=GOOD_J.replace("over", "over") + " | NOT WRITTEN by 09:25: TSLA",
                     alive=False)
t = posts[0][1] if posts else ""
need = ["AMD: EC2 stopped", "SPX: candle-feed failed", "QQQ: HEAD bbbbbbb", "NVDA: 3 session-limit", "TSLA: 1 TEMP",
        "NOT WRITTEN", "alert router not alive"]
ck("M3", rc == 1 and posts and posts[0][0] == "critical" and all(n in t for n in need),
   "rc %s missing %s" % (rc, [n for n in need if n not in t]))

# M4
recs4 = {"AMD": wake_rec(head="c" * 40), "SPX": wake_rec(), "QQQ": wake_rec(timers=["candle-logger.timer",
                                                                                    "retention-purge.timer"])}
rc, posts = run_wake(st, recs4, behind=lambda a, b: True)
rep = open(os.path.join(TMP, DAY + ".txt")).read().split("== %s wake" % DAY)[-1]
ck("M4", rc == 0 and "AMD: HEAD ccccccc is behind main by docs only" in rep and "timers: QQQ differs (+retention-purge"
   in rep and "2/3 boxes share" in rep, "rc %s" % rc)


# M5 / M6
def shadow(rules):
    return {"symbol": "?", "status": "RED" if any(v["status"] == "RED" for v in rules.values()) else "GREEN",
            "rules": rules, "errors": []}


def rule(status="GREEN", dec=2, rows=2, mix=None):
    return {"status": status, "decisions": dec, "rows": rows, "log_lines": rows, "mix": mix or {"keep": rows}}


def run_shadow(step, recs, states=None):
    posts = []
    states = states or {s: "running" for s in recs}
    rc = M.main(["--step", step, "--day", DAY], post_fn=lambda k, t: posts.append((k, t)), route_alive_fn=lambda: True,
                trading_fn=lambda d: True, fleet_fn=fleet_of(states), map_fn=mapper(recs, "SHADOW_STATUS"), script="print(1)", report_dir=TMP)
    return rc, posts


good = {"AMD": shadow({"HUNT_OR_EM": rule(mix={"keep": 1, "would_skip": 1}), "PARK_SMA50": rule(dec=0, rows=0, mix={})}),
        "SPX": shadow({"HUNT_OR_EM": rule(dec=0, rows=0, mix={}), "PARK_SMA50": rule(dec=0, rows=0, mix={})})}
rc_g, p_g = run_shadow("hunt", good)
red = dict(good, SPX=shadow({"HUNT_OR_EM": rule("RED", dec=3, rows=0, mix={}), "PARK_SMA50": rule(dec=0, rows=0, mix={})}))
rc_r, p_r = run_shadow("hunt", red)
unk = {"AMD": shadow({"HUNT_OR_EM": rule(mix={"unknown": 2}), "PARK_SMA50": rule(dec=0, rows=0, mix={})})}
rc_u, p_u = run_shadow("hunt", unk)
rc_n, p_n = run_shadow("hunt", {}, states={"AMD": "running"})
ck("M5", rc_g == 0 and p_g[0][0] == "info" and "HUNT_OR_EM 2 rows on 1 box(es) (keep 1 would_skip 1)" in p_g[0][1]
   and rc_r == 1 and p_r[0][0] == "critical" and "SPX HUNT_OR_EM: 3 decisions, 0 rows" in p_r[0][1]
   and rc_u == 1 and "all 2 rows unknown" in p_u[0][1] and rc_n == 1 and "no box answered" in p_n[0][1],
   "green %r | red %r | unknown %r | none %r" % (p_g, p_r[0][1][-60:], p_u[0][1][-40:], p_n[0][1][-40:]))

park = {"AMD": shadow({"HUNT_OR_EM": rule(), "PARK_SMA50": rule(mix={"keep": 1, "would_skip": 1})}),
        "SPX": shadow({"HUNT_OR_EM": rule(dec=0, rows=0, mix={}), "PARK_SMA50": rule(mix={"keep": 2})})}
rc_p, p_p = run_shadow("park", park)
ck("M6", rc_p == 0 and "PARK_SMA50 4 rows on 2 box(es)" in p_p[0][1] and "HUNT_OR_EM 2 rows" in p_p[0][1]
   and "PARK equity keep 1 would_skip 1, index keep 2" in p_p[0][1], p_p[0][1])

# M7
posts7 = []
rc7 = M.main(["--step", "wake", "--day", "2026-11-26"], post_fn=lambda k, t: posts7.append(k), route_alive_fn=lambda: True,
             trading_fn=lambda d: False, report_dir=TMP)
ck("M7", rc7 == 0 and posts7 == [], "rc %s posts %r" % (rc7, posts7))


# M8
def boom():
    raise RuntimeError("ec2 discover failed")


posts8 = []
rc8 = M.main(["--step", "wake", "--day", DAY], post_fn=lambda k, t: posts8.append((k, t)), route_alive_fn=lambda: True, trading_fn=lambda d: True,
             fleet_fn=boom, report_dir=TMP)
ck("M8", rc8 == 2 and posts8 and posts8[0][0] == "critical" and "COULD NOT RUN" in posts8[0][1], "rc %s %r" % (rc8, posts8))

# M9
tim = open(os.path.join(ROOT, "tools", "dtp-morning-check.timer")).read()
svc = open(os.path.join(ROOT, "tools", "dtp-morning-check.service")).read()
ins = os.path.join(ROOT, "tools", "install_morning_check.sh")
cal = re.findall(r"^OnCalendar=(.+)$", tim, re.M)
bash_ok = subprocess.run(["bash", "-n", ins], capture_output=True).returncode == 0
isrc = open(ins).read()
ck("M9", cal == ["Mon..Fri *-*-* %s:00 America/New_York" % h for h in ("09:19", "09:50", "11:10")]
   and "tools/morning_check.py" in svc
   and [l for l in svc.splitlines() if l.startswith("Environment")] == ["EnvironmentFile=/home/ubuntu/day_trader_pro/.env"]
   and "for u in dtp-feed-triage dtp-regime dtp-eod-analysis; do" in isrc and bash_ok, "cal %s bash -n %s" % (cal, bash_ok))

# M10 — the real wake script through bash
cmd = M._ship("DAY = %r\n" % DAY + M.BOX_WAKE)
p = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=60)
w = M._tagged(p.stdout, "WAKE_STATUS")
ck("M10", isinstance(w, dict) and set(w) >= {"feed", "bot", "head", "refused", "bad502", "pins", "assign_age_s",
                                              "timers"} and isinstance(w["timers"], list),
   "keys %s rc %s" % (sorted(w) if w else None, p.returncode))

# M11 — the real shadow status script through bash
srs = os.path.join(M.OTV5, "tools", "shadow_rule_status.py")
if os.path.exists(srs):
    p = subprocess.run(["bash", "-c", M._ship(open(srs, "rb").read(), "--day %s --since 09:30" % DAY)],
                       capture_output=True, text=True, timeout=60)
    s11 = M._tagged(p.stdout, "SHADOW_STATUS")
    ck("M11", isinstance(s11, dict) and "rules" in s11, "parsed %s" % (sorted(s11) if s11 else p.stdout[-200:]))
else:
    ck("M11", False, "no %s" % srs)

# M12 — docs_only_behind on a real repo
g = os.path.join(TMP, "repo")
os.makedirs(os.path.join(g, "docs"))
def git(*a):
    return subprocess.run(["git", "-C", g] + list(a), capture_output=True, text=True, check=True).stdout.strip()
git("init", "-q")
git("config", "user.email", "t@t")
git("config", "user.name", "t")
open(os.path.join(g, "bot.py"), "w").write("x=1\n")
git("add", "-A"); git("commit", "-qm", "a")
a = git("rev-parse", "HEAD")
open(os.path.join(g, "docs", "B.md"), "w").write("row\n")
git("add", "-A"); git("commit", "-qm", "b")
b = git("rev-parse", "HEAD")
open(os.path.join(g, "bot.py"), "w").write("x=2\n")
git("add", "-A"); git("commit", "-qm", "c")
c = git("rev-parse", "HEAD")
ck("M12", M.docs_only_behind(a, b, tree=g) is True and M.docs_only_behind(a, c, tree=g) is False,
   "docs-only %s, code %s" % (M.docs_only_behind(a, b, tree=g), M.docs_only_behind(a, c, tree=g)))

# M13
via_r, via_d, sent = [], [], []
r1 = M.deliver("info", "x", post_fn=lambda k, t: via_r.append(k), alive_fn=lambda: True, send_fn=sent.append)
r2 = M.deliver("critical", "MORNING CHECK RED", post_fn=lambda k, t: via_d.append(k), alive_fn=lambda: False,
               send_fn=sent.append)
ck("M13", r1 == "router" and via_r == ["info"] and r2 == "direct" and via_d == [] and len(sent) == 1
   and sent[0].startswith("🔴 MORNING CHECK RED") and "router is not alive" in sent[0], "%s %s %r" % (r1, r2, sent))

print()
if FAILS:
    print("RED — %s" % ", ".join(FAILS))
    sys.exit(1)
print("GREEN — %d checks" % len(RAN))
