#!/usr/bin/env python3
"""
day_trader_pro/tools/study_dispatch.py  v1.0
v1.0  2026-11-11  dtp r549 / SAT.8 — THE SATURDAY STUDY QUEUE RUNS ON THE BOXES, IN PARALLEL.
      The operator, 2026-11-11, on the queue not fitting the brief's time: "What about just waking more boxes at
      the 0300 to run these studies in parallel?" r548 ran ~/reviews/WEEKEND_STUDIES.md on control after
      sections 1-5, one heavy job at a time, which left about 30 minutes: one or two of nine items a week.
      This tool gives every OPEN item (a sub-item such as WS.6a counts as its own) its own stopped box and a
      bounded headless `claude -p` study agent there, then collects, validates, cleans and stops.

WHAT IT DOES (`run`, started by the Saturday brief with nohup right after its wake and box reads):
  1. REFUSES during RTH (Mon-Fri 08:45-16:50 ET, the box-research-recruits window).
  2. Parses the queue. One OPEN item per box; CRM is NEVER used; a box with someone else's claim in
     ~/reviews/box_claims is skipped. It writes its own claim (O_EXCL) for every box it takes.
  3. Every power call (start / stop) goes through ec2ops (the one logged power chokepoint) under
     flock /tmp/claude-fleet.lock. Unassigned, unclaimed, non-CRM boxes that are running are stopped.
  4. Ships a kit to ~/study_<run>/<ID>/ on the box: brief.txt (the item, the queue's HOW block, the rules),
     runner.sh, ctx/ (~/reviews/*.csv, the queue file, the prior study folders the item names, text only).
     runner.sh stops optionsbot and candle-feed, reads the research token from SSM with the box's venv boto3
     (never printed, never copied from control), and runs `timeout N claude -p` with stdin closed.
  5. Polls. The moment SEAL.txt appears it is copied to control with its sha256, so the seal lives on control
     before any outcome exists. A finished item is pulled to ~/reviews/studies/<ID>_<YYYYMMDD>/ and validated:
     SEAL.txt unchanged since it was first seen, and SEAL.txt older than FROZEN.json older than RESULT.json
     (box mtimes). RESULT.json must carry n, ev, ci, window_ev, window_ci, verdict, outcome.
  6. CLEANUP ON EVERY EXIT PATH (finish, timeout, failure, exception): kill the claude session, remove
     ~/study_<run> and ~/.claude/projects/-home-ubuntu-study-<run>*, delete s3://<bucket>/study_dispatch/<run>/,
     stop the box, release the claim. A freed box takes the next queued item while time allows.
  7. Writes WEEKEND_STUDIES.md statuses itself (DONE / FORWARD; INVALID or failed items stay OPEN) and a
     state.json + summary.md in --out, which `wait` prints for the brief's sections 6 and 7.

COMMANDS:
  run      [--deadline HH:MM] [--out DIR] [--queue F] [--only SYM,..] [--max N] [--no-update-queue] [--no-stop-idle]
  wait     [--deadline HH:MM] [--out DIR]      block until `run` finishes (or the deadline), print the summary
  status   [--out DIR]
  cleanup  [--run RUN_ID]                      clean + stop + release every box claimed by study_dispatch
  plan     [--queue F]                         print the OPEN items it would dispatch, touch nothing

It lands nothing, sends nothing, and never writes a repo.
"""
import argparse
import fcntl
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timedelta

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover
    ET = None

HOME = os.path.expanduser("~")
DTP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE = os.path.join(HOME, "reviews", "WEEKEND_STUDIES.md")
STUDIES = os.path.join(HOME, "reviews", "studies")
CLAIMS = os.path.join(HOME, "reviews", "box_claims")
FLEET_LOCK = "/tmp/claude-fleet.lock"
DEFAULT_OUT = os.path.join(HOME, "study_dispatch_runs")
OWNER = "study_dispatch"
NEVER_BOXES = frozenset({"CRM"})          # runs the operator's tmux session: never woken, used or stopped
RTH_START = (8, 45)                       # box-research-recruits: done by 08:45 ET ...
RTH_END = (16, 50)                        # ... and from 16:50 ET after self-close
MARGIN_S = 25 * 60                        # every box is killed this long before the deadline
MIN_RUN_S = 45 * 60                       # an item is not started with less than this left
MAX_RUN_S = 3 * 3600                      # per-item cap
POLL_S = 60
CTX_FILE_MAX = 2 * 1024 * 1024
CTX_TOTAL_MAX = 40 * 1024 * 1024
CTX_EXT = (".md", ".txt", ".json", ".csv", ".py")
RESULT_KEYS = ("n", "ev", "ci", "window_ev", "window_ci", "verdict", "outcome")


# ── time ────────────────────────────────────────────────────────────────────────────────────────────────────
def now_et():
    return datetime.now(ET) if ET else datetime.now()


def in_rth(dt):
    """True inside the weekday window when boxes trade or wake for trading (08:45-16:50 ET, Mon-Fri)."""
    if dt.weekday() >= 5:
        return False
    hm = (dt.hour, dt.minute)
    return RTH_START <= hm < RTH_END


