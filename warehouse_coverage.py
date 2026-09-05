#!/usr/bin/env python3
# day_trader_pro/warehouse_coverage.py — v1.2
# v1.2 (2026-09-05) — dtp r277. PER-STREAM, PER-DAY, PER-BOX COVERAGE (S3.10).
#      ADDITIVE: `--streams`. The VIX report, its verdicts and its exit code are
#      untouched, because a menu item that quietly starts answering a different
#      question is worse than a second item (WH.11's rule).
#      🔑 COVERAGE MEANS TWO DIFFERENT THINGS AND THE REPORT SAYS WHICH. Read
#      from `otv4/warehouse/s3_push.py`: `push_derived` writes ONE OBJECT PER
#      TABLE PER RUN holding a batch (line 959), `push_series` batches at
#      `OT_S3_SERIES_BATCH` = 50,000, and `push_candles` ships high-water
#      batches — while `push_jsonl_tree` and `push_trades` write one object per
#      RECORD. So an object count on `raw/derived_*` counts PUSH RUNS and an
#      object count on `raw/signal_journal` counts rows, and reading the first
#      as the second is how 5,389 `derived_plan_check` objects sat beside
#      2.38M rows with nothing reconciling them. Every row carries its GRAIN.
#      🔴 AND FOR A DERIVED STREAM THIS IS A PUSHER CHECK, NOT A ROW CHECK.
#      `push_derived` files under `datetime.now(ET).date()` — the PUSH day, not
#      the row's day (C.9). A `dt=` partition therefore answers "did this box's
#      pusher run that day" and CANNOT answer "are that day's rows complete".
#      Two questions; conflating them is the trap this mode exists to avoid, so
#      the header states it and every derived row is labelled `pusher`.
#      ⚠️ THE EXPECTATION IS DECLARED PER STREAM, because "absent" is not one
#      fact. `chain_snapshots` is written only by a box that TRADED, `shadow`
#      was NEVER INSTALLED on the v4 fleet, VIX has a single writer by design,
#      and `theo_series`/`underlying_series` were unsubscribed at r118/r125b.
#      Counting any of those as a gap would put a permanent red on the board,
#      which is the one thing that stops a board being read (the CV.1 lesson).
#      ⚠️ A SILENT BOX IS DIAGNOSED ONCE, NOT ONCE PER STREAM. A box that
#      pushed NOTHING that day is reported as BOX_SILENT and its absences are
#      attributed to it rather than counted against twenty streams — the same
#      split v1.0 already makes for VIX between PUSH_DEFECT and OWNER_DOWN,
#      generalised. Those are different diagnoses with different fixes.
#      ⚠️ THE PANEL IS IMPORTED FROM `selector.PANEL`, never retyped. r185
#      records that the fleet count sat wrong on the front page for nine days
#      because one fact lived in three documents; a hardcoded list here would
#      be the fourth. If it cannot be imported the mode FAILS LOUDLY rather
#      than falling back to a guess — a coverage check that skips reports
#      success, which is worth less than none (dtp r250).
#      ⚠️ A STREAM IN THE BUCKET THAT THIS FILE DOES NOT DECLARE is reported as
#      UNDECLARED, never skipped. A tool that quietly shrinks its own scope is
#      as misleading as one that over-reports — v1.1's own finding.
#      ⚠️ PRESENCE IS ONE DELIMITED LIST PER (stream, day) and returns the
#      `sym=` prefixes directly, so a 5-day sweep is tens of calls rather than
#      streams x boxes x days. Object COUNTS need full pagination and are
#      opt-in behind `--counts`; the cheap check is the decisive one.
# v1.1 (2026-08-18) — 🔴 IT CRIED WOLF ON A SUNDAY. v1.0 judged every dt=
#      partition present in the bucket without asking whether that date was a
#      TRADING DAY, so one stray weekend object (2026-08-16, SPX candles=1 —
#      a late flush or a daily bar) manufactured a partition and then a
#      PUSH_DEFECT verdict against a day the market was closed. There were no
#      VIX 1-minute bars to miss. A check that reports a defect on a Sunday
#      trains the operator to skim its output, which is the exact failure the
#      phase exists to prevent (the CV.1 lesson).
#      Two categories added, both REPORTED rather than silently skipped — a
#      tool that quietly shrinks its own scope is as misleading as one that
#      over-reports:
#        NOT_A_SESSION      market_calendar.is_trading_day() is False
#        PARTIAL_BY_DESIGN  before COLLECTION_START, where the first push
#                           shipped whatever history each box still had, so
#                           absence proves nothing (the warehouse reader's
#                           third category, applied here)
#      Neither counts as a failure; neither counts as coverage.
# v1.0 (2026-08-18) — VIX COVERAGE IN THE WAREHOUSE, BEFORE THE SEVER.
#      Once S3 becomes the official store, the control-side copy stops being
#      written and anything absent from the bucket is GONE. VIX is the highest
#      exposure in that transition for one structural reason: every box logs it
#      but `s3_push.push_candles` skips it unless `me == "SPX"` ("SPX owns
#      VIX"), so VIX has ONE writer. Any day SPX does not run, or its candles
#      stage fails, VIX simply does not land — and nothing reports it, because
#      the other 28 boxes skipping VIX is the normal, correct behaviour.
#      This is LIST-only and read-only: no GetObject, no writes, no box access.
#      It answers three questions per date, from the bucket alone:
#        1. did VIX 1m land, and how many objects
#        2. did VIX 1d land
#        3. did SPX push its OWN candles that day
#      (3) is what separates the two diagnoses that must never be confused:
#        · SPX pushed its own candles but no VIX  -> A PUSH DEFECT. Data that
#          existed on the box was not warehoused. Actionable now.
#        · SPX pushed nothing at all              -> SPX WAS DOWN. Explained,
#          still a gap, and the argument for a fallback VIX writer.
#      Deliberately NOT a full multi-stream coverage report — ⬛ SUPERSEDED AT
#      v1.2, which adds `--streams` beside it rather than in place of it.
#      EXPECTED_STREAMS is a table so adding one is a one-line edit, but this
#      ships answering the question that was asked.
#      ⚠️ MARKED IN PLACE, NOT REWRITTEN. Rule 5 forbids leaving a changelog
#      describing behaviour the code no longer has; r240's precedent is that a
#      superseded entry is STRUCK rather than deleted, because the entries are
#      a per-revision record while one a later entry contradicts is a wrong
#      answer rather than history. And the v1.1 sentence was RIGHT when it was
#      written — extending it took a revision, not the one line it predicted,
#      because coverage turned out to mean two different things by stream.
"""
Usage (control box, from ~/day_trader_pro):

  python3 warehouse_coverage.py                     # last 10 sessions
  python3 warehouse_coverage.py --since 2026-08-13  # explicit start
  python3 warehouse_coverage.py --date 2026-08-18   # one day
  python3 warehouse_coverage.py --json out.json     # machine-readable

Exit status: 0 = every checked date has VIX 1m. 1 = at least one date is
missing it. Never raises on an empty bucket — a missing stream is the finding,
not an error, and a tool must not throw when the thing it measures is fixed.
"""

