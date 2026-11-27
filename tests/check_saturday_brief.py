#!/usr/bin/env python3
"""
day_trader_pro/tests/check_saturday_brief.py  v2.7
v2.7  2026-11-27  dtp r586 (SATLONG.1, REC-20261126-4). The operator, 2026-11-26: "that Saturday report should be the long
      form version of what was left out of the nightly reports to keep them lightweight & relevant". NEW S42-S47, the
      one new scorer tools/saturday_long.py DRIVEN on fixtures: S42 2A carries PAPER VS CASH - EDGE TRANSFER (after the
      Runaway watch) and 2B LEADS - FULL LEDGER in the prompt and spec v3.4, and the scorer writes both parts; S43 the
      cash/paper pairing (a cash row's paper twin: same box, day, setup and side within TWIN_JOIN_S, never a walled
      PARK row or a row 300 s away; else the C5_STRICT v1.1 1 s model row; else NOT MEASURED), the slippage against the
      row's mark, a paper box never listed; S44 the empty week ("No cash trades this week.", a cash box with no trade
      named with its cumulative book); S45 every ledger row by status with its evidence, a malformed row skipped and
      named, a bad header or missing ledger NOT READ, never a crash; S46 every forward scorer's Status line and whole
      cumulative block, dated, the daily log and *_TEST* dry runs never shown as the record; S47 the minimum-edge
      baseline is one named constant (0, a TODO: the operator's call), never a config or env knob; S48 a cash trade
      with no twin and no precomputed row is priced by RUNAWAY_LIVEFILL_CHECK's own model (read only, hash-checked, a
      child interpreter, cached quotes), a data failure stays NOT MEASURED and says which. S36's spec anchor
      accepts v3.3 or later (v2.6's exact v3.3 anchor is red on spec v3.4). BORN RED on 8ce8189 at S42-S48.
v2.6  2026-11-24  dtp r583 (CASHBOOK.3). NEW S41: 1C shows C5 beside C1-C4 (prompt): the same scorer, C5 frozen in
      ~/reviews/cash_candidate_c5_20261124/PREREG.md, its own "C5 forward" table from 2026-11-24 apart from C1-C4's
      forward window, the ranking tag, and C5's in-sample and combined figures never evidence (only its forward figures
      count). Prompt only; spec v3.3 unchanged. BORN RED on 926bf64.
v2.5  2026-11-23  dtp r579 (TRIM.2). S32: LiquidityHunt and OGAP are retired (OTV5 r153; strategy_registry v1.13
      HISTORICAL), so the fixture's history line holds five rows (GEXPinButterfly 1, LiquidityHunt 2, OGAP 2), not one,
      and weekly_facts.md names no LiquidityHunt either. Expectation only; weekly_facts unchanged.
v2.4  2026-11-22  dtp r575 (HALF.2, RWATCH.1). S36's header anchor is spec v3.3. NEW S39: 2A carries the Runaway
      equity watch (prompt and spec): the one scorer tools/runaway_watch.py run for the Friday, WATCH.md frozen, the bar
      (8 forward trades from 2026-11-23, net EV a trade below zero after fees), the statuses, the DIRECTION arrow with
      n, quoted never re-derived, a RECOMMEND CUT for the operator's yes, report only. NEW S40: a 13:00 half day is a
      non-trading day: weekly_facts, DRIVEN for the week of 2026-11-23, counts three sessions (11-27 out, named), keeps
      a trade dated 11-27 in the totals and names it on a DEFECT line; the prompt's rules and the spec's rule 15 say so.
v2.3  2026-11-22  dtp r572 / PREREG amendment 1. NEW S38: the C1-C4 block in 1C (prompt and spec) shows gross without
      the two largest winners only beside gross without the two largest losers, as concentration context, never a
      qualifier, and never "dependent on its best trades" without the worst-trades figure; the one-sided wording is gone.
v2.2  2026-11-22  dtp r572 (SD.3, CASHBOOK.1). NEW S36: 2B collects the WHOLE WEEK's study runs: the prompt reads every
      <WORK>/study_dispatch_nightly_<date> folder with `study_dispatch.py status --out` beside Friday's and counts the
      week's verdicts over all of them, the spec v3.2 says the same, and the wrapper names the folders (NIGHTLY) before
      the session. NEW S37: 1C carries the cash candidate books C1-C4: the prompt runs tools/cash_books.py with the
      week and the Friday, inside 1C (before 2A), quotes it, and carries the report-only rules (never in the window EV
      or the theories, the choice is the operator's, never "paper size"); the spec's 1C names PREREG and the scorer.
v2.1  2026-11-21  dtp r571 (the 11-21 brief's R4 and R6). S29's 2B placement no longer wants the R6 no-progress lead;
      NEW S34: the lead is RETIRED (Breakout, its population, dormant since OTV5 r110): no part of the prompt or the
      spec names noprog_lead.py or the lead, and the retirement table and the v3.1 entry say so. NEW S35: the Friday
      timer reads INSTALLED in both (no "until then the brief's fallback runs the queue"), GIVE.2 and DAY.1 are not
      standing studies (closed OTV5 r81), and 4.2 sizes OGAP with Hunt, Runaway and PARK while the ramp max binds
      Breakout's rows only. S22c re-anchored to the four-setup budget line; S22/S22b read 3200/3800 characters of 4.2 (was 2500/3000:
      the OGAP row and the Breakout-only line lengthen it). Spec v3.1.
v2.0  2026-11-21  dtp r570 (SAT.10). THE OPERATOR'S NEW LAYOUT: FOUR SECTIONS, TEN PARTS. The operator, 2026-11-21: "1)
      Trading- A. ... B. ... C. ... 2) Our edge- A) ... B) ... 3) Bot performance- A) ... B) ... C) ... 4)
      Recommendations", and "the things I forgot to mention should be worked into whichever section they best fit
      into". S10/S10b RESTATED: the prompt and spec v3.0 carry 1. TRADING (1A 1B 1C), 2. OUR EDGE (2A 2B), 3. BOT
      PERFORMANCE (3A 3B 3C) and 4. RECOMMENDATIONS in order, and no old v2.x header. S11 adds the retired setups the
      fleet traded in the epoch (the spec's search block). S22 (cash table), S25 (the mark), S26 (OGAP, OGAP VS PARK)
      and S28 are re-anchored to their new parts (4.2, the prompt's head, 2A); S27/S27b (the O08 would-be) are
      REPLACED by S27: it is retired, named in no part of the prompt or spec (S27c, the nightly review, stays).
      NEW: S29/S29b each agreed placement sits inside its part in the prompt and the spec (1A risk, ladder fill,
      QQQ-only, exclusions; 1B never right, missed moves, history; 1C the epoch, intervals, tape, the window through
      11-28; 2A decisions in progress through 12-04 with the Hunt line; 2B the coming queue and PASS/FAIL/VOID; 3A
      fleet health beside the logs; 3B live evidence; 3C backlog with doc and hygiene items; 4 the cash table, the
      readiness checklist, the calendar, and the Sunday work list LAST). S30: the v3.0 changelog maps every old item
      (1.1-1.11, 2-7) to a new home or RETIRED. S31-S33 DRIVE tools/weekly_facts.py on a fixture: net = gross − fees
      and EV is gross (fees never inside), a setup that no longer trades is never named, the OTV4TEST rows are
      dropped and counted, its interval is review_kit.boot's own, and the prompt runs it before section 1 (the tape: TastyTrade's
      daily candles, raw/candles_full/interval=1d).
v1.15 2026-11-19  dtp r566 (MARK.1). THE MARK IS THE ONLY BASIS. The operator, 2026-11-19: "I don't give a rat shit what
      the bid-ask is. Mark is the worst buy or sell we accept." S25 RESTATED (it pinned r557's executable lead): the
      prompt's section 1 leads at the mark, sorts the theories by the mark EV, names the basis "the ladder's fill (mark
      or better)", forbids a spread-cost line and exec figures in prose (trailing data column only), and carries none of
      r557's lead text; spec v2.16 says the same. S28: OGAP, OGAP VS PARK and the O08 would-be are scored at the mark
      (pnl_usd) in the prompt and in spec 1.9-1.11, with no "ask in, bid out", no pnl_exec_usd and no UNPRICED rule.
      S27/S27b follow (pnl_usd, not pnl_exec_usd). Red on r565 at S25, S27, S27b and S28.
v1.14 2026-11-16  dtp r565 (O08). S27/S27b: section 1 reports the RUNAWAY O08 WOULD-BE (report only, never in the
      window EV or the theories): Runaway trades from 2026-11-16 re-scored on entry_bid/entry_ask (skip above 5% of
      mid), exec basis (pnl_exec_usd) all vs kept with a day-bootstrap interval, fees beside, skipped $200+ winners named
      as a cost, unscored rows named, OTV4TEST out, and the decision note fixed 2026-11-16 quoted verbatim in the prompt
      and the spec v2.15. The operator, 2026-11-16: "Include its 'would be' in the weekend briefs." Not the nightly review.
v1.13 2026-11-15  dtp r564 (OTV5 HYG.28). S26b accepts spec v2.13 OR LATER (S23b's pattern): spec v2.14 renames the ramp
      max's key in §1.8, and the pin on the exact version string made any later spec red. Same checks otherwise.
v1.12 2026-11-14  dtp (OGAP.1). S26/S26b: section 1 reports OGAP on its own line (never in the window EV or the
      theories) and OGAP VS PARK like for like (index rows, the exec basis, $500 of outlay a row, overlap days and the
      daily-P&L correlation), with the decision rule fixed 2026-11-14 quoted verbatim in the prompt and the spec v2.13,
      report only until its point. The operator, 2026-11-14: "let's design & paper trade the OGAP on QQQ", "compare them".
v1.11 2026-11-14  dtp r557 / AM.1. S25: §1 and spec v2.12 lead the EV benchmark with the executable basis.
v1.10 2026-11-14  dtp r555 / AM.9. S24: the prompt and spec v2.11 say the seal is the dispatcher's, control proves the
      order (FROZEN seen an earlier poll than RESULT), and the on-control fallback logs each sha in CONTROL_LOG.txt.
v1.9  2026-11-13  dtp r552 / SAT.9. S21 restated and S23/S23b/S23c added: the study queue runs Friday night. The
      prompt collects <WORK>/study_dispatch (started Fri 17:15 ET by dtp-study-dispatch, deadline Sat 02:30) before it
      would start anything, starts the dispatch itself only as FALLBACK 1 into <WORK>/study_dispatch_sat, does not
      CLOSE while a dispatch it started runs, and names the `- Depends:` second round; the spec v2.9 names the timer,
      the deadline, the fallback, the second round, the midnight hold and the power-audit acks; the wrapper passes
      STUDIES (the Friday folder and whether its state.json exists) before the session starts.
v1.8  2026-11-11  dtp r551 / CASH.1. S22c: the cash table's sizing rule matches OTV5 size_for. Breakout's risk count
      carries the at-least-1 floor and falls back to the geometry count without a usable stop premium; r550's text
      (no floor, NOT MEASURED without a stop premium) would have refused Breakout trades the bot takes. S22/S22b now
      read "never rounded up to 1" (a refused trade is one under 1 contract).
v1.7  2026-11-11  dtp r550 / CASH.1. S22/S22b: the QQQ cash size table runs every Saturday until 2026-12-07 and then
      skips itself. The prompt and the spec name both schemes ($250/$500 and $500/$750, cap = the ramp max), the
      refusal (never rounded to 1), fees beside EV, the date stop, and REPORT ONLY; the item stays out of the study queue.
v1.6  2026-11-11  dtp r549 / SAT.8. S21/S21b/S21c: the study queue runs on the boxes. The prompt starts
      tools/study_dispatch.py after the box reads, collects it with `wait`, runs `cleanup`, and does not CLOSE while
      it runs; the spec names the same; the wrapper exports STUDY_DISPATCH_DEADLINE_ET and runs the cleanup after
      the session. S20 still holds (the control fallback keeps the heavy lock).
v1.5  2026-11-11  dtp r548 / SAT.7. S20/S20b: the prompt and the spec name the study queue ~/reviews/WEEKEND_STUDIES.md and
      its rules (seal first, run once, the heavy lock, unfinished items to NOT MEASURED).
v1.4  2026-11-08  dtp r527 / SAT.6 (the 11-07 brief R9). S5 was RED in the 11-07 sweep, rc=0: the sweep ran while
      the real brief held the LIVE in-flight marker, the wrapper stood down on it, and the refusal was never
      reached. Worse, S7 touched that same live marker to "6 hours ago" and then left it — a sweep during a
      real brief backdated the running brief's guard. Every wrapper run here now uses a SCRATCH marker
      (_SCRATCH carries SATURDAY_BRIEF_MARKER); S5c DRIVES the 11-07 shape (a fresh marker AND no prompt must
      still REFUSE, and write one REFUSED ledger line); S18 the run parameters and --dry carry OTV5's and dtp's
      HEADs (fixture repos) and never otv4's; S19 the prior comes from the weekly folder only (an anchor with
      handoffs/saturday_*.md is ignored), and S19b/S19c a prior without a _work folder is passed as NONE while
      one with it is passed as the --prior path.
v1.3  2026-10-31  dtp r520 / SAT.4 — THE BRIEF IS THE OPERATOR'S SEVEN SECTIONS, FOR THE FLEET THAT EXISTS.
      The operator, 2026-10-31: "Re-do the entire brief" and "don't list the retired strategies either".
      S10/S10b the prompt and the tracked spec (docs/SATURDAY_BRIEF.md) name the same seven sections in order;
      S11/S11b no retired strategy or retired section is named in the prompt, or in the spec's report sections
      (the search list lives in the spec's RETIRED-SEARCH block, read from there); S12 the prompt follows the
      tracked spec, not handoffs/; S13 the brief is written outside handoffs/ (check_scratch_purge P12);
      S14 the standing rules are in the prompt; S15-S17 DRIVEN: a deadline is passed to timeout(1), and a real
      run holds its own in-flight marker while the session runs, hands it BRIEF/WORK/DEADLINE, and clears it.
      S7's abandoned marker is 6 h old (the expiry moved from 3 h to 5 h).
v1.2  2026-09-26  r432 — writes to ITS OWN log and ledger, never the operator's.
      The ledger exists to answer "is the brief still happening?" by `tail`.
      This file was filling it with deliberate failures, and on 2026-09-26
      that answer came back wrong on the morning of the first real Saturday.
v1.1  2026-09-20  dtp r396 / SAT.3 — S2b REPLACED. It asserted
      '"deploy.sh" not in TOOLS', i.e. that a string was absent from a list
      that DOES NOT SCOPE SHELL COMMANDS — a check providing no protection
      while reading as if it did. S2b/S2c/S2d/S2e now drive the real
      refusal: the wrapper exports the marker, deploy.sh AND land.sh both
      exit 9 on it, and an ATTENDED run is NOT refused so the guard cannot
      have simply disabled landing. Every wrapper invocation also writes to
      a TEMP out-path, because running against the live brief made three
      checks fail once a genuine brief existed — a red for the wrong reason.
v1.0  2026-09-20  dtp r394 / SAT.2 — THE UNATTENDED SESSION MUST NOT BE ABLE
      TO LAND, AND THE TIMER MUST NOT BE SILENTLY DEAD.

🔴 WHY EACH CHECK EXISTS, MEASURED RATHER THAN IMAGINED.
  · The first schedule used `CRON_TZ=America/New_York` and WOULD NEVER HAVE
    FIRED — cron 3.0pl1 does not support it; a live probe never fired and the
    string is absent from /usr/sbin/cron. Worse, the comment beside it claimed
    "VERIFIED by live probe" before anything had been verified. A timer that
    does not fire is INDISTINGUISHABLE FROM A QUIET WEEK, so S1 pins the
    schedule form itself.
  · The session runs unattended on a box holding a live funded broker token, a
    GitHub token with write on both repos and the Telegram token. S2/S3 pin
    that its tool grant cannot reach the lander or a fleet mutator — §38.9,
    and the operator's own standing rule that he approves every land.
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SH = os.path.join(ROOT, "tools", "saturday_brief.sh")
PROMPT = os.path.join(ROOT, "tools", "saturday_brief.prompt")

# ⚠️ EVERY WRAPPER INVOCATION BELOW WRITES TO A TEMP PATH. Running against the
# live brief path meant that once a real brief existed the wrapper stood down
# — correctly — and three checks failed for a reason unrelated to what they
# assert. A red for the wrong reason is worse than no red.
import tempfile
_TMPOUT = os.path.join(tempfile.gettempdir(), "check_saturday_brief_out.md")
_SCRATCH = {
    "SATURDAY_BRIEF_LOG": os.path.join(tempfile.gettempdir(),
                                       "check_saturday_brief.log"),
    "SATURDAY_BRIEF_LEDGER": os.path.join(tempfile.gettempdir(),
                                          "check_saturday_brief.ledger"),
    # v1.4: NEVER the live marker. A sweep running during the real brief made the wrapper stand down on
    # the brief's own marker (S5 red, rc=0), and S7 backdated that marker.
    "SATURDAY_BRIEF_MARKER": os.path.join(tempfile.gettempdir(),
                                          "check_saturday_brief.inflight"),
}
_MK = _SCRATCH["SATURDAY_BRIEF_MARKER"]
if os.path.exists(_MK):
    os.remove(_MK)


FAILS, RAN = [], []


def ck(n, ok, msg):
    RAN.append(n)
    print(f"  {n:<4} {'PASS' if ok else 'FAIL'}  {msg}")
    if not ok:
        FAILS.append(n)


src = open(SH).read() if os.path.exists(SH) else ""
ck("S0", src and os.path.exists(PROMPT),
   f"wrapper and prompt both present ({os.path.basename(SH)}, "
   f"{os.path.basename(PROMPT)})")

# ------------------------------------------------------------------------ S1
# ⚠️ THE SCHEDULE IS CHECKED WHERE IT LIVES — in the installed crontab, not in
# a comment. §21: source text proves nothing about runtime.
cr = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
lines = [l for l in cr.stdout.splitlines()
         if l.strip() and not l.lstrip().startswith("#")]
# ⚠️ UPDATED WITH THE RULING, NOT LOOSENED TO STAY GREEN (§36). S1 asserted
# "exactly one entry" and went red the moment the watchdog and canary were
# added — which was the arrangement getting MORE robust, not less. The
# property that actually matters is that exactly one entry can PRODUCE a
# brief; the flagged ones cannot double-write.
sat = [l for l in lines if "saturday_brief.sh" in l]
bare = [l for l in sat if "--" not in l.split("saturday_brief.sh", 1)[1]]
ck("S1", len(bare) == 1,
   f"exactly ONE un-flagged entry can produce a brief ({len(bare)} of "
   f"{len(sat)} total) — the flagged layers cannot double-write")

if sat:
    ck("S1b", not any(l.startswith("CRON_TZ") for l in lines),
       "no CRON_TZ line — unsupported by cron 3.0pl1, and an entry written "
       "that way is SILENTLY DEAD")
    fields = sat[0].split()[:5]
    ck("S1c", fields[4] == "6",
       f"day-of-week is Saturday: {' '.join(fields)}")
    hh = int(fields[1])
    # 07:17 UTC = 03:17 EDT / 02:17 EST — both early Saturday ET, both clear
    # of the 08:00 read, so it is right on BOTH sides of the DST boundary.
    ck("S1d", 5 <= hh <= 9,
       f"UTC hour {hh:02d} lands before 08:00 ET in BOTH DST states "
       f"(EDT {hh-4:02d}:xx, EST {hh-5:02d}:xx)")

# ------------------------------------------------------------------------ S2
m = re.search(r'^TOOLS="([^"]*)"', src, re.M)
tools = (m.group(1) if m else "")
ck("S2", m is not None and tools,
   f"the wrapper declares an explicit tool grant: {tools or '(none)'}")

# 🔴 S2b REPLACED — THE OLD CHECK PROVIDED NO PROTECTION AND READ AS IF IT
# DID. It asserted `"deploy.sh" not in TOOLS`, i.e. that a string was absent
# from a list that DOES NOT SCOPE SHELL COMMANDS. Measured 2026-09-20: a
# session granted only `Bash` was asked to touch a file and the file
# appeared. Omitting the lander from --allowedTools never made it
# unreachable, because it is reached THROUGH Bash.
# ✅ The real enforcement is a refusal inside the thing being protected.
ck("S2b", "VERTIGO_UNATTENDED=1" in src and "export VERTIGO_UNATTENDED" in src,
   "the wrapper EXPORTS VERTIGO_UNATTENDED for every path through it")

_lander = os.path.join(ROOT, "tools", "deploy.sh")
r = subprocess.run(["bash", _lander, "--dry"], capture_output=True, text=True,
                   timeout=120, env=dict(os.environ, VERTIGO_UNATTENDED="1"))
ck("S2c", r.returncode == 9 and "REFUSED" in r.stdout,
   f"deploy.sh REFUSES an unattended caller (rc={r.returncode}, expect 9)")

r = subprocess.run(["bash", os.path.join(ROOT, "tools", "land.sh"), "otv4"],
                   capture_output=True, text=True, timeout=120,
                   env=dict(os.environ, VERTIGO_UNATTENDED="1"))
ck("S2d", r.returncode == 9 and "REFUSED" in r.stdout,
   f"land.sh REFUSES it too — guarding only the wrapper would leave the "
   f"lander reachable directly (rc={r.returncode})")

r = subprocess.run(["bash", _lander, "--dry"], capture_output=True, text=True,
                   timeout=120, env={k: v for k, v in os.environ.items()
                                     if k != "VERTIGO_UNATTENDED"})
ck("S2e", r.returncode != 9,
   f"an ATTENDED run is NOT refused — the guard did not simply disable the "
   f"lander (rc={r.returncode})")

# ------------------------------------------------------------------------ S3
# 🔑 THE PROMPT MUST SAY IT TOO. The tool list is the enforcement; the prompt
# is what stops a session deciding to be helpful. Belt and braces, because the
# operator is asleep.
p = open(PROMPT).read() if os.path.exists(PROMPT) else ""
ck("S3", "LAND NOTHING" in p.upper() and "deploy.sh" in p,
   "the prompt tells the session it lands nothing and names the path it must "
   "not use")
ck("S3b", "Telegram" in p or "§17" in p,
   "the prompt forbids paging the operator — §17, the alert path is for "
   "emergencies and a weekly report is not one")

# ------------------------------------------------------------------------ S4
# ⚠️ BEHAVIOUR, NOT SOURCE TEXT (§21). The first cut of S4 and S5 grepped the
# wrapper for "--smoke" and "REFUSED", and BOTH MUTATIONS SURVIVED: commenting
# the branch out left the strings sitting in the file. A check a comment can
# satisfy is asserting about the comment. Seventh instance of this shape
# today; it is caught here only because the mutation was run.
# `claude` is removed from PATH so --smoke fails FAST instead of buying a run;
# reaching the smoke banner proves the branch is live.
env = dict(os.environ, **_SCRATCH, SATURDAY_BRIEF_CLAUDE="/bin/false")
r = subprocess.run(["bash", SH, "--smoke"], capture_output=True, text=True,
                   timeout=120, env=env)
ck("S4", "smoke:" in r.stdout and r.returncode != 0,
   f"--smoke ENTERS its own branch and REPORTS FAILURE when the binary is "
   f"unusable (rc={r.returncode}) — no live API call is bought by this gate")

r = subprocess.run(["bash", SH, "--dry"], env=dict(os.environ, **_SCRATCH), capture_output=True, text=True,
                   timeout=60)
ck("S4b", r.returncode == 0 and "prompt file present" in r.stdout,
   f"--dry runs, touches nothing, and confirms the prompt is there "
   f"(rc={r.returncode})")

# ------------------------------------------------------------------------ S5
# S5 — DRIVEN, by hiding the prompt file and watching the wrapper refuse.
_bak = PROMPT + ".s5bak"
os.rename(PROMPT, _bak)
try:
    # ⚠️ THE BINARY IS NEUTERED HERE ON PURPOSE. Without it, a mutation that
    # removes the refusal lets the wrapper invoke the REAL claude with an
    # empty prompt — which CRASHED this checker instead of failing it, and a
    # gate that dies tells the reader less than one that fails.
    r = subprocess.run(["bash", SH], capture_output=True, text=True,
                       timeout=120,
                       env=dict(os.environ, **_SCRATCH, SATURDAY_BRIEF_CLAUDE="/bin/false",
                                SATURDAY_BRIEF_OUT=_TMPOUT))
    ck("S5", r.returncode != 0 and "REFUSED" in (r.stdout + r.stderr),
       f"a MISSING prompt REFUSES (rc={r.returncode}) rather than invoking "
       f"claude with an empty brief")
    # S5c — THE 11-07 SHAPE: a FRESH in-flight marker AND no prompt. The refusal must come first.
    open(_MK, "w").close()
    _led = _SCRATCH["SATURDAY_BRIEF_LEDGER"]
    _n0 = sum(1 for _ in open(_led)) if os.path.exists(_led) else 0
    r = subprocess.run(["bash", SH], capture_output=True, text=True, timeout=120,
                       env=dict(os.environ, **_SCRATCH, SATURDAY_BRIEF_CLAUDE="/bin/false",
                                SATURDAY_BRIEF_OUT=_TMPOUT))
    _new = open(_led).read().splitlines()[_n0:] if os.path.exists(_led) else []
    ck("S5c", r.returncode != 0 and "REFUSED" in (r.stdout + r.stderr)
       and any("REFUSED no_prompt" in l for l in _new),
       f"a missing prompt REFUSES even while a fresh in-flight marker stands (rc={r.returncode}), "
       f"and writes one REFUSED ledger line ({len(_new)} new)")
finally:
    os.rename(_bak, PROMPT)
    if os.path.exists(_MK):
        os.remove(_MK)

ck("S5b", os.path.exists(PROMPT), "the prompt file was restored by this check")

# ------------------------------------------------------------------------ S9
# 🔴 THE TRANSCRIPT HAZARD, PINNED ON BEHAVIOUR. `claude -p --continue` does
# not fork — it APPENDS TO THE LIVE SESSION'S TRANSCRIPT (measured: 5137->5161
# lines, zero new session files, entries under the attached session's own id).
# The operator reattaches to a long-lived agent, so a timer using --continue
# would be cron writing into an agent he is attached to. The wrapper prints
# the flags it will actually pass; a source grep would be satisfied by a
# comment (§21), and a neutered binary hides the difference entirely.
cmd = subprocess.run(["bash", SH, "--print-cmd"], env=dict(os.environ, **_SCRATCH), capture_output=True,
                     text=True, timeout=60).stdout.strip()
ck("S9", "--session-id" in cmd,
   f"the invocation forces an ISOLATED session id: {cmd[:60]}")
ck("S9b", " -c" not in f" {cmd}" and "--continue" not in cmd,
   f"the invocation carries NO --continue / -c — it can never write into the "
   f"attached session's transcript: {cmd[:60]}")

# ------------------------------------------------------------------------ S6
# 🔑 THE ARRANGEMENT IS FOUR LAYERS BECAUSE THE FAILURE IT MUST SURVIVE IS
# SILENCE. These pin that the layers exist and are ordered so they cannot
# collide: preferred (in-session) → fallback → watchdog, each after the last.
lines_ = [l for l in subprocess.run(["crontab", "-l"], capture_output=True,
                                    text=True).stdout.splitlines()
          if l.strip() and not l.lstrip().startswith("#")]
def _hhmm(pred):
    for l in lines_:
        if pred(l):
            f = l.split()
            return int(f[1]) * 60 + int(f[0]), f[4]
    return None, None
fb, fbd = _hhmm(lambda l: "saturday_brief.sh" in l and "--" not in l)
wd, wdd = _hhmm(lambda l: "--watchdog" in l)
cn, cnd = _hhmm(lambda l: "--canary" in l)

ck("S6", fb is not None and wd is not None,
   f"fallback and watchdog are both installed (fallback {fb}, watchdog {wd})")
ck("S6b", fb is not None and wd is not None and wd > fb,
   f"the watchdog runs AFTER the fallback ({wd} > {fb}) — a watchdog that "
   f"ran first would report a failure the fallback was about to fix")
ck("S6c", fbd == "6" and wdd == "6",
   f"both are Saturday jobs (dow {fbd}/{wdd})")
ck("S6d", cn is not None and cnd not in (None, "6"),
   f"the canary runs on a NON-Saturday (dow {cnd}) — proving the chain works "
   f"midweek is the point; on Saturday it would be too late")

# ------------------------------------------------------------------------ S7
# 🔴 A STALE IN-FLIGHT MARKER MUST NOT SILENCE THE FALLBACK FOREVER. A session
# that crashes mid-brief leaves one behind; without expiry the fallback would
# stand down every week while nothing was produced — precisely the silent
# failure the layers exist to prevent.
# 🔴 THE GATE WRITES TO ITS OWN LOG AND LEDGER, NEVER THE OPERATOR'S.
# This file runs the real script with /bin/false standing in for claude — a
# correct test of the failure path — and every one of those runs used to
# append `FAILED fallback rc=1` to the ledger the operator tails to ask "is
# the brief still happening?". 97 such lines accumulated and on 2026-09-26
# they were read as a broken timer, on the morning of its FIRST Saturday.

MARK = _MK  # v1.4: the scratch marker, never the live one
_pre = os.path.exists(MARK)
try:
    subprocess.run(["touch", "-d", "6 hours ago", MARK], check=True)
    r = subprocess.run(["bash", SH], capture_output=True, text=True, timeout=120,
                       env=dict(os.environ, **_SCRATCH, SATURDAY_BRIEF_CLAUDE="/bin/false",
                                SATURDAY_BRIEF_OUT=_TMPOUT))
    ck("S7", "ABANDONED" in r.stdout,
       "a 6-hour-old in-flight marker is treated as ABANDONED, not obeyed")
    subprocess.run(["touch", MARK], check=True)
    r = subprocess.run(["bash", SH], capture_output=True, text=True, timeout=120,
                       env=dict(os.environ, **_SCRATCH, SATURDAY_BRIEF_CLAUDE="/bin/false",
                                SATURDAY_BRIEF_OUT=_TMPOUT))
    ck("S7b", "IN FLIGHT" in r.stdout,
       "a FRESH marker IS obeyed — the expiry did not simply disable the guard")
finally:
    if not _pre:
        subprocess.run(["rm", "-f", MARK])

# ------------------------------------------------------------------------ S8
ck("S8", "LEDGER" in src and "one line per run" in src.lower()
   or "ledger" in src.lower(),
   "every run appends to a ledger — 'is the brief still happening?' must be "
   "answerable without reading a megabyte of session output")

# ------------------------------------------------------------------------ S10
# 🔑 v1.3 — THE OPERATOR'S SEVEN SECTIONS (2026-10-31), IN THE PROMPT AND IN THE TRACKED SPEC, IN ORDER.
SPEC = os.path.join(ROOT, "docs", "SATURDAY_BRIEF.md")
spec = open(SPEC).read() if os.path.exists(SPEC) else ""
# v2.0 (SAT.10): the operator's 2026-11-21 layout, four sections and ten parts. The old seven are gone.
SECTIONS = ["## 1. TRADING\n", "### 1A. THE WEEK'S TRADES",
            "### 1B. GIVEBACK ON EXITS, NEVER RIGHT ON ENTRIES, AND EACH SETUP AGAINST ITS HISTORY",
            "### 1C. THE EPOCH (OTV5)", "## 2. OUR EDGE\n",
            "### 2A. TOP EARNING SETUP CONDITIONS, AND WHERE TO LOOK FOR EDGE", "### 2B. THE WEEK'S STUDIES",
            "## 3. BOT PERFORMANCE\n", "### 3A. ERRORS AND ISSUES THIS WEEK", "### 3B. HOW LAST WEEK'S FIXES DID",
            "### 3C. THE BACKLOG", "## 4. RECOMMENDATIONS\n"]
OLD_SECTIONS = ["## 1. TRADING SUMMARY", "## 2. ISSUES FROM THE BOT LOGS", "## 3. FLEET HEALTH",
                "## 4. DOCUMENTATION CORRECTIONS", "## 5. CODE HYGIENE", "## 6. PROPOSED STUDIES TO INCREASE P&L",
                "## 7. RECOMMENDATIONS"]


def _in_order(text, heads, start=0):
    pos = [text.find(h, start) for h in heads]
    return all(x >= 0 for x in pos) and pos == sorted(pos)


def _body(text):
    """The report itself: from the first real '## 1. TRADING' line (the spec's shape block is indented)."""
    i = text.find("\n## 1. TRADING\n")
    i = i if i >= 0 else text.find("\n  ## 1. TRADING\n")
    return text[i:] if i >= 0 else ""


_P_HEADS = [h.replace("## ", "  ## ", 1) if h.startswith("## ") else h.replace("### ", "  ### ", 1) for h in SECTIONS]
ck("S10", _in_order(p, _P_HEADS) and not [h for h in OLD_SECTIONS if h in p],
   "the prompt names the four sections and ten parts in the operator's order, and no old v2.x header")
_m10 = re.search(r"# THE SATURDAY BRIEF — spec v(\d+)\.(\d+)", spec)
ck("S10b", _in_order(spec, ["\n" + h for h in SECTIONS]) and not [h for h in OLD_SECTIONS if h in spec]
   and _m10 is not None and int(_m10.group(1)) >= 3,
   "the tracked spec v3.0 has the same four sections and ten parts, in the same order, and no old header")

# ------------------------------------------------------------------------ S11
# 🔴 "don't list the retired strategies either." The search list is the spec's own RETIRED-SEARCH block, so the
# list exists once; the prompt may name none of it, and neither may the spec outside that block and its
# retirement table.
_blk = re.search(r"<!-- RETIRED-SEARCH.*?-->(.*?)<!-- /RETIRED-SEARCH -->", spec, re.S)
RETIRED = [t for t in re.split(r"\s{2,}|\n", _blk.group(1)) if t.strip()] if _blk else []
RETIRED = [t.strip() for t in RETIRED] + ["ORB", "AAL", "SEVENTEEN", "veto"]


def _named(text):
    hits = []
    for t in RETIRED:
        rx = r"(?<![\w-])" + re.escape(t) + r"(?![\w])"
        if re.search(rx, text, 0 if any(c.isupper() for c in t) else re.I):
            hits.append(t)
    return hits


ck("S11", len(RETIRED) >= 12 and not _named(p),
   f"the prompt names no retired strategy or section ({len(RETIRED)} terms searched; named: {_named(p) or 'none'})")
_report = spec
if _blk:
    _report = _report.replace(_blk.group(0), "")
_report = _report.split("## WHAT THIS SPEC RETIRED")[0]
_report = _body(_report)
_named_spec = [t for t in _named(_report) if t not in ("ORB",)]   # 3C says the ORB *engine* stays
ck("S11b", bool(_report) and not _named_spec,
   f"the spec's four sections name no retired strategy outside the search block (named: {_named_spec or 'none'})")

# ------------------------------------------------------------------------ S12
ck("S12", "/home/ubuntu/day_trader_pro/docs/SATURDAY_BRIEF.md" in p and "handoffs/SATURDAY" not in p,
   "the prompt follows the tracked spec in dtp docs/, not the gitignored handoffs/ copy")
_ign = subprocess.run(["git", "-C", ROOT, "check-ignore", "-q", "docs/SATURDAY_BRIEF.md"]).returncode
ck("S12b", bool(spec) and _ign == 1, f"docs/SATURDAY_BRIEF.md exists and is not gitignored (check-ignore rc={_ign})")

# ------------------------------------------------------------------------ S13
_env13 = {k: v for k, v in os.environ.items() if k not in ("SATURDAY_BRIEF_OUT", "SATURDAY_BRIEF_WEEKLY")}
_env13.update(_SCRATCH)
r = subprocess.run(["bash", SH, "--dry"], env=_env13, capture_output=True, text=True, timeout=60)
_out = re.search(r"output: (\S+)", r.stdout)
_out = _out.group(1) if _out else ""
ck("S13", _out.startswith("/home/ubuntu/reviews/weekly/saturday_") and "handoffs" not in _out
   and "/options-trader-v4/" not in _out,
   f"the default brief path is outside handoffs/ and outside every repo: {_out or '(none)'}")

# ------------------------------------------------------------------------ S14
_rules = {"wake": "--wake-only" in p and "--shutdown-only" in p and "wake_and_bake" in p,
          "they/them": "they/them" in p,
          "no env": "Never print an environment" in p and "is-active" in p,
          "read-only": "mode=ro" in p and "Reads only" in p,
          "fees": "never inside EV" in p,
          "filter": "mainline()" in p,
          "not measured": "NOT MEASURED" in p,
          "otv5 r suite": "/home/ubuntu/OTV5/tests/" in p and "r_ledger" in p,
          "non-events": "No non-events" in p and "Checked, nothing to report" in p,
          "venv": "/home/ubuntu/day_trader_pro/venv/bin/python" in p}
ck("S14", all(_rules.values()), f"the standing rules are in the prompt (missing: "
   f"{[k for k, v in _rules.items() if not v] or 'none'})")

# ------------------------------------------------------------------------ S15
_pc = subprocess.run(["bash", SH, "--print-cmd"], env=dict(os.environ, **_SCRATCH), capture_output=True,
                     text=True, timeout=60).stdout
_t = re.search(r"timeout=(\d+)", _pc)
ck("S15", bool(_t) and 0 < int(_t.group(1)) <= 18000,
   f"the session is given a deadline: {(_t.group(0) if _t else 'none')} (≤ 5 h, ends by 07:30 ET on a timer run)")

# ------------------------------------------------------------------------ S16
# DRIVEN: a stub stands in for claude, records whether the in-flight marker exists while it runs, and keeps the
# prompt it was handed. The wrapper used to write no marker of its own, so the watchdog's retry could start a
# second brief beside a long-running first one.
_d = tempfile.mkdtemp(prefix="chk_satbrief_")
_stub = os.path.join(_d, "claude_stub.sh")
_mk = os.path.join(_d, "inflight")
open(_stub, "w").write(f'#!/bin/bash\n[ -f "{_mk}" ] && echo yes > "{_d}/seen"\nprintf "%s\\n" "$@" > "{_d}/prompt"\nexit 0\n')
os.chmod(_stub, 0o755)
_o16 = os.path.join(_d, "weekly", "saturday_TEST.md")
r = subprocess.run(["bash", SH], capture_output=True, text=True, timeout=120,
                   env=dict(os.environ, **dict(_SCRATCH, SATURDAY_BRIEF_MARKER=_mk), SATURDAY_BRIEF_CLAUDE=_stub,
                            SATURDAY_BRIEF_WEEKLY=os.path.join(_d, "weekly"), SATURDAY_BRIEF_OUT=_o16))
ck("S16", os.path.exists(os.path.join(_d, "seen")) and not os.path.exists(_mk),
   "a real run holds its own in-flight marker while the session runs, and clears it after")
_hp = open(os.path.join(_d, "prompt")).read() if os.path.exists(os.path.join(_d, "prompt")) else ""
ck("S17", f"exactly this path: {_o16}" in _hp and "WORK" in _hp and "DEADLINE" in _hp
   and os.path.isdir(_o16[:-3] + "_work") and "## 1. TRADING\n" in _hp,
   "the session is handed the prompt, its BRIEF path, its WORK folder (created) and its DEADLINE")

# ------------------------------------------------------------------------ S18 / S19
# v1.4 — DRIVEN on fixtures. Two throwaway git repos stand in for OTV5 and dtp, an anchor with a
# handoffs/ brief stands in for the frozen otv4, and a weekly folder holds the priors.
import shutil
_f = tempfile.mkdtemp(prefix="chk_satbrief_trees_")
def _repo(name):
    d = os.path.join(_f, name); os.makedirs(d)
    g = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
             GIT_COMMITTER_EMAIL="t@t")
    subprocess.run(["git", "init", "-q", d], check=True, env=g)
    open(os.path.join(d, "f"), "w").write(name)
    subprocess.run(["git", "-C", d, "add", "f"], check=True, env=g)
    subprocess.run(["git", "-C", d, "commit", "-qm", name], check=True, env=g)
    return d, subprocess.run(["git", "-C", d, "rev-parse", "--short", "HEAD"], capture_output=True,
                             text=True).stdout.strip()