def deadline_dt(hhmm, base):
    h, m = (int(x) for x in hhmm.split(":"))
    d = base.replace(hour=h, minute=m, second=0, microsecond=0)
    if d <= base:
        d += timedelta(days=1)
    return d


# ── the queue file ──────────────────────────────────────────────────────────────────────────────────────────
_SEC = re.compile(r"^### (WS\.\d+)\b.*$", re.M)
_SUB = re.compile(r"^- \*\*(WS\.\d+[a-z])\b", re.M)
_STATUS = re.compile(r"^- Status: (.*)$", re.M)
_SUBSTATUS = re.compile(r"\s*\[Status: ([^\]]*)\]\s*$")


def how_block(text):
    m = re.search(r"^## HOW AN ITEM IS RUN.*?(?=^## |\Z)", text, re.M | re.S)
    return m.group(0).strip() if m else ""


def parse_queue(text):
    """-> [{id, title, status, text, parent}] for every item and sub-item under ## QUEUE (not ## DONE)."""
    q = text.split("## QUEUE", 1)[-1].split("\n## DONE", 1)[0]
    secs = list(_SEC.finditer(q))
    items = []
    for i, m in enumerate(secs):
        body = q[m.start(): secs[i + 1].start() if i + 1 < len(secs) else len(q)]
        body = body.split("\n---", 1)[0].rstrip()
        st = _STATUS.search(body)
        status = st.group(1).strip() if st else "OPEN"
        title = m.group(0)[4:].strip()
        subs = list(_SUB.finditer(body))
        if not subs:
            items.append({"id": m.group(1), "title": title, "status": status, "text": body, "parent": None})
            continue
        shared = body[: subs[0].start()].rstrip()
        for j, s in enumerate(subs):
            line_end = body.find("\n- ", s.start() + 1)
            sub_txt = body[s.start(): line_end if line_end > 0 else len(body)].rstrip()
            ss = _SUBSTATUS.search(sub_txt.splitlines()[0])
            sub_status = ss.group(1).strip() if ss else ("OPEN" if status.startswith("OPEN") else status)
            items.append({"id": s.group(1), "title": f"{title} / {s.group(1)}", "status": sub_status,
                          "text": shared + "\n" + sub_txt, "parent": m.group(1)})
    return items


def open_items(items):
    return [it for it in items if it["status"].upper().startswith("OPEN")]


def set_status(text, item_id, status):
    """Rewrite one item's status in the queue text. Sub-items carry a trailing [Status: ...] on their bullet."""
    if re.fullmatch(r"WS\.\d+", item_id):
        pat = re.compile(r"(^### " + re.escape(item_id) + r"\b.*?^- Status: )([^\n]*)", re.M | re.S)
        new, n = pat.subn(lambda m: m.group(1) + status, text, count=1)
        return new if n else text
    pat = re.compile(r"^(- \*\*" + re.escape(item_id) + r"\b[^\n]*?)(\s*\[Status: [^\]]*\])?$", re.M)
    return pat.sub(lambda m: f"{m.group(1)} [Status: {status}]", text, count=1)


def roll_parent(text, parent):
    """A parent with sub-items is DONE only when every sub-item is DONE or FORWARD."""
    subs = [it for it in parse_queue(text) if it["parent"] == parent]
    if subs and all(not it["status"].upper().startswith("OPEN") for it in subs):
        return set_status(text, parent, "DONE (all sub-items closed; see each)")
    return text


# ── claims and the fleet lock ───────────────────────────────────────────────────────────────────────────────
def claim(sym, run_id, claims_dir=None):
    claims_dir = claims_dir or CLAIMS
    os.makedirs(claims_dir, exist_ok=True)
    p = os.path.join(claims_dir, sym)
    try:
        fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w") as fh:
        fh.write(f"{OWNER} {run_id}: Saturday study queue item on this box; "
                 f"{now_et():%Y-%m-%d %H:%M:%S} ET\n")
    return True


def claim_owner(sym, claims_dir=None):
    try:
        return open(os.path.join(claims_dir or CLAIMS, sym)).read().split(":", 1)[0].strip()
    except OSError:
        return None


def release(sym, run_id, claims_dir=None):
    claims_dir = claims_dir or CLAIMS
    if claim_owner(sym, claims_dir) == f"{OWNER} {run_id}":
        os.remove(os.path.join(claims_dir, sym))
        return True
    return False


@contextmanager
def fleet_lock(path=FLEET_LOCK):
    fh = open(path, "a")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fh, fcntl.LOCK_UN)
        fh.close()


