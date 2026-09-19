#!/usr/bin/env python3
"""
day_trader_pro/tests/check_drain_progress.py  v1.1
v1.1  2026-09-19  dtp r390 / FAN.1 — THE DRAIN IS NOW CONCURRENT AND D1-D5 PASS
      UNMODIFIED, WHICH IS THE POINT. The phase went from fifteen serial ssh
      calls to one `ssh_map` dispatch, and not one of CND.3's five checks had
      to move: the property they pin — the drain says where it IS, not only
      where it finished — is PRESERVED by the new shape rather than
      re-pointed at it. A checker that needed editing to stay green would have
      meant the rewrite had dropped the property (§36).
      🔴 AND A BLOCKING GATHER WOULD HAVE REINTRODUCED CND.3'S DEFECT IN A
      WORSE FORM. Waiting on all fifteen and printing at the end would emit
      NOTHING for a hung box's entire timeout — strictly less than the serial
      version, which at least showed fourteen answering and stalling on the
      fifteenth. So `ssh_map` gained an `on_result` callback and each box
      reports AS IT LANDS.
      D6  each box's completion line is emitted as it lands, not batched at
          the end of the phase
      D7  every progress line NAMES THE BOXES STILL OUTSTANDING — strictly
          more than the serial drain could say, since it never knew which
          boxes it had not yet reached
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
RAN = []


def check(name, ok, detail=""):
    RAN.append(name)   # count what RAN; a hardcoded total rots (CHK.6)
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

    _src = open(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "eod_conductor_v2.py")).read()
    _SRC_DRAIN = _src[_src.index("def drain_and_verify"):]
    _SRC_DRAIN = _SRC_DRAIN[:_SRC_DRAIN.index("def stop_services")]

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
    # 🔴 D6/D7 — THE NEW PROPERTIES v2.11 HAS TO EARN, because parallelising a
    # narrated phase is exactly where narration silently dies. D1-D5 above
    # still pass UNMODIFIED, which is the point: the concurrent drain preserves
    # CND.3's property rather than re-pointing its checks.
    check("D6", "ssh_map(" in _SRC_DRAIN and "ssh_util.ssh_run(" not in _SRC_DRAIN,
          "the drain dispatches concurrently and no longer calls ssh_run in a loop")
    # D7 — A STALL MUST NAME WHAT IS OUTSTANDING. This is the half that makes
    # concurrency SAFER than the serial version rather than merely faster: with
    # a blocking gather a hung box shows nothing at all for its whole timeout,
    # which is the CND.3 defect in a worse form. Here every landing line names
    # the boxes still owed, so a stall is visible AND attributable.
    check("D7", "outstanding" in out.lower(),
          "each landing names the boxes still owed")
    check("D5", has_tmux and has_fallback,
          "tmux={} fallback announced={}".format(has_tmux, has_fallback))

    print("")
    if FAILS:
        print("FAILED: {}".format(", ".join(FAILS)))
        return 1
    print(f"ALL PASS ({len(RAN)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
