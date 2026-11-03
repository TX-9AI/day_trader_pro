#!/usr/bin/env python3
"""
day_trader_pro/tests/check_feed_triage.py  v1.1
v1.1  2026-11-03  dtp r521 / FEED.14 — the operator's rulings ("Yes to the proposal"):
  T3  (changed) the demotion is by H4P only: T1/T1P reject SPX in the fixture too, and only H4P's rejection counts
  T18 R1: a theory other than H4P that excludes a symbol demotes nothing; a theories file without H4P demotes none
  T19 R2: ev_rank = ev x min(n, 20) / 20; a 2-trade +$200 symbol ranks BELOW a 25-trade +$30 one; 20+ trades unshrunk
  T20 R4: at 15:45 ET every box the tool stood down (stopped, incl. one past MAX_FAILED_RETURNS) is started in one
      pass, a stopped box it did NOT stand down is never started, an operation in flight is dropped, one message;
      15:44 does not, 15:50 does nothing more (once a day), a half day wakes at 12:45, a running stood-down box is
      not started again; dry run calls nothing
  T21 R5 (box half): every instance stop/start is preceded by a "takedown_intent" action line for that box, so the
      router can mute the box's own STOPPED/STARTED alert even when it arrives before the action line
v1.0  2026-11-02  dtp r521 / FEED.14 — WHO GETS A DXLINK SLOT: THE DECISION RULES, WITH FAKES FOR THE FLEET.

  T1  pre-r70 feed lines classify: "candle subscriptions live" LIVE, "feed stream error ... 502" BLIND,
      "... number of user sessions has exceeded ..." REFUSED; a quiet feed older than the lookback is LIVE
  T2  r70 lines classify with their node: "FEED.13 connected on dxlink node X", "SESSION_LIMIT: ... node X"
  T3  the ranking formula: holding (and unknown) first, theory-demoted lower, window EV desc, then n, then name;
      out-of-window CSVs and the fee column are not read; the demotion comes from the theories file
  T4  a box holding a position is NEVER stood down, nor one whose positions are unknown, even when it ranks last
  T5  the LOWEST-ranked flat live box is stood down, by INSTANCE STOP (not a feed stop), one action per pass;
      a flat refused box's feed is kicked, a holding one is never touched
  T6  restore on failure: the rescued box still refused after VERIFY_S -> the stood-down box is woken, then BACK
  T7  return when a slot frees (a live feed went away) after QUIET_S / MIN_DOWN_S, verified -> BACK
  T8  cooldowns: no second stand-down for the same refused box, the action gap, the victim cooldown
  T9  kill switch: no actuator call, no message
  T10 dry run: no actuator call, no outbox line, no action-log line
  T11 RTH guard: 08:00 ET, 16:30 ET, a Saturday and a holiday act on nothing; 15:50 starts nothing new
  T12 one STOOD DOWN and one BACK message for a contingency take-down - none while the box is down/blind
  T13 node gate: no return while the box's node is down in a fresh probe status; a stale status does not gate
  T14 an unconfirmed refusal (one line, or < CONFIRM_S) starts nothing
  T15 a refused return re-stops the box with a backoff; after MAX_FAILED_RETURNS it stays down
  T16 the box script is read-only and runs: ?mode=ro, no Environment, no write, no unit change; open count and
      the BLIND ALERT fallback parse from a fixture ~/options-trader
  T17 messages go only to the outbox: no Telegram sender in the tool
"""
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)
import feed_triage as F  # noqa: E402

FAILS, RAN = [], []
ET = F.ET
TMP = tempfile.mkdtemp(prefix="check_feed_triage_")


def ck(n, ok, msg):
    RAN.append(n)
    print(f"  {n:<4} {'PASS' if ok else 'FAIL'}  {msg}")
    if not ok:
        FAILS.append(n)


def at(h, m, s=0, d=(2026, 11, 2)):
    return datetime(d[0], d[1], d[2], h, m, s, tzinfo=ET).timestamp()


def cal(d):
    return d.weekday() < 5 and d.isoformat() != "2026-11-26", d.isoformat() == "2026-11-27"


class FakeAct:
    def __init__(self, flat=True, ok=True):
        self.calls, self.flat, self.ok = [], flat, ok

    def confirm_flat(self, s):
        self.calls.append(("confirm_flat", s))
        return self.flat

    def stop_instance(self, s):
        self.calls.append(("stop_instance", s))
        return self.ok

    def start_instance(self, s):
        self.calls.append(("start_instance", s))
        return self.ok

    def kick_feed(self, s):
        self.calls.append(("kick_feed", s))
        return True

    def acts(self):
        return [c for c in self.calls if c[0] != "confirm_flat"]


