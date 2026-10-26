#!/usr/bin/env python3
"""
day_trader_pro/ohlc_from_s3.py  v0.1.0
v0.1.0  2026-10-26 — dtp r514 / LABEL.1 — THE NIGHTLY 1m TAPE COMES FROM THE WAREHOUSE WHEN THE BOXES ARE DOWN.
        auto_label and daily_bars read ohlc/<date>/<SYM>_ohlc_<date>.csv, which only harvest (an scp from a RUNNING box)
        ever wrote; eod_analysis runs after TAKEDOWN, so ohlc/ had held one empty 2026-09-03 dir and LABEL had been
        rc=1 ("no tape for <date>") every night, DAILY_BARS "0 symbol(s) rebuilt". The same bars are in S3 under
        raw/candles/dt=<date>/sym=<SYM>/interval=1m/ (each object ~5 minutes of bars, {"record": [...]}), the stream
        the drain VERIFIES local=s3 per box. materialize() writes them in the layout harvest and the box's
        candle_logger use: timestamp,open,high,low,close,volume, ET ISO timestamps, from the session open (09:30 ET)
        onward, one row per bar (deduplicated on ts_epoch_ms), ascending.

        WHICH SYMBOLS: every sym= partition of the day that is a declared engine box on that day
        (strategy_registry.box_lineage is MAIN or OTV5) - never *_EXT (extended hours), never an undeclared stream
        (VIX), never a TEST box's (AAL; s3-trades-mixed-fleets). An existing CSV is never overwritten, so a harvest
        that ran while the boxes were up still wins. Control's role reads S3; nothing here writes to it.

        CLI:  python3 ohlc_from_s3.py --date YYYY-MM-DD [--prior] [--root DIR]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

DIR = os.path.dirname(os.path.abspath(__file__))
ET = ZoneInfo("America/New_York")
BUCKET = os.environ.get("OT_S3_BUCKET", "vertigo-warehouse-tx9ai")
REGION = os.environ.get("OT_S3_REGION", "us-east-2")
PREFIX = os.environ.get("OT_S3_PREFIX", "raw")
OHLC_ROOT = os.path.join(DIR, "ohlc")
SESSION_OPEN = (9, 30)


def _client():
    import boto3
    return boto3.client("s3", region_name=REGION)


def _engine_box(sym: str, date: str) -> bool:
    try:
        import strategy_registry as R
        return R.box_lineage(sym, date) in (R.MAIN, R.OTV5)
    except Exception:                                           # noqa: BLE001
        return False


def symbols(s3, date: str) -> list:
    """The day's 1m candle streams that belong to an engine box, sorted."""
    pre = f"{PREFIX}/candles/dt={date}/"
    out = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=pre, Delimiter="/"):
        for p in page.get("CommonPrefixes", []) or []:
            sym = p["Prefix"][len(pre):].strip("/").split("=", 1)[-1]
            if sym and not sym.upper().endswith("_EXT") and _engine_box(sym, date):
                out.append(sym.upper())
    return sorted(set(out))


def bars(s3, date: str, sym: str) -> list:
    """[(ts_et, o, h, l, c, v)] for the day from the session open on, one per ts_epoch_ms, ascending."""
    pre = f"{PREFIX}/candles/dt={date}/sym={sym}/interval=1m/"
    day = datetime.strptime(date, "%Y-%m-%d").date()
    t0 = int(datetime(day.year, day.month, day.day, *SESSION_OPEN, tzinfo=ET).timestamp() * 1000)
    t1 = int(datetime(day.year, day.month, day.day, 23, 59, 59, tzinfo=ET).timestamp() * 1000)
    by_ts = {}
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=pre):
        for o in page.get("Contents", []) or []:
            try:
                env = json.loads(s3.get_object(Bucket=BUCKET, Key=o["Key"])["Body"].read())
            except Exception as exc:                            # noqa: BLE001
                print(f"[OHLC_S3 ] unreadable {o['Key']}: {exc}", file=sys.stderr)
                continue
            for r in (env.get("record") if isinstance(env, dict) else None) or []:
                try:
                    if str(r.get("interval", "1m")) != "1m":
                        continue
                    t = int(r["ts_epoch_ms"])
                    if t0 <= t <= t1:
                        by_ts[t] = (float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]),
                                    r.get("volume"))
                except (KeyError, TypeError, ValueError):
                    continue
    return [(datetime.fromtimestamp(t / 1000, tz=timezone.utc).astimezone(ET), *by_ts[t]) for t in sorted(by_ts)]


def materialize(date: str, root: str = OHLC_ROOT, s3=None) -> dict:
    """Write ohlc/<date>/<SYM>_ohlc_<date>.csv for each engine box's stream. {SYM: rows written | 'kept' | 0}."""
    s3 = s3 or _client()
    out = {}
    day_dir = os.path.join(root, date)
    for sym in symbols(s3, date):
        path = os.path.join(day_dir, f"{sym}_ohlc_{date}.csv")
        if os.path.exists(path) and os.path.getsize(path) > 0:
            out[sym] = "kept"
            continue
        rows = bars(s3, date, sym)
        if not rows:
            out[sym] = 0
            continue
        os.makedirs(day_dir, exist_ok=True)
        tmp = path + ".part"
        with open(tmp, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["timestamp", "open", "high", "low", "close", "volume"])
            for ts, o, h, l, c, v in rows:
                w.writerow([ts.isoformat(), o, h, l, c, v if v is not None else ""])
        os.replace(tmp, path)
        out[sym] = len(rows)
    return out


def prior_session(date: str, s3=None, max_back: int = 7) -> str:
    """The nearest earlier date with an engine box's 1m stream in S3 (auto_label's SWEEP needs it), or ''."""
    s3 = s3 or _client()
    d = datetime.strptime(date, "%Y-%m-%d").date()
    for k in range(1, max_back + 1):
        c = (d - timedelta(days=k))
        if c.weekday() >= 5:
            continue
        if symbols(s3, c.isoformat()):
            return c.isoformat()
    return ""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="materialize ohlc/<date>/ from the S3 1m candle stream")
    ap.add_argument("--date", required=True)
    ap.add_argument("--prior", action="store_true", help="also the prior session (auto_label's SWEEP reads it)")
    ap.add_argument("--root", default=OHLC_ROOT)
    a = ap.parse_args(argv)
    s3 = _client()
    dates = [a.date]
    if a.prior:
        p = prior_session(a.date, s3)
        if p:
            dates.append(p)
    rc = 0
    for d in dates:
        res = materialize(d, a.root, s3)
        wrote = sum(1 for v in res.values() if isinstance(v, int) and v > 0)
        kept = sum(1 for v in res.values() if v == "kept")
        empty = sorted(s for s, v in res.items() if v == 0)
        print(f"[OHLC_S3 ] {d}: {wrote} written, {kept} kept, {len(empty)} empty{(' ' + ','.join(empty)) if empty else ''}")
        if d == a.date and not wrote and not kept:
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
