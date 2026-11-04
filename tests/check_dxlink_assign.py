#!/usr/bin/env python3
"""
day_trader_pro/tests/check_dxlink_assign.py  v1.0
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

print()
if FAILS:
    print(f"RED — {len(FAILS)} of {len(RAN)} check(s) failed: {' '.join(FAILS)}")
    sys.exit(1)
print(f"GREEN — {len(RAN)} checks")
