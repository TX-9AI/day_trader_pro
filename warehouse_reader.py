#!/usr/bin/env python3
# day_trader_pro/warehouse_reader.py — v2.0
# v2.0  2026-09-05 — dtp r276. 🔴 THE CDC COLLAPSE KEYS ON THE TABLE'S OWN
#       DECLARED PRIMARY KEY. `_rid` was never an identity — it is the source
#       table's sqlite `rowid`, and r266 scoped it to the partition to stop two
#       sessions colliding. That fixed an UNDER-count and opened an OVER-count
#       in the same motion: one CDC row re-pushed on two days is one row and
#       two partitions, so the scoped key keeps BOTH copies. Every one of these
#       tables except `character_ledger` declares a PRIMARY KEY the box already
#       enforces, so the identity was sitting in the schema the whole time.
#       ⚠️ r266's STATED MECHANISM IS NOT ESTABLISHED and this does not rest on
#       it. Its comment says rowids restart because "boxes purge and rebuild
#       their derived stores"; `otv4/warehouse/retention_purge.py` at HEAD
#       touches the derived store ONLY for DERIVED_ARTIFACT_DAYS
#       (indicator/fork/surface_series), and `plan_check` and `plan_tick` are in
#       neither that list nor NEVER_PURGE — nothing deletes them and nothing
#       protects them by name. A box REBUILD restarts rowids; the nightly purge
#       does not. Keyed on the natural key, both readings are moot.
#       🔑 THE COUNT BECOMES SELF-VERIFYING. Distinct primary keys per ET day IS
#       the row population, so "is 2.38M complete" stops being unanswerable.
#       ⚠️ A MISSING KEY COMPONENT FALLS BACK TO r266's SCOPED `_rid` AND IS
#       COUNTED OUT LOUD in the banner. Absent is not zero: a silent fallback
#       would mean two collapse rules running with nothing saying which.
#       ⚠️ ABSENT IS TESTED AS `is None`, NEVER FALSINESS — `direction` is
#       NOT NULL DEFAULT '' and `ts_epoch` can be 0.0, and `x or DEFAULT`
#       rewrites a valid extreme into the sentinel for missing (C.45).
# v1.9  2026-09-04 — dtp r266. 🔴 THE CDC COLLAPSE KEY NOW CARRIES THE
#       PARTITION. `_rid` is the source table's sqlite `rowid` (otv4
#       s3_push:945), unique only within ONE box's table at ONE moment — boxes
#       purge and rebuild, so rowids RESTART every session and (QQQ, 1) on 09-01
#       collided with (QQQ, 1) on 09-04, later push winning. Measured
#       08-31..09-04: strategy_note 325,762 rows -> 37,584, and the fit report
#       read 2 fired GEX butterflies against 20 in the trade log. The collapse
#       itself is correct and stays; only its SCOPE was wrong.
# v1.8 (2026-09-01) — r240. PROGRESS ON THE SHARED FETCH PATH. Operator:
#   "the S3 options in devtools need a progress meter, some of them run
#   long" — 53.5s for one date, measured. fit_readiness, pnl_s3,
#   warehouse_coverage and eod_analysis all pull through `read_prefix` and
#   none had a meter; wiring it here covers every consumer rather than four
#   retrofits that drift. STDERR ONLY — report_parity diffs these reports'
#   OUTPUT, so a meter on stdout would land inside the comparison.
#   🔴 THE METER MAKES THE WAIT VISIBLE, NOT SMALLER: this function still
#   materialises the whole partition (RPT.10). warehouse_cache is the
#   streaming path.
# v1.7 (2026-08-29) — r184 / dtp r226. DERIVED-TABLE READER (backlog S3.2).
#      `load_derived()` returns the latest state of one derived_store table
#      from raw/derived_<table>/, CDC-collapsed latest-per-(symbol,_rid) by
#      pushed_at_utc — the same contract as the trade reader one level up.
#      Built so `fit_readiness.py` can run on control at all: its --db
#      pointed at ~/options-trader/data/derived_store.db, a BOX path that
#      does not exist on the control server (WORKING_AGREEMENT 3), so menu
#      57 has never produced a number there.
#      🔴 `dt=` ON A DERIVED PREFIX IS THE PUSH DAY, NOT THE ROW'S DAY, AND
#      READING ONE PARTITION PER REQUESTED DATE WOULD SILENTLY UNDER-REPORT.
#      push_derived files every CHANGED row under `datetime.now(ET).date()`
#      at push time — so a plan created Monday and updated Wednesday ships
#      into Wednesday's partition, and the FIRST push after any gap files a
#      whole table's history under that one day. This scans a forward window
#      of partitions and then files every row by ITS OWN timestamp converted
#      to the ET trading day. Partition selection and row attribution are
#      two different questions, and conflating them is how a join returns
#      nothing and looks like a flat day.
#      ⚠️ EMPTY AND UNREACHABLE STAY DIFFERENT FACTS. `read_prefix` raises
#      on a credential or network failure and returns [] for a partition
#      that simply holds nothing; both would print as "0 rows". Every load
#      returns a `WhMeta` whose banner names which, and the caller prints it.
# v1.6 (2026-08-16) — 🔴 SORT ORDER. The parity run showed report 40 differing
#      at one figure out of 421 — but the located lines revealed the reports
#      hold the SAME rows in a DIFFERENT ORDER, not different values
#      (`max_loss_floor/Continuation` vs `orb_structure_stop/ORBStrategy` at the
#      same position). consolidate_trades sorts trades by (box, entry_time);
#      this reader sorted by (entry_time, box). Trade-level equality was never
#      affected — which is why `--compare` said 153/153 — but any downstream
#      grouping that breaks ties by input order lands differently. Now matches
#      consolidate_trades exactly. **A "value" difference that is really an
#      ordering difference is the kind of finding that gets misdiagnosed as
#      data corruption.**
# v1.5 (2026-08-16) — an AWS failure printed a RAW TRACEBACK. Found by driving
#      the new menu items instead of the shell: item 65 dumped 11 lines of
#      botocore stack for what is really "no credentials". On control it has
#      credentials so this never showed in shell testing — which is the argument
#      for testing the path the operator actually uses.
# v1.4 (2026-08-16) — 🔴 THE DEFAULT OUTPUT PATH CONTAMINATED REPORT 41.
#      `--out` defaulted to `reports/fleet_trades_s3_<date>.json`, and report 41
#      globs `reports/fleet_trades_*.json`. So merely RUNNING this reader
#      silently injected warehouse-sourced bundles into 41's input set — and
#      because 41 de-dupes by keeping the MOST-FILLED row, an S3 row could win
#      over the local one. **The tool built to compare the two sources was
#      quietly merging them.** Output now goes to `reports/warehouse/`, which is
#      outside the glob (41's pattern is non-recursive), and a write into the
#      glob namespace is REFUSED rather than warned about.
# v1.3 (2026-08-16) — THE FLOOR WAS THE WRONG QUANTITY, and `--explain`.
#      v1.2 derived the floor from the earliest dt= partition and got
#      2026-07-06, which excluded nothing. **dt= coverage is not COLLECTION
#      coverage.** The first push ran 2026-08-13 and shipped every row then in
#      each box's trades.db, whose entry_time values reach back to early July —
#      so pre-08-13 dates hold only what SURVIVED on the boxes (trim_trade_dbs
#      trims them) and are partial by construction. The floor is now the
#      COLLECTION START, read from `meta/collection_start` if present and
#      otherwise OT_WAREHOUSE_START, defaulting to 2026-08-13.
#      `--explain <date>` lists the specific trade_ids on each side so a
#      divergence is READ rather than inferred.
# v1.2 (2026-08-16) — COVERAGE WINDOW, DERIVED NOT HARDCODED. `--all` flagged
#      pre-warehouse dates as divergent, which is noise: reports/ goes back to
#      07-13 and the bucket only holds 30 days. Asked whether to hardcode a
#      cutoff — a hardcoded date goes stale the moment history is backfilled or
#      lifecycle expires something, and then it lies in the safe direction,
#      silently skipping dates it should be checking. So the window is READ FROM
#      THE BUCKET: the earliest dt= partition present under raw/trades/, via one
#      LIST with a delimiter. Dates before it are reported as OUT OF COVERAGE —
#      a third category, never counted as either a match or a divergence.
#      `--since` overrides it when a date inside the window is known-partial.
# v1.1 (2026-08-16) — `--all`. The first --compare MATCHED exactly on 2026-08-14
#      (153 trades, net +5839.50, from 178 stored states). One date is not
#      evidence: it is one date. This sweeps every local bundle and reports a
#      per-date verdict plus a tally, so the claim being made is "N of N dates
#      reproduce" rather than "the one I happened to pick did".
# v1.0 (2026-08-16) — WH.8. Rebuilds the fleet_trades_<date> bundle from
#      s3://vertigo-warehouse-tx9ai instead of from the scp'd per-box DBs, so
#      reports 40/41 can be run against the warehouse and DIFFED against the
#      local pipeline. This is the read side the project has been missing:
#      eleven streams push IN and, until now, nothing read OUT.
"""
Warehouse reader — the S3 counterpart to consolidate_trades.py.

WHY IT DELIBERATELY IMPORTS FROM consolidate_trades
    `_stats`, `_load_selection` and `_num` are reused, not reimplemented. If
    this file computed its own win-rate the WH.11 diff would compare two
    ARITHMETICS as well as two SOURCES, and a mismatch would be ambiguous. The
    only thing that may differ between the two bundles is where the rows came
    from — everything downstream of the rows is literally the same code.

    `selection` also still comes from control's own `data/selection_log.jsonl`.
    It is control's file, not a box artifact; nothing pushes it and nothing
    should.

THE ONE PIECE OF REAL LOGIC HERE: LATEST-STATE-PER-TRADE
    A trade row MUTATES — written at entry, rewritten at exit — and the pusher
    stores each distinct state as its own immutable object. So the warehouse
    holds several versions of one trade, which is MORE than the local pipeline
    keeps, and the reader must collapse them: group by `trade_id`, keep the
    object with the latest `pushed_at_utc`. Report 40 then filters
    `status='closed'` on top of that.

    ⚠️ Collapse BEFORE filtering, never after. A trade that is open at 10:00
    and closed at 15:00 has objects in both states; filtering first and
    collapsing second would keep whichever happened to survive the filter and
    silently drop the trade if only its open state matched.

`box` COMES FROM THE PARTITION, NOT A FILENAME
    consolidate_trades tags each row with `box` taken from the DB FILENAME,
    calling it the authoritative fleet tag. The warehouse has no filenames, so
    the equivalent authority is the `sym=` partition the object was written
    under. The row's own `symbol` column is left untouched either way, so a
    mislabeled row cannot confuse the merge and both values survive for audit —
    same contract, different source.

CLI
  python3 warehouse_reader.py --date 2026-08-14
  python3 warehouse_reader.py --date 2026-08-14      # -> reports/warehouse/
  python3 warehouse_reader.py --date 2026-08-14 --compare   # diff vs the local bundle
  python3 warehouse_reader.py --all                        # compare EVERY local bundle
"""

