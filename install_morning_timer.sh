#!/usr/bin/env bash
# day_trader_pro/install_morning_timer.sh — v1.0
# Installs the control-server MORNING spool-up timer, timezone-aware
# (America/New_York) so it holds ET wall-clock even though this box runs UTC:
#   dtp-morning.timer  09:15 ET  -> orchestrator.py  (wake SPX + QQQ baseline)
#
# This is the timer that was MISSING — the reason nothing spooled up after the
# 09:15 brief all week. orchestrator.py v0.2.0 wakes only SPX+QQQ (discretionary
# selection retired), so it no longer depends on report.json.
#
# Idempotent: re-running overwrites the unit cleanly.
# Run once on the control server:   sudo bash install_morning_timer.sh
#
# NOTE: the orchestrator still no-ops unless control is ENABLED
#       (python control_state.py enable) and it's a trading day.
set -euo pipefail

DIR=/home/ubuntu/day_trader_pro
PY=$DIR/venv/bin/python

sudo tee /etc/systemd/system/dtp-morning.service >/dev/null <<UNIT
[Unit]
Description=day_trader_pro morning spool-up (wake SPX + QQQ baseline)
After=network-online.target

[Service]
Type=oneshot
User=ubuntu
WorkingDirectory=$DIR
EnvironmentFile=$DIR/.env
ExecStart=$PY $DIR/orchestrator.py
UNIT

sudo tee /etc/systemd/system/dtp-morning.timer >/dev/null <<UNIT
[Unit]
Description=day_trader_pro morning spool-up timer (09:15 ET, weekdays)

[Timer]
OnCalendar=Mon-Fri 09:15:00 America/New_York
Persistent=false

[Install]
WantedBy=timers.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --now dtp-morning.timer

echo
echo "Installed. Next scheduled run:"
systemctl list-timers dtp-morning.timer --no-pager | head -3
echo
echo "Reminder: orchestrator no-ops unless control is ENABLED —"
echo "  check:  python control_state.py status"
echo "  enable: python control_state.py enable"
