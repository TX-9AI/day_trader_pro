#!/usr/bin/env python3
# day_trader_pro/warehouse_reader.py — v1.0
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
  python3 warehouse_reader.py --date 2026-08-14 --out reports/fleet_trades_s3_2026-08-14.json
  python3 warehouse_reader.py --date 2026-08-14 --compare   # diff vs the local bundle
"""

import argparse
import json
import os
import sys
from collections import OrderedDict
from datetime import datetime
from zoneinfo import ZoneInfo

import boto3

import config
import consolidate_trades as CT

BUCKET = os.environ.get("OT_S3_BUCKET", "vertigo-warehouse-tx9ai")
REGION = os.environ.get("OT_S3_REGION", "us-east-2")
PREFIX = os.environ.get("OT_S3_PREFIX", "raw")

_ET = ZoneInfo("US/Eastern")


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
    """Every object under raw/<datatype>/dt=<date>/, as (sym, envelope)."""
    out = []
    prefix = f"{PREFIX}/{datatype}/dt={date}/"
    pg = s3.get_paginator("list_objects_v2")
    keys = []
    for page in pg.paginate(Bucket=BUCKET, Prefix=prefix):
        for o in page.get("Contents", []) or []:
            keys.append(o["Key"])
    for k in keys:
        try:
            body = s3.get_object(Bucket=BUCKET, Key=k)["Body"].read()
            out.append((_sym_of(k), json.loads(body)))
        except Exception as exc:
            _log("WARN", f"unreadable object {k}: {exc}")
    return out


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
    rows.sort(key=lambda r: (str(r.get("entry_time") or ""), str(r.get("box") or "")))
    return rows


def build(date, s3=None):
    """The fleet_trades bundle, sourced from S3, in consolidate_trades' shape."""
    s3 = s3 or _client()

    trade_objs = read_prefix(s3, "trades", date)
    trades = latest_per_trade(trade_objs)
    _log("READ", f"trades: {len(trade_objs)} object(s) -> {len(trades)} unique trade(s)")

    regime = []
    for sym, env in read_prefix(s3, "regime_log", date):
        r = dict(env.get("record") or {})
        r["box"] = sym
        regime.append(r)
    regime.sort(key=lambda r: (str(r.get("logged_at") or ""), str(r.get("box", ""))))

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
            "regime_log": sum(1 for r in regime if r.get("box") == b),
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
        ("regime_timeline", regime),
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


def main(argv):
    p = argparse.ArgumentParser(description="Rebuild the fleet_trades bundle from S3")
    p.add_argument("--date", default=None, help="YYYY-MM-DD (default: today ET)")
    p.add_argument("--out", default=None, help="write the bundle here")
    p.add_argument("--compare", action="store_true",
                   help="diff against reports/fleet_trades_<date>.json")
    a = p.parse_args(argv[1:])
    date = a.date or datetime.now(_ET).date().isoformat()

    if a.compare:
        return compare(date)

    bundle = build(date)
    m, st = bundle["meta"], bundle["fleet_stats"]
    print(f"s3 bundle {date}: {len(m['boxes_reporting'])} boxes, "
          f"{m['n_trades']} trades ({m['n_closed']} closed) from "
          f"{m['n_trade_objects']} stored states, net {st['net_pnl']:+.2f}, "
          f"win {st['win_rate']:.0%}")
    out = a.out or os.path.join(config.REPORTS_DIR, f"fleet_trades_s3_{date}.json")
    tmp = out + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(bundle, fh, indent=2, default=str)
    os.replace(tmp, out)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
