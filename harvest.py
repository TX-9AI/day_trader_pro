# day_trader_pro/harvest.py — v0.1.0
"""
Trade-anatomy harvester. Runs on the control server (~15:55 ET, after each bot
writes trades_today.json at 15:50, BEFORE the 16:00 sweep stops the boxes).

It SSH-pulls every running box's full closed-trade detail and folds it into ONE
analysis file: daily_trades_<date>.json. That single file is what you hand to
Claude for "study the fleet's trades today" — every trade, every column, plus
fleet-wide stats and the morning's selection (what was chosen vs how it did).

Pure read: it never stops a box. Safe to run any time to snapshot current state.

CLI:
  python harvest.py            # pull + aggregate + write + Telegram note
  python harvest.py --quiet     # no Telegram
  python harvest.py --mock       # offline demo
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

import config
import instance_registry
import notify
import ssh_util

_ET = ZoneInfo("US/Eastern")
HARVEST_DIR = os.path.join(config.DATA_DIR, "harvest")
SELECTION_LOG = os.path.join(config.DATA_DIR, "selection_log.jsonl")


def _today_et():
    return datetime.now(_ET).strftime("%Y-%m-%d")


def _pull(ip):
    rc, out, err = ssh_util.ssh_run(ip, "cat ~/eod/trades_today.json")
    if rc != 0:
        return None, (err.strip().splitlines() or ["ssh failed"])[-1][:100]
    try:
        return json.loads(out), None
    except json.JSONDecodeError:
        return None, "bad/empty trades file"


def _mock_pull(sym):
    h = abs(hash(sym))
    n = h % 5
    trades = []
    for i in range(n):
        pnl = round(((h >> i) % 300) - 120 + i * 3.5, 2)
        trades.append({
            "trade_id": f"{sym}-{i}", "status": "closed",
            "setup_type": ["ORB", "IronCondor", "Butterfly", "SweepRev"][(h + i) % 4],
            "setup_grade": ["A", "B", "C"][(h + i) % 3],
            "option_side": "call" if (h + i) % 2 else "put",
            "contracts": 1 + (h + i) % 4, "pnl_usd": pnl,
            "exit_reason": ["target", "stop", "regime_flip", "eod"][(h + i) % 4],
        })
    return {"date_et": _today_et(), "instrument": sym, "paper": True,
            "trades": trades, "open_positions": []}, None


def _load_selection():
    """Most recent selection-log entry for today (what Claude picked)."""
    try:
        today = _today_et()
        latest = None
        with open(SELECTION_LOG) as fh:
            for line in fh:
                e = json.loads(line)
                if e.get("ts_utc", "").startswith(today) or True:
                    latest = e  # keep last; today filter is soft
        return latest
    except Exception:  # noqa: BLE001
        return None


def _stats(all_trades):
    def num(t):
        try:
            return float(t.get("pnl_usd") or 0)
        except (TypeError, ValueError):
            return 0.0
    pnls = [num(t) for t in all_trades]
    wins = [p for p in pnls if p > 0]
    by_setup = defaultdict(lambda: {"n": 0, "net": 0.0})
    by_grade = defaultdict(lambda: {"n": 0, "net": 0.0})
    for t in all_trades:
        p = num(t)
        by_setup[t.get("setup_type", "?")]["n"] += 1
        by_setup[t.get("setup_type", "?")]["net"] += p
        by_grade[t.get("setup_grade", "?")]["n"] += 1
        by_grade[t.get("setup_grade", "?")]["net"] += p
    return {
        "n_trades": len(pnls),
        "wins": len(wins),
        "losses": len(pnls) - len(wins),
        "win_rate": round(len(wins) / len(pnls), 3) if pnls else 0.0,
        "net_pnl": round(sum(pnls), 2),
        "best": round(max(pnls), 2) if pnls else 0.0,
        "worst": round(min(pnls), 2) if pnls else 0.0,
        "by_setup": {k: {"n": v["n"], "net": round(v["net"], 2)}
                     for k, v in by_setup.items()},
        "by_grade": {k: {"n": v["n"], "net": round(v["net"], 2)}
                     for k, v in by_grade.items()},
    }


def run(quiet=False):
    mapping, _ = instance_registry.discover(config.UNIVERSE)
    running = {s: r for s, r in mapping.items() if r.get("state") == "running"}
    today = _today_et()

    per_symbol = {}
    all_trades = []
    missing = []

    for sym in sorted(running):
        ip = running[sym].get("private_ip", "")
        data, err = _mock_pull(sym) if config.MOCK_AWS else (
            _pull(ip) if ip else (None, "no private IP"))
        if data is None:
            missing.append(f"{sym} ({err})")
            continue
        trades = data.get("trades", [])
        for t in trades:
            t["symbol"] = sym          # tag each trade with its box
            all_trades.append(t)
        per_symbol[sym] = {
            "instrument": data.get("instrument", sym),
            "paper": data.get("paper"),
            "n_trades": len(trades),
            "net_pnl": round(sum(float(t.get("pnl_usd") or 0) for t in trades), 2),
            "open_positions": data.get("open_positions", []),
            "trades": trades,
        }

    report = {
        "date_et": today,
        "generated_utc": datetime.now(ZoneInfo("UTC")).isoformat(),
        "fleet": {
            "running": len(running),
            "reporting": len(per_symbol),
            "missing": missing,
        },
        "selection": _load_selection(),   # what Claude picked this morning
        "fleet_stats": _stats(all_trades),
        "by_symbol": per_symbol,
        "all_trades": all_trades,         # flat, each tagged with "symbol"
    }

    os.makedirs(HARVEST_DIR, exist_ok=True)
    out = os.path.join(HARVEST_DIR, f"daily_trades_{today}.json")
    tmp = out + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(report, fh, indent=2, default=str)
    os.replace(tmp, out)

    st = report["fleet_stats"]
    print(f"harvest {today}: {len(per_symbol)}/{len(running)} boxes, "
          f"{st['n_trades']} trades, net {st['net_pnl']:+.2f}, "
          f"win rate {st['win_rate']:.0%}")
    print(f"wrote {out}")
    if missing:
        print(f"missing: {', '.join(missing)}")

    if not quiet:
        msg = (f"*trade harvest {today}*\n"
               f"{len(per_symbol)}/{len(running)} boxes · {st['n_trades']} trades · "
               f"net {st['net_pnl']:+.2f} · win {st['win_rate']:.0%}\n"
               f"saved daily_trades_{today}.json")
        if missing:
            msg += f"\n⚠️ no trade file: {', '.join(missing)}"
        notify.send(msg)
    return 0


def main(argv):
    p = argparse.ArgumentParser(description="day_trader_pro trade harvester")
    p.add_argument("--mock", action="store_true", help="offline demo")
    p.add_argument("--quiet", action="store_true", help="no Telegram note")
    args = p.parse_args(argv[1:])
    if args.mock:
        config.set_mock(True)
    return run(quiet=args.quiet)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
