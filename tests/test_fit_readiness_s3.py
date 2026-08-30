#!/usr/bin/env python3
# day_trader_pro/tests/test_fit_readiness_s3.py — v1.0
# v1.0 (2026-08-29) — r184 / dtp r226. Proves S3.2: fit_readiness reads the
#   warehouse, the two sources agree, and the forward partition scan is load
#   bearing rather than decorative.
#
# ⚠️ A PLAIN SCRIPT WITH AN EXIT CODE, NOT A PYTEST FILE. day_trader_pro's venv
#   has no pytest — that has cost this project a whole evening before, and a
#   check that goes red on ENVIRONMENT rather than CONTENT teaches the operator
#   to ignore reds.
#
# 🔑 CASE C IS THE ONE THAT MATTERS. It is a POSITIVE CONTROL for the design
#   decision in warehouse_reader v1.7: `dt=` on a derived prefix is the PUSH
#   day, so a row whose own timestamp is Monday can live in Wednesday's
#   partition. The case asserts that reading ONLY the requested partition
#   loses that row and that the forward scan recovers it. If someone later
#   "simplifies" the scan away, this goes red.
#
# Run:  python3 tests/test_fit_readiness_s3.py

import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import warehouse_reader as wr          # noqa: E402
import fit_readiness as fr             # noqa: E402

ET = ZoneInfo("US/Eastern")
DAY = "2026-08-25"
NEXT = "2026-08-27"


def ep(day, hh, mm=0):
    """Epoch seconds for an ET wall-clock time on `day`."""
    d = datetime.strptime(day, "%Y-%m-%d").replace(hour=hh, minute=mm, tzinfo=ET)
    return d.timestamp()


def note(ts, strat, fired, outcome, payload, rid, sym="NVDA"):
    return {"_rid": rid, "ts_epoch": ts, "symbol": sym, "strategy": strat,
            "fired": 1 if fired else 0, "trade_id": None, "outcome": outcome,
            "tick_id": 0, "price": 100.0, "payload": json.dumps(payload)}


def gate(ts, strat, g, event, rid, sym="NVDA"):
    return {"_rid": rid, "ts_epoch": ts, "symbol": sym, "strategy": strat,
            "gate": g, "reason": None, "detail": None, "event": event,
            "held_s": None, "ticks": 1}


def plan(created, strat, reason, rid, sym="NVDA"):
    return {"_rid": rid, "plan_id": "p%d" % rid, "symbol": sym,
            "strategy": strat, "state": "CLOSED", "created_ts": created,
            "updated_ts": created + 60, "closed_ts": created + 60,
            "terminal_reason": reason}


# ── the fixture: one session's worth of rows, and WHERE each was pushed ──
# ORB fires 4, declines 6; the declines land on three different rungs so the
# shape is realistic rather than degenerate.
NOTES_DAY = (
    [note(ep(DAY, 9, 40 + i), "ORBStrategy", True, None,
          {"adx": 28.0 + i, "atr_pct": 0.30}, 100 + i) for i in range(4)]
    + [note(ep(DAY, 10, i), "ORBStrategy", False, "adx_floor",
            {"adx": 14.0 + i, "atr_pct": 0.11}, 200 + i) for i in range(3)]
    + [note(ep(DAY, 11, i), "ORBStrategy", False, "spread_too_wide",
            {"adx": 22.0, "atr_pct": 0.09}, 210 + i) for i in range(2)]
    + [note(ep(DAY, 12, 0), "ORBStrategy", False, "no_retest",
            {"adx": 31.0, "atr_pct": 0.40}, 220)]
)
GATES_DAY = ([gate(ep(DAY, 10, i), "ORBStrategy", "MIN_ADX", "BLOCKED", 300 + i)
              for i in range(5)]
             + [gate(ep(DAY, 13, 0), "ORBStrategy", "MIN_ADX", "CLEARED", 320)])
