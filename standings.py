# day_trader_pro/standings.py — v1.4
# v1.4 (2026-09-02) — dtp r249. 🔴 `REMOTE_DB` IS "~/options-trader/trades.db"
#   AND PYTHON DOES NOT EXPAND `~`. The sqlite3 CLI never had to — the REMOTE
#   SHELL expanded it before sqlite3 saw the argument. r248 moved that same
#   string into a Python string literal, where nothing expands it, so every
#   box failed to open a path that had worked for months because of something
#   the shell was quietly doing for it. `os.path.expanduser` on the box.
#   ⚠️ AND THE ERROR PICKER CHOSE THE WRONG LINE TWICE RUNNING: [-1] is the
#   CARET of a sqlite error, and the first "named" line of a Python traceback
#   is the HEADER. It now takes the LAST line that names a fault, which is
#   correct for both shapes, and the remote program reports the resolved path
#   and whether the file exists so the next failure diagnoses itself.
# v1.3 (2026-09-02) — dtp r248. 🔴 ALL FIFTEEN BOXES RETURNED A PARSE CARET.
#   r236 sent an 807-character query with nested quoting through ssh, a remote
#   shell and into the sqlite3 CLI. The SQL is VALID against the sqlite
#   library, so the fault was TRANSPORT. It now ships base64-encoded and runs
#   under the box's python3: no metacharacters to escape, no CLI version to
#   depend on — and C.26 says that CLI is not installed at all, a note I
#   dismissed on 09-01 because the report was working, without checking that
#   the working version and the one I was writing used the same mechanism.
#   ⚠️ AND THE ERROR LINE WAS THE LEAST USEFUL ONE: [-1] of a multi-line
#   sqlite error is the CARET, so the report printed 'error here ---^' fifteen
#   times and hid its own diagnosis behind its own formatting.
# v1.2 (2026-09-01) — dtp r237. 🔴 HOTFIX: r236 BROKE THE LIVE PATH IT WAS
#   WRITTEN FOR. `_query` gained `off` and `today_et`; the MOCK call site was
#   updated and the REAL one was not, so menu 59 raised TypeError on the first
#   box and the whole report died — `_query() missing 2 required positional
#   arguments`.
#   ⚠️ AND THE TEST COULD NOT HAVE CAUGHT IT. tests/test_standings_rows.py
#   runs under `config.set_mock(True)`, so every case took the `_mock_query`
#   branch and the live branch was never executed. Eight green checks over a
#   report that could not run — the same shape as r195's standing offer,
#   where the checks exercised `resting_orders` directly and never drove
#   `_place_single_leg` in paper.
#   THE FIX IS THE TEST, NOT ONLY THE LINE: S9 now stubs `ssh_util.ssh_run`
#   and runs `run()` with MOCK_AWS FALSE, so the real `_query` executes and
#   parses a real tab-separated payload. Born red against r236.
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
import base64
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
    # 🔴 r248 — THE sqlite3 CLI IS GONE FROM THIS PATH. r236 sent an 807-char
    # query with nested quoting through ssh, a remote shell and into a CLI
    # whose version nobody had checked, and on 2026-09-02 ALL FIFTEEN BOXES
    # came back with a parse caret. The SQL itself is VALID — executed against
    # the sqlite LIBRARY it returns the right rows — so the fault was in
    # TRANSPORT, not in the query.
    # 🔑 BASE64 REMOVES THE QUOTING PROBLEM RATHER THAN MANAGING IT. The
    # payload carries no shell metacharacters, so nothing between here and the
    # box can mangle it; no amount of careful escaping is as reliable as having
    # nothing to escape.
    # ⚠️ AND IT RUNS UNDER THE BOX'S python3, NOT A CLI. C.26 recorded that
    # sqlite3 is not installed on the boxes. I dismissed that note on
    # 2026-09-01 because this report was working — without checking that the
    # WORKING version and the version I was WRITING used the same mechanism.
    # python3 is certainly present (the bot runs on it) and its sqlite3 module
    # needs no separator flag, no version floor and no quoting.
    # ⚠️ READ-ONLY BY URI: a report must never be able to write to the book.
    # 🔴 r249 — `REMOTE_DB` IS "~/options-trader/trades.db" AND PYTHON DOES NOT
    # EXPAND `~`. The sqlite3 CLI never had to: the REMOTE SHELL expanded the
    # tilde before sqlite3 saw the argument. r248 moved that same string into a
    # PYTHON STRING LITERAL, where nothing expands it, so every box failed with
    # "unable to open database file" — a path that had worked for months
    # because of something the shell was doing for it, silently.
    # ⚠️ THE LESSON IS THE MOVE, NOT THE TILDE: a value that crosses from a
    # shell context into a program context loses everything the shell was doing
    # for it, and none of that is visible in the value itself.
    # ⚠️ AND THE PROGRAM DIAGNOSES ITSELF NOW. A bare traceback told us the
    # exception type and nothing about WHY, so it reports the resolved path and
    # whether the file is there — the two facts needed to tell a bad path from
    # a missing database from a permissions problem.
    prog = (
        "import sqlite3,base64,sys,os\n"
        "p=os.path.expanduser(%r)\n"
        "q=base64.b64decode('%s').decode()\n"
        "try:\n"
        "    c=sqlite3.connect('file:'+p+'?mode=ro',uri=True)\n"
        "    sys.stdout.write('\\n'.join(r[0] for r in c.execute(q)))\n"
        "except Exception as e:\n"
        "    sys.stderr.write('DBError: %%s: %%s (path=%%s exists=%%s)'\n"
        "                     %% (type(e).__name__, e, p, os.path.exists(p)))\n"
        "    raise SystemExit(1)\n"
        % (REMOTE_DB, base64.b64encode(_sql(off).encode()).decode()))
    cmd = "echo %s | base64 -d | python3 -" % (
        base64.b64encode(prog.encode()).decode())
    rc, out, err = ssh_util.ssh_run(ip, cmd)
    if rc != 0:
        # 🔴 THE ERROR LINE WAS THE LEAST USEFUL ONE. This took [-1] of stderr
        # and 80 characters of it — and for a multi-line sqlite error the last
        # line is the CARET, so all fifteen boxes reported
        # "                    error here ---^" and the report hid its own
        # diagnosis behind its own formatting. Prefer the line that names the
        # fault; fall back to the first non-empty line, never the last.
        # 🔴 THIS PICKED THE WRONG LINE TWICE RUNNING. First it took [-1],
        # which for a multi-line sqlite error is the CARET. Then r248 took the
        # FIRST "named" line and matched on "Traceback" — which is the HEADER
        # of a Python traceback, so fifteen boxes reported
        # "Traceback (most recent call last):" and the actual exception, on
        # the LAST line, was thrown away again.
        # 🔑 THE INFORMATIVE LINE IS THE MOST SPECIFIC ONE, AND IT IS LAST IN A
        # TRACEBACK AND FIRST IN A CLI ERROR — so take the LAST line that names
        # an error, which is correct for both. "Traceback" is never a match:
        # it names no fault.
        lines = [ln.strip() for ln in (err or "").splitlines() if ln.strip()]
        named = [ln for ln in lines
                 if ("Error" in ln or "error:" in ln or "Exception" in ln)
                 and not ln.startswith("Traceback")]
        return None, (named[-1] if named else
                      (lines[-1] if lines else "ssh failed"))[:160]
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
            data, err = _query(ip, off, today_et)

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
