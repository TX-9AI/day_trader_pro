# day_trader_pro/fleet.py — v0.4.0
"""
Fleet SSH fan-out. Pulls every monitored box's private IP from its tag and
reaches each one, one at a time, from the control server.

This is the general-purpose management plane: connectivity checks, ad-hoc
commands, deploy verification, health pings — anything you'd otherwise SSH
into the boxes by hand to do.

Targets RUNNING boxes by default (you can't SSH a stopped instance); use
--all to also list the stopped ones as skipped.

CLI:
    python fleet.py list                          # symbol -> IP -> state (no SSH)
    python fleet.py ping                          # SSH echo-test each running box
    python fleet.py ping --all                    # include stopped (shown skipped)
    python fleet.py run "uptime"                  # run a command on each running box
    python fleet.py run "systemctl is-active optionsbot"

    # standardized fleet deploy — each bot runs its own push.sh --deploy
    # (fetch + hard-reset to origin + restart + verify; the download half of
    # the same push.sh used to publish up):
    python fleet.py update                         # deploy to running boxes
    python fleet.py update --wake                  # start stopped boxes first, then deploy
    python fleet.py update --no-restart            # deploy without restarting the service
    python fleet.py update --only SPX,QQQ,NVDA     # scope to specific symbols

    # repoint the WHOLE fleet from the current repo to a NEW repo URL (e.g.
    # migrating options_trader_v2 -> options_trader_v3), collision-guarded so a
    # live untracked secret is never clobbered by the new repo's tracked files:
    python fleet.py repoint https://github.com/TX-9AI/options_trader_v3.git
    python fleet.py repoint <url> --check-only     # phase 1 only: report collisions, change nothing
    python fleet.py repoint <url> --wake           # start stopped boxes first
    python fleet.py repoint <url> --no-restart     # sync but don't restart the service
    python fleet.py repoint <url> --only SPX,QQQ   # scope to specific symbols

    # pull files back from the boxes to ~/day_trader_pro/pulls/ (symbol-tagged):
    python fleet.py pull db                         # every box's trades.db
    python fleet.py pull db --only IWM,SPX          # scoped
    python fleet.py pull ohlc --day 2026-07-10      # that day's OHLC csv per box
    python fleet.py pull ohlc --day 2026-07-10 --only IWM

Add --mock to preview offline.

repoint is TWO-PHASE and fails safe:
  Phase 1 (CHECK — non-mutating): on every targeted box, fetch the new repo
    into FETCH_HEAD (origin is NOT touched) and list any file the new repo
    TRACKS that currently exists here as an UNTRACKED file — i.e. anything a
    hard reset would overwrite. Live per-symbol secrets that live in the
    systemd environment are outside the repo and cannot be reached by a reset;
    the only way to lose a secret is if it sits as an untracked file whose name
    collides with something the new repo tracks. Phase 1 finds exactly that.
  Phase 2 (COMMIT — only if EVERY targeted box is clean): set origin -> new
    URL, fetch, hard-reset to origin/main, repair *.sh +x, restart + verify.
  If ANY box reports a collision in phase 1, the whole run ABORTS before phase
  2 — no box is repointed, nothing is reset, so you never end up with a
  half-migrated (split-brain) fleet. Resolve the flagged files, then re-run.

NOTE: after a successful repoint, ongoing `fleet.py update` calls the bot's
own push.sh --deploy. The v1.6 push.sh hardcodes REPO=options_trader_v2 in its
deploy path, so make sure the NEW repo ships a push.sh that targets the new
repo — the reset pulls it in automatically and keeps future deploys correct.

Changelog:
  v0.4.0 (2026-07-10)
    * NEW action `pull db|ohlc`: download trades.db or a day's OHLC csv from
      one/all/some boxes to ~/day_trader_pro/pulls/ with symbol-tagged names.
      Uses ssh_util.scp_pull (v0.2.0). --day selects the OHLC date.
  v0.3.0 (2026-07-09)
    * NEW action `repoint <new_repo_url>`: migrate the fleet from the current
      repo to a new one. Two-phase, collision-guarded (see above), fail-safe
      (aborts before any mutation if any box would lose an untracked file).
    * --check-only runs phase 1 alone (read-only audit against the new repo).
    * Token for a private new repo is read from each box's systemd env
      (GITHUB_TOKEN), same source push.sh uses; falls back to the plain URL.
    * repoint does its own fetch/reset (does NOT delegate to push.sh, whose
      deploy path is pinned to options_trader_v2 and would drag boxes back).
  v0.2.1
    * Fleet update via push.sh --deploy; list / ping / run management plane.
"""

