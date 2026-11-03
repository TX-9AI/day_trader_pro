#!/usr/bin/env python3
"""
day_trader_pro/tools/feed_triage.py — v1.1
v1.1  2026-11-03  dtp r521 / FEED.14 — THE OPERATOR'S RULINGS, BUILT IN AS DEFAULTS (no env or config knob). The
      operator, 2026-11-03: "Yes to the proposal" (the five triage rulings). (R1) A symbol is demoted ONLY by the
      leading pre-cash theory, H4P (DEMOTE_THEORY), not by any theory that rejects it. (R2) The ranking EV is shrunk
      toward 0 until a symbol has EV_FULL_N (20) window trades: ev_rank = ev x min(n, 20) / 20 - a symbol with 5
      trades counts a quarter of its EV, 20 or more counts all of it; the stored/printed EV stays the raw mean.
      (R3) unchanged: the stand-down is an instance stop of a box proven flat. (R4) At the close minus
      LAST_ACTION_MIN (15:45 ET, 12:45 on a half day) every box THIS TOOL stood down is woken - the one action
      allowed then, and only for those boxes - so each is up for the EOD drain, the S3 push and the 16:01 EOD run;
      one message lists them. (R5) is the router's half (dtp r522 alert_router reads var/feed_triage/actions.jsonl
      and mutes the box STOPPED/STARTED alerts of a triage take-down); for it every instance stop or start is
      preceded by a "takedown_intent" action line, so the router knows before the box's own STOPPED line arrives.
v1.0  2026-11-02  dtp r521 / FEED.14 — CONTROL DECIDES WHO GETS A DXLINK SLOT WHEN THE NODES REFUSE SESSIONS.
      The operator, 2026-11-02 14:40 ET (after 129.153.134.53 began answering 502 at 14:19 and the AWS nodes
      184.195.238.144 / 54.204.44.247 refused "The number of user sessions has exceeded the configured limit"
      after ~4-6 boxes each): "We should manage our connections more actively, including standing down our worst
      performers or boxes who are flat when refusals occur". ~14:50 ET: "I don't need to see blind box alerts if
      it's a contingency take-down." The box side (OTV5 r70, FEED.13) makes each box switch nodes fast and never
      spin; this decides WHO holds the slots.

WHAT ONE PASS DOES (`python3 tools/feed_triage.py`, a oneshot; the timer runs it every 60 s)
  1. OBSERVE, read-only: fleet.get_fleet() for every box's EC2 state, then ONE base64-shipped python script per
     running box over ssh_util.ssh_map (BOX_SCRIPT below): `systemctl is-active` for candle-feed / optionsbot,
     `systemctl show -p ActiveEnterTimestamp` (one named property - never the Environment), the candle-feed
     journal's last LOOKBACK_S filtered to the feed lines, the open-position count from
     ~/options-trader/trades.db opened `?mode=ro`, the last `BLIND ALERT ... open_positions=N` line of bot.log,
     and the /etc/hosts "# TEMP 2026-11-02 dxfeed node pin" lines (read, never written).
  2. CLASSIFY each box's feed (classify_feed): LIVE / REFUSED / BLIND / CONNECTING / DOWN / STOPPED / UNKNOWN,
     from both the pre-r70 lines ("N/M candle subscriptions live", "feed stream error: ... 502 Bad Gateway",
     "... number of user sessions has exceeded ...") and r70's ("FEED.13 dxlink node X for ...",
     "FEED.13 connected on dxlink node X", "SESSION_LIMIT: ... on dxlink node X", "SESSION_LIMIT lockout cleared").
  3. RANK (rank_boxes; the formula is below) and DECIDE (Triage.step): at most ONE action per pass.
  4. ACT through the Actuator, LOG every decision to var/feed_triage/actions.jsonl, and put ONE message per action
     in the outbox (enqueue).

THE RANKING (rank_boxes) - a box's priority key, smallest first:
     key = (holding ? 0 : 1,  demoted ? 1 : 0,  -EV x min(n, 20)/20,  -n,  symbol)
  · holding = the box's trades.db has a status='open' row, OR it could not be read (UNKNOWN counts as holding:
    a box we cannot prove flat is never touched). Fallback when the DB read fails: the last BLIND ALERT line's
    open_positions=N within 30 min.
  · EV = the benchmark's window EV per trade for that symbol: mean(pnl_usd) over the operator's review CSVs
    ~/reviews/trades/YYYY-MM-DD.csv for WINDOW_START..WINDOW_END (2026-10-26..2026-11-27). pnl_usd only - the
    `fee` column is never read (fees are never inside EV). A symbol with no window trade has EV 0, n 0.
    SHRUNK FOR RANKING (R2, operator 2026-11-03): ev_rank = EV x min(n, EV_FULL_N) / EV_FULL_N, EV_FULL_N = 20 -
    linear toward 0 until 20 window trades, so one lucky or unlucky trade cannot move a box up or down the order.
  · demoted = the LEADING pre-cash theory, DEMOTE_THEORY = H4P (R1, operator 2026-11-03: by the leading theory
    only, not by any theory), loaded from ~/reviews/scripts/theories.py (not copied), rejects a probe trade of
    this symbol (strategy Breakout, entry 09:45 ET) while accepting the same probe for another fleet symbol - i.e.
    the filter excludes the SYMBOL, not a strategy or a time. Today that is SPX. theories.py unreadable, or no
    H4P in it -> no symbol is demoted and the pass says so.
  · ties: more window trades first, then the symbol name ascending - total and deterministic.

THE DECISION RULES (Triage.step), in order; the first that yields an action ends the pass:
  G0  kill switch file present (var/feed_triage/KILL, or DTP_TRIAGE_KILL) -> observe and log, act on nothing.
  G1  outside the action window -> act on nothing. The window: an exchange trading day, PREOPEN_START (09:14 ET,
      the 09:15 wake) to the close (16:00, 13:00 on a half day); NEW stand-downs and returns stop
      LAST_ACTION_MIN (15) minutes before the close.
  G1b THE CLOSE WAKE (R4, operator 2026-11-03): from the close minus LAST_ACTION_MIN (15:45 ET; 12:45 on a half
      day) to the close, every box in the stood-down list - only boxes THIS TOOL stood down - whose instance is not
      running is started, once per day, in one pass (an operation in flight is dropped: the close wins). The one
      action allowed then. One message names them; each is then left to the 16:01 EOD run (no verification).
  G2  one operation in flight at a time (a rescue or a return awaiting its verification) and ACTION_GAP_S between
      any two actions.
  R1  RESCUE. A running box R is REFUSED (session limit) on >= 2 lines spanning >= CONFIRM_S, is not stood down
      and not in its rescue cooldown. Candidates V: running, known FLAT (holding is False - never unknown), feed
      LIVE, bot active, RANKED BELOW R, not stood down, not in the victim cooldown. If R's refusing node is known
      and a candidate is LIVE on that node, only those are candidates (the slot frees on the node that refused).
      V = the LOWEST-ranked candidate. A box holding a position is NEVER a candidate. ONE V per R per
      R_COOLDOWN_S; at most MAX_STOOD_DOWN boxes down at once.
      Act: re-read V (Actuator.confirm_flat) - still flat, or abort; STAND DOWN V = stop V's EC2 instance (below);
      if R is itself known flat, restart R's candle-feed so it redials at once (a holding R is never touched and
      redials on its own). One message.
  R2  VERIFY THE RESCUE. R connects (a connect line after the stand-down) -> done, logged, no message. Not
      connected after VERIFY_S -> RESTORE: wake V again ("rather than leave both blind"), R enters its rescue
      cooldown. The "back" message is sent when V verifies (R3).
  R3  VERIFY A RETURN. V is running, optionsbot active and its feed LIVE (a connect after the wake) -> one "back"
      message, V leaves the stood-down list (and is not chosen again for VICTIM_COOLDOWN_S). V REFUSED after a
      slot-return -> stood down again (one message), its next try backs off RETURN_RETRY_S x2^k, and after
      MAX_FAILED_RETURNS failures it stays down for the day. Not verified in RETURN_VERIFY_S -> one message saying
      so, and V is left running.
  R4  RETURN WHEN A SLOT FREES. No running box is REFUSED and none has been for QUIET_S; V has been down
      >= MIN_DOWN_S; and a slot has plausibly freed: fewer LIVE feeds than when V went down, or the box V went down
      for is no longer running, or RETURN_PROBE_S has passed since V went down / last tried. The best-ranked
      eligible V returns first. NODE GATE: V does not return while the dxlink node it last used (or its /etc/hosts
      pin) is down/unreachable in a fresh (<= NODE_STATUS_FRESH_S) tools/dxlink_probe.py status file, nor while
      that file is fresh and shows no node up.

THE STAND-DOWN IS AN INSTANCE STOP, NOT A FEED STOP (operator ~14:50 ET: "I don't need to see blind box alerts if
  it's a contingency take-down"). A stopped feed under a running bot trips the bot's own BlindnessLatch (45 s,
  three ticks) and the box pages BLIND straight to Telegram (OTV5 TG.1 sends from the box); suppressing it
  needs the alert router (b_alertroute) on the boxes, which is not built and is box code under the benchmark
  freeze. A stopped instance cannot page BLIND at all. The Actuator calls wake_and_bake's own stage functions,
  stage_shutdown / stage_wake, on that ONE box (instance_registry.discover([SYM])), not wake_and_bake.run(), so
  wake_and_bake's own "🛠️ wake_and_bake [...]" Telegram is not sent either. Trade-off: while stopped the box
  writes nothing - no bars, no S3 push, no EOD drain - until it is woken (here, or by the 09:15 wake); s3_push
  catches up then. The bot's own one-line STOPPED / STARTED messages (BOX.9) still go out from the box. A
  returning box that is refused can page BLIND once (the latch pages once per outage) before R3 stops it again.

ONLY THESE ACTIONS EXIST: stop one flat box's instance, start an instance this tool stopped, restart candle-feed on
  a refused box that is known flat. No reboot, no bot restart, no code/config/env edit, no /etc/hosts edit, and a
  box this tool did not stand down is never started.

MESSAGES: no control Telegram queue exists yet (dtp notify.py sends directly; the router is being built), so
  every message is a JSON line appended to the outbox var/feed_triage/outbox.jsonl (DTP_TRIAGE_OUTBOX) for the
  router to drain. Nothing here sends to Telegram.

    venv/bin/python tools/feed_triage.py              # one pass
    venv/bin/python tools/feed_triage.py --dry-run    # observe, rank and print the decision; act, save, enqueue nothing
    venv/bin/python tools/feed_triage.py --order      # the priority order now (the 09:15 wake's connect order)
    venv/bin/python tools/feed_triage.py --status     # stored state
"""
import argparse
import base64
import csv
import fcntl
import glob
import importlib.util
import json
import os
import re
import sys
import time
from datetime import date, datetime, time as dtime, timedelta, timezone
UTC = timezone.utc

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