import argparse
import json
import os
import sys
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import boto3

import config
import consolidate_trades as CT

BUCKET = os.environ.get("OT_S3_BUCKET", "vertigo-warehouse-tx9ai")
REGION = os.environ.get("OT_S3_REGION", "us-east-2")
PREFIX = os.environ.get("OT_S3_PREFIX", "raw")

_ET = ZoneInfo("US/Eastern")

# The date the warehouse began COLLECTING, which is not the same as the earliest
# dt= partition it holds: the first push shipped whatever history each box still
# had on disk, so earlier dates are partial by construction and comparing them
# to a full local bundle is meaningless.
COLLECTION_START = os.environ.get("OT_WAREHOUSE_START", "2026-08-13")

# Warehouse-sourced bundles live HERE, never in reports/ itself.
# report 41 globs reports/fleet_trades_*.json (non-recursive), so anything
# written beside it becomes 41's input whether or not that was intended.
WAREHOUSE_OUT = os.path.join(config.REPORTS_DIR, "warehouse")
GLOB_HAZARD = "fleet_trades_"


def _log(tag, msg):
    print(f"[{tag:<8}] {msg}")


def _client():
    return boto3.client("s3", region_name=REGION)


def _sym_of(key):
    """The `sym=` partition value — the warehouse's equivalent of the filename."""
    for part in key.split("/"):
        if part.startswith("sym="):
            return part[4:]
    return "?"


