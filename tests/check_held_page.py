#!/usr/bin/env python3
"""
day_trader_pro/tests/check_held_page.py — v1.0
v1.0  2026-11-22  dtp r573 / HELD.1 — THE 15:35 HELD-CONTRACTS PAGE (tools/held_contracts_page.py v1.0; the operator,
      2026-11-21: "TT options desk allows me to message them to indicate my intent to manage long contracts into the
      close. On days where we are holding positions up until 1545 I'll do that part.").
No box, no Telegram: the fleet, ssh, delivery and calendar are fakes, except H9, which runs the REAL box command
through bash on this host against a throwaway trades.db (HOME pointed at a temp dir), and H3, which uses the real
market_calendar.
  H1   the units: Mon..Fri 15:35 America/New_York, not Persistent; the service runs this tool as ubuntu with
       TimeoutStartSec <= 120; the installer installs both units, parses, and says the land does not run it
  H2   a holiday (2026-11-26): rc 0, no fleet read, nothing sent
  H3   a 13:00 half day (2026-11-27, the real market_calendar): rc 0, no fleet read, nothing sent
  H4   every box read and nothing open: no page
  H5   live + paper + unreachable: ONE page, kind critical; the LIVE lines come before the desk message, the paper
       list and the UNREACHABLE line; the paper list carries no desk line
  H6   paper only: kind info, the first line says NO DESK MESSAGE NEEDED, no desk message
  H7   a box that does not answer and nothing open elsewhere: still a page, the box named UNREACHABLE (never silence)
  H8   the desk message is the operator's text exactly, with the live contract lines filled in and the account
       placeholder "[operator fills in]" kept; nothing reads an account number (no account column, no env read)
  H9   the real box command under bash on a fixture trades.db: one parseable HELD_STATUS with the open rows only;
       the db (made read-only) is byte-identical after; ?mode=ro; no sudo / systemctl / broker in the command
  H10  legs: a single, a short single, a vertical, a tent and a butterfly body, quantities times contracts; a live
       short leg or a non-0DTE expiry adds an edit-before-sending NOTE
  H11  bounds: one ssh wave, ~20 s a box (BOX_CMD_S + the connect timeout), the run budget under the unit's 120 s;
       a run that overruns its budget pages COULD NOT RUN (critical, rc 2)
  H12  delivery: through morning_check.deliver - router alive -> the router's outbox; router dead -> straight to Telegram
"""
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOLS = os.path.join(ROOT, "tools")
sys.path.insert(0, TOOLS)
sys.path.insert(0, ROOT)
FAILS, RAN = [], []


def ck(n, ok, msg):
    RAN.append(n)
    print(f"  {n:<4} {'PASS' if ok else 'FAIL'}  {msg}")
    if not ok:
        FAILS.append(n)


print("check_held_page")
try:
    import held_contracts_page as H
except Exception as e:                                                     # noqa: BLE001
    H = None
    print(f"  (tools/held_contracts_page.py does not import: {type(e).__name__}: {e})")

IDS = ["H%d" % i for i in range(1, 13)]
if H is None:
    for n in IDS:
        ck(n, False, "tools/held_contracts_page.py is missing")
    print(f"\nFAILED: {', '.join(FAILS)}")
    sys.exit(1)

DAY = "2026-11-24"                     # a Tuesday, a full session
OPERATOR_TEXT = ("Hi, account [operator fills in]: I'm holding the following long 0DTE contracts and intend to manage "
                 "them myself into the close, closing all of them by 15:55 ET: {lines}. Please don't close them on my "
                 "behalf. Thank you.")


def row(**k):
    base = {"trade_id": "t", "symbol": "QQQ", "strategy": "PARK", "contracts": 1, "is_short_position": 0,
            "paper_trade": 1}
    base.update(k)
    return base


FLEET = [("QQQ", "10.0.0.1", "running"), ("SPY", "10.0.0.2", "running"), ("AMD", "10.0.0.3", "running"),
         ("NVDA", "10.0.0.4", "running"), ("TSLA", "10.0.0.5", "stopped")]


