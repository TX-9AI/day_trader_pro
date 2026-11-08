#!/usr/bin/env python3
"""
day_trader_pro/tools/botlog_scan.py — v1.1
v1.1  2026-11-08  dtp r526 / SAT.5 — THE SCAN NAMES WHY A BOX TOOK NO TRADE, AND ITS CAP COLUMN IS REAL. The 11-07
      Saturday brief (§2, §5 item 2) found: the `cap` column counted the start-up banner (`catastrophic_loss_cap=`)
      on 14/14 boxes; `refused=False` (a BLIND BARS_STALE field) counted as a refusal; the ORB engine's "[orb] the
      tick's ORB snapshot is STALE ... re-armed" note counted as a feed fault; days were keyed by the box's UTC
      stamp; and only `[pin]` refusals were named, so nine of eleven sat-out box-days read "unexplained" when
      bot.log held COMMIT.2 blocks and sizing rejections (the 11-07 sit-out trace, ~/reviews/studies/sitout_1107/).
      Now: the banner is a START only; a cap is a cap HIT / episode / `[capped]` / "catastrophic cap reached";
      refusals are classed refused:<class> - pin, pin_exempt_would_refuse, commit, sizing:<reason>, size:<tag>,
      entry_end, plan_log, observe, orb_break, gate:<Strategy>@<condition>, afd, park_starved, park_failed_closed,
      no_chain, ladder, credit_pairing, other:<tag> (the fallback, never `refused=`); the engine note is not feed;
      every line is keyed by its ET day and clock (box-local -> epoch -> ET, standard library); each day carries
      its start times (`starts`) and a `start_rth` count for a start between 09:30 and 16:00 ET. --by-day prints
      each box-day's refusal classes. A v1.0 payload (a saved transcript) is re-read with its banner "cap"
      signatures moved to start-only and its engine-note "feed" lines removed (upgrade_v1), so an old week's cap
      column reads true; its refusals cannot be re-classed (v1.0 never kept those lines) and are marked v1.0.
v1.0  2026-10-31  dtp r520 / SAT.4 — THE SATURDAY BRIEF'S "ISSUES FROM THE BOT LOGS", READ-ONLY, FLEET-WIDE.
      The operator, 2026-10-31: the brief "should include issues from the bot logs". Until now nothing read
      bot.log on a schedule: the 10-31 brief said "why SPX wrote no gate rows ... not read from SPX's bot.log"
      and "Runaway state and the pin/commit refusals are in bot.log, not S3".

WHAT IT DOES
  1. Builds ONE read-only box script (BOX_SCRIPT, below) and ships it base64-encoded through the ordinary fan-out,
     `fleet.py run "echo <b64> | base64 -d | python3 - FROM TO" --timeout 180`, so no quoting survives to the box.
  2. On each box the script reads ~/options-trader/bot.log and its rotations (bot.log.1 .. bot.log.5, the
     RotatingFileHandler's names, 50 MB each) and keeps only lines whose timestamp day is FROM..TO. It counts, per
     day: ERROR, CRITICAL, Traceback (with the exception line that ends it), REFUSED / blocked entries by gate tag,
     blind / stale / reconnect feed lines, cap hits, and service starts ("Service mode:"). Each line becomes a
     SIGNATURE: the message with digits, hex ids and prices folded, and anything token-shaped redacted.
  3. Prints ONE line per box, `BOTLOG_JSON {...}`. Control parses those out of fleet.py's per-box sections, writes
     <out>/botlog.json, prints the table, and diffs signatures against <prior>/botlog.json (NEW signatures first).

🔴 READ-ONLY AND CREDENTIAL-SAFE BY CONSTRUCTION, PINNED BY tests/check_botlog_scan.py:
  · the box script opens files for reading only, under ~/options-trader, by the exact names bot.log[.N];
  · it never runs a subprocess, never reads a unit, an environment, /proc, .env or a bootstrap;
  · every signature passes redact() (token-, key- and secret-shaped text) before it leaves the box.
A box that cannot be read is reported NOT READ by name, never folded into a zero (§0.5).

Usage:
  venv/bin/python tools/botlog_scan.py --from 2026-11-02 --to 2026-11-06 --out DIR [--prior DIR] [--only SPX,QQQ]
  venv/bin/python tools/botlog_scan.py --print-box-script        # the exact script a box runs
  venv/bin/python tools/botlog_scan.py ... --fleet-output FILE   # parse a saved fleet.py run transcript (tests)
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# ── THE BOX SCRIPT ────────────────────────────────────────────────────────────
# Runs on the box under the box's own python3 with argv FROM TO. Standard library only.
BOX_SCRIPT = r'''
import datetime, json, os, re, sys, time
FROM, TO = sys.argv[1], sys.argv[2]
BASE = os.path.join(os.path.expanduser("~"), "options-trader")
NAMES = ["bot.log.%d" % i for i in range(5, 0, -1)] + ["bot.log"]
TS = re.compile(r"^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}) \[(\w+)\s*\] ([^:]+): (.*)$")
SECRET = re.compile(r"(?i)(token|secret|password|passwd|bearer|authorization|api[_-]?key|refresh)[=: ]+\S+")
LONG = re.compile(r"[A-Za-z0-9+/_=-]{32,}")
HEX = re.compile(r"\b[0-9a-f]{8,}\b")
NUM = re.compile(r"[-+]?\$?\d[\d,]*(\.\d+)?%?")
TAG = re.compile(r"^\[([A-Za-z_][\w-]*)\]")
GATE_AT = re.compile(r"^\[gate\] (\S+) BLOCKED at (\S+)")
SIZE_WHY = re.compile(r"^Sizing rejected: ([A-Za-z_]+)")
SIZE_TAG = re.compile(r"^\[size\] (\S+) REFUSED")
def redact(s):
    return LONG.sub("<redacted>", SECRET.sub(r"\1=<redacted>", s))
def sig(msg):
    return NUM.sub("N", HEX.sub("H", redact(msg)))[:160]
# v1.1: bot.log is stamped in the BOX's local time (UTC on the fleet). Every line is keyed by its ET session day
# and ET clock: box-local -> epoch (time.mktime, the box's own zone rules) -> ET by the US rule (second Sunday of
# March 02:00 to first Sunday of November 02:00), standard library only, cached per hour.
def _sun(y, m, n):
    d = datetime.date(y, m, 1)
    return 1 + (6 - d.weekday()) % 7 + 7 * (n - 1)
_OFF = {}
def to_et(d, t):
    k = d + t[:2]
    off = _OFF.get(k)
    if off is None:
        ep = time.mktime(time.strptime(d + " " + t[:2] + ":30:00", "%Y-%m-%d %H:%M:%S"))
        u = datetime.datetime.fromtimestamp(ep, datetime.timezone.utc).replace(tzinfo=None)
        y = u.year
        dst = datetime.datetime(y, 3, _sun(y, 3, 2), 7) <= u < datetime.datetime(y, 11, _sun(y, 11, 1), 6)
        loc = datetime.datetime.strptime(d + " " + t[:2] + ":30:00", "%Y-%m-%d %H:%M:%S")
        off = (u - datetime.timedelta(hours=4 if dst else 5)) - loc
        _OFF[k] = off
    e = datetime.datetime.strptime(d + " " + t, "%Y-%m-%d %H:%M:%S") + off
    return e.strftime("%Y-%m-%d"), e.strftime("%H:%M:%S")
def gate(msg):
    # v1.1: every refusal class the 11-07 sit-out trace needed, named; a fallback keeps unknown refusals visible.
    if msg.startswith("[pin] REFUSED"): return "pin"
    if msg.startswith("[pin] ") and "NOT gated" in msg:
        return "pin_exempt_would_refuse" if "would have REFUSED" in msg else None
    if msg.startswith("[commit] BLOCKED"): return "commit"
    m = SIZE_WHY.match(msg)
    if m: return "sizing:" + m.group(1)
    m = SIZE_TAG.match(msg)
    if m: return "size:" + m.group(1)
    if msg.startswith("[observe] LOG-ONLY"):
        if "past its entry end" in msg: return "entry_end"
        if "switched to LOG" in msg: return "plan_log"
        return "observe"
    if msg.startswith("ORB break REFUSED"): return "orb_break"
    m = GATE_AT.match(msg)
    if m: return "gate:" + m.group(1) + "@" + m.group(2)
    if msg.startswith("[gate] "): return None              # "STILL BLOCKED" repeats a counted block
    if msg.startswith("[afd] pre-dispatch") and "blocked" in msg: return "afd"
    if msg.startswith("[park] commitment gate STARVED"): return "park_starved"
    if "FAILED CLOSED" in msg and "PARK" in msg: return "park_failed_closed"
    if msg.startswith("Could not fetch options chain"): return "no_chain"
    if msg.startswith("[ladder]") and "REFUSED" in msg: return "ladder"
    if msg.startswith("Credit pairing BLOCKED"): return "credit_pairing"
    m = msg.lower()
    if "upgrade_refused" in m: return None                  # a feed line (dxFeed refused the socket), not a gate
    if ("refused" in m and "refused=" not in m) or "entry blocked" in m:
        t = TAG.match(msg)
        return "other:" + (t.group(1) if t else "untagged")
    return None
def classes(level, msg):
    out = []
    if level == "ERROR": out.append("error")
    if level == "CRITICAL": out.append("critical")
    if msg.startswith("Service mode:"):
        # The start-up banner names catastrophic_loss_cap=: it is a START, never a cap hit (v1.0 counted it as both).
        out.append("start")
        return out
    m = msg.lower()
    if ("catastrophic loss cap hit" in m or "cap episode" in m or msg.startswith("[capped]")
            or "catastrophic cap reached" in m or "loss cap reached" in m):
        out.append("cap")
    else:
        g = gate(msg)
        if g: out.append("refused:" + g)
    engine_note = msg.startswith("[orb]") and "snapshot is stale" in m
    if not engine_note and ("blind" in m or "stale" in m or "reconnecting" in m or "feed stream error" in m
                            or "upgrade_refused" in m):
        out.append("feed")
    return out
days, sigs, files, starts, tb_pending = {}, {}, [], {}, None
def bump(day, c, s, ts):
    days.setdefault(day, {}).setdefault(c, 0); days[day][c] += 1
    k = c + "\t" + s
    e = sigs.get(k)
    if e is None: sigs[k] = [1, day + " " + ts, day + " " + ts]
    else: e[0] += 1; e[2] = day + " " + ts
_d = lambda s, n: (datetime.date(*map(int, s.split("-"))) + datetime.timedelta(days=n)).isoformat()
LO, HI = _d(FROM, -1), _d(TO, 1)                            # box-local dates that can hold an ET line of FROM..TO
for n in NAMES:
    p = os.path.join(BASE, n)
    if not os.path.isfile(p): continue
    files.append(n)
    cur = None
    with open(p, "r", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            # Fast path: a dated line outside the widened window ends any open traceback and is skipped
            # without the regex (a rotation set is up to 300 MB).
            if line[4:5] == "-" and line[7:8] == "-" and line[:4].isdigit() and not (LO <= line[:10] <= HI):
                if tb_pending: bump(tb_pending[0], "traceback", "(no exception line)", tb_pending[1]); tb_pending = None
                cur = None
                continue
            m = TS.match(line)
            if m:
                if tb_pending: bump(tb_pending[0], "traceback", "(no exception line)", tb_pending[1]); tb_pending = None
                d, t = to_et(m.group(1), m.group(2))
                cur = (d, t) if FROM <= d <= TO else None
                if cur is None: continue
                for c in classes(m.group(3), m.group(5)):
                    bump(d, c, sig(m.group(4) + ": " + m.group(5)), t)
                    if c == "start":
                        starts.setdefault(d, []).append(t[:5])
                        if "09:30:00" <= t < "16:00:00": bump(d, "start_rth", "start inside RTH", t)
                continue
            if cur is None: continue
            if line.startswith("Traceback (most recent call last)"):
                tb_pending = cur
            elif tb_pending and line and not line.startswith((" ", "\t")):
                bump(tb_pending[0], "traceback", sig(line), tb_pending[1]); tb_pending = None
if tb_pending: bump(tb_pending[0], "traceback", "(no exception line)", tb_pending[1])
top = {}
for k, v in sigs.items():
    c = k.split("\t", 1)[0]
    top.setdefault(c, []).append([c, k.split("\t", 1)[1]] + v)
out = []
for c, rows in top.items():
    rows.sort(key=lambda r: -r[2]); out.extend(rows[:40])
print("BOTLOG_JSON " + json.dumps({"v": "1.1", "clock": "ET", "files": files, "days": days, "starts": starts,
                                   "sigs": out}, sort_keys=True))
'''

# What the box script must never contain, and what it may only do. check_botlog_scan reads these.
FORBIDDEN_ON_BOX = ("subprocess", "os.system", "popen", "environ", "/proc", ".env", "systemctl",
                    "bootstrap", "flash_creds", "open(p, \"w", "open(p, 'w", "remove(", "unlink", "rename(")

SECTION = re.compile(r"^── (\S+) \(([^)]*)\) ─")


def box_command(frm: str, to: str) -> str:
    b64 = base64.b64encode(BOX_SCRIPT.encode()).decode()
    return f"echo {b64} | base64 -d | python3 - {frm} {to}"


def parse_fleet_output(text: str) -> dict:
    """fleet.py run's transcript -> {box: payload | None}. A box with no BOTLOG_JSON line maps to None."""
    boxes, cur = {}, None
    for line in text.splitlines():
        m = SECTION.match(line)
        if m:
            cur = m.group(1)
            boxes.setdefault(cur, None)
            continue
        if line.startswith("── ") and "skipped" in line:
            boxes.setdefault(line.split()[1], None)
            cur = None
            continue
        if cur and line.startswith("BOTLOG_JSON "):
            try:
                boxes[cur] = json.loads(line[len("BOTLOG_JSON "):])
            except ValueError:
                boxes[cur] = None
    return boxes


