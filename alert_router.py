#!/usr/bin/env python3
# day_trader_pro/alert_router.py — v0.2.0
# v0.2.0 (2026-11-03) — PAGE.2 + FEED.14 R5 — A TRIAGE TAKE-DOWN IS ONE LINE, NOT A STOPPED AND A STARTED ALERT.
#   The operator, 2026-11-02: "I don't need to see blind box alerts if it's a contingency take-down"; 2026-11-03 "Yes
#   to the proposal" (ruling R5: the router mutes STOPPED/STARTED for take-downs). poll_triage() follows dtp r521's
#   connection-triage files: var/feed_triage/actions.jsonl (DTP_TRIAGE_LOG) and var/feed_triage/outbox.jsonl
#   (DTP_TRIAGE_OUTBOX), the same paths feed_triage.py writes. Every takedown_intent / stand_down / wake /
#   close_wake line marks its box; a box's own DN (STOPPED) or UP (STARTED) alert from TAKEDOWN_LEAD_S before to
#   TAKEDOWN_MUTE_S after a mark is MUTED - taken (acked, so the box does not send it either), spooled and logged on
#   control as "muted", never sent - checked when its group flushes, GROUP_HOLD_S after it arrives, so a box line
#   that comes before the action line is still caught. The triage's own outbox message is the one summary line, sent as a Control
#   status line. A box's alert sent direct (critical / fallback) cannot be muted and is not. Offsets persist in
#   triage_offsets.json; a first start skips the outbox backlog and re-reads the last TAKEDOWN_MUTE_S of actions.
# v0.1.0 (2026-11-02) — PAGE.2 — CONTROL DELIVERS THE FLEET'S ALERTS: ONE PACED, PRIORITISED, GROUPED TELEGRAM QUEUE.
#   2026-11-02 09:30 and 14:19 ET a dxFeed node failure made 3, then 8+, boxes each send "BOT IS BLIND" inside a minute.
#   The operator, 2026-10-30: "I like the idea of control being informed if an issue before I find out about it,
#   because Claude code can take appropriate actions to recover the affected boxes ... while simultaneously organizing
#   the alerts and letting me know you are working on the problem"; 2026-11-02: "we need that message routing slash
#   queue triage more than ever".
#   The box half is OTV5 r71 (notifications/alert_route v5.0): a managed box writes every alert as `[alert] {json}` in
#   bot.log and sends it itself only when it is critical (always; this side dedups) or when control's ack file is
#   stale. pager.py v0.2.0 streams those lines here (ack=True) and writes this router's heartbeats and acks back to
#   each box. This router:
#     - OWNS an alert once it is SPOOLED (data/alert_router/spool-<ET date>.jsonl, flushed + fsync) and only then acks
#       it; a restart replays what was acked and not yet sent (REPLAY_S).
#     - GROUPS: BLD by cause into one episode message ("8 boxes BLIND since 14:19 ET - BARS_STALE on 1m"), boxes
#       holding open positions named first; later boxes join as one update per UPDATE_HOLD_S; SEE closes the episode
#       with one recovery message (partial recoveries name who is still blind, open first). UP, DN and same-text MSG
#       alerts collapse the same way (GROUP_HOLD_S). A group of one is sent as the box's own words.
#     - DEDUPS: an alert the box sent itself (via=direct: critical or fallback) is recorded and never re-sent; a
#       `[alerted] <id>` drops a queued copy; one id is taken once.
#     - PRIORITISES: P0 critical words not yet delivered and any group naming an open position, P1 blind/sight/stops/
#       status lines, P2 trades, P3 startups/summaries/the rest; FIFO inside a priority.
#     - PACES: at least MIN_GAP_S between sends and at most PER_MIN in any 60 s (Telegram: about 1 message a second to
#       one chat, 20 a minute to a group), a 429's retry_after holds the whole queue, 5xx/timeouts back off 2-60 s, a
#       message is DROPPED (logged by its first 80 characters) only after DELIVERY_DEADLINE_S.
#     - GOES QUIET WHEN IT CANNOT DELIVER: healthy() is false after UNHEALTHY_AFTER_S of failed sends or a stalled
#       loop; the pager then writes no heartbeat and no ack, and every box sends its own alerts within 45 s.
#     - TAKES STATUS LINES from the recovery side through the outbox (post_status(): one JSON file per line in
#       data/alert_router/outbox/, written tmp + rename): "working" joins the matching episode's message (or goes
#       alone), "recovered" marks boxes recovered, "info"/"critical" go alone. router_alive() reads health.json.
#   Credentials: the control Telegram pair in DTP_TELEGRAM_TOKEN / DTP_TELEGRAM_CHAT_ID (config.ENV_TELEGRAM_*, the
#   explicit exception: Telegram only), read at start and never printed; every logged error is scrubbed of the token.
#   Without them `run` refuses (exit 2) unless --dry-run, which prints and NEVER ACKS (boxes keep sending). One router
#   at a time (flock on data/alert_router/router.lock; a second exits 3). Not installed: install_alert_router.sh.
#   Gate: tests/check_alert_router.py.
"""Control's alert router: follow the fleet's [alert] lines and deliver them as one paced, grouped Telegram queue.

    python alert_router.py run [--dry-run]                      # follow every running box until SIGTERM
    python alert_router.py post --kind working --boxes AMD,AVGO --cause BARS_STALE "restarting the feed on AVGO"
    python alert_router.py status                               # health.json, queue depth, open episodes

The recovery side (a sub-agent, the connection-triage tool) posts through post_status() / `post`; it never needs
Telegram credentials.
"""

