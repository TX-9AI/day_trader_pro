#!/usr/bin/env python3
"""
day_trader_pro/tests/check_daily_recap.py  v1.6
v1.6  2026-11-23  dtp r580 / RECAP.3 + CAL.1 (cash_books v1.4, daily_brief v1.5, the prompt v1.8). R11 wants daily_brief
      v1.5. NEW:
  R20 the scoreboard prints its size basis: score() carries "sizes" (QQQ $1,050; SPX $4,200 from 2026-11-23, was
      $5,000), the md prints the "Entry sizes" line, figures() holds 1050, 4200 and 5000, so a commentary naming the SPX
      size change is kept; a commentary quoting a setup's FACTS day figure the scoreboard never printed (the 11-23 case:
      the Runaway's +$127) is still withheld; the prompt says FACTS day figures never go in this commentary and to use
      "The day" rows. BORN RED on 613fb1d (the 11-23 commentary withheld for $4,200 and $5,000).
  R22 the PDF's cash re-scale is date-aware: daily_brief.cash_budget is SPX $5,000 on 2026-11-20, $4,200 on 2026-11-23
      and after, QQQ $1,050 on both; compute() and section 5's sizing line call it (no flat CASH_BUDGET[...] read left)
  R21 the PDF has section 7, the schedule, from tools/calendar_view.py (build, table_rows, the load summary, NOT READ
      on a failure)
  R7 (fixed) the copy of the real queue renames the real 11-23 recap items' markers before the fixture appends as
      2026-11-23 (red on 613fb1d since the 11-23 recap queued WS.38-WS.39: the fixture's P1 and P2 read as already
      appended)
v1.5  2026-11-22  dtp r578 / CAP.11 (daily_recap v1.5, daily_brief v1.4, the prompt v1.7). R11 wants daily_brief v1.4. The
      as-cash context block, the brief's extras lines and the prompt's rule are pinned by tests/check_as_cash.py A7-A9.
v1.4  2026-11-22  dtp r576 / BOXF.1 (daily_recap v1.4, the prompt v1.5). NEW:
  R19 the Box flags block: from the conductor's extracts (each box's LAST [flags] line of the day) and a stand-in OTV5
      show tool (--otv5 on a scratch tree): a default box is listed plainly, a box with a difference and a REFUSED tail
      names both, a box whose HEAD file hash or values differ is PENDING, a box with no [flags] line is NOT SEEN, a box
      that restarted reads its last line; all-default boxes read "all defaults on N box(es)"; the show tool runs once,
      as `python3 -I ... --json`, with an env of PATH/HOME/LANG only (no OT_ / TT_ key reaches it); a missing show tool
      reads HEAD NOT READ; the context names no Environment, token or account; the prompt quotes the block, report only
v1.3  2026-11-22  dtp r575 / HALF.2 + RWATCH.1 (daily_recap v1.3, daily_recap.sh v1.2, the prompt v1.4, daily_brief
      v1.3). R11 wants daily_brief v1.3; R15's PARA_KEYS anchor names "runaway_watch" before "sources". NEW:
  R17 a 13:00 half day is a non-trading day (the operator, 2026-11-22: "Yes, just treat them as bank holidays. No
      trading."): the 11-27 recap still runs (R2), its context opens with the HALF DAY block (11-23's does not), every
      proposal on 11-27 is refused by name and nothing is queued (the same notes on 11-23 queue), the PDF code states
      the ruling under the title and in section 3 and names a half-day trade as a DEFECT, and the prompt says zero
      trades is expected, never a defect, never a study
  R18 the Runaway equity watch: context writes the scorer's runaway_watch.md / .json and names each watch status; a
      commentary quoting a figure the scorer did not print, or saying "paper size", is withheld (append records
      runaway_watch_withheld), a commentary quoting it is kept; the PDF has section 5c from tools/runaway_watch.py with
      a trend line per equity; the wrapper passes RWATCH and --runaway-watch; the prompt carries the report-only rules
v1.2  2026-11-22  dtp r572 / PREREG amendment 1. NEW R16: a C1-C4 commentary that names the two best trades (or a book
      "dependent on its best trades") without the two worst beside them is withheld, one that gives both is kept; the
      PDF's 5b column prints ex top-2 and ex bottom-2 together; the prompt says both or neither, never a qualifier.
v1.1  2026-11-22  dtp r572 / SD.3 + RECAP.2 + CASHBOOK.1 (daily_recap v1.2, daily_recap.sh v1.1, the prompt v1.2,
      daily_brief v1.2). The fixture proposals carry "setup" (now required). R11 wants daily_brief v1.2. NEW:
  R12 a proposal's setup: required, read by the dispatcher's own parser (an unknown or miscased name is refused), the
      appended item carries `- Setup: <names>` under its Status and reads tier 0 for PARK / Runaway; over the daily
      cap the PARK / Runaway proposals are admitted first
  R13 no duplicate study: context lists the DONE items' ids and titles; the validator (with the queue) refuses an
      exact or near duplicate (word sets equal, or Jaccard >= 0.8) of an OPEN, FORWARD or DONE title and accepts a
      distinct one; an item's own earlier append is not its duplicate (a re-run appends nothing)
  R14 bot logs: context counts each box's ERROR / CRITICAL / Traceback / restart lines from the conductor's extracts
      and names a NOT READ box; the wrapper passes BOTLOGS and --botlogs; the prompt reads them (no more "needs a box
      read")
  R15 the cash books: context writes the scorer's cash_books.md / .json; a commentary quoting a figure the scorer did
      not print, or saying "paper size", is withheld (append records cash_books_withheld and drops it), a commentary
      quoting the scorer is kept; the PDF has section 5b from cash_books; the prompt carries the report-only rules
v1.0  2026-11-21  dtp r569 / RECAP.1 — THE DAILY RECAP PDF RUNS FROM A TIMER (tools/daily_recap.sh, daily_recap.py,
      daily_recap.prompt, daily_brief.py, dtp-daily-recap.{service,timer}, install_daily_recap.sh) AND THE FRIDAY
      DISPATCH WAITS FOR IT (tools/friday_studies.sh v1.2). The operator, 2026-11-21: "Yes, we are going to begin
      firming up our system, our trading & our analysis". Everything below runs the real scripts with a fake claude, a
      fake brief python, a fake systemctl and a fake page, in a scratch tree: nothing reaches the real queue, the
      real ~/reviews, a box or the operator.
  R1  the units: the service verifies, its ExecStart is the landed daily_recap.sh, it carries no Environment; the timer
      elapses only Mon-Fri 17:00 ET across a DST change and is Persistent; the installer parses, installs exactly
      these two units and builds the brief's venv OUTSIDE the repo (/home/ubuntu/venvs/daily_brief)
  R2  daily_recap.py plan: a weekend and a holiday (11-26) skip, a full day is due at 16:40 ET, the 11-27 half day at
      13:40, not before; --day refuses a holiday and a session not yet closed, accepts a closed one
  R3  the wrapper on a Saturday and on 11-26 skips: exit 0, a SKIPPED day=<date> ledger line, no session, no PDF
  R4  the wrapper waits for the nightly review (its file AND its service no longer running) before the session, and a
      review that never comes is waited for only up to the cap, the session told it is MISSING
  R5  it never runs twice for a day: a second run with the PDF present stands down without a session; a run while
      another holds the lock stands down; valid notes already written are reused without a session
  R6  it writes only inside its allowed paths (notes dir, output dir, the queue + its .bak, its ledger/log, its WORK
      root) and removes its WORK dir; the session runs isolated (--session-id, never --continue), unattended
      (VERTIGO_UNATTENDED=1), with TMPDIR in its WORK dir; a session that edits the queue has it restored
  R7  the study append keeps the queue parseable: the accepted proposals become OPEN items with the next free,
      unique ids (study_dispatch.parse_queue on the result, on a fixture AND on a copy of the real queue when it is
      readable), inserted before "## DONE", a .bak first; a proposal with a resting take-profit, a missing field or
      over the daily cap is refused by name and never queued; a re-run appends nothing
  R8  the notice is ONE line through the injected router post: the day, the PDF, P&L at the mark, fees beside, the
      queued ids and the maintenance id with weekday/Sunday; validate refuses a bad 'when'
  R9  friday_studies.sh starts the dispatch only after today's recap ledger line (it waits while the recap runs), does
      not wait for a recap that is not installed, and goes ahead at the cap
  R10 the prompt carries the operator's rules (mark only, fees beside, mainline, TastyTrade only, retired strategies,
      resting take-profits closed, no knobs, never log-only, never edit the queue, one maintenance, weekday/Sunday)
  R11 the generator is in the repo (tools/daily_brief.py v1.1, compiles), its notes default under
      ~/reviews/daily_brief/notes, no venv inside the repo, and it takes --facts / --summary-json
"""
import json
import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOLS = os.path.join(ROOT, "tools")
sys.path.insert(0, TOOLS)
sys.path.insert(0, ROOT)
ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")
FAILS, RAN = [], []
TMP = tempfile.mkdtemp(prefix="check_daily_recap_")
WRAP = os.path.join(TOOLS, "daily_recap.sh")
FRI = os.path.join(TOOLS, "friday_studies.sh")
HELPER = os.path.join(TOOLS, "daily_recap.py")


