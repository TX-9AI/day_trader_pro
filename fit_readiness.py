#!/usr/bin/env python3
"""
day_trader_pro/fit_readiness.py  v1.0
Per setup type: what fired, what was declined, and whether it is FITTABLE yet.

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

Run:  python3 fit_readiness.py                      # today
      python3 fit_readiness.py --date 2026-08-24
      python3 fit_readiness.py --from A --to B      # a range
      python3 fit_readiness.py --setup ORBStrategy  # one section
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


def collect(dc, dates: list) -> dict:
    """Per strategy: fired/declined rows, rung histogram, derived vectors."""
    out = defaultdict(lambda: {
        "fired": [], "declined": [], "rungs": Counter(),
        "plans": Counter(), "vec_fired": defaultdict(list),
        "vec_declined": defaultdict(list)})
    if dc is None:
        return out

    lo = datetime.strptime(dates[0], "%Y-%m-%d").timestamp()
    hi = datetime.strptime(dates[-1], "%Y-%m-%d").timestamp() + 86400

    # ── the two populations, from ONE table ─────────────────────────────
    # ⚠️ `strategy_note` HOLDS BOTH SIDES BY DESIGN: one row per strategy
    # EVALUATION, fired and declined alike, each carrying the derived vector
    # that was true at the moment the engine looked. That is what makes the
    # comparison possible at all — the skipped trades have snapshots too.
    try:
        cur = dc.execute(
            "SELECT strategy, fired, outcome, payload FROM strategy_note"
            " WHERE ts_epoch >= ? AND ts_epoch < ?", (lo, hi))
        for strat, fired, outcome, payload in cur.fetchall():
            rec = out[strat]
            try:
                p = json.loads(payload) if payload else {}
            except Exception:                                   # noqa: BLE001
                p = {}
            side = "fired" if fired else "declined"
            rec[side].append(p)
            bucket = rec["vec_fired"] if fired else rec["vec_declined"]
            for k, v in p.items():
                fv = _f(v)
                if fv is not None:
                    bucket[k].append(fv)
            if not fired and outcome:
                rec["rungs"][str(outcome)[:48]] += 1
    except sqlite3.Error:
        pass

    # ── which rung refused, from the gate reporter ──────────────────────
    try:
        cur = dc.execute(
            "SELECT strategy, gate, COUNT(*) FROM gate_disposition"
            " WHERE ts_epoch >= ? AND ts_epoch < ? AND event != 'CLEARED'"
            " GROUP BY strategy, gate", (lo, hi))
        for strat, gate, n in cur.fetchall():
            out[strat]["rungs"][gate] += n
    except sqlite3.Error:
        pass

    # ── intent that never became a trade ────────────────────────────────
    try:
        cur = dc.execute(
            "SELECT strategy, COALESCE(terminal_reason,'(live)'), COUNT(*)"
            " FROM plan_ledger WHERE created_ts >= ? AND created_ts < ?"
            " GROUP BY strategy, terminal_reason", (lo, hi))
        for strat, reason, n in cur.fetchall():
            out[strat]["plans"][reason] += n
    except sqlite3.Error:
        pass
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
    ap.add_argument("--db", default=os.path.expanduser(
        "~/options-trader/data/derived_store.db"))
    a = ap.parse_args(argv[1:] if argv else None)

    dates = _dates(a)
    dc = _connect(a.db)
    if dc is None:
        # ⚠️ SAY WHICH, NEVER RENDER AN EMPTY REPORT. "no derived store here"
        # and "no evaluations that day" are different facts and an empty
        # section conflates them.
        print(f"No derived store at {a.db}.")
        print("On control this reads a PULLED copy; on a box it reads the "
              "live one. Point --db at the store you mean.")
        return 1
    data = collect(dc, dates)
    print(render(data, dates, a.setup))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
