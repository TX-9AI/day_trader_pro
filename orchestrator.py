# day_trader_pro/orchestrator.py — v0.3.0
# v0.3.0 (2026-07-29) — MORNING REPORT FRESHNESS GUARD + fallback path repaired.
#   Found this reading a report frozen at 2026-07-06 for 23 consecutive mornings
#   in total silence: $DTP_REPORT_JSON was never set, emit.py took its
#   os.getcwd() fallback, and the two projects had been pointing at different
#   files since the variable was invented. Now audits the report's `date` and
#   its `move_ranked` sidecar, Telegrams on either problem, and stamps
#   report_path/report_date/report_stale/report_move_ranked onto the selection so
#   provenance is visible instead of inferred. Proceeds by default (a stale
#   cohort beats not waking 13 boxes); DTP_REPORT_STALE_STRICT=1 fails closed to
#   ALWAYS_ON. Fallback repointed from ~/market_brief/out/report.json — which was
#   misspelled AND pointed at a non-existent out/ subdir, so it never once
#   resolved — to the reporter's real default drop, ~/market-brief/report.json.
#   This is the DURABLE half of the fix: committed code, survives a rebuild,
#   unlike an env var in a gitignored .env that install.sh overwrites.
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


# v0.3.0 — the reporter's REAL default output. emit.py resolves its path as
# explicit arg -> $DTP_REPORT_JSON -> os.getcwd()/report.json, and the service
# runs with WorkingDirectory=<install dir>, so with the env var unset the brief
# lands HERE. The previous fallback pointed at ~/market_brief/out/report.json:
# wrong twice over (underscore for the real hyphenated dir, and an out/ subdir
# that has never existed), so it could never resolve and a missing primary file
# degraded silently to no discretionary selection at all.
_REPORTER_FALLBACKS = (
    "~/market-brief/report.json",
    "~/market_brief/report.json",     # tolerate an underscored checkout
)


def _report_date_et():
    """Today's date in ET as the reporter stamps it (YYYY-MM-DD)."""
    import datetime as _dt
    from zoneinfo import ZoneInfo as _Z
    return _dt.datetime.now(_Z("America/New_York")).strftime("%Y-%m-%d")


def _load_selection():
    """Load report.json and run selector.select(). Never raises — returns a
    baseline-only fallback dict on any failure.

    v0.3.0 STALENESS GUARD. On 2026-07-29 this function was found to have been
    reading a report frozen at 2026-07-06 — 23 days stale — every single morning
    without one word of complaint. $DTP_REPORT_JSON was never set, so emit took
    its cwd fallback and wrote the brief somewhere nothing read, while this
    function kept consuming a static file. Consequences: the same 13 names woke
    daily (the frozen composite scores never changed), and because a report that
    old predates emit v1.3.0's `move_ranked` sidecar, selector's strength lookup
    missed for every symbol and defaulted to 0.3 — so the brief's signed
    sentiment reached the bot's Stage-3 nudge as a CONSTANT, forever.

    The path was the symptom; the silence was the defect. This now ALERTS and
    stamps the result, and by default still proceeds — a stale cohort of liquid
    names is a lesser harm than refusing to wake 13 boxes. Set
    DTP_REPORT_STALE_STRICT=1 to fail closed to ALWAYS_ON instead.
    """
    try:
        import selector
        path = _os.environ.get("DTP_REPORT_JSON") or _os.path.join(
            config.DATA_DIR if hasattr(config, "DATA_DIR") else ".", "report.json")
        used_fallback = None
        if not _os.path.isfile(path):
            for cand in _REPORTER_FALLBACKS:
                cand = _os.path.expanduser(cand)
                if _os.path.isfile(cand):
                    path, used_fallback = cand, cand
                    break
        with open(path) as fh:
            report = _json.load(fh)

        # ── freshness + shape audit (never fatal by default) ────────────────
        today = _report_date_et()
        rdate = str(report.get("date") or "")
        stale = rdate != today
        n_mr = len(report.get("move_ranked") or [])
        problems = []
        if stale:
            problems.append(f"report date {rdate or '(missing)'} != today {today}")
        if n_mr == 0:
            problems.append("no move_ranked sidecar (pre-emit-v1.3.0 or broken) "
                            "-> every brief_strength defaults to 0.3, so the "
                            "Stage-3 sentiment nudge is a constant")
        if used_fallback:
            problems.append(f"primary report path missing; read fallback {used_fallback}")

        if problems:
            msg = ("\u26A0\uFE0F MORNING REPORT PROBLEM | " + " | ".join(problems)
                   + f" | path={path}")
            try:
                notify.send(msg)
            except Exception:  # noqa: BLE001
                pass
            print(f"[selection] {msg}")

        if stale and _os.environ.get("DTP_REPORT_STALE_STRICT", "0") == "1":
            return {"final": list(config.ALWAYS_ON), "discretionary": [],
                    "always_on": list(config.ALWAYS_ON), "brief_strength": {},
                    "ranked": [], "rationale": {}, "confidence": {},
                    "fallback": True, "error": f"stale report ({rdate}); STRICT",
                    "report_path": path, "report_date": rdate,
                    "report_stale": True, "report_move_ranked": n_mr}

        sel = selector.select(report)
        # stamp the audit onto the result so the wake message and the ack can
        # show provenance instead of anyone having to infer it later
        sel.update({"report_path": path, "report_date": rdate,
                    "report_stale": stale, "report_move_ranked": n_mr})
        return sel
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