def ck(n, ok, msg):
    RAN.append(n)
    print(f"  {n:<4} {'PASS' if ok else 'FAIL'}  {msg}")
    if not ok:
        FAILS.append(n)


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def write(p, s, mode=None):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(s)
    if mode:
        os.chmod(p, mode)


# ── R1 ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
svc = os.path.join(TOOLS, "dtp-daily-recap.service")
tmr = os.path.join(TOOLS, "dtp-daily-recap.timer")
vdir = os.path.join(TMP, "units")
os.makedirs(vdir)
for u in (svc, tmr):
    shutil.copy(u, vdir)
r = subprocess.run(["systemd-analyze", "verify", os.path.join(vdir, "dtp-daily-recap.service")], capture_output=True,
                   text=True)
ours = [l for l in (r.stdout + r.stderr).splitlines() if "daily-recap" in l]
sv = read(svc)
ex = re.search(r"^ExecStart=(.*)$", sv, re.M).group(1)


def elapses(spec, base):
    out = subprocess.run(["systemd-analyze", "calendar", "--iterations=12", "--base-time=" + base, spec],
                         capture_output=True, text=True, env=dict(os.environ, TZ="UTC")).stdout
    return [datetime.strptime(m, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC).astimezone(ET)
            for m in re.findall(r"(?:Next elapse|Iteration #\d+): \w{3} (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) UTC", out)]


tt = read(tmr)
specs = re.findall(r"^OnCalendar=(.*)$", tt, re.M)
hits = [t for s in specs for b in ("2026-11-05 12:00:00 UTC", "2027-03-10 12:00:00 UTC") for t in elapses(s, b)]
hm = sorted({t.strftime("%H:%M") for t in hits})
inst = read(os.path.join(TOOLS, "install_daily_recap.sh"))
inst_units = re.findall(r"for u in ([^;]+); do", inst)
ok1 = (r.returncode == 0 and not ours and ex == "/bin/bash /home/ubuntu/day_trader_pro/tools/daily_recap.sh"
       and "Environment" not in sv and "TimeoutStartSec=" in sv
       and hm == ["17:00"] and all(t.weekday() < 5 for t in hits) and len(hits) >= 20
       and any(t.utcoffset() == timedelta(hours=-4) for t in hits)
       and any(t.utcoffset() == timedelta(hours=-5) for t in hits)
       and re.search(r"^Persistent=true$", tt, re.M) is not None
       and subprocess.run(["bash", "-n", os.path.join(TOOLS, "install_daily_recap.sh")]).returncode == 0
       and inst_units == ["dtp-daily-recap.service dtp-daily-recap.timer"]
       and "VENV=/home/ubuntu/venvs/daily_brief" in inst and "daily_brief.requirements.txt" in inst
       and "enable --now dtp-daily-recap.timer" in inst)
ck("R1", ok1, "verify rc=%d own=%s exec=%s; timer ET %s n=%d (EST+EDT), Persistent; installer units %s, venv outside "
   "the repo" % (r.returncode, ours[:2], ex, hm, len(hits), inst_units))

# ── R2 ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
import daily_recap as DR  # noqa: E402

cases = {("2026-11-21T17:00", None): "SKIP", ("2026-11-26T17:00", None): "SKIP",
         ("2026-11-23T16:39", None): "SKIP", ("2026-11-23T16:40", None): "DAY 2026-11-23",
         ("2026-11-23T17:00", None): "DAY 2026-11-23", ("2026-11-27T13:39", None): "SKIP",
         ("2026-11-27T13:40", None): "DAY 2026-11-27", ("2026-11-27T17:00", None): "DAY 2026-11-27",
         ("2026-11-27T17:00", "2026-11-26"): "REFUSED", ("2026-11-23T12:00", "2026-11-23"): "REFUSED",
         ("2026-11-21T09:00", "2026-11-20"): "DAY 2026-11-20"}
got = {}
for (n, d), want in cases.items():
    k, v = DR.plan(datetime.fromisoformat(n).replace(tzinfo=ET), d)
    got[(n, d)] = k if k != "DAY" else "DAY " + v
bad = {k: (got[k], w) for k, w in cases.items() if got[k] != w}
ck("R2", not bad, "%d clock cases (weekend, 11-26 holiday, pre-due, 11-27 half day 13:40, --day refusals); wrong=%s"
   % (len(cases), bad))

# ── the sandbox and the fakes ────────────────────────────────────────────────────────────────────────────────────────
SB = os.path.join(TMP, "sb")
REV = os.path.join(SB, "reviews")
OUTD = os.path.join(REV, "daily_brief")
NOTESD = os.path.join(OUTD, "notes")
QUEUE = os.path.join(REV, "WEEKEND_STUDIES.md")
OTHER = os.path.join(SB, "other")
LEDGER = os.path.join(SB, "daily_recap.ledger")
LOG = os.path.join(SB, "daily_recap.log")
WROOT = os.path.join(SB, "work")
CALLS = os.path.join(TMP, "calls.txt")
POSTS = os.path.join(TMP, "posts.txt")
STATE = os.path.join(TMP, "sysstate")

QFIX = """# WEEKEND STUDIES — fixture

## HOW AN ITEM IS RUN (every item, every time)
1. Seal first.

## ADDING AN ITEM
Append it under QUEUE with the same fields. IDs are WS.<n> and are never reused.

---

## QUEUE

### WS.20 — A done item
- Status: DONE 2026-11-21 — REJECT. (/home/ubuntu/reviews/studies/WS.20_x)
- Why: fixture.

### WS.21 — An open item
- Status: OPEN
- Why: fixture.

### WS.6 — PARK, with sub-items
- Status: OPEN
- Shared: text.
- **WS.6a, calls vs puts.** Hypothesis. [Status: FORWARD to 2026-11-27 — interval [-882, -177] (n=33)]
- **WS.6b, gate.** Hypothesis.

## DONE
(none yet; WS.24 was mentioned once)
"""


def proposal(title, **over):
    p = {"title": title, "hypothesis": "h", "evidence": "the day: -$100.00", "data": "warehouse, mainline()",
         "blind": "seal 11-23..12-04, run once", "change": "one gate", "why": "two trades, window n=50",
         "arms": "A = the book; B = the gate", "model": "1m marks, exits at the 1m mark",
         "positive_control": "arm A reproduces booked pnl_usd within 5%", "days": "design 10-26..11-20; sealed 11-23..12-04",
         "pass_bar": "EV/trade beats A with a day-bootstrap 95% interval; prune ledger", "outcome": "TUNE (the gate) or KEEP",
         "setup": "Runaway"}
    p.update(over)
    return p


NOTES_OK = {"revision": "r", "headline": ["h"], "day_note": ["d"], "symbols": {"QQQ": {"tape": "t", "bots": "b",
            "well": "w", "better": "x"}}, "section1_close": ["c"], "studies_intro": ["i"], "studies": [],
            "study_recs": [], "proposals_intro": ["p"],
            "proposals": [proposal("Bounce-trap filter"), proposal("Second idea")],
            "code_intro": ["c"], "code": [], "cash_verdict": ["v"],
            "maintenance": {"id": "HYG.9", "backlog": "OTV5", "title": "t", "what": "w", "why": "y", "risk": "r",
                            "proof": "p", "when": "weekday", "when_reason": "control-side"}, "sources": ["s"]}
