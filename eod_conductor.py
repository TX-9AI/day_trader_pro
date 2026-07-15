# day_trader_pro/eod_conductor.py — v1.0.0
"""
End-of-day conductor (control server). ONE ordered, completion-gated chain that
calls the existing helpers in sequence — it rewrites none of them, it sequences
them. Every step blocks on the previous one succeeding, and any failure HALTS
LOUDLY (Telegram + stderr) leaving the fleet exactly as-is so you can troubleshoot
and re-run. Replaces the independent dtp-harvest + dtp-eod timers with one timer.

Order (each gated on the last):
  1. GATE      — poll every TRADED (running) box until it has produced everything
                 the server needs: ~/eod/pnl_today.json, ~/eod/trades_today.json,
                 and its OHLC CSV (with bars). Nothing downstream runs until this
                 passes; timeout ⇒ HALT (boxes left up).
  2. HARVEST   — harvest.py: pull trades.db + OHLC + trade JSON → trades/ ohlc/,
                 aggregate + consolidate → reports/. Gate: the raw dirs populated.
  3. REPORT    — eod_report.py: unified P&L Telegram, then STOP the traded boxes
                 (frees vCPU/streams for the backfill). Gate: all stopped.
  4. BACKFILL  — eod_backfill.py --batch 5: wake the SAT-OUT symbols five at a time,
                 produce → pull → stop, until every symbol's OHLC is on the server.
                 Still-missing ⇒ loud WARNING (not a halt: may be unfetchable next-day),
                 recorded in the summary.
  5. CONSOLIDATE — consolidate_trades.py: final fleet_trades bundle over the now-
                 complete tape. Gate: bundle written.
  6. REGIME    — ~/validate_regime.sh <date>: replay confluence over ohlc/<date>/
                 (chatter metric) + upsert the diary. Runs LAST, on complete tape.

CLI:
  python eod_conductor.py              # run the full chain for today
  python eod_conductor.py --date D     # a specific date
  python eod_conductor.py --dry-run    # show the plan + gate status, mutate nothing
  python eod_conductor.py --batch 5    # sat-out backfill batch size (default 5)
  python eod_conductor.py --no-regime  # skip step 6 (e.g. harness not synced yet)
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
VALIDATE_SH = os.path.expanduser("~/validate_regime.sh")

GATE_TIMEOUT = 420          # s to wait for all traded boxes to finish producing
GATE_POLL = 15              # s between gate polls


def _today_et():
    return datetime.now(_ET).strftime("%Y-%m-%d")


def _log(tag, msg):
    print(f"[{tag:<11}] {msg}", flush=True)


class _Halt(Exception):
    """Raised to stop the chain loudly at a failed gate."""


def _halt(phase, msg):
    line = (f"🚨 EOD conductor HALTED at {phase}: {msg}\n"
            f"Fleet left as-is — troubleshoot and re-run eod_conductor.py.")
    _log("HALT", msg)
    try:
        notify.send(line)
    except Exception:  # noqa: BLE001
        pass
    raise _Halt(msg)


# ── step 1: GATE on bot production ────────────────────────────────────────────
def _box_ready(ip, sym, date):
    """True once this box has pnl_today.json + trades_today.json + an OHLC csv with bars."""
    cmd = (f'D={date}; test -s ~/eod/pnl_today.json && test -s ~/eod/trades_today.json '
           f'&& f=~/{REMOTE_REPO}/data/OHLC/$D/{sym}.csv && [ -s "$f" ] '
           f'&& [ "$(wc -l < "$f")" -gt 1 ] && echo READY || echo WAIT')
    rc, out, _e = ssh_util.ssh_run(ip, cmd)
    return rc == 0 and "READY" in out


def phase_gate(running, date, dry):
    who = ", ".join(sorted(running))
    _log("GATE", f"waiting on {len(running)} traded box(es) to finish producing: {who}")
    if dry:
        _log("GATE", "[dry] would poll each box for pnl/trades JSON + OHLC csv")
        return
    deadline = time.time() + GATE_TIMEOUT
    pending = dict(running)     # sym -> ip
    while pending and time.time() < deadline:
        for sym in list(pending):
            if _box_ready(pending[sym], sym, date):
                pending.pop(sym)
        if pending:
            time.sleep(GATE_POLL)
    if pending:
        _halt("GATE", f"boxes never finished producing after {GATE_TIMEOUT}s: "
                      f"{', '.join(sorted(pending))}")
    _log("GATE", "✅ all traded boxes have produced — proceeding")


# ── step wrappers ─────────────────────────────────────────────────────────────
def phase_harvest(date, dry):
    if dry:
        _log("HARVEST", "[dry] would run harvest.py (pull + consolidate)")
        return
    _log("HARVEST", "harvest.py — pull trades.db + OHLC + trade JSON, consolidate")
    try:
        harvest.run(quiet=False)
    except Exception as exc:  # noqa: BLE001
        _halt("HARVEST", f"harvest.run raised: {exc}")
    # gate: today's raw dirs must be populated
    td = os.path.join(config.TRADES_DIR, date)
    od = os.path.join(config.OHLC_DIR, date)
    if not (os.path.isdir(td) and os.listdir(td)):
        _halt("HARVEST", f"no trades pulled into {td}")
    if not (os.path.isdir(od) and os.listdir(od)):
        _halt("HARVEST", f"no OHLC pulled into {od}")
    _log("HARVEST", "✅ raw trades/ + ohlc/ populated")


def phase_report(dry):
    if dry:
        _log("REPORT", "[dry] would run eod_report.py (P&L + stop traded boxes)")
        return
    _log("REPORT", "eod_report.py — unified P&L, then stop the traded boxes")
    try:
        rc = eod_report.run(dry_run=False)
    except Exception as exc:  # noqa: BLE001
        _halt("REPORT", f"eod_report.run raised: {exc}")
        return
    if rc != 0:
        _halt("REPORT", f"eod_report returned rc={rc} (a box failed to stop) — check EC2")
    _log("REPORT", "✅ P&L sent + traded boxes stopped")


def phase_backfill(date, batch, dry):
    _log("BACKFILL", f"eod_backfill.py — sat-out symbols, {batch} at a time")
    if dry:
        eod_backfill.run(date=date, batch=batch, dry=True)
        return []
    try:
        rc = eod_backfill.run(date=date, batch=batch)
    except Exception as exc:  # noqa: BLE001
        _halt("BACKFILL", f"eod_backfill.run raised: {exc}")
        return []
    still = eod_backfill._missing(date)     # re-check what's left
    if still:
        msg = f"⚠️ backfill left {len(still)} symbol(s) without candles: {', '.join(still)}"
        _log("BACKFILL", msg)
        try:
            notify.send("🛠️ EOD conductor — " + msg + " (continuing; diary runs on tape present)")
        except Exception:  # noqa: BLE001
            pass
    else:
        _log("BACKFILL", "✅ every symbol has OHLC on the server")
    return still


def phase_consolidate(date, dry):
    if dry:
        _log("CONSOLIDATE", "[dry] would run consolidate_trades.py over complete tape")
        return
    _log("CONSOLIDATE", "consolidate_trades.py — final fleet_trades bundle")
    try:
        _b, out_json, _c = consolidate_trades.consolidate(date=date)
    except Exception as exc:  # noqa: BLE001
        _halt("CONSOLIDATE", f"consolidate raised: {exc}")
        return
    if not (out_json and os.path.exists(out_json)):
        _halt("CONSOLIDATE", "no fleet_trades bundle written")
    _log("CONSOLIDATE", f"✅ {os.path.basename(out_json)}")


def phase_regime(date, dry):
    if dry:
        _log("REGIME", f"[dry] would run {VALIDATE_SH} {date}")
        return
    if not (os.path.isfile(VALIDATE_SH) and os.access(VALIDATE_SH, os.X_OK)):
        _halt("REGIME", f"{VALIDATE_SH} missing/non-executable (chmod +x ~/validate_regime.sh?)")
    _log("REGIME", f"{VALIDATE_SH} {date} — replay + diary over complete tape")
    try:
        rc = subprocess.run([VALIDATE_SH, date], timeout=1800).returncode
    except Exception as exc:  # noqa: BLE001
        _halt("REGIME", f"validate_regime.sh raised: {exc}")
        return
    # replay acceptance codes: 0 = pass, 2 = acceptance-fail but diary still upserted.
    if rc not in (0, 2):
        _halt("REGIME", f"validate_regime.sh returned rc={rc}")
    _log("REGIME", f"✅ diary upserted for {date} (replay rc={rc})")


def run(date=None, batch=5, dry=False, do_regime=True):
    date = date or _today_et()
    mapping, _ = instance_registry.discover(config.UNIVERSE)
    running = {s: r.get("private_ip", "") for s, r in mapping.items()
              if r.get("state") == "running"}
    started = datetime.now(_ET).strftime("%H:%M")
    _log("START", f"EOD conductor {date} — {len(running)} traded box(es) up, "
                  f"{('DRY-RUN' if dry else 'LIVE')} @ {started} ET")
    if not dry:
        try:
            notify.send(f"🛠️ EOD conductor started {date} — {len(running)} traded boxes")
        except Exception:  # noqa: BLE001
            pass

    try:
        phase_gate(running, date, dry)
        phase_harvest(date, dry)
        phase_report(dry)
        still = phase_backfill(date, batch, dry)
        phase_consolidate(date, dry)
        if do_regime:
            phase_regime(date, dry)
        else:
            _log("REGIME", "skipped (--no-regime)")
    except _Halt:
        return 1

    tail = f" | ⚠️ still missing: {', '.join(still)}" if still else ""
    _log("DONE", f"✅ EOD conductor complete for {date}{tail}")
    if not dry:
        try:
            notify.send(f"✅ EOD conductor complete {date}{tail}")
        except Exception:  # noqa: BLE001
            pass
    return 0


def main(argv):
    p = argparse.ArgumentParser(description="Control-side EOD conductor (gated, fail-loud)")
    p.add_argument("--date", default=None, help="YYYY-MM-DD (default: today ET)")
    p.add_argument("--batch", type=int, default=5, help="sat-out backfill batch size")
    p.add_argument("--dry-run", action="store_true", help="show the plan, mutate nothing")
    p.add_argument("--no-regime", action="store_true", help="skip the regime replay/diary step")
    args = p.parse_args(argv[1:])
    return run(date=args.date, batch=args.batch, dry=args.dry_run, do_regime=not args.no_regime)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