def read_prefix(s3, datatype, date):
    """Every object under raw/<datatype>/dt=<date>/, as (sym, envelope).

    ⚠️ r240 — PROGRESS IS REPORTED HERE because this is the shared fetch path:
    fit_readiness, pnl_s3, warehouse_coverage and eod_analysis all pull through
    it and NONE of them had a meter. Operator, 2026-09-01: "the S3 options in
    devtools need a progress meter, some of them run long" — the butterfly
    probe measured 53.5s for a single date.
    ⚠️ STDERR ONLY. `report_parity.py` diffs these reports' OUTPUT, so a meter
    on stdout would land inside the comparison.
    🔴 THIS FUNCTION STILL MATERIALISES THE WHOLE PARTITION (RPT.10) — the
    meter makes the wait visible, it does not make it smaller. `warehouse_cache`
    is the streaming path; this one is unchanged on purpose so the reports that
    depend on its return shape keep working.
    """
    from progress import Ticker
    out = []
    prefix = f"{PREFIX}/{datatype}/dt={date}/"
    pg = s3.get_paginator("list_objects_v2")
    keys = []
    for page in pg.paginate(Bucket=BUCKET, Prefix=prefix):
        for o in page.get("Contents", []) or []:
            keys.append((o["Key"], int(o.get("Size", 0) or 0)))
    tk = Ticker(f"{datatype} {date}", total=len(keys))
    for k, size in keys:
        try:
            body = s3.get_object(Bucket=BUCKET, Key=k)["Body"].read()
            out.append((_sym_of(k), json.loads(body)))
        except Exception as exc:
            _log("WARN", f"unreadable object {k}: {exc}")
        tk.step(1, size)
    tk.done()
    return out


class WhMeta:
    """What a warehouse read actually did. Never let empty look like broken.

    ⚠️ THIS EXISTS BECAUSE THE CONFLATION HAS COST THIS PROJECT TWICE IN ONE
    WEEK. A report that prints "0 evaluations" for a flat session and "0
    evaluations" for an expired credential is a report that cannot be acted
    on, and the second case looks exactly like the answer you were hoping
    for. The banner always prints, on success and failure alike.
    """

    def __init__(self, what):
        self.what = what
        self.partitions = 0      # dt= prefixes actually scanned
        self.objects = 0         # envelopes read
        self.rows = 0            # rows after CDC collapse
        self.kept = 0            # rows inside the requested ET window
        self.error = ""
        # r276 — WHICH COLLAPSE RULE RAN, and how many rows could not be
        # keyed by it. r266 already established that a printed number must
        # name the collapse that produced it; these two make that true of
        # the natural-key rule and of its fallback.
        self.collapsed_by = ""
        self.unkeyed = 0

    def banner(self) -> str:
        head = "SOURCE: s3://%s/%s [%s]" % (BUCKET, PREFIX, self.what)
        if self.error:
            return "%s — 🔴 COULD NOT READ THE WAREHOUSE: %s" % (head, self.error)
        tail = ("%d partition(s), %d object(s), %d row(s) after collapse, "
                "%d in window" % (self.partitions, self.objects,
                                  self.rows, self.kept))
        if self.collapsed_by:
            tail += "  [collapsed by %s]" % self.collapsed_by
        if self.unkeyed:
            tail += ("  ⚠️ %d row(s) lacked a key component and fell back to "
                     "(sym, dt, _rid)" % self.unkeyed)
        if self.objects == 0:
            tail += "  (a real, empty result — not a missing path)"
        return "%s — %s" % (head, tail)


