#!/usr/bin/env bash
# day_trader_pro/tools/saturday_brief.sh — v2.0
# v2.0 (2026-11-11) — dtp r549 / SAT.8 (the operator, 2026-11-11: "What about just waking more boxes at the 0300 to
#   run these studies in parallel?"). The session now starts tools/study_dispatch.py, which runs the study queue on
#   the boxes. This wrapper EXPORTS STUDY_DISPATCH_DEADLINE_ET (the session's own deadline) so the dispatcher's
#   boxes are killed, cleaned and stopped before the session is, and after the session ends it runs
#   `study_dispatch.py cleanup` (only boxes claimed by study_dispatch; it refuses inside the trading window) so a
#   session killed at its deadline cannot leave a recruited box running or claimed.
# v1.9 (2026-11-08) — dtp r539 / TIMER.1 (the operator, 2026-11-08: "consolidate, clean up and optimize"). Comment
#   only: the layer table below named 07:17 / 08:47 / 11:17 UTC; the installed crontab fires the brief Sat 08:00 UTC,
#   the watchdog Sat 12:45 UTC and the canary Wed 07:17 UTC, and the in-session layer was removed (the crontab's
#   own header says why). The table now states what runs. No behaviour change.
# v1.8 (2026-11-08) — dtp r527 / SAT.6 (the 11-07 brief R9; hygiene queue item 2). Operator, 2026-11-07:
#   "These should all be addressed one at a time by their own agent".
#   · A MISSING PROMPT REFUSES FIRST. check_saturday_brief S5 was red in the 11-07 sweep (rc=0): the sweep
#     ran at 03:06-03:24 ET while the real brief held ~/.saturday_brief_inflight, so the wrapper STOOD
#     DOWN on the live marker before it ever reached the prompt check. A missing prompt is a broken chain
#     whatever else is true, so the refusal now comes before the brief-exists and in-flight stand-downs,
#     and it writes one REFUSED line to the ledger. The gate drives its own marker (S5c: a fresh marker
#     AND no prompt must still refuse).
#   · THE BRIEF'S TREES ARE OTV5 AND dtp, NOT THE FROZEN otv4. --smoke asked for otv4's HEAD and the
#     brief reported it as its tree; the run parameters now carry OTV5's and dtp's HEADs (TREES line, also
#     printed by --dry). The session still starts in ~/options-trader-v4: that is the working directory
#     Claude's project memory is keyed by (the operator's standing session uses the same one), and only
#     that; it is never read as a tree.
#   · THE PRIOR BRIEF COMES ONLY FROM ~/reviews/weekly/. The otv4/handoffs/ fallback is gone (no brief has
#     lived there since r520). A prior whose _work folder does not exist (10-31's were in /tmp) is passed
#     as NONE with the reason, so the session does not pass a dead --prior to botlog_scan/checker_sweep.
# v1.7 (2026-10-31) — dtp r520 / SAT.4. THE BRIEF IS REWRITTEN FOR THE FLEET THAT EXISTS, AND IT
#   LEAVES THE GITIGNORED FOLDER. The operator, 2026-10-31: "Re-do the entire brief".
#   · OUT defaults to ~/reviews/weekly/saturday_<date>.md (beside the daily reviews), not
#     options-trader-v4/handoffs/, which is gitignored and which check_scratch_purge P12
#     flags for every authored file. Its working files (sweep.json, botlog.json, disk.json)
#     go to ~/reviews/weekly/saturday_<date>_work/, so next week can diff against them.
#   · The spec it follows is the tracked docs/SATURDAY_BRIEF.md in this repo.
#   · A DEADLINE: the session is killed at 07:30 ET (SATURDAY_BRIEF_DEADLINE_ET), at most
#     SATURDAY_BRIEF_MAX_S (5 h) after it starts; the prompt is told the same time.
#   · THE REAL RUN WRITES ITS OWN IN-FLIGHT MARKER and removes it on exit. Until now only the
#     standing session wrote one, so a long fallback run had nothing stopping the watchdog's
#     retry from starting a second brief beside it. The marker expires after 5 h (was 3 h),
#     longer than the deadline allows a run to live.
# v1.6 (2026-10-02) — r456 / OPS.63. THE SELF-CALLS GO THROUGH bash, NOT THE
#   EXECUTE BIT. The 09-30 canary logged `saturday_brief.sh: Permission denied`
#   and marked the chain broken: git tracks this file 100644, and r454's land
#   rewrote it on disk without the +x it had been hand-given, so `"$0" --smoke`
#   (canary) and `"$0"` (the watchdog's retry) could not run. The brief itself
#   is unaffected — cron calls it via /bin/bash — and --smoke passed when run
#   directly 10-02. Now `bash "$0"`, so no land can break it this way again.
# v1.5 (2026-09-29) — r454 / OPS.61. TWO STANDING SECTIONS IN THE PROMPT, the
#   operator's weekly apples-to-apples read of the two populations. §6 MAIN vs
#   TEST: R per (lineage, strategy) from trade_report.modified_r, MATCHED DAYS
#   ONLY, GROSS OF FEES by his ruling (minuscule test sizes make fees measure the
#   sizing, not the strategy), n<10 flagged, and mean R with the best trade
#   removed. §7 THE TAPE: SOFI/AAL vs QQQ 5-minute return correlation from the
#   warehouse's own candles — "a meaningful proxy for QQQ on the mainline side,
#   not a replacement for QQQ-TEST" — with no conclusion drawn until weeks have
#   accumulated, his caution about one day. Recommendations moved to §8. Also:
#   the prompt's bare "(§40.1)" now names OTV4TEST's WA and quotes it, the same
#   dangling citation r447 fixed in WORKING_AGREEMENT.
# v1.4 (2026-09-26) — r445 / S1. THE MINIMUM-STOP VETO IS REPORTED WEEKLY AND
#   NEVER ENFORCED. Operator approved a REPORT in place of the live recorder I
#   had originally proposed. 🔑 THE RECORDER WAS REDUNDANT AND MEASURING IT IS
#   WHAT SHOWED THAT: `underlying_entry` and `underlying_stop` are present on
#   294 of 294 ORB trades, so what a `stop < 0.05% of spot` veto WOULD have
#   refused is computable RETROACTIVELY over the entire corpus — no box-side
#   code, no deploy, no risk to the trading path, and it works on history from
#   the first run rather than accumulating from today.
#   ⚠️ THE COMPUTATION IS SPELLED OUT IN THE PROMPT so every week's number is
#   the same number; a section that re-derives its own method each Saturday
#   produces a trend out of its own drift.
#   ⚠️ AND IT REPORTS THE KEPT SIDE TOO. A veto is only worth taking if what it
#   refuses is worse than what it keeps, and a refused-only figure cannot show
#   that. It is item 5, BEFORE recommendations — my first cut put it after, so
#   the brief would have reported a finding its own recommendations could not
#   reference.
# v1.3 (2026-09-26) — r440. THE PROMPT MAY NOW WAKE THE FLEET, AND MUST CLOSE
#   IT. Operator: *"The automated session should invoke the wake command
#   through the instance map if it needs to check anything."*
#   🔴 r394 TOLD THIS SESSION "DO NOT START THEM" AND THE OPERATOR HAD NEVER
#   ASKED FOR THAT. His own spec (handoffs/SATURDAY_BRIEF.md) says the
#   opposite in as many words: *"If you start at midnight, I have no problem
#   with that & you can bring up the fleet to check things."* The constraint
#   was mine, invented at r394, and on 2026-09-26 it cost an entire item —
#   the brief reported DISK 0/17 with AAL and SOFI never measured at all,
#   while the session had `Bash` in its tool list the whole time and could
#   have woken them. A session that obeys a wrong instruction correctly looks
#   exactly like one that hit a real limit.
#   ⚠️ THE CLOSE IS MANDATORY AND MUST SURVIVE A FAILURE. Seventeen boxes left
#   up bill all weekend; the prompt now requires the CLOSE even when a
#   measurement raises, and requires the `17/17 reached stopped` line to be
#   quoted rather than assumed.
#   ⚠️ AND THE COMMANDS ARE EXPLICIT, NOT `$PY`. The prompt is text handed to a
#   session, not a shell script — a `$PY` would not expand, and it appeared
#   nowhere else in the file. `./venv/bin/python` is named because dtp's venv
#   carries numpy and the system interpreter does not; the peer session had a
#   land refused by exactly that on the same day.
# v1.2 (2026-09-26) — r432. LOG and LEDGER are OVERRIDABLE, because the gate
#   was writing into them. check_saturday_brief runs THIS script for real with
#   SATURDAY_BRIEF_CLAUDE=/bin/false and a `touch -d "5 hours ago"` in-flight
#   marker — both correct tests — and every such run appended to the
#   PRODUCTION ledger. 97 `FAILED fallback rc=1` lines accumulated, which is
#   /bin/false exiting 1 exactly as instructed, plus 37 `REFUSED: no prompt
#   file` lines from S5 renaming the prompt away.
#   🔴 ON 2026-09-26 THAT LEDGER WAS READ AS A DEAD TIMER AND REPORTED TO THE
#   OPERATOR AS SUCH — on the morning of its FIRST EVER SATURDAY. The only
#   line cron ever wrote is `2026-09-23T07:17:10Z CANARY pass`. The mechanism
#   had never failed; its own test had made its evidence unreadable.
#   ⚠️ A CHECKER MAY NOT MANUFACTURE ENTRIES IN THE AUDIT TRAIL THE OPERATOR
#   READS. Same defect found in dtp's power ledger hours earlier (r431) and in
#   otv4 OPS.6, where checkers resolving ~-expanded defaults built a month of
#   stray bot.log on control. The peer session states it as §40.1: a check may
#   assert only what its OWN child could have done.
# v1.1 (2026-09-20) — dtp r396 / SAT.3. THE SAFETY CLAIM IN v1.0 WAS FALSE
#   and is corrected in the body; this file now EXPORTS VERTIGO_UNATTENDED=1
#   on every path and the lander refuses it. SATURDAY_BRIEF_OUT is
#   overridable so the gate need not run against the live brief path.