def fake_map(per_box):
    calls = []

    def m(targets, command, timeout=None):
        calls.append((list(targets), command, timeout))
        out = {}
        for sym, _ip in targets:
            v = per_box.get(sym, {"db": True, "rows": []})
            out[sym] = (255, "", "ssh: connect to host port 22: Connection timed out") if v is None else \
                (0, "HELD_STATUS " + json.dumps(v) + "\n", "")
        return out
    m.calls = calls
    return m


def run(per_box, day=DAY, trading=True, half=False, fleet=None, **kw):
    sent, read = [], []
    m = fake_map(per_box)

    def fl():
        read.append(1)
        return list(fleet or FLEET)
    rd = tempfile.mkdtemp(prefix="ckheld_")
    rc = H.main(["--day", day], fleet_fn=fl, map_fn=m, deliver_fn=lambda k, t: (sent.append((k, t)), "router")[1],
                trading_fn=(lambda d: trading) if not isinstance(trading, type(run)) else trading,
                half_fn=(lambda d: half) if not isinstance(half, type(run)) else half, report_dir=rd, **kw)
    return rc, sent, read, m, rd


# H1 units + installer
tm = open(os.path.join(TOOLS, "dtp-held-page.timer")).read() if os.path.exists(os.path.join(TOOLS, "dtp-held-page.timer")) else ""
sv = open(os.path.join(TOOLS, "dtp-held-page.service")).read() if os.path.exists(os.path.join(TOOLS, "dtp-held-page.service")) else ""
ins_p = os.path.join(TOOLS, "install_held_page.sh")
ins = open(ins_p).read() if os.path.exists(ins_p) else ""
_to = re.search(r"TimeoutStartSec=(\d+)", sv)
_bn = subprocess.run(["bash", "-n", ins_p], capture_output=True).returncode if ins else 1
ck("H1", "OnCalendar=Mon..Fri *-*-* 15:35:00 America/New_York" in tm and "Persistent=false" in tm
   and "tools/held_contracts_page.py" in sv and "User=ubuntu" in sv and "Type=oneshot" in sv
   and _to is not None and int(_to.group(1)) <= 120 and "Environment=" not in sv
   and "dtp-held-page.service" in ins and "dtp-held-page.timer" in ins and "systemctl enable --now dtp-held-page.timer" in ins
   and "NOT RUN BY THE LAND" in ins and _bn == 0,
   f"timer Mon..Fri 15:35 ET, not Persistent; service oneshot as ubuntu, timeout {_to.group(1) if _to else '?'} s; "
   f"installer parses (bash -n rc {_bn})")

# H2 holiday / H3 half day
rc, sent, read, m, _ = run({}, day="2026-11-26", trading=False)
ck("H2", rc == 0 and not sent and not read and not m.calls, "a holiday: rc 0, no fleet read, no ssh, nothing sent")
import market_calendar  # noqa: E402
rc, sent, read, m, _ = run({}, day="2026-11-27", trading=market_calendar.is_trading_day, half=market_calendar.is_half_day)
rc2, sent2, read2, m2, _ = run({"QQQ": {"db": True, "rows": [row(option_symbol="QQQ   261124C00505000")]}},
                                day=DAY, trading=market_calendar.is_trading_day, half=market_calendar.is_half_day)
ck("H3", rc == 0 and not sent and not read and not m.calls and market_calendar.is_trading_day(
    __import__("datetime").date(2026, 11, 27)) and read2 and sent2,
   "2026-11-27 (13:00 close, a trading day): nothing read, nothing sent; 2026-11-24 (full day) reads and pages")

# H4 nothing open
rc, sent, read, m, rd = run({})
ck("H4", rc == 0 and not sent and read and len(m.calls) == 1 and [t[0] for t in m.calls[0][0]] == ["QQQ", "SPY", "AMD", "NVDA"],
   "every running box read (the stopped one is not ssh'd), nothing open: no page")

# H5 live + paper + unreachable
LIVE_OCC, PAPER_OCC = "QQQ   261124C00505000", "SPY   261124P00580000"
per = {"QQQ": {"db": True, "rows": [row(trade_id="a1", option_symbol=LIVE_OCC, contracts=2, paper_trade=0)]},
       "SPY": {"db": True, "rows": [row(trade_id="b1", symbol="SPY", strategy="OGAP", option_symbol=PAPER_OCC)]},
       "AMD": None}
