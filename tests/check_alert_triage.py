#!/usr/bin/env python3
"""
day_trader_pro/tests/check_alert_triage.py  v1.0
v1.0  2026-11-08  dtp r540 / ROUTE.1 — control triages each alert by event type as it arrives (alert_triage.py v1.0,
      alert_router.py v0.4.0). No box, no Telegram, no EC2: fake clock, fake ssh, fake status poster.
  T1   classify(): every box code maps to its event type; BLIND with positions, BLIND refused by the session limit,
       disk and critical words are told apart
  T2   feed(): UP / DN in the 09:15 wake and the close -> digest; critical / disk / blind-with-positions -> now
  T3   on_event() writes one inbox line per event (type, feed, action, notify) and Claude's lines carry notify
  T4   a flat box still BLIND after the grace: flat proven by a read-only trades.db read, "working" posted, the feed
       restarted, the inbox says done
  T5   a box that heals itself inside the grace (SIGHT) is not touched
  T6   a box the fresh read finds holding is not touched (inbox notify); an unreadable box is "could not prove flat"
       - critical, untouched; the router's own open count stops the plan before any ssh
  T7   the kill-switch file: the event is still written, nothing is planned
  T8   one action per box per cooldown; the daily limit; both say so to the operator (critical) and the inbox
  T9   more than FLEET_BLIND_MAX boxes blind = a feed-side outage: no restart
  T10  START_BOT only for an unexpected DN in RTH outside the wake / close (a requested stop, 16:05, 08:00: none)
  T11  PURGE only outside RTH; a disk alert in RTH is the operator's
  T12  a failed action is critical and notify
  T14  the REAL flat-check command, run through bash against a throwaway trades.db: OPEN 0, then OPEN 1
  T13  the router: a wake-window UP wave is ONE message after DIGEST_HOLD_S (none at 30 s); a routed alert of a
       critical type goes out at once, ungrouped; a triage that raises costs no alert its delivery; a replay is not
       triaged; run() builds the triage only when it is not a dry run
"""
import json
import os
import sys
import tempfile
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import alert_triage as T  # noqa: E402
import alert_router as ar  # noqa: E402

FAILS, RAN = [], []
TMP = tempfile.mkdtemp(prefix="check_alert_triage_")


def ck(n, ok, msg=""):
    RAN.append(n)
    print(f"  {n:<4} {'PASS' if ok else 'FAIL'}  {msg}")
    if not ok:
        FAILS.append(n)


def at(h, m, day=9):
    return datetime(2026, 11, day, h, m, tzinfo=T.ET).timestamp()


class Clock:
    def __init__(self, t):
        self.t = t
        self.hooks = []                      # (when, fn)

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += max(s, 0.5)
        for when, fn in list(self.hooks):
            if self.t >= when:
                self.hooks.remove((when, fn))
                fn()


def mk(t0, ssh_out=None, open_n=None, sd=None):
    clk = Clock(t0)
    posts, cmds = [], []
    sd = sd or tempfile.mkdtemp(dir=TMP)

    def ssh(ip, cmd, timeout=None):
        cmds.append(cmd)
        if cmd == T.FLAT_CMD:
            return ssh_out.get("flat", (0, "OPEN 0\n", "")) if ssh_out else (0, "OPEN 0\n", "")
        return ssh_out.get("act", (0, "active\n", "")) if ssh_out else (0, "active\n", "")
    tr = T.Triage(post_status=lambda k, t, boxes=(), cause="": posts.append((k, t)), ip_of=lambda b: "10.0.0.1",
                  ssh=ssh, state_dir=sd, clock=clk, sleep=clk.sleep, open_n=open_n, start=False)
    return tr, clk, posts, cmds, sd


def inbox(sd):
    rows = []
    d = os.path.join(sd, "inbox")
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        rows += [json.loads(x) for x in open(os.path.join(d, f))]
    return rows


def rec(code, text="", **kw):
    r = {"id": kw.pop("id", "a.%s" % code), "code": code, "text": text, "via": kw.pop("via", "control"), "ts": 0}
    r.update(kw)
    return r