import argparse
import json
import textwrap
import os
import sys
from datetime import date as _date, timedelta

import boto3

import config  # noqa: F401  (kept for path/env parity with the other tools)
import market_calendar

BUCKET = os.environ.get("OT_S3_BUCKET", "vertigo-warehouse-tx9ai")
REGION = os.environ.get("OT_S3_REGION", "us-east-2")
PREFIX = os.environ.get("OT_S3_PREFIX", "raw")

# The one stream this tool exists for. A dict, not a hardcode, so extending the
# check to another single-writer stream is one line — but see the header: this
# ships scoped to the question asked.
EXPECTED_STREAMS = {
    "VIX_1m": ("candles", "VIX", "1m"),
    "VIX_1d": ("candles", "VIX", "1d"),
}
OWNER = "SPX"          # the only box permitted to push VIX (s3_push.push_candles)

# The date the warehouse began COLLECTING — earlier partitions exist but are
# partial by construction. Same constant and same reasoning as warehouse_reader.
COLLECTION_START = os.environ.get("OT_WAREHOUSE_START", "2026-08-13")

# ── v1.2 — WHAT EACH STREAM OWES, AND WHAT ONE OBJECT MEANS ────────────────
# Every entry: datatype -> (expectation, grain, note). Read out of
# `otv4/warehouse/s3_push.py`'s own stage list (~line 1162) and the push
# helpers, never assembled from memory.
#
#   EXPECTATION   EVERY        every panel box on a trading day; absence is a gap
#                 OWNER:<SYM>  one writer by design; absence from others is right
#                 CONDITIONAL  only when the event happened; absence proves nothing
#                 DEAD         retired or never installed; absence is correct
#   GRAIN         record       one object per row/line   -> object count IS volume
#                 batch        one object per push RUN   -> object count is RUNS
#                 file         one object per source file
#                 pusher       batch AND `dt=` is the PUSH day (C.9) — this row
#                              can only speak to whether the pusher ran
#
# ⚠️ CONDITIONAL IS NOT A SOFTER "EVERY". It means the tape decides, so the
# report prints what landed and refuses to grade it. Calling a quiet day a gap
# is how a board earns a permanent red and stops being read.
STREAM_POLICY = {
    "trades":            ("EVERY", "record", "closed + open trade rows, per box"),
    "signal_journal":    ("EVERY", "record", "one object per journal line"),
    "candles":           ("EVERY", "batch",  "high-water per symbol+interval"),
    "ohlc":              ("EVERY", "file",   "one CSV per day"),
    "liquidity_ledger":  ("EVERY", "file",   "one JSON per sampled bar"),
    "eod":               ("EVERY", "file",   "pnl_today / trades_today"),
    "greeks_series":     ("EVERY", "batch",  "per-contract greeks"),
    "quote_series":      ("EVERY", "batch",  "per-contract bid/ask"),
    "prints":            ("EVERY", "batch",  "TimeAndSale, with aggressor"),
    "last_trade":        ("EVERY", "batch",  "Trade events"),
    "session_summary":   ("EVERY", "batch",  "Summary, prev-day close"),
    "indicator_series":  ("EVERY", "batch",  "ADX/ATR/EMA/VWAP  (ns=dseries)"),
    "fork_series":       ("EVERY", "batch",  "pitchfork state    (ns=dseries)"),
    "surface_series":    ("EVERY", "batch",  "charm/vanna/GEX   (ns=dseries)"),
    "derived_plan_tick":        ("EVERY", "pusher", "the plan spine"),
    "derived_plan_check":       ("EVERY", "pusher", "one row per VARIABLE per plan per tick"),
    "derived_strategy_note":    ("EVERY", "pusher", "one row per strategy EVALUATION"),
    "derived_gate_disposition": ("EVERY", "pusher", "which rung refused, edge-triggered"),
    "derived_level_ledger":     ("EVERY", "pusher", "levels, operator lifecycle"),
    "derived_plan_ledger":      ("CONDITIONAL", "pusher", "a plan must have been declared"),
    "derived_fire_snapshot":    ("CONDITIONAL", "pusher", "written only on a FILL"),
    "derived_character_ledger": ("CONDITIONAL", "pusher", "BANDS_SET=False since r85 — emits no state"),
    "derived_exit_counterfactual": ("CONDITIONAL", "pusher", "only when a flow exit WOULD have fired"),
    "chain_snapshots":   ("CONDITIONAL", "record", "only boxes that TRADED; NOT reconstructible after the session"),
    "circuit_breaker":   ("CONDITIONAL", "record", "only on a breaker trip"),
    "shadow":            ("DEAD", "record", "NEVER INSTALLED on the v4 fleet — verified on a box"),
    "theo_series":       ("DEAD", "batch",  "unsubscribed r118 after it took SPX's chain down"),
    "underlying_series": ("DEAD", "batch",  "published zero events on both symbol spaces (r125b)"),
    "orb_range":         ("DEAD", "record", "retired s3_push v1.8, 2026-08-16"),
    "orb_state":         ("DEAD", "record", "retired s3_push v1.8 — captured zero objects in 30 days"),
}


