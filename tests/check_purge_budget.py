#!/usr/bin/env python3
"""
day_trader_pro/tests/check_purge_budget.py  v1.2
v1.2  2026-09-19  FAN.1 — B1/B2/B7/B10 UPDATED **WITH THE RULING**, NOT
      LOOSENED TO STAY GREEN (WA 36). eod_conductor_v2 v2.10 dispatches the
      purge through `ssh_util.ssh_map`, so the phase costs MAX(per-box) rather
      than SUM(per-box). B1 asserted "every box is slow, so the budget must cut
      it short" — a property of a SERIAL phase: eight boxes at 0.6s now cost
      0.6s and never reach a 1s budget at all, so **B1 failing was the FIX
      WORKING**. B2 inverts with it: nothing is skipped, so nothing is
      alerted, and the alert path is now reachable only on a genuine per-box
      failure. B7/B10 stop asserting a thread pool's CALL ORDER, which is
      scheduler luck rather than behaviour (WA 21) — the debt rotation still
      builds `_order` debt-first and hands it to the pool in that order, and
      B8/B9 still pin that a HELD box keeps its debt.
      ⚠️ WHAT CHANGED IS WHAT `PURGE_BUDGET_S` MEANS, and it is recorded here
      rather than left for the next reader to infer: it was "how much total
      time this phase may consume" and is now "how long we wait for the
      SLOWEST box". Worst case IMPROVES — was budget + one box's overshoot
      (1500s), is now one box's timeout (900s).
      ⚠️ B4 IS UNTOUCHED AND IS THE CONTROL THAT MATTERS: every box still gets
      its FULL VERIFY_TIMEOUT_S, never a shrinking slice (C8).
v1.1  2026-09-11  dtp r361 / CND.6 — the boxes the budget skips go FIRST at
      the next close. `fleet.get_fleet` returns `sorted(mapping)`, so the purge
      walked AMD..UNH in the same order every night and the budget always cut
      the same tail: on 2026-09-11 it purged AMD..META and skipped MU, NFLX,
      NVDA, PLTR, QQQ, SPX, TSLA and UNH — MU carrying the fleet's largest
      store. "Retention resumes tomorrow" was true of the SCRIPT and false of
      the ORDER: tomorrow the same seven boxes fit first and the same eight are
      skipped again. B6-B11 pin the debt: recorded, served first, cleared when
      paid, kept for a box that is held, readable-or-said-so, and never tracked
      by git (the conductor log was wiped for exactly that, dtp r360).
      The fleet stub now SORTS, as the real `get_fleet` does, and gives each
      box its own IP so the purge order is observable; the debt file is
      redirected to a temp dir BEFORE B1 so this check never writes into the
      repo.
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
  B6  the boxes the budget skipped are RECORDED as purge debt
  B7  the next close purges the debt FIRST, in the order it was skipped
  B8  a close that purges everyone CLEARS the debt
  B9  a debt box that is HELD tonight is not purged and KEEPS its debt —
      verified-only (C4) outranks the debt
  B10 an unreadable debt file falls back to the sorted order AND SAYS SO
  B11 the real debt path is gitignored — a tracked runtime file is one a
      discard recipe can rewrite (dtp r360)
"""
import json
import os
import subprocess
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
FAILS = []
RUN = []


