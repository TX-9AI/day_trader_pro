#!/usr/bin/env python3
# day_trader_pro/tools/plan_dupe_probe.py — v1.0
# v1.0 (2026-09-05) — dtp r295 / RPT.5. WHY DOES ONE TRIGGER LEAVE TWO
#   PLAN-LEDGER ROWS?
#
#   🔴 THE OBSERVATION: CRM printed `RunawayContinuation [TRIGGERED] @ 259.38`
#   TWICE. r199 collapses duplicates FOR DISPLAY and prints how many it
#   collapsed, so the duplication stays visible — it does not explain it, and
#   the backlog row says plainly: *"a write-side question nobody has asked
#   yet. Do not mask it further."*
#
#   🔑 WHAT THE CODE ALREADY TELLS US, AND WHY THAT IS NOT THE ANSWER.
#   `plan_ledger.open_plan()` mints `uuid4().hex[:16]` per call, so two rows
#   means `_ledger_open` RAN TWICE. r212 already closes the previous unfilled
#   plan of that strategy first, with `terminal_reason = "superseded — never
#   filled"`. So two rows may be entirely CORRECT — two genuine intents, the
#   first refused an entry and superseded — or a real double-write. **Those
#   look identical in a display collapse and are opposite findings.**
#
#   ⚠️ SO THIS MEASURES INSTEAD OF ARGUING. For every cluster sharing
#   (symbol, strategy, trigger_price) it prints each row's state, its terminal
#   reason and the gap between them. The verdict falls out of the states:
#     · earlier row `superseded — never filled` → the r212 path, WORKING. The
#       strategy re-armed after a refused entry. A strategy question, not a
#       ledger defect.
#     · earlier row still LIVE, or terminal for another reason → a genuine
#       double-write, and the ledger is wrong.
#     · gap ≈ 0s → the same tick wrote twice, which r212's own reasoning says
#       cannot happen ("take() and the entry attempt happen on the SAME tick").
#
#   ⚠️ A STUDY, NOT A MENU ITEM (operator, 2026-09-01: "we run those as separate
#   studies from the CLI"). It takes real arguments and can be re-run over a
#   different range without a prompt in between.
#
# Run:  python3 tools/plan_dupe_probe.py --from 2026-09-01 --to 2026-09-04
#       python3 tools/plan_dupe_probe.py --from 2026-09-04 --sym CRM
"""Cluster plan_ledger rows that share a trigger, and name the mechanism."""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ettime                                            # noqa: E402
import warehouse_cache as WCACHE                         # noqa: E402

# `plan_id` is the table's whole primary key — without it the cache cannot
# collapse this table at all and would report CDC duplicates as findings
# (dtp r286). `terminal_reason` is what distinguishes the two verdicts.
NEED = ["plan_id", "strategy", "state", "created_ts", "trigger_price",
        "direction", "terminal_reason"]

SUPERSEDED = "superseded"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--from", dest="d0", default=None,
                    help="ET start date (default: today)")
    ap.add_argument("--to", dest="d1", default=None, help="ET end date")
    ap.add_argument("--sym", default=None, help="limit to one symbol")
    a = ap.parse_args(argv)

    # ⚠️ ET, VIA THE BOUNDARY (TZ.1). A report asked for "today" after 20:00 ET
    # on a UTC box otherwise asks for tomorrow and finds nothing.
    d0 = ettime.operator_date(a.d0)
    d1 = ettime.operator_date(a.d1) if a.d1 else d0
    # ⚠️ THE DAY COUNT COMES FROM DATE ARITHMETIC, NOT FROM DIVIDING EPOCHS.
    # A first cut computed it from `et_bounds` seconds // 86400, which yields a
    # FLOAT and blew up inside `range()` — and would have been an hour wrong
    # across a DST boundary even if it had not.
    from datetime import date as _date
    span = (_date.fromisoformat(d1) - _date.fromisoformat(d0)).days + 1
    if span < 1:
        raise SystemExit(f"--from {d0} is after --to {d1}")
    dates = ettime.days_back(span, end=d1)

    cache = WCACHE.WarehouseCache("plandupe")
    syms = [a.sym.upper()] if a.sym else None
    n = cache.load("plan_ledger", dates, NEED, syms=syms)
    print(f"plan_ledger {d0}..{d1}: {n:,} row(s) — "
          f"{cache.collapse_note('plan_ledger')}")
    if not n:
        # ⚠️ AN EMPTY RANGE IS A REAL RESULT, NOT A MISSING PATH — this report's
        # own house rule, and the reason it is said out loud.
        print("  no plans in range (a real empty result, not a missing path)")
        return 0

    rows = cache.query('SELECT symbol, strategy, state, created_ts, '
                       'trigger_price, direction, terminal_reason '
                       'FROM "plan_ledger" ORDER BY created_ts')
    clusters = defaultdict(list)
    for r in rows:
        tp = r["trigger_price"]
        if tp is None:
            continue
        # Round to the cent: a trigger is a price, and float equality on a
        # price is a way to miss the thing you are looking for.
        clusters[(r["symbol"], r["strategy"], round(float(tp), 2))].append(r)

    dupes = {k: v for k, v in clusters.items() if len(v) > 1}
    print(f"  {len(clusters):,} distinct trigger(s); "
          f"{len(dupes):,} with more than one row")
    if not dupes:
        print("  ✅ no duplicate-trigger clusters in this range")
        return 0

    worked = broken = 0
    for (sym, strat, price), rs in sorted(dupes.items()):
        rs.sort(key=lambda r: r["created_ts"] or 0)
        gap = (rs[-1]["created_ts"] or 0) - (rs[0]["created_ts"] or 0)
        earlier = rs[0]
        reason = (earlier["terminal_reason"] or "").lower()
        if SUPERSEDED in reason:
            verdict = "r212 supersession — the ledger is doing its job"
            worked += 1
        elif not reason and (earlier["state"] or "").upper() not in ("CLOSED",):
            verdict = ("🔴 EARLIER ROW STILL LIVE — a genuine double-write, "
                       "not supersession")
            broken += 1
        else:
            verdict = (f"🔴 earlier row terminal for another reason "
                       f"({earlier['terminal_reason']!r})")
            broken += 1
        print(f"\n  {sym} {strat} @ {price} — {len(rs)} rows, "
              f"{gap:.1f}s apart")
        print(f"    {verdict}")
        for r in rs:
            print(f"      {ettime.stamp_et(r['created_ts'])}  "
                  f"{(r['state'] or '?'):<12} {(r['direction'] or '?'):<5} "
                  f"{r['terminal_reason'] or '—'}")
        # ⚠️ A ZERO GAP CONTRADICTS r212's OWN REASONING — "take() and the entry
        # attempt happen on the SAME tick, so by the time the next one fires
        # the previous has resolved." Two rows in the same second means that
        # assumption does not hold, whatever the states say.
        if gap < 1.0:
            print("      ⚠️ SAME-SECOND: r212 assumes the previous plan has "
                  "resolved before the next fires. It had not.")

    print(f"\n  {worked} cluster(s) explained by supersession, "
          f"{broken} unexplained")
    # Non-zero only for the unexplained ones: supersession is the designed
    # path and must not read as a failure.
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