_o5, _h5 = _repo("otv5fx")
_dt, _hd = _repo("dtpfx")
_an, _ha = _repo("anchorfx")
os.makedirs(os.path.join(_an, "handoffs"))
open(os.path.join(_an, "handoffs", "saturday_2026-09-01.md"), "w").write("old")
_wk = os.path.join(_f, "weekly"); os.makedirs(_wk)
_fx = dict(os.environ, **_SCRATCH, SATURDAY_BRIEF_OTV5=_o5, SATURDAY_BRIEF_DTP=_dt,
           SATURDAY_BRIEF_ANCHOR=_an, SATURDAY_BRIEF_WEEKLY=_wk,
           SATURDAY_BRIEF_OUT=os.path.join(_wk, "saturday_TEST.md"))
def _dry():
    return subprocess.run(["bash", SH, "--dry"], env=_fx, capture_output=True, text=True, timeout=60).stdout
_d0 = _dry()
_tl = next((l for l in _d0.splitlines() if l.strip().startswith("trees:")), "")
ck("S18", f"OTV5 {_h5}" in _tl and f"dtp {_hd}" in _tl and _ha not in _tl,
   f"the brief's trees are OTV5 and dtp, never the anchor (otv4): {_tl.strip()[:90]}")
_pl = next((l for l in _d0.splitlines() if l.strip().startswith("prior:")), "")
_pw = next((l for l in _d0.splitlines() if l.strip().startswith("prior_work:")), "")
ck("S19", "(none)" in _pl and "handoffs" not in _d0 and "NONE" in _pw,
   f"with an empty weekly folder there is NO prior, even though the anchor holds handoffs/saturday_*.md: "
   f"{_pl.strip()} | {_pw.strip()[:40]}")