def panel():
    """The trading panel, from its ONE authority.

    🔑 `selector.PANEL` is named there and nowhere else (r185). A copy here
    would be the fourth place one fact lives, which is exactly how the fleet
    count sat wrong on the README front page for nine days.
    Raises rather than defaulting: a coverage report that silently invents its
    own expected set reports success it did not measure (dtp r250).
    """
    import selector
    p = list(getattr(selector, "PANEL", []) or [])
    if not p:
        raise RuntimeError(
            "selector.PANEL is empty — discretionary selection is on, so there "
            "is no fixed expected set and this mode cannot grade a stream")
    return p


def _stream_days(s3):
    """Every datatype under raw/, and the dt= days each one holds. One
    delimited LIST per level — no bodies, no pagination over objects."""
    out = {}
    pg = s3.get_paginator("list_objects_v2")
    for page in pg.paginate(Bucket=BUCKET, Prefix=f"{PREFIX}/", Delimiter="/"):
        for cp in page.get("CommonPrefixes", []) or []:
            out[cp["Prefix"].rstrip("/").split("/")[-1]] = None
    return sorted(out)


def _boxes(s3, datatype, day):
    """Which `sym=` partitions exist for one stream on one day.

    ⚠️ ONE DELIMITED LIST. The prefixes come back directly, so this does not
    page over objects — which is what makes a multi-stream sweep affordable at
    all. Object COUNTS are a different, far more expensive question and live
    behind `--counts`.
    """
    out = set()
    pg = s3.get_paginator("list_objects_v2")
    for page in pg.paginate(Bucket=BUCKET,
                            Prefix=f"{PREFIX}/{datatype}/dt={day}/",
                            Delimiter="/"):
        for cp in page.get("CommonPrefixes", []) or []:
            part = cp["Prefix"].rstrip("/").split("/")[-1]
            if part.startswith("sym="):
                out.add(part[4:])
    return out


