# day_trader_pro/orchestrator.py — v0.2.0
"""
Morning spool-up. Runs on the control server on a pre-market systemd timer
(dtp-morning.timer, ~09:15 ET) and wakes the daily baseline fleet so it's up
and warming its feed before the 09:30 open.

Flow:
  0. Master switch (control_state) — no-op if control is DISABLED.
  1. Trading-day gate (skip weekends/holidays) unless --no-gate.
  2. Resolve the baseline symbols (config.ALWAYS_ON = SPX + QQQ) to instance IDs.
  3. Start them (unless --dry-run/--mock).
  4. Confirm they reach 'running'; page on any that don't.
  5. Telegram the morning wake summary (always sends; a silent failed morning
     is the worst outcome).

DISCRETIONARY SELECTION RETIRED (v0.2.0): the model-driven "pick the top 5-6
high-conviction names" step was removed. A week of running all 29 showed the
strongest-R trades were NOT the names the model would have selected, so the
pick added complexity and a report/LLM dependency for no proven edge. The
orchestrator now wakes ONLY SPX + QQQ; start any additional names by hand.
No report.json is read and no model is called.

CLI:
  python orchestrator.py --mock --no-gate     # full offline spool-up
  python orchestrator.py --dry-run --no-gate   # real reads, no start
  python orchestrator.py                       # scheduled morning run

Changelog:
  v0.2.0 (2026-07-10) — retire discretionary selection. Wake SPX+QQQ only;
    drop report.json load, selector.select, and all selection-ack fields.
    Removed --report. (Rationale above.)
  v0.1.2 — report-driven selection of up to MAX_DISCRETIONARY names + SPX/QQQ.
"""

import argparse
import sys

import config
import control_state
import ec2ops
import instance_registry
import market_calendar
import notify


def run(dry_run=False, gate=True):
    # 0. Master switch
    if not control_state.is_enabled():
        print("Control is DISABLED — orchestrator no-op. "
              "(python control_state.py enable to turn on)")
        return 0

    # 1. Trading-day gate
    if gate and not market_calendar.is_trading_day():
        print("Not a trading day; nothing to do.")
        return 0

    # 2. Baseline only — SPX + QQQ. No report, no model selection.
    baseline = list(config.ALWAYS_ON)
    print(f"Baseline wake: {baseline}")

    # 3. Resolve to instance IDs
    resolved, missing = instance_registry.resolve(baseline)
    if missing:
        notify.send("⚠️ *day_trader_pro* could not resolve instances for: "
                    f"{', '.join(missing)}. Check tags / run reconcile.")

    # 4. Start
    ids = list(resolved.values())
    if dry_run:
        print(f"[DRY-RUN] would start {len(ids)} instance(s): {resolved}")
        reached = {i: True for i in ids}
    else:
        ec2ops.start(ids)
        reached = ec2ops.wait_state(ids, "running")

    not_running = [iid for iid, ok in reached.items() if not ok]

    # 5. Morning ack (always sends)
    notify.send(_format_ack(baseline, resolved, missing, reached, dry_run))

    if not_running:
        notify.send("🚨 *day_trader_pro* these instances did NOT reach running "
                    f"within {config.START_CONFIRM_TIMEOUT}s: {not_running}")
        return 1
    return 0


def _short(iid):
    return iid[-5:] if iid else "?????"


def _format_ack(baseline, resolved, missing, reached, dry_run):
    """Explicit per-server morning message: which boxes, which IDs, what state."""
    verb = "Would wake" if dry_run else "Woke"
    lines = ["*day_trader_pro — morning wake (SPX + QQQ)*"]
    if dry_run:
        lines.append("_(dry run — nothing was actually started)_")
    lines.append(f"*{verb} {len(resolved)} baseline server(s):*")
    for s in baseline:
        if s not in resolved:
            continue
        iid = resolved[s]
        mark = "•" if dry_run else ("✅" if reached.get(iid) else "🚨")
        lines.append(f"  {mark} {s} [floor] `{_short(iid)}`")
    if missing:
        lines.append(f"⚠️ Unresolved (no live instance): {', '.join(missing)}")
    lines.append("_Discretionary selection retired — start extra names by hand._")
    return "\n".join(lines)


def main(argv):
    p = argparse.ArgumentParser(description="day_trader_pro morning spool-up (SPX+QQQ)")
    p.add_argument("--mock", action="store_true",
                   help="force full offline mock (AWS+Telegram)")
    p.add_argument("--dry-run", action="store_true",
                   help="real reads, but do not start instances")
    p.add_argument("--no-gate", action="store_true",
                   help="skip the trading-day gate")
    args = p.parse_args(argv[1:])

    if args.mock:
        config.set_mock(True)

    return run(dry_run=args.dry_run, gate=not args.no_gate)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
