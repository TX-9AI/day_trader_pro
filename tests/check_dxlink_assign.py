#!/usr/bin/env python3
"""
day_trader_pro/tests/check_dxlink_assign.py  v1.1
v1.1  2026-11-07  dtp r525 / FEED.15b — THE ASSIGNMENT GOES LIVE, DELIVERED AS EACH BOX COMES UP.
  D7  run_window(): passes repeat until every running/expected box has its file; a box whose ssh is not up yet, or
      that reaches running late, is written on a later pass; a written box keeps its node and is never written twice;
      the deadline stops it with NOT WRITTEN named and rc 1; ONE outbox line; a dry run is one pass, writes nothing
  D8  the units: the timer fires Mon..Fri 09:16 America/New_York (after the 09:15 wake, dtp-morning.timer), not
      persistent; the service runs --apply --until 09:25, before OTV5 candle_feed's ASSIGN_SWITCH_BY_ET 09:27;
      systemd-analyze verify passes; the installer installs both units and enables the timer, and is not run by
      the land
  D9  main(): --until on a non-trading day writes nothing and returns 0; --until without --apply is a dry pass
v1.0  2026-11-04  dtp r523 / FEED.15 — CONTROL ASSIGNS EACH BOX ITS DXLINK NODE (tools/dxlink_assign.py).
  D1  plan(): 14 boxes over 3 up nodes - cap 5, every box assigned, no node over the cap; a box already on an up node
      keeps it; a box on a node that is not up moves; holding and unknown boxes are placed first; deterministic
  D2  plan(): no up node -> nothing; 2 nodes -> cap 7; up_nodes() reads only CONFIRMED up nodes of a FRESH status
  D3  WRITE_SCRIPT, run for real under a scratch HOME: writes ~/options-trader/data/dxlink_assign.json atomically with
      today's ET date, the symbol, an IPv4 node, written_at, by - the schema OTV5 candle_feed v5.9 read_assignment
      accepts - and reads it back (ASSIGN_WROTE ok)
  D4  READ_SCRIPT, run for real under a scratch HOME: the open-trade count from trades.db (?mode=ro); no journal -> node
      None; it prints one ASSIGN_READ line and nothing else
  D5  run(): a dry run writes nothing; --apply writes each running box once and posts ONE outbox line; a stale probe
      status is re-probed read-only; with no node up nothing is written
  D6  the module never restarts, stops or starts anything, never reads an environment and writes only that one file
"""
import ast
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)
import dxlink_assign as A  # noqa: E402

FAILS, RAN = [], []
TMP = tempfile.mkdtemp(prefix="check_dxlink_assign_")
N1, N2, N3 = "10.0.0.1", "10.0.0.2", "10.0.0.3"
SYMS = ["AMD", "AMZN", "AVGO", "CRM", "CVX", "GOOGL", "META", "NFLX", "NVDA", "QQQ", "SOFI", "SPX", "TSLA", "UNH"]


def ck(n, ok, msg):
    RAN.append(n)
    print(f"  {n:<4} {'PASS' if ok else 'FAIL'}  {msg}")
    if not ok:
        FAILS.append(n)


# ── D1 / D2 ──────────────────────────────────────────────────────────────────────────────────────────────
boxes = [{"sym": s, "open": 0, "node": N1} for s in SYMS]          # the 11-02 herd: everyone on one node
boxes[SYMS.index("SOFI")]["open"] = 2                               # holding
boxes[SYMS.index("UNH")]["open"] = None                             # unknown
boxes[SYMS.index("TSLA")]["node"] = "10.9.9.9"                      # on a node that is not up
p1, cap1 = A.plan(boxes, [N3, N1, N2])
p1b, _ = A.plan(list(reversed(boxes)), [N2, N3, N1])
load = {n: sum(1 for v in p1.values() if v == n) for n in (N1, N2, N3)}
ck("D1", cap1 == 5 and len(p1) == 14 and max(load.values()) <= 5 and sum(load.values()) == 14
   and p1["SOFI"] == N1 and p1["UNH"] == N1 and p1["TSLA"] in (N2, N3) and p1 == p1b,
   "cap=%d load=%s SOFI=%s UNH=%s TSLA=%s deterministic=%s" % (cap1, load, p1["SOFI"], p1["UNH"], p1["TSLA"],
                                                                 p1 == p1b))
