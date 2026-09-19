# day_trader_pro/ssh_util.py — v0.5.0
"""
Shared SSH helper. One place for the exact ssh invocation so eod_report and
fleet behave identically (same key, user, timeouts, host-key policy).

Keyed, non-interactive (BatchMode), auto-trusts new hosts on first contact.
Returns (returncode, stdout, stderr); never raises.

Changelog:
  v0.5.0 (2026-09-19) — FU.2. ADD ssh_map(): THE SAME WORK, CONCURRENTLY.
    🔴 THE FLEET FAN-OUT HAS ALWAYS BEEN SERIAL. Nothing in this module or in
    fleet.py has ever used a thread pool, so every fleet command walks fifteen
    boxes one at a time — which is why a `find / -xdev` sweep costs ~7 minutes
    rather than ~28 seconds.
    📊 AND IT IS WHAT MAKES THE EOD PURGE MISS MOST OF THE FLEET. The conductor
    caps the whole phase at PURGE_BUDGET_S (600s, CND.2) and spends it SERIALLY,
    so measured over the last seven closes it reached 7 → 7 → 3 → 2 → 2 → 3 → 4
    boxes of fifteen. A full rotation takes 4–5 nights, which makes the 5-day
    `1m` retention policy arithmetically unreachable — PLTR and QQQ were both
    +14 days beyond policy on 2026-09-19 and PLTR sat at 93% disk with 661M
    free, past the DEV.7 guard, which fired for real.
    🔑 THE WORK IS PER-BOX, INDEPENDENT AND EXECUTED ON THE BOX. Control is
    only holding an ssh session and waiting. So the SAME budget spent
    concurrently covers all fifteen: the phase cost falls from SUM(per-box) to
    MAX(per-box).
    ⚠️ CND.2's PROTECTION GETS STRONGER, NOT WEAKER. That budget exists because
    the purge starved the halt and left the fleet up all night; bounding by MAX
    rather than SUM is a tighter bound, not a looser one. And C8's rule is
    untouched — every box still gets its FULL timeout, never a shrinking slice,
    which is the exact mistake check_conductor_purge C8 refused once already.
    ⚠️ IT REUSES ssh_run RATHER THAN REIMPLEMENTING IT (WA 7). The explicit
    UTF-8 decode and errors="replace" are not duplicated here; a second copy of
    that would be a second place for the 2026-08-28 mojibake to come back.
    ⚠️ RESULTS ARE RETURNED AS A DICT, NEVER A COMPLETION-ORDERED LIST, so a
    caller's report reads in ITS order and parallelism cannot scramble output.
  v0.4.0 (2026-09-13) — dtp r379 / LVL.17. ADD scp_push() TO UPLOAD A FILE TO A
    BOX. The module had a PULL and no PUSH for two months because everything
    control needed was a download — the harvest, the report, the ledger book.
    The delivered level history reverses the direction: control BUILDS the
    defense record from banked tape and the box READS it. The operator's framing
    is why it must be a push and not a fetch — *"I'm not saying the bots would
    'pull' from s3. I'm saying we could construct their ledgers from that
    data."* A trading box never reaches the warehouse, so WORKING_AGREEMENT 30
    still holds: the bot owns its own book, control is the source of the history
    and nothing else.
    ⚠️ Same key, user, host-key policy and explicit UTF-8 decode as the other
    two call sites, so v0.3.0's fix covers this one by construction rather than
    by a second implementation.
    ⚠️ scp WILL NOT CREATE THE REMOTE DIRECTORY and the failure is a terse "No
    such file or directory" — the caller mkdirs first. Said here because the
    next caller will hit it.

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

import concurrent.futures as _fut
import subprocess

import config

# ⚠️ CAPPED FOR THE CONTROL BOX, NOT FOR THE FLEET (OPS.4: 2 vCPU, no swap).
MAX_FANOUT_WORKERS = int(__import__('os').environ.get("DTP_FANOUT_WORKERS", "16"))


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


def ssh_map(targets, command, timeout=None, workers=None, on_result=None):
    """Run ONE command on MANY boxes concurrently. {key: (rc, stdout, stderr)}.

    `targets` is an iterable of (key, ip). The key is whatever the caller wants
    back — a symbol, usually — and it is what the result dict is keyed on.

    🔑 ONE OWNER FOR THE SSH INVOCATION. Every worker calls `ssh_run`, so the
    key, user, host-key policy, timeout arithmetic and the explicit UTF-8
    decode all stay in exactly one place (WA 7). This function adds
    concurrency and NOTHING else.

    ⚠️ FAILURE IS PER BOX AND NEVER COLLECTIVE. A worker that raises is caught
    and recorded as that box's own (255, "", reason); one unreachable box must
    not cost the other fourteen their answers, which is the whole reason the
    serial loop was fragile.

    🔑 `on_result(key, (rc, out, err), done, total)` FIRES AS EACH BOX LANDS,
    AND IT IS NOT DECORATION. CND.3 exists because the drain printed one line
    and went silent for minutes, which is INDISTINGUISHABLE FROM A HANG — and
    on 2026-09-10 the run genuinely was hung and looked identical. A blocking
    gather would reintroduce exactly that: nothing at all until the slowest box
    returns, so one box hanging for its full timeout would show NOTHING for the
    whole window, which is WORSE than the serial version it replaces (serial at
    least showed fourteen answering and then stalling on the fifteenth).
    So results are consumed AS THEY COMPLETE and the caller is told, with a
    running count, which is what lets it name what is still OUTSTANDING.
    ⚠️ A RAISING CALLBACK MUST NOT COST A RESULT — narration is not allowed to
    lose data, so it is wrapped.

    ⚠️ WORKERS ARE CAPPED. ssh clients are IO-bound and control is a 2-vCPU
    t3.medium with ZERO swap (OPS.4), so the ceiling protects the control box
    rather than the fleet: fifteen waiting sockets are cheap, an unbounded pool
    on a future larger fleet is not.
    """
    items = [(k, ip) for k, ip in targets]
    if not items:
        return {}
    n = workers or min(len(items), MAX_FANOUT_WORKERS)
    # 🔴 THE PHASE BOUND DEPENDS ON THIS NUMBER AND THE CALLER'S DOES TOO.
    # A pool with FEWER workers than targets runs in WAVES, so the real bound
    # is ceil(N / workers) × per-box timeout — NOT one box's timeout. Saying
    # "the phase now costs MAX(per-box)" is only true at full width, and a
    # caller that quietly got two waves would report a worst case wrong by a
    # factor of two. So the actual figure is RETURNED rather than assumed:
    # `ssh_map.last_waves` is what a caller should quote, never `1`.
    ssh_map.last_waves = -(-len(items) // n)      # ceil
    ssh_map.last_workers = n
    out = {}

    def _one(pair):
        key, ip = pair
        try:
            return key, ssh_run(ip, command, timeout=timeout)
        except Exception as exc:                                # noqa: BLE001
            return key, (255, "", f"ssh_map error: {exc}")

    total = len(items)
    with _fut.ThreadPoolExecutor(max_workers=n) as ex:
        futs = [ex.submit(_one, it) for it in items]
        for f in _fut.as_completed(futs):
            key, res = f.result()
            out[key] = res
            if on_result is not None:
                try:
                    on_result(key, res, len(out), total)
                except Exception:                               # noqa: BLE001
                    pass    # narration must never cost a result
    # ⚠️ RETURNED IN THE CALLER'S ORDER, NOT COMPLETION ORDER. The dict is
    # rebuilt against `items` so a report reads the same way every night; a
    # human diffing two nightly logs must not see scheduler noise as change.
    return {k: out[k] for k, _ip in items if k in out}


def scp_push(ip, local_path, remote_path, timeout=None):
    """UPLOAD local_path to remote_path on the box. The mirror of `scp_pull`.

    v0.4.0 (2026-09-13) — dtp r379 / LVL.17. The module had a PULL and no PUSH
    for two months because everything control needed was a download: the
    harvest, the report, the ledger book. The delivered level history reverses
    the direction — control BUILDS it from banked tape and the box reads it —
    and the operator's framing is why it must be a push rather than a fetch:
    *"I'm not saying the bots would 'pull' from s3. I'm saying we could construct
    their ledgers from that data."* A trading box never reaches the warehouse.

    `remote_path` is relative to the box's home dir (e.g.
    'options-trader/data/level_history/AMD.json') for the same reason `scp_pull`
    documents: it resolves identically under legacy and SFTP-mode scp.
    ⚠️ THE REMOTE DIRECTORY MUST EXIST. scp will not create it and the failure is
    a terse "No such file or directory" — the caller mkdirs first.
    Returns (rc, stdout, stderr); never raises.
    """
    timeout = timeout or config.SSH_CONNECT_TIMEOUT
    cmd = [
        "scp", "-i", config.SSH_KEY_PATH,
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", f"ConnectTimeout={config.SSH_CONNECT_TIMEOUT}",
        local_path, f"{config.SSH_USER}@{ip}:{remote_path}",
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           timeout=timeout + 60)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 255, "", "scp timeout"
    except Exception as exc:  # noqa: BLE001
        return 255, "", f"scp error: {exc}"


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