__version__ = "1.1"

# ── tunables (seconds unless named) ──────────────────────────────────────────────────────────────────────
LOOKBACK_S = 900            # journal read per pass; >= 3x the longest r70 lockout wait (300 s)
CONFIRM_S = 90              # a refusal must span this long (and >= 2 lines) before a rescue
VERIFY_S = 420              # a rescued box must connect within this (r70 hold <= 300 s; pre-r70 backoff <= 60 s)
RETURN_VERIFY_S = 1500      # a woken box: boot + boot sweep + bot + feed connect
ACTION_GAP_S = 120          # between any two actions
R_COOLDOWN_S = 1800         # one rescue per refused box per 30 min
VICTIM_COOLDOWN_S = 1800    # a box that just came back is not stood down again for 30 min
MIN_DOWN_S = 900            # a stood-down box stays down at least 15 min (unless restored)
QUIET_S = 600               # no refusal anywhere for 10 min before a return
RETURN_PROBE_S = 1800       # with no other sign of a free slot, try a return every 30 min
RETURN_RETRY_S = 1800       # after a refused return: 30 min, 60 min, ...
MAX_FAILED_RETURNS = 2      # then the box stays down for the day
MAX_STOOD_DOWN = 4
LAST_ACTION_MIN = 15        # new stand-downs and slot returns stop here; the R4 close wake happens here
PREOPEN_START = dtime(9, 14)
BLIND_FALLBACK_S = 1800     # the BLIND ALERT open_positions fallback is trusted for 30 min
NODE_STATUS_FRESH_S = 600
WINDOW_START = "2026-10-26"
WINDOW_END = "2026-11-27"
DEMOTE_THEORY = "H4P"       # R1 (operator 2026-11-03): demote by the leading pre-cash theory only
THEORY_IDS = (DEMOTE_THEORY,)
EV_FULL_N = 20              # R2: ranking EV = ev x min(n, EV_FULL_N) / EV_FULL_N (shrunk toward 0 below 20 trades)