class Boom(FakeAct):
    def __getattribute__(self, name):
        if name in ("confirm_flat", "stop_instance", "start_instance", "kick_feed"):
            raise AssertionError("actuator called: " + name)
        return object.__getattribute__(self, name)


LIVE_LINE = "candle-feed[11]: 2026-11-02 19:00:00 INFO 3/3 candle subscriptions live"
R70_LIVE = "candle-feed[11]: INFO FEED.13 connected on dxlink node %s"
LIMIT_OLD = ("candle-feed[11]: ERROR feed stream error: SessionLimit: The number of user sessions has exceeded the "
             "configured limit — reconnecting in 6.0s")
LIMIT_R70 = ("candle-feed[11]: ERROR SESSION_LIMIT: TastyTrade refused the streamer on dxlink node %s (user sessions "
             "over the configured limit) - no other node known, holding; next attempt in 150.0s")
E502 = ("candle-feed[11]: ERROR feed stream error: server rejected WebSocket connection: HTTP 502 Bad Gateway — "
        "reconnecting in 12.0s")


def raw(kind, now, holding=False, node="54.204.44.247", connect_at=None, bot=True):
    ev = []
    if kind == "LIVE":
        ev = [[connect_at or (now - 600), R70_LIVE % node]]
    elif kind == "REFUSED":
        ev = [[now - 800, R70_LIVE % node], [now - 300, LIMIT_R70 % node], [now - 150, LIMIT_R70 % node],
              [now - 10, LIMIT_R70 % node]]
    elif kind == "REFUSED1":
        ev = [[now - 20, LIMIT_R70 % node]]
    elif kind == "BLIND":
        ev = [[now - 30, E502]]
    return {"feed": "active", "bot": "active" if bot else "inactive", "feed_since": "Mon 2026-11-02 14:00:00 UTC",
            "events": ev, "open": (None if holding is None else (1 if holding else 0)), "pins": []}


def fleet(now, spec):
    """spec: {sym: (kind, holding[, node])}; kind 'STOPPED' = instance stopped."""
    out = {}
    for s, v in spec.items():
        kind, hold = v[0], v[1]
        node = v[2] if len(v) > 2 else "54.204.44.247"
        if kind == "STOPPED":
            out[s] = F.classify_box(s, "stopped", None, now)
        else:
            r = raw(kind, now, hold, node, connect_at=(v[3] if len(v) > 3 else None))
            out[s] = F.classify_box(s, "running", r, now)
    return out


EV = {"AAA": (50.0, 10), "BBB": (20.0, 10), "CCC": (-5.0, 10), "DDD": (-40.0, 10), "SPX": (90.0, 10)}
DEM = {"SPX": ["T1"]}


def engine(act, dry=False, node_status=None, kill=None):
    msgs, logs = [], []
    e = F.Triage(act, dry=dry, notify=msgs.append, log=logs.append,
                 kill_path=kill or os.path.join(TMP, "nokill"), calendar=cal,
                 node_status=node_status if node_status is not None else {})
    return e, msgs, logs


# ── T1 / T2 ────────────────────────────────────────────────────────────────────────────────────────────────
now = at(14, 30)
o_live = F.classify_box("A", "running", {"feed": "active", "bot": "active", "events": [[now - 60, LIVE_LINE]],
                                         "open": 0, "feed_since": ""}, now)
o_502 = F.classify_box("A", "running", raw("BLIND", now), now)
o_lim = F.classify_box("A", "running", {"feed": "active", "bot": "active", "open": 0, "feed_since": "",
                                        "events": [[now - 200, LIMIT_OLD], [now - 100, LIMIT_OLD]]}, now)
o_quiet = F.classify_box("A", "running", {"feed": "active", "bot": "active", "open": 0, "events": [],
                                          "feed_since": "Mon 2026-11-02 14:00:00 UTC"}, now)
o_new = F.classify_box("A", "running", {"feed": "active", "bot": "active", "open": 0, "events": [],
                                        "feed_since": datetime.fromtimestamp(now - 30, F.UTC).strftime(
                                            "Mon %Y-%m-%d %H:%M:%S UTC")}, now)