import argparse
import os
import sys
import time

import config
import instance_registry
import ssh_util

INSTALL_DIR = "~/options-trader"
SERVICE     = "optionsbot"
# Where pulled files land on the control server (flat, symbol-tagged filenames).
PULL_DIR    = os.path.expanduser("~/day_trader_pro/pulls")
# Remote paths for scp are relative to the box's home dir (no leading ~/).
REMOTE_HOME_REL = "options-trader"


def get_fleet(only=None):
    """Return sorted list of (symbol, ip, state) for the monitored universe."""
    symbols = only or config.UNIVERSE
    mapping, _ = instance_registry.discover(symbols)
    out = []
    for s in sorted(mapping):
        rec = mapping[s]
        out.append((s, rec.get("private_ip", ""), rec.get("state", "?")))
    return out


def _targets(fleet, include_all):
    """Running boxes are SSH-able; stopped are returned separately if --all."""
    running = [(s, ip, st) for s, ip, st in fleet if st == "running"]
    skipped = [(s, ip, st) for s, ip, st in fleet if st != "running"]
    return running, (skipped if include_all else [])


def cmd_list(only=None):
    fleet = get_fleet(only)
    print(f"{'SYMBOL':<8}{'PRIVATE IP':<18}{'STATE':<10}")
    for s, ip, st in fleet:
        print(f"{s:<8}{ip or '-':<18}{st:<10}")
    running = sum(1 for _, _, st in fleet if st == "running")
    print(f"\n{running}/{len(fleet)} running")


def _exec(symbol, ip, command):
    if config.MOCK_AWS:
        return 0, f"[mock output for {symbol}: {command}]", ""
    if not ip:
        return 255, "", "no private IP"
    return ssh_util.ssh_run(ip, command)


def cmd_ping(only=None, include_all=False):
    fleet = get_fleet(only)
    running, skipped = _targets(fleet, include_all)
    print(f"Pinging {len(running)} running box(es) one by one...\n")
    ok = 0
    print(f"{'SYMBOL':<8}{'PRIVATE IP':<18}RESULT")
    for s, ip, _ in running:
        rc, _out, err = _exec(s, ip, "echo OK")
        if rc == 0:
            ok += 1
            print(f"{s:<8}{ip:<18}✅ reachable")
        else:
            print(f"{s:<8}{ip:<18}🚨 {err.strip()[:40] or 'failed'}")
    for s, ip, st in skipped:
        print(f"{s:<8}{(ip or '-'):<18}· skipped ({st})")
    print(f"\nReachable: {ok}/{len(running)} running box(es)")
    return 0 if ok == len(running) else 1


def cmd_run(command, only=None, include_all=False):
    fleet = get_fleet(only)
    running, skipped = _targets(fleet, include_all)
    print(f"Running on {len(running)} box(es): `{command}`\n")
    fails = 0
    for s, ip, _ in running:
        rc, out, err = _exec(s, ip, command)
        head = f"── {s} ({ip}) "
        print(head + "─" * max(0, 50 - len(head)))
        if rc == 0:
            print((out.rstrip() or "(no output)"))
        else:
            fails += 1
            print(f"🚨 rc={rc} {err.strip()[:200]}")
    for s, ip, st in skipped:
        print(f"── {s} ({ip or '-'}) · skipped ({st})")
    print(f"\nDone. {len(running) - fails}/{len(running)} succeeded.")
    return 0 if fails == 0 else 1


# ─── Fleet update (fresh pull + restart + verify) ────────────────────────────

