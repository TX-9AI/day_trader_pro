#!/usr/bin/env python3
"""
day_trader_pro/tools/morning_check.py — v1.0
v1.0  2026-11-08  dtp r539 / TIMER.1 — ONE MORNING CHECK ON A TIMER, NOT THREE CHECKS IN A CLAUDE SESSION.
      The operator, 2026-11-08: "On the timers, yes consolidate, clean up and optimize." The 09:19 wake verify and
      the 09:50 / 11:10 shadow-rule checks were session crons: a session restart wiped them, silently. They are
      now one oneshot run by dtp-morning-check.timer at 09:19, 09:50 and 11:10 ET on trading days. Each run does
      the STEP its time picks (or --step names):
        wake  (09:19)  every box: EC2 running, candle-feed + optionsbot active, HEAD = OTV5 main (a box behind by
                       docs-only commits is a note, not a red), no "sessions has exceeded" / 502 in the candle-feed
                       journal since 09:15, no TEMP /etc/hosts pin, today's dxlink_assign.json; and each box's
                       TIMER SET (unit names), so the 14 can be compared - the boxes differing from the majority
                       are named. Control: the 09:16 dtp-dxlink-assign run (a NOT WRITTEN is red) and the alert
                       router alive.
        hunt  (09:50)  OTV5 tools/shadow_rule_status.py shipped to every running box (read-only, since 09:30):
                       HUNT_OR_EM rows / mix / RED per box.
        park  (11:10)  the same, PARK_SMA50 since 11:00 (equity and index split), and the HUNT_OR_EM count again.
      The operator 2026-11-08 on the log-only rules: "I want immediate feedback that it's really logging." So
      EVERY run sends one line to the operator through control's alert router (post_status): kind "critical" when
      anything is RED, when a rule's rows are ALL unknown, or when no box answered; "info" otherwise. When the router
      is not alive the line goes straight to Telegram (notify.send) instead, so a dead router cannot swallow it. Each run's
      full report is appended to ~/reviews/morning_check/<day>.txt and its one line is the last line printed.
      rc 0 green, 1 red, 2 could not run. Not a trading day -> one line, rc 0, nothing sent. Read-only on every box.
Run:  python3 tools/morning_check.py [--step wake|hunt|park] [--no-post] [--day YYYY-MM-DD]
"""
import base64
import collections
import json
import os
import subprocess
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

__version__ = "1.0"

OTV5 = os.environ.get("DTP_OTV5_TREE", os.path.expanduser("~/OTV5"))
REPORT_DIR = os.environ.get("DTP_MORNING_CHECK_DIR", os.path.expanduser("~/reviews/morning_check"))
INDEX = {"SPX", "QQQ", "SPY", "IWM", "NDX", "XSP"}
STEPS = ("wake", "hunt", "park")

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:                                                          # noqa: BLE001
    ET = None

# The one thing that runs on a box for the wake step: read-only, never an Environment block.
BOX_WAKE = r'''
import json, os, subprocess
def sh(c):
    try:
        return subprocess.run(c, shell=True, capture_output=True, text=True, timeout=25).stdout.strip()
    except Exception as e:
        return "ERR %s" % type(e).__name__
H = os.path.expanduser("~/options-trader")
o = {}
o["feed"] = sh("systemctl is-active candle-feed")
o["bot"] = sh("systemctl is-active optionsbot")
o["head"] = sh("git -C %s rev-parse HEAD" % H)
j = sh("journalctl -u candle-feed --since '%s 09:15' --no-pager -o cat 2>/dev/null" % DAY)
o["refused"] = sum(1 for l in j.splitlines() if "sessions has exceeded" in l)
o["bad502"] = sum(1 for l in j.splitlines() if "502 Bad Gateway" in l)
o["pins"] = sum(1 for l in open("/etc/hosts") if "TEMP 2026-11-02" in l)
a = os.path.join(H, "data", "dxlink_assign.json")
o["assign_age_s"] = round(__import__("time").time() - os.path.getmtime(a)) if os.path.exists(a) else None
o["timers"] = sorted(l.split()[-2] for l in sh("systemctl list-timers --all --no-legend --no-pager").splitlines()
                     if l.strip() and l.split()[-2].endswith(".timer"))
print("WAKE_STATUS " + json.dumps(o))
'''