rc, sent, read, m, rd = run(per)
k, t = sent[0] if sent else (None, "")
L = t.splitlines()
_i = lambda pfx: next((i for i, l in enumerate(L) if l.startswith(pfx)), 99)
ck("H5", rc == 0 and len(sent) == 1 and k == "critical" and "DESK MESSAGE NEEDED (1 live box)" in L[0]
   and _i("LIVE QQQ:") == 1 and _i("LIVE QQQ:") < _i("Desk message") < _i("Hi, account") < _i("paper (no message needed):")
   < _i("UNREACHABLE AMD") and "  SPY: " + PAPER_OCC + " x1 long (OGAP)" in L
   and t.count("Hi, account") == 1 and PAPER_OCC not in L[_i("Hi, account")]
   and os.path.exists(os.path.join(rd, DAY + ".txt")),
   "ONE critical page: LIVE line first, then the desk message, then the paper list, then UNREACHABLE; report kept")
print("\n".join("        | " + l for l in L))

# H6 paper only
rc, sent, read, m, _ = run({"SPY": per["SPY"]})
k, t = sent[0] if sent else (None, "")
ck("H6", len(sent) == 1 and k == "info" and t.splitlines()[0].endswith("paper only, NO DESK MESSAGE NEEDED")
   and "Hi, account" not in t and "paper (no message needed):" in t,
   "paper only: info, NO DESK MESSAGE NEEDED in the first line, no desk message")

# H7 unreachable only
rc, sent, read, m, _ = run({"AMD": None, "NVDA": {"db": False, "rows": []}})
k, t = sent[0] if sent else (None, "")
ck("H7", len(sent) == 1 and "UNREACHABLE AMD" in t and "UNREACHABLE NVDA (no trades.db on the box)" in t
   and "Hi, account" not in t and k == "info",
   "a box that does not answer (or has no trades.db) is named UNREACHABLE: never silence")

# H8 the operator's text exactly
rc, sent, read, m, _ = run({"QQQ": {"db": True, "rows": [
    row(trade_id="a1", option_symbol=LIVE_OCC, contracts=2, paper_trade=0),
    row(trade_id="a2", option_symbol="QQQ   261124P00495000", contracts=1, paper_trade=0)]}})
t = sent[0][1] if sent else ""
_want = OPERATOR_TEXT.format(lines="2 x %s; 1 x QQQ   261124P00495000" % LIVE_OCC)
_src = open(H.__file__).read()
ck("H8", _want in t.splitlines() and "[operator fills in]" in t
   and not re.search(r"account_(number|id)|OT_ACCOUNT|TT_ACCOUNT|os\.environ|getenv", _src)
   and not any("account" in c for c in H.COLS),
   "the desk message is the operator's text exactly, live lines filled, the placeholder kept; no account read")

# H9 the real box command
_home = tempfile.mkdtemp(prefix="ckheld_home_")
os.makedirs(os.path.join(_home, "options-trader"))
_db = os.path.join(_home, "options-trader", "trades.db")
c = sqlite3.connect(_db)
c.execute("CREATE TABLE trades (trade_id TEXT, symbol TEXT, strategy TEXT, option_symbol TEXT, contracts INTEGER, "
          "is_short_position INTEGER, paper_trade INTEGER, status TEXT, notes TEXT)")
c.execute("INSERT INTO trades VALUES ('o1','QQQ','PARK','QQQ   261124C00505000',2,0,1,'open','n')")
c.execute("INSERT INTO trades VALUES ('c1','QQQ','PARK','QQQ   261124C00500000',1,0,1,'closed','n')")
c.commit()
c.close()
os.chmod(_db, 0o444)
os.chmod(os.path.dirname(_db), 0o555)
_sha = hashlib.sha256(open(_db, "rb").read()).hexdigest()
_cmd = H.box_command()
p = subprocess.run(["bash", "-c", _cmd], capture_output=True, text=True, env=dict(os.environ, HOME=_home), timeout=30)
_st = None
for ln in p.stdout.splitlines():
    if ln.startswith("HELD_STATUS "):
        _st = json.loads(ln[12:])
