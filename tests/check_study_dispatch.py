#!/usr/bin/env python3
"""
day_trader_pro/tests/check_study_dispatch.py  v1.2
v1.2  2026-11-13  dtp r553 / SAT.9. K4: the launch command, run for real under bash through a pipe the way ssh holds
      it, returns within seconds while the runner keeps running (v1.1's AND-list `&` held the pipe until the runner
      ended; red on v1.1).
v1.1  2026-11-13  dtp r552 / SAT.9. D1-D6 the `- Depends:` second round (parsed; waits for its dependencies and runs
      on the box the last one frees, with their results and folders in its brief and kit; none passed -> DONE without
      a box; a broken dependency -> NOT RUN, stays OPEN, NOT MEASURED; a dependency already closed in the queue counts;
      a dependent ready with no active box claims a fresh one), M1-M2 the midnight-halt hold flag (set only when
      absent, cleared only when ours), AK1-AK2 the power-audit acks (one per box per ET day held, none on a fake
      without an ack file), T1-T3 the Friday wrapper and its units (bash -n, systemd-analyze verify, Fri 17:15 ET,
      the deadline, the conductor wait, the weekday guard, --dry touches nothing).
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
        self.pass_items = set()

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
                   "fees_per_trade": 6.0, "verdict": "PASS" if iid in self.pass_items else "FAIL",
                   "outcome": "TUNE" if iid in self.pass_items else "TRIM", "forward_to": "",
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


def env(fleet, behaviour=None, t0=None, deadline_h=4, raise_on_poll=False, claims=None, queue=None, **kw):
    root = tempfile.mkdtemp(prefix="cksd_")
    q = os.path.join(root, "WEEKEND_STUDIES.md")
    open(q, "w").write(queue or QUEUE)
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

# ── v1.1 ─────────────────────────────────────────────────────────────────────────────────────────────────────
DQUEUE = QUEUE.replace("""---

## DONE""", """### WS.9 — Combined gate
- Status: OPEN (added 2026-11-13)
- Depends: WS.1, WS.6a, WS.6b
- Why: combine what passed.

---

## DONE""")
ck("D1", [i.get("depends") for i in sd.parse_queue(DQUEUE) if i["id"] == "WS.9"] == [["WS.1", "WS.6a", "WS.6b"]]
   and all(not i.get("depends") for i in sd.parse_queue(DQUEUE) if i["id"] != "WS.9"),
   "a `- Depends:` line is parsed into the item's dependency list, and only that item has one")

# D2 the second round: waits, then runs on a freed box with the results in its brief and the folders in its kit
root, q, cl, st, ops, d = env([("BBB", "10.0.0.2", "stopped"), ("DDD", "10.0.0.4", "stopped")], queue=DQUEUE)
ops.pass_items = {"WS.1"}
d.run()
pushes = [c for c in ops.calls if c[0] == "push"]
order = [c[2].split("/")[-1].split(".tar.gz")[0] for c in pushes]
k9 = next(k for kits in ops.kits.values() for k in kits if any(n.startswith("WS.9/") for n in k))
b9 = next(v for n, v in k9.items() if n.endswith("brief.txt"))
ck("D2", order[-1] == "WS.9" and len(order) == 4
   and [c for c in ops.calls if c[0] == "start"] == [("start", ("BBB", "DDD"), "")]
   and d.state["items"]["WS.9"]["status"] == "DONE",
   f"WS.9 launches last, after all three dependencies, on a box already held (launch order {order})")
ck("D3", "DEPENDENCY RESULTS" in b9 and "- WS.1: PASS" in b9 and "- WS.6a: not a pass" in b9
   and "studies/WS.1_20261114" in b9 and any("ctx/studies/WS.1_20261114/RESULT.json" in n for n in k9)
   and not os.listdir(cl),
   "its brief names each dependency's verdict and folder, the folders ship in its kit, every claim is released")
shutil.rmtree(root)

# D4 none passed: DONE without a box
root, q, cl, st, ops, d = env([("BBB", "10.0.0.2", "stopped")], queue=DQUEUE, max_boxes=1)
d.run()
order = [c[2].split("/")[-1].split(".tar.gz")[0] for c in ops.calls if c[0] == "push"]
ck("D4", "WS.9" not in order and d.state["items"]["WS.9"]["status"] == "DONE"
   and "DONE 2026-11-14 — nothing passed, not run" in open(q).read() and not os.listdir(cl),
   "when no dependency PASSED the item is marked DONE 'nothing passed, not run' and never gets a box")
shutil.rmtree(root)

