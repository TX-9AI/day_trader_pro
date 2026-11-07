#!/usr/bin/env bash
# day_trader_pro/tools/install_nightly_review.sh — v1.0
# v1.0 (2026-11-07) — dtp r524 / RPT.36. Installs the nightly-review timer (16:40 ET, 13:40 ET on a half day,
#   Persistent) and its 18:30 ET missing-review check. NOT RUN BY THE LAND: the operator installs control units.
#   Run once on control:  sudo bash /home/ubuntu/day_trader_pro/tools/install_nightly_review.sh
#   Undo:  sudo systemctl disable --now dtp-nightly-review.timer dtp-nightly-review-check.timer
set -euo pipefail
SRC="$(dirname "$(readlink -f "$0")")"
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
for u in dtp-nightly-review.service dtp-nightly-review.timer dtp-nightly-review-check.service dtp-nightly-review-check.timer; do
  install -m 0644 "$SRC/$u" "/etc/systemd/system/$u"
done
systemd-analyze verify /etc/systemd/system/dtp-nightly-review.service /etc/systemd/system/dtp-nightly-review-check.service
systemctl daemon-reload
systemctl enable --now dtp-nightly-review.timer dtp-nightly-review-check.timer
systemctl list-timers dtp-nightly-review.timer dtp-nightly-review-check.timer --no-pager
