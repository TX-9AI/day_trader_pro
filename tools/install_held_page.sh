#!/usr/bin/env bash
# day_trader_pro/tools/install_held_page.sh — v1.0
# v1.0 (2026-11-22) — dtp r573 / HELD.1. Installs the 15:35 ET held-contracts page (tools/held_contracts_page.py,
#   dtp-held-page.timer Mon-Fri 15:35 America/New_York, not Persistent: a missed 15:35 is not re-run after the close).
#   NOT RUN BY THE LAND: the operator installs control units.
#   Run once on control:  sudo bash /home/ubuntu/day_trader_pro/tools/install_held_page.sh
#   Undo:                 sudo systemctl disable --now dtp-held-page.timer
set -euo pipefail
SRC="$(dirname "$(readlink -f "$0")")"
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
for u in dtp-held-page.service dtp-held-page.timer; do
  install -m 0644 "$SRC/$u" "/etc/systemd/system/$u"
done
systemd-analyze verify /etc/systemd/system/dtp-held-page.service
systemctl daemon-reload
systemctl enable --now dtp-held-page.timer
systemctl list-timers dtp-held-page.timer --no-pager
