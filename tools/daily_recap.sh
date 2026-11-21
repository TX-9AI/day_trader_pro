#!/usr/bin/env bash
# day_trader_pro/tools/daily_recap.sh — v1.0
# v1.0 (2026-11-21) — dtp r569 / RECAP.1. THE DAILY RECAP PDF, EVERY TRADING DAY, FROM A TIMER. The operator,
#   2026-11-21: "Yes, we are going to begin firming up our system, our trading & our analysis". Their process: each
#   trading day the recap proposes studies to improve P&L and ONE piece of code maintenance from the backlog for a yes
#   (Sunday for delicate / live-order-path items); Friday evening, after the recap and the drain, the week's studies
#   run (dtp-study-dispatch, which now waits for this service); Saturday's brief compiles them; Sundays implement.
#   🔑 THE SHAPE IS nightly_review.sh's: a headless `claude -p` in an ISOLATED session (--session-id, never
#   --continue), the prompt in a file beside this script, the paths passed in, a hard budget (timeout), a one-line-per-
#   run ledger, VERTIGO_UNATTENDED=1 so the lander refuses the session, scratch in its own dir on disk, removed.
#   🔑 THE NUMBERS ARE NOT THE SESSION'S TO INVENT: tools/daily_brief.py --facts computes the data pass the PDF prints,
#   and the session quotes it. 🔑 THE SESSION NEVER EDITS THE QUEUE: it writes proposals into its notes and
#   tools/daily_recap.py append adds them to ~/reviews/WEEKEND_STUDIES.md (a .bak first, proven with
#   study_dispatch.parse_queue, idempotent). A session that touches the queue anyway has it restored.
#
# WHEN (tools/dtp-daily-recap.{service,timer}): Mon-Fri 17:00 ET, Persistent. It recaps TODAY only: a weekend or
#   holiday skips (daily_recap.py plan, dtp market_calendar), a session not yet closed + 40 min skips, a half day
#   (13:00 close, 2026-11-27) is recapped at 17:00 like any other. It waits for the nightly review (~/reviews/DAY.md
#   and dtp-nightly-review.service no longer running, up to DAILY_RECAP_REVIEW_WAIT_S), then runs. A day whose PDF
#   exists stands down (it never runs twice for a day; delete the PDF to rebuild), and a second start while one runs
#   stands down on the lock. Notes already written and valid for the day are reused (no second session).
#
# WRITES ONLY: the notes dir (~/reviews/daily_brief/notes/DAY.json, DAY.summary.json), ~/reviews/daily_brief/ (the PDF),
#   the queue file (with WEEKEND_STUDIES.md.bak_recap_YYYYMMDD first), its ledger/log, and its own WORK dir (removed).
#   Read-only on OTV5, S3 and the boxes (no box is read). Never prints an environment.
#
# Usage:  bash tools/daily_recap.sh [--day YYYY-MM-DD] [--dry|--print-cmd]
set -uo pipefail