def _base(sym):
    """`NVDA_EXT` is NVDA's own non-RTH tape, not a box of its own.

    🔴 r194's guard did an EXACT string match and proposed deleting the
    extended tape of every panel symbol, because `"NVDA_EXT" != "NVDA"` passed
    straight through. A guard that matches a name FORMAT rather than an
    IDENTITY is not a guard.
    """
    return sym[:-4] if sym.endswith("_EXT") else sym


def check_streams(s3, day, want, counts=False):
    """One day's per-stream verdict. Pure lookup — no writes, no box access."""
    if not _is_session(day):
        return {"date": day, "verdict": "NOT_A_SESSION", "rows": [], "silent": []}
    partial = day < COLLECTION_START

    seen = {}
    for dtp_ in sorted(set(_stream_days(s3)) | set(STREAM_POLICY)):
        seen[dtp_] = {_base(s) for s in _boxes(s3, dtp_, day)}

    # 🔑 A BOX THAT PUSHED NOTHING IS ONE DIAGNOSIS, NOT TWENTY. Attributing
    # its absences to the box rather than to every stream is the same split
    # v1.0 makes between PUSH_DEFECT and OWNER_DOWN — different fixes.
    pushed_something = set().union(*seen.values()) if seen else set()
    silent = sorted(b for b in want if b not in pushed_something)
    live = [b for b in want if b not in silent]

    rows = []
    for dtp_ in sorted(seen):
        pol = STREAM_POLICY.get(dtp_)
        boxes = seen[dtp_]
        if pol is None:
            rows.append({"stream": dtp_, "expect": "UNDECLARED", "grain": "?",
                         "n": len(boxes), "missing": [],
                         "verdict": "UNDECLARED", "note":
                         "in the bucket and not in STREAM_POLICY — declare it "
                         "or record why it is not expected"})
            continue
        expect, grain, note = pol
        missing = []
        if partial:
            verdict = "PARTIAL_BY_DESIGN"
        elif expect == "EVERY":
            missing = [b for b in live if b not in boxes]
            verdict = "OK" if not missing else "GAP"
        elif expect.startswith("OWNER:"):
            owner = expect.split(":", 1)[1]
            if owner in silent:
                verdict = "OWNER_SILENT"
            else:
                missing = [] if owner in boxes else [owner]
                verdict = "OK" if not missing else "GAP"
        elif expect == "CONDITIONAL":
            verdict = "CONDITIONAL"
        else:
            verdict = "DEAD"
        row = {"stream": dtp_, "expect": expect, "grain": grain,
               "n": len(boxes), "missing": missing, "verdict": verdict,
               "note": note}
        if counts:
            row["objects"] = sum(
                _count(s3, f"{PREFIX}/{dtp_}/dt={day}/sym={b}/") for b in boxes)
        rows.append(row)
    return {"date": day, "verdict": "PARTIAL_BY_DESIGN" if partial else "JUDGED",
            "rows": rows, "silent": silent}


