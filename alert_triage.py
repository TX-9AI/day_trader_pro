#!/usr/bin/env python3
"""
day_trader_pro/alert_triage.py — v1.0
v1.0  2026-11-08  dtp r540 / ROUTE.1 — CONTROL TRIAGES EACH ALERT AS IT ARRIVES, BY EVENT TYPE. NOTHING POLLS A BOX.
      The operator, 2026-11-08, on the per-minute triage timer (deleted in dtp r539): "It should be reactionary, by
      event type—not run every minute looking for problems. The telegram alerts should be flowing to control—that's
      your 'notification' when something happens. You get the message instead of the operator & you decide how to
      triage that whilst queuing the feed the operator sees."
      The boxes already hand every alert to control (OTV5 notifications/alert_route, PAGE.2): the pager streams each
      `[alert]` line and alert_router.ingest_alert() owns it. The router now calls Triage.on_event() for every alert
      it takes (live, not replayed), which:
        1. CLASSIFIES it (classify(): one EVENT TYPE per alert, the table POLICY below);
        2. WRITES it to the inbox, data/alert_router/inbox/<ET day>.jsonl (one JSON line per event and per action
           result; `notify: true` on the lines Claude must look at). The Claude session follows it with Monitor
           (`tail -F` + grep '"notify": true'); the nightly review reads the whole day;
        3. ACTS, when the type has an action, on a worker thread (the router's loop never waits): only the actions on
           the list the operator approved 2026-11-02, only on a box PROVEN FLAT by a fresh read-only trades.db read
           (unknown is never flat), at most one action per box per ACTION_COOLDOWN_S, MAX_ACTIONS_PER_BOX_DAY a day,
           and none while the kill-switch file exists. Before acting it posts "working" (the line joins the
           operator's BLIND message), after it "recovered" or a failure line (critical, and `notify` in the inbox).
        4. SAYS WHAT THE OPERATOR SEES (feed()): "now" (critical words, a box with positions, a failed action),
           "group" (the router's normal grouped queue), "digest" (UP / DN inside the scheduled 09:15 wake and the
           close: one message for the whole wave, DIGEST_HOLD_S). Nothing is suppressed: a box's BOT IS BLIND and
           every money-at-risk alert still goes out at once (the box sends those direct itself; the router dedups).
      Approved actions built here (operator 2026-11-02; "Open positions come first in every triage"):
        RESTART_FEED   a flat box BLIND still blind after BLIND_GRACE_S, while at most FLEET_BLIND_MAX boxes are
                       blind (more is a feed-side outage a restart cannot cure: reported, not acted on):
                       `sudo systemctl restart candle-feed` on that box. A box refused by the dxlink session limit is
                       NOT restarted (it switches node itself, FEED.13; a redial adds to the load) - inbox notify.
        START_BOT      a flat box's optionsbot DOWN in RTH, outside the wake / close / halt windows and not a
                       requested stop, with no UP within DOWN_GRACE_S: `sudo systemctl start optionsbot`.
        PURGE          a DISK alert outside RTH on a flat box: the box's own warehouse/retention_purge.py (retention
                       rules already in code; never trade data). In RTH the purge would stop the feed, so a disk alert
                       in RTH is the operator's (forwarded now, inbox notify).
      Not built (stays report-and-ask): standing a flat box down to free a dxlink slot for a box holding a position
      (the 11-02 connection-triage ruling) - it stops an instance during RTH and gets its own change.
"""
import collections
import json
import os
import queue
import re
import threading
import time
from datetime import datetime

import config

__version__ = "1.0"

STATE_DIR = os.path.join(config.DATA_DIR, "alert_router")
KILL_FILE = "TRIAGE_OFF"                # in STATE_DIR: present -> classify and write the inbox, act on nothing
BLIND_GRACE_S = 90.0                    # a box may heal itself (FEED.13 switches node fast); act only after this
DOWN_GRACE_S = 60.0
ACTION_COOLDOWN_S = 600.0
MAX_ACTIONS_PER_BOX_DAY = 3
DIGEST_HOLD_S = 240.0                   # the 09:15 wake brings 14 boxes up over ~3 min: one message for the wave
SSH_BUDGET_S = 40
FLEET_BLIND_MAX = 3                     # more boxes blind at once = an outage at the feed, not a stuck box

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:                                                          # noqa: BLE001
    ET = None

