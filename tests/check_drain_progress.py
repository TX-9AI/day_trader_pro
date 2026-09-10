#!/usr/bin/env python3
"""
day_trader_pro/tests/check_drain_progress.py  v1.0
v1.0  2026-09-10  dtp r348 / CND.3 — the drain must say where it IS, not only
      where it finished.

🔴 WHY. Each box runs a full `--verify` — a walk of 600+ prefixes against S3.
The conductor printed `draining + verifying 15 box(es)` and then went silent
for minutes. Fifteen of those is the longest unnarrated wait in the close and
it is INDISTINGUISHABLE FROM A HANG: on 2026-09-10 the run genuinely was hung
and looked exactly like a slow one.

  D1  a header naming the box is printed BEFORE its ssh call — a line emitted
      only on completion says where it FINISHED, never where it is STUCK
  D2  the header carries position (i/n) so progress is visible
  D3  elapsed seconds are reported per box
  D4  every box still gets the full VERIFY_TIMEOUT_S (r221's ceiling stands)
  D5  the LIVE CLOSE menu path is tmux-wrapped, with an in-session fallback
      that announces itself
"""
import io
import os
import sys
from contextlib import redirect_stdout

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
FAILS = []


def check(name, ok, detail=""):
    print("  {:<4} {}  {}".format(name, "PASS" if ok else "FAIL", detail))
    if not ok:
        FAILS.append(name)


LINE = ("DRAIN host=h sym={s} drained=yes pushed=1 failed=0 prefixes=600 "
        "local=10 s3=10 short=0 OK")


def main():
    try:
        import eod_conductor_v2 as C
        import ssh_util
        import fleet
    except Exception as exc:                                    # noqa: BLE001
        print("  FAIL  conductor did not import: {}".format(exc))
        return 1

    syms = ["AMD", "AMZN", "AVGO"]
    fleet.get_fleet = lambda only=None: [(s, "10.0.0.1", "running")
                                         for s in (only or syms)]
    order, timeouts = [], []

    def fake(ip, cmd, timeout=None):
        # what has been PRINTED by the time the call is made is the whole
        # point: the header must already be out.
        order.append(("call", buf.getvalue()))
        timeouts.append(timeout)
        return 0, LINE.format(s=syms[len(timeouts) - 1]), ""

    ssh_util.ssh_run = fake
    buf = io.StringIO()
    with redirect_stdout(buf):
        C.drain_and_verify(syms, False)
    out = buf.getvalue()

    before_first = order[0][1] if order else ""
    check("D1", "AMD" in before_first and "verifying" in before_first,
          "header printed before the first ssh call")
    check("D2", "[1/3]" in out and "[3/3]" in out,
          "position markers present")
    check("D3", "answered in" in out, "elapsed reported per box")
    check("D4", timeouts and all(t == C.VERIFY_TIMEOUT_S for t in timeouts),
          "every box got {}s".format(C.VERIFY_TIMEOUT_S))

    fn = open(os.path.join(REPO, "menu_functions.sh"), encoding="utf-8").read()
    body = fn.split("mi_eod_conductor_full_gated_eod_dry_run_preview()", 1)[-1]
    body = body.split("\n}", 1)[0]
    has_tmux = "tmux new -As eodclose" in body
    has_fallback = "tmux not present" in body
    check("D5", has_tmux and has_fallback,
          "tmux={} fallback announced={}".format(has_tmux, has_fallback))

    print("")
    if FAILS:
        print("FAILED: {}".format(", ".join(FAILS)))
        return 1
    print("ALL PASS (5)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
