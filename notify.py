# day_trader_pro/notify.py — v0.3.0
"""
Telegram notifier for the control server (orchestrator alerts + EOD summary).
Separate from the trading boxes' own Telegram alerts.

Reads token/chat from the environment (never hardcode):
    DTP_TELEGRAM_TOKEN
    DTP_TELEGRAM_CHAT_ID

v0.3.0 — TEST-MODE GUARD: a test can no longer page the operator. Detected
from sys.modules/argv, or forced with DTP_NOTIFY_CAPTURE=1; messages are
CAPTURED so a test can assert on them. See the block above send().

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


# ── 🔴 TEST-MODE GUARD (v0.3.0, 2026-08-25) ─────────────────────────────────
# A TEST MUST NEVER BE ABLE TO PAGE THE OPERATOR. On 2026-08-25 they received
# "EOD conductor [RECOVER] 2026-08-18: 2 pull(s) FAILED" on EVERY COMMIT for
# days. The cause: tests/test_conductor_recovery.py drives the partial-failure
# branch ON PURPOSE, that branch sends, and the test stubbed `harvest` but not
# `notify`. It runs in every deploy gate. The dates in the alert were nothing
# but the test's own fixture literals.
#
# ⚠️ FIXING THE ONE TEST WAS NOT ENOUGH. The next test that exercises an alert
# branch reintroduces it, and it fails SILENTLY-IN-REVERSE: the alert looks
# real, so the operator investigates data that was never wrong. The guard makes
# the whole class impossible instead of the instance.
#
# ⚠️ AND IT TRAINS THE CHANNEL TO BE IGNORED, which is the actual damage. The
# standing rule is that Telegram is an EMERGENCY channel: routine traffic there
# teaches the operator to skip it, and then it fails the one time it matters.
#
# ⚠️ DETECTED, NOT DECLARED. Relying on each test to remember `notify.send = ...`
# is exactly what failed. `pytest`/`unittest` in sys.modules, or a filename
# under tests/, is enough — plus DTP_NOTIFY_CAPTURE=1 for anything that runs
# outside those (a menu smoke test, a manual harness).
_CAPTURED: list = []


def _in_test() -> bool:
    if os.environ.get("DTP_NOTIFY_CAPTURE") == "1":
        return True
    if "pytest" in sys.modules or "unittest" in sys.modules:
        return True
    # A plain-script test (this repo's own convention) has no pytest import.
    arg0 = (sys.argv[0] or "")
    return "/tests/" in arg0 or os.path.basename(arg0).startswith(("test_", "check_"))


def captured() -> list:
    """What WOULD have been sent. Lets a test assert on the message."""
    return list(_CAPTURED)


def send(text, silent=False):
    """Send a Telegram message as plain text. Returns True on success (or mock)."""
    body = _plain(text)

    # ⚠️ RECORDED, NOT DISCARDED — capturing is strictly stronger than
    # silencing, because a test can then assert the alert was COMPOSED.
    if _in_test():
        _CAPTURED.append(body)
        print(f"[notify] CAPTURED (test mode, not sent): {body[:90]}",
              file=sys.stderr)
        return True

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