# v1.0 (2026-09-20) — dtp r394 / SAT.2. THE SATURDAY BRIEF, ON A TIMER.
#
#   Operator, 2026-09-20: "Everything that you've done for me today has not
#   required any elevated permissions. So I see no reason why waking you with
#   a timer would be any different." He was right, and FOUR of my claims about
#   this mechanism were wrong before one of them was measured:
#     · "it needs sudo"            — no: a USER crontab installs as ubuntu
#                                     through the setgid /usr/bin/crontab.
#     · "cron can only run a script, not the analysis" — no: it runs claude.
#     · "CRON_TZ handles DST"      — NOT SUPPORTED by cron 3.0pl1. A live
#                                     probe never fired and the string is
#                                     absent from /usr/sbin/cron. That entry
#                                     was SILENTLY DEAD.
#     · "--continue wakes his agent" — it APPENDS TO THE LIVE SESSION'S
#                                     TRANSCRIPT. Measured against the
#                                     operator's own running session:
#                                     5137 -> 5161 lines, md5 changed, ZERO
#                                     new session files, and the reply written
#                                     as an assistant entry under THAT
#                                     SESSION'S OWN ID.
#   Every one came from reasoning about a mechanism instead of running it.
#
# 🔑 HE REATTACHES TO A LONG-LIVED AGENT AND THAT IS THE ONE TO WAKE. So the
#   PREFERRED path is an in-session scheduler firing inside that process —
#   not this file. This file is the durable layer underneath it.
#
# 🔴 FOUR LAYERS, BECAUSE THE FAILURE THIS MUST SURVIVE IS SILENCE. A timer
#   that stops firing is indistinguishable from a quiet week.
#     1 REMOVED    the in-session layer (it died with the session that made
#                  it, silently; see the crontab header).
#     2 BRIEF      Sat 08:00 UTC (this file, no flag) = 03:00 EST / 04:00 EDT.
#                  ISOLATED --session-id, stands down if the brief exists or
#                  another run is in flight.
#     3 WATCHDOG   Sat 12:45 UTC (--watchdog). Retries once, then leaves a
#                  file the operator trips over. Nothing here pages them (§17).
#     4 CANARY     WED 07:17 UTC (--canary). Proves the chain midweek, so a
#                  break is found then rather than on Saturday morning.
#
# 🔴 v1.1 — THE ORIGINAL SAFETY CLAIM HERE WAS FALSE AND IS CORRECTED.
#   v1.0 said: "IT LANDS NOTHING, AND THAT IS ENFORCED RATHER THAN REQUESTED.
#   `--allowedTools` omits the lander and every fleet mutator."
#   ⚠️ OMITTING THE LANDER FROM A TOOL LIST DOES NOTHING. `--allowedTools`
#   grants the Bash TOOL, and a tool-name grant DOES NOT SCOPE SHELL COMMANDS
#   — the lander is reached THROUGH Bash. MEASURED 2026-09-20: a session
#   granted only `Bash` was asked to `touch /tmp/allowtest_marker` and the
#   file appeared. Worse, this file's own gate asserted `"deploy.sh" not in
#   TOOLS`, which verified a string was absent from a list that never scoped
#   anything — a check that provided no protection while reading as if it did.
#   🔑 FOUND BY A BRIEF THIS WRAPPER ITSELF PRODUCED. An unattended session
#   spawned during testing wrote 874 lines and led with this defect.
#   🔑 SCOPING IS NOT THE FIX EITHER. `Bash(git log:*)` genuinely blocks an
#   unlisted command — verified — but matching is prefix-based on the command
#   string, so the brief would stall at 03:17 on the first shape nobody
#   anticipated, with nobody awake to approve it.
#   ✅ SO THE ENFORCEMENT MOVED INTO THE THING BEING PROTECTED: this wrapper
#   exports VERTIGO_UNATTENDED=1 and tools/land.sh and tools/deploy.sh BOTH
#   REFUSE it, exit 9. That holds however the session behaves, it is
#   mutation-testable, and it does not rest on CLI semantics misread once.
#   The operator approves every land (§38.9, and his own standing rule).
#
# ⚠️ IT SENDS NOTHING. No Telegram (§17 — the alert path is for emergencies
#   and a weekly report is not one), no push, no commit. One file, then stop.
#
# Usage:  bash tools/saturday_brief.sh [--dry|--smoke|--canary|--watchdog]
set -uo pipefail

