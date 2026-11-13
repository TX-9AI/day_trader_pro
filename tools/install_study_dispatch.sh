#!/usr/bin/env bash
# day_trader_pro/tools/install_study_dispatch.sh — v1.0
# v1.0 (2026-11-13) — dtp r552 / SAT.9. Installs the Friday-night study queue timer (Fri 17:15 ET, not Persistent).
#   NOT RUN BY THE LAND: the operator installs control units.
#   Run once on control:  sudo bash /home/ubuntu/day_trader_pro/tools/install_study_dispatch.sh
#   Undo:  sudo systemctl disable --now dtp-study-dispatch.timer
set -euo pipefail
SRC="$(dirname "$(readlink -f "$0")")"
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
for u in dtp-study-dispatch.service dtp-study-dispatch.timer; do
  install -m 0644 "$SRC/$u" "/etc/systemd/system/$u"
done
systemd-analyze verify /etc/systemd/system/dtp-study-dispatch.service
systemctl daemon-reload
systemctl enable --now dtp-study-dispatch.timer
systemctl list-timers dtp-study-dispatch.timer --no-pager
