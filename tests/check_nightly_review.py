#!/usr/bin/env python3
"""
day_trader_pro/tests/check_nightly_review.py  v1.2
v1.2  2026-11-08  dtp r537 / SWEEP.7 — THE REVIEW'S SCRATCH LIVES IN ITS OWN DIR ON DISK AND IS REMOVED.
  N12 the wrapper for real with a fake claude that writes scratch to $TMPDIR: TMPDIR is a fresh
      <WORK_ROOT>/<day>-<epoch>-<pid> dir (never /tmp), the RUN PARAMETERS name it, and it is gone after a run that
      PRODUCED and after one that wrote no review; a killed run's dir older than 2 days is pruned at the next start,
      a younger one and a non-run dir are kept; the prompt forbids /tmp
v1.1  2026-11-07  dtp r525 / RPT.37 — GIVEBACK WITHOUT PARK, AND HUNT BY CALL AND PUT (tools/review_kit.py v1.1).
  N9  giveback without PARK on the fixture (the hand-computed ex-PARK giveback, peak open, share and green-to-red
      beside the overall); a seven-column giveback.csv is migrated in place (every old row and cell kept, six
      columns appended) and the day's row is written with all thirteen
  N10 hunt DAY: LiquidityHunt split long -> call, short -> put; the day and the window to date (n, net, win %, EV a
      trade); fees BESIDE (never inside EV), the estimate counted in fees_est; other setups and OTV4TEST rows
      excluded; an unknown direction refuses; upserts hunt_side.csv, a re-run never double-appends
  N11 backfill FROM TO: the recorded giveback cells are never rewritten (a recomputed cell that differs is a printed
      MISMATCH), the new cells are appended, the hunt rows are written; a second run changes nothing; the prompt
      asks for both tracks
v1.0  2026-11-07  dtp r524 / RPT.36 — THE NIGHTLY REVIEW RUNS FROM A SYSTEMD TIMER (tools/nightly_review.sh,
      tools/review_kit.py, tools/dtp-nightly-review{,-check}.{service,timer}, tools/install_nightly_review.sh).
  N1  the four units pass `systemd-analyze verify`; each service's ExecStart is the landed nightly_review.sh
  N2  the calendars resolve IN ET across a DST change: the review timer elapses only at 16:40 and 13:40 ET, Mon-Fri,
      and is Persistent; the check timer only at 18:30 ET, Mon-Fri, not Persistent
  N3  review_kit due: the session whose close + 40 min has passed (16:40 ET; 13:40 on the 11-27 half day); a
      holiday (11-26), a weekend and a pre-close run name the previous session
  N4  the wrapper, run for real with a fake claude: a due day with no review runs ONE isolated session
      (--session-id, never --continue) with VERTIGO_UNATTENDED=1 and the OUT path, and records PRODUCED; an existing
      review, a fresh in-flight marker and a not-due clock each stand down without calling claude; --day refuses a
      session not yet closed
  N5  --check-missing at 18:30: a missing review on a session day posts ONE line naming the day (exit 1); a present
      review, a holiday and a weekend post nothing; a router that is not alive also leaves the marker file
  N6  review_kit upsert REPLACES the day's rows (a re-run never double-appends), drops a non-date junk row (the
      11-07 '--help' row), keeps every other row and refuses a header that differs; a non-date day writes nothing
  N7  review_kit giveback and window on a fixture: the hand-computed giveback, peak open, green-to-red, EV, fees
      beside (model fee when present, else the $1.25 / $2.47 SPX estimate), ex worst setup / symbol
  N8  the prompt carries the operator's rules and every nightly track; the installer parses and installs the four
      units and nothing else
"""
import csv
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOLS = os.path.join(ROOT, "tools")
sys.path.insert(0, TOOLS)
sys.path.insert(0, ROOT)
ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")
FAILS, RAN = [], []
TMP = tempfile.mkdtemp(prefix="check_nightly_review_")
WRAP = os.path.join(TOOLS, "nightly_review.sh")
UNITS = ["dtp-nightly-review.service", "dtp-nightly-review.timer", "dtp-nightly-review-check.service",
         "dtp-nightly-review-check.timer"]