import argparse
import collections
import heapq
import itertools
import json
import os
import re
import signal
import sys
import threading
import time
from datetime import datetime

import config
import ettime

__version__ = "0.2.0"

STATE_DIR = os.path.join(config.DATA_DIR, "alert_router")

GROUP_HOLD_S = 20.0          # the first alert of a cause waits this long for the rest of the fleet
UPDATE_HOLD_S = 45.0         # boxes joining an announced episode are batched into one update per this
RECOVERY_HOLD_S = 20.0       # sight-restored lines are batched this long before the recovery message
EPISODE_IDLE_S = 3 * 3600.0  # an episode with no activity for this long is closed without a message
MIN_GAP_S = 1.1              # between any two sends
PER_MIN = 18                 # sends in any rolling 60 s (Telegram's group-chat limit is 20)
REQUEST_TIMEOUT_S = 10.0
DELIVERY_DEADLINE_S = 900.0
BACKOFF_START_S, BACKOFF_CAP_S = 2.0, 60.0
RETRY_AFTER_CAP_S = 120.0
UNHEALTHY_AFTER_S = 90.0     # failing sends for this long -> stop acking, boxes send their own
LOOP_STALL_S = 15.0
ACCEPT_WINDOW_S = 28.0       # a via=control alert older than this (box clock) is the box's own by now: not taken
REPLAY_S = 900.0
OUTBOX_MAX_AGE_S = 900.0
MAX_TEXT = 4000
TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

GROUP_CODES = {"UP", "DN", "MSG"}           # collapse by (code, cause / text shape)
EPISODE_CODES = {"BLD"}                     # collapse into an episode that SEE closes
P_CRIT, P_HIGH, P_TRADE, P_LOW = 0, 1, 2, 3
CODE_PRIO = {"BLD": P_HIGH, "SEE": P_HIGH, "DN": P_HIGH, "HCF": P_CRIT, "EXR": P_CRIT, "SLC": P_CRIT, "RCU": P_CRIT,
             "ENT": P_TRADE, "EXT": P_TRADE, "RCV": P_TRADE, "ADP": P_TRADE, "PHN": P_TRADE,
             "UP": P_LOW, "SUM": P_LOW, "ORF": P_LOW, "MSG": P_HIGH}
CRIT_RE = re.compile(r"EMERGENCY|CATASTROPHIC|HALT|KILL[ _-]?SWITCH|DISK|RECONCILE MISMATCH|could not be cancelled|"
                     r"LONE SHORT|GO TO TASTYTRADE NOW", re.IGNORECASE)
STATUS_KINDS = ("working", "recovered", "info", "critical")

# FEED.14 R5 — the connection triage's files (dtp tools/feed_triage.py writes them; same env names, same defaults)
TRIAGE_VAR = os.environ.get("DTP_TRIAGE_VAR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "var",
                                                          "feed_triage"))
TRIAGE_ACTIONS = os.environ.get("DTP_TRIAGE_LOG", os.path.join(TRIAGE_VAR, "actions.jsonl"))
TRIAGE_OUTBOX = os.environ.get("DTP_TRIAGE_OUTBOX", os.path.join(TRIAGE_VAR, "outbox.jsonl"))
TAKEDOWN_KINDS = {"takedown_intent", "stand_down", "stand_down_again", "wake", "close_wake"}
TAKEDOWN_LEAD_S = 300.0      # a box's DN/UP up to this long BEFORE the action line is still the take-down's
TAKEDOWN_MUTE_S = 1800.0     # ... and up to this long after it (a woken box boots, sweeps and starts in ~25 min)
MUTED_CODES = {"UP", "DN"}


def _now():
    return time.time()


def et_hm(ts):
    return datetime.fromtimestamp(float(ts), ettime.ET).strftime("%H:%M")


def scrub(text, token):
    text = str(text)
    return text.replace(token, "<token>") if token else text


def _shape(text, box):
    """A MSG alert's grouping key: its words with the box symbol, numbers and clock times blanked."""
    t = str(text or "")
    if box:
        t = t.replace(box, "{SYM}")
    t = re.sub(r"\d+(?:[.:]\d+)*", "#", t)
    return re.sub(r"\s+", " ", t).strip()[:160]


# ── the queue entry ─────────────────────────────────────────────────────────────────────────────────────────────────
class Msg:
    __slots__ = ("text", "prio", "ids", "enq", "attempts", "backoff", "not_before", "label")

    def __init__(self, text, prio, ids=(), enq=None, label=""):
        self.text = text if len(text) <= MAX_TEXT else text[:MAX_TEXT - 12] + "\n…(cut)"
        self.prio, self.ids, self.label = prio, list(ids), label
        self.enq = _now() if enq is None else enq
        self.attempts, self.backoff, self.not_before = 0, BACKOFF_START_S, 0.0


class Group:
    """UP / DN / MSG: one cause, one window, one message."""

    def __init__(self, key, code, first_ts, due):
        self.key, self.code, self.first_ts, self.due = key, code, first_ts, due
        self.members = collections.OrderedDict()      # box -> rec


