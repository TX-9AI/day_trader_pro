#!/usr/bin/env python3
"""
day_trader_pro/tools/held_contracts_page.py — v1.0
v1.0  2026-11-22  dtp r573 / HELD.1 — THE 15:35 HELD-CONTRACTS PAGE. The operator, 2026-11-21: "TT options desk allows
      me to message them to indicate my intent to manage long contracts into the close. On days where we are holding
      positions up until 1545 I'll do that part." tastytrade's risk team may close expiring positions before the bell
      on expiration day; our own close is later (PARK and OGAP 15:45, the debit ladder from 15:50, everything crosses
      15:55), so the operator messages the desk first. dtp-held-page.timer runs this at 15:35 ET Mon-Fri:
        · a holiday (market_calendar.is_trading_day) or a 13:00 half day (market_calendar.is_half_day: the r494
          half-day routing moves the whole close schedule up three hours, so a 15:35 read is after the bell) -> one
          line, rc 0, nothing read, nothing sent;
        · every RUNNING box: one bounded ssh (BOX_CMD_S on the box under `timeout`, ssh_util's connect timeout on
          top: about 20 s per box, one parallel wave) runs BOX_READ, which opens ~/options-trader/trades.db with
          `?mode=ro` and prints the open rows' contract columns. Nothing on the box is placed, cancelled, modified
          or restarted, and control never calls the broker. The legs follow OTV5 exit_engine._eod_legs (a tent's
          three legs, a vertical's two, a single's one; a butterfly's body counts two short);
        · ONE page (alert_router.post_status when the router is alive, else straight to Telegram: morning_check's
          deliver()) when any box holds an open option or any box could not be read. LIVE lines (paper_trade = 0)
          come first, then the ready-to-paste desk message built from the live legs only; paper lines follow in a
          short "paper (no message needed)" list, and a page with no live line says NO DESK MESSAGE NEEDED in its
          first line and carries no desk message. A box that does not answer is one UNREACHABLE line. Live ->
          kind "critical"; paper only / unreachable only -> "info". Nothing open and every box read -> no page;
        · the account number is never read, stored or printed: the desk message keeps the placeholder
          "[operator fills in]" exactly. Each run appends its text to ~/reviews/held_page/<date>.txt;
        · the whole run is bounded by RUN_BUDGET_S (an alarm); a run that overruns or raises pages
          "COULD NOT RUN" (never silent), and the unit's TimeoutStartSec is 120.
      No config knob, no environment read. Installed by the operator: sudo bash tools/install_held_page.sh.
      Gate: tests/check_held_page.py H1-H12.
Run:  venv/bin/python tools/held_contracts_page.py [--no-post] [--day YYYY-MM-DD]
"""
import base64
import json
import os
import signal
import sys
from datetime import date, datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

__version__ = "1.0"

REPORT_DIR = os.path.expanduser("~/reviews/held_page")
BOX_CMD_S = 8                 # on the box, under `timeout`; ssh_util adds its connect timeout (12 s): ~20 s per box
RUN_BUDGET_S = 100            # the whole run, discovery included; the unit's TimeoutStartSec is 120
MAX_PAGE = 3500               # the router's MAX_TEXT is 4000, and it prefixes its own head

DESK_MESSAGE = ("Hi, account [operator fills in]: I'm holding the following long 0DTE contracts and intend to manage "
                "them myself into the close, closing all of them by 15:55 ET: {lines}. Please don't close them on my "
                "behalf. Thank you.")
CLOSE_LINE = "Our close: PARK and OGAP 15:45, the debit ladder from 15:50, everything crosses 15:55."

COLS = ("trade_id", "symbol", "strategy", "setup_type", "option_symbol", "short_symbol", "long_symbol",
        "lower_symbol", "center_symbol", "upper_symbol", "contracts", "is_short_position", "paper_trade", "expiry")

