# day_trader_pro/eod_conductor.py — v1.4.0
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

CLI:
  python eod_conductor.py              # full chain for today
  python eod_conductor.py --date D
  python eod_conductor.py --dry-run
  python eod_conductor.py --batch 5
  python eod_conductor.py --no-regime
"""

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import config
import consolidate_trades
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
        eod_backfill.run(date=date, batch=batch)
    except Exception as exc:  # noqa: BLE001
        _warn(warns, "BACKFILL", f"eod_backfill raised: {exc}")
        return []
    still = eod_backfill._missing(date)
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


def run(date=None, batch=5, dry=False, do_regime=True):
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
    phase_report(running, dry, warns)
    still = phase_backfill(date, batch, dry, warns)
    phase_consolidate(date, dry, warns)
    phase_label(date, dry, warns)
    if do_regime:
        phase_regime(dry, warns)
    else:
        _log("REGIME", "skipped (--no-regime)")
    phase_excursion(date, dry, warns)

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
    args = p.parse_args(argv[1:])
    return run(date=args.date, batch=args.batch, dry=args.dry_run, do_regime=not args.no_regime)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