export PATH="/home/ubuntu/.local/bin:/usr/local/bin:/usr/bin:/bin"
# 🔴 THE ENFORCEMENT. Exported for EVERY path through this file — brief,
# smoke, canary and watchdog alike — because a session that can land is a
# session that can land whichever flag started it.
export VERTIGO_UNATTENDED=1
# The session's WORKING DIRECTORY only: Claude's project memory is keyed by it, and the operator's
# standing session uses the same one. It is frozen (otv4) and is never reported as the brief's tree.
ANCHOR="${SATURDAY_BRIEF_ANCHOR:-/home/ubuntu/options-trader-v4}"
# The trees the brief is ABOUT (v1.8): their HEADs go into the run parameters and --dry.
OTV5="${SATURDAY_BRIEF_OTV5:-/home/ubuntu/OTV5}"
DTP="${SATURDAY_BRIEF_DTP:-$(dirname "$(dirname "$(readlink -f "$0")")")}"
_head() { git -C "$1" rev-parse --short HEAD 2>/dev/null || echo "UNREADABLE"; }
TREES="OTV5 $(_head "$OTV5") ($OTV5) · dtp $(_head "$DTP") ($DTP)"
STAMP="$(date +%Y-%m-%d)"
# ⚠️ OVERRIDABLE SO THE GATE NEED NOT DEPEND ON TODAY'S REAL BRIEF. Its
# first cut ran against the live path, so once a genuine brief existed the
# wrapper correctly stood down and three checks failed for a reason that had
# nothing to do with what they assert.
WEEKLY="${SATURDAY_BRIEF_WEEKLY:-/home/ubuntu/reviews/weekly}"
OUT="${SATURDAY_BRIEF_OUT:-$WEEKLY/saturday_${STAMP}.md}"
WORK="${OUT%.md}_work"
MARKER="${SATURDAY_BRIEF_MARKER:-/home/ubuntu/.saturday_brief_inflight}"
# 🔑 THE PRIOR BRIEF, FOR THE WEEK-ON-WEEK DIFF: the newest saturday_*.md before today in the
# weekly folder ONLY (v1.8: no handoffs/ fallback). Its _work folder is the --prior for botlog_scan
# and checker_sweep; when it does not exist the session is told NONE and why.
PRIOR="$(ls -1 "$WEEKLY"/saturday_20*.md 2>/dev/null | grep -v "saturday_${STAMP}.md" | sort | tail -1)"
if [ -n "$PRIOR" ] && [ -d "${PRIOR%.md}_work" ]; then
  PRIOR_WORK="${PRIOR%.md}_work"