def report_streams(s3, days, counts=False):
    """-> exit code. Only a GAP on an EVERY stream is a failure."""
    try:
        want = panel()
    except Exception as exc:                                   # noqa: BLE001
        _log("STREAMS", f"🔴 cannot establish the expected box set: {exc}")
        _log("STREAMS", "   refusing to grade coverage against a guessed panel")
        return 2

    _log("STREAMS", f"expected boxes ({len(want)}, from selector.PANEL): "
                    f"{', '.join(want)}")
    # ⚠️ THREE LINES, NOT ONE. This is read over Termius on a phone, where a
    # soft-wrapped sentence is a sentence nobody finishes (r210's 60-character
    # rule), and the grain is the one thing on this report that must be read.
    _log("STREAMS", "GRAIN  record = one object per row -> the count IS volume")
    _log("STREAMS", "       batch  = one object per push RUN -> it is not")
    _log("STREAMS", "       pusher = batch, and dt= is the PUSH day (C.9), so "
                    "this row")
    _log("STREAMS", "                speaks to the PUSHER and never to whether "
                    "that")
    _log("STREAMS", "                day's rows are complete")
    bad = 0
    for day in days:
        d = check_streams(s3, day, want, counts=counts)
        if d["verdict"] == "NOT_A_SESSION":
            _log("STREAMS", f"· {day}  market closed — no session, no streams")
            continue
        head = f"── {day} " + ("(PARTIAL_BY_DESIGN — before "
                               f"{COLLECTION_START})" if d["verdict"] ==
                               "PARTIAL_BY_DESIGN" else "")
        _log("STREAMS", head)
        live_n = [b for b in want if b not in d["silent"]]
        if d["silent"]:
            _log("STREAMS", f"  ⚠️ BOX_SILENT ({len(d['silent'])}): "
                            f"{', '.join(d['silent'])}")
            _log("STREAMS", "     pushed NOTHING at all — their absences are "
                            "attributed here,")
            _log("STREAMS", "     not counted against every stream below")
        for r in d["rows"]:
            mark = {"OK": "✅", "GAP": "🔴", "OWNER_SILENT": "⚠️",
                    "CONDITIONAL": "◇", "DEAD": "·",
                    "PARTIAL_BY_DESIGN": "◐", "UNDECLARED": "❓"}[r["verdict"]]
            # ⚠️ WIDTH IS THE CONSTRAINT AND NOT TASTE — this is read over
            # Termius on a phone. The longest declared stream name is
            # `derived_exit_counterfactual` at 27, so the column is 27.
            line = (f"  {mark} {r['stream']:<27} {r['grain']:<6} "
                    f"{r['n']:>2}bx")
            if counts and "objects" in r:
                line += f" {r['objects']:>7,}o"
            if r["missing"]:
                # 🔑 EVERY LIVE BOX MISSING IS A DIFFERENT FINDING FROM ONE BOX
                # MISSING — a stream that stopped landing fleet-wide, against a
                # single box that fell behind — and they have different fixes.
                # Saying so also keeps the line inside a phone screen, which
                # fifteen comma-separated symbols would not.
                if len(r["missing"]) == len(live_n) and live_n:
                    line += f"  MISS: ALL {len(live_n)} live"
                elif len(r["missing"]) > 4:
                    line += (f"  MISS: {len(r['missing'])}/{len(live_n)} "
                             f"({','.join(r['missing'][:3])},...)")
                else:
                    line += f"  MISS: {','.join(r['missing'])}"
            _log("STREAMS", line)
            # ⚠️ THE NOTE GOES ON ITS OWN LINE. Appended, it pushed the widest
            # row past 140 characters, and a line that soft-wraps on a phone is
            # one the operator reconstructs by eye before reading (§19).
            if r["verdict"] in ("CONDITIONAL", "DEAD", "UNDECLARED"):
                for chunk in textwrap.wrap(r["note"], 54):
                    _log("STREAMS", f"       {chunk}")
            if r["verdict"] in ("GAP", "UNDECLARED"):
                bad += 1
    if bad:
        _log("STREAMS", f"🔴 {bad} stream-day(s) need an answer.")
    else:
        _log("STREAMS", "✅ every EVERY-stream had all expected boxes on every "
                        "judged session.")
    return 1 if bad else 0



