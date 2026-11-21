#!/usr/bin/env bash
# day_trader_pro/tools/friday_studies.sh — v1.2
# v1.2 (2026-11-21) — dtp r569 / RECAP.1. THE DISPATCH STARTS AFTER FRIDAY'S DAILY RECAP, NOT AT A FIXED TIME. The
#   operator, 2026-11-21: "Friday evening, after the daily recap and the drain, run all the studies accumulated during
#   the week". The recap (dtp-daily-recap, 17:00 ET) appends the day's studies to the queue, so the dispatch must read
#   the queue after it. After the conductor wait, this waits for the recap: it is done when its ledger
#   (~/daily_recap.ledger) has a line for today (PRODUCED, PARTIAL, FAILED, STOOD_DOWN or SKIPPED day=<today>), or the
#   service is not installed, or it is not running at two polls in a row with no line. Capped at 2 h
#   (FRIDAY_STUDIES_RECAP_WAIT_S); a recap still running then is logged and the dispatch goes ahead. The timer stays
#   Fri 17:15 ET (not Persistent): it is the earliest start, the waits decide the real one.
#   For the gate only: FRIDAY_STUDIES_SYSTEMCTL, FRIDAY_STUDIES_POLL_S and FRIDAY_STUDIES_LOCK stand in for
#   systemctl, the 30 s poll and the lock file.
# v1.1 (2026-11-15) — dtp r562 / B5.9 (hygiene item 9). The 16:50 below is study_dispatch.RTH_END's, typed again
#   because bash cannot import it; check_const_parity P12 fails the day the two differ. No behaviour change.
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
SYSTEMCTL="${FRIDAY_STUDIES_SYSTEMCTL:-systemctl}"
POLL_S="${FRIDAY_STUDIES_POLL_S:-30}"
LOCK="${FRIDAY_STUDIES_LOCK:-/tmp/study_dispatch_friday.lock}"
RECAP_LEDGER="${FRIDAY_STUDIES_RECAP_LEDGER:-/home/ubuntu/daily_recap.ledger}"
RECAP_WAIT_S="${FRIDAY_STUDIES_RECAP_WAIT_S:-7200}"
DRY=0; [ "${1:-}" = "--dry" ] && DRY=1
_et() { if [ -n "$NOW" ]; then TZ=America/New_York date -d "$NOW" "$@"; else TZ=America/New_York date "$@"; fi; }
DOW="$(_et +%u)"; HM="$(_et +%H%M)"; TODAY="$(_et +%F)"
SAT="$(TZ=America/New_York date -d "$TODAY +1 day" +%F)"
WORK="$WEEKLY/saturday_${SAT}_work"
OUT="$WORK/study_dispatch"
LOG="$WORK/study_dispatch.log"
_ledger() { [ "$DRY" = 1 ] || echo "$(date -u +%FT%TZ) $*" >> "$LEDGER"; }

# 1650 == tools/study_dispatch.py RTH_END (16, 50): pinned by tests/check_const_parity.py P12
if [ "$DOW" != "5" ] || [ "$HM" -lt 1650 ]; then
  echo "SKIPPED: not Friday evening ET ($TODAY $HM, day $DOW); the 03:00 Saturday brief starts the queue itself if needed"
  _ledger "SKIPPED not-friday-evening $TODAY $HM"
  exit 0
fi
if [ "$DRY" = 1 ]; then
  echo "would run: $PY $DTP/tools/study_dispatch.py run --deadline $DEADLINE --out $OUT > $LOG"
  echo "  deadline $DEADLINE ET on $SAT; then study_dispatch.py cleanup; ledger $LEDGER"
  echo "  first waits for the conductor, then for today's daily recap (ledger $RECAP_LEDGER, up to ${RECAP_WAIT_S}s)"
  exit 0
fi

mkdir -p "$OUT" || { _ledger "FAILED cannot-create $OUT"; exit 1; }
# the conductor's capture and stop first (Type=oneshot: 'activating' while it runs)
for _ in $(seq 1 90); do
  st="$($SYSTEMCTL show -p ActiveState --value dtp-eod-conductor.service 2>/dev/null)"
  [ "$st" = "activating" ] || [ "$st" = "active" ] || [ "$st" = "reloading" ] || break
  sleep "$POLL_S"
done
# v1.2: then Friday's daily recap (it appends the day's studies to the queue this run reads)
_rw=0; _idle=0; _why="cap"
while [ "$_rw" -lt "$RECAP_WAIT_S" ]; do
  if grep -Eq "^[^ ]+ (PRODUCED|PARTIAL|FAILED|STOOD_DOWN|SKIPPED) day=$TODAY( |$)" "$RECAP_LEDGER" 2>/dev/null; then
    _why="done"; break
  fi
  [ "$($SYSTEMCTL show -p LoadState --value dtp-daily-recap.service 2>/dev/null)" = "loaded" ] || { _why="not-installed"; break; }
  st="$($SYSTEMCTL show -p ActiveState --value dtp-daily-recap.service 2>/dev/null)"
  if [ "$st" = "activating" ] || [ "$st" = "active" ] || [ "$st" = "reloading" ]; then _idle=0
  else _idle=$(( _idle + 1 )); [ "$_idle" -ge 2 ] && { _why="not-running"; break; }
  fi
  sleep "$POLL_S"; _rw=$(( _rw + POLL_S ))
done
echo "$(date -u +%FT%TZ) friday_studies: daily recap wait ${_rw}s ($_why)" >> "$LOG"
exec 9> "$LOCK"
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