def et_day(ts) -> str:
    """A unix epoch -> the ET TRADING DAY it belongs to.

    ⚠️ THE PREDICATE IS AN EXCHANGE FACT, NOT A DISPLAY CHOICE. Every
    ts_epoch in the derived store is UTC seconds and the control box runs
    UTC, so a naive `datetime.fromtimestamp(ts).date()` rolls the day at
    20:00 ET — the long-standing symptom that a report for "today" run
    after the close comes back wrong. Convert explicitly; never lean on the
    ambient clock.
    """
    try:
        return (datetime.fromtimestamp(float(ts), tz=timezone.utc)
                .astimezone(_ET).date().isoformat())
    except (TypeError, ValueError, OSError, OverflowError):
        return ""


def et_bounds(d0: str, d1: str) -> tuple:
    """[start, end) epoch seconds spanning the ET days d0..d1 inclusive."""
    a = datetime.strptime(d0, "%Y-%m-%d").replace(tzinfo=_ET)
    b = datetime.strptime(d1, "%Y-%m-%d").replace(tzinfo=_ET) + timedelta(days=1)
    return a.timestamp(), b.timestamp()


# A row is dated by the column that says when the THING happened. A plan is
# dated by when it was FORMED, not when it last changed state, or a plan that
# transitions on the next session would be counted twice or on the wrong day.
DERIVED_TS_COL = {"plan_ledger": "created_ts"}
DEFAULT_TS_COL = "ts_epoch"

# 🔑 r276 — EACH TABLE'S OWN DECLARED PRIMARY KEY. Read out of otv4's schemas,
# never invented, because a key this file made up would be a second definition
# of identity and the box would not be enforcing it:
#   fire_snapshot        data/derived_store.py:170
#   strategy_note        derived/notes.py:109
#   plan_ledger          derived/plan_ledger.py:144
#   plan_tick            strategy/plan.py:301
#   plan_check           strategy/plan.py:313
#   gate_disposition     analysis/gate_report.py:125
#   level_ledger         data/derived_store.py:127
#   exit_counterfactual  derived/counterfactual.py:80
# `screen_plan_gates` already groups its per-tick panel on plan_check's own PK
# (dtp r271) — the natural key is not a new idea here, it is the one that was
# already working in the one consumer that needed to be right.
#
# ⚠️ `character_ledger` IS DELIBERATELY ABSENT. Its key is
# `id INTEGER PRIMARY KEY AUTOINCREMENT` (derived/character_engine.py:83), and
# in sqlite an INTEGER PRIMARY KEY *is* the rowid — so it has no identity
# independent of `_rid` and falls back to r266's partition-scoped key. Listing
# it here would look like coverage and mean nothing.
DERIVED_NATURAL_KEY = {
    "fire_snapshot":       ("trade_id",),
    "strategy_note":       ("ts_epoch", "symbol", "strategy"),
    "plan_ledger":         ("plan_id",),
    "plan_tick":           ("ts_epoch", "symbol", "strategy", "direction"),
    "plan_check":          ("ts_epoch", "symbol", "strategy", "direction",
                            "check_name"),
    "gate_disposition":    ("ts_epoch", "symbol", "strategy"),
    "level_ledger":        ("level_id",),
    "exit_counterfactual": ("trade_id", "ts_epoch"),
}


def collapse_key(table, sym, part, row):
    """The identity of one derived row -> (key, keyed_naturally).

    The writing box rides in the key even when the table's own PK already
    carries `symbol`: two boxes are two stores, and cheap belt-and-braces
    beats a cross-box merge nobody would ever see.

    ⚠️ A COMPONENT IS ABSENT ONLY IF IT IS MISSING OR None. `direction` is
    `NOT NULL DEFAULT ''` and `ts_epoch` can legitimately be 0.0, so a
    falsiness test would rewrite valid values into the fallback — C.45, the
    `x or DEFAULT` idiom that turned the freshest sweep into the stale
    sentinel. Falling back is not free: it reinstates the r266 key, which
    over-counts a row pushed on two days.

    ⚠️ EXTRACTED TO MODULE LEVEL so the checker drives the real function
    rather than a copy of the arithmetic (C.23).
    """
    cols = DERIVED_NATURAL_KEY.get(table)
    if cols:
        vals = []
        for c in cols:
            if c not in row or row[c] is None:
                vals = None
                break
            vals.append(row[c])
        if vals is not None:
            return (sym, "PK", tuple(vals)), True
    return (sym, "RID", part, row.get("_rid")), False