def _log(tag, msg):
    print(f"[{tag:<9}] {msg}")


def _client():
    return boto3.client("s3", region_name=REGION)


def _count(s3, prefix):
    """Objects under a prefix. LIST only — never fetches a body."""
    n = 0
    pg = s3.get_paginator("list_objects_v2")
    for page in pg.paginate(Bucket=BUCKET, Prefix=prefix):
        n += len(page.get("Contents", []) or [])
    return n


def _dt_days(s3, datatype):
    """Every dt= partition present under raw/<datatype>/."""
    days = set()
    pg = s3.get_paginator("list_objects_v2")
    for page in pg.paginate(Bucket=BUCKET, Prefix=f"{PREFIX}/{datatype}/",
                            Delimiter="/"):
        for cp in page.get("CommonPrefixes", []) or []:
            part = cp["Prefix"].rstrip("/").split("/")[-1]
            if part.startswith("dt="):
                days.add(part[3:])
    return sorted(days)


def _is_session(day):
    """v1.1 — was the market open? Weekends AND holidays, via the repo's own
    calendar rather than a weekday test, because a holiday looks exactly like
    a defect otherwise."""
    try:
        return market_calendar.is_trading_day(_date.fromisoformat(day))
    except Exception:                                          # noqa: BLE001
        return True        # unknown date format: judge it rather than excuse it