o_down = F.classify_box("A", "running", {"feed": "inactive", "bot": "active", "open": 0}, now)
ck("T1", (o_live["state"], o_502["state"], o_lim["state"], o_lim["refusals"], o_quiet["state"], o_new["state"],
          o_down["state"]) == ("LIVE", "BLIND", "REFUSED", 2, "LIVE", "CONNECTING", "DOWN"),
   "pre-r70: live=%s 502=%s limit=%s(%d) quiet=%s new=%s inactive=%s" % (
       o_live["state"], o_502["state"], o_lim["state"], o_lim["refusals"], o_quiet["state"], o_new["state"],
       o_down["state"]))
k1 = F.classify_line(R70_LIVE % "184.195.238.144")
k2 = F.classify_line(LIMIT_R70 % "129.153.134.53")
k3 = F.classify_line("INFO FEED.13 dxlink node 54.204.44.247 for tasty-openapi-dxlink-md-ws.dxfeed.com (sticky)")
k4 = F.classify_line("ERROR feed stream error on dxlink node 129.153.134.53: HTTP 502 Bad Gateway — reconnecting")
k5 = F.classify_line("INFO SESSION_LIMIT lockout cleared - connected after 2 lockout wait(s), 1 held")
o_r = F.classify_box("A", "running", raw("REFUSED", now, node="129.153.134.53"), now)
ck("T2", (k1, k2, k3, k4, k5[0]) == (("CONNECT", "184.195.238.144"), ("REFUSED", "129.153.134.53"),
                                    ("DIAL", "54.204.44.247"), ("BLIND502", "129.153.134.53"), "CONNECT")
   and o_r["refused_node"] == "129.153.134.53" and o_r["refusals"] == 3,
   "r70: %s %s %s %s %s refused_node=%s" % (k1, k2, k3, k4, k5, o_r.get("refused_node")))

# ── T3 ranking ─────────────────────────────────────────────────────────────────────────────────────────────
tdir = os.path.join(TMP, "trades")
os.makedirs(tdir)
hdr = "sym,trade_id,strategy,direction,contracts,entry_premium,exit_premium,pnl_usd,entry_time,exit_time,exit_reason,fee\n"
with open(os.path.join(tdir, "2026-10-28.csv"), "w") as fh:
    fh.write(hdr + "AAA,1,Breakout,long,1,1,1,100.0,2026-10-28T13:40:00+00:00,x,x,99999\n"
                   "AAA,2,Breakout,long,1,1,1,-20.0,2026-10-28T13:41:00+00:00,x,x,99999\n"
                   "BBB,3,PARK,long,1,1,1,40.0,2026-10-28T15:01:00+00:00,x,x,0\n"
                   "CCC,4,PARK,long,1,1,1,40.0,2026-10-28T15:01:00+00:00,x,x,0\n"
                   "CCC,5,PARK,long,1,1,1,40.0,2026-10-28T15:01:00+00:00,x,x,0\n"
                   "SPX,6,PARK,long,1,1,1,900.0,2026-10-28T15:01:00+00:00,x,x,0\n")
with open(os.path.join(tdir, "2026-10-20.csv"), "w") as fh:        # before the window - must not count
    fh.write(hdr + "DDD,7,Breakout,long,1,1,1,5000.0,2026-10-20T13:40:00+00:00,x,x,0\n")
ev = F.load_window_ev(os.path.join(tdir, "20*.csv"))
theo = os.path.join(TMP, "theories.py")
with open(theo, "w") as fh:
    fh.write('''
def t1(x): return x["sym"] != "SPX"
def t1p(x): return x["sym"] != "SPX" or x["strat"] == "PARK"
FILTERS = [("baseline", lambda x: True), ("T1 no SPX", t1), ("T2 no entries after 10:01", lambda x: x["sec"] <= 36060),
           ("T1P SPX PARK only", t1p), ("P0 all symbols PARK only", lambda x: x["strat"] == "PARK"),
           ("H4P SPX PARK only, <=10:30 or PARK", lambda x: t1p(x) and (x["sec"] <= 37800 or x["strat"] == "PARK"))]
''')
filt, err = F.load_theory_filters(theo)
dem = F.demoted_symbols(["AAA", "BBB", "CCC", "DDD", "SPX"], filt)
order = F.rank_boxes(["AAA", "BBB", "CCC", "DDD", "SPX", "EEE"],
                     {"AAA": False, "BBB": False, "CCC": False, "DDD": True, "SPX": False, "EEE": None}, ev, dem)