# How many days PAST the requested window to scan for late-pushed rows. Three
# covers a weekend plus one night the pusher did not run. Raising it costs
# LIST calls, never correctness; lowering it can silently drop rows.
DERIVED_FORWARD_DAYS = int(os.environ.get("DTP_DERIVED_FORWARD_DAYS", "3"))


def load_derived(table, dates, s3=None, forward=None):
    """Latest state of one derived_store table for the ET days `dates`.

    -> (rows, WhMeta). Rows are plain dicts exactly as the box wrote them,
    collapsed latest-per-(box, PRIMARY KEY) by `pushed_at_utc` — r276, see
    `collapse_key` — then filtered to the requested ET days by each row's own
    timestamp column. The banner names the rule that ran and counts any row
    that had to fall back to the partition-scoped `_rid`.
    """
    meta = WhMeta("derived_%s %s..%s" % (table, dates[0], dates[-1]))
    _nat = DERIVED_NATURAL_KEY.get(table)
    meta.collapsed_by = ("(sym, %s)" % ", ".join(_nat) if _nat
                         else "(sym, dt, _rid) — no natural key for this table")
    s3 = s3 or _client()
    fwd = DERIVED_FORWARD_DAYS if forward is None else forward

    scan = set(dates)
    last = datetime.strptime(dates[-1], "%Y-%m-%d")
    for i in range(1, fwd + 1):
        scan.add((last + timedelta(days=i)).date().isoformat())

    best = {}
    for d in sorted(scan):
        try:
            objs = read_prefix(s3, "derived_%s" % table, d)
        except Exception as exc:                                # noqa: BLE001
            # ⚠️ FAIL THE WHOLE LOAD, DO NOT SKIP THE PARTITION. A partial
            # read that reports success is the shape of every bad number this
            # project has chased.
            meta.error = "%s: %s" % (type(exc).__name__, exc)
            return [], meta
        meta.partitions += 1
        for sym, env in objs:
            meta.objects += 1
            stamp = str(env.get("pushed_at_utc") or "")
            sym = env.get("symbol") or sym
            for r in (env.get("record") or []):
                if not isinstance(r, dict):
                    continue
                # 🔴 dtp-r276 — THE KEY IS THE TABLE'S OWN PRIMARY KEY.
                # `_rid` is the source table's sqlite `rowid` (s3_push:945,
                # `SELECT rowid AS _rid, *`), unique only within ONE box's
                # table at ONE moment. r266 scoped it to the partition after
                # (QQQ, 1) on 09-01 collided with (QQQ, 1) on 09-04 and the
                # later push silently won — strategy_note 325,762 rows
                # collapsing to 37,584, and the fit report reading 2 fired
                # butterflies against 20 in the trade log.
                # ⚠️ THAT FIXED AN UNDER-COUNT AND OPENED AN OVER-COUNT. CDC
                # re-pushes a row whenever it changes, and `push_derived`
                # files under the PUSH day — so one row touched on two days
                # lands in two partitions, and a partition-scoped key keeps
                # both. Under-count, then over-count, on the same data.
                # 🔑 THE COLLAPSE ITSELF IS CORRECT AND STAYS. Only its
                # SUBJECT was wrong: these rows have an identity the box
                # already enforces, and it is not the rowid.
                key, keyed = collapse_key(table, sym, d, r)
                if not keyed:
                    meta.unkeyed += 1
                if key not in best or stamp >= best[key][0]:
                    best[key] = (stamp, sym, r)

    want = set(dates)
    col = DERIVED_TS_COL.get(table, DEFAULT_TS_COL)
    out = []
    for _stamp, sym, r in best.values():
        meta.rows += 1
        if et_day(r.get(col)) in want:
            # These tables all carry `symbol`, but a row that somehow lacks it
            # still needs a box, and the sym= partition is the warehouse's
            # answer to "which box wrote this".
            r.setdefault("symbol", sym)
            out.append(r)
    meta.kept = len(out)
    return out, meta


def latest_per_trade(objects):
    """Collapse a trade's several stored states down to its most recent one.

    This is the whole reason the warehouse holds more than the local bundle:
    the pusher keeps every state a row passed through. Ordering is by the
    envelope's `pushed_at_utc`, which is stamped by the box at push time and is
    monotonic per box for a given row.
    """
    best = {}
    for sym, env in objects:
        rec = env.get("record") or {}
        tid = rec.get("trade_id")
        if tid is None:
            continue
        stamp = str(env.get("pushed_at_utc") or "")
        prev = best.get(tid)
        if prev is None or stamp >= prev[0]:
            best[tid] = (stamp, sym, rec)
    rows = []
    for tid, (_stamp, sym, rec) in best.items():
        row = dict(rec)
        row["box"] = sym            # partition == authoritative fleet tag
        rows.append(row)
    # MUST match consolidate_trades.py:239 — (box, entry_time), in that order.
    # Downstream reports break grouping ties by input order, so a different
    # sort produces a different-looking report from identical data.
    rows.sort(key=lambda r: (str(r.get("box") or ""), str(r.get("entry_time") or "")))
    return rows


