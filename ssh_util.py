# day_trader_pro/ssh_util.py — v0.2.0
"""
Shared SSH helper. One place for the exact ssh invocation so eod_report and
fleet behave identically (same key, user, timeouts, host-key policy).

Keyed, non-interactive (BatchMode), auto-trusts new hosts on first contact.
Returns (returncode, stdout, stderr); never raises.

Changelog:
  v0.2.0 (2026-07-10) — add scp_pull() to DOWNLOAD a file from a box to the
    control server (trades.db / OHLC pulls driven by fleet.py pull + devtools).
    Same key/user/host-key policy as ssh_run. Remote paths are relative to the
    box's home dir (no leading ~/), so they resolve under SFTP-mode scp too.
  v0.1.0 — ssh_run only.
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


def scp_pull(ip, remote_path, local_path, timeout=None):
    """Download remote_path from the box to local_path on the control server.
    remote_path should be relative to the box's home dir (e.g.
    'options-trader/trades.db') so it resolves the same under both legacy and
    SFTP-mode scp. Returns (rc, stdout, stderr); never raises. Files transfer
    can take longer than a command, so the timeout budget is more generous.
    """
    timeout = timeout or config.SSH_CONNECT_TIMEOUT
    cmd = [
        "scp", "-i", config.SSH_KEY_PATH,
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", f"ConnectTimeout={config.SSH_CONNECT_TIMEOUT}",
        f"{config.SSH_USER}@{ip}:{remote_path}", local_path,
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout + 60)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 255, "", "scp timeout"
    except Exception as exc:  # noqa: BLE001
        return 255, "", f"scp error: {exc}"