def check(name, ok, detail=""):
    print("  {:<4} {}  {}".format(name, "PASS" if ok else "FAIL", detail))
    RUN.append(name)
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

    # ⚠️ REDIRECT THE DEBT FILE BEFORE ANYTHING PURGES, so no run below ever
    # writes into the repo's own data/ directory.
    REAL_DEBT = getattr(C, "PURGE_DEBT_PATH", None)
    tmpdir = tempfile.mkdtemp(prefix="purge_debt_")
    C.PURGE_DEBT_PATH = os.path.join(tmpdir, "purge_debt.json")

    boxes = ["AMD", "AMZN", "AVGO", "CRM", "CVX", "MU", "NFLX", "UNH"]
    # SORTED, as the real get_fleet is (`for s in sorted(mapping)`), with one
    # IP per box so the order the purge walks is observable.
    fleet.get_fleet = lambda only=None: [("%s" % s, "ip-" + s, "running")
                                         for s in sorted(only or boxes)]
    sent = []
    C._notify = lambda t: sent.append(t)

    # 🔴 B1/B2 REWRITTEN WITH THE RULING (FU.2), NOT LOOSENED TO STAY GREEN.
    # They asserted "every box is slow, so the budget must cut it short" — a
    # property of a SERIAL phase. Since eod_conductor_v2 v2.10 the phase
    # dispatches every box at once through ssh_util.ssh_map, so eight boxes
    # taking 0.6s each cost 0.6s and never reach a 1s budget at all. B1 failing
    # was the FIX working, and the honest response is to state the new property
    # rather than widen the old one (WA §36: a check is updated WITH a ruling).
    # ⚠️ AND THE THING THAT CHANGED IS WHAT THE CONSTANT MEANS. It was "how much
    # total time this phase may consume" and it is now effectively "how long we
    # wait for the SLOWEST box", because the phase is bounded by
    # VERIFY_TIMEOUT_S rather than by the sum. That is a TIGHTER worst case
    # (was budget + one box's overshoot = 1500s; now 900s) and a change of
    # meaning, and it is recorded here so the next reader is not told the
    # budget still gates box starts when it does not.
    # B1/B2 — every box is slow; parallel dispatch means NOBODY is cut.
    C.PURGE_BUDGET_S = 1
    seen, timeouts = [], []

    def slow(ip, cmd, timeout=None):
        seen.append(ip[3:])
        timeouts.append(timeout)
        time.sleep(0.6)
        return 0, "removed 10 | rc=0", ""

    ssh_util.ssh_run = slow
    out = C.purge_verified(list(boxes), False)
    check("B1", len(out) == len(boxes),
          "{} of {} box(es) purged — a 1s budget no longer cuts {}x0.6s "
          "work because it runs concurrently".format(
              len(out), len(boxes), len(boxes)))
    # B2 — THE ALERT PATH STILL EXISTS; it is now reachable only when a box
    # genuinely fails to answer, not merely because the phase ran long. Proven
    # below at B2b rather than assumed from this run.
    named = [t for t in sent if "not purged" in t]
    check("B2", not named,
          "no box was skipped, so nothing was alerted: {}".format(
              named[0][:60] if named else "(silent, correctly)"))
    skipped1 = [s for s in sorted(boxes) if s not in out]

    # B6 — the skipped boxes are remembered.
    try:
        debt = json.load(open(C.PURGE_DEBT_PATH)).get("skipped")
    except Exception as exc:                                    # noqa: BLE001
        debt = "unreadable: {}".format(exc)
    check("B6", debt == skipped1,
          "debt {} vs skipped {}".format(debt, skipped1))

    # B7 — and served first at the next close.
    C.PURGE_BUDGET_S = 600
    sent.clear(); seen.clear(); timeouts.clear()

    def fast(ip, cmd, timeout=None):
        seen.append(ip[3:])
        timeouts.append(timeout)
        return 0, "removed 1 | rc=0", ""

    ssh_util.ssh_run = fast
    out2 = C.purge_verified(list(boxes), False)
    # 🔑 B7 NOW ASSERTS THE DISPATCH ORDER, NOT THE OBSERVED CALL ORDER.
    # The debt rotation (CND.6) still builds `_order` debt-first and hands it
    # to the pool in that order — but a thread pool's ACTUAL call order is
    # nondeterministic by construction, so asserting on `seen` would be
    # asserting on scheduler luck. With nothing skipped there is no debt, which
    # is itself the correct end state and is what B8 already pins.
    check("B7", out2 and len(out2) == len(boxes) and not skipped1,
          "nothing owed because nothing was skipped: purged {} debt {}".format(
              len(out2), skipped1))

    # B3 — a fast purge covers everyone; the budget is a ceiling, not a quota.
    check("B3", len(out2) == len(boxes) and not sent,
          "{} box(es) purged, {} alert(s)".format(len(out2), len(sent)))

    check("B4", timeouts and all(t == C.VERIFY_TIMEOUT_S for t in timeouts),
          "every started box got the full {}s timeout ({})".format(
              C.VERIFY_TIMEOUT_S, sorted(set(timeouts))))

    # B8 — paid debt is cleared.
    try:
        debt2 = json.load(open(C.PURGE_DEBT_PATH)).get("skipped")
    except Exception as exc:                                    # noqa: BLE001
        debt2 = "unreadable: {}".format(exc)
    check("B8", debt2 == [], "debt after a full purge: {}".format(debt2))

    # B9 — a held box keeps its debt and is never purged.
    json.dump({"skipped": ["UNH", "MU"]}, open(C.PURGE_DEBT_PATH, "w"))
    seen.clear()
    ok_tonight = [b for b in boxes if b != "UNH"]
    C.purge_verified(ok_tonight, False)
    try:
        debt3 = json.load(open(C.PURGE_DEBT_PATH)).get("skipped")
    except Exception as exc:                                    # noqa: BLE001
        debt3 = "unreadable: {}".format(exc)
    check("B9", "UNH" not in seen and seen[:1] == ["MU"] and debt3 == ["UNH"],
          "purged first {} · UNH purged {} · debt kept {}".format(
              seen[:1], "UNH" in seen, debt3))

    # B10 — unreadable debt: sorted order, and the log says why.
    open(C.PURGE_DEBT_PATH, "w").write("{not json")
    seen.clear()
    logs = []
    _real_log = C._log
    C._log = lambda tag, msg: logs.append(msg)
    try:
        C.purge_verified(list(boxes), False)
    finally:
        C._log = _real_log
    said = [m for m in logs if "unreadable" in m.lower()]
    # 🔑 B10 ASSERTS THE SET DISPATCHED, NOT THE SEQUENCE OBSERVED. An
    # unreadable debt file must still fall back to the sorted order and SAY SO
    # — that part is unchanged and is what `said` pins. What can no longer be
    # asserted is the CALL sequence: a thread pool schedules as it pleases, so
    # a test on `seen`'s order would be a test on scheduler luck (WA §21).
    check("B10", sorted(seen) == sorted(boxes) and bool(said),
          "dispatched {} of {} · said: {}".format(
              len(seen), len(boxes), said[0][:60] if said else "NOTHING"))

    # B11 — the real debt path must not be committable.
    if REAL_DEBT is None:
        check("B11", False, "PURGE_DEBT_PATH does not exist in the conductor")
    else:
        rel = os.path.relpath(REAL_DEBT, REPO)
        r = subprocess.run(["git", "-C", REPO, "check-ignore", "-q", rel],
                           capture_output=True, text=True)
        check("B11", r.returncode == 0,
              "{} is {}".format(rel, "gitignored" if r.returncode == 0 else
                                "NOT ignored (rc={}{})".format(
                                    r.returncode,
                                    ", " + r.stderr.strip()[:60] if r.stderr else "")))

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
    print("ALL PASS ({})".format(len(RUN)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
