# day_trader_pro/wake_and_bake.py — v1.1
"""
One-touch fleet maintenance. Wake the whole universe, resolve every box to the
GitHub repo (the single source of truth), restart the service, verify, and shut
the fleet back down — ending with every server on origin/main and stopped.

Full pipeline (each stage reports; the fleet is ALWAYS stopped at the end
unless --leave-running):

  1. WAKE      start every UNIVERSE instance, wait for 'running'
  2. PING      wait for SSH, confirm the expected box count is reachable
  3. BAKE      git fetch + show changed files + reset --hard origin/main
  4. VERIFY    every box HEAD == origin/main AND all boxes share ONE commit
  5. RESTART   clear __pycache__, systemctl restart optionsbot, confirm 'active'
  6. SHUTDOWN  orderly EC2 stop of the whole fleet (never terminate)

Modes:
  (default)         full pipeline above
  --wake-only       WAKE + PING only, fleet is left running. No sync, no
                    restart, no shutdown.
  --bake-only       fleet already awake: PING → BAKE → VERIFY → RESTART.
                    No WAKE, no shutdown — fleet stays up.
  --leave-running   full pipeline ("leave on"): pycache clear + restart still
                    happen, final SHUTDOWN is skipped.
  --shutdown-only   PING → clear __pycache__ on every reachable box → hand off
                    to eod_report.run() (P&L rollup + orderly fleet stop).

Safety:
  * Refuses to run during RTH (09:30-16:00 ET, Mon-Fri) unless --force, for
    every mode that restarts services or stops boxes (full, bake-only,
    shutdown-only). --wake-only is allowed during RTH (it stops nothing).
  * Requires confirmation (type the fleet size) unless --yes.
  * In full mode, SHUTDOWN runs even if an earlier stage fails, so a
    maintenance run never strands boxes running.

CLI:
  python wake_and_bake.py                   # interactive full run
  python wake_and_bake.py --yes             # 1-click, no prompt
  python wake_and_bake.py --wake-only       # just wake the fleet
  python wake_and_bake.py --bake-only       # ping + sync + restart (no wake/stop)
  python wake_and_bake.py --shutdown-only   # pycache clear + EOD report + stop
  python wake_and_bake.py --leave-running   # full run, skip final shutdown
  python wake_and_bake.py --dry-run         # show the plan, mutate nothing
  python wake_and_bake.py --mock            # offline synthetic fleet
  python wake_and_bake.py --strict          # abort if any box missing/unreachable
  python wake_and_bake.py --only SPX,QQQ    # scope to specific boxes

Changelog:
  v1.1 (2026-07-09)
    * NEW modes: --wake-only, --bake-only, --shutdown-only.
    * SYNC stage renamed BAKE. Now runs `git diff --name-status HEAD
      origin/main` before the hard reset and prints every changed file per
      box (like a normal git pull), then reports
      "successfully synched N file(s)" per box and fleet-wide.
    * RESTART stage now clears __pycache__ (recursive) before bouncing the
      service — applies to full runs, --leave-running ("leave on"), and
      --bake-only.
    * --shutdown-only clears __pycache__ on every reachable box, then calls
      eod_report.run() for the P&L rollup + orderly fleet stop.
    * --wake-only is permitted during RTH without --force (stops nothing).
  v1.0
    * Initial: WAKE / PING / SYNC / VERIFY / RESTART / SHUTDOWN pipeline.
"""

import argparse
import sys
import time
from datetime import datetime, time as dtime

from zoneinfo import ZoneInfo

import config
import ec2ops
import eod_report
import instance_registry
import notify
import ssh_util

_ET = ZoneInfo("US/Eastern")
INSTALL_DIR = "~/options-trader"
SERVICE = "optionsbot"

