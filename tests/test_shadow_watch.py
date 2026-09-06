#!/usr/bin/env python3
"""day_trader_pro/tests/test_shadow_watch.py — v1.0
v1.0  2026-09-05 — dtp r299 / SHD.2.

🔴 THE GUARD EXISTS BECAUSE STAGE 2 FAILS SILENTLY. `scorer.score()` runs per
tick inside RTH and the tick handler catches and warns, so a scorer that throws
writes `scores: []` — **the same shape stage 1 wrote for seven weeks.** Service
active, log quiet, rows present, corpus empty.

⚠️ SO THE CASES DRIVE BOTH DIRECTIONS, and the silent ones matter as much as the
loud one: Telegram is an EMERGENCY channel (§17), and a guard that pages on an
expected condition — a holiday, a fleet the operator stopped — teaches him to
ignore the one that counts.
"""
import io
import os
import sys
from contextlib import redirect_stdout

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
FAILED = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        FAILED.append(name)


def _run(argv, boxes, enabled=True, sent=None):
    """Drive the guard with a fake fleet. -> (rc, stdout)."""
    import control_state
    import fleet
    import tools.shadow_watch as SW

    real = (fleet._targets, fleet.get_fleet, fleet._exec,
            control_state.is_enabled, SW.notify)
    fleet.get_fleet = lambda only=None: None
    fleet._targets = lambda f, inc: ([(s, "1.2.3.4", "running") for s in boxes],
                                     [])
    fleet._exec = lambda s, ip, cmd: (0, boxes[s], "")
    control_state.is_enabled = lambda: enabled

    class _N:
        @staticmethod
        def send(t, silent=False):
            if sent is not None:
                sent.append(t)
            return True
    SW.notify = _N
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            rc = SW.main(argv)
    finally:
        (fleet._targets, fleet.get_fleet, fleet._exec,
         control_state.is_enabled, SW.notify) = real
    return rc, buf.getvalue()


def main():
    OK = {"QQQ": "rows=412 scored=390", "SPX": "rows=400 scored=377"}
    DARK = {"QQQ": "rows=412 scored=0", "SPX": "rows=400 scored=377"}
    TUE = ["--date", "2026-09-08"]

    # ══ 🔴 W1 — A DARK BOX PAGES, AND NAMES ITSELF ═══════════════════════
    sent = []
    rc, out = _run(TUE, DARK, sent=sent)
    check("W1 a box writing rows with ZERO scored pages", rc != 0 and sent,
          f"rc={rc}")
    check("W1b ...and the message names the box and its row count",
          sent and "QQQ" in sent[0] and "412" in sent[0],
          (sent[0][:64] if sent else ""))
    # ⚠️ THE HEALTHY BOX MUST NOT BE NAMED AS DARK. An alert that lists the
    # whole fleet when one box is broken is an alert nobody can act on.
    check("W1c ...and does NOT list the healthy box as dark",
          sent and "SPX (" not in sent[0])

    # ══ 🔴 W2 — A HEALTHY FLEET IS SILENT ════════════════════════════════
    # Telegram is an emergency channel. No nightly "shadow fine".
    sent2 = []
    rc2, out2 = _run(TUE, OK, sent=sent2)
    check("W2 a scoring fleet sends nothing at all", rc2 == 0 and not sent2,
          f"rc={rc2} sent={len(sent2)}")

    # ══ 🔴 W3 — EXPECTED CONDITIONS NEVER PAGE ═══════════════════════════
    # Labor Day 2026-09-07 is why this was automated instead of run by hand.
    sent3 = []
    rc3, out3 = _run(["--date", "2026-09-07"], DARK, sent=sent3)
    check("W3 a non-trading day is silent even with a dark fleet",
          rc3 == 0 and not sent3 and "not a trading day" in out3, f"rc={rc3}")
    # A fleet the operator stopped on purpose is not a fault.
    sent4 = []
    rc4, out4 = _run(TUE, DARK, enabled=False, sent=sent4)
    check("W3b a deliberately disabled control is silent",
          rc4 == 0 and not sent4 and "control disabled" in out4, f"rc={rc4}")

    # ══ ⚠️ W4 — AN UNANSWERING BOX IS NOT GREEN ══════════════════════════
    # A box we know nothing about must not read as healthy — that is the
    # silent-empty failure this guard exists to catch, one level up.
    sent5 = []
    rc5, out5 = _run(TUE, {"QQQ": "rows=412 scored=390", "MU": "ssh: timeout"},
                     sent=sent5)
    check("W4 a box that did not answer is reported, not assumed healthy",
          rc5 != 0 and sent5 and "MU" in sent5[0], f"rc={rc5}")

    # ══ ⚠️ W5 — THE REMOTE LINE CANNOT LOSE ITS OUTPUT ═══════════════════
    # `grep -c` returns 1 on a zero count, which once marked all 29 boxes
    # failed and DISCARDED stdout. The line must echo its own count and end
    # `|| true`, and the PARSE must decide — never the exit code.
    import tools.shadow_watch as SW
    check("W5 the remote line echoes its count and cannot exit non-zero",
          "|| true" in SW.REMOTE and "echo" in SW.REMOTE
          and "|| echo 0" in SW.REMOTE)
    # 🔑 AND IT COUNTS NON-EMPTY `scores`, not the presence of the key —
    # `scores: []` is exactly what a thrown scorer writes.
    check("W5b ...and matches a NON-EMPTY scores array, not the key",
          '"scores": \\[[^]]' in SW.REMOTE or '[^]]' in SW.REMOTE)

    # ══ 🔴 W6 — THE ALERT PATH IS EXERCISABLE WITHOUT A FAULT ════════════
    # Modelled on the fleet's blind-alert DRILL. Without this the first real
    # send is the morning something breaks — an untested path at the worst
    # possible moment, which is the failure class this whole session has been
    # about.
    sent6 = []
    rc6, out6 = _run(["--drill", "--date", "2026-09-08"], OK, sent=sent6)
    check("W6 --drill sends for real so the path is proven",
          rc6 == 0 and len(sent6) == 1, f"rc={rc6} sent={len(sent6)}")
    # ⚠️ AND IT IS MARKED. An unmarked test page trains the operator to
    # hesitate over a real one — the same reason the fleet drill says so.
    check("W6b ...and is marked DRILL so it cannot be read as a live alert",
          sent6 and sent6[0].startswith("DRILL - NOT REAL"),
          (sent6[0][:34] if sent6 else ""))
    # 🔑 A DRILL ON A DARK FLEET STILL ONLY DRILLS. It must not double as the
    # real check, or a drill would page twice and mean two different things.
    sent7 = []
    rc7, out7 = _run(["--drill", "--date", "2026-09-08"], DARK, sent=sent7)
    check("W6c ...and a drill never also fires the real alert",
          len(sent7) == 1 and "NOT SCORING" not in sent7[0], f"sent={len(sent7)}")

    print()
    if FAILED:
        print(f"RED — {len(FAILED)} failed: {', '.join(FAILED)}")
        return 1
    print("GREEN — 12 checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