# The one thing that runs on a box: the bot's own trades.db, read-only. Never an Environment block, never the broker.
BOX_READ = r'''
import json, os, sqlite3
p = os.path.expanduser("~/options-trader/trades.db")
o = {"db": os.path.exists(p), "rows": []}
if o["db"]:
    c = sqlite3.connect("file:" + p + "?mode=ro", uri=True, timeout=5)
    have = {r[1] for r in c.execute("PRAGMA table_info(trades)")}
    cols = [k for k in COLS if k in have]
    if "status" in have and cols:
        for r in c.execute("SELECT %s FROM trades WHERE status='open'" % ",".join(cols)):
            o["rows"].append(dict(zip(cols, r)))
    c.close()
print("HELD_STATUS " + json.dumps(o, default=str))
'''.replace("COLS", repr(COLS))


def box_command():
    b64 = base64.b64encode(BOX_READ.encode()).decode()
    return ("f=$(mktemp /tmp/held.XXXXXX) && echo %s | base64 -d > $f && timeout %d python3 $f; rc=$?; rm -f $f; "
            "exit $rc" % (b64, BOX_CMD_S))


def now_et():
    import ettime
    return ettime.now_et()


def _occ_expiry(occ):
    """YYYY-MM-DD from an OCC symbol's fixed-width tail (OTV5 broker_reconcile.parse_occ), or None."""
    core = str(occ or "").lstrip(".").rstrip()
    if len(core) < 15 or not core[-15:-9].isdigit() or core[-9:-8].upper() not in ("C", "P"):
        return None
    y = core[-15:-9]
    return "20%s-%s-%s" % (y[:2], y[2:4], y[4:6])


def legs(row):
    """[(occ, signed qty)] for one open row, after OTV5 exit_engine._eod_legs; None when no contract is recorded."""
    g = row.get
    n = int(g("contracts") or 0) or 1
    setup = str(g("setup_type") or "").lower()
    strat = str(g("strategy") or "").lower().replace("_", "")
    if setup.startswith("tent") or "tent" in strat:
        per = [(g("short_symbol"), -1), (g("long_symbol"), 1), (g("lower_symbol"), 1)]
    elif g("center_symbol"):
        per = [(g("lower_symbol"), 1), (g("center_symbol"), -2), (g("upper_symbol"), 1)]
    elif g("short_symbol") and g("long_symbol"):
        per = [(g("short_symbol"), -1), (g("long_symbol"), 1)]
    elif g("option_symbol"):
        per = [(g("option_symbol"), -1 if g("is_short_position") else 1)]
    else:
        return None
    out = [(str(s).rstrip(), q * n) for s, q in per if s]
    return out or None


def read_fleet(fleet_fn=None, map_fn=None):
    """-> {sym: {"ok": bool, "why": str, "rows": [...]}} for every RUNNING box, in fleet order."""
    if fleet_fn is None:
        import fleet
        fleet_fn = fleet.get_fleet
    if map_fn is None:
        import ssh_util
        map_fn = ssh_util.ssh_map
    running = [(s, ip) for s, ip, st in fleet_fn() if st == "running" and ip]
    res = map_fn(running, box_command(), timeout=BOX_CMD_S) if running else {}
    out = {}
    for sym, _ip in running:
        rc, so, se = res.get(sym, (255, "", "no answer"))
        st = None
        for line in (so or "").splitlines():
            if line.startswith("HELD_STATUS "):
                try:
                    st = json.loads(line[len("HELD_STATUS "):])
                except ValueError:
                    st = None
        if st is None:
            why = ((se or "").strip().splitlines() or ["rc %s" % rc])[-1][:100]
            out[sym] = {"ok": False, "why": "ssh rc %s: %s" % (rc, why), "rows": []}
        elif not st.get("db"):
            out[sym] = {"ok": False, "why": "no trades.db on the box", "rows": []}
        else:
            out[sym] = {"ok": True, "why": "", "rows": list(st.get("rows") or [])}
    return out