VAR_DIR = os.environ.get("DTP_TRIAGE_VAR", os.path.join(ROOT, "var", "feed_triage"))
STATE_PATH = os.environ.get("DTP_TRIAGE_STATE", os.path.join(VAR_DIR, "state.json"))
ACTIONS_LOG = os.environ.get("DTP_TRIAGE_LOG", os.path.join(VAR_DIR, "actions.jsonl"))
OUTBOX = os.environ.get("DTP_TRIAGE_OUTBOX", os.path.join(VAR_DIR, "outbox.jsonl"))
KILL_PATH = os.environ.get("DTP_TRIAGE_KILL", os.path.join(VAR_DIR, "KILL"))
LOCK_PATH = os.path.join(VAR_DIR, "lock")
NODE_STATUS = os.environ.get("DTP_DXPROBE_STATUS", os.path.join(VAR_DIR, "dxlink_nodes_status.json"))
TRADES_GLOB = os.environ.get("DTP_TRIAGE_TRADES", os.path.expanduser("~/reviews/trades/20*.csv"))
THEORIES = os.environ.get("DTP_TRIAGE_THEORIES", os.path.expanduser("~/reviews/scripts/theories.py"))

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:                                                              # noqa: BLE001
    ET = None


# ══ messages ══════════════════════════════════════════════════════════════════════════════════════════════
def enqueue(text, source="feed_triage", path=None):
    """Append one message to the outbox (JSON line). The ONLY way this tool (and dxlink_probe) talks to the
    operator; the router drains it. Never sends anything itself."""
    p = path or OUTBOX
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": round(time.time(), 3), "source": source, "text": text}) + "\n")


def _log_action(rec, path=None):
    p = path or ACTIONS_LOG
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")


# ══ the box script: read-only, the one thing that runs on a box ═══════════════════════════════════════════
BOX_SCRIPT = r'''
import json, os, re, sqlite3, subprocess, sys
LOOK = int(sys.argv[1]) if len(sys.argv) > 1 else 900
H = os.path.expanduser("~/options-trader")
FEED_RE = re.compile(r"candle subscriptions live|connected on dxlink node|FEED\.13 dxlink node|SESSION_LIMIT|"
                     r"user sessions|feed stream error|Bad Gateway|\b502\b", re.I)
SECRET = re.compile(r"[A-Za-z0-9_\-+/=]{32,}")
def sh(argv):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception as e:
        return "ERR %s" % type(e).__name__
out = {"v": 1}
out["feed"] = sh(["systemctl", "is-active", "candle-feed"])
out["bot"] = sh(["systemctl", "is-active", "optionsbot"])
out["feed_since"] = sh(["systemctl", "show", "candle-feed", "-p", "ActiveEnterTimestamp", "--value"])
ev = []
j = sh(["journalctl", "-u", "candle-feed", "--since", "%d seconds ago" % LOOK, "-o", "short-unix",
        "--no-pager", "-q"])
for line in j.splitlines():
    if FEED_RE.search(line):
        ts, _, rest = line.partition(" ")
        try:
            ev.append([float(ts), SECRET.sub("<redacted>", rest)[:300]])
        except ValueError:
            pass
out["events"] = ev[-80:]
try:
    c = sqlite3.connect("file:" + os.path.join(H, "trades.db") + "?mode=ro", uri=True, timeout=5)
    out["open"] = int(c.execute("SELECT COUNT(*) FROM trades WHERE status='open'").fetchone()[0])
    c.close()
except Exception as e:
    out["open"] = None
    out["open_err"] = "%s" % type(e).__name__
try:
    p = os.path.join(H, "bot.log")
    with open(p, "rb") as fh:
        fh.seek(max(0, os.path.getsize(p) - 1048576))
        tail = fh.read().decode("utf-8", "replace").splitlines()
    b = [l for l in tail if "BLIND ALERT |" in l and "open_positions=" in l]
    if b:
        m = re.match(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)", b[-1])
        n = re.search(r"open_positions=(\d+)", b[-1])
        out["blind"] = [m.group(1) if m else None, int(n.group(1)) if n else None]
except Exception:
    pass
try:
    with open("/etc/hosts") as fh:
        out["pins"] = [l.split()[0] for l in fh if "dxfeed node pin" in l and l.strip() and not l.startswith("#")]
except Exception:
    out["pins"] = []
print("TRIAGE_JSON " + json.dumps(out))
'''