open(os.path.join(_wk, "saturday_2026-10-31.md"), "w").write("p1")
_d1 = _dry()
_pw1 = next((l for l in _d1.splitlines() if l.strip().startswith("prior_work:")), "")
ck("S19b", "saturday_2026-10-31.md" in _d1 and "NONE" in _pw1 and "does not exist" in _pw1,
   f"a prior whose _work folder is missing is passed as NONE with the reason: {_pw1.strip()[:70]}")
os.makedirs(os.path.join(_wk, "saturday_2026-11-07_work"))
open(os.path.join(_wk, "saturday_2026-11-07.md"), "w").write("p2")
_d2 = _dry()
_pw2 = next((l for l in _d2.splitlines() if l.strip().startswith("prior_work:")), "")
ck("S19c", _pw2.strip() == f"prior_work: {os.path.join(_wk, 'saturday_2026-11-07_work')}",
   f"the newest prior with a _work folder is the --prior path: {_pw2.strip()[:80]}")
# and the real run hands the session the same TREES line (stub claude, scratch marker)
_st = os.path.join(_f, "stub.sh")
open(_st, "w").write(f'#!/bin/bash\nprintf "%s\\n" "$@" > "{_f}/prompt"\nexit 0\n')
os.chmod(_st, 0o755)
subprocess.run(["bash", SH], env=dict(_fx, SATURDAY_BRIEF_CLAUDE=_st), capture_output=True, text=True,
               timeout=120)
