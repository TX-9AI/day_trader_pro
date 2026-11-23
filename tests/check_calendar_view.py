#!/usr/bin/env python3
"""
day_trader_pro/tests/check_calendar_view.py — v1.0
v1.0  2026-11-23  dtp r580 / CAL.1 — new. tools/calendar_view.py v1.0 (the operator, 2026-11-23: "We just want to
      prevent unscheduled work from colliding with planned jobs."). Hermetic: the timers are stand-ins (no systemctl),
      the planned file is a scratch one, the clock is fixed; only `systemd-analyze calendar` runs (it reads nothing).

  V1  planned.tsv: the header is required; a bad time, a bad touches and an end with no start are each named and left
      out; "~" times read as about; an end before the start ends the next day; a blank start is a day item
  V2  the box windows on Tue 2026-11-24: wake + sweep 09:15-09:30, RTH 09:30-16:00, the close 16:05 for the last run's
      length (14 min), the study dispatch 17:15 to Wed 07:30; Fri 11-27 (a half day) RTH is 09:30-13:00 NO TRADING and
      the dispatch runs to Sat 02:30; Thu 11-26 is "market closed" with no box window
  V3  COLLISION: a planned box row at 09:25-09:35 hits the wake + sweep and RTH; 16:33-17:00 is clear of a 14-min
      close and hits a 40-min one; two overlapping planned box rows hit each other; a control row over RTH is never
      flagged; a moment inside RTH is flagged; a boxes-ro (read-only ssh) row inside RTH is clear, one over the
      wake + sweep is flagged
  V4  a timer firing more than RECUR_MAX times in the window is one "recurring" row; a daily one is one row per fire
  V5  the load line: "tonight (now to <next wake>): N planned, M timers; heavy|light"; heavy on a collision tonight
      or 3+ planned rows tonight; the window ends 17:00 ET tomorrow (--days 7: seven days on)
  V6  read only: the only commands are systemctl list-units / show and systemd-analyze calendar; no file is opened
      for writing; the markdown has one row per block, sorted by start
BORN RED on 613fb1d (r579): there is no tools/calendar_view.py.

Run:  python3 tests/check_calendar_view.py
"""
import ast
import os
import sys
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)
ET = ZoneInfo("America/New_York")
FAILS, RAN = [], []


def ck(n, ok, msg=""):
    RAN.append(n)
    print(f"  {n:<3} {'PASS' if ok else 'FAIL'}  {msg if not ok else ''}")
    if not ok:
        FAILS.append(n)


UNITS = [
    {"id": "dtp-morning.timer", "calendars": ["Mon..Fri *-*-* 09:15:00 America/New_York"], "last_min": 1.0},
    {"id": "dtp-eod-conductor.timer", "calendars": ["Mon..Fri *-*-* 16:05:00 America/New_York"], "last_min": 14.0},
    {"id": "dtp-study-dispatch.timer", "calendars": ["Mon..Thu *-*-* 17:15:00 America/New_York",
                                                     "Fri *-*-* 17:15:00 America/New_York"], "last_min": None},
    {"id": "dtp-daily-recap.timer", "calendars": ["Mon..Fri *-*-* 17:00:00 America/New_York"], "last_min": 9.0},
    {"id": "dtp-scratch-purge.timer", "calendars": ["*-*-* *:00/30:00"], "last_min": 0.0},
]
HEAD = "date\tstart\tend\twhat\ttouches\n"


def planned(tmp, body, name="p.tsv"):
    p = os.path.join(tmp, name)
    with open(p, "w") as fh:
        fh.write(body)
    return p


def find(cal, what, day=None):
    return [b for b in cal["rows"] if what in b["what"] and (day is None or b["start"].strftime("%m-%d") == day)]


