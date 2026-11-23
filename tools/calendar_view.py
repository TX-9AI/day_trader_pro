#!/usr/bin/env python3
"""
day_trader_pro/tools/calendar_view.py  v1.0  -  the schedule: what runs when, and where planned work collides.
v1.0  2026-11-23  dtp r580 / CAL.1 — new. The operator, 2026-11-23: "Try and keep it simple. Not convoluted. We just
      want to prevent unscheduled work from colliding with planned jobs." On 2026-11-23 a wake_and_bake run at 16:12 ET
      restarted 13 boxes under the close. READ ONLY: it runs nothing, schedules nothing, keeps no database.

It merges three sources into one timeline, sorted, one row per block:
  (a) control's systemd timers, system and user scope, the ones installed under /etc/systemd or ~/.config/systemd
      (the OS's own under /usr/lib are left out): each OnCalendar expanded over the window by
      `systemd-analyze calendar --base-time --iterations`; a timer that fires more than RECUR_MAX times in the window
      is one "recurring" row (its count, first and last fire).
  (b) the fixed box-side windows, on market days only (market_calendar.is_trading_day; a holiday is one "market
      closed" row): the 09:15 wake + boot sweep (dtp-morning.timer to the open), RTH 09:30-16:00 (a 13:00 half day is
      09:30-13:00 with NO TRADING, the operator's ruling 2026-11-22: the boxes are up and record data only),
      the 16:05 close (dtp-eod-conductor.timer, until it ends: the last run's length, else CONDUCTOR_GUESS_MIN), and the
      study dispatch (dtp-study-dispatch.timer to its deadline: 07:30 ET the next morning Mon-Thu, Saturday 02:30 ET on
      a Friday; tools/friday_studies.sh).
  (c) ~/reviews/schedule/planned.tsv, the coordinator's file: date, start, end, what, touches (boxes|control|none).
      touches boxes-ro is read-only ssh to the boxes: allowed during RTH, still flagged against the wake + sweep, the
      close, the study dispatch and other box rows. date YYYY-MM-DD; start/end HH:MM ET (a leading "~" means about); a blank end is a moment; an end before the start
      ends the next day; a blank start is a day item with no time.
A planned row that touches boxes and overlaps RTH, the close, the wake + sweep, the study dispatch or another planned
box row is flagged COLLISION. The load line: "tonight (now to the next 09:15 wake): N planned, M timers; heavy|light"
(heavy = a COLLISION tonight or 3+ planned rows tonight). Collisions anywhere in the window are listed on top.

Usage:  python3 tools/calendar_view.py [--days N] [--planned PATH] [--now 2026-11-23T17:00] [--json]
        default window: now to tomorrow 17:00 ET; --days 7 for the Saturday brief.
"""
import argparse
import csv
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
import market_calendar as MC                                     # noqa: E402

ET = ZoneInfo("America/New_York")
PLANNED = os.path.expanduser("~/reviews/schedule/planned.tsv")
COLS = ["date", "start", "end", "what", "touches"]
TOUCHES = ("boxes", "boxes-ro", "control", "none")   # boxes-ro: read-only ssh to the boxes (allowed during RTH)
RTH = (time(9, 30), time(16, 0))
WAKE, CLOSE, STUDY = "dtp-morning.timer", "dtp-eod-conductor.timer", "dtp-study-dispatch.timer"
BOX_TIMERS = (WAKE, CLOSE, STUDY)
STUDY_DEADLINE = {"nightly": time(7, 30), "friday": time(2, 30)}   # tools/friday_studies.sh NIGHTLY_DEADLINE / DEADLINE
CONDUCTOR_GUESS_MIN = 30
RECUR_MAX = 4


def _sh(args, run=subprocess.run):
    try:
        p = run(args, capture_output=True, text=True, timeout=30, env=dict(os.environ, TZ="UTC", LANG="C"))
        return p.stdout if p.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def market_day(d):
    """A market session (a 13:00 half day included: the boxes wake, record data and close; they open nothing)."""
    return MC.is_trading_day(d)