_hp2 = open(os.path.join(_f, "prompt")).read() if os.path.exists(os.path.join(_f, "prompt")) else ""
ck("S18b", f"TREES   the trees this brief reports on" in _hp2 and f"OTV5 {_h5}" in _hp2
   and f"dtp {_hd}" in _hp2 and f"PRIOR_WORK" in _hp2
   and os.path.join(_wk, "saturday_2026-11-07_work") in _hp2,
   "the real run's parameters carry the OTV5 and dtp HEADs and the prior _work path")
shutil.rmtree(_f, ignore_errors=True)

# S20 (v1.5, dtp r548 / SAT.7): THE STUDY QUEUE. The operator, 2026-11-10: "Make sure you add whatever we want
# to study to the 0300 weekend activity." The prompt and the spec both name ~/reviews/WEEKEND_STUDIES.md, tell the
# session to seal before testing and run once, run the queue through the heavy lock, and send unfinished items to
# NOT MEASURED.
_q = "/home/ubuntu/reviews/WEEKEND_STUDIES.md"
ck("S20", _q in p and "SEAL.txt" in p and "ONCE" in p and "claude-heavy.lock" in p
   and "NOT MEASURED" in p.split("THE STUDY QUEUE", 1)[-1][:2000],
   "the prompt runs the study queue blind (seal, run once), through the heavy lock, unfinished to NOT MEASURED")
ck("S20b", "WEEKEND_STUDIES.md" in spec and "SEAL.txt" in spec and "claude-heavy.lock" in spec,
   "the spec names the same study queue and its rules")

# S21 (v1.6, dtp r549 / SAT.8): THE STUDY QUEUE RUNS ON THE BOXES. The operator, 2026-11-11: "What about just
# waking more boxes at the 0300 to run these studies in parallel?"
_q6 = p.split("THE STUDY QUEUE", 1)[-1][:4000]
ck("S21", "tools/study_dispatch.py run" in _q6 and "study_dispatch.py wait" in _q6 and "FALLBACK 1" in _q6
   and "do NOT CLOSE while it runs" in p and "study_dispatch.py cleanup" in p,
   "the prompt collects the box dispatch, starts it only as a fallback, cleans up, and does not CLOSE while one it "
   "started runs")
ck("S21b", "study_dispatch.py" in spec and "CLOSED only after" in spec and "box_claims" in spec,
   "the spec names the box dispatch, its claims, and the late CLOSE")
_shs = open(SH).read()
ck("S21c", 'export STUDY_DISPATCH_DEADLINE_ET="$_deadline_hm"' in _shs and '"$_SD" cleanup' in _shs
   and _shs.index("export STUDY_DISPATCH_DEADLINE_ET") < _shs.index('timeout "$BUDGET_S"'),
   "the wrapper hands the deadline to the dispatcher before the session and runs its cleanup after")

# S23 (v1.9, dtp r552 / SAT.9): THE QUEUE RUNS FRIDAY NIGHT. The operator, 2026-11-13: "Yes, don't wait until Sunday to
# do that study. Add it to the rest".
_qf = re.sub(r"\s+", " ", _q6)
ck("S23", "dtp-study-dispatch" in _qf and "friday_studies.sh" in _qf and "Friday 17:15 ET" in _qf
   and "Saturday 02:30 ET" in _qf and "wait --out <WORK>/study_dispatch " in _qf
   and "--out <WORK>/study_dispatch_sat > <WORK>/study_dispatch_sat.log" in _qf and "- Depends:" in _qf and "nothing passed, not run" in _qf
   and _qf.find("COLLECT IT") < _qf.find("FALLBACK 1") < _qf.find("tools/study_dispatch.py run") < _qf.find("FALLBACK 2"),
   "the prompt collects Friday's run first, starts its own only as FALLBACK 1 into its own folder, and names the second round")
_sf = re.sub(r"\s+", " ", spec)
ck("S23b", ("spec v2.9" in spec or re.search(r"spec v[3-9]\.\d+", spec) is not None) and "dtp-study-dispatch" in _sf and "--deadline 02:30" in _sf and "not Persistent" in _sf
   and "NO_MIDNIGHT_HALT" in _sf and "power_ack.txt" in _sf and "- Depends: WS.a, WS.b" in _sf
   and "study_dispatch_sat" in _sf,
   "the spec v2.9 names the Friday timer, the deadline, the fallback folder, the second round, the hold flag and the acks")
# S24 (v1.10, dtp r555 / AM.9): THE SEAL IS THE DISPATCHER'S, AND THE ON-CONTROL FALLBACK LOGS ITS ORDER.
ck("S24", "the SEAL is the dispatcher's" in _qf and "earlier poll than RESULT.json" in _qf
   and "CONTROL_LOG.txt" in _qf and "AMENDMENTS.txt" in _qf
   and "**v2.11 ·" in spec and "never self-attested" in _sf and "FROZEN.ack" in _sf and "CONTROL_LOG.txt" in _sf,
   "the prompt and spec v2.11: the dispatcher writes the seal, control proves the order, the fallback logs each sha")
# S25 (v1.15, dtp r566 / MARK.1; restated from v1.11's executable lead): §1's EV benchmark is at the mark only
_p1 = re.sub(r"\s+", " ", p.split("THE OPERATOR'S LAYOUT (2026-11-21)", 1)[-1][:1800])   # v2.0: the basis heads the layout
_m25 = re.search(r"# THE SATURDAY BRIEF — spec v(\d+)\.(\d+)", spec)
_s25 = re.sub(r"\s+", " ", spec)
ck("S25", "AT THE MARK, THE ONLY BASIS" in _p1 and "SORTED BY THE MARK EV" in re.sub(r"\s+", " ", p)
   and "the ladder's fill (mark or better)" in _p1 and "No spread-cost line" in _p1 and "never in prose" in _p1
   and "the total adds up from the rows shown" in _p1
   and "LED BY THE EXECUTABLE BASIS" not in _p1 and "the spread cost on its own line" not in _p1
   and "exec_unpriced_n named" not in _p1 and "Mark is the worst buy or sell we accept." in _p1
   and _m25 is not None and (int(_m25.group(1)), int(_m25.group(2))) >= (2, 16)
   and "THE MARK IS THE ONLY BASIS" in _s25 and "sorted by the mark EV" in _s25
   and "the ladder's fill (mark or better)" in _s25 and "**The basis is the mark (v2.16):**" in _s25
   and "Fees beside EV, never inside EV" in _p1 and "net = gross − fees" in _p1
   and "Paper books the mark both ways, which no live fill gets" not in _s25,
   "the prompt's layout head and spec v2.16+: the mark is the only basis, theories by the mark EV, exec only as a "
   "trailing column, fees beside with net = gross − fees")
_shs = open(SH).read()
ck("S23c", '$WORK/study_dispatch — $_fri' in _shs and 'if [ -f "$WORK/study_dispatch/state.json" ]' in _shs
   and _shs.index('_fri="state.json present') < _shs.index('timeout "$BUDGET_S"'),
   "the wrapper tells the session where Friday's run is and whether it happened, before the session starts")

# S22 (v1.7, dtp r550 / CASH.1): THE QQQ CASH SIZE TABLE. The operator, 2026-11-11: "On the weekend prior, let's do a
# table of $250/$500 & $500/$750 with a cap at the ramp max", then "just brief it every weekend until the date arrives".
_c = p.split("THE QQQ CASH SIZE TABLE", 1)[-1][:3200] if "THE QQQ CASH SIZE TABLE" in p else ""
_c1 = p.find("THE QQQ CASH SIZE TABLE")
ck("S22", bool(_c) and "on or after 2026-12-07, skip it" in _c and "$250, ramp max $500" in _c
   and "$500, ramp max $750" in _c and "cap = the ramp max" in _c and "never rounded up to 1" in _c
   and "fees beside it (never in it)" in _c and "REPORT ONLY" in _c and "~/reviews/trades/*.csv" in _c
   and "never an R-item" in _c and p.find("  ## 4. RECOMMENDATIONS") < _c1 < p.find("4.3 THE 12-04 CASH-TEST READINESS"),
   "the prompt's section 4 (4.2) sizes QQQ under both schemes until 2026-12-07, refuses not floors, report only")
_c8 = spec.split("**4.2 The QQQ cash size table", 1)[-1][:3800] if "**4.2 The QQQ cash size table" in spec else ""
ck("S22b", bool(_c8) and "On or after 2026-12-07 the brief skips this item" in _c8 and "| A | $250 | $500 |" in _c8
   and "| B | $500 | $750 |" in _c8 and "never rounded up to one" in _c8 and "Report only:" in _c8
   and "never an R-item" in _c8
   and spec.find("\n## 4. RECOMMENDATIONS") < spec.find("**4.2 The QQQ cash size table") < spec.find("**4.3 The 12-04"),
   "the spec's 4.2 names the same two schemes, the refusal, the date stop and report only")
# S22c (v1.8, dtp r551): THE SIZING RULE IS THE CODE'S. OTV5 _size_geometry floors Breakout's risk count at 1 and
# falls back to geometry; r550 wrote min(floor(...), floor(...)) with no floor and sent a missing stop to NOT MEASURED.
_flat = lambda t: re.sub(r"\s+", " ", t)
_cf, _c8f = _flat(_c), _flat(_c8)
ck("S22c", "by_risk = max(1, floor(base / ((entry - stop premium) x 100))) when 0 < stop premium < entry" in _cf
   and "else the geometry count max(1, floor(width / distance))" in _cf
   and "by_budget = floor(ramp max / (entry x 100)); under 1 the trade is REFUSED" in _cf
   and "Hunt, Runaway, PARK and OGAP take _size_budget: floor(base / (entry x 100))" in _cf
   and "OT_SIZE_ON_RISK is off by default" in _cf
   and "min(floor(base / ((entry - stop premium) x 100))" not in _cf
   and "with no stop premium goes to NOT MEASURED" not in _cf
   and "by_risk = **max(1,** floor(base / ((entry − stop premium) × 100))**)**" in _c8f
   and "max(1, floor(width / distance))" in _c8f and "without a stop premium goes to NOT MEASURED" not in _c8f,
   "the cash table sizes Breakout as size_for does: risk count floored at 1, geometry fallback, refused only over the ramp max")