NOTES_SRC = os.path.join(TMP, "notes_src.json")
write(NOTES_SRC, json.dumps(NOTES_OK))

FAKE_CLAUDE = os.path.join(TMP, "fake_claude.sh")
write(FAKE_CLAUDE, "#!/bin/bash\n"
      "printf 'ARGS %s\\n' \"$*\" | tr '\\n' ' ' | head -c 60000 >> " + CALLS + "; echo >> " + CALLS + "\n"
      "echo \"UNATTENDED=${VERTIGO_UNATTENDED:-unset} TMPDIR=$TMPDIR PWD=$PWD\" >> " + CALLS + "\n"
      "out=$(printf '%s' \"$*\" | sed -n 's/.*write the notes JSON to exactly this path: \\([^ ]*\\).*/\\1/p' | head -1)\n"
      "echo scratch > \"$TMPDIR/scratch.txt\"\n"
      "[ \"${FAKE_TOUCH_QUEUE:-0}\" = 1 ] && echo 'JUNK FROM THE SESSION' >> \"$FAKE_QUEUE\"\n"
      "[ \"${FAKE_WRITE:-1}\" = 1 ] && [ -n \"$out\" ] && cp \"$FAKE_NOTES\" \"$out\"\n"
      "exit 0\n", 0o755)
FAKE_BRIEF = os.path.join(TMP, "fake_brief.sh")
write(FAKE_BRIEF, "#!/bin/bash\n"
      "echo \"BRIEF $*\" >> " + CALLS + "\n"
      "day=; facts=; out=; summ=\n"
      "while [ $# -gt 0 ]; do case \"$1\" in --date) day=$2; shift 2;; --facts) facts=$2; shift 2;;\n"
      "  --out) out=$2; shift 2;; --summary-json) summ=$2; shift 2;; *) shift;; esac; done\n"
      "if [ -n \"$facts\" ]; then echo '{\"day\": \"'$day'\"}' > \"$facts\"; exit 0; fi\n"
      "mkdir -p \"$out\"; echo '%PDF-1.4 fake' > \"$out/daily_brief_$day.pdf\"\n"
      "echo '{\"day\": \"'$day'\", \"pdf\": \"'$out/daily_brief_$day.pdf'\", \"pages\": 7, \"trades\": 20,"
      " \"paper\": 4149.0, \"fees\": 213.5}' > \"$summ\"\n", 0o755)
FAKE_POST = os.path.join(TMP, "fake_post.sh")
write(FAKE_POST, "#!/bin/bash\nprintf '%s\\n' \"$*\" >> " + POSTS + "\n", 0o755)
# fake systemctl: `show -p ActiveState|LoadState --value UNIT`; per unit a file STATE/UNIT.<prop> holding a list of
# answers, one per call (the last repeats); a STATE/UNIT.hook run at each call (to land a review mid-wait)
FAKE_SC = os.path.join(TMP, "fake_systemctl.sh")
write(FAKE_SC, "#!/bin/bash\n"
      "prop=; unit=\n"
      "while [ $# -gt 0 ]; do case \"$1\" in -p) prop=$2; shift 2;; --value|show) shift;; *) unit=$1; shift;; esac; done\n"
      "f=" + STATE + "/$unit.$prop; c=" + STATE + "/$unit.$prop.n\n"
      "[ -x " + STATE + "/$unit.hook ] && " + STATE + "/$unit.hook\n"
      "[ -f \"$f\" ] || { [ \"$prop\" = LoadState ] && echo not-found || echo inactive; exit 0; }\n"
      "n=$(cat \"$c\" 2>/dev/null || echo 0); n=$((n+1)); echo $n > \"$c\"\n"
      "l=$(wc -l < \"$f\"); [ $n -gt $l ] && n=$l; sed -n \"${n}p\" \"$f\"\n", 0o755)


def fresh():
    for p in (SB, STATE, CALLS, POSTS):
        if os.path.isdir(p):
            shutil.rmtree(p)
        elif os.path.exists(p):
            os.remove(p)
    for d in (REV, OUTD, NOTESD, OTHER, STATE):
        os.makedirs(d, exist_ok=True)
    write(QUEUE, QFIX)
    write(os.path.join(OTHER, "keep.txt"), "untouched")


def sc_state(unit, prop, answers, hook=None):
    write(os.path.join(STATE, f"{unit}.{prop}"), "\n".join(answers) + "\n")
    if hook:
        write(os.path.join(STATE, f"{unit}.hook"), "#!/bin/bash\n" + hook + "\n", 0o755)


def wrap(args, now, extra=None):
    env = dict(os.environ, DAILY_RECAP_CLAUDE=FAKE_CLAUDE, DAILY_RECAP_BRIEF_PY=FAKE_BRIEF, DAILY_RECAP_PY=sys.executable,
               DAILY_RECAP_REVIEWS=REV, DAILY_RECAP_OUT=OUTD, DAILY_RECAP_NOTES=NOTESD, DAILY_RECAP_QUEUE=QUEUE,
               DAILY_RECAP_LOG=LOG, DAILY_RECAP_LEDGER=LEDGER, DAILY_RECAP_WORK_ROOT=WROOT,
               DAILY_RECAP_SYSTEMCTL=FAKE_SC, DAILY_RECAP_POST=FAKE_POST, DAILY_RECAP_POLL_S="1",
               DAILY_RECAP_REPOS=os.path.join(SB, "norepo"), FAKE_NOTES=NOTES_SRC, FAKE_QUEUE=QUEUE)
    env.pop("VERTIGO_UNATTENDED", None)
    if now:
        env["DAILY_RECAP_NOW"] = now
    env.update(extra or {})
    return subprocess.run(["bash", WRAP] + args, capture_output=True, text=True, env=env, timeout=180)


def calls():
    return read(CALLS) if os.path.exists(CALLS) else ""


def ledger():
    return read(LEDGER) if os.path.exists(LEDGER) else ""


def snapshot(root):
    out = {}
    for dp, _dn, fn in os.walk(root):
        for f in fn:
            p = os.path.join(dp, f)
            st = os.stat(p)
            out[p] = (st.st_size, st.st_mtime_ns)
    return out


# ── R3 ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
fresh()
r_sat = wrap([], "2026-11-21T17:00")
r_hol = wrap([], "2026-11-26T17:00")
L = ledger()
ck("R3", r_sat.returncode == 0 and r_hol.returncode == 0 and "SKIPPED day=2026-11-21 not-a-trading-day" in L
   and "SKIPPED day=2026-11-26 not-a-trading-day" in L and "ARGS" not in calls() and not os.listdir(OUTD + "/notes")
   and not [f for f in os.listdir(OUTD) if f.endswith(".pdf")],
   "Saturday and Thanksgiving skip with a ledger line, no session, no PDF (%r)" % r_sat.stdout.strip()[:80])

# ── R4 ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
fresh()
review = os.path.join(REV, "2026-11-23.md")
sc_state("dtp-nightly-review.service", "ActiveState", ["activating", "activating", "activating", "inactive"],
         hook="n=$(cat %s/dtp-nightly-review.service.ActiveState.n 2>/dev/null || echo 0); [ $n -ge 2 ] && "
              "echo '# review' > %s; true" % (STATE, review))
t0 = time.time()
r4 = wrap([], "2026-11-23T17:00")
lg = read(LOG) if os.path.exists(LOG) else ""
m = re.search(r"review present after (\d+)s", lg)
ok_wait = (r4.returncode == 0 and m is not None and int(m.group(1)) >= 2 and calls().count("ARGS") == 1
           and "(present)" in calls())
fresh()
r4b = wrap([], "2026-11-23T17:00", {"DAILY_RECAP_REVIEW_WAIT_S": "2"})
lg = read(LOG) if os.path.exists(LOG) else ""
ok_cap = (r4b.returncode == 0 and "review wait cap 2s reached" in lg and "review MISSING after" in lg
          and "(MISSING)" in calls() and calls().count("ARGS") == 1)
ck("R4", ok_wait and ok_cap, "waited %ss for the review file + service before the one session; a review that never "
   "came: the cap, then the session told MISSING (%s/%s)" % (m.group(1) if m else "?", ok_wait, ok_cap))