# ── (a) timers ─────────────────────────────────────────────────────────────────────────────────────────────────────
def timer_units(run=subprocess.run):
    """-> [{"id", "scope", "calendars": [OnCalendar exprs], "service", "last_min"}] for control's own timers."""
    out = []
    for scope in ("system", "user"):
        base = ["systemctl"] + (["--user"] if scope == "user" else [])
        names = [ln.split()[0] for ln in _sh(base + ["list-units", "--type=timer", "--all", "--no-legend", "--plain"],
                                              run).splitlines() if ln.strip()]
        for n in names:
            txt = _sh(base + ["show", n, "-p", "Id", "-p", "FragmentPath", "-p", "TimersCalendar", "-p", "Unit"], run)
            frag = re.search(r"^FragmentPath=(.*)$", txt, re.M)
            frag = frag.group(1) if frag else ""
            if not (frag.startswith("/etc/systemd") or "/.config/systemd" in frag):
                continue
            svc = re.search(r"^Unit=(.*)$", txt, re.M)
            svc = svc.group(1) if svc else n.replace(".timer", ".service")
            st = _sh(base + ["show", svc, "-p", "ExecMainStartTimestamp", "-p", "ExecMainExitTimestamp"], run)
            out.append({"id": n, "scope": scope, "service": svc,
                        "calendars": re.findall(r"OnCalendar=(.*?) ; next_elapse", txt),
                        "last_min": _last_minutes(st)})
    return out


def _last_minutes(show_txt):
    got = dict(re.findall(r"^(ExecMain(?:Start|Exit)Timestamp)=(.+)$", show_txt or "", re.M))
    try:
        a = datetime.strptime(got["ExecMainStartTimestamp"].strip(), "%a %Y-%m-%d %H:%M:%S %Z")
        b = datetime.strptime(got["ExecMainExitTimestamp"].strip(), "%a %Y-%m-%d %H:%M:%S %Z")
    except (KeyError, ValueError):
        return None
    m = (b - a).total_seconds() / 60.0
    return round(m, 1) if m >= 0 else None


def fires(expr, lo, hi, run=subprocess.run, cap=2000):
    """-> [ET datetimes] of one OnCalendar expression in [lo, hi], via systemd-analyze (TZ=UTC output)."""
    base = lo.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    txt = _sh(["systemd-analyze", "calendar", "--base-time=" + base, "--iterations=%d" % cap, expr], run)
    out = []
    for m in re.finditer(r"(?:Next elapse|Iteration #\d+): \w+ (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) UTC", txt):
        t = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).astimezone(ET)
        if t > hi:
            break
        if t >= lo:
            out.append(t)
    return out


# ── the blocks ─────────────────────────────────────────────────────────────────────────────────────────────────────
def blk(start, end, what, touches, source, note=""):
    return {"start": start, "end": end, "what": what, "touches": touches, "source": source, "note": note, "flag": ""}


def timer_blocks(units, lo, hi, run=subprocess.run):
    """-> (control timer rows, box-window rows). Box windows sit on trading days only."""
    rows, box = [], []
    for u in units:
        ts = sorted({t for c in u["calendars"] for t in fires(c, lo - timedelta(days=1), hi, run)})
        if u["id"] in BOX_TIMERS:
            for t in ts:
                d = t.date()
                if not market_day(d):
                    continue
                if u["id"] == WAKE:
                    e = datetime.combine(d, RTH[0], ET)
                    if t < e:
                        box.append(blk(t, e, "wake + boot sweep (boxes start, sweep runs)", "boxes", WAKE))
                elif u["id"] == CLOSE:
                    mins = u.get("last_min") or CONDUCTOR_GUESS_MIN
                    lab = ("last run %.0f min" % u["last_min"]) if u.get("last_min") else \
                        "no last run read: %d min assumed" % CONDUCTOR_GUESS_MIN
                    box.append(blk(t, t + timedelta(minutes=mins), "the close: eod_conductor_v2 (holds the fleet lock)",
                                   "boxes", CLOSE, "until it ends; " + lab))
                else:
                    fri = d.weekday() == 4
                    dl = datetime.combine(d + timedelta(days=1), STUDY_DEADLINE["friday" if fri else "nightly"], ET)
                    box.append(blk(t, dl, "study dispatch (wakes boxes for OPEN queue items)", "boxes", STUDY,
                                   "deadline %s ET" % dl.strftime("%a %H:%M")))
            continue
        ts = [t for t in ts if lo <= t <= hi]
        if not ts:
            continue
        if len(ts) > RECUR_MAX:
            rows.append(blk(ts[0], ts[-1], "%s: recurring, %d fires" % (u["id"], len(ts)), "control", "timer",
                            "; ".join(u["calendars"])))
        else:
            for t in ts:
                rows.append(blk(t, None, u["id"], "control", "timer",
                                ("last run %.0f min" % u["last_min"]) if u.get("last_min") else ""))
    return rows, box


