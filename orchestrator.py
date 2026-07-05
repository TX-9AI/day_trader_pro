# day_trader_pro/orchestrator.py — v0.1.0
"""
Morning orchestration. Runs on the control server (the reporter box) on a
pre-market systemd timer, AFTER market_brief_v1 has emitted report.json.

Flow:
  1. Gate on trading day (skip weekends/holidays) unless --no-gate.
  2. Load the finished brief (report.json) or generate a sample in mock.
  3. Ask the model which discretionary symbols to wake (selector.select).
  4. Resolve symbols -> instance IDs by tag (instance_registry.resolve).
  5. Start the instances (unless --dry-run/--mock).
  6. Confirm they reach 'running'; page on any that don't.
  7. Telegram the morning's selection + confirmations (or page on failure).

Failure philosophy: a silent failed morning is the worst outcome, so the
selection ack ALWAYS sends, and any resolution/start problem is surfaced
loudly. Selection itself never crashes the run (falls back to SPX+QQQ).

CLI:
  python orchestrator.py --mock --no-gate     # full offline spool-up
  python orchestrator.py --dry-run --no-gate   # real reads, no start
  python orchestrator.py --report /path/report.json
"""

import argparse
import json
import sys

import config
import ec2ops
import instance_registry
import market_calendar
import notify
import selector


def load_report(path):
    with open(path, "r") as fh:
        return json.load(fh)


def run(dry_run=False, gate=True, report_path=None):
    # 1. Trading-day gate
    if gate and not market_calendar.is_trading_day():
        print("Not a trading day; nothing to do.")
        return 0

    # 2. Load brief
    if config.MOCK_LLM or config.MOCK_AWS:
        report = selector.sample_report()
        print("[MOCK] using built-in sample report.")
    else:
        try:
            report = load_report(report_path or config.REPORT_JSON_PATH)
        except Exception as exc:  # noqa: BLE001
            notify.send(f"🚨 *day_trader_pro* could not read the brief "
                        f"({report_path or config.REPORT_JSON_PATH}): {exc}\n"
                        f"Falling back to SPX+QQQ only.")
            report = {"scores": {}}

    # 3. Selection
    sel = selector.select(report)
    final = sel["final"]
    print(f"Selection: {final}  (fallback={sel['fallback']})")

    # 4. Resolve to instance IDs
    resolved, missing = instance_registry.resolve(final)
    if missing:
        notify.send("⚠️ *day_trader_pro* could not resolve instances for: "
                    f"{', '.join(missing)}. Check tags / run reconcile.")

    # 5. Start
    ids = list(resolved.values())
    if dry_run:
        print(f"[DRY-RUN] would start {len(ids)} instances: {resolved}")
        reached = {i: True for i in ids}
    else:
        ec2ops.start(ids)
        reached = ec2ops.wait_state(ids, "running")

    not_running = [iid for iid, ok in reached.items() if not ok]

    # 6/7. Compose and send the morning ack
    msg = _format_ack(sel, resolved, missing, not_running, dry_run)
    notify.send(msg)

    if not_running:
        notify.send("🚨 *day_trader_pro* these instances did NOT reach running "
                    f"within {config.START_CONFIRM_TIMEOUT}s: {not_running}")
        return 1
    return 0


def _format_ack(sel, resolved, missing, not_running, dry_run):
    lines = ["*day_trader_pro — morning wake*"]
    if dry_run:
        lines.append("_(dry run — no instances started)_")
    if sel["fallback"]:
        lines.append(f"⚠️ selection fell back to floor. err: {sel['error']}")
    lines.append(f"Floor: {', '.join(sel['always_on'])}")
    if sel["discretionary"]:
        lines.append("Discretionary:")
        for s in sel["discretionary"]:
            why = sel["rationale"].get(s, "")
            conf = sel["confidence"].get(s)
            conf_s = f" ({conf})" if conf is not None else ""
            lines.append(f"  • {s}{conf_s} — {why}")
    else:
        lines.append("Discretionary: none")
    lines.append(f"Started {len(resolved)} instance(s).")
    if missing:
        lines.append(f"Unresolved: {', '.join(missing)}")
    return "\n".join(lines)


def main(argv):
    p = argparse.ArgumentParser(description="day_trader_pro orchestrator")
    p.add_argument("--mock", action="store_true",
                   help="force full offline mock (AWS+LLM+Telegram)")
    p.add_argument("--dry-run", action="store_true",
                   help="real reads, but do not start instances")
    p.add_argument("--no-gate", action="store_true",
                   help="skip the trading-day gate")
    p.add_argument("--report", default=None, help="path to report.json")
    args = p.parse_args(argv[1:])

    if args.mock:
        config.set_mock(True)

    return run(dry_run=args.dry_run, gate=not args.no_gate,
               report_path=args.report)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
