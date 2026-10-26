#!/usr/bin/env python3
"""day_trader_pro/tests/check_streams_count.py — v1.0
v1.0  2026-10-26 — dtp r513 / STRM.1 — THE STREAMS WARNING COUNTS GAP ROWS, AND THE DRAIN WRITES THE OHLC FILE FIRST.
      2026-10-26: one ohlc gap row was reported as "2 gap(s)" (the board's own 🔴 summary line was counted too), and the
      gap itself was the close racing: candle-logger.timer (16:05 ±30 s) and QUIESCE stopping it, so 9 of 14 boxes had no
      ohlc file when the drain verified.

  S1  _stream_gaps on 10-26's real flagged lines (one ohlc row + the summary) is 1
  S2  two gap rows + the summary + a stale exemption (❗) is 2
  S3  eod_analysis._streams' warning uses _stream_gaps (AST), not a bare 🔴 count
  S4  drain_and_verify's box command starts candle-logger.service BEFORE `s3_push.py --verify`, its failure tolerated
      (driven with ssh_run faked, as check_drain_progress)

Born red on dtp 8946cfd at S1, S2, S3 (no _stream_gaps) and S4.
"""
import ast
import io
import os
import sys
from contextlib import redirect_stdout

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
FAILED = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        FAILED.append(name.split()[0])


def main():
    import eod_analysis as A
    g = getattr(A, "_stream_gaps", None)
    d1026 = ["🔴 ohlc                        file    5bx  MISS: 9/14 (AMD,GOOGL,META,...)",
             "🔴 1 stream-day(s) need an answer."]
    two = ["🔴 ohlc   file  5bx  MISS: 9/14 (AMD,...)", "🔴 raw/trades  row  MISS: 1/14 (SOFI)",
           "❗ chain_snap  exemption RESOLVED - delete the entry", "▪ dark_pool accepted loss",
           "🔴 3 stream-day(s) need an answer."]
    check("S1 10-26's board (one ohlc row + the summary) counts 1 gap", g is not None and g(d1026) == 1,
          "missing" if g is None else f"got {g(d1026)}")
    check("S2 two gap rows + summary + a stale exemption counts 2", g is not None and g(two) == 2,
          "missing" if g is None else f"got {g(two)}")

    src = open(os.path.join(REPO, "eod_analysis.py"), encoding="utf-8").read()
    fn = next((n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "_streams"), None)
    body = ast.unparse(fn) if fn else ""
    check("S3 the STREAMS warning counts through _stream_gaps", "_stream_gaps(flagged)" in body)

    import eod_conductor_v2 as C
    import ssh_util
    import fleet
    fleet.get_fleet = lambda only=None: [(s, "10.0.0.1", "running") for s in (only or ["AMD"])]
    cmds = []

    def fake(ip, cmd, timeout=None):
        cmds.append(cmd)
        return 0, "DRAIN host=h sym=AMD drained=yes pushed=1 failed=0 prefixes=600 local=10 s3=10 short=0 OK", ""
    _real = ssh_util.ssh_run
    ssh_util.ssh_run = fake
    try:
        with redirect_stdout(io.StringIO()):
            C.drain_and_verify(["AMD"], False)
    finally:
        ssh_util.ssh_run = _real
    c = cmds[0] if cmds else ""
    i_log, i_ver = c.find("systemctl start candle-logger.service"), c.find("s3_push.py --verify")
    check("S4 the drain starts candle-logger.service before s3_push --verify, its failure tolerated",
          0 <= i_log < i_ver and "|| true; }" in c[i_log:i_ver], c[:160])

    print()
    if FAILED:
        print(f"RED — {len(FAILED)} failed: {', '.join(FAILED)}")
        return 1
    print("GREEN — 4 checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
