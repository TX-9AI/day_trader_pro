# day_trader_pro/shutdown_manager.py — v0.1.0
"""
End-of-day sweep, run FROM the control server on its own systemd timer
(~16:00 ET, after the trading boxes have closed positions at 15:45 and each
box has already sent its own per-symbol P&L summary at ~15:50).

Why a control-server sweep rather than each box stopping itself:
  - The control server has the authority (IAM) and the whole-fleet view.
  - It catches boxes that CRASHED or hit the catastrophic circuit breaker and
    never reached their own shutdown — those would otherwise burn money all
    night. This is the safety net.

This module STOPS (never terminates). Config, EBS volumes, and persistent
paper/live settings survive the stop and are intact on the next wake.

CLI:
  python shutdown_manager.py --mock       # offline demo
  python shutdown_manager.py --dry-run     # real reads, no stop
"""

import argparse
import sys

import config
import ec2ops
import instance_registry
import notify


def run(dry_run=False):
    # Discover the full trading universe (not the reporter) and find what's up.
    mapping, _ = instance_registry.discover(config.UNIVERSE)
    running = {s: r["instance_id"] for s, r in mapping.items()
               if r.get("state") == "running"}

    if not running:
        notify.send("*day_trader_pro — EOD sweep*\nNo trading instances "
                    "running. Nothing to stop.")
        print("Nothing running.")
        return 0

    ids = list(running.values())
    if dry_run:
        print(f"[DRY-RUN] would stop {len(ids)}: {running}")
        stopped_ok = {i: True for i in ids}
    else:
        ec2ops.stop(ids)
        reached = ec2ops.wait_state(ids, "stopped")
        stopped_ok = reached

    failed = [iid for iid, ok in stopped_ok.items() if not ok]

    lines = ["*day_trader_pro — EOD sweep*"]
    if dry_run:
        lines.append("_(dry run — nothing actually stopped)_")
    lines.append("Stopped: " + ", ".join(sorted(running.keys())))
    if failed:
        lines.append(f"🚨 FAILED to confirm stopped: {failed} — check console.")
    notify.send("\n".join(lines))

    return 1 if failed else 0


def main(argv):
    p = argparse.ArgumentParser(description="day_trader_pro EOD shutdown sweep")
    p.add_argument("--mock", action="store_true", help="force full offline mock")
    p.add_argument("--dry-run", action="store_true",
                   help="real reads, but do not stop instances")
    args = p.parse_args(argv[1:])
    if args.mock:
        config.set_mock(True)
    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