elif [ -n "$PRIOR" ]; then
  PRIOR_WORK="NONE - ${PRIOR%.md}_work does not exist; run botlog_scan and checker_sweep without --prior and say so"
else
  PRIOR_WORK="NONE - no prior brief; run botlog_scan and checker_sweep without --prior and say so"
fi
# ⏱ THE DEADLINE. The operator reads it after 07:30 ET; a session still running then is
# killed by timeout(1) and the wrapper records FAILED, rather than racing the reader.
DEADLINE_ET="${SATURDAY_BRIEF_DEADLINE_ET:-07:30}"
MAX_S="${SATURDAY_BRIEF_MAX_S:-18000}"
_dl=$(TZ=America/New_York date -d "today $DEADLINE_ET" +%s 2>/dev/null || echo 0)
BUDGET_S=$(( _dl - $(date +%s) ))
# Run by hand after the deadline: the ceiling alone applies.
if [ "$BUDGET_S" -le 0 ] || [ "$BUDGET_S" -gt "$MAX_S" ]; then BUDGET_S="$MAX_S"; fi
# 🔴 OVERRIDABLE SO THE GATE STOPS WRITING INTO THE OPERATOR'S EVIDENCE.
# check_saturday_brief runs THIS script for real with SATURDAY_BRIEF_CLAUDE
# set to /bin/false and a 5-hour-old in-flight marker. Both are correct tests.
# Both appended to the PRODUCTION log and ledger, so a `tail` of the ledger
# showed 97 `FAILED fallback rc=1` lines that were /bin/false doing its job —
# and on 2026-09-26 that read as a dead timer and cost a false alarm to the
# operator before its first Saturday had even arrived. A checker may not
# manufacture entries in the audit trail the operator reads (otv4 OPS.6; the
# peer session's §40.1: a check may assert only what its OWN child could do).
LOG="${SATURDAY_BRIEF_LOG:-/home/ubuntu/saturday_brief.log}"
# 🔑 A ONE-LINE-PER-RUN LEDGER, SEPARATE FROM THE CHATTY LOG. The failure this
# arrangement most needs to survive is SILENCE — a timer that stops firing is
# indistinguishable from a quiet week — so every invocation appends exactly
# one line saying what it did. `tail` on this answers "is the brief still
# happening?" without reading a megabyte of session output.
LEDGER="${SATURDAY_BRIEF_LEDGER:-/home/ubuntu/saturday_brief.ledger}"
# The prompt beside this script (v1.7), so a gate run from a build clone tests the clone's
# prompt, not the live one; the landed path is the same file it always was.
PROMPT_FILE="${SATURDAY_BRIEF_PROMPT:-$(dirname "$(readlink -f "$0")")/saturday_brief.prompt}"

