# day_trader_pro/eod_conductor.py — v1.16.0
# v1.16.0 (2026-08-22) — the six otv3-dependent phases (the nightly replay,
#   SWALLOW, VWAP, EVM, READINESS) are DELETED with their CLI flags. Each
#   shelled into a checkout that is not present, took its not-found branch,
#   and fired a Telegram warning every night about an engine that was
#   deliberately retired. Rebuild against v4 data if wanted; do not
#   resurrect by path.
# v1.15.0 (2026-08-20) — PHASE 4b (SAT-OUT ARCHIVE RECOVERY) DELETED. It existed
#   for boxes that did not trade that day: phase_backfill woke them five at a
#   time for candles, and while they were up they handed over journal/chain
#   dates control had never pulled. After the 2026-08-20 fleet resize there are
#   no sat-outs by construction — UNIVERSE is the panel (config v0.1.5), every
#   box is up every session, and the phase degraded to a logged
#   "no boxes running - deferred". Operator: "Sat-outs is now archaic."
#   ⚠️ NOTHING IS LOST, and that was checked rather than assumed: phase 2b runs
#   the SAME recovery earlier in the chain with the WHOLE fleet up, right after
#   harvest and before phase_report stops them. 4b only ever reached boxes 2b
#   could not. `scope` is gone with it — a parameter with one caller and one
#   possible value misleads the next reader into thinking a second mode exists.
#   ⚠️ phase_backfill STAYS. Its sat-out wake disappeared with the UNIVERSE
#   prune, but its real job did not: a PANEL box whose harvest genuinely failed
#   still has to be woken and fetched.
# v1.14.0 (2026-08-18) — +PHASE 15 WAREHOUSE COVERAGE (VIX). Gate for the
#   sever: once S3 is the official store the control-side copy stops being
#   written, so anything absent from the bucket is gone. VIX carries the
#   highest exposure in that transition because it has ONE writer —
#   s3_push.push_candles skips VIX unless the box is SPX — so any day SPX is
#   down or its candles stage fails, VIX does not land, and NOTHING reports it,
#   since 28 boxes skipping VIX is correct behaviour. Runs
#   warehouse_coverage.py (LIST-only, read-only) and warns on a missing date,
#   separating "SPX pushed candles but no VIX" (a push defect) from "SPX pushed
#   nothing" (box down). LAST in the chain on purpose: the pusher runs on its
#   own timer, so checking earlier would report objects that are merely still
#   in flight as missing. Warn-never-stop, like every other phase.
# v1.13.0 (2026-08-04) — PHASE 10 NAMES THE NEW SWALLOWS. The 08-03 warning read
#   "silent handlers ROSE 83 -> 87 — a new swallow was added" and stopped there,
#   so every firing cost a manual census to find out WHICH. Both snapshots are
#   already loaded here, so the diff is free: the warning now names up to five
#   additions as file:line func, tier-1 first. Identity is (file, func, guards),
#   NOT the line number — a line moves whenever anything above it changes, and a
#   line-keyed diff would report a whole file as new after a one-line edit. An
#   alarm that cannot point at what it detected gets read more slowly each time
#   it fires (WORKING_AGREEMENT 17). Matches options_trader_v3
#   tests/swallow_audit.py v1.1 --since, which does the same diff by hand.
# v1.12.0 (2026-08-02) — +PHASE 5c ARCHIVE THE MORNING REPORT. data/report.json is
#   OVERWRITTEN every morning at 09:15, so the day's per-symbol sentiment score is
#   destroyed before anyone can join it to that day's outcomes. Copies it to
#   reports/morning_report_<date>.json so the score becomes joinable the same way
#   gap_pct is — by (date, symbol).
#   WHY THIS AND NOT A TRADE-ROW COLUMN: the score is per SYMBOL PER DAY, not per
#   trade, so every trade on a symbol-day inherits one value — identical structure
#   to gap class. Archiving the file needs no sqlite migration, nothing box-side,
#   and no exposure to the Aug 21 behavioural freeze. It is pure recording.
#   WHY IT IS URGENT EVEN THOUGH THE ANALYSIS IS NOT: `brief_strength` was a
#   hardcoded 0.30 for every name every day until the DTP_REPORT_JSON fix landed
#   after the close on 2026-07-30, so real per-symbol sentiment has existed for
#   only a couple of sessions. The correlation study is a nice-to-have; the
#   RECORDING is time-sensitive, because a month of accumulation cannot start
#   until the file stops being thrown away.
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
#   (4b REMOVED at v1.15.0 — the fleet resize left no sat-outs. 2b remains.)
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
# v1.2.0 — 2026-07-15 — box-state-independent recovery: BACKFILL/CONSOLIDATE/REPLAY
#          ALWAYS run regardless of whether traded boxes are up/down/never-ran; the
#          upstream gate/harvest/report steps now WARN-and-proceed instead of halting,
#          so box state can never block the candle recovery. (Same code as the v1.1.0
#          fix; version re-stamped for deploy clarity.)
# v1.0.0 — 2026-07-11 — initial gated conductor.
"""
End-of-day conductor (control server). ONE ordered chain that calls the existing
helpers in sequence — it sequences them, it rewrites none of them.

v1.1.0 principle: the WHOLE point of EOD is to end up with complete tape + diary,
so the recovery path (BACKFILL → CONSOLIDATE → REPLAY) ALWAYS runs — regardless of
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


def phase_archive_recovery(dry, warns):
    """Phase 2b — SELF-HEALING ARCHIVE GAP RECOVERY, run while the boxes are up.

    Runs ONCE, after phase_harvest and BEFORE phase_report stops the fleet —
    logs first, then the lights go out.

    v1.15.0: the second call (scope="satouts", after phase_backfill) is deleted
    along with the `scope` parameter. It served boxes that had not traded that
    day; the panel now trades every box every session, so it reached nobody 2b
    had not already reached.

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
        _log("RECOVER", "no archive gaps — journal + chains complete")
        return
    todo = sorted({d for ds in gaps.values() for d in ds})[:MAX_RECOVERY_DATES]
    for root, ds in gaps.items():
        _log("RECOVER", f"{root}: {len(ds)} session(s) missing "
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
            _warn(warns, "RECOVER", f"{d} raised: {exc}")
            continue
        if res is None:
            _log("RECOVER", f"{d}: no boxes running — deferred")
            continue
        got = len(res.get("journal", {}).get("ok", [])) + \
              len(res.get("chains", {}).get("ok", []))
        failed = len(res.get("journal", {}).get("failed", [])) + \
                 len(res.get("chains", {}).get("failed", []))
        ok += 1
        _log("RECOVER", f"{d}: recovered {got} file(s)"
                        + (f", {failed} FAILED" if failed else ""))
        if failed:
            _warn(warns, "RECOVER", f"{d}: {failed} pull(s) FAILED "
                                    f"(not merely absent)")
    remaining = sum(len(v) for v in gaps.values()) - ok
    if remaining > 0:
        _log("RECOVER", f"{remaining} session(s) still to recover — "
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


# ── 5c. ARCHIVE THE MORNING REPORT (always; control-side) ────────────────────
def phase_archive_report(date, dry, warns):
    """Preserve the day's per-symbol sentiment score before it is overwritten.

    data/report.json is rewritten every morning by market_brief_v1, so today's
    scores vanish at tomorrow's 09:15. Copying it under a dated name makes the
    score joinable to that day's trades by (date, symbol) — the same shape
    gap_pct.json already has, so tests/gap_outcome_join.py's machinery applies
    with only the conditioning column swapped.

    Recording only. Reads nothing live, changes no behaviour, gates nothing.
    """
    src = os.path.join(config.DATA_DIR, "report.json")
    dest = os.path.join(config.REPORTS_DIR, f"morning_report_{date}.json")
    if dry:
        _log("REPORT", f"[dry] would archive {src} -> {dest}")
        return
    if not os.path.isfile(src):
        _warn(warns, "REPORT", f"no {src} to archive — sentiment for {date} is lost")
        return
    try:
        with open(src) as fh:
            payload = json.load(fh)
    except Exception as exc:  # noqa: BLE001
        _warn(warns, "REPORT", f"report.json unreadable ({exc}) — not archived")
        return
    # A stale report is worse than none: it would silently attribute an old day's
    # sentiment to today's trades. The 07-29 defect was exactly this failure mode
    # (a frozen file read for 23 days), so the freshness stamp is checked here.
    stamp = str(payload.get("date") or payload.get("generated_at") or "")
    if stamp and date not in stamp:
        _warn(warns, "REPORT",
              f"report.json is stamped {stamp!r}, not {date} — archiving anyway "
              f"but DO NOT join it to {date} trades")
    try:
        os.makedirs(config.REPORTS_DIR, exist_ok=True)
        with open(dest, "w") as fh:
            json.dump(payload, fh, indent=1, sort_keys=True)
    except Exception as exc:  # noqa: BLE001
        _warn(warns, "REPORT", f"archive write failed: {exc}")
        return
    n = len(payload.get("scores") or payload.get("move_ranked") or [])
    _log("REPORT", f"✅ archived morning report ({n} symbols) -> "
                   f"morning_report_{date}.json")


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


def phase_label(date, dry, warns):
    """v1.4.0 — Tier-B session labeling, automated (ROADMAP L1.8/L1.6/L1.7).

    Was a manual 10-minute EOD habit via label_day.sh, which also could not
    label the archived past. auto_label.py derives the labels from RAW PRICE
    ACTION only — it imports nothing from the retired classifier, so the
    labels stay INDEPENDENT ground truth rather than a
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


def phase_coverage(date, dry, warns):
    """Phase 15 — IS THE WAREHOUSE ACTUALLY HOLDING VIX? (pre-sever gate)

    WHY THIS IS A PHASE AND NOT A COMMAND SOMEONE RUNS: after the sever the
    bucket is the only copy, and a stream that quietly stops landing is
    unrecoverable — DXFeed history is use-it-or-lose-it and nothing in the
    system can delete or re-create it. A check that depends on anyone
    remembering to run it is a comment, not a control.

    WHY VIX SPECIFICALLY: it is the only stream with a SINGLE writer. Every box
    logs VIX into feed_store, but push_candles skips it unless the box is SPX
    ("SPX owns VIX" — the dedup decision). So VIX collection is exactly as
    reliable as one box, and its absence looks identical to normal behaviour on
    the other 28.

    Control-side, read-only, LIST-only against S3 — never touches a box, never
    fetches an object body. Warn-never-stop per the recovery-path rule.
    """
    script = os.path.join(config.BASE_DIR, "warehouse_coverage.py")
    out = os.path.join(config.REPORTS_DIR, f"warehouse_coverage_{date}.json")
    if dry:
        _log("COVERAGE", f"[dry] would run {script} --date {date} --json -> {out}")
        return
    if not os.path.isfile(script):
        _warn(warns, "COVERAGE", f"{script} not found — VIX coverage NOT checked")
        return
    try:
        proc = subprocess.run([sys.executable, script, "--date", date,
                               "--json", out],
                              capture_output=True, text=True, timeout=180)
    except Exception as exc:  # noqa: BLE001
        _warn(warns, "COVERAGE", f"warehouse_coverage.py raised: {exc}")
        return
    for line in (proc.stdout or "").splitlines():
        _log("COVERAGE", line.rstrip())
    if proc.returncode == 2:
        _warn(warns, "COVERAGE", "could not list the bucket — coverage UNKNOWN "
                                 f"for {date}: {(proc.stderr or '').strip()[:160]}")
        return
    if proc.returncode != 0:
        # rc=1 means a checked date is missing VIX. The stdout above already
        # names which of the two diagnoses it is; the warning has to carry
        # enough to act on without re-running anything.
        _warn(warns, "COVERAGE",
              f"VIX MISSING from the warehouse for {date} — see "
              f"{os.path.basename(out)}. Do NOT sever the control-side copy "
              f"while this is red.")


def phase_coverage(date, dry, warns):
    """Phase 15 — IS THE WAREHOUSE ACTUALLY HOLDING VIX? (pre-sever gate)

    WHY THIS IS A PHASE AND NOT A COMMAND SOMEONE RUNS: after the sever the
    bucket is the only copy, and a stream that quietly stops landing is
    unrecoverable — DXFeed history is use-it-or-lose-it and nothing in the
    system can delete or re-create it. A check that depends on anyone
    remembering to run it is a comment, not a control.

    WHY VIX SPECIFICALLY: it is the only stream with a SINGLE writer. Every box
    logs VIX into feed_store, but push_candles skips it unless the box is SPX
    ("SPX owns VIX" — the dedup decision). So VIX collection is exactly as
    reliable as one box, and its absence looks identical to normal behaviour on
    the other 28.

    Control-side, read-only, LIST-only against S3 — never touches a box, never
    fetches an object body. Warn-never-stop per the recovery-path rule.
    """
    script = os.path.join(config.BASE_DIR, "warehouse_coverage.py")
    out = os.path.join(config.REPORTS_DIR, f"warehouse_coverage_{date}.json")
    if dry:
        _log("COVERAGE", f"[dry] would run {script} --date {date} --json -> {out}")
        return
    if not os.path.isfile(script):
        _warn(warns, "COVERAGE", f"{script} not found — VIX coverage NOT checked")
        return
    try:
        proc = subprocess.run([sys.executable, script, "--date", date,
                               "--json", out],
                              capture_output=True, text=True, timeout=180)
    except Exception as exc:  # noqa: BLE001
        _warn(warns, "COVERAGE", f"warehouse_coverage.py raised: {exc}")
        return
    for line in (proc.stdout or "").splitlines():
        _log("COVERAGE", line.rstrip())
    if proc.returncode == 2:
        _warn(warns, "COVERAGE", "could not list the bucket — coverage UNKNOWN "
                                 f"for {date}: {(proc.stderr or '').strip()[:160]}")
        return
    if proc.returncode != 0:
        # rc=1 means a checked date is missing VIX. The stdout above already
        # names which of the two diagnoses it is; the warning has to carry
        # enough to act on without re-running anything.
        _warn(warns, "COVERAGE",
              f"VIX MISSING from the warehouse for {date} — see "
              f"{os.path.basename(out)}. Do NOT sever the control-side copy "
              f"while this is red.")


def run(date=None, batch=5, dry=False, do_recover=True, do_coverage=True):
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
        phase_archive_recovery(dry, warns)
    phase_report(running, dry, warns)
    # phase_backfill KEEPS its retry job (a panel box whose harvest failed), but
    # its sat-out wake is gone: UNIVERSE is the panel, so _missing() can only
    # name a box that was up and short. v1.15.0 deleted the 4b recovery call
    # that used to piggyback on that wake.
    still = phase_backfill(date, batch, dry, warns)
    # After BACKFILL on purpose: backfill fetches candles for days the boxes
    # never handed over, so aggregating earlier would build daily bars from
    # tape that is about to get more complete.
    phase_daily_bars(dry, warns)
    phase_archive_report(date, dry, warns)
    phase_consolidate(date, dry, warns)
    phase_label(date, dry, warns)
    # ── 🔴 v1.16.0 (2026-08-22) — SIX otv3-DEPENDENT PHASES DELETED ─────────
    # The nightly replay, TABLES, SWALLOW, VWAP, EVM and READINESS all
    # scripts inside the options_trader_v3 checkout. That checkout is not
    # present, so every one of them took its not-found branch and fired a
    # Telegram WARNING every single night:
    #     "EOD conductor [EVM] .../options-trader-v3/tests/evm_status.py not
    #      found - no earned-value reading"
    # ...five of those, plus a summary line, on a fleet that no longer runs v3.
    #
    # ⚠️ THEY WERE NOT BROKEN - THEY WERE ORPHANED. Each phase was written
    # warn-never-stop, so the correct not-found branch ran correctly forever.
    # The conductor was faithfully reporting the absence of an engine that was
    # deliberately retired. A nightly warning nobody can action is worse than
    # silence: it is the alarm that teaches you to ignore alarms.
    #
    # ⚠️ THE NIGHTLY REPLAY WENT WITH THEM. That phase shelled out to
    # a v3 replay script whose premise
    # otv4 retired. Operator, 2026-08-22: the term is gone from the menu too.
    #
    # If any of this analysis is wanted against v4, it gets REBUILT against
    # v4's own data, not resurrected by path. See docs/ for the r58/r59
    # precedent: a ported tool is a claim about v4 nobody has checked.
    phase_excursion(date, dry, warns)
    # LAST on purpose — the box-side pusher runs on its own timer, so an
    # earlier check would call objects still in flight "missing".
    if do_coverage:
        phase_coverage(date, dry, warns)
    else:
        _log("COVERAGE", "skipped (--no-coverage)")

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
    p.add_argument("--no-recover", action="store_true")
    p.add_argument("--no-coverage", action="store_true",
                   help="skip the VIX warehouse-coverage check (phase 15)")
    args = p.parse_args(argv[1:])
    return run(date=args.date, batch=args.batch, dry=args.dry_run,
               do_recover=not args.no_recover,
               do_coverage=not args.no_coverage)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
