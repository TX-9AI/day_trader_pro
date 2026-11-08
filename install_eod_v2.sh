#!/usr/bin/env bash
# day_trader_pro/install_eod_v2.sh — v1.2
# v1.2 (2026-11-08) — dtp r539 / TIMER.1. THE 16:30 dtp-eod-analysis UNIT IS NO LONGER WRITTEN. Its timer has
#   been disabled since v1.0 (the conductor runs eod_analysis.run() itself once the boxes are down) and the
#   devtools item calls eod_analysis.py directly, so the unit had no caller; tools/install_morning_check.sh
#   removes it from control. The operator, 2026-11-08: "consolidate, clean up and optimize". --rollback no longer
#   re-arms it. check_eod_units U2 retired; U3's floor keeps the analysis allowance as a named constant.
# v1.1 (2026-09-11) — dtp r361 / CND.4 + CND.5. 🔴 THIS INSTALLER DROPPED THE
#   CLOSE'S TELEGRAM CREDENTIALS. install_eod_conductor.sh (v1) wrote
#   `EnvironmentFile=${DIR}/.env` into the conductor unit and warned when a
#   name was missing; v1.0 here rewrote the unit WITHOUT it, and notify.py reads
#   only os.environ, so no conductor alert has been delivered since 2026-08-25
#   (23 "[notify] missing" lines in the log before 2026-09-11, three that night).
#   Both units load $REPO/.env again and the names-only presence check is back:
#   it greps for the NAME and never prints a value (WORKING_AGREEMENT §18a).
#   ⚠️ NO `-` PREFIX: an optional EnvironmentFile would make a missing .env
#   silent again; required, the unit refuses to start and says why — the same
#   choice dtp-morning and dtp-shadow-watch already make.
#   🔴 AND TimeoutStartSec 1800 -> 7200. 2026-09-11 verified and halted all 15
#   boxes and was killed at exactly 30:00 inside the last report phase. Floor
#   ~6000s = close ~900 (measured) + purge budget 600 + one overshoot 900 + the
#   analysis unit's declared 3600. Gated by tests/check_eod_units.py.
# v1.0 (2026-08-25) — SWITCH THE CLOSE OVER TO THE THREE-STEP CONDUCTOR.
#
# 🔴 EVERYTHING BUILT THIS WEEKEND WAS LANDED AND NONE OF IT WAS WIRED. The old
# 16:05 unit still ran eod_conductor.py (eleven phases, shutdown in the middle),
# and dtp-harvest at 15:55 and dtp-eod at 16:15 were still armed. Monday's close
# would have run the OLD chain on code we replaced — the same shape as
# s3_push's `--verify` sitting unused for twelve days because nothing called it.
#
# WHAT THIS DOES:
#   16:05  dtp-eod-conductor  -> eod_conductor_v2.py, WHICH THEN RUNS THE
#                                REPORTS ITSELF once the boxes are down
#   15:55  dtp-harvest        -> DISABLED   (the conductor drains to S3 itself)
#   16:15  dtp-eod            -> DISABLED   (P&L now comes from the warehouse)
#   16:30  dtp-eod-analysis   -> REMOVED    (ordered by the conductor, not timed; v1.2)
#
# 🔑 THE REPORTS ARE ORDERED, NOT SCHEDULED. A 16:30 timer with a 25-minute gap
# was a CLOCK STANDING IN FOR A DEPENDENCY. The conductor knows when the close
# finished, so it starts the reports then — and "a slow report must not delay
# the close" is satisfied by ORDER, since the reports begin after takedown.
# ⚠️ CONSEQUENCE, STATED PLAINLY: if control is disabled, NO REPORTS RUN. That
# is correct — reports are a control function. The BOXES still close themselves
# at 16:45 on their own timer, and that is the part that must never depend on
# control being alive.
#
# ⚠️ DISABLED, NOT DELETED. `systemctl disable` leaves the unit on disk, so
# --rollback re-arms the old chain in one command. A switchover you cannot undo
# on a Monday morning is not a switchover, it is a bet.
#
# ⚠️ IT PRINTS THE TIMER TABLE AFTERWARDS. "The command succeeded" and "the
# timers are what I intended" are different claims, and only the second one
# matters at 16:05.
#
# Run:  bash install_eod_v2.sh            # switch over
#       bash install_eod_v2.sh --rollback # back to the old chain
set -euo pipefail

REPO="$HOME/day_trader_pro"
PY="$REPO/venv/bin/python"
MODE="${1:-install}"

if [ "$MODE" = "--rollback" ]; then
  echo "ROLLBACK — restoring the old EOD chain"
  sudo sed -i "s|eod_conductor_v2.py|eod_conductor.py|" \
       /etc/systemd/system/dtp-eod-conductor.service
  sudo systemctl enable --now dtp-harvest.timer dtp-eod.timer 2>/dev/null || true
  sudo systemctl daemon-reload
  echo; systemctl list-timers 'dtp-*' --all --no-pager
  exit 0
fi

# ── 1. repoint the 16:05 conductor ──────────────────────────────────────────
sudo tee /etc/systemd/system/dtp-eod-conductor.service >/dev/null <<UNIT
[Unit]
Description=day_trader_pro EOD conductor v2 (stop trading -> drain -> verify -> take down)
After=network-online.target

[Service]
Type=oneshot
User=ubuntu
WorkingDirectory=$REPO
ExecStart=$PY $REPO/eod_conductor_v2.py
EnvironmentFile=$REPO/.env
StandardOutput=append:$REPO/logs/eod_conductor.log
StandardError=append:$REPO/logs/eod_conductor.log
TimeoutStartSec=7200
UNIT

# ── 3. retire what the new chain replaces ───────────────────────────────────
# harvest: the conductor drains to S3 and the reports read S3, so pulling a
#          second copy to control has no consumer left.
# eod:     P&L came from here AND from eod_summary on each box — two answers to
#          one question. pnl_s3 is now the single source.
sudo systemctl disable --now dtp-harvest.timer 2>/dev/null || true
sudo systemctl disable --now dtp-eod.timer 2>/dev/null || true

# ── 4. can the close page? — NAMES ONLY, never a value (§18a) ──────────────
# v1.1 — restored from install_eod_conductor.sh v1, which this file replaced
# and which was the last installer to check it.
echo "  Telegram credentials for the close (both units load $REPO/.env):"
if [ -f "$REPO/.env" ]; then
  for V in DTP_TELEGRAM_TOKEN DTP_TELEGRAM_CHAT_ID; do
    if grep -q "^$V=" "$REPO/.env"; then echo "   ✅ $V present"
    else echo "   ⚠️  $V MISSING from $REPO/.env — the close still cannot page"; fi
  done
else
  echo "   ⚠️  $REPO/.env does not exist — both units will REFUSE TO START"
fi

mkdir -p "$REPO/logs"
sudo systemctl daemon-reload

echo
echo "=============================================================="
echo "  EOD CHAIN AFTER SWITCHOVER"
echo "=============================================================="
systemctl list-timers 'dtp-*' --all --no-pager
echo
echo "  16:05  conductor v2 — stop trading, drain, verify, take down per box"
echo "  ordered  analysis   — run BY the conductor once the boxes are down"
echo "  15:55  harvest      — DISABLED (conductor drains to S3 itself)"
echo "  16:15  eod_report   — DISABLED (P&L comes from the warehouse)"
echo
echo "  undo:  bash install_eod_v2.sh --rollback"
