#!/usr/bin/env bash
# day_trader_pro/tools/install_dxlink_assign.sh — v1.0
# v1.0 (2026-11-07) — dtp r525 / FEED.15b. Installs the dxlink node assignment (09:16 ET weekdays, after the 09:15
#   wake; the service writes each box's ~/options-trader/data/dxlink_assign.json as it comes up, until 09:25 ET).
#   NOT RUN BY THE LAND: the operator installs control units.
#   Run once on control:  sudo bash /home/ubuntu/day_trader_pro/tools/install_dxlink_assign.sh
#   Undo:  sudo systemctl disable --now dtp-dxlink-assign.timer
set -euo pipefail
SRC="$(dirname "$(readlink -f "$0")")"
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
for u in dtp-dxlink-assign.service dtp-dxlink-assign.timer; do
  install -m 0644 "$SRC/$u" "/etc/systemd/system/$u"
done
systemd-analyze verify /etc/systemd/system/dtp-dxlink-assign.service
systemctl daemon-reload
systemctl enable --now dtp-dxlink-assign.timer
systemctl list-timers dtp-dxlink-assign.timer --no-pager