def build(date, s3=None):
    """The fleet_trades bundle, sourced from S3, in consolidate_trades' shape."""
    s3 = s3 or _client()

    trade_objs = read_prefix(s3, "trades", date)
    trades = latest_per_trade(trade_objs)
    _log("READ", f"trades: {len(trade_objs)} object(s) -> {len(trades)} unique trade(s)")

    breaker = []
    for sym, env in read_prefix(s3, "circuit_breaker", date):
        b = dict(env.get("record") or {})
        b["box"] = sym
        breaker.append(b)
    breaker.sort(key=lambda b: (str(b.get("event_time") or ""), str(b.get("box", ""))))

    # ohlc_index: the local bundle lists day-CSV filenames. The warehouse
    # equivalent is which symbols have an ohlc object for the date — same
    # question, expressed in partitions.
    ohlc_syms = sorted({sym for sym, _ in read_prefix(s3, "ohlc", date)})

    boxes = sorted({str(t.get("box")) for t in trades if t.get("box")})
    by_box = {}
    for b in boxes:
        by_box[b] = {
            "trades": sum(1 for t in trades if t.get("box") == b),
            "breaker_events": sum(1 for x in breaker if x.get("box") == b),
        }

    col_union = OrderedDict()
    for t in trades:
        for c in t:
            col_union.setdefault(c, None)

    n_closed = sum(1 for t in trades if str(t.get("status", "")).lower() == "closed")
    return OrderedDict([
        ("meta", OrderedDict([
            ("date_et", date),
            ("generated_utc", datetime.now(ZoneInfo("UTC")).isoformat()),
            ("source", f"s3://{BUCKET}/{PREFIX}"),
            ("boxes_reporting", boxes),
            ("boxes_skipped", []),
            ("n_trades", len(trades)),
            ("n_closed", n_closed),
            ("n_open", len(trades) - n_closed),
            ("n_trade_objects", len(trade_objs)),   # states seen, not trades
            ("trade_columns", list(col_union.keys())),
        ])),
        ("selection", CT._load_selection(date)),    # control's own file
        ("fleet_stats", CT._stats(trades)),         # SAME code as the local path
        ("by_box", by_box),
        ("breaker_events", breaker),
        ("ohlc_index", ohlc_syms),
        ("trades", trades),
    ])


def compare(date, s3=None):
    """Diff the warehouse bundle against the local one. This is WH.11's gate.

    Reports only what MATTERS: trade counts, the closed set, and per-trade P&L.
    A `generated_utc` that differs is not a finding.
    """
    local_path = os.path.join(config.REPORTS_DIR, f"fleet_trades_{date}.json")
    if not os.path.exists(local_path):
        _log("DIFF", f"no local bundle at {local_path} — run option 39 first")
        return 2
    with open(local_path) as fh:
        loc = json.load(fh)
    s3b = build(date, s3)

    lt = {str(t.get("trade_id")): t for t in loc.get("trades", [])}
    st = {str(t.get("trade_id")): t for t in s3b.get("trades", [])}
    only_local = sorted(set(lt) - set(st))
    only_s3 = sorted(set(st) - set(lt))
    pnl_diff = []
    for tid in sorted(set(lt) & set(st)):
        a, b = CT._num(lt[tid].get("pnl_usd")), CT._num(st[tid].get("pnl_usd"))
        if round(a, 2) != round(b, 2):
            pnl_diff.append((tid, a, b))
    status_diff = [tid for tid in sorted(set(lt) & set(st))
                   if str(lt[tid].get("status")) != str(st[tid].get("status"))]

    print()
    print(f"  local  : {len(lt)} trades, net {loc['fleet_stats']['net_pnl']:+.2f}")
    print(f"  s3     : {len(st)} trades, net {s3b['fleet_stats']['net_pnl']:+.2f}"
          f"  (from {s3b['meta']['n_trade_objects']} stored states)")
    print(f"  only in local : {len(only_local)} {only_local[:8]}")
    print(f"  only in s3    : {len(only_s3)} {only_s3[:8]}")
    print(f"  pnl mismatch  : {len(pnl_diff)} {pnl_diff[:5]}")
    print(f"  status mismatch: {len(status_diff)} {status_diff[:5]}")
    clean = not (only_local or only_s3 or pnl_diff or status_diff)
    print("\n  " + ("✅ MATCH — the warehouse reproduces the local bundle"
                    if clean else
                    "❌ DIVERGENCE — do NOT sever; investigate above"))
    return 0 if clean else 1


def warehouse_range(s3, datatype="trades"):
    """(earliest, latest) dt= partition actually present, or (None, None).

    Read from the bucket rather than hardcoded. A hardcoded cutoff goes stale
    the moment history is backfilled or a lifecycle rule expires something —
    and it fails in the SILENT direction, skipping dates it should be checking.
    One LIST with a delimiter returns the partition prefixes without touching
    a single object.
    """
    days = []
    try:
        pg = s3.get_paginator("list_objects_v2")
        for page in pg.paginate(Bucket=BUCKET,
                                Prefix=f"{PREFIX}/{datatype}/", Delimiter="/"):
            for cp in page.get("CommonPrefixes", []) or []:
                part = cp.get("Prefix", "").rstrip("/").split("/")[-1]
                if part.startswith("dt="):
                    days.append(part[3:])
    except Exception:
        return None, None
    if not days:
        return None, None
    return min(days), max(days)