CRIT_CODES = {"HCF", "EXR", "SLC", "RCU"}
CRIT_RE = re.compile(r"EMERGENCY|CATASTROPHIC|HALT|KILL[ _-]?SWITCH|RECONCILE MISMATCH|could not be cancelled|"
                     r"LONE SHORT|GO TO TASTYTRADE NOW", re.IGNORECASE)
DISK_RE = re.compile(r"\bDISK\b", re.IGNORECASE)
REFUSED_RE = re.compile(r"SESSION_LIMIT|sessions has exceeded", re.IGNORECASE)
REQUESTED_STOP_RE = re.compile(r"shutdown|requested|SIGTERM|midnight|halt|self[_ -]?close|eod|instance stop|update|"
                               r"restart", re.IGNORECASE)

# EVENT TYPE -> (action, operator feed, claude must look)
POLICY = collections.OrderedDict([
    ("CRITICAL",     (None,           "now",    True)),    # HCF EXR SLC RCU, emergency/halt/kill/broker words
    ("BLIND_OPEN",   (None,           "now",    True)),    # BLIND with positions: never touched
    ("BLIND",        ("RESTART_FEED", "group",  False)),   # flat box blind
    ("REFUSED",      (None,           "group",  True)),    # the box switches node itself (FEED.13); a redial adds load
    ("SIGHT",        (None,           "group",  False)),   # sight restored: closes the episode
    ("DISK",         ("PURGE",        "now",    True)),    # PURGE only outside RTH on a flat box
    ("BOT_DOWN",     ("START_BOT",    "group",  False)),   # START_BOT only unexpected, in RTH, flat
    ("BOT_UP",       (None,           "group",  False)),
    ("TRADE",        (None,           "group",  False)),   # ENT EXT RCV ADP PHN
    ("SUMMARY",      (None,           "group",  False)),   # SUM ORF
    ("OTHER",        (None,           "group",  False)),   # MSG and anything new
])


def et(ts=None):
    t = time.time() if ts is None else ts
    return datetime.fromtimestamp(t, ET) if ET else datetime.fromtimestamp(t)


def _hm(ts):
    d = et(ts)
    return d.hour * 60 + d.minute


def in_rth(ts):
    hm = _hm(ts)
    return 9 * 60 + 30 <= hm < 16 * 60


def scheduled_window(ts):
    """The fleet's own ups and downs: the 09:15 wake, the close and the midnight halt."""
    hm = _hm(ts)
    return 9 * 60 + 10 <= hm < 9 * 60 + 35 or 15 * 60 + 55 <= hm < 17 * 60 or hm < 30 or hm >= 23 * 60 + 50


def classify(rec):
    code = str(rec.get("code") or "MSG").upper()
    text = str(rec.get("text") or "")
    if code in CRIT_CODES or CRIT_RE.search(text):
        return "CRITICAL"
    if code == "DSK" or DISK_RE.search(text):
        return "DISK"
    if code == "BLD":
        if isinstance(rec.get("open"), int) and rec["open"] > 0:
            return "BLIND_OPEN"
        return "REFUSED" if REFUSED_RE.search(str(rec.get("cause", "")) + " " + text) else "BLIND"
    if code == "SEE":
        return "SIGHT"
    if code == "DN":
        return "BOT_DOWN"
    if code == "UP":
        return "BOT_UP"
    if code in ("ENT", "EXT", "RCV", "ADP", "PHN"):
        return "TRADE"
    if code in ("SUM", "ORF"):
        return "SUMMARY"
    return "OTHER"


FLAT_CMD = ("python3 -c \"import sqlite3,os;c=sqlite3.connect('file:'+os.path.expanduser('~/options-trader/trades.db')"
            "+'?mode=ro',uri=True);print('OPEN',c.execute(\\\"select count(*) from trades where status='open'\\\")"
            ".fetchone()[0])\"")
ACTION_CMD = {
    "RESTART_FEED": "sudo systemctl restart candle-feed && sleep 20 && systemctl is-active candle-feed",
    "START_BOT": "sudo systemctl start optionsbot && sleep 10 && systemctl is-active optionsbot",
    "PURGE": "cd ~/options-trader && timeout 900 python3 warehouse/retention_purge.py; echo rc=$?",
}


