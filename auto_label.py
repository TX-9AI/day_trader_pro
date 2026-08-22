#!/usr/bin/env python3
# day_trader_pro/auto_label.py — v1.0
# v1.0 (2026-07-23) — automate the Tier-B session labeling habit (ROADMAP L1.8),
#   and BACKFILL every archived session in one pass.
"""
Auto session labeler — derives Tier-B labels from RAW PRICE ACTION.

WHY THIS EXISTS
    label_day.sh v1.0 is a 10-minute manual EOD habit. It works, but it has two
    problems: it is one more script to remember, and it CANNOT LABEL THE PAST.
    Layer-1 DONE needs ">= 10 sessions x 29 symbols of labeled tape" — and there
    are already ~13 archived sessions in ohlc/ that no amount of daily
    discipline can retroactively tag. This labels all of them in one run.

THE INDEPENDENCE RULE (why this is legitimate, and where the line is)
    Tier-B labels are GROUND TRUTH used to validate a classifier. Deriving
    them FROM that classifier would grade it against its own
    output and prove nothing.

    So this module imports NOTHING from any classification stack, and no
    trend engine. Every rule
    below is computed from OHLC bars alone using textbook price-action
    definitions that existed long before this system did. That is what keeps the
    acceptance test honest.

    Labels are written with "source":"auto" so the calibration can weight,
    audit, or exclude them. A human override via label_day.sh writes the same
    date with no source field and wins downstream (latest line per date wins).

THE RULES (all thresholds tunable; all from OHLC only)
    TREND     body/range >= TREND_BODY and close in the top/bottom
              TREND_CLOSE decile of the day's range.
              "Opened one end, closed the other" — the classic trend day.
    SWEEP     took out the prior session's extreme and CLOSED BACK INSIDE it.
              A failed breach = a liquidity sweep. Needs a prior session.
    BREAKOUT  broke the prior session's extreme and CLOSED BEYOND it (held).
              The mirror image of SWEEP; mutually exclusive with it by
              construction.
    PIN       final-hour range <= PIN_RATIO of the day's range — the
              coil-into-the-close that COMPRESSION is supposed to catch.
    CHOP      session-level: fewer than CHOP_MAX_TREND_FRAC of symbols
              qualified as TREND. Useful for flat-angle base rates (L1.6).

WHAT THIS DELIBERATELY DOES NOT DO
    SWEEP here is a price-action proxy, not a "mapper-confirmed named-zone
    reclaim" as the Tier-B row specifies. It is a strong candidate filter, not
    a substitute for confirming the zone was a mapped one. Treat auto SWEEP
    labels as a shortlist to confirm, not as closure of that row.

USAGE
    python auto_label.py --backfill              # every archived date, skip existing
    python auto_label.py --backfill --rebuild    # re-label everything
    python auto_label.py --date 2026-07-23       # one session
    python auto_label.py --backfill --dry-run    # print, write nothing

Read-only against the tape. Appends only to reports/session_labels.jsonl.
"""

import argparse
import json
import os
import sys
from datetime import datetime

try:
    import pandas as pd
except ImportError:
    print("auto_label needs pandas (it is already in the dtp venv)")
    raise

DIR = os.path.dirname(os.path.abspath(__file__))
OHLC_ROOT = os.path.join(DIR, "ohlc")
OUT = os.path.join(DIR, "reports", "session_labels.jsonl")

# ── thresholds (CLI-overridable) ──────────────────────────────────────────────
TREND_BODY = 0.60          # |close-open| / (high-low)
TREND_CLOSE = 0.20         # close within this fraction of the day's extreme
PIN_RATIO = 0.25           # last-hour range / day range
CHOP_MAX_TREND_FRAC = 0.10  # < this share of symbols trending => CHOP session
MIN_BARS = 60              # ignore symbol-days thinner than this


def load_day(path):
    try:
        df = pd.read_csv(path)
        if df.empty or "close" not in df.columns:
            return None
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df.set_index("timestamp").sort_index()
    except Exception:
        return None


def sym_of(fname):
    up = fname.upper()
    for tag in ("_OHLC_",):
        if tag in up:
            return fname[: up.index(tag)].upper()
    return os.path.splitext(fname)[0].upper()


def day_stats(df):
    """Everything the rules need, from bars alone."""
    o = float(df["open"].iloc[0])
    c = float(df["close"].iloc[-1])
    h = float(df["high"].max())
    l = float(df["low"].min())
    rng = h - l
    if rng <= 0:
        return None
    last = df.iloc[-60:] if len(df) >= 60 else df
    lh, ll = float(last["high"].max()), float(last["low"].min())
    return {
        "open": o, "close": c, "high": h, "low": l, "range": rng,
        "body_frac": abs(c - o) / rng,
        "close_pos": (c - l) / rng,          # 1.0 = closed at the high
        "last_hour_frac": (lh - ll) / rng,
    }


