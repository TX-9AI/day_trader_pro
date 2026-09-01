# day_trader_pro/standings.py — v1.1
# v1.1 (2026-09-01) — dtp r236. THE ROLLUP SHOWS THE TRADES, NOT JUST THE
#   TOTALS. Operator, 2026-09-01: "it correctly lists open positions on x, y &
#   z — great, so show me what they are (time entered, symbol, strategy,
#   premium & open P&L at that moment) for all OPEN trades ... [and] the day's
#   closed trades below the open positions."  Pulled straight from the boxes,
#   same read-only SSH path as the per-symbol lines.
#   · TELEGRAM PROMPT REMOVED. "I'm already in the terminal & that's where I
#     want to see it." The menu no longer asks; `--send` survives as a CLI flag
#     for any non-interactive caller.
#   🔴 THE `-4 hours` SESSION OFFSET WAS EDT, HARDCODED, AND SILENTLY WRONG IN
#   NOVEMBER. r125 found and fixed exactly this class in the otv4 devtools
#   sensors — "the FIRST VERSION OF THAT FIX WAS -4 hours, WHICH IS EDT AND
#   SILENTLY WRONG IN NOVEMBER" — and this file kept the bug, with a comment
#   saying it mirrors eod_summary.py, which means eod_summary has it too
#   (filed, not fixed here: one file per revision). The offset is now READ FROM
#   THE TZ DATABASE on control at run time, so it is -4 in September and -5 in
#   December without anyone remembering.
#   ⚠️ OPEN P&L IS SIGNED BY STRUCTURE, and this is NOT what query.py does.
#   A credit vertical's `current_premium` is the spread's CURRENT VALUE and it
#   profits as that falls, so its P&L is (credit - now), the mirror of a debit's
#   (now - cost). query.py:268 applies the debit formula to everything, so its
#   Unrealized line is sign-inverted on every credit spread — filed as RPT.6
#   rather than copied here, because propagating it to make two reports agree
#   would be agreeing on the wrong number.
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
def _et_offset() -> str:
    """The ET UTC offset RIGHT NOW, as an sqlite modifier: '-4 hours' in EDT,
    '-5 hours' in EST.

    🔴 THIS WAS A HARDCODED '-4 hours'. r125 caught the identical bug in the
    otv4 sensor reports and its own note is the warning: EDT is right for eight
    months and silently wrong for four, and the failure is a report that filters
    on the wrong day rather than one that errors. Read from the tz database so
    nobody has to remember in November.
    """
    off = datetime.now(_ET).utcoffset()
    return f"{int(off.total_seconds() // 3600)} hours"


def _sql(off: str) -> str:
    """Aggregates AND the rows behind them, in ONE round trip per box.

    ⚠️ ONE QUERY, NOT TWO. A second SSH call per box would double the fan-out
    latency on a 15-box fleet and could straddle a fill, so the totals and the
    trade list would disagree with each other on the same screen.
    ⚠️ TAGGED UNION: column MEANING depends on col 1. For an open row col 6 is
    the live mark; for a closed row it is the exit price. Named in the parser
    rather than left to the reader.
    """
    today = f"date(datetime(entry_time,'{off}'))=date('now','{off}')"
    closed_today = f"date(datetime(exit_time,'{off}'))=date('now','{off}')"
    return (
        "SELECT 'O'||char(9)||COALESCE(datetime(entry_time,'" + off + "'),'')"
        "||char(9)||COALESCE(symbol,'')||char(9)||COALESCE(strategy,'')"
        "||char(9)||COALESCE(entry_premium,0)||char(9)||COALESCE(current_premium,0)"
        "||char(9)||COALESCE(contracts,0)||char(9)||''"
        "||char(9)||COALESCE(credit_received,0) "
        "FROM trades WHERE status='open' "
        "UNION ALL "
        "SELECT 'C'||char(9)||COALESCE(datetime(exit_time,'" + off + "'),'')"
        "||char(9)||COALESCE(symbol,'')||char(9)||COALESCE(strategy,'')"
        "||char(9)||COALESCE(entry_premium,0)||char(9)||COALESCE(exit_price,0)"
        "||char(9)||COALESCE(contracts,0)||char(9)||COALESCE(pnl_usd,0)"
        "||char(9)||COALESCE(credit_received,0) "
        f"FROM trades WHERE status='closed' AND {closed_today} "
        "ORDER BY 1"
    )