class Episode:
    """One BLIND cause: who went blind when, who came back, what has been said."""

    def __init__(self, key, cause, now):
        self.key, self.cause, self.start, self.last = key, cause, now, now
        self.blind = collections.OrderedDict()        # box -> rec (currently blind)
        self.ever = collections.OrderedDict()         # box -> first rec (every box of the episode)
        self.recovered = collections.OrderedDict()    # box -> (ts, blind_for_s)
        self.announced = set()                        # boxes the operator has been told are blind
        self.due_announce = None
        self.due_recover = None
        self.pending_recover = collections.OrderedDict()   # box -> SEE rec (or status)
        self.notes = []                               # status lines waiting to ride the next message
        self.sent_any = False


class Router:
    def __init__(self, post, state_dir=None, clock=_now, log=None, spool=True):
        self.post = post                              # post(text) -> ("ok"|"retry"|"fatal", retry_after|None, why)
        self.state_dir = state_dir or STATE_DIR
        self.clock = clock
        self.log = log or (lambda m: print("alert_router: %s" % m, file=sys.stderr, flush=True))
        self.spool_on = spool
        self.lock = threading.RLock()
        self.taken = {}                               # (box, id) -> "routed" | "direct"
        self.direct_done = set()                      # (box, id) the box delivered itself
        self.open = {}                                # box -> {"refs": set, "n": int|None, "n_ts": float, "live": bool}
        self.groups = {}
        self.episodes = {}
        self.queue = []
        self.seq = itertools.count()
        self.sent_times = collections.deque()
        self.hold_until = 0.0
        self.last_send = 0.0
        self.fail_since = None
        self.last_tick = clock()
        self.sent = []                                # (ts, label, text) — what went out, for tests and status
        self.dropped = 0
        self.takedowns = {}                           # box -> [action ts, ...] from the triage action log (R5)
        self.muted = []                               # (box, code, id) muted take-down alerts, for tests and status
        self.tri_off = None                           # {path: byte offset} into the triage files
        if self.spool_on:
            os.makedirs(self.state_dir, exist_ok=True)

    # ── health ──────────────────────────────────────────────────────────────────────────────────────────────────────
    def healthy(self, now=None):
        now = self.clock() if now is None else now
        with self.lock:
            if now - self.last_tick > LOOP_STALL_S:
                return False
            return self.fail_since is None or now - self.fail_since < UNHEALTHY_AFTER_S

    # ── open positions ──────────────────────────────────────────────────────────────────────────────────────────────
    def _note_open(self, box, rec, now):
        o = self.open.setdefault(box, {"refs": set(), "n": None, "n_ts": 0.0, "live": False})
        code, ref = rec.get("code"), rec.get("ref") or ""
        if code == "UP":                              # a fresh process: its resumed positions page RCV after this
            o["refs"].clear()
            o["n"] = None
        elif code == "ENT" and ref:
            o["refs"].add(ref)
        elif code == "EXT" and ref:
            o["refs"].discard(ref)
            if o["n"]:
                o["n"] -= 1
        elif code in ("RCV", "HCF", "ADP"):
            o["refs"].add(ref or ("%s-%s" % (code, rec.get("id"))))
        if isinstance(rec.get("open"), int):
            o["n"], o["n_ts"] = rec["open"], now
            if "paper" in rec:
                o["live"] = not rec.get("paper")
        if "[LIVE]" in str(rec.get("text", "")):
            o["live"] = True

    def open_n(self, box):
        """The larger of the box's last reported count (a BLIND names it) and the ENT/EXT-tracked set: when the two
        disagree the box is treated as holding a position, because naming a flat box first costs nothing and
        burying a box with a position costs the operator the minute that matters."""
        o = self.open.get(box)
        if not o:
            return 0
        return max(o["n"] or 0, len(o["refs"]))

    def order(self, boxes):
        """Open-position boxes first (most open first), then the rest by name."""
        return sorted(boxes, key=lambda b: (0 if self.open_n(b) else 1, -self.open_n(b), b))

    def _tag(self, box, rec=None):
        n = self.open_n(box)
        if not n:
            return box
        live = self.open.get(box, {}).get("live")
        extra = ", paged by box" if rec is not None and rec.get("via") == "direct" else ""
        return "%s (%d open, %s%s)" % (box, n, "LIVE" if live else "paper", extra)

    # ── intake ──────────────────────────────────────────────────────────────────────────────────────────────────────
    def ingest_alert(self, box, rec, replay=False):
        """One [alert] from `box`. -> True when control now owns its delivery (the pager acks it)."""
        now = self.clock()
        aid = str(rec.get("id", ""))
        key = (box, aid)
        with self.lock:
            if key in self.taken:
                return self.taken[key] == "routed"
            via = rec.get("via", "control")
            if via == "control" and not replay:
                try:
                    age = now - float(rec.get("ts", now))
                except (TypeError, ValueError):
                    age = 0.0
                if age > ACCEPT_WINDOW_S:
                    self.taken[key] = "late"
                    self.log("%s: alert %s is %.0fs old - the box sends it; not taken" % (box, aid, age))
                    return False
            if via == "control" and not self.healthy(now) and not replay:
                return False                          # do not take what we cannot deliver; the box will
            if self.spool_on and not replay:
                if not self._spool({"t": "in", "box": box, "rec": rec}):
                    return False
            self.taken[key] = "routed" if via == "control" else "direct"
            if via != "control":
                self.direct_done.add(key)
            self._note_open(box, rec, now)
            self._place(box, rec, now)                # an UP/DN is held GROUP_HOLD_S; _flush_group mutes take-downs
            return via == "control"

    # ── FEED.14 R5: triage take-downs ──────────────────────────────────────────────────────────────────────────────
    def _is_takedown(self, box, rec):
        if rec.get("code") not in MUTED_CODES or CRIT_RE.search(rec.get("text", "")):
            return False
        try:
            ts = float(rec.get("ts"))
        except (TypeError, ValueError):
            ts = self.clock()
        return any(a - TAKEDOWN_LEAD_S <= ts <= a + TAKEDOWN_MUTE_S for a in self.takedowns.get(box, ()))

    def _mute(self, box, rec):
        aid = str(rec.get("id", ""))
        self.muted.append((box, rec.get("code"), aid))
        self.log("%s: %s alert %s muted - a connection-triage take-down (%s)"
                 % (box, rec.get("code"), aid, str(rec.get("text", ""))[:60]))
        self._spool({"t": "done", "ids": ["%s|%s" % (box, aid)], "muted": True})

    def poll_triage(self, actions=None, outbox=None):
        """Follow the triage's action log (take-down marks) and outbox (its summary lines). -> lines read."""
        actions, outbox = actions or TRIAGE_ACTIONS, outbox or TRIAGE_OUTBOX
        first = self.tri_off is None
        if first:
            self.tri_off = self._load_offsets()
        n = 0
        for path, is_actions in ((actions, True), (outbox, False)):
            try:
                size = os.path.getsize(path)
            except OSError:
                continue
            off = self.tri_off.get(path)
            if off is None or off > size:             # unseen, or rotated / truncated
                off = 0 if is_actions else (size if first and off is None else 0)
            if off == size:
                self.tri_off[path] = off
                continue
            try:
                with open(path, "rb") as fh:
                    fh.seek(off)
                    data = fh.read()
            except OSError:
                continue
            end = data.rfind(b"\n") + 1                # only whole lines
            for raw in data[:end].splitlines():
                try:
                    row = json.loads(raw.decode("utf-8"))
                except Exception:                           # noqa: BLE001
                    continue
                n += 1
                if is_actions:
                    self._note_takedown(row)
                else:
                    self._triage_line(row)
            self.tri_off[path] = off + end
        if n or first:
            self._save_offsets()
        return n

    def _note_takedown(self, row):
        if row.get("kind") not in TAKEDOWN_KINDS or row.get("dry") or not row.get("sym"):
            return
        try:
            at = float(row.get("at"))
        except (TypeError, ValueError):
            return
        if self.clock() - at > TAKEDOWN_MUTE_S:
            return
        with self.lock:
            self.takedowns.setdefault(str(row["sym"]), []).append(at)

    def _triage_line(self, row):
        try:
            ts = float(row.get("ts", self.clock()))
        except (TypeError, ValueError):
            ts = self.clock()
        if self.clock() - ts > OUTBOX_MAX_AGE_S:
            self.log("triage outbox line too old (%s); not sent" % str(row.get("text", ""))[:60])
            return
        st = {"kind": "info", "text": row.get("text", ""), "ts": ts, "source": row.get("source", "feed_triage")}
        self._spool({"t": "st", "st": st})
        self.ingest_status(st)

    def _offsets_path(self):
        return os.path.join(self.state_dir, "triage_offsets.json")

    def _load_offsets(self):
        try:
            with open(self._offsets_path(), encoding="utf-8") as fh:
                return {k: int(v) for k, v in json.load(fh).items()}
        except Exception:                                   # noqa: BLE001
            return {}

    def _save_offsets(self):
        if not self.spool_on:
            return
        try:
            tmp = self._offsets_path() + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.tri_off, fh)
            os.replace(tmp, self._offsets_path())
        except Exception as e:                              # noqa: BLE001
            self.log("triage offsets not saved (%s)" % type(e).__name__)

    def ingest_alerted(self, box, aid):
        """The box sent `aid` itself (control did not ack in time)."""
        with self.lock:
            self.direct_done.add((box, str(aid)))
            if self.spool_on:
                self._spool({"t": "done", "ids": ["%s|%s" % (box, aid)]})

    def _place(self, box, rec, now):
        code = rec.get("code", "MSG")
        if code in EPISODE_CODES:
            return self._blind(box, rec, now)
        if code == "SEE":
            return self._sight(box, rec, now)
        if code in GROUP_CODES and rec.get("via") == "control" and not CRIT_RE.search(rec.get("text", "")):
            gk = (code, (rec.get("cause") or "") if code != "MSG" else _shape(rec.get("text"), box))
            g = self.groups.get(gk)
            if g is None:
                g = self.groups[gk] = Group(gk, code, now, now + GROUP_HOLD_S)
            g.members[box] = rec
            return None
        if rec.get("via") != "control":
            return None                               # the box delivered it; nothing to send
        prio = CODE_PRIO.get(code, P_LOW)
        if CRIT_RE.search(rec.get("text", "")):
            prio = P_CRIT
        self._enqueue(Msg(rec.get("text", ""), prio, ["%s|%s" % (box, rec.get("id"))], now, label=code))
        return None

    def _episode_for(self, box=None, cause=None, boxes=()):
        """The open episode matching a box, a box set or a cause (prefix either way)."""
        cands = list(self.episodes.values())
        for ep in cands:
            if box and box in ep.blind:
                return ep
        for ep in cands:
            if boxes and set(boxes) & set(ep.ever):
                return ep
        if cause:
            c = str(cause).lower()
            for ep in cands:
                e = ep.cause.lower()
                if e.startswith(c) or c.startswith(e):
                    return ep
        return None

    def _blind(self, box, rec, now):
        cause = rec.get("cause") or "UNKNOWN"
        ep = self.episodes.get(("BLD", cause))
        if ep is None:
            ep = self.episodes[("BLD", cause)] = Episode(("BLD", cause), cause, now)
        ep.last = now
        ep.blind[box] = rec
        ep.ever.setdefault(box, rec)
        ep.recovered.pop(box, None)
        ep.pending_recover.pop(box, None)
        if not ep.announced and ep.due_announce is None:
            ep.due_announce = now + GROUP_HOLD_S
        elif ep.announced and box not in ep.announced and ep.due_announce is None:
            ep.due_announce = now + UPDATE_HOLD_S

    def _sight(self, box, rec, now):
        ep = self._episode_for(box=box)
        if ep is None:
            if rec.get("via") == "control":
                self._enqueue(Msg(rec.get("text", ""), P_HIGH, ["%s|%s" % (box, rec.get("id"))], now, label="SEE"))
            return
        ep.last = now
        ep.pending_recover[box] = rec
        if ep.due_recover is None:
            ep.due_recover = now + RECOVERY_HOLD_S

    def ingest_status(self, st):
        """A line from the recovery side: {"kind", "text", "boxes", "cause", "ts"}."""
        now = self.clock()
        kind = st.get("kind") if st.get("kind") in STATUS_KINDS else "info"
        text = str(st.get("text", "")).strip()
        boxes = [str(b) for b in (st.get("boxes") or [])]
        with self.lock:
            ep = self._episode_for(cause=st.get("cause"), boxes=boxes) if (st.get("cause") or boxes) else None
            if kind == "working" and ep is not None and not ep.announced:
                ep.notes.append(text)                 # rides the episode's first message
                return
            if kind == "recovered" and ep is not None:
                for b in boxes or list(ep.blind):
                    if b in ep.blind:
                        ep.pending_recover[b] = {"via": "status", "text": text}
                if text:
                    ep.notes.append(text)
                if ep.due_recover is None:
                    ep.due_recover = now + RECOVERY_HOLD_S
                return
            icon = {"working": "\U0001F6E0", "recovered": "✅", "critical": "\U0001F6A8"}.get(kind, "ℹ️")
            head = {"working": "Working on it", "recovered": "Recovered", "critical": "CONTROL",
                    "info": "Control"}[kind]
            who = (" | " + ", ".join(self._tag(b) for b in self.order(boxes))) if boxes else ""
            cause = (" | cause " + str(st.get("cause"))) if st.get("cause") else ""
            prio = P_CRIT if kind == "critical" or any(self.open_n(b) for b in boxes) else P_HIGH
            self._enqueue(Msg("%s %s: %s%s%s" % (icon, head, text, cause, who), prio, [], now, label="status"))

    # ── the clock ───────────────────────────────────────────────────────────────────────────────────────────────────
    def tick(self, now=None):
        """Flush every due group / episode message into the queue, then send what pacing allows."""
        now = self.clock() if now is None else now
        with self.lock:
            self.last_tick = now
            for gk in [k for k, g in self.groups.items() if now >= g.due]:
                self._flush_group(self.groups.pop(gk), now)
            for ek, ep in list(self.episodes.items()):
                if ep.due_announce is not None and now >= ep.due_announce:
                    self._announce(ep, now)
                if ep.due_recover is not None and now >= ep.due_recover:
                    self._recover(ep, now)
                if not ep.blind and ep.due_announce is None and ep.due_recover is None:
                    del self.episodes[ek]
                elif now - ep.last > EPISODE_IDLE_S:
                    self.log("episode %s idle %.0f min; closed (still blind: %s)"
                             % (ep.cause, (now - ep.last) / 60, ", ".join(ep.blind)))
                    del self.episodes[ek]
        self._send_due(now)

    def _flush_group(self, g, now):
        if g.code in MUTED_CODES:                     # R5: the action line may have come after the box's alert
            for b in [b for b in g.members if self._is_takedown(b, g.members[b])]:
                self._mute(b, g.members.pop(b))
            if not g.members:
                return
        boxes = self.order(list(g.members))
        ids = ["%s|%s" % (b, g.members[b].get("id")) for b in boxes]
        if len(boxes) == 1:
            rec = g.members[boxes[0]]
            self._enqueue(Msg(rec.get("text", ""), CODE_PRIO.get(g.code, P_LOW), ids, now, label=g.code))
            return
        when = et_hm(g.first_ts)
        if g.code == "UP":
            head = "\U0001F680 %d boxes STARTED %s ET%s" % (len(boxes), when,
                                                             (" (%s)" % g.key[1]) if g.key[1] else "")
            body = ["%s %s" % (self._tag(b), g.members[b].get("brief") or "") for b in boxes]
            text = head + "\n" + "\n".join(x.rstrip() for x in body)
        elif g.code == "DN":
            head = "\U0001F534 %d boxes STOPPED %s ET%s" % (len(boxes), when,
                                                             (" - " + g.key[1]) if g.key[1] else "")
            text = head + "\n" + self._listing(boxes, g.members)
        else:
            sample = g.members[boxes[0]].get("text", "")
            text = ("%d boxes, same alert since %s ET:\n" % (len(boxes), when)) + self._listing(boxes, g.members) + \
                   "\n" + sample.replace(boxes[0], "{SYM}")
        prio = P_CRIT if any(self.open_n(b) for b in boxes) and g.code != "UP" else CODE_PRIO.get(g.code, P_LOW)
        self._enqueue(Msg(text, prio, ids, now, label="group-" + g.code))

    def _listing(self, boxes, members=None):
        opened = [b for b in boxes if self.open_n(b)]
        rest = [b for b in boxes if not self.open_n(b)]
        lines = []
        if opened:
            lines.append("OPEN POSITIONS: " + ", ".join(self._tag(b, (members or {}).get(b)) for b in opened))
        if rest:
            lines.append(("Also: " if opened else "") + ", ".join(rest))
        return "\n".join(lines)

    def _announce(self, ep, now):
        new = [b for b in ep.blind if b not in ep.announced]
        ep.due_announce = None
        if not new:
            return
        recs = {b: ep.blind[b] for b in new}
        boxes = self.order(new)
        ids = ["%s|%s" % (b, recs[b].get("id")) for b in boxes]
        routed = [b for b in boxes if recs[b].get("via") == "control"]
        first = not ep.announced
        ep.announced.update(new)
        notes, ep.notes = ep.notes, []
        if first and len(boxes) == 1 and not notes:
            if routed:                               # a group of one: the box's own words
                self._enqueue(Msg(recs[boxes[0]].get("text", ""), P_HIGH, ids, now, label="BLD"))
            ep.sent_any = ep.sent_any or bool(routed)
            return
        if not routed and not notes and len(boxes) == 1:
            return                                    # the box paged it itself
        since = et_hm(min(float(ep.ever[b].get("ts", ep.start)) for b in ep.ever))
        if first:
            head = "\U0001F534 %d box%s BLIND since %s ET - cause %s" % (len(boxes), "" if len(boxes) == 1 else "es",
                                                                         since, ep.cause)
        else:
            head = "\U0001F534 +%d more BLIND (%s, since %s ET; %d blind now): " % (
                len(boxes), ep.cause, since, len(ep.blind))
        details = {str(recs[b].get("detail") or "") for b in boxes}
        lines = [head, self._listing(boxes, recs)]
        if len(details) == 1 and details != {""}:
            lines.append("detail: " + details.pop())
        for n in notes:
            lines.append("Control: " + n)
        if first and not notes:
            lines.append("Control is on it; updates follow.")
        prio = P_CRIT if any(self.open_n(b) for b in boxes) else P_HIGH
        ep.sent_any = True
        self._enqueue(Msg("\n".join(lines), prio, ids, now, label="episode-BLD"))

    def _recover(self, ep, now):
        back = list(ep.pending_recover)
        recs = dict(ep.pending_recover)
        ep.pending_recover.clear()
        ep.due_recover = None
        for b in back:
            rec = ep.blind.pop(b, None)
            if rec is not None:
                ep.recovered[b] = (now, recs[b].get("blind_for_s"))
        ids = ["%s|%s" % (b, recs[b].get("id")) for b in back if recs[b].get("id")]
        notes, ep.notes = ep.notes, []
        if len(ep.ever) == 1 and not notes:
            b = back[0] if back else None
            if b and recs[b].get("via") == "control" and ep.sent_any:
                self._enqueue(Msg(recs[b].get("text", ""), P_HIGH, ids, now, label="SEE"))
            elif b and recs[b].get("via") == "control" and not ep.sent_any:
                pass                                  # the operator never heard of it from here; the box paged both
            return
        if not back and not notes:
            return
        since = et_hm(min(float(ep.ever[b].get("ts", ep.start)) for b in ep.ever))
        if not ep.blind:
            mins = max(0.0, (now - ep.start) / 60.0)
            head = "✅ All %d boxes see again - %s episode since %s ET (%.0f min)" % (len(ep.ever), ep.cause,
                                                                                        since, mins)
        else:
            head = "✅ %d of %d recovered - %s since %s ET" % (len(ep.recovered), len(ep.ever), ep.cause, since)
        lines = [head]
        if back:
            lines.append("back now: " + ", ".join(self._tag(b) for b in self.order(back)))
        if ep.blind:
            lines.append("STILL BLIND: " + ", ".join(self._tag(b) for b in self.order(list(ep.blind))))
        for n in notes:
            lines.append("Control: " + n)
        prio = P_CRIT if any(self.open_n(b) for b in ep.blind) else P_HIGH
        self._enqueue(Msg("\n".join(lines), prio, ids, now, label="episode-SEE"))

    # ── the queue ───────────────────────────────────────────────────────────────────────────────────────────────────
    def _enqueue(self, m):
        heapq.heappush(self.queue, (m.prio, next(self.seq), m))

    def pending(self):
        with self.lock:
            return len(self.queue)

    def _all_direct(self, m):
        return bool(m.ids) and all(tuple(i.split("|", 1)) in self.direct_done for i in m.ids)

    def _send_due(self, now):
        """Send at most one message per call, when pacing allows. Called every loop tick."""
        with self.lock:
            while self.queue and self._all_direct(self.queue[0][2]):
                _p, _s, m = heapq.heappop(self.queue)
                self.log("dropped a queued %s: the box delivered it itself" % m.label)
                self._spool({"t": "done", "ids": m.ids})
            if not self.queue:
                return False
            if now < self.hold_until or now - self.last_send < MIN_GAP_S:
                return False
            while self.sent_times and now - self.sent_times[0] >= 60.0:
                self.sent_times.popleft()
            if len(self.sent_times) >= PER_MIN:
                return False
            prio, seq, m = self.queue[0]
            if now < m.not_before:
                return False
            heapq.heappop(self.queue)
        try:
            verdict, wait, why = self.post(m.text)
        except Exception as e:                                  # noqa: BLE001
            verdict, wait, why = "retry", None, "%s: %s" % (type(e).__name__, e)
        with self.lock:
            self.last_send = now
            self.sent_times.append(now)
            m.attempts += 1
            if verdict == "ok":
                self.fail_since = None
                self.sent.append((now, m.label, m.text))
                self._spool({"t": "done", "ids": m.ids})
                return True
            if self.fail_since is None:
                self.fail_since = now
            if verdict == "fatal" or now - m.enq >= DELIVERY_DEADLINE_S:
                self.dropped += 1
                self.log("DROPPED after %d attempt(s) (%s): %s" % (m.attempts, why, m.text[:80].replace("\n", " ")))
                self._spool({"t": "done", "ids": m.ids, "dropped": True})
                return False
            if wait is not None:
                self.hold_until = now + min(float(wait), RETRY_AFTER_CAP_S)     # a 429 holds the whole queue
            else:
                m.not_before = now + m.backoff
                m.backoff = min(m.backoff * 2, BACKOFF_CAP_S)
            self.log("send failed (%s); retry %d" % (why, m.attempts))
            heapq.heappush(self.queue, (prio, seq, m))
        return False

    # ── the spool ───────────────────────────────────────────────────────────────────────────────────────────────────
    def _spool_path(self, now=None):
        d = datetime.fromtimestamp(now or self.clock(), ettime.ET).date().isoformat()
        return os.path.join(self.state_dir, "spool-%s.jsonl" % d)

    def _spool(self, row):
        if not self.spool_on:
            return True
        try:
            row = dict(row, at=round(self.clock(), 3))
            with open(self._spool_path(), "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=True, separators=(",", ":")) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            return True
        except Exception as e:                                  # noqa: BLE001
            self.log("spool write failed (%s); not acking" % type(e).__name__)
            return False

    def replay(self):
        """Re-take what an earlier run acked and did not send (within REPLAY_S). -> how many."""
        now = self.clock()
        rows = []
        for path in sorted(p for p in os.listdir(self.state_dir) if p.startswith("spool-"))[-2:]:
            try:
                with open(os.path.join(self.state_dir, path), encoding="utf-8") as fh:
                    rows += [json.loads(ln) for ln in fh if ln.strip()]
            except Exception:                                   # noqa: BLE001
                continue
        done = set()
        for r in rows:
            if r.get("t") == "done":
                done.update(r.get("ids") or [])
        n = 0
        for r in rows:
            if r.get("t") != "in" or now - float(r.get("at", 0)) > REPLAY_S:
                continue
            rec, box = r.get("rec") or {}, r.get("box")
            if "%s|%s" % (box, rec.get("id")) in done:
                with self.lock:
                    self.taken[(box, str(rec.get("id")))] = "routed"
                continue
            self.ingest_alert(box, rec, replay=True)
            n += 1
        return n

    # ── the outbox (the recovery side's door) ───────────────────────────────────────────────────────────────────────
    def poll_outbox(self, outbox=None):
        outbox = outbox or os.path.join(self.state_dir, "outbox")
        try:
            names = sorted(n for n in os.listdir(outbox) if n.endswith(".json"))
        except FileNotFoundError:
            return 0
        n = 0
        for name in names:
            path = os.path.join(outbox, name)
            try:
                with open(path, encoding="utf-8") as fh:
                    st = json.load(fh)
                os.unlink(path)
            except Exception:                                   # noqa: BLE001
                continue
            if self.clock() - float(st.get("ts", self.clock())) > OUTBOX_MAX_AGE_S:
                self.log("outbox line too old (%s); not sent" % str(st.get("text", ""))[:60])
                continue
            self._spool({"t": "st", "st": st})
            self.ingest_status(st)
            n += 1
        return n

    def write_health(self, followed=()):
        try:
            h = {"ts": round(self.clock(), 3), "healthy": self.healthy(), "queue": self.pending(),
                 "episodes": [{"cause": e.cause, "blind": list(e.blind), "recovered": list(e.recovered)}
                              for e in list(self.episodes.values())],
                 "followed": sorted(followed), "dropped": self.dropped, "pid": os.getpid()}
            tmp = os.path.join(self.state_dir, "health.json.tmp")
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(h, fh)
            os.replace(tmp, os.path.join(self.state_dir, "health.json"))
        except Exception:                                       # noqa: BLE001
            pass


# ── the recovery side's interface ───────────────────────────────────────────────────────────────────────────────────
_post_n = itertools.count()


def post_status(kind, text, boxes=(), cause="", state_dir=None):
    """Queue one status line for the operator through control's router. kind: working | recovered | info | critical.
    boxes: the symbols it is about (open-position boxes are named first by the router); cause: the episode's cause
    (BARS_STALE, ...) so a "working" line joins the BLIND message it belongs to. -> the outbox file written.
    Needs no credentials; never sends anything itself."""
    if kind not in STATUS_KINDS:
        raise ValueError("kind must be one of %s" % ", ".join(STATUS_KINDS))
    outbox = os.path.join(state_dir or STATE_DIR, "outbox")
    os.makedirs(outbox, exist_ok=True)
    now = _now()
    name = "%.6f-%d-%d.json" % (now, os.getpid(), next(_post_n))
    tmp = os.path.join(outbox, "." + name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"kind": kind, "text": str(text), "boxes": [str(b) for b in boxes], "cause": str(cause or ""),
                   "ts": now}, fh)
    os.replace(tmp, os.path.join(outbox, name))
    return os.path.join(outbox, name)