def diff(now: dict, prior: dict) -> list:
    """Signatures present this week (any box) and absent from every box last week: [(class, sig, boxes, n)]."""
    def index(d):
        idx = {}
        for box, p in (d or {}).items():
            for c, s, n, *_ in (p or {}).get("sigs", []):
                e = idx.setdefault((c, s), [set(), 0]); e[0].add(box); e[1] += n
        return idx
    a, b = index(now), index(prior)
    new = [(c, s, sorted(v[0]), v[1]) for (c, s), v in a.items() if (c, s) not in b]
    return sorted(new, key=lambda r: (r[0] not in ("critical", "traceback", "error"), -r[3]))


def _box_classes():
    """The box script's classes() and gate(), run on control (for upgrade_v1 and the tests)."""
    ns = {}
    src = BOX_SCRIPT.split("days, sigs, files, starts, tb_pending")[0]
    exec(compile(src.replace("FROM, TO = sys.argv[1], sys.argv[2]", "FROM, TO = '', ''"), "box", "exec"), ns)
    return ns["classes"]


def upgrade_v1(p):
    """A v1.0 payload -> its totals re-read under v1.1 where the saved signatures allow it (see the header).
    Returns {class: total} or None for an unread box."""
    if p is None:
        return None
    tot = {}
    for day in p.get("days", {}).values():
        for c, n in day.items():
            tot[c] = tot.get(c, 0) + n
    if p.get("v"):
        return tot
    classes = _box_classes()
    for c, s, n, *_ in p.get("sigs", []):
        if c not in ("cap", "feed") and not c.startswith("refused:"):
            continue
        msg = s.split(": ", 1)[1] if ": " in s else s
        if c not in classes("INFO", msg) and not (c.startswith("refused:") and any(
                k.startswith("refused:") for k in classes("INFO", msg))):
            tot[c] = max(0, tot.get(c, 0) - n)
    if not any(c == "cap" and "cap" in classes("INFO", (s.split(": ", 1) + [s])[1]) for c, s, *_ in p.get("sigs", [])):
        tot["cap"] = 0
    tot["_v1"] = 1
    return tot