# ── R5 ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
fresh()
write(os.path.join(REV, "2026-11-23.md"), "# review\n")
r5a = wrap([], "2026-11-23T17:00")
n_first = calls().count("ARGS")
r5b = wrap([], "2026-11-23T17:30")
n_second = calls().count("ARGS")
os.remove(os.path.join(OUTD, "daily_brief_2026-11-23.pdf"))
q_before = read(QUEUE)
r5c = wrap([], "2026-11-23T18:00")                          # rebuild: notes valid -> no session, no second append
n_third = calls().count("ARGS")
os.remove(os.path.join(OUTD, "daily_brief_2026-11-23.pdf"))
os.makedirs(WROOT, exist_ok=True)
holder = subprocess.Popen(["flock", os.path.join(WROOT, ".lock"), "sleep", "20"])
time.sleep(0.5)
r5d = wrap([], "2026-11-23T18:30")
holder.terminate()
holder.wait()
L = ledger()
ck("R5", n_first == 1 and n_second == 1 and n_third == 1 and "STOOD_DOWN exists day=2026-11-23" in L
   and "STOOD_DOWN inflight day=2026-11-23" in L and read(QUEUE) == q_before
   and os.path.exists(os.path.join(OUTD, "daily_brief_2026-11-23.pdf")) is False
   and L.count("PRODUCED day=2026-11-23") == 2,
   "sessions %d/%d/%d: a built day stands down, a rebuild reuses valid notes (no session, queue unchanged), the lock "
   "stands a second run down" % (n_first, n_second, n_third))

# ── R6 ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
fresh()
write(os.path.join(REV, "2026-11-23.md"), "# review\n")
real_q = os.path.expanduser("~/reviews/WEEKEND_STUDIES.md")
real_out = os.path.expanduser("~/reviews/daily_brief")
rq0 = os.stat(real_q).st_mtime_ns if os.path.exists(real_q) else None
ro0 = snapshot(real_out) if os.path.isdir(real_out) else {}
before = snapshot(SB)
r6 = wrap([], "2026-11-23T17:00")
after = snapshot(SB)
allowed = (NOTESD + "/", OUTD + "/", QUEUE, LEDGER, LOG, WROOT + "/")
changed = [p for p in after if before.get(p) != after[p]]
outside = [p for p in changed if not (p == QUEUE or p.startswith(QUEUE + ".bak_recap_") or p in (LEDGER, LOG)
                                      or p.startswith(NOTESD + "/") or p.startswith(OUTD + "/")
                                      or p.startswith(WROOT + "/"))]
work_left = [d for d in os.listdir(WROOT) if d.startswith("2026-")] if os.path.isdir(WROOT) else []
c6 = calls()
iso = re.search(r"--session-id [0-9a-f-]{36}", c6) is not None and "--continue" not in c6
unatt = "UNATTENDED=1" in c6 and re.search(r"TMPDIR=" + re.escape(WROOT) + r"/2026-11-23-\d+-\d+ ", c6) is not None
perm = "--permission-mode acceptEdits" in c6 and ("--add-dir " + NOTESD) in c6
fresh()
write(os.path.join(REV, "2026-11-23.md"), "# review\n")
q0 = read(QUEUE)
r6b = wrap([], "2026-11-23T17:00", {"FAKE_TOUCH_QUEUE": "1"})
q1 = read(QUEUE)
restored = "JUNK FROM THE SESSION" not in q1 and "QUEUE_RESTORED day=2026-11-23" in ledger() and "### WS.25 —" in q1
rq1 = os.stat(real_q).st_mtime_ns if os.path.exists(real_q) else None
ro1 = snapshot(real_out) if os.path.isdir(real_out) else {}
ck("R6", r6.returncode == 0 and not outside and not work_left and iso and unatt and perm and restored
   and rq0 == rq1 and ro0 == ro1,
   "changed outside the allowed paths: %s; WORK left: %s; isolated %s, unattended+TMPDIR %s, acceptEdits+add-dir %s; "
   "a session's queue edit restored (then the appender's own items): %s; the real queue and ~/reviews/daily_brief "
   "untouched" % (outside[:3], work_left, iso, unatt, perm, restored))

# ── R7 ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
import study_dispatch as SD  # noqa: E402


def r7_on(text, label):
    q = os.path.join(TMP, "q7_%s.md" % label)
    nf = os.path.join(TMP, "n7_%s.json" % label)
    write(q, text)
    notes = dict(NOTES_OK)
    notes["proposals"] = [proposal("Good one"),
                          proposal("Resting exit", change="place a resting take-profit order at +50%"),
                          proposal("Missing arms", arms=""),
                          proposal("Good two"),
                          proposal("Good three"),
                          proposal("Over the cap")]
    write(nf, json.dumps(notes))
    before = SD.parse_queue(text)
    n0 = DR.next_ws_id(text)
    rc = DR.main(["append", "--day", "2026-11-23", "--notes", nf, "--queue", q])
    new = read(q)
    after = SD.parse_queue(new)
    nn = json.loads(read(nf))
    ids = [p.get("ws_id") for p in nn["proposals"]]
    want = ["WS.%d" % n0, None, None, "WS.%d" % (n0 + 1), "WS.%d" % (n0 + 2), None]
    heads = re.findall(r"^### (WS\.\d+)\b", new, re.M)
    got = {it["id"]: it for it in after}
    ok = (rc == 0 and ids == want and len(after) == len(before) + 3 and len(heads) == len(set(heads))
          and all(got[w]["status"].startswith("OPEN") for w in want if w)
          and [it["id"] for it in after][:len(before)] == [it["id"] for it in before]
          and os.path.exists(q + ".bak_recap_20261123") and read(q + ".bak_recap_20261123") == text
          and "resting take-profit" in nn["proposals"][1].get("queue_refused", "")
          and "missing arms" in nn["proposals"][2].get("queue_refused", "")
          and "daily cap" in nn["proposals"][5].get("queue_refused", "")
          and (new.find("### WS.%d" % n0) < new.find("\n## DONE") or "\n## DONE" not in new)
          and "Basis (HOW 3b): at the mark" in new and "Never log-only." in new)
    rc2 = DR.main(["append", "--day", "2026-11-23", "--notes", nf, "--queue", q])
    ok2 = rc2 == 0 and read(q) == new
    return ok and ok2, (rc, ids, want, len(before), len(after), ok2)


ok7a, d7a = r7_on(QFIX, "fixture")
if os.path.exists(real_q):
    # v1.6: the real queue now holds the 11-23 recap's own items, "(daily recap 2026-11-23, Pn)", which read as this
    # fixture's earlier append (an item's own earlier append appends nothing): rename them in the copy only
    ok7b, d7b = r7_on(read(real_q).replace("(daily recap 2026-11-23, P", "(daily recap 2026-11-23 real, P"), "realcopy")
else:
    ok7b, d7b = True, "real queue not readable here (fixture only)"
ck("R7", ok7a and ok7b and DR.next_ws_id(QFIX) == 25,
   "fixture %s; a copy of the real queue %s: accepted proposals OPEN with the next unique ids before ## DONE, a .bak "
   "first, refusals named, a re-run appends nothing" % (d7a if not ok7a else "ok", d7b if not ok7b else "ok"))

# ── R8 ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
fresh()
write(os.path.join(REV, "2026-11-23.md"), "# review\n")
r8 = wrap([], "2026-11-23T17:00")
posts = read(POSTS).splitlines() if os.path.exists(POSTS) else []
p0 = posts[0] if posts else ""
bad_when = dict(NOTES_OK, maintenance=dict(NOTES_OK["maintenance"], when="Saturday"))
_f, _r, mp = DR.validate(bad_when)
ck("R8", len(posts) == 1 and "Daily recap 2026-11-23 ready" in p0 and "+$4,149.00 at the mark" in p0
   and "fees $213.50 beside" in p0 and "WS.25, WS.26" in p0 and "Maintenance HYG.9 (weekday) awaits your yes" in p0
   and "\n" not in p0 and any("weekday / Sunday" in x for x in mp),
   "one line: %r; a 'when' of Saturday refused" % p0[:160])