p0, c0 = A.plan(boxes, [])
p2, c2 = A.plan(boxes, [N1, N2])
now = time.time()
st = {"probed_at": now - 60, "nodes": {N1: {"state": "up"}, N2: {"state": "down"}, N3: {"state": "up", "pending": "down"}}}
u1 = A.up_nodes(st, now)
u2 = A.up_nodes(dict(st, probed_at=now - A.STATUS_FRESH_S - 5), now)
ck("D2", p0 == {} and c0 == 0 and c2 == 7 and max(sum(1 for v in p2.values() if v == n) for n in (N1, N2)) == 7
   and u1 == [N1, N3] and u2 is None and A.up_nodes({}, now) is None,
   "none=%s cap2=%d up=%s stale=%s" % (p0, c2, u1, u2))

# ── D3 / D4: the box scripts, executed for real under a scratch HOME ─────────────────────────────────────
home = os.path.join(TMP, "home")
os.makedirs(os.path.join(home, "options-trader"), exist_ok=True)
env = dict(os.environ, HOME=home)


def local_ssh(ip, command, timeout=None):
    p = subprocess.run(["bash", "-c", command], capture_output=True, text=True, env=env, timeout=60)
    return p.returncode, p.stdout, p.stderr


t = time.time()
ok3 = A.write({"sym": "AMZN", "ip": "127.0.0.1"}, N2, t, ssh_run=local_ssh)
fp = os.path.join(home, A.ASSIGN_REL_PATH)
d3 = json.load(open(fp)) if os.path.exists(fp) else {}
from datetime import datetime  # noqa: E402
today = datetime.fromtimestamp(t, A.ET).strftime("%Y-%m-%d")
ck("D3", ok3 and d3.get("date") == today and d3.get("symbol") == "AMZN" and d3.get("node") == N2
   and abs(float(d3.get("written_at")) - t) < 1 and d3.get("by", "").startswith("dtp dxlink_assign")
   and not os.path.exists(fp + ".tmp"),
   "wrote=%s file=%s" % (ok3, d3))

db = os.path.join(home, "options-trader", "trades.db")
c = sqlite3.connect(db)
c.execute("CREATE TABLE trades (trade_id TEXT, status TEXT)")
c.executemany("INSERT INTO trades VALUES (?,?)", [("a", "open"), ("b", "closed")])
c.commit()
c.close()
rc, so, se = local_ssh("127.0.0.1", A._cmd(A.READ_SCRIPT))
r4 = A._tagged(so, "ASSIGN_READ")
ck("D4", rc == 0 and r4 == {"v": 1, "open": 1, "node": None} and len([l for l in so.splitlines() if l.strip()]) == 1,
   "rc=%s read=%s lines=%d" % (rc, r4, len(so.splitlines())))

# ── D5: run() ────────────────────────────────────────────────────────────────────────────────────────────
calls, posts = [], []


def fake_ssh(ip, command, timeout=None):
    calls.append(ip)
    return local_ssh(ip, command, timeout)


bx = [{"sym": "AMZN", "ip": "10.1.0.1", "open": 0, "node": N1}, {"sym": "QQQ", "ip": "10.1.0.2", "open": 0, "node": N1}]
fresh = {"probed_at": time.time() - 30, "nodes": {N1: {"state": "up"}, N2: {"state": "up"}}}
_, pd, wd = A.run(apply=False, boxes=bx, status=fresh, ssh_run=fake_ssh, enqueue=lambda m, source=None: posts.append(m))
dry_calls, dry_posts = len(calls), len(posts)
_, pa, wa = A.run(apply=True, boxes=bx, status=fresh, ssh_run=fake_ssh, enqueue=lambda m, source=None: posts.append(m))
probed = []
A.probe_now = lambda: probed.append(1) or [N2]
_, ps, _w = A.run(apply=False, boxes=bx, status={"probed_at": 1.0, "nodes": {}}, ssh_run=fake_ssh,
                  enqueue=lambda m, source=None: None)
n_before = len(calls)
_, pn, wn = A.run(apply=True, boxes=bx, nodes=[], ssh_run=fake_ssh, enqueue=lambda m, source=None: posts.append(m))
ck("D5", dry_calls == 0 and dry_posts == 0 and wd == [] and sorted(wa) == ["AMZN", "QQQ"] and len(calls) - 0 >= 2
   and len(posts) == 1 and "DXLINK ASSIGNMENT written" in posts[0] and probed == [1] and set(ps.values()) == {N2}
   and pn == {} and wn == [] and len(calls) == n_before and pa == pd,
   "dry calls=%d posts=%d; apply wrote=%s posts=%s; stale re-probed=%s -> %s; no node -> %s" % (
       dry_calls, dry_posts, wa, posts[:1], probed, ps, pn))

