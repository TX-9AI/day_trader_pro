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
Description=day_trader_pro EOD conductor (gate->harvest->report->backfill->consolidate)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=${U}
WorkingDirectory=${DIR}
# AX (2026-08-03) — WITHOUT THIS THE CONDUCTOR CANNOT NOTIFY. notify.py reads
# DTP_TELEGRAM_TOKEN / DTP_TELEGRAM_CHAT_ID from the environment, systemd handed
# this unit NOTHING, and every warning it has ever raised went to a journal
# nobody reads — including the 2026-08-03 run's "7 symbol(s) still without
# candles". Same box-vs-control credential split as the blind-alert drill, one
# layer up. dtp-eod-timer and dtp-morning-timer already load this exact file;
# the conductor was the only unit that did not.
EnvironmentFile=${DIR}/.env
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

# AX — say plainly whether the notify path can work, rather than discovering it
# in a journal weeks later. Presence only; no values printed.
if [ -f "$DIR/.env" ]; then
  for V in DTP_TELEGRAM_TOKEN DTP_TELEGRAM_CHAT_ID; do
    if grep -q "^$V=" "$DIR/.env"; then echo "   ✅ $V present in .env"
    else echo "   ⚠️  $V MISSING from $DIR/.env — the conductor still cannot notify"; fi
  done
else
  echo "   ⚠️  $DIR/.env does not exist — the unit will fail to start"
fi
systemctl list-timers dtp-eod-conductor.timer --no-pager 2>/dev/null | sed -n '1,2p'
