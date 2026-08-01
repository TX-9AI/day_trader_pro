#!/usr/bin/env python3
"""
day_trader_pro/daily_bars.py — v1.0 — 2026-08-01

Rebuild a DAILY OHLC series per symbol from the 1-minute tape we already own.

WHY THIS EXISTS — item AP, the pitchfork's daily fork had no data source
    §4.2 of docs/WHITEPAPER_pitchfork_overlay.md wants a daily fork at k=2 with
    R=40 recency. Live serves `TIMEFRAMES["1d"]["candles"] = 10` — ten daily bars
    cannot yield a k=2 triple with 5-bar separation, let alone 40 bars of
    recency. §6 then names a daily rail within C*ATR of an hourly rail as the
    HIGHEST-VALUE signal the whole overlay produces, and with only one fork there
    is nothing to confluence against. So the missing daily series blocks the
    paper's headline application, not merely a second fork.

WHY NOT YFINANCE, which was the obvious candidate and is the wrong one
    1. It was PURGED from the data path for cause: large disparity against
       TastyTrade on the lowest timeframes. It normalises on the highest, but a
       fractal pivot anchors on HIGHS AND LOWS, not closes — and daily H/L is
       exactly where a differing consolidated tape or pre/post-market inclusion
       would show up. "It normalises" is an observation about convergence, not a
       guarantee about the two values the fork actually reads.
    2. A "30 day" 1-minute pull is capped at 21 SESSIONS, so building dailies up
       from their intraday inherits both the cap and the disparity.
    3. The operator's decisive objection, and it is the right one: WHAT HAPPENS
       WHEN A FORK INVALIDATES. Re-anchoring selects a NEW triple from the daily
       series, so those bars must be current AT THAT MOMENT. A manual pull is
       stale the next day; making it recurring means a second live data
       dependency — the very thing the purge removed. Any yfinance arrangement
       here is a band-aid.

    Aggregating our own tape has none of that. `phase_harvest` lands a new
    `ohlc/<date>/` every night, so the series extends itself. A fork invalidating
    in October re-anchors against a series that is current by construction, with
    no manual step and no second feed. It also keeps the fork's
    "reconstructible from tape" property literally true, which is what its
    determinism rests on.

WHY IT REBUILDS RATHER THAN APPENDS
    Recomputing the whole series each night is cheap at this scale and
    IDEMPOTENT. It self-heals when a session is backfilled late or re-harvested —
    which an append would silently get wrong, leaving a bar computed from partial
    tape sitting in the series forever with nothing to flag it.

WHY NIGHTLY AND NOT WEEKLY
    Same invalidation argument. A weekly rebuild means a fork dying on Wednesday
    re-anchors against a series missing Mon-Wed. Nightly matches the harvest
    cadence, so the series is never more than one session behind.

HISTORY, STATED PLAINLY
    The tape starts ~2026-07-13, so the series is SHORT and grows one bar per
    session. A k=2 fork needs P0 at index >=2, P1 >=7, P2 >=12, confirmed at 14 —
    so ~15 sessions is the floor and it is reached with zero margin. Comfortable
    (~29 bars) by the Aug 21 freeze, which is when PF.4 wiring happens anyway.
    The daily fork therefore ripens on the schedule the overlay needs it. Do not
    "fix" the short history by reaching back to a second feed.

SCOPE NOTE — control-side only, deliberately
    This writes on CONTROL. PF.1/PF.2/PF.3 are offline work that runs here, so
    that is sufficient today. Getting the series onto the bot boxes is a PF.4
    (post-freeze) distribution problem and is NOT solved here — see AP.

Run standalone:  python3 daily_bars.py            (rebuild all symbols)
                 python3 daily_bars.py --dry-run
In the conductor: phase_daily_bars(), after phase_harvest.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    from config import OHLC_DIR
except Exception:                                                 # noqa: BLE001
    OHLC_DIR = os.path.join(BASE_DIR, "ohlc")

DAILY_DIR = os.path.join(os.path.dirname(OHLC_DIR), "daily")
DATE_RE = re.compile(r"^20\d\d-\d\d-\d\d$")

# A session with fewer than this many 1-minute rows is PARTIAL — a late start, a
# feed outage, a box that woke mid-morning. Its high/low are not the session's,
# and a fractal pivot anchored on them would be anchored on an artifact. Recorded
# in the series with a flag rather than silently dropped, so the gap is visible.
MIN_ROWS_FULL_SESSION = 300          # of ~390 RTH minutes


def _sessions(ohlc_root: str) -> List[str]:
    if not os.path.isdir(ohlc_root):
        return []
    return sorted(d for d in os.listdir(ohlc_root)
                  if DATE_RE.match(d) and os.path.isdir(os.path.join(ohlc_root, d)))


def _tape_files(day_dir: str) -> Dict[str, str]:
    """{SYMBOL: path}. Keyed on the '_ohlc_' infix so sibling artifacts
    (fleet_trades_*.csv and friends) are never mistaken for tape."""
    out = {}
    for f in sorted(os.listdir(day_dir)):
        low = f.lower()
        if "_ohlc_" in low and low.endswith(".csv"):
            out[f.split("_ohlc_")[0].upper()] = os.path.join(day_dir, f)
    return out


def _aggregate(path: str) -> Optional[Tuple[float, float, float, float, int, int]]:
    """One session's 1-minute rows -> (open, high, low, close, volume, n_rows).

    Reads with csv rather than pandas so the conductor phase carries no heavy
    import. Rows with unparseable numbers are skipped, not guessed at, and the
    row count comes back so the caller can judge completeness.
    """
    o = c = None
    hi = float("-inf")
    lo = float("inf")
    vol = 0
    n = 0
    try:
        with open(path, newline="") as fh:
            for row in csv.DictReader(fh):
                try:
                    ro, rh, rl, rc = (float(row["open"]), float(row["high"]),
                                      float(row["low"]), float(row["close"]))
                except (KeyError, TypeError, ValueError):
                    continue
                if o is None:
                    o = ro
                c = rc
                hi = max(hi, rh)
                lo = min(lo, rl)
                try:
                    vol += int(float(row.get("volume") or 0))
                except (TypeError, ValueError):
                    pass
                n += 1
    except OSError:
        return None
    if o is None or n == 0:
        return None
    return o, hi, lo, c, vol, n


def rebuild(ohlc_root: str = OHLC_DIR, daily_dir: str = DAILY_DIR,
            dry_run: bool = False) -> Dict[str, int]:
    """Rebuild daily/<SYM>.csv for every symbol present in the tape.

    Returns {SYMBOL: bars written}. Never raises on a bad session — a symbol that
    cannot be aggregated for one date simply has no bar for that date, and the
    `partial` column marks sessions built from short tape.
    """
    dates = _sessions(ohlc_root)
    series: Dict[str, List[list]] = {}

    for date in dates:
        for sym, path in _tape_files(os.path.join(ohlc_root, date)).items():
            agg = _aggregate(path)
            if agg is None:
                continue
            o, hi, lo, c, vol, n = agg
            series.setdefault(sym, []).append(
                [date, f"{o:.4f}", f"{hi:.4f}", f"{lo:.4f}", f"{c:.4f}",
                 vol, n, int(n < MIN_ROWS_FULL_SESSION)])

    if dry_run:
        return {s: len(rows) for s, rows in series.items()}

    os.makedirs(daily_dir, exist_ok=True)
    written = {}
    for sym, rows in series.items():
        rows.sort(key=lambda r: r[0])
        tmp = os.path.join(daily_dir, f".{sym}.csv.tmp")
        dest = os.path.join(daily_dir, f"{sym}.csv")
        # write-then-rename: a reader mid-rebuild sees the old series or the new
        # one, never a half-written file. The fork's determinism assumes the
        # series it reads is whole.
        with open(tmp, "w", newline="") as fh:
            # lineterminator="\n". csv.writer defaults to CRLF, which puts a
            # literal \r on the last field of every row — awk/grep then compare
            # against "1\r" and quietly never match. Caught while verifying the
            # partial-session flag, which WAS being set and looked as if it were
            # not. Unix endings, so downstream tools behave.
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(["date", "open", "high", "low", "close", "volume",
                        "minute_rows", "partial"])
            w.writerows(rows)
        os.replace(tmp, dest)
        written[sym] = len(rows)
    return written


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ohlc-root", default=OHLC_DIR)
    ap.add_argument("--daily-dir", default=DAILY_DIR)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv[1:])

    res = rebuild(a.ohlc_root, a.daily_dir, dry_run=a.dry_run)
    if not res:
        print(f"no tape found under {a.ohlc_root}")
        return 2
    bars = max(res.values())
    print(f"{'[dry] ' if a.dry_run else ''}daily series: {len(res)} symbols, "
          f"{bars} sessions max -> {a.daily_dir}")
    # The floor the pitchfork needs, stated every run so the gap stays visible
    # instead of being rediscovered when a fork silently fails to build.
    if bars < 15:
        print(f"    NOTE: a k=2 daily fork needs ~15 sessions (P2 confirmed at "
              f"index 14). At {bars} it cannot build yet — this fills in at one "
              f"bar per session.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
