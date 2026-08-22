#!/usr/bin/env bash
# day_trader_pro/install_eod_analysis.sh — v1.0
# v1.0 (2026-08-25) — the REPORTS timer. Runs at 16:30, after the conductor has
# already verified and stopped the fleet.
#
# 🔴 16:30 IS DELIBERATE AND IT IS LATE ON PURPOSE. The conductor starts at
# 16:05 and has the boxes down by ~16:08. Twenty minutes of margin means a slow
# close can never collide with the reports, and the reports can never delay a
# close — which is the entire reason the two were split.
#
# ⚠️ NOTHING HERE WAKES A BOX. Every read is S3 or control-side, so this unit
# is safe to re-run, safe to run late, and safe to run on a day the fleet never
# came up at all.
#
# ⚠️ IT MUST NOT MARK FAILED ON A WARNED NIGHT. eod_analysis exits 0 even with
# warnings, because systemd shows a unit as failed on any non-zero rc and the
# old conductor spent weeks displaying `failed` on healthy runs.
set -euo pipefail

REPO="$HOME/day_trader_pro"
PY="$REPO/venv/bin/python"

sudo tee /etc/systemd/system/dtp-eod-analysis.service >/dev/null <<UNIT
[Unit]
Description=day_trader_pro EOD analysis (reports from S3; no boxes touched)
After=network-online.target

[Service]
Type=oneshot
User=ubuntu
WorkingDirectory=$REPO
ExecStart=$PY $REPO/eod_analysis.py
StandardOutput=append:$REPO/logs/eod_analysis.log
StandardError=append:$REPO/logs/eod_analysis.log
UNIT

sudo tee /etc/systemd/system/dtp-eod-analysis.timer >/dev/null <<UNIT
[Unit]
Description=Run the EOD analysis at 16:30 ET, Mon-Fri

[Timer]
OnCalendar=Mon-Fri 16:30:00 America/New_York
Persistent=false

[Install]
WantedBy=timers.target
UNIT

mkdir -p "$REPO/logs"
sudo systemctl daemon-reload
sudo systemctl enable --now dtp-eod-analysis.timer
echo "installed. next run:"
systemctl list-timers dtp-eod-analysis.timer --no-pager | head -3
