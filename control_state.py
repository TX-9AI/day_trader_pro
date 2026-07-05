# day_trader_pro/control_state.py — v0.1.0
"""
Master on/off switch for the control server.

ENABLED  -> orchestrator wakes the fleet; EOD sweep pulls P&L and stops boxes.
DISABLED -> both no-op (log and exit). Run bots by hand with zero interference.

State lives in data/control_state.json so it can be toggled from Termius via
devtools without editing code. Missing file defaults to ENABLED (fail-safe
toward normal automated operation, since that's the intended daily mode).

CLI:
    python control_state.py status
    python control_state.py enable
    python control_state.py disable
"""

import json
import os
import sys
from datetime import datetime, timezone

import config


def _load():
    try:
        with open(config.CONTROL_STATE_PATH, "r") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"enabled": True, "changed_at": None}


def _save(state):
    os.makedirs(config.DATA_DIR, exist_ok=True)
    state["changed_at"] = datetime.now(timezone.utc).isoformat()
    with open(config.CONTROL_STATE_PATH, "w") as fh:
        json.dump(state, fh, indent=2)


def is_enabled():
    return bool(_load().get("enabled", True))


def set_enabled(on: bool):
    _save({"enabled": bool(on)})
    return is_enabled()


def status_line():
    s = _load()
    word = "ENABLED" if s.get("enabled", True) else "DISABLED"
    return f"control is {word}  (changed_at={s.get('changed_at')})"


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd == "status":
        print(status_line())
    elif cmd == "enable":
        set_enabled(True)
        print("control ENABLED — orchestrator + EOD sweep will run.")
    elif cmd == "disable":
        set_enabled(False)
        print("control DISABLED — orchestrator + EOD sweep will no-op.")
    else:
        print("Usage: python control_state.py [status|enable|disable]")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