def compare_all(s3=None, since=None):
    """Compare every date that has a local bundle. Read-only.

    A single matching date proves the reader parses one day correctly. It does
    not establish that the warehouse reproduces the pipeline — for that the
    claim has to be "N of N dates", and any date that diverges has to be named
    rather than averaged away.
    """
    import glob
    import re
    s3 = s3 or _client()
    wh_start, wh_end = warehouse_range(s3)
    # NOT wh_start — see the v1.3 note. wh_start is the oldest entry_time that
    # happened to survive on a box, not the day collection began.
    floor = since or COLLECTION_START
    paths = sorted(glob.glob(os.path.join(config.REPORTS_DIR, "fleet_trades_*.json")))
    dates = []
    for p_ in paths:
        m = re.search(r"fleet_trades_(\d{4}-\d{2}-\d{2})\.json$", p_)
        if m:
            dates.append(m.group(1))
    if not dates:
        _log("DIFF", "no local bundles found — nothing to compare against")
        return 2

    if floor:
        src = "--since" if since else "collection start"
        print(f"\n  warehouse holds dt= {wh_start} .. {wh_end}, but only "
              f"COLLECTS from {COLLECTION_START}")
        print(f"  dates before {floor} hold whatever survived on the boxes at "
              f"first push — partial by construction")
        print(f"  floor: {floor} ({src})")
    else:
        print("\n  ⚠️ could not read the warehouse's dt= range — comparing all dates")
    print(f"  {len(dates)} local bundle(s) found\n")

    ok, bad, empty, outside = [], [], [], []
    for d in dates:
        if floor and d < floor:
            # NOT a divergence. The warehouse simply did not exist yet for this
            # date, and calling that a mismatch would train you to ignore the
            # word.
            outside.append(d)
            continue
        try:
            loc_p = os.path.join(config.REPORTS_DIR, f"fleet_trades_{d}.json")
            with open(loc_p) as fh:
                loc = json.load(fh)
            s3b = build(d, s3)
            lt = {str(t.get("trade_id")): t for t in loc.get("trades", [])}
            st = {str(t.get("trade_id")): t for t in s3b.get("trades", [])}
            diffs = (len(set(lt) ^ set(st))
                     + sum(1 for k in set(lt) & set(st)
                           if round(CT._num(lt[k].get("pnl_usd")), 2)
                           != round(CT._num(st[k].get("pnl_usd")), 2))
                     + sum(1 for k in set(lt) & set(st)
                           if str(lt[k].get("status")) != str(st[k].get("status"))))
            tag = "MATCH " if diffs == 0 else "DIFF  "
            if diffs == 0:
                (empty if not lt else ok).append(d)
            else:
                bad.append((d, diffs))
            print(f"  {tag} {d}  local {len(lt):>4}  s3 {len(st):>4}"
                  f"  states {s3b['meta']['n_trade_objects']:>4}"
                  + ("" if diffs == 0 else f"   ⚠️ {diffs} difference(s)"))
        except Exception as exc:
            bad.append((d, str(exc)[:60]))
            print(f"  ERROR {d}  {exc}")

    print()
    if outside:
        print(f"  ⏸  {len(outside)} date(s) OUT OF COVERAGE (before {floor}) — "
              f"not checked: {outside[0]} .. {outside[-1]}")
    print(f"  {len(ok)} date(s) matched with trades · {len(empty)} matched but EMPTY "
          f"both sides · {len(bad)} divergent")
    if empty:
        # An empty-vs-empty date is not evidence of anything. Say so rather than
        # letting it inflate the pass count.
        print(f"  (empty dates prove nothing: {', '.join(empty[:8])}"
              + (" …" if len(empty) > 8 else "") + ")")
    if bad:
        print("  ❌ DIVERGENT: " + ", ".join(f"{d}({n})" for d, n in bad))
        print("  do NOT sever — investigate the dates above")
        return 1
    span = f"{ok[0]} .. {ok[-1]}" if ok else "(no dates with trades)"
    print(f"  ✅ MATCHED {span} — every in-coverage date with trades reproduces")
    if outside:
        print(f"  ⏸  NOT MATCHED before {floor}: those dates predate the "
              f"warehouse and are unverifiable, not wrong")
    return 0


