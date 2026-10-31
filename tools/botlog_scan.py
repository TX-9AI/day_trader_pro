#!/usr/bin/env python3
"""
day_trader_pro/tools/botlog_scan.py — v1.0
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
import json, os, re, sys
FROM, TO = sys.argv[1], sys.argv[2]
BASE = os.path.join(os.path.expanduser("~"), "options-trader")
NAMES = ["bot.log.%d" % i for i in range(5, 0, -1)] + ["bot.log"]
TS = re.compile(r"^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}) \[(\w+)\s*\] ([^:]+): (.*)$")
SECRET = re.compile(r"(?i)(token|secret|password|passwd|bearer|authorization|api[_-]?key|refresh)[=: ]+\S+")
LONG = re.compile(r"[A-Za-z0-9+/_=-]{32,}")
HEX = re.compile(r"\b[0-9a-f]{8,}\b")
NUM = re.compile(r"[-+]?\$?\d[\d,]*(\.\d+)?%?")
TAG = re.compile(r"^\[([A-Za-z_][\w-]*)\]")
def redact(s):
    return LONG.sub("<redacted>", SECRET.sub(r"\1=<redacted>", s))
def sig(msg):
    return NUM.sub("N", HEX.sub("H", redact(msg)))[:160]
def classes(level, msg):
    out = []
    if level == "ERROR": out.append("error")
    if level == "CRITICAL": out.append("critical")
    m = msg.lower()
    cap = "catastrophic" in m or "cap reached" in m or msg.startswith("[capped]") or "cap episode" in m
    if cap: out.append("cap")
    elif "refused" in m or "entry blocked" in m:
        t = TAG.match(msg); out.append("refused:" + (t.group(1) if t else "other"))
    if "blind" in m or "stale" in m or "reconnecting" in m or "feed stream error" in m: out.append("feed")
    if msg.startswith("Service mode:"): out.append("start")
    return out
days, sigs, files, tb_pending = {}, {}, [], None
def bump(day, c, s, ts):
    days.setdefault(day, {}).setdefault(c, 0); days[day][c] += 1
    k = c + "\t" + s
    e = sigs.get(k)
    if e is None: sigs[k] = [1, day + " " + ts, day + " " + ts]
    else: e[0] += 1; e[2] = day + " " + ts
for n in NAMES:
    p = os.path.join(BASE, n)
    if not os.path.isfile(p): continue
    files.append(n)
    cur = None
    with open(p, "r", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            # Fast path: a dated line outside the window ends any open traceback and is skipped
            # without the regex (a rotation set is up to 300 MB).
            if line[4:5] == "-" and line[7:8] == "-" and line[:4].isdigit() and not (FROM <= line[:10] <= TO):
                if tb_pending: bump(tb_pending[0], "traceback", "(no exception line)", tb_pending[1]); tb_pending = None
                cur = None
                continue
            m = TS.match(line)
            if m:
                if tb_pending: bump(tb_pending[0], "traceback", "(no exception line)", tb_pending[1]); tb_pending = None
                d = m.group(1)
                cur = (d, m.group(2)) if FROM <= d <= TO else None
                if cur is None: continue
                for c in classes(m.group(3), m.group(5)):
                    bump(d, c, sig(m.group(4) + ": " + m.group(5)), m.group(2))
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
print("BOTLOG_JSON " + json.dumps({"files": files, "days": days, "sigs": out}, sort_keys=True))
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


def table(boxes: dict) -> list:
    cls = ("error", "critical", "traceback", "feed", "cap", "start")
    out = [f"{'box':<6} " + " ".join(f"{c:>9}" for c in cls) + "  refused(by tag)"]
    for box in sorted(boxes):
        p = boxes[box]
        if p is None:
            out.append(f"{box:<6} NOT READ (no BOTLOG_JSON line: unreachable, stopped, or the script failed)")
            continue
        tot = {}
        for day in p.get("days", {}).values():
            for c, n in day.items():
                tot[c] = tot.get(c, 0) + n
        ref = {c.split(":", 1)[1]: n for c, n in tot.items() if c.startswith("refused:")}
        out.append(f"{box:<6} " + " ".join(f"{tot.get(c, 0):>9}" for c in cls) + "  "
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
