#!/usr/bin/env python3
"""day_trader_pro/tests/test_ohlc_from_s3.py — v1.0
v1.0  2026-10-26 — dtp r514 / LABEL.1 — THE NIGHTLY TAPE COMES FROM S3, AND LABEL / DAILY_BARS READ IT.
      LABEL had been rc=1 ("no tape for <date>") every night and DAILY_BARS rebuilt 0 symbols: both read ohlc/<date>/,
      which only harvest from a RUNNING box wrote, and eod_analysis runs after takedown. A fake S3 client (no network).

  T1  only engine boxes' 1m streams are materialized: AMD yes; AMD_EXT, VIX (undeclared) and AAL (TEST) no
  T2  overlapping objects are deduplicated on ts_epoch_ms; bars before 09:30 ET dropped; ascending
  T3  the file is ohlc/<date>/<SYM>_ohlc_<date>.csv with header timestamp,open,high,low,close,volume and ET timestamps
  T4  an existing (harvested) CSV is kept, never overwritten
  T5  auto_label.label_session reads the materialized day and returns a row; daily_bars.rebuild builds AMD from it
  T6  eod_analysis runs a TAPE phase BEFORE DAILY_BARS and LABEL, through ohlc_from_s3.materialize

Born red on dtp 98a980e at T1 (no module) and every check after it.
"""
import ast
import io
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
FAILED = []
ET = ZoneInfo("America/New_York")
DATE = "2026-10-26"


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        FAILED.append(name.split()[0])


def _ms(h, m):
    return int(datetime(2026, 10, 26, h, 0, tzinfo=ET).timestamp() * 1000) + m * 60_000      # m may pass 59


def _bar(sym, h, m, px):
    return {"symbol": sym, "interval": "1m", "ts_epoch_ms": _ms(h, m), "open": px, "high": px + 0.5,
            "low": px - 0.5, "close": px + 0.1, "volume": 1000.0}


class FakeS3:
    """list_objects_v2 paginator (with Delimiter) + get_object over an in-memory key -> envelope map."""

    def __init__(self, objs):
        self.objs = objs

    def get_paginator(self, _name):
        objs = self.objs

        class Pg:
            def paginate(self, Bucket, Prefix, Delimiter=None):
                keys = sorted(k for k in objs if k.startswith(Prefix))
                if Delimiter:
                    cps = sorted({Prefix + k[len(Prefix):].split(Delimiter, 1)[0] + Delimiter
                                  for k in keys if Delimiter in k[len(Prefix):]})
                    yield {"CommonPrefixes": [{"Prefix": c} for c in cps]}
                else:
                    yield {"Contents": [{"Key": k, "Size": 1} for k in keys]}
        return Pg()

    def get_object(self, Bucket, Key):
        return {"Body": io.BytesIO(json.dumps(self.objs[Key]).encode())}


def _env(rows):
    return {"schema_version": 1, "datatype": "candles", "record": rows}


def main():
    try:
        import ohlc_from_s3 as T
    except Exception as exc:                                    # noqa: BLE001
        check("T1 ohlc_from_s3 imports", False, f"{type(exc).__name__}: {exc}")
        print(f"\nRED — {len(FAILED)} failed: {', '.join(FAILED)}")
        return 1
    base = f"raw/candles/dt={DATE}"
    amd = [_bar("AMD", 9, 30 + i, 100 + i) for i in range(0, 70)]          # 09:30 .. 10:39
    objs = {
        f"{base}/sym=AMD/interval=1m/a.json": _env([_bar("AMD", 9, 25, 99)] + amd[:40]),   # a pre-open bar + 40
        f"{base}/sym=AMD/interval=1m/b.json": _env(amd[30:]),                              # overlaps 10 bars
        f"{base}/sym=AMD/interval=5m/c.json": _env([dict(_bar("AMD", 9, 30, 1), interval="5m")]),
        f"{base}/sym=AMD_EXT/interval=1m/d.json": _env([_bar("AMD_EXT", 17, 0, 1)]),
        f"{base}/sym=VIX/interval=1m/e.json": _env([_bar("VIX", 10, 0, 20)]),
        f"{base}/sym=AAL/interval=1m/f.json": _env([_bar("AAL", 10, 0, 12)]),
        f"{base}/sym=QQQ/interval=1m/g.json": _env([_bar("QQQ", 9, 30 + i, 600 + i) for i in range(70)]),
    }
    s3 = FakeS3(objs)
    root = tempfile.mkdtemp(prefix="t_ohlc_s3_")
    try:
        syms = T.symbols(s3, DATE)
        check("T1 engine boxes only: AMD and QQQ; no AMD_EXT, VIX or AAL", syms == ["AMD", "QQQ"], str(syms))

        qpath = os.path.join(root, DATE, f"QQQ_ohlc_{DATE}.csv")
        os.makedirs(os.path.dirname(qpath))
        open(qpath, "w").write("timestamp,open,high,low,close,volume\nHARVESTED\n")
        res = T.materialize(DATE, root, s3)
        apath = os.path.join(root, DATE, f"AMD_ohlc_{DATE}.csv")
        lines = open(apath).read().splitlines() if os.path.exists(apath) else []
        ts = [l.split(",")[0] for l in lines[1:]]
        check("T2 deduplicated on ts, pre-open dropped, ascending: 70 bars 09:30..10:39",
              res.get("AMD") == 70 and len(ts) == 70 and ts == sorted(ts) and ts[0].startswith(f"{DATE}T09:30"),
              f"res={res.get('AMD')} n={len(ts)} first={ts[:1]}")
        check("T3 <SYM>_ohlc_<date>.csv, the box's header, ET timestamps",
              lines[:1] == ["timestamp,open,high,low,close,volume"] and ts[0].endswith("-04:00"), str(lines[:2]))
        check("T4 a harvested CSV is kept, never overwritten",
              res.get("QQQ") == "kept" and "HARVESTED" in open(qpath).read(), str(res.get("QQQ")))

        os.remove(qpath)
        T.materialize(DATE, root, s3)
        import auto_label
        import daily_bars
        row = auto_label.label_session(DATE, root)
        dd = tempfile.mkdtemp(prefix="t_daily_")
        try:
            built = daily_bars.rebuild(ohlc_root=root, daily_dir=dd)
        finally:
            shutil.rmtree(dd, ignore_errors=True)
        check("T5 auto_label labels the materialized day; daily_bars builds AMD and QQQ",
              bool(row) and isinstance(built, dict) and {"AMD", "QQQ"} <= set(built), f"row={bool(row)} built={built}")
    finally:
        shutil.rmtree(root, ignore_errors=True)

    src = open(os.path.join(REPO, "eod_analysis.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    import re
    m = re.search(r"for nm, fn, note in \((.*?)\)\):", src, re.S)
    order = re.findall(r'\("([A-Z_]+)"', m.group(1)) if m else []
    tape = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_tape"), None)
    check("T6 a TAPE phase runs before DAILY_BARS and LABEL, through ohlc_from_s3.materialize",
          "TAPE" in order and "DAILY_BARS" in order and "LABEL" in order
          and order.index("TAPE") < order.index("DAILY_BARS") < order.index("LABEL")
          and tape is not None and "materialize" in ast.unparse(tape), str(order))

    print()
    if FAILED:
        print(f"RED — {len(FAILED)} failed: {', '.join(FAILED)}")
        return 1
    print("GREEN — 6 checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