# D5 a broken dependency: NOT RUN, stays OPEN, NOT MEASURED
root, q, cl, st, ops, d = env([("BBB", "10.0.0.2", "stopped")], queue=DQUEUE, behaviour={"BBB": "noseal"}, max_boxes=1)
d.run()
ws9q = open(q).read().split("### WS.9")[1]
ck("D5", d.state["items"]["WS.9"]["status"].startswith("NOT RUN") and "- Status: OPEN (added 2026-11-13)" in ws9q
   and any(x.startswith("WS.9: not run") for x in d.state["not_measured"]),
   "a dependency that ends INVALID leaves the dependent OPEN, NOT RUN, and on the NOT MEASURED list with the reason")
shutil.rmtree(root)

# D6 dependencies already closed in the queue: ready at the start, claims its own box
CQ = DQUEUE.replace("- Status: OPEN (added 2026-11-10)\n- Why: shorts lose.",
                    "- Status: DONE 2026-11-13 — PASS, TUNE: skip works (/home/x/reviews/studies/WS.1_20261113)\n- Why: shorts lose.")
CQ = CQ.replace("- Depends: WS.1, WS.6a, WS.6b", "- Depends: WS.1, WS.2")
root, q, cl, st, ops, d = env([("BBB", "10.0.0.2", "stopped"), ("DDD", "10.0.0.4", "stopped")], queue=CQ)
os.makedirs(os.path.join(st, "WS.1_20261113"))
open(os.path.join(st, "WS.1_20261113", "RESULT.json"), "w").write("{}")
d.run()
k9 = next(k for kits in ops.kits.values() for k in kits if any(n.startswith("WS.9/") for n in k))
b9 = next(v for n, v in k9.items() if n.endswith("brief.txt"))
ck("D6", d.state["items"]["WS.9"]["status"] == "DONE" and "- WS.1: PASS" in b9 and "- WS.2: not a pass" in b9
   and any("ctx/studies/WS.1_20261113/RESULT.json" in n for n in k9),
   "dependencies closed in an earlier run count, from the queue's own status lines and folders")
shutil.rmtree(root)

# M1-M2 the midnight-halt hold flag
ck("M1", 'if [ ! -e "$HOLD" ]' in sd.RUNNER and "/home/ubuntu/options-trader/data/NO_MIDNIGHT_HALT" in sd.RUNNER
   and 'echo "study_dispatch' in sd.RUNNER, "the runner writes the midnight-halt hold flag only when none exists")
_cc = sd.cleanup_cmd("sdT", "b")
_box = tempfile.mkdtemp(prefix="cksd_m_")
import subprocess as _sp
def _clear(content):
    f = os.path.join(_box, "NO_MIDNIGHT_HALT")
    if content is not None:
        open(f, "w").write(content)
    i0 = _cc.index("if [ -f " + sd.BOX_HOLD_FLAG)
    cmd = _cc[i0:_cc.index("HOLD_CLEARED; fi") + len("HOLD_CLEARED; fi")]
    _sp.run(["bash", "-c", cmd.replace(sd.BOX_HOLD_FLAG, f)], capture_output=True)
    return os.path.exists(f)
ck("M2", _clear("study_dispatch 2026-11-13T22:20:00Z\n") is False and _clear("operator: keep up tonight\n") is True,
   "the cleanup removes the hold flag only when its content is study_dispatch's, never an operator's own hold")
shutil.rmtree(_box)

# AK1-AK2 power-audit acks
root, q, cl, st, ops, d = env([("BBB", "10.0.0.2", "stopped")], t0=datetime(2026, 11, 13, 23, 50, tzinfo=ET),
                               deadline_h=4, max_boxes=1)
ops.behaviour = {"BBB": "hang"}
d.ack_path = os.path.join(root, "power_ack.txt")
d.run()
acks = open(d.ack_path).read().splitlines()
ck("AK1", "BBB 2026-11-13 study_dispatch sdTEST" in "\n".join(acks) and "BBB 2026-11-14 study_dispatch sdTEST" in "\n".join(acks)
   and len(acks) == 2, f"a held box is acknowledged once per ET day it is held, across midnight ({len(acks)} lines)")
shutil.rmtree(root)
root, q, cl, st, ops, d = env([("BBB", "10.0.0.2", "stopped")], max_boxes=1)
ck("AK2", d.ack_path is None, "a fake without an ack file writes no ack (tests never touch the real file)")
shutil.rmtree(root)

