# day_trader_pro/fleet.py — v0.1.0
"""
Fleet SSH fan-out. Pulls every monitored box's private IP from its tag and
reaches each one, one at a time, from the control server.

This is the general-purpose management plane: connectivity checks, ad-hoc
commands, deploy verification, health pings — anything you'd otherwise SSH
into 29 boxes by hand to do.

Targets RUNNING boxes by default (you can't SSH a stopped instance); use
--all to also list the stopped ones as skipped.

CLI:
    python fleet.py list                        # symbol -> IP -> state (no SSH)
    python fleet.py ping                          # SSH echo-test each running box
    python fleet.py ping --all                    # include stopped (shown skipped)
    python fleet.py run "uptime"                  # run a command on each running box
    python fleet.py run "systemctl is-active optionsbot"
    python fleet.py run "cat ~/eod/pnl_today.json"

    # scope to specific symbols:
    python fleet.py run "uptime" --only SPX,QQQ,NVDA

Add --mock to preview offline.
"""

import argparse
import sys

import config
import instance_registry
import ssh_util


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


def main(argv):
    p = argparse.ArgumentParser(description="day_trader_pro fleet SSH fan-out")
    p.add_argument("action", choices=["list", "ping", "run"])
    p.add_argument("command", nargs="?", default=None,
                   help="command string (for 'run')")
    p.add_argument("--only", default=None,
                   help="comma-separated symbols to target (e.g. SPX,QQQ)")
    p.add_argument("--all", action="store_true",
                   help="include stopped boxes (shown as skipped)")
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
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
