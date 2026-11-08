#!/usr/bin/env python3
"""
day_trader_pro/fit_readiness.py — v1.10
v1.10 2026-11-08 — dtp r532 / OTV4DEP.1 (hygiene queue item 6). 🔴 THE REPORT LISTED RETIRED STRATEGIES. Old
      gate_disposition and plan rows still carry names that no longer trade (TrendCreditSpread, and the CreditRoll
      management plan), so 11-02..11-06 printed them as setups with 0 trades. The operator, 2026-10-31: "don't list the
      retired strategies either." `render` now lists only strategy_registry's LIVE set; every other name with rows is
      COUNTED in one closing line (how many names, how many rows), never named, so nothing is dropped silently.
      `collect` and the verdict are unchanged; the decode maps that read old rows stay.
v1.9  2026-11-08 — dtp r531 / FIT.3 (Saturday brief 11-07 D7, carried). 🔴 READY COUNTED SIGNAL ROWS AS IF THEY WERE TRADES. `verdict()` floored "fired" at MIN_FIRED, and `fired` is the number of `strategy_note` rows whose evaluation fired - one per TICK while a plan stays armed - so 11-02..11-06 printed LiquidityHunt READY on 4,383 "fired" against 32 closed trades and RunawayContinuation on 8,114 against 39. The outcome floor is about OUTCOMES, and an outcome is a trade. 🔑 THE FLOOR NOW READS CLOSED TRADES (MIN_TRADES 30), counted per strategy from the warehouse `trades` prefix (latest state per trade_id, OTV4TEST rows dropped through strategy_registry.resolve_lineage, ET entry day inside the window), or from the box's own trades.db beside --db. ⚠️ FAILS CLOSED: a trade source that cannot be read is NOT READY with the reason named, never READY on signal rows. ⚠️ NO COLUMN DROPPED: `fired` and `declined` still print, the fired line now says it counts signal rows, and a `trades` line is added. The operator, 2026-11-07: "Try not to suggest 'log only' as the proposed fix".
v1.8  2026-09-20 — r397 / D3 — THE VOLUME FLOOR AND THE JUDGEMENT WERE APPLIED TO DIFFERENT POPULATIONS. `verdict()` tested `MIN_DECLINED` against `declined` — for ORBStrategy over 2026-09-14..09-18 that is **3,362, of which 3,265 are `manage`** — and then ran the dominance test over an ENTRY sample of **3**, emitting "100% of declines are 'entry_underwater'" while the report printed `declined 3362` two lines above. A factor of 1,120 between the number in the sentence and the number in the verdict, on the strategy carrying the operator's open question. It cost the 2026-09-20 brief a full reconciliation pass and came within one step of overturning a correct finding from the week before. 🔑 THE FLOOR NOW GUARDS THE POPULATION IT IS ABOUT (`total`, the entry-rung count the histogram has always printed correctly) and the message NAMES ITS DENOMINATOR. ⚠️ THE dtp-r267 SPLIT ITSELF IS UNTOUCHED AND CORRECT — the defect was the sentence and the floor, not the design. ⚠️ `management_rungs()` is extracted so `verdict()` and `render()` share one definition, and it DERIVES rather than subtracting: `rungs` is fed from strategy_note, gate_disposition AND plan_ledger, so `declined - entry_total` is not the management count.
v1.7  2026-09-08 — dtp r322 / CND.1 — THE SAME r287 MISTAKE, IN THE SAME REVISION. `import ettime` sat inside this module's docstring, so `today_et()` at the bottom of `_dates()` raised NameError. Menu item 47 (FIT READINESS) would have died on use; it is run by hand rather than by timer, which is the only reason it was not noticed first. Moved to the import block and verified by execution.
v1.6  2026-09-05 — dtp r287 / TZ.1 — the naive `today` here asked a UTC box and rolled at 20:00 ET (19:00 in winter), so a report run after that silently asked for TOMORROW and came back empty. It now goes through `ettime`, the one ET/UTC boundary.
v1.5  2026-09-05 — dtp r286 / S3.11. 🔴 THE SOURCE BANNER DESCRIBED A COLLAPSE
      THAT NEVER TOUCHED THIS REPORT'S DATA. It printed "N after collapse by
      (_rid, ts)" — a number computed over the cache — while the docstring
      above claimed the real collapse ran upstream in
      `warehouse_reader.load_derived`. NEITHER WAS TRUE: `load_derived` has no
      production callers, and `WarehouseCache.load`, the path this report
      actually takes, collapsed nothing. The count was real and the sentence
      was false, which is the worse half of the two.
      🔑 THE COLLAPSE MOVED INTO THE CACHE (dtp r286), so `n` is already the
      post-collapse count, and the banner now ASKS which rule ran through
      `collapse_note()` instead of asserting one.
      🔴 AND `plan_ledger` GAINS `plan_id` — not cosmetic. It is that table's
      entire primary key, and without it in the projection the cache cannot
      collapse plan_ledger at all; it would have to fold on a subset and merge
      every plan in the range. One column buys correct de-duplication.

v1.4  2026-09-04 — dtp r267. TWO WRONG POPULATIONS, NEITHER A DATA
      PROBLEM. (1) STRATEGY_ALIAS canonicalises on READ: otv4 stamped the raw
      dispatch label on strategy_note while plans and gates used the class
      name, so the report showed "ORB" (78 fired, ZERO declined) and
      "ORBStrategy" (zero fired, 4,260 declined) as two strategies and
      neither arm could ever be fittable. otv4 r239 fixes the writer; this
      map exists because that only helps TOMORROW, and a report that cannot
      read its own history is not a fix.
      (2) `manage` IS NOT AN ENTRY RUNG — it is the management path declining
      to act on an OPEN position, and it held 70%% of the butterfly's
      refusals, 89%% of the runaway's and 100%% of two others. The verdict
      read "one rung dominates, so there is no surface to fit": a true
      sentence about the wrong population. Split, not dropped — the count
      still prints, on its own line, where it cannot share a denominator
      with an entry gate.
# v1.3  2026-09-04 — dtp r266. 🔴 THE SECOND COLLAPSE WAS THE ONE THAT
#       DROPPED ROWS. `SELECT * FROM t GROUP BY _rid` ran across the whole date
#       range and undid the upstream partition-scoped collapse. Removing it
#       outright let a re-pushed object DOUBLE-COUNT (caught by
#       test_fit_readiness_memory M4), so the de-dup returns on (_rid, ts): two
#       sessions' row 1 have different timestamps, one object pushed twice does
#       not. `_NEED` gains the timestamp column per table to make that possible.
Per setup type: what fired, what was declined, and whether it is FITTABLE yet.

v1.2  2026-09-02  dtp r245 — 🔴 OOM-KILLED TWICE ON THE SAME RANGE, FROM
  TWO INDEPENDENT CAUSES, AND I FIXED THE WRONG ONE FIRST.
  (1) `collect()` retained EVERY PAYLOAD DICT in `fired`/`declined`, and both
  are consumed only by `len()` — several GB held to produce two integers. They
  are counters now, and the derived vectors are `array('d')` rather than lists:
  8 bytes a value against ~32 for a boxed float, quantiles still exact.
  (2) `load_derived` materialised all three tables. They stream through
  warehouse_cache now, projected to the columns actually read, with the CDC
  collapse preserved UPSTREAM in load_derived, scoped to its partition
  by (symbol, dt, _rid) — r266. It is NOT repeated here.
  ⚠️ r240 ADDED A PROGRESS METER HERE AND I SAID AT THE TIME IT MAKES THE WAIT
  VISIBLE, NOT SMALLER. It did exactly that and the operator was killed again.
  A meter on a known memory fault is instrumentation standing in for a fix.

v1.1  2026-08-29  r184 / dtp r226 — THE WAREHOUSE IS THE SOURCE (backlog S3.2).
  🔴 THIS REPORT HAS NEVER PRODUCED A NUMBER ON CONTROL, AND THE REASON WAS
  A PATH. `--db` defaulted to `~/options-trader/data/derived_store.db` — a
  BOX path. WORKING_AGREEMENT 3 is explicit that `~/options-trader` does not
  exist on the control server, so devtools item 57 has always printed "No
  derived store at ..." unless somebody hand-scp'd a copy, which nobody did.
  It failed loudly, which is why it was never mistaken for a flat result —
  and also why it sat unnoticed as a menu item that could not work.
  Now: `WarehouseCache.load()` for each of the three tables — and NOT
  `warehouse_reader.load_derived()`, which this line used to name. That
  function carries the same natural-key collapse and has no production
  callers; r286 moved the collapse into the cache, where the data is,
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
from array import array
from collections import Counter, defaultdict
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import warehouse_reader as wr    # noqa: E402  (needs HERE on sys.path first)
import ettime                                            # noqa: E402

# ⚠️ THE BAR IS DELIBERATELY CRUDE AND STATED OUT LOUD. These are not tuned
# numbers — they are the point at which a human should LOOK, not a verdict.
MIN_TRADES = 30           # closed trades; below this, outcome stats are noise (v1.9: was MIN_FIRED on signal rows)
MIN_FIRED = MIN_TRADES    # the old name, kept for any reader; v1.9 floors TRADES, never signal rows
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
    return [ettime.today_et()]


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


# ⚠️ r266 — THE TIMESTAMP COLUMN IS PART OF THE PROJECTION NOW. It is what
# makes the de-dup below partition-safe: `_rid` alone repeats across sessions
# because boxes rebuild their stores and rowids restart, but (_rid, ts) does
# not — two sessions' row 1 have different timestamps.
# 🔴 dtp-r267 — THE SAME SPLIT THE FLEET HAD. otv4 `_note_evaluation` stamped
# the raw `_safe_strategy` label on `strategy_note` while the plan and gate
# rows used the class name, so the report saw "ORB" (78 fired, ZERO declined)
# and "ORBStrategy" (zero fired, 4,260 declined) as two strategies, and
# neither arm could ever be fittable. otv4 r239 fixes the writer.
# ⚠️ THIS MAP EXISTS BECAUSE THE FIX ONLY HELPS TOMORROW. Every row already in
# the warehouse carries the old label, and a report that cannot read its own
# history is not a fix. Mirrors `strategy/plan.py:DISPATCH_ALIAS`.
STRATEGY_ALIAS = {
    "ORB": "ORBStrategy",
    "SweepForLeg2": "SweepCreditSpread",
    "CondorPlan": "IronCondorStrategy",
    "CondorLeg": "IronCondorStrategy",
}


def canon(strategy):
    return STRATEGY_ALIAS.get(str(strategy or ""), str(strategy or ""))


_NEED = {
    "strategy_note":    ["_rid", "ts_epoch", "strategy", "fired", "outcome",
                         "payload"],
    "gate_disposition": ["_rid", "ts_epoch", "strategy", "gate", "event"],
    # 🔴 r286 — `plan_id` ADDED, AND IT IS NOT COSMETIC. It is this table's whole
    # primary key, and without it in the projection the cache CANNOT collapse
    # plan_ledger — it would have to fold on a subset, merging every plan in
    # the range. One column buys the correct de-duplication.
    "plan_ledger":      ["plan_id", "_rid", "created_ts", "strategy", "terminal_reason"],
}
_DEDUP_TS = {"strategy_note": "ts_epoch", "gate_disposition": "ts_epoch",
             "plan_ledger": "created_ts"}


def _rows_warehouse(dates, cache):
    """The three tables from S3, STREAMED through a local cache.

    🔴 r245 — THIS RETURNED THREE FULLY MATERIALISED LISTS. `load_derived`
    downloads every object in a partition, parses it, holds a dict spanning the
    whole range plus a forward window and builds a second list. The operator
    was OOM-killed on 2026-08-24..09-01 TWICE — once before the meter existed
    and once after, because r240's meter made the wait visible, not smaller.
    Each table now streams into a projected sqlite table and `collect()`
    receives an ITERATOR: one object is parsed at a time and released.

    ⚠️ THE CDC COLLAPSE IS PRESERVED, IN SQL. `load_derived` keeps one row per
    `_rid`; dropping it would double-count any record pushed twice and inflate
    every number in the report. ⚠️ r266 — IT IS NOT REPEATED HERE. A second
    `GROUP BY _rid` cannot carry the partition, and rowids restart when a box
    rebuilds its store, so re-collapsing across a range folded whole sessions
    together and undid the upstream fix.
    ⚠️ AND THE PER-TABLE SOURCE BANNER SURVIVES. An unreachable bucket and a
    session with no evaluations must never render the same — this report's own
    stated contract, and a rewrite is exactly when that gets lost.
    """
    notes, src = [], {}
    for t in TABLES:
        try:
            n = cache.load(t, dates, _NEED[t])
        except Exception as exc:                                # noqa: BLE001
            notes.append(f"SOURCE: s3 [{t}] — 🔴 UNREADABLE: "
                         f"{type(exc).__name__}: {exc}")
            src[t] = []
            continue
        # 🔴 dtp-r266 — THIS SECOND COLLAPSE WAS THE ONE THE REPORT PRINTED,
        # AND IT WAS WRONG THE SAME WAY THE READER WAS. `_rid` is the source
        # table's sqlite `rowid`, unique only within ONE box's table at ONE
        # moment; boxes purge and rebuild, so rowids restart and a GROUP BY
        # across a multi-day range folds different sessions' rows together.
        # It reported 325,762 -> 37,584 on 08-31..09-04 and made the butterfly
        # look like 2 fires when the trade log has 20.
        # ⚠️ THE COLLAPSE NOW HAPPENS ONCE, UPSTREAM, PARTITION-SCOPED, in
        # `warehouse_reader.load_derived`. Repeating it here on a key that
        # cannot carry the partition would undo that fix silently — so the
        # banner reports what was LOADED and names where the collapse ran,
        # rather than recomputing it against a key that does not identify a row.
        # 🔴 r286 — THIS LINE USED TO DESCRIBE A COLLAPSE THAT NEVER TOUCHED
        # THIS DATA. It computed `GROUP BY _rid, ts` over the cache and printed
        # it as "after collapse", while the docstring above claimed the real
        # collapse happened upstream in `warehouse_reader.load_derived`.
        # Neither was true: `load_derived` has NO production callers, and
        # `WarehouseCache.load` — the path every report actually takes —
        # collapsed nothing at all. The number was real and the sentence was
        # false, which is the worse half.
        # ⚠️ IT NOW ASKS THE CACHE WHICH RULE RAN rather than asserting one.
        # `n` is already the post-collapse count, because the cache dedupes at
        # insert through a UNIQUE index on the natural key.
        notes.append(f"SOURCE: s3 [{t}] — {n:,} row(s), "
                     f"{cache.collapse_note(t)}")
        # ⚠️ PLAIN DICTS, NOT sqlite3.Row. `collect()`'s own docstring says it
        # "takes plain dicts and knows nothing about the source", and that is
        # what keeps the local and warehouse runs from drifting into two
        # different sets of numbers. A Row has no `.get`, so handing one over
        # would both break it and quietly violate that contract.
        src[t] = (dict(r) for r in
                  # 🔴 dtp-r266 — THE `GROUP BY _rid` IS GONE, AND THIS WAS
                  # THE LINE THAT ACTUALLY DROPPED ROWS. `_rid` is the source
                  # table's sqlite rowid, unique only within ONE box's table
                  # at ONE moment; boxes purge and rebuild, so grouping on it
                  # across a multi-day range folded different sessions
                  # together. `load_derived` already collapses CDC correctly,
                  # scoped to its partition by (symbol, dt, _rid), so doing it
                  # again here on a key that cannot carry the partition
                  # silently undid that. Measured: the report read 2 fired
                  # GEX butterflies where the trade log has 20.
                  cache.iter(f'SELECT * FROM "{t}"'
                             f' GROUP BY _rid, {_DEDUP_TS[t]}'))
    return src, notes


def _entry_day(rec) -> str:
    """The ET session day a trade was ENTERED, from its ISO `entry_time` (UTC on every box)."""
    raw = str((rec or {}).get("entry_time") or "").strip()
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return raw[:10]
    if dt.tzinfo is None:                      # an untagged stamp is the box's UTC
        from datetime import timezone
        dt = dt.replace(tzinfo=timezone.utc)
    return ettime.et_day(dt.timestamp())


def trade_counts(rows, dates):
    """{strategy: n} CLOSED trades entered on an ET day in `dates`, OTV4TEST rows dropped. -> (counts, dropped).

    🔑 v1.9 — THE POPULATION READY FLOORS. One row per trade_id (the caller collapses push states). The lineage rule
    is strategy_registry.resolve_lineage, the same one every dtp rollup reads, so an OTV4TEST row (SOFI/AAL before
    their OTV5 day) never counts toward an OTV5 setup's readiness.
    """
    import strategy_registry as SR
    want, counts, dropped = set(dates), Counter(), 0
    for r in rows:
        if str(r.get("status") or "").lower() != "closed":
            continue
        day = _entry_day(r)
        if day not in want:
            continue
        if SR.resolve_lineage(r, day) == SR.TEST:
            dropped += 1
            continue
        counts[canon(r.get("strategy"))] += 1
    return counts, dropped


def _trades_warehouse(dates, s3=None):
    """Closed-trade counts from raw/trades. -> (counts or None, note). None = unreadable, named."""
    try:
        s3 = s3 or wr._client()
        objs = []
        # ⚠️ `dt=` on raw/trades is the PUSH day (UTC): a close after 19:00 ET files under the next day.
        last = datetime.strptime(dates[-1], "%Y-%m-%d").date() + timedelta(days=1)
        for d in list(dates) + [last.isoformat()]:
            objs.extend(wr.read_prefix(s3, "trades", d))
        rows = wr.latest_per_trade(objs)
    except Exception as exc:                                    # noqa: BLE001
        return None, f"SOURCE: s3 [trades] — 🔴 UNREADABLE: {type(exc).__name__}: {exc}"
    counts, dropped = trade_counts(rows, dates)
    return counts, (f"SOURCE: s3 [trades] — {sum(counts.values())} closed trade(s) in the window"
                    f", {dropped} OTV4TEST row(s) dropped")


def _trades_sqlite(db):
    """Closed-trade rows from the trades.db beside a --db derived store. -> (rows or None, note)."""
    path = os.path.join(os.path.dirname(os.path.abspath(db)), "trades.db")
    if not os.path.exists(path):
        return None, f"SOURCE: {path} — 🔴 NO trades.db BESIDE --db (READY cannot be judged)"
    try:
        tc = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        tc.row_factory = sqlite3.Row
        rows = [dict(r) for r in tc.execute("SELECT * FROM trades")]
        tc.close()
    except sqlite3.Error as exc:
        return None, f"SOURCE: {path} [trades] — 🔴 UNREADABLE: {exc}"
    return rows, f"SOURCE: {path} [trades] — {len(rows)} row(s)"


def collect(src: dict, dates: list, trades=None) -> dict:
    """Per strategy: fired/declined rows, rung histogram, derived vectors.

    🔑 IT TAKES PLAIN DICTS AND KNOWS NOTHING ABOUT THE SOURCE. Both
    loaders hand it the same shape, so the local and warehouse runs cannot
    drift into two different sets of numbers — the failure that took four
    instrumentation defects to find the last time two paths computed the
    "same" report.
    """
    # 🔴 r245 — THIS FUNCTION WAS THE OOM, NOT THE FETCH. `fired` and
    # `declined` held EVERY PAYLOAD DICT — and both are consumed only by
    # `len()`, in `verdict()` and in `render()`. A payload with thirty keys is
    # roughly 3-4 KB as a Python dict; a million evaluations over a nine-day
    # range is several GB retained to produce two integers.
    # ⚠️ AND THE VECTORS ARE `array('d')`, NOT LISTS. Only p10/median/p90 are
    # ever read off them, but the quantiles must stay EXACT, so sampling is
    # wrong — an array of doubles is 8 bytes per value against ~32 for a
    # boxed float in a list, so the same numbers cost a quarter as much.
    # 🔑 r242's LESSON, APPLIED WHERE IT BELONGS: I fixed the fetch yesterday
    # and left the analysis, and the operator hit the same kill twice.
    out = defaultdict(lambda: {
        "fired": 0, "declined": 0, "rungs": Counter(),
        "plans": Counter(), "vec_fired": defaultdict(lambda: array("d")),
        "vec_declined": defaultdict(lambda: array("d")), "trades": None})
    # 🔑 v1.9 — CLOSED TRADES PER STRATEGY, the population READY floors. `trades` is {strategy: n} from
    # trade_counts(), or None when the trade source could not be read (verdict() then fails closed and says so).
    if trades is not None:
        for strat, n in trades.items():
            out[canon(strat)]["trades"] = int(n)
    if not src:
        return out

    # ⚠️ `strategy_note` HOLDS BOTH SIDES BY DESIGN: one row per strategy
    # EVALUATION, fired and declined alike, each carrying the derived vector
    # that was true at the moment the engine looked. That is what makes the
    # comparison possible at all — the skipped trades have snapshots too.
    for r in src.get("strategy_note") or []:
        strat = canon(r.get("strategy"))   # dtp-r267
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
        rec["fired" if fired else "declined"] += 1
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
        strat, gate = canon(r.get("strategy")), r.get("gate")   # dtp-r267
        if strat and gate:
            out[strat]["rungs"][gate] += 1

    # intent that never became a trade
    for r in src.get("plan_ledger") or []:
        strat = canon(r.get("strategy"))   # dtp-r267
        if strat:
            out[strat]["plans"][r.get("terminal_reason") or "(live)"] += 1
    if trades is not None:
        # ⚠️ A STRATEGY SEEN ONLY IN THE DERIVED ROWS TRADED ZERO TIMES - a read source, not an unread one.
        for strat in out:
            if out[strat]["trades"] is None:
                out[strat]["trades"] = 0
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


# 🔴 dtp-r267 — `manage` IS NOT AN ENTRY RUNG. It is the MANAGEMENT path
# declining to act on an OPEN position, and it swamped every strategy's
# distribution: 70% of the butterfly's refusals, 89% of the runaway's, 100% of
# IronCondorStrategy's and ORBStrategy's. The verdict then read "one rung
# dominates, so there is no surface to fit" — a true sentence about the wrong
# population. The butterfly's actual entry story was underneath it:
# wing_search 461, entry_window 296, legs 152.
# ⚠️ SPLIT, NOT DROPPED. A management decline is a real event and its count is
# still printed — on its own line, where it cannot be mistaken for an entry
# refusal or dominate a share that is computed over entries.
MANAGEMENT_RUNGS = {"manage"}


def entry_rungs(rungs):
    """The rungs that describe an ENTRY decision. Management is reported apart."""
    return {g: n for g, n in rungs.items() if g not in MANAGEMENT_RUNGS}


def management_rungs(rungs):
    """The rungs that describe a MANAGEMENT decision. Counterpart of the above.

    🔑 r397 — EXTRACTED SO THERE IS ONE DEFINITION. `render()` derived this
    inline while `verdict()` did not derive it at all, which is how the two
    came to disagree about which population they were describing.
    ⚠️ AND IT IS DERIVED, NEVER SUBTRACTED. `rec["declined"]` counts
    `strategy_note` rows only, while `rec["rungs"]` is fed from THREE sources
    — strategy_note outcomes, `gate_disposition` gates and `plan_ledger` — so
    `declined - entry_total` is not the management count and would silently
    drift the moment any of those three moves.
    """
    return {g: n for g, n in rungs.items() if g in MANAGEMENT_RUNGS}


def verdict(rec: dict) -> tuple:
    """(READY|NOT READY, reason). Coverage, not volume."""
    nf, nd = rec["fired"], rec["declined"]
    # 🔴 v1.9 — THE OUTCOME FLOOR READS CLOSED TRADES, NEVER SIGNAL ROWS. `fired` counts strategy_note rows whose
    # evaluation fired - one per TICK while a plan stays armed - and printed Hunt READY on 4,383 against 32 trades.
    nt = rec.get("trades")
    if nt is None:
        # ⚠️ FAILS CLOSED, BY NAME: no trade count is not zero trades, and it is never READY on signal rows.
        return ("NOT READY", f"closed-trade count unreadable ({nf} fired signal row(s) are evaluations, "
                             f"not trades; READY needs ~{MIN_TRADES} closed trades)")
    if nt < MIN_TRADES:
        return ("NOT READY", f"only {nt} closed trade(s) (need ~{MIN_TRADES} for outcomes; the {nf} fired "
                             f"signal row(s) are evaluations, not trades)")
    # ⚠️ dtp-r267 — computed over ENTRY rungs only. Including `manage` made
    # every strategy look un-fittable for a reason that has nothing to do with
    # its entry gates.
    _entry = entry_rungs(rec["rungs"])
    total = sum(_entry.values())
    _mgmt = sum(management_rungs(rec["rungs"]).values())
    # 🔴 r397 — THE VOLUME FLOOR AND THE JUDGEMENT WERE APPLIED TO DIFFERENT
    # POPULATIONS, AND THAT IS THE WHOLE DEFECT.
    # This read `if nd < MIN_DECLINED`, testing the floor against `declined`
    # — which for ORBStrategy over 2026-09-14..09-18 was **3,362, of which
    # 3,265 were `manage`** — and then ran the dominance test over an ENTRY
    # sample of **3**. So a setup cleared "enough declines to judge" on
    # MANAGEMENT traffic and was then declared un-fittable on three rows, and
    # the report printed `declined 3362` two lines above a verdict whose real
    # denominator was 1,120x smaller.
    # 🔑 THE FLOOR NOW GUARDS THE POPULATION IT IS ABOUT. `total` is the
    # entry-rung count — the same number the histogram below the verdict has
    # always printed correctly — so a dominance verdict can no longer rest on
    # a sample the floor never looked at.
    if total < MIN_DECLINED:
        _why = f"only {total} ENTRY refusal(s) on record (need ~{MIN_DECLINED})"
        if _mgmt:
            # ⚠️ NAMED, NOT DROPPED. "few entry refusals" and "plenty of
            # traffic, none of it about entry" are different states and must
            # not read the same (WA §0.5).
            _why += (f"; {_mgmt} of the {nd} decline(s) are MANAGEMENT, "
                     f"not entry")
        return "NOT READY", _why
    if total:
        top, n = max(_entry.items(), key=lambda kv: kv[1])
        share = n / total
        if share > MAX_RUNG_SHARE:
            # 🔴 THE FINDING THAT MATTERS MOST, AND THE ONE A ROW COUNT HIDES.
            # ⚠️ r397 — THE DENOMINATOR IS NAMED IN THE SENTENCE. It used to
            # read "N% of declines", borrowing a word this same report uses
            # for a different and much larger number one line above.
            return ("NOT READY",
                    f"{share:.0%} of the {total} recorded ENTRY refusals are "
                    f"'{top}' — one rung dominates, so there is no surface to "
                    f"fit; the data shows where the line IS, not where it "
                    f"should be")
    if len(_entry) < 2:
        return "NOT READY", "declines land on fewer than two distinct rungs"
    return ("READY", f"{nt} closed trade(s) / {nf} fired signal row(s) / {nd} declined across "
                     f"{len(rec['rungs'])} rungs")


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

    # v1.10 — only LIVE setups are listed (strategy_registry.status); the rest are counted below, never named.
    import strategy_registry as SR
    hidden_names, hidden_rows = 0, 0
    for strat in sorted(data):
        if only and only.lower() not in strat.lower():
            continue
        rec = data[strat]
        if SR.status(strat) != SR.LIVE:
            hidden_names += 1
            hidden_rows += int(rec.get("fired") or 0) + int(rec.get("declined") or 0)
            continue
        v, why = verdict(rec)
        L.append("─" * 74)
        L.append(f"  {strat}")
        L.append("─" * 74)
        L.append(f"    {v}: {why}")
        L.append("")
        _nt = rec.get("trades")
        L.append(f"    trades   {('unread' if _nt is None else _nt):>6}   closed trades - the population READY floors")
        L.append(f"    fired    {rec['fired']:>6}   signal rows (one per evaluation tick that fired), NOT trades")
        L.append(f"    declined {rec['declined']:>6}")

        _entry = entry_rungs(rec["rungs"])
        _mgmt = sum(management_rungs(rec["rungs"]).values())
        if _entry:
            total = sum(_entry.values())
            L.append("")
            L.append("    Where the ENTRY refusals land:")
            for gate, n in sorted(_entry.items(), key=lambda kv: -kv[1])[:8]:
                bar = "█" * max(1, int(28 * n / total))
                L.append(f"      {gate:<26} {n:>5}  {n/total:>4.0%} {bar}")
        elif rec["rungs"]:
            L.append("")
            L.append("    No ENTRY refusals recorded — every rung was management.")
        if _mgmt:
            # ⚠️ PRINTED, NOT DROPPED. A management decline is a real event;
            # it is simply not evidence about an entry gate, so it does not
            # share a denominator with one.
            L.append(f"    (management declines, not entry: {_mgmt:>5})")

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
    if hidden_names:
        L.append(f"  Not listed: {hidden_names} retired or non-strategy name(s) with {hidden_rows} row(s) in this window"
                 " (strategy_registry: not LIVE).")
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
    # ⚠️ THE CACHE MUST OUTLIVE THE ITERATORS. `collect()` consumes generators
    # backed by the cache's sqlite connection; closing it before collect() runs
    # would empty the report SILENTLY rather than erroring.
    _cache = None
    if a.db:
        src, notes = _rows_sqlite(a.db, dates)
        _trows, _tnote = _trades_sqlite(a.db)
        trades = None if _trows is None else trade_counts(_trows, dates)[0]
    else:
        import warehouse_cache as _wc
        _cache = _wc.WarehouseCache("fitready")
        src, notes = _rows_warehouse(dates, _cache)
        trades, _tnote = _trades_warehouse(dates)
    notes.append(_tnote)
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
    try:
        print(render(collect(src, dates, trades), dates, a.setup))
    finally:
        if _cache is not None:
            _cache.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
