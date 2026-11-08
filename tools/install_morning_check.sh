#!/usr/bin/env bash
# day_trader_pro/tools/install_morning_check.sh — v1.0
# v1.0 (2026-11-08) — dtp r539 / TIMER.1. Installs the morning check (09:19 wake verify, 09:50 Hunt shadow rule,
#   11:10 PARK shadow rule; tools/morning_check.py) and REMOVES the control units the consolidation retires:
#   dtp-feed-triage (a per-minute poll; the operator 2026-11-08: "It should be reactionary, by event type"),
#   dtp-regime (its nightly_regime.sh no longer exists) and dtp-eod-analysis (the 16:05 conductor runs
#   eod_analysis itself). Each retired unit is stopped, disabled and its files deleted; a missing one is skipped.
#   Run once on control:  sudo bash /home/ubuntu/day_trader_pro/tools/install_morning_check.sh
#   Undo the install:     sudo systemctl disable --now dtp-morning-check.timer
set -euo pipefail
SRC="$(dirname "$(readlink -f "$0")")"
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
for u in dtp-feed-triage dtp-regime dtp-eod-analysis; do
  systemctl disable --now "$u.timer" 2>/dev/null || true
  systemctl stop "$u.service" 2>/dev/null || true
  for f in "/etc/systemd/system/$u.timer" "/etc/systemd/system/$u.service"; do
    [ -e "$f" ] && { rm -f -- "$f"; echo "removed $f"; }
  done
done
for u in dtp-morning-check.service dtp-morning-check.timer; do
  install -m 0644 "$SRC/$u" "/etc/systemd/system/$u"
done
systemd-analyze verify /etc/systemd/system/dtp-morning-check.service
systemctl daemon-reload
systemctl reset-failed 2>/dev/null || true
systemctl enable --now dtp-morning-check.timer
systemctl list-timers dtp-morning-check.timer --no-pager