# ── the real fleet / ssh (tests pass a fake with the same methods) ──────────────────────────────────────────
class RealOps:
    def __init__(self):
        sys.path.insert(0, DTP)
        import fleet, ssh_util, ec2ops, instance_registry, config  # noqa: E401
        self.fleet_mod, self.ssh_util, self.ec2ops, self.reg, self.config = \
            fleet, ssh_util, ec2ops, instance_registry, config
        self.bucket = getattr(config, "WAREHOUSE_BUCKET", "")

    def fleet(self):
        return self.fleet_mod.get_fleet()

    def _ids(self, syms):
        mapping, _ = self.reg.discover(list(syms))
        return [mapping[s]["instance_id"] for s in syms if mapping.get(s, {}).get("instance_id")]

    def start(self, syms):
        ids = self._ids(syms)
        with fleet_lock():
            self.ec2ops.start(ids)
            self.ec2ops.wait_state(ids, "running")

    def stop(self, syms):
        ids = self._ids(syms)
        with fleet_lock():
            self.ec2ops.stop(ids)
            r = self.ec2ops.wait_state(ids, "stopped")
        return sum(1 for v in r.values() if v), len(ids)

    def ssh(self, ip, cmd, timeout=120):
        return self.ssh_util.ssh_run(ip, cmd, timeout=timeout)

    def push(self, ip, local, remote):
        return self.ssh_util.scp_push(ip, local, remote, timeout=300)

    def pull(self, ip, remote, local):
        return self.ssh_util.scp_pull(ip, remote, local, timeout=600)

    def now(self):
        return now_et()

    def sleep(self, s):
        time.sleep(s)


# ── what runs on the box ────────────────────────────────────────────────────────────────────────────────────
RUNNER = r'''#!/bin/bash
# study_dispatch runner (dtp tools/study_dispatch.py). Runs ON a recruited box: bash -l runner.sh RUN_S
export HISTFILE=/dev/null VERTIGO_UNATTENDED=1
D="$(cd "$(dirname "$0")" && pwd)"; cd "$D" || exit 1
RUN_S="${1:-3600}"
echo "START $(date -u +%FT%TZ)" > status.txt
echo $$ > runner.pid
sudo -n systemctl stop optionsbot candle-feed >/dev/null 2>&1; echo "SERVICES_STOPPED rc=$?" >> status.txt
PY=$(ls /home/ubuntu/options-trader/venv/bin/python3 /home/ubuntu/*/venv/bin/python3 2>/dev/null | head -1)
TOK=$("$PY" -c 'import boto3;print(boto3.client("ssm",region_name="us-east-2").get_parameter(Name="/otv5/claude_research_token",WithDecryption=True)["Parameter"]["Value"])' 2>/dev/null)
if [ -z "$TOK" ]; then echo "NO_TOKEN" >> status.txt; echo "exit=97 $(date -u +%FT%TZ)" >> status.txt; exit 0; fi
CL=$(command -v claude || echo "$HOME/.local/bin/claude")
mkdir -p work && cd work || exit 1
env -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN CLAUDE_CODE_OAUTH_TOKEN="$TOK" timeout "$RUN_S" "$CL" -p "$(cat ../brief.txt)" \
  --max-turns 300 --allowedTools "Bash,Read,Write,Edit,Glob,Grep" </dev/null > ../claude_out.txt 2>&1
rc=$?
unset TOK
echo "exit=$rc $(date -u +%FT%TZ)" >> ../status.txt
'''

BRIEF_HEAD = """You are a study-only research agent recruited onto one of Vertigo Capital's trading boxes for the Saturday
study queue (run {run_id}). Nobody is watching and nobody can answer a question. Do the study, write the files,
then stop.

WHERE YOU WORK: only inside {work} (your current directory). Context is in ../ctx (the queue file
WEEKEND_STUDIES.md, ~/reviews CSVs, and the prior study folders this item names). Never write anywhere else.

RULES (the operator's; not negotiable):
- READ ONLY outside your directory. No git, no systemctl, no sudo, no config or service changes, no edits to any
  file under ~/options-trader. Never write to S3. Never print or copy a token, credential or environment block.
- Data: the S3 warehouse (bucket {bucket}) read with this box's own role, via
  /home/ubuntu/options-trader/venv/bin/python and boto3. Market data is TastyTrade's (the warehouse). No
  yfinance, no other source. No TastyTrade calls from here: if data you need is missing, list it in RESULT.json
  "data_gaps" and carry on with what exists.
- Filter the OTV4TEST fleet's rows out of every warehouse measurement: sys.path.insert(0,
  "/home/ubuntu/options-trader/tests"); from warehouse_source import mainline.
- Stream; do not materialise large data. This box has little memory. Use nice -n 10 for long python runs.
- Fees go BESIDE EV, never inside it. Lead with the window EV and its interval. Say n every time.
- Blind discipline, exactly as the HOW block below says. Write SEAL.txt FIRST, with a UTC timestamp line
  ("SEALED_AT <ISO-8601 UTC>"), the sealed days and the pass bar copied from the item, BEFORE you compute any
  outcome. Then FROZEN.json (the frozen rule), then the single blind run. Never re-tune after the blind run.
- You have about {minutes} minutes. If you cannot finish, still write RESULT.json with "verdict": "INCOMPLETE".

FILES YOU MUST WRITE in {work}:
  SEAL.txt, FROZEN.json, README.md (short: method, data, caveats), and LAST of all RESULT.json:
  {{"id": "{item_id}", "n": <blind n>, "ev": <blind EV per trade>, "ci": [lo, hi], "window_ev": <EV per trade
   over the window>, "window_ci": [lo, hi], "fees_per_trade": <beside EV>, "verdict": "PASS"|"FAIL"|"FORWARD"|
   "INCOMPLETE", "outcome": "TUNE"|"TRIM"|"KEEP"|"NONE", "forward_to": "<YYYY-MM-DD or empty>",
   "one_line": "<one plain sentence>", "recommendation": "<the TUNE change or the TRIM, for the operator's yes>",
   "data_gaps": [..]}}
  FORWARD means too few fresh days to seal: write the pre-registration into README.md and set forward_to.

THE QUEUE'S RULES:
{how}

YOUR ITEM ({item_id}):
{item}
"""