def main():
    try:
        import calendar_view as CV
    except ImportError as e:
        print(f"  V1  FAIL  no tools/calendar_view.py: {e}")
        print("\nFAILED: V1")
        return 1
    tmp = tempfile.mkdtemp(prefix="calv_")
    now = datetime(2026, 11, 23, 17, 30, tzinfo=ET)

    # V1
    p1 = planned(tmp, "# a comment\n" + HEAD +
                 "2026-11-24\t~17:45\t~18:30\treview\tcontrol\n"
                 "2026-11-24\t23:30\t01:00\tovernight job\tcontrol\n"
                 "2026-11-27\t\t\tday item\tcontrol\n"
                 "2026-11-24\t25:00\t\tbad time\tboxes\n"
                 "2026-11-24\t10:00\t\tbad touches\tfleet\n"
                 "2026-11-24\t\t10:00\tend no start\tnone\n")
    rows, bad = CV.load_planned(p1)
    byw = {r["what"]: r for r in rows}
    ck("V1", len(rows) == 3 and len(bad) == 3 and all("row" in b for b in bad)
       and byw["review"]["note"] == "times are about"
       and byw["overnight job"]["end"].day == 25 and byw["day item"].get("timeless")
       and CV.load_planned(planned(tmp, "a\tb\n", "h.tsv"))[1][0].startswith("planned file header")
       and CV.load_planned(os.path.join(tmp, "missing.tsv"))[1][0].startswith("planned file"),
       f"rows {[r['what'] for r in rows]} bad {bad}")

    # V2
    cal = CV.build(now, 5, planned(tmp, HEAD, "empty.tsv"), units=UNITS)

    def hm(b):
        return (b["start"].strftime("%m-%d %H:%M"), b["end"].strftime("%m-%d %H:%M") if b["end"] else None)
    w24, r24 = find(cal, "wake + boot sweep", "11-24"), find(cal, "RTH", "11-24")
    c24, s24 = find(cal, "the close", "11-24"), find(cal, "study dispatch", "11-24")
    r27, s27 = find(cal, "half day", "11-27"), find(cal, "study dispatch", "11-27")
    ck("V2", [hm(b) for b in w24] == [("11-24 09:15", "11-24 09:30")]
       and [hm(b) for b in r24] == [("11-24 09:30", "11-24 16:00")]
       and [hm(b) for b in c24] == [("11-24 16:05", "11-24 16:19")]
       and [hm(b) for b in s24] == [("11-24 17:15", "11-25 07:30")]
       and [hm(b) for b in r27] == [("11-27 09:30", "11-27 13:00")] and "NO TRADING" in r27[0]["what"]
       and [hm(b) for b in s27] == [("11-27 17:15", "11-28 02:30")]
       and find(cal, "market closed", "11-26") and not [b for b in cal["rows"] if b["start"].strftime("%m-%d") == "11-26"
                                                         and b["touches"] == "boxes"],
       f"{[hm(b) for b in w24 + r24 + c24 + s24 + r27 + s27]}")

    # V3
    p3 = planned(tmp, HEAD +
                 "2026-11-24\t09:25\t09:35\tbot-log copy\tboxes\n"
                 "2026-11-24\t16:33\t17:00\tprobe\tboxes\n"
                 "2026-11-24\t16:50\t17:05\tsecond box job\tboxes\n"
                 "2026-11-24\t11:00\t12:00\tcontrol job\tcontrol\n"
                 "2026-11-24\t12:00\t\tmoment in RTH\tboxes\n"
                 "2026-11-24\t09:41\t09:50\tro read in RTH\tboxes-ro\n"
                 "2026-11-24\t09:20\t09:25\tro read in sweep\tboxes-ro\n", "p3.tsv")
    cal = CV.build(now, 1, p3, units=UNITS)
    f = {b["what"]: b["flag"] for b in cal["rows"] if b["source"] == "planned"}
    u40 = [dict(u, last_min=40.0) if u["id"] == "dtp-eod-conductor.timer" else u for u in UNITS]
    p3b = planned(tmp, HEAD + "2026-11-24\t16:33\t17:00\tprobe\tboxes\n", "p3b.tsv")
    f40 = {b["what"]: b["flag"] for b in CV.build(now, 1, p3b, units=u40)["rows"] if b["source"] == "planned"}
    f14 = {b["what"]: b["flag"] for b in CV.build(now, 1, p3b, units=UNITS)["rows"] if b["source"] == "planned"}
    ck("V3", "wake + boot sweep" in f["bot-log copy"] and "RTH" in f["bot-log copy"]
       and f14["probe"] == "" and "the close" in f40["probe"]
       and "planned: second box job" in f["probe"] and "planned: probe" in f["second box job"]
       and f["control job"] == "" and "RTH" in f["moment in RTH"] and f["ro read in RTH"] == ""
       and f["ro read in sweep"] == "COLLISION with wake + boot sweep" and len(cal["collisions"]) == 5, f"{f} / {f40}")

    # V4
    cal = CV.build(now, 1, planned(tmp, HEAD, "e4.tsv"), units=UNITS)
    rec = find(cal, "dtp-scratch-purge.timer")
    rc = find(cal, "dtp-daily-recap.timer")
    ck("V4", len(rec) == 1 and "recurring" in rec[0]["what"] and len(rc) == 1 and rc[0]["end"] is None,
       f"{[b['what'] for b in rec]} {[b['what'] for b in rc]}")

    # V5
    p5 = planned(tmp, HEAD + "2026-11-23\t18:00\t18:30\ta\tcontrol\n2026-11-23\t19:00\t19:30\tb\tcontrol\n"
                 "2026-11-23\t20:00\t20:30\tc\tnone\n", "p5.tsv")
    cal = CV.build(now, 1, p5, units=UNITS)
    cl = CV.build(now, 1, planned(tmp, HEAD + "2026-11-23\t18:00\t18:30\ta\tcontrol\n", "p5b.tsv"), units=UNITS)
    cc = CV.build(now, 1, planned(tmp, HEAD + "2026-11-23\t17:20\t17:40\tx\tboxes\n", "p5c.tsv"), units=UNITS)
    c7 = CV.build(now, 7, planned(tmp, HEAD, "p5d.tsv"), units=UNITS)
    ck("V5", cal["summary"] == "tonight (now to Tue 11-24 09:15 ET): 3 planned, 1 timers; heavy"
       and cl["summary"].endswith("1 planned, 1 timers; light") and cc["summary"].endswith("; heavy")
       and cal["hi"] == datetime(2026, 11, 24, 17, 0, tzinfo=ET) and c7["hi"] == datetime(2026, 11, 30, 17, 0, tzinfo=ET),
       f"{cal['summary']} | {cl['summary']} | {cc['summary']}")

    # V6
    src = open(os.path.join(ROOT, "tools", "calendar_view.py")).read()
    tree = ast.parse(src)
    cmds = []
    for n in ast.walk(tree):
        if isinstance(n, ast.List) and n.elts and isinstance(n.elts[0], ast.Constant) and \
                n.elts[0].value in ("systemctl", "systemd-analyze"):
            cmds.append(n.elts[0].value)
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "open":
            for a in list(n.args[1:]) + [k.value for k in n.keywords if k.arg == "mode"]:
                if isinstance(a, ast.Constant) and any(c in str(a.value) for c in "wax+"):
                    cmds.append("WRITE")
    md = CV.render_md(CV.build(now, 1, p3, units=UNITS))
    trs = [ln for ln in md.splitlines() if ln.startswith("| ") and not ln.startswith("| When")]
    n_rows = len(CV.build(now, 1, p3, units=UNITS)["rows"])
    ck("V6", "WRITE" not in cmds and set(cmds) <= {"systemctl", "systemd-analyze"}
       and "subprocess.Popen" not in src and "os.system" not in src and len(trs) == n_rows
       and "COLLISIONS: 5" in md, f"cmds {cmds} rows {len(trs)} vs {n_rows}")

    print()
    if FAILS:
        print(f"FAILED: {' '.join(FAILS)}")
        return 1
    print(f"ALL {len(RAN)} PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