_, bad_err = F.load_theory_filters(os.path.join(TMP, "missing.py"))
ck("T3", ev.get("AAA") == (40.0, 2) and "DDD" not in ev and set(dem) == {"SPX"} and sorted(dem["SPX"]) == ["H4P"]
   and order == ["DDD", "EEE", "AAA", "CCC", "BBB", "SPX"] and bad_err,
   "ev AAA=%s, DDD (pre-window) absent=%s, demoted=%s, order=%s, missing theories -> %s" % (
       ev.get("AAA"), "DDD" not in ev, dem, order, bool(bad_err)))

# ── T4 / T5 position safety and victim choice ─────────────────────────────────────────────────────────────
now = at(14, 30)
obs = fleet(now, {"SPX": ("REFUSED", True), "AAA": ("LIVE", False), "BBB": ("LIVE", False),
                  "CCC": ("LIVE", False), "DDD": ("LIVE", True)})
a = FakeAct()
e, msgs, logs = engine(a)
st = e.step({}, obs, EV, DEM, now)
ck("T4", ("stop_instance", "DDD") not in a.calls and st["stood_down"].keys() == {"CCC"},
   "DDD (lowest EV, holding) untouched; stood down %s" % sorted(st["stood_down"]))
obs_u = fleet(now, {"AAA": ("REFUSED", True), "BBB": ("LIVE", None), "CCC": ("LIVE", None)})
a_u = FakeAct()
e_u, _m, _l = engine(a_u)
e_u.step({}, obs_u, EV, DEM, now)
ck("T4b", a_u.acts() == [], "unknown positions are never stood down: calls=%s" % a_u.calls)
ck("T5", a.acts() == [("stop_instance", "CCC")] and len(msgs) == 1 and "STOOD DOWN CCC" in msgs[0]
   and st["op"]["kind"] == "rescue",
   "holding SPX refused -> lowest flat CCC stopped by instance, SPX feed not kicked: %s" % a.acts())
obs_f = fleet(now, {"AAA": ("REFUSED", False), "BBB": ("LIVE", False), "CCC": ("LIVE", False),
                    "DDD": ("LIVE", False)})
a_f = FakeAct()
e_f, _m, _l = engine(a_f)
e_f.step({}, obs_f, EV, DEM, now)
ck("T5b", a_f.acts() == [("stop_instance", "DDD"), ("kick_feed", "AAA")],
   "flat refused AAA: lowest DDD stopped, AAA's feed kicked: %s" % a_f.acts())
obs_hi = fleet(now, {"DDD": ("REFUSED", False), "AAA": ("LIVE", False), "BBB": ("LIVE", False)})
a_hi = FakeAct()
e_hi, _m, _l = engine(a_hi)
e_hi.step({}, obs_hi, EV, DEM, now)
ck("T5c", a_hi.acts() == [], "a refused box never stands down a HIGHER-ranked one: %s" % a_hi.acts())
obs_n = fleet(now, {"SPX": ("REFUSED", True, "129.153.134.53"), "AAA": ("LIVE", False, "129.153.134.53"),
                    "BBB": ("LIVE", False, "54.204.44.247"), "CCC": ("LIVE", False, "54.204.44.247")})
a_n = FakeAct()
e_n, _m, _l = engine(a_n)
e_n.step({}, obs_n, EV, DEM, now)
ck("T5d", a_n.acts() == [("stop_instance", "AAA")],
   "the refusing node's own flat box is preferred: %s" % a_n.acts())

# ── T6 restore on failure, T12 messages ────────────────────────────────────────────────────────────────────
t = now
all_msgs = list(msgs)
e6, m6, _l = engine(a)
for dt in (60, 180, 300):                                      # SPX still refused, CCC stopped
    o6 = fleet(t + dt, {"SPX": ("REFUSED", True), "AAA": ("LIVE", False), "BBB": ("LIVE", False),
                        "CCC": ("STOPPED", None), "DDD": ("LIVE", True)})
    st = e6.step(st, o6, EV, DEM, t + dt)
quiet_while_down = (m6 == [] and a.acts() == [("stop_instance", "CCC")])
o6 = fleet(t + 430, {"SPX": ("REFUSED", True), "AAA": ("LIVE", False), "BBB": ("LIVE", False),
                     "CCC": ("STOPPED", None), "DDD": ("LIVE", True)})
st = e6.step(st, o6, EV, DEM, t + 430)
restored = a.acts()[-1] == ("start_instance", "CCC") and st["op"]["why"] == "restore"
for dt in (600, 900):                                          # booting: unreadable, then connecting
    o6 = fleet(t + dt, {"SPX": ("REFUSED", True), "AAA": ("LIVE", False), "BBB": ("LIVE", False),
                        "CCC": ("BLIND", False), "DDD": ("LIVE", True)})
    st = e6.step(st, o6, EV, DEM, t + dt)
