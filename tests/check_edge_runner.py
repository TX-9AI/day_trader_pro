#!/usr/bin/env python3
"""
day_trader_pro/tests/check_edge_runner.py  v1.0
v1.0  2026-10-31  dtp r518 / RPT.29 — the R suite runs OTV5's tools, and a failed tool says why.
      eod_analysis shelled R_LEDGER and EDGE_SCAN to the FROZEN otv4 checkout (~/options-trader-v4/tests), whose
      edge_scan v1.2 raised KeyError on a sparse feature: EDGE_SCAN never ran clean on a Friday from 2026-08-28, and
      its warning carried only "rc=1". Operator: "Yes to dtp & the filter" (2026-10-31).

  R1  the R-suite tools resolve under DTP_OTV5_DIR/tests, and the default is ~/OTV5/tests
  R2  ... and never under ~/options-trader-v4, even with the old DTP_OTV4_DIR set (source and resolution)
  R3  a stub edge_scan exiting 0 with "MEETS THE PRE-REGISTERED BAR" is parsed as before: logged, paged once with
      the block, no warning
  R4  a stub edge_scan exiting 1 with a traceback gives an EDGE_SCAN warning carrying rc=1 and the stderr tail
      (the KeyError line), at most 300 characters of it
  R5  a stub r_ledger exiting 1 gives an R_LEDGER warning carrying the stderr tail; exit 0 logs the BOOK headline
  R6  a missing OTV5 checkout warns BY NAME (the path and DTP_OTV5_DIR), and nothing is run

The stubs are real scripts executed by the real phase (subprocess, as on control); notify is replaced by a
recorder, so nothing reaches Telegram. Born red on 112815c.  Run:  python3 tests/check_edge_runner.py
"""
import atexit
import io
import os
import shutil
import sys
import tempfile
from contextlib import redirect_stdout

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
FAILS = []
SCRATCH = tempfile.mkdtemp(prefix="edge_runner_")
atexit.register(shutil.rmtree, SCRATCH, True)


def check(name, ok, detail=""):
    print("  {:<4} {}  {}".format(name, "PASS" if ok else "FAIL", detail))
    if not ok:
        FAILS.append(name)


def guard(name, fn):
    try:
        ok, detail = fn()
    except Exception as exc:                                    # noqa: BLE001
        check(name, False, f"{type(exc).__name__}: {exc}")
        return
    check(name, bool(ok), detail)


import eod_analysis as ea                                       # noqa: E402

OTV4 = os.path.join(os.path.expanduser("~"), "options-trader-v4")
DATE = "2026-10-30"                                             # a Friday

MEETS = '''import sys
print("  1081 closed unrelaxed trades")
print("  MEETS THE PRE-REGISTERED BAR:")
print("    [call] session_fraction_remaining d=+0.202 p=0.000 nW/nL=207/321 sessions=30")
sys.exit(0)
'''
CRASH = '''import sys
print("  SOURCE: s3://bucket/raw [trades] - 9959 object(s) listed", flush=True)
sys.stderr.write("Traceback (most recent call last):\\n" + "".join(
    '  File "/x/edge_scan.py", line %d, in scan_features\\n    padding padding padding\\n' % i for i in range(40))
    + "KeyError: 'flow_imbalance'\\n")
sys.exit(1)
'''
RL_FAIL = '''import sys
sys.stderr.write("Traceback (most recent call last):\\nValueError: r_ledger stub broke\\n")
sys.exit(1)
'''
RL_OK = '''print("  BOOK n=54 net=+$1,234 R=+0.31")
'''


class _Rec:
    def __init__(self):
        self.sent = []

    def send(self, msg):
        self.sent.append(msg)


def _stub(tools: dict) -> str:
    d = tempfile.mkdtemp(dir=SCRATCH)
    os.makedirs(os.path.join(d, "tests"))
    for name, body in tools.items():
        with open(os.path.join(d, "tests", name), "w") as f:
            f.write(body)
    return d


