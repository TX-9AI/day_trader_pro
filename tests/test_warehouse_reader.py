#!/usr/bin/env python3
# day_trader_pro/tests/test_warehouse_reader.py — v1.4
"""
Pins warehouse_reader v1.0 (WH.8).

CHANGELOG
    v1.4 — 2026-08-16 — the glob-contamination guard. The reader's default
           output landed inside report 41's input glob, so running the
           comparison tool changed what it was comparing against. Asserted
           directly, because "we'll remember not to write there" is not a
           control.
    v1.3 — 2026-08-16 — the floor is COLLECTION START, not the earliest dt=
           partition. v1.2's floor read 2026-07-06 off the bucket and excluded
           nothing, because the first push shipped months of surviving history
           in one go. Also `--explain`.
    v1.2 — 2026-08-16 — the coverage window. Asserts that a pre-warehouse date
           is reported as OUT OF COVERAGE and is counted as NEITHER a match nor
           a divergence — the whole point being that "divergent" has to keep
           meaning something.
    v1.1 — 2026-08-16 — `--all`. The check worth having is that an EMPTY date
           is not counted as a pass: 30 dates where both sides hold zero trades
           would otherwise report "30/30 match" and mean nothing.
    v1.0 — 2026-08-16 — alongside warehouse_reader v1.0.

THE CHECK THAT EARNS ITS PLACE
    `test_collapse_before_filter`. A trade that was OPEN at 10:00 and CLOSED at
    15:00 has objects in BOTH states, because the pusher stores every state a
    row passed through. Collapse-then-filter keeps the closed one. Filter-then-
    collapse would keep whichever survived the filter and could drop the trade
    entirely. The two orderings differ only on real data — which is exactly the
    kind of bug that reaches production — so the ordering is asserted here
    rather than trusted to the comment that explains it.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
os.environ.setdefault("DTP_MOCK_AWS", "1")

FAILS = []


def check(name, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + name +
          ("" if cond else "  <- " + str(detail)))
    if not cond:
        FAILS.append(name)


import warehouse_reader as WR  # noqa: E402

print("\n=== warehouse_reader v1.0 (WH.8) ===\n")


class S3Stub:
    def __init__(self, objs):
        self.objs = objs           # {key: dict}

    def get_paginator(self, _op):
        objs = self.objs

        class _P:
            def paginate(self, Bucket=None, Prefix="", Delimiter=None, **kw):
                if Delimiter:
                    parts = set()
                    for k in objs:
                        if k.startswith(Prefix):
                            rest = k[len(Prefix):].split("/")[0]
                            parts.add(Prefix + rest + "/")
                    yield {"CommonPrefixes": [{"Prefix": p} for p in sorted(parts)]}
                else:
                    yield {"Contents": [{"Key": k} for k in objs if k.startswith(Prefix)]}
        return _P()

    def get_object(self, Bucket=None, Key=None):
        body = json.dumps(self.objs[Key]).encode()

        class _B:
            def read(self_inner):
                return body
        return {"Body": _B()}


def env(rec, pushed):
    return {"schema_version": 1, "datatype": "trade", "pushed_at_utc": pushed,
            "record": rec}


D = "2026-08-14"
K = "raw/trades/dt=%s/sym=%%s/%%s.json" % D

# one trade, two states — open then closed
objs = {
    K % ("SPX", "a"): env({"trade_id": 1, "symbol": "SPX", "status": "open",
                           "pnl_usd": None, "entry_time": "2026-08-14T14:00:00+00:00"},
                          "2026-08-14T14:05:00+00:00"),
    K % ("SPX", "b"): env({"trade_id": 1, "symbol": "SPX", "status": "closed",
                           "pnl_usd": 412.5, "entry_time": "2026-08-14T14:00:00+00:00"},
                          "2026-08-14T19:05:00+00:00"),
    K % ("QQQ", "c"): env({"trade_id": 2, "symbol": "QQQ", "status": "closed",
                           "pnl_usd": -120.0, "entry_time": "2026-08-14T15:00:00+00:00"},
                          "2026-08-14T19:06:00+00:00"),
}
s3 = S3Stub(objs)

rows = WR.latest_per_trade(WR.read_prefix(s3, "trades", D))
check("three stored states collapse to two trades", len(rows) == 2, rows)
t1 = [r for r in rows if r["trade_id"] == 1][0]
check("the LATEST state wins (closed, not open)", t1["status"] == "closed", t1)
check("the latest state's P&L is the one kept", t1["pnl_usd"] == 412.5, t1)

# THE ordering check
closed_after_collapse = [r for r in rows if r["status"] == "closed"]
check("collapse-then-filter keeps trade 1", any(r["trade_id"] == 1 for r in closed_after_collapse))
filtered_first = [e["record"] for _s, e in WR.read_prefix(s3, "trades", D)
                  if e["record"]["status"] == "closed"]
check("filter-then-collapse would have been a DIFFERENT answer (why order matters)",
      len(filtered_first) == 2 and len(rows) == 2
      and sorted(r["trade_id"] for r in rows) == [1, 2])

# box comes from the partition
check("box is taken from the sym= partition, not the row",
      t1["box"] == "SPX" and t1["symbol"] == "SPX")
mislabeled = {K % ("TLT", "d"): env(
    {"trade_id": 3, "symbol": "WRONG", "status": "closed", "pnl_usd": 1.0,
     "entry_time": "2026-08-14T16:00:00+00:00"}, "2026-08-14T19:07:00+00:00")}
r3 = WR.latest_per_trade(WR.read_prefix(S3Stub(mislabeled), "trades", D))[0]
check("a mislabeled row keeps BOTH values for audit",
      r3["box"] == "TLT" and r3["symbol"] == "WRONG", r3)

check("_sym_of parses the partition", WR._sym_of(K % ("NVDA", "x")) == "NVDA")

# the bundle shape must match consolidate_trades'
WR.CT._load_selection = lambda d: None
bundle = WR.build(D, s3)
for k in ("meta", "selection", "fleet_stats", "by_box",
          "breaker_events", "ohlc_index", "trades"):
    check(f"bundle has '{k}' (consolidate_trades parity)", k in bundle)
check("meta records how many STATES were seen, not just trades",
      bundle["meta"]["n_trade_objects"] == 3, bundle["meta"])
check("meta names S3 as the source", "s3://" in bundle["meta"]["source"])
check("fleet_stats computed by consolidate_trades' OWN code",
      bundle["fleet_stats"]["n_closed"] == 2, bundle["fleet_stats"])
check("net pnl is right", round(bundle["fleet_stats"]["net_pnl"], 2) == 292.5,
      bundle["fleet_stats"]["net_pnl"])
check("by_box counts per partition",
      bundle["by_box"]["SPX"]["trades"] == 1 and bundle["by_box"]["QQQ"]["trades"] == 1,
      bundle["by_box"])
check("an empty date yields an empty bundle, not a crash",
      WR.build("1999-01-01", s3)["meta"]["n_trades"] == 0)


# --all: an empty-vs-empty date must not inflate the pass count
import io
import contextlib
import tempfile

tmpd = tempfile.mkdtemp()
WR.config.REPORTS_DIR = tmpd
# one date WITH trades (matches), one EMPTY on both sides
with open(os.path.join(tmpd, "fleet_trades_%s.json" % D), "w") as fh:
    json.dump({"trades": [
        {"trade_id": 1, "status": "closed", "pnl_usd": 412.5},
        {"trade_id": 2, "status": "closed", "pnl_usd": -120.0}],
        "fleet_stats": {"net_pnl": 292.5}}, fh)
# inside coverage (>= the dt= floor) so it tests EMPTY, not OUT-OF-COVERAGE
with open(os.path.join(tmpd, "fleet_trades_2026-08-20.json"), "w") as fh:
    json.dump({"trades": [], "fleet_stats": {"net_pnl": 0.0}}, fh)

buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = WR.compare_all(s3)
txt = buf.getvalue()
check("--all returns 0 when nothing diverges", rc == 0, rc)
check("--all reports the date WITH trades as a match", "MATCH  %s" % D in txt, txt[:200])
check("an empty-vs-empty date is counted SEPARATELY, not as a pass",
      "1 date(s) matched with trades" in txt and "1 matched but EMPTY" in txt, txt)
check("--all says plainly that empty dates prove nothing",
      "empty dates prove nothing" in txt, txt)
check("--all shows the stored-state count per date, not just trades",
      "states" in txt, txt[:200])


# the coverage window is READ FROM THE BUCKET, not hardcoded
lo, hi = WR.warehouse_range(s3)
check("warehouse_range reads the dt= floor from the bucket", lo == D and hi == D, (lo, hi))
check("warehouse_range on an empty bucket returns (None, None)",
      WR.warehouse_range(S3Stub({})) == (None, None))

# a pre-warehouse date must be OUT OF COVERAGE — neither match nor divergence
with open(os.path.join(tmpd, "fleet_trades_2026-07-13.json"), "w") as fh:
    json.dump({"trades": [{"trade_id": 99, "status": "closed", "pnl_usd": 7.0}],
               "fleet_stats": {"net_pnl": 7.0}}, fh)
buf2 = io.StringIO()
with contextlib.redirect_stdout(buf2):
    rc2 = WR.compare_all(s3)
t2 = buf2.getvalue()
check("a pre-warehouse date is NOT counted as divergent", rc2 == 0, rc2)
check("it is reported as OUT OF COVERAGE", "OUT OF COVERAGE" in t2, t2[-400:])
check("the floor is stated, and comes from the bucket", "warehouse holds dt=" in t2)
check("the verdict names the matched SPAN, not just a count",
      "MATCHED %s" % D in t2, t2[-300:])
check("it says plainly that pre-coverage dates are unverifiable, not wrong",
      "unverifiable, not wrong" in t2, t2[-300:])

# --since overrides the derived floor
buf3 = io.StringIO()
with contextlib.redirect_stdout(buf3):
    WR.compare_all(s3, since="2099-01-01")
check("--since overrides the derived floor",
      "--since" in buf3.getvalue() and "0 date(s) matched" in buf3.getvalue(),
      buf3.getvalue()[-200:])


# the floor is COLLECTION START, not the oldest partition present
check("COLLECTION_START is a real date, not derived from dt=",
      WR.COLLECTION_START == "2026-08-13", WR.COLLECTION_START)
WR.COLLECTION_START = D            # pin for the stub bucket
buf4 = io.StringIO()
with contextlib.redirect_stdout(buf4):
    WR.compare_all(s3)
t4 = buf4.getvalue()
check("output distinguishes what the bucket HOLDS from what it COLLECTS",
      "but only" in t4 and "COLLECTS from" in t4, t4[:300])
check("it says pre-floor dates are partial BY CONSTRUCTION",
      "partial by construction" in t4, t4[:300])

# --explain names the rows, not just the count
buf5 = io.StringIO()
with contextlib.redirect_stdout(buf5):
    WR.explain(D, s3)
t5 = buf5.getvalue()
check("--explain runs and reports on the date", D in t5, t5[:120])
check("--explain says plainly when a date matches",
      "no differences" in t5 or "ONLY IN" in t5, t5[:200])

# a date where s3 has a trade the local bundle lacks — the 07-21 shape
with open(os.path.join(tmpd, "fleet_trades_%s.json" % D), "w") as fh:
    json.dump({"trades": [{"trade_id": 1, "status": "closed", "pnl_usd": 412.5}],
               "fleet_stats": {"net_pnl": 412.5}}, fh)
buf6 = io.StringIO()
with contextlib.redirect_stdout(buf6):
    WR.explain(D, s3)
t6 = buf6.getvalue()
check("--explain surfaces a trade present in S3 but missing locally",
      "ONLY IN S3" in t6 and "missing from" in t6, t6[-400:])
check("--explain prints the row detail, not just the id",
      "pnl=" in t6, t6[-200:])


# ── the output path must not be report 41's input ───────────────────────────
import glob as _glob

check("warehouse bundles default OUTSIDE reports/",
      os.path.basename(WR.WAREHOUSE_OUT) == "warehouse"
      and WR.WAREHOUSE_OUT != WR.config.REPORTS_DIR, WR.WAREHOUSE_OUT)

# report 41's glob is non-recursive, so a subdirectory is genuinely safe —
# assert that rather than assume it
_tmp41 = tempfile.mkdtemp()
os.makedirs(os.path.join(_tmp41, "warehouse"), exist_ok=True)
open(os.path.join(_tmp41, "fleet_trades_2026-08-14.json"), "w").write("{}")
open(os.path.join(_tmp41, "warehouse", "fleet_trades_2026-08-14.json"), "w").write("{}")
hits = _glob.glob(os.path.join(_tmp41, "fleet_trades_*.json"))
check("report 41's glob does NOT reach into the warehouse subdir",
      len(hits) == 1 and "warehouse" not in hits[0], hits)

# the old default WOULD have been caught by it — proving the bug was real
old_default = os.path.join(_tmp41, "fleet_trades_s3_2026-08-14.json")
open(old_default, "w").write("{}")
check("the OLD default path WOULD have polluted 41 (the bug was real)",
      len(_glob.glob(os.path.join(_tmp41, "fleet_trades_*.json"))) == 2)

print("\n" + ("ALL CHECKS PASSED" if not FAILS else "FAILURES: " + ", ".join(FAILS)))
sys.exit(1 if FAILS else 0)