o6 = fleet(t + 1000, {"SPX": ("REFUSED", True), "AAA": ("LIVE", False), "BBB": ("LIVE", False),
                      "CCC": ("LIVE", False, "54.204.44.247", t + 990), "DDD": ("LIVE", True)})
st = e6.step(st, o6, EV, DEM, t + 1000)
all_msgs += m6
ck("T6", restored and "CCC" not in st["stood_down"] and st["op"] is None and len(m6) == 1 and "BACK CCC" in m6[0],
   "SPX still refused after %ds -> CCC woken, verified back: %s" % (F.VERIFY_S, m6))
ck("T12", quiet_while_down and len(all_msgs) == 2 and "STOOD DOWN CCC" in all_msgs[0] and "BACK CCC" in all_msgs[1]
   and "no BLIND alerts" in all_msgs[0],
   "exactly one STOOD DOWN and one BACK, nothing while down or blind: %d message(s)" % len(all_msgs))

# ── T8 cooldowns (continuing: SPX still refused, CCC back) ─────────────────────────────────────────────────
before = len(a.acts())
o8 = fleet(t + 1200, {"SPX": ("REFUSED", True), "AAA": ("LIVE", False), "BBB": ("LIVE", False),
                      "CCC": ("LIVE", False), "DDD": ("LIVE", True)})
st8 = e6.step(st, o8, EV, DEM, t + 1200)
no_second = len(a.acts()) == before
a8 = FakeAct()
e8, _m, _l = engine(a8)
o8b = fleet(t + 1200, {"AAA": ("REFUSED", False), "BBB": ("LIVE", False), "CCC": ("LIVE", False),
                       "DDD": ("LIVE", True)})
e8.step(st8, o8b, EV, DEM, t + 1200)
victim_cd = ("stop_instance", "CCC") not in a8.calls and ("stop_instance", "BBB") in a8.calls
a8c = FakeAct()
e8c, _m, _l = engine(a8c)
gap_state = dict(st8, last_action_at=t + 1150)
e8c.step(gap_state, o8b, EV, DEM, t + 1200)
ck("T8", no_second and victim_cd and a8c.acts() == [],
   "SPX in rescue cooldown=%s; just-returned CCC skipped for BBB=%s; action gap holds=%s" % (
       no_second, victim_cd, a8c.acts() == []))

# ── T9 kill switch, T10 dry run ────────────────────────────────────────────────────────────────────────────
kill = os.path.join(TMP, "KILL")
open(kill, "w").close()
a9 = Boom()
e9, m9, l9 = engine(a9, kill=kill)
try:
    e9.step({}, obs, EV, DEM, now)
    ok9 = m9 == [] and l9 == []
except AssertionError as exc:
    ok9 = False
    print("    ", exc)
ck("T9", ok9, "kill switch file present -> no call, no message")
a10 = Boom()
e10, m10, l10 = engine(a10, dry=True)
try:
    st10 = e10.step({}, obs, EV, DEM, now)
    ok10 = m10 == [] and l10 == [] and any("would enqueue" in s for s in e10.lines)
except AssertionError as exc:
    ok10 = False
    print("    ", exc)
ck("T10", ok10, "dry run decides (prints 'would enqueue'), calls nothing, logs and enqueues nothing")

# ── T11 RTH guard ──────────────────────────────────────────────────────────────────────────────────────────
res = []
for when in (at(8, 0), at(16, 30), at(12, 0, d=(2026, 11, 7)), at(12, 0, d=(2026, 11, 26)), at(15, 50),
             at(12, 50, d=(2026, 11, 27))):
    a11 = FakeAct()
    e11, _m, _l = engine(a11)
    e11.step({}, fleet(when, {"SPX": ("REFUSED", True), "AAA": ("LIVE", False), "BBB": ("LIVE", False)}),
             EV, DEM, when)
    res.append(a11.acts() == [])
a11 = FakeAct()
e11, _m, _l = engine(a11)
pre = at(9, 20)
e11.step({}, fleet(pre, {"AAA": ("REFUSED", False), "BBB": ("LIVE", False), "CCC": ("LIVE", False)}), EV, DEM, pre)
ck("T11", all(res) and a11.acts() == [("stop_instance", "CCC"), ("kick_feed", "AAA")],
   "08:00, 16:30, Saturday, Thanksgiving, 15:50, half-day 12:50 act on nothing %s; the 09:20 wake window acts" % res)

