# day_trader_pro/wake_and_bake.py — v1.0
"""
One-touch fleet maintenance. Wake the whole universe, resolve every box to the
GitHub repo (the single source of truth), restart the service, verify, and shut
the fleet back down — ending with every server on origin/main and stopped.

Pipeline (each stage reports; the fleet is ALWAYS stopped at the end unless
--leave-running):

  1. WAKE      start every UNIVERSE instance, wait for 'running'
  2. PING      wait for SSH, confirm the expected box count is reachable
  3. SYNC      git fetch + reset --hard origin/main on every reachable box
  4. VERIFY    every box HEAD == origin/main AND all boxes share ONE commit
  5. RESTART   systemctl restart optionsbot, confirm it returns to 'active'
  6. SHUTDOWN  orderly EC2 stop of the whole fleet (never terminate)

Safety:
  * Refuses to run during RTH (09:30-16:00 ET, Mon-Fri) unless --force — it
    wakes AND stops the fleet, so it must never touch a live session.
  * Requires confirmation (type the fleet size) unless --yes.
  * SHUTDOWN runs even if an earlier stage fails, so a maintenance run never
    strands boxes running. Use --leave-running to keep them up for debugging.

CLI:
  python wake_and_bake.py                 # interactive real run
  python wake_and_bake.py --yes            # 1-click, no prompt
  python wake_and_bake.py --dry-run        # show the plan, mutate nothing
  python wake_and_bake.py --mock            # offline synthetic fleet
  python wake_and_bake.py --strict          # abort if any box is missing/unreachable
  python wake_and_bake.py --leave-running   # skip the final shutdown
  python wake_and_bake.py --only SPX,QQQ    # scope to specific boxes
"""

import argparse
import sys
import time
from datetime import datetime, time as dtime

from zoneinfo import ZoneInfo

import config
import ec2ops
import instance_registry
import notify
import ssh_util

_ET = ZoneInfo("US/Eastern")
INSTALL_DIR = "~/options-trader"
SERVICE = "optionsbot"

# Remote sync: fetch, hard-reset to origin/main, then emit one parseable line:
#   OK|<HEAD sha>|<origin/main sha>|<subject>
# The && chain means any git failure yields a non-zero rc and no OK line.
SYNC_CMD = (
    f"cd {INSTALL_DIR} && git fetch origin -q && "
    f"git reset --hard origin/main -q && "
    f'echo "OK|$(git rev-parse HEAD)|$(git rev-parse origin/main)|'
    f'$(git log --oneline -1 | tr \'|\' \' \')"'
)
# Remote restart: bounce the service, let it settle, report is-active.
RESTART_CMD = f"sudo systemctl restart {SERVICE} && sleep 3 && systemctl is-active {SERVICE}"

SSH_READY_TIMEOUT = 180
SSH_READY_INTERVAL = 10


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


def stage_sync(mapping, symbols, dry):
    if dry:
        _log("SYNC", f"[dry-run] would run on {len(symbols)} box(es):")
        _log("SYNC", f"          {SYNC_CMD}")
        return {"heads": {}, "fails": []}
    if config.MOCK_AWS:
        _log("SYNC", f"[mock] all {len(symbols)} boxes -> mocksha0000")
        return {"heads": {s: "mocksha0000" for s in symbols}, "fails": []}

    heads, fails = {}, []
    for sym in sorted(symbols):
        rc, out, err = _exec(mapping[sym].get("private_ip", ""), SYNC_CMD)
        line = next((l for l in out.splitlines() if l.startswith("OK|")), None)
        if rc != 0 or not line:
            fails.append(sym)
            _log("SYNC", f"{sym:<5} 🚨 {(err or out).strip()[:60] or 'no OK line'}")
            continue
        parts = line.split("|")
        head, origin = (parts + ["", ""])[1:3]
        subject = parts[3] if len(parts) > 3 else ""
        if head != origin or not head:
            fails.append(sym)
            _log("SYNC", f"{sym:<5} 🚨 HEAD!=origin ({head[:8]} vs {origin[:8]})")
            continue
        heads[sym] = head
        _log("SYNC", f"{sym:<5} ✅ {head[:10]}  {subject[:48]}")
    return {"heads": heads, "fails": fails}


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
            _log("RESTART", f"{sym:<5} ✅ active")
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