def check_date(s3, day):
    """One date's verdict. Pure lookup — no side effects."""
    row = {"date": day}
    if not _is_session(day):
        # v1.1 — no session, no bars. Reported, not skipped.
        row.update({"VIX_1m": 0, "VIX_1d": 0, "owner_candles": 0,
                    "verdict": "NOT_A_SESSION"})
        return row
    for name, (datatype, sym, interval) in EXPECTED_STREAMS.items():
        row[name] = _count(
            s3, f"{PREFIX}/{datatype}/dt={day}/sym={sym}/interval={interval}/")
    row["owner_candles"] = _count(
        s3, f"{PREFIX}/{datatype}/dt={day}/sym={OWNER}/")
    if day < COLLECTION_START:
        # v1.1 — the first push shipped whatever history survived on each box,
        # so a thin pre-collection date is expected and proves nothing either
        # way. Never a defect, never counted as coverage.
        row["verdict"] = "PARTIAL_BY_DESIGN"
    elif row["VIX_1m"] > 0:
        row["verdict"] = "OK"
    elif row["owner_candles"] > 0:
        row["verdict"] = "PUSH_DEFECT"      # SPX pushed candles, VIX missing
    else:
        row["verdict"] = "OWNER_DOWN"       # SPX pushed nothing that day
    return row


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="VIX coverage in the S3 warehouse (read-only, LIST only)")
    ap.add_argument("--date", default=None, help="check a single YYYY-MM-DD")
    ap.add_argument("--since", default=None, help="check every dt= from this date")
    ap.add_argument("--last", type=int, default=10,
                    help="if neither --date nor --since: the N most recent dt= "
                         "partitions present in the bucket (default 10)")
    ap.add_argument("--json", default="", help="also write the rows to this path")
    ap.add_argument("--streams", action="store_true",
                    help="v1.2 — per-stream, per-day, per-box coverage across "
                         "EVERY declared stream (LIST only)")
    ap.add_argument("--counts", action="store_true",
                    help="with --streams: also count objects per stream-day. "
                         "This PAGES OVER OBJECTS and is much slower; presence "
                         "is the decisive check and counts are the extra.")
    args = ap.parse_args(argv)

    try:
        s3 = _client()
        present = _dt_days(s3, "candles")
    except Exception as exc:                                   # noqa: BLE001
        _log("COVERAGE", f"cannot list the bucket: {exc}")
        return 2

    if not present:
        _log("COVERAGE", f"no candle partitions under s3://{BUCKET}/{PREFIX}/candles/")
        return 1

    if args.date:
        days = [args.date]
    elif args.since:
        days = [d for d in present if d >= args.since]
    else:
        days = present[-args.last:]

    # v1.2 — ADDITIVE. `--streams` is its own report with its own exit code;
    # the VIX report below is byte-for-byte the v1.1 behaviour, because a menu
    # item that quietly starts answering a different question is worse than a
    # second item.
    if args.streams:
        return report_streams(s3, days, counts=args.counts)

    rows = [check_date(s3, d) for d in days]    # v1.1 — only two verdicts are failures. NOT_A_SESSION and
    # PARTIAL_BY_DESIGN are explanations, and treating an explanation as a
    # failure is how an alarm stops being read.
    missing = [r for r in rows
               if r["verdict"] in ("PUSH_DEFECT", "OWNER_DOWN")]

    _log("COVERAGE", f"s3://{BUCKET}/{PREFIX}/candles/ — {len(rows)} date(s) checked")
    for r in rows:
        mark = {"OK": "✅", "PUSH_DEFECT": "🔴", "OWNER_DOWN": "⚠️",
                "NOT_A_SESSION": "·", "PARTIAL_BY_DESIGN": "◐"}[r["verdict"]]
        _log("COVERAGE",
             f"  {mark} {r['date']}  VIX 1m={r['VIX_1m']:<4} 1d={r['VIX_1d']:<3} "
             f"{OWNER} candles={r['owner_candles']:<4} {r['verdict']}")

    if missing:
        defects = [r["date"] for r in missing if r["verdict"] == "PUSH_DEFECT"]
        downs = [r["date"] for r in missing if r["verdict"] == "OWNER_DOWN"]
        if defects:
            _log("COVERAGE", f"🔴 PUSH DEFECT on {len(defects)}: {', '.join(defects)} "
                             f"— {OWNER} warehoused its own candles but no VIX. "
                             f"The data existed on the box and did not land.")
        if downs:
            _log("COVERAGE", f"⚠️ {OWNER} pushed nothing on {len(downs)}: "
                             f"{', '.join(downs)} — VIX has a single writer, so "
                             f"those days have no VIX anywhere once control is severed.")
    else:
        _sess = sum(1 for r in rows if r["verdict"] == "OK")
        _skip = len(rows) - _sess
        _log("COVERAGE", f"✅ every trading day checked has VIX 1m in the "
                         f"warehouse ({_sess} session(s); {_skip} not judged — "
                         f"non-session or pre-collection)")

    if args.json:
        try:
            with open(args.json, "w", encoding="utf-8") as fh:
                json.dump({"bucket": BUCKET, "owner": OWNER, "rows": rows}, fh,
                          indent=2)
            _log("COVERAGE", f"wrote {args.json}")
        except Exception as exc:                               # noqa: BLE001
            _log("COVERAGE", f"could not write {args.json}: {exc}")

    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