def ck(n, ok, msg):
    RAN.append(n)
    print(f"  {n:<4} {'PASS' if ok else 'FAIL'}  {msg}")
    if not ok:
        FAILS.append(n)


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


# ── N1 ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
vdir = os.path.join(TMP, "units")
os.makedirs(vdir)
for u in UNITS:
    shutil.copy(os.path.join(TOOLS, u), vdir)
r = subprocess.run(["systemd-analyze", "verify"] + [os.path.join(vdir, u) for u in UNITS], capture_output=True,
                   text=True)
ours = [l for l in (r.stdout + r.stderr).splitlines() if "nightly-review" in l]
execs = [re.search(r"^ExecStart=(.*)$", read(os.path.join(TOOLS, u)), re.M).group(1)
         for u in UNITS if u.endswith(".service")]
ck("N1", r.returncode == 0 and not ours
   and execs == ["/bin/bash /home/ubuntu/day_trader_pro/tools/nightly_review.sh",
                 "/bin/bash /home/ubuntu/day_trader_pro/tools/nightly_review.sh --check-missing"],
   "verify rc=%d own lines=%s exec=%s" % (r.returncode, ours[:2], execs))


# ── N2 ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
def elapses(spec, base):
    out = subprocess.run(["systemd-analyze", "calendar", "--iterations=12", "--base-time=" + base, spec],
                         capture_output=True, text=True, env=dict(os.environ, TZ="UTC")).stdout
    return [datetime.strptime(m, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC).astimezone(ET)
            for m in re.findall(r"(?:Next elapse|Iteration #\d+): \w{3} (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) UTC", out)]


def timer_et(unit, bases=("2026-11-05 12:00:00 UTC", "2027-03-10 12:00:00 UTC")):
    txt = read(os.path.join(TOOLS, unit))
    specs = re.findall(r"^OnCalendar=(.*)$", txt, re.M)
    hits = [t for s in specs for b in bases for t in elapses(s, b)]
    return specs, hits, re.search(r"^Persistent=(\w+)$", txt, re.M).group(1)


specs, hits, pers = timer_et("dtp-nightly-review.timer")
hm = sorted({t.strftime("%H:%M") for t in hits})
ok_rev = (hm == ["13:40", "16:40"] and all(t.weekday() < 5 for t in hits) and len(hits) >= 40 and pers == "true"
          and any(t.utcoffset() == timedelta(hours=-4) for t in hits) and any(t.utcoffset() == timedelta(hours=-5)
                                                                                for t in hits))
specs2, hits2, pers2 = timer_et("dtp-nightly-review-check.timer")
hm2 = sorted({t.strftime("%H:%M") for t in hits2})
ok_chk = hm2 == ["18:30"] and all(t.weekday() < 5 for t in hits2) and len(hits2) >= 20 and pers2 == "false"
ck("N2", ok_rev and ok_chk, "review ET %s n=%d Persistent=%s (EST and EDT both seen); check ET %s n=%d Persistent=%s"
   % (hm, len(hits), pers, hm2, len(hits2), pers2))

# ── N3 ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
import review_kit as K  # noqa: E402

cases = {"2026-11-06T16:39": "2026-11-05", "2026-11-06T16:40": "2026-11-06", "2026-11-07T03:00": "2026-11-06",
         "2026-11-09T13:40": "2026-11-06", "2026-11-09T16:41": "2026-11-09", "2026-11-26T18:30": "2026-11-25",
         "2026-11-27T13:39": "2026-11-25", "2026-11-27T13:40": "2026-11-27", "2026-11-30T09:00": "2026-11-27"}
got = {n: K.due(datetime.fromisoformat(n).replace(tzinfo=ET)) for n in cases}
bad = {n: (got[n], cases[n]) for n in cases if got[n] != cases[n]}
ck("N3", not bad, "%d clock cases (full day, 11-27 half day, 11-26 holiday, weekend, pre-close); wrong=%s"
   % (len(cases), bad))