# T1
cases = [(rec("HCF", "x"), "CRITICAL"), (rec("MSG", "KILL SWITCH engaged"), "CRITICAL"),
         (rec("BLD", "BOT IS BLIND", open=1), "BLIND_OPEN"), (rec("BLD", "BOT IS BLIND", open=0), "BLIND"),
         (rec("BLD", "BOT IS BLIND", cause="SESSION_LIMIT on dxlink"), "REFUSED"), (rec("DSK", "DISK 94%"), "DISK"),
         (rec("SEE", "Sight restored"), "SIGHT"), (rec("DN", "OptionsBot STOPPED"), "BOT_DOWN"),
         (rec("UP", "STARTED"), "BOT_UP"), (rec("ENT", "entered"), "TRADE"), (rec("SUM", "summary"), "SUMMARY"),
         (rec("MSG", "something new"), "OTHER")]
got = [(T.classify(r), want) for r, want in cases]
ck("T1", all(g == w for g, w in got) and set(T.POLICY) == {w for _r, w in cases},
   "mismatches %s" % [(g, w) for g, w in got if g != w])

# T2
tr, clk, *_ = mk(at(9, 16))
f_wake = tr.feed(rec("UP", "STARTED"))
f_mid = tr.feed(rec("UP", "STARTED"), now=at(11, 0))
f_close = tr.feed(rec("DN", "STOPPED"), now=at(16, 5))
f_now = [tr.feed(rec(c, t, open=1)) for c, t in (("HCF", ""), ("DSK", "DISK 93%"), ("BLD", "BLIND"))]
ck("T2", f_wake == "digest" and f_mid == "group" and f_close == "digest" and f_now == ["now"] * 3,
   "%s %s %s %s" % (f_wake, f_mid, f_close, f_now))

# T3
tr, clk, posts, cmds, sd = mk(at(11, 0))
tr.on_event("AMD", rec("HCF", "HARD CLOSE INCOMPLETE"))
tr.on_event("AMD", rec("ENT", "entered", id="a.2"))
rows = inbox(sd)
ck("T3", len(rows) == 2 and rows[0]["type"] == "CRITICAL" and rows[0]["notify"] is True and rows[0]["feed"] == "now"
   and rows[1]["type"] == "TRADE" and rows[1]["notify"] is False and rows[1]["action"] is None and cmds == [],
   "%r" % rows)

# T4
tr, clk, posts, cmds, sd = mk(at(11, 0))
typ, feed, plan = tr.on_event("AMD", rec("BLD", "BOT IS BLIND", open=0, cause="BARS_STALE"))
item = tr.q.get_nowait()
res = tr.act(*item)
rows = inbox(sd)
ck("T4", plan == "RESTART_FEED" and res == "done" and cmds == [T.FLAT_CMD, T.ACTION_CMD["RESTART_FEED"]]
   and posts and posts[0][0] == "working" and "restart feed on AMD" in posts[0][1]
   and clk.t - at(11, 0) >= T.BLIND_GRACE_S and rows[-1]["result"] == "done", "res %s cmds %s posts %s" % (res, cmds, posts))

# T5
tr, clk, posts, cmds, sd = mk(at(11, 0))
tr.on_event("AMD", rec("BLD", "BOT IS BLIND", open=0))
item = tr.q.get_nowait()
clk.hooks.append((at(11, 0) + 30, lambda: tr.on_event("AMD", rec("SEE", "Sight restored", id="a.see"))))
res = tr.act(*item)
ck("T5", res == "healed" and clk.t < at(11, 0) + T.BLIND_GRACE_S and cmds == [] and posts == [] and inbox(sd)[-1]["result"].startswith("not needed"),
   "res %s cmds %s" % (res, cmds))