# ── R9 ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
fri = date.today() + timedelta(days=(4 - date.today().weekday()) % 7 + 7)      # a Friday next week (deadline ahead)
FD = os.path.join(TMP, "fri")
FAKE_PY = os.path.join(TMP, "fake_py.sh")
write(FAKE_PY, "#!/bin/bash\necho \"PY $* at $(date +%s.%N)\" >> " + os.path.join(FD, "py_calls") + "\n", 0o755)


def friday(rl_hook, recap_states, load="loaded", extra=None):
    if os.path.isdir(FD):
        shutil.rmtree(FD)
    os.makedirs(FD)
    if os.path.isdir(STATE):
        shutil.rmtree(STATE)
    os.makedirs(STATE)
    rl = os.path.join(FD, "recap.ledger")
    sc_state("dtp-eod-conductor.service", "ActiveState", ["inactive"])
    sc_state("dtp-daily-recap.service", "LoadState", [load])
    sc_state("dtp-daily-recap.service", "ActiveState", recap_states,
             hook=rl_hook % {"n": STATE + "/dtp-daily-recap.service.ActiveState.n", "rl": rl, "day": fri.isoformat()})
    env = dict(os.environ, FRIDAY_STUDIES_PY=FAKE_PY, FRIDAY_STUDIES_WEEKLY=os.path.join(FD, "weekly"),
               FRIDAY_STUDIES_LEDGER=os.path.join(FD, "fs.ledger"), FRIDAY_STUDIES_NOW="%s 17:15" % fri,
               FRIDAY_STUDIES_SYSTEMCTL=FAKE_SC, FRIDAY_STUDIES_POLL_S="1",
               FRIDAY_STUDIES_LOCK=os.path.join(FD, "lock"), FRIDAY_STUDIES_RECAP_LEDGER=rl)
    env.update(extra or {})
    r = subprocess.run(["bash", FRI], capture_output=True, text=True, env=env, timeout=120)
    pyc = read(os.path.join(FD, "py_calls")) if os.path.exists(os.path.join(FD, "py_calls")) else ""
    log = "".join(read(p) for p in [os.path.join(FD, "weekly", "saturday_%s_work" % (fri + timedelta(days=1)),
                                                 "study_dispatch.log")] if os.path.exists(p))
    lt = os.path.getmtime(rl) if os.path.exists(rl) else None
    first = re.search(r"study_dispatch\.py run .* at (\d+\.\d+)", pyc)
    return r, pyc, log, lt, (float(first.group(1)) if first else None)


hook = ("n=$(cat %(n)s 2>/dev/null || echo 0); [ $n -ge 3 ] && ! grep -q PRODUCED %(rl)s 2>/dev/null && "
        "echo \"$(date -u +%%FT%%TZ) PRODUCED day=%(day)s session=rc=0 x\" >> %(rl)s; true")
r9a, pyc, log, lt, t_run = friday(hook, ["activating"] * 3 + ["inactive"])
ok_a = (r9a.returncode == 0 and "daily recap wait" in log and "(done)" in log and lt is not None and t_run is not None
        and t_run >= lt and "study_dispatch.py run --deadline 02:30" in pyc)
r9b, pyc_b, log_b, _lt, _t = friday("true", ["inactive"], load="not-found")
ok_b = "daily recap wait 0s (not-installed)" in log_b and "study_dispatch.py run" in pyc_b
r9c, pyc_c, log_c, _lt, _t = friday("true", ["activating"], extra={"FRIDAY_STUDIES_RECAP_WAIT_S": "3"})
ok_c = re.search(r"daily recap wait [34]s \(cap\)", log_c) is not None and "study_dispatch.py run" in pyc_c
fs_src = read(FRI)
ok_t1 = ('"$HM" -lt 1650' in fs_src and "dtp-daily-recap.service" in fs_src
         and 0 < fs_src.find("--value dtp-eod-conductor.service") < fs_src.find("--value dtp-daily-recap.service")
         < fs_src.find("exec 9>"))
ck("R9", ok_a and ok_b and ok_c and ok_t1,
   "the dispatch ran after the recap's ledger line (%s), without waiting for a recap not installed (%s), and at the "
   "cap (%s); conductor wait, then recap wait, then the lock (%s)" % (ok_a, ok_b, ok_c, ok_t1))

# ── R10 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
pr = re.sub(r"\s+", " ", read(os.path.join(TOOLS, "daily_recap.prompt")))
need = ["P&L IS AT THE MARK ONLY", "the ladder's fill (mark or better)", "Fees go BESIDE P&L and EV, never inside",
        "mainline()", "TastyTrade's", "No yfinance", "ORBStrategy", "Breakout (DORMANT", "butterflies", "PARC", "TCS",
        "Never propose resting take-profit orders", "No new config knobs", "never log-only",
        "Never edit ~/reviews/WEEKEND_STUDIES.md", "ONE object", '"weekday" or "Sunday"', "live order path",
        "Never print or copy a service Environment block", "Honest, not cheerleading", "NOT MEASURED", "never /tmp"]
miss = [n for n in need if n not in pr]
ws = re.sub(r"(?m)^\s*#.*$", "", read(WRAP))                   # the code, not its comments
ck("R10", not miss and "export VERTIGO_UNATTENDED=1" in ws and "--continue" not in ws and "--session-id" in ws
   and 'timeout "$MAX_S"' in ws and "Environment" not in ws and "printenv" not in ws and "env |" not in ws,
   "prompt rules present (missing: %s); the wrapper is unattended, isolated and capped" % miss)

# ── R11 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
gen = os.path.join(TOOLS, "daily_brief.py")
gs = read(gen)
try:
    py_compile.compile(gen, cfile=os.path.join(TMP, "db.pyc"), doraise=True)
    comp = True
except py_compile.PyCompileError:
    comp = False
ck("R11", comp and "daily_brief.py  v1.5" in gs and 'NOTES_DIR = os.path.expanduser("~/reviews/daily_brief/notes")' in gs
   and "--facts" in gs and "--summary-json" in gs and "/home/ubuntu/venvs/daily_brief" in gs
   and not os.path.exists(os.path.join(TOOLS, "venv")) and not os.path.exists(os.path.join(TOOLS, "notes"))
   and "11-20 showed" not in gs and os.path.exists(os.path.join(TOOLS, "daily_brief.requirements.txt")),
   "tools/daily_brief.py v1.5 compiles; notes under ~/reviews/daily_brief/notes; no venv or notes in the repo")

# ── R12 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
_r12q = os.path.join(TMP, "q12.md")
_r12n = os.path.join(TMP, "n12.json")
write(_r12q, QFIX)
_n12 = dict(NOTES_OK)
_n12["proposals"] = [proposal("Hunt idea one", setup="Hunt"), proposal("No setup at all", setup=""),
                     proposal("Miscased setup", setup="park"), proposal("Hunt idea two", setup="Hunt"),
                     proposal("PARK late lock", setup="PARK"), proposal("Runaway reentry", setup="Runaway, Hunt")]
write(_r12n, json.dumps(_n12))
_rc12 = DR.main(["append", "--day", "2026-11-23", "--notes", _r12n, "--queue", _r12q])
_q12 = read(_r12q)
_p12 = json.loads(read(_r12n))["proposals"]
_it12 = {it["title"].split(" — ", 1)[-1]: it for it in SD.parse_queue(_q12)}
ck("R12", _rc12 == 0 and [bool(p.get("ws_id")) for p in _p12] == [True, False, False, False, True, True]
   and "missing setup" in _p12[1].get("queue_refused", "") and "setup:" in _p12[2].get("queue_refused", "")
   and "daily cap" in _p12[3].get("queue_refused", "")
   and "- Setup: PARK\n" in _q12 and "- Setup: Runaway, Hunt\n" in _q12
   and SD.priority_tier(_it12["PARK late lock"]) == 0 and SD.priority_tier(_it12["Hunt idea one"]) == 1
   and re.search(r"- Status: OPEN \(added 2026-11-23[^\n]*\n- Setup: PARK\n", _q12) is not None,
   "setup required and read by the dispatcher (blank and 'park' refused); `- Setup:` under the Status; over the cap the "
   "PARK / Runaway proposals went first: %s" % [(p["title"], p.get("ws_id"), p.get("queue_refused", "")[:30]) for p in _p12])