export PATH="/home/ubuntu/.local/bin:/home/ubuntu/day_trader_pro/venv/bin:/usr/local/bin:/usr/bin:/bin"
export VERTIGO_UNATTENDED=1
HERE="$(dirname "$(readlink -f "$0")")"
DTP="$(dirname "$HERE")"
PY="${DAILY_RECAP_PY:-/home/ubuntu/day_trader_pro/venv/bin/python}"
[ -x "$PY" ] || PY="python3"
BRIEF_PY="${DAILY_RECAP_BRIEF_PY:-/home/ubuntu/venvs/daily_brief/bin/python}"   # outside the repo (install_daily_recap.sh)
HELPER="$HERE/daily_recap.py"
BRIEF="$HERE/daily_brief.py"
PROMPT_FILE="${DAILY_RECAP_PROMPT:-$HERE/daily_recap.prompt}"
REVIEWS="${DAILY_RECAP_REVIEWS:-/home/ubuntu/reviews}"
OUTDIR="${DAILY_RECAP_OUT:-$REVIEWS/daily_brief}"
NOTES_DIR="${DAILY_RECAP_NOTES:-$OUTDIR/notes}"
QUEUE="${DAILY_RECAP_QUEUE:-$REVIEWS/WEEKEND_STUDIES.md}"
MODEL_NOTES="${DAILY_RECAP_MODEL_NOTES:-$NOTES_DIR/2026-11-20.json}"
LOG="${DAILY_RECAP_LOG:-/home/ubuntu/daily_recap.log}"
LEDGER="${DAILY_RECAP_LEDGER:-/home/ubuntu/daily_recap.ledger}"
WORK_ROOT="${DAILY_RECAP_WORK_ROOT:-/home/ubuntu/daily_recap_work}"     # on disk, never the /tmp tmpfs
SYSTEMCTL="${DAILY_RECAP_SYSTEMCTL:-systemctl}"
POST_CMD="${DAILY_RECAP_POST:-$PY /home/ubuntu/day_trader_pro/alert_router.py post --kind info}"
CLAUDE_BIN="${DAILY_RECAP_CLAUDE:-claude}"
TOOLS="Bash,Read,Glob,Grep,Write,Edit,TodoWrite"
MAX_S="${DAILY_RECAP_MAX_S:-2700}"               # the session's hard cap: 45 min
REVIEW_WAIT_S="${DAILY_RECAP_REVIEW_WAIT_S:-9000}"  # the nightly review's own budget
POLL_S="${DAILY_RECAP_POLL_S:-30}"
FACTS_S=900; PDF_S=1200
REPOS="${DAILY_RECAP_REPOS:-/home/ubuntu/OTV5 /home/ubuntu/day_trader_pro /home/ubuntu/options-trader-v4}"
SESSION_ID="$(cat /proc/sys/kernel/random/uuid 2>/dev/null || python3 -c 'import uuid;print(uuid.uuid4())')"
ISOLATE="--session-id $SESSION_ID"
NOW_ARG=""; [ -n "${DAILY_RECAP_NOW:-}" ] && NOW_ARG="--now ${DAILY_RECAP_NOW}"

ledger() { echo "$(date -u +%FT%TZ) $*" >> "$LEDGER"; }
log() { echo "$(date -u +%FT%TZ) $*" >> "$LOG"; }

MODE="run"; DAY_ARG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --day) DAY_ARG="${2:-}"; shift 2 ;;
    --dry|--print-cmd) MODE="${1#--}"; shift ;;
    *) echo "  usage: daily_recap.sh [--day YYYY-MM-DD] [--dry|--print-cmd]"; exit 2 ;;
  esac
done

if [ "$MODE" = "print-cmd" ]; then
  printf '%s\n' "$ISOLATE"
  printf 'timeout=%s\n' "$MAX_S"
  printf 'tools=%s\n' "$TOOLS"
  printf 'permission-mode=acceptEdits\n'
  exit 0
fi

DA=""; [ -n "$DAY_ARG" ] && DA="--day $DAY_ARG"
PLAN="$("$PY" "$HELPER" plan $DA $NOW_ARG 2>&1)"; prc=$?
case "$PLAN" in
  "DAY "*) DAY="${PLAN#DAY }" ;;
  "SKIP "*) _td="${DAILY_RECAP_NOW:0:10}"; [ -n "$_td" ] || _td="$(TZ=America/New_York date +%F)"
           echo "  SKIPPED: ${PLAN#SKIP }"; ledger "SKIPPED day=$_td ${PLAN#SKIP }"; exit 0 ;;
  *) echo "  ⚠️ REFUSED: ${PLAN#REFUSED }"; ledger "REFUSED ${DAY_ARG:-today} ${PLAN#REFUSED }"; exit 2 ;;
esac
PDF="$OUTDIR/daily_brief_$DAY.pdf"
NOTES="$NOTES_DIR/$DAY.json"
REVIEW="$REVIEWS/$DAY.md"

if [ "$MODE" = "dry" ]; then
  echo "  --dry: would recap $DAY"
  echo "  review: $REVIEW $([ -f "$REVIEW" ] && echo present || echo 'missing (would wait)')"
  echo "  notes:  $NOTES $([ -f "$NOTES" ] && echo '(exists: the session would be skipped if valid)')"
  echo "  pdf:    $PDF $([ -f "$PDF" ] && echo '(exists: a real run would stand down)')"
  echo "  queue:  $QUEUE"
  echo "  budget: ${MAX_S}s session; brief python $BRIEF_PY"
  exit 0
