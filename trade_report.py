# day_trader_pro/trade_report.py — v1.0
"""
Cross-day trade breakdown — what actually made and lost money, ranked.

Read-only, offline. Pools every closed trade from the fleet_trades_<date>.json
bundles that consolidate_trades.py already writes, then ranks performance across
the dimensions that matter:

    by regime          which market states pay
    by strategy        which trade types pay
    by setup_type      which setups pay
    by setup_grade     does the grade actually predict outcome
    by exit_reason     how trades end, and what each ending costs
    regime x strategy  the cross-cut that matters most: a strategy is rarely
                       good or bad outright, it is good or bad IN A REGIME

Also derives HOLD DURATION (exit_time - entry_time), which is computed nowhere
else, and pairs it with the MFE/MAE telemetry (max/min_premium_seen) so exit
behaviour is visible: did winners get room to run, were losers cut before or
after they went against you.

Small buckets are flagged, not hidden -- a 3-trade bucket with a great win rate
is noise, and the report says so rather than letting it look like signal.

Usage:
    python trade_report.py                     # all banked sessions
    python trade_report.py --since 2026-07-14  # from a date forward
    python trade_report.py --min-n 10          # flag threshold (default 8)
    python trade_report.py --live              # live trades only (default: all)
    python trade_report.py --paper             # paper trades only
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import config
    REPORTS_DIR = getattr(config, "REPORTS_DIR",
                          os.path.expanduser("~/day_trader_pro/reports"))
except Exception:                                     # standalone use
    REPORTS_DIR = os.path.expanduser("~/day_trader_pro/reports")

BUNDLE_GLOB = os.path.join(REPORTS_DIR, "fleet_trades_*.json")


# ── loading ──────────────────────────────────────────────────────────────────
def load_trades(since: Optional[str], mode: Optional[str]) -> tuple:
    files = sorted(glob.glob(BUNDLE_GLOB))
    trades, used = [], []
    for path in files:
        date = os.path.basename(path)[len("fleet_trades_"):-len(".json")]
        if since and date < since:
            continue
        try:
            with open(path) as fh:
                bundle = json.load(fh)
        except Exception as exc:                       # noqa: BLE001
            print(f"  ! skipped {os.path.basename(path)}: {exc}", file=sys.stderr)
            continue
        rows = bundle.get("trades") or []
        closed = [r for r in rows if (r.get("status") or "") == "closed"]
        if mode == "live":
            closed = [r for r in closed if not _truthy(r.get("paper_trade"))]
        elif mode == "paper":
            closed = [r for r in closed if _truthy(r.get("paper_trade"))]
        for r in closed:
            r["_date"] = date
        trades.extend(closed)
        used.append((date, len(closed)))
    return trades, used


def _truthy(v) -> bool:
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "t")
    return bool(v)


def _f(v) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def hold_minutes(row: Dict[str, Any]) -> Optional[float]:
    """exit_time - entry_time in minutes. Timestamps are UTC ISO from ts_for_db()."""
    a, b = row.get("entry_time"), row.get("exit_time")
    if not a or not b:
        return None
    try:
        t0 = datetime.fromisoformat(str(a).replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(str(b).replace("Z", "+00:00"))
        m = (t1 - t0).total_seconds() / 60.0
        return m if m >= 0 else None
    except (TypeError, ValueError):
        return None


# ── aggregation ──────────────────────────────────────────────────────────────
def bucket(trades: List[dict], key: str) -> Dict[str, dict]:
    agg: Dict[str, dict] = defaultdict(
        lambda: {"n": 0, "wins": 0, "net": 0.0, "pnls": [], "holds": []})
    for t in trades:
        k = t.get(key) or "(none)"
        p = _f(t.get("pnl_usd"))
        if p is None:
            continue
        a = agg[str(k)]
        a["n"] += 1
        a["net"] += p
        a["pnls"].append(p)
        if p > 0:
            a["wins"] += 1
        h = hold_minutes(t)
        if h is not None:
            a["holds"].append(h)
    return agg


def fmt_row(name: str, a: dict, min_n: int, width: int = 26) -> str:
    n = a["n"]
    win = a["wins"] / n if n else 0.0
    avg = a["net"] / n if n else 0.0
    hold = statistics.median(a["holds"]) if a["holds"] else None
    flag = "  <- thin" if n < min_n else ""
    hold_s = f"{hold:>7.1f}" if hold is not None else "      -"
    return (f"  {name[:width]:<{width}}{n:>5}{win:>7.0%}"
            f"{a['net']:>11.2f}{avg:>9.2f}{hold_s}{flag}")


def print_dimension(title: str, agg: Dict[str, dict], min_n: int) -> None:
    if not agg:
        return
    print(f"\n{title}")
    print(f"  {'':<26}{'N':>5}{'WIN%':>7}{'NET $':>11}{'AVG $':>9}{'HOLD m':>7}")
    for name, a in sorted(agg.items(), key=lambda kv: -kv[1]["net"]):
        print(fmt_row(name, a, min_n))


def print_cross(trades: List[dict], min_n: int) -> None:
    """regime x strategy — where a strategy actually earns or bleeds."""
    agg: Dict[tuple, dict] = defaultdict(
        lambda: {"n": 0, "wins": 0, "net": 0.0, "pnls": [], "holds": []})
    for t in trades:
        p = _f(t.get("pnl_usd"))
        if p is None:
            continue
        k = (str(t.get("regime") or "(none)"), str(t.get("strategy") or "(none)"))
        a = agg[k]
        a["n"] += 1
        a["net"] += p
        a["pnls"].append(p)
        if p > 0:
            a["wins"] += 1
        h = hold_minutes(t)
        if h is not None:
            a["holds"].append(h)
    if not agg:
        return
    print("\nREGIME x STRATEGY  (the cross-cut: a strategy is good IN a regime)")
    print(f"  {'':<26}{'N':>5}{'WIN%':>7}{'NET $':>11}{'AVG $':>9}{'HOLD m':>7}")
    for (reg, strat), a in sorted(agg.items(), key=lambda kv: -kv[1]["net"]):
        print(fmt_row(f"{reg[:14]} / {strat[:11]}", a, min_n))


def print_excursion(trades: List[dict]) -> None:
    """Winners vs losers: hold time and how far each ran / bled (MFE/MAE)."""
    win_h, los_h, win_mfe, los_mae = [], [], [], []
    for t in trades:
        p = _f(t.get("pnl_usd"))
        if p is None:
            continue
        h = hold_minutes(t)
        entry = _f(t.get("entry_premium"))
        mx, mn = _f(t.get("max_premium_seen")), _f(t.get("min_premium_seen"))
        if p > 0:
            if h is not None:
                win_h.append(h)
            if entry and mx:
                win_mfe.append((mx - entry) / entry)
        else:
            if h is not None:
                los_h.append(h)
            if entry and mn:
                los_mae.append((mn - entry) / entry)
    if not (win_h or los_h):
        return
    print("\nEXIT BEHAVIOUR  (did winners get room, were losers cut early)")
    if win_h:
        print(f"  winners   n={len(win_h):<5} median hold {statistics.median(win_h):>7.1f} min")
    if los_h:
        print(f"  losers    n={len(los_h):<5} median hold {statistics.median(los_h):>7.1f} min")
    if win_mfe:
        print(f"  winners   median MFE {statistics.median(win_mfe):>+7.1%} of entry premium")
    if los_mae:
        print(f"  losers    median MAE {statistics.median(los_mae):>+7.1%} of entry premium")
    if win_h and los_h:
        wm, lm = statistics.median(win_h), statistics.median(los_h)
        if lm > 0 and wm / lm < 1.2:
            print("  NOTE winners are not being held meaningfully longer than losers —")
            print("       exits may be cutting runners as fast as they cut mistakes.")


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description="cross-day trade breakdown")
    ap.add_argument("--since", help="only sessions on/after this date (YYYY-MM-DD)")
    ap.add_argument("--min-n", type=int, default=8,
                    help="flag buckets thinner than this (default 8)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--live", action="store_true", help="live trades only")
    g.add_argument("--paper", action="store_true", help="paper trades only")
    args = ap.parse_args(argv[1:])
    mode = "live" if args.live else ("paper" if args.paper else None)

    trades, used = load_trades(args.since, mode)
    if not trades:
        print(f"No closed trades found in {BUNDLE_GLOB}")
        print("Run the consolidation first (devtools: re-run consolidation).")
        return 2

    print(f"loaded {len(used)} session(s):")
    for date, n in used:
        print(f"   {date}   {n:>5} closed trades")

    pnls = [_f(t.get("pnl_usd")) for t in trades]
    pnls = [p for p in pnls if p is not None]
    wins = [p for p in pnls if p > 0]
    holds = [h for h in (hold_minutes(t) for t in trades) if h is not None]

    print("\n" + "=" * 74)
    label = {"live": "LIVE", "paper": "PAPER"}.get(mode, "ALL")
    print(f"TRADE BREAKDOWN — {len(pnls)} closed trades [{label}]")
    print("=" * 74)
    print(f"  net {sum(pnls):+.2f}   win rate {len(wins)/len(pnls):.0%}   "
          f"avg {sum(pnls)/len(pnls):+.2f}   "
          f"best {max(pnls):+.2f}   worst {min(pnls):+.2f}")
    if holds:
        print(f"  median hold {statistics.median(holds):.1f} min   "
              f"({len(holds)}/{len(pnls)} rows have both timestamps)")
    else:
        print("  hold duration unavailable (entry_time/exit_time missing)")

    print_dimension("BY REGIME", bucket(trades, "regime"), args.min_n)
    print_dimension("BY STRATEGY", bucket(trades, "strategy"), args.min_n)
    print_dimension("BY SETUP TYPE", bucket(trades, "setup_type"), args.min_n)
    print_dimension("BY SETUP GRADE", bucket(trades, "setup_grade"), args.min_n)
    print_dimension("BY EXIT REASON", bucket(trades, "exit_reason"), args.min_n)
    print_cross(trades, args.min_n)
    print_excursion(trades)

    print("\n" + "=" * 74)
    print(f"Rows are sorted by NET. '<- thin' marks fewer than {args.min_n} trades —")
    print("those win rates are noise, not signal. Read the cross-cut before")
    print("concluding a strategy is bad: it may only be bad in one regime.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
