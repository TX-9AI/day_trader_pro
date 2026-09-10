#!/usr/bin/env python3
"""
day_trader_pro/tests/check_purge_budget.py  v1.0
v1.0  2026-09-10  dtp r346 / CND.2 — the purge must never starve the halt.

🔴 WHAT HAPPENED. 2026-09-10: the conductor verified all 15 boxes, stopped the
services on the 8 that passed, and was still deleting inside the retention
purge (prints 918,192 · greeks_series 484,442 · surface_series 691,626) when
systemd's `TimeoutStartSec=1800` killed it at 30 minutes. `ec2ops.stop` sits
AFTER the purge, so **the fleet stayed up all night** — and the P&L headline
and the HELD-boxes alert sit after it too, so the operator got fifteen
STOPPED alerts and then silence. 1.762s CPU over 30min wall: blocked on
deletes, not spinning.

⚠️ THE FILE ALREADY CLAIMED THIS COULD NOT HAPPEN — *"it never blocks the
halt; a purge failure is logged and stepped over"* — which is true of a
FAILURE and false of a SLOW RUN. The claim was about exceptions; the budget
is about time.

  B1  a slow purge stops after the budget instead of running forever
  B2  the boxes it skipped are NAMED, and alerted, never silent
  B3  a fast purge still covers every box — the budget is not a throttle
  B4  a box that STARTS still gets the full long timeout — the budget gates
      entry to the loop, it never shortens a running purge (check_conductor_purge
      C8: a 1.7M-row purge handed 30s fails at ssh while the work continues)
  B5  the operator's 08-27 ordering is intact: purge still runs BEFORE the
      halt, on the verified list only
"""
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
FAILS = []


def check(name, ok, detail=""):
    print("  {:<4} {}  {}".format(name, "PASS" if ok else "FAIL", detail))
    if not ok:
        FAILS.append(name)


def main():
    try:
        import eod_conductor_v2 as C
        import ssh_util
        import fleet
    except Exception as exc:                                    # noqa: BLE001
        print("  FAIL  conductor did not import: {}".format(exc))
        return 1
    if not hasattr(C, "PURGE_BUDGET_S"):
        print("  FAIL  PURGE_BUDGET_S does not exist — the purge is unbounded")
        return 1

    boxes = ["AMD", "AMZN", "AVGO", "CRM", "CVX", "MU", "NFLX", "UNH"]
    fleet.get_fleet = lambda only=None: [(s, "10.0.0.1", "running")
                                         for s in (only or boxes)]
    sent = []
    C._notify = lambda t: sent.append(t)

    # B1/B2 — every box is slow; the budget must cut it short.
    C.PURGE_BUDGET_S = 1
    seen, timeouts = [], []

    def slow(ip, cmd, timeout=None):
        seen.append(cmd)
        timeouts.append(timeout)
        time.sleep(0.6)
        return 0, "removed 10 | rc=0", ""

    ssh_util.ssh_run = slow
    out = C.purge_verified(list(boxes), False)
    check("B1", len(out) < len(boxes),
          "{} of {} box(es) purged before the budget cut it".format(
              len(out), len(boxes)))
    named = [t for t in sent if "not purged" in t]
    check("B2", bool(named) and any(s in named[0] for s in boxes),
          named[0][:70] if named else "no alert sent")

    # B3 — a fast purge covers everyone; the budget is a ceiling, not a quota.
    C.PURGE_BUDGET_S = 600
    sent.clear(); seen.clear(); timeouts.clear()
    ssh_util.ssh_run = lambda ip, cmd, timeout=None: (
        timeouts.append(timeout) or (0, "removed 1 | rc=0", ""))
    out2 = C.purge_verified(list(boxes), False)
    check("B3", len(out2) == len(boxes) and not sent,
          "{} box(es) purged, {} alert(s)".format(len(out2), len(sent)))

    check("B4", timeouts and all(t == C.VERIFY_TIMEOUT_S for t in timeouts),
          "every started box got the full {}s timeout ({})".format(
              C.VERIFY_TIMEOUT_S, sorted(set(timeouts))))

    # B5 — ordering, read from source: purge_verified is called before the
    # ec2 stop inside takedown, and only with the verified list.
    src = open(os.path.join(REPO, "eod_conductor_v2.py"), encoding="utf-8").read()
    body = src.split("def takedown(", 1)[-1]
    ip_, is_ = body.find("purge_verified(ok"), body.find("ec2ops.stop(")
    check("B5", ip_ != -1 and is_ != -1 and ip_ < is_,
          "purge at {} precedes ec2ops.stop at {}".format(ip_, is_))

    print("")
    if FAILS:
        print("FAILED: {}".format(", ".join(FAILS)))
        return 1
    print("ALL PASS (5)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
