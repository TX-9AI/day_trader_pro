#!/usr/bin/env python3
# day_trader_pro/tools/plan_dupe_probe.py — v1.2
# v1.2 (2026-09-05) — dtp r297. A BULK RESTART WIPE IS NOT AN OVERLAP, AND THE
#   ARITHMETIC SAYS SO. First v1.1 run over 09-01..09-04: 262 plans, 41 series,
#   ZERO never closed, and **all 31 overlaps were `WIPED_BY_RESTART` on
#   2026-09-01** — the session the operator had already stopped and hotfixed by
#   hand. Their spans ran 18,000-20,700s, five to six HOURS, because a wipe
#   stamps `closed_ts` on every live plan at the moment of the restart: plans
#   opened at 10:16, 10:23, 10:48 and 10:50 all take the same late close time
#   and therefore all overlap each other. **Five wiped plans produce ten
#   pairs.** That is arithmetic, not a double-write.
#   🔑 SO THE VERDICT IS SEPARATED, NOT SUPPRESSED. Wipe-closed pairs still
#   print, under their own heading and with the count, because r199's whole
#   lesson is that hiding duplication is what left this question open for
#   weeks. They just do not set the exit code.
#   ⚠️ AND THE ANSWER TO RPT.5 IS IN THIS FILE'S HISTORY: outside the wipes
#   there are NO overlapping live plans. r212's supersession works,
#   `close_unfilled` leaves nothing open, and CRM's two rows at 259.38 were two
#   genuine intents.
# v1.1 (2026-09-05) — dtp r296.
# v1.1 (2026-09-05) — dtp r296. 🔴 v1.0 CLUSTERED ON THE WRONG KEY AND REPORTED
#   THE TRADE LOG AS A DEFECT. It grouped on (symbol, strategy, trigger_price),
#   assuming a trigger price identifies an EVENT. It does not — **it is a
#   SESSION LEVEL.** ORB's opening range and Runaway's breakout level are fixed
#   for the day, so every re-entry shares one. First real run, 2026-09-01..04:
#   32 clusters "unexplained", including META RunawayContinuation @ 594.10 with
#   27 rows — **27 separate completed trades**, each with its own exit and its
#   own P&L, reported as duplication. Zero of the 32 were the double-write
#   RPT.5 asks about.
#   🔑 THE KEY IS AN OVERLAP, NOT A PRICE. `plan_ledger.live_plans()` selects on
#   `closed_ts IS NULL`, so "two intents at once" means one plan opened while
#   another of the SAME strategy was still live. That is the question RPT.5
#   actually poses, and it is answerable without guessing what a trigger means.
#   ⚠️ THE TRIGGER PRICE IS KEPT AS CONTEXT, NEVER AS THE KEY — re-entering the
#   same level is what these strategies DO.
# v1.0 (2026-09-05) — dtp r295 / RPT.5. WHY DOES ONE TRIGGER LEAVE TWO
#   PLAN-LEDGER ROWS? (superseded above)
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
"""Find plans that were live at the same time as another of their own strategy."""
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
# `closed_ts` IS THE WHOLE POINT of v1.1 — it is what `live_plans()` keys on,
# and without it an overlap cannot be seen at all.
NEED = ["plan_id", "strategy", "state", "created_ts", "closed_ts",
        "trigger_price", "direction", "terminal_reason"]

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

    rows = cache.query('SELECT symbol, strategy, state, created_ts, closed_ts, '
                       'trigger_price, direction, terminal_reason '
                       'FROM "plan_ledger" ORDER BY created_ts')

    # ── OVERLAP, NOT PRICE ──────────────────────────────────────────────────
    # Two intents at once for one strategy = a plan opened while an earlier one
    # of the same strategy was still live (`closed_ts IS NULL` is what
    # `live_plans()` selects on). Re-entering the same LEVEL is what these
    # strategies do all session; it is context, never the key.
    by_strat = defaultdict(list)
    for r in rows:
        by_strat[(r["symbol"], r["strategy"])].append(r)

    # 🔴 A WIPE CLOSES EVERY LIVE PLAN AT ONE INSTANT, so wiped plans overlap
    # each other by construction. Kept and counted, never silently dropped.
    def _wiped(r):
        # ⚠️ INDEXED, NOT `.get()` — `cache.query` returns `sqlite3.Row`, which
        # has no `.get`. `fit_readiness` documents this exact hazard and I hit
        # it anyway.
        return "WIPED_BY_RESTART" in (r["terminal_reason"] or "")

    overlaps, wiped_pairs, live_at_end = [], [], 0
    for (sym, strat), rs in sorted(by_strat.items()):
        rs.sort(key=lambda r: r["created_ts"] or 0)
        for i, later in enumerate(rs):
            for earlier in rs[:i]:
                c0 = earlier["closed_ts"]
                if _wiped(earlier) or _wiped(later):
                    wiped_pairs.append((sym, strat, earlier, later))
                elif c0 is None:
                    # ⚠️ NEVER CLOSED AT ALL. r212's `close_unfilled` exists so
                    # this cannot happen; a plan still live when the next one
                    # opens is the leak it was written to stop.
                    overlaps.append((sym, strat, earlier, later, None))
                elif (later["created_ts"] or 0) < c0:
                    overlaps.append((sym, strat, earlier, later,
                                     c0 - (later["created_ts"] or 0)))
        live_at_end += sum(1 for r in rs if r["closed_ts"] is None)

    print(f"  {len(by_strat):,} (symbol, strategy) series; "
          f"{len(rows):,} plans; {live_at_end:,} never closed")
    if wiped_pairs:
        boxes = sorted({p[0] for p in wiped_pairs})
        print(f"  ▪ {len(wiped_pairs)} pair(s) involve WIPED_BY_RESTART "
              f"({', '.join(boxes)}) — a bulk wipe closes every live plan at "
              f"one instant, so those overlap each other by construction. "
              f"Reported, not counted.")
    if not overlaps:
        print("  ✅ no overlapping live plans — every intent closed before the "
              "next of its strategy opened")
        return 0

    print(f"  🔴 {len(overlaps)} overlapping pair(s) — two live intents for one "
          f"strategy")
    for sym, strat, e, l, secs in overlaps[:40]:
        span = "earlier NEVER CLOSED" if secs is None else f"overlap {secs:.1f}s"
        print(f"\n  {sym} {strat} — {span}")
        print(f"    earlier {ettime.stamp_et(e['created_ts'])} "
              f"{(e['state'] or '?'):<10} @ {e['trigger_price']} "
              f"{e['terminal_reason'] or '— still live'}")
        print(f"    later   {ettime.stamp_et(l['created_ts'])} "
              f"{(l['state'] or '?'):<10} @ {l['trigger_price']}")
    if len(overlaps) > 40:
        print(f"\n  … {len(overlaps) - 40} more")
    return 1


if __name__ == "__main__":
    sys.exit(main())