def build_brief(item, how, run_id, bucket, minutes, work):
    return BRIEF_HEAD.format(run_id=run_id, work=work, bucket=bucket or "(config.WAREHOUSE_BUCKET)",
                             minutes=minutes, item_id=item["id"], how=how, item=item["text"])


def _prior_dirs(item_text, studies=None):
    studies = studies or STUDIES
    names = set(re.findall(r"studies/([A-Za-z0-9_.-]+)", item_text))
    names |= set(re.findall(r"`([a-z][a-z0-9_]*_\d{4})`", item_text))
    return sorted(n for n in names if os.path.isdir(os.path.join(studies, n)))


def build_kit(item, how, run_id, bucket, minutes, kit_dir, queue_path, studies=None):
    """Write brief.txt, runner.sh and ctx/ into kit_dir and return a .tar.gz path."""
    studies = studies or STUDIES
    work = f"/home/ubuntu/study_{run_id}/{item['id']}/work"
    os.makedirs(os.path.join(kit_dir, "ctx", "studies"), exist_ok=True)
    open(os.path.join(kit_dir, "brief.txt"), "w").write(build_brief(item, how, run_id, bucket, minutes, work))
    open(os.path.join(kit_dir, "runner.sh"), "w").write(RUNNER)
    total = 0
    srcs = [queue_path] + sorted(os.path.join(os.path.dirname(studies), f)
                                 for f in os.listdir(os.path.dirname(studies)) if f.endswith(".csv"))
    for s in srcs:
        if os.path.isfile(s):
            shutil.copy2(s, os.path.join(kit_dir, "ctx", os.path.basename(s)))
            total += os.path.getsize(s)
    for name in _prior_dirs(item["text"], studies):
        for root, _d, files in os.walk(os.path.join(studies, name)):
            for f in files:
                p = os.path.join(root, f)
                sz = os.path.getsize(p)
                if not f.endswith(CTX_EXT) or sz > CTX_FILE_MAX or total + sz > CTX_TOTAL_MAX:
                    continue
                rel = os.path.relpath(p, studies)
                os.makedirs(os.path.join(kit_dir, "ctx", "studies", os.path.dirname(rel)), exist_ok=True)
                shutil.copy2(p, os.path.join(kit_dir, "ctx", "studies", rel))
                total += sz
    tgz = kit_dir.rstrip("/") + ".tar.gz"
    with tarfile.open(tgz, "w:gz") as t:
        t.add(kit_dir, arcname=item["id"])
    return tgz


def box_root(run_id):
    return f"/home/ubuntu/study_{run_id}"


def cleanup_cmd(run_id, bucket):
    root = box_root(run_id)
    py = ("import boto3,sys;b=sys.argv[1];c=boto3.client('s3');"
          "ks=[o['Key'] for p in c.get_paginator('list_objects_v2').paginate(Bucket=b,Prefix='study_dispatch/"
          + run_id + "/') for o in p.get('Contents',[])];"
          "[c.delete_object(Bucket=b,Key=k) for k in ks];print('S3_SCRATCH_DELETED',len(ks))")
    s3 = (f"/home/ubuntu/options-trader/venv/bin/python -c {shlex.quote(py)} {shlex.quote(bucket)} 2>/dev/null "
          f"|| echo S3_SCRATCH_UNCHECKED") if bucket else "echo S3_SCRATCH_UNCHECKED"
    return (f"pkill -TERM -u ubuntu -f '[c]laude -p' ; sleep 2 ; pkill -KILL -u ubuntu -f '[c]laude -p' ; "
            f"for f in {root}/*/runner.pid; do [ -f \"$f\" ] && kill \"$(cat \"$f\")\" 2>/dev/null; done ; "
            f"rm -rf {root} ; rm -rf /home/ubuntu/.claude/projects/-home-ubuntu-study-{run_id}* ; {s3} ; "
            f"echo CLEAN_DONE ; ls -d {root} /home/ubuntu/.claude/projects/-home-ubuntu-study-{run_id}* 2>/dev/null"
            f" | sed 's/^/LEFT /'")


def file_sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None


