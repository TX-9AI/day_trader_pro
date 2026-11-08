#!/usr/bin/env bash
# day_trader_pro/tools/nightly_review.sh — v1.1
# v1.1 (2026-11-08) — dtp r537 / SWEEP.7. EVERY RUN WORKS IN ITS OWN DIRECTORY ON DISK AND REMOVES IT.
#   🔴 The 11-06 backfill session chose /tmp/nr and /tmp/rev1106 for itself (361M, a 196M derived_1106.json) and left
#   them: /tmp on control is a 1.9G tmpfs, it reached 80%, and sqlite VACUUM in two checkers failed "disk I/O error".
#   Now: WORK=$NIGHTLY_REVIEW_WORK_ROOT/<day>-<epoch>-<pid> (default ~/nightly_review_work, on disk), TMPDIR=$WORK for the
#   session, the path in RUN PARAMETERS ("every scratch file goes here, never /tmp"), removed by the EXIT trap on every
#   path out; a run killed before its trap fires leaves a dir that the next run prunes (older than 2 days).
# v1.0 (2026-11-07) — dtp r524 / RPT.36. THE NIGHTLY POST-RTH REVIEW RUNS FROM A SYSTEMD TIMER, NOT FROM A SESSION.
#   🔴 WHAT HAPPENED. The review (~/reviews/YYYY-MM-DD.md, the EV benchmark's daily record) was a session-only
#   CronCreate job ("20 20 * * 1-5", created 10-26). Session jobs expire after 7 days and die with the session: its
#   last fire was 11-02, and the 11-05 01:08 ET restart would have wiped it anyway. It was also fixed in UTC, so after
#   the 11-01 DST change it fired at 15:20 ET, BEFORE the close. 11-03 was written by hand, 11-04/11-05 late on 11-06,
#   11-06 not at all; the 11-07 Saturday brief computed Friday itself (R2). The operator, 2026-11-07: "Yes, on the
#   timer".
#   🔑 THE SHAPE IS saturday_brief.sh's (dtp r520), which has produced every brief since 10-31: a headless
#   `claude -p` in an ISOLATED session (never --continue: that appends to the live session's transcript, measured
#   2026-09-20), the prompt in a file beside this script, the output path passed in, a deadline, a one-line-per-run
#   ledger, an in-flight marker that expires, VERTIGO_UNATTENDED=1 so the lander refuses the session.
#   🔑 THE NUMBERS ARE NOT THE SESSION'S TO INVENT: tools/review_kit.py computes the window, the theories and the
#   giveback (and upserts their CSVs) exactly as the hand-written reviews did; the prompt quotes them.
#
# WHEN (the units, tools/dtp-nightly-review.{service,timer} and dtp-nightly-review-check.{service,timer}):
#   the timer fires Mon-Fri 13:40 and 16:40 ET, Persistent=true (a fire missed while control was down runs at boot).
#   This script decides WHICH session is due (review_kit due: the latest trading day whose close + 40 min has
#   passed - 16:40 ET, 13:40 on a half day such as 11-27; a holiday or weekend names the previous session) and stands
#   down when its review already exists, so the 13:40 fire on a full day and a Persistent catch-up after a written
#   review are both no-ops.
#   18:30 ET (--check-missing): when today is a trading session and its review is missing, ONE status line goes to
#   the operator through control's alert router (alert_router.py post --kind info: the router sends status lines at
#   P1); if the router is not healthy the line still waits in its outbox (replayed for 15 min) and
#   ~/NIGHTLY_REVIEW_MISSING.txt is written as the marker the operator trips over.
#
# Usage:  bash tools/nightly_review.sh [--day YYYY-MM-DD] [--dry|--print-cmd|--check-missing]
#   --day D   review session D (a backfill); refused unless D is a trading day whose close has passed
set -uo pipefail

