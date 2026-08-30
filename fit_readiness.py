#!/usr/bin/env python3
"""
day_trader_pro/fit_readiness.py  v1.1
Per setup type: what fired, what was declined, and whether it is FITTABLE yet.

v1.1  2026-08-29  r184 / dtp r226 — THE WAREHOUSE IS THE SOURCE (backlog S3.2).
  🔴 THIS REPORT HAS NEVER PRODUCED A NUMBER ON CONTROL, AND THE REASON WAS
  A PATH. `--db` defaulted to `~/options-trader/data/derived_store.db` — a
  BOX path. WORKING_AGREEMENT 3 is explicit that `~/options-trader` does not
  exist on the control server, so devtools item 57 has always printed "No
  derived store at ..." unless somebody hand-scp'd a copy, which nobody did.
  It failed loudly, which is why it was never mistaken for a flat result —
  and also why it sat unnoticed as a menu item that could not work.
  Now: `warehouse_reader.load_derived()` for each of the three tables,
  defaulting to S3. `--db` survives as the EXPLICIT local escape hatch, for
  running this on a box against the live store.
  ⚠️ THE ET-DAY BOUND IS A CORRECTNESS FIX, NOT A PORT ARTIFACT. v1.0 built
  its window with `datetime.strptime(date).timestamp()`, which is NAIVE
  LOCAL time. The control box runs UTC, so "2026-08-25" meant 20:00 ET on
  the 24th and the window was four hours out of place — the operator's own
  long-standing symptom, "any time I run a report for today after the
  session ends it fails". Both paths now bound on the ET trading day: the
  local path by explicit ET epochs, the warehouse path by each row's own
  timestamp converted to ET.
  🔑 ONE AGGREGATOR, TWO SOURCES. `collect()` consumes plain dicts and knows
  nothing about where they came from; only the two loaders differ. A second
  aggregation path is a second set of numbers that agree until they do not.
  ⚠️ AND THE SOURCE LINE ALWAYS PRINTS. An unreachable bucket and a session
  with no evaluations must never render the same, which is the failure this
  project has now paid for twice.

v1.0  2026-08-25  Replaces `fit_report.py`, which is obsolete — see below.

🔴 WHY THE OLD FIT REPORT CANNOT ANSWER THIS. It bundled a trade breakdown, an
excursion read and a (long dead) v3 section into one text file, all sourced
from `trades`. But `trades` is the population that FIRED. **The question "is
this setup ready to fit?" is mostly answered by the population that did NOT** —
and `strategy_note`, `gate_disposition` and `plan_ledger` did not exist when
that report was written.

⚠️ AND ONE OF ITS FOUR SECTIONS HAD NEVER PRODUCED A NUMBER: section 3 shelled
into a validation script inside an otv3 checkout that is not present, so every
fitting report ever generated printed "SKIPPED, rc 127" there.

🔑 THE READINESS TEST IS COVERAGE, NOT COUNT. A setup is not fittable because
it has many observations; it is fittable when its DECLINES ARE DISTRIBUTED.
  · 400 declines, 380 of them on one rung → that rung cannot be fitted. Every
    observation sits on ONE SIDE of the boundary, so the data says where the
    line currently is and nothing about where it should be.
  · declines spread across four rungs with real counts each → there is a
    surface to fit against.
This is the single most important thing the report says, and it is the reason
"when are we ready" is the right question rather than "fit it now".

⚠️ EVERY NUMBER HERE STARTS AT ZERO ON 2026-08-25. `strategy_note`,
`gate_disposition`, `plan_ledger` and `character_ledger` were all built this
weekend and have never run against a live tape. So the first several runs of
this report are measuring DISTANCE FROM FITTABLE, which is itself the answer.

⚠️ IT NEVER RECOMMENDS A THRESHOLD. It reports whether the evidence could
support fitting one. The operator's standing split: setting a baseline where
none exists is judgment, correctness is a defect, and re-tuning a working dial
is not wanted. This tool serves the first two and refuses the third.

Run:  python3 fit_readiness.py                      # today, from S3
      python3 fit_readiness.py --date 2026-08-24
      python3 fit_readiness.py --from A --to B      # a range
      python3 fit_readiness.py --setup ORBStrategy  # one section
      python3 fit_readiness.py --db data/derived_store.db   # ON A BOX
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import warehouse_reader as wr    # noqa: E402  (needs HERE on sys.path first)

# ⚠️ THE BAR IS DELIBERATELY CRUDE AND STATED OUT LOUD. These are not tuned
# numbers — they are the point at which a human should LOOK, not a verdict.
MIN_FIRED = 30            # below this, outcome stats are noise
MIN_DECLINED = 50         # below this, the decline surface is not populated
MAX_RUNG_SHARE = 0.70     # one rung holding more than this = no surface


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _connect(path):
    if not os.path.exists(path):
        return None
    try:
        return sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error:
        return None


def _dates(a) -> list:
    if a.date:
        return [a.date]
    if a.frm and a.to:
        d0 = datetime.strptime(a.frm, "%Y-%m-%d").date()
        d1 = datetime.strptime(a.to, "%Y-%m-%d").date()
        out, d = [], min(d0, d1)
        while d <= max(d0, d1):
            out.append(d.isoformat())
            d += timedelta(days=1)
        return out
    return [datetime.now().strftime("%Y-%m-%d")]


TABLES = ("strategy_note", "gate_disposition", "plan_ledger")


def _rows_sqlite(db, dates):
    """The three tables from a local derived_store.db. -> (src, notes)."""
    src = {t: [] for t in TABLES}
    notes = []
    dc = _connect(db)
    if dc is None:
        notes.append("SOURCE: %s — 🔴 NO DERIVED STORE AT THAT PATH" % db)
        return None, notes
    dc.row_factory = sqlite3.Row
    lo, hi = wr.et_bounds(dates[0], dates[-1])
    for t in TABLES:
        col = wr.DERIVED_TS_COL.get(t, wr.DEFAULT_TS_COL)
        try:
            src[t] = [dict(r) for r in dc.execute(
                "SELECT * FROM %s WHERE %s >= ? AND %s < ?" % (t, col, col),
                (lo, hi))]
            notes.append("SOURCE: %s [%s] — %d row(s)" % (db, t, len(src[t])))
        except sqlite3.Error as exc:
            # ⚠️ A MISSING TABLE IS NOT AN EMPTY ONE. Say which, by name.
            notes.append("SOURCE: %s [%s] — 🔴 UNREADABLE: %s" % (db, t, exc))
    return src, notes


def _rows_warehouse(dates):
    """The three tables from S3. -> (src, notes). Boxes are never touched."""
    src, notes, s3 = {}, [], None
    try:
        s3 = wr._client()
    except Exception as exc:                                    # noqa: BLE001
        notes.append("🔴 COULD NOT OPEN AN S3 CLIENT: %s: %s"
                     % (type(exc).__name__, exc))
        return None, notes
    for t in TABLES:
        rows, meta = wr.load_derived(t, dates, s3=s3)
        src[t] = rows
        notes.append(meta.banner())
    return src, notes


def collect(src: dict, dates: list) -> dict:
    """Per strategy: fired/declined rows, rung histogram, derived vectors.

    🔑 IT TAKES PLAIN DICTS AND KNOWS NOTHING ABOUT THE SOURCE. Both
    loaders hand it the same shape, so the local and warehouse runs cannot
    drift into two different sets of numbers — the failure that took four
    instrumentation defects to find the last time two paths computed the
    "same" report.
    """
    out = defaultdict(lambda: {
        "fired": [], "declined": [], "rungs": Counter(),
        "plans": Counter(), "vec_fired": defaultdict(list),
        "vec_declined": defaultdict(list)})
    if not src:
        return out

    # ⚠️ `strategy_note` HOLDS BOTH SIDES BY DESIGN: one row per strategy
    # EVALUATION, fired and declined alike, each carrying the derived vector
    # that was true at the moment the engine looked. That is what makes the
    # comparison possible at all — the skipped trades have snapshots too.
    for r in src.get("strategy_note") or []:
        strat = r.get("strategy")
        if not strat:
            continue
        rec = out[strat]
        try:
            p = json.loads(r.get("payload") or "{}")
        except Exception:                                       # noqa: BLE001
            p = {}
        if not isinstance(p, dict):
            p = {}
        fired = bool(r.get("fired"))
        rec["fired" if fired else "declined"].append(p)
        bucket = rec["vec_fired"] if fired else rec["vec_declined"]
        for k, v in p.items():
            fv = _f(v)
            if fv is not None:
                bucket[k].append(fv)
        if not fired and r.get("outcome"):
            rec["rungs"][str(r["outcome"])[:48]] += 1

    # which rung refused, from the gate reporter
    for r in src.get("gate_disposition") or []:
        if str(r.get("event") or "") == "CLEARED":
            continue
        strat, gate = r.get("strategy"), r.get("gate")
        if strat and gate:
            out[strat]["rungs"][gate] += 1

    # intent that never became a trade
    for r in src.get("plan_ledger") or []:
        strat = r.get("strategy")
        if strat:
            out[strat]["plans"][r.get("terminal_reason") or "(live)"] += 1
    return out


def _spread(vals: list) -> str:
    """p10 / median / p90 — the shape, not a single number."""
    if not vals:
        return "—"
    s = sorted(vals)
    n = len(s)
    p10 = s[max(0, int(n * 0.10) - 0)]
    p50 = s[n // 2]
    p90 = s[min(n - 1, int(n * 0.90))]
    return f"{p10:>8.3f} {p50:>8.3f} {p90:>8.3f}"


def verdict(rec: dict) -> tuple:
    """(READY|NOT READY, reason). Coverage, not volume."""
    nf, nd = len(rec["fired"]), len(rec["declined"])
    if nf < MIN_FIRED:
        return "NOT READY", f"only {nf} fired (need ~{MIN_FIRED} for outcomes)"
    if nd < MIN_DECLINED:
        return "NOT READY", f"only {nd} declined (need ~{MIN_DECLINED})"
    total = sum(rec["rungs"].values())
    if total:
        top, n = rec["rungs"].most_common(1)[0]
        share = n / total
        if share > MAX_RUNG_SHARE:
            # 🔴 THE FINDING THAT MATTERS MOST, AND THE ONE A ROW COUNT HIDES.
            return ("NOT READY",
                    f"{share:.0%} of declines are '{top}' — one rung dominates, "
                    f"so there is no surface to fit; the data shows where the "
                    f"line IS, not where it should be")
    if len(rec["rungs"]) < 2:
        return "NOT READY", "declines land on fewer than two distinct rungs"
    return "READY", f"{nf} fired / {nd} declined across {len(rec['rungs'])} rungs"


def render(data: dict, dates: list, only=None) -> str:
    span = dates[0] if len(dates) == 1 else f"{dates[0]} → {dates[-1]}"
    L = ["=" * 74,
         f"  FIT READINESS — by setup type   ({span})",
         "=" * 74,
         "",
         "  A setup is fittable when its DECLINES ARE DISTRIBUTED, not when it",
         "  has many rows. One rung holding most of the refusals means every",
         "  observation sits on one side of the boundary.",
         ""]
    if not data:
        L += ["  No evaluations recorded for this window.",
              "",
              "  ⚠️ Expected before 2026-08-24 — strategy_note, gate_disposition",
              "  and plan_ledger were built 2026-08-22..25 and have not yet run",
              "  against a live tape.", "=" * 74]
        return "\n".join(L)

    for strat in sorted(data):
        if only and only.lower() not in strat.lower():
            continue
        rec = data[strat]
        v, why = verdict(rec)
        L.append("─" * 74)
        L.append(f"  {strat}")
        L.append("─" * 74)
        L.append(f"    {v}: {why}")
        L.append("")
        L.append(f"    fired    {len(rec['fired']):>6}")
        L.append(f"    declined {len(rec['declined']):>6}")

        if rec["rungs"]:
            total = sum(rec["rungs"].values())
            L.append("")
            L.append("    Where the refusals land:")
            for gate, n in rec["rungs"].most_common(8):
                bar = "█" * max(1, int(28 * n / total))
                L.append(f"      {gate:<26} {n:>5}  {n/total:>4.0%} {bar}")

        if rec["plans"]:
            L.append("")
            L.append("    Plans (intent that may never have traded):")
            for reason, n in rec["plans"].most_common(6):
                L.append(f"      {reason:<26} {n:>5}")

        # ── the comparison this whole file exists for ───────────────────
        # ⚠️ SIDE BY SIDE, SAME MEASURE, BOTH POPULATIONS. A derived value is
        # only informative if it DIFFERS between what fired and what did not;
        # printing either alone tells you nothing about the boundary.
        keys = [k for k in sorted(set(rec["vec_fired"]) | set(rec["vec_declined"]))
                if len(rec["vec_fired"].get(k, [])) >= 3
                and len(rec["vec_declined"].get(k, [])) >= 3]
        if keys:
            L.append("")
            L.append("    Derived vector — TAKEN vs SKIPPED   (p10 / median / p90)")
            for k in keys[:12]:
                L.append(f"      {k:<24}")
                L.append(f"        taken   {_spread(rec['vec_fired'][k])}")
                L.append(f"        skipped {_spread(rec['vec_declined'][k])}")
        else:
            L.append("")
            L.append("    Derived vector: not enough paired observations yet.")
        L.append("")
    L.append("=" * 74)
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--from", dest="frm")
    ap.add_argument("--to", dest="to")
    ap.add_argument("--setup", help="filter to one setup type")
    ap.add_argument("--db", default=None,
                    help="EXPLICIT local escape hatch: read this "
                         "derived_store.db instead of S3. Default is the "
                         "warehouse, which is the only source that works on "
                         "control.")
    a = ap.parse_args(argv[1:] if argv else None)

    dates = _dates(a)
    src, notes = (_rows_sqlite(a.db, dates) if a.db else _rows_warehouse(dates))
    for n in notes:
        print("  " + n)
    print()
    if src is None:
        # ⚠️ SAY WHICH, NEVER RENDER AN EMPTY REPORT. "the source could not be
        # read" and "no evaluations that day" are different facts, and an empty
        # section conflates them into the answer you were hoping for.
        print("  Nothing was read, so there is no report — the lines above "
              "say why.")
        print("  On control the default (S3) is the working source; --db is "
              "for running this ON A BOX.")
        return 1
    print(render(collect(src, dates), dates, a.setup))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