# Remote bake: fetch, list the files that are about to change (name-status,
# exactly what a git pull prints), hard-reset to origin/main, then emit one
# parseable line:
#   OK|<HEAD sha>|<origin/main sha>|<subject>
# The && chain means any git failure yields a non-zero rc and no OK line.
# The diff lines (e.g. "M\tfleet.py") arrive BEFORE the OK line on stdout.
BAKE_CMD = (
    f"cd {INSTALL_DIR} && git fetch origin -q && "
    f"git diff --name-status HEAD origin/main && "
    f"git reset --hard origin/main -q && "
    f'echo "OK|$(git rev-parse HEAD)|$(git rev-parse origin/main)|'
    f"$(git log --oneline -1 | tr '|' ' ')\""
)

# Recursive __pycache__ purge. `;` (not &&) before the next command so a noisy
# find never blocks what follows. Emits CLEARED so callers can verify.
PYCLEAR = (
    f"find {INSTALL_DIR} -type d -name __pycache__ -exec rm -rf {{}} + "
    f"2>/dev/null; echo CLEARED"
)

# Remote restart: clear pycache, bounce the service, let it settle, report
# is-active.
RESTART_CMD = (
    f"{PYCLEAR} && sudo systemctl restart {SERVICE} && sleep 3 && "
    f"systemctl is-active {SERVICE}"
)

SSH_READY_TIMEOUT = 180
SSH_READY_INTERVAL = 10

_STATUS_MAP = {"M": "modified", "A": "added", "D": "deleted", "R": "renamed",
               "C": "copied", "T": "type-changed"}


class _Abort(Exception):
    pass


def _log(stage, msg):
    print(f"[{stage:<8}] {msg}", flush=True)


def _exec(ip, cmd):
    if config.MOCK_AWS:
        return 0, "[mock]", ""
    if not ip:
        return 255, "", "no private IP"
    return ssh_util.ssh_run(ip, cmd)


def _discover(only):
    mapping, _ = instance_registry.discover(only or config.UNIVERSE)
    return mapping


def _in_rth(now=None):
    now = now or datetime.now(_ET)
    if now.weekday() >= 5:
        return False
    return dtime(9, 30) <= now.time() <= dtime(16, 0)


def _ids(mapping):
    return [r["instance_id"] for r in mapping.values() if r.get("instance_id")]


# ── stages ───────────────────────────────────────────────────────────────────

def stage_wake(mapping, dry):
    ids = _ids(mapping)
    if dry:
        _log("WAKE", f"[dry-run] would start {len(ids)} instance(s) and wait for 'running'")
        return True
    _log("WAKE", f"starting {len(ids)} instance(s)…")
    ec2ops.start(ids)
    reached = ec2ops.wait_state(ids, "running")
    up = sum(1 for v in reached.values() if v)
    _log("WAKE", f"{up}/{len(ids)} reached 'running'")
    return up == len(ids)


def stage_ping(only, expected, dry):
    if dry:
        _log("PING", "[dry-run] would wait for SSH and echo-test each box")
        return True, [], []
    deadline = time.time() + SSH_READY_TIMEOUT
    while True:
        mapping = _discover(only)
        ok, bad = [], []
        for sym in sorted(mapping):
            rc, _o, _e = _exec(mapping[sym].get("private_ip", ""), "echo OK")
            (ok if rc == 0 else bad).append(sym)
        if not bad or time.time() > deadline:
            break
        _log("PING", f"…waiting for SSH ({len(ok)}/{len(ok) + len(bad)} ready)")
        time.sleep(SSH_READY_INTERVAL)
    tail = f" — MISSING: {', '.join(bad)}" if bad else ""
    _log("PING", f"reachable {len(ok)}/{expected}{tail}")
    return (len(ok) == expected and not bad), ok, bad


def _parse_file_lines(out):
    """Extract git name-status lines ("M\tpath") that precede the OK| line."""
    files = []
    for line in out.splitlines():
        if line.startswith("OK|"):
            break
        if "\t" in line:
            status, _, path = line.partition("\t")
            status = status.strip()
            # rename/copy scores like R100 → keep the letter
            letter = status[:1]
            if letter in _STATUS_MAP:
                files.append((letter, path.strip()))
    return files


