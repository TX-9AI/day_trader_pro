# day_trader_pro/orchestrator.py — v0.2.1
# v0.2.1 (2026-07-21) — wake message now shows each discretionary box's reporter rank
#   and signal strength/score, plus a 'just missed' near-miss list below the
#   cutoff, to support tuning MAX_DISCRETIONARY from observed signal spread.
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
  v0.3.0 (2026-07-15) — RESTORE report-driven selection at fixed fleet size.
    Wakes ALWAYS_ON (SPX+QQQ) + EXACTLY MAX_DISCRETIONARY (8) discretionary
    names chosen by selector.select() from market_brief's move_ranked (model
    concurs/swaps; deterministic backfill guarantees the count). After each
    box reaches running, writes ~/brief_flags.json onto it (its signed
    move-strength) for the bot's setup-score nudge. Selection failure falls
    back to ALWAYS_ON-only — never blocks the wake.
  v0.2.0 (2026-07-10) — retire discretionary selection. Wake SPX+QQQ only;
    drop report.json load, selector.select, and all selection-ack fields.
    Removed --report. (Rationale above.)
  v0.1.2 — report-driven selection of up to MAX_DISCRETIONARY names + SPX/QQQ.
"""

import argparse
import sys

import config
import json as _json
import os as _os
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

    # 2. Baseline + discretionary. Load the brief, let the model concur on the
    #    reporter's move_ranked, backfill to EXACTLY MAX_DISCRETIONARY.
    baseline = list(config.ALWAYS_ON)
    sel = _load_selection()          # {"final","discretionary","brief_strength",...}
    wake_list = sel["final"]         # baseline + exactly-N discretionary
    brief_strength = sel.get("brief_strength", {})
    if sel.get("fallback"):
        notify.send("⚠️ *day_trader_pro* selection fell back to baseline-only "
                    f"({sel.get('error')}). Waking SPX+QQQ; no discretionary names.")
    print(f"Wake list ({len(wake_list)}): {wake_list}")

    # 3. Resolve to instance IDs
    resolved, missing = instance_registry.resolve(wake_list)
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

    # 4b. Deliver each box its signed move-strength for the setup-score nudge.
    if not dry_run:
        _push_brief_flags(resolved, reached, brief_strength)

    # 5. Morning ack (always sends)
    notify.send(_format_ack(wake_list, baseline, resolved, missing, reached, dry_run, sel))

    if not_running:
        notify.send("🚨 *day_trader_pro* these instances did NOT reach running "
                    f"within {config.START_CONFIRM_TIMEOUT}s: {not_running}")
        return 1
    return 0


def _load_selection():
    """Load report.json and run selector.select(). Never raises — returns a
    baseline-only fallback dict on any failure."""
    try:
        import selector
        path = _os.environ.get("DTP_REPORT_JSON") or _os.path.join(
            config.DATA_DIR if hasattr(config, "DATA_DIR") else ".", "report.json")
        if not _os.path.isfile(path):
            # try the reporter's default drop next to this project
            alt = _os.path.expanduser("~/market_brief/out/report.json")
            path = alt if _os.path.isfile(alt) else path
        with open(path) as fh:
            report = _json.load(fh)
        return selector.select(report)
    except Exception as exc:  # noqa: BLE001
        return {"final": list(config.ALWAYS_ON), "discretionary": [],
                "always_on": list(config.ALWAYS_ON), "brief_strength": {},
                "ranked": [], "rationale": {}, "confidence": {}, "fallback": True,
                "error": f"{type(exc).__name__}: {exc}"}


def _push_brief_flags(resolved, reached, brief_strength):
    """Write ~/brief_flags.json onto each running box: {symbol, strength, date}.
    Best-effort per box; a delivery failure never fails the wake (the bot's
    setup_scorer treats a missing/blank flag as strength 0 = no nudge).
    IPs come from fleet.get_fleet() — the same (symbol, ip, state) source the
    fleet uses for all its SSH."""
    import ssh_util, base64, datetime as _dt
    try:
        import fleet
        ip_by_sym = {s: ip for s, ip, st in fleet.get_fleet()
                     if st == "running" and ip}
    except Exception:  # noqa: BLE001
        return
    today = _dt.date.today().isoformat()
    for sym, iid in resolved.items():
        if not reached.get(iid):
            continue
        ip = ip_by_sym.get(sym)
        if not ip:
            continue
        strength = float(brief_strength.get(sym, 0.0))
        payload = _json.dumps({"symbol": sym, "strength": strength, "date": today})
        b64 = base64.b64encode(payload.encode()).decode()
        cmd = f"echo {b64} | base64 -d > ~/brief_flags.json"
        try:
            ssh_util.ssh_run(ip, cmd, timeout=15)
        except Exception:  # noqa: BLE001
            pass


def _short(iid):
    return iid[-5:] if iid else "?????"


def _fmt_score(r, strength=None):
    """Compact 'str +0.92 sc 88' from a ranked row (+ optional brief strength)."""
    parts = []
    st = r.get("strength") if r.get("strength") is not None else strength
    if st is not None:
        parts.append(f"str {st:+.2f}")
    if r.get("score") is not None:
        parts.append(f"sc {r['score']}")
    return " ".join(parts) if parts else "n/a"


def _format_ack(wake_list, baseline, resolved, missing, reached, dry_run, sel):
    """Per-server morning message with WHY each box was selected: its reporter
    rank and signal strength/score, plus the near-miss names just below the
    cutoff — so the discretionary cutoff can be tuned from what you observe."""
    verb = "Would wake" if dry_run else "Woke"
    disc = [s for s in wake_list if s not in baseline]
    lines = [f"*day_trader_pro — morning wake (2 baseline + {len(disc)} discretionary)*"]
    if dry_run:
        lines.append("_(dry run — nothing was actually started)_")
    lines.append(f"*{verb} {len(resolved)} server(s):*")

    ranked = sel.get("ranked", [])
    rank_by = {r["symbol"]: r for r in ranked}
    strength = sel.get("brief_strength", {})

    # Baseline (floor) first
    for s in baseline:
        if s in resolved:
            iid = resolved[s]
            mark = "•" if dry_run else ("✅" if reached.get(iid) else "🚨")
            lines.append(f"  {mark} {s} [floor] `{_short(iid)}`")

    # Discretionary, in wake order, each with rank + strength/score
    for s in disc:
        if s not in resolved:
            continue
        iid = resolved[s]
        mark = "•" if dry_run else ("✅" if reached.get(iid) else "🚨")
        r = rank_by.get(s, {})
        rk = f"#{r['rank']}" if r.get("rank") else "#?"
        lines.append(f"  {mark} {s} [{rk} {_fmt_score(r, strength.get(s))}] `{_short(iid)}`")

    # Near-miss: highest-ranked names that did NOT make the cut — the boundary
    # you use to judge whether the discretionary count is right.
    misses = [r for r in ranked if not r.get("selected")][:6]
    if misses:
        lines.append("*— cutoff — just missed:*")
        for r in misses:
            lines.append(f"  · {r['symbol']} [#{r['rank']} {_fmt_score(r)}]")

    if missing:
        lines.append(f"⚠️ Unresolved (no live instance): {', '.join(missing)}")
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