def rth_blocks(lo, hi):
    out, d = [], lo.date()
    while d <= hi.date():
        if market_day(d) and MC.is_half_day(d):
            out.append(blk(datetime.combine(d, RTH[0], ET), datetime.combine(d, time(13, 0), ET),
                           "13:00 half day: boxes up, data only, NO TRADING (operator ruling)", "boxes", "market_calendar"))
        elif not market_day(d) and d.weekday() < 5:
            out.append(blk(datetime.combine(d, time(0, 0), ET), None, "market closed (holiday)", "none",
                           "market_calendar"))
        elif market_day(d):
            out.append(blk(datetime.combine(d, RTH[0], ET), datetime.combine(d, RTH[1], ET), "RTH (the boxes trade)",
                           "boxes", "market_calendar"))
        d += timedelta(days=1)
    return [b for b in out if (b["end"] or b["start"]) >= lo and b["start"] < hi]


def _hm(s):
    s = (s or "").strip().lstrip("~").strip()
    if not s:
        return None
    m = re.fullmatch(r"(\d{1,2}):(\d\d)", s)
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        raise ValueError("time %r is not HH:MM" % s)
    return time(int(m.group(1)), int(m.group(2)))


def load_planned(path=PLANNED):
    """-> (blocks, problems). A bad row is named in problems and left out; a missing file is one problem."""
    if not os.path.exists(path):
        return [], ["planned file %s not found" % path]
    rows, bad = [], []
    with open(path, encoding="utf-8", newline="") as fh:
        rd = csv.DictReader((ln for ln in fh if ln.strip() and not ln.lstrip().startswith("#")), delimiter="\t")
        if [c.strip() for c in (rd.fieldnames or [])] != COLS:
            return [], ["planned file header is %s, not %s" % (rd.fieldnames, "\t".join(COLS))]
        for i, r in enumerate(rd, 2):
            try:
                d = date.fromisoformat((r["date"] or "").strip())
                a, b = _hm(r["start"]), _hm(r["end"])
                t = (r["touches"] or "").strip()
                if t not in TOUCHES:
                    raise ValueError("touches %r is not one of %s" % (t, "|".join(TOUCHES)))
                if a is None and b is not None:
                    raise ValueError("an end with no start")
                s = datetime.combine(d, a or time(0, 0), ET)
                e = None if b is None else datetime.combine(d, b, ET)
                if e is not None and e < s:
                    e += timedelta(days=1)
                x = blk(s, e, (r["what"] or "").strip(), t, "planned",
                        "day item, no time" if a is None else ("times are about" if "~" in (r["start"] or "") + (
                            r["end"] or "") else ""))
                x["timeless"] = a is None
                rows.append(x)
            except (ValueError, TypeError, KeyError) as ex:
                bad.append("planned row %d: %s" % (i, ex))
    return rows, bad


def _iv(b):
    """A block's interval; a timeless day item spans its day, a moment is [t, t]."""
    if b.get("timeless"):
        return b["start"], b["start"] + timedelta(days=1)
    return b["start"], b["end"] or b["start"]


def _overlap(x, y):
    """Half-open intervals; a moment [t, t] overlaps an interval that holds t, and another moment only at t."""
    (a1, a2), (b1, b2) = _iv(x), _iv(y)
    if a1 == a2 and b1 == b2:
        return a1 == b1
    if a1 == a2:
        return b1 <= a1 < b2
    if b1 == b2:
        return a1 <= b1 < a2
    return a1 < b2 and b1 < a2


def flag(planned, box_windows):
    """Mark COLLISION on each planned box row that overlaps a box window or another planned box row."""
    pb = [p for p in planned if p["touches"] in ("boxes", "boxes-ro") and not p.get("timeless")]
    for p in pb:
        hits = [w["what"].split(" (")[0] for w in box_windows if _overlap(p, w)
                and not (p["touches"] == "boxes-ro" and w["source"] == "market_calendar")]
        hits += ["planned: " + q["what"] for q in pb if q is not p and _overlap(p, q)]
        if hits:
            p["flag"] = "COLLISION with " + "; ".join(hits)
    return planned


