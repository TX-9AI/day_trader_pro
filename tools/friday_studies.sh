#!/usr/bin/env bash
# day_trader_pro/tools/friday_studies.sh — v1.0
# v1.0 (2026-11-13) — dtp r552 / SAT.9. THE WEEKEND STUDY QUEUE RUNS FRIDAY NIGHT. The operator, 2026-11-13: "Yes,
#   don't wait until Sunday to do that study. Add it to the rest" (to: move the studies to Friday night so the
#   Saturday brief digests finished results). Started by the control timer dtp-study-dispatch (Fri 17:15 ET, after
#   the 16:05 conductor and the 16:40 nightly review). It runs tools/study_dispatch.py over ~/reviews/WEEKEND_STUDIES.md
#   into the Saturday brief's own WORK folder (~/reviews/weekly/saturday_<Sat>_work/study_dispatch, which the brief
#   collects at 03:00 ET), with the deadline Saturday 02:30 ET (every box is killed, cleaned and stopped 25 min before
#   it), then runs `study_dispatch.py cleanup` as the safety net. One ledger line per run (~/friday_studies.ledger).
#   🔑 IT REFUSES OFF FRIDAY EVENING (Fri 16:50-23:59 ET only): the timer is Persistent=false, and a late catch-up
#   would collide with the 03:00 brief's box reads. The dispatcher itself refuses inside the trading window.
#   🔑 IT WAITS FOR THE CONDUCTOR (dtp-eod-conductor.service, up to 45 min): the conductor's capture and stop must
#   finish before any box is claimed.
#   It lands nothing and sends nothing. Never prints an environment.
# Usage:  bash tools/friday_studies.sh [--dry]
set -uo pipefail
export PATH="/home/ubuntu/.local/bin:/usr/local/bin:/usr/bin:/bin"
export VERTIGO_UNATTENDED=1
DTP="$(dirname "$(dirname "$(readlink -f "$0")")")"
PY="${FRIDAY_STUDIES_PY:-/home/ubuntu/day_trader_pro/venv/bin/python}"
WEEKLY="${FRIDAY_STUDIES_WEEKLY:-/home/ubuntu/reviews/weekly}"
LEDGER="${FRIDAY_STUDIES_LEDGER:-/home/ubuntu/friday_studies.ledger}"
DEADLINE="${FRIDAY_STUDIES_DEADLINE_ET:-02:30}"
NOW="${FRIDAY_STUDIES_NOW:-}"                     # a test clock, "YYYY-MM-DD HH:MM" ET; empty = now
DRY=0; [ "${1:-}" = "--dry" ] && DRY=1
_et() { if [ -n "$NOW" ]; then TZ=America/New_York date -d "$NOW" "$@"; else TZ=America/New_York date "$@"; fi; }
DOW="$(_et +%u)"; HM="$(_et +%H%M)"; TODAY="$(_et +%F)"
SAT="$(TZ=America/New_York date -d "$TODAY +1 day" +%F)"
WORK="$WEEKLY/saturday_${SAT}_work"
OUT="$WORK/study_dispatch"
LOG="$WORK/study_dispatch.log"
_ledger() { [ "$DRY" = 1 ] || echo "$(date -u +%FT%TZ) $*" >> "$LEDGER"; }

if [ "$DOW" != "5" ] || [ "$HM" -lt 1650 ]; then
  echo "SKIPPED: not Friday evening ET ($TODAY $HM, day $DOW); the 03:00 Saturday brief starts the queue itself if needed"
  _ledger "SKIPPED not-friday-evening $TODAY $HM"
  exit 0
fi
if [ "$DRY" = 1 ]; then
  echo "would run: $PY $DTP/tools/study_dispatch.py run --deadline $DEADLINE --out $OUT > $LOG"
  echo "  deadline $DEADLINE ET on $SAT; then study_dispatch.py cleanup; ledger $LEDGER"
  exit 0
fi

mkdir -p "$OUT" || { _ledger "FAILED cannot-create $OUT"; exit 1; }
# the conductor's capture and stop first (Type=oneshot: 'activating' while it runs)
for _ in $(seq 1 90); do
  st="$(systemctl show -p ActiveState --value dtp-eod-conductor.service 2>/dev/null)"
  [ "$st" = "activating" ] || [ "$st" = "active" ] || [ "$st" = "reloading" ] || break
  sleep 30
done
exec 9> /tmp/study_dispatch_friday.lock
flock -n 9 || { echo "another Friday dispatch holds the lock"; _ledger "STOOD_DOWN locked"; exit 0; }
_dl="$(TZ=America/New_York date -d "$SAT $DEADLINE" +%s)"
BUDGET=$(( _dl - $(date +%s) + 900 ))
[ "$BUDGET" -gt 900 ] || { _ledger "SKIPPED past-deadline"; exit 0; }
echo "$(date -u +%FT%TZ) friday_studies: run --deadline $DEADLINE --out $OUT (budget ${BUDGET}s)" >> "$LOG"
cd "$DTP" || exit 1
timeout "$BUDGET" "$PY" tools/study_dispatch.py run --deadline "$DEADLINE" --out "$OUT" >> "$LOG" 2>&1
rc=$?
timeout 900 "$PY" tools/study_dispatch.py cleanup >> "$LOG" 2>&1 || echo "cleanup rc=$?" >> "$LOG"
[ "$rc" = "124" ] && echo "ERROR: the dispatch hit its timeout (rc=124)" >> "$LOG"
_ledger "RAN rc=$rc out=$OUT"
exit "$rc"