# T6
tr, clk, posts, cmds, sd = mk(at(11, 0), ssh_out={"flat": (0, "OPEN 2\n", "")})
tr.on_event("AMD", rec("BLD", "BOT IS BLIND", open=0))
res_h = tr.act(*tr.q.get_nowait())
row_h = inbox(sd)[-1]
tr2, clk2, posts2, cmds2, sd2 = mk(at(11, 0), ssh_out={"flat": (255, "", "ssh timeout")})
tr2.on_event("AMD", rec("BLD", "BOT IS BLIND", open=0))
res_u = tr2.act(*tr2.q.get_nowait())
tr4, _c4, _p4, cmds4, _sd4 = mk(at(11, 0), ssh_out={"flat": (1, "OPEN 0\n", "sqlite3.OperationalError")})
tr4.on_event("AMD", rec("BLD", "BOT IS BLIND", open=0))
res_e = tr4.act(*tr4.q.get_nowait())
tr3, _c3, _p3, cmds3, _sd3 = mk(at(11, 0), open_n=lambda b: 1)
_t, _f, plan3 = tr3.on_event("AMD", rec("BLD", "BOT IS BLIND", open=0))
ck("T6", res_h == "holding" and cmds == [T.FLAT_CMD] and row_h["notify"] is True and "2 open" in row_h["result"]
   and res_u == "failed" and cmds2 == [T.FLAT_CMD] and posts2 and posts2[-1][0] == "critical"
   and "could not prove the box flat" in posts2[-1][1] and res_e == "failed" and cmds4 == [T.FLAT_CMD]
   and plan3 is None and cmds3 == [] and tr3.q.empty(),
   "%s %s %s / %s %s / %s" % (res_h, cmds, row_h, res_u, posts2, plan3))

# T7
tr, clk, posts, cmds, sd = mk(at(11, 0))
open(os.path.join(sd, T.KILL_FILE), "w").close()
_t, _f, plan = tr.on_event("AMD", rec("BLD", "BOT IS BLIND", open=0))
ck("T7", plan is None and tr.q.empty() and len(inbox(sd)) == 1, "plan %s" % plan)

# T8
tr, clk, posts, cmds, sd = mk(at(11, 0))
tr.on_event("AMD", rec("BLD", "BOT IS BLIND", open=0))
r1 = tr.act(*tr.q.get_nowait())
tr.on_event("AMD", rec("BLD", "BOT IS BLIND", open=0, id="a.b2"))
r2 = tr.act(*tr.q.get_nowait())
lim_post = posts[-1]
for k in range(3):                                         # past the cooldown each time: 2 more, then the day's limit
    clk.t += T.ACTION_COOLDOWN_S + 1
    tr.on_event("AMD", rec("BLD", "BOT IS BLIND", open=0, id="a.c%d" % k))
    last = tr.act(*tr.q.get_nowait())
ck("T8", r1 == "done" and r2 == "limited" and lim_post[0] == "critical" and "cooldown" in lim_post[1]
   and last == "limited" and "daily limit" in posts[-1][1] and inbox(sd)[-1]["notify"] is True,
   "%s %s %s %s" % (r1, r2, last, posts[-1]))

# T9
tr, clk, posts, cmds, sd = mk(at(11, 0))
for b in ("AMD", "AVGO", "CRM", "CVX"):
    _t, _f, plan = tr.on_event(b, rec("BLD", "BOT IS BLIND", open=0, id="x." + b))
queued = tr.q.qsize()
ck("T9", plan is None and queued == T.FLEET_BLIND_MAX and cmds == [], "plan %s queued %d" % (plan, queued))

# T10
plans = []
for when, cause in ((at(11, 0), ""), (at(11, 0), "shutdown requested"), (at(16, 5), ""), (at(8, 0), ""),
                    (at(9, 20), "")):
    tr, *_ = mk(when)
    plans.append(tr.on_event("AMD", rec("DN", "OptionsBot STOPPED", cause=cause))[2])
ck("T10", plans == ["START_BOT", None, None, None, None], "%s" % plans)

# T11
tr, *_ = mk(at(17, 30))
p_after = tr.on_event("AMD", rec("DSK", "DISK 94%"))[2]
tr, *_ = mk(at(11, 0))
p_rth = tr.on_event("AMD", rec("DSK", "DISK 94%"))[2]
ck("T11", p_after == "PURGE" and p_rth is None, "%s %s" % (p_after, p_rth))