def _wake(stopped):
    """Start stopped instances. Best-effort and non-fatal:
      1) if the registry exposes a starter, use it;
      2) else fall back to boto3 start_instances using instance_id from discover;
      3) else print how to start them by hand and continue with running boxes.
    """
    symbols = [s for s, _, _ in stopped]
    if not symbols:
        return
    print(f"Waking {len(symbols)} stopped box(es): {', '.join(symbols)}")
    if config.MOCK_AWS:
        print(f"  [mock] would start: {', '.join(symbols)}")
        return

    # 1) registry-provided starter, if present
    for fn in ("start_instances", "start", "wake"):
        if hasattr(instance_registry, fn):
            try:
                getattr(instance_registry, fn)(symbols)
                print(f"  instance_registry.{fn}() issued for {len(symbols)} box(es)")
                return
            except Exception as e:
                print(f"  registry.{fn}() failed ({e}); trying boto3…")

    # 2) boto3 fallback via instance_id from the registry
    try:
        import boto3
        mapping, _ = instance_registry.discover(symbols)
        ids = [mapping[s].get("instance_id")
               for s in symbols
               if mapping.get(s, {}).get("instance_id")]
        if not ids:
            print("  ⚠️  no instance_id in the registry — can't wake automatically.\n"
                  "     Start these in the EC2 console (or add instance_id to the\n"
                  "     registry), then re-run `update` without --wake.")
            return
        region = getattr(config, "AWS_REGION", None)
        ec2 = boto3.client("ec2", region_name=region) if region else boto3.client("ec2")
        ec2.start_instances(InstanceIds=ids)
        print(f"  start_instances issued for {len(ids)} instance(s)")
    except Exception as e:
        print(f"  ⚠️  wake failed ({e}); continuing with already-running boxes.")


def _wait_running_and_ssh(only=None, timeout=180, interval=10):
    """After a wake, poll until boxes are 'running' AND answer SSH. Re-discovers
    each pass (state flips as instances boot). Returns the SSH-ready list."""
    deadline = time.time() + timeout
    ready = []
    while time.time() < deadline:
        fleet = get_fleet(only)
        running = [(s, ip, st) for s, ip, st in fleet if st == "running" and ip]
        ready = []
        for s, ip, _ in running:
            rc, _o, _e = _exec(s, ip, "echo OK")
            if rc == 0:
                ready.append((s, ip, "running"))
        if running and len(ready) == len(running):
            return ready
        print(f"  …waiting for SSH ({len(ready)}/{len(running)} ready)")
        time.sleep(interval)
    return ready


def cmd_update(only=None, restart=True, wake=False):
    fleet = get_fleet(only)
    stopped = [(s, ip, st) for s, ip, st in fleet if st != "running"]

    if wake and stopped:
        _wake(stopped)
        running = _wait_running_and_ssh(only)
    else:
        running = [(s, ip, st) for s, ip, st in fleet if st == "running" and ip]

    # The bots own the git logic. push.sh --deploy fetches, hard-resets to the
    # remote branch it detects, repairs .sh perms, restarts the service and
    # verifies it — the download counterpart of push.sh's upload. fleet just
    # wakes boxes and fans the command out.
    flag = "" if restart else " --no-restart"
    cmd = f"bash {INSTALL_DIR}/push.sh --deploy{flag}"

    print(f"\nDeploying to {len(running)} box(es) via `push.sh --deploy`"
          f"{' (no restart)' if not restart else ''}\n")
    fails = 0
    for s, ip, _ in running:
        head = f"── {s} ({ip}) "
        print(head + "─" * max(0, 50 - len(head)))
        rc, out, err = _exec(s, ip, cmd)
        print((out.rstrip() or err.rstrip() or "(no output)"))
        if rc != 0:
            fails += 1
            print(f"  🚨 rc={rc}")

    if not wake:
        for s, ip, st in stopped:
            print(f"── {s} ({ip or '-'}) · skipped ({st}; use --wake to start)")

    print(f"\nDone. {len(running) - fails}/{len(running)} deployed cleanly.")
    return 0 if fails == 0 else 1


# ─── Fleet repoint (migrate to a new repo, collision-guarded) ────────────────

import re

_SENTINEL_FETCH_FAIL = "__REPOINT_FETCH_FAILED__"
_SENTINEL_OK = "__REPOINT_OK__"


