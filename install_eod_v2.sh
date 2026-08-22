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
#   16:05  dtp-eod-conductor  -> eod_conductor_v2.py   (was eod_conductor.py)
#   16:30  dtp-eod-analysis   -> eod_analysis.py       (NEW; reports from S3)
#   15:55  dtp-harvest        -> DISABLED   (the conductor drains to S3 itself)
#   16:15  dtp-eod            -> DISABLED   (P&L now comes from the warehouse)
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
  sudo systemctl disable --now dtp-eod-analysis.timer 2>/dev/null || true
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
# ⚠️ THE GAP IS THE POINT. The conductor has the boxes down by ~16:08; starting
# reports at 16:30 means a slow close can never collide with them and a slow
# report can never delay a close.
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

mkdir -p "$REPO/logs"
sudo systemctl daemon-reload
sudo systemctl enable --now dtp-eod-analysis.timer

echo
echo "=============================================================="
echo "  EOD CHAIN AFTER SWITCHOVER"
echo "=============================================================="
systemctl list-timers 'dtp-*' --all --no-pager
echo
echo "  16:05  conductor v2 — stop trading, drain, verify, take down per box"
echo "  16:30  analysis     — P&L + reports, read from S3, boxes stay off"
echo "  15:55  harvest      — DISABLED (conductor drains to S3 itself)"
echo "  16:15  eod_report   — DISABLED (P&L comes from the warehouse)"
echo
echo "  undo:  bash install_eod_v2.sh --rollback"