# ⚠️ THIS PLAN IS PUSHED TWO DAYS LATE. It was created on DAY and its row
# changed again later, so push_derived filed it under NEXT.
PLANS_LATE = [plan(ep(DAY, 9, 45), "ORBStrategy", "MISSED", 400)]
PLANS_DAY = [plan(ep(DAY, 9, 50), "ORBStrategy", "FILLED", 401)]


def envelope(table, rows, stamp, sym="NVDA"):
    return {"schema_version": 1, "datatype": "derived_%s" % table,
            "symbol": sym, "dt": DAY, "src_host": "ip-x",
            "pushed_at_utc": stamp, "record": rows}


BUCKET_FIXTURE = {
    ("strategy_note", DAY): [envelope("strategy_note", NOTES_DAY, "2026-08-25T20:05:00Z")],
    ("gate_disposition", DAY): [envelope("gate_disposition", GATES_DAY, "2026-08-25T20:05:01Z")],
    ("plan_ledger", DAY): [envelope("plan_ledger", PLANS_DAY, "2026-08-25T20:05:02Z")],
    ("plan_ledger", NEXT): [envelope("plan_ledger", PLANS_LATE, "2026-08-27T20:05:00Z")],
}


def fake_read_prefix(_s3, datatype, date):
    table = datatype[len("derived_"):]
    return [("NVDA", e) for e in BUCKET_FIXTURE.get((table, date), [])]


def sqlite_fixture(path):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE strategy_note (ts_epoch REAL, symbol TEXT, "
                "strategy TEXT, fired INTEGER, trade_id TEXT, outcome TEXT, "
                "tick_id INTEGER, price REAL, payload TEXT)")
    con.execute("CREATE TABLE gate_disposition (ts_epoch REAL, symbol TEXT, "
                "strategy TEXT, gate TEXT, reason TEXT, detail TEXT, "
                "event TEXT, held_s REAL, ticks INTEGER)")
    con.execute("CREATE TABLE plan_ledger (plan_id TEXT, symbol TEXT, "
                "strategy TEXT, state TEXT, created_ts REAL, updated_ts REAL, "
                "closed_ts REAL, terminal_reason TEXT)")
    for r in NOTES_DAY:
        con.execute("INSERT INTO strategy_note VALUES (?,?,?,?,?,?,?,?,?)",
                    (r["ts_epoch"], r["symbol"], r["strategy"], r["fired"],
                     r["trade_id"], r["outcome"], r["tick_id"], r["price"],
                     r["payload"]))
    for r in GATES_DAY:
        con.execute("INSERT INTO gate_disposition VALUES (?,?,?,?,?,?,?,?,?)",
                    (r["ts_epoch"], r["symbol"], r["strategy"], r["gate"],
                     r["reason"], r["detail"], r["event"], r["held_s"],
                     r["ticks"]))
    for r in PLANS_DAY + PLANS_LATE:
        con.execute("INSERT INTO plan_ledger VALUES (?,?,?,?,?,?,?,?)",
                    (r["plan_id"], r["symbol"], r["strategy"], r["state"],
                     r["created_ts"], r["updated_ts"], r["closed_ts"],
                     r["terminal_reason"]))
    con.commit()
    con.close()


def shape(data):
    """A comparable summary: the numbers the report is built from."""
    return {s: (len(v["fired"]), len(v["declined"]),
                dict(v["rungs"]), dict(v["plans"]))
            for s, v in sorted(data.items())}


