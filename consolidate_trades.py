# day_trader_pro/consolidate_trades.py — v1.1.1
# v1.1.1 (2026-07-23) — correct stale data/harvest path references (layout retired; now reports/ + ohlc/ + trades/)
"""
Fleet trades consolidator. Merges the raw per-box trades.db files that harvest
pulled into trades/<date>/ into ONE full-fidelity deliverable for the
trades-analysis thread — nothing curated away, because every column the bots
log is a variable to study.

Sources (all local — pure SQLite reads, no fleet round-trip):
  trades/<date>/<SYM>_<date>_trades.db        (one per running box)
  ohlc/<date>/<SYM>_ohlc_<date>.csv           (indexed, not embedded)
  data/selection_log.jsonl                     (what Claude picked this morning)

From each db it reads, VERBATIM (SELECT * — so any future ALTER TABLE ADD COLUMN
is carried automatically, nothing hard-coded):
  * trades                  — every row, every column (full ~55-field schema)
  * regime_log              — the day's regime classifications (conviction/ADX/trigger)
  * circuit_breaker_events  — any daily-loss halts that fired
Each row is tagged with `box` (the SYMBOL from the FILENAME — authoritative fleet
tag), and the row's own `symbol` column is left untouched, so a mislabeled db can
never confuse the merge and both values survive for audit.

Outputs into the same day folder:
  fleet_trades_<date>.json   ← THE deliverable for the analysis thread (bundle:
                               meta + selection + fleet_stats + regime_timeline +
                               breaker_events + ohlc_index + every trade, full schema)
  fleet_trades_<date>.csv    ← flat trades union (superset of columns) for pandas

Robust: a missing/locked/corrupt db is skipped and reported, never fatal; a box on
an older schema (no regime_log / circuit_breaker_events table) is handled gracefully.

CLI:
  python consolidate_trades.py                      # today, default harvest dir
  python consolidate_trades.py --date 2026-07-09    # any past day
  python consolidate_trades.py --dir /path/to/day   # an explicit folder
  python consolidate_trades.py --no-csv             # JSON only
"""

import argparse
import csv
import glob
import json
import os
import re
import sqlite3
import sys
from collections import OrderedDict, defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

import config

_ET = ZoneInfo("US/Eastern")
SELECTION_LOG = os.path.join(config.DATA_DIR, "selection_log.jsonl")

_DB_RE = re.compile(r"^(?P<sym>.+)_trades_(?P<date>\d{4}-\d{2}-\d{2})\.db$")


def _today_et():
    return datetime.now(_ET).strftime("%Y-%m-%d")


def _read_table(conn, table):
    """(columns, [rowdict,...]) for `table`; ([],[]) if the table is absent."""
    try:
        cur = conn.execute(f"SELECT * FROM {table}")
    except sqlite3.OperationalError:
        return [], []            # older schema without this table — not an error
    cols = [d[0] for d in cur.description]
    rows = [OrderedDict(zip(cols, r)) for r in cur.fetchall()]
    return cols, rows


def _load_selection(date):
    """Most recent selection-log entry, preferring today's (what Claude picked AM)."""
    try:
        latest = None
        with open(SELECTION_LOG) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if e.get("ts_utc", "").startswith(date):
                    latest = e
                elif latest is None:
                    latest = e   # soft fallback: keep last seen if none match today
        return latest
    except FileNotFoundError:
        return None
    except Exception:  # noqa: BLE001
        return None


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _stats(trades):
    """Calibration rollups over CLOSED trades (open/orphan rows still ride along in
    trades[]; they're just excluded from win-rate math)."""
    closed = [t for t in trades if str(t.get("status", "")).lower() == "closed"]
    pnls = [_num(t.get("pnl_usd")) for t in closed]
    wins = [p for p in pnls if p > 0]

    def _bucket(key):
        agg = defaultdict(lambda: {"n": 0, "net": 0.0, "wins": 0})
        for t in closed:
            k = t.get(key)
            k = "?" if k in (None, "") else str(k)
            p = _num(t.get("pnl_usd"))
            agg[k]["n"] += 1
            agg[k]["net"] += p
            agg[k]["wins"] += 1 if p > 0 else 0
        return {k: {"n": v["n"], "net": round(v["net"], 2),
                    "win_rate": round(v["wins"] / v["n"], 3) if v["n"] else 0.0}
                for k, v in sorted(agg.items())}

    return {
        "n_trades_total": len(trades),
        "n_closed": len(closed),
        "n_open": len(trades) - len(closed),
        "wins": len(wins),
        "losses": len(closed) - len(wins),
        "win_rate": round(len(wins) / len(closed), 3) if closed else 0.0,
        "net_pnl": round(sum(pnls), 2),
        "best": round(max(pnls), 2) if pnls else 0.0,
        "worst": round(min(pnls), 2) if pnls else 0.0,
        "by_strategy": _bucket("strategy"),
        "by_setup_type": _bucket("setup_type"),
        "by_setup_grade": _bucket("setup_grade"),
        "by_regime": _bucket("regime"),
        "by_exit_reason": _bucket("exit_reason"),
    }