# ── N4 / N5: the wrapper for real, with a fake claude and a fake page ──────────────────────────────────────────────
FAKE = os.path.join(TMP, "fake_claude.sh")
CALLS = os.path.join(TMP, "claude_calls.txt")
with open(FAKE, "w") as fh:
    fh.write("#!/bin/bash\n"
             "printf 'ARGS %s\\n' \"$*\" | head -c 300 >> " + CALLS + "; echo >> " + CALLS + "\n"
             "echo \"UNATTENDED=${VERTIGO_UNATTENDED:-unset}\" >> " + CALLS + "\n"
             "out=$(printf '%s' \"$*\" | sed -n 's/.*write the finished review to exactly this path: \\([^ ]*\\).*/\\1/p'"
             " | head -1)\n"
             "[ -n \"$out\" ] && echo '# fake review' > \"$out\"\n"
             "exit 0\n")
os.chmod(FAKE, 0o755)
POSTS = os.path.join(TMP, "posts.txt")
FAKE_POST = os.path.join(TMP, "fake_post.sh")
with open(FAKE_POST, "w") as fh:
    fh.write("#!/bin/bash\nprintf '%s\\n' \"$*\" >> " + POSTS + "\n")
os.chmod(FAKE_POST, 0o755)


def wrap(args, now, reviews, alive="true", extra=None):
    env = dict(os.environ, NIGHTLY_REVIEW_CLAUDE=FAKE, NIGHTLY_REVIEW_DIR=reviews,
               NIGHTLY_REVIEW_LOG=os.path.join(TMP, "log"), NIGHTLY_REVIEW_LEDGER=os.path.join(TMP, "ledger"),
               NIGHTLY_REVIEW_MARKER=os.path.join(TMP, "marker"), NIGHTLY_REVIEW_POST=FAKE_POST,
               NIGHTLY_REVIEW_ALIVE=alive, NIGHTLY_REVIEW_MISSING_FLAG=os.path.join(TMP, "MISSING.txt"),
               NIGHTLY_REVIEW_PY=sys.executable)
    env.pop("VERTIGO_UNATTENDED", None)
    if now:
        env["NIGHTLY_REVIEW_NOW"] = now
    env.update(extra or {})
    return subprocess.run(["bash", WRAP] + args, capture_output=True, text=True, env=env, timeout=120)


def calls():
    return read(CALLS) if os.path.exists(CALLS) else ""


def reset(*paths):
    for p in paths:
        if os.path.isdir(p):
            shutil.rmtree(p)
        elif os.path.exists(p):
            os.remove(p)


rv = os.path.join(TMP, "reviews")
os.makedirs(rv)
read_ledger = lambda: read(os.path.join(TMP, "ledger")) if os.path.exists(os.path.join(TMP, "ledger")) else ""
# a due day, no review: one isolated session, the env, the OUT path, PRODUCED
reset(CALLS)
a = wrap([], "2026-11-06T16:41", rv)
c1 = calls()
produced = os.path.exists(os.path.join(rv, "2026-11-06.md")) and "PRODUCED" in read_ledger()
iso = "--session-id" in c1 and "--continue" not in c1 and " -c " not in c1 and c1.count("ARGS") == 1
unatt = "UNATTENDED=1" in c1
# the review exists: stands down, claude not called
reset(CALLS)
b = wrap([], "2026-11-06T18:00", rv)
stood = "STOOD_DOWN exists" in read_ledger() and calls() == ""
# a fresh in-flight marker: stands down
os.remove(os.path.join(rv, "2026-11-06.md"))
open(os.path.join(TMP, "marker"), "w").close()
reset(CALLS)
c = wrap([], "2026-11-06T18:00", rv)
inflight = "STOOD_DOWN inflight" in read_ledger() and calls() == ""
reset(os.path.join(TMP, "marker"))
# not due (a Saturday morning whose session's review exists is still a stand-down; a pre-close Monday names Friday)
open(os.path.join(rv, "2026-11-06.md"), "w").write("x")
reset(CALLS)
d = wrap([], "2026-11-09T10:00", rv)
notdue = calls() == "" and "STOOD_DOWN exists" in read_ledger().splitlines()[-1]
# --day refuses a session that has not closed (real clock: a far-future day)
reset(CALLS)
e = wrap(["--day", "2099-01-05"], None, rv)
refused = e.returncode == 2 and calls() == ""
pc = wrap(["--print-cmd"], None, rv).stdout
ck("N4", produced and iso and unatt and stood and inflight and notdue and refused and "--session-id" in pc
   and "--continue" not in pc,
   "produced=%s isolated=%s unattended=%s exists=%s inflight=%s notdue=%s day-refused=%s rc=%s/%s/%s/%s/%s"
   % (produced, iso, unatt, stood, inflight, notdue, refused, a.returncode, b.returncode, c.returncode,
      d.returncode, e.returncode))

