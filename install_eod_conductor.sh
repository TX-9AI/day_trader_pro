#!/usr/bin/env bash
# day_trader_pro/install_eod_conductor.sh — v1.0
# Installs the SINGLE EOD conductor timer on the control server and PURGES the old
# split timers (dtp-harvest + dtp-eod) so nothing races the conductor. The conductor
# gates internally, so the timer only needs to fire after the bots begin producing —
# its GATE step waits for actual completion.
# Run once on the control server:  sudo bash install_eod_conductor.sh
set -euo pipefail
DIR="$HOME/day_trader_pro"; [ -d "$DIR" ] || DIR="/home/ubuntu/day_trader_pro"
PY="$DIR/venv/bin/python"; [ -x "$PY" ] || PY="$(command -v python3)"
U="$(id -un)"

# --- purge the retired split EOD timers ---------------------------------------
for u in dtp-harvest dtp-eod; do
  sudo systemctl disable --now "${u}.timer" >/dev/null 2>&1 || true
  sudo rm -f "/etc/systemd/system/${u}.timer" "/etc/systemd/system/${u}.service"
done
echo "purged old timers: dtp-harvest, dtp-eod"

sudo tee /etc/systemd/system/dtp-eod-conductor.service >/dev/null <<UNIT
[Unit]
Description=day_trader_pro EOD conductor (gate->harvest->report->backfill->consolidate->regime)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=${U}
WorkingDirectory=${DIR}
ExecStart=${PY} ${DIR}/eod_conductor.py
TimeoutStartSec=3600
UNIT
sudo chmod 644 /etc/systemd/system/dtp-eod-conductor.service

sudo tee /etc/systemd/system/dtp-eod-conductor.timer >/dev/null <<'UNIT'
[Unit]
Description=day_trader_pro EOD conductor timer (Mon-Fri 16:05 ET)

[Timer]
OnCalendar=Mon-Fri 16:05:00 America/New_York
Persistent=false
AccuracySec=30s

[Install]
WantedBy=timers.target
UNIT
sudo chmod 644 /etc/systemd/system/dtp-eod-conductor.timer

sudo systemctl daemon-reload
sudo systemctl enable --now dtp-eod-conductor.timer >/dev/null 2>&1
echo "✅ dtp-eod-conductor.timer installed (16:05 ET)"
systemctl list-timers dtp-eod-conductor.timer --no-pager 2>/dev/null | sed -n '1,2p'
