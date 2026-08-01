# day_trader_pro/eod_conductor.py — v1.11.0
# v1.11.0 (2026-08-01) — +PHASE 5b DAILY BARS. Rebuilds a daily OHLC series per
#   symbol from the 1-minute tape phase_harvest just landed (daily_bars.py v1.0),
#   into daily/<SYM>.csv. Closes item AP: the pitchfork's DAILY fork had no data
#   source — TIMEFRAMES["1d"] serves 10 bars and §4.2 needs k=2 with R=40 — which
#   also blocked §6's daily/hourly confluence, the highest-value signal the
#   overlay was to produce.
#   NOT a yfinance pull, deliberately. yfinance was purged for a large disparity
#   against TastyTrade on low timeframes; a fractal pivot anchors on HIGHS AND
#   LOWS, and its "30 day" 1m pull caps at 21 sessions. The decisive objection is
#   invalidation: re-anchoring a dead fork selects a NEW triple and needs bars
#   CURRENT AT THAT MOMENT, so a manual pull is stale the next day and a
#   recurring one re-introduces the dependency the purge removed. Aggregating our
#   own tape extends itself and keeps the fork reconstructible from tape.
#   REBUILDS rather than appends — idempotent, and self-heals when a session is
#   backfilled late, which an append would silently get wrong forever.
#   Placed AFTER phase_backfill, not after phase_harvest: backfill fetches
#   candles for days the boxes never handed over, so aggregating earlier would
#   build daily bars from tape that is about to get more complete. Control-side,
#   so it does NOT need the boxes-still-up window. It is a PHASE and not a manual
#   command for the standing reason: a step someone has to remember is a step
#   that stops happening.
# v1.10.0 (2026-07-30) — +PHASE 2b/4b ARCHIVE GAP RECOVERY, run TWICE per night at
#   the two moments boxes are actually up. 2b: the traders, after phase_harvest
#   and BEFORE phase_report stops them — logs first, then the lights go out.
#   4b: the sat-out boxes, right after phase_backfill wakes them five at a time
#   for candles; while they are up they hand over anything control never pulled.
#   WHY: the makedirs defect meant nothing reached signal_journal/ or
#   chain_snapshots/ before 07-27, while the boxes wrote from 07-18 and 07-23 and
#   NEITHER WRITER PRUNES — five sessions of journal and two of chains were
#   sitting on the fleet, invisible to every tool needing them. Item E's Aug 1
#   retro ledger assumes journal "since 07-18" and would have queried a third of
#   its sample without a word. Recovering by hand fixes today; a gap SCAN fixes
#   it whenever it recurs. Uses ohlc/ as the reference set (the one root that has
#   never had a gap), skips dates before each writer existed, pulls journal+chains
#   ONLY (never re-touches correct OHLC), caps at DTP_MAX_RECOVERY_DATES=4 per
#   night so a backlog drains over several runs, and warns-never-stops.
# v1.9.0 (2026-07-30) — +PHASE 12 EVM. Earned value against docs/BACKLOG.md every
#   night, so a schedule slip is visible while it is still small. Reports TWO
#   indices on purpose: SPI(all) is calendar truth, SPI(desk) is accountability —
#   of the work that was ours to move, how much moved. A late [DESK·DATA] item is
#   a DC&A dependency, not an execution failure, and averaging them yields a
#   number nobody can act on. Only a DESK slip WARNS, because it is the only
#   variance effort can fix; data waits get re-dated, never compressed.
# v1.8.0 (2026-07-30) —
# v1.8.0 (2026-07-30) — +PHASE 10 SWALLOW and +PHASE 11 VWAP, both control-side,
#   both added under a standing rule: ANYTHING that has to happen around the EOD
#   chain belongs IN the conductor, never in a command someone has to remember —
#   INCLUDING a one-time check, and it gets recorded here for posterity so there
#   is a record that it ran and why it was added.
#   PHASE 10 SWALLOW — nightly silent-failure census (backlog W.2) via
#     options_trader_v3 tests/swallow_audit.py. Writes
#     reports/swallow_audit_<date>.json and WARNS when the silent-handler count
#     rises against the newest earlier snapshot, i.e. when someone adds a new
#     exception handler that swallows without logging. The week of 2026-07-27
#     produced eight defects of exactly that shape; a census nobody runs would
#     have caught none of them.
#   PHASE 11 VWAP — nightly VWAP orientation ledger (evidence for backlog item
#     E) via tests/vwap_orientation_ledger.py. Writes
#     reports/vwap_orientation_<date>.txt and echoes the per-strategy verdicts.
#     E must not be BUILT until the evidence says which direction the gate
#     belongs in — VWAP alignment is a trend filter and Sweep Reversal enters
#     counter to extension by design — and evidence that accrues only when
#     someone remembers to run a script will not exist on decision day.
#   Both are read-only, stdlib-only, warn-never-stop, and skippable via
#   --no-swallow / --no-vwap.
# v1.7.0 (2026-07-29) — HARVEST COMPLETENESS: this phase asserted only that
#   ohlc/<date> was non-empty and logged ✅ on that alone. It did so on
#   2026-07-29 with signal_journal and chain_snapshots both empty — and empty for
#   three sessions running. Every artifact class is now checked while the fleet
#   is STILL UP (this chain stops the boxes, so the next morning is too late),
#   each miss naming its recovery command, and harvest v0.6.0's per-box manifest
#   is read so a genuinely quiet box never pages while a FAILED pull always does.
# v1.6.0 (2026-07-27) — PHASE 9 READINESS: nightly readiness digest from the
#   harvested signal journal (otv3 tests/readiness_digest.py --quiet), warn-
#   never-stop, Telegram headline (🧭), --no-readiness to skip. Pairs with
#   harvest v0.5.0 (journal pull) — together they close the 07-18 journal-
#   harvest deferral and make readiness dial-tuning fully unattended.
# day_trader_pro/eod_conductor.py — v1.5.1
# v1.5.1 (2026-07-23) — BACKFILL now reads eod_backfill.run()'s RETURN CODE.
#   It previously discarded it, so a cap-guard refusal (rc=2 — boxes still
#   running, i.e. REPORT did not stop them all) fell through to the generic
#   "still without candles — DXFeed history may be gone" warning. That
#   MISATTRIBUTED the cause and would send the operator chasing a feed problem
#   that did not exist. rc=2 now emits its own warning naming the real cause and
#   the recovery command; rc=1 (some symbols unrecoverable) keeps the DXFeed
#   wording, which is accurate for that case. Behaviour otherwise identical —
#   diagnosis only, no control-flow change.
# v1.5.0 (2026-07-23) — NEW final phase 8 TABLES: runs the options_trader_v3
#   tool tests/conditional_tables.py (--quiet) over the accumulated per-symbol
#   trade DBs, so the ROADMAP L3.4 conviction-bar substrate builds itself
#   nightly instead of depending on a manual run. Cumulative BY DESIGN — it
#   re-reads every session on disk each night, because a conditional cell only
#   becomes decision-grade as sample accrues; the artifact is one rolling
#   reports/conditional_tables_<first>_<last>.{txt,jsonl}. Lives in the otv3
#   repo (same precedent as tests/a2_cooccurrence.py, devtools item 47) and is
#   invoked from the checkout at ~/options-trader-v3; stdlib-only, so it falls
#   back to this interpreter when that venv is absent. Read-only against the
#   DBs. Warn-never-stop; a missing checkout is a warning, not a failure.
# v1.4.0 (2026-07-23) — NEW phase_label: runs auto_label.py after consolidate
#   so Tier-B session labels (ROADMAP L1.6/L1.7) accumulate automatically
#   instead of depending on a manual daily habit. Warn-never-stop.
# v1.3.0 — 2026-07-16 — NEW final phase 7 EXCURSION: runs excursion_report.py
#          over the day's harvested per-symbol DBs (MFE/MAE distributions →
#          reports/excursions_<date>.txt) and Telegrams the headline. ALWAYS
#          runs (recovery-path rule); any failure is a loud warning, never a
#          stop. DTP_EXCURSION_LIVE=1 additionally produces the live-rows
#          report (written with a _live suffix once live boxes exist).
# v1.2.0 — 2026-07-15 — box-state-independent recovery: BACKFILL/CONSOLIDATE/REGIME
#          ALWAYS run regardless of whether traded boxes are up/down/never-ran; the
#          upstream gate/harvest/report steps now WARN-and-proceed instead of halting,
#          so box state can never block the candle recovery. (Same code as the v1.1.0
#          fix; version re-stamped for deploy clarity.)
# v1.0.1 — 2026-07-15 — regime phase calls nightly_regime.sh (today + gap-day sweep).
# v1.0.0 — 2026-07-11 — initial gated conductor.
"""
End-of-day conductor (control server). ONE ordered chain that calls the existing
helpers in sequence — it sequences them, it rewrites none of them.

v1.1.0 principle: the WHOLE point of EOD is to end up with complete tape + diary,
so the recovery path (BACKFILL → CONSOLIDATE → REGIME) ALWAYS runs — regardless of
whether the traded boxes are up, down, never ran, or errored. The upstream steps
(gate/harvest/report) only act on boxes that are actually running; if there's
nothing to collect they SKIP, and any problem is a LOUD WARNING, never a dead-end.
Every warning is surfaced (Telegram + stderr) and rolled into the final summary so
nothing fails silently — but box state can never stop the candle recovery.

Order:
  1. GATE        — if traded boxes are up, wait until they've produced pnl/trades
                   JSON + OHLC; laggards after the timeout are a warning, not a stop.
  2. HARVEST     — if boxes are up: pull trades.db + OHLC + trade JSON, consolidate.
                   No boxes up ⇒ skip (backfill will fetch the candles).
  3. REPORT      — if boxes are up: unified P&L Telegram, then stop them.
  4. BACKFILL    — ALWAYS: wake the sat-out symbols in batches, produce → pull →
                   stop, until every symbol's OHLC is on the server.
  5. CONSOLIDATE — ALWAYS: fleet_trades bundle over whatever tape is present.
  6. REGIME      — ALWAYS: nightly_regime.sh (replay + diary + gap-day sweep).
  7. EXCURSION   — ALWAYS: excursion_report.py over the harvested trade DBs
                   (MFE/MAE per exit reason + floor/leash verdicts) →
                   reports/excursions_<date>.txt, headline to Telegram.
  8. TABLES      — ALWAYS: conditional_tables.py (otv3) over EVERY session on
                   disk — P(win) + fee-adjusted expectancy per conditioning
                   cell with Wilson 95% intervals → reports/
                   conditional_tables_<first>_<last>.{txt,jsonl}, headline to
                   Telegram. The L3.4 bar-placement substrate. Runs last
                   because it wants the day's DBs already landed.

CLI:
  python eod_conductor.py              # full chain for today
  python eod_conductor.py --date D
  python eod_conductor.py --dry-run
  python eod_conductor.py --batch 5
  python eod_conductor.py --no-regime
  python eod_conductor.py --no-tables   # skip the conditional-tables phase
  python eod_conductor.py --no-swallow  # skip the silent-failure census
  python eod_conductor.py --no-vwap     # skip the VWAP orientation ledger

Env:
  DTP_EXCURSION_LIVE=1        also produce the live excursion report
  DTP_OTV3_DIR=<path>         override the options_trader_v3 checkout location
  CT_FEES_RT_PER_CONTRACT=..  fee-adjust the conditional-table expectancy
  DTP_CT_MIN_N=<int>          min sample before a cell is headline-eligible
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import config
import consolidate_trades
import daily_bars
import eod_backfill
import eod_report
import harvest
import instance_registry
import notify
import ssh_util

_ET = ZoneInfo("US/Eastern")
REMOTE_REPO = "options-trader"
NIGHTLY_REGIME = os.path.expanduser("~/day_trader_pro/nightly_regime.sh")

GATE_TIMEOUT = 420
GATE_POLL = 15


def _today_et():
    return datetime.now(_ET).strftime("%Y-%m-%d")


def _log(tag, msg):
    print(f"[{tag:<11}] {msg}", flush=True)


def _warn(warns, phase, msg):
    """Loud, non-fatal: log + Telegram + record for the summary. Never stops the chain."""
    _log(phase, f"⚠️ {msg}")
    warns.append(f"{phase}: {msg}")
    try:
        notify.send(f"⚠️ EOD conductor [{phase}] {msg}")
    except Exception:  # noqa: BLE001
        pass


# ── 1. GATE ───────────────────────────────────────────────────────────────────
def _box_ready(ip, sym, date):
    cmd = (f'D={date}; test -s ~/eod/pnl_today.json && test -s ~/eod/trades_today.json '
           f'&& f=~/{REMOTE_REPO}/data/OHLC/$D/{sym}.csv && [ -s "$f" ] '
           f'&& [ "$(wc -l < "$f")" -gt 1 ] && echo READY || echo WAIT')
    rc, out, _e = ssh_util.ssh_run(ip, cmd)
    return rc == 0 and "READY" in out


def phase_gate(running, date, dry, warns):
    if not running:
        _log("GATE", "no traded boxes up — nothing to wait on")
        return
    _log("GATE", f"waiting on {len(running)} traded box(es): {', '.join(sorted(running))}")
    if dry:
        _log("GATE", "[dry] would poll each box for pnl/trades JSON + OHLC csv")
        return
    deadline = time.time() + GATE_TIMEOUT
    pending = dict(running)
    while pending and time.time() < deadline:
        for sym in list(pending):
            if _box_ready(pending[sym], sym, date):
                pending.pop(sym)
        if pending:
            time.sleep(GATE_POLL)
    if pending:
        _warn(warns, "GATE", f"{len(pending)} box(es) never finished producing "
                             f"({', '.join(sorted(pending))}) — proceeding; backfill covers OHLC")
    else:
        _log("GATE", "✅ all traded boxes have produced")


# ── 2. HARVEST ────────────────────────────────────────────────────────────────
def phase_harvest(date, running, dry, warns):
    if not running:
        _log("HARVEST", "no traded boxes up — skipping (backfill will fetch missing candles)")
        return
    if dry:
        _log("HARVEST", "[dry] would run harvest.py (pull + consolidate)")
        return
    _log("HARVEST", "harvest.py — pull trades.db + OHLC + trade JSON, consolidate")
    try:
        harvest.run(quiet=False)
    except Exception as exc:  # noqa: BLE001
        _warn(warns, "HARVEST", f"harvest.run raised: {exc} — proceeding to backfill")
        return
    od = os.path.join(config.OHLC_DIR, date)
    if not (os.path.isdir(od) and os.listdir(od)):
        _warn(warns, "HARVEST", "boxes were up but no OHLC came back — backfill will retry")
    else:
        _log("HARVEST", "✅ raw trades/ + ohlc/ populated")

    # v1.7.0 COMPLETENESS — this phase used to assert ONLY that ohlc/<date> was
    # non-empty and logged ✅ on that basis. On 2026-07-29 it did exactly that
    # while signal_journal and chain_snapshots were both EMPTY, and had been for
    # three sessions (harvest was pulling into directories nothing had created).
    # The boxes shut themselves down at the end of this chain, so a gap noticed
    # the next morning is a gap noticed too late: every artifact class is checked
    # HERE, while the fleet is still up.
    for _cls, _root, _why in (
            ("signal_journal", os.path.join(config.BASE_DIR, "signal_journal"),
             "L3 rejection ledger + readiness digest read this"),
            ("chain_snapshots", os.path.join(config.BASE_DIR, "chain_snapshots"),
             "CANNOT be reconstructed after 16:00")):
        _dir = os.path.join(_root, date)
        _n = len(os.listdir(_dir)) if os.path.isdir(_dir) else 0
        if _n == 0:
            _warn(warns, "HARVEST",
                  f"{_cls}/{date} is EMPTY — {_why}. Boxes are still up NOW; the "
                  f"files live on the box at ~/options-trader/data/{_cls}/{date}/ "
                  f"and can be recovered later with: python harvest.py --date {date}")
        else:
            _log("HARVEST", f"✅ {_cls}: {_n} file(s)")

    # harvest v0.6.0's manifest distinguishes a quiet box (absent) from a broken
    # pull (failed). Only `failed` is a defect; page on it alone.
    try:
        _rep = os.path.join(config.REPORTS_DIR, f"daily_trades_{date}.json")
        with open(_rep) as _fh:
            _pf = json.load(_fh).get("fleet", {}).get("manifest", {}).get("pull_failures", [])
        if _pf:
            _warn(warns, "HARVEST",
                  f"{len(_pf)} artifact pull(s) FAILED (not merely absent): "
                  f"{', '.join(_pf[:8])}{' …' if len(_pf) > 8 else ''}")
    except Exception:  # noqa: BLE001
        pass          # pre-v0.6.0 report, or no report — nothing to assert


# Writers' first-release dates. A date before these CANNOT have the artifact, so
# the gap scan must not chase it forever. signal_journal v1.0 = 2026-07-18,
# chain_snapshot v1.0 = 2026-07-23 (both verified in their module headers).
ARTIFACT_EPOCH = {"signal_journal": "2026-07-18", "chain_snapshots": "2026-07-23"}
MAX_RECOVERY_DATES = int(os.environ.get("DTP_MAX_RECOVERY_DATES", "4"))


def _archive_gaps():
    """Dates present in ohlc/ but MISSING (or empty) in an artifact root.

    ohlc/ is the reference because it is the one root that has never had a gap —
    every trading day since 2026-07-13 is there. Anything in it that is absent
    from signal_journal/ or chain_snapshots/ is a genuine hole.
    """
    ohlc_root = config.OHLC_DIR
    if not os.path.isdir(ohlc_root):
        return {}
    sessions = sorted(d for d in os.listdir(ohlc_root)
                      if re.match(r"^\d{4}-\d{2}-\d{2}$", d)
                      and os.path.isdir(os.path.join(ohlc_root, d)))
    gaps = {}
    for root, epoch in ARTIFACT_EPOCH.items():
        missing = []
        for d in sessions:
            if d < epoch:
                continue                       # writer did not exist yet
            p = os.path.join(config.BASE_DIR, root, d)
            if not os.path.isdir(p) or not os.listdir(p):
                missing.append(d)
        if missing:
            gaps[root] = missing
    return gaps


def phase_archive_recovery(dry, warns, scope):
    """Phase 2b / 4b — SELF-HEALING ARCHIVE GAP RECOVERY, run while boxes are up.

    scope = "traders"  -> the 15 that traded today, still up after phase_harvest
                          and BEFORE phase_report stops them.
    scope = "satouts"  -> the sat-out boxes woken five at a time by phase_backfill
                          to fetch candles; while they are up they also hand over
                          any journal/chain dates control never pulled.

    WHY THIS EXISTS: the makedirs defect meant NOTHING was pulled into
    signal_journal/ or chain_snapshots/ before 2026-07-27, while the boxes wrote
    continuously from 07-18 and 07-23. Neither writer prunes, so five sessions of
    journal and two of chains were sitting on the fleet, unreachable to every
    tool that needs them — item E's Aug 1 retro ledger assumes journal "since
    07-18" and would have run against a third of its sample without saying so.
    Recovering that by hand once fixes today; a gap SCAN fixes it whenever it
    happens again, which is the difference between a chore and a guard.

    Pulls ONLY journal + chains. OHLC is the reference set and is never touched.
    Capped at MAX_RECOVERY_DATES per run so a long backlog drains over several
    nights instead of hammering the fleet in one. Warn-never-stop.
    """
    gaps = _archive_gaps()
    if not gaps:
        _log("RECOVER", f"[{scope}] no archive gaps — journal + chains complete")
        return
    todo = sorted({d for ds in gaps.values() for d in ds})[:MAX_RECOVERY_DATES]
    for root, ds in gaps.items():
        _log("RECOVER", f"[{scope}] {root}: {len(ds)} session(s) missing "
                        f"({ds[0]} … {ds[-1]})")
    if dry:
        _log("RECOVER", f"[dry] would back-harvest {todo} (journal+chains only)")
        return
    ok = 0
    for d in todo:
        try:
            res = harvest.backharvest(d, quiet=True,
                                      artifacts=("journal", "chains"))
        except Exception as exc:  # noqa: BLE001
            _warn(warns, "RECOVER", f"[{scope}] {d} raised: {exc}")
            continue
        if res is None:
            _log("RECOVER", f"[{scope}] {d}: no boxes running — deferred")
            continue
        got = len(res.get("journal", {}).get("ok", [])) + \
              len(res.get("chains", {}).get("ok", []))
        failed = len(res.get("journal", {}).get("failed", [])) + \
                 len(res.get("chains", {}).get("failed", []))
        ok += 1
        _log("RECOVER", f"[{scope}] {d}: recovered {got} file(s)"
                        + (f", {failed} FAILED" if failed else ""))
        if failed:
            _warn(warns, "RECOVER", f"[{scope}] {d}: {failed} pull(s) FAILED "
                                    f"(not merely absent)")
    remaining = sum(len(v) for v in gaps.values()) - ok
    if remaining > 0:
        _log("RECOVER", f"[{scope}] {remaining} session(s) still to recover — "
                        f"next run continues (cap {MAX_RECOVERY_DATES}/night)")


# ── 3. REPORT ─────────────────────────────────────────────────────────────────
def phase_report(running, dry, warns):
    if not running:
        _log("REPORT", "no traded boxes up — skipping P&L/stop")
        return
    if dry:
        _log("REPORT", "[dry] would run eod_report.py (P&L + stop traded boxes)")
        return
    _log("REPORT", "eod_report.py — unified P&L, then stop the traded boxes")
    try:
        rc = eod_report.run(dry_run=False)
    except Exception as exc:  # noqa: BLE001
        _warn(warns, "REPORT", f"eod_report raised: {exc}")
        return
    if rc != 0:
        _warn(warns, "REPORT", f"rc={rc} — a box may not have stopped (backfill's cap guard protects it)")
    else:
        _log("REPORT", "✅ P&L sent + traded boxes stopped")


# ── 4. BACKFILL (always) ──────────────────────────────────────────────────────
def phase_backfill(date, batch, dry, warns):
    _log("BACKFILL", f"eod_backfill.py — sat-out symbols, {batch} at a time")
    if dry:
        eod_backfill.run(date=date, batch=batch, dry=True)
        return []
    try:
        rc = eod_backfill.run(date=date, batch=batch)
    except Exception as exc:  # noqa: BLE001
        _warn(warns, "BACKFILL", f"eod_backfill raised: {exc}")
        return []

    still = eod_backfill._missing(date)

    # rc=2 is the pre-flight CAP GUARD, not a data problem: boxes were still
    # running when backfill started, so it refused before touching anything.
    # In the normal chain REPORT has already stopped them, so this means REPORT
    # partially failed. Name that, or the generic warning below sends the
    # operator after DXFeed for a fleet-state problem.
    if rc == 2:
        _warn(warns, "BACKFILL",
              f"cap guard refused — boxes still running (REPORT did not stop "
              f"them all), so NO candles were pulled and {len(still)} symbol(s) "
              f"are short ({', '.join(still) or 'none'}). This is NOT a DXFeed "
              f"issue: stop the fleet, then re-run "
              f"`python3 eod_backfill.py --date {date}`")
        return still

    if still:
        _warn(warns, "BACKFILL", f"{len(still)} symbol(s) still without candles "
                                 f"({', '.join(still)}) — DXFeed history may be gone")
    else:
        _log("BACKFILL", "✅ every symbol has OHLC on the server")
    return still


# ── 5. CONSOLIDATE (always) ───────────────────────────────────────────────────
def phase_consolidate(date, dry, warns):
    if dry:
        _log("CONSOLIDATE", "[dry] would run consolidate_trades.py over the tape present")
        return
    _log("CONSOLIDATE", "consolidate_trades.py — fleet_trades bundle")
    try:
        _b, out_json, _c = consolidate_trades.consolidate(date=date)
    except Exception as exc:  # noqa: BLE001
        _warn(warns, "CONSOLIDATE", f"raised: {exc}")
        return
    if out_json and os.path.exists(out_json):
        _log("CONSOLIDATE", f"✅ {os.path.basename(out_json)}")
    else:
        _log("CONSOLIDATE", "no trades to bundle (tape-only day)")


# ── 5b. DAILY BARS (always; control-side, AFTER backfill) ────────────────────
def phase_daily_bars(dry, warns):
    """Rebuild daily/<SYM>.csv from the 1-minute tape. Item AP.

    Cheap and idempotent: it recomputes the whole series every night rather than
    appending, so a late backfill or re-harvest heals itself instead of leaving a
    bar computed from partial tape sitting in the series with nothing to flag it.
    Sessions built from short tape are marked in a `partial` column rather than
    dropped, so the gap stays visible to whoever anchors on them.
    """
    if dry:
        _log("DAILY", "[dry] would rebuild daily/<SYM>.csv from ohlc/ tape")
        return
    _log("DAILY", "daily_bars.py — rebuild daily series from 1m tape")
    try:
        written = daily_bars.rebuild()
    except Exception as exc:  # noqa: BLE001
        _warn(warns, "DAILY", f"daily_bars.rebuild raised: {exc}")
        return
    if not written:
        _warn(warns, "DAILY", "no tape found — daily series NOT updated")
        return
    bars = max(written.values())
    _log("DAILY", f"✅ {len(written)} symbols, {bars} sessions")
    # Stated every night until it clears, so the pitchfork's blocker cannot be
    # quietly forgotten and then rediscovered when a fork fails to build.
    if bars < 15:
        _warn(warns, "DAILY",
              f"only {bars} sessions — a k=2 daily fork needs ~15 (P2 confirmed "
              f"at index 14). Fills at one bar per session; not actionable.")


# ── 6. REGIME (always) ────────────────────────────────────────────────────────
def phase_regime(dry, warns):
    if dry:
        _log("REGIME", f"[dry] would run bash {NIGHTLY_REGIME} (replay + diary + backfill sweep)")
        return
    if not os.path.isfile(NIGHTLY_REGIME):
        _warn(warns, "REGIME", f"{NIGHTLY_REGIME} not found — diary NOT updated")
        return
    _log("REGIME", f"{NIGHTLY_REGIME} — replay + diary + gap-day sweep over complete tape")
    try:
        rc = subprocess.run(["bash", NIGHTLY_REGIME], timeout=1800).returncode
    except Exception as exc:  # noqa: BLE001
        _warn(warns, "REGIME", f"nightly_regime.sh raised: {exc}")
        return
    if rc not in (0, 2):
        _warn(warns, "REGIME", f"nightly_regime.sh rc={rc}")
    else:
        _log("REGIME", f"✅ diary upserted + gap sweep done (rc={rc})")


AUTO_LABEL_PY = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "auto_label.py")


def phase_label(date, dry, warns):
    """v1.4.0 — Tier-B session labeling, automated (ROADMAP L1.8/L1.6/L1.7).

    Was a manual 10-minute EOD habit via label_day.sh, which also could not
    label the archived past. auto_label.py derives the labels from RAW PRICE
    ACTION only — it imports nothing from the regime stack, so the labels stay
    independent ground truth for validating regime_confluence rather than a
    restatement of its output. Rows are tagged source="auto"; a human override
    via label_day.sh writes the same date and wins downstream.

    Warn-never-stop, like every other phase.
    """
    if dry:
        _log("LABEL", f"[dry] would run {AUTO_LABEL_PY} --date {date}")
        return
    if not os.path.isfile(AUTO_LABEL_PY):
        _warn(warns, "LABEL", f"{AUTO_LABEL_PY} not found — session NOT labeled")
        return
    _log("LABEL", f"auto_label.py --date {date} (Tier-B labels from price action)")
    try:
        rc = subprocess.run([sys.executable, AUTO_LABEL_PY, "--date", date],
                            timeout=600).returncode
    except Exception as exc:  # noqa: BLE001
        _warn(warns, "LABEL", f"auto_label.py raised: {exc}")
        return
    if rc != 0:
        _warn(warns, "LABEL", f"auto_label.py rc={rc}")
    else:
        _log("LABEL", "✅ session labeled")


EXCURSION_PY = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "excursion_report.py")


def phase_excursion(date, dry, warns):
    """Phase 7 — MFE/MAE excursion report over the day's harvested DBs.
    Runs AFTER harvest/consolidate so trades/<date>/ is as complete as it will
    get. Non-fatal by the recovery-path rule: a failed report is a loud
    warning, never a stop. Telegrams the headline so the report arrives even
    when nobody remembers to ask for it."""
    if dry:
        _log("EXCURSION", f"[dry] would run excursion_report.py --date {date} "
                          f"(paper; +live if DTP_EXCURSION_LIVE=1)")
        return
    if not os.path.isfile(EXCURSION_PY):
        _warn(warns, "EXCURSION", f"{EXCURSION_PY} not found — report NOT written")
        return
    modes = [[]]
    if os.environ.get("DTP_EXCURSION_LIVE", "") == "1":
        modes.append(["--live"])
    for extra in modes:
        label = "live" if extra else "paper"
        _log("EXCURSION", f"excursion_report.py --date {date} ({label})")
        try:
            proc = subprocess.run(
                [sys.executable, EXCURSION_PY, "--date", date] + extra,
                capture_output=True, text=True, timeout=180)
        except Exception as exc:  # noqa: BLE001
            _warn(warns, "EXCURSION", f"excursion_report.py ({label}) raised: {exc}")
            continue
        if proc.returncode != 0:
            _warn(warns, "EXCURSION",
                  f"excursion_report.py ({label}) rc={proc.returncode}: "
                  f"{(proc.stderr or '').strip()[:200]}")
            continue
        headline = next((ln for ln in proc.stdout.splitlines() if ln.strip()), "")
        _log("EXCURSION", f"✅ {headline}")
        try:
            notify.send(f"📐 {headline} → reports/excursions_{date}"
                        f"{'_live' if extra else ''}.txt")
        except Exception:  # noqa: BLE001
            pass


OTV3_DIR = os.environ.get("DTP_OTV3_DIR",
                          os.path.expanduser("~/options-trader-v3"))


def phase_tables(dry, warns):
    """Phase 8 — conditional-probability tables (ROADMAP L3.4 substrate).

    Deliberately CUMULATIVE: no --date is passed, so every session on disk is
    re-binned each night. That is the point — a cell like
    "ORB x TRENDING_BULL x grade A" is noise at n=6 and decision-grade at n=60,
    and only calendar time moves it. The tool prints one honest headline in
    --quiet mode: it names a cell ONLY when that cell's Wilson 95% interval has
    cleared 50%, and otherwise says nothing has separated from chance — which
    is the expected message for the first weeks.

    The tool lives in the options_trader_v3 repo (analysis tooling belongs with
    the engine it analyses — same rule as tests/a2_cooccurrence.py). It is
    stdlib-only and read-only against the trade DBs, so it cannot disturb the
    chain; per the recovery-path rule any failure here is a loud warning and
    never a stop.
    """
    script = os.path.join(OTV3_DIR, "tests", "conditional_tables.py")
    if dry:
        _log("TABLES", f"[dry] would run {script} --quiet (all sessions on disk)")
        return
    if not os.path.isfile(script):
        _warn(warns, "TABLES", f"{script} not found — is {OTV3_DIR} checked out? "
                               f"conditional tables NOT updated")
        return
    venv_py = os.path.join(OTV3_DIR, "venv", "bin", "python")
    py = venv_py if os.access(venv_py, os.X_OK) else sys.executable
    cmd = [py, script, "--quiet",
           "--trades-root",  config.TRADES_DIR,
           "--reports-dir",  config.REPORTS_DIR,
           "--journal-root", os.path.join(config.BASE_DIR, "signal_journal"),
           "--min-n",        os.environ.get("DTP_CT_MIN_N", "5")]
    _log("TABLES", "conditional_tables.py --quiet (cumulative, all sessions)")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except Exception as exc:  # noqa: BLE001
        _warn(warns, "TABLES", f"conditional_tables.py raised: {exc}")
        return
    if proc.returncode != 0:
        _warn(warns, "TABLES", f"conditional_tables.py rc={proc.returncode}: "
                               f"{(proc.stderr or '').strip()[:200]}")
        return
    headline = next((ln for ln in proc.stdout.splitlines() if ln.strip()), "")
    _log("TABLES", f"✅ {headline}")
    try:
        notify.send(f"🎲 {headline}")
    except Exception:  # noqa: BLE001
        pass


def phase_swallow(date, dry, warns):
    """Phase 10 — nightly SILENT-FAILURE CENSUS (backlog W.2).

    Runs options_trader_v3's tests/swallow_audit.py, writes a dated JSON
    snapshot, and compares the silent-handler count against the most recent
    prior snapshot. A rise means a new exception handler that swallows without
    logging was added since last night.

    WHY THIS IS A CONDUCTOR PHASE AND NOT A COMMAND SOMEONE RUNS: the week of
    2026-07-27 produced eight defects that all shared one shape — code that
    failed without saying so. The census that finds them is worthless if it
    depends on anyone remembering to run it, which is the same reasoning that
    put the completeness check in phase_harvest. A one-off check that matters
    is a phase; a check nobody runs is a comment.

    Control-side, read-only, static analysis — it never imports the code it
    audits and never touches a box. Warn-never-stop per the recovery-path rule.
    """
    script = os.path.join(OTV3_DIR, "tests", "swallow_audit.py")
    out = os.path.join(config.REPORTS_DIR, f"swallow_audit_{date}.json")
    if dry:
        _log("SWALLOW", f"[dry] would run {script} --json -> {out}")
        return
    if not os.path.isfile(script):
        _warn(warns, "SWALLOW", f"{script} not found — census NOT run")
        return
    venv_py = os.path.join(OTV3_DIR, "venv", "bin", "python")
    py = venv_py if os.access(venv_py, os.X_OK) else sys.executable
    try:
        proc = subprocess.run([py, script, "--json", "--root", OTV3_DIR],
                              capture_output=True, text=True, timeout=180)
    except Exception as exc:  # noqa: BLE001
        _warn(warns, "SWALLOW", f"swallow_audit.py raised: {exc}")
        return
    if proc.returncode != 0:
        _warn(warns, "SWALLOW", f"swallow_audit.py rc={proc.returncode}: "
                                f"{(proc.stderr or '').strip()[:200]}")
        return
    try:
        rows = json.loads(proc.stdout)
    except Exception as exc:  # noqa: BLE001
        _warn(warns, "SWALLOW", f"unparseable census output: {exc}")
        return
    os.makedirs(config.REPORTS_DIR, exist_ok=True)
    with open(out, "w") as fh:
        json.dump(rows, fh, indent=1, sort_keys=True)

    silent = sum(1 for r in rows if str(r.get("loudness", "")).startswith("SILENT"))
    t1 = sum(1 for r in rows
             if r.get("tier") == 0 and str(r.get("loudness", "")).startswith("SILENT"))
    # compare against the newest EARLIER snapshot, whatever date it carries
    prior, prior_silent = None, None
    try:
        snaps = sorted(f for f in os.listdir(config.REPORTS_DIR)
                       if f.startswith("swallow_audit_") and f.endswith(".json")
                       and f < os.path.basename(out))
        if snaps:
            prior = snaps[-1]
            pr = json.load(open(os.path.join(config.REPORTS_DIR, prior)))
            prior_silent = sum(1 for r in pr
                               if str(r.get("loudness", "")).startswith("SILENT"))
    except Exception:  # noqa: BLE001
        pass

    if prior_silent is not None and silent > prior_silent:
        _warn(warns, "SWALLOW",
              f"silent handlers ROSE {prior_silent} -> {silent} since {prior} — "
              f"a new swallow was added. Run: python3 tests/swallow_audit.py --critical")
    else:
        delta = ("" if prior_silent is None
                 else f" ({silent - prior_silent:+d} vs {prior})")
        _log("SWALLOW", f"\u2705 {len(rows)} handlers, {silent} silent "
                        f"({t1} in tier-1 risk/orders/record){delta}")


def phase_vwap(date, dry, warns):
    """Phase 11 — VWAP orientation ledger (backlog item E evidence).

    Per strategy x direction x VWAP alignment, with realized P&L: would the
    proposed VWAP_FILTER_ACTIVE hard gate have blocked winners or losers? Writes
    reports/vwap_orientation_<date>.txt.

    WHY NIGHTLY AND AUTOMATIC: item E must not be BUILT until the evidence says
    which direction the gate belongs in, or whether it belongs on a given
    strategy at all — VWAP alignment is a trend-following filter, and Sweep
    Reversal enters counter to extension by design. Evidence that accrues only
    when someone remembers to run a script is evidence that will not be there on
    decision day.

    FALSIFICATION ONLY. The tool emits no weights and no thresholds, and nothing
    in the live path reads its output. A verdict licenses a design review whose
    conclusion must stand on mechanism, not on the P&L that flagged it.
    """
    script = os.path.join(OTV3_DIR, "tests", "vwap_orientation_ledger.py")
    out = os.path.join(config.REPORTS_DIR, f"vwap_orientation_{date}.txt")
    if dry:
        _log("VWAP", f"[dry] would run {script} {date} -> {out}")
        return
    if not os.path.isfile(script):
        _warn(warns, "VWAP", f"{script} not found — orientation ledger NOT run")
        return
    venv_py = os.path.join(OTV3_DIR, "venv", "bin", "python")
    py = venv_py if os.access(venv_py, os.X_OK) else sys.executable
    try:
        proc = subprocess.run([py, script, date], capture_output=True,
                              text=True, timeout=300)
    except Exception as exc:  # noqa: BLE001
        _warn(warns, "VWAP", f"vwap_orientation_ledger.py raised: {exc}")
        return
    os.makedirs(config.REPORTS_DIR, exist_ok=True)
    with open(out, "w") as fh:
        fh.write(proc.stdout or "")
        if proc.stderr:
            fh.write("\n--- stderr ---\n" + proc.stderr)
    if proc.returncode != 0:
        _warn(warns, "VWAP", f"ledger rc={proc.returncode} — see {out}")
        return
    verdicts = [ln.strip() for ln in (proc.stdout or "").splitlines()
                if "orientation looks" in ln or "INSUFFICIENT" in ln]
    _log("VWAP", f"\u2705 orientation ledger -> {os.path.basename(out)}")
    for v in verdicts[:6]:
        _log("VWAP", f"    {v}")


def phase_evm(date, dry, warns):
    """Phase 12 — EARNED VALUE against docs/BACKLOG.md.

    Reports schedule performance nightly so a slip is visible while it is still
    small. Two indices, deliberately: SPI(all) is calendar truth, SPI(desk) is
    accountability — of the work that was OURS to move, how much moved. A late
    [DESK·DATA] item is a DC&A dependency and must not be averaged into the
    number that measures execution, or the metric stops being actionable.

    Here because of the standing rule: a check that depends on someone
    remembering to run it is a check that will not run. Read-only.
    """
    script = os.path.join(OTV3_DIR, "tests", "evm_status.py")
    if dry:
        _log("EVM", f"[dry] would run {script} --quiet")
        return
    if not os.path.isfile(script):
        _warn(warns, "EVM", f"{script} not found — no earned-value reading")
        return
    venv_py = os.path.join(OTV3_DIR, "venv", "bin", "python")
    py = venv_py if os.access(venv_py, os.X_OK) else sys.executable
    try:
        proc = subprocess.run([py, script, "--quiet", "--asof", date],
                              capture_output=True, text=True, timeout=120)
    except Exception as exc:  # noqa: BLE001
        _warn(warns, "EVM", f"evm_status.py raised: {exc}")
        return
    if proc.returncode != 0:
        _warn(warns, "EVM", f"evm_status.py rc={proc.returncode}: "
                            f"{(proc.stderr or '').strip()[:200]}")
        return
    line = next((l for l in proc.stdout.splitlines() if l.strip()), "")
    _log("EVM", f"\U0001F4CA {line}")
    # A DESK slip is the only variance effort can fix, so it is the only one
    # that pages. Data waits are re-dated, not compressed.
    m = re.search(r"SPI\(desk\)\s+([0-9.]+)", line)
    if m and float(m.group(1)) < 1.0:
        _warn(warns, "EVM", f"SPI(desk) {m.group(1)} — DESK work is behind and "
                            f"nothing is blocking it. See the get-well plan: "
                            f"python3 tests/evm_status.py")
    else:
        try:
            notify.send(f"\U0001F4CA {line}")
        except Exception:  # noqa: BLE001
            pass


def phase_readiness(date, dry, warns):
    """Phase 9 — readiness digest (trade_readiness v1.1 dial-tuning report).

    Digests the harvested signal-journal readiness rows (machine states, R
    distribution, would-fire counts, arm episodes, staged picks, anticipation
    lead-times) into reports/readiness_digest_<date>.{txt,jsonl}. This is the
    file the readiness bars (OT_TR_*) get tuned from — the whole point of the
    log-only observer is that this report accumulates with no manual step.
    Consumes what harvest v0.5.0 pulled; on a fleet that has not yet deployed
    main v4.4 the tool prints an honest "no readiness rows" headline and
    returns 0, so this phase is safe to ship AHEAD of the fleet deploy.
    Warn-never-stop, same recovery rule as every phase.
    """
    script = os.path.join(OTV3_DIR, "tests", "readiness_digest.py")
    if dry:
        _log("READINESS", f"[dry] would run {script} --quiet --date {date}")
        return
    if not os.path.isfile(script):
        _warn(warns, "READINESS", f"{script} not found — is {OTV3_DIR} checked out? "
                                  f"readiness digest NOT written")
        return
    venv_py = os.path.join(OTV3_DIR, "venv", "bin", "python")
    py = venv_py if os.access(venv_py, os.X_OK) else sys.executable
    cmd = [py, script, "--quiet", "--date", date,
           "--journal-root", os.path.join(config.BASE_DIR, "signal_journal"),
           "--reports-dir",  config.REPORTS_DIR]
    _log("READINESS", f"readiness_digest.py --quiet --date {date}")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except Exception as exc:  # noqa: BLE001
        _warn(warns, "READINESS", f"readiness_digest.py raised: {exc}")
        return
    if proc.returncode != 0:
        _warn(warns, "READINESS", f"readiness_digest.py rc={proc.returncode}: "
                                  f"{(proc.stderr or '').strip()[:200]}")
        return
    headline = next((ln for ln in proc.stdout.splitlines() if ln.strip()), "")
    _log("READINESS", f"✅ {headline}")
    try:
        notify.send(headline)
    except Exception:  # noqa: BLE001
        pass


def run(date=None, batch=5, dry=False, do_regime=True, do_tables=True,
        do_swallow=True, do_vwap=True, do_evm=True, do_recover=True,
        do_readiness=True):
    date = date or _today_et()
    mapping, _ = instance_registry.discover(config.UNIVERSE)
    running = {s: r.get("private_ip", "") for s, r in mapping.items()
              if r.get("state") == "running"}
    warns = []
    _log("START", f"EOD conductor {date} — {len(running)} traded box(es) up, "
                  f"{('DRY-RUN' if dry else 'LIVE')} @ {datetime.now(_ET).strftime('%H:%M')} ET")
    if not dry:
        try:
            notify.send(f"🛠️ EOD conductor started {date} — {len(running)} traded boxes up")
        except Exception:  # noqa: BLE001
            pass

    phase_gate(running, date, dry, warns)
    phase_harvest(date, running, dry, warns)
    # 2b. Traders are STILL UP here; phase_report stops them. Take their backlog
    #     first, exactly as instructed — logs before the lights go out.
    if do_recover:
        phase_archive_recovery(dry, warns, "traders")
    phase_report(running, dry, warns)
    still = phase_backfill(date, batch, dry, warns)
    # 4b. The sat-out boxes were just woken five at a time to fetch candles.
    #     While they are up, collect any journal/chain dates control never pulled.
    if do_recover:
        phase_archive_recovery(dry, warns, "satouts")
    # After BACKFILL on purpose: backfill fetches candles for days the boxes
    # never handed over, so aggregating earlier would build daily bars from
    # tape that is about to get more complete.
    phase_daily_bars(dry, warns)
    phase_consolidate(date, dry, warns)
    phase_label(date, dry, warns)
    if do_regime:
        phase_regime(dry, warns)
    else:
        _log("REGIME", "skipped (--no-regime)")
    phase_excursion(date, dry, warns)
    if do_tables:
        phase_tables(dry, warns)
    if do_swallow:
        phase_swallow(date, dry, warns)
    if do_vwap:
        phase_vwap(date, dry, warns)
    if do_evm:
        phase_evm(date, dry, warns)
    else:
        _log("TABLES", "skipped (--no-tables)")
    if do_readiness:
        phase_readiness(date, dry, warns)
    else:
        _log("READINESS", "skipped (--no-readiness)")

    if warns:
        _log("DONE", f"⚠️ EOD conductor finished {date} with {len(warns)} warning(s):")
        for w in warns:
            _log("DONE", f"   • {w}")
    else:
        _log("DONE", f"✅ EOD conductor complete for {date}")
    if not dry:
        tail = (" — ⚠️ " + " | ".join(warns)) if warns else ""
        try:
            notify.send((f"{'⚠️' if warns else '✅'} EOD conductor {date} "
                        f"{'with warnings' if warns else 'complete'}{tail}")[:900])
        except Exception:  # noqa: BLE001
            pass
    return 1 if warns else 0


def main(argv):
    p = argparse.ArgumentParser(description="Control-side EOD conductor (always reaches backfill)")
    p.add_argument("--date", default=None)
    p.add_argument("--batch", type=int, default=5)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-regime", action="store_true")
    p.add_argument("--no-tables", action="store_true")
    p.add_argument("--no-swallow", action="store_true")
    p.add_argument("--no-vwap", action="store_true")
    p.add_argument("--no-evm", action="store_true")
    p.add_argument("--no-recover", action="store_true")
    p.add_argument("--no-readiness", action="store_true")
    args = p.parse_args(argv[1:])
    return run(date=args.date, batch=args.batch, dry=args.dry_run,
               do_regime=not args.no_regime, do_tables=not args.no_tables,
               do_swallow=not args.no_swallow, do_vwap=not args.no_vwap,
               do_evm=not args.no_evm, do_recover=not args.no_recover,
               do_readiness=not args.no_readiness)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