# ── R13 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
_r13q = os.path.join(TMP, "q13.md")
_r13n = os.path.join(TMP, "n13.json")
_q13 = QFIX.replace("### WS.20 — A done item", "### WS.20 — Hunt shorts: skip against the QQQ day trend")
write(_r13q, _q13)
_n13 = dict(NOTES_OK)
_n13["proposals"] = [proposal("Hunt shorts — skip against the QQQ day-trend", setup="Hunt"),
                     proposal("Hunt shorts: skip against the QQQ day trend, again", setup="Hunt"),
                     proposal("An open item!", setup="PARK"),
                     proposal("PARK call trim on gap days", setup="PARK")]
write(_r13n, json.dumps(_n13))
_rc13 = DR.main(["append", "--day", "2026-11-24", "--notes", _r13n, "--queue", _r13q])
_p13 = json.loads(read(_r13n))["proposals"]
_after13 = read(_r13q)
_rc13b = DR.main(["append", "--day", "2026-11-24", "--notes", _r13n, "--queue", _r13q])
_w13 = os.path.join(TMP, "w13")
DR.main(["context", "--day", "2026-11-24", "--work", _w13, "--queue", _r13q, "--notes-dir", os.path.join(TMP, "nd13"),
         "--studies", os.path.join(TMP, "st13"), "--weekly", os.path.join(TMP, "wk13"),
         "--otv5-backlog", os.path.join(TMP, "nobl"), "--hygiene", os.path.join(TMP, "hy13"),
         "--botlogs", os.path.join(TMP, "bl13"), "--trades", os.path.join(TMP, "tr13")])
_c13 = read(os.path.join(_w13, "context.md"))
ck("R13", _rc13 == 0 and [bool(p.get("ws_id")) for p in _p13] == [False, False, False, True]
   and all("duplicates WS.20" in _p13[i].get("queue_refused", "") for i in (0, 1))
   and "duplicates WS.21" in _p13[2].get("queue_refused", "")
   and _rc13b == 0 and read(_r13q) == _after13
   and "Queue items already DONE" in _c13 and "WS.20 WS.20 — Hunt shorts: skip against the QQQ day trend" in _c13
   and DR.dup_of("Hunt shorts skip against QQQ day trend window", _q13) == "WS.20"
   and DR.dup_of("Runaway equity calls after 09:45", _q13) is None,
   "exact and near duplicates of a DONE and an OPEN title refused, a distinct one queued, the re-run appends nothing, "
   "context lists the DONE items: %s" % [(p["title"][:30], p.get("ws_id"), p.get("queue_refused", "")[:30]) for p in _p13])

# ── R14 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
_bl = os.path.join(TMP, "bl14", "2026-11-24")
write(os.path.join(_bl, "AMD.txt"), "# AMD 2026-11-24 bot.log extract: x\n== bot.log (bot.log)\n"
      "2026-11-24 09:32:00 [ERROR] main: boom\nTraceback (most recent call last):\n  File x\n"
      "2026-11-24 10:00:00 [CRITICAL] risk: y\n2026-11-24 09:30:01 [INFO ] a: ALERT: OptionsBot [PAPER] STARTED | AMD\n")
write(os.path.join(_bl, "NVDA.txt"), "# NVDA 2026-11-24 NOT READ: ssh rc=255 timed out (eod_conductor_v2, x)\n")
_w14 = os.path.join(TMP, "w14")
DR.main(["context", "--day", "2026-11-24", "--work", _w14, "--queue", _r13q, "--notes-dir", os.path.join(TMP, "nd13"),
         "--studies", os.path.join(TMP, "st13"), "--weekly", os.path.join(TMP, "wk13"),
         "--otv5-backlog", os.path.join(TMP, "nobl"), "--hygiene", os.path.join(TMP, "hy13"),
         "--botlogs", os.path.join(TMP, "bl14"), "--trades", os.path.join(TMP, "tr13")])
_c14 = read(os.path.join(_w14, "context.md"))
_pr14 = re.sub(r"\s+", " ", read(os.path.join(TOOLS, "daily_recap.prompt")))
_ws14 = read(WRAP)
ck("R14", "AMD: 1 ERROR, 1 CRITICAL, 1 Traceback, 1 restart marker(s)" in _c14 and "NVDA: NOT READ" in _c14
   and "BOTLOGS   $OUTDIR/botlogs/$DAY" in _ws14 and '--botlogs "$OUTDIR/botlogs"' in _ws14
   and "needs a box read" not in _pr14 and "BOTLOGS" in _pr14 and "restart markers" in _pr14,
   "context counts the conductor's extracts per box and names a NOT READ box; the wrapper and the prompt use them")

# ── R15 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
import cash_books as CB  # noqa: E402
_tr = os.path.join(TMP, "tr15")
write(os.path.join(_tr, "2026-11-23.csv"),
      "sym,trade_id,strategy,direction,contracts,entry_premium,exit_premium,pnl_usd,entry_time,exit_time,exit_reason,fee\n"
      "QQQ,a,PARK,long,2,1,2,1234.0,2026-11-23T16:01:00+00:00,2026-11-23T20:45:00+00:00,x,10.0\n"
      "AMD,b,RunawayContinuation,long,2,1,2,-200.0,2026-11-23T14:40:00+00:00,2026-11-23T15:00:00+00:00,x,5.0\n")
_w15 = os.path.join(TMP, "w15")
DR.main(["context", "--day", "2026-11-23", "--work", _w15, "--queue", _r13q, "--notes-dir", os.path.join(TMP, "nd13"),
         "--studies", os.path.join(TMP, "st13"), "--weekly", os.path.join(TMP, "wk13"),
         "--otv5-backlog", os.path.join(TMP, "nobl"), "--hygiene", os.path.join(TMP, "hy13"),
         "--botlogs", os.path.join(TMP, "bl14"), "--trades", _tr])
_cj = os.path.join(_w15, "cash_books.json")
_sc15 = json.loads(read(_cj)) if os.path.exists(_cj) else {}
_good = dict(NOTES_OK, cash_books=["A big index PARK day: C1 netted $1,224 on the day, C2 $1,019."])
_inv = dict(NOTES_OK, cash_books=["C1 made $9,999 today."])
_ps = dict(NOTES_OK, cash_books=["At paper size C1 netted $1,224."])
_n15 = os.path.join(TMP, "n15.json")
_q15 = os.path.join(TMP, "q15.md")
write(_q15, QFIX)
write(_n15, json.dumps(_inv))
DR.main(["append", "--day", "2026-11-23", "--notes", _n15, "--queue", _q15, "--cash-books", _cj])
_after15 = json.loads(read(_n15))
_bs = read(os.path.join(TOOLS, "daily_brief.py"))
_pr15 = re.sub(r"\s+", " ", read(os.path.join(TOOLS, "daily_recap.prompt")))
ck("R15", os.path.exists(os.path.join(_w15, "cash_books.md")) and _sc15.get("windows", {}).get("day", {}).get("books", {})
   .get("C1", {}).get("net") == 1224.0
   and DR.cash_problems(_good, _sc15) == [] and any("$9,999" in x for x in DR.cash_problems(_inv, _sc15))
   and any("paper size" in x for x in DR.cash_problems(_ps, _sc15))
   and "cash_books" not in _after15 and "$9,999" in _after15.get("cash_books_withheld", "")
   and "5b. The cash candidate books C1-C4" in _bs and "cash_books_rows(day)" in _bs
   and '"cash_books", "runaway_watch", "sources")' in _bs
   and '"cash_books":' in _pr15 and "REPORT ONLY" in _pr15 and "paper size" in _pr15
   and "never in the window EV or the theories" in _pr15 and "never propose changing a book's definition" in _pr15
   and "CASHBOOKS $WORK/cash_books.md" in read(WRAP) and '--cash-books "$WORK/cash_books.json"' in read(WRAP),
   "the scoreboard lands in WORK; an invented figure and 'paper size' withhold the commentary, quoted figures pass; "
   "PDF section 5b and the prompt's report-only rules")

