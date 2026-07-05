# day_trader_pro/ssh_util.py — v0.1.0
"""
Shared SSH helper. One place for the exact ssh invocation so eod_report and
fleet behave identically (same key, user, timeouts, host-key policy).

Keyed, non-interactive (BatchMode), auto-trusts new hosts on first contact.
Returns (returncode, stdout, stderr); never raises.
"""

import subprocess

import config


def ssh_run(ip, command, timeout=None):
    timeout = timeout or config.SSH_CONNECT_TIMEOUT
    cmd = [
        "ssh", "-i", config.SSH_KEY_PATH,
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", f"ConnectTimeout={config.SSH_CONNECT_TIMEOUT}",
        f"{config.SSH_USER}@{ip}", command,
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout + 10)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 255, "", "ssh timeout"
    except Exception as exc:  # noqa: BLE001
        return 255, "", f"ssh error: {exc}"