# ── T7 return when a slot frees, T13 node gate ─────────────────────────────────────────────────────────────
t7 = at(13, 0)
st7 = {"day": "2026-11-02", "stood_down": {"DDD": {"at": t7, "for": "SPX", "node": "54.204.44.247", "live_at": 4,
                                                   "failed_returns": 0}},
       "op": None, "last_action_at": t7, "last_refusal_at": t7 + 200, "r_cooldown": {}, "victim_cooldown": {}}
spec_free = {"SPX": ("LIVE", True), "AAA": ("LIVE", False), "BBB": ("LIVE", False), "CCC": ("STOPPED", None),
             "DDD": ("STOPPED", None)}
a7 = FakeAct()
e7, m7, _l = engine(a7)
s = e7.step(st7, fleet(t7 + 600, spec_free), EV, DEM, t7 + 600)          # quiet only 400 s, down 600 s
early = a7.acts() == []
s = e7.step(s, fleet(t7 + 1000, spec_free), EV, DEM, t7 + 1000)
woke = a7.acts() == [("start_instance", "DDD")]
spec_back = dict(spec_free, DDD=("LIVE", False, "54.204.44.247", t7 + 1500))
s = e7.step(s, fleet(t7 + 1600, spec_back), EV, DEM, t7 + 1600)
ck("T7", early and woke and m7 and "BACK DDD" in m7[-1] and not s["stood_down"],
   "held while refusals are recent (%s), woken when CCC's feed went away (%s), verified back" % (early, woke))
fresh_down = {"probed_at": t7 + 990, "nodes": {"54.204.44.247": {"state": "down"}, "184.195.238.144": {"state": "up"}}}
a13 = FakeAct()
e13, _m, _l = engine(a13, node_status=fresh_down)
e13.step(st7, fleet(t7 + 1000, spec_free), EV, DEM, t7 + 1000)
none_up = {"probed_at": t7 + 990, "nodes": {"54.204.44.247": {"state": "up"}, "1.2.3.4": {"state": "down"}}}
none_up["nodes"]["54.204.44.247"]["state"] = "unreachable"
a13b = FakeAct()
e13b, _m, _l = engine(a13b, node_status=none_up)
e13b.step(st7, fleet(t7 + 1000, spec_free), EV, DEM, t7 + 1000)
stale = dict(fresh_down, probed_at=t7 - 3600)
a13c = FakeAct()
e13c, _m, _l = engine(a13c, node_status=stale)
e13c.step(st7, fleet(t7 + 1000, spec_free), EV, DEM, t7 + 1000)
ck("T13", a13.acts() == [] and a13b.acts() == [] and a13c.acts() == [("start_instance", "DDD")],
   "its node down -> held; no node up -> held; stale status -> not gated")

# ── T14 unconfirmed refusal ────────────────────────────────────────────────────────────────────────────────
a14 = FakeAct()
e14, _m, _l = engine(a14)
e14.step({}, fleet(now, {"SPX": ("REFUSED1", True), "AAA": ("LIVE", False), "BBB": ("LIVE", False)}), EV, DEM, now)
ck("T14", a14.acts() == [], "one refusal line 20 s old starts nothing")

# ── T15 refused return ─────────────────────────────────────────────────────────────────────────────────────
a15 = FakeAct()
e15, m15, _l = engine(a15)
s15 = e15.step(st7, fleet(t7 + 1000, spec_free), EV, DEM, t7 + 1000)        # woken
s15 = e15.step(s15, fleet(t7 + 1400, dict(spec_free, DDD=("REFUSED", False))), EV, DEM, t7 + 1400)
sd = s15["stood_down"].get("DDD", {})
first = (a15.acts() == [("start_instance", "DDD"), ("stop_instance", "DDD")] and sd.get("failed_returns") == 1
         and sd.get("next_return_at") == t7 + 1400 + F.RETURN_RETRY_S and "STAYS DOWN" in m15[-1])
s15b = dict(s15, stood_down={"DDD": dict(sd, failed_returns=F.MAX_FAILED_RETURNS, next_return_at=0)},
            last_refusal_at=0, last_action_at=0)
a15b = FakeAct()
e15b, _m, _l = engine(a15b)
e15b.step(s15b, fleet(t7 + 9000, spec_free), EV, DEM, t7 + 9000)
ck("T15", first and a15b.acts() == [],
   "refused return -> re-stopped, next try +%ds, one message; after %d failures no more tries" % (
       F.RETURN_RETRY_S, F.MAX_FAILED_RETURNS))