def explain(date, s3=None):
    """List the trade_ids that differ on a single date, with why.

    A count tells you THAT two sides disagree. Diagnosing needs the specific
    rows, so this prints them rather than leaving the divergence to be reasoned
    about from totals.
    """
    s3 = s3 or _client()
    local_path = os.path.join(config.REPORTS_DIR, f"fleet_trades_{date}.json")
    if not os.path.exists(local_path):
        _log("EXPLAIN", f"no local bundle at {local_path}")
        return 2
    with open(local_path) as fh:
        loc = json.load(fh)
    s3b = build(date, s3)
    lt = {str(t.get("trade_id")): t for t in loc.get("trades", [])}
    st = {str(t.get("trade_id")): t for t in s3b.get("trades", [])}

    def _row(t):
        return (f"{str(t.get('box') or t.get('symbol') or '?'):<6} "
                f"{str(t.get('entry_time') or '')[:19]:<19} "
                f"{str(t.get('status') or ''):<8} "
                f"pnl={CT._num(t.get('pnl_usd')):>9.2f}")

    only_l = sorted(set(lt) - set(st))
    only_s = sorted(set(st) - set(lt))
    print(f"\n  {date}: local {len(lt)} · s3 {len(st)} "
          f"(from {s3b['meta']['n_trade_objects']} stored states)\n")
    if only_l:
        print(f"  ONLY IN LOCAL ({len(only_l)}) — in the bundle, absent from S3:")
        for tid in only_l[:25]:
            print(f"    {tid:<12} {_row(lt[tid])}")
        if len(only_l) > 25:
            print(f"    … and {len(only_l) - 25} more")
    if only_s:
        print(f"\n  ONLY IN S3 ({len(only_s)}) — pushed by a box, missing from "
              f"the bundle:")
        for tid in only_s[:25]:
            print(f"    {tid:<12} {_row(st[tid])}")
        if len(only_s) > 25:
            print(f"    … and {len(only_s) - 25} more")
    both = sorted(set(lt) & set(st))
    mism = [t for t in both
            if round(CT._num(lt[t].get("pnl_usd")), 2)
            != round(CT._num(st[t].get("pnl_usd")), 2)
            or str(lt[t].get("status")) != str(st[t].get("status"))]
    if mism:
        print(f"\n  PRESENT BOTH SIDES BUT DIFFERENT ({len(mism)}):")
        for tid in mism[:25]:
            print(f"    {tid:<12} local {_row(lt[tid])}")
            print(f"    {'':<12} s3    {_row(st[tid])}")
    if not (only_l or only_s or mism):
        print("  no differences — this date matches")
    print()
    return 0


def main(argv):
    p = argparse.ArgumentParser(description="Rebuild the fleet_trades bundle from S3")
    p.add_argument("--date", default=None, help="YYYY-MM-DD (default: today ET)")
    p.add_argument("--out", default=None, help="write the bundle here")
    p.add_argument("--compare", action="store_true",
                   help="diff against reports/fleet_trades_<date>.json")
    p.add_argument("--all", action="store_true",
                   help="compare every in-coverage date that has a local bundle")
    p.add_argument("--since", default=None,
                   help="override the coverage floor (YYYY-MM-DD)")
    p.add_argument("--explain", action="store_true",
                   help="list the trade_ids that differ on --date")
    a = p.parse_args(argv[1:])
    date = a.date or datetime.now(_ET).date().isoformat()

    if a.explain:
        return explain(date)
    if a.all:
        return compare_all(since=a.since)
    if a.compare:
        return compare(date)

    bundle = build(date)
    m, st = bundle["meta"], bundle["fleet_stats"]
    print(f"s3 bundle {date}: {len(m['boxes_reporting'])} boxes, "
          f"{m['n_trades']} trades ({m['n_closed']} closed) from "
          f"{m['n_trade_objects']} stored states, net {st['net_pnl']:+.2f}, "
          f"win {st['win_rate']:.0%}")
    out = a.out or os.path.join(WAREHOUSE_OUT, f"fleet_trades_{date}.json")
    # Refuse, do not warn. A warning about a path that silently changes another
    # report's inputs is a warning nobody reads until the numbers are wrong.
    if (os.path.dirname(os.path.abspath(out)) == os.path.abspath(config.REPORTS_DIR)
            and os.path.basename(out).startswith(GLOB_HAZARD)):
        print(f"refusing to write {out}\n"
              f"  reports/{GLOB_HAZARD}*.json is report 41's input glob — a file\n"
              f"  there becomes 41's data. Use {WAREHOUSE_OUT}/ or a path outside\n"
              f"  reports/.")
        return 2
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    tmp = out + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(bundle, fh, indent=2, default=str)
    os.replace(tmp, out)
    print(f"wrote {out}")
    return 0


def _cli(argv):
    """Turn an AWS/network failure into a sentence instead of a stack trace."""
    try:
        return main(argv)
    except KeyboardInterrupt:
        print("\ninterrupted — this reader is read-only, nothing was written")
        return 130
    except Exception as exc:                              # noqa: BLE001
        name = type(exc).__name__
        msg = str(exc).splitlines()[0][:200]
        print(f"warehouse_reader: {name}: {msg}")
        if "Credential" in name or "credential" in msg:
            print("  the control role is not providing S3 credentials — check "
                  "the instance profile, or run from 1-REPORTER")
        elif "AccessDenied" in msg:
            print("  VertigoWarehouseControlRead is missing an action for this "
                  "call — the message above names it")
        return 1


if __name__ == "__main__":
    sys.exit(_cli(sys.argv))