# ── R16 (amendment 1) ────────────────────────────────────────────────────────────────────────────────────────────────
_t1 = dict(NOTES_OK, cash_books=["C1 leans on its top two trades."])
_t2 = dict(NOTES_OK, cash_books=["C2 is dependent on its best trades."])
_t3 = dict(NOTES_OK, cash_books=["Without its two largest winners C1 is lower, and without its two largest losers higher."])
_pr16 = re.sub(r"\s+", " ", read(os.path.join(TOOLS, "daily_recap.prompt")))
_bs16 = read(os.path.join(TOOLS, "daily_brief.py"))
ck("R16", any("amendment 1" in x for x in DR.cash_problems(_t1, _sc15))
   and any("amendment 1" in x for x in DR.cash_problems(_t2, _sc15)) and DR.cash_problems(_t3, _sc15) == []
   and '"Fwd ex top-2 / ex bottom-2"' in _bs16 and 'f["gross_ex_bottom2"]' in _bs16
   and "quote both or neither" in _pr16 and "never a qualifier" in _pr16 and "(gross without the top two)" not in _pr16,
   "the top-two figure alone is withheld, both together pass; the PDF and the prompt carry both or neither")

# ── R17 (v1.3, HALF.2): a half day is a non-trading day ──────────────────────────────────────────────────────────────
_ctx = lambda day, w, q, tr: DR.main(["context", "--day", day, "--work", w, "--queue", q,     # noqa: E731
                                      "--notes-dir", os.path.join(TMP, "nd17"), "--studies", os.path.join(TMP, "st17"),
                                      "--weekly", os.path.join(TMP, "wk17"), "--otv5-backlog", os.path.join(TMP, "nobl"),
                                      "--hygiene", os.path.join(TMP, "hy17"), "--botlogs", os.path.join(TMP, "bl17"),
                                      "--trades", tr])
_q17 = os.path.join(TMP, "q17.md")
write(_q17, QFIX)
_w17h, _w17f = os.path.join(TMP, "w17h"), os.path.join(TMP, "w17f")
_ctx("2026-11-27", _w17h, _q17, os.path.join(TMP, "tr17"))
_ctx("2026-11-23", _w17f, _q17, os.path.join(TMP, "tr17"))
_c17h, _c17f = read(os.path.join(_w17h, "context.md")), read(os.path.join(_w17f, "context.md"))
_n17 = os.path.join(TMP, "n17.json")
write(_n17, json.dumps(dict(NOTES_OK, proposals=[proposal("Runaway gap filter", setup="Runaway")])))
_rc17 = DR.main(["append", "--day", "2026-11-27", "--notes", _n17, "--queue", _q17])
_p17 = json.loads(read(_n17))["proposals"][0]
_q17after = read(_q17)
_fat17, _ref17, _ = DR.validate(json.loads(read(_n17)), QFIX, "2026-11-23")
_pr17 = re.sub(r"\s+", " ", read(os.path.join(TOOLS, "daily_recap.prompt")))
_bs17 = read(os.path.join(TOOLS, "daily_brief.py"))
ck("R17", "HALF DAY: 2026-11-27 is a 13:00 early close, a NON-TRADING day" in _c17h and "HALF DAY" not in _c17f
   and "ZERO TRADES IS EXPECTED" in _c17h and _rc17 == 0 and not _p17.get("ws_id")
   and "non-trading day" in _p17.get("queue_refused", "") and _q17after == QFIX and not _ref17
   and "A HALF DAY IS A NON-TRADING DAY" in _pr17 and "never a defect, never a study" in _pr17
   and "Yes, just treat them as bank holidays. No trading." in _pr17
   and "HALF_DAY_LINE" in _bs17 and "if half_day:" in _bs17 and "DEFECT: {len(trades)} trade(s) on a half day" in _bs17
   and "No study is proposed from a half day" in _bs17,
   "11-27's context says NON-TRADING (11-23's does not); its proposal refused (%s) and the queue untouched; the same "
   "proposal valid on 11-23; prompt and PDF state the ruling" % _p17.get("queue_refused", "")[:60])

# ── R18 (v1.3, RWATCH.1): the Runaway equity watch ───────────────────────────────────────────────────────────────────
import runaway_watch as RW  # noqa: E402
_tr18 = os.path.join(TMP, "tr18")
write(os.path.join(_tr18, "2026-11-23.csv"),
      "sym,trade_id,strategy,direction,contracts,entry_premium,exit_premium,pnl_usd,entry_time,exit_time,exit_reason,fee\n"
      "NVDA,a,RunawayContinuation,long,2,1,2,-412.0,2026-11-23T14:40:00+00:00,2026-11-23T15:00:00+00:00,x,8.0\n"
      "TSLA,b,RunawayContinuation,long,2,1,2,250.0,2026-11-23T14:41:00+00:00,2026-11-23T15:10:00+00:00,x,5.0\n")
_w18 = os.path.join(TMP, "w18")
_ctx("2026-11-23", _w18, _q17, _tr18)
_c18 = read(os.path.join(_w18, "context.md"))
_rj = os.path.join(_w18, "runaway_watch.json")
_sc18 = json.loads(read(_rj)) if os.path.exists(_rj) else {}
_g18 = dict(NOTES_OK, runaway_watch=["NVDA is ON NOTICE: 1 forward trade, net $420; 7 more are needed."])
_i18 = dict(NOTES_OK, runaway_watch=["NVDA lost $9,999."])
_ps18 = dict(NOTES_OK, runaway_watch=["At paper size NVDA lost $420."])
_n18 = os.path.join(TMP, "n18.json")
write(_n18, json.dumps(_i18))
DR.main(["append", "--day", "2026-11-23", "--notes", _n18, "--queue", _q17, "--runaway-watch", _rj])
_a18 = json.loads(read(_n18))
_pr18 = re.sub(r"\s+", " ", read(os.path.join(TOOLS, "daily_recap.prompt")))
_bs18 = read(os.path.join(TOOLS, "daily_brief.py"))
_ws18 = read(WRAP)
ck("R18", os.path.exists(os.path.join(_w18, "runaway_watch.md"))
   and (_sc18.get("equities", {}).get("NVDA", {}).get("forward") or {}).get("net") == -420.0
   and "NVDA ON NOTICE (forward n 1)" in _c18
   and DR.watch_problems(_g18, _sc18) == [] and any("$9,999" in x for x in DR.watch_problems(_i18, _sc18))
   and any("paper size" in x for x in DR.watch_problems(_ps18, _sc18))
   and "runaway_watch" not in _a18 and "$9,999" in _a18.get("runaway_watch_withheld", "")
   and "5c. The Runaway equity watch" in _bs18 and "watch_chart(RW, wsc)" in _bs18 and '"runaway_watch", "sources")' in _bs18
   and "RWATCH    $WORK/runaway_watch.md" in _ws18 and _ws18.count('--runaway-watch "$WORK/runaway_watch.json"') == 2
   and '"runaway_watch":' in _pr18 and "REPORT ONLY; never \"paper size\"" in _pr18
   and "never a decision" in _pr18 and "never propose a different bar, a different list" in _pr18
   and "RWATCH (RUN PARAMETERS)" in _pr18,
   "the watch lands in WORK and its statuses in the context; an invented figure and 'paper size' withhold the "
   "commentary, quoted figures pass; PDF section 5c, the wrapper and the prompt's report-only rules")

# ── R19 (v1.4, BOXF.1): the Box flags block ───────────────────────────────────────────────────────────────────────
_bl19 = os.path.join(TMP, "bl19", "2026-11-23")
_D = "\u00b7"
write(os.path.join(_bl19, "QQQ.txt"), "# QQQ x\n2026-11-23 09:15:03 [INFO ] __main__: [flags] QQQ source=none (defaults) "
      f"sha256=- commit=c0ffee0000 {_D} schema v1: no keys {_D} differs: none\n")
write(os.path.join(_bl19, "SPX.txt"), "# SPX x\n2026-11-23 09:15:03 [WARNING] __main__: [flags] SPX "
      f"source=deploy/box_flags/SPX sha256=0123456789ab commit=c0ffee0000 {_D} ogap=off {_D} differs: ogap(off, "
      f"default on) {_D} REFUSED: line 2 unknown key 'brk': ignored (schema v1: ogap)\n")
write(os.path.join(_bl19, "NVDA.txt"), "# NVDA x\n2026-11-23 09:15:03 [INFO ] __main__: [flags] NVDA source=none "
      f"(defaults) sha256=- commit=c0ffee0000 {_D} ogap=on {_D} differs: none\n2026-11-23 11:00:00 [INFO ] __main__: "
      f"[flags] NVDA source=none (defaults) sha256=- commit=c0ffee0001 {_D} ogap=on {_D} differs: none\n")
