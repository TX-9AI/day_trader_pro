# day_trader_pro/ssh_util.py — v0.3.0
"""
Shared SSH helper. One place for the exact ssh invocation so eod_report and
fleet behave identically (same key, user, timeouts, host-key policy).

Keyed, non-interactive (BatchMode), auto-trusts new hosts on first contact.
Returns (returncode, stdout, stderr); never raises.

Changelog:
  v0.3.0 (2026-08-28) — DECODE REMOTE OUTPUT AS UTF-8, WITH errors="replace".
    `text=True` alone uses the CONTROL SERVER'S LOCALE, and the boxes print
    box-drawing rules (`═` is U+2550, THREE bytes). When the ssh stream chunks
    mid-character the decoder loses sync: on 2026-08-28 a 62-character rule in
    query.py came back as ~186 QUESTION MARKS — one per byte, 62 x 3 = 186 —
    in two panels while fifteen other rules on the same page were clean. That
    byte count is what identified the cause; it was not a width bug in sep().
    `errors="replace"` matters as much as the encoding: the default is STRICT,
    which raises UnicodeDecodeError and would lose the ENTIRE box's output over
    one broken character. A garbled rule is cosmetic; a swallowed report is
    not. Both call sites (ssh_run and scp_pull) are covered. Pinned by
    tests/check_ssh_decode.py (S1 mutation-proven).

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
        # 🔴 DECODE AS UTF-8 EXPLICITLY, AND NEVER RAISE ON A SPLIT CHARACTER.
        # ⚠️ `text=True` with no encoding uses the CONTROL SERVER'S LOCALE. The
        # boxes print box-drawing rules (`═` is U+2550, THREE bytes in UTF-8),
        # and when the ssh stream chunks mid-character the decoder loses sync —
        # `query.py` output on 2026-08-28 showed a 62-char rule rendered as
        # ~186 QUESTION MARKS, one per BYTE, in two panels while the other
        # fifteen came through clean.
        # ⚠️ `errors="replace"` matters as much as the encoding: the default is
        # STRICT, which raises UnicodeDecodeError and would lose the ENTIRE
        # box's output over one broken character. A garbled rule is a cosmetic
        # problem; a swallowed report is not.
        p = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
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
        # Same explicit decode as ssh_run above — a scp progress line can carry
        # non-ASCII too, and a strict decoder would lose the whole result.
        p = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           timeout=timeout + 60)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 255, "", "scp timeout"
    except Exception as exc:  # noqa: BLE001
        return 255, "", f"scp error: {exc}"