def build(now=None, days=None, planned_path=None, units=None, run=subprocess.run):
    """-> dict(lo, hi, rows, summary, problems). `units` overrides the systemd read (gates)."""
    now = (now or datetime.now(ET)).astimezone(ET)
    end_day = now.date() + timedelta(days=days or 1)
    hi = datetime.combine(end_day, time(17, 0), ET)
    problems = []
    if units is None:
        units = timer_units(run)
        if not units:
            problems.append("systemd timers NOT READ (systemctl gave nothing)")
    trows, box = timer_blocks(units, now, hi, run)
    box = [b for b in box if b["end"] > now and b["start"] < hi]
    box += rth_blocks(now, hi)
    planned, bad = load_planned(planned_path or PLANNED)
    problems += bad
    planned = [p for p in planned if _iv(p)[1] >= now and p["start"] < hi]
    flag(planned, [b for b in box if b["touches"] == "boxes"])
    rows = sorted(trows + box + planned, key=lambda b: (b["start"], b["source"] != "planned", b["what"]))
    # tonight: now to the next wake (09:15 on the next trading day), else the window's end
    wake = [b["start"] for b in box if b["source"] == WAKE and b["start"] > now]
    night_end = min(wake) if wake else hi
    n_pl = sum(1 for p in planned if p["start"] < night_end)
    n_tm = len({r["what"].split(":")[0] for r in trows if r["start"] < night_end})
    heavy = any(p["flag"] and p["start"] < night_end for p in planned) or n_pl >= 3
    summary = "tonight (now to %s): %d planned, %d timers; %s" % (
        night_end.strftime("%a %m-%d %H:%M ET"), n_pl, n_tm, "heavy" if heavy else "light")
    return {"lo": now, "hi": hi, "rows": rows, "summary": summary, "problems": problems,
            "collisions": [p for p in planned if p["flag"]]}


def _when(b):
    if b.get("timeless"):
        return b["start"].strftime("%a %m-%d") + " (no time)"
    return b["start"].strftime("%a %m-%d %H:%M")


def _until(b):
    if b.get("timeless") or not b["end"]:
        return ""
    if b["end"].date() == b["start"].date():
        return b["end"].strftime("%H:%M")
    return b["end"].strftime("%a %H:%M" if (b["end"] - b["start"]) < timedelta(days=6) else "%a %m-%d %H:%M")


def table_rows(cal):
    """-> [[when, until, what, touches, source, flag]] (header first), for the PDF and the markdown."""
    out = [["When (ET)", "Until", "What", "Touches", "Source", "Flag"]]
    for b in cal["rows"]:
        what = b["what"] + (" (%s)" % b["note"] if b["note"] else "")
        out.append([_when(b), _until(b), what, b["touches"], b["source"], b["flag"]])
    return out


def render_md(cal):
    L = ["# Schedule, %s -> %s" % (cal["lo"].strftime("%a %Y-%m-%d %H:%M ET"), cal["hi"].strftime("%a %Y-%m-%d %H:%M ET")),
         "", cal["summary"], ""]
    if cal["collisions"]:
        L += ["COLLISIONS: %d" % len(cal["collisions"])] + ["- %s %s: %s" % (_when(p), p["what"], p["flag"])
                                                           for p in cal["collisions"]] + [""]
    for p in cal["problems"]:
        L.append("NOTE: " + p)
    if cal["problems"]:
        L.append("")
    t = table_rows(cal)
    L.append("| " + " | ".join(t[0]) + " |")
    L.append("|" + "---|" * len(t[0]))
    for r in t[1:]:
        L.append("| " + " | ".join(c.replace("|", "/") for c in r) + " |")
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="the schedule: timers, box windows and planned work (read only)")
    ap.add_argument("--days", type=int, default=1, help="window end: 17:00 ET this many days ahead (default 1)")
    ap.add_argument("--planned", default=PLANNED)
    ap.add_argument("--now", default=None, help="ISO time in ET (default: now)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    now = datetime.fromisoformat(a.now).replace(tzinfo=ET) if a.now else None
    cal = build(now, a.days, a.planned)
    if a.json:
        print(json.dumps({"summary": cal["summary"], "problems": cal["problems"], "rows": table_rows(cal)}, indent=1))
    else:
        sys.stdout.write(render_md(cal))
    return 0


if __name__ == "__main__":
    sys.exit(main())