# S26 (v1.12, OGAP.1): OGAP ON ITS OWN LINE, AND OGAP VS PARK. The operator, 2026-11-14: "let's design & paper trade the
# OGAP on QQQ" (its own line, outside the benchmark) and "compare them" (a rule fixed now, stated verbatim weekly).
_RULE = ("Decide when each has >= 20 index trades, or at 2026-12-31, whichever comes first. Keep the better one if their "
         "daily P&L correlation is >= 0.5. Keep both if both have EV > 0 and correlation < 0.5. Keep neither if neither "
         "clears zero.")
_pf, _sf = _flat(p), _flat(spec)
_o1, _o2 = p.find("· OGAP (standing"), p.find("· OGAP VS PARK")
ck("S26", 0 < p.find("  ### 2A.") < _o1 < _o2 < p.find("· THE HUNT LINE") < p.find("  ### 2B.")
   and "DECISIONS IN PROGRESS, every Saturday brief dated on or before 2026-12-04" in _pf
   and "never in the 10-26..11-27 window EV, the theories" in _pf and "labelled SHADOW, never in EV" in _pf
   and "INDEX rows only (QQQ, SPX)" in _pf and "each row scaled to $500 of premium outlay" in _pf
   and "the correlation of daily P&L" in _pf and _RULE in _pf and "REPORT ONLY" in _pf[_pf.find("OGAP VS PARK"):],
   "the prompt's 2A has OGAP on its own line and OGAP VS PARK with the fixed rule, report only, then the Hunt line")
_m26 = re.search(r"# THE SATURDAY BRIEF — spec v(\d+)\.(\d+)", spec)     # v1.13: v2.13 or any later spec
ck("S26b", _m26 is not None and (int(_m26.group(1)), int(_m26.group(2))) >= (3, 0) and "**OGAP, its own line**" in spec
   and "**OGAP vs PARK**" in spec and _RULE in _sf and "REPORT ONLY" in _sf[_sf.find("**OGAP vs PARK**"):]
   and spec.find("\n### 2A.") < spec.find("**Decisions in progress (every Saturday brief dated on or before 2026-12-04).**")
   < spec.find("**OGAP, its own line**") < spec.find("**OGAP vs PARK**") < spec.find("**The Hunt line.**")
   < spec.find("\n### 2B."),
   "the spec v3.0 carries OGAP and OGAP vs PARK in 2A's decisions in progress with the same rule, verbatim, then the Hunt")

# S27 (v2.0, SAT.10; replaces v1.14's S27/S27b): THE RUNAWAY O08 WOULD-BE IS RETIRED. The operator agreed to drop it,
# 2026-11-21. It is named nowhere in the prompt and in no part of the spec (its changelog entry and the retirement
# table keep the history).
_sp_body = _body(spec).split("## WHAT THIS SPEC RETIRED")[0]
ck("S27", "O08" not in p and "WOULD-BE" not in p.upper() and "O08" not in _sp_body and "1.11" not in _sp_body
   and "| v2.15 §1.11 RUNAWAY O08 WOULD-BE (2026-11-21) | retired" in spec,
   "the O08 would-be is retired: not in the prompt, not in any part of the spec, named in the retirement table")
_NR = os.path.join(ROOT, "tools", "nightly_review.prompt")
ck("S27c", os.path.exists(_NR) and "O08" not in open(_NR).read(),
   "the nightly review does not carry the O08 would-be (the operator said weekend briefs)")

# S28 (v1.15, dtp r566 / MARK.1): OGAP, OGAP VS PARK and the O08 would-be are scored at the mark, in the prompt
# and in spec 1.9-1.11. The operator, 2026-11-19: "I just want the brief to reflect how we actually trade—which is the
# ladder."
_i28, _j28 = _pf.find("· OGAP (standing"), _sf.find("**OGAP, its own line**")
_p28 = _pf[_i28:_pf.find("### 2B.", _i28)] if _i28 >= 0 else ""
_s28 = _sf[_j28:_sf.find("### 2B.", _j28)] if _j28 >= 0 else ""
_bad = ("ask in, bid out", "pnl_exec_usd", "exec-basis", "exec basis", "UNPRICED", "the mark beside it",
        "the mark basis beside it")
ck("S28", bool(_p28) and bool(_s28) and not [b for b in _bad if b in _p28 or b in _s28]
   and _p28.count("the ladder's fill, mark or better") >= 2 and _s28.count("the ladder's fill, mark or better") >= 2,
   "OGAP and OGAP VS PARK at the mark (pnl_usd), no ask/bid basis, no UNPRICED rule; found %s"
   % [b for b in _bad if b in _p28 or b in _s28])

# S29 (v2.0, SAT.10): EVERY AGREED PLACEMENT SITS INSIDE ITS PART, in the prompt and in the spec. The operator, 2026-11-21:
# "the things I forgot to mention should be worked into whichever section they best fit into".
def _parts(text, heads):
    """-> {head: text of that part, up to the next head}; '' for a missing head."""
    pos = [(text.find(h), h) for h in heads]
    out = {}
    for k, (i, h) in enumerate(pos):
        nxt = [j for j, _ in pos[k + 1:] if j > i]
        out[h] = re.sub(r"\s+", " ", text[i:(min(nxt) if nxt else len(text))]) if i >= 0 else ""
    return out


PLACE = {   # part -> phrases that must sit inside it (prompt, spec)
    "1A": (["THE QQQ-ONLY VIEW", "RISK: the worst day", "losing streak", "drawdown from the peak",
            "peak capital deployed", "~$6,250", "LADDER FILL QUALITY", "THE EXCLUDED LINE, every week", "MFE/MAE",
            "net = gross − fees", "r_ledger.py", "weekly_facts.md §1A"],
           ["**the QQQ-only view**", "**risk**", "losing-trade streak", "drawdown from its peak",
            "**peak capital deployed**", "(~$6,250)", "**ladder fill quality.**", "**the exclusions line, every week**",
            "**MFE/MAE**", "net (gross − fees)", "r_ledger.py", "`weekly_facts.md` §1A"]),
    "1B": (["GIVEBACK: ~/reviews/giveback.csv", "NEVER RIGHT on entries", "EACH SETUP AGAINST ITS OWN HISTORY",
            "MISSED AND UNDER-CAPTURED MOVES", "PARK late-day shadow", "selection vs extension"],
           ["**Giveback** (old §1.4)", "**Never right on entries**", "**Each setup against its own history**",
            "**Missed and under-captured moves** (old §1.3)", "**The PARK late-day shadow (never in EV)** (old §1.5)",
            "**selection vs extension**"]),
    "1C": (["the epoch (OTV5 from 2026-10-26)", "improving or worsening, read against the tape", "trend efficiency",
            "median VIX close", "consistency", "noteworthy in the sample", "through the brief of 2026-11-28 only",
            "on or after 2026-12-05, skip it", "SORTED BY THE MARK EV"],
           ["whether it is improving or worsening, read against the tape", "**week by week**", "trend efficiency",
            "the median VIX close", "**consistency**", "**noteworthy in the sample**",
            "through the brief of 2026-11-28 only", "from 2026-12-05 the brief skips it", "**sorted by the mark EV**"]),
    "2A": (["CONDITION CELLS", "WHERE TO LOOK", "stop_sweep", "· OGAP (standing", "· OGAP VS PARK", "· THE HUNT LINE",
            "on or before 2026-12-04"],
           ["**Condition cells**", "**Where to look for edge improvements**", "stop_sweep.py",
            "**OGAP, its own line**", "**OGAP vs PARK**", "**The Hunt line.**", "on or before 2026-12-04"]),
    "2B": (["PASS, FAIL or VOID", "THE COMING FRIDAY'S QUEUE, so the operator can strike any before they run",
            "study_dispatch.py plan", "THE STUDY QUEUE (standing", "at most five"],
           ["**PASS, FAIL or VOID**", "**The coming Friday's queue, so the operator can strike any before they run.**",
            "study_dispatch.py plan", "**The study queue (standing", "at most five"]),
    "3A": (["tools/botlog_scan.py", "tools/checker_sweep.py diffed by check ID", "S3 parity", "days to full",
            "every box on current code"],
           ["botlog_scan.py", "checker_sweep.py", "**S3 parity:**", "**Days to full**",
            "**Every box on current code, and its services:**"]),
    "3B": (["GENESIS", "live evidence", "WORKED, NOT YET EXERCISED", "DID NOT WORK"],
           ["GENESIS", "**live evidence**", "**WORKED**", "**NOT YET EXERCISED**", "**DID NOT WORK**"]),
    "3C": (["BACKLOG.md PART 1", "backlog.json", "documentation corrections, each written as a proposed backlog row",
            "code hygiene, each written as a proposed backlog row"],
           ["PART 1", "backlog.json", "**Documentation corrections, as backlog items** (old §4)",
            "**Code hygiene, as backlog items** (old §5)", "<!-- RETIRED-SEARCH"]),
    "4": (["4.1 RANKED", "4.2 THE QQQ CASH SIZE TABLE", "4.3 THE 12-04 CASH-TEST READINESS CHECKLIST",
           "OT_DAILY_LOSS_LIMIT", "auto-exercise", "the Hunt decision", "the OGAP decision", "the test-day log checklist",
           "4.4 NEXT WEEK'S CALENDAR", "2026-11-26 closed", "2026-11-27 a half day", "the Fed and CPI", "earnings",
           "4.5 THE SUNDAY WORK LIST, LAST", "DELICATE", "ROUTINE", "The brief ENDS with it"],
          ["**4.1 Ranked recommendations.**", "**4.2 The QQQ cash size table", "**4.3 The 12-04 cash-test readiness",
           "`OT_DAILY_LOSS_LIMIT` confirmed", "auto-exercise", "**The Hunt decision**", "**the OGAP decision**",
           "**The test-day log checklist**", "**4.4 Next week's calendar.**", "2026-11-26 is closed",
           "2026-11-27 is a half day", "the Fed and CPI", "earnings on our symbols",
           "**4.5 The Sunday work list (the brief ENDS with it).**", "**DELICATE**", "**ROUTINE**"]),
}
_ph = _parts(p, ["  ### 1A.", "  ### 1B.", "  ### 1C.", "  ### 2A.", "  ### 2B.", "  ### 3A.", "  ### 3B.", "  ### 3C.",
                 "  ## 4. RECOMMENDATIONS", "Put an INDEX on top"])
_sh = _parts(spec, ["\n### 1A.", "\n### 1B.", "\n### 1C.", "\n### 2A.", "\n### 2B.", "\n### 3A.", "\n### 3B.", "\n### 3C.",
                    "\n## 4. RECOMMENDATIONS", "\n## WHAT THIS SPEC RETIRED"])
_pk = dict(zip(PLACE, list(_ph.values())[:9]))
_sk = dict(zip(PLACE, list(_sh.values())[:9]))
_miss_p = {k: [x for x in v[0] if x not in _pk[k]] for k, v in PLACE.items()}
_miss_s = {k: [x for x in v[1] if x not in _sk[k]] for k, v in PLACE.items()}
ck("S29", not any(_miss_p.values()) and p.find("4.4 NEXT WEEK'S CALENDAR") < p.find("4.5 THE SUNDAY WORK LIST, LAST")
   < p.find("Put an INDEX on top"),
   "every agreed placement is inside its part of the prompt, and the Sunday work list is section 4's last item "
   "(missing: %s)" % ({k: v for k, v in _miss_p.items() if v} or "none"))
_s4 = spec[spec.find("\n## 4. RECOMMENDATIONS"):spec.find("\n## WHAT THIS SPEC RETIRED")]
ck("S29b", not any(_miss_s.values()) and _s4.find("**4.4 Next week's calendar.**") < _s4.find("**4.5 The Sunday work list")
   and _s4.rstrip().rstrip("-").rstrip().endswith("only NOT MEASURED follows it."),
   "every agreed placement is inside its part of the spec, and 4.5 ends section 4 (missing: %s)"
   % ({k: v for k, v in _miss_s.items() if v} or "none"))

# S30 (v2.0): NOTHING CURRENTLY COMPUTED SILENTLY DISAPPEARS. The v3.0 changelog maps every old item to a new home or
# RETIRED, and the retirement table names what went.
_v3 = spec[spec.find("**v3.0 ·"):spec.find("**v2.17 ·")] if "**v3.0 ·" in spec and "**v2.17 ·" in spec else ""
_olds = ["§1.1 ", "§1.2 ", "§1.3 ", "§1.4 ", "§1.5 ", "§1.6 ", "§1.7 R ledger", "§1.7 P&L by exit rule", "§1.8 ",
         "§1.9 ", "§1.10 ", "§1.11 ", "§2 ", "§3 ", "§4 ", "§5 ", "§6 counterfactual", "§6 R6", "§7 "]
_rows = {o: next((l for l in _v3.splitlines() if l.startswith("| " + o)), "") for o in _olds}
ck("S30", bool(_v3) and all(_rows.values()) and all(re.search(r"\*\*(1A|1B|1C|2A|2B|3A|3C|4\.\d|RETIRED)\*\*", l)
                                                    for l in _rows.values())
   and "**RETIRED**" in _rows["§1.11 "] and "the operator agreed to drop it" in _rows["§1.11 "],
   "the v3.0 changelog maps every old item (1.1-1.11, 2-7) to a new part or RETIRED (unmapped: %s)"
   % ([o for o, l in _rows.items() if not l] or "none"))