# N5
reset(POSTS, os.path.join(TMP, "MISSING.txt"))
os.remove(os.path.join(rv, "2026-11-06.md"))
m1 = wrap(["--check-missing"], "2026-11-06T18:30", rv)
p1 = read(POSTS) if os.path.exists(POSTS) else ""
one = m1.returncode == 1 and p1.count("NIGHTLY REVIEW MISSING for 2026-11-06") == 1 and \
    not os.path.exists(os.path.join(TMP, "MISSING.txt"))
reset(POSTS)
m2 = wrap(["--check-missing"], "2026-11-06T18:30", rv, alive="false")
marker = m2.returncode == 1 and os.path.exists(os.path.join(TMP, "MISSING.txt")) and os.path.exists(POSTS)
reset(POSTS)
open(os.path.join(rv, "2026-11-06.md"), "w").write("x")
m3 = wrap(["--check-missing"], "2026-11-06T18:30", rv)
m4 = wrap(["--check-missing"], "2026-11-26T18:30", rv)      # Thanksgiving
m5 = wrap(["--check-missing"], "2026-11-07T18:30", rv)      # Saturday
quiet = not os.path.exists(POSTS) and m3.returncode == 0 and m4.returncode == 0 and m5.returncode == 0
ck("N5", one and marker and quiet, "missing->one post=%s router down->marker=%s present/holiday/weekend quiet=%s"
   % (one, marker, quiet))

# ── N6 ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
gb = os.path.join(TMP, "giveback.csv")
with open(gb, "w") as fh:
    fh.write(K.GIVEBACK_HDR + "\n--help,0,0.00,0.00,0.00,0,0.00\n2026-11-05,23,1,2,3,4,5\n2026-11-06,1,1,1,1,1,1\n")
K.upsert(gb, "2026-11-06", K.GIVEBACK_HDR, ["2026-11-06,16,2,2,2,2,2"])
K.upsert(gb, "2026-11-06", K.GIVEBACK_HDR, ["2026-11-06,16,2,2,2,2,2"])
lines = read(gb).splitlines()
rep = (lines == [K.GIVEBACK_HDR, "2026-11-05,23,1,2,3,4,5", "2026-11-06,16,2,2,2,2,2"])
try:
    K.upsert(gb, "2026-11-06", "date,trades", ["2026-11-06,1"])
    hdr_refused = False
except SystemExit:
    hdr_refused = read(gb).splitlines() == lines
try:
    K.upsert(gb, "--help", K.GIVEBACK_HDR, ["--help,0,0,0,0,0,0"])
    junk_refused = False
except SystemExit:
    junk_refused = read(gb).splitlines() == lines
ck("N6", rep and hdr_refused and junk_refused, "replace twice -> one row, junk row gone=%s; header mismatch refused=%s;"
   " non-date day refused=%s" % (rep, hdr_refused, junk_refused))

# ── N7 ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
fx = os.path.join(TMP, "fx")
os.makedirs(os.path.join(fx, "trades"))
os.makedirs(os.path.join(fx, "scripts"))
_live_theories = os.path.join(os.path.expanduser("~"), "reviews", "scripts", "theories.py")
if os.path.exists(_live_theories):
    shutil.copy(_live_theories, os.path.join(fx, "scripts"))
