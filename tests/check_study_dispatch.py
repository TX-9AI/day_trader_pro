#!/usr/bin/env python3
"""
day_trader_pro/tests/check_study_dispatch.py  v1.0
v1.0  2026-11-11  dtp r549 / SAT.8. tools/study_dispatch.py, driven against a FAKE fleet and FAKE ssh (no box, no
      AWS, no token): queue parsing (sub-items are their own items), status rewrites, the RTH refusal (nothing
      touched), assignment (CRM never used, someone else's claim respected, own claims written and released, idle
      boxes stopped), the happy path (seal copied to control first, folder pulled, queue marked DONE), cleanup on
      every failure path (launch failure, no seal, a changed seal, a hang past the deadline, an exception), the
      requeue of more items than boxes, cleanup_all touching only study_dispatch claims, and the box kit (the
      brief carries the item and the HOW block; the runner closes stdin and never prints the token).
"""
import io
import json
import os
import shutil
import sys
import tarfile
import tempfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import study_dispatch as sd  # noqa: E402

ET = ZoneInfo("America/New_York")
FAILS, RAN = [], []


def ck(n, ok, msg):
    RAN.append(n)
    print(f"  {'PASS' if ok else 'FAIL'} {n}: {msg}")
    if not ok:
        FAILS.append(n)


QUEUE = """# WEEKEND STUDIES

## HOW AN ITEM IS RUN (every item, every time)
1. Write SEAL.txt first.
2. Run it ONCE.

## ADDING AN ITEM
Append it.

---

## QUEUE

### WS.1 — Hunt shorts
- Status: OPEN (added 2026-11-10)
- Why: shorts lose.
- Seal rule: after 2026-11-09. Prior studies: `~/reviews/studies/hunt_direction_1109`.

### WS.2 — Hunt time stop
- Status: DONE 2026-11-01 — FAIL
- Why: old.

### WS.6 — PARK, from Park's studies
- Status: OPEN (added 2026-11-10)
- Seal rule (all parts): after 2026-11-10.
- **WS.6a, calls vs puts.** Hypothesis: calls lose.
- **WS.6b, Gate-G.** Never against the gap.

---

## DONE
(none yet)
"""