def run(only=None, assume_yes=False, dry=False, leave_running=False,
        strict=False, force=False):
    expected = len(only or config.UNIVERSE)
    now = datetime.now(_ET)
    tags = (" [DRY-RUN]" if dry else "") + (" [MOCK]" if config.MOCK_AWS else "")
    _log("START", f"wake_and_bake — {expected} box(es) — {now:%Y-%m-%d %H:%M ET}{tags}")

    if _in_rth(now) and not force and not config.MOCK_AWS:
        _log("ABORT", "inside RTH (09:30-16:00 ET). This wakes AND stops the fleet — "
                      "refusing. Re-run with --force only if you truly mean to.")
        return 2

    if not assume_yes and not dry:
        ans = input(f"This will WAKE, resync, restart, and STOP {expected} servers.\n"
                    f"Type the fleet size ({expected}) to proceed: ").strip()
        if ans != str(expected):
            _log("ABORT", "confirmation did not match; nothing done.")
            return 2

    live = not dry and not config.MOCK_AWS
    if live:
        notify.send(f"🛠️ wake_and_bake: resyncing {expected} boxes to origin/main…")

    mapping = _discover(only)
    waked = False
    summary = []
    rc_final = 0

    try:
        # 1 WAKE
        waked = True
        if not stage_wake(mapping, dry):
            summary.append("WAKE incomplete")
            if strict:
                raise _Abort("not all instances reached 'running'")
        if live:
            mapping = _discover(only)  # refresh state + IPs after boot

        # 2 PING
        _ok, reachable, missing = stage_ping(only, expected, dry)
        targets = sorted(mapping) if dry else (reachable or [])
        if missing:
            summary.append(f"missing: {', '.join(missing)}")
            rc_final = 1
            if strict:
                raise _Abort(f"unreachable: {', '.join(missing)}")

        # 3 SYNC
        sync = stage_sync(mapping, targets, dry)

        # 4 VERIFY convergence
        if live:
            heads, fails = sync["heads"], sync["fails"]
            shas = set(heads.values())
            if fails:
                summary.append(f"sync failed: {', '.join(fails)}")
                rc_final = 1
            if not fails and len(shas) == 1 and len(heads) == expected:
                sha = next(iter(shas))[:10]
                _log("VERIFY", f"✅ all {len(heads)}/{expected} boxes on {sha} (== origin/main)")
                summary.append(f"synced → {sha}")
            else:
                head_map = ", ".join(f"{s}:{h[:8]}" for s, h in sorted(heads.items()))
                _log("VERIFY", f"🚨 NOT converged: {len(heads)}/{expected} synced, "
                               f"{len(shas)} distinct commit(s). {head_map}")
                summary.append("git NOT converged")
                rc_final = 1
        else:
            _log("VERIFY", "[dry/mock] convergence check skipped")

        # 5 RESTART
        bad = stage_restart(mapping, targets, dry)
        if live:
            if bad:
                summary.append(f"restart bad: {', '.join(bad)}")
                rc_final = 1
            else:
                _log("RESTART", f"✅ optionsbot active on all {len(targets)} box(es)")

    except _Abort as exc:
        _log("ABORT", str(exc))
        rc_final = rc_final or 1
    except KeyboardInterrupt:
        _log("ABORT", "interrupted — proceeding to shutdown so nothing is left running.")
        rc_final = rc_final or 130
    finally:
        # 6 SHUTDOWN — always, unless explicitly told to leave the fleet up
        if leave_running:
            _log("SHUTDOWN", "skipped (--leave-running)")
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
    line = f"wake_and_bake done — {verdict}" + (" — " + " · ".join(summary) if summary else "")
    _log("DONE", line)
    if live:
        notify.send("🛠️ " + line)
    return rc_final


def main(argv):
    p = argparse.ArgumentParser(description="One-click fleet wake/sync/restart/verify/shutdown")
    p.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    p.add_argument("--dry-run", action="store_true", help="show the plan, mutate nothing")
    p.add_argument("--mock", action="store_true", help="offline synthetic fleet")
    p.add_argument("--strict", action="store_true", help="abort if any box is missing/unreachable")
    p.add_argument("--leave-running", action="store_true", help="skip the final shutdown")
    p.add_argument("--force", action="store_true", help="allow running during RTH")
    p.add_argument("--only", default=None, help="comma-separated symbols (e.g. SPX,QQQ)")
    args = p.parse_args(argv[1:])

    if args.mock:
        config.set_mock(True)
    only = [s.strip().upper() for s in args.only.split(",")] if args.only else None

    return run(only=only, assume_yes=args.yes, dry=args.dry_run,
               leave_running=args.leave_running, strict=args.strict, force=args.force)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