def _repo_name_from_url(url):
    """https://github.com/OWNER/options_trader_v3.git -> options_trader_v3."""
    m = re.search(r"github\.com[:/]+[^/]+/([^/]+?)(?:\.git)?/?$", url)
    return m.group(1) if m else None


def _phase1_check_cmd(new_url, repo):
    """Non-mutating: fetch the new repo into FETCH_HEAD (origin untouched) and
    print any untracked file on this box that the new repo TRACKS. Prints the
    fetch-fail sentinel if the new repo can't be reached."""
    repo_clause = (
        f'if [ -n "$TOKEN" ]; then '
        f'URL="https://TX-9AI:${{TOKEN}}@github.com/TX-9AI/{repo}.git"; '
        f'else URL="{new_url}"; fi; '
    ) if repo else f'URL="{new_url}"; '
    return (
        f"cd {INSTALL_DIR} || exit 9; "
        f"TOKEN=$(sudo systemctl show {SERVICE} --property=Environment 2>/dev/null "
        f"| grep -o 'GITHUB_TOKEN=[^ ]*' | cut -d= -f2); "
        f"{repo_clause}"
        f'git fetch "$URL" main -q 2>/dev/null || {{ echo {_SENTINEL_FETCH_FAIL}; exit 3; }}; '
        f"comm -12 <(git ls-tree -r --name-only FETCH_HEAD | sort) "
        f"<(git ls-files --others --exclude-standard | sort)"
    )


def _phase2_commit_cmd(new_url, repo, restart):
    """Mutating: point origin at the new repo, hard-reset to it, repair *.sh
    +x, optionally restart + verify. Leaves origin on a token-free new URL."""
    clean_url = f"https://github.com/TX-9AI/{repo}.git" if repo else new_url
    fetch_clause = (
        f'if [ -n "$TOKEN" ]; then '
        f'FURL="https://TX-9AI:${{TOKEN}}@github.com/TX-9AI/{repo}.git"; '
        f'else FURL="{new_url}"; fi; '
    ) if repo else f'FURL="{new_url}"; '
    restart_clause = (
        f"sudo systemctl restart {SERVICE} && sleep 3 && "
        f'echo "service: $(systemctl is-active {SERVICE})"'
    ) if restart else 'echo "(service not restarted — --no-restart)"'
    return (
        f"cd {INSTALL_DIR} || exit 9; "
        f"TOKEN=$(sudo systemctl show {SERVICE} --property=Environment 2>/dev/null "
        f"| grep -o 'GITHUB_TOKEN=[^ ]*' | cut -d= -f2); "
        f"{fetch_clause}"
        f'git remote set-url origin "$FURL" || exit 4; '
        f"git fetch origin main -q || exit 5; "
        f"OLD=$(git rev-parse --short HEAD 2>/dev/null); "
        f"git reset --hard origin/main -q || exit 6; "
        f'git remote set-url origin "{clean_url}"; '
        f"git ls-files '*.sh' | xargs -r chmod +x 2>/dev/null; "
        f"NEW=$(git rev-parse --short HEAD 2>/dev/null); "
        f'echo "{_SENTINEL_OK} $OLD -> $NEW"; '
        f"{restart_clause}"
    )


