# day_trader_pro/standings.py — v1.0
"""
Live fleet P&L rollup — READ ONLY. Runs on the control server, any time during
the session. SSH-pulls each RUNNING box's realized (closed) P&L for today
straight from its trades.db and prints per-symbol lines plus a fleet total.

It is the intraday "how are we doing right now" glance. Unlike eod_report.py it
NEVER stops a box, and unlike harvest.py it does NOT depend on the 15:50
trades_today.json — it reads the DB live, so it works from the opening bell.

What it shows per box:
  - closed trades today + realized net (the booked number on 0DTE)
  - ● a live open position (normal mid-session — a trade in progress)
  - ⚠ a STALE open row (entry not today = cross-session ghost/orphan)

Symbols come from the EC2 tag Name, so instrument labels are always correct
(no OT_INSTRUMENT / tzdata dependency).

CLI:
  python standings.py            # print the rollup to the terminal
  python standings.py --send      # also push it to Telegram (control bot)
  python standings.py --mock       # offline demo (fake fleet + fake P&L)
"""

import argparse
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import config
import instance_registry
import notify
import ssh_util

_ET = ZoneInfo("US/Eastern")

REMOTE_DB = "~/options-trader/trades.db"

# Realized (closed) net for today's ET session, live open count, and stale
# (cross-session) open count. The '-4 hours' offset mirrors eod_summary.py so
# these numbers agree with the EOD rollup. Pure SELECTs — no writes.
_SQL = (
    "SELECT "
    "(SELECT COUNT(*) FROM trades WHERE status='closed' "
    "AND date(datetime(entry_time,'-4 hours'))=date('now','-4 hours')),"
    "(SELECT COALESCE(ROUND(SUM(pnl_usd),2),0) FROM trades WHERE status='closed' "
    "AND date(datetime(entry_time,'-4 hours'))=date('now','-4 hours')),"
    "(SELECT COUNT(*) FROM trades WHERE status='open' "
    "AND date(datetime(entry_time,'-4 hours'))=date('now','-4 hours')),"
    "(SELECT COUNT(*) FROM trades WHERE status='open' "
    "AND date(datetime(entry_time,'-4 hours'))<>date('now','-4 hours'))"
)


def _query(ip):
    """Return (dict, err). dict is None on failure. Read-only over SSH."""
    cmd = f'sqlite3 -batch {REMOTE_DB} "{_SQL};"'
    rc, out, err = ssh_util.ssh_run(ip, cmd)
    if rc != 0:
        return None, (err.strip().splitlines() or ["ssh/sqlite failed"])[-1][:80]
    line = out.strip().splitlines()[0] if out.strip() else ""
    parts = line.split("|")
    if len(parts) != 4:
        return None, f"unexpected output: {line[:40] or 'empty'}"
    try:
        return {
            "closed": int(parts[0]),
            "net": float(parts[1]),
            "open_today": int(parts[2]),
            "open_stale": int(parts[3]),
        }, None
    except ValueError:
        return None, f"parse error: {line[:40]}"


def _mock_query(sym):
    h = abs(hash(sym))
    return {
        "closed": h % 4,
        "net": round(((h % 500) - 200) + (h % 100) / 100.0, 2),
        "open_today": 1 if h % 3 == 0 else 0,
        "open_stale": 1 if sym.endswith("D") else 0,   # e.g. AMD -> fake ghost
    }, None


def _money(v):
    return f"{'+' if v >= 0 else '-'}${abs(v):.2f}"


def run(send=False):
    mapping, _ = instance_registry.discover(config.UNIVERSE)
    running = {s: r for s, r in mapping.items() if r.get("state") == "running"}
    now_lbl = datetime.now(_ET).strftime("%H:%M ET")

    if not running:
        msg = f"*VERTIGO — live P&L* ({now_lbl})\nNo boxes running."
        print(msg)
        if send:
            notify.send(msg)
        return 0

    rows = []              # (sym, data_or_None, err_or_None)
    total_net = 0.0
    total_closed = 0
    live_syms = []
    ghost_syms = []
    errs = []

    for sym in sorted(running):
        ip = running[sym].get("private_ip", "")
        if config.MOCK_AWS:
            data, err = _mock_query(sym)
        elif not ip:
            data, err = None, "no private IP"
        else:
            data, err = _query(ip)

        rows.append((sym, data, err))
        if data is None:
            errs.append(f"{sym} ({err})")
            continue
        total_net += data["net"]
        total_closed += data["closed"]
        if data["open_today"]:
            live_syms.append(sym)
        if data["open_stale"]:
            ghost_syms.append(sym)

    lines = [f"*VERTIGO — live P&L* ({now_lbl})"]
    for sym, data, _err in rows:
        if data is None:
            lines.append(f"`{sym:<5}` {'—':>10}  (err)")
            continue
        mark = " ●" if data["open_today"] else ""
        mark += " ⚠" if data["open_stale"] else ""
        lines.append(f"`{sym:<5}` {_money(data['net']):>10}  ({data['closed']}t){mark}")

    reporting = sum(1 for _, d, _ in rows if d is not None)
    lines.append("──────────────")
    lines.append(f"*Net: {_money(total_net)}*  "
                 f"({reporting}/{len(running)} boxes · {total_closed} trades)")
    if live_syms:
        lines.append(f"● live position open: {', '.join(live_syms)}")
    if ghost_syms:
        lines.append(f"⚠ STALE open row (ghost): {', '.join(ghost_syms)} — check box")
    if errs:
        lines.append(f"no read: {', '.join(errs)}")

    msg = "\n".join(lines)
    print(msg)
    if send:
        notify.send(msg)
    return 0


def main(argv):
    p = argparse.ArgumentParser(description="day_trader_pro live P&L rollup (read-only)")
    p.add_argument("--mock", action="store_true", help="offline demo")
    p.add_argument("--send", action="store_true", help="also push to Telegram")
    args = p.parse_args(argv[1:])
    if args.mock:
        config.set_mock(True)
    return run(send=args.send)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