# 🔑 READ AND MEASURE ONLY. Bash is needed because every measurement in this
# brief is a shell or python invocation, but the lander is reached only
# through tools/deploy.sh and that is NOT in this list, so a scheduled run
# cannot commit, push or deploy even if it decided to.
TOOLS="Bash,Read,Glob,Grep,Write,Edit,TodoWrite"

# 🔑 THE BINARY IS INJECTABLE SO THE GATE NEED NOT BUY A REAL RUN. The first
# cut of check_saturday_brief S4 proved the --smoke branch by EXECUTING it,
# which made a live API call on every land — wasteful, and flaky the moment
# the network hiccups, which is a gate that fails for a reason unrelated to
# the thing it checks. The default is unchanged for every real invocation.
CLAUDE_BIN="${SATURDAY_BRIEF_CLAUDE:-claude}"

# ── 🔴 --continue IS FORBIDDEN HERE, AND THIS IS MEASURED ──────────────────
# `claude -p --continue` does NOT fork a new conversation. It APPENDS TO THE
# LIVE SESSION'S TRANSCRIPT. Measured 2026-09-20 against the operator's own
# running session: line count 5137 -> 5161, the file's md5 changed, ZERO new
# session files were created, and the probe's reply was written as an
# assistant entry carrying that session's OWN id.
# ⚠️ THE OPERATOR REATTACHES TO A LONG-LIVED SESSION — he never uses
# --continue. So a timer using it would have had cron writing into the
# transcript of an attached, running agent at 03:17 on a Saturday: two
# writers on one file, and the corruption would surface as a confused agent
# rather than as an error.
# So this wrapper starts an ISOLATED session with its own id. It is the
# fallback for the case where his session is GONE; waking the session he is
# actually attached to is the in-session scheduler's job, not cron's.
SESSION_ID="$(cat /proc/sys/kernel/random/uuid 2>/dev/null || python3 -c 'import uuid;print(uuid.uuid4())')"
ISOLATE="--session-id $SESSION_ID"

