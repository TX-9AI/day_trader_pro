#!/usr/bin/env python3
"""
tests/check_floor_overshoot.py  v1.3

v1.3  2026-11-08  r534 — THE GATE NO LONGER RESTS ON BUNDLES THAT CAN BE PRUNED. F1/F2 read the
      untracked reports/warehouse corpus, which grows a session a day and is pruned by hand, and
      F3/F5 drove the report on two named bundles in it (the Saturday brief 11-07 §5 "also found").
      Now: tests/fixtures/floor_overshoot/corpus_r383.json is the r383 corpus itself, frozen (every
      hard_stop_* row of the 13 bundles 08-31..09-15, fields copied verbatim; it reproduces 171 / 146
      / -20.0% / -23.3% exactly), and tests/fixtures/floor_overshoot/bundles/ holds byte-identical
      copies of the 09-14 and 09-07 bundles F3-F5 drive the report on. Because the corpus is frozen it
      cannot grow, so F1/F2 assert r383's own figures again (v1.1's reason not to - a growing corpus -
      is gone); the live corpus is still read when present and PRINTED, never asserted. A missing
      fixture is a FAIL (a defect in this repo), so the GREEN VACUOUS branch is gone.

v1.2  2026-09-26  r433 — the report it DRIVES now writes to scratch. F3/F4/F5
      run excursion_report.py for real, which is right, but the child landed on
      reports/excursions_2026-09-14 and _2026-09-07 — two of the operator's
      banked artefacts — resetting their mtime on every sweep. Found by diffing
      the whole of /home/ubuntu across a sweep. ⚠️ I MISATTRIBUTED THIS TWICE
      FIRST: to check_excursions_item.py on a NAME match, then again by
      assumption, before bisecting the sweep checker-by-checker. Reading is
      unaffected — --bundles-dir is still passed explicitly.

v1.1  2026-09-18  r388 — 🔴 F1 WAS PINNED TO A COUNT AND THE COUNT GROWS. MINE.
      I wrote `EXPECT_N = 171` / `EXPECT_WORSE = 146` against a 13-session
      corpus that gains a session every trading day, so **it went red on the
      very next one** and stayed red for three sessions unnoticed. §24 says this
      in as many words: *"a canary pinned to a VERSION STRING rots on the next
      legitimate bump — training the reader to skim past failures while a real
      one looks identical. Canaries check BEHAVIOUR, never a version number."*
      📊 AND THE FINDING NEVER MOVED, WHICH IS THE POINT: at 13 sessions it was
      146/171 = 85%; at 16 it is 166/195 = 85%, with the medians identical at
      -20.0% declared against -23.3% realized. The relationship is stable and
      only my frozen number rotted. F1 now asserts the RELATIONSHIP and PRINTS
      the live figures so drift is visible without being fatal; the r383
      numbers stay below as the measurement of record, where they belong.
      🔴 AND IT WENT RED IN ANY CLONE, FOR ENVIRONMENT. `reports/warehouse` is
      not tracked, so a fresh checkout reported FAIL for having no bundles —
      CV.1's shape, a gate red for a property of the target rather than a defect
      in it, which is the thing that teaches an operator to ignore reds. An
      absent corpus is now GREEN VACUOUS and says so: nothing was checked can
      never read as everything passed (r373's S0 rule).
v1.0  2026-09-16  r383 / EXIT.4 — THE FLOOR A ROW DECLARED vs THE FLOOR IT GOT.

🔴 THE DEFECT IN THE REPORT, not in the bot. `excursion_report`'s FLOOR VERDICT
collapsed the floor a trade ANNOUNCED and the floor it ACHIEVED into one
averaged number, so a stop that declared -20% and filled at -23% read as a clean
-20% stop. The information was in the row the whole time: `stop_premium` and
`entry_premium` give the declared floor, `pnl_pct` gives what was taken.

📊 MEASURED BY HAND ACROSS 13 BANKED SESSIONS BEFORE THE REPORT WAS TOUCHED:
**146 of 171 debit floor exits (85%) realized worse than their own declared
floor.** Median realized -23.3% against a median declared -20.0%; median
overshoot 2.5 points, worst 17.5. MU 2026-09-14's -32.7% on a 25% stop is the
tail of this distribution, not an outlier.

🔑 WHY THIS FILE EXISTS AND WHAT IT REFUSES TO DO. It recomputes the figure from
the bundles INDEPENDENTLY — it does not parse the report's own output. A check
that reads the thing it is checking is self-consistent by construction and
proves only that the code agrees with itself (§0.4). The number below was
obtained by hand, from the same rows, before the report knew how to print it.

⚠️ AND IT IS A PAPER LOWER BOUND, WHICH THE REPORT MUST SAY OUT LOUD. In paper
`exit_premium == exit_mark_at_trigger`, `exit_latency_ms` 0, one ladder step —
the fill IS the trigger mark, so the entire overshoot is SAMPLING: the floor is
a price level checked against a 15-second poll and is usually never observed.
Live adds the spread on top. F4 pins that the caveat reaches the page, because a
number this shape without it invites someone to treat it as the live figure.

⚠️ WHAT EACH CHECK IS, LABELLED HONESTLY — because only two of these five are
born-red evidence and calling the rest controls would dress up the record.

  RED AT HEAD (the defect)   F3, F4
  INDEPENDENT REPRODUCTION   F1, F2 — green at HEAD **and** on the build, by
                             design: they recompute the figure from the bundles
                             and pin it to what was measured BY HAND. They are
                             not evidence the report was broken; they are the
                             reason the report's number can be trusted.
  VACUOUS AT HEAD            F5 — at HEAD the block does not exist, so there is
                             nothing to render a zero and the check passes
                             trivially. It is only meaningful on the build.
                             Stated rather than counted as a control.

  F1  the RELATIONSHIP holds — most debit floor exits realize worse than the
      floor they declared. Recomputed from the bundles, not read from the
      report. Prints the live figures beside r383's so drift is visible.
  F2  the median declared (-20.0%) and median realized (-23.3%) are both
      reported and are NOT the same number
  F3  the report actually PRINTS the split — driven by running it, not grepped
  F4  the PAPER-lower-bound caveat travels with the number
  F5  a window with no floor stops says NOT COMPUTABLE rather than printing a
      clean zero. An absent measurement must never render as a measured one.
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import tempfile
import sys
from statistics import median

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)

_fails: list = []

# 📊 THE MEASUREMENT OF RECORD, r383, 13 banked sessions: 146 of 171 debit floor
# exits (85%) realized worse than their own declared floor; median declared
# -20.0%, median realized -23.3%, median overshoot 2.5 pts, worst 17.5.
# ⚠️ THESE ARE NOT ASSERTED — see v1.1. They are here so a later reader can see
# what the figure was when the report was built, and compare.
R383_N, R383_WORSE = 171, 146
# What IS asserted: the relationship, which is what the report claims and what a
# regression would break. The floor is deliberately well below the observed 85%
# so an honest shift in the tape does not go red — only the finding vanishing.
MIN_CORPUS = 40
MIN_WORSE_SHARE = 0.70
# v1.3: the asserted corpus and the bundles the report is driven on are FIXTURES; the live
# reports/warehouse corpus (untracked, grows daily, pruned by hand) is only printed.
FIXTURE = os.path.join(_root, "tests", "fixtures", "floor_overshoot")
CORPUS_R383 = os.path.join(FIXTURE, "corpus_r383.json")
BUNDLES = os.path.join(FIXTURE, "bundles")
LIVE_BUNDLES = os.path.join(_root, "reports", "warehouse")

# 🔴 THE REPORT IS RUN FOR REAL (F3-F5) AND MUST NOT LAND IN reports/.
# Driving the report instead of grepping it is correct — a source assertion
# passes against a block that never executes (§21, the r201 shape). But the
# child WRITES reports/excursions_<date>_bundle_warehouse.txt, so this gate was
# resetting the mtime on two of the operator's banked reports on every sweep.
# Reading is unaffected: --bundles-dir is passed explicitly, so only the
# child's OUTPUT directory moves.
_SCRATCH_REPORTS = os.path.join(tempfile.mkdtemp(prefix="floor_gate_"), "reports")
_SCRATCH_ENV = dict(os.environ, DTP_REPORTS_DIR=_SCRATCH_REPORTS)


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("  PASS  " if ok else "  FAIL  ") + name + (f"   [{detail}]" if detail else ""))
    if not ok:
        _fails.append(name)


def _floor_rows(trades):
    """(declared, realized, overshoot) for every debit floor exit, recomputed from scratch."""
    rows = []
    for t in trades:
        er = str(t.get("exit_reason") or "")
        if not er.startswith("hard_stop_"):
            continue
        sp, ep, pp = (t.get("stop_premium"), t.get("entry_premium"),
                      t.get("pnl_pct"))
        if not sp or not ep or ep <= 0 or pp is None:
            continue
        declared = (1.0 - (sp / ep)) * 100.0
        realized = -pp * 100.0
        rows.append((declared, realized, realized - declared))
    return rows


def _fixture_corpus():
    """The r383 corpus, frozen: the rows exactly as the 13 bundles held them."""
    with open(CORPUS_R383, encoding="utf-8") as fh:
        return _floor_rows(json.load(fh).get("rows") or [])


def _live_corpus():
    """Every debit floor exit in the live banked bundles (printed only, never asserted)."""
    trades = []
    for p in sorted(glob.glob(os.path.join(LIVE_BUNDLES, "fleet_trades_*.json"))):
        try:
            trades += json.load(open(p, encoding="utf-8")).get("trades") or []
        except Exception:                                      # noqa: BLE001
            continue
    return _floor_rows(trades)


def main() -> int:
    print("check_floor_overshoot — the floor a row declared vs the floor it got")
    print()

    # v1.3: the fixtures ship with the repo, so a missing one is a defect HERE, not a
    # property of the host - FAIL, never vacuous.
    have = os.path.isfile(CORPUS_R383) and all(
        os.path.isfile(os.path.join(BUNDLES, f"fleet_trades_{d}.json")) for d in ("2026-09-14", "2026-09-07"))
    check("F0 the fixtures are present", have, FIXTURE)
    if not have:
        print()
        print("FAILED: " + ", ".join(_fails))
        return 1

    rows = _fixture_corpus()
    worse = [r for r in rows if r[2] > 0.5]
    share = (len(worse) / len(rows)) if rows else 0.0
    check("F1 the finding holds: most debit floor exits realize WORSE than the "
          "floor they declared - r383's own corpus reproduces its own count",
          len(rows) == R383_N and len(worse) == R383_WORSE
          and len(rows) >= MIN_CORPUS and share >= MIN_WORSE_SHARE,
          f"n={len(rows)} worse={len(worse)} ({share:.0%})  "
          f"[r383 recorded {R383_WORSE}/{R383_N} = "
          f"{R383_WORSE / R383_N:.0%} over 13 sessions]")
    live = _live_corpus()
    if live:
        lw = [r for r in live if r[2] > 0.5]
        print(f"  LIVE  reports/warehouse today: n={len(live)} worse={len(lw)} "
              f"({len(lw) / len(live):.0%}), median declared -{median(r[0] for r in live):.1f}% "
              f"realized -{median(r[1] for r in live):.1f}%   (printed, not asserted)")

    if rows:
        md, mr = median(r[0] for r in rows), median(r[1] for r in rows)
        check("F2 declared and realized are DIFFERENT numbers, both reported",
              abs(md - 20.0) < 0.05 and abs(mr - 23.3) < 0.05 and mr > md,
              f"median declared -{md:.1f}%  median realized -{mr:.1f}%  "
              f"median overshoot {median(r[2] for r in rows):.1f} pts")
    else:
        check("F2 declared and realized are DIFFERENT numbers, both reported",
              False, "no rows")

    # ── F3 / F4 — DRIVEN. Asserting the source contains the strings would pass
    # against a block that never executes (§21, the r201 shape), so the report
    # is RUN and its output read.
    out = ""
    try:
        res = subprocess.run(
            [sys.executable, os.path.join(_root, "excursion_report.py"),
             "--date", "2026-09-14", "--bundles-dir", BUNDLES],
            capture_output=True, text=True, timeout=180, cwd=_root,
            env=_SCRATCH_ENV)
        out = (res.stdout or "") + (res.stderr or "")
    except Exception as exc:                                   # noqa: BLE001
        out = f"<run failed: {exc}>"
    check("F3 the report PRINTS the declared-vs-realized split",
          "DECLARED FLOOR vs REALIZED" in out
          and "median declared" in out and "median realized" in out,
          out.strip().splitlines()[-1][:80] if out.strip() else "no output")
    check("F4 the PAPER lower-bound caveat travels with the number",
          "PAPER LOWER BOUND" in out,
          "caveat present" if "PAPER LOWER BOUND" in out else "caveat MISSING")

    # ── F5 — CONTROL. A window with no floor stops must say so, not print a
    # clean zero. 2026-09-07 is a holiday bundle with no trades.
    empty_out = ""
    try:
        res2 = subprocess.run(
            [sys.executable, os.path.join(_root, "excursion_report.py"),
             "--date", "2026-09-07", "--bundles-dir", BUNDLES],
            capture_output=True, text=True, timeout=180, cwd=_root,
            env=_SCRATCH_ENV)
        empty_out = (res2.stdout or "") + (res2.stderr or "")
    except Exception as exc:                                   # noqa: BLE001
        empty_out = f"<run failed: {exc}>"
    # Either the whole report declines (no trades at all) or the block says NOT
    # COMPUTABLE. What must NOT happen is a rendered split with zeros in it.
    bad = ("DECLARED FLOOR vs REALIZED" in empty_out
           and "NOT COMPUTABLE" not in empty_out
           and "median declared -0.0%" in empty_out)
    check("F5 a window with no floor stops never renders a clean zero",
          not bad,
          "declines or says NOT COMPUTABLE" if not bad
          else "printed a zeroed split")

    print()
    if _fails:
        print("FAILED: " + ", ".join(_fails))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