def now_et():
    return datetime.now(ET) if ET else datetime.now()


def pick_step(dt):
    hm = dt.hour * 60 + dt.minute
    if hm < 9 * 60 + 40:
        return "wake"
    if hm < 11 * 60:
        return "hunt"
    return "park"


def _ship(script, args=""):
    b64 = base64.b64encode(script.encode() if isinstance(script, str) else script).decode()
    return ("f=$(mktemp /tmp/mchk.XXXXXX) && echo %s | base64 -d > $f && python3 $f %s; rc=$?; rm -f $f; exit $rc"
            % (b64, args))


def fan_out(command, fleet_fn=None, map_fn=None, timeout=90):
    """-> (records [(sym, state)], {sym: (rc, out, err)}) for the running boxes."""
    if fleet_fn is None:
        import fleet
        fleet_fn = fleet.get_fleet
    if map_fn is None:
        import ssh_util
        map_fn = ssh_util.ssh_map
    recs = fleet_fn()
    running = [(s, ip) for s, ip, st in recs if st == "running" and ip]
    res = map_fn(running, command, timeout=timeout) if running else {}
    return [(s, st) for s, _ip, st in recs], res


def _tagged(out, tag):
    for line in (out or "").splitlines():
        if line.startswith(tag + " "):
            try:
                return json.loads(line[len(tag) + 1:])
            except ValueError:
                return None
    return None


def git(*a, tree=None):
    p = subprocess.run(["git", "-C", tree or OTV5] + list(a), capture_output=True, text=True, timeout=30)
    return p.returncode, p.stdout.strip()


def docs_only_behind(box_head, main_head, tree=None):
    """True iff every file changed from box_head to main_head is under docs/ (a box needs no update for it)."""
    rc, out = git("diff", "--name-only", box_head, main_head, tree=tree)
    return rc == 0 and all(f.startswith("docs/") for f in out.splitlines() if f.strip())


def control_side(day, journal_fn=None, alive_fn=None):
    """-> (reds, notes) for the 09:16 assignment and the router."""
    reds, notes = [], []
    if journal_fn is None:
        def journal_fn(unit):
            p = subprocess.run(["journalctl", "-u", unit, "--since", day + " 00:00", "--no-pager", "-o", "cat"],
                               capture_output=True, text=True, timeout=30)
            return p.stdout
    j = [l for l in journal_fn("dtp-dxlink-assign.service").splitlines() if "DXLINK ASSIGNMENT" in l]
    if not j:
        reds.append("control: dtp-dxlink-assign wrote no DXLINK ASSIGNMENT line today")
    elif "NOT WRITTEN" in j[-1]:
        reds.append("control: " + j[-1].split("] ", 1)[-1][:160])
    else:
        notes.append("assign: " + j[-1].split("] ", 1)[-1][:120])
    if alive_fn is None:
        import alert_router
        alive_fn = alert_router.router_alive
    if not alive_fn():
        reds.append("control: alert router not alive (health.json stale or unhealthy)")
    return reds, notes