# ── T16 the box script ─────────────────────────────────────────────────────────────────────────────────────
src = F.BOX_SCRIPT
banned = ["Environment", "open(p, \"w", "'w'", "\"w\"", "\"a\"", "restart", "\"stop\"", "\"start\"", "remove(",
          "unlink", "rename", ".env", "environ[", "sudo"]
ro = "?mode=ro" in src and all(b not in src for b in banned)
home = os.path.join(TMP, "home")
oh = os.path.join(home, "options-trader")
os.makedirs(oh)
db = sqlite3.connect(os.path.join(oh, "trades.db"))
db.execute("CREATE TABLE trades (trade_id TEXT, status TEXT)")
db.executemany("INSERT INTO trades VALUES (?,?)", [("a", "open"), ("b", "closed"), ("c", "open")])
db.commit()
db.close()
with open(os.path.join(oh, "bot.log"), "w") as fh:
    fh.write("2026-11-02 19:20:00 [ERROR] notifications.alert_manager: BLIND ALERT | QQQ | cause=STALE tf=1m "
             "blind_for=60s open_positions=1 paper=True | x=1\n")
env = dict(os.environ, HOME=home)
p = subprocess.run(["bash", "-c", F.box_command(900)], capture_output=True, text=True, env=env, timeout=60)
out = F.parse_box_output(p.stdout) or {}
mtime_ok = sqlite3.connect("file:" + os.path.join(oh, "trades.db") + "?mode=ro", uri=True).execute(
    "SELECT COUNT(*) FROM trades").fetchone()[0] == 3
ck("T16", ro and out.get("open") == 2 and out.get("blind") == ["2026-11-02 19:20:00", 1] and mtime_ok,
   "read-only source=%s; ran for real: open=%s blind=%s" % (ro, out.get("open"), out.get("blind")))
r16 = F.classify_box("QQQ", "running", {"feed": "active", "bot": "active", "open": None, "open_err": "x",
                                        "blind": ["2026-11-02 19:20:00", 1], "events": []},
                     datetime(2026, 11, 2, 19, 30, tzinfo=F.ET).timestamp() - 5 * 3600)
ck("T16b", r16["holding"] is True, "a failed DB read falls back to a fresh BLIND ALERT open_positions=1")

# ── T17 outbox only ────────────────────────────────────────────────────────────────────────────────────────
tool_src = open(F.__file__, encoding="utf-8").read()
ob = os.path.join(TMP, "outbox.jsonl")
F.enqueue("hello", path=ob)
line = json.loads(open(ob).read().strip())
ck("T17", "api.telegram.org" not in tool_src and "notify.send" not in tool_src and "import notify" not in tool_src
   and line["text"] == "hello" and line["source"] == "feed_triage",
   "no Telegram sender in the tool; enqueue writes one JSON line to the outbox")

# ── T18 R1 demotion by H4P only ────────────────────────────────────────────────────────────────────────────
theo18 = os.path.join(TMP, "theories18.py")
with open(theo18, "w") as fh:
    fh.write('''
FILTERS = [("T1 no AAA", lambda x: x["sym"] != "AAA"), ("H4 no BBB", lambda x: x["sym"] != "BBB"),
           ("P0 no CCC", lambda x: x["sym"] != "CCC"), ("H4P no SPX", lambda x: x["sym"] != "SPX")]
''')
f18, _e = F.load_theory_filters(theo18)
d18 = F.demoted_symbols(["AAA", "BBB", "CCC", "SPX"], f18)
theo18b = os.path.join(TMP, "theories18b.py")
with open(theo18b, "w") as fh:
    fh.write('FILTERS = [("T1 no SPX", lambda x: x["sym"] != "SPX"), ("H4 no SPX", lambda x: x["sym"] != "SPX")]\n')
f18b, _e = F.load_theory_filters(theo18b)
d18b = F.demoted_symbols(["AAA", "SPX"], f18b)
ck("T18", d18 == {"SPX": ["H4P"]} and list(f18) == ["H4P"] and d18b == {} and F.DEMOTE_THEORY == "H4P",
   "only H4P demotes: %s; without H4P nothing is demoted: %s" % (d18, d18b))