def stage_bake(mapping, symbols, dry):
    """Fetch + hard-reset every box to origin/main, showing changed files."""
    if dry:
        _log("BAKE", f"[dry-run] would run on {len(symbols)} box(es):")
        _log("BAKE", f"          {BAKE_CMD}")
        return {"heads": {}, "fails": [], "n_files": 0}
    if config.MOCK_AWS:
        _log("BAKE", f"[mock] all {len(symbols)} boxes -> mocksha0000 (0 files)")
        return {"heads": {s: "mocksha0000" for s in symbols}, "fails": [],
                "n_files": 0}

    heads, fails = {}, []
    total_files = 0
    for sym in sorted(symbols):
        rc, out, err = _exec(mapping[sym].get("private_ip", ""), BAKE_CMD)
        line = next((l for l in out.splitlines() if l.startswith("OK|")), None)
        if rc != 0 or not line:
            fails.append(sym)
            _log("BAKE", f"{sym:<5} 🚨 {(err or out).strip()[:60] or 'no OK line'}")
            continue
        parts = line.split("|")
        head, origin = (parts + ["", ""])[1:3]
        subject = parts[3] if len(parts) > 3 else ""
        if head != origin or not head:
            fails.append(sym)
            _log("BAKE", f"{sym:<5} 🚨 HEAD!=origin ({head[:8]} vs {origin[:8]})")
            continue
        files = _parse_file_lines(out)
        for letter, path in files:
            _log("BAKE", f"{sym:<5}   {letter} {path}  ({_STATUS_MAP[letter]})")
        heads[sym] = head
        total_files += len(files)
        if files:
            _log("BAKE", f"{sym:<5} ✅ {head[:10]}  {subject[:40]} — "
                         f"successfully synched {len(files)} file(s)")
        else:
            _log("BAKE", f"{sym:<5} ✅ {head[:10]}  {subject[:40]} — already up to date")
    _log("BAKE", f"successfully synched {total_files} file(s) across "
                 f"{len(heads)}/{len(symbols)} box(es)")
    return {"heads": heads, "fails": fails, "n_files": total_files}


def stage_pyclear(mapping, symbols, dry):
    """Standalone __pycache__ purge (used by --shutdown-only)."""
    if dry:
        _log("PYCLEAR", f"[dry-run] would run on {len(symbols)} box(es): {PYCLEAR}")
        return []
    if config.MOCK_AWS:
        _log("PYCLEAR", f"[mock] all {len(symbols)} boxes -> CLEARED")
        return []
    bad = []
    for sym in sorted(symbols):
        rc, out, err = _exec(mapping[sym].get("private_ip", ""), PYCLEAR)
        if rc != 0 or "CLEARED" not in out:
            bad.append(sym)
            _log("PYCLEAR", f"{sym:<5} 🚨 {err.strip()[:40] or f'rc={rc}'}")
        else:
            _log("PYCLEAR", f"{sym:<5} ✅ cleared")
    return bad


def stage_restart(mapping, symbols, dry):
    if dry:
        _log("RESTART", f"[dry-run] would run on {len(symbols)} box(es): {RESTART_CMD}")
        return []
    if config.MOCK_AWS:
        _log("RESTART", f"[mock] all {len(symbols)} boxes -> active")
        return []
    bad = []
    for sym in sorted(symbols):
        rc, out, err = _exec(mapping[sym].get("private_ip", ""), RESTART_CMD)
        st = out.splitlines()[-1].strip() if out.strip() else ""
        if rc != 0 or st != "active":
            bad.append(sym)
            _log("RESTART", f"{sym:<5} 🚨 {st or err.strip()[:40] or f'rc={rc}'}")
        else:
            _log("RESTART", f"{sym:<5} ✅ pycache cleared, service active")
    return bad


def stage_shutdown(mapping, dry):
    ids = _ids(mapping)
    if dry:
        _log("SHUTDOWN", f"[dry-run] would stop {len(ids)} instance(s)")
        return True
    _log("SHUTDOWN", f"stopping {len(ids)} instance(s)…")
    ec2ops.stop(ids)
    reached = ec2ops.wait_state(ids, "stopped")
    down = sum(1 for v in reached.values() if v)
    _log("SHUTDOWN", f"{down}/{len(ids)} reached 'stopped'")
    return down == len(ids)