{
  echo "=============================================================="
  echo " SATURDAY BRIEF — $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "=============================================================="
} >> "$LOG"

# 🔑 --smoke PROVES THE PLUMBING WITHOUT BUYING THE WHOLE BRIEF. It runs the
# REAL binary, the REAL --allowedTools list, the REAL cwd and the REAL output
# path, but with a two-line prompt. What it verifies is exactly what a cron
# run can get wrong and a --dry run cannot see: that `claude` is on cron's
# stripped PATH, that the tool list is accepted, that a tool actually
# EXECUTES, and that the file lands where the wrapper says it will.
# ⚠️ IT IS NOT A REHEARSAL OF THE BRIEF and does not pretend to be — it proves
# the pipe, not the content.
# ── --watchdog: TURN SILENCE INTO A VISIBLE FAILURE ────────────────────────
# Runs AFTER both the in-session job and the fallback have had their turn. If
# no brief exists by then, nothing else in this arrangement is going to notice
# — so it records a DEGRADED line the operator can see and makes ONE retry.
if [ "${1:-}" = "--watchdog" ]; then
  if [ -f "$OUT" ]; then
    echo "$(date -u +%FT%TZ) WATCHDOG ok $OUT" >> "$LEDGER"
    echo "  watchdog: brief present for $STAMP."
    exit 0
  fi
  echo "$(date -u +%FT%TZ) WATCHDOG DEGRADED no brief for $STAMP — retrying once" >> "$LEDGER"
  echo "  🔴 watchdog: NO BRIEF for $STAMP. Retrying once."
  bash "$0" >> "$LOG" 2>&1
  if [ -f "$OUT" ]; then
    echo "$(date -u +%FT%TZ) WATCHDOG recovered $OUT" >> "$LEDGER"; exit 0
  fi
  echo "$(date -u +%FT%TZ) WATCHDOG FAILED brief missing after retry" >> "$LEDGER"
  # A marker the operator trips over, since nothing here may page him (§17).
  printf 'SATURDAY BRIEF DID NOT RUN on %s — see %s\n' "$STAMP" "$LEDGER" \
    > /home/ubuntu/SATURDAY_BRIEF_FAILED.txt
  exit 1
fi

# ── --print-cmd: THE INVOCATION ITSELF, FOR THE GATE TO ASSERT ON ─────────
# 🔴 THIS EXISTS BECAUSE A MUTATION SURVIVED. Restoring `-c` in place of the
# isolated --session-id was NOT caught: the only checks available were source
# greps, and §21 is explicit that source text proves nothing about runtime —
# a comment mentioning --session-id would satisfy one. Neutering the binary
# hides the difference too, since /bin/false touches no transcript either way.
# So the wrapper PRINTS the flags it will actually pass. That is behaviour,
# it is free, and it cannot be satisfied by prose.
# ⚠️ WHAT IT GUARDS IS NOT COSMETIC: `claude -p --continue` APPENDS TO THE
# LIVE SESSION'S TRANSCRIPT — measured, 5137->5161 lines with zero new session
# files and entries under the attached session's own id. At 03:17 on a
# Saturday that is cron writing into an agent the operator is attached to.
if [ "${1:-}" = "--print-cmd" ]; then
  printf '%s\n' "$ISOLATE"
  printf 'timeout=%s\n' "$BUDGET_S"
  exit 0
fi