def validate(dest, seal_sha, mtimes):
    """-> (ok, reason, result). mtimes: {name: epoch} as seen on the box before the pull."""
    rp = os.path.join(dest, "RESULT.json")
    if not os.path.exists(rp):
        return False, "no RESULT.json", None
    try:
        res = json.load(open(rp))
    except ValueError as e:
        return False, f"RESULT.json unreadable ({e})", None
    if str(res.get("verdict", "")).upper() == "INCOMPLETE":
        return False, "the agent reported INCOMPLETE", res
    missing = [k for k in RESULT_KEYS if k not in res]
    if missing:
        return False, f"RESULT.json lacks {missing}", res
    if seal_sha is None or not os.path.exists(os.path.join(dest, "SEAL.txt")):
        return False, "no SEAL.txt was seen before the result", res
    if file_sha(os.path.join(dest, "SEAL.txt")) != seal_sha:
        return False, "SEAL.txt changed after it was first copied to control", res
    if "SEALED_AT" not in open(os.path.join(dest, "SEAL.txt")).read():
        return False, "SEAL.txt has no SEALED_AT timestamp line", res
    s, f, r = mtimes.get("SEAL.txt"), mtimes.get("FROZEN.json"), mtimes.get("RESULT.json")
    if not (s and f and r and s <= f <= r):
        return False, f"file order is not SEAL <= FROZEN <= RESULT (mtimes {s}, {f}, {r})", res
    return True, "ok", res