class FakeOps:
    """Simulates the fleet, ec2ops and ssh. behaviour[sym] picks how that box's study goes."""

    def __init__(self, fleet, t0, behaviour=None, raise_on_poll=False):
        self._fleet = fleet
        self.t = t0
        self.behaviour = behaviour or {}
        self.calls = []                     # (kind, sym_or_ip, detail)
        self.polls = {}
        self.raise_on_poll = raise_on_poll
        self.bucket = "test-bucket"
        self.ip2sym = {ip: s for s, ip, _ in fleet}
        self.items_on = {}

    def fleet(self):
        return list(self._fleet)

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += timedelta(seconds=s)

    def start(self, syms):
        self.calls.append(("start", tuple(syms), ""))

    def stop(self, syms):
        self.calls.append(("stop", tuple(syms), ""))
        return len(syms), len(syms)

    def _b(self, ip):
        return self.behaviour.get(self.ip2sym[ip], "ok")

    def ssh(self, ip, cmd, timeout=120):
        sym = self.ip2sym[ip]
        self.calls.append(("ssh", sym, cmd))
        if "CLEAN_DONE" in cmd:
            return 0, "S3_SCRATCH_DELETED 0\nCLEAN_DONE\n", ""
        if cmd == "echo SSH_OK":
            return 0, "SSH_OK\n", ""
        if cmd.startswith("mkdir -p"):
            return 0, "OK\n", ""
        if "nohup setsid" in cmd:
            iid = cmd.split("tar xzf ", 1)[1].split(".tar.gz", 1)[0]
            self.items_on[sym] = iid
            return 0, "START 2026-11-14T08:31:00Z\n", ""
        if "status.txt 2>/dev/null; echo ---" in cmd:
            if self.raise_on_poll:
                raise RuntimeError("boom")
            n = self.polls[sym] = self.polls.get(sym, 0) + 1
            b = self._b(ip)
            st = "START x\n"
            stats = ""
            if b != "noseal" and n >= 1:
                stats += "SEAL.txt 100\n"
            if b in ("ok", "changed_seal") and n >= 2:
                st += "exit=0 x\n"
                stats += "FROZEN.json 200\nRESULT.json 300\n"
            if b == "noseal" and n >= 2:
                st += "exit=0 x\n"
                stats += "FROZEN.json 200\nRESULT.json 300\n"
            return 0, st + "---\n" + stats, ""
        if "tar czf" in cmd:
            return 0, "", ""
        if "pkill -TERM" in cmd:
            return 0, "", ""
        return 0, "", ""

    def push(self, ip, local, remote):
        sym = self.ip2sym[ip]
        self.calls.append(("push", sym, remote))
        if self._b(ip) == "fail_launch":
            return 1, "", "scp: connection refused"
        self.kits = getattr(self, "kits", {})
        with tarfile.open(local) as t:
            self.kits.setdefault(sym, []).append(
                {m.name: t.extractfile(m).read().decode() for m in t.getmembers() if m.isfile()})
        return 0, "", ""

    def pull(self, ip, remote, local):
        sym = self.ip2sym[ip]
        self.calls.append(("pull", sym, remote))
        iid = self.items_on.get(sym, "WS.1")
        if remote.endswith("SEAL.txt"):
            open(local, "w").write(f"SEALED_AT 2026-11-14T08:32:00Z\nsealed days: 11-10..11-13 ({iid})\n")
            return 0, "", ""
        if remote.endswith(".pull.tgz"):
            seal = f"SEALED_AT 2026-11-14T08:32:00Z\nsealed days: 11-10..11-13 ({iid})\n"
            if self._b(ip) == "changed_seal":
                seal += "edited later\n"
            res = {"id": iid, "n": 12, "ev": 41.5, "ci": [-10, 90], "window_ev": 20, "window_ci": [-5, 50],
                   "fees_per_trade": 6.0, "verdict": "FAIL", "outcome": "TRIM", "forward_to": "",
                   "one_line": "the rule did not beat the baseline", "recommendation": "trim it", "data_gaps": []}
            files = {"work/FROZEN.json": "{}", "work/RESULT.json": json.dumps(res), "work/README.md": "m"}
            if self._b(ip) != "noseal":
                files["work/SEAL.txt"] = seal
            with tarfile.open(local, "w:gz") as t:
                for name, body in files.items():
                    data = body.encode()
                    ti = tarfile.TarInfo(name)
                    ti.size = len(data)
                    t.addfile(ti, io.BytesIO(data))
            return 0, "", ""
        return 1, "", "no such file"


def env(fleet, behaviour=None, t0=None, deadline_h=4, raise_on_poll=False, claims=None, **kw):
    root = tempfile.mkdtemp(prefix="cksd_")
    q = os.path.join(root, "WEEKEND_STUDIES.md")
    open(q, "w").write(QUEUE)
    studies = os.path.join(root, "reviews", "studies")
    os.makedirs(os.path.join(studies, "hunt_direction_1109"))
    open(os.path.join(studies, "hunt_direction_1109", "BLIND_RESULT.md"), "w").write("prior result")
    open(os.path.join(root, "reviews", "hunt_side.csv"), "w").write("date,n\n")
    cl = os.path.join(root, "claims")
    os.makedirs(cl)
    for sym, owner in (claims or {}).items():
        open(os.path.join(cl, sym), "w").write(f"{owner}: busy\n")
    t0 = t0 or datetime(2026, 11, 14, 3, 30, tzinfo=ET)          # a Saturday
    ops = FakeOps(fleet, t0, behaviour, raise_on_poll)
    d = sd.Dispatcher(ops, t0 + timedelta(hours=deadline_h), os.path.join(root, "out"), queue_path=q,
                      claims_dir=cl, studies=studies, run_id="sdTEST", **kw)
    return root, q, cl, studies, ops, d


FLEET = [("AAA", "10.0.0.1", "stopped"), ("BBB", "10.0.0.2", "stopped"), ("CCC", "10.0.0.3", "running"),
         ("CRM", "10.0.0.9", "running"), ("DDD", "10.0.0.4", "stopped"), ("EEE", "10.0.0.5", "running")]

print("check_study_dispatch")

# Q1-Q3 parsing and status rewrites
items = sd.parse_queue(QUEUE)
ids = [i["id"] for i in items]
ck("Q1", ids == ["WS.1", "WS.2", "WS.6a", "WS.6b"] and
   [i["id"] for i in sd.open_items(items)] == ["WS.1", "WS.6a", "WS.6b"],
   f"sub-items are their own items and only OPEN ones dispatch: {ids}")