# T12
tr, clk, posts, cmds, sd = mk(at(11, 0), ssh_out={"act": (1, "failed\n", "")})
tr.on_event("AMD", rec("DN", "OptionsBot STOPPED"))
res = tr.act(*tr.q.get_nowait())
ck("T12", res == "failed" and posts[-1][0] == "critical" and inbox(sd)[-1]["notify"] is True
   and inbox(sd)[-1]["result"].startswith("FAILED"), "%s %s" % (res, posts))


# T13 — the router
class Post:
    def __init__(self):
        self.sent = []

    def __call__(self, text):
        self.sent.append((CLK.t, text))
        return "ok", None, ""


CLK = Clock(at(9, 16))
p = Post()
tr, _c, _p, _cm, sd = mk(at(9, 16))
tr.clock = CLK
r = ar.Router(p, state_dir=os.path.join(TMP, "r13"), clock=CLK, spool=False, triage=tr, log=lambda m: None)
for i, b in enumerate(("AMD", "AVGO", "CRM")):
    r.tick()
    r.ingest_alert(b, rec("UP", "🚀 %s STARTED" % b, id="u%d" % i, ts=CLK.t))
    for _ in range(4):
        CLK.t += 5
        r.tick()
n30 = len(p.sent)                                          # 60 s in: a plain group would have gone at 20 s
while CLK.t < at(9, 16) + ar.DIGEST_HOLD_S + 10:
    CLK.t += 5
    r.tick()
wave = [t for _ts, t in p.sent]
CLK.t = at(11, 0)
r.tick()
r.ingest_alert("NVDA", rec("MSG", "EMERGENCY flatten failed", id="m1", ts=CLK.t))
r.tick()
crit_at_once = any("EMERGENCY flatten failed" in t for _ts, t in p.sent[len(wave):])


class Boom:
    def on_event(self, *a):
        raise RuntimeError("boom")


p2 = Post()
CLK.t = at(11, 0)
r2 = ar.Router(p2, state_dir=os.path.join(TMP, "r13b"), clock=CLK, spool=False, triage=Boom(), log=lambda m: None)
r2.tick()
took = r2.ingest_alert("AMD", rec("ENT", "entered AMD", id="e1", ts=CLK.t))
for _ in range(5):
    r2.tick()
    CLK.t += 2
seen = []
r3 = ar.Router(Post(), state_dir=os.path.join(TMP, "r13c"), clock=CLK, spool=False,
               triage=type("S", (), {"on_event": lambda self, b, x: seen.append(b) or ("OTHER", "group", None)})(),
               log=lambda m: None)
r3.ingest_alert("AMD", rec("ENT", "x", id="z1", ts=CLK.t), replay=True)
import inspect  # noqa: E402
src = inspect.getsource(ar.run)
ck("T13", n30 == 0 and len(wave) == 1 and all(b in wave[0] for b in ("AMD", "AVGO", "CRM")) and crit_at_once
   and took is True and any("entered AMD" in t for _ts, t in p2.sent) and seen == []
   and "if not dry_run:" in src and "alert_triage.Triage(" in src,
   "n30 %d wave %r crit %s took %s seen %s" % (n30, wave, crit_at_once, took, seen))

# T14 — the real command line
import sqlite3  # noqa: E402
import subprocess  # noqa: E402
home = os.path.join(TMP, "home")
os.makedirs(os.path.join(home, "options-trader"))
db = os.path.join(home, "options-trader", "trades.db")
c = sqlite3.connect(db)
c.execute("CREATE TABLE trades (trade_id TEXT, status TEXT)")
c.execute("INSERT INTO trades VALUES ('t1', 'closed')")
c.commit()
o0 = subprocess.run(["bash", "-c", T.FLAT_CMD], capture_output=True, text=True, env=dict(os.environ, HOME=home)).stdout
c.execute("INSERT INTO trades VALUES ('t2', 'open')")
c.commit()
c.close()
o1 = subprocess.run(["bash", "-c", T.FLAT_CMD], capture_output=True, text=True, env=dict(os.environ, HOME=home)).stdout
ck("T14", o0.strip() == "OPEN 0" and o1.strip() == "OPEN 1", "%r %r" % (o0, o1))

print()
if FAILS:
    print("RED — %s" % ", ".join(FAILS))
    sys.exit(1)
print("GREEN — %d checks" % len(RAN))