def main():
    problems = []
    orig = wr.read_prefix
    wr.read_prefix = fake_read_prefix
    try:
        # ── A. the warehouse path loads and files rows by their OWN ET day ──
        src_wh, notes = fr._rows_warehouse([DAY])
        wh = shape(collect_or_none(src_wh, [DAY], problems))
        if wh:
            f, d, rungs, plans = wh.get("ORBStrategy", (0, 0, {}, {}))
            if (f, d) != (4, 6):
                problems.append("A: expected 4 fired / 6 declined, got %d / %d"
                                % (f, d))
            # CLEARED must not be counted as a refusal
            if rungs.get("MIN_ADX") != 5:
                problems.append("A: MIN_ADX should be 5 BLOCKED (the CLEARED "
                                "row must not count), got %s"
                                % rungs.get("MIN_ADX"))
            if plans != {"FILLED": 1, "MISSED": 1}:
                problems.append("A: expected both plans, got %s" % plans)
        if not any("derived_strategy_note" in n for n in notes):
            problems.append("A: the SOURCE banner did not name the stream")

        # ── B. sqlite and warehouse must agree, row for row ────────────────
        with tempfile.TemporaryDirectory() as d:
            db = os.path.join(d, "derived_store.db")
            sqlite_fixture(db)
            src_db, _ = fr._rows_sqlite(db, [DAY])
            lo = shape(fr.collect(src_db, [DAY]))
        if lo != wh:
            problems.append("B: PARITY BROKEN — sqlite %s vs warehouse %s"
                            % (lo, wh))

        # ── C. POSITIVE CONTROL for the forward scan ───────────────────────
        # Without it the late-pushed plan is lost, and the report would show a
        # smaller, plausible number with nothing to indicate anything is wrong.
        narrow, _ = wr.load_derived("plan_ledger", [DAY], s3=object(), forward=0)
        wide, _ = wr.load_derived("plan_ledger", [DAY], s3=object(), forward=3)
        if len(narrow) != 1:
            problems.append("C: forward=0 should see only the same-day plan, "
                            "saw %d" % len(narrow))
        if len(wide) != 2:
            problems.append("C: forward=3 should recover the late-pushed plan, "
                            "saw %d — THE FORWARD SCAN IS NOT WORKING" % len(wide))

        # ── D. a row outside the window is excluded by ITS OWN timestamp ────
        other, _ = wr.load_derived("strategy_note", ["2026-08-26"],
                                   s3=object(), forward=3)
        if other:
            problems.append("D: rows dated %s leaked into a 2026-08-26 report "
                            "(%d) — the ET-day filter is not applied" % (DAY, len(other)))

        # ── E. unreachable must not read as empty ──────────────────────────
        def boom(*_a, **_k):
            raise RuntimeError("NoCredentialsError")
        wr.read_prefix = boom
        rows, meta = wr.load_derived("strategy_note", [DAY], s3=object())
        if rows or not meta.error or "COULD NOT READ" not in meta.banner():
            problems.append("E: a failed read did not report as an error: %s"
                            % meta.banner())
        wr.read_prefix = fake_read_prefix

        # ── F. the ET bound is not the naive local one ──────────────────────
        # 2026-08-25 00:00 ET is 04:00 UTC; a naive bound on a UTC box would
        # start four hours early and pull in the previous session's tail.
        lo_, hi_ = wr.et_bounds(DAY, DAY)
        if datetime.fromtimestamp(lo_, ET).hour != 0 or (hi_ - lo_) != 86400:
            problems.append("F: et_bounds is not an ET midnight-to-midnight "
                            "day: %s..%s" % (lo_, hi_))
        if wr.et_day(ep(DAY, 20, 30)) != DAY:
            problems.append("F: 20:30 ET on %s must still be %s (a naive UTC "
                            "read rolls it to the next day)" % (DAY, DAY))
    finally:
        wr.read_prefix = orig

    if problems:
        print("PROBLEMS (%d):" % len(problems))
        for p in problems:
            print("  ✗ " + p)
        print("\nFAIL")
        return 1
    print("  A warehouse load: 4 fired / 6 declined / 3 rungs / 2 plans")
    print("  B parity:         sqlite == warehouse, row for row")
    print("  C forward scan:   forward=0 loses the late plan, forward=3 keeps it")
    print("  D window filter:  rows excluded by their own ET day")
    print("  E unreachable:    reports an error, never an empty result")
    print("  F ET bounds:      midnight-to-midnight ET, 20:30 stays same-day")
    print("\nPASS")
    return 0


def collect_or_none(src, dates, problems):
    if src is None:
        problems.append("A: the warehouse loader returned nothing at all")
        return {}
    return fr.collect(src, dates)


if __name__ == "__main__":
    sys.exit(main())
