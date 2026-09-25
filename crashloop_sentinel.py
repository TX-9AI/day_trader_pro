#!/usr/bin/env python3
# day_trader_pro/crashloop_sentinel.py — v1.1
# v1.1 (2026-09-25) — r429 / OPS.53. A LOOP WHOSE PERIOD IS THE WINDOW WAS
#   INVISIBLE. AAL restarted at 14:11, 15:11 and 16:07 UTC — about SIXTY
#   minutes apart against WINDOW_S=3600 — so each event aged out before three
#   could coexist. The log read "in-window=2" then "in-window=1", THRESHOLD was
#   never reached, and ZERO alerts went out while the box sat blind for roughly
#   23 minutes across two episodes in prime RTH.
#   ⚠️ THE ARITHMETIC WAS NEVER WRONG AND I SAID IT WAS. `hist + [now] * delta`
#   already credits every restart between two polls, so a BURST always alerted.
#   I reported "under-counts fast loops" from the summary numbers before
#   reading the evaluator, and told both the operator and the peer session the
#   opposite of the truth. The window is the wrong instrument for a SLOW loop;
#   the counting was fine. check S2 pins that the burst rule still works.
#   🔑 THE FIX IS A SECOND RULE ALONGSIDE, NOT INSTEAD: restarts accumulated
#   over the ET TRADING DAY, which nothing can age out. On AAL's real timeline
#   it fires at 15:15 UTC — after the second restart, ~52 min before the third.
#   ⚠️ ONCE PER DAY PER BOX (§17). Each box already telegraphs its own restart;
#   the value added here is naming the PATTERN, not repeating the event.
# v1.0 (2026-09-23) — dtp r418 / OPS.41. A CRASH LOOP LOOKS EXACTLY LIKE A
#   HEALTHY RESTART, AND THAT IS WHY FORTY-ONE OF THEM WENT UNNAMED.
#   🔴 THE FAILURE, FROM THE OPERATOR'S OWN PHONE, 2026-09-23. QQQ's
#   `optionsbot` restarted 41 times on a corrupt `feed_store.db`, and every one
#   emitted the SAME line the bot sends on any boot:
#     `🚀 OptionsBot [PAPER] STARTED | QQQ | service restart | IP … | 15:08 ET`
#   Nothing in that stream says "this is the 41st in an hour". One of them even
#   read *"bake — restarting on a new revision"*, which is indistinguishable
#   from routine maintenance. The operator: *"I'm seeing a lot of restart
#   notifications … can I get a proper telegram notification for crash-looping
#   boxes that's less ambiguous than this?"*
#   🔑 THE SIGNAL EXISTED AND CARRIED NO ALARM. This is §17's cry-wolf failure
#   INVERTED: not a false alarm nobody should read, but a true one nobody CAN
#   read, because the alarming case renders identically to the benign one. The
#   fix is not another per-restart message — it is an AGGREGATE that only a
#   watcher holding state can compute.
#   ⚠️ THE ALERT CARRIES THE CAUSE. "QQQ is restarting" costs a round trip to
#   become actionable; "QQQ restarted 41× — database disk image is malformed"
#   is a decision. The journal's last error line ships WITH the count.
#   ⚠️ A SINGLE PLANNED RESTART MUST NEVER FIRE IT. A bake restarts each box
#   once; the threshold is a COUNT IN A WINDOW, so maintenance stays quiet and
#   a loop does not.
#   ⚠️ AND IT SAYS WHEN IT STOPS. An alert with no all-clear trains the reader
#   to ignore the channel, which is how the next one gets missed.
"""Crash-loop sentinel — watch `optionsbot` restart counts across the fleet.

Detection is on the DELTA between polls, not the absolute count, so a
`systemctl reset-failed` or a service-file reload cannot mask a loop or
manufacture one.

    python3 crashloop_sentinel.py            # one pass, alert if warranted
    python3 crashloop_sentinel.py --dry-run  # print, never send
    python3 crashloop_sentinel.py --status   # show state, decide nothing
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

# Restarts within WINDOW_S that trip the alarm.
# 🔴 THE WINDOW IS AN HOUR BECAUSE SYSTEMD'S BACKOFF SETS THE SPACING, NOT THE
# CRASH. Measured on QQQ 2026-09-23, restarts landed 14:42, 14:49, 14:58,
# 15:06, 15:25 ET — roughly 8-10 minutes apart. The first cut of this file
# shipped THRESHOLD=3 over a 900s window, which a loop at that spacing can
# NEVER reach: fifteen minutes only ever holds two. A sentinel that passed
# every one of its own checks and could not detect the incident it was
# written for. Found by running it against the live loop, not by reading it.
# ⚠️ AN HOUR STILL SEPARATES THE TWO CASES CLEANLY: a bake restarts each box
# ONCE (so 1 per hour, silent), a loop at 8-minute spacing produces ~7 (so it
# trips on the third, ~25 minutes in). Gated by C8, which drives the SHIPPED
# defaults against a realistic loop rather than a convenient fixture.
THRESHOLD = int(os.environ.get("DTP_CRASHLOOP_THRESHOLD", "3"))
WINDOW_S = int(os.environ.get("DTP_CRASHLOOP_WINDOW_S", "3600"))
# Re-alert cadence for a loop that is still burning, so one alert does not have
# to carry an unbounded incident.
RENOTIFY_S = int(os.environ.get("DTP_CRASHLOOP_RENOTIFY_S", "1800"))

# 🔴 r429 / OPS.53 — THE ROLLING WINDOW CANNOT SEE A LOOP WHOSE PERIOD IS THE
# WINDOW. Measured on AAL, 2026-09-25: optionsbot self-shut-down and restarted
# at 14:11, 15:11 and 16:07 UTC — roughly SIXTY minutes apart against
# WINDOW_S=3600 — so the sentinel logged "in-window=2" then "in-window=1" as
# each event aged out, and never reached THRESHOLD. Three crash loops, ~23
# minutes blind across two of them in prime RTH, and ZERO alerts.
# ⚠️ THE COUNTING WAS NEVER WRONG. `hist + [now] * delta` already credits every
# restart between two polls, so a BURST alerts correctly; I first diagnosed
# this as under-counting fast loops and that was backwards. The window is the
# wrong instrument for a SLOW loop, not the arithmetic.
# 🔑 SO A SECOND RULE RUNS ALONGSIDE, NOT INSTEAD: restarts accumulated over
# the ET TRADING DAY, which cannot expire under a box that restarts on any
# cadence. The rolling window still catches bursts inside the hour.
SESSION_THRESHOLD = int(os.environ.get("DTP_CRASHLOOP_SESSION_THRESHOLD", "2"))
STATE_PATH = os.environ.get(
    "DTP_CRASHLOOP_STATE",
    os.path.join(_HERE, "data", "crashloop_state.json"))


def load_state(path=None):
    """Prior observations. A missing or unreadable file is a FRESH start."""
    p = path or STATE_PATH
    try:
        with open(p, "r", encoding="utf-8") as fh:
            got = json.load(fh)
        return got if isinstance(got, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(state, path=None):
    p = path or STATE_PATH
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=0, sort_keys=True)
        os.replace(tmp, p)
        return True
    except OSError as exc:
        print(f"[sentinel] WARN state not saved ({exc})", file=sys.stderr)
        return False


def _et_day(now) -> str:
    """The ET trading day `now` falls in. The reset boundary for the session
    counter — UTC midnight would split a session in half (r125)."""
    try:
        import ettime
        return ettime.et_day(now)
    except Exception:                                          # noqa: BLE001
        import datetime
        from zoneinfo import ZoneInfo
        return datetime.datetime.fromtimestamp(
            now, ZoneInfo("America/New_York")).strftime("%Y-%m-%d")


def evaluate(prev, obs, now):
    """(new_state, alerts) — pure, so the rule is testable without a fleet.

    `obs` maps symbol -> {"restarts": int|None, "sub": str, "err": str}.
    A `restarts` of None means the box could not be read, which is REPORTED
    rather than skipped: an unreachable box during RTH is itself a finding
    (§0.5), and silently dropping it is how a dead box reads as a healthy one.
    """
    new, alerts = {}, []
    for sym in sorted(obs):
        o = obs[sym] or {}
        cur = o.get("restarts")
        p = dict(prev.get(sym) or {})
        hist = [t for t in (p.get("events") or []) if now - t <= WINDOW_S]

        if cur is None:
            new[sym] = {"restarts": p.get("restarts"), "events": hist,
                        "last_alert": p.get("last_alert", 0),
                        "level": p.get("level", 0),
                        # ⚠️ AN UNREADABLE POLL MUST NOT WIPE THE SESSION
                        # TALLY. A box that is briefly unreachable and then
                        # restarts again is the same loop, not a fresh one.
                        "session_day": p.get("session_day"),
                        "session_restarts": int(p.get("session_restarts", 0)),
                        "unreachable": int(p.get("unreachable", 0)) + 1}
            # Two consecutive misses, not one — a single ssh blip is noise.
            if new[sym]["unreachable"] == 2:
                alerts.append({
                    "sym": sym, "kind": "unreachable", "count": 0,
                    "text": (f"⚠️ SENTINEL BLIND | {sym} | optionsbot state "
                             f"unreadable on 2 consecutive polls — the box may "
                             f"be down, not healthy"),
                })
            continue

        prev_n = p.get("restarts")
        delta = 0
        if isinstance(prev_n, int) and cur >= prev_n:
            delta = cur - prev_n
        elif isinstance(prev_n, int) and cur < prev_n:
            # Counter went BACKWARDS: reset-failed, or the unit was reloaded.
            # Treat as a fresh baseline rather than a negative, and do not
            # invent restarts we did not observe.
            delta = 0
        hist = hist + [now] * delta
        level = p.get("level", 0)
        last_alert = p.get("last_alert", 0)
        n = len(hist)

        # ── r429 — THE SESSION TALLY, which nothing can age out ────────────
        # Same delta, a different clock: this one resets on the ET TRADING DAY
        # and not on a rolling hour, so a box restarting once an hour still
        # accumulates. AAL 2026-09-25 is the case it exists for.
        today = _et_day(now)
        if p.get("session_day") == today:
            session_n = int(p.get("session_restarts", 0)) + delta
        else:
            session_n = delta          # new ET day: start this session's count
        session_alerted = (p.get("session_day") == today
                           and bool(p.get("session_alerted")))

        if n >= THRESHOLD:
            due = (level == 0) or (now - last_alert >= RENOTIFY_S)
            if due:
                mins = max(1, int(WINDOW_S / 60))
                err = (o.get("err") or "").strip()
                tail = f"\nlast error: {err[:160]}" if err else (
                    "\nlast error: (none found in journal — check the unit)")
                alerts.append({
                    "sym": sym, "kind": "loop", "count": n,
                    "text": (f"🔁 CRASH LOOP | {sym} | optionsbot restarted "
                             f"{n}× in {mins} min (total {cur}) — this is NOT "
                             f"a normal restart{tail}"),
                })
                last_alert, level = now, 1
        elif level and n == 0:
            alerts.append({
                "sym": sym, "kind": "recovered", "count": 0,
                "text": (f"✅ RECOVERED | {sym} | optionsbot has stopped "
                         f"restarting (stable for {int(WINDOW_S / 60)} min)"),
            })
            level, last_alert = 0, now

        # ── r429 — THE SLOW-LOOP RULE, DELIBERATELY NOT IN THE elif CHAIN ──
        # 🔴 IT WAS AN elif FIRST AND THAT BROKE RECOVERY. Sitting above
        # `elif level and n == 0`, it swallowed the RECOVERED alert whenever a
        # box had session restarts — caught by check_crashloop_sentinel C7,
        # which is exactly why that gate exists. The two rules answer different
        # questions and must not compete for one branch.
        if session_n >= SESSION_THRESHOLD and not session_alerted:
            err2 = (o.get("err") or "").strip()
            tail2 = f"\nlast error: {err2[:160]}" if err2 else ""
            alerts.append({
                "sym": sym, "kind": "session_loop", "count": session_n,
                "text": (f"\U0001F501 REPEAT RESTARTS | {sym} | optionsbot has "
                         f"restarted {session_n}\u00d7 today (total {cur}) — "
                         f"spread out, so the {int(WINDOW_S/60)}-min burst rule "
                         f"will not catch it{tail2}"),
            })
            session_alerted, last_alert = True, now

        new[sym] = {"restarts": cur, "events": hist, "last_alert": last_alert,
                    "level": level, "unreachable": 0,
                    "session_day": today, "session_restarts": session_n,
                    "session_alerted": session_alerted}
    return new, alerts


# ── the only part that touches the fleet ────────────────────────────────────
_PROBE = (
    "systemctl show optionsbot -p NRestarts -p SubState 2>/dev/null; "
    "echo '---ERR---'; "
    "journalctl -u optionsbot --since '20 min ago' --no-pager 2>/dev/null "
    "| grep -iE 'error|traceback|exception|malformed|locked' | tail -1"
)


def _parse(block):
    out = {"restarts": None, "sub": "", "err": ""}
    head, _, err = block.partition("---ERR---")
    out["err"] = err.strip().split("]: ")[-1].strip()
    for line in head.splitlines():
        line = line.strip()
        if line.startswith("NRestarts="):
            try:
                out["restarts"] = int(line.split("=", 1)[1])
            except ValueError:
                pass
        elif line.startswith("SubState="):
            out["sub"] = line.split("=", 1)[1]
    return out


def observe(only=None, timeout=45):
    """symbol -> parsed probe. Read-only; never writes to a box.

    ⚠️ USES `ssh_util.ssh_map`, WHICH IS THE ONLY THING THAT RETURNS PER-BOX
    OUTPUT. `fleet.cmd_run` PRINTS and returns a status code — a sentinel
    built on it would have had nothing to evaluate. (First cut of this
    function invented `fleet.run_map`; §0.4, caught by reading fleet.py
    rather than by running.)
    ⚠️ A box that fails is recorded as `restarts=None`, NOT dropped: an
    unreachable box during RTH is a finding, and silence would render it
    identical to a healthy one.
    """
    import fleet
    import ssh_util
    obs = {}
    try:
        rows = fleet.get_fleet(only)
    except Exception as exc:                              # noqa: BLE001
        print(f"[sentinel] cannot list fleet ({exc})", file=sys.stderr)
        return obs
    targets = [(s, ip) for s, ip, st in rows if st == "running" and ip]
    if not targets:
        return obs
    try:
        results = ssh_util.ssh_map(targets, _PROBE, timeout=timeout)
    except Exception as exc:                              # noqa: BLE001
        print(f"[sentinel] ssh_map failed ({exc})", file=sys.stderr)
        return {s: {"restarts": None, "sub": "", "err": ""} for s, _ in targets}
    for sym, _ip in targets:
        rc_out = results.get(sym)
        if not rc_out:
            obs[sym] = {"restarts": None, "sub": "", "err": ""}
            continue
        rc, out, err = rc_out
        if rc != 0 and not (out or "").strip():
            obs[sym] = {"restarts": None, "sub": "",
                        "err": (err or "").strip()[:160]}
            continue
        obs[sym] = _parse(out or "")
    return obs


def main(argv=None):
    ap = argparse.ArgumentParser(description="fleet crash-loop sentinel")
    ap.add_argument("--dry-run", action="store_true",
                    help="evaluate and print; send nothing, save nothing")
    ap.add_argument("--status", action="store_true",
                    help="print stored state and exit")
    ap.add_argument("--only", default=None)
    ap.add_argument("--ignore-calendar", action="store_true",
                    help="watch even on a non-trading day")
    args = ap.parse_args(argv[1:] if argv else sys.argv[1:])

    if args.status:
        st = load_state()
        if not st:
            print("no state yet (never run, or state file unreadable)")
            return 0
        for sym in sorted(st):
            s = st[sym]
            print(f"  {sym:6s} restarts={s.get('restarts')} "
                  f"in-window={len(s.get('events') or [])} "
                  f"level={s.get('level')} unreachable={s.get('unreachable')}")
        return 0

    # ⚠️ THE TIMER FIRES ON A CLOCK; THE HOLIDAY CALENDAR IS AN EXCHANGE FACT.
    # systemd's OnCalendar handles weekends and DST (it takes an explicit
    # America/New_York), but it does not know Thanksgiving. Asked here rather
    # than encoded in the unit, which is r125's rule: a date predicate belongs
    # to the calendar, not to a crontab.
    # ⚠️ A MISSING CALENDAR DOES NOT SILENCE THE SENTINEL — it watches and says
    # why. Failing open on a watchdog is the correct direction.
    if not args.ignore_calendar:
        try:
            import market_calendar
            if not market_calendar.is_trading_day():
                print("[sentinel] not a trading day — nothing to watch")
                return 0
        except Exception as exc:                              # noqa: BLE001
            print(f"[sentinel] calendar unavailable ({exc}) — watching anyway",
                  file=sys.stderr)

    now = time.time()
    prev = load_state()
    obs = observe(args.only)
    if not obs:
        print("[sentinel] no running boxes — nothing to watch")
        return 0
    new, alerts = evaluate(prev, obs, now)

    # ⚠️ A RUN IS NEVER SILENT. The first cut printed NOTHING when nothing was
    # wrong, which is indistinguishable from a crashed sentinel — the exact
    # plausible-silence class this repo keeps paying for (§0.5). Found by
    # running it, not by reading it.
    seen = len(obs)
    blind = sum(1 for o in obs.values() if (o or {}).get("restarts") is None)
    print(f"[sentinel] polled {seen} running box(es), {blind} unreadable, "
          f"{len(alerts)} alert(s)")
    for sym in sorted(obs):
        o = obs[sym] or {}
        n = o.get("restarts")
        inwin = len((new.get(sym) or {}).get("events") or [])
        print(f"    {sym:6s} NRestarts={'?' if n is None else n:>5} "
              f"in-window={inwin}")
    for a in alerts:
        print(f"[sentinel] {a['kind'].upper()} {a['sym']}: {a['text'][:120]}")

    if args.dry_run:
        # ⚠️ AND WHY A DRY RUN CANNOT DETECT ANYTHING ON ITS OWN IS SAID OUT
        # LOUD. Detection is a DELTA between polls; a dry run deliberately
        # does not persist, so every dry run is a fresh baseline and in-window
        # is always 0. Reading that as "the fleet is healthy" would be wrong,
        # and silence let the first cut imply exactly that.
        print("[sentinel] DRY RUN — nothing sent, state NOT saved. Detection "
              "needs two saved polls, so in-window above is a baseline, not a "
              "verdict.")
        return 0
    if alerts:
        import notify
        for a in alerts:
            notify.send(a["text"])
    save_state(new)
    return 0


if __name__ == "__main__":
    sys.exit(main())
