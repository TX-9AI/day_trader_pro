# day_trader_pro/wake_and_bake.py — v1.4
# v1.4 (2026-08-18) — VERIFY IS NOW REPO-AWARE, because the fleet no longer
#   shares one repo: the QQQ box runs the options_trader_smc fork while the
#   other 28 stay on options_trader_v3. VERIFY required ONE commit across ALL
#   boxes, so a heterogeneous fleet printed "🚨 NOT converged" and returned
#   rc=1 on EVERY run — nothing broken, nothing reverted, just a red light
#   that means nothing. That is the CV.1 class: a check that cries wolf trains
#   you to ignore red runs. Convergence is now asked PER REMOTE — every box in
#   a repo group must share one commit, and every box must be accounted for.
#   BAKE_CMD carries the remote in its OK line to make that possible.
#   ⚠️ UNCHANGED BY DESIGN: BAKE still does `git fetch origin && git reset
#   --hard origin/main` and still names NO repo — it follows whatever remote
#   the box carries, which is what makes the fork deployable at all.
# v1.3 (2026-08-16) — WH.7: THE EMERGENCY STOP NO LONGER HANGS.
#   Option 27 pinged all 29 boxes over SSH before stopping anything. Discovery
#   returns STOPPED instances with a stale private_ip, so the ping SSHed
#   machines that cannot answer at SSH_CONNECT_TIMEOUT=12s each, sequentially:
#   ~27 down = ~5.4 min for ONE pass, longer than SSH_READY_TIMEOUT=180s (only
#   checked BETWEEN passes), and the first "…waiting for SSH" line prints only
#   AFTER a full pass. ~5 silent minutes before the stop was attempted — worst
#   precisely when the fleet is partially up. Shutdown now skips the ping
#   entirely: stopping needs an instance ID, not an IP or a reachable host.
#   ⚠️ UNCHANGED BY DESIGN, verified BY NAME (July 22 rule): the HALT gate, the
#   position-abandonment warning, the RTH exemption, and "no EOD, no pycache".
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
  --bake-only       fleet already awake: PING → BAKE → VERIFY, then STOP. Syncs
                    files to disk and does NOT restart anything — running bots
                    keep their in-memory code until a later restart. Safe to run
                    inside RTH (mirrors `fleet.py update --no-restart`).
  --leave-running   full pipeline ("leave on"): pycache clear + restart still
                    happen, final SHUTDOWN is skipped.
  --shutdown-only   PING → clear __pycache__ on every reachable box → hand off
                    to eod_report.run() (P&L rollup + orderly fleet stop).

Safety:
  * Refuses to run during RTH (09:30-16:00 ET, Mon-Fri) unless --force, ONLY for
    the modes that restart services or stop boxes: `full` and `shutdown-only`.
    --wake-only (starts boxes only) and --bake-only (syncs files only, no
    restart) are allowed during RTH.
  * Requires confirmation (type the fleet size) unless --yes.
  * In full mode, SHUTDOWN runs even if an earlier stage fails, so a
    maintenance run never strands boxes running.

CLI:
  python wake_and_bake.py                   # interactive full run
  python wake_and_bake.py --yes             # 1-click, no prompt
  python wake_and_bake.py --wake-only       # just wake the fleet
  python wake_and_bake.py --bake-only       # ping + sync files, NO restart (RTH-safe)
  python wake_and_bake.py --shutdown-only   # pycache clear + EOD report + stop
  python wake_and_bake.py --leave-running   # full run, skip final shutdown
  python wake_and_bake.py --dry-run         # show the plan, mutate nothing
  python wake_and_bake.py --mock            # offline synthetic fleet
  python wake_and_bake.py --strict          # abort if any box missing/unreachable
  python wake_and_bake.py --only SPX,QQQ    # scope to specific boxes