def router_alive(state_dir=None, max_age_s=30.0):
    """True iff a router wrote health.json within max_age_s and called itself healthy."""
    try:
        with open(os.path.join(state_dir or STATE_DIR, "health.json"), encoding="utf-8") as fh:
            h = json.load(fh)
        return bool(h.get("healthy")) and _now() - float(h.get("ts", 0)) <= max_age_s
    except Exception:                                           # noqa: BLE001
        return False


# ── Telegram, control's pair ────────────────────────────────────────────────────────────────────────────────────────
def telegram_post(token, chat_id, timeout=REQUEST_TIMEOUT_S):
    """-> post(text) for Router. Plain text (no parse_mode can fail on a P&L line). Never logs the token."""
    import requests

    def post(text):
        try:
            r = requests.post(TELEGRAM_API.format(token=token), json={"chat_id": chat_id, "text": text},
                              timeout=timeout)
        except Exception as e:                                  # noqa: BLE001
            return "retry", None, scrub("%s: %s" % (type(e).__name__, e), token)
        code = getattr(r, "status_code", 0)
        if code == 200:
            return "ok", None, "200"
        body = scrub(getattr(r, "text", ""), token)[:160]
        if code == 429:
            try:
                wait = float((r.json().get("parameters") or {}).get("retry_after"))
            except Exception:                                   # noqa: BLE001
                wait = 5.0
            return "retry", wait, "429 %s" % body
        if 400 <= code < 500 and code != 408:
            return "fatal", None, "%d %s" % (code, body)
        return "retry", None, "%d %s" % (code, body)

    return post