def open_pnl(entry_prem, mark, contracts, credit):
    """Unrealized dollars, SIGNED BY STRUCTURE.

    🔑 A credit vertical's `current_premium` is the spread's CURRENT VALUE and
    the position profits as that FALLS, so its P&L is (credit - now); a debit's
    is (now - cost). Returns None when the box has not stamped a mark yet —
    absent is not zero, and a fabricated 0.00 on a live position is exactly the
    plausible-silence class this project keeps finding.
    """
    try:
        e, m, n = float(entry_prem or 0), float(mark or 0), int(contracts or 0)
    except (TypeError, ValueError):
        return None
    if not e or not m or not n:
        return None
    return ((e - m) if float(credit or 0) > 0 else (m - e)) * n * 100


_STRAT_ABBR = {
    "ORBStrategy": "ORB", "RunawayContinuation": "RUN",
    "GEXPinButterfly": "BFLY", "SweepCreditSpread": "SWP",
    "TrendCreditSpread": "TCS", "IronCondorStrategy": "CNDR",
    "SweepReversal": "SWPR", "ContinuationStrategy": "CONT",
}


def _abbr(name):
    """Short strategy tag. ⚠️ An unknown name is TRUNCATED, never dropped — a
    blank column would silently hide a strategy nobody added to this table.
    Same table and same rule as trade_report._abbr (r202)."""
    n = str(name or "?")
    return _STRAT_ABBR.get(n, n[:4].upper())


def _query(ip, off, today_et):
    """Return (dict, err). dict is None on failure. Read-only over SSH.

    ⚠️ THE ROWS ARE THE SOURCE AND THE TOTALS ARE DERIVED FROM THEM, not
    computed separately on the box. Two independent computations of one number
    is how a header comes to disagree with the list beneath it.
    """
    cmd = f'sqlite3 -batch -separator "|" {REMOTE_DB} "{_sql(off)};"'
    rc, out, err = ssh_util.ssh_run(ip, cmd)
    if rc != 0:
        return None, (err.strip().splitlines() or ["ssh/sqlite failed"])[-1][:80]
    opens, closed = [], []
    for line in (out or "").strip().splitlines():
        f = line.split("\t")
        if len(f) != 9:
            continue
        tag, ts, sym, strat, ep, mk, n, pnl, credit = f
        rec = {"ts": ts, "sym": sym, "strategy": strat, "entry": ep,
               "mark": mk, "contracts": n, "credit": credit}
        if tag == "O":
            # ⚠️ STALE vs LIVE is decided on the ENTRY DATE, exactly as before:
            # an open row from a prior session is a cross-session ghost, not a
            # position in progress, and the two must not be summed together.
            rec["stale"] = not str(ts).startswith(today_et)
            rec["pnl"] = open_pnl(ep, mk, n, credit)
            opens.append(rec)
        else:
            try:
                rec["pnl"] = float(pnl)
            except (TypeError, ValueError):
                rec["pnl"] = 0.0
            closed.append(rec)
    live = [o for o in opens if not o["stale"]]
    ghosts = [o for o in opens if o["stale"]]
    return {
        "closed": len(closed),
        "net": round(sum(c["pnl"] for c in closed), 2),
        "open_today": len(live),
        "open_stale": len(ghosts),
        "rows_open": live,
        "rows_ghost": ghosts,
        "rows_closed": closed,
    }, None


def _stable_hash(sym):
    """⚠️ NOT `hash()`. Python randomises string hashing per process, so the
    v1.0 mock produced DIFFERENT fake fleets on consecutive runs — fine for a
    demo, useless as a fixture, and a test built on it would flake for reasons
    unrelated to the code. crc32 is stable across processes and releases."""
    import zlib
    return zlib.crc32(str(sym).encode())


