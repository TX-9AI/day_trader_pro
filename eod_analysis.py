#!/usr/bin/env python3
"""
day_trader_pro/eod_analysis.py  v1.1
The reports. Runs AFTER the boxes are down, reads the warehouse.

v1.1  2026-08-23  TWO R-SUITE PHASES, conductor-driven, no new timers.
  · R_LEDGER — nightly. Shells to the otv4 checkout's tests/r_ledger.py
    (S3 source; the tool prints its own SOURCE line). Telegram carries the
    HEADLINE ONLY — R, expectancy, capture — never the table: Telegram is an
    emergency-services channel and a nightly wall of numbers is how it stops
    being read.
  · EDGE_SCAN — FRIDAYS ONLY, and SILENT unless a feature clears the
    pre-registered bar. Its bar needs 10 sessions and 200 trades per side;
    nightly it would say NOT YET five times a week and train the operator to
    scroll past the one night it says something else.
  Both shell out (the otv4 tools own their argv), both warn-never-stop, and
  a MISSING otv4 checkout is a NAMED warning — "0 trades" from an empty day
  and "0 trades" from a wrong path must never look alike.

v1.0  2026-08-25  The second half of the EOD streamline. `eod_conductor_v2.py`
owns the CLOSE (stop trading → drain → verify → take down); this owns the
REPORTS, and the two never overlap.

🔴 WHY THEY WERE SPLIT. v1.16 ran eleven phases with the shutdown in the
MIDDLE, so six report phases sat between "stop the boxes" and "check the data
arrived". Consequences, all of them real:

  · A slow report DELAYED THE CLOSE. Boxes burned EC2 time waiting on
    excursion statistics that had nothing to do with stopping them.
  · The completeness check ran LAST, after the boxes were dead — correct for
    in-flight S3 objects, useless for anything recoverable.
  · Reports read LOCAL state pulled by an in-chain harvest, so the chain had
    to keep a second copy of data that was already in the bucket.

⚠️ ONE PHASE DID NOT MOVE AND COULD NOT: `phase_backfill` WAKES BOXES to fetch
candles for symbols that sat out. It needs the fleet UP, so it belongs in the
close (or its own pre-close step) and not here. Moving it would have produced
a report run that silently woke the fleet it was supposed to run without.

⚠️ EVERY PHASE HERE IS WARN-NEVER-STOP. A report that raises must not prevent
the next report from running — the close already happened and its verdict is
the one that mattered.

⚠️ AND NOTHING HERE TOUCHES A BOX. If a phase needs a box, it is in the wrong
file.

Run:  python3 eod_analysis.py                 # today
      python3 eod_analysis.py --date 2026-08-21
      python3 eod_analysis.py --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config                                                   # noqa: E402
try:
    import notify
except Exception:                                               # noqa: BLE001
    notify = None


def _log(tag: str, msg: str) -> None:
    print(f"[{tag:<11}] {msg}", flush=True)


def _warn(warns: list, tag: str, msg: str) -> None:
    warns.append(f"{tag}: {msg}")
    _log(tag, f"⚠️  {msg}")


def _phase(name, fn, warns, *a, **kw):
    """Run one report. NEVER lets it stop the run.

    ⚠️ A RAISED REPORT IS A WARNING, NOT A FAILURE OF THE EVENING. The close
    is already done; these are derived artifacts and each is independent.
    """
    try:
        return fn(*a, **kw)
    except Exception as exc:                                    # noqa: BLE001
        _warn(warns, name, f"raised: {exc}")
        return None


def run(date: str, dry: bool) -> int:
    warns: list = []
    _log("START", f"EOD analysis — {date}" + ("  [DRY-RUN]" if dry else ""))
    _log("START", "boxes are DOWN; every read below is control-side or S3")

    # ── P&L from the warehouse ──────────────────────────────────────────
    # ⚠️ THE CONDUCTOR ALREADY SENT THIS ONE. Repeating it here would be the
    # SECOND time the same number reached the operator tonight — exactly the
    # duplication (eod_summary at 15:50, eod_report at 16:15) that this
    # rewrite exists to remove. Computed for the record, NOT re-notified.
    def _pnl():
        import pnl_s3
        per_day, per_sym, tot = pnl_s3.collect([date])
        _log("PNL", f"net={tot['net']:+.2f} closed={tot['closed']} "
                    f"open={tot['open']}")
    if not dry:
        # ⚠️ "CANNOT REACH S3" AND "NO TRADES" MUST NOT LOOK ALIKE. A
        # credentials failure is an environment fault, not a flat day.
        _phase("PNL", _pnl, warns)
    else:
        _log("PNL", "[dry] would read P&L from S3")

    # ── consolidate: the fleet_trades bundle ────────────────────────────
    def _consolidate():
        # 🔴 READ THE WAREHOUSE, NOT THE LOCAL PULL. Operator's ruling
        # 2026-08-25: "any EOD reports done by the conductor should be against
        # the s3 store, not local, not on the traders."
        # ⚠️ `consolidate_trades.consolidate()` READS `trades/<date>/` — the
        # folder harvest scps off the boxes — so using it here would keep the
        # whole pull path alive just to feed one report, and would report an
        # empty night for any date whose harvest never ran even though S3 held
        # the trades all along. `warehouse_reader.build()` produces the SAME
        # bundle shape from the bucket.
        # ⚠️ `build()` RETURNS THE BUNDLE ONLY — it does not write. I first
        # unpacked it as (bundle, path) from habit; the signature says
        # otherwise. Read the contract, do not assume the shape.
        import json as _json
        import warehouse_reader
        bundle = warehouse_reader.build(date)
        # ⚠️ AND THE OUTPUT PATH IS NOT FREE CHOICE. warehouse_reader REFUSES
        # to write a `fleet_trades_*` file under reports/ because that glob is
        # report 41's INPUT — a warehouse-sourced bundle landing there would
        # silently become the local report's data. Write where it expects.
        os.makedirs(warehouse_reader.WAREHOUSE_OUT, exist_ok=True)
        out_json = os.path.join(warehouse_reader.WAREHOUSE_OUT,
                                f"fleet_trades_{date}.json")
        tmp = out_json + ".tmp"
        with open(tmp, "w") as fh:
            _json.dump(bundle, fh, indent=2, default=str)
        os.replace(tmp, out_json)
        if not os.path.exists(out_json):
            _warn(warns, "CONSOLIDATE", "no bundle written")
            return
        # ⚠️ A BUNDLE IS NOT THE SAME AS DATA. The builder writes a valid,
        # EMPTY bundle and returns success when the source holds nothing — so a
        # ✅ on the filename alone would report a green night for a date that
        # collected NOTHING. Count the rows.
        n = 0
        try:
            n = len((bundle or {}).get("trades") or [])
        except Exception:                                       # noqa: BLE001
            pass
        if n:
            _log("CONSOLIDATE", f"✅ {os.path.basename(out_json)} — {n} trade(s)")
        else:
            _warn(warns, "CONSOLIDATE",
                  f"{os.path.basename(out_json)} written but EMPTY — "
                  f"no trades for {date}")
    if not dry:
        _phase("CONSOLIDATE", _consolidate, warns)
    else:
        _log("CONSOLIDATE", "[dry] would build the fleet_trades bundle")

    # ── daily bars, labels, excursion, coverage ─────────────────────────
    # ⚠️ THESE TWO ARE CALLED BY THEIR REAL ENTRY POINTS, VERIFIED IN SOURCE.
    # A first draft invented `daily_bars.update()` and `auto_label.run()` —
    # neither exists — and THE DRY RUN PASSED ANYWAY, because dry mode prints
    # "would run" without ever touching the function. A dry run that never
    # calls the thing cannot tell you the call is wrong.
    def _daily_bars():
        import daily_bars
        # rebuild() returns a Dict[str, int] of symbol -> rows, not a count.
        res = daily_bars.rebuild()
        n = len(res) if isinstance(res, dict) else res
        _log("DAILY_BARS", f"✅ {n} symbol(s) rebuilt from 1m tape")

    def _label():
        # auto_label exposes main() with its own argv parsing; the old
        # conductor shelled to it for the same reason.
        import subprocess
        rc = subprocess.run([sys.executable, "auto_label.py", "--date", date],
                            cwd=os.path.dirname(os.path.abspath(__file__)),
                            capture_output=True, text=True, timeout=300).returncode
        if rc != 0:
            _warn(warns, "LABEL", f"auto_label.py rc={rc}")
        else:
            _log("LABEL", "✅ session labelled from price action")

    # ⚠️ BOTH SHELL OUT RATHER THAN IMPORT-AND-CALL. Verified in source:
    # excursion_report.main() takes NO arguments and parses sys.argv itself,
    # and warehouse_coverage.main(argv) parses with its own argparse — so
    # calling either in-process either fails on arity or, worse, PARSES THIS
    # SCRIPT'S OWN sys.argv and errors on arguments meant for us. That second
    # failure is the interesting one: it produced a usage message naming
    # eod_analysis.py for a flag warehouse_coverage was reading.
    _here = os.path.dirname(os.path.abspath(__file__))

    def _excursion():
        import subprocess
        r = subprocess.run([sys.executable, "excursion_report.py", "--date", date],
                           cwd=_here, capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            _warn(warns, "EXCURSION", f"rc={r.returncode} "
                                      f"{(r.stderr or '').strip()[:120]}")
        else:
            _log("EXCURSION", "✅ excursion report written")

    def _coverage():
        import subprocess
        r = subprocess.run([sys.executable, "warehouse_coverage.py", "--date", date],
                           cwd=_here, capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            _warn(warns, "COVERAGE", f"rc={r.returncode} "
                                     f"{(r.stderr or '').strip()[:120]}")
        else:
            _log("COVERAGE", "✅ coverage checked")

    # ── the R suite (otv4 tools, S3-sourced, run HERE on control) ───────
    # ⚠️ CROSS-REPO BY SUBPROCESS, NEVER BY IMPORT — the modularity contract.
    # Precedent: the conductor has always shelled to validate_regime.sh in
    # the trading repo's control checkout.
    otv4 = os.environ.get("DTP_OTV4_DIR",
                          os.path.join(os.path.expanduser("~"), "options-trader-v4"))

    def _r_ledger():
        import subprocess
        tool = os.path.join(otv4, "tests", "r_ledger.py")
        if not os.path.exists(tool):
            _warn(warns, "R_LEDGER", f"otv4 checkout missing at {otv4} — set "
                                     f"DTP_OTV4_DIR (this is a PATH fault, not "
                                     f"an empty day)")
            return
        r = subprocess.run([sys.executable, tool, "--date", date],
                           capture_output=True, text=True, timeout=600)
        print(r.stdout)
        if r.returncode != 0:
            _warn(warns, "R_LEDGER", f"rc={r.returncode} "
                                     f"{(r.stdout or r.stderr or '').strip()[-160:]}")
            return
        head = next((l.strip() for l in (r.stdout or "").splitlines()
                     if l.strip().startswith("BOOK")), "")
        if head and notify:
            # HEADLINE ONLY. The full table lives in the analysis log.
            try:
                notify.send(f"📐 R {date}: {head[:300]}")
            except Exception:                                   # noqa: BLE001
                pass
        _log("R_LEDGER", f"✅ {head or 'no closed trades in the warehouse'}")

    def _edge_scan():
        import subprocess
        tool = os.path.join(otv4, "tests", "edge_scan.py")
        if not os.path.exists(tool):
            _warn(warns, "EDGE_SCAN", f"otv4 checkout missing at {otv4}")
            return
        r = subprocess.run([sys.executable, tool, "--from",
                            _weeks_ago(date, 6), "--to", date],
                           capture_output=True, text=True, timeout=1200)
        print(r.stdout)
        if r.returncode != 0:
            _warn(warns, "EDGE_SCAN", f"rc={r.returncode}")
            return
        if "MEETS THE PRE-REGISTERED BAR" in (r.stdout or ""):
            block = r.stdout.split("MEETS THE PRE-REGISTERED BAR", 1)[1][:500]
            if notify:
                try:
                    notify.send(f"🔎 edge_scan {date}: a feature CLEARED the "
                                f"pre-registered bar:\n{block}")
                except Exception:                               # noqa: BLE001
                    pass
            _log("EDGE_SCAN", "✅ a feature cleared the bar — paged")
        else:
            # ⚠️ SILENT BY DESIGN. NOT YET is the expected answer for weeks,
            # and a weekly NOT-YET page is how the real page gets ignored.
            _log("EDGE_SCAN", "✅ ran; nothing clears the bar (expected)")

    for nm, fn, note in (("DAILY_BARS", _daily_bars, "daily bars rebuilt from the 1m tape"),
                         ("LABEL", _label, "price-action session label"),
                         ("EXCURSION", _excursion, "MFE/MAE report"),
                         ("COVERAGE", _coverage, "warehouse coverage"),
                         ("R_LEDGER", _r_ledger, "R baseline from the warehouse (headline → Telegram)"),
                         ("EDGE_SCAN", _edge_scan, "weekly edge scan (Fridays; silent unless the bar clears)")):
        if nm == "EDGE_SCAN":
            try:
                is_friday = datetime.strptime(date, "%Y-%m-%d").weekday() == 4
            except ValueError:
                is_friday = False
            if not is_friday:
                _log(nm, "skipped — runs Fridays only (its bar needs ~10 "
                         "sessions; a nightly NOT-YET is noise)")
                continue
        if dry:
            # ⚠️ THE DRY RUN SAYS "WOULD", NEVER "DID" — the conductor's own
            # dry-run fabricates its verification and is labelled; these must
            # not imply success either.
            _log(nm, f"[dry] would run {note}")
            continue
        _log(nm, note)
        _phase(nm, fn, warns)

    # ── report ──────────────────────────────────────────────────────────
    if warns:
        _log("DONE", f"{len(warns)} warning(s):")
        for w in warns:
            _log("DONE", f"  · {w}")
        # ⚠️ TELEGRAM ONLY WHEN SOMETHING WENT WRONG. A nightly "reports ran"
        # message is exactly the routine traffic that teaches an operator to
        # ignore the channel that matters.
        if notify and not dry:
            try:
                notify.send(f"⚠️ EOD analysis {date}: {len(warns)} warning(s)\n"
                            + "\n".join(f"· {w}" for w in warns[:6]))
            except Exception:                                   # noqa: BLE001
                pass
    else:
        _log("DONE", "all reports clean")
    # ⚠️ EXIT 0 EVEN WITH WARNINGS. systemd marks a unit failed on non-zero,
    # and a warned-but-complete report run is not a failed unit — the 08-06
    # lesson where the conductor showed `failed` on healthy nights.
    return 0


def _weeks_ago(date: str, n: int) -> str:
    from datetime import datetime as _dt, timedelta as _td
    return (_dt.strptime(date, "%Y-%m-%d") - _td(weeks=n)).strftime("%Y-%m-%d")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv[1:] if argv else None)
    return run(a.date, a.dry_run)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