def _guarded(post):
    """The notify.py test guard: under a test runner nothing reaches Telegram."""
    import notify

    def g(text):
        if notify._in_test():
            notify._CAPTURED.append(text)
            return "ok", None, "captured"
        return post(text)
    return g


def run(dry_run=False, state_dir=None, discover_fn=None, stop=None):
    import fcntl
    import pager
    state_dir = state_dir or STATE_DIR
    os.makedirs(state_dir, exist_ok=True)
    lockf = open(os.path.join(state_dir, "router.lock"), "w")
    try:
        fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("alert_router: another router holds %s; exiting" % os.path.join(state_dir, "router.lock"),
              file=sys.stderr)
        return 3
    token = os.environ.get(config.ENV_TELEGRAM_TOKEN, "")
    chat = os.environ.get(config.ENV_TELEGRAM_CHAT, "")
    if dry_run:
        def post(text):
            print("----- [alert_router dry-run] -----\n%s\n" % text, flush=True)
            return "ok", None, "dry-run"
    elif not (token and chat):
        print("alert_router: %s / %s not set; refusing to take alerts I cannot send (use --dry-run to watch)"
              % (config.ENV_TELEGRAM_TOKEN, config.ENV_TELEGRAM_CHAT), file=sys.stderr)
        return 2
    else:
        post = _guarded(telegram_post(token, chat))

    def log(m):
        print("alert_router: %s" % scrub(m, token), file=sys.stderr, flush=True)

    r = Router(post, state_dir=state_dir, log=log)
    n = r.replay()
    if n:
        log("replayed %d acked-but-unsent alert(s) from the spool" % n)
    pg = pager.Pager(out=open(os.devnull, "w"), on_alert=r.ingest_alert, on_alerted=r.ingest_alerted,
                     ack=not dry_run, healthy_fn=r.healthy)
    stop = stop or threading.Event()

    def _stop(_s, _f):
        stop.set()
        pg.stop.set()
    try:
        signal.signal(signal.SIGTERM, _stop)
        signal.signal(signal.SIGINT, _stop)
    except ValueError:
        pass                                                    # not the main thread (a test)
    follower = threading.Thread(target=pg.follow, kwargs={"discover_fn": discover_fn}, name="router-pager",
                                daemon=True)
    follower.start()
    last_health = 0.0
    while not stop.is_set():
        r.poll_outbox()
        r.poll_triage()
        r.tick()
        if time.time() - last_health >= 5.0:
            r.write_health(followed=list(pg.streams))
            last_health = time.time()
        stop.wait(0.25)
    pg.stop.set()
    follower.join(timeout=10)
    end = time.time() + 5
    while r.pending() and time.time() < end:
        r.tick()
        time.sleep(0.25)
    r.write_health()
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Control's alert router (PAGE.2).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    rp = sub.add_parser("run")
    rp.add_argument("--dry-run", action="store_true", help="print instead of sending; never acks a box")
    pp = sub.add_parser("post")
    pp.add_argument("--kind", default="info", choices=STATUS_KINDS)
    pp.add_argument("--boxes", default="")
    pp.add_argument("--cause", default="")
    pp.add_argument("text")
    sub.add_parser("status")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        return run(dry_run=a.dry_run)
    if a.cmd == "post":
        boxes = [b for b in a.boxes.split(",") if b]
        print(post_status(a.kind, a.text, boxes=boxes, cause=a.cause))
        if not router_alive():
            print("alert_router: no healthy router in the last 30 s - the line waits in the outbox (15 min)",
                  file=sys.stderr)
        return 0
    try:
        with open(os.path.join(STATE_DIR, "health.json"), encoding="utf-8") as fh:
            print(fh.read())
    except FileNotFoundError:
        print("no health.json: the router has not run")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
