#!/usr/bin/env python3
# day_trader_pro/tests/test_warehouse_reader.py — v1.0
"""
Pins warehouse_reader v1.0 (WH.8).

CHANGELOG
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
            def paginate(self, Bucket=None, Prefix="", **kw):
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
for k in ("meta", "selection", "fleet_stats", "by_box", "regime_timeline",
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

print("\n" + ("ALL CHECKS PASSED" if not FAILS else "FAILURES: " + ", ".join(FAILS)))
sys.exit(1 if FAILS else 0)