def label_session(date, ohlc_root, prior_date=None, thresholds=None):
    t = thresholds or {}
    tb = t.get("trend_body", TREND_BODY)
    tc = t.get("trend_close", TREND_CLOSE)
    pr = t.get("pin_ratio", PIN_RATIO)

    day_dir = os.path.join(ohlc_root, date)
    if not os.path.isdir(day_dir):
        return None
    files = [f for f in sorted(os.listdir(day_dir)) if f.lower().endswith(".csv")]
    if not files:
        return None

    prior_dir = os.path.join(ohlc_root, prior_date) if prior_date else None
    tags = {"TREND": [], "SWEEP": [], "PIN": [], "BREAKOUT": []}
    n_sym = 0

    for f in files:
        df = load_day(os.path.join(day_dir, f))
        if df is None or len(df) < MIN_BARS:
            continue
        s = day_stats(df)
        if not s:
            continue
        sym = sym_of(f)
        n_sym += 1

        # TREND — opened one end, closed the other, with a dominant body
        if s["body_frac"] >= tb and (s["close_pos"] >= 1 - tc or s["close_pos"] <= tc):
            tags["TREND"].append(sym)

        # PIN — coiled into the close
        if s["last_hour_frac"] <= pr:
            tags["PIN"].append(sym)

        # SWEEP / BREAKOUT — need the prior session's extremes
        if prior_dir and os.path.isdir(prior_dir):
            pf = None
            for cand in os.listdir(prior_dir):
                if sym_of(cand) == sym and cand.lower().endswith(".csv"):
                    pf = os.path.join(prior_dir, cand)
                    break
            if pf:
                pdf = load_day(pf)
                if pdf is not None and len(pdf) >= MIN_BARS:
                    ph, pl = float(pdf["high"].max()), float(pdf["low"].min())
                    # breached the prior extreme, closed back INSIDE  -> sweep
                    if (s["high"] > ph and s["close"] < ph) or \
                       (s["low"] < pl and s["close"] > pl):
                        tags["SWEEP"].append(sym)
                    # breached and CLOSED BEYOND -> breakout that held
                    elif (s["high"] > ph and s["close"] > ph) or \
                         (s["low"] < pl and s["close"] < pl):
                        tags["BREAKOUT"].append(sym)

    if not n_sym:
        return None
    chop = (len(tags["TREND"]) / n_sym) < t.get("chop_frac", CHOP_MAX_TREND_FRAC)

    row = {"date": date,
           "labeled_at": datetime.now().astimezone().isoformat(timespec="seconds"),
           "source": "auto"}
    for k in ("TREND", "SWEEP", "PIN", "BREAKOUT"):
        if tags[k]:
            row[k] = sorted(tags[k])
    row["CHOP"] = chop
    row["note"] = f"auto v1.0 from price action; {n_sym} symbols"
    return row


def existing_dates(path):
    got = set()
    if not os.path.isfile(path):
        return got
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                got.add(json.loads(line).get("date"))
            except Exception:
                pass
    return got


def main():
    ap = argparse.ArgumentParser(description="Auto Tier-B session labeler (price action only)")
    ap.add_argument("--date", help="label one date (YYYY-MM-DD)")
    ap.add_argument("--backfill", action="store_true", help="label every archived date")
    ap.add_argument("--rebuild", action="store_true", help="re-label dates already present")
    ap.add_argument("--dry-run", action="store_true", help="print, write nothing")
    ap.add_argument("--ohlc", default=OHLC_ROOT, help="ohlc root (default ./ohlc)")
    ap.add_argument("--out", default=OUT, help="session_labels.jsonl path")
    ap.add_argument("--trend-body", type=float, default=TREND_BODY)
    ap.add_argument("--trend-close", type=float, default=TREND_CLOSE)
    ap.add_argument("--pin-ratio", type=float, default=PIN_RATIO)
    a = ap.parse_args()

    root = os.path.abspath(os.path.expanduser(a.ohlc))
    if not os.path.isdir(root):
        print(f"no ohlc root at {root}")
        return 1
    dates = sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d)))
    if a.date:
        dates = [d for d in dates if d == a.date]
        if not dates:
            print(f"no tape for {a.date}")
            return 1
    elif not a.backfill:
        dates = dates[-1:]          # default: most recent session

    have = existing_dates(a.out)
    thresholds = {"trend_body": a.trend_body, "trend_close": a.trend_close,
                  "pin_ratio": a.pin_ratio}

    rows, skipped = [], 0
    for i, d in enumerate(dates):
        if d in have and not a.rebuild:
            skipped += 1
            continue
        prior = dates[i - 1] if i > 0 else None
        r = label_session(d, root, prior_date=prior, thresholds=thresholds)
        if r:
            rows.append(r)

    if not rows:
        print(f"nothing to label ({skipped} already labeled; --rebuild to redo)")
        return 0

    print(f"{'date':12s} {'TREND':>6s} {'SWEEP':>6s} {'PIN':>5s} {'BREAK':>6s}  CHOP")
    for r in rows:
        print(f"{r['date']:12s} {len(r.get('TREND', [])):>6d} {len(r.get('SWEEP', [])):>6d} "
              f"{len(r.get('PIN', [])):>5d} {len(r.get('BREAKOUT', [])):>6d}  {r['CHOP']}")

    if a.dry_run:
        print(f"\n(dry run — {len(rows)} row(s) not written)")
        return 0

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "a") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    print(f"\nwrote {len(rows)} row(s) -> {a.out}"
          f"{f'  ({skipped} already labeled)' if skipped else ''}")
    print("Tier-B coverage now:")
    for tag in ("TREND", "SWEEP", "PIN", "BREAKOUT"):
        n = sum(1 for r in rows if r.get(tag))
        print(f"  {tag:9s} {n} session(s) in this run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