ck("Q2", "SEAL.txt first" in sd.how_block(QUEUE) and "ADDING" not in sd.how_block(QUEUE)
   and "Seal rule (all parts)" in items[2]["text"] and "Gate-G" not in items[2]["text"],
   "the HOW block is extracted, and a sub-item carries its parent's shared lines but not its siblings")
t2 = sd.set_status(QUEUE, "WS.6a", "DONE 2026-11-14 — FAIL")
t3 = sd.roll_parent(sd.set_status(t2, "WS.6b", "FORWARD to 2026-11-27"), "WS.6")
t4 = sd.set_status(QUEUE, "WS.1", "DONE 2026-11-14 — PASS")
ck("Q3", "[Status: DONE 2026-11-14 — FAIL]" in t2 and "WS.6 — PARK" in t2
   and [i["status"] for i in sd.parse_queue(t2) if i["id"] == "WS.6a"] == ["DONE 2026-11-14 — FAIL"]
   and "- Status: DONE (all sub-items closed" in t3
   and "- Status: DONE 2026-11-14 — PASS" in t4 and "- Status: DONE 2026-11-01 — FAIL" in t4,
   "status rewrites: a sub-item bullet, the parent roll-up, a top-level item, and no other item touched")

# R1 the RTH refusal touches nothing
root, q, cl, st, ops, d = env(FLEET, t0=datetime(2026, 11, 10, 10, 0, tzinfo=ET))
rc = d.run()
ck("R1", rc == 2 and not ops.calls and not os.listdir(cl) and open(q).read() == QUEUE,
   "inside Mon-Fri 08:45-16:50 ET it refuses: no ssh, no power call, no claim, queue untouched")
ck("R1b", sd.in_rth(datetime(2026, 11, 10, 8, 45, tzinfo=ET)) and not sd.in_rth(datetime(2026, 11, 10, 16, 50, tzinfo=ET))
   and not sd.in_rth(datetime(2026, 11, 14, 10, 0, tzinfo=ET)), "the window edges, and Saturday is open")
shutil.rmtree(root)

# A1 + H1 assignment and the happy path
root, q, cl, st, ops, d = env(FLEET, claims={"AAA": "park_cont analysis"})
rc = d.run()
touched = {c[1] if isinstance(c[1], str) else s for c in ops.calls for s in (c[1] if isinstance(c[1], tuple) else (c[1],))}
starts = [c[1] for c in ops.calls if c[0] == "start"]
stops = [s for c in ops.calls if c[0] == "stop" for s in c[1]]
ck("A1", "CRM" not in touched and "AAA" not in touched,
   "CRM is never woken, used or stopped, and a box someone else claimed is left alone")
ck("A2", starts == [("BBB", "DDD")] and set(ops.items_on) == {"BBB", "CCC", "DDD"},
   f"one item per box on unclaimed boxes; only the stopped chosen boxes are woken (start calls {starts})")
ck("A3", "EEE" in stops and open(os.path.join(cl, "AAA")).read().startswith("park_cont"),
   "the idle running box is stopped; the other owner's claim file is untouched")
ck("A4", sorted(os.listdir(cl)) == ["AAA"] and all(b.get("released") for b in d.state["boxes"].values()),
   "every claim this run wrote is released at the end")
qt = open(q).read()
ck("H1", rc == 0 and qt.count("DONE 2026-11-14 — FAIL, TRIM") == 3 and "- Status: DONE (all sub-items closed" in qt,
   "all three items finish and the queue is marked DONE (with the parent rolled up)")
f1 = os.path.join(st, "WS.1_20261114")
ck("H2", os.path.exists(os.path.join(f1, "RESULT.json")) and os.path.exists(os.path.join(f1, "SEAL.control.txt"))
   and d.state["items"]["WS.1"].get("seal_on_control"),
   "the study folder is pulled to ~/reviews/studies/<ID>_<date>, and the seal reached control before the result")
cleans = [c for c in ops.calls if c[0] == "ssh" and "CLEAN_DONE" in c[2]]
ck("H3", len(cleans) == 3 and all("rm -rf /home/ubuntu/study_sdTEST" in c[2] and
                                  "-home-ubuntu-study-sdTEST" in c[2] and "pkill" in c[2] for c in cleans)
   and set(stops) >= {"BBB", "CCC", "DDD"},
   "every box: the session killed, the work dir and the transcripts removed, then stopped")
