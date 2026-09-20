#!/usr/bin/env bash
# day_trader_pro/tools/saturday_brief.sh — v1.1
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
#     1 PREFERRED  in-session, Sat 07:17 UTC, inside the attached agent.
#                  Best output, most fragile: dies on restart, expires in 7d.
#     2 FALLBACK   Sat 08:47 UTC (this file, no flag). ISOLATED --session-id,
#                  stands down if the brief exists or the primary is in flight.
#     3 WATCHDOG   Sat 11:17 UTC (--watchdog). Retries once, then leaves a
#                  file the operator trips over. Nothing here pages him (§17).
#     4 CANARY     WED 07:17 UTC (--canary). Proves the chain midweek, so a
#                  break is found then rather than at 08:00 Saturday.
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
OTV4="/home/ubuntu/options-trader-v4"
STAMP="$(date +%Y-%m-%d)"
# ⚠️ OVERRIDABLE SO THE GATE NEED NOT DEPEND ON TODAY'S REAL BRIEF. Its
# first cut ran against the live path, so once a genuine brief existed the
# wrapper correctly stood down and three checks failed for a reason that had
# nothing to do with what they assert.
OUT="${SATURDAY_BRIEF_OUT:-$OTV4/handoffs/saturday_${STAMP}.md}"
LOG="/home/ubuntu/saturday_brief.log"
# 🔑 A ONE-LINE-PER-RUN LEDGER, SEPARATE FROM THE CHATTY LOG. The failure this
# arrangement most needs to survive is SILENCE — a timer that stops firing is
# indistinguishable from a quiet week — so every invocation appends exactly
# one line saying what it did. `tail` on this answers "is the brief still
# happening?" without reading a megabyte of session output.
LEDGER="/home/ubuntu/saturday_brief.ledger"
PROMPT_FILE="/home/ubuntu/day_trader_pro/tools/saturday_brief.prompt"

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
  "$0" >> "$LOG" 2>&1
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
  exit 0
fi

# ── --canary: FIND THE BREAK MIDWEEK, NOT ON SATURDAY ──────────────────────
# The whole chain can rot quietly — claude moved, prompt deleted, tool list
# rejected. Discovering that at 08:00 Saturday is discovering it too late, so
# this runs a --smoke midweek and records the verdict in the ledger.
if [ "${1:-}" = "--canary" ]; then
  if "$0" --smoke >> "$LOG" 2>&1; then
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
  cd "$OTV4" || { echo "  cannot cd $OTV4"; exit 1; }
  "$CLAUDE_BIN" -p $ISOLATE "Run exactly one shell command: git -C $OTV4 rev-parse --short HEAD
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
if [ -f "$OUT" ]; then
  echo "  brief already written for $STAMP — the standing session got there first; exiting."
  echo "$(date -u +%FT%TZ) STOOD_DOWN brief_exists $OUT" >> "$LEDGER"
  exit 0
fi
if [ -f /home/ubuntu/.saturday_brief_inflight ]; then
  # ⚠️ AN IN-FLIGHT MARKER THAT NEVER CLEARS WOULD SILENCE THIS FALLBACK
  # FOREVER. A session that crashed mid-brief leaves one behind, and the
  # fallback would then stand down every week while nothing was produced —
  # the exact silent failure this whole arrangement exists to prevent. So the
  # marker EXPIRES: older than 3 hours and it is treated as abandoned.
  _age=$(( $(date +%s) - $(stat -c %Y /home/ubuntu/.saturday_brief_inflight 2>/dev/null || echo 0) ))
  if [ "$_age" -lt 10800 ]; then
    echo "  standing session IN FLIGHT (${_age}s) on $STAMP — not starting a second one."
    echo "$(date -u +%FT%TZ) STOOD_DOWN inflight age=${_age}s" >> "$LEDGER"
    exit 0
  fi
  echo "  ⚠️ stale in-flight marker (${_age}s old) — treating as ABANDONED and proceeding."
  echo "$(date -u +%FT%TZ) STALE_MARKER age=${_age}s proceeding" >> "$LEDGER"
  rm -f /home/ubuntu/.saturday_brief_inflight
fi

if [ ! -f "$PROMPT_FILE" ]; then
  echo "  ⚠️ REFUSED: no prompt file at $PROMPT_FILE" | tee -a "$LOG"
  exit 1
fi

cd "$OTV4" || { echo "  ⚠️ cannot cd $OTV4" | tee -a "$LOG"; exit 1; }

# ⚠️ THE OUTPUT PATH IS PASSED IN, NOT GUESSED BY THE SESSION. A brief that
# writes to a name nobody predicted is a brief nobody finds.
"$CLAUDE_BIN" -p $ISOLATE "$(cat "$PROMPT_FILE")

Write your finished brief to exactly this path: $OUT" \
  --allowedTools "$TOOLS" >> "$LOG" 2>&1
rc=$?

rm -f /home/ubuntu/.saturday_brief_inflight
if [ -f "$OUT" ]; then
  echo "  ✅ brief written: $OUT ($(wc -l < "$OUT") lines)" | tee -a "$LOG"
  echo "$(date -u +%FT%TZ) PRODUCED fallback lines=$(wc -l < "$OUT") $OUT" >> "$LEDGER"
  exit 0
fi
echo "  🔴 NO BRIEF WRITTEN (claude rc=$rc) — see $LOG" | tee -a "$LOG"
echo "$(date -u +%FT%TZ) FAILED fallback rc=$rc" >> "$LEDGER"
exit 1
