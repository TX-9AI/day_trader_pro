# day_trader_pro/notify.py — v0.2.0
"""
Telegram notifier for the control server (orchestrator alerts + EOD summary).
Separate from the trading boxes' own Telegram alerts.

Reads token/chat from the environment (never hardcode):
    DTP_TELEGRAM_TOKEN
    DTP_TELEGRAM_CHAT_ID

v0.2.0 — send as PLAIN TEXT (no parse_mode). Machine-generated P&L text is
full of characters (- . _ + | negative numbers) that Telegram's Markdown
parser rejects mid-message ("can't parse entities"), which would silently
drop a wake/EOD confirmation. Plain text can never fail to render. Our message
builders use *bold* / `code` markers for readability; we strip those markers
here so plain output stays clean instead of showing literal * and `.

In mock mode, messages print to stdout.

CLI:
    python notify.py --test
"""

import os
import re
import sys

import config

# Strip the emphasis markers our builders use (*bold*, `code`, _italic_)
# so the plain-text message reads cleanly. Underscores inside words/IDs are
# left alone; only paired _italic_ wrappers around parentheticals are removed.
_STRIP = re.compile(r"[*`]")
_ITALIC = re.compile(r"_(\([^)]*\))_")


def _plain(text: str) -> str:
    text = _ITALIC.sub(r"\1", text)
    return _STRIP.sub("", text)


def send(text, silent=False):
    """Send a Telegram message as plain text. Returns True on success (or mock)."""
    body = _plain(text)

    if config.MOCK_TELEGRAM:
        print("----- [MOCK TELEGRAM] -----")
        print(body)
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
        # No parse_mode: Telegram treats the body literally and never raises
        # an entity-parse error regardless of P&L content.
        r = requests.post(url, json={
            "chat_id": chat_id,
            "text": body,
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
        ok = send("*day_trader_pro* notify test ✅ (plain-text mode)")
        print("sent" if ok else "failed")
        return 0 if ok else 1
    print("Usage: python notify.py --test")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