# ── T19 R2 shrink ──────────────────────────────────────────────────────────────────────────────────────────
ev19 = {"XXX": (200.0, 2), "YYY": (30.0, 25), "ZZZ": (-50.0, 1), "WWW": (-10.0, 40)}
o19 = F.rank_boxes(["XXX", "YYY", "ZZZ", "WWW"], {s: False for s in ev19}, ev19, {})
vals = (F.shrunk_ev(200.0, 2), F.shrunk_ev(30.0, 25), F.shrunk_ev(30.0, 20), F.shrunk_ev(-50.0, 1), F.shrunk_ev(5.0, 0))
ck("T19", o19 == ["YYY", "XXX", "ZZZ", "WWW"] and vals == (20.0, 30.0, 30.0, -2.5, 0.0) and F.EV_FULL_N == 20,
   "ev x min(n,20)/20 = %s; order %s (a 2-trade +$200 below a 25-trade +$30)" % (vals, o19))

# ── T20 R4 the close wake ──────────────────────────────────────────────────────────────────────────────────
def st20(t):
    return {"day": "2026-11-02", "last_action_at": t - 3600,
            "stood_down": {"CCC": {"at": t - 7200, "for": "SPX", "node": "54.204.44.247", "live_at": 4,
                                   "failed_returns": 0},
                           "DDD": {"at": t - 7200, "for": "SPX", "node": "54.204.44.247", "live_at": 4,
                                   "failed_returns": F.MAX_FAILED_RETURNS}},
            "op": {"kind": "rescue", "r": "SPX", "v": "CCC", "at": t - 60}}
spec20 = {"SPX": ("LIVE", True), "AAA": ("LIVE", False), "CCC": ("STOPPED", False), "DDD": ("STOPPED", False),
          "EEE": ("STOPPED", False)}
t20 = at(15, 45)
a20 = FakeAct()
e20, m20, l20 = engine(a20)
s20 = e20.step(st20(t20), fleet(t20, spec20), EV, DEM, t20)
a20b = FakeAct()
e20b, m20b, _l = engine(a20b)
s20b = e20b.step(s20, fleet(at(15, 50), spec20), EV, DEM, at(15, 50))
t44 = at(15, 44)
a44 = FakeAct()
e44, _m, _l = engine(a44)
e44.step(st20(t44), fleet(t44, spec20), EV, DEM, t44)
th = at(12, 45, d=(2026, 11, 27))
sth = st20(th)
sth["day"] = "2026-11-27"
ah = FakeAct()
eh, mh, _l = engine(ah)
eh.step(sth, fleet(th, spec20), EV, DEM, th)
spec_up = dict(spec20, CCC=("LIVE", False))
au = FakeAct()
eu, mu, _l = engine(au)
eu.step(st20(t20), fleet(t20, spec_up), EV, DEM, t20)
ad = Boom()
ed, md, ld = engine(ad, dry=True)
ed.step(st20(t20), fleet(t20, spec20), EV, DEM, t20)
ck("T20", a20.acts() == [("start_instance", "CCC"), ("start_instance", "DDD")] and len(m20) == 1
   and "Close wake" in m20[0] and "CCC, DDD" in m20[0] and s20["stood_down"] == {} and s20["op"] is None
   and s20.get("close_wake_at") == t20 and a20b.acts() == [] and not m20b
   and ("start_instance", "CCC") not in a44.acts()
   and ah.acts() == [("start_instance", "CCC"), ("start_instance", "DDD")] and len(mh) == 1
   and au.acts() == [("start_instance", "DDD")] and "already up: CCC" in mu[0]
   and ld == [] and md == [],
   "15:45 %s msg=%s; 15:50 %s; 15:44 %s; half day 12:45 %s; CCC running -> %s; dry run calls nothing" % (
       a20.acts(), m20, a20b.acts(), a44.acts(), ah.acts(), au.acts()))

# ── T21 R5 intent lines ────────────────────────────────────────────────────────────────────────────────────
def intent_first(logs_):
    kinds = [(r["kind"], r["sym"]) for r in logs_]
    for i, (k, sy) in enumerate(kinds):
        if k in ("stand_down", "close_wake", "wake", "stand_down_again"):
            if ("takedown_intent", sy) not in kinds[:i]:
                return False
    return True
ck("T21", intent_first(logs) and intent_first(l20) and ("takedown_intent", "CCC") in [(r["kind"], r["sym"]) for r in logs]
   and sum(1 for r in l20 if r["kind"] == "takedown_intent") == 2,
   "intent lines precede the stand-down %s and the close wake %s" % (
       [r["kind"] for r in logs], [r["kind"] for r in l20]))

print()
if FAILS:
    print(f"RED — {len(FAILS)} of {len(RAN)} check(s) failed: {' '.join(FAILS)}")
    sys.exit(1)
print(f"GREEN — {len(RAN)} checks")