# ── D6: what the module can never do ─────────────────────────────────────────────────────────────────────
src = open(A.__file__, encoding="utf-8").read()
_tree = ast.parse(src)
for _n in ast.walk(_tree):                  # drop docstrings: the module's own NEVER list names the words it forbids
    if isinstance(_n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and _n.body and isinstance(_n.body[0], ast.Expr) \
            and isinstance(getattr(_n.body[0], "value", None), ast.Constant) and isinstance(_n.body[0].value.value, str):
        _n.body = _n.body[1:] or [ast.Pass()]
code = ast.unparse(_tree)
bad = [w for w in ("systemctl stop", "systemctl start", "systemctl restart", "stage_shutdown", "stage_wake",
                   "environ", "/proc/", ".env", "reboot", "os.remove", "unlink(") if w in code]
writes = [w for w in ("open(tmp, \"w\"", "open(tmp, 'w'") if w in code]
ck("D6", not bad and len(writes) == 1 and code.count("os.replace(") == 1,
   "forbidden=%s writes=%d replace=%d" % (bad, len(writes), code.count("os.replace(")))

# ── D7: run_window() ─────────────────────────────────────────────────────────────────────────────────────
class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


t0 = datetime(2026, 11, 9, 9, 16, 5, tzinfo=A.ET).timestamp()
ck7 = Clock(t0)
up = {"AMZN": 0, "QQQ": 1, "SPX": 2}          # the pass on which each box first answers ssh
writes7, posts7 = [], []


def obs7():
    p = int(round((ck7.t - t0) / 20.0))
    out = []
    for s_, k in up.items():
        if p >= k:
            out.append({"sym": s_, "ip": "10.2.0.%d" % k, "open": 0, "node": None, "read": True})
    return out


def ssh7(ip, command, timeout=None):
    writes7.append(ip)
    return local_ssh(ip, command, timeout)


rc7, done7, miss7 = A.run_window(apply=True, until="09:25", every=20, clock=ck7, sleep=ck7.sleep, observe_fn=obs7,
                                 ssh_run=ssh7, enqueue=lambda m, source=None: posts7.append(m), nodes=[N1, N2],
                                 expected=["AMZN", "QQQ", "SPX"])
ck8 = Clock(t0)
up8 = {"AMZN": 0}
posts8 = []


def obs8():
    return [{"sym": "AMZN", "ip": "10.3.0.1", "open": 0, "node": None, "read": True}]


rc8, done8, miss8 = A.run_window(apply=True, until="09:17", every=20, clock=ck8, sleep=ck8.sleep, observe_fn=obs8,
                                 ssh_run=local_ssh, enqueue=lambda m, source=None: posts8.append(m), nodes=[N1],
                                 expected=["AMZN", "GOOGL"])
# a holding box that comes up LATE sorts first; the flat box written on pass 1 must keep its node, written once
ck9 = Clock(t0)
w9 = []


def obs9():
    p = int(round((ck9.t - t0) / 20.0))
    out = [{"sym": "QQQ", "ip": "10.4.0.2", "open": 0, "node": None, "read": True}]
    if p >= 1:
        out.append({"sym": "AMZN", "ip": "10.4.0.1", "open": 1, "node": None, "read": True})
    return out


def ssh9(ip, command, timeout=None):
    w9.append(ip)
    return local_ssh(ip, command, timeout)


rc9, done9, _m9 = A.run_window(apply=True, until="09:25", every=20, clock=ck9, sleep=ck9.sleep, observe_fn=obs9,
                               ssh_run=ssh9, enqueue=lambda m, source=None: None, nodes=[N1, N2],
                               expected=["AMZN", "QQQ"])
pp, _c = A.plan([{"sym": "AMZN", "open": 1, "node": None}, {"sym": "QQQ", "open": 0, "node": None}], [N1, N2],
                pinned={"QQQ": N1})
ckd = Clock(t0)
dw = []
rcd, doned, _m = A.run_window(apply=False, until="09:25", every=20, clock=ckd, sleep=ckd.sleep, observe_fn=obs7,
                              ssh_run=lambda *a, **k: dw.append(1) or (0, "", ""), enqueue=lambda m, source=None: dw.append(m),
                              nodes=[N1], expected=["AMZN", "QQQ", "SPX"])
ck("D7", rc7 == 0 and sorted(done7) == ["AMZN", "QQQ", "SPX"] and miss7 == [] and len(writes7) == 3
   and len(set(writes7)) == 3 and len(posts7) == 1 and "written 3/3" in posts7[0]
   and rc8 == 1 and miss8 == ["GOOGL"] and len(posts8) == 1 and "NOT WRITTEN by 09:17: GOOGL" in posts8[0]
   and ck8.t <= datetime(2026, 11, 9, 9, 17, tzinfo=A.ET).timestamp()
   and rcd == 0 and doned == {} and dw == [] and ckd.t == t0
   and rc9 == 0 and done9 == {"QQQ": N1, "AMZN": N2} and sorted(w9) == ["10.4.0.1", "10.4.0.2"] and pp == {"QQQ": N1, "AMZN": N2},
   "late boxes: done=%s writes=%d posts=%s; deadline: rc=%d missing=%s; dry: done=%s calls=%d" % (
       sorted(done7), len(writes7), posts7[:1], rc8, miss8, doned, len(dw)))

# ── D8: the units ────────────────────────────────────────────────────────────────────────────────────────
TD = os.path.join(ROOT, "tools")
tmr = open(os.path.join(TD, "dtp-dxlink-assign.timer")).read()
svc = open(os.path.join(TD, "dtp-dxlink-assign.service")).read()
ins = open(os.path.join(TD, "install_dxlink_assign.sh")).read()
import re  # noqa: E402
cal = re.findall(r"^OnCalendar=(.+)$", tmr, re.M)
until = re.search(r"--until (\d\d:\d\d)", svc)
cf = os.path.expanduser("~/OTV5/data/candle_feed.py")
by = None
if os.path.exists(cf):
    mby = re.search(r"^ASSIGN_SWITCH_BY_ET = \((\d+), (\d+)\)", open(cf).read(), re.M)
    by = (int(mby.group(1)), int(mby.group(2))) if mby else None
by = by or (9, 27)
ver = subprocess.run(["systemd-analyze", "verify", os.path.join(TD, "dtp-dxlink-assign.service")],
                     capture_output=True, text=True)
ver_err = [l for l in (ver.stderr or "").splitlines() if "dtp-dxlink-assign" in l]
nxt = subprocess.run(["systemd-analyze", "calendar", "--iterations=2", cal[0] if cal else "x"],
                     capture_output=True, text=True).stdout
ck("D8", cal == ["Mon..Fri *-*-* 09:16:00 America/New_York"] and "Persistent=false" in tmr
   and "--apply" in svc and "--dry-run" not in svc and until is not None
   and tuple(int(x) for x in until.group(1).split(":")) < by
   and ver.returncode == 0 and not ver_err
   and "install -m 0644" in ins and "enable --now dtp-dxlink-assign.timer" in ins and 'id -u)" = 0' in ins
   and "Next elapse" in nxt,
   "cal=%s until=%s switch_by=%s verify=%s %s" % (cal, until.group(1) if until else None, by, ver.returncode,
                                                  ver_err[:1]))

# ── D9: main() ───────────────────────────────────────────────────────────────────────────────────────────
import market_calendar  # noqa: E402
_itd = market_calendar.is_trading_day
seen9 = []
_rw = A.run_window
A.run_window = lambda **k: seen9.append(k) or (0, {}, [])
market_calendar.is_trading_day = lambda d=None: False
r9a = A.main(["--apply", "--until", "09:25"])
market_calendar.is_trading_day = lambda d=None: True
r9b = A.main(["--until", "09:25"])
r9c = A.main(["--apply", "--until", "09:25", "--every", "15"])
market_calendar.is_trading_day = _itd
A.run_window = _rw
ck("D9", r9a == 0 and len(seen9) == 2 and seen9[0]["apply"] is False and seen9[1]["apply"] is True
   and seen9[1]["every"] == 15 and seen9[1]["until"] == "09:25",
   "holiday rc=%s calls=%s" % (r9a, [(k["apply"], k["until"], k["every"]) for k in seen9]))

print()
if FAILS:
    print(f"RED — {len(FAILS)} of {len(RAN)} check(s) failed: {' '.join(FAILS)}")
    sys.exit(1)
print(f"GREEN — {len(RAN)} checks")