def cmd_repoint(new_url, only=None, restart=True, wake=False,
                check_only=False, assume_yes=False):
    if not new_url or "github.com" not in new_url:
        print(f"repoint needs a GitHub repo URL, e.g.:\n"
              f"  python fleet.py repoint https://github.com/TX-9AI/options_trader_v3.git")
        return 2
    repo = _repo_name_from_url(new_url)

    fleet = get_fleet(only)
    stopped = [(s, ip, st) for s, ip, st in fleet if st != "running"]
    if wake and stopped:
        _wake(stopped)
        running = _wait_running_and_ssh(only)
    else:
        running = [(s, ip, st) for s, ip, st in fleet if st == "running" and ip]

    if not running:
        print("No running, SSH-reachable boxes to repoint. "
              "(Use --wake to start stopped boxes.)")
        return 1

    print(f"\nRepoint target: {new_url}")
    print(f"Detected repo:  {repo or '(could not parse — using URL verbatim)'}")
    print(f"Fleet:          {len(running)} running box(es)"
          + (f", {len(stopped)} stopped (skipped)" if stopped and not wake else ""))

    # ── PHASE 1 — collision check against the NEW repo (non-mutating) ──────────
    print(f"\n{'='*58}\nPHASE 1 — collision check vs new repo (nothing is changed)\n{'='*58}")
    check_cmd = _phase1_check_cmd(new_url, repo)
    collisions, unreachable = {}, []
    for s, ip, _ in running:
        rc, out, err = _exec(s, ip, check_cmd)
        lines = [l for l in out.splitlines() if l.strip()]
        if _SENTINEL_FETCH_FAIL in out or rc == 3:
            unreachable.append(s)
            print(f"{s:<8}{ip:<18}🚨 could not fetch new repo (token/network?)")
        elif rc != 0:
            unreachable.append(s)
            print(f"{s:<8}{ip:<18}🚨 check failed rc={rc} {err.strip()[:40]}")
        elif lines:
            collisions[s] = lines
            print(f"{s:<8}{ip:<18}🚨 {len(lines)} collision(s): {', '.join(lines)}")
        else:
            print(f"{s:<8}{ip:<18}✅ clean")

    if collisions or unreachable:
        print(f"\n{'='*58}")
        print("🚨 ABORT — phase 2 will NOT run. No box was repointed.")
        if collisions:
            print("\nBoxes with untracked files the new repo would OVERWRITE:")
            for s, files in collisions.items():
                for f in files:
                    print(f"    {s}: {f}")
            print("\nThese are likely live secrets/config. Move them into the\n"
                  "systemd env (or back them up) before repointing.")
        if unreachable:
            print(f"\nBoxes that couldn't reach the new repo: {', '.join(unreachable)}")
            print("Check the repo exists, is spelled right, and the box's\n"
                  "GITHUB_TOKEN can read it.")
        return 1

    print(f"\n✅ All {len(running)} box(es) clean — no untracked file collides "
          f"with the new repo.")

    if check_only:
        print("--check-only: stopping here. Re-run without it to migrate.")
        return 0

    # ── confirmation ──────────────────────────────────────────────────────────
    if not assume_yes and not config.MOCK_AWS:
        ans = input(f"\nProceed to REPOINT + hard-reset {len(running)} box(es) to "
                    f"{repo or new_url}?\nType the fleet size ({len(running)}) to "
                    f"confirm: ").strip()
        if ans != str(len(running)):
            print("Confirmation did not match; nothing changed.")
            return 2

    # ── PHASE 2 — commit the repoint (only reached if fully clean) ────────────
    print(f"\n{'='*58}\nPHASE 2 — repoint + sync"
          f"{' + restart' if restart else ''}\n{'='*58}")
    commit_cmd = _phase2_commit_cmd(new_url, repo, restart)
    fails = 0
    for s, ip, _ in running:
        head = f"── {s} ({ip}) "
        print(head + "─" * max(0, 50 - len(head)))
        rc, out, err = _exec(s, ip, commit_cmd)
        body = out.rstrip() or err.rstrip() or "(no output)"
        print(body)
        ok = (rc == 0) and (_SENTINEL_OK in out or config.MOCK_AWS)
        if restart and not config.MOCK_AWS and "service: active" not in out:
            ok = False
        if not ok:
            fails += 1
            print(f"  🚨 rc={rc} — box may be partially migrated; inspect before retry")

    print(f"\nDone. {len(running) - fails}/{len(running)} repointed cleanly to "
          f"{repo or new_url}.")
    if fails == 0:
        print("Ongoing deploys: ensure the new repo's push.sh targets it, then "
              "`fleet.py update` works as before.")
    return 0 if fails == 0 else 1


# ─── Fleet pull (download trades.db / OHLC back to the control server) ────────