else:  # a minimal stand-in with the two names review_kit uses
    with open(os.path.join(fx, "scripts", "theories.py"), "w") as fh:
        fh.write("from datetime import datetime\nfrom zoneinfo import ZoneInfo\nET = ZoneInfo('America/New_York')\n"
                 "FILTERS = [(l, (lambda x: True)) for l in ('baseline', 'T1 no SPX', 'T2 no entries after 10:01',"
                 " 'T3 no GEXPin/PARK', 'T1+T2', 'T1+T3', 'T1+T2+T3')]\n"
                 "def norm(sym, strat, pnl, entry_iso):\n"
                 "    t = datetime.fromisoformat(entry_iso.replace('Z', '+00:00')).astimezone(ET)\n"
                 "    return dict(sym=sym, strat=strat, pnl=float(pnl), day=t.date().isoformat(),"
                 " sec=t.hour * 3600 + t.minute * 60 + t.second)\n")
rows = [  # sym, strat, contracts, entry, exit, mfe, pnl, entry ET, fee
    ("SPX", "PARK", 1, 40.0, 30.0, 45.0, -1000.0, "2026-11-05T11:01:00-05:00", ""),
    ("AMD", "LiquidityHunt", 2, 2.0, 3.0, 3.5, 200.0, "2026-11-05T09:40:00-05:00", "5.00"),
    ("QQQ", "Breakout", 1, 1.0, 0.8, 1.2, -20.0, "2026-11-06T09:50:00-05:00", ""),
    ("AMD", "RunawayContinuation", 4, 1.0, 1.5, 1.5, 200.0, "2026-11-06T09:35:00-05:00", ""),
]
for day in ("2026-11-05", "2026-11-06"):
    with open(os.path.join(fx, "trades", day + ".csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=K.TRADE_COLS)
        w.writeheader()
        for i, (s, st_, c, e, x, mf, p, t, fee) in enumerate(rows):
            if t[:10] == day:
                w.writerow(dict(sym=s, trade_id="t%d" % i, strategy=st_, direction="long", contracts=c,
                                entry_premium=e, exit_premium=x, pnl_usd=p, entry_time=t, exit_time=t,
                                exit_reason="x", fee=fee, mfe_premium=mf))
os.environ["DTP_REVIEWS_DIR"] = fx
K.REVIEWS = fx
g = K.cmd_giveback("2026-11-05", write=False)
# SPX: peak 45 > entry 40, exit 30: giveback (45-40)*100 = 500, peak open 500, green-to-red (-1000);
# AMD: peak 3.5, exit 3.0: giveback 0.5*2*100 = 100, peak open 1.5*2*100 = 300
g_ok = (abs(g["giveback"] - 600) < 1e-6 and abs(g["peak_open"] - 800) < 1e-6 and g["g2r_n"] == 1
        and abs(g["g2r_usd"] + 1000) < 1e-6 and abs(g["kept"] + 800) < 1e-6)
wv = K.window("2026-11-06")
# n 4, total -620, EV -155; fees: SPX 2.47 est, AMD 5.00 model, QQQ 1.25 est, AMD 4 x 1.25 = 5.00 est -> 13.72
w_ok = (wv["n"] == 4 and abs(wv["total"] + 620) < 1e-6 and abs(wv["ev"] + 155) < 1e-6
        and abs(wv["fees"] - 13.72) < 1e-6 and abs(wv["fees_est"] - 8.72) < 1e-6
        and wv["worst_setup"] == "PARK" and abs(wv["ev_ex_setup"] - 380 / 3) < 1e-6
        and wv["worst_sym"] == "SPX" and abs(wv["ev_ex_sym"] - 380 / 3) < 1e-6 and wv["lo"] is not None)
ck("N7", g_ok and w_ok, "giveback %.0f peak %.0f g2r %d/%.0f kept %.0f; window n=%d EV %.2f fees %.2f (est %.2f) "
   "worst %s/%s" % (g["giveback"], g["peak_open"], g["g2r_n"], g["g2r_usd"], g["kept"], wv["n"], wv["ev"],
                    wv["fees"], wv["fees_est"], wv["worst_setup"], wv["worst_sym"]))

# ── N8 ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
pr = read(os.path.join(TOOLS, "nightly_review.prompt"))
need = ["READ ONLY", "Never land", "Environment block", "No box reads", "OTV4TEST", "BESIDE EV, never inside",
        "window EV and its interval", "premarket_lead.csv", "decay_vs_own.csv", "cont_gate_park.csv", "theories",
        "window_ev", "giveback", "TO SPEC or BROKEN", "NQ=F", "upsert", "they/them", "retired strategies"]
miss = [n for n in need if n not in pr]
inst = read(os.path.join(TOOLS, "install_nightly_review.sh"))
inst_units = re.findall(r"dtp-nightly-review[\w.-]*\.(?:service|timer)", inst.split("for u in", 1)[1].split("do", 1)[0])
bn = subprocess.run(["bash", "-n", os.path.join(TOOLS, "install_nightly_review.sh")]).returncode
ck("N8", not miss and sorted(inst_units) == sorted(UNITS) and bn == 0,
   "prompt missing=%s installer units=%s bash -n rc=%d" % (miss, inst_units, bn))

# ── N9 ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
gbp = os.path.join(fx, "giveback.csv")
with open(gbp, "w") as fh:
    fh.write(K.GIVEBACK_HDR_V1 + "\n2026-11-04,25,6334.00,16564.50,5409.00,8,-4821.50\n")
g9 = K.cmd_giveback("2026-11-05", write=True)
gl = read(gbp).splitlines()
# ex PARK: AMD only - giveback 100, peak open 300 (33.33%), no green-to-red; overall 600 of 800 = 75%
n9 = (abs(g9["x_giveback"] - 100) < 1e-6 and abs(g9["x_peak_open"] - 300) < 1e-6 and abs(g9["x_pct"] - 100 / 3.0) < 1e-6
      and g9["x_g2r_n"] == 0 and abs(g9["pct"] - 75.0) < 1e-6
      and gl[0] == K.GIVEBACK_HDR and gl[0].startswith(K.GIVEBACK_HDR_V1 + ",")
      and gl[1] == "2026-11-04,25,6334.00,16564.50,5409.00,8,-4821.50,,,,,,"
      and gl[2] == "2026-11-05,2,600.00,800.00,-800.00,1,-1000.00,75.00,100.00,300.00,33.33,0,0.00"
      and all(l.count(",") == K.GIVEBACK_HDR.count(",") for l in gl))
ck("N9", n9, "ex-PARK %.0f of %.0f (%.2f%%) vs overall %.2f%%; file=%s" % (g9["x_giveback"], g9["x_peak_open"],
                                                                         g9["x_pct"] or -1, g9["pct"] or -1, gl[1:]))

# ── N10 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
fx2 = os.path.join(TMP, "fx2")
os.makedirs(os.path.join(fx2, "trades"))
shutil.copytree(os.path.join(fx, "scripts"), os.path.join(fx2, "scripts"))
hrows = [  # day, sym, strategy, direction, contracts, pnl, fee
    ("2026-11-04", "SPX", "LiquidityHunt", "long", 1, 500.0, "3.00"),
    ("2026-11-04", "AMD", "LiquidityHunt", "short", 2, -100.0, ""),       # est 2 x 1.25 = 2.50
    ("2026-11-05", "QQQ", "LiquidityHunt", "long", 1, -50.0, "1.50"),
    ("2026-11-05", "QQQ", "LiquidityHunt", "short", 1, 80.0, "1.00"),
    ("2026-11-05", "SPX", "LiquidityHunt", "short", 1, 20.0, ""),        # est 2.47
    ("2026-11-05", "AMD", "RunawayContinuation", "long", 1, 999.0, "1.00"),
    ("2026-11-05", "AAL", "LiquidityHunt", "long", 1, 777.0, "1.00"),     # OTV4TEST
]
for day in ("2026-11-04", "2026-11-05"):
    with open(os.path.join(fx2, "trades", day + ".csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=K.TRADE_COLS)
        w.writeheader()
        for i, (d, s_, st_, dr, c, p_, fee) in enumerate(hrows):
            if d == day:
                w.writerow(dict(sym=s_, trade_id="h%d" % i, strategy=st_, direction=dr, contracts=c, entry_premium=1,
                                exit_premium=1, pnl_usd=p_, entry_time=d + "T09:40:00-05:00",
                                exit_time=d + "T09:45:00-05:00", exit_reason="x", fee=fee, mfe_premium=1))
K.REVIEWS = fx2
h = K.cmd_hunt("2026-11-05", write=True)
K.cmd_hunt("2026-11-05", write=True)
hl = read(os.path.join(fx2, "hunt_side.csv")).splitlines()
dc, cc = h["call"]
dp, cp = h["put"]
n10 = (dc["n"] == 1 and dc["net"] == -50 and dc["win"] == 0 and dc["ev"] == -50 and abs(dc["fees"] - 1.5) < 1e-9
       and cc["n"] == 2 and cc["net"] == 450 and cc["win"] == 50 and cc["ev"] == 225 and abs(cc["fees"] - 4.5) < 1e-9
       and dp["n"] == 2 and dp["net"] == 100 and dp["win"] == 100 and abs(dp["fees_est"] - 2.47) < 1e-9
       and cp["n"] == 3 and cp["net"] == 0 and abs(cp["ev"]) < 1e-9 and abs(cp["fees"] - 5.97) < 1e-9
       and abs(cp["fees_est"] - 4.97) < 1e-9 and hl[0] == K.HUNT_HDR and len(hl) == 3
       and hl[1] == "2026-11-05,call,1,-50.00,0.00,-50.00,1.50,0.00,2,450.00,50.00,225.00,4.50,0.00"
       and hl[2] == "2026-11-05,put,2,100.00,100.00,50.00,3.47,2.47,3,0.00,66.67,0.00,5.97,4.97")
with open(os.path.join(fx2, "trades", "2026-11-06.csv"), "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=K.TRADE_COLS)
    w.writeheader()
    w.writerow(dict(sym="QQQ", trade_id="hx", strategy="LiquidityHunt", direction="sideways", contracts=1,
                    entry_premium=1, exit_premium=1, pnl_usd=1, entry_time="2026-11-06T09:40:00-05:00",
                    exit_time="2026-11-06T09:45:00-05:00", exit_reason="x", fee="", mfe_premium=1))
try:
    K.hunt("2026-11-06")
    bad_dir = False
except SystemExit:
    bad_dir = True
os.remove(os.path.join(fx2, "trades", "2026-11-06.csv"))
ck("N10", n10 and bad_dir, "call day %s window %s | put day %s window %s | rows=%d unknown direction refused=%s"
   % ((dc["n"], dc["net"]), (cc["n"], cc["net"], cc["ev"]), (dp["n"], dp["net"]), (cp["n"], cp["net"], cp["fees"]),
      len(hl) - 1, bad_dir))

# ── N11 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
gb2 = os.path.join(fx2, "giveback.csv")
with open(gb2, "w") as fh:   # 11-04 recorded with a DIFFERENT figure than the recompute: it must be kept
    fh.write(K.GIVEBACK_HDR_V1 + "\n2026-11-04,2,1.00,2.00,3.00,4,5.00\n")
days11, mism11 = K.cmd_backfill("2026-10-26", "2026-11-05")
b1 = read(gb2)
h1 = read(os.path.join(fx2, "hunt_side.csv"))
K.cmd_backfill("2026-10-26", "2026-11-05")
gl2 = b1.splitlines()
n11 = (days11 == ["2026-11-04", "2026-11-05"] and [m[0] for m in mism11] == ["2026-11-04"]
       and gl2[1].startswith("2026-11-04,2,1.00,2.00,3.00,4,5.00,") and gl2[1].count(",") == K.GIVEBACK_HDR.count(",")
       and gl2[2].startswith("2026-11-05,") and len(gl2) == 3
       and read(gb2) == b1 and read(os.path.join(fx2, "hunt_side.csv")) == h1 and len(h1.splitlines()) == 5
       and "python $K hunt DAY" in pr and "without PARK" in pr and "hunt_side.csv" in pr)
ck("N11", n11, "days=%s mismatches=%s kept=%s idempotent=%s prompt=%s" % (
    days11, [m[0] for m in mism11], gl2[1][:34], read(gb2) == b1, "python $K hunt DAY" in pr))

# ── N12 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
WR = os.path.join(TMP, "work_root")
os.makedirs(WR)
FAKE12 = os.path.join(TMP, "fake_claude12.sh")
SEEN12 = os.path.join(TMP, "seen12.txt")
with open(FAKE12, "w") as fh:
    fh.write("#!/bin/bash\n"
             "echo \"TMPDIR=$TMPDIR\" >> " + SEEN12 + "\n"
             "printf '%s' \"$*\" | grep -o 'WORK      [^ ]*' >> " + SEEN12 + "; echo >> " + SEEN12 + "\n"
             "head -c 4096 /dev/zero > \"$TMPDIR/derived_dump.json\"\n"
             "out=$(printf '%s' \"$*\" | sed -n 's/.*write the finished review to exactly this path: \\([^ ]*\\).*/\\1/p'"
             " | head -1)\n"
             "[ \"${FAKE12_WRITE:-1}\" = 1 ] && [ -n \"$out\" ] && echo '# fake review' > \"$out\"\n"
             "exit 0\n")
os.chmod(FAKE12, 0o755)
stale = os.path.join(WR, "2026-11-01-1000")
young = os.path.join(WR, "2026-11-05-2000")
keep = os.path.join(WR, "notes")
for dpath in (stale, young, keep):
    os.makedirs(dpath)
old_t = datetime.now().timestamp() - 3 * 86400
os.utime(stale, (old_t, old_t))
rv12 = os.path.join(TMP, "reviews12")
os.makedirs(rv12)
x12 = {"NIGHTLY_REVIEW_CLAUDE": FAKE12, "NIGHTLY_REVIEW_WORK_ROOT": WR}
g = wrap([], "2026-11-06T16:41", rv12, extra=x12)
seen = read(SEEN12) if os.path.exists(SEEN12) else ""
m12 = re.search(r"TMPDIR=(\S+)", seen)
tdir = m12.group(1) if m12 else ""
in_root = tdir.startswith(WR + "/2026-11-06-")
wrap_src = read(WRAP)
default_disk = 'WORK_ROOT="${NIGHTLY_REVIEW_WORK_ROOT:-/home/ubuntu/nightly_review_work}"' in wrap_src
named = ("WORK      " + tdir) in seen
gone_ok = bool(tdir) and not os.path.exists(tdir) and os.path.exists(os.path.join(rv12, "2026-11-06.md"))
pruned = not os.path.exists(stale) and os.path.isdir(young) and os.path.isdir(keep)
# a session that writes no review: the work dir still goes
os.remove(os.path.join(rv12, "2026-11-06.md"))
reset(SEEN12)
h = wrap([], "2026-11-06T16:41", rv12, extra=dict(x12, FAKE12_WRITE="0"))
seen2 = read(SEEN12) if os.path.exists(SEEN12) else ""
m2 = re.search(r"TMPDIR=(\S+)", seen2)
t2 = m2.group(1) if m2 else ""
gone_fail = h.returncode == 1 and t2.startswith(WR + "/2026-11-06-") and not os.path.exists(t2)
left = sorted(os.listdir(WR))
pr12 = read(os.path.join(TOOLS, "nightly_review.prompt"))
pforbid = "WORK directory" in pr12 and "Never" in pr12 and "write to /tmp" in pr12
ck("N12", in_root and default_disk and named and gone_ok and pruned and gone_fail and pforbid and left == ["2026-11-05-2000", "notes"],
   "tmpdir_in_root=%s default_on_disk=%s named=%s gone_after_produced=%s pruned_stale_only=%s gone_after_failed=%s prompt=%s left=%s rc=%s/%s"
   % (in_root, default_disk, named, gone_ok, pruned, gone_fail, pforbid, left, g.returncode, h.returncode))

shutil.rmtree(TMP, ignore_errors=True)
print()
if FAILS:
    print(f"RED — {len(FAILS)} of {len(RAN)} check(s) failed: {' '.join(FAILS)}")
    sys.exit(1)
print(f"GREEN — {len(RAN)} checks")
