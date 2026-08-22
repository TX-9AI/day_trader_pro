#!/usr/bin/env bash
# day_trader_pro/install_eod_v2.sh — v1.0
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
#   16:30  dtp-eod-analysis   -> DISABLED   (ordered by the conductor, not timed)
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
  sudo systemctl enable --now dtp-eod-analysis.timer 2>/dev/null || true
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
StandardOutput=append:$REPO/logs/eod_conductor.log
StandardError=append:$REPO/logs/eod_conductor.log
TimeoutStartSec=1800
UNIT

# ── 2. the reports, 25 minutes later ────────────────────────────────────────
# ⚠️ THIS UNIT IS INSTALLED BUT ITS TIMER IS DISABLED. The conductor invokes
# eod_analysis directly once the boxes are down, so the schedule below is only
# a fallback the operator can re-arm; the service definition is what devtools
# item 56 and any manual re-run use.
sudo tee /etc/systemd/system/dtp-eod-analysis.service >/dev/null <<UNIT
[Unit]
Description=day_trader_pro EOD analysis (reports from S3; no boxes touched)
After=network-online.target

[Service]
Type=oneshot
User=ubuntu
WorkingDirectory=$REPO
ExecStart=$PY $REPO/eod_analysis.py
StandardOutput=append:$REPO/logs/eod_analysis.log
StandardError=append:$REPO/logs/eod_analysis.log
TimeoutStartSec=3600
UNIT

sudo tee /etc/systemd/system/dtp-eod-analysis.timer >/dev/null <<UNIT
[Unit]
Description=Run the EOD analysis at 16:30 ET, Mon-Fri

[Timer]
OnCalendar=Mon-Fri 16:30:00 America/New_York
Persistent=false

[Install]
WantedBy=timers.target
UNIT

# ── 3. retire what the new chain replaces ───────────────────────────────────
# harvest: the conductor drains to S3 and the reports read S3, so pulling a
#          second copy to control has no consumer left.
# eod:     P&L came from here AND from eod_summary on each box — two answers to
#          one question. pnl_s3 is now the single source.
sudo systemctl disable --now dtp-harvest.timer 2>/dev/null || true
sudo systemctl disable --now dtp-eod.timer 2>/dev/null || true

# ⚠️ THE ANALYSIS TIMER IS DISABLED, NOT DELETED. The unit stays on disk so
# devtools item 56 and a manual re-run still work, and so --rollback can re-arm
# it without reinstalling anything.
sudo systemctl disable --now dtp-eod-analysis.timer 2>/dev/null || true

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
