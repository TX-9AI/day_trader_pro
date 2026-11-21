#!/usr/bin/env bash
# day_trader_pro/tools/install_daily_recap.sh — v1.0
# v1.0 (2026-11-21) — dtp r569 / RECAP.1. Installs the daily recap timer (Mon-Fri 17:00 ET, Persistent) and, once,
#   the daily brief's own venv OUTSIDE the repo (/home/ubuntu/venvs/daily_brief, from daily_brief.requirements.txt,
#   owned by ubuntu). Copies the 2026-11-20 model notes into ~/reviews/daily_brief/notes/ when they are not there.
#   NOT RUN BY THE LAND: the operator installs control units.
#   Run once on control:  sudo bash /home/ubuntu/day_trader_pro/tools/install_daily_recap.sh
#   Undo:  sudo systemctl disable --now dtp-daily-recap.timer
set -euo pipefail
SRC="$(dirname "$(readlink -f "$0")")"
VENV=/home/ubuntu/venvs/daily_brief
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
if [ ! -x "$VENV/bin/python" ]; then
  sudo -u ubuntu mkdir -p /home/ubuntu/venvs
  sudo -u ubuntu python3 -m venv "$VENV"
  sudo -u ubuntu "$VENV/bin/pip" install --quiet -r "$SRC/daily_brief.requirements.txt"
fi
sudo -u ubuntu "$VENV/bin/python" -I -c "import matplotlib, reportlab, boto3, pypdfium2; print('daily_brief venv ok')"
sudo -u ubuntu mkdir -p /home/ubuntu/reviews/daily_brief/notes
_m=/home/ubuntu/otv5_builds/daily_brief/notes/2026-11-20.json
[ -f /home/ubuntu/reviews/daily_brief/notes/2026-11-20.json ] || { [ -f "$_m" ] && sudo -u ubuntu cp -p "$_m" /home/ubuntu/reviews/daily_brief/notes/; } || true
for u in dtp-daily-recap.service dtp-daily-recap.timer; do
  install -m 0644 "$SRC/$u" "/etc/systemd/system/$u"
done
systemd-analyze verify /etc/systemd/system/dtp-daily-recap.service
systemctl daemon-reload
systemctl enable --now dtp-daily-recap.timer
systemctl list-timers dtp-daily-recap.timer --no-pager