_after = hashlib.sha256(open(_db, "rb").read()).hexdigest()
os.chmod(os.path.dirname(_db), 0o755)
ck("H9", p.returncode == 0 and _st is not None and [r["trade_id"] for r in _st["rows"]] == ["o1"]
   and "notes" not in _st["rows"][0] and _sha == _after and "?mode=ro" in H.BOX_READ
   and not re.search(r"sudo|systemctl|tastytrade|INSERT|UPDATE|DELETE", H.BOX_READ) and "timeout %d python3" % H.BOX_CMD_S in _cmd,
   f"the real command on a read-only fixture db: rc {p.returncode}, rows {[r['trade_id'] for r in (_st or {}).get('rows', [])]}, "
   f"db unchanged {_sha == _after}; {p.stderr.strip()[:80]}")

# H10 legs
lg = H.legs
_tent = lg(row(setup_type="tent_hedge", short_symbol="S", long_symbol="L", lower_symbol="W", contracts=2))
rc, sent, read, m, _ = run({"QQQ": {"db": True, "rows": [
    row(trade_id="s1", option_symbol="QQQ   261124C00510000", is_short_position=1, paper_trade=0),
    row(trade_id="s2", option_symbol="QQQ   261127C00510000", paper_trade=0)]}})
t = sent[0][1] if sent else ""
ck("H10", lg(row(option_symbol="X", contracts=3)) == [("X", 3)] and lg(row(option_symbol="X", is_short_position=1)) == [("X", -1)]
   and lg(row(short_symbol="S", long_symbol="L", contracts=2)) == [("S", -2), ("L", 2)]
   and _tent == [("S", -2), ("L", 2), ("W", 2)]
   and lg(row(lower_symbol="A", center_symbol="B", upper_symbol="C")) == [("A", 1), ("B", -2), ("C", 1)]
   and lg(row()) is None and "x1 short" in t and "NOTE: QQQ QQQ   261124C00510000 is short" in t
   and "expires 2026-11-27, not today" in t and "is not 0DTE" in t,
   "single, short single, vertical, tent, butterfly body; a live short leg or a non-0DTE leg adds a NOTE")

# H11 bounds
import config  # noqa: E402
rc, sent, read, m, _ = run({})
_svto = int(_to.group(1)) if _to else 999


def slow_map(targets, command, timeout=None):
    time.sleep(3)
    return {}


_b = H.RUN_BUDGET_S
H.RUN_BUDGET_S = 1
sent2 = []
rc2 = H.main(["--day", DAY], fleet_fn=lambda: FLEET, map_fn=slow_map, deliver_fn=lambda k, t: (sent2.append((k, t)), "router")[1],
             trading_fn=lambda d: True, half_fn=lambda d: False, report_dir=tempfile.mkdtemp(prefix="ckheld_"))
H.RUN_BUDGET_S = _b
ck("H11", len(m.calls) == 1 and m.calls[0][2] == H.BOX_CMD_S and H.BOX_CMD_S + config.SSH_CONNECT_TIMEOUT <= 20
   and H.RUN_BUDGET_S + 10 <= _svto <= 120 and rc2 == 2 and sent2 and sent2[0][0] == "critical"
   and "COULD NOT RUN" in sent2[0][1],
   f"one ssh wave at {H.BOX_CMD_S}+{config.SSH_CONNECT_TIMEOUT} s a box; budget {H.RUN_BUDGET_S} s < unit {_svto} s; "
   f"an overrun pages COULD NOT RUN (rc {rc2})")

# H12 delivery
import morning_check as M  # noqa: E402
_posted, _direct = [], []
r1 = M.deliver("critical", "x", post_fn=lambda k, t: _posted.append((k, t)), alive_fn=lambda: True,
               send_fn=lambda t: _direct.append(t))
r2 = M.deliver("info", "y", post_fn=lambda k, t: _posted.append((k, t)), alive_fn=lambda: False,
               send_fn=lambda t: _direct.append(t))
ck("H12", "morning_check.deliver" in _src and r1 == "router" and r2 == "direct" and _posted == [("critical", "x")]
   and len(_direct) == 1 and _direct[0].startswith("y"),
   "the page goes through morning_check.deliver: the router when alive, straight to Telegram when not")

print()
if FAILS:
    print(f"FAILED: {', '.join(FAILS)}")
    sys.exit(1)
print(f"ALL PASS ({len(RAN)})")
