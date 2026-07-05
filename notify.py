# day_trader_pro/notify.py — v0.1.0
"""
Telegram notifier for the control server (orchestrator alerts + shutdown
sweep summary). This is SEPARATE from the trading boxes' own Telegram alerts;
the per-symbol daily P&L still comes from each box.

Reads token/chat from the environment (never hardcode):
    DTP_TELEGRAM_TOKEN
    DTP_TELEGRAM_CHAT_ID

In mock mode, messages print to stdout instead of hitting the API.

CLI:
    python notify.py --test
"""

import os
import sys

import config


def send(text, silent=False):
    """Send a Telegram message. Returns True on success (or mock)."""
    if config.MOCK_TELEGRAM:
        print("----- [MOCK TELEGRAM] -----")
        print(text)
        print("---------------------------")
        return True

    import requests

    token = os.environ.get(config.ENV_TELEGRAM_TOKEN)
    chat_id = os.environ.get(config.ENV_TELEGRAM_CHAT)
    if not token or not chat_id:
        print(f"[notify] missing {config.ENV_TELEGRAM_TOKEN}/"
              f"{config.ENV_TELEGRAM_CHAT}; cannot send.", file=sys.stderr)
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_notification": silent,
        }, timeout=15)
        ok = r.ok and r.json().get("ok", False)
        if not ok:
            print(f"[notify] telegram error: {r.status_code} {r.text}",
                  file=sys.stderr)
        return ok
    except Exception as exc:  # noqa: BLE001
        print(f"[notify] telegram exception: {exc}", file=sys.stderr)
        return False


def main(argv):
    if "--test" in argv:
        ok = send("*day_trader_pro* notify test ✅")
        print("sent" if ok else "failed")
        return 0 if ok else 1
    print("Usage: python notify.py --test")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