sm = open(os.path.join(d.out, "summary.md")).read()
ck("H4", "| WS.6a |" in sm and "trim it" in sm and "## NOT MEASURED" in sm, "summary.md carries the table and the recommendations")
shutil.rmtree(root)

# F1 launch failure -> cleanup, stop, release, item stays OPEN, NOT MEASURED
root, q, cl, st, ops, d = env([("BBB", "10.0.0.2", "stopped")], behaviour={"BBB": "fail_launch"}, max_boxes=1)
d.run()
ck("F1", "FAILED_TO_LAUNCH" in d.state["items"]["WS.1"]["status"]
   and any("CLEAN_DONE" in c[2] for c in ops.calls if c[0] == "ssh")
   and ("stop", ("BBB",), "") in ops.calls and not os.listdir(cl)
   and "- Status: OPEN (added 2026-11-10)" in open(q).read().split("### WS.2")[0]
   and any(x.startswith("WS.1: failed to launch") for x in d.state["not_measured"]),
   "a launch failure cleans the box, stops it, releases the claim, leaves the item OPEN and lists it NOT MEASURED")
shutil.rmtree(root)

# F2 no seal -> INVALID, stays OPEN
root, q, cl, st, ops, d = env([("BBB", "10.0.0.2", "stopped")], behaviour={"BBB": "noseal"}, max_boxes=1)
d.run()
ck("F2", d.state["items"]["WS.1"]["status"].startswith("INVALID (no SEAL.txt")
   and "OPEN (added" in open(q).read().split("### WS.2")[0] and not os.listdir(cl),
   "a result with no seal seen first is not accepted; the item stays OPEN; the box is released")
shutil.rmtree(root)

# F3 seal edited after it was copied -> INVALID
root, q, cl, st, ops, d = env([("BBB", "10.0.0.2", "stopped")], behaviour={"BBB": "changed_seal"}, max_boxes=1)
d.run()
ck("F3", "SEAL.txt changed" in d.state["items"]["WS.1"]["status"], "a seal edited after control copied it is refused")
shutil.rmtree(root)

# F4 a hang past the deadline -> killed, cleaned, released
root, q, cl, st, ops, d = env([("BBB", "10.0.0.2", "stopped")], behaviour={"BBB": "hang"}, deadline_h=2,
                               max_boxes=1)
d.run()
ws1 = d.state["items"]["WS.1"]
ck("F4", ws1.get("timed_out") and any("pkill -TERM" in c[2] for c in ops.calls if c[0] == "ssh")
   and ops.t <= d.deadline - timedelta(seconds=sd.MARGIN_S) + timedelta(seconds=sd.POLL_S)
   and not os.listdir(cl) and ("stop", ("BBB",), "") in ops.calls,
   "a study still running at deadline minus the margin is killed, cleaned and the box stopped and released")
ck("F4b", ws1.get("run_s", 0) <= 2 * 3600 - sd.MARGIN_S, f"the per-item timeout fits the deadline ({ws1.get('run_s')} s)")
shutil.rmtree(root)

# F5 an exception mid-run still cleans and releases
root, q, cl, st, ops, d = env([("BBB", "10.0.0.2", "stopped")], raise_on_poll=True, max_boxes=1)
try:
    d.run()
    raised = False
except RuntimeError:
    raised = True
ck("F5", raised and any("CLEAN_DONE" in c[2] for c in ops.calls if c[0] == "ssh") and not os.listdir(cl)
   and d.state["finished"], "an exception propagates, but the box is cleaned, stopped and released first")
shutil.rmtree(root)

# F6 too little time left to start anything: the boxes it claimed are still cleaned, stopped and released
root, q, cl, st, ops, d = env([("BBB", "10.0.0.2", "stopped")], deadline_h=1, max_boxes=1)
d.run()
ck("F6", not [c for c in ops.calls if c[0] == "push"] and not os.listdir(cl) and ("stop", ("BBB",), "") in ops.calls
   and any(x.startswith("WS.1: not started") for x in d.state["not_measured"]),
   "with under MIN_RUN_S left nothing launches, the claimed box is released and stopped, items go NOT MEASURED")