# ── --canary: FIND THE BREAK MIDWEEK, NOT ON SATURDAY ──────────────────────
# The whole chain can rot quietly — claude moved, prompt deleted, tool list
# rejected. Discovering that at 08:00 Saturday is discovering it too late, so
# this runs a --smoke midweek and records the verdict in the ledger.
if [ "${1:-}" = "--canary" ]; then
  if bash "$0" --smoke >> "$LOG" 2>&1; then
    echo "$(date -u +%FT%TZ) CANARY pass" >> "$LEDGER"; echo "  canary: pass"; exit 0
  fi
  echo "$(date -u +%FT%TZ) CANARY FAIL the brief chain is broken" >> "$LEDGER"
  printf 'SATURDAY BRIEF CANARY FAILED %s — the chain is broken; see %s\n' \
    "$(date -u +%FT%TZ)" "$LEDGER" > /home/ubuntu/SATURDAY_BRIEF_FAILED.txt
  echo "  🔴 canary: FAIL"; exit 1
fi

if [ "${1:-}" = "--smoke" ]; then
  SMOKE_OUT="/home/ubuntu/saturday_brief_smoke.md"
  rm -f "$SMOKE_OUT"
  echo "  smoke: invoking the real claude with tools [$TOOLS]"
  cd "$ANCHOR" || { echo "  cannot cd $ANCHOR"; exit 1; }
  "$CLAUDE_BIN" -p $ISOLATE "Run exactly one shell command: git -C $OTV5 rev-parse --short HEAD
Then write a file to exactly this path: $SMOKE_OUT
containing one line: SMOKE OK <that sha> <today's date>
Do nothing else. Do not commit, push, or deploy."     --allowedTools "$TOOLS" >> "$LOG" 2>&1
  rc=$?
  if [ -f "$SMOKE_OUT" ]; then
    echo "  ✅ SMOKE PASS — $(cat "$SMOKE_OUT")"
    echo "     claude reachable on a stripped PATH, tool list accepted,"
    echo "     a Bash tool executed, and the file landed at the wrapper's path."
    exit 0
  fi
  echo "  🔴 SMOKE FAIL (claude rc=$rc) — no file at $SMOKE_OUT; see $LOG"
  exit 1
fi

if [ "${1:-}" = "--dry" ]; then
  echo "  --dry: would run claude -p with tools [$TOOLS]"
  echo "  prompt: $PROMPT_FILE"
  echo "  output: $OUT"
  echo "  work:   $WORK"
  echo "  prior:  ${PRIOR:-(none)}"
  echo "  prior_work: $PRIOR_WORK"
  echo "  trees:  $TREES"
  echo "  budget: ${BUDGET_S}s (deadline $DEADLINE_ET ET)"
  [ -f "$PROMPT_FILE" ] && echo "  prompt file present ($(wc -l < "$PROMPT_FILE") lines)" \
                        || echo "  ⚠️ PROMPT FILE MISSING"
  exit 0
fi

# ── 🔑 THE FALLBACK DEFERS TO THE OPERATOR'S STANDING SESSION ──────────────
# The operator keeps 1-REPORTER up 24/7 and his intent is that the timer wakes
# THAT agent — the one already carrying the repo's context — rather than
# spawning a blank one that re-reads every document from scratch. So the
# in-session scheduler is PRIMARY and this wrapper is the FALLBACK for the
# case he cannot cover: the session being down or restarted.
# ⚠️ TWO TIMERS FOR ONE JOB IS A DOUBLE-BRIEF WAITING TO HAPPEN, so this runs
# 90 MINUTES LATER and refuses if the work is already done or in flight.
# 🔴 v1.8: A MISSING PROMPT REFUSES BEFORE EITHER STAND-DOWN. On 11-07 the sweep's S5 ran while the
# real brief held the in-flight marker, the wrapper stood down (rc 0) and never reached this check;
# a missing prompt is a broken chain whatever the marker says.
if [ ! -f "$PROMPT_FILE" ]; then
  echo "  ⚠️ REFUSED: no prompt file at $PROMPT_FILE" | tee -a "$LOG"
  echo "$(date -u +%FT%TZ) REFUSED no_prompt $PROMPT_FILE" >> "$LEDGER"
  exit 1
fi
if [ -f "$OUT" ]; then
  echo "  brief already written for $STAMP — the standing session got there first; exiting."
  echo "$(date -u +%FT%TZ) STOOD_DOWN brief_exists $OUT" >> "$LEDGER"
  exit 0