def by_day(boxes: dict) -> list:
    """Each box-day: trades are not in bot.log, so this is the refusal record a sat-out day is read against."""
    out = []
    for box in sorted(boxes):
        p = boxes[box]
        if p is None:
            out.append(f"{box:<6} NOT READ")
            continue
        for d in sorted(p.get("days", {})):
            day = p["days"][d]
            ref = {c.split(":", 1)[1]: n for c, n in day.items() if c.startswith("refused:")}
            st = ",".join((p.get("starts") or {}).get(d, [])) or "-"
            out.append(f"{box:<6} {d}  starts {st}  " + (", ".join(
                f"{k} {v}" for k, v in sorted(ref.items(), key=lambda kv: -kv[1])) or "no refusal lines"))
    return out


def table(boxes: dict) -> list:
    cls = ("error", "critical", "traceback", "feed", "cap", "start", "start_rth")
    out = [f"{'box':<6} " + " ".join(f"{c:>9}" for c in cls) + "  refused(by class)"]
    for box in sorted(boxes):
        p = boxes[box]
        if p is None:
            out.append(f"{box:<6} NOT READ (no BOTLOG_JSON line: unreachable, stopped, or the script failed)")
            continue
        tot = upgrade_v1(p)
        ref = {c.split(":", 1)[1]: n for c, n in tot.items() if c.startswith("refused:") and n}
        out.append(f"{box:<6} " + " ".join(f"{tot.get(c, 0):>9}" for c in cls) + "  "
                   + ("[v1.0 payload: cap/feed re-read, refusals as v1.0 kept them] " if tot.get("_v1") else "")
                   + ", ".join(f"{k} {v}" for k, v in sorted(ref.items(), key=lambda kv: -kv[1])))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[2])
    ap.add_argument("--from", dest="frm")
    ap.add_argument("--to")
    ap.add_argument("--out")
    ap.add_argument("--prior", default=None, help="last week's --out directory")
    ap.add_argument("--only", default=None)
    ap.add_argument("--fleet-output", default=None, help="parse this saved transcript instead of running the fan-out")
    ap.add_argument("--print-box-script", action="store_true")
    ap.add_argument("--by-day", action="store_true", help="also print each box-day's refusal classes and starts")
    a = ap.parse_args(argv)
    if a.print_box_script:
        print(BOX_SCRIPT)
        return 0
    if not (a.frm and a.to and a.out):
        ap.error("--from, --to and --out are required")
    for d in (a.frm, a.to):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
            ap.error(f"not a date: {d}")
    os.makedirs(a.out, exist_ok=True)
    if a.fleet_output:
        text = open(a.fleet_output).read()
    else:
        py = os.path.join(ROOT, "venv", "bin", "python")
        cmd = [py if os.path.exists(py) else sys.executable, os.path.join(ROOT, "fleet.py"), "run",
               box_command(a.frm, a.to), "--timeout", "180"]
        if a.only:
            cmd += ["--only", a.only]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
        text = r.stdout
        with open(os.path.join(a.out, "fleet_run.txt"), "w") as fh:
            # The transcript keeps fleet.py's headers and each box's single JSON line; the command echo is
            # base64 of BOX_SCRIPT, which holds no secret.
            fh.write(text)
    boxes = parse_fleet_output(text)
    with open(os.path.join(a.out, "botlog.json"), "w") as fh:
        json.dump({"from": a.frm, "to": a.to, "boxes": boxes}, fh, sort_keys=True, indent=1)
    print(f"BOT LOGS {a.frm}..{a.to}: {sum(1 for v in boxes.values() if v is not None)}/{len(boxes)} boxes read")
    for line in table(boxes):
        print("  " + line)
    if a.by_day:
        print("\nBY BOX-DAY (ET):")
        for line in by_day(boxes):
            print("  " + line)
    if a.prior and os.path.exists(os.path.join(a.prior, "botlog.json")):
        prior = json.load(open(os.path.join(a.prior, "botlog.json"))).get("boxes", {})
        new = diff(boxes, prior)
        print(f"\nNEW SIGNATURES vs {a.prior}: {len(new)}")
        for c, s, bx, n in new[:60]:
            print(f"  {c:<14} n={n:<5} {','.join(bx)}  {s}")
    elif a.prior:
        print(f"\nNO PRIOR botlog.json under {a.prior}: every signature is new this week (first run).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