fi

if [ -f "$PDF" ]; then
  echo "  recap already built for $DAY - standing down"; ledger "STOOD_DOWN exists day=$DAY $PDF"; exit 0
fi
mkdir -p "$WORK_ROOT" "$NOTES_DIR" "$OUTDIR" || { ledger "FAILED mkdir day=$DAY"; exit 1; }
exec 8> "$WORK_ROOT/.lock"
flock -n 8 || { echo "  a recap is IN FLIGHT - not starting a second"; ledger "STOOD_DOWN inflight day=$DAY"; exit 0; }
{ echo "=============================================================="
  echo " DAILY RECAP $DAY — $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "=============================================================="; } >> "$LOG"

# ── wait for the nightly review (its file AND its service no longer running), capped ──
_waited=0
while :; do
  st="$($SYSTEMCTL show -p ActiveState --value dtp-nightly-review.service 2>/dev/null)"
  if [ -f "$REVIEW" ] && [ "$st" != "activating" ] && [ "$st" != "active" ] && [ "$st" != "reloading" ]; then break; fi
  if [ "$_waited" -ge "$REVIEW_WAIT_S" ]; then log "review wait cap ${REVIEW_WAIT_S}s reached (state=$st)"; break; fi
  sleep "$POLL_S"; _waited=$(( _waited + POLL_S ))
done
REVIEW_STATE="present"; [ -f "$REVIEW" ] || REVIEW_STATE="MISSING"
log "review $REVIEW_STATE after ${_waited}s"

find "$WORK_ROOT" -mindepth 1 -maxdepth 1 -type d -name '20??-??-??-*' -mtime +2 -exec rm -rf -- {} + 2>/dev/null
WORK="$WORK_ROOT/$DAY-$(date +%s)-$$"
mkdir -p "$WORK" || { ledger "FAILED mkdir work day=$DAY"; exit 1; }
trap '[ -n "${WORK:-}" ] && case "$WORK" in "$WORK_ROOT"/20??-??-??-*) rm -rf -- "$WORK" ;; esac' EXIT
export TMPDIR="$WORK"

# ── the data pass (the PDF's own figures) ──
if ! timeout "$FACTS_S" "$BRIEF_PY" -I "$BRIEF" --date "$DAY" --facts "$WORK/facts.json" >> "$LOG" 2>&1; then
  echo "  🔴 the data pass failed for $DAY - see $LOG"; ledger "FAILED facts day=$DAY"; exit 1
fi
"$PY" "$HELPER" context --day "$DAY" --work "$WORK" --queue "$QUEUE" --notes-dir "$NOTES_DIR" >> "$LOG" 2>&1 \
  || { ledger "FAILED context day=$DAY"; exit 1; }

# ── the session (skipped when valid notes for the day already exist) ──
SESSION="skipped"
if [ -f "$NOTES" ] && "$PY" "$HELPER" validate --day "$DAY" --notes "$NOTES" >> "$LOG" 2>&1; then
  log "notes exist and are valid: no session"
else
  [ -f "$PROMPT_FILE" ] || { echo "  ⚠️ REFUSED: no prompt file at $PROMPT_FILE"; ledger "FAILED no_prompt day=$DAY"; exit 1; }
  [ -f "$QUEUE" ] && cp -p "$QUEUE" "$WORK/queue.pre"
  _qsha="$(sha256sum "$QUEUE" 2>/dev/null | cut -c1-64)"
  for r in $REPOS; do [ -d "$r/.git" ] && echo "$r $(git -C "$r" status --porcelain 2>/dev/null | sha256sum | cut -c1-16)"; done > "$WORK/repos.pre"
  _deadline_hm="$(TZ=America/New_York date -d "@$(( $(date +%s) + MAX_S ))" +%H:%M)"
  FRI_NOTE=""; [ "$(date -d "$DAY" +%u)" = 5 ] && FRI_NOTE=" (a Friday: this week's queued studies run on the boxes tonight, after you)"
  ( cd "$WORK" && timeout "$MAX_S" "$CLAUDE_BIN" -p $ISOLATE "$(cat "$PROMPT_FILE")

RUN PARAMETERS (from the wrapper; use them exactly):
  DAY       $DAY$FRI_NOTE
  NOTES     write the notes JSON to exactly this path: $NOTES
  FACTS     $WORK/facts.json
  REVIEW    $REVIEW ($REVIEW_STATE)
  CONTEXT   $WORK/context.md
  MODEL     $MODEL_NOTES
  WORK      $WORK  - EVERY scratch file you make goes here (it is deleted when you finish); never /tmp
  DEADLINE  you are stopped at $_deadline_hm ET; have the file written well before it" \
      --allowedTools "$TOOLS" --permission-mode acceptEdits --add-dir "$NOTES_DIR" --add-dir "$WORK" \
      < /dev/null >> "$LOG" 2>&1 )
  crc=$?
  SESSION="rc=$crc"
  [ "$crc" = "124" ] && log "the session hit its ${MAX_S}s budget (timeout rc=124)"
  # the session never edits the queue: restore it if it did
  if [ -f "$WORK/queue.pre" ] && [ "$(sha256sum "$QUEUE" 2>/dev/null | cut -c1-64)" != "$_qsha" ]; then
    cp -p "$WORK/queue.pre" "$QUEUE"; ledger "QUEUE_RESTORED day=$DAY (the session edited it)"
  fi
  for r in $REPOS; do [ -d "$r/.git" ] && echo "$r $(git -C "$r" status --porcelain 2>/dev/null | sha256sum | cut -c1-16)"; done > "$WORK/repos.post"
  cmp -s "$WORK/repos.pre" "$WORK/repos.post" || ledger "WARN repo_changed day=$DAY $(diff "$WORK/repos.pre" "$WORK/repos.post" | grep '^>' | cut -d' ' -f2 | tr '\n' ' ')"
fi

# ── validate, queue the studies, build the PDF ──
STATUS="PRODUCED"; QUEUED="-"
if [ -f "$NOTES" ] && "$PY" "$HELPER" validate --day "$DAY" --notes "$NOTES" > "$WORK/validate.txt" 2>&1; then
  cat "$WORK/validate.txt" >> "$LOG"
  if [ -f "$QUEUE" ]; then
    QUEUED="$("$PY" "$HELPER" append --day "$DAY" --notes "$NOTES" --queue "$QUEUE" 2>&1)"; arc=$?
    log "$QUEUED"
    [ "$arc" = 0 ] || { STATUS="PARTIAL"; ledger "WARN queue_append_refused day=$DAY"; }
  else
    STATUS="PARTIAL"; ledger "WARN no_queue day=$DAY $QUEUE"
  fi
  NOTES_ARG="--notes $NOTES"
else
  cat "$WORK/validate.txt" >> "$LOG" 2>/dev/null
  STATUS="PARTIAL"; NOTES_ARG="--notes $WORK/none.json"; ledger "WARN notes_missing_or_invalid day=$DAY session=$SESSION"
fi
if ! timeout "$PDF_S" "$BRIEF_PY" -I "$BRIEF" --date "$DAY" $NOTES_ARG --out "$OUTDIR" \
      --summary-json "$WORK/summary.json" >> "$LOG" 2>&1 || [ ! -f "$PDF" ]; then
  echo "  🔴 NO PDF BUILT for $DAY - see $LOG"; ledger "FAILED pdf day=$DAY session=$SESSION"; exit 1
fi
cp "$WORK/summary.json" "$NOTES_DIR/$DAY.summary.json" 2>/dev/null

# ── the one-line notice through control's alert router (status line, no new channel) ──
MSG="$("$PY" "$HELPER" notice --day "$DAY" --notes "$NOTES" --summary "$WORK/summary.json" 2>/dev/null)"
[ "$STATUS" = "PARTIAL" ] && MSG="$MSG (PARTIAL: notes missing or invalid, see $LOG)"
if [ -n "$MSG" ] && eval "$POST_CMD \"\$MSG\"" >> "$LOG" 2>&1; then _n="posted"; else _n="post_failed"; fi
echo "  ✅ recap built: $PDF ($STATUS, notice $_n)"
ledger "$STATUS day=$DAY session=$SESSION notice=$_n queued=$(printf '%s' "$QUEUED" | head -1 | cut -c1-120 | tr ' ' '_') $PDF"
exit 0