# S34 (v2.1, dtp r571; the 11-21 brief R6): THE R6 NO-PROGRESS LEAD IS RETIRED. Its population is Breakout's, dormant
# since OTV5 r110, so it failed by construction every week (P5 could no longer be met). Named nowhere a session reads as
# an instruction: not in the prompt, not in any part of the spec; the retirement table and the v3.1 entry record it.
_sparts = spec[spec.find("\n## 1. TRADING"):spec.find("\n## WHAT THIS SPEC RETIRED")]
_ret = spec[spec.find("\n## WHAT THIS SPEC RETIRED"):]
_v31 = spec[spec.find("**v3.1 ·"):spec.find("**v3.0 ·")] if "**v3.1 ·" in spec and "**v3.0 ·" in spec else ""
ck("S34", "noprog_lead" not in p and "no-progress lead" not in p.lower() and "noprog_lead" not in _sparts
   and "no-progress lead" not in _sparts.lower() and "| the R6 no-progress lead (2026-11-21) | retired" in _ret
   and "The R6 no-progress lead is RETIRED from 2B" in _v31 and "OTV5 r110" in _v31,
   "the R6 no-progress lead is retired: named in no part of the prompt or the spec, recorded in the retirement table "
   "and the v3.1 entry")
# S35 (v2.1, dtp r571; the 11-21 brief section 4 items 1, 9 and 10, verified on control 2026-11-21: the timer is
# enabled and active, unit files 2026-11-14; GIVE.2 and DAY.1 closed in OTV5 BACKLOG PART 2 at r81).
_b2 = _flat(spec[spec.find("\n### 2B."):spec.find("\n### 3A.")])
_p2 = _flat(p[p.find("  ### 2B."):p.find("  ### 3A.")])
ck("S35", "until then the brief's fallback runs" not in _flat(_sparts) and "until then the brief's fallback runs" not in _flat(p)
   and "**The timer is INSTALLED**" in _b2 and "INSTALLED 2026-11-14, first timer run 2026-11-20" in _p2
   and "**GIVE.2, fleet:**" not in _b2 and "**DAY.1, final score:**" not in _b2
   and "the standing studies (CUT.1, PIN.3)" in _p2 and "GIVE.2" not in _p2 and "DAY.1" not in _p2
   and "| Hunt, Runaway, PARK, OGAP | `_size_budget`" in _c8 and "binds Breakout's rows only" in _c8f
   and "binds Breakout's rows only" in _cf and "(Hunt, Runaway, PARK, OGAP, and Breakout's rows to 2026-11-13)" in _cf,
   "the timer reads INSTALLED, GIVE.2 and DAY.1 are not standing studies, and 4.2 sizes OGAP on the base with the ramp "
   "max binding Breakout's rows only")

# S31-S33 (v2.0): tools/weekly_facts.py, DRIVEN on a fixture (no S3: --no-warehouse).
WF = os.path.join(ROOT, "tools", "weekly_facts.py")
_wf = tempfile.mkdtemp(prefix="chk_satbrief_wf_")
os.makedirs(os.path.join(_wf, "trades"))
_HDR = ("sym,trade_id,strategy,direction,contracts,entry_premium,exit_premium,pnl_usd,entry_time,exit_time,"
        "exit_reason,fee,mfe_premium,entry_exec_premium,exit_exec_premium,pnl_exec_usd,would_fill_live")
_FX = {   # day -> rows (sym, id, strategy, dir, contracts, entry, pnl, entry ET hh:mm, fee, mfe)
    "2026-11-09": [("QQQ", "a1", "RunawayContinuation", "long", 2, 1.00, 100.0, "09:40", 2.50, 1.80),
                   ("SPX", "a2", "PARK", "short", 1, 5.00, -50.0, "11:00", 2.47, 5.00),
                   ("NVDA", "a3", "GEXPinButterfly", "long", 1, 2.00, 40.0, "10:05", 1.25, 2.60)],
    "2026-11-10": [("QQQ", "b1", "LiquidityHunt", "short", 4, 0.50, -80.0, "09:50", 5.00, 0.50),
                   ("QQQ", "b2", "OGAP", "long", 1, 2.00, 30.0, "09:35", 1.25, 2.50),
                   ("AAL", "b3", "RunawayContinuation", "long", 9, 0.10, 999.0, "09:45", 1.00, 0.30)],
    "2026-11-16": [("QQQ", "c1", "RunawayContinuation", "long", 2, 1.00, -60.0, "09:41", 2.50, 1.00),
                   ("SPX", "c2", "PARK", "short", 1, 6.00, 300.0, "11:00", 2.47, 9.50),
                   ("CRM", "c3", "LiquidityHunt", "long", 3, 1.00, 90.0, "10:40", 3.75, 1.60)],
    "2026-11-17": [("QQQ", "d1", "OGAP", "short", 1, 1.50, -20.0, "09:36", "", 1.50),
                   ("QQQ", "d2", "PARK", "long", 2, 2.50, 120.0, "11:00", 2.50, 3.40)],
}
for _d, _rs in _FX.items():
    with open(os.path.join(_wf, "trades", _d + ".csv"), "w") as fh:
        fh.write(_HDR + "\n")
        for (sy, ti, stg, dr, c, ep, pnl, hm, fee, mfe) in _rs:
            hh, mm = map(int, hm.split(":"))
            et_in = "%sT%02d:%02d:00+00:00" % (_d, hh + 5, mm)          # 2026-11: EST, UTC-5
            et_out = "%sT%02d:%02d:00+00:00" % (_d, hh + 6, mm)
            fh.write("%s,%s,%s,%s,%d,%.2f,%.2f,%.2f,%s,%s,exit,%s,%.2f,,,,\n" % (sy, ti, stg, dr, c, ep, ep + pnl / (c * 100),
                                                                              pnl, et_in, et_out, fee, mfe))
_out = os.path.join(_wf, "out")
r = subprocess.run([sys.executable, "-I", WF, "--fri", "2026-11-20", "--out", _out, "--no-warehouse"],
                   capture_output=True, text=True, timeout=300, env=dict(os.environ, DTP_REVIEWS_DIR=_wf))
_j = json.load(open(os.path.join(_out, "weekly_facts.json"))) if r.returncode == 0 else {}
_md = open(os.path.join(_out, "weekly_facts.md")).read() if r.returncode == 0 else ""
_bs = _j.get("week_by_strategy", {})
_net_ok = bool(_bs) and all(abs(a["net"] - (a["gross"] - a["fees"])) < 0.01 and abs(a["ev"] - a["gross"] / a["n"]) < 0.01
                            for a in _bs.values())
_wk = _j.get("week_book", {})
ck("S31", r.returncode == 0 and _net_ok and _wk.get("n") == 5 and abs(_wk.get("gross", 0) - 430.0) < 0.01
   and abs(_wk.get("net", 0) - (430.0 - _wk.get("fees", 0))) < 0.01 and _wk.get("fees_est", 0) > 0
   and "net (gross − fees)" in _md and "x gross |" in _md,
   "weekly_facts: EV is gross a trade, net = gross − fees in its own column, an estimated fee is counted "
   "(rc=%s %s)" % (r.returncode, (r.stderr or "")[-200:]))
_ex = _j.get("excluded", {})
_eb = _j.get("epoch_by_strategy", {})
ck("S32", r.returncode == 0 and "GEXPinButterfly" not in _md and "LiquidityHunt" not in _md   # v2.5 (r579)
   and "setups no longer trading (history)" in _eb
   and _eb["setups no longer trading (history)"]["n"] == 5 and _ex.get("otv4test_rows_csv") == 1   # GEXB 1 + Hunt 2 + OGAP 2
   and _j.get("epoch_book", {}).get("n") == 10 and _j.get("epoch_start") == "2026-10-26",
   "weekly_facts: a setup that no longer trades is one unnamed history line, the OTV4TEST row is dropped and counted, "
   "the epoch starts 2026-10-26")
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.environ["DTP_REVIEWS_DIR"] = _wf
import importlib  # noqa: E402
import review_kit as _RK  # noqa: E402
import weekly_facts as _WF  # noqa: E402
_rows, _ = _WF.load_rows("2026-10-26", "2026-11-20", _wf)
_mine = _WF.boot(_rows, n=3000)
_theirs = _RK.boot(_rows, n=3000)
_ov = _j.get("ogap_vs_park", {})
ck("S33", _mine == _theirs and _mine[0] is not None and _ov.get("overlap_days") == 1
   and abs((_ov.get("OGAP") or {}).get("gross", 0) - (30.0 * 500 / 200 - 20.0 * 500 / 150)) < 0.01
   and "weekly_facts.py" in p and p.find("weekly_facts.py") < p.find("  ## 1. TRADING")
   and "flock /tmp/claude-heavy.lock env HEAVY_MAX=2500M" in p and "--fri <this Friday> --out <WORK>" in p
   and "tools/weekly_facts.py --fri <Fri> --out <WORK>" in spec and "QUOTE IT; never re-derive" in p
   and "raw/candles_full/interval=1d" in spec,
   "weekly_facts' interval is review_kit.boot's own (%s vs %s), OGAP vs PARK scales to $500, the prompt runs it before "
   "section 1 and quotes it, the tape is TastyTrade's daily candles" % (_mine, _theirs))
shutil.rmtree(_wf, ignore_errors=True)

# S36 (v2.2, dtp r572 / SD.3): 2B is the whole week's runs, the weeknights' and Friday's
_p36 = re.sub(r"\s+", " ", p)
_s36 = re.sub(r"\s+", " ", spec)
_b2 = _p36.split("### 2B.", 1)[-1].split("## 3.", 1)[0]
_sh36 = open(SH).read()
ck("S36", "<WORK>/study_dispatch_nightly_<YYYY-MM-DD>" in _b2 and "study_dispatch.py status --out <WORK>/study_dispatch_nightly_" in _b2
   and "2B covers EVERY run of the week" in _b2 and "at most 3 at once" in _b2 and "PARK and Runaway" in _b2
   and re.search(r"# THE SATURDAY BRIEF — spec v3\.([3-9]|\d\d)\n", spec) is not None and "**The whole week's runs (v3.2).**" in spec
   and "study_dispatch_nightly_<YYYY-MM-DD>" in _s36 and "Mon–Fri 17:15 ET" in _s36
   and 'NIGHTLY the week' in _sh36 and "study_dispatch_nightly_20??-??-??" in _sh36
   and _sh36.index("_nightly=") < _sh36.index('timeout "$BUDGET_S"'),
   "2B reads every weeknight folder and Friday's, spec v3.2 says so, the wrapper names them before the session")
# S37 (v2.2, dtp r572 / CASHBOOK.1): the cash candidate books in 1C
_c1 = _p36.split("### 1C.", 1)[-1].split("### 2A.", 1)[0]
_sc1 = _s36.split("### 1C. THE EPOCH (OTV5)")[-1].split("### 2A.", 1)[0]       # the part itself, not the outline
ck("S37", "THE CASH CANDIDATE BOOKS C1-C4" in _c1 and "tools/cash_books.py --through <this Friday>" in _c1
   and "--week-start <this Monday>" in _c1 and "cash_candidates_20261121/PREREG.md" in _c1 and "QUOTE ITS FIGURES" in _c1
   and "never in the window EV or the theories" in _c1 and "choice of book is the operator's" in _c1
   and '"paper size"' in _c1 and "never propose changing a book's definition" in _c1
   and "**The cash candidate books C1–C4 (v3.2).**" in _sc1 and "tools/cash_books.py --through <Fri>" in _sc1
   and "PREREG" in _sc1 and "Report only" in _sc1,
   "1C runs the one C1-C4 scorer for the week and the forward window, quotes it, and keeps the books report-only")

# S38 (v2.3, PREREG amendment 1): both concentration figures or neither
ck("S38", "BESIDE gross without the two largest losers" in _c1 and "never a qualifier" in _c1
   and "never the top-two alone" in _c1 and "gross without the top two" not in _c1 and "leans on its top two" not in _c1
   and "beside gross without the two largest losers" in _sc1 and "never a qualifier" in _sc1
   and "gross without the top two" not in _sc1 and "leans on its top two" not in _sc1,
   "1C's C1-C4 block: ex top-2 only beside ex bottom-2, concentration context, never a qualifier")

# S39 (v2.4, dtp r575 / RWATCH.1): the Runaway equity watch in 2A
_a2 = _p36.split("### 2A.", 1)[-1].split("### 2B.", 1)[0]
_sa2 = _s36.split("### 2A. TOP EARNING SETUP CONDITIONS, AND WHERE TO LOOK FOR EDGE")[-1].split("### 2B.", 1)[0]
ck("S39", "THE RUNAWAY EQUITY WATCH" in _a2 and "tools/runaway_watch.py --through <this Friday>" in _a2
   and "runaway_watch_20261122/WATCH.md" in _a2 and "at least 8" in _a2 and "below zero" in _a2
   and "ON NOTICE / RECOMMEND CUT / OFF THE LIST" in _a2 and "DIRECTION arrow" in _a2 and "QUOTE ITS FIGURES" in _a2
   and "operator's yes, never a decision" in _a2 and "REPORT ONLY" in _a2 and '"paper size"' in _a2
   and "small sample" in _a2 and "NVDA, AMD, META" in _a2
   and "**The Runaway equity watch (v3.3)**" in _sa2 and "tools/runaway_watch.py --through <Fri>" in _sa2
   and "WATCH.md" in _sa2 and "Report only" in _sa2 and "DIRECTION arrow" in _sa2,
   "2A runs the one Runaway watch scorer for the Friday, quotes it, and keeps a cut the operator's yes")

