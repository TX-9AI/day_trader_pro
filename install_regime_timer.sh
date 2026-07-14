#!/usr/bin/env bash
# day_trader_pro/install_regime_timer.sh — v1.1
# v1.1 — 2026-07-14 — renamed units to the house dtp- convention and slotted
#        into the existing control-server schedule (see below); v1.0's 16:40
#        generic naming superseded before deployment.
# v1.0 — 2026-07-14 — initial.
#
# Installs the LAST link of the nightly pipeline. Control-server schedule:
#   dtp-morning.timer  09:15 ET -> orchestrator.py  (wake baseline fleet)
#   dtp-harvest.timer  15:55 ET -> harvest.py       (pull tape + trades from fleet)
#   dtp-eod.timer      16:15 ET -> eod_report.py    (P&L rollup, STOP fleet)
#   dtp-regime.timer   16:30 ET -> nightly_regime.sh (replay + diary, LOCAL files
#                                   only — never touches a box)  << THIS INSTALLER
# Idempotent — safe to re-run.  Usage:  bash install_regime_timer.sh
set -euo pipefail
DIR="$HOME/day_trader_pro"
[ -f "$DIR/nightly_regime.sh" ] || { echo "put nightly_regime.sh in $DIR first"; exit 1; }
chmod +x "$DIR/nightly_regime.sh" 2>/dev/null || true
chmod +x "$HOME/validate_regime.sh" 2>/dev/null || true

sudo tee /etc/systemd/system/dtp-regime.service >/dev/null <<UNIT
[Unit]
Description=day_trader_pro regime replay + diary (L1+L2 pipeline, local harvest files)
After=network-online.target

[Service]
Type=oneshot
User=$USER
Environment=HOME=$HOME
ExecStart=/usr/bin/env bash $DIR/nightly_regime.sh
TimeoutStartSec=3600
UNIT

sudo tee /etc/systemd/system/dtp-regime.timer >/dev/null <<UNIT
[Unit]
Description=day_trader_pro regime pipeline timer (16:30 ET, weekdays; after dtp-harvest)

[Timer]
OnCalendar=Mon-Fri 16:30:00 America/New_York
Persistent=true
RandomizedDelaySec=60

[Install]
WantedBy=timers.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --now dtp-regime.timer
echo "── installed ──"
systemctl list-timers 'dtp-*' --no-pager | head -6
echo "test now:  sudo systemctl start dtp-regime.service && journalctl -u dtp-regime -f"
