#!/usr/bin/env python3
"""
day_trader_pro/tests/check_daily_recap.py  v1.10
v1.10 2026-11-26  dtp r585 / LEADS.1 (daily_recap v1.8, daily_recap.sh v1.4, daily_brief v1.9). The operator,
      2026-11-26: "If you could include in the daily recap any standing leads under evaluation that made forward
      progress (further study, shadow, seeded a new study, or recommend incorporating)." R11 wants daily_brief v1.9;
      R26 finds the recommendations as section 9, still last; R29 passes a fixture --leads and holds lead_recs to the
      no-APPROVED rule; R6 wants the real ~/reviews/schedule/leads.tsv untouched by the wrapper's run. NEW (each BORN
      RED on 38d06e2):
  R31 the section is present: daily_brief has "8. Leads — forward progress" after section 7 and before section 9,
      from daily_recap.lead_section (head line, the table, the "Also moved" line, notes, NOT READ on a failure); the
      wrapper passes --leads "$LEADS" to context, recs and the brief, LEADS is $REVIEWS/schedule/leads.tsv (no new
      env variable), the brief takes --leads
  R32 only the DAY's rows: from a fixture ledger, the leads whose last_progress is the day and no other (earlier,
      later, blank), recommend-incorporating first, CLOSED last; a FORWARD / FORWARD-SHADOW row carries a forward
      cell, any other "-"; more than LEAD_ROWS_MAX moved leads cap the table, the rest on one "Also moved today" line
  R33 graceful on an empty or missing ledger: missing -> "No lead progress today." and "Leads ledger NOT READ (not
      found: ...)", a header-only ledger -> "Standing leads: none.", a bad header -> NOT READ, a quiet day -> the
      standing leads counted by status (closed apart); context prints NOT READ / (none) and goes on
  R34 no crash on a malformed row: a short row, a long row, a row with no id and a row whose last_progress is not a
      date are each skipped with a note, the good rows still listed; more than three notes fold into one line;
      lead_recs and context on the same ledger run clean
  R35 the forward line is dated: the newest FORWARD*SUMMARY.md's Status line labelled with the file's own ET date and
      time and the lead's decision read; a name without its date suffix resolves to its one folder; a *_TEST* dry run
      only -> "no forward record yet (dry run only)", none -> "no forward summary yet"; a summary written after the
      day's 17:00 says "after this recap"; the PARK "Sessions ..." form is read too
  R36 recommend incorporating becomes a recommendation: rec_append with the leads ledger appends one NEW decision row
      "Incorporate lead L-nn: ..." with [ref L-nn] for a lead that progressed on the day and recommends it, nothing
      for one that progressed earlier or only moved forward; a re-run appends nothing; a lead breaking the proposal
      rules is refused by name; `recs` through main() with --leads appends it; context lists the day's leads
v1.9  2026-11-24  dtp r584 / RECS.1 (daily_recap v1.7, daily_recap.sh v1.3, daily_brief v1.8, the prompt v1.11). The
      operator, 2026-11-24: "I would like the final section to contain a summary of the recommendations so we can get
      those approved & scheduled." R11 wants daily_brief v1.8; R23 the prompt v1.11; R18 counts three --runaway-watch
      passes in the wrapper (validate, append and now recs); R6 allows the wrapper's write to
      the sandbox ledger (REV/schedule/recommendations.tsv) and wants the real ~/reviews/schedule/recommendations.tsv
      untouched. NEW (each BORN RED on dbe68da):
  R26 the section exists and is LAST: daily_brief has "8. Recommendations — for approval" after section 7, no h1 after
      it (only the Sources list), its table from daily_recap.rec_section (#, ID, What, Why, Type, Touches, Proposed
      slot, Status) and the refusals under it; the wrapper passes --recs to context, the recs step and the brief
  R27 the ledger append: created with its header; the queued proposal and the maintenance item become NEW rows
      REC-20261124-1/-2 (an unqueued proposal does not); a session line is kept, and refused by name for a bad type, a
      second line, an invented dollar figure, a retired strategy, an over-long line, a missing field and a resting
      take-profit; a cash-readiness file's row is dated its own day (REC-20261123-1, CARRIED on 11-24), a bad one is
      refused; DE-DUPES: a near-duplicate line in the same notes, a re-run (bytes unchanged), a line matching a
      DECLINED row's words and a maintenance id already in the ledger ([ref]) append nothing
  R28 it carries open ledger items: on 11-24 an 11-20 NEW row reads "CARRIED from 11-20", an 11-24 NEW row NEW, an
      APPROVED row decided 11-23 "APPROVED-scheduled" with its slot, a DECLINED row decided 11-23 "DECLINED 11-23";
      an old APPROVED (slot past), an old DECLINED and a future row are left out; NEW, CARRIED, APPROVED, DECLINED in
      that order; slots from a fixed calendar: a queued box study the next study dispatch, control work a free
      weekday-evening hour clear of a planned row (each hour used once), box work a Sunday block, a decision the
      operator's reply; no calendar: NOT READ
  R29 it never sets APPROVED: a session line carrying "status": "APPROVED", an id and a slot is appended NEW with the
      appender's id and no slot; every existing line (the coordinator's APPROVED and DECLINED rows) is a byte prefix
      of the new file; the append path (rec_append, own_recs, session_recs, cash_ready_recs) holds no "APPROVED" or
      "DECLINED" literal; `recs` through main() records the refusals in the notes
  R30 the wrapper's run appends the sandbox notes' two queued studies and maintenance (3 NEW rows); context lists the
      ledger; the prompt says one plain line for a yes or no, no new figures, never an id / status / slot / date, the
      cash-readiness rows come as CARRIED
v1.8  2026-11-24  dtp r583 / CASHBOOK.3 (cash_books v1.6, daily_brief v1.7, the prompt v1.10). R11 wants daily_brief
      v1.7; R23 the prompt v1.10. NEW:
  R25 C5 beside C1-C4 in the recap: on a fixture through 2026-11-25 the board (context's cash_books.md) carries C5's
      own forward window, the hindsight tag and note, and the validator passes a commentary quoting C5's forward
      figures; daily_brief v1.7 section 5b lists every scored book and takes C5's Fwd columns from forward_c5, never
      C1-C4's forward window; the prompt says C5's in-sample and combined figures are never evidence and only its
      forward figures count (from 2026-11-24, apart from C1-C4's 11-23). BORN RED on 926bf64.
v1.7  2026-11-23  dtp r581 / REFUSE.1 + the SPX size dates (daily_recap v1.6, cash_books v1.5, daily_brief v1.6, the
      prompt v1.9). The operator moved SPX back to $5,000 (2026-11-23 18:41 ET): R11 wants daily_brief v1.6; R20's
      Entry sizes line is the 11-23 one (SPX $4,200 on 2026-11-23 only, $5,000 every other day); R22 cash_budget is SPX
      $5,000 on 2026-11-20, $4,200 on 2026-11-23, $5,000 on 2026-11-24 and 2026-12-07. NEW:
  R23 context's "Fires that booked no trade" block: NOT READ with no refusals file; from a file, one line per box,
      setup and side with each reason and its count, "no fill" only for the rows that say so; the prompt quotes the
      reason and writes "no fill" only where the block does. BORN RED on 5621ada.
  R24 cash_books.size_on: SPX 5000 / 4200 / 5000 on 2026-11-20 / 2026-11-23 / 2026-11-24 (QQQ 1050 throughout); the
      line for a 2026-11-24 board reads SPX $5,000 ($4,200 on 2026-11-23 only); figures() holds 1050, 4200, 5000; the
      recap and Saturday prompts no longer say SPX sizes on $4,200 from 2026-11-23. BORN RED on 5621ada.
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
real_recs = os.path.expanduser("~/reviews/schedule/recommendations.tsv")
rr0 = os.stat(real_recs).st_mtime_ns if os.path.exists(real_recs) else None
real_leads = os.path.expanduser("~/reviews/schedule/leads.tsv")             # v1.10: read only, never written
rl0 = os.stat(real_leads).st_mtime_ns if os.path.exists(real_leads) else None
SBRECS = os.path.join(REV, "schedule", "recommendations.tsv")              # v1.9: the sandbox ledger
r6 = wrap([], "2026-11-23T17:00")
after = snapshot(SB)
R6_LEDGER = read(SBRECS) if os.path.exists(SBRECS) else ""
allowed = (NOTESD + "/", OUTD + "/", QUEUE, LEDGER, LOG, WROOT + "/")
changed = [p for p in after if before.get(p) != after[p]]
outside = [p for p in changed if not (p == QUEUE or p.startswith(QUEUE + ".bak_recap_") or p in (LEDGER, LOG, SBRECS)
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
rr1 = os.stat(real_recs).st_mtime_ns if os.path.exists(real_recs) else None
rl1 = os.stat(real_leads).st_mtime_ns if os.path.exists(real_leads) else None
ro1 = snapshot(real_out) if os.path.isdir(real_out) else {}
ck("R6", r6.returncode == 0 and not outside and not work_left and iso and unatt and perm and restored
   and rq0 == rq1 and ro0 == ro1 and rr0 == rr1 and rl0 == rl1,
   "changed outside the allowed paths: %s; WORK left: %s; isolated %s, unattended+TMPDIR %s, acceptEdits+add-dir %s; "
   "a session's queue edit restored (then the appender's own items): %s; the real queue and ~/reviews/daily_brief "
   "and the real recommendations and leads ledgers untouched" % (outside[:3], work_left, iso, unatt, perm, restored))

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
ck("R11", comp and "daily_brief.py  v1.9" in gs and 'NOTES_DIR = os.path.expanduser("~/reviews/daily_brief/notes")' in gs
   and "--facts" in gs and "--summary-json" in gs and "/home/ubuntu/venvs/daily_brief" in gs
   and not os.path.exists(os.path.join(TOOLS, "venv")) and not os.path.exists(os.path.join(TOOLS, "notes"))
   and "11-20 showed" not in gs and os.path.exists(os.path.join(TOOLS, "daily_brief.requirements.txt")),
   "tools/daily_brief.py v1.9 compiles; notes under ~/reviews/daily_brief/notes; no venv or notes in the repo")

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
   and "RWATCH    $WORK/runaway_watch.md" in _ws18 and _ws18.count('--runaway-watch "$WORK/runaway_watch.json"') == 3   # v1.9: validate, append, recs
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
_sz = dict(NOTES_OK, cash_books=["SPX entries sized on $4,200 on 2026-11-23 only ($5,000 otherwise); QQQ on $1,050. "
                                 "C1 netted $1,224 on the day."])
_rw = dict(NOTES_OK, cash_books=["The Runaway made $127 on the day; C1 netted $1,224."])
_pr20 = re.sub(r"\s+", " ", read(os.path.join(TOOLS, "daily_recap.prompt")))
ck("R20", {1050, 4200, 5000} <= _f20 and 127 not in _f20
   and "Entry sizes (per entry, as the boxes trade them; paper is sized as cash): QQQ $1,050; SPX $4,200 on "
       "2026-11-23 only, $5,000 every other day; per contract unchanged." in _md20
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
   and _cb22("SPX", "2026-11-24") == 5000.0 and _cb22("SPX", "2026-12-07") == 5000.0 and _cb22("QQQ", "2026-11-20") == _cb22("QQQ", "2026-11-23") == 1050.0
   and 'budget = cash_budget(r["symbol"], day)' in _bs22 and "money(cash_budget('SPX', day)" in _bs22
   and "CASH_BUDGET[" not in _bs22.replace("CASH_BUDGET[sym]", ""),
   "SPX 5000 on 11-20, 4200 on 11-23 only, 5000 on 11-24 and 12-07; QQQ 1050; the re-scale and the sizing line use it")

# ── R23 (v1.7, REFUSE.1): the recap context names each fire's refusal reason ──────────────────────────────────────
_c15 = read(os.path.join(_w15, "context.md")) if os.path.exists(os.path.join(_w15, "context.md")) else ""
_rf = getattr(DR, "refusal_block", None)
_tr23 = os.path.join(TMP, "r23", "trades")
os.makedirs(_tr23, exist_ok=True)
_nr23 = _rf("2026-11-23", _tr23) if _rf else []
write(os.path.join(TMP, "r23", "refusals", "2026-11-23.csv"),
      "sym,strategy,direction,plan_id,fired_et,state,terminal_reason,outcome,reason\n"
      "SPX,RunawayContinuation,short,aaaa1111,09:40:04,EXPIRED,superseded — never filled,sizing_rejected insufficient_"
      "capital: need $4340.00/contract,sizing_rejected insufficient_capital: need $4340.00/contract\n"
      "SPX,RunawayContinuation,short,bbbb2222,09:41:48,TRIGGERED,,gate_block:commit_abandoned,gate_block:commit_abandoned\n"
      "QQQ,RunawayContinuation,short,cccc3333,09:53:48,TRIGGERED,,gate_block:commit_abandoned,gate_block:commit_abandoned\n"
      "NVDA,LiquidityHunt,long,dddd4444,10:29:48,TRIGGERED,,,no fill\n")
_r23 = _rf("2026-11-23", _tr23) if _rf else []
_j23 = "\n".join(_r23)
_pr23 = re.sub(r"\s+", " ", read(os.path.join(TOOLS, "daily_recap.prompt")))
ck("R23", bool(_rf) and "Fires that booked no trade" in _c15 and any("NOT READ" in x for x in _nr23)
   and "SPX RunawayContinuation short: 2 fire(s) 09:40:04-09:41:48, none traded" in _j23
   and "sizing_rejected x1" in _j23 and "gate_block:commit_abandoned x1" in _j23
   and "QQQ RunawayContinuation short: 1 fire(s) 09:53:48-09:53:48, none traded; gate_block:commit_abandoned x1; "
       "last plan cccc3333 TRIGGERED" in _j23
   and "NVDA LiquidityHunt long: 1 fire(s) 10:29:48-10:29:48, none traded; no fill x1" in _j23
   and _j23.count("no fill") == 2 and _j23.count("no fill x") == 1
   and 'write "no fill" ONLY where the block says "no fill"' in _pr23
   and "A FIRE THAT DID NOT TRADE IS A REFUSAL, NOT A FILL FAILURE" in _pr23 and "daily_recap.prompt v1.11" in _pr23,
   "refusal block: %s" % (_r23[1:] or _nr23))

# ── R24 (v1.7): SPX $5,000 again from 2026-11-24, $4,200 on 2026-11-23 only ─────────────────────────────────────────
_so = getattr(CB, "size_on", None)
_sc24 = {"sizes": [{"sym": a, "usd": _so(a, "2026-11-24"), "base": u,
                    "dated": [{"from": lo, "to": hi, "usd": x} for lo, hi, x in dt]} for a, u, dt in CB.SIZES]} if _so else {}
_pb24 = read(os.path.join(TOOLS, "saturday_brief.prompt"))
ck("R24", bool(_so) and [_so("SPX", d) for d in ("2026-11-20", "2026-11-23", "2026-11-24")] == [5000, 4200, 5000]
   and {_so("QQQ", d) for d in ("2026-11-20", "2026-11-23", "2026-11-24")} == {1050}
   and CB.size_line(_sc24) == "Entry sizes (per entry, as the boxes trade them; paper is sized as cash): QQQ $1,050; "
                              "SPX $5,000 ($4,200 on 2026-11-23 only); per contract unchanged."
   and {1050, 4200, 5000} <= CB.figures(dict(_sc24, windows={}))
   and "$4,200 from 2026-11-23" not in _pr23 and "$4,200 an entry from 2026-11-23" not in _pr23
   and "SPX $5,000 an entry ($4,200 on 2026-11-23 only)" in _pr23
   and "SPX sizes on $4,200 from 2026-11-23" not in _pb24 and "SPX sizes on $5,000, except $4,200 on 2026-11-23 only." in _pb24,
   "size_on SPX 11-20/11-23/11-24 %s; line %s" % ([_so("SPX", d) for d in ("2026-11-20", "2026-11-23", "2026-11-24")]
                                                  if _so else "?", CB.size_line(_sc24) if _so else "?"))

# ── R25 (v1.8, CASHBOOK.3): C5 beside C1-C4 ─────────────────────────────────────────────────────────────────────────
_ok25, _m25 = False, ""
try:
    _t25 = os.path.join(TMP, "trades25")
    os.makedirs(_t25, exist_ok=True)
    _h25 = ("sym,trade_id,strategy,direction,contracts,entry_premium,exit_premium,pnl_usd,entry_time,exit_time,"
            "exit_reason,fee\n")
    for _d, _rows in (("2026-11-20", [("UNH", "RunawayContinuation", 300, 2)]),
                      ("2026-11-23", [("QQQ", "PARK", 500, 3)]),
                      ("2026-11-24", [("SPX", "RunawayContinuation", 1234, 2), ("NVDA", "RunawayContinuation", -900, 2)]),
                      ("2026-11-25", [("CVX", "RunawayContinuation", -50, 1)])):
        with open(os.path.join(_t25, _d + ".csv"), "w") as _fh:
            _fh.write(_h25 + "".join("%s,t,%s,long,1,1,1,%s,%sT15:00:00+00:00,%sT16:00:00+00:00,x,%s\n"
                                     % (s, st, pn, _d, _d, fe) for s, st, pn, fe in _rows))
    _sc25 = CB.score("2026-11-25", day="2026-11-25", trades_dir=_t25)
    _md25 = CB.render_md(_sc25)
    _f25 = (_sc25["windows"].get("forward_c5") or {}).get("books", {}).get("C5") or {}
    _good25 = dict(NOTES_OK, cash_books=["C5 has two forward sessions: net $1,181 on its own forward window from "
                                         "11-24 (n 2); a small sample."])
    _bs25 = read(os.path.join(TOOLS, "daily_brief.py"))
    _pb25 = re.sub(r"\s+", " ", read(os.path.join(TOOLS, "saturday_brief.prompt")))
    _ok25 = (_f25.get("n") == 2 and _f25.get("net") == 1181 and "C5" not in _sc25["windows"]["forward"]["books"]
             and "## C5 forward" in _md25 and "(hindsight list; forward from 11-24)" in _md25
             and CB.HINDSIGHT_NOTE in _md25 and DR.cash_problems(_good25, _sc25) == []
             and any("$9,999" in x for x in DR.cash_problems(dict(NOTES_OK, cash_books=["C5 made $9,999."]), _sc25))
             and 'src = W.get("forward_c5") if b == "C5" else fwc' in _bs25 and 'if b not in sc["books"]:' in _bs25
             and "5b. The cash candidate books C1-C4 and C5" in _bs25
             and "C5'S IN-SAMPLE AND COMBINED FIGURES ARE NEVER EVIDENCE" in _pr23
             and "ONLY C5'S FORWARD FIGURES COUNT" in _pr23 and "cash_candidate_c5_20261124/PREREG.md" in _pr23
             and "(hindsight list; forward from 11-24)" in _pr23 and "apart from C1-C4's forward window" in _pr23
             and "C5'S IN-SAMPLE AND COMBINED FIGURES ARE NEVER EVIDENCE" in _pb25
             and "ONLY C5'S FORWARD FIGURES COUNT" in _pb25 and "cash_candidate_c5_20261124/PREREG.md" in _pb25)
    _m25 = "C5 forward %s; board tag %s" % ({k: _f25.get(k) for k in ("n", "net")},
                                            "(hindsight list; forward from 11-24)" in _md25)
except Exception as e:                                   # noqa: BLE001 (HEAD: no C5)
    _m25 = "%s: %s" % (type(e).__name__, e)
ck("R25", _ok25, _m25)

# ── R26-R30 (v1.9, RECS.1): the recommendations section and its ledger ─────────────────────────────────────────────
_HDR26 = ["#", "ID", "What", "Why", "Type", "Touches", "Proposed slot", "Status"]
_LH = "id\tdate\twhat\twhy\ttype\ttouches\tstatus\tslot\tdecided_on\tnote\n"


def _lrow(i, d, what, st, slot="", dec="", note="", typ="fix", tch="control", why="w"):
    return "\t".join([i, d, what, why, typ, tch, st, slot, dec, note]) + "\n"


def _ledger_rows(path):
    return [dict(zip(_LH.strip().split("\t"), ln.rstrip("\n").split("\t"))) for ln in read(path).splitlines()
            if ln and not ln.startswith("#") and not ln.startswith("id\t")]


# R26
try:
    _bs26 = read(os.path.join(TOOLS, "daily_brief.py"))
    _ws26 = read(WRAP)
    _i8 = _bs26.find('P("9. Recommendations — for approval", "h1")')   # v1.10: section 9 (the leads are 8)
    _after8 = _bs26[_i8:] if _i8 >= 0 else ""
    _sec = DR.rec_section("2026-11-24", os.path.join(TMP, "no_ledger.tsv"), None, "x")
    _ok26 = (_i8 > _bs26.find('P("7. The schedule, now to tomorrow 17:00 ET", "h1")') > 0
             and _i8 > _bs26.find('P("8. Leads — forward progress", "h1")') > 0
             and _i8 < _bs26.find("# ── sources ──") and _after8.count('"h1")') == 1
             and "DR.rec_section(day, ledger or RECS_DEFAULT, cal, cerr, now)" in _bs26
             and "rsec, rerr = recommendations(day, recs)" in _bs26 and 'notes.get("recommendations_refused")' in _bs26
             and 'f"Recommendations: NOT READ ({rerr}).' in _bs26 and _sec["rows"] == [_HDR26]
             and '--recs "$RECS"' in _ws26 and _ws26.count('"$RECS"') >= 3 and 'recs --day "$DAY"' in _ws26)
    _m26 = "section 9 at %d (sections 7 and 8 before it, sources after it, %d h1 from it); header %s" % (
        _i8, _after8.count('"h1")'), _sec["rows"][0])
except Exception as e:                                   # noqa: BLE001 (HEAD: no section 8, no rec_section)
    _ok26, _m26 = False, "%s: %s" % (type(e).__name__, e)
ck("R26", _ok26, _m26)

# R27
try:
    _d27 = os.path.join(TMP, "r27")
    _L27 = os.path.join(_d27, "schedule", "recommendations.tsv")
    _cr27 = os.path.join(_d27, "cash_readiness")
    write(os.path.join(_cr27, "2026-11-23.tsv"), "what\twhy\ttype\ttouches\n"
          "Pin the QQQ ladder's cancel time in the cash checklist\tThe 11-23 replay walked four rungs.\tfix\tboxes\n")
    write(os.path.join(_cr27, "2026-11-24.tsv"), "what\twhy\ttype\ttouches\nA bad row\tx\tfix\tfleet\n")
    _n27 = dict(NOTES_OK)
    _n27["proposals"] = [dict(proposal("Queued idea"), ws_id="WS.25", why="QQQ lost $100.00 today. More."),
                         proposal("Not queued idea")]
    _n27["recommendations"] = [
        {"what": "Re-run capture_all for the 11-23 candles", "why": "QQQ lost $100.00 on the day.", "type": "fix",
         "touches": "control"},
        {"what": "Re-run capture_all for the 11-23 candles!", "why": "again", "type": "fix", "touches": "control"},
        {"what": "Do x", "why": "y", "type": "chore", "touches": "control"},
        {"what": "Do two\nlines", "why": "y", "type": "fix", "touches": "control"},
        {"what": "Cut AMD", "why": "It lost $9,999.", "type": "decision", "touches": "none"},
        {"what": "Bring back the butterfly", "why": "y", "type": "study", "touches": "boxes"},
        {"what": "x" * 230, "why": "y", "type": "fix", "touches": "control"},
        {"what": "No touches", "why": "y", "type": "fix"},
        {"what": "Place a resting take-profit order at +50%", "why": "y", "type": "fix", "touches": "boxes"}]
    _f27 = DR.rec_figures(facts={"pnl_mark_usd": -100.0})
    _new27, _dup27, _ref27, _ = DR.rec_append("2026-11-24", _n27, _L27, _cr27, _f27)
    _b27 = read(_L27)
    _rows27 = _ledger_rows(_L27)
    _ids27 = [r["id"] for r in _rows27]
    _byid = {r["id"]: r for r in _rows27}
    _refj = " | ".join("%s: %s" % (w, "; ".join(y)) for w, y in _ref27)
    _new27b, _dup27b, _, _ = DR.rec_append("2026-11-24", _n27, _L27, _cr27, _f27)
    _same = read(_L27) == _b27
    # a DECLINED row's words, and a maintenance id already in the ledger, append nothing
    write(_L27, read(_L27) + _lrow("REC-20261120-1", "2026-11-20", "Rename the handoff label now the sweep is retired",
                                   "DECLINED", dec="2026-11-23"))
    _n27c = dict(NOTES_OK, proposals=[], recommendations=[
        {"what": "Rename the handoff label, now the sweep is retired", "why": "y", "type": "decision", "touches": "none"}])
    _new27c, _dup27c, _, _ = DR.rec_append("2026-11-25", _n27c, _L27, os.path.join(_d27, "none"), _f27)
    _ok27 = (_b27.startswith("# The recommendations ledger") and "\n" + _LH in _b27
             and _ids27 == ["REC-20261124-1", "REC-20261124-2", "REC-20261124-3", "REC-20261123-1"]
             and _byid["REC-20261124-1"]["type"] == "study" and _byid["REC-20261124-1"]["touches"] == "boxes"
             and "WS.25" in _byid["REC-20261124-1"]["what"] and "[ref WS.25]" in _byid["REC-20261124-1"]["note"]
             and _byid["REC-20261124-1"]["why"] == "QQQ lost $100.00 today."
             and _byid["REC-20261124-2"]["type"] == "maintenance" and "HYG.9" in _byid["REC-20261124-2"]["what"]
             and _byid["REC-20261124-2"]["touches"] == "control"
             and _byid["REC-20261124-3"]["what"] == "Re-run capture_all for the 11-23 candles"
             and _byid["REC-20261123-1"]["date"] == "2026-11-23" and "cash-readiness review 2026-11-23" in
             _byid["REC-20261123-1"]["note"]
             and all(r["status"] == "NEW" and r["slot"] == "" and r["decided_on"] == "" for r in _rows27)
             and "Not queued idea" not in _b27 and len(_dup27) == 1
             and all(x in _refj for x in ("type 'chore'", "what is more than one line", "$9,999", "retired strategy",
                                          "over 200 characters", "missing touches", "resting take-profit",
                                          "touches 'fleet'"))
             and _new27b == [] and _same and _new27c == [] and ("Rename the handoff label, now the sweep is retired", "REC-20261120-1") in _dup27c)
    _n27d = dict(NOTES_OK, proposals=[])                 # the maintenance HYG.9 again, on another day: its [ref]
    _new27d, _dup27d, _, _ = DR.rec_append("2026-11-25", _n27d, _L27, os.path.join(_d27, "none"), _f27)
    _ok27 = _ok27 and _new27d == [] and _dup27d and _dup27d[0][1] == "REC-20261124-2"
    _m27 = "ids %s; dups %s / %s / %s; refused %s" % (_ids27, _dup27, _dup27c, _dup27d if "_dup27d" in dir() else "?",
                                                     _refj[:300])
except Exception as e:                                   # noqa: BLE001 (HEAD: no rec_append)
    _ok27, _m27 = False, "%s: %s" % (type(e).__name__, e)
ck("R27", _ok27, _m27)

# R28
try:
    import calendar_view as CV  # noqa: E402
    _L28 = os.path.join(TMP, "r28", "recommendations.tsv")
    write(_L28, "# c\n" + _LH
          + _lrow("REC-20261120-1", "2026-11-20", "Old open control fix", "NEW")
          + _lrow("REC-20261124-1", "2026-11-24", "Run study WS.25 blind in the nightly queue: x", "NEW", typ="study",
                  tch="boxes", note="daily recap 2026-11-24 P1 [ref WS.25]")
          + _lrow("REC-20261124-2", "2026-11-24", "Second control fix", "NEW")
          + _lrow("REC-20261124-3", "2026-11-24", "Sunday box fix", "NEW", tch="boxes")
          + _lrow("REC-20261124-4", "2026-11-24", "A decision", "NEW", typ="decision", tch="none")
          + _lrow("REC-20261123-1", "2026-11-23", "Approved recently", "APPROVED", slot="2026-11-29 10:00-12:00 ET",
                  dec="2026-11-23")
          + _lrow("REC-20261110-1", "2026-11-10", "Approved long ago", "APPROVED", slot="2026-11-12 18:30 ET",
                  dec="2026-11-10")
          + _lrow("REC-20261123-2", "2026-11-23", "Declined recently", "DECLINED", dec="2026-11-23")
          + _lrow("REC-20261110-2", "2026-11-10", "Declined long ago", "DECLINED", dec="2026-11-10")
          + _lrow("REC-20261125-1", "2026-11-25", "From the future", "NEW"))
    _now28 = datetime(2026, 11, 24, 17, 10, tzinfo=ET)
    _units28 = [
        {"id": "dtp-morning.timer", "calendars": ["Mon..Fri *-*-* 09:15:00 America/New_York"], "last_min": 1.0},
        {"id": "dtp-eod-conductor.timer", "calendars": ["Mon..Fri *-*-* 16:05:00 America/New_York"], "last_min": 14.0},
        {"id": "dtp-study-dispatch.timer", "calendars": ["Mon..Thu *-*-* 17:15:00 America/New_York",
                                                         "Fri *-*-* 17:15:00 America/New_York"], "last_min": None}]
    _p28 = os.path.join(TMP, "r28", "planned.tsv")
    write(_p28, "date\tstart\tend\twhat\ttouches\n2026-11-24\t~17:45\t19:30\tcash-readiness review\tcontrol\n"
                "2026-11-29\t10:00\t12:00\tSunday fleet update\tboxes\n")
    _cal28 = CV.build(_now28, 7, _p28, units=_units28)
    _s28 = DR.rec_section("2026-11-24", _L28, _cal28, None, _now28)
    _r28 = {r[1]: r for r in _s28["rows"][1:]}
    _nc = DR.rec_section("2026-11-24", _L28, None, "no systemd", _now28)
    _rnc = {r[1]: r for r in _nc["rows"][1:]}
    _ok28 = ([r[1] for r in _s28["rows"][1:]] == ["REC-20261124-1", "REC-20261124-2", "REC-20261124-3",
                                                   "REC-20261124-4", "REC-20261120-1", "REC-20261123-1",
                                                   "REC-20261123-2"]
             and [r[0] for r in _s28["rows"][1:]] == [str(i) for i in range(1, 8)]
             and _r28["REC-20261120-1"][7] == "CARRIED from 11-20" and _r28["REC-20261124-2"][7] == "NEW"
             and _r28["REC-20261123-1"][7] == "APPROVED-scheduled" and _r28["REC-20261123-1"][6] == "2026-11-29 10:00-12:00 ET"
             and _r28["REC-20261123-2"][7] == "DECLINED 11-23"
             and _r28["REC-20261124-1"][6] == "next study dispatch Tue 11-24 17:15 ET (queued: it runs unless declined)"
             and _r28["REC-20261124-2"][6] == "Tue 11-24 19:30-20:30 ET (control)"
             and _r28["REC-20261120-1"][6] == "Tue 11-24 20:30-21:30 ET (control)"
             and _r28["REC-20261124-3"][6] == "Sun 11-29 12:00-14:00 ET (Sunday box work)"
             and _r28["REC-20261124-4"][6] == "your reply (no slot needed)"
             and _rnc["REC-20261124-2"][6].startswith("calendar NOT READ (no systemd)")
             and _rnc["REC-20261124-4"][6] == "your reply (no slot needed)"
             and any("calendar NOT READ" in x for x in _nc["problems"]))
    _m28 = "; ".join("%s %s [%s]" % (r[1], r[7], r[6]) for r in _s28["rows"][1:])
except Exception as e:                                   # noqa: BLE001 (HEAD: no rec_section)
    _ok28, _m28 = False, "%s: %s" % (type(e).__name__, e)
ck("R28", _ok28, _m28)

# R29
try:
    import ast as _ast
    _L29 = os.path.join(TMP, "r29", "recommendations.tsv")
    _pre29 = ("# c\n" + _LH + _lrow("REC-20261123-1", "2026-11-23", "Approved by the operator", "APPROVED",
                                    slot="2026-11-25 18:30 ET", dec="2026-11-23")
              + _lrow("REC-20261123-2", "2026-11-23", "Declined by the operator", "DECLINED", dec="2026-11-23"))
    write(_L29, _pre29)
    _n29p = os.path.join(TMP, "r29", "notes.json")
    write(_n29p, json.dumps(dict(NOTES_OK, proposals=[], maintenance={}, recommendations=[
        {"what": "Self-approved line", "why": "y", "type": "fix", "touches": "control", "status": "APPROVED",
         "id": "REC-20991231-9", "slot": "2026-11-25 18:30 ET", "decided_on": "2026-11-24"},
        {"what": "Bad line", "why": "y", "type": "nope", "touches": "control"}])))
    _rc29 = DR.main(["recs", "--day", "2026-11-24", "--notes", _n29p, "--ledger", _L29,
                     "--cash-ready", os.path.join(TMP, "r29", "none"), "--leads", os.path.join(TMP, "r29", "none.tsv")])
    _t29 = read(_L29)
    _rows29 = _ledger_rows(_L29)
    _src = read(HELPER)
    _tree = _ast.parse(_src)
    _fns = {n.name: _ast.get_source_segment(_src, n) for n in _tree.body if isinstance(n, _ast.FunctionDef)}
    _path = "".join(_fns.get(k, "MISSING") for k in ("rec_append", "own_recs", "session_recs", "cash_ready_recs",
                                                     "lead_recs"))
    _nn29 = json.loads(read(_n29p))
    _ok29 = (_rc29 == 0 and _t29.startswith(_pre29) and len(_rows29) == 3
             and _rows29[2]["id"] == "REC-20261124-1" and _rows29[2]["status"] == "NEW"
             and _rows29[2]["slot"] == "" and _rows29[2]["decided_on"] == ""
             and [r["status"] for r in _rows29[:2]] == ["APPROVED", "DECLINED"]
             and "MISSING" not in _path and "APPROVED" not in _path and "DECLINED" not in _path
             and any("type 'nope'" in x for x in _nn29.get("recommendations_refused", [])))
    _m29 = "rows %s" % [(r["id"], r["status"], r["slot"]) for r in _rows29]
except Exception as e:                                   # noqa: BLE001 (HEAD: no recs)
    _ok29, _m29 = False, "%s: %s" % (type(e).__name__, e)
except SystemExit as e:                                  # HEAD: argparse refuses the unknown `recs`
    _ok29, _m29 = False, "SystemExit %s (no `recs` command)" % e
ck("R29", _ok29, _m29)

# R30
try:
    _rows30 = [ln.split("\t") for ln in R6_LEDGER.splitlines() if ln.startswith("REC-")]
    _pr30 = re.sub(r"\s+", " ", read(os.path.join(TOOLS, "daily_recap.prompt")))
    _w30 = os.path.join(TMP, "w30")
    DR.main(["context", "--day", "2026-11-24", "--work", _w30, "--queue", _q17, "--notes-dir", os.path.join(TMP, "nd30"),
             "--studies", os.path.join(TMP, "st30"), "--weekly", os.path.join(TMP, "wk30"),
             "--otv5-backlog", os.path.join(TMP, "nobl"), "--hygiene", os.path.join(TMP, "hy30"),
             "--botlogs", os.path.join(TMP, "bl30"), "--trades", os.path.join(TMP, "tr30"), "--recs", _L28])
    _c30 = read(os.path.join(_w30, "context.md"))
    _ok30 = ([r[0] for r in _rows30] == ["REC-20261123-1", "REC-20261123-2", "REC-20261123-3"]
             and all(r[6] == "NEW" for r in _rows30) and "WS.25" in _rows30[0][2] and "WS.26" in _rows30[1][2]
             and "HYG.9" in _rows30[2][2]
             and "Recommendations already in the ledger" in _c30 and "REC-20261123-2 2026-11-23 DECLINED" in _c30
             and "REC-20261125-1" not in _c30
             and '"recommendations":' in _pr30 and "ONE PLAIN LINE THE OPERATOR CAN ANSWER YES OR NO TO" in _pr30
             and "NEVER WRITE AN ID, A STATUS, A SLOT OR A DATE" in _pr30 and "no new figures" in _pr30
             and "only the coordinator marks one APPROVED or DECLINED" in _pr30 and "as CARRIED" in _pr30)
    _m30 = "wrapper ledger rows %s" % [(r[0], r[6], r[2][:30]) for r in _rows30]
except Exception as e:                                   # noqa: BLE001
    _ok30, _m30 = False, "%s: %s" % (type(e).__name__, e)
except SystemExit as e:                                  # HEAD: argparse refuses context's unknown --recs
    _ok30, _m30 = False, "SystemExit %s (context takes no --recs)" % e
ck("R30", _ok30, _m30)

# ── R31-R36 (v1.10, LEADS.1): the leads that made forward progress ─────────────────────────────────────────────────
_LCOLS = ["id", "opened", "lead", "source_study", "evidence", "status", "next_step", "decision_read", "last_progress",
          "progress_note"]
_LHDR = "\t".join(_LCOLS) + "\n"
_LT_HDR = ["ID", "Lead", "Status", "Progress today · next", "Forward scorer (last run before the recap)"]


def _lead(i, lead, st, lp, src="-", nxt="-", dr="-", note="moved", ev="ev"):
    return "\t".join([i, "2026-11-20", lead, src, ev, st, nxt, dr, lp, note]) + "\n"


def _mtime_et(p, y, mo, d, h, mi):
    t = datetime(y, mo, d, h, mi, tzinfo=ET).timestamp()
    os.utime(p, (t, t))


_D31 = os.path.join(TMP, "r31")
_ST31 = os.path.join(_D31, "studies")
# the studies: one with a real summary (11-25 19:05 ET), one dry run only, one with none, one written after the recap
write(os.path.join(_ST31, "ALPHA_EXITS_20261120", "FORWARD_SUMMARY.md"),
      "# FORWARD_SUMMARY - ALPHA\n\nGenerated.\n\n**Status:** NOT DECIDABLE: 3/20 counted sessions (from 2026-11-23). "
      "No decision may be taken.\n")
write(os.path.join(_ST31, "ALPHA_EXITS_20261120", "FORWARD_SUMMARY_TEST.md"), "**Status:** DRY 9/20 counted\n")
_mtime_et(os.path.join(_ST31, "ALPHA_EXITS_20261120", "FORWARD_SUMMARY.md"), 2026, 11, 25, 19, 5)
_mtime_et(os.path.join(_ST31, "ALPHA_EXITS_20261120", "FORWARD_SUMMARY_TEST.md"), 2026, 11, 26, 9, 0)
write(os.path.join(_ST31, "BETA_PARK_20261120", "FORWARD_S2_SUMMARY_TEST.md"), "# DRY RUN\nSessions: 2\n")
os.makedirs(os.path.join(_ST31, "GAMMA_NONE_20261120"), exist_ok=True)
write(os.path.join(_ST31, "DELTA_LATE_20261120", "FORWARD_SUMMARY.md"), "**Status:** NOT DECIDABLE: 4/20 counted.\n")
_mtime_et(os.path.join(_ST31, "DELTA_LATE_20261120", "FORWARD_SUMMARY.md"), 2026, 11, 26, 18, 45)
write(os.path.join(_ST31, "EPS_PARK_20261120", "FORWARD_SUMMARY.md"),
      "# PARK forward\n\nSessions scored: 5 (2026-11-30 .. 2026-12-04); index PARK fires with quotes: 7 of the pass "
      "bar's 20; booked PARK rows: 7\n")
_mtime_et(os.path.join(_ST31, "EPS_PARK_20261120", "FORWARD_SUMMARY.md"), 2026, 12, 4, 19, 1)
_L31 = os.path.join(_D31, "leads.tsv")
write(_L31, "# leads fixture\n" + _LHDR
      + _lead("L-01", "Alpha exits beat booked", "FORWARD", "2026-11-26", "ALPHA_EXITS_20261120", dr="~50 / ~100 sessions")
      + _lead("L-02", "Old lead moved yesterday", "FORWARD", "2026-11-25", "ALPHA_EXITS_20261120")
      + _lead("L-03", "Shadow lead", "FORWARD-SHADOW", "2026-11-26", "BETA_PARK / GAMMA_NONE_20261120",
              dr="20 index fires")
      + _lead("L-04", "Closed lead", "CLOSED-as-trigger", "2026-11-26")
      + _lead("L-05", "Parked lead", "PARKED", "2026-11-26", nxt="revisit later")
      + _lead("L-06", "Incorporate-worthy lead", "CHECKING", "2026-11-26", "ALPHA_EXITS_20261120",
              note="recommend incorporating after the live-fill check", ev="Booked edge held. Second sentence.")
      + _lead("L-07", "Future lead", "FORWARD", "2026-11-27")
      + _lead("L-08", "Never progressed", "INPUT", "")
      + _lead("L-09", "Late scorer lead", "FORWARD", "2026-11-26", "DELTA_LATE_20261120", dr="~50 sessions"))

# R31
try:
    _bs31 = read(os.path.join(TOOLS, "daily_brief.py"))
    _ws31 = read(WRAP)
    _i7 = _bs31.find('P("7. The schedule, now to tomorrow 17:00 ET", "h1")')
    _i8l = _bs31.find('P("8. Leads — forward progress", "h1")')
    _i9 = _bs31.find('P("9. Recommendations — for approval", "h1")')
    _mid = _bs31[_i8l:_i9] if 0 < _i8l < _i9 else ""
    _ok31 = (0 < _i7 < _i8l < _i9 and _mid.count('"h1")') == 1
             and "lsec, lerr = lead_progress(day, leads)" in _mid and 'f"Leads: NOT READ ({lerr}).' in _mid
             and 'lsec["lines"]' in _mid and 'lsec["rows"]' in _mid and 'lsec["more"]' in _mid
             and 'lsec["problems"]' in _mid
             and "DR.lead_section(day, ledger or LEADS_DEFAULT, now=now)" in _bs31
             and 'ap.add_argument("--leads"' in _bs31 and "build(day, notes, a.out, a.recs, a.leads)" in _bs31
             and 'LEADS="$REVIEWS/schedule/leads.tsv"' in _ws31 and _ws31.count('--leads "$LEADS"') == 3
             and "DAILY_RECAP_LEADS" not in _ws31 and 'recs --day "$DAY"' in _ws31)
    _m31 = "sections 7/8/9 at %d/%d/%d; --leads passes %d; h1 in section 8: %d" % (
        _i7, _i8l, _i9, _ws31.count('--leads "$LEADS"'), _mid.count('"h1")'))
except Exception as e:                                   # noqa: BLE001 (HEAD: no section 8 leads)
    _ok31, _m31 = False, "%s: %s" % (type(e).__name__, e)
ck("R31", _ok31, _m31)

# R32
try:
    _s32 = DR.lead_section("2026-11-26", _L31, _ST31)
    _r32 = {r[0]: r for r in _s32["rows"][1:]}
    _ids32 = [r[0] for r in _s32["rows"][1:]]
    # the cap: LEAD_ROWS_MAX + 3 leads moved on one day
    _n32 = DR.LEAD_ROWS_MAX + 3
    _Lcap = os.path.join(_D31, "cap.tsv")
    write(_Lcap, _LHDR + "".join(_lead("L-%02d" % k, "Lead %d" % k, "INPUT", "2026-11-26") for k in range(1, _n32 + 1)))
    _c32 = DR.lead_section("2026-11-26", _Lcap, _ST31)
    _ok32 = (_s32["rows"][0] == _LT_HDR and _ids32 == ["L-06", "L-01", "L-09", "L-03", "L-05", "L-04"]
             and "L-02" not in _r32 and "L-07" not in _r32 and "L-08" not in _r32
             and _s32["lines"][0].startswith("6 lead(s) moved on 11-26:")
             and _r32["L-05"][4] == "-" and _r32["L-04"][4] == "-" and _r32["L-06"][4] == "-"
             and _r32["L-01"][4] != "-" and _r32["L-03"][4] != "-"
             and _r32["L-06"][3].startswith("RECOMMEND INCORPORATING") and "next: revisit later" in _r32["L-05"][3]
             and _s32["more"] is None
             and len(_c32["rows"]) == DR.LEAD_ROWS_MAX + 1 and _c32["more"] is not None
             and _c32["more"].startswith("Also moved today: ") and _c32["more"].count("INPUT") == 3)
    _m32 = "rows %s; cap %d rows + more=%r" % (_ids32, len(_c32["rows"]) - 1, (_c32["more"] or "")[:60])
except Exception as e:                                   # noqa: BLE001 (HEAD: no lead_section)
    _ok32, _m32 = False, "%s: %s" % (type(e).__name__, e)
ck("R32", _ok32, _m32)

# R33
try:
    _miss33 = os.path.join(_D31, "missing.tsv")
    _a33 = DR.lead_section("2026-11-26", _miss33, _ST31)
    _Lh = os.path.join(_D31, "header_only.tsv")
    write(_Lh, "# only a header\n" + _LHDR)
    _b33 = DR.lead_section("2026-11-26", _Lh, _ST31)
    _Lb = os.path.join(_D31, "bad_header.tsv")
    write(_Lb, "id\tlead\tstatus\nL-01\tx\tFORWARD\n")
    _c33 = DR.lead_section("2026-11-26", _Lb, _ST31)
    _Le = os.path.join(_D31, "empty.tsv")
    write(_Le, "")
    _e33 = DR.lead_section("2026-11-26", _Le, _ST31)
    _q33 = DR.lead_section("2026-11-30", _L31, _ST31)
    _w33 = os.path.join(TMP, "w33")
    DR.main(["context", "--day", "2026-11-26", "--work", _w33, "--queue", _q17, "--notes-dir", os.path.join(TMP, "nd33"),
             "--studies", os.path.join(TMP, "st33"), "--weekly", os.path.join(TMP, "wk33"),
             "--otv5-backlog", os.path.join(TMP, "nobl"), "--hygiene", os.path.join(TMP, "hy33"),
             "--botlogs", os.path.join(TMP, "bl33"), "--trades", os.path.join(TMP, "tr33"),
             "--recs", os.path.join(TMP, "nr33.tsv"), "--leads", _miss33])
    _cx33 = read(os.path.join(_w33, "context.md"))
    _ok33 = (_a33["lines"] == ["No lead progress today.", "Leads ledger NOT READ (not found: %s)." % _miss33]
             and _a33["rows"] == [_LT_HDR]
             and _b33["lines"] == ["No lead progress today.", "Standing leads: none."] and _b33["rows"] == [_LT_HDR]
             and _c33["lines"][0] == "No lead progress today." and "NOT READ (header is" in _c33["lines"][1]
             and "NOT READ (header is" in _e33["lines"][1]
             and _q33["lines"] == ["No lead progress today.",
                                   "Standing leads: 4 FORWARD, 1 CHECKING, 1 FORWARD-SHADOW, 1 INPUT, 1 PARKED; "
                                   "1 closed."]
             and "Leads that progressed on 2026-11-26" in _cx33 and "  NOT READ (not found:" in _cx33)
    _m33 = "missing %s; header-only %s; bad header %s; quiet %s" % (_a33["lines"][1][:40], _b33["lines"][1],
                                                                    _c33["lines"][1][:40], _q33["lines"][1])
except Exception as e:                                   # noqa: BLE001
    _ok33, _m33 = False, "%s: %s" % (type(e).__name__, e)
except SystemExit as e:                                  # HEAD: context takes no --leads
    _ok33, _m33 = False, "SystemExit %s (context takes no --leads)" % e
ck("R33", _ok33, _m33)

# R34
try:
    _Lm = os.path.join(_D31, "malformed.tsv")
    write(_Lm, _LHDR
          + _lead("L-01", "Good lead", "FORWARD", "2026-11-26", "ALPHA_EXITS_20261120")
          + "L-02\tshort row\tFORWARD\t2026-11-26\n"
          + _lead("L-03", "Long row", "FORWARD", "2026-11-26").rstrip("\n") + "\textra\tcells\n"
          + _lead("", "No id", "FORWARD", "2026-11-26")
          + _lead("L-05", "Bad date", "FORWARD", "Thursday")
          + "\x00\x01 junk \t\n"
          + _lead("L-07", "Second good lead", "PARKED", "2026-11-26"))
    _s34 = DR.lead_section("2026-11-26", _Lm, _ST31)
    _ids34 = [r[0] for r in _s34["rows"][1:]]
    _pr34 = _s34["problems"]
    _lr34 = DR.lead_recs("2026-11-26", _Lm)
    _w34 = os.path.join(TMP, "w34")
    DR.main(["context", "--day", "2026-11-26", "--work", _w34, "--queue", _q17, "--notes-dir", os.path.join(TMP, "nd34"),
             "--studies", os.path.join(TMP, "st34"), "--weekly", os.path.join(TMP, "wk34"),
             "--otv5-backlog", os.path.join(TMP, "nobl"), "--hygiene", os.path.join(TMP, "hy34"),
             "--botlogs", os.path.join(TMP, "bl34"), "--trades", os.path.join(TMP, "tr34"),
             "--recs", os.path.join(TMP, "nr34.tsv"), "--leads", _Lm])
    _cx34 = read(os.path.join(_w34, "context.md"))
    _rows_m, _bad_m, _err_m = DR.read_leads(_Lm)
    _ok34 = (_ids34 == ["L-01", "L-07"] and len(_pr34) == 4 and _pr34[3] == "and 2 more malformed leads row(s)"
             and len(_bad_m) == 5 and any("L-02): 4 fields, not 10" in x for x in _bad_m)
             and any("12 fields, not 10" in x for x in _bad_m) and any("no id" in x for x in _bad_m)
             and any("'Thursday' is not a YYYY-MM-DD date" in x for x in _bad_m)
             and _err_m is None and _lr34 == ([], []) and "  L-01 FORWARD: Good lead" in _cx34)
    _m34 = "rows %s; notes %s" % (_ids34, _pr34)
except Exception as e:                                   # noqa: BLE001
    _ok34, _m34 = False, "%s: %s" % (type(e).__name__, e)
except SystemExit as e:
    _ok34, _m34 = False, "SystemExit %s" % e
ck("R34", _ok34, _m34)

# R35
try:
    _r35 = {r[0]: r for r in DR.lead_section("2026-11-26", _L31, _ST31)["rows"][1:]}
    _f1, _f3, _f9 = _r35["L-01"][4], _r35["L-03"][4], _r35["L-09"][4]
    _Lp = os.path.join(_D31, "park.tsv")
    write(_Lp, _LHDR + _lead("L-01", "PARK stop", "FORWARD", "2026-12-07", "EPS_PARK", dr="20 index fires"))
    _f_p = DR.lead_section("2026-12-07", _Lp, _ST31)["rows"][1][4]
    _ok35 = (_f1 == "11-25 19:05 ET: NOT DECIDABLE: 3/20 counted sessions (from 2026-11-23) · decision read ~50 / "
                    "~100 sessions"
             and _f3 == "no forward record yet (dry run only) · decision read 20 index fires"
             and DR.lead_study_dirs("BETA_PARK / GAMMA_NONE_20261120", _ST31) == ["BETA_PARK_20261120",
                                                                                 "GAMMA_NONE_20261120"]
             and DR.lead_study_dirs("../etc + operator direction 11-26", _ST31) == []
             and DR.forward_line("GAMMA_NONE_20261120", _ST31) == (None, False)
             and "lead_forward_cell" in read(HELPER)
             and _f9.startswith("11-26 18:45 ET, after this recap: NOT DECIDABLE: 4/20 counted")
             and _f_p.startswith("12-04 19:01 ET: Sessions scored: 5 (2026-11-30 .. 2026-12-04); index PARK fires "
                                 "with quotes: 7 of the pass bar's 20")
             and _f_p.endswith(" · decision read 20 index fires"))
    _m35 = "L-01 %r | L-03 %r | L-09 %r | PARK %r" % (_f1, _f3, _f9[:50], _f_p[:60])
except Exception as e:                                   # noqa: BLE001
    _ok35, _m35 = False, "%s: %s" % (type(e).__name__, e)
ck("R35", _ok35, _m35)

# R36
try:
    _L36 = os.path.join(TMP, "r36", "recommendations.tsv")
    _n36 = dict(NOTES_OK, proposals=[], maintenance={})
    _new36, _dup36, _ref36, _ = DR.rec_append("2026-11-26", _n36, _L36, os.path.join(TMP, "r36", "none"), set(), _L31)
    _rows36 = _ledger_rows(_L36)
    _b36 = read(_L36)
    _new36b, _dup36b, _, _ = DR.rec_append("2026-11-26", _n36, _L36, os.path.join(TMP, "r36", "none"), set(), _L31)
    _same36 = read(_L36) == _b36
    _new36c, _, _, _ = DR.rec_append("2026-11-25", _n36, _L36, os.path.join(TMP, "r36", "none"), set(), _L31)
    _Lr = os.path.join(TMP, "r36", "rule.tsv")
    write(_Lr, _LHDR + _lead("L-20", "Place a resting take-profit order at +50%", "RECOMMEND", "2026-11-26"))
    _, _, _ref36d, _ = DR.rec_append("2026-11-26", _n36, os.path.join(TMP, "r36", "rule_recs.tsv"),
                                     os.path.join(TMP, "r36", "none"), set(), _Lr)
    _L36e = os.path.join(TMP, "r36", "main_recs.tsv")
    _np36 = os.path.join(TMP, "r36", "notes.json")
    write(_np36, json.dumps(_n36))
    _rc36 = DR.main(["recs", "--day", "2026-11-26", "--notes", _np36, "--ledger", _L36e,
                     "--cash-ready", os.path.join(TMP, "r36", "none"), "--leads", _L31])
    _rows36e = _ledger_rows(_L36e)
    _ok36 = (len(_rows36) == 1 and _rows36[0]["id"] == "REC-20261126-1" and _rows36[0]["status"] == "NEW"
             and _rows36[0]["what"] == "Incorporate lead L-06: Incorporate-worthy lead"
             and _rows36[0]["why"] == "Booked edge held." and _rows36[0]["type"] == "decision"
             and _rows36[0]["touches"] == "none" and "[ref L-06]" in _rows36[0]["note"]
             and _rows36[0]["slot"] == "" and _new36b == [] and _same36 and _dup36b and _dup36b[0][1] == "REC-20261126-1"
             and _new36c == []
             and any(w == "lead L-20" and any("resting take-profit" in x for x in y) for w, y in _ref36d)
             and _rc36 == 0 and [r["what"] for r in _rows36e] == ["Incorporate lead L-06: Incorporate-worthy lead"])
    _m36 = "rows %s; re-run dups %s; refused %s" % ([(r["id"], r["what"][:40]) for r in _rows36], _dup36b,
                                                    [w for w, _y in _ref36d])
except Exception as e:                                   # noqa: BLE001 (HEAD: rec_append takes no leads)
    _ok36, _m36 = False, "%s: %s" % (type(e).__name__, e)
except SystemExit as e:
    _ok36, _m36 = False, "SystemExit %s (recs takes no --leads)" % e
ck("R36", _ok36, _m36)

shutil.rmtree(TMP, ignore_errors=True)
print()
if FAILS:
    print(f"RED — {len(FAILS)} of {len(RAN)} check(s) failed: {' '.join(FAILS)}")
    sys.exit(1)
print(f"GREEN — {len(RAN)} checks")