export PATH="/home/ubuntu/.local/bin:/home/ubuntu/day_trader_pro/venv/bin:/usr/local/bin:/usr/bin:/bin"
# 🔴 THE ENFORCEMENT, as in saturday_brief.sh: tools/land.sh and tools/deploy.sh exit 9 under it.
export VERTIGO_UNATTENDED=1
HERE="$(dirname "$(readlink -f "$0")")"
PY="${NIGHTLY_REVIEW_PY:-/home/ubuntu/day_trader_pro/venv/bin/python}"
[ -x "$PY" ] || PY="python3"
KIT="$HERE/review_kit.py"
PROMPT_FILE="${NIGHTLY_REVIEW_PROMPT:-$HERE/nightly_review.prompt}"
REVIEWS="${NIGHTLY_REVIEW_DIR:-/home/ubuntu/reviews}"
LOG="${NIGHTLY_REVIEW_LOG:-/home/ubuntu/nightly_review.log}"
LEDGER="${NIGHTLY_REVIEW_LEDGER:-/home/ubuntu/nightly_review.ledger}"
MARKER="${NIGHTLY_REVIEW_MARKER:-/home/ubuntu/.nightly_review_inflight}"
MISSING_FLAG="${NIGHTLY_REVIEW_MISSING_FLAG:-/home/ubuntu/NIGHTLY_REVIEW_MISSING.txt}"
WORK_ROOT="${NIGHTLY_REVIEW_WORK_ROOT:-/home/ubuntu/nightly_review_work}"   # on disk, never the /tmp tmpfs
# The page. Injectable so the gate never queues a real line into the operator's Telegram.
POST_CMD="${NIGHTLY_REVIEW_POST:-$PY /home/ubuntu/day_trader_pro/alert_router.py post --kind info}"
ALIVE_CMD="${NIGHTLY_REVIEW_ALIVE:-}"          # empty: ask alert_router.router_alive (health.json within 120 s)
CLAUDE_BIN="${NIGHTLY_REVIEW_CLAUDE:-claude}"
TOOLS="Bash,Read,Glob,Grep,Write,Edit,TodoWrite"
MAX_S="${NIGHTLY_REVIEW_MAX_S:-9000}"          # 2.5 h ceiling; the 18:30 check comes first only if it overruns
SESSION_ID="$(cat /proc/sys/kernel/random/uuid 2>/dev/null || python3 -c 'import uuid;print(uuid.uuid4())')"
ISOLATE="--session-id $SESSION_ID"
# NIGHTLY_REVIEW_NOW (ISO, ET) stands in for the clock so the gate can ask "what is due at 13:40 on 11-27".
NOW_ARG=""
[ -n "${NIGHTLY_REVIEW_NOW:-}" ] && NOW_ARG="--now ${NIGHTLY_REVIEW_NOW}"

ledger() { echo "$(date -u +%FT%TZ) $*" >> "$LEDGER"; }

MODE="run"; DAY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --day) DAY="${2:-}"; shift 2 ;;
    --dry|--print-cmd|--check-missing) MODE="${1#--}"; shift ;;
    *) echo "  usage: nightly_review.sh [--day YYYY-MM-DD] [--dry|--print-cmd|--check-missing]"; exit 2 ;;
  esac
done

if [ "$MODE" = "print-cmd" ]; then
  # Behaviour, not prose, for the gate: the flags this wrapper will really pass.
  printf '%s\n' "$ISOLATE"
  printf 'timeout=%s\n' "$MAX_S"
  printf 'tools=%s\n' "$TOOLS"
  exit 0
fi

DUE="$("$PY" "$KIT" due $NOW_ARG 2>/dev/null)"

if [ "$MODE" = "check-missing" ]; then
  TODAY="$("$PY" -c 'import sys; sys.path.insert(0, "'"$HERE"'/.."); import ettime; print(ettime.today_et())' 2>/dev/null)"
  [ -n "${NIGHTLY_REVIEW_NOW:-}" ] && TODAY="${NIGHTLY_REVIEW_NOW:0:10}"
  if [ -z "$DUE" ] || [ "$DUE" != "$TODAY" ]; then
    echo "  check: no session of today's due (${DUE:-none}; today $TODAY) - nothing to check"
    ledger "CHECK not_a_session today=$TODAY due=${DUE:-none}"
    exit 0
  fi
  if [ -f "$REVIEWS/$DUE.md" ]; then
    echo "  check: review present for $DUE"
    ledger "CHECK ok $REVIEWS/$DUE.md"
    exit 0
  fi
  MSG="NIGHTLY REVIEW MISSING for $DUE: no $REVIEWS/$DUE.md at $(TZ=America/New_York date +%H:%M) ET. Last ledger line: $(tail -n 1 "$LEDGER" 2>/dev/null | cut -c1-160)"
  if eval "$POST_CMD \"\$MSG\"" >> "$LOG" 2>&1; then
    ledger "CHECK MISSING paged $DUE"
    echo "  🔴 check: review MISSING for $DUE - paged through the router"
  else
    ledger "CHECK MISSING page_failed $DUE"
    echo "  🔴 check: review MISSING for $DUE - the router post FAILED"
  fi
  if [ -n "$ALIVE_CMD" ]; then eval "$ALIVE_CMD" >/dev/null 2>&1; _alive=$?
  else "$PY" -c 'import sys; sys.path.insert(0, "/home/ubuntu/day_trader_pro"); import alert_router as a; sys.exit(0 if a.router_alive(max_age_s=120) else 1)' >/dev/null 2>&1; _alive=$?
  fi
  if [ "$_alive" != 0 ]; then
    printf '%s\n(the alert router was not healthy at the check; the line waits in its outbox)\n' "$MSG" > "$MISSING_FLAG"
    ledger "CHECK router_not_alive marker $MISSING_FLAG"
  fi
  exit 1
fi

if [ -n "$DAY" ]; then
  # A backfill: the day must be a trading session whose review is already due (never a future or open session).
  OK="$("$PY" - "$DAY" "$KIT" <<'PYEOF'
import sys, importlib.util
from datetime import date, datetime, timedelta
spec = importlib.util.spec_from_file_location("rk", sys.argv[2]); rk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rk)
try:
    d = date.fromisoformat(sys.argv[1])
except ValueError:
    print("bad"); sys.exit()