def step_wake(day, fleet_fn=None, map_fn=None, journal_fn=None, alive_fn=None, main_head=None, behind_fn=None):
    recs, res = fan_out(_ship("DAY = %r\n" % day + BOX_WAKE), fleet_fn, map_fn)
    if main_head is None:
        _rc, main_head = git("rev-parse", "HEAD")
    behind_fn = behind_fn or docs_only_behind
    reds, notes, lines = [], [], []
    timer_sets = {}
    for sym, st in recs:
        if st != "running":
            reds.append("%s: EC2 %s at the wake check" % (sym, st))
            continue
        rc, out, err = res.get(sym, (255, "", "no answer"))
        w = _tagged(out, "WAKE_STATUS")
        if w is None:
            reds.append("%s: no answer (rc %s %s)" % (sym, rc, (err or "").strip()[:60]))
            continue
        bad = []
        if w["feed"] != "active":
            bad.append("candle-feed " + w["feed"])
        if w["bot"] != "active":
            bad.append("optionsbot " + w["bot"])
        if w["head"] != main_head:
            if w["head"] and behind_fn(w["head"], main_head):
                notes.append("%s: HEAD %s is behind main by docs only" % (sym, w["head"][:7]))
            else:
                bad.append("HEAD %s != %s" % ((w["head"] or "?")[:7], main_head[:7]))
        if w["refused"]:
            bad.append("%d session-limit refusal(s)" % w["refused"])
        if w["bad502"]:
            bad.append("%d x 502" % w["bad502"])
        if w["pins"]:
            bad.append("%d TEMP hosts pin(s)" % w["pins"])
        if w["assign_age_s"] is None or w["assign_age_s"] > 3 * 3600:
            notes.append("%s: no dxlink_assign.json from today" % sym)
        timer_sets[sym] = tuple(w["timers"])
        (reds.append("%s: %s" % (sym, ", ".join(bad))) if bad else None)
        lines.append("%-5s feed %-8s bot %-8s %s  timers %d" % (sym, w["feed"], w["bot"], w["head"][:7],
                                                                 len(w["timers"])))
    if timer_sets:
        major, n = collections.Counter(timer_sets.values()).most_common(1)[0]
        notes.append("timers: %d/%d boxes share one set of %d: %s" % (n, len(timer_sets), len(major),
                                                                      " ".join(t[:-6] for t in major)))
        for sym, ts in sorted(timer_sets.items()):
            if ts != major:
                extra, miss = sorted(set(ts) - set(major)), sorted(set(major) - set(ts))
                notes.append("timers: %s differs (+%s -%s)" % (sym, ",".join(extra) or "0", ",".join(miss) or "0"))
    r2, n2 = control_side(day, journal_fn, alive_fn)
    reds += r2
    notes += n2
    up = sum(1 for _s, st in recs if st == "running")
    one = ("MORNING CHECK 09:19 wake: %d/%d up, HEAD %s, " % (up, len(recs), (main_head or "?")[:7])
           + ("RED: " + "; ".join(reds) if reds else "all GREEN"))
    return reds, notes, lines, one


def step_shadow(day, step, fleet_fn=None, map_fn=None, script=None):
    since = "09:30" if step == "hunt" else "11:00"
    if script is None:
        with open(os.path.join(OTV5, "tools", "shadow_rule_status.py"), "rb") as fh:
            script = fh.read()
    recs, res = fan_out(_ship(script, "--day %s --since %s" % (day, since)), fleet_fn, map_fn)
    reds, notes, lines = [], [], []
    tot = {"HUNT_OR_EM": collections.Counter(), "PARK_SMA50": collections.Counter()}
    split = {"equity": collections.Counter(), "index": collections.Counter()}
    answered = 0
    for sym, st in recs:
        if st != "running":
            reds.append("%s: EC2 %s" % (sym, st))
            continue
        rc, out, err = res.get(sym, (255, "", "no answer"))
        s = _tagged(out, "SHADOW_STATUS")
        if s is None:
            reds.append("%s: no SHADOW_STATUS (rc %s %s)" % (sym, rc, (err or "").strip()[:60]))
            continue
        answered += 1
        for rule, v in s.get("rules", {}).items():
            tot.setdefault(rule, collections.Counter()).update(v.get("mix", {}))
            if rule == "PARK_SMA50":
                split["index" if sym in INDEX else "equity"].update(v.get("mix", {}))
            if v.get("status") == "RED":
                reds.append("%s %s: %d decisions, %d rows, %d log lines" % (sym, rule, v.get("decisions", 0),
                                                                           v.get("rows", 0), v.get("log_lines", 0)))
            lines.append("%-5s %-10s %-5s dec %3d rows %3d log %3d %s" % (
                sym, rule, v.get("status"), v.get("decisions", 0), v.get("rows", 0), v.get("log_lines", 0),
                " ".join("%s=%d" % kv for kv in sorted(v.get("mix", {}).items())) or "-"))
        for e in s.get("errors", []):
            notes.append("%s: %s" % (sym, str(e)[:120]))
    if not answered:
        reds.append("no box answered")
    rules = ["HUNT_OR_EM"] if step == "hunt" else ["PARK_SMA50", "HUNT_OR_EM"]
    for rule in rules:
        mix = tot.get(rule, collections.Counter())
        n = sum(mix.values())
        if n and mix.get("unknown", 0) == n:
            reds.append("%s: all %d rows unknown" % (rule, n))
    def fmt(rule):
        mix = tot.get(rule, collections.Counter())
        boxes = sum(1 for l in lines if (" %s " % rule) in l and " rows   0 " not in l)
        return "%s %d rows on %d box(es) (%s)" % (rule, sum(mix.values()), boxes,
                                                 " ".join("%s %d" % kv for kv in sorted(mix.items())) or "none yet")
    head = "MORNING CHECK %s %s: " % ("09:50" if step == "hunt" else "11:10", step)
    body = "; ".join(fmt(r) for r in rules)
    if step == "park":
        body += " | PARK equity %s, index %s" % (
            " ".join("%s %d" % kv for kv in sorted(split["equity"].items())) or "-",
            " ".join("%s %d" % kv for kv in sorted(split["index"].items())) or "-")
    one = head + body + (" | RED: " + "; ".join(reds) if reds else "")
    return reds, notes, lines, one