def _mock_query(sym, today_et):
    h = _stable_hash(sym)
    n_closed = h % 4
    closed = [{"ts": f"{today_et} 1{i}:0{i}:00", "sym": sym,
               "strategy": "ORBStrategy", "entry": "1.20", "mark": "1.05",
               "contracts": "4", "credit": "0",
               "pnl": round(((h + i) % 300) - 150.0, 2)}
              for i in range(n_closed)]
    opens = ([{"ts": f"{today_et} 13:05:00", "sym": sym,
               "strategy": "GEXPinButterfly", "entry": "0.42", "mark": "0.55",
               "contracts": "12", "credit": "0", "stale": False,
               "pnl": open_pnl("0.42", "0.55", "12", "0")}]
             if h % 3 == 0 else [])
    ghosts = ([{"ts": "2026-08-31 14:00:00", "sym": sym, "strategy": "?",
                "entry": "0.50", "mark": "0", "contracts": "1", "credit": "0",
                "stale": True, "pnl": None}]
              if sym.endswith("D") else [])
    return {
        "closed": len(closed),
        "net": round(sum(c["pnl"] for c in closed), 2),
        "open_today": len(opens),
        "open_stale": len(ghosts),
        "rows_open": opens, "rows_ghost": ghosts, "rows_closed": closed,
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

    off = _et_offset()
    today_et = datetime.now(_ET).strftime("%Y-%m-%d")
    all_open, all_ghost, all_closed = [], [], []

    for sym in sorted(running):
        ip = running[sym].get("private_ip", "")
        if config.MOCK_AWS:
            data, err = _mock_query(sym, today_et)
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
        all_open.extend(data.get("rows_open") or [])
        all_ghost.extend(data.get("rows_ghost") or [])
        all_closed.extend(data.get("rows_closed") or [])

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

    # ── THE TRADES BEHIND THE TOTALS ──────────────────────────────────────
    # Operator, 2026-09-01: show what the open positions ARE, and the day's
    # closed trades below them. 43 characters wide, because this is read over
    # Termius on a phone (r202's constraint, same reason).
    def _hhmm(ts):
        # `ts` is already ET (converted in SQL). A malformed stamp renders as
        # '--:--' rather than raising — one bad row must not cost the report.
        try:
            return str(ts).split(" ")[1][:5]
        except (IndexError, AttributeError):
            return "--:--"

    def _pnl(v):
        # ⚠️ '—' NOT '$0.00'. A box that has not stamped a mark yet is
        # UNMEASURED, and a fabricated zero on a live position reads as a
        # flat trade — the plausible-silence class this project keeps finding.
        return "—" if v is None else _money(v)

    if all_open:
        lines.append("")
        lines.append(f"OPEN POSITIONS ({len(all_open)})")
        lines.append(f"  {'time':<5} {'sym':<5} {'strat':<4} "
                     f"{'entry':>5} {'now':>5} {'P&L':>9}")
        for r in sorted(all_open, key=lambda x: str(x["ts"])):
            lines.append(f"  {_hhmm(r['ts']):<5} {r['sym'][:5]:<5} "
                         f"{_abbr(r['strategy']):<4} "
                         f"{float(r['entry'] or 0):>5.2f}"
                         f"→{float(r['mark'] or 0):>5.2f} {_pnl(r['pnl']):>9}")
        _live = [r["pnl"] for r in all_open if r["pnl"] is not None]
        if _live:
            # ⚠️ OPEN AND REALIZED ARE NEVER ADDED TOGETHER. The headline Net
            # above is BOOKED money; this is a separate, moving number and
            # summing them would present a mark as though it were a fill.
            lines.append(f"  unrealized (not in Net): {_money(sum(_live))}")

    if all_ghost:
        lines.append("")
        lines.append(f"⚠ STALE OPEN ROWS ({len(all_ghost)}) — entry not today")
        for r in sorted(all_ghost, key=lambda x: str(x["ts"])):
            lines.append(f"  {str(r['ts'])[:16]} {r['sym'][:5]:<5} "
                         f"{_abbr(r['strategy']):<4}")

    if all_closed:
        lines.append("")
        lines.append(f"CLOSED TODAY ({len(all_closed)})")
        lines.append(f"  {'time':<5} {'sym':<5} {'strat':<4} "
                     f"{'entry':>5} {'exit':>5} {'P&L':>9}")
        for r in sorted(all_closed, key=lambda x: str(x["ts"])):
            lines.append(f"  {_hhmm(r['ts']):<5} {r['sym'][:5]:<5} "
                         f"{_abbr(r['strategy']):<4} "
                         f"{float(r['entry'] or 0):>5.2f}"
                         f"→{float(r['mark'] or 0):>5.2f} "
                         f"{_money(r['pnl']):>9}")

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