now = datetime.now(rk.ET)
print("ok" if rk.market_calendar.is_trading_day(d) and now >= rk.close_et(d) + timedelta(minutes=rk.DUE_AFTER_MIN) else "bad")
PYEOF
)"
  if [ "$OK" != "ok" ]; then
    echo "  ⚠️ REFUSED: --day $DAY is not a trading session whose review is due"; ledger "REFUSED day=$DAY"; exit 2
  fi
  DUE="$DAY"
fi

if [ -z "$DUE" ]; then
  echo "  no session due"; ledger "NOT_DUE"; exit 0
fi
OUT="$REVIEWS/$DUE.md"
PRIOR="$(ls -1 "$REVIEWS"/20??-??-??.md 2>/dev/null | awk -v d="$REVIEWS/$DUE.md" '$0 < d' | sort | tail -1)"

if [ "$MODE" = "dry" ]; then
  echo "  --dry: would review $DUE with claude -p [$TOOLS]"
  echo "  prompt: $PROMPT_FILE"
  echo "  output: $OUT"
  echo "  prior:  ${PRIOR:-(none)}"
  echo "  budget: ${MAX_S}s"
  [ -f "$PROMPT_FILE" ] && echo "  prompt file present ($(wc -l < "$PROMPT_FILE") lines)" || echo "  ⚠️ PROMPT FILE MISSING"
  [ -f "$OUT" ] && echo "  (the review exists; a real run would stand down)"
  exit 0
fi

if [ -f "$OUT" ]; then
  echo "  review already written for $DUE - standing down"; ledger "STOOD_DOWN exists $OUT"; exit 0
fi
if [ -f "$MARKER" ]; then
  # ⚠️ AN IN-FLIGHT MARKER THAT NEVER CLEARS WOULD SILENCE THE TIMER FOREVER, so it expires past the budget.
  _age=$(( $(date +%s) - $(stat -c %Y "$MARKER" 2>/dev/null || echo 0) ))
  if [ "$_age" -lt "$MAX_S" ]; then
    echo "  a review is IN FLIGHT (${_age}s) - not starting a second"; ledger "STOOD_DOWN inflight age=${_age}s"; exit 0
  fi
  ledger "STALE_MARKER age=${_age}s proceeding"; rm -f "$MARKER"
fi
if [ ! -f "$PROMPT_FILE" ]; then
  echo "  ⚠️ REFUSED: no prompt file at $PROMPT_FILE" | tee -a "$LOG"; ledger "FAILED no_prompt"; exit 1
fi
mkdir -p "$REVIEWS" || { ledger "FAILED mkdir"; exit 1; }
cd "$REVIEWS" || { ledger "FAILED cd"; exit 1; }
{ echo "=============================================================="
  echo " NIGHTLY REVIEW $DUE — $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "=============================================================="; } >> "$LOG"
touch "$MARKER"
# The session's scratch: its own dir on disk, pruned of any killed run's leftovers, removed on every path out.
mkdir -p "$WORK_ROOT" || { rm -f "$MARKER"; ledger "FAILED mkdir work"; exit 1; }
find "$WORK_ROOT" -mindepth 1 -maxdepth 1 -type d -name '20??-??-??-*' -mtime +2 -exec rm -rf -- {} + 2>/dev/null
WORK="$WORK_ROOT/$DUE-$(date +%s)-$$"
mkdir -p "$WORK" || { rm -f "$MARKER"; ledger "FAILED mkdir work"; exit 1; }
trap 'rm -f "$MARKER"; [ -n "${WORK:-}" ] && case "$WORK" in "$WORK_ROOT"/20??-??-??-*) rm -rf -- "$WORK" ;; esac' EXIT
export TMPDIR="$WORK"
_deadline_hm="$(TZ=America/New_York date -d "@$(( $(date +%s) + MAX_S ))" +%H:%M)"
timeout "$MAX_S" "$CLAUDE_BIN" -p $ISOLATE "$(cat "$PROMPT_FILE")

RUN PARAMETERS (from the wrapper; use them exactly):
  DAY       $DUE
  OUT       write the finished review to exactly this path: $OUT
  PRIOR     the previous review, the format to follow: ${PRIOR:-NONE - use the section list above}
  KIT       $KIT  (python: $PY)
  WORK      $WORK  - EVERY scratch file you make goes here (it is deleted when you finish); never /tmp
  DEADLINE  you are stopped at $_deadline_hm ET; have the file written well before it" \
  --allowedTools "$TOOLS" >> "$LOG" 2>&1
rc=$?
rm -f "$MARKER"
if [ -f "$OUT" ]; then
  echo "  ✅ review written: $OUT ($(wc -l < "$OUT") lines)" | tee -a "$LOG"
  ledger "PRODUCED lines=$(wc -l < "$OUT") $OUT"
  rm -f "$MISSING_FLAG"
  exit 0
fi
[ "$rc" = "124" ] && echo "  🔴 the session hit its ${MAX_S}s budget (timeout rc=124)" | tee -a "$LOG"
echo "  🔴 NO REVIEW WRITTEN for $DUE (claude rc=$rc) - see $LOG" | tee -a "$LOG"
ledger "FAILED rc=$rc $DUE"
exit 1