# T1-T3 the Friday wrapper and its units
TOOLS = os.path.join(os.path.dirname(HERE), "tools")
fs = os.path.join(TOOLS, "friday_studies.sh")
src = open(fs).read()
ck("T1", _sp.run(["bash", "-n", fs]).returncode == 0 and "--deadline" in src and "02:30" in src
   and "study_dispatch.py" in src and "saturday_${SAT}_work" in src and 'OUT="$WORK/study_dispatch"' in src
   and "dtp-eod-conductor.service" in src and "Fri" in src,
   "friday_studies.sh parses, runs the dispatch into the Saturday brief's WORK with the 02:30 deadline, waits for the "
   "conductor and refuses off Friday evening")
_tmp = tempfile.mkdtemp(prefix="cksd_t_")
r = _sp.run(["bash", fs, "--dry"], capture_output=True, text=True,
            env=dict(os.environ, FRIDAY_STUDIES_WEEKLY=_tmp, FRIDAY_STUDIES_LEDGER=os.path.join(_tmp, "l"),
                     FRIDAY_STUDIES_NOW="2026-11-13 17:15"))
r2 = _sp.run(["bash", fs, "--dry"], capture_output=True, text=True,
             env=dict(os.environ, FRIDAY_STUDIES_WEEKLY=_tmp, FRIDAY_STUDIES_LEDGER=os.path.join(_tmp, "l"),
                      FRIDAY_STUDIES_NOW="2026-11-14 05:00"))
ck("T2", r.returncode == 0 and "saturday_2026-11-14_work/study_dispatch" in r.stdout and "deadline 02:30" in r.stdout
   and not os.path.exists(os.path.join(_tmp, "saturday_2026-11-14_work"))
   and r2.returncode == 0 and "SKIPPED" in r2.stdout,
   f"--dry names Saturday's WORK and the deadline and touches nothing; off Friday evening it skips ({r.stdout.strip()[-120:]!r})")
shutil.rmtree(_tmp)
tm = open(os.path.join(TOOLS, "dtp-study-dispatch.timer")).read()
sv = open(os.path.join(TOOLS, "dtp-study-dispatch.service")).read()
v = _sp.run(["systemd-analyze", "verify", os.path.join(TOOLS, "dtp-study-dispatch.service")], capture_output=True, text=True)
cal = _sp.run(["systemd-analyze", "calendar", "Fri *-*-* 17:15:00 America/New_York"], capture_output=True, text=True)
ck("T3", "OnCalendar=Fri *-*-* 17:15:00 America/New_York" in tm and "Persistent=false" in tm
   and "friday_studies.sh" in sv and "Environment" not in sv and "TimeoutStartSec=" in sv
   and "Fri" in cal.stdout and not [ln for ln in (v.stdout + v.stderr).splitlines()
                                    if "dtp-study-dispatch" in ln and "ExecStart" not in ln and "WorkingDirectory" not in ln],
   "the timer fires Fri 17:15 ET, never catches up after downtime (it would collide with the 03:00 brief), "
   "and the service carries no environment block")

# K4 the launch returns while the runner runs (run for real, through a pipe, as ssh holds it)
import subprocess as _sp2, time as _t2
_lr = tempfile.mkdtemp(prefix="cksd_k4_")
_kd = os.path.join(_lr, "kit", "WS.1")
os.makedirs(_kd)
open(os.path.join(_kd, "runner.sh"), "w").write('echo "START x" > status.txt; sleep 20; echo done > done.txt\n')
with tarfile.open(os.path.join(_lr, "WS.1.tar.gz"), "w:gz") as _t:
    _t.add(_kd, arcname="WS.1")
_c = sd.launch_cmd(_lr, "WS.1", 30).replace("bash -l runner.sh", "bash runner.sh")
_t0 = _t2.time()
try:
    _r = _sp2.run(["bash", "-c", _c], capture_output=True, text=True, timeout=15)
    _el, _out = _t2.time() - _t0, _r.stdout
except _sp2.TimeoutExpired:
    _el, _out = 99, ""
_alive = not os.path.exists(os.path.join(_lr, "WS.1", "done.txt"))
ck("K4", _el < 10 and "START" in _out and _alive and "&&" in _c and " & " not in _c,
   f"the launch returns in {_el:.1f} s with the runner still running and nothing backgrounded with '&'")
_sp2.run(["pkill", "-f", "sleep 20"], capture_output=True)
shutil.rmtree(_lr, ignore_errors=True)

print()
if FAILS:
    print(f"FAILED: {', '.join(FAILS)}")
    sys.exit(1)
print(f"ALL PASS ({len(RAN)})")