# ── the dispatcher ──────────────────────────────────────────────────────────────────────────────────────────
class Dispatcher:
    def __init__(self, ops, deadline, out, queue_path=None, claims_dir=None, studies=None,
                 update_queue=True, stop_idle=True, only=None, max_boxes=None, bucket=None, run_id=None):
        self.ops, self.deadline, self.out = ops, deadline, out
        # resolved at call time, never bound at import: a caller (or a test) that repoints the module paths wins
        self.queue_path = queue_path or QUEUE
        self.claims_dir = claims_dir or CLAIMS
        self.studies = studies or STUDIES
        self.update_queue, self.stop_idle, self.only, self.max_boxes = update_queue, stop_idle, only, max_boxes
        self.bucket = bucket if bucket is not None else getattr(ops, "bucket", "")
        self.run_id = run_id or "sd" + ops.now().strftime("%Y%m%dT%H%M")
        self.day = ops.now().strftime("%Y%m%d")
        self.state = {"run_id": self.run_id, "deadline": deadline.isoformat(), "started": ops.now().isoformat(),
                      "finished": None, "boxes": {}, "items": {}, "not_measured": [], "log": []}
        os.makedirs(out, exist_ok=True)

    # bookkeeping
    def log(self, msg):
        line = f"{self.ops.now():%H:%M:%S} {msg}"
        self.state["log"].append(line)
        print(line, flush=True)
        self.save()

    def save(self):
        tmp = os.path.join(self.out, "state.json.tmp")
        json.dump(self.state, open(tmp, "w"), indent=1, default=str)
        os.replace(tmp, os.path.join(self.out, "state.json"))

    def left_s(self):
        return (self.deadline - self.ops.now()).total_seconds() - MARGIN_S

    # the run
    def run(self):
        if in_rth(self.ops.now()):
            self.log("REFUSED: inside the trading window (Mon-Fri 08:45-16:50 ET). Nothing touched.")
            self.state["finished"] = self.ops.now().isoformat()
            self.state["refused"] = "RTH"
            self.save()
            return 2
        text = open(self.queue_path).read()
        how = how_block(text)
        pending = open_items(parse_queue(text))
        for it in pending:
            self.state["items"][it["id"]] = {"status": "QUEUED", "title": it["title"]}
        self.log(f"run {self.run_id}: {len(pending)} OPEN item(s): {', '.join(i['id'] for i in pending) or 'none'}")
        boxes = self.pick_boxes(len(pending))
        active = {}                                   # sym -> {item, ip, started, seal_sha}
        try:
            for sym, ip in boxes:
                if not pending:
                    break
                if self.left_s() < MIN_RUN_S:
                    break
                self.launch(sym, ip, pending.pop(0), how, active)
            for it in pending:
                self.state["items"][it["id"]]["status"] = "QUEUED"
            self.save()
            while active:
                self.ops.sleep(POLL_S)
                for sym in list(active):
                    done = self.poll(sym, active[sym])
                    if done or self.left_s() <= 0:
                        a = active.pop(sym)
                        self.finish(sym, a, timed_out=not done)
                        if pending and self.left_s() >= MIN_RUN_S:
                            self.launch(sym, a["ip"], pending.pop(0), how, active, fresh=False)
                        else:
                            self.retire(sym)
        except Exception as e:                         # every exit path cleans up
            self.log(f"ERROR {type(e).__name__}: {e} — cleaning every box this run took")
            for sym in list(active):
                a = active.pop(sym)
                self.state["items"][a["item"]["id"]]["status"] = f"FAILED ({type(e).__name__})"
                self.clean_box(sym, a["ip"])
                self.retire(sym)
            raise
        finally:
            for sym, b in self.state["boxes"].items():
                if b.get("claimed") and not b.get("released"):
                    self.clean_box(sym, b["ip"])
                    self.retire(sym)
            for it in pending:
                self.state["not_measured"].append(f"{it['id']}: not started (no box or not enough time left)")
            self.state["finished"] = self.ops.now().isoformat()
            self.save()
            self.write_summary()
        return 0

    def pick_boxes(self, need):
        fleet = self.ops.fleet()
        chosen, idle = [], []
        for sym, ip, st in fleet:
            if sym in NEVER_BOXES or (self.only and sym not in self.only):
                continue
            owner = claim_owner(sym, self.claims_dir)
            if owner is not None:
                self.log(f"skip {sym}: claimed by '{owner}'")
                continue
            if len(chosen) < need and (self.max_boxes is None or len(chosen) < self.max_boxes) and ip:
                if claim(sym, self.run_id, self.claims_dir):
                    chosen.append((sym, ip, st))
                    self.state["boxes"][sym] = {"ip": ip, "claimed": True, "released": False}
                continue
            if st == "running":
                idle.append(sym)
        to_wake = [s for s, _ip, st in chosen if st != "running"]
        if to_wake:
            self.log(f"waking {len(to_wake)}: {', '.join(to_wake)}")
            self.ops.start(to_wake)
            for sym, ip, _st in chosen:                # 'running' is not 'answers ssh': wait for sshd
                for _ in range(24):
                    rc, out, _e = self.ops.ssh(ip, "echo SSH_OK", timeout=30)
                    if rc == 0 and "SSH_OK" in out:
                        break
                    self.ops.sleep(10)
        if idle and self.stop_idle:
            self.log(f"stopping {len(idle)} idle unclaimed box(es): {', '.join(idle)}")
            self.ops.stop(idle)
        self.save()
        return [(s, ip) for s, ip, _st in chosen]

    def launch(self, sym, ip, item, how, active, fresh=True):
        iid = item["id"]
        run_s = int(min(MAX_RUN_S, self.left_s()))
        st = self.state["items"][iid]
        st.update({"status": "RUNNING", "box": sym, "started": self.ops.now().isoformat(), "run_s": run_s})
        self.log(f"launch {iid} on {sym} ({run_s // 60} min)")
        kit = tempfile.mkdtemp(prefix=f"sd_{iid}_", dir=self.out)
        try:
            tgz = build_kit(item, how, self.run_id, self.bucket, run_s // 60, kit, self.queue_path, self.studies)
            root = box_root(self.run_id)
            rc, out, err = self.ops.ssh(ip, f"mkdir -p {root} && echo OK", timeout=120)
            if rc != 0:
                raise RuntimeError(f"ssh mkdir rc={rc} {err.strip()[:200]}")
            rc, out, err = self.ops.push(ip, tgz, f"study_{self.run_id}/{iid}.tar.gz")
            if rc != 0:
                raise RuntimeError(f"push rc={rc} {err.strip()[:200]}")
            rc, out, err = self.ops.ssh(ip, (
                f"cd {root} && tar xzf {iid}.tar.gz && rm -f {iid}.tar.gz && cd {iid} && "
                f"nohup setsid bash -l runner.sh {run_s} > runner.log 2>&1 < /dev/null & sleep 3; "
                f"cat {root}/{iid}/status.txt 2>/dev/null"), timeout=120)
            if rc != 0 or "START" not in out:
                raise RuntimeError(f"runner did not start rc={rc} {(out + err).strip()[:200]}")
            active[sym] = {"item": item, "ip": ip, "seal_sha": None, "started": self.ops.now()}
        except Exception as e:
            st["status"] = f"FAILED_TO_LAUNCH ({e})"
            self.state["not_measured"].append(f"{iid}: failed to launch on {sym}: {e}")
            self.log(f"launch of {iid} on {sym} FAILED: {e}")
            self.clean_box(sym, ip)
            self.retire(sym)
        finally:
            shutil.rmtree(kit, ignore_errors=True)
            if os.path.exists(kit + ".tar.gz"):
                os.remove(kit + ".tar.gz")

    def _box_dir(self, iid):
        return f"{box_root(self.run_id)}/{iid}"

    def dest(self, iid):
        return os.path.join(self.studies, f"{iid}_{self.day}")

    def poll(self, sym, a):
        iid, ip = a["item"]["id"], a["ip"]
        d = self._box_dir(iid)
        rc, out, _err = self.ops.ssh(ip, f"cat {d}/status.txt 2>/dev/null; echo ---; "
                                         f"cd {d}/work 2>/dev/null && stat -c '%n %Y' SEAL.txt FROZEN.json "
                                         f"RESULT.json 2>/dev/null", timeout=60)
        if rc != 0:
            return False
        status, _, stats = out.partition("---")
        mt = {ln.split()[0]: int(ln.split()[1]) for ln in stats.split("\n") if len(ln.split()) == 2}
        a["mtimes"] = mt
        if a["seal_sha"] is None and "SEAL.txt" in mt:
            dest = self.dest(iid)
            os.makedirs(dest, exist_ok=True)
            rc2, _o, _e = self.ops.pull(ip, f"{d.replace('/home/ubuntu/', '')}/work/SEAL.txt",
                                        os.path.join(dest, "SEAL.txt"))
            if rc2 == 0:
                a["seal_sha"] = file_sha(os.path.join(dest, "SEAL.txt"))
                self.state["items"][iid]["seal_on_control"] = self.ops.now().isoformat()
                self.log(f"{iid}: SEAL.txt copied to control ({a['seal_sha'][:12]})")
        return "exit=" in status

    def finish(self, sym, a, timed_out):
        iid, ip = a["item"]["id"], a["ip"]
        st = self.state["items"][iid]
        d = self._box_dir(iid)
        if timed_out:
            self.ops.ssh(ip, "pkill -TERM -u ubuntu -f '[c]laude -p'; sleep 5", timeout=60)
            self.poll(sym, a)                              # last look at the files after the kill
        dest = self.dest(iid)
        os.makedirs(dest, exist_ok=True)
        rel = d.replace("/home/ubuntu/", "")
        rc, _o, err = self.ops.ssh(ip, (f"cd {d} && cp -f status.txt claude_out.txt work/ 2>/dev/null; "
                                        f"tar czf {d}.pull.tgz --exclude='*.pkl' --exclude='*.parquet' "
                                        f"--exclude='*.gz' -C {d} work"), timeout=300)
        if rc == 0:
            tmp = os.path.join(self.out, f"{iid}.pull.tgz")
            rc, _o, err = self.ops.pull(ip, f"{rel}.pull.tgz", tmp)
            if rc == 0 and os.path.exists(tmp):
                seal_keep = os.path.join(self.out, f"{iid}.SEAL.control")
                if os.path.exists(os.path.join(dest, "SEAL.txt")):
                    shutil.copy2(os.path.join(dest, "SEAL.txt"), seal_keep)
                with tarfile.open(tmp) as t:
                    for m in t.getmembers():
                        if m.name.startswith("/") or ".." in m.name or not (m.isfile() or m.isdir()):
                            continue
                        m.name = m.name[len("work/"):] if m.name.startswith("work/") else m.name
                        if m.name in ("", "work"):
                            continue
                        t.extract(m, dest)
                os.remove(tmp)
                if os.path.exists(seal_keep):         # the control copy is the seal of record
                    shutil.copy2(seal_keep, os.path.join(dest, "SEAL.control.txt"))
                    os.remove(seal_keep)
        ok, why, res = validate(dest, a.get("seal_sha"), a.get("mtimes", {}))
        st.update({"folder": dest, "finished": self.ops.now().isoformat(), "timed_out": timed_out})
        if ok:
            verdict = str(res.get("verdict")).upper()
            st.update({"status": "DONE" if verdict != "FORWARD" else "FORWARD", "result": res})
            self.log(f"{iid}: {verdict} — {res.get('one_line', '')}")
            self.mark_queue(iid, res, dest)
        else:
            st.update({"status": f"INVALID ({why})", "result": res})
            self.state["not_measured"].append(f"{iid}: {why}" + (" (timed out)" if timed_out else ""))
            self.log(f"{iid}: NOT ACCEPTED — {why}")
        self.clean_box(sym, ip)

    def mark_queue(self, iid, res, dest):
        if not self.update_queue:
            return
        text = open(self.queue_path).read()
        verdict = str(res.get("verdict")).upper()
        if verdict == "FORWARD":
            status = f"FORWARD to {res.get('forward_to') or '?'} — {res.get('one_line', '')} ({dest})"
        else:
            status = (f"DONE {self.ops.now():%Y-%m-%d} — {verdict}, {res.get('outcome')}: "
                      f"{res.get('one_line', '')} ({dest})")
        new = set_status(text, iid, status)
        parent = next((it["parent"] for it in parse_queue(text) if it["id"] == iid), None)
        if parent:
            new = roll_parent(new, parent)
        if new != text:
            tmp = self.queue_path + ".tmp"
            open(tmp, "w").write(new)
            os.replace(tmp, self.queue_path)

    def clean_box(self, sym, ip):
        rc, out, err = self.ops.ssh(ip, cleanup_cmd(self.run_id, self.bucket), timeout=180)
        left = [ln for ln in out.splitlines() if ln.startswith("LEFT ")]
        b = self.state["boxes"].setdefault(sym, {"ip": ip})
        b["cleaned"] = rc == 0 and "CLEAN_DONE" in out and not left
        b["clean_out"] = " | ".join(ln for ln in out.strip().splitlines() if ln)[:300]
        b["clean_note"] = (out.strip().splitlines() or [""])[-1][:200] if not b["cleaned"] else "clean"
        if not b["cleaned"]:
            self.state["not_measured"].append(f"{sym}: cleanup unconfirmed (rc={rc}) {err.strip()[:120]}")
        self.log(f"{sym}: cleanup {'OK' if b['cleaned'] else 'UNCONFIRMED'}")

    def retire(self, sym):
        b = self.state["boxes"].setdefault(sym, {})
        if b.get("released"):
            return
        try:
            down, total = self.ops.stop([sym])
            b["stopped"] = f"{down}/{total}"
        except Exception as e:                         # still release: a stuck claim blocks every later run
            b["stopped"] = f"FAILED ({e})"
            self.state["not_measured"].append(f"{sym}: stop failed ({e})")
        b["released"] = release(sym, self.run_id, self.claims_dir)
        self.log(f"{sym}: stopped {b['stopped']}, claim released={b['released']}")

    def write_summary(self):
        lines = [f"# study_dispatch {self.run_id}", "",
                 f"started {self.state['started']}, finished {self.state['finished']}, "
                 f"deadline {self.state['deadline']}", "",
                 "| item | box | status | blind n | blind EV [95%] | window EV [95%] | verdict | outcome |",
                 "|---|---|---|---|---|---|---|---|"]
        for iid, st in self.state["items"].items():
            r = st.get("result") or {}
            lines.append(f"| {iid} | {st.get('box', '-')} | {st['status']} | {r.get('n', '-')} | "
                         f"{r.get('ev', '-')} {r.get('ci', '')} | {r.get('window_ev', '-')} {r.get('window_ci', '')}"
                         f" | {r.get('verdict', '-')} | {r.get('outcome', '-')} |")
        lines += ["", "## Recommendations (each needs the operator's yes)"]
        for iid, st in self.state["items"].items():
            r = st.get("result") or {}
            if r.get("recommendation") and st["status"] in ("DONE", "FORWARD"):
                lines.append(f"- {iid}: {r['recommendation']}")
        lines += ["", "## NOT MEASURED"] + [f"- {x}" for x in self.state["not_measured"]] + \
                 ["", "## Boxes"] + [f"- {s}: stopped {b.get('stopped')}, cleaned {b.get('cleaned')}, "
                                     f"claim released {b.get('released')}" for s, b in self.state["boxes"].items()]
        open(os.path.join(self.out, "summary.md"), "w").write("\n".join(lines) + "\n")


def cleanup_all(ops, run_filter=None, claims_dir=None):
    """Clean, stop and release every box whose claim belongs to study_dispatch (optionally one run)."""
    claims_dir = claims_dir or CLAIMS
    if in_rth(ops.now()):
        print("REFUSED: inside the trading window (Mon-Fri 08:45-16:50 ET).")
        return 2
    ips = {s: ip for s, ip, _st in ops.fleet()}
    n = 0
    for sym in sorted(os.listdir(claims_dir)) if os.path.isdir(claims_dir) else []:
        owner = claim_owner(sym, claims_dir) or ""
        if not owner.startswith(OWNER + " "):
            continue
        run_id = owner.split()[1]
        if run_filter and run_id != run_filter or sym in NEVER_BOXES or sym not in ips:
            continue
        d = Dispatcher(ops, ops.now() + timedelta(hours=1), tempfile.mkdtemp(prefix="sd_cleanup_"),
                       claims_dir=claims_dir, run_id=run_id, update_queue=False)
        d.state["boxes"][sym] = {"ip": ips[sym], "claimed": True, "released": False}
        d.clean_box(sym, ips[sym])
        d.retire(sym)
        n += 1
    print(f"cleanup: {n} box(es) cleaned, stopped and released")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("cmd", choices=("run", "wait", "status", "cleanup", "plan"))
    ap.add_argument("--deadline", default=os.environ.get("STUDY_DISPATCH_DEADLINE_ET", "07:30"))
    ap.add_argument("--out", default=os.environ.get("STUDY_DISPATCH_OUT", ""))
    ap.add_argument("--queue", default=QUEUE)
    ap.add_argument("--only", default="")
    ap.add_argument("--max", type=int, default=None)
    ap.add_argument("--run", default=None)
    ap.add_argument("--no-update-queue", action="store_true")
    ap.add_argument("--no-stop-idle", action="store_true")
    a = ap.parse_args(argv)
    out = a.out or os.path.join(DEFAULT_OUT, now_et().strftime("%Y%m%d"))
    if a.cmd == "plan":
        items = open_items(parse_queue(open(a.queue).read()))
        for it in items:
            print(f"{it['id']}: {it['title']}")
        print(f"{len(items)} OPEN item(s)")
        return 0
    if a.cmd in ("wait", "status"):
        dl = deadline_dt(a.deadline, now_et())
        p = os.path.join(out, "state.json")
        while a.cmd == "wait" and now_et() < dl - timedelta(minutes=10):
            if os.path.exists(p) and json.load(open(p)).get("finished"):
                break
            time.sleep(30)
        sm = os.path.join(out, "summary.md")
        if os.path.exists(sm):
            print(open(sm).read())
        elif os.path.exists(p):
            print(open(p).read())
        else:
            print(f"no study_dispatch state in {out}")
        fin = os.path.exists(p) and json.load(open(p)).get("finished")
        return 0 if fin else 1
    ops = RealOps()
    if a.cmd == "cleanup":
        return cleanup_all(ops, a.run)
    d = Dispatcher(ops, deadline_dt(a.deadline, ops.now()), out, queue_path=a.queue,
                   update_queue=not a.no_update_queue, stop_idle=not a.no_stop_idle,
                   only=set(x for x in a.only.split(",") if x) or None, max_boxes=a.max)
    return d.run()


if __name__ == "__main__":
    sys.exit(main())