shutil.rmtree(root)

# Q4 more items than boxes: requeued on the freed box
root, q, cl, st, ops, d = env([("BBB", "10.0.0.2", "stopped")], max_boxes=1)
d.run()
launched = [c[2] for c in ops.calls if c[0] == "push"]
ck("Q4", len(launched) == 3 and all(d.state["items"][i]["status"] == "DONE" for i in ("WS.1", "WS.6a", "WS.6b"))
   and not os.listdir(cl), "three items on one box run one after another, then the box is released")
shutil.rmtree(root)

# C1 cleanup_all: only study_dispatch claims, and never in RTH
root, q, cl, st, ops, d = env(FLEET, claims={"AAA": "park_cont analysis", "BBB": "study_dispatch sdOLD"})
ops.calls.clear()
rc = sd.cleanup_all(ops, claims_dir=cl)
ck("C1", rc == 0 and ("stop", ("BBB",), "") in ops.calls and not any(c[1] == "AAA" or c[1] == ("AAA",) for c in ops.calls)
   and sorted(os.listdir(cl)) == ["AAA"]
   and any("study_sdOLD" in c[2] for c in ops.calls if c[0] == "ssh"),
   "cleanup_all cleans, stops and releases a stale study_dispatch claim and leaves other claims alone")
ops.t = datetime(2026, 11, 10, 11, 0, tzinfo=ET)
ops.calls.clear()
ck("C2", sd.cleanup_all(ops, claims_dir=cl) == 2 and not ops.calls, "cleanup_all refuses inside the trading window")
shutil.rmtree(root)

# P1 module paths are read when the dispatcher is built, not bound at import (the 11-10 dry run found this:
#    a repointed STUDIES was ignored and the dry run's folder landed in the real ~/reviews/studies)
_tmp = tempfile.mkdtemp(prefix="cksd_p_")
_old = (sd.STUDIES, sd.CLAIMS, sd.QUEUE)
sd.STUDIES, sd.CLAIMS, sd.QUEUE = os.path.join(_tmp, "s"), os.path.join(_tmp, "c"), os.path.join(_tmp, "q.md")
_dp = sd.Dispatcher(FakeOps(FLEET, datetime(2026, 11, 14, 3, 30, tzinfo=ET)), datetime(2026, 11, 14, 7, 30, tzinfo=ET),
                    os.path.join(_tmp, "o"), run_id="sdP")
ck("P1", (_dp.studies, _dp.claims_dir, _dp.queue_path) == (sd.STUDIES, sd.CLAIMS, sd.QUEUE),
   "the studies, claims and queue paths follow the module at construction time")
sd.STUDIES, sd.CLAIMS, sd.QUEUE = _old
shutil.rmtree(_tmp)

# K1 the kit
root, q, cl, st, ops, d = env([("BBB", "10.0.0.2", "stopped")], max_boxes=1)
d.run()
kit = ops.kits["BBB"][0]
brief = next(v for k, v in kit.items() if k.endswith("brief.txt"))
runner = next(v for k, v in kit.items() if k.endswith("runner.sh"))
ck("K1", "SEALED_AT" in brief and "SEAL.txt first" in brief and "Hunt shorts" in brief and "OTV4TEST" in brief
   and "Never write to S3" in brief and "test-bucket" in brief,
   "the brief carries the item, the queue's HOW block, the seal-first rule and the read-only rules")
ck("K2", "</dev/null" in runner and "env -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN" in runner
   and "echo $TOK" not in runner and 'echo "$TOK"' not in runner and "unset TOK" in runner
   and "systemctl stop optionsbot candle-feed" in runner and "timeout \"$RUN_S\"" in runner,
   "the runner closes stdin, clears other credentials, never prints the token, stops the bot, and is time-boxed")
ck("K3", any(k.endswith("ctx/WEEKEND_STUDIES.md") for k in kit) and any(k.endswith("ctx/hunt_side.csv") for k in kit)
   and any("hunt_direction_1109/BLIND_RESULT.md" in k for k in kit),
   "the kit ships the queue, the reviews CSVs and the prior study the item names")
shutil.rmtree(root)

print()
if FAILS:
    print(f"FAILED: {', '.join(FAILS)}")
    sys.exit(1)
print(f"ALL PASS ({len(RAN)})")
