# day_trader_pro/fleet.py — v0.2.1
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

Add --mock to preview offline.
"""

import argparse
import sys
import time

import config
import instance_registry
import ssh_util

INSTALL_DIR = "~/options-trader"
SERVICE     = "optionsbot"


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


def main(argv):
    p = argparse.ArgumentParser(description="day_trader_pro fleet SSH fan-out")
    p.add_argument("action", choices=["list", "ping", "run", "update"])
    p.add_argument("command", nargs="?", default=None,
                   help="command string (for 'run')")
    p.add_argument("--only", default=None,
                   help="comma-separated symbols to target (e.g. SPX,QQQ)")
    p.add_argument("--all", action="store_true",
                   help="include stopped boxes (shown as skipped)")
    p.add_argument("--no-restart", action="store_true",
                   help="update: deploy only, don't restart the service")
    p.add_argument("--wake", action="store_true",
                   help="update: start stopped boxes first, then deploy to them")
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
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