fi
if [ -f "$MARKER" ]; then
  # ⚠️ AN IN-FLIGHT MARKER THAT NEVER CLEARS WOULD SILENCE THIS FALLBACK
  # FOREVER. A session that crashed mid-brief leaves one behind, and the
  # fallback would then stand down every week while nothing was produced —
  # the exact silent failure this whole arrangement exists to prevent. So the
  # marker EXPIRES: older than 3 hours and it is treated as abandoned.
  _age=$(( $(date +%s) - $(stat -c %Y "$MARKER" 2>/dev/null || echo 0) ))
  if [ "$_age" -lt 18000 ]; then
    echo "  standing session IN FLIGHT (${_age}s) on $STAMP — not starting a second one."
    echo "$(date -u +%FT%TZ) STOOD_DOWN inflight age=${_age}s" >> "$LEDGER"
    exit 0
  fi
  echo "  ⚠️ stale in-flight marker (${_age}s old) — treating as ABANDONED and proceeding."
  echo "$(date -u +%FT%TZ) STALE_MARKER age=${_age}s proceeding" >> "$LEDGER"
  rm -f "$MARKER"
fi

cd "$ANCHOR" || { echo "  ⚠️ cannot cd $ANCHOR" | tee -a "$LOG"; exit 1; }

# ⚠️ THE OUTPUT PATH IS PASSED IN, NOT GUESSED BY THE SESSION. A brief that
# writes to a name nobody predicted is a brief nobody finds.
mkdir -p "$WEEKLY" "$WORK" || { echo "  ⚠️ cannot create $WORK" | tee -a "$LOG"; exit 1; }
touch "$MARKER"
trap 'rm -f "$MARKER"' EXIT
_deadline_hm="$(TZ=America/New_York date -d "@$(( $(date +%s) + BUDGET_S ))" +%H:%M)"
export STUDY_DISPATCH_DEADLINE_ET="$_deadline_hm"   # SAT.8: the box studies end before the session does
timeout "$BUDGET_S" "$CLAUDE_BIN" -p $ISOLATE "$(cat "$PROMPT_FILE")

RUN PARAMETERS (from the wrapper; use them exactly):
  BRIEF   write the finished brief to exactly this path: $OUT
  WORK    your working files (sweep.json, botlog.json, disk.json, tool outputs): $WORK
  PRIOR   last week's brief: ${PRIOR:-NONE - say so; nothing can be called new}
  PRIOR_WORK  last week's working files (the --prior for botlog_scan and checker_sweep): $PRIOR_WORK
  TREES   the trees this brief reports on (section 3.4 and the header): $TREES
  DEADLINE    you are stopped at $_deadline_hm ET; have the file written well before it" \
  --allowedTools "$TOOLS" >> "$LOG" 2>&1
rc=$?

rm -f "$MARKER"
# SAT.8: the safety net. Only boxes claimed by study_dispatch; a no-op when the session cleaned up itself.
_SD="$(dirname "$(readlink -f "$0")")/study_dispatch.py"
if [ -z "${SATURDAY_BRIEF_CLAUDE:-}" ] && [ -f "$_SD" ]; then
  timeout 900 /home/ubuntu/day_trader_pro/venv/bin/python "$_SD" cleanup >> "$LOG" 2>&1 \
    || echo "  ⚠️ study_dispatch cleanup rc=$? — see $LOG" | tee -a "$LOG"
fi
if [ -f "$OUT" ]; then
  echo "  ✅ brief written: $OUT ($(wc -l < "$OUT") lines)" | tee -a "$LOG"
  echo "$(date -u +%FT%TZ) PRODUCED fallback lines=$(wc -l < "$OUT") $OUT" >> "$LEDGER"
  exit 0
fi
[ "$rc" = "124" ] && echo "  🔴 the session hit the $DEADLINE_ET ET deadline (timeout rc=124)" | tee -a "$LOG"
echo "  🔴 NO BRIEF WRITTEN (claude rc=$rc) — see $LOG" | tee -a "$LOG"
echo "$(date -u +%FT%TZ) FAILED fallback rc=$rc" >> "$LEDGER"
exit 1