# S40 (v2.4, dtp r575 / HALF.2): a half day is not a session; weekly_facts DRIVEN for the week of 11-23
_wf40 = tempfile.mkdtemp(prefix="chk_satbrief_wf40_")
os.makedirs(os.path.join(_wf40, "trades"))
for _d, _rs in {"2026-11-23": [("QQQ", "h1", "PARK", "long", 2, 1.00, 100.0, "11:01", 2.50, 1.80)],
                "2026-11-27": [("NVDA", "h2", "RunawayContinuation", "long", 1, 2.00, -40.0, "09:45", 1.25, 2.00)]}.items():
    with open(os.path.join(_wf40, "trades", _d + ".csv"), "w") as fh:
        fh.write(_HDR + "\n")
        for (sy, ti, stg, dr, c, ep, pnl, hm, fee, mfe) in _rs:
            hh, mm = map(int, hm.split(":"))
            fh.write("%s,%s,%s,%s,%d,%.2f,%.2f,%.2f,%sT%02d:%02d:00+00:00,%sT%02d:%02d:00+00:00,exit,%s,%.2f,,,,\n" % (
                sy, ti, stg, dr, c, ep, ep + pnl / (c * 100), pnl, _d, hh + 5, mm, _d, hh + 6, mm, fee, mfe))
_o40 = os.path.join(_wf40, "out")
r40 = subprocess.run([sys.executable, "-I", WF, "--fri", "2026-11-27", "--out", _o40, "--no-warehouse"],
                     capture_output=True, text=True, timeout=300, env=dict(os.environ, DTP_REVIEWS_DIR=_wf40))
_j40 = json.load(open(os.path.join(_o40, "weekly_facts.json"))) if r40.returncode == 0 else {}
_md40 = open(os.path.join(_o40, "weekly_facts.md")).read() if r40.returncode == 0 else ""
shutil.rmtree(_wf40, ignore_errors=True)
_rules = _p36.split("THE RULES (the spec explains each one):", 1)[-1].split("THE BOXES:", 1)[0]
ck("S40", r40.returncode == 0 and _j40.get("week") == ["2026-11-23", "2026-11-24", "2026-11-25"]
   and _j40.get("half_days") == ["2026-11-27"] and (_j40.get("week_book") or {}).get("n") == 2
   and [t.get("sym") for t in _j40.get("half_day_trades", [])] == ["NVDA"]
   and "Sessions this week: 3" in _md40 and "DEFECT: trades dated on a half day" in _md40
   and "A 13:00 half day is a NON-TRADING day" in _rules and "never a session" in _rules
   and "15. **A 13:00 half day is a non-trading day**" in spec and "a non-trading day: no entries, data only" in _p36
   and "a non-trading day: no entries, data only" in _s36,
   "weekly_facts: week of 11-23 = %s, half days %s, the 11-27 trade kept and named; the rules say so (rc=%s %s)" % (
       _j40.get("week"), _j40.get("half_days"), r40.returncode, (r40.stderr or "")[-200:]))

# S41 (v2.6, dtp r583 / CASHBOOK.3): C5 beside C1-C4 in 1C
ck("S41", "C5 BESIDE C1-C4" in _c1 and "cash_candidate_c5_20261124/PREREG.md" in _c1
   and "UNH, AMZN, TSLA, SOFI, CVX, NFLX and GOOGL" in _c1 and '"C5 forward" table (from 2026-11-24' in _c1
   and "apart from C1-C4's forward window, which starts 11-23" in _c1
   and "C5'S IN-SAMPLE AND COMBINED FIGURES ARE NEVER EVIDENCE" in _c1 and "ONLY C5'S FORWARD FIGURES COUNT" in _c1
   and '"(hindsight list; forward from 11-24)"' in _c1 and _c1.find("C5 BESIDE C1-C4") > _c1.find("THE CASH CANDIDATE BOOKS C1-C4"),
   "1C shows C5 beside C1-C4: its own forward table from 11-24, hindsight in-sample never evidence")

# S42-S47 (v2.7, dtp r586 / SATLONG.1): the long form - paper vs cash edge transfer (2A) and the full leads ledger (2B),
# one scorer tools/saturday_long.py, DRIVEN on fixtures (no S3: the warehouse rows are injected or --no-warehouse).
from datetime import datetime          # noqa: E402
from zoneinfo import ZoneInfo          # noqa: E402
SL = os.path.join(ROOT, "tools", "saturday_long.py")
_sl_src = open(SL).read() if os.path.exists(SL) else ""
_a2_42 = _p36.split("### 2A.", 1)[-1].split("### 2B.", 1)[0]
_b2_42 = _p36.split("### 2B.", 1)[-1].split("## 3.", 1)[0]
_sa2_42 = _s36.split("### 2A. TOP EARNING SETUP CONDITIONS, AND WHERE TO LOOK FOR EDGE")[-1].split("### 2B.", 1)[0]
_sb2_42 = _s36.split("### 2B. THE WEEK'S STUDIES")[-1].split("## 3. BOT PERFORMANCE", 1)[0]
_TC42 = ("sym,trade_id,strategy,direction,contracts,entry_premium,exit_premium,pnl_usd,entry_time,exit_time,exit_reason,"
         "fee,mfe_premium,entry_exec_premium,exit_exec_premium,pnl_exec_usd,would_fill_live,paper_trade,after_cap")


def _fx42(root):
    """A reviews tree: QQQ in cash mode 11-30 and 12-01 (Service mode LIVE), SPX paper. 11-30: cash k1 with a paper
    twin t1 (25 s), a paper Runaway t9 300 s after k3 (no twin), a walled PARK p1 (another setup, no twin), cash k2 with a
    C5_STRICT model row (1 s: -150; a 0.5 s decoy), cash k3 with neither; an SPX paper row (a paper box)."""
    for d, modes in (("2026-11-30", {"QQQ": "LIVE", "SPX": "PAPER"}), ("2026-12-01", {"QQQ": "LIVE"}),
                     ("2026-12-07", {"QQQ": "LIVE"})):
        bd = os.path.join(root, "daily_brief", "botlogs", d)
        os.makedirs(bd, exist_ok=True)
        for sym, m in modes.items():
            open(os.path.join(bd, sym + ".txt"), "w").write(
                "%s 13:51:04 [INFO ] __main__: Service mode: %s | %s | risk=$1050/trade\n" % (d, m, sym))
    os.makedirs(os.path.join(root, "trades"), exist_ok=True)
    rows = [("QQQ", "k1", "RunawayContinuation", "long", 2, 1.00, 1.50, 100.0, "14:40:05", 2.0, 0),
            ("QQQ", "t1", "RunawayContinuation", "long", 2, 0.98, 1.52, 108.0, "14:40:30", 2.0, 1),
            ("QQQ", "t9", "RunawayContinuation", "long", 1, 0.90, 1.00, 10.0, "16:05:00", 2.0, 1),
            ("QQQ", "p1", "PARK", "long", 2, 1.00, 2.00, 200.0, "14:40:10", 2.0, 1),
            ("QQQ", "k2", "RunawayContinuation", "short", 3, 2.00, 1.60, -120.0, "15:30:00", 2.0, 0),
            ("QQQ", "k3", "RunawayContinuation", "long", 1, 1.00, 1.10, 10.0, "16:00:00", 2.0, 0),
            ("SPX", "s1", "RunawayContinuation", "long", 1, 5.00, 6.00, 100.0, "14:41:00", 2.0, 1)]
    with open(os.path.join(root, "trades", "2026-11-30.csv"), "w") as fh:
        fh.write(_TC42 + "\n")
        for (sy, ti, stg, dr, c, ep, xp, pnl, hms, fee, pap) in rows:
            fh.write("%s,%s,%s,%s,%d,%.2f,%.2f,%.2f,2026-11-30T%s+00:00,2026-11-30T16:30:00+00:00,trail,%.2f,,,,,,%d,\n"
                     % (sy, ti, stg, dr, c, ep, xp, pnl, hms, fee, pap))
    c5 = os.path.join(root, "studies", "C5_STRICT_20261124")
    os.makedirs(c5, exist_ok=True)
    with open(os.path.join(c5, "results_v1_1.csv"), "w") as fh:
        fh.write("day,trade_id,symbol,delay,filled,strict_pnl,scorable\n"
                 "2026-11-30,k2,QQQ,0.5,1,-999.0,1\n2026-11-30,k2,QQQ,1.0,1,-150.0,1\n")
    return [dict(trade_id="k1", entry_bid=0.98, entry_ask=1.00, exit_mark_at_trigger=1.52),
            dict(trade_id="k2", entry_bid=1.98, entry_ask=2.04, exit_bid=1.58, exit_ask=1.64)]


_t42 = tempfile.mkdtemp(prefix="chk_satbrief_long_")
_wh42 = _fx42(_t42)
_E = _E0 = _E1 = None
_err42 = ""
try:
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import saturday_long as SLM          # noqa: E402
    _E = SLM.edge_transfer("2026-12-04", _t42, os.path.join(_t42, "studies"), wh_rows=_wh42)
    _E0 = SLM.edge_transfer("2026-11-27", _t42, os.path.join(_t42, "studies"), use_wh=False)   # before any cash day
    _E1 = SLM.edge_transfer("2026-12-11", _t42, os.path.join(_t42, "studies"), use_wh=False)   # cash box, no trade
except Exception as _e42:                # a crash is a red, never a stop
    _err42 = "%s: %s" % (type(_e42).__name__, _e42)
_o42 = os.path.join(_t42, "out")
r42 = subprocess.run([sys.executable, "-I", SL, "--fri", "2026-12-04", "--out", _o42, "--no-warehouse",
                      "--reviews", _t42], capture_output=True, text=True, timeout=300)
_md42 = open(os.path.join(_o42, "edge_transfer.md")).read() if r42.returncode == 0 else ""
_ld42 = open(os.path.join(_o42, "leads_full.md")).read() if r42.returncode == 0 else ""

ck("S42", "· PAPER VS CASH — EDGE TRANSFER" in _a2_42 and "tools/saturday_long.py --fri <this Friday> --out <WORK>" in _a2_42
   and _a2_42.find("THE RUNAWAY EQUITY WATCH") < _a2_42.find("· PAPER VS CASH — EDGE TRANSFER") < _a2_42.find("· DECISIONS IN PROGRESS")
   and "QUOTE IT" in _a2_42 and "No cash trades this week." in _a2_42 and "MIN_EDGE_EV_PER_TRADE_USD" in _a2_42
   and "· LEADS — FULL LEDGER" in _b2_42 and "<WORK>/leads_full.md" in _b2_42 and "EVERY row" in _b2_42
   and "never a *_TEST* dry run" in _b2_42
   and "**Paper vs cash — edge transfer (v3.4)**" in _sa2_42 and "**Leads — full ledger (v3.4)**" in _sb2_42
   and re.search(r"# THE SATURDAY BRIEF — spec v3\.([4-9]|\d\d)", spec) is not None and "**v3.4 ·" in spec
   and r42.returncode == 0 and _md42.startswith("# Paper vs cash - edge transfer (2A)")
   and _ld42.startswith("# Leads - full ledger (2B)"),
   "2A carries the edge transfer after the Runaway watch, 2B the full leads ledger, spec v3.4 says so, and the one "
   "scorer writes both parts (rc=%s %s)" % (r42.returncode, (r42.stderr or "")[-200:]))

_tr = {t["tid"]: t for t in (_E or {}).get("trades", [])}
_q = next((x for x in (_E or {}).get("symbols", []) if x["sym"] == "QQQ"), None)
_k1, _k2, _k3 = _tr.get("k1", {}), _tr.get("k2", {}), _tr.get("k3", {})
ck("S43", _E is not None and _E["cash_boxes"] == ["QQQ"] and sorted(_tr) == ["k1", "k2", "k3"]
   and _k1.get("cmp") == 108.0 and str(_k1.get("cmp_src", "")).startswith("paper twin t1")
   and _k2.get("cmp") == -150.0 and "C5_STRICT v1.1" in str(_k2.get("cmp_src")) and _k3.get("cmp") is None
   and _E["not_measured"] == ["k3"] and _E["no_slip"] == ["k3"]
   and abs((_k1.get("entry_slip") or 0) - 2.0) < 1e-6 and abs((_k1.get("exit_slip") or 0) - 4.0) < 1e-6
   and abs((_k1.get("mark_pnl") or 0) - 106.0) < 1e-6
   and abs((_k2.get("entry_slip") or 0) + 3.0) < 1e-6 and abs((_k2.get("exit_slip") or 0) - 3.0) < 1e-6
   and _q is not None and _q["week"]["n"] == 3 and _q["week"]["n_cmp"] == 2 and _q["week"]["n_twin"] == 1
   and abs(_q["week"]["diff"] - 22.0) < 1e-6 and abs(_q["week"]["net"] - (-16.0)) < 1e-6
   and _q["cash_start"] == "2026-11-30" and _q["flag"] == "BELOW BASELINE"
   and SLM.flag(_q["cum"], baseline=-10.0) == "at or above"
   and "SPX" not in [x["sym"] for x in _E["symbols"]] and "NOT MEASURED (no comparator): k3." in _md42
   and "C5_STRICT v1.1" in _md42 and "paper twin t1" in _md42,
   "cash rows pair with their paper twin (same box, day, setup, side, within the window; never a walled PARK or a row "
   "300 s away), else the model's 1 s row, else NOT MEASURED; slippage against the row's mark; a paper box is not "
   "listed (%s)" % (_err42 or "trades %s" % sorted(_tr)))