def box_command(lookback=LOOKBACK_S):
    b64 = base64.b64encode(BOX_SCRIPT.encode()).decode()
    return "echo %s | base64 -d | python3 - %d" % (b64, int(lookback))


def parse_box_output(text):
    for line in (text or "").splitlines():
        if line.startswith("TRIAGE_JSON "):
            try:
                return json.loads(line[len("TRIAGE_JSON "):])
            except ValueError:
                return None
    return None


# ══ classification ════════════════════════════════════════════════════════════════════════════════════════
NODE_RE = re.compile(r"dxlink node (\d{1,3}(?:\.\d{1,3}){3}|dns)")


def classify_line(text):
    """One candle-feed line -> (kind, node). kind: CONNECT / REFUSED / BLIND502 / ERROR / DIAL / None."""
    t = text or ""
    low = t.lower()
    m = NODE_RE.search(t)
    node = m.group(1) if m else None
    if node == "dns":
        node = None
    if "candle subscriptions live" in low or "connected on dxlink node" in low or "lockout cleared" in low:
        return "CONNECT", node
    if "session_limit:" in low or "user sessions has exceeded" in low or "number of user sessions" in low:
        return "REFUSED", node
    if "feed stream error" in low:
        if "502" in t or "bad gateway" in low:
            return "BLIND502", node
        return "ERROR", node
    if "feed.13 dxlink node" in low:
        return "DIAL", node
    return None, node


def _parse_since(s):
    """`Mon 2026-11-02 14:15:22 UTC` (the box clock is UTC) -> epoch, else None."""
    try:
        parts = (s or "").split()
        d = datetime.strptime(" ".join(parts[1:3]), "%Y-%m-%d %H:%M:%S")
        from datetime import timezone
        return d.replace(tzinfo=timezone.utc).timestamp()
    except (ValueError, IndexError):
        return None


def _blind_epoch(stamp):
    try:
        from datetime import timezone
        return datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
    except (TypeError, ValueError):
        return None


def classify_box(sym, ec2_state, raw, now, lookback=LOOKBACK_S):
    """-> observation dict for one box. `raw` is the box script's JSON (None = unreadable)."""
    o = {"sym": sym, "ec2": ec2_state, "state": "UNKNOWN", "holding": None, "node": None, "bot_active": False,
         "refused_since": None, "refusals": 0, "last_connect": None, "pins": [], "detail": ""}
    if ec2_state != "running":
        o["state"] = "STOPPED"
        o["holding"] = None
        return o
    if not raw:
        o["detail"] = "box unreadable"
        return o
    o["bot_active"] = raw.get("bot") == "active"
    o["pins"] = list(raw.get("pins") or [])
    # holding: the DB first; a failed read falls back to a FRESH BLIND ALERT line; else unknown (= protected)
    if isinstance(raw.get("open"), int):
        o["holding"] = raw["open"] > 0
        o["open"] = raw["open"]
    else:
        b = raw.get("blind") or [None, None]
        be = _blind_epoch(b[0])
        if be is not None and now - be <= BLIND_FALLBACK_S and isinstance(b[1], int):
            o["holding"] = b[1] > 0
            o["open"] = b[1]
            o["detail"] = "positions from BLIND ALERT line"
        else:
            o["holding"] = None
            o["detail"] = "positions unknown (%s)" % raw.get("open_err", "?")
    feed = raw.get("feed")
    if feed != "active":
        o["state"] = "DOWN"
        return o
    evs = sorted((float(t), s) for t, s in (raw.get("events") or []))
    last_kind, last_node, refused = None, None, []
    for t, s in evs:
        kind, node = classify_line(s)
        if node:
            last_node = node
        if kind is None or kind == "DIAL":
            continue
        last_kind = kind
        if kind == "CONNECT":
            o["last_connect"] = t
            refused = []
        elif kind == "REFUSED":
            refused.append((t, node))
        else:
            refused = []
    o["node"] = last_node or (o["pins"][0] if o["pins"] else None)
    since = _parse_since(raw.get("feed_since"))
    if last_kind == "CONNECT":
        o["state"] = "LIVE"
    elif last_kind == "REFUSED":
        o["state"] = "REFUSED"
        o["refused_since"] = refused[0][0] if refused else None
        o["refusals"] = len(refused)
        o["refused_node"] = next((n for _t, n in reversed(refused) if n), None) or o["node"]
    elif last_kind in ("BLIND502", "ERROR"):
        o["state"] = "BLIND"
        o["detail"] = (o["detail"] + " 502" if last_kind == "BLIND502" else o["detail"]).strip()
    elif since is not None and now - since > lookback:
        # every failed attempt logs a line within <= 300 s, so a feed quiet for the whole lookback is connected
        o["state"] = "LIVE"
    else:
        o["state"] = "CONNECTING"
    return o