Changelog:
  v1.2 (2026-07-10)
    * --bake-only no longer restarts. It is now PING → BAKE → VERIFY only:
      it syncs the new code to disk and leaves every running bot untouched
      (matches `fleet.py update --no-restart`). Restart via a full run, or
      bounce a specific service by hand, when you're ready.
    * Because bake-only no longer restarts, it is EXEMPT from the RTH guard —
      it can run any time, including mid-session, without --force. The guard
      now blocks only `full` and `shutdown-only` during RTH.
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
import os
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
#   OK|<HEAD sha>|<origin/main sha>|<repo>|<subject>
# v1.4 added <repo> (the remote's basename, .git stripped) so VERIFY can group
# by repo instead of demanding one commit across a fleet that has two.
# The && chain means any git failure yields a non-zero rc and no OK line.
# The diff lines (e.g. "M\tfleet.py") arrive BEFORE the OK line on stdout.
BAKE_CMD = (
    f"cd {INSTALL_DIR} && git fetch origin -q && "
    f"git diff --name-status HEAD origin/main && "
    f"git reset --hard origin/main -q && "
    f'echo "OK|$(git rev-parse HEAD)|$(git rev-parse origin/main)|'
    f'$(basename "$(git remote get-url origin 2>/dev/null)" .git)|'
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
        return {"heads": {}, "fails": [], "n_files": 0, "repos": {}}
    if config.MOCK_AWS:
        _log("BAKE", f"[mock] all {len(symbols)} boxes -> mocksha0000 (0 files)")
        return {"heads": {s: "mocksha0000" for s in symbols}, "fails": [],
                "n_files": 0,
                "repos": {s: "options_trader_v3" for s in symbols}}

    heads, fails, repos = {}, [], {}
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
        # v1.4 — five fields now: OK|head|origin|repo|subject. A four-field
        # line means the box answered an older BAKE_CMD; treat the repo as
        # UNKNOWN rather than mistaking the subject for a repo name.
        if len(parts) >= 5:
            repo = parts[3].strip() or "?"
            subject = parts[4]
        else:
            repo = "?"
            subject = parts[3] if len(parts) > 3 else ""
        repos[sym] = repo
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
    return {"heads": heads, "fails": fails, "n_files": total_files,
            "repos": repos}


def verify_convergence(heads, repos, fails, expected):
    """v1.4 — is every box where it should be, GROUPED BY REPO?

    Pure and side-effect free so it can be tested without a fleet (the
    property the old inline block did not have). Returns
    (ok: bool, lines: [(level, text)], note: str).

    The rule that changed: convergence is asked WITHIN each repo group, not
    across the fleet. Two boxes on two different repos are SUPPOSED to sit on
    different commits — that is the point of the fork, not a fault. What is
    still a fault: two boxes on the SAME repo disagreeing, a bake failure, or
    a box that never reported at all.
    """
    lines = []
    if fails:
        lines.append(("err", f"🚨 bake failed on: {', '.join(sorted(fails))}"))

    groups = {}
    for sym, head in heads.items():
        groups.setdefault(repos.get(sym, "?"), {})[sym] = head

    bad = []
    for repo in sorted(groups):
        g = groups[repo]
        shas = set(g.values())
        if len(shas) == 1:
            lines.append(("info", f"✅ {len(g)}/{len(g)} on {next(iter(shas))[:10]} "
                                  f"({repo})"))
        else:
            head_map = ", ".join(f"{s}:{h[:8]}" for s, h in sorted(g.items()))
            lines.append(("err", f"🚨 {repo}: {len(shas)} distinct commit(s) "
                                 f"across {len(g)} box(es). {head_map}"))
            bad.append(repo)

    missing = expected - len(heads)
    if missing > 0:
        lines.append(("err", f"🚨 {len(heads)}/{expected} boxes reported — "
                             f"{missing} did not answer"))

    ok = not fails and not bad and missing <= 0
    if ok:
        note = ("converged: " +
                " · ".join(f"{len(groups[r])}×{r}" for r in sorted(groups)))
        if len(groups) > 1:
            lines.append(("info", f"ℹ️  {len(groups)} repo groups on this fleet "
                                  f"— separate repos are EXPECTED to differ"))
    else:
        note = "git NOT converged"
    return ok, lines, note


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
    _log("SHUTDOWN", f"stopping {len(ids)} instance(s)… (stop request sent "
                     f"before any wait; nothing here needs SSH)")
    ec2ops.stop(ids)
    _log("SHUTDOWN", "stop requested — polling for 'stopped'…")
    reached = ec2ops.wait_state(ids, "stopped")
    down = sum(1 for v in reached.values() if v)
    _log("SHUTDOWN", f"{down}/{len(ids)} reached 'stopped'")
    return down == len(ids)


# ── orchestration ────────────────────────────────────────────────────────────

_MODE_DESC = {
    "full":     "WAKE, resync, restart, and STOP",
    "wake":     "WAKE (and leave running)",
    "bake":     "resync files (no restart, no wake, no stop)",
    "shutdown": "EMERGENCY STOP the fleet NOW (no EOD, no pycache, RTH-exempt)",
}


def run(only=None, assume_yes=False, dry=False, leave_running=False,
        strict=False, force=False, mode="full"):
    expected = len(only or config.UNIVERSE)
    now = datetime.now(_ET)
    mode_label = "full-leave-on" if (mode == "full" and leave_running) else mode
    tags = (" [DRY-RUN]" if dry else "") + (" [MOCK]" if config.MOCK_AWS else "")
    _log("START", f"wake_and_bake [{mode_label}] — {expected} box(es) — "
                  f"{now:%Y-%m-%d %H:%M ET}{tags}")

    # RTH guard: only modes that RESTART services or STOP boxes are blocked
    # during market hours — that's `full` and `shutdown`. `wake` only starts
    # boxes; `bake` only syncs files to disk (no restart), so both are safe to
    # run inside RTH and are exempt.
    # RTH guard: blocks `full` during market hours because it RESTARTS bots
    # (yanking them mid-position). `shutdown` is DELIBERATELY exempt — it is the
    # emergency kill switch; stopping a misbehaving fleet during RTH is exactly
    # when you need it. `wake`/`bake` only start boxes or sync files (no restart),
    # so they're safe in RTH too.
    if mode == "full" and _in_rth(now) and not force and not config.MOCK_AWS:
        _log("ABORT", "inside RTH (09:30-16:00 ET). A full run restarts the "
                      "fleet mid-session — refusing. Re-run with --force only if "
                      "you truly mean to. (For an emergency stop, use shutdown.)")
        return 2

    if not assume_yes and not dry:
        if mode == "shutdown":
            # Emergency kill switch — a deliberate "HALT" gate instead of the
            # numeric confirm. This ALWAYS shows: reaching for the kill switch
            # means you should see the position-abandonment warning every time.
            in_rth = _in_rth(now) and not config.MOCK_AWS
            live_fleet = os.environ.get("OT_PAPER_TRADING", "True") == "False"
            print("\n" + "═" * 60)
            print("⚠️  WARNING — Open Positions will no longer be managed!")
            if in_rth and live_fleet:
                print("    LIVE fleet, INSIDE market hours: any open 0DTE")
                print("    positions are abandoned at the broker with NO exit")
                print("    logic until you restart. This is irreversible for")
                print("    the current session.")
            elif in_rth:
                print("    Paper fleet, inside market hours: boxes stop")
                print("    mid-session (no real positions at risk).")
            print(f"    Stopping {expected} box(es).")
            print("═" * 60)
            ans = input('Type "HALT" to proceed: ').strip()
            if ans != "HALT":
                _log("ABORT", "not confirmed (expected HALT); nothing done.")
                return 2
        else:
            # leave_running is a full run that SKIPS the final shutdown — say so,
            # rather than showing the plain "full" banner that ends in STOP.
            desc = ("WAKE, resync, restart, and LEAVE RUNNING (no stop)"
                    if (mode == "full" and leave_running)
                    else _MODE_DESC[mode])
            ans = input(f"This will {desc} {expected} servers.\n"
                        f"Press ENTER to proceed, or Ctrl-C to cancel: ").strip()
            if ans.lower() in ("n", "no", "q", "quit", "cancel"):
                _log("ABORT", "cancelled; nothing done.")
                return 2

    live = not dry and not config.MOCK_AWS
    if live:
        notify_desc = ("WAKE, resync, restart, and LEAVE RUNNING (no stop)"
                       if (mode == "full" and leave_running)
                       else _MODE_DESC[mode])
        notify.send(f"🛠️ wake_and_bake [{mode_label}]: {notify_desc} — "
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

        # 2 PING — every mode EXCEPT shutdown.
        #
        # 🔴 THE EMERGENCY STOP USED TO PING ALL 29 BOXES FIRST, AND THAT IS
        # WHY IT APPEARED TO HANG WITH NO WARNING. Discovery returns STOPPED
        # instances too, and a stopped box keeps a stale private_ip, so the
        # ping SSHed machines that cannot answer and paid SSH_CONNECT_TIMEOUT
        # (12s) for each. The loop is sequential, so ~27 down = ~5.4 min for a
        # single pass — LONGER than SSH_READY_TIMEOUT (180s), which is only
        # checked BETWEEN passes — and the first "…waiting for SSH" line only
        # prints AFTER a full pass. Five silent minutes before the stop was
        # even attempted, worst exactly when the fleet is partially up, which
        # is when you reach for a kill switch.
        #
        # STOPPING NEEDS NO SSH AND NO IP. `_ids()` reads instance_id;
        # ec2ops.stop() takes ids; wait_state("stopped") already returns True
        # for a box that is stopped. Reachability is irrelevant to the one job
        # this mode has.
        if mode == "shutdown":
            _log("SHUTDOWN", "skipping SSH reachability — stopping by instance "
                             "ID; a box that cannot answer still stops")
        else:
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
            # EMERGENCY CLEAN STOP: no pycache, no EOD/P&L harvest — the fastest
            # safe path to a fully stopped fleet. Use when something has gone
            # wrong and you want every box DOWN now. RTH-exempt (see the guard
            # below): killing the fleet is the correct move in a bad-state
            # emergency regardless of market hours. The nightly eod_report timer
            # owns P&L; this does not touch it. Changed 2026-07-18.
            if stage_shutdown(mapping, dry):
                if not dry:
                    summary.append("fleet stopped (emergency, no EOD/pyclear)")
            elif not dry:
                _log("SHUTDOWN", "🚨 some boxes did NOT reach 'stopped' — CHECK EC2 CONSOLE")
                summary.append("shutdown incomplete")
                rc_final = rc_final or 1
            return rc_final

        # 3 BAKE — full + bake-only
        bake = stage_bake(mapping, targets, dry)

        # 4 VERIFY convergence
        if live:
            ok, lines, note = verify_convergence(
                bake["heads"], bake.get("repos", {}), bake["fails"], expected)
            for lvl, text in lines:
                _log("VERIFY", text)
            if bake["fails"]:
                summary.append(f"bake failed: {', '.join(bake['fails'])}")
            summary.append(note if not ok
                           else f"synched {bake['n_files']} file(s) — {note}")
            if not ok:
                rc_final = 1
        else:
            _log("VERIFY", "[dry/mock] convergence check skipped")

        # 5 RESTART (includes __pycache__ clear) — FULL mode only.
        # bake-only deliberately does NOT restart: it syncs files to disk and
        # leaves every running bot untouched, so it's safe to run inside RTH
        # (mirrors `fleet.py update --no-restart`). Restart the bots later with
        # a full run, or bounce a specific service by hand when you're ready.
        if mode == "full":
            bad = stage_restart(mapping, targets, dry)
            if live:
                if bad:
                    summary.append(f"restart bad: {', '.join(bad)}")
                    rc_final = 1
                else:
                    _log("RESTART", f"✅ pycache cleared + optionsbot active on all "
                                   f"{len(targets)} box(es)")

        if mode == "bake":
            _log("BAKE", "files synced to disk — bots NOT restarted (bake-only). "
                         "Running bots keep their in-memory code until a later "
                         "restart.")
            summary.append("synced, not restarted (bake-only)")

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
                       help="pycache clear, then a clean fleet stop (NO EOD/P&L harvest)")
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