_md0 = SLM.render_edge(_E0) if _E0 else ""
_md1 = SLM.render_edge(_E1) if _E1 else ""
_q1 = next((x for x in (_E1 or {}).get("symbols", []) if x["sym"] == "QQQ"), None)
ck("S44", _E0 is not None and _E0["empty"] and _E0["cash_boxes"] == [] and "No cash trades this week." in _md0
   and "## Cumulative" not in _md0
   and _E1 is not None and _E1["empty"] and _E1["cash_boxes"] == ["QQQ"] and "No cash trades this week." in _md1
   and "Boxes in cash mode with no cash trade: QQQ." in _md1 and _q1 is not None and _q1["cum"]["n"] == 3
   and _q1["cash_start"] == "2026-11-30" and "## Cumulative since each symbol's cash start" in _md1,
   "an empty week prints 'No cash trades this week.'; a cash box with no trade is named and keeps its cumulative book")

_lt = os.path.join(_t42, "leads")
os.makedirs(_lt)
_LH = "\t".join(("id", "opened", "lead", "source_study", "evidence", "status", "next_step", "decision_read",
                 "last_progress", "progress_note"))
open(os.path.join(_lt, "good.tsv"), "w").write("\n".join([
    _LH,
    "L-01\t2026-11-26\tSPX exits A\tSTUDY_A_20261126\t+$10/session in-sample\tFORWARD\tnightly scorer\t~50 sessions\t2026-11-26\topened",
    "L-02\t2026-11-26\tclosed one\t-\tfailed\tCLOSED-checked\t-\t-\t2026-11-26\tclosed",
    "L-03\t2026-11-26\tbad row\tonly four fields",
    "L-04\t2026-11-26\tparked one\tSTUDY_C\tthin\tPARKED\trevisit\t-\t2026-11-20\tparked",
    "L-05\t2026-11-26\tshadow B\tSTUDY_B_20261126\tpost hoc\tFORWARD-SHADOW\tnightly\t~50 sessions\t2026-11-26\tfrozen",
    "L-06\t2026-11-26\tadopt it\tSTUDY_A_20261126\tpassed\tRECOMMEND\tincorporate\t20 fires\t2026-11-27\trecommend incorporating"]) + "\n")
open(os.path.join(_lt, "badhdr.tsv"), "w").write("id\tlead\nL-01\tx\n")
_sa = os.path.join(_t42, "studies", "STUDY_A_20261126")
_sb = os.path.join(_t42, "studies", "STUDY_B_20261126")
os.makedirs(_sa)
os.makedirs(_sb)
open(os.path.join(_sa, "FORWARD_SUMMARY.md"), "w").write(
    "# FORWARD_SUMMARY - STUDY_A frozen arms\n\nGenerated.\n\n**Status:** NOT DECIDABLE: 3/20 counted sessions.\n\n"
    "## Cumulative (counted sessions only)\n\n**All:** n=4, diff +$12/session [-5, +30]\n\n| arm | diff |\n|---|---|\n"
    "| A1 | +12 |\n\n## Daily log (one row per DAY)\n\n| day | x |\n|---|---|\n| 2026-11-30 | DAILYROW |\n")
open(os.path.join(_sa, "FORWARD_SUMMARY_TEST.md"), "w").write("**Status:** TESTROW\n")
open(os.path.join(_sb, "FORWARD_SUMMARY_TEST.md"), "w").write("**Status:** TESTROW\n")
_ts = datetime(2026, 11, 28, 2, 0, tzinfo=ZoneInfo("America/New_York")).timestamp()
os.utime(os.path.join(_sa, "FORWARD_SUMMARY.md"), (_ts, _ts))
_st42 = os.path.join(_t42, "studies")
_Lg = _Lb = _Lm = None
_err45 = ""
try:
    _Lg = SLM.leads_full(os.path.join(_lt, "good.tsv"), _st42)
    _Lb = SLM.leads_full(os.path.join(_lt, "badhdr.tsv"), _st42)
    _Lm = SLM.leads_full(os.path.join(_lt, "missing.tsv"), _st42)
    _rg, _rb, _rm = SLM.render_leads(_Lg), SLM.render_leads(_Lb), SLM.render_leads(_Lm)
except Exception as _e45:
    _err45 = "%s: %s" % (type(_e45).__name__, _e45)
    _rg = _rb = _rm = ""
_ids = [r["id"] for g in (_Lg or {}).get("groups", []) for r in g["rows"]]
_gs = [g["status"] for g in (_Lg or {}).get("groups", [])]
ck("S45", not _err45 and _ids == ["L-06", "L-01", "L-05", "L-04", "L-02"] and _gs[0] == "RECOMMEND"
   and _gs[-1].startswith("CLOSED") and "Skipped (malformed): leads row 4 (L-03)" in _rg
   and "+$10/session in-sample" in _rg and "nightly scorer" in _rg and "~50 sessions" in _rg
   and "2026-11-20: parked" in _rg
   and _Lb is not None and _Lb["err"] and "Leads ledger NOT READ (header is" in _rb
   and _Lm is not None and "Leads ledger NOT READ (not found:" in _rm,
   "every ledger row by status (recommend first, CLOSED last) with evidence, next step and decision read; a malformed "
   "row skipped and named; a bad header or a missing ledger NOT READ, never a crash (%s)" % (_err45 or _ids))

_sc = {s["folder"]: s for s in (_Lg or {}).get("scorers", []) if s.get("folder")}
_fa = (_sc.get("STUDY_A_20261126") or {}).get("files") or [{}]
ck("S46", "STUDY_A_20261126" in _sc and _sc["STUDY_A_20261126"]["leads"] == ["L-01"]
   and _fa[0].get("dated") == "2026-11-28 02:00 ET" and "dated 2026-11-28 02:00 ET" in _rg
   and "Status: NOT DECIDABLE: 3/20 counted sessions." in _rg and "#### Cumulative (counted sessions only)" in _rg
   and "**All:** n=4, diff +$12/session [-5, +30]" in _rg and "| A1 | +12 |" in _rg
   and "DAILYROW" not in _rg and "TESTROW" not in _rg
   and "Dry runs in the folder (never counted, not shown): FORWARD_SUMMARY_TEST.md." in _rg
   and "No forward summary yet (dry run only: FORWARD_SUMMARY_TEST.md)." in _rg
   and "STUDY_C" not in _sc and len(_fa) == 1,
   "each FORWARD / FORWARD-SHADOW lead's scorer: the Status line and the whole cumulative block, dated with the file's "
   "ET time; the daily log and *_TEST* dry runs never shown as a record")

_m47 = re.search(r"^MIN_EDGE_EV_PER_TRADE_USD = (\S+)$", _sl_src, re.M)
_doc47 = _sl_src[max(0, _sl_src.find("THE MINIMUM-EDGE BASELINE")):(_m47.start() if _m47 else 0)]
_cfgs = [os.path.join(ROOT, f) for f in ("config.py", "tools/menu_functions.sh", "menu_functions.sh", "menu_registry.sh")]
_knob = [f for f in _cfgs if os.path.exists(f) and "MIN_EDGE" in open(f).read()]
ck("S47", _m47 is not None and float(_m47.group(1)) == 0.0 and "TODO(operator)" in _doc47
   and "operator's call" in _doc47 and "never a config or env knob" in _doc47
   and "os.environ" not in _sl_src and "getenv" not in _sl_src and not _knob
   and _sl_src.count("MIN_EDGE_EV_PER_TRADE_USD") >= 3
   and "Minimum-edge baseline: net EV a trade below $0.00" in _md42
   and "MIN_EDGE_EV_PER_TRADE_USD" in _sa2_42 and "never a config or env knob" in _sa2_42,
   "the minimum-edge baseline is ONE named constant in saturday_long.py (0, a placeholder), its TODO says it is the "
   "operator's call, nothing reads it from the environment or config, and the brief prints it")

# S48 (v2.7, dtp r586 / SATLONG.1b): a cash trade with no twin and no precomputed model row is priced by the live-fill
# model itself (RUNAWAY_LIVEFILL_CHECK's code, read only, hash-checked, in a child interpreter) from a cached quote
# window; a data failure (no option symbol; no quotes and no S3 read) still renders NOT MEASURED, saying which.
_c48 = os.path.join(_t42, "lfcache")
os.makedirs(_c48)
_te48 = datetime(2026, 11, 30, 15, 0, 0, tzinfo=ZoneInfo("UTC")).timestamp()
_tx48 = _te48 + 600
_q48, _t = [], _te48 - 180
while _t < _te48 + 6 * 3600:
    if _t < _te48 + 3:
        _q48.append([_t, 1.00, 1.02])
    elif _t < _tx48 - 30:
        _q48.append([_t, 0.97, 0.98] if _te48 + 20 <= _t < _te48 + 35 else [_t, 0.99, 1.01])
    elif _t < _tx48 + 20:
        _q48.append([_t, 1.20, 1.22])
    else:
        _q48.append([_t, 1.24, 1.25] if _tx48 + 40 <= _t < _tx48 + 60 else [_t, 1.21, 1.23])
    _t += 1.5
json.dump({"q": _q48}, open(os.path.join(_c48, "k4.json"), "w"))
_cash48 = [dict(trade_id=k, _day="2026-11-30", sym="QQQ", contracts=n, entry_time="2026-11-30T15:00:00+00:00",
                exit_time="2026-11-30T15:10:00+00:00", exit_reason="trail") for k, n in (("k4", "2"), ("k5", "1"), ("k6", "1"))]
_wh48 = {"k4": dict(trade_id="k4", option_symbol="QQQ   261130C00606000", entry_bid=1.00, entry_ask=1.02, exit_bid=1.20,
                    exit_ask=1.22, exit_reason="orb_trail_stop pnl=20%"),
         "k5": dict(trade_id="k5"), "k6": dict(trade_id="k6", option_symbol="QQQ   261130C00606000")}
_err48, _m48, _v48 = "", {}, {}
try:
    _m48 = SLM.compute_models(_cash48, _wh48, _c48, fetch=False)
    _v48 = {c["trade_id"]: SLM.trade_view(c, None, _m48.get(c["trade_id"]), _wh48[c["trade_id"]]) for c in _cash48}
except Exception as _e48:
    _err48 = "%s: %s" % (type(_e48).__name__, _e48)
_k4m = _m48.get("k4") or ()
# ... and through the part itself: a cash box's only trade, no twin, no precomputed row -> the computed comparator
_r48 = os.path.join(_t42, "r48")
os.makedirs(os.path.join(_r48, "daily_brief", "botlogs", "2026-11-30"))
os.makedirs(os.path.join(_r48, "trades"))
open(os.path.join(_r48, "daily_brief", "botlogs", "2026-11-30", "QQQ.txt"), "w").write(
    "2026-11-30 09:15:04 [INFO ] __main__: Service mode: LIVE | QQQ | risk=$1050/trade\n")
with open(os.path.join(_r48, "trades", "2026-11-30.csv"), "w") as fh:
    fh.write(_TC42 + "\nQQQ,k4,RunawayContinuation,long,2,1.00,1.21,42.00,2026-11-30T15:00:00+00:00,"
             "2026-11-30T15:10:00+00:00,trail,2.00,,,,,,0,\n")
_E48 = None
try:
    _E48 = SLM.edge_transfer("2026-12-04", _r48, os.path.join(_r48, "studies"), wh_rows=[_wh48["k4"]], cache=_c48,
                             fetch=False)
except Exception as _e48b:
    _err48 = _err48 or "%s: %s" % (type(_e48b).__name__, _e48b)
_t48 = {t["tid"]: t for t in (_E48 or {}).get("trades", [])}
ck("S48", not _err48 and len(_k4m) == 3 and (_t48.get("k4") or {}).get("cmp") == 42.0
   and "computed" in (_t48.get("k4") or {}).get("cmp_src", "") and (_E48 or {}).get("not_measured") == []
   and (SLM.LIVEFILL_DELAY_S, SLM.LIVEFILL_MODE, SLM.LIVEFILL_START) == (1.0, "strict", "post") and _k4m[0] == 42.0 and _k4m[1] is True and "computed" in _k4m[2]
   and (_v48.get("k4") or {}).get("cmp") == 42.0 and "computed" in (_v48.get("k4") or {}).get("cmp_src", "")
   and (_v48.get("k5") or {}).get("cmp") is None and "no option symbol" in (_v48.get("k5") or {}).get("cmp_src", "")
   and (_v48.get("k6") or {}).get("cmp") is None and "no cached quotes" in (_v48.get("k6") or {}).get("cmp_src", "")
   and "NOT MEASURED" in (_v48.get("k6") or {}).get("cmp_src", "")
   and SLM.LIVEFILL_SHA in _sl_src and SLM.QX_SHA in _sl_src and '"--livefill-worker"' in _sl_src
   and "import fill_v2 as F" in _sl_src and "sys.dont_write_bytecode = True" in _sl_src and "fill_v2.py" not in [os.path.basename(f) for f in os.listdir(os.path.join(ROOT, "tools"))],
   "a QQQ cash trade with no twin and no precomputed row gets the live-fill model's own prediction (imported read only, "
   "hash-checked, cached quotes): %s; a data failure stays NOT MEASURED and says which (%s)"
   % (_k4m, _err48 or {k: v.get("cmp_src") for k, v in _v48.items() if k != "k4"}))
shutil.rmtree(_t42, ignore_errors=True)

print()
if FAILS:
    print(f"FAILED: {', '.join(FAILS)}")
    sys.exit(1)
print(f"ALL PASS ({len(RAN)})")