def consolidate(date=None, write_csv=True):
    date = date or _today_et()
    trades_dir = os.path.join(config.TRADES_DIR, date)   # <SYM>_trades_<date>.db
    ohlc_dir = os.path.join(config.OHLC_DIR, date)       # <SYM>_ohlc_<date>.csv
    os.makedirs(config.REPORTS_DIR, exist_ok=True)       # flat aggregates land here

    dbs = sorted(glob.glob(os.path.join(trades_dir, f"*_trades_{date}.db")))
    if not dbs:
        cause = ("no trades/ folder yet — harvest hasn't run for this date"
                 if not os.path.isdir(trades_dir) else f"no *_trades_{date}.db there")
        print(f"⚠️  nothing to consolidate for {date}: {cause}.")
        print(f"    looked in: {trades_dir}")
        print("    run harvest first (python harvest.py), or stage dbs as "
              "trades/<date>/<SYM>_trades_<date>.db.")
    trades = []
    regime = []
    breaker = []
    by_box = OrderedDict()
    boxes_read = []
    skipped = []
    col_union = OrderedDict()      # preserves first db's schema order, appends extras

    for path in dbs:
        base = os.path.basename(path)
        m = _DB_RE.match(base)
        sym = m.group("sym") if m else base
        try:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5.0)
        except sqlite3.Error as exc:
            skipped.append(f"{sym} ({exc})")
            continue
        try:
            _tc, trows = _read_table(conn, "trades")
            for r in trows:
                r["box"] = sym                 # authoritative fleet tag (from filename)
                for c in r:
                    col_union.setdefault(c, None)
                trades.append(r)
            _rc, rrows = _read_table(conn, "regime_log")
            for r in rrows:
                r["box"] = sym
                regime.append(r)
            _bc, brows = _read_table(conn, "circuit_breaker_events")
            for r in brows:
                r["box"] = sym
                breaker.append(r)
            by_box[sym] = {"trades": len(trows), "regime_log": len(rrows),
                           "breaker_events": len(brows)}
            boxes_read.append(sym)
        except sqlite3.DatabaseError as exc:
            skipped.append(f"{sym} (corrupt: {exc})")
        finally:
            conn.close()

    # Deterministic ordering for readability (does not drop anything).
    trades.sort(key=lambda t: (str(t.get("box", "")), str(t.get("entry_time") or "")))
    regime.sort(key=lambda r: (str(r.get("logged_at") or ""), str(r.get("box", ""))))
    breaker.sort(key=lambda b: (str(b.get("event_time") or ""), str(b.get("box", ""))))

    ohlc_index = sorted(os.path.basename(p) for p in (
        glob.glob(os.path.join(ohlc_dir, f"*_ohlc_{date}.csv"))
        + glob.glob(os.path.join(ohlc_dir, f"*_OHLC_{date}.csv"))))

    n_closed = sum(1 for t in trades if str(t.get("status", "")).lower() == "closed")
    bundle = OrderedDict([
        ("meta", OrderedDict([
            ("date_et", date),
            ("generated_utc", datetime.now(ZoneInfo("UTC")).isoformat()),
            ("boxes_reporting", boxes_read),
            ("boxes_skipped", skipped),
            ("n_trades", len(trades)),
            ("n_closed", n_closed),
            ("n_open", len(trades) - n_closed),
            ("trade_columns", list(col_union.keys())),   # the full variable list
        ])),
        ("selection", _load_selection(date)),            # AM picks + reasoning
        ("fleet_stats", _stats(trades)),
        ("by_box", by_box),
        ("regime_timeline", regime),
        ("breaker_events", breaker),
        ("ohlc_index", ohlc_index),                      # cross-ref, not embedded
        ("trades", trades),                              # every row, every column
    ])

    out_json = os.path.join(config.REPORTS_DIR, f"fleet_trades_{date}.json")
    tmp = out_json + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(bundle, fh, indent=2, default=str)
    os.replace(tmp, out_json)

    out_csv = None
    if write_csv and trades:
        out_csv = os.path.join(config.REPORTS_DIR, f"fleet_trades_{date}.csv")
        fieldnames = ["box"] + [c for c in col_union if c != "box"]
        tmpc = out_csv + ".tmp"
        with open(tmpc, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore", restval="")
            w.writeheader()
            for t in trades:
                w.writerow(t)
        os.replace(tmpc, out_csv)

    return bundle, out_json, out_csv


def main(argv):
    p = argparse.ArgumentParser(description="Consolidate the fleet's raw trades.db into one bundle")
    p.add_argument("--date", default=None, help="YYYY-MM-DD (default: today ET)")
    p.add_argument("--no-csv", action="store_true", help="write JSON only")
    args = p.parse_args(argv[1:])
    bundle, out_json, out_csv = consolidate(date=args.date, write_csv=not args.no_csv)
    m = bundle["meta"]
    st = bundle["fleet_stats"]
    print(f"consolidated {m['date_et']}: {len(m['boxes_reporting'])} boxes, "
          f"{m['n_trades']} trades ({m['n_closed']} closed), "
          f"net {st['net_pnl']:+.2f}, win {st['win_rate']:.0%}")
    print(f"wrote {out_json}")
    if out_csv:
        print(f"wrote {out_csv}")
    if m["boxes_skipped"]:
        print(f"skipped: {', '.join(m['boxes_skipped'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
