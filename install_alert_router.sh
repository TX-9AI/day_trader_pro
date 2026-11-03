#!/usr/bin/env bash
# day_trader_pro/install_alert_router.sh — v1.0
# v1.0 (2026-11-02) — dtp r522 / PAGE.2. Installs control's alert router (alert_router.py run) as ONE always-on
#   service: it follows every running box's bot.log over ssh (pager.py v0.2.0, ack mode) and delivers the fleet's
#   alerts as one paced, grouped Telegram queue with control's pair from .env (DTP_TELEGRAM_TOKEN /
#   DTP_TELEGRAM_CHAT_ID; presence is checked, values are never printed).
#
# ⚠️ NOTHING ON A BOX CHANGES UNTIL OTV5 r71 IS ON IT. A box running r70 or older never writes `[alert]` lines and
#   never reads the ack file, so the service is inert for it (it still writes ~/.optbot/control_ack there, which
#   nothing reads).
# ⚠️ STOPPING THE SERVICE IS SAFE BY DESIGN: the heartbeat stops, each box's ack file goes stale in 45 s and every
#   box sends its own alerts again (its routed alerts not acked in 30 s are sent from the box too).
# ⚠️ ONE ROUTER: a second `alert_router.py run` exits 3 on data/alert_router/router.lock. A terminal `pager.py`
#   beside it is harmless (plain mode never writes the ack file).
#
# Run:  bash install_alert_router.sh          (needs sudo; not run by the build)
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$DIR/venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"

if [ -f "$DIR/.env" ]; then
  for V in DTP_TELEGRAM_TOKEN DTP_TELEGRAM_CHAT_ID; do
    if grep -q "^$V=" "$DIR/.env"; then echo "   ✅ $V present in .env"
    else echo "   ❌ $V MISSING from $DIR/.env — the router refuses to run without it"; exit 1; fi
  done
else
  echo "   ❌ $DIR/.env does not exist — the router has no Telegram pair"; exit 1
fi

sudo tee /etc/systemd/system/dtp-alert-router.service >/dev/null <<UNIT
[Unit]
Description=day_trader_pro alert router (fleet alerts -> one paced, grouped Telegram queue; dtp r522 PAGE.2)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$DIR
EnvironmentFile=$DIR/.env
ExecStart=$PY $DIR/alert_router.py run
Restart=always
RestartSec=5
# SIGTERM: the pager's ssh children are killed, the queue gets 5 s, health.json is written
TimeoutStopSec=20

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --now dtp-alert-router.service
echo
systemctl --no-pager --lines=0 status dtp-alert-router.service | sed -n '1,3p'
echo
echo "Health:        $PY $DIR/alert_router.py status"
echo "Post a status: $PY $DIR/alert_router.py post --kind working --boxes AMD --cause BARS_STALE \"restarting the feed\""
echo "Watch only:    $PY $DIR/alert_router.py run --dry-run   (with the service stopped; never acks a box)"
