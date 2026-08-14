#!/usr/bin/env python3
"""
day_trader_pro/fit_report.py — v1.1 — 2026-08-10

v1.1 — sections 5 and 6 now receive THE RANGE. v1.0 let ramp_calibration and
       a2_cooccurrence auto-discover the corpus, so on the first real run they
       read 21 files back to 2026-07-13 inside a report headed "2026-08-10" —
       four sections answering one window and two answering another, in a
       document whose entire purpose is to stop exactly that. The header said
       so, but a caveat is not a control. Both tools take an explicit file list;
       the range is passed through, and when no replay exists in range the
       sections are SKIPPED rather than silently widened.

ONE FILE CONTAINING EVERY REPORT NEEDED TO FIT SOMETHING.

WHY IT EXISTS. Fitting a ramp, a stop or an entry gate needs the trade
breakdown, the excursion/MFE-MAE read, the regime diary and the calibration
telemetry TOGETHER — and they were four separate menu options producing four
separate screenfuls. Running them one at a time and screenshotting each is slow
on mobile and, worse, it makes it easy to fit against numbers drawn from
different windows without noticing.

WHAT IT DOES NOT DO — and this is deliberate: it does not RE-IMPLEMENT any
report. Every section is the real tool, invoked as a subprocess, with its output
captured verbatim. There is exactly one source of truth per number, and a fix to
excursion_report shows up here the next run with no change to this file. The
cost is that this file must know each tool's CLI; the benefit is that it can
never quietly disagree with the tool it is quoting.

⚠️ THE THREE THINGS THIS PRINTS THAT NO INDIVIDUAL REPORT CAN

  1. PROVENANCE. Both repos' git HEAD, the resolved interpreters, and the date
     range — stamped at the top. A fit made against an unknown engine version is
     not reproducible, and this project has already had one calibration
     invalidated by bounds fitted against an engine that no longer ran.

  2. THE BAKE-BOUNDARY WARNING. Engine changes land on dated bakes, and per-regime
     statistics are NOT poolable across one. If the requested range spans a known
     bake the report says so at the TOP, before any number, rather than leaving
     the reader to remember. Add new bake dates to BAKE_DATES as they happen.

  3. SECTION-LEVEL FAILURE THAT IS VISIBLE. A tool that errors, is missing, or
     refuses gets its section written with the failure text and a FAILED marker,
     and the run continues. A fit report that silently omits a section is worse
     than one that admits a hole — the reader would fit against what remains and
     never know something was missing.

USAGE
    python3 fit_report.py                          # today, single day
    python3 fit_report.py --date 2026-08-10
    python3 fit_report.py --since 2026-07-23       # cumulative to today
    python3 fit_report.py --since 2026-07-23 --date 2026-08-10
    python3 fit_report.py --date 2026-08-10 --no-slow   # skip replay-corpus tools

OUTPUT
    reports/fit_report_<date>.txt              (single day)
    reports/fit_report_<since>_to_<date>.txt   (cumulative)
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys
from datetime import datetime

HOME        = os.path.expanduser("~")
DTP_DIR     = os.path.dirname(os.path.abspath(__file__))
OTV3_DIR    = os.path.join(HOME, "options-trader-v3")
OTV3_PY     = os.path.join(OTV3_DIR, "venv", "bin", "python")
VALIDATE_SH = os.path.join(OTV3_DIR, "validate_regime.sh")
REPORTS_DIR = os.path.join(DTP_DIR, "reports")
JOURNAL_ROOT = os.path.join(DTP_DIR, "signal_journal")

# Dated fleet bakes that changed WHICH TRADES FIRE or how they are LABELLED.
# Statistics either side of one of these are not the same measurement, so a
# range that spans one gets a warning at the top of the report. APPEND, never
# edit — the list is the record of when the basis moved.
BAKE_DATES = {
    "2026-08-08": "RGM.3 (SWEEP out of the argmax) + SWP.1/2 + CNT.1/2/3 + "
                  "MEM.2 + N.7 + VW.1e — changes which trades fire AND the "
                  "label vocabulary",
}

SEP = "=" * 78


def sh(cmd, cwd=None, timeout=900):
    """Run a command, capture everything. Never raises."""
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout)
        out = (p.stdout or "") + (("\n[stderr]\n" + p.stderr) if p.stderr.strip() else "")
        return p.returncode, out
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT after {timeout}s: {' '.join(cmd)}"
    except FileNotFoundError as exc:
        return 127, f"NOT FOUND: {exc}"
    except Exception as exc:                                  # noqa: BLE001
        return 1, f"{type(exc).__name__}: {exc}"


def head(fh, title, note=""):
    fh.write(f"\n\n{SEP}\n  {title}\n")
    if note:
        fh.write(f"  {note}\n")
    fh.write(f"{SEP}\n")


def section(fh, title, cmd, cwd=None, note="", timeout=900):
    head(fh, title, note)
    fh.write(f"  $ {' '.join(cmd)}\n\n")
    rc, out = sh(cmd, cwd=cwd, timeout=timeout)
    fh.write(out.rstrip() + "\n")
    if rc != 0:
        # VISIBLE, never silent. A refusal is a legitimate result here (the
        # tools refuse on thin samples by design) so the marker names the code
        # rather than asserting a fault.
        fh.write(f"\n  [SECTION EXIT rc={rc} — read the text above; a REFUSAL "
                 f"on a thin sample is a correct result, an error is not]\n")
    print(f"  {'ok ' if rc == 0 else f'rc={rc}'}  {title}")
    return rc


def git_head(path):
    if not os.path.isdir(os.path.join(path, ".git")):
        return "(not a git checkout)"
    rc, out = sh(["git", "rev-parse", "--short", "HEAD"], cwd=path, timeout=30)
    rc2, out2 = sh(["git", "status", "--porcelain"], cwd=path, timeout=30)
    dirty = " +DIRTY" if (rc2 == 0 and out2.strip()) else ""
    return (out.strip() or "?") + dirty


def replay_files(since, date):
    """The replay jsonl files INSIDE the requested range.

    v1.1 — sections 5 and 6 auto-discovered the whole corpus and therefore
    answered a DIFFERENT WINDOW than sections 1-4, inside a file headed with one
    date. Both tools accept an explicit file list, so the range is now passed
    through. A report that says 2026-08-10 must mean 2026-08-10 throughout, or
    it invites exactly the cross-window fit the bake warning exists to prevent.
    """
    lo = since or date
    out = []
    for p in sorted(glob.glob(os.path.join(REPORTS_DIR, "regime_replay_*.jsonl"))):
        d = os.path.basename(p)[len("regime_replay_"):-len(".jsonl")]
        if lo <= d <= date:
            out.append(p)
    return out


def spanned_bakes(since, date):
    lo = since or date
    return {d: why for d, why in BAKE_DATES.items() if lo < d <= date}


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"),
                    help="the day, or the END of a cumulative range")
    ap.add_argument("--since", default=None,
                    help="start of a cumulative range; omit for a single day")
    ap.add_argument("--no-slow", action="store_true",
                    help="skip the replay-corpus tools (A2 drift, ramp calibration)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv[1:])

    cumulative = bool(a.since)
    os.makedirs(REPORTS_DIR, exist_ok=True)
    out_path = a.out or os.path.join(
        REPORTS_DIR,
        f"fit_report_{a.since}_to_{a.date}.txt" if cumulative
        else f"fit_report_{a.date}.txt")

    py = sys.executable or "python3"
    otv3_py = OTV3_PY if os.path.exists(OTV3_PY) else None

    print(f"fit report -> {out_path}")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(f"{SEP}\n  FIT REPORT — "
                 f"{'CUMULATIVE ' + a.since + ' .. ' + a.date if cumulative else a.date}\n{SEP}\n")
        fh.write(f"  generated      {datetime.now().isoformat(timespec='seconds')}\n")
        fh.write(f"  day_trader_pro {git_head(DTP_DIR)}\n")
        fh.write(f"  options_trader {git_head(OTV3_DIR)}\n")
        fh.write(f"  interpreters   dtp={py}\n")
        fh.write(f"                 otv3={otv3_py or 'MISSING — otv3 sections will fail'}\n")

        bakes = spanned_bakes(a.since, a.date)
        if bakes:
            fh.write(f"\n  {'!' * 72}\n")
            fh.write("  ⚠️  THIS RANGE SPANS A FLEET BAKE. Per-regime and per-strategy\n")
            fh.write("      statistics either side of one are NOT THE SAME MEASUREMENT and\n")
            fh.write("      must not be pooled. Split the range at the date(s) below before\n")
            fh.write("      fitting anything to a per-regime number.\n")
            for d, why in sorted(bakes.items()):
                fh.write(f"        {d} — {why}\n")
            fh.write(f"  {'!' * 72}\n")
        else:
            fh.write("\n  bake boundaries in range: none\n")

        fh.write("\n  WHAT EACH SECTION IS FOR WHEN FITTING\n")
        fh.write("    1 trade breakdown  — population, regime x strategy, exit vocabulary\n")
        fh.write("    2 excursion        — STOPS: floor sweep, never-favourable, giveback\n")
        fh.write("    3 regime report    — LABELS: L1 distribution, L2 churn, acceptance\n")
        fh.write("    4 readiness digest — ENTRIES: arming, would-fire vs fired, pegged ramps\n")
        fh.write("    5 ramp calibration — RAMPS: per-term saturation + input percentiles\n")
        fh.write("    6 A2 + HTF drift   — forward drift by label; the null control\n")

        results = {}

        # ── 1. TRADE BREAKDOWN ──────────────────────────────────────────────
        cmd = [py, "trade_report.py"] + (["--since", a.since] if cumulative else
                                         ["--since", a.date])
        results["trade breakdown"] = section(
            fh, "1. TRADE BREAKDOWN (trade_report.py)", cmd, cwd=DTP_DIR,
            note="population, regime x strategy, exit reason x session spread")

        # ── 2. EXCURSION ────────────────────────────────────────────────────
        cmd = [py, "excursion_report.py", "--date", a.date]
        if cumulative:
            cmd += ["--since", a.since]
        results["excursion"] = section(
            fh, "2. EXCURSION / MFE-MAE (excursion_report.py)", cmd, cwd=DTP_DIR,
            note="STOP fitting: floor sweep, never-favourable, leash verdict, "
                 "score dispersion")

        # ── 3. REGIME REPORT / DIARY ────────────────────────────────────────
        if os.access(VALIDATE_SH, os.X_OK):
            cmd = ([VALIDATE_SH, "--diary"] if cumulative
                   else [VALIDATE_SH, "--report", a.date])
            results["regime"] = section(
                fh, "3. REGIME " + ("DIARY (all days)" if cumulative else
                                    f"REPORT ({a.date})"),
                cmd, cwd=OTV3_DIR,
                note="LABEL fitting: L1 score distribution, L2 churn, A1-A5 acceptance")
        else:
            head(fh, "3. REGIME REPORT")
            fh.write(f"  SKIPPED — {VALIDATE_SH} missing or not executable\n")
            results["regime"] = 127

        # ── 4. READINESS DIGEST ─────────────────────────────────────────────
        if otv3_py:
            cmd = [otv3_py, "-m", "tests.readiness_digest",
                   "--journal-root", JOURNAL_ROOT,
                   "--reports-dir", REPORTS_DIR, "--date", a.date]
            results["readiness"] = section(
                fh, "4. READINESS DIGEST (entries / arming)", cmd, cwd=OTV3_DIR,
                note="ENTRY fitting: arming counts, would-fire vs fired, pegged ramps. "
                     "SINGLE DAY even in cumulative mode — it reads one journal folder")
        else:
            head(fh, "4. READINESS DIGEST")
            fh.write(f"  SKIPPED — {OTV3_PY} missing\n")
            results["readiness"] = 127

        # ── 5 + 6. REPLAY-CORPUS TOOLS (slow) ───────────────────────────────
        if a.no_slow:
            head(fh, "5-6. RAMP CALIBRATION + A2/HTF DRIFT")
            fh.write("  SKIPPED — --no-slow\n")
        elif otv3_py:
            rf = replay_files(a.since, a.date)
            if not rf:
                head(fh, "5-6. RAMP CALIBRATION + A2/HTF DRIFT")
                fh.write(f"  NO REPLAY FILES IN RANGE ({a.since or a.date} .. {a.date}).\n")
                fh.write("  Sections 5-6 SKIPPED rather than silently widened to the\n")
                fh.write("  whole corpus — they would have answered a different window\n")
                fh.write("  than sections 1-4 inside a file headed with one date.\n")
                fh.write("  Run devtools 42/43 to build the replay for these dates.\n")
                results["ramps"] = results["a2drift"] = 3
            else:
                _span = f"{len(rf)} replay file(s) IN RANGE"
                results["ramps"] = section(
                    fh, "5. RAMP CALIBRATION (per-term saturation)",
                    [otv3_py, "-m", "tests.ramp_calibration"] + rf, cwd=OTV3_DIR,
                    note="RAMP fitting: which terms are pegged (a term pegged >60% is "
                         "a SWITCH, not a dial) + input percentiles. " + _span)
                results["a2drift"] = section(
                    fh, "6. A2 CO-OCCURRENCE + HTF FORWARD DRIFT",
                    [otv3_py, "-m", "tests.a2_cooccurrence"] + rf, cwd=OTV3_DIR,
                    note="forward drift by label with a RANGE_ONLY null control. "
                         + _span)
        else:
            head(fh, "5-6. RAMP CALIBRATION + A2/HTF DRIFT")
            fh.write(f"  SKIPPED — {OTV3_PY} missing\n")

        # ── FOOTER ──────────────────────────────────────────────────────────
        fh.write(f"\n\n{SEP}\n  SECTION STATUS\n{SEP}\n")
        for k, rc in results.items():
            fh.write(f"  {'OK    ' if rc == 0 else f'rc={rc:<4}'} {k}\n")
        fh.write("\n  A non-zero section is not automatically a fault — these tools\n")
        fh.write("  REFUSE on thin samples by design, and a refusal is the honest\n")
        fh.write("  answer. Read the section text before treating it as a failure.\n")
        if bakes:
            fh.write("\n  ⚠️  REMINDER: this range spans a fleet bake (see the top of\n")
            fh.write("      this file). Do not pool per-regime numbers across it.\n")
        fh.write(f"\n  written {out_path}\n")

    size = os.path.getsize(out_path)
    print(f"\nwrote {out_path}  ({size:,} bytes)")
    bad = [k for k, rc in results.items() if rc != 0]
    if bad:
        print(f"sections with non-zero exit: {', '.join(bad)} "
              f"— read them, a REFUSAL is a valid result")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