class Triage:
    """One per router. on_event() is called under the router's lock and only queues; a worker thread acts."""

    def __init__(self, post_status=None, ip_of=None, ssh=None, state_dir=None, clock=time.time, sleep=time.sleep,
                 open_n=None, log=None, start=True):
        self.state_dir = state_dir or STATE_DIR
        self.clock, self.sleep = clock, sleep
        self.log = log or (lambda m: None)
        self._post = post_status
        self._ip_of = ip_of
        self._ssh = ssh
        self.open_n = open_n or (lambda box: 0)
        self.last_action = {}                  # box -> ts
        self.count = collections.Counter()    # (day, box) -> actions
        self.seen = {}                         # (box, type) -> ts of the newest event (SEE / UP clear a pending act)
        self.blind = set()                     # boxes blind now (BLIND / BLIND_OPEN / REFUSED until SIGHT)
        self.q = queue.Queue()
        self.lock = threading.Lock()
        self.worker = None
        if start:
            self.worker = threading.Thread(target=self._loop, name="alert-triage", daemon=True)
            self.worker.start()

    # ── the inbox ────────────────────────────────────────────────────────────────────────────────────────────────
    def inbox_path(self, ts=None):
        return os.path.join(self.state_dir, "inbox", et(ts).strftime("%Y-%m-%d") + ".jsonl")

    def write(self, row):
        try:
            p = self.inbox_path(row.get("ts"))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        except Exception as e:                                         # noqa: BLE001
            self.log("inbox not written (%s)" % type(e).__name__)

    # ── feed and classification ─────────────────────────────────────────────────────────────────────────────────
    def feed(self, rec, now=None):
        """What the operator sees for this alert: now | group | digest."""
        now = self.clock() if now is None else now
        typ = classify(rec)
        mode = POLICY[typ][1]
        if typ in ("BOT_UP", "BOT_DOWN") and scheduled_window(now):
            return "digest"
        return mode

    def on_event(self, box, rec):
        now = self.clock()
        typ = classify(rec)
        action, feed, must = POLICY[typ]
        if typ in ("BOT_UP", "BOT_DOWN") and scheduled_window(now):
            feed = "digest"
        with self.lock:
            self.seen[(box, typ)] = now
            if typ in ("BLIND", "BLIND_OPEN", "REFUSED"):
                self.blind.add(box)
            elif typ in ("SIGHT", "BOT_UP"):
                self.blind.discard(box)
        planned = self._plan(box, typ, rec, now) if action else None
        self.write({"ts": round(now, 3), "kind": "event", "box": box, "type": typ, "code": rec.get("code"),
                    "id": rec.get("id"), "via": rec.get("via"), "open": rec.get("open"), "feed": feed,
                    "action": planned or None, "notify": bool(must),
                    "text": str(rec.get("text", ""))[:300]})
        if planned:
            self.q.put((box, typ, planned, now, rec))
        return typ, feed, planned

    def _plan(self, box, typ, rec, now):
        """-> the action to try, or None (and why goes in the log)."""
        action = POLICY[typ][0]
        if os.path.exists(os.path.join(self.state_dir, KILL_FILE)):
            return None
        if self.open_n(box):
            return None                         # the router believes it holds a position: never touched
        if action == "START_BOT":
            if not in_rth(now) or scheduled_window(now) or REQUESTED_STOP_RE.search(
                    str(rec.get("cause", "")) + " " + str(rec.get("text", ""))):
                return None
        if action == "PURGE" and in_rth(now):
            return None
        if action == "RESTART_FEED" and len(self.blind) > FLEET_BLIND_MAX:
            return None
        return action

    # ── acting ──────────────────────────────────────────────────────────────────────────────────────────────────
    def _loop(self):
        while True:
            item = self.q.get()
            if item is None:
                return
            try:
                self.act(*item)
            except Exception as e:                                     # noqa: BLE001
                self.log("triage action failed (%s: %s)" % (type(e).__name__, str(e)[:120]))

    def stop(self):
        self.q.put(None)

    def _wait_grace(self, box, typ, action, t0):
        """Wait out the grace period; -> False when the box healed itself (SEE after a BLIND, UP after a DN)."""
        grace = BLIND_GRACE_S if action == "RESTART_FEED" else DOWN_GRACE_S if action == "START_BOT" else 0.0
        heal = {"RESTART_FEED": "SIGHT", "START_BOT": "BOT_UP"}.get(action)
        end = t0 + grace
        while self.clock() < end:
            self.sleep(min(5.0, max(0.0, end - self.clock())))
            with self.lock:
                if heal and self.seen.get((box, heal), 0) >= t0:
                    return False
        with self.lock:
            return not (heal and self.seen.get((box, heal), 0) >= t0)

    def act(self, box, typ, action, t0, rec):
        day = et(t0).strftime("%Y-%m-%d")
        if not self._wait_grace(box, typ, action, t0):
            self.write({"ts": round(self.clock(), 3), "kind": "action", "box": box, "action": action,
                        "result": "not needed - the box healed itself", "notify": False})
            return "healed"
        with self.lock:
            wide = action == "RESTART_FEED" and len(self.blind) > FLEET_BLIND_MAX
        if wide:
            self.write({"ts": round(self.clock(), 3), "kind": "action", "box": box, "action": action,
                        "result": "not taken - %d boxes blind: a feed-side outage" % len(self.blind), "notify": True})
            return "outage"
        with self.lock:
            last = self.last_action.get(box, 0.0)
            if self.clock() - last < ACTION_COOLDOWN_S or self.count[(day, box)] >= MAX_ACTIONS_PER_BOX_DAY:
                why = "cooldown" if self.clock() - last < ACTION_COOLDOWN_S else "daily limit"
                self.write({"ts": round(self.clock(), 3), "kind": "action", "box": box, "action": action,
                            "result": "skipped (%s) - the operator's" % why, "notify": True})
                self._status("critical", "%s still %s; %s not retried (%s) - needs a look" % (
                    box, typ.lower(), action.lower().replace("_", " "), why), [box], rec)
                return "limited"
            self.last_action[box] = self.clock()
            self.count[(day, box)] += 1
        ip = self._ip(box)
        if not ip:
            return self._fail(box, action, "no address (EC2 not running?)", rec)
        rc, out, _err = self._run(ip, FLAT_CMD)
        m = re.search(r"OPEN (\d+)", out or "")
        if rc != 0 or not m:
            return self._fail(box, action, "could not prove the box flat - left alone", rec)
        if int(m.group(1)) > 0:
            self.write({"ts": round(self.clock(), 3), "kind": "action", "box": box, "action": action,
                        "result": "not taken - %s open position(s)" % m.group(1), "notify": True})
            return "holding"
        self._status("working", "%s on %s (flat)" % (action.lower().replace("_", " "), box), [box], rec)
        rc, out, err = self._run(ip, ACTION_CMD[action], timeout=960 if action == "PURGE" else SSH_BUDGET_S + 30)
        ok = rc == 0 and ("active" in (out or "") if action != "PURGE" else "rc=0" in (out or "")
                          or "rc=4" in (out or ""))
        if not ok:
            return self._fail(box, action, "rc %s %s" % (rc, (out or err or "").strip()[-80:]), rec)
        self.write({"ts": round(self.clock(), 3), "kind": "action", "box": box, "action": action, "result": "done",
                    "notify": False})
        if action == "PURGE":
            self._status("info", "%s: retention purge done after a disk alert" % box, [box], rec)
        return "done"

    def _fail(self, box, action, why, rec):
        self.write({"ts": round(self.clock(), 3), "kind": "action", "box": box, "action": action,
                    "result": "FAILED - " + why, "notify": True})
        self._status("critical", "%s: %s failed - %s" % (box, action.lower().replace("_", " "), why), [box], rec)
        return "failed"

    def _status(self, kind, text, boxes, rec):
        try:
            if self._post is None:
                import alert_router
                self._post = alert_router.post_status
            self._post(kind, "Control: " + text, boxes=boxes, cause=str(rec.get("cause") or ""))
        except Exception as e:                                         # noqa: BLE001
            self.log("status not posted (%s)" % type(e).__name__)

    def _ip(self, box):
        try:
            if self._ip_of is None:
                import fleet
                return next((ip for s, ip, st in fleet.get_fleet(only=[box]) if st == "running" and ip), None)
            return self._ip_of(box)
        except Exception:                                              # noqa: BLE001
            return None

    def _run(self, ip, cmd, timeout=SSH_BUDGET_S):
        if self._ssh is None:
            import ssh_util
            self._ssh = ssh_util.ssh_run
        return self._ssh(ip, cmd, timeout=timeout)