def _run(phase, root):
    """Run one real phase with DTP_OTV5_DIR=root and a recording notify -> (warns, stdout, sent)."""
    old = {k: os.environ.get(k) for k in ("DTP_OTV5_DIR", "DTP_OTV4_DIR")}
    os.environ["DTP_OTV5_DIR"] = root
    os.environ["DTP_OTV4_DIR"] = OTV4                           # the old knob must not steer anything
    rec, old_notify = _Rec(), ea.notify
    ea.notify = rec
    warns, buf = [], io.StringIO()
    try:
        with redirect_stdout(buf):
            phase(DATE, warns)
    finally:
        ea.notify = old_notify
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return warns, buf.getvalue(), rec.sent


def r1():
    root = _stub({})
    os.environ["DTP_OTV5_DIR"] = root
    try:
        got = [ea.r_suite_tool(n) for n in ("edge_scan.py", "r_ledger.py")]
    finally:
        os.environ.pop("DTP_OTV5_DIR", None)
    dflt = [ea.r_suite_tool(n) for n in ("edge_scan.py", "r_ledger.py")]
    home5 = os.path.join(os.path.expanduser("~"), "OTV5", "tests")
    ok = (all(p == os.path.join(root, "tests", os.path.basename(p)) for p in got)
          and all(os.path.dirname(p) == home5 for p in dflt))
    return ok, f"env={got} default={dflt}"


def r2():
    os.environ["DTP_OTV4_DIR"] = OTV4
    try:
        paths = [ea.r_suite_tool(n) for n in ("edge_scan.py", "r_ledger.py")]
    finally:
        os.environ.pop("DTP_OTV4_DIR", None)
    src = open(os.path.join(REPO, "eod_analysis.py"), encoding="utf-8").read()
    code = [l for l in src.split('"""', 2)[-1].splitlines() if not l.lstrip().startswith("#")]
    bad = [l.strip() for l in code if "options-trader-v4" in l or "DTP_OTV4_DIR" in l]
    ok = not any(p.startswith(OTV4) for p in paths) and not bad
    return ok, f"paths={paths} code lines naming otv4={bad}"


def r3():
    warns, out, sent = _run(ea.edge_scan_phase, _stub({"edge_scan.py": MEETS}))
    ok = (not warns and "a feature cleared the bar" in out and len(sent) == 1
          and "session_fraction_remaining" in sent[0] and "CLEARED" in sent[0])
    return ok, f"warns={warns} sent={len(sent)}"


def r4():
    warns, _out, sent = _run(ea.edge_scan_phase, _stub({"edge_scan.py": CRASH}))
    w = next((x for x in warns if x.startswith("EDGE_SCAN")), "")
    tail = w.split("rc=1", 1)[-1].strip()
    ok = ("rc=1" in w and "KeyError: 'flow_imbalance'" in w and 0 < len(tail) <= 300 and not sent)
    return ok, f"warning={w[:90]!r}... tail_len={len(tail)}"


def r5():
    wf, _o, _s = _run(ea.r_ledger_phase, _stub({"r_ledger.py": RL_FAIL}))
    wo, out, sent = _run(ea.r_ledger_phase, _stub({"r_ledger.py": RL_OK}))
    w = next((x for x in wf if x.startswith("R_LEDGER")), "")
    ok = ("rc=1" in w and "r_ledger stub broke" in w and not wo
          and "BOOK n=54" in out and len(sent) == 1 and "BOOK n=54" in sent[0])
    return ok, f"fail_warning={w!r} ok_warns={wo}"


def r6():
    root = tempfile.mkdtemp(prefix="empty_", dir=SCRATCH)
    we, out_e, _ = _run(ea.edge_scan_phase, root)
    wr, out_r, _ = _run(ea.r_ledger_phase, root)
    ok = (any("EDGE_SCAN" in w and root in w and "DTP_OTV5_DIR" in w for w in we)
          and any("R_LEDGER" in w and root in w and "DTP_OTV5_DIR" in w for w in wr))
    return ok, f"{we + wr}"


print("=" * 66)
print("EDGE RUNNER: the R suite runs OTV5's tools and says why one failed")
print("=" * 66)
for _n, _f in (("R1", r1), ("R2", r2), ("R3", r3), ("R4", r4), ("R5", r5), ("R6", r6)):
    guard(_n, _f)
print("-" * 66)
if FAILS:
    print(f"RED — {len(FAILS)} of 6 failed: {', '.join(FAILS)}")
    sys.exit(1)
print("GREEN — 6 checks")