# ── orchestration ────────────────────────────────────────────────────────────

_MODE_DESC = {
    "full":     "WAKE, resync, restart, and STOP",
    "wake":     "WAKE (and leave running)",
    "bake":     "resync + restart (no wake, no stop)",
    "shutdown": "pycache-clear, EOD report, and STOP",
}


def run(only=None, assume_yes=False, dry=False, leave_running=False,
        strict=False, force=False, mode="full"):
    expected = len(only or config.UNIVERSE)
    now = datetime.now(_ET)
    tags = (" [DRY-RUN]" if dry else "") + (" [MOCK]" if config.MOCK_AWS else "")
    _log("START", f"wake_and_bake [{mode}] — {expected} box(es) — "
                  f"{now:%Y-%m-%d %H:%M ET}{tags}")

    # RTH guard: every mode that restarts services or stops boxes is blocked.
    # wake-only stops/restarts nothing, so it's exempt.
    if mode != "wake" and _in_rth(now) and not force and not config.MOCK_AWS:
        _log("ABORT", "inside RTH (09:30-16:00 ET). This mode restarts or stops "
                      "the fleet — refusing. Re-run with --force only if you "
                      "truly mean to.")
        return 2

    if not assume_yes and not dry:
        ans = input(f"This will {_MODE_DESC[mode]} {expected} servers.\n"
                    f"Type the fleet size ({expected}) to proceed: ").strip()
        if ans != str(expected):
            _log("ABORT", "confirmation did not match; nothing done.")
            return 2

    live = not dry and not config.MOCK_AWS
    if live:
        notify.send(f"🛠️ wake_and_bake [{mode}]: {_MODE_DESC[mode]} — "
                    f"{expected} boxes…")

    mapping = _discover(only)
    waked = False
    summary = []
    rc_final = 0

    try:
        # 1 WAKE — full + wake-only
        if mode in ("full", "wake"):
            waked = True
            if not stage_wake(mapping, dry):
                summary.append("WAKE incomplete")
                if strict:
                    raise _Abort("not all instances reached 'running'")
            if live:
                mapping = _discover(only)  # refresh state + IPs after boot

        # 2 PING — every mode
        _ok, reachable, missing = stage_ping(only, expected, dry)
        targets = sorted(mapping) if dry else (reachable or [])
        if missing:
            summary.append(f"missing: {', '.join(missing)}")
            rc_final = 1
            if strict:
                raise _Abort(f"unreachable: {', '.join(missing)}")

        if mode == "wake":
            summary.append(f"{len(targets) if not dry else expected} box(es) "
                           f"awake + reachable, left running")
            return rc_final  # finally-block still runs (no shutdown in wake mode)

        if mode == "shutdown":
            # pycache clear first, then hand off to the EOD report, which
            # pulls P&L and performs the orderly fleet stop itself.
            bad = stage_pyclear(mapping, targets, dry)
            if bad:
                summary.append(f"pyclear bad: {', '.join(bad)}")
                rc_final = 1
            _log("EOD", "handing off to eod_report.run() for P&L rollup + stop…")
            eod_rc = eod_report.run(dry_run=dry)
            summary.append("EOD report + stop "
                           + ("✅" if eod_rc == 0 else f"🚨 rc={eod_rc}"))
            rc_final = rc_final or eod_rc
            return rc_final

        # 3 BAKE — full + bake-only
        bake = stage_bake(mapping, targets, dry)

        # 4 VERIFY convergence
        if live:
            heads, fails = bake["heads"], bake["fails"]
            shas = set(heads.values())
            if fails:
                summary.append(f"bake failed: {', '.join(fails)}")
                rc_final = 1
            if not fails and len(shas) == 1 and len(heads) == expected:
                sha = next(iter(shas))[:10]
                _log("VERIFY", f"✅ all {len(heads)}/{expected} boxes on {sha} (== origin/main)")
                summary.append(f"synched {bake['n_files']} file(s) → {sha}")
            else:
                head_map = ", ".join(f"{s}:{h[:8]}" for s, h in sorted(heads.items()))
                _log("VERIFY", f"🚨 NOT converged: {len(heads)}/{expected} synced, "
                               f"{len(shas)} distinct commit(s). {head_map}")
                summary.append("git NOT converged")
                rc_final = 1
        else:
            _log("VERIFY", "[dry/mock] convergence check skipped")

        # 5 RESTART (includes __pycache__ clear) — full + bake-only
        bad = stage_restart(mapping, targets, dry)
        if live:
            if bad:
                summary.append(f"restart bad: {', '.join(bad)}")
                rc_final = 1
            else:
                _log("RESTART", f"✅ pycache cleared + optionsbot active on all "
                               f"{len(targets)} box(es)")

        if mode == "bake":
            summary.append("fleet left running (bake-only)")

    except _Abort as exc:
        _log("ABORT", str(exc))
        rc_final = rc_final or 1
    except KeyboardInterrupt:
        _log("ABORT", "interrupted — proceeding per-mode cleanup.")
        rc_final = rc_final or 130
    finally:
        # 6 SHUTDOWN — full mode only; always runs there unless --leave-running.
        # wake/bake modes intentionally leave the fleet up; shutdown mode
        # already stopped it via eod_report.
        if mode == "full":
            if leave_running:
                _log("SHUTDOWN", "skipped (--leave-running) — pycache clear + "
                                 "restart already done")
                summary.append("left running")
            elif waked:
                if stage_shutdown(mapping, dry):
                    if not dry:
                        summary.append("fleet stopped")
                elif not dry:
                    _log("SHUTDOWN", "🚨 some boxes did NOT reach 'stopped' — CHECK EC2 CONSOLE")
                    summary.append("shutdown incomplete")
                    rc_final = rc_final or 1

        verdict = "✅ clean" if rc_final == 0 else "🚨 issues"
        line = (f"wake_and_bake [{mode}] done — {verdict}"
                + (" — " + " · ".join(summary) if summary else ""))
        _log("DONE", line)
        if live:
            notify.send("🛠️ " + line)
    return rc_final