def build_page(day, results):
    """-> (kind, text) or (None, why-no-page). kind: critical (a live line) | info."""
    live, paper, desk, notes, bad = [], [], [], [], []
    for sym, r in results.items():
        if not r["ok"]:
            bad.append("UNREACHABLE %s (%s) - its positions are unknown, check it" % (sym, r["why"]))
            continue
        for row in r["rows"]:
            is_live = str(row.get("paper_trade")) in ("0", "False")
            strat = row.get("strategy") or "?"
            lg = legs(row)
            if lg is None:
                (live if is_live else paper).append("%s %s: open %s row %s with no contract recorded"
                                                    % ("LIVE" if is_live else "paper", sym, strat,
                                                       row.get("trade_id") or "?"))
                continue
            for occ, q in lg:
                side = "long" if q > 0 else "short"
                exp = _occ_expiry(occ)
                tail = "" if exp in (None, day) else ", expires %s, not today" % exp
                line = "%s %s: %s x%d %s (%s%s)" % ("LIVE" if is_live else "paper", sym, occ, abs(q), side, strat, tail)
                if is_live:
                    live.append(line)
                    desk.append("%d x %s" % (abs(q), occ))
                    if side == "short" or tail:
                        notes.append("NOTE: %s %s is %s - the desk message names long 0DTE contracts; edit it "
                                     "before sending" % (sym, occ, side if side == "short" else "not 0DTE"))
                else:
                    paper.append(line)
    if not (live or paper or bad):
        return None, "no open option on %d box(es) read" % len(results)
    n_live = len({l.split()[1].rstrip(":") for l in live})
    if live:
        head = ("HELD CONTRACTS 15:35 ET %s - DESK MESSAGE NEEDED (%d live box%s)"
                % (day, n_live, "" if n_live == 1 else "es"))
    elif paper:
        head = "HELD CONTRACTS 15:35 ET %s - paper only, NO DESK MESSAGE NEEDED" % day
    else:
        head = "HELD CONTRACTS 15:35 ET %s - no open option on the boxes read, but a box did not answer" % day
    out = [head]
    if live:
        out += live
        if desk:
            out += ["Desk message (paste to the tastytrade options desk):", DESK_MESSAGE.format(lines="; ".join(desk))]
        out += notes
    if paper:
        out += ["paper (no message needed):"] + ["  " + l[len("paper "):] for l in paper]
    out += bad
    out.append(CLOSE_LINE)
    text = "\n".join(out)
    if len(text) > MAX_PAGE:
        text = text[:MAX_PAGE - 40] + "\n... (cut; full text in ~/reviews/held_page)"
    return ("critical" if live else "info"), text


def write_report(day, text, report_dir=None):
    d = report_dir or REPORT_DIR
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "%s.txt" % day)
    with open(p, "a") as fh:
        fh.write("%s\n%s\n\n" % (datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), text))
    return p


class _Overrun(Exception):
    pass


def _alarm(_sig, _frm):
    raise _Overrun("the run passed its %d s budget" % RUN_BUDGET_S)


def main(argv=None, fleet_fn=None, map_fn=None, deliver_fn=None, trading_fn=None, half_fn=None, report_dir=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    day = argv[argv.index("--day") + 1] if "--day" in argv else now_et().strftime("%Y-%m-%d")
    d = date.fromisoformat(day)
    if trading_fn is None or half_fn is None:
        import market_calendar
        trading_fn = trading_fn or market_calendar.is_trading_day
        half_fn = half_fn or market_calendar.is_half_day
    if not trading_fn(d):
        print("HELD PAGE: %s is not a trading day - nothing read" % day)
        return 0
    if half_fn(d):
        print("HELD PAGE: %s is a 13:00 half day - the close is long past at 15:35, nothing read" % day)
        return 0
    if deliver_fn is None:
        import morning_check
        deliver_fn = morning_check.deliver
    old = signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(RUN_BUDGET_S)
    failed = False
    try:
        results = read_fleet(fleet_fn, map_fn)
        kind, text = build_page(day, results)
    except Exception as exc:                                                # noqa: BLE001  (_Overrun included)
        kind, text, failed = "critical", ("HELD CONTRACTS 15:35 ET %s: COULD NOT RUN - %s: %s. Check the boxes "
                                          "holding positions by hand before 15:45." % (day, type(exc).__name__,
                                                                                         str(exc)[:160])), True
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)
    if kind is None:
        print("HELD PAGE %s: %s - no page" % (day, text))
        return 0
    try:
        write_report(day, text, report_dir)
    except OSError as exc:
        print("  note  report not written: %s" % exc)
    print(text)
    if "--no-post" not in argv:
        print("  sent via %s (%s)" % (deliver_fn(kind, text), kind))
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
