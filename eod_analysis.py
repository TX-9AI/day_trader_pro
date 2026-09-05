#!/usr/bin/env python3
"""
day_trader_pro/eod_analysis.py  v1.3
The reports. Runs AFTER the boxes are down, reads the warehouse.

v1.3  2026-09-05  dtp r285 / S3.12 — THE PER-STREAM COVERAGE BOARD JOINS THE
      NIGHTLY CHAIN, and it joins it LAST rather than on the day it was built.
      🔑 THE PRECONDITION WAS THE POINT. r277 shipped `--streams` and
      deliberately did NOT wire it, because the CONDITIONAL and DEAD
      classifications were declarations read out of `s3_push`'s stage list and
      never checked against a real bucket. The first hand-run raised NINE flags
      and SEVEN were the policy table — `prints` graded EVERY when SPX is a cash
      index that publishes none, `trades` graded EVERY when `push_trades` is
      CDC, and `shadow` graded DEAD when 15 boxes push it every session. All
      three were corrected in r280, and the two real absences were closed as
      ACCEPTED_LOSS in r284. **An alarm wired before that would have cried wolf
      on its first night and been ignored by its second.**
      ⚠️ A SEPARATE PHASE FROM `COVERAGE`. The VIX report answers "did the
      single-writer stream land"; this answers "did every box push every stream
      it owes". Two questions behind one green is how a passing check stops
      meaning anything.
      ⚠️ IT PRINTS THE FLAGGED ROWS, NOT A COUNT. dtp r282 is one phase over:
      `head -3` ate the cause of every purge failure for weeks. A summary that
      hides the rows is a summary nobody can act on. The ACCEPTED-LOSS rows
      print on a clean night too — r284's contract is that a closed absence
      stays VISIBLE, not that it disappears.
      ⚠️ WARN, NEVER STOP: a coverage gap is a fact about yesterday, and a
      phase that aborted would cost the R baseline over a missing OHLC file.

v1.2  2026-08-29  r186 / dtp r227 — EXCURSION READS THE BUNDLE CONSOLIDATE
      JUST BUILT (backlog S3.3). 🔴 THIS PHASE HAS BEEN FAILING EVERY NIGHT
      SINCE THE v2 EOD INSTALL, AND THE CHAIN ITSELF IS WHAT BROKE IT.
      `_consolidate` was pointed at S3 and writes to `reports/warehouse/`;
      one phase later `_excursion` still shelled `excursion_report.py --date
      <date>` with NO `--bundles-dir`, which takes the per-box-DB path and
      reads `trades/<date>/*_trades_<date>.db`. `install_eod_v2.sh` DISABLES
      `dtp-harvest.timer` — deliberately, because the conductor drains to S3
      and a second copy on control has no consumer — so that folder is not
      populated any more. The report then falls back to a ROOT
      `reports/fleet_trades_<date>.json`, which `_consolidate` no longer
      writes either. Both sources gone, so `load_day` returns None and
      excursion_report exits 1.
      ⚠️ IT FAILED LOUDLY, WHICH IS THE ONLY GOOD NEWS: the phase is
      warn-never-stop, so every night it logged `EXCURSION rc=1 No
      trades/<date>/*_trades.db and no fleet_trades_<date>.json` and the
      chain carried on. Not a laundered green — a real warning that nothing
      chased down. Now it passes `--bundles-dir` pointing at
      `warehouse_reader.WAREHOUSE_OUT`, the exact directory `_consolidate`
      wrote to seconds earlier.
      ⚠️ AND IT CHECKS THE BUNDLE EXISTS FIRST, BY NAME. If CONSOLIDATE
      produced nothing, the warning now says so and names the missing file
      instead of reporting an excursion failure for a consolidate problem.
      Two phases, two causes, two messages.
      ⚠️ THE OUTPUT FILENAME CHANGES, DELIBERATELY: a `--bundles-dir` run
      lands at `reports/excursions_<date>_bundle_warehouse.txt`, because
      excursion_report v3.4 refuses to let two sources collide on one path.
      `tools/report_parity.py` writes that same name during a parity run;
      both are deterministic from the same bundle and parity regenerates
      before it reads, so the overwrite is safe — but it is two owners of
      one filename and it is recorded here rather than discovered later.
      ABSOLUTE PATH, never relative: a relative `--bundles-dir` has bitten
      this project before.

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
        import warehouse_reader as _wr
        # The bundle CONSOLIDATE wrote seconds ago, by absolute path.
        bundles = _wr.WAREHOUSE_OUT
        bundle = os.path.join(bundles, f"fleet_trades_{date}.json")
        if not os.path.exists(bundle):
            # ⚠️ NAME THE ACTUAL CAUSE. "excursion failed" for a missing
            # consolidate output sends the reader to the wrong phase, and this
            # chain is warn-never-stop so a mislabelled warning is all anyone
            # will ever see of it.
            _warn(warns, "EXCURSION",
                  f"no bundle at {bundle} — CONSOLIDATE produced nothing for "
                  f"{date}, so there is nothing to report on. This is a "
                  f"CONSOLIDATE problem, not an excursion problem.")
            return
        r = subprocess.run([sys.executable, "excursion_report.py",
                            "--date", date, "--bundles-dir", bundles],
                           cwd=_here, capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            _warn(warns, "EXCURSION", f"rc={r.returncode} "
                                      f"{(r.stderr or '').strip()[:120]}")
        else:
            tag = os.path.basename(os.path.normpath(bundles))
            _log("EXCURSION", f"✅ excursion report written FROM THE WAREHOUSE "
                              f"→ reports/excursions_{date}_bundle_{tag}.txt")

    def _coverage():
        import subprocess
        r = subprocess.run([sys.executable, "warehouse_coverage.py", "--date", date],
                           cwd=_here, capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            _warn(warns, "COVERAGE", f"rc={r.returncode} "
                                     f"{(r.stderr or '').strip()[:120]}")
        else:
            _log("COVERAGE", "✅ coverage checked")

    def _streams():
        """S3.12 — per-stream, per-day, per-box coverage, in the nightly chain.

        🔑 A SEPARATE PHASE FROM `COVERAGE`, NOT AN ARGUMENT TO IT. The VIX
        report answers "did the single-writer stream land"; this answers "did
        every box push every stream it owes". Different questions, different
        exit codes, and folding them into one line would make a green mean two
        things at once.

        ⚠️ IT PRINTS THE FLAGGED ROWS, NOT A COUNT, AND NOT A TRUNCATION. The
        `head -3` lesson from dtp r282 is one phase over: a summary that hides
        the rows is a summary nobody can act on. The ACCEPTED-LOSS rows print
        too, on a clean night as much as a dirty one, because r284's whole
        contract is that a closed absence stays visible.

        ⚠️ WARN, NEVER STOP. A coverage gap is a fact about yesterday; the rest
        of the chain still has work to do, and a phase that aborted the run
        would cost the R baseline over a missing OHLC file.
        """
        import subprocess
        r = subprocess.run(
            [sys.executable, "warehouse_coverage.py", "--streams", "--date", date],
            cwd=_here, capture_output=True, text=True, timeout=900)
        out = (r.stdout or "") + (r.stderr or "")
        # 🔴 / ❗ / ❓ are the rows that need an answer; ▪ is a recorded loss and
        # prints by contract. Everything else is the ordinary green board.
        flagged = [l for l in out.splitlines()
                   if any(m in l for m in ("🔴", "❗", "❓", "▪"))]
        for line in flagged[:20]:
            _log("STREAMS", line.split("] ", 1)[-1].strip())
        if r.returncode == 0:
            _log("STREAMS", "✅ every stream had every box it owes")
        else:
            _warn(warns, "STREAMS",
                  f"rc={r.returncode} — {len([l for l in flagged if '🔴' in l])} "
                  f"gap(s), {len([l for l in flagged if '❗' in l])} stale "
                  f"exemption(s); see the rows above")

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
                         ("STREAMS", _streams, "per-stream, per-day, per-box coverage"),
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