def write_report(day, step, reds, notes, lines, one, report_dir=None):
    d = report_dir or REPORT_DIR
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, day + ".txt")
    with open(p, "a", encoding="utf-8") as fh:
        fh.write("\n== %s %s (%s ET) ==\n" % (day, step, now_et().strftime("%H:%M")))
        for l in lines:
            fh.write("  " + l + "\n")
        for r in reds:
            fh.write("  RED   " + r + "\n")
        for n in notes:
            fh.write("  note  " + n + "\n")
        fh.write(one + "\n")
    return p


def deliver(kind, text, post_fn=None, alive_fn=None, send_fn=None):
    """Through control's alert router when it is alive; straight to Telegram (notify.send, control's .env) when it is
    not - a dead router is exactly when this line must not sit in an outbox nobody drains. -> "router" | "direct"."""
    import alert_router
    alive_fn = alive_fn or alert_router.router_alive
    if alive_fn():
        (post_fn or alert_router.post_status)(kind, text)
        return "router"
    if send_fn is None:
        import notify
        send_fn = notify.send
    send_fn(("🔴 " if kind == "critical" else "") + text + " (sent direct: the alert router is not alive)")
    return "direct"


def main(argv=None, post_fn=None, trading_fn=None, route_alive_fn=None, send_fn=None, **inject):
    argv = list(sys.argv[1:] if argv is None else argv)
    def arg(name):
        return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else None
    dt = now_et()
    day = arg("--day") or dt.strftime("%Y-%m-%d")
    step = arg("--step") or pick_step(dt)
    if step not in STEPS:
        print("unknown step %r (wake | hunt | park)" % step)
        return 2
    if trading_fn is None:
        import market_calendar
        trading_fn = market_calendar.is_trading_day
    report_dir = inject.pop("report_dir", None)
    if not trading_fn(datetime.strptime(day, "%Y-%m-%d").date()):
        print("MORNING CHECK %s: %s is not a trading day - nothing checked" % (step, day))
        return 0
    try:
        if step == "wake":
            reds, notes, lines, one = step_wake(day, **inject)
        else:
            reds, notes, lines, one = step_shadow(day, step, **inject)
    except Exception as exc:                                                # noqa: BLE001
        reds, notes, lines = ["the check itself failed: %s: %s" % (type(exc).__name__, str(exc)[:160])], [], []
        one = "MORNING CHECK %s: COULD NOT RUN - %s" % (step, reds[0])
        failed = True
    else:
        failed = False
    for l in lines:
        print("  " + l)
    for r in reds:
        print("  RED   " + r)
    for n in notes:
        print("  note  " + n)
    try:
        write_report(day, step, reds, notes, lines, one, report_dir)
    except OSError as exc:
        print("  note  report not written: %s" % exc)
    if "--no-post" not in argv:
        deliver("critical" if reds else "info", one[:900], post_fn, route_alive_fn, send_fn)
    print(one)
    return 2 if failed else (1 if reds else 0)


if __name__ == "__main__":
    sys.exit(main())
