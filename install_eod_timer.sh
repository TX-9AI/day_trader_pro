#!/usr/bin/env bash
# day_trader_pro/install_eod_timer.sh — v1.2
# Installs the control-server EOD timers, timezone-aware (America/New_York) so
# they hold their ET wall-clock time even though this box runs on UTC:
#   dtp-harvest.timer  15:55 ET  -> harvest.py    (pull full trade detail)
#   dtp-eod.timer      16:15 ET  -> eod_report.py (pull P&L, stop fleet, message)
#
# Run once on the control server:   sudo bash install_eod_timer.sh
#
# v1.2 — 2026-07-10 — EOD sweep moved 16:00 -> 16:15 ET so the 16:05 per-box
#        candle-logger has a full window to write its forensic 1-min OHLC CSVs
#        before the fleet is stopped. Control-side only; bots are unchanged.
#        (15:55 harvest timer unchanged — it stops nothing.)
set -euo pipefail

DIR=/home/ubuntu/day_trader_pro
PY=$DIR/venv/bin/python

# --- 15:55 harvest -------------------------------------------------------
sudo tee /etc/systemd/system/dtp-harvest.service >/dev/null <<UNIT
[Unit]
Description=day_trader_pro trade harvest (pull full trade detail from fleet)
After=network-online.target

[Service]
Type=oneshot
User=ubuntu
WorkingDirectory=$DIR
EnvironmentFile=$DIR/.env
ExecStart=$PY $DIR/harvest.py
UNIT

sudo tee /etc/systemd/system/dtp-harvest.timer >/dev/null <<UNIT
[Unit]
Description=day_trader_pro trade harvest timer (15:55 ET, weekdays)

[Timer]
OnCalendar=Mon-Fri 15:55:00 America/New_York
Persistent=false

[Install]
WantedBy=timers.target
UNIT

# --- 16:00 sweep ---------------------------------------------------------
sudo tee /etc/systemd/system/dtp-eod.service >/dev/null <<UNIT
[Unit]
Description=day_trader_pro EOD sweep (pull P&L, stop fleet, unified message)
After=network-online.target

[Service]
Type=oneshot
User=ubuntu
WorkingDirectory=$DIR
EnvironmentFile=$DIR/.env
ExecStart=$PY $DIR/eod_report.py
UNIT

sudo tee /etc/systemd/system/dtp-eod.timer >/dev/null <<UNIT
[Unit]
Description=day_trader_pro EOD sweep timer (16:15 ET, weekdays)

[Timer]
OnCalendar=Mon-Fri 16:15:00 America/New_York
Persistent=false

[Install]
WantedBy=timers.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --now dtp-harvest.timer dtp-eod.timer

echo
echo "Installed. Next scheduled runs:"
systemctl list-timers dtp-harvest.timer dtp-eod.timer --no-pager | head -4