# ══ ranking ═══════════════════════════════════════════════════════════════════════════════════════════════
def load_window_ev(pattern=None, start=WINDOW_START, end=WINDOW_END):
    """{sym: (ev_per_trade, n)} from the review CSVs in the window. pnl_usd only; `fee` is never read."""
    acc = {}
    for fn in sorted(glob.glob(pattern or TRADES_GLOB)):
        day = os.path.basename(fn)[:10]
        if not (start <= day <= end):
            continue
        try:
            with open(fn, newline="", encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    v = r.get("pnl_usd")
                    if v in (None, "") or not r.get("sym"):
                        continue
                    s, n = acc.get(r["sym"], (0.0, 0))
                    acc[r["sym"]] = (s + float(v), n + 1)
        except (OSError, ValueError):
            continue
    return {k: (s / n, n) for k, (s, n) in acc.items() if n}


def load_theory_filters(path=None):
    """{id: predicate} for THEORY_IDS, loaded from the operator's theories.py. (filters, error)."""
    p = path or THEORIES
    try:
        spec = importlib.util.spec_from_file_location("_triage_theories", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        got = {}
        for label, f in getattr(mod, "FILTERS", []):
            tid = label.split()[0]
            if tid in THEORY_IDS:
                got[tid] = f
        return got, None
    except Exception as exc:                                                   # noqa: BLE001
        return {}, "theories unreadable (%s: %s)" % (type(exc).__name__, exc)


def demoted_symbols(symbols, filters):
    """Symbols some filter excludes BY SYMBOL: it rejects this symbol's probe trade and accepts another's."""
    def probe(s):
        return {"sym": s, "strat": "Breakout", "pnl": 0.0, "day": WINDOW_START, "sec": 9 * 3600 + 45 * 60}
    out = {}
    for s in symbols:
        for tid in sorted(filters):
            f = filters[tid]
            try:
                if not f(probe(s)) and any(f(probe(t)) for t in symbols if t != s):
                    out.setdefault(s, []).append(tid)
            except Exception:                                                  # noqa: BLE001
                continue
    return out


def shrunk_ev(e, n, full_n=EV_FULL_N):
    """R2: a small sample's EV counts in proportion to its trade count, up to full_n trades."""
    return float(e) * min(int(n), full_n) / float(full_n)


def rank_key(sym, holding, ev, demoted):
    e, n = ev.get(sym, (0.0, 0))
    return (0 if holding is not False else 1, 1 if sym in demoted else 0, -round(shrunk_ev(e, n), 6), -n, sym)


def rank_boxes(symbols, holding, ev, demoted):
    """[sym, ...] highest priority first. holding: {sym: True/False/None}; None counts as holding."""
    return sorted(symbols, key=lambda s: rank_key(s, holding.get(s), ev, demoted))


# ══ the action window ═════════════════════════════════════════════════════════════════════════════════════
def _calendar(d):
    try:
        import market_calendar
        return market_calendar.is_trading_day(d), market_calendar.is_half_day(d)
    except Exception:                                                          # noqa: BLE001
        return d.weekday() < 5, False


def window(now, calendar=None):
    """(acts_allowed, new_actions_allowed, why) for epoch `now`."""
    t = datetime.fromtimestamp(now, ET)
    trading, half = (calendar or _calendar)(t.date())
    if not trading:
        return False, False, "not a trading day"
    close = dtime(13, 0) if half else dtime(16, 0)
    if t.time() < PREOPEN_START or t.time() >= close:
        return False, False, "outside %s-%s ET" % (PREOPEN_START.strftime("%H:%M"), close.strftime("%H:%M"))
    last = (datetime.combine(t.date(), close) - timedelta(minutes=LAST_ACTION_MIN)).time()
    if t.time() >= last:
        return True, False, "within %d min of the close: verifications only" % LAST_ACTION_MIN
    return True, True, "open"


# ══ node status (tools/dxlink_probe.py) ═══════════════════════════════════════════════════════════════════
def load_node_status(path=None):
    try:
        with open(path or NODE_STATUS, encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def node_gate(status, node, now):
    """(ok, why) - may a box whose last node is `node` be woken now?"""
    if not status or now - float(status.get("probed_at") or 0) > NODE_STATUS_FRESH_S:
        return True, "node status stale or absent - not gating"
    nodes = status.get("nodes") or {}
    if not any(n.get("state") == "up" for n in nodes.values()):
        return False, "no dxlink node is up (control probe)"
    if node and node in nodes and nodes[node].get("state") != "up":
        return False, "its node %s is %s (control probe)" % (node, nodes[node].get("state"))
    return True, "node ok"


# ══ the engine ════════════════════════════════════════════════════════════════════════════════════════════
def _et(t):
    return datetime.fromtimestamp(t, ET).strftime("%H:%M ET") if t else "?"


def _money(v):
    return ("-$%.2f" % -v) if v < 0 else ("$%.2f" % v)


class Triage:
    """One pass = step(). The Actuator does the four things this tool can do; `dry` never calls it."""

    def __init__(self, actuator, dry=False, notify=None, log=None, kill_path=None, calendar=None,
                 node_status=None):
        self.act = actuator
        self.dry = dry
        self.notify = notify or enqueue
        self.log = log or _log_action
        self.kill_path = kill_path or KILL_PATH
        self.calendar = calendar
        self.node_status = node_status if node_status is not None else load_node_status()
        self.lines = []
        self.messages = []

    def say(self, s):
        self.lines.append(s)
        print("[triage] " + s)

    def _msg(self, text):
        self.messages.append(text)
        if self.dry:
            self.say("DRY RUN - would enqueue: " + text)
        else:
            self.notify(text)

    def _record(self, kind, sym, reason, now, **kw):
        rec = dict(kind=kind, sym=sym, reason=reason, at=round(now, 1), dry=self.dry, **kw)
        if not self.dry:
            self.log(rec)
        self.say("ACTION %s %s - %s" % (kind, sym, reason))

    def step(self, state, obs, ev, demoted, now):
        """state: the persisted dict (mutated copy returned). obs: {sym: classify_box()}. -> new state."""
        st = json.loads(json.dumps(state or {}))
        today = datetime.fromtimestamp(now, ET).strftime("%Y-%m-%d")
        if st.get("day") != today:                   # the 09:15 wake brings every box up: a fresh day
            st = {"day": today}
        for k in ("stood_down", "r_cooldown", "victim_cooldown"):
            st.setdefault(k, {})
        st.setdefault("op", None)
        st.setdefault("last_action_at", 0)
        st.setdefault("last_refusal_at", 0)
        holding = {s: o.get("holding") for s, o in obs.items()}
        for s in st["stood_down"]:                   # stopped by this tool only when proven flat; it ranks as flat
            if s in holding and obs[s]["ec2"] != "running":
                holding[s] = False
        order = rank_boxes(sorted(obs), holding, ev, demoted)
        pos = {s: i for i, s in enumerate(order)}
        st["order"] = order
        if any(o["state"] == "REFUSED" for s, o in obs.items() if s not in st["stood_down"]):
            st["last_refusal_at"] = now
        self.say("order: " + " > ".join("%s%s" % (s, "*" if holding.get(s) is not False else "") for s in order)
                 + "   (* holding or unknown)")
        for s in order:
            o = obs[s]
            self.say("  %-6s %-10s holding=%-5s node=%-15s bot=%s %s" % (
                s, o["state"] + ("/SD" if s in st["stood_down"] else ""), o.get("holding"), o.get("node") or "-",
                "up" if o.get("bot_active") else "-", o.get("detail", "")))

        # G0 / G1
        if os.path.exists(self.kill_path):
            self.say("KILL SWITCH %s present - observing only, no action" % self.kill_path)
            return st
        acts, new_ok, why = window(now, self.calendar)
        if not acts:
            self.say("action window closed (%s) - observing only" % why)
            return st
        # G1b - the close wake (R4)
        if not new_ok:
            if st["stood_down"] and not st.get("close_wake_at"):
                return self._close_wake(st, obs, now)
        # R2 / R3 - an operation in flight
        op = st.get("op")
        if op:
            return self._verify(st, op, obs, ev, pos, now)
        if not new_ok:
            self.say("no new stand-down or return: %s" % why)
            return st
        if now - float(st.get("last_action_at") or 0) < ACTION_GAP_S:
            self.say("action gap: last action %.0fs ago" % (now - st["last_action_at"]))
            return st
        # R1 - rescue
        for r in order:
            o = obs[r]
            if r in st["stood_down"] or o["state"] != "REFUSED":
                continue
            if o["refusals"] < 2 or o["refused_since"] is None or now - o["refused_since"] < CONFIRM_S:
                self.say("%s refused, not yet confirmed (%d line(s))" % (r, o["refusals"]))
                continue
            if now < float(st["r_cooldown"].get(r, 0)):
                self.say("%s refused, in rescue cooldown until %s" % (r, _et(st["r_cooldown"][r])))
                continue
            if len(st["stood_down"]) >= MAX_STOOD_DOWN:
                self.say("%s refused, but %d box(es) are already stood down (cap)" % (r, MAX_STOOD_DOWN))
                break
            cand = [v for v in order
                    if v != r and pos[v] > pos[r] and v not in st["stood_down"]
                    and obs[v]["holding"] is False and obs[v]["state"] == "LIVE" and obs[v].get("bot_active")
                    and obs[v]["ec2"] == "running" and now >= float(st["victim_cooldown"].get(v, 0))]
            if not cand:
                self.say("%s refused - no flat, live, lower-ranked box to stand down" % r)
                continue
            rn = o.get("refused_node")
            same = [v for v in cand if rn and obs[v].get("node") == rn]
            v = (same or cand)[-1]
            return self._rescue(st, r, v, obs, ev, demoted, pos, len(order), now, same_node=bool(same))
        # R4 - returns
        if st["stood_down"]:
            busy = [s for s, o in obs.items() if o["state"] == "REFUSED" and s not in st["stood_down"]]
            if busy:
                self.say("returns held: %s refused now" % ", ".join(sorted(busy)))
                return st
            if now - float(st.get("last_refusal_at") or 0) < QUIET_S:
                self.say("returns held: last refusal %.0fs ago (< %ds)" % (now - st["last_refusal_at"], QUIET_S))
                return st
            live_now = sum(1 for o in obs.values() if o["state"] == "LIVE")
            for v in sorted(st["stood_down"], key=lambda s: pos.get(s, 99)):
                sd = st["stood_down"][v]
                if sd.get("failed_returns", 0) >= MAX_FAILED_RETURNS:
                    continue
                if now < float(sd["at"]) + MIN_DOWN_S or now < float(sd.get("next_return_at") or 0):
                    continue
                fr = sd.get("for")
                signal = None
                if live_now < int(sd.get("live_at", 0)):
                    signal = "fewer live feeds (%d) than at the stand-down (%d)" % (live_now, sd["live_at"])
                elif fr and (fr not in obs or obs[fr]["ec2"] != "running"):
                    signal = "%s, the box it stood down for, is no longer running" % fr
                elif now - max(float(sd["at"]), float(sd.get("tried_at") or 0)) >= RETURN_PROBE_S:
                    signal = "periodic return probe (%d min quiet)" % (QUIET_S // 60)
                if not signal:
                    continue
                ok, nwhy = node_gate(self.node_status, sd.get("node"), now)
                if not ok:
                    self.say("%s not returned: %s" % (v, nwhy))
                    continue
                return self._wake(st, v, "slot", signal, now)
        return st

    def _rescue(self, st, r, v, obs, ev, demoted, pos, total, now, same_node):
        o, ov = obs[r], obs[v]
        if not self.dry and not self.act.confirm_flat(v):
            self.say("ABORT stand-down of %s: the fresh re-read did not prove it flat" % v)
            st["victim_cooldown"][v] = now + ACTION_GAP_S
            return st
        reason = ("%s (rank %d/%d%s) refused by the session limit on node %s since %s; %s is the lowest-ranked "
                  "flat live box%s" % (r, pos[r] + 1, total, ", holding" if o["holding"] is not False else "",
                                       o.get("refused_node") or "?", _et(o["refused_since"]), v,
                                       " on that node" if same_node else ""))
        e, n = ev.get(v, (0.0, 0))
        if not self.dry:
            self._record("takedown_intent", v, "stopping the instance", now)    # R5: the router mutes before DN
            if not self.act.stop_instance(v):
                self._record("stand_down_failed", v, reason, now)
                st["victim_cooldown"][v] = now + VICTIM_COOLDOWN_S
                st["last_action_at"] = now
                return st
            if obs[r]["holding"] is False:
                self.act.kick_feed(r)
        self._record("stand_down", v, reason, now, for_sym=r, kicked=obs[r]["holding"] is False)
        live = sum(1 for x in obs.values() if x["state"] == "LIVE")
        st["stood_down"][v] = {"at": now, "for": r, "node": ov.get("node"), "live_at": live, "failed_returns": 0}
        st["op"] = {"kind": "rescue", "r": r, "v": v, "at": now}
        st["last_action_at"] = now
        st["r_cooldown"][r] = now + R_COOLDOWN_S
        self._msg("FEED TRIAGE | STOOD DOWN %s (flat, rank %d/%d, window EV %s/trade over %d%s) | for %s "
                  "(refused: user session limit, node %s, since %s%s) | instance stopped, no BLIND alerts; "
                  "returns automatically when a slot frees"
                  % (v, pos[v] + 1, total, _money(e), n, ", theory-demoted" if v in demoted else "", r,
                     o.get("refused_node") or "?", _et(o["refused_since"]),
                     ", holding" if o["holding"] is not False else ""))
        return st

    def _close_wake(self, st, obs, now):
        """R4: at the close minus LAST_ACTION_MIN, start every box this tool stood down (and only those)."""
        woke, up, failed = [], [], []
        for v in sorted(st["stood_down"]):
            if obs.get(v, {}).get("ec2") == "running":
                self._record("close_wake_skip", v, "already running", now)
                up.append(v)
                continue
            if not self.dry:
                self._record("takedown_intent", v, "starting the instance (close wake)", now)
            if self.dry or self.act.start_instance(v):
                self._record("close_wake", v, "%d min before the close: up for the EOD run" % LAST_ACTION_MIN, now)
                woke.append(v)
            else:
                self._record("close_wake_failed", v, "start_instance failed", now)
                failed.append(v)
        st["stood_down"] = {}
        st["op"] = None
        st["close_wake_at"] = now
        st["last_action_at"] = now
        text = "🔌 Close wake %s: %s started for the EOD run (stood down by connection triage today)" % (
            _et(now), ", ".join(woke) if woke else "none")
        if up:
            text += "; already up: %s" % ", ".join(up)
        if failed:
            text += "; START FAILED: %s" % ", ".join(failed)
        self._msg(text)
        return st

    def _wake(self, st, v, why, signal, now):
        if not self.dry:
            self._record("takedown_intent", v, "starting the instance (%s)" % why, now)
        if not self.dry and not self.act.start_instance(v):
            self._record("wake_failed", v, signal, now)
            st["stood_down"][v]["tried_at"] = now
            st["last_action_at"] = now
            return st
        self._record("wake", v, "%s: %s" % (why, signal), now)
        st["stood_down"][v]["tried_at"] = now
        st["op"] = {"kind": "return", "v": v, "why": why, "at": now}
        st["last_action_at"] = now
        return st

    def _verify(self, st, op, obs, ev, pos, now):
        if op["kind"] == "rescue":
            r, v = op["r"], op["v"]
            o = obs.get(r) or {}
            if o.get("state") == "LIVE" and (o.get("last_connect") or 0) >= op["at"] - 5:
                self._record("rescued", r, "connected after %s stood down" % v, now)
                st["op"] = None
            elif o.get("state") == "LIVE" and o.get("last_connect") is None and now - op["at"] >= LOOKBACK_S:
                self._record("rescued", r, "feed quiet-live after %s stood down" % v, now)
                st["op"] = None
            elif now - op["at"] >= VERIFY_S:
                self.say("%s still not connected %.0fs after %s stood down - restoring %s" % (r, now - op["at"], v, v))
                st["r_cooldown"][r] = now + R_COOLDOWN_S
                st["op"] = None
                return self._wake(st, v, "restore", "%s still refused after the freed slot" % r, now)
            else:
                self.say("rescue in flight: %s %s, %.0fs of %ds" % (r, o.get("state"), now - op["at"], VERIFY_S))
            return st
        v = op["v"]
        o = obs.get(v) or {}
        sd = st["stood_down"].get(v, {})
        if (o.get("ec2") == "running" and o.get("bot_active") and o.get("state") == "LIVE"
                and (o.get("last_connect") or now) >= op["at"]):
            down_min = (now - float(sd.get("at", now))) / 60.0
            self._msg("FEED TRIAGE | BACK %s | feed live on node %s, bot active | down %.0f min (%s)"
                      % (v, o.get("node") or "?", down_min, "restored: the rescue did not take"
                         if op["why"] == "restore" else "a slot freed"))
            self._record("back", v, op["why"], now)
            st["stood_down"].pop(v, None)
            st["victim_cooldown"][v] = now + VICTIM_COOLDOWN_S
            st["op"] = None
        elif (op["why"] == "slot" and o.get("state") == "REFUSED" and o.get("refusals", 0) >= 2
              and o.get("holding") is False):
            k = int(sd.get("failed_returns", 0)) + 1
            if not self.dry:
                self._record("takedown_intent", v, "stopping the instance again", now)
            if not self.dry and not self.act.stop_instance(v):
                self._record("restop_failed", v, "refused on return", now)
                st["op"] = None
                st["stood_down"].pop(v, None)
                return st
            sd["failed_returns"] = k
            sd["next_return_at"] = now + RETURN_RETRY_S * (2 ** (k - 1))
            sd["at"] = sd.get("at", now)
            st["stood_down"][v] = sd
            st["op"] = None
            st["last_action_at"] = now
            self._record("stand_down_again", v, "refused on return (%d)" % k, now)
            self._msg("FEED TRIAGE | %s STAYS DOWN | its return was refused (user session limit) | %s"
                      % (v, "next try %s" % _et(sd["next_return_at"]) if k < MAX_FAILED_RETURNS
                         else "no more tries today"))
        elif now - op["at"] >= RETURN_VERIFY_S:
            self._msg("FEED TRIAGE | %s WOKEN, NOT VERIFIED | %.0f min after the wake: ec2 %s, bot %s, feed %s | "
                      "left running" % (v, (now - op["at"]) / 60, o.get("ec2"),
                                        "active" if o.get("bot_active") else "not active", o.get("state")))
            self._record("back_unverified", v, op["why"], now)
            st["stood_down"].pop(v, None)
            st["op"] = None
        else:
            self.say("return in flight: %s ec2=%s feed=%s, %.0fs of %ds" % (
                v, o.get("ec2"), o.get("state"), now - op["at"], RETURN_VERIFY_S))
        return st


# ══ the real world: observation and the actuator ══════════════════════════════════════════════════════════
def observe(only=None, timeout=60, now=None):
    """{sym: classify_box()} for every fleet box. Read-only."""
    import fleet
    import ssh_util
    import instance_registry
    now = now or time.time()
    # the TAGGED fleet only - never fleet.default_scope(), which adds any running untagged box (SPX-TEST)
    rows = fleet.get_fleet(only or instance_registry.fleet_members())
    running = [(s, ip) for s, ip, st in rows if st == "running" and ip]
    res = ssh_util.ssh_map(running, box_command(), timeout=timeout) if running else {}
    out = {}
    for s, ip, st in rows:
        raw = None
        if st == "running" and s in res:
            rc, so, _se = res[s]
            raw = parse_box_output(so)
        out[s] = classify_box(s, st, raw, now)
        out[s]["ip"] = ip
    return out


class Actuator:
    """The four actions. Each acts on ONE named box and returns True on success."""

    def _one(self, sym):
        import instance_registry
        mapping, _ = instance_registry.discover([sym])
        rec = mapping.get(sym)
        if not rec or not rec.get("instance_id") or set(mapping) - {sym}:
            raise RuntimeError("instance for %s not resolved to exactly one record" % sym)
        return {sym: rec}

    def confirm_flat(self, sym):
        try:
            o = observe([sym]).get(sym) or {}
            return o.get("holding") is False
        except Exception as exc:                                               # noqa: BLE001
            print("[triage] confirm_flat %s failed: %s" % (sym, exc), file=sys.stderr)
            return False

    def stop_instance(self, sym):
        try:
            import wake_and_bake
            return bool(wake_and_bake.stage_shutdown(self._one(sym), False))
        except Exception as exc:                                               # noqa: BLE001
            print("[triage] stop %s failed: %s" % (sym, exc), file=sys.stderr)
            return False

    def start_instance(self, sym):
        try:
            import wake_and_bake
            return bool(wake_and_bake.stage_wake(self._one(sym), False))
        except Exception as exc:                                               # noqa: BLE001
            print("[triage] start %s failed: %s" % (sym, exc), file=sys.stderr)
            return False

    def kick_feed(self, sym):
        try:
            import fleet
            import ssh_util
            ip = next((ip for s, ip, st in fleet.get_fleet([sym]) if s == sym and st == "running"), None)
            if not ip:
                return False
            rc, _o, _e = ssh_util.ssh_run(ip, "sudo systemctl restart candle-feed && systemctl is-active candle-feed",
                                          timeout=60)
            return rc == 0
        except Exception as exc:                                               # noqa: BLE001
            print("[triage] kick %s failed: %s" % (sym, exc), file=sys.stderr)
            return False


def load_state(path=None):
    try:
        with open(path or STATE_PATH, encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(d, path=None):
    p = path or STATE_PATH
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=1, sort_keys=True)
    os.replace(tmp, p)


def ranking_inputs(symbols):
    ev = load_window_ev()
    filters, err = load_theory_filters()
    if err:
        print("[triage] THEORIES UNREADABLE - no symbol demoted: %s" % err)
    return ev, demoted_symbols(sorted(symbols), filters)


def main(argv=None):
    ap = argparse.ArgumentParser(description="dxlink connection triage (control)")
    ap.add_argument("--dry-run", action="store_true", help="observe, rank, print the decision; act on nothing")
    ap.add_argument("--order", action="store_true", help="print the priority order and exit")
    ap.add_argument("--status", action="store_true", help="print the stored state and exit")
    a = ap.parse_args(argv)
    if a.status:
        print(json.dumps(load_state(), indent=1, sort_keys=True))
        return 0
    os.makedirs(VAR_DIR, exist_ok=True)
    lock = open(LOCK_PATH, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("[triage] another pass is running - skipped")
        return 0
    now = time.time()
    if a.order:
        import instance_registry
        syms = list(instance_registry.fleet_members())
        ev, dem = ranking_inputs(syms)
        for i, s in enumerate(rank_boxes(syms, {s: False for s in syms}, ev, dem), 1):
            e, n = ev.get(s, (0.0, 0))
            print("%2d  %-6s EV %9s/trade  n=%-3d %s" % (i, s, _money(e), n,
                                                          "demoted by " + ",".join(dem[s]) if s in dem else ""))
        ns = load_node_status()
        age = now - float(ns.get("probed_at") or 0)
        print("dxlink nodes (control probe, %s): %s" % (
            "%.0fs old" % age if ns else "no status file",
            ", ".join("%s %s" % (ip, n.get("state")) for ip, n in sorted((ns.get("nodes") or {}).items())) or "-"))
        return 0
    obs = observe()
    ev, dem = ranking_inputs(obs)
    eng = Triage(Actuator(), dry=a.dry_run)
    new = eng.step(load_state(), obs, ev, dem, now)
    if a.dry_run:
        print("[triage] DRY RUN - nothing acted on, state not saved, nothing enqueued")
        return 0
    save_state(new)
    return 0


if __name__ == "__main__":
    sys.exit(main())