write(os.path.join(_bl19, "AMD.txt"), "# AMD x\n2026-11-23 09:32:00 [ERROR] main: boom\n")
_o5 = os.path.join(TMP, "otv5_19")
_envf = os.path.join(TMP, "env19.json")
write(os.path.join(_o5, "tools", "box_flags_show.py"),
      "import json, os, sys\n"
      f"open({_envf!r}, 'a').write(json.dumps({{'argv': sys.argv[1:], 'env': sorted(os.environ), 'I': sys.flags.isolated}}) + '\\n')\n"
      "H = {'QQQ': ('-', {}), 'SPX': ('0123456789ab', {'ogap': 'off'}), 'NVDA': ('fedcba987654', {'ogap': 'off'}),\n"
      "     'TSLA': ('-', {})}\n"
      "syms = [sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == '--symbol']\n"
      "print(json.dumps({'schema_version': 1, 'schema': {}, 'boxes': [{'symbol': s, 'sha256': H[s][0], "
      "'values': H[s][1]} for s in syms]}))\n")
os.environ["TT_REFRESH_TOKEN"] = "r19-secret-must-not-pass"
os.environ["OT_INSTRUMENT_R19"] = "x"
_f19 = DR.flags_summary("2026-11-23", os.path.join(TMP, "bl19"), _o5)
_bl19b = os.path.join(TMP, "bl19b", "2026-11-23")
for _s in ("QQQ", "TSLA"):
    write(os.path.join(_bl19b, _s + ".txt"), f"# {_s}\n2026-11-23 09:15:03 [INFO ] __main__: [flags] {_s} source=none "
          f"(defaults) sha256=- commit=c0ffee0000 {_D} schema v1: no keys {_D} differs: none\n")
_f19b = DR.flags_summary("2026-11-23", os.path.join(TMP, "bl19b"), _o5)
_f19c = DR.flags_summary("2026-11-23", os.path.join(TMP, "bl19b"), os.path.join(TMP, "no_otv5"))
os.environ.pop("TT_REFRESH_TOKEN", None)
os.environ.pop("OT_INSTRUMENT_R19", None)
_calls19 = [json.loads(x) for x in read(_envf).splitlines() if x.strip()] if os.path.exists(_envf) else []
_w19 = os.path.join(TMP, "w19")
DR.main(["context", "--day", "2026-11-23", "--work", _w19, "--queue", _q17, "--notes-dir", os.path.join(TMP, "nd19"),
         "--studies", os.path.join(TMP, "st19"), "--weekly", os.path.join(TMP, "wk19"),
         "--otv5-backlog", os.path.join(TMP, "nobl"), "--hygiene", os.path.join(TMP, "hy19"),
         "--botlogs", os.path.join(TMP, "bl19"), "--trades", os.path.join(TMP, "tr19"), "--otv5", _o5])
_c19 = read(os.path.join(_w19, "context.md"))
_j19 = " | ".join(_f19)
_pr19 = re.sub(r"\s+", " ", read(os.path.join(TOOLS, "daily_recap.prompt")))
ck("R19", _f19[0] == "defaults, as HEAD: QQQ"
   and any(x.startswith("SPX: differs: ogap(off, default on); REFUSED: line 2 unknown key 'brk'") for x in _f19)
   and any(x.startswith("NVDA: PENDING: HEAD would start it with ogap=off (file fedcba987654)") and "c0ffee0001" in x
           for x in _f19)
   and any(x.startswith("NOT SEEN") and "AMD" in x for x in _f19) and "PENDING" not in _j19.split("NVDA")[0]
   and _f19b == ["all defaults on 2 box(es) (QQQ, TSLA)"]
   and any(x.startswith("HEAD NOT READ") for x in _f19c)
   and len(_calls19) == 2 and all(c["I"] == 1 and "--json" in c["argv"] for c in _calls19)
   and all(set(c["env"]) <= {"PATH", "HOME", "LANG", "LC_CTYPE"} for c in _calls19)
   and "Box flags (each box's [flags] start line" in _c19 and "NVDA: PENDING" in _c19
   and not re.search(r"Environment|r19-secret|TT_REFRESH|account number", _c19)
   and 'CONTEXT\'s "Box flags" block' in _pr19 and "Report only: never propose a flag change" in _pr19,
   "box flags: %s / %s / %s; calls %s" % (_f19, _f19b, _f19c, _calls19))

# ── R20 (v1.6, RECAP.3): the size basis is printed, a FACTS day figure is not ─────────────────────────────────────
_md20 = read(os.path.join(_w15, "cash_books.md")) if os.path.exists(os.path.join(_w15, "cash_books.md")) else ""
_f20 = CB.figures(_sc15) if _sc15 else set()
_sz = dict(NOTES_OK, cash_books=["SPX entries size on $4,200 from 2026-11-23 (was $5,000); QQQ on $1,050. "
                                 "C1 netted $1,224 on the day."])
_rw = dict(NOTES_OK, cash_books=["The Runaway made $127 on the day; C1 netted $1,224."])
_pr20 = re.sub(r"\s+", " ", read(os.path.join(TOOLS, "daily_recap.prompt")))
ck("R20", {1050, 4200, 5000} <= _f20 and 127 not in _f20
   and "Entry sizes (per entry, as the boxes trade them; paper is sized as cash): QQQ $1,050; SPX $4,200 from "
       "2026-11-23 (was $5,000); per contract unchanged." in _md20
   and DR.cash_problems(_sz, _sc15) == [] and any("$127" in x for x in DR.cash_problems(_rw, _sc15))
   and 'its "Entry sizes" line included; for the day, its "The day" rows' in _pr20
   and "is not a scoreboard figure and never goes in this commentary" in _pr20,
   "sizes %s; kept %s; withheld %s" % (sorted(x for x in _f20 if x in (127, 1050, 4200, 5000)),
                                         DR.cash_problems(_sz, _sc15) if _sc15 else "?",
                                         DR.cash_problems(_rw, _sc15) if _sc15 else "?"))

# ── R21 (v1.6, CAL.1): the PDF's schedule section ────────────────────────────────────────────────────────────────
_bs21 = read(os.path.join(TOOLS, "daily_brief.py"))
ck("R21", '"7. The schedule, now to tomorrow 17:00 ET"' in _bs21 and "import calendar_view as CV" in _bs21
   and "CV.build(now)" in _bs21 and "CV.table_rows(cal)" in _bs21 and 'cal["summary"]' in _bs21
   and 'f"Schedule: NOT READ ({cerr}).' in _bs21
   and _bs21.find("7. The schedule") < _bs21.find("# ── sources ──"),
   "daily_brief section 7 from tools/calendar_view.py")

# ── R22 (v1.6, RECAP.3): the SPX cash budget follows the 2026-11-23 change ───────────────────────────────────────
_bs22 = read(os.path.join(TOOLS, "daily_brief.py"))
_ns22 = {}
_m22 = re.search(r"^CASH_BUDGET = .*?^def cash_budget\(sym, day\):.*?(?=^\S)", _bs22, re.M | re.S)
if _m22:
    exec(compile(_m22.group(0), "daily_brief.cash_budget", "exec"), _ns22)
_cb22 = _ns22.get("cash_budget")
ck("R22", bool(_cb22) and _cb22("SPX", "2026-11-20") == 5000.0 and _cb22("SPX", "2026-11-23") == 4200.0
   and _cb22("SPX", "2026-12-07") == 4200.0 and _cb22("QQQ", "2026-11-20") == _cb22("QQQ", "2026-11-23") == 1050.0
   and 'budget = cash_budget(r["symbol"], day)' in _bs22 and "money(cash_budget('SPX', day)" in _bs22
   and "CASH_BUDGET[" not in _bs22.replace("CASH_BUDGET[sym]", ""),
   "SPX 5000 before 2026-11-23, 4200 from it; QQQ 1050; the re-scale and the sizing line use it")

shutil.rmtree(TMP, ignore_errors=True)
print()
if FAILS:
    print(f"RED — {len(FAILS)} of {len(RAN)} check(s) failed: {' '.join(FAILS)}")
    sys.exit(1)
print(f"GREEN — {len(RAN)} checks")