def cmd_pull(what, only=None, day=None):
    """Download a file from each targeted box to PULL_DIR, symbol-tagged.
      what='db'   -> options-trader/trades.db          -> pulls/<SYM>_trades.db
      what='ohlc' -> options-trader/data/OHLC/<day>/<SYM>.csv
                                                        -> pulls/<SYM>_OHLC_<day>.csv
    """
    if what == "ohlc" and not day:
        print("pull ohlc needs --day YYYY-MM-DD, e.g.:\n"
              "  python fleet.py pull ohlc --day 2026-07-10 --only IWM")
        return 2
    os.makedirs(PULL_DIR, exist_ok=True)

    fleet = get_fleet(only)
    running = [(s, ip, st) for s, ip, st in fleet if st == "running" and ip]
    if not running:
        print("No running, SSH-reachable boxes to pull from.")
        return 1

    label = "trades.db" if what == "db" else f"OHLC {day}"
    print(f"Pulling {label} from {len(running)} box(es) -> {PULL_DIR}\n")
    ok = 0
    for s, ip, _ in running:
        if what == "db":
            remote = f"{REMOTE_HOME_REL}/trades.db"
            local  = os.path.join(PULL_DIR, f"{s}_trades.db")
        else:
            remote = f"{REMOTE_HOME_REL}/data/OHLC/{day}/{s}.csv"
            local  = os.path.join(PULL_DIR, f"{s}_OHLC_{day}.csv")
        if config.MOCK_AWS:
            print(f"{s:<8}[mock] would scp {remote} -> {local}")
            ok += 1
            continue
        rc, _out, err = ssh_util.scp_pull(ip, remote, local)
        if rc == 0 and os.path.exists(local):
            size = os.path.getsize(local)
            print(f"{s:<8}✅ {os.path.basename(local)} ({size:,} bytes)")
            ok += 1
        else:
            msg = err.strip()[:60] or f"rc={rc}"
            print(f"{s:<8}🚨 {msg}")
    print(f"\nDone. {ok}/{len(running)} pulled into {PULL_DIR}")
    return 0 if ok == len(running) else 1


def main(argv):
    p = argparse.ArgumentParser(description="day_trader_pro fleet SSH fan-out")
    p.add_argument("action", choices=["list", "ping", "run", "update", "repoint", "pull"])
    p.add_argument("command", nargs="?", default=None,
                   help="command string (for 'run'), new repo URL (for 'repoint'), "
                        "or 'db'/'ohlc' (for 'pull')")
    p.add_argument("--only", default=None,
                   help="comma-separated symbols to target (e.g. SPX,QQQ)")
    p.add_argument("--all", action="store_true",
                   help="include stopped boxes (shown as skipped)")
    p.add_argument("--day", default=None,
                   help="pull ohlc: date YYYY-MM-DD to fetch (data/OHLC/<day>/<SYM>.csv)")
    p.add_argument("--no-restart", action="store_true",
                   help="update/repoint: sync only, don't restart the service")
    p.add_argument("--wake", action="store_true",
                   help="update/repoint: start stopped boxes first, then act on them")
    p.add_argument("--check-only", action="store_true",
                   help="repoint: run phase-1 collision check only, change nothing")
    p.add_argument("--yes", action="store_true",
                   help="repoint: skip the confirmation prompt")
    p.add_argument("--mock", action="store_true", help="offline preview")
    args = p.parse_args(argv[1:])

    if args.mock:
        config.set_mock(True)
    only = [s.strip().upper() for s in args.only.split(",")] if args.only else None

    if args.action == "list":
        cmd_list(only)
        return 0
    if args.action == "ping":
        return cmd_ping(only, args.all)
    if args.action == "run":
        if not args.command:
            print("run needs a command, e.g.:  python fleet.py run \"uptime\"")
            return 2
        return cmd_run(args.command, only, args.all)
    if args.action == "update":
        return cmd_update(only, restart=not args.no_restart, wake=args.wake)
    if args.action == "repoint":
        if not args.command:
            print("repoint needs a new repo URL, e.g.:\n"
                  "  python fleet.py repoint https://github.com/TX-9AI/options_trader_v3.git")
            return 2
        return cmd_repoint(args.command, only=only, restart=not args.no_restart,
                           wake=args.wake, check_only=args.check_only,
                           assume_yes=args.yes)
    if args.action == "pull":
        what = (args.command or "").lower()
        if what not in ("db", "ohlc"):
            print("pull needs 'db' or 'ohlc', e.g.:\n"
                  "  python fleet.py pull db --only IWM\n"
                  "  python fleet.py pull ohlc --day 2026-07-10 --only IWM")
            return 2
        return cmd_pull(what, only=only, day=args.day)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