def main(argv):
    p = argparse.ArgumentParser(
        description="Fleet wake/bake/restart/verify/shutdown with per-mode control")
    p.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    p.add_argument("--dry-run", action="store_true", help="show the plan, mutate nothing")
    p.add_argument("--mock", action="store_true", help="offline synthetic fleet")
    p.add_argument("--strict", action="store_true", help="abort if any box is missing/unreachable")
    p.add_argument("--leave-running", action="store_true",
                   help="full run ('leave on'): pycache clear + restart, skip final shutdown")
    p.add_argument("--force", action="store_true", help="allow running during RTH")
    p.add_argument("--only", default=None, help="comma-separated symbols (e.g. SPX,QQQ)")

    modes = p.add_mutually_exclusive_group()
    modes.add_argument("--wake-only", action="store_true",
                       help="WAKE + PING only; leave fleet running")
    modes.add_argument("--bake-only", action="store_true",
                       help="fleet already awake: PING + git sync + restart; no wake/stop")
    modes.add_argument("--shutdown-only", action="store_true",
                       help="pycache clear, then EOD report (P&L rollup + fleet stop)")
    args = p.parse_args(argv[1:])

    if args.mock:
        config.set_mock(True)
    only = [s.strip().upper() for s in args.only.split(",")] if args.only else None

    mode = ("wake" if args.wake_only else
            "bake" if args.bake_only else
            "shutdown" if args.shutdown_only else "full")

    if args.leave_running and mode != "full":
        p.error("--leave-running only applies to a full run "
                "(wake/bake modes already leave the fleet up)")

    return run(only=only, assume_yes=args.yes, dry=args.dry_run,
               leave_running=args.leave_running, strict=args.strict,
               force=args.force, mode=mode)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
