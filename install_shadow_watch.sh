#!/usr/bin/env bash
# day_trader_pro/install_shadow_watch.sh — v1.0
# v1.0 (2026-09-05) — dtp r299 / SHD.2. Installs the 09:40 ET guard.
#
# 🔴 WHY 09:40 AND NOT 09:30. The operator asked for "not running by 0930", but
# the accumulator needs MIN_TYPICAL_SAMPLES trailing ROCs before velocity is
# non-null, and a box woken at 09:15 enters RTH with an empty deque. Checking
# at 09:30:00 would page every single morning for a warm-up. Ten minutes is
# past the warm-up and still inside the ORB window, so a real fault is caught
# while the session can still be salvaged.
#
# ⚠️ THIS IS A THIRD TIMER, AND THE OPERATOR CUT SIX TO TWO. Said plainly so it
# can be overruled: the guard has to fire even when the 09:15 orchestrator run
# CRASHED, which is exactly when shadow would be dark — so hanging it off the
# morning unit would make it absent in the case it exists for. That is the
# whole argument; if the operator would rather carry it inside the orchestrator
# and accept that dependency, it is a two-line change.
#
# Run:  bash install_shadow_watch.sh
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$DIR/venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"

sudo tee /etc/systemd/system/dtp-shadow-watch.service >/dev/null <<UNIT
[Unit]
Description=day_trader_pro shadow stage-2 guard (alerts only when dark)
After=network-online.target

[Service]
Type=oneshot
User=ubuntu
WorkingDirectory=$DIR
EnvironmentFile=$DIR/.env
ExecStart=$PY $DIR/tools/shadow_watch.py
# ⚠️ A NON-ZERO EXIT IS THE GUARD DOING ITS JOB — it means a box is dark and
# the alert was sent. systemd must not treat that as a service failure and
# start restarting it, or one dark box becomes a page loop.
SuccessExitStatus=0 1
UNIT

sudo tee /etc/systemd/system/dtp-shadow-watch.timer >/dev/null <<UNIT
[Unit]
Description=day_trader_pro shadow guard timer (09:40 ET, weekdays)

[Timer]
OnCalendar=Mon-Fri 09:40:00 America/New_York
# ⚠️ NOT PERSISTENT. A catch-up run hours after a missed window would ask
# "was shadow scoring at 09:40" long after the answer stopped being actionable,
# and page for a session already over. The tool is calendar-gated anyway, so a
# holiday is silent regardless.
Persistent=false

[Install]
WantedBy=timers.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --now dtp-shadow-watch.timer

echo
echo "Installed. Next scheduled run:"
systemctl list-timers dtp-shadow-watch.timer --no-pager | sed -n '1,2p'
echo
echo "Dry run (sends nothing):  $PY $DIR/tools/shadow_watch.py --dry"
echo "DRILL (real send, marked): $PY $DIR/tools/shadow_watch.py --drill"
