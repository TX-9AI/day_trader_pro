#!/usr/bin/env python3
"""
tests/check_fanout_parallel.py  v1.0
v1.0  2026-09-19  FU.2 — THE FLEET FAN-OUT IS CONCURRENT, AND THE BUDGET STILL
      BOUNDS IT.

🔴 WHY. `PURGE_BUDGET_S` (600s, CND.2) caps the whole EOD purge phase and was
spent SERIALLY on work that executes entirely ON the box. Measured over the
seven closes to 2026-09-18 the phase reached 7 → 7 → 3 → 2 → 2 → 3 → 4 boxes of
fifteen — a full rotation every 4–5 nights, which makes the 5-day `1m` retention
policy unreachable. PLTR and QQQ were both +14 days beyond policy; PLTR sat at
93% disk, past the DEV.7 guard, which fired for real.

🔑 P2 IS THE CHECK THAT MATTERS AND IT MEASURES RATHER THAN ASSERTS. Source that
merely CONTAINS `ThreadPoolExecutor` proves nothing about runtime (WA §21) — so
P2 stubs `ssh_run` with a sleeper and requires N slow boxes to finish in about
ONE box's time. A serial implementation fails it on the clock.

⚠️ AND P6 IS A CONTROL, NOT A FEATURE. `check_conductor_purge` C8 once refused a
cut that shortened the per-box timeout to whatever budget remained: a 1.7M-row
purge handed 30s fails at the ssh layer while its work continues on the far
side. Every box must still get its FULL timeout. P6 goes red if that is ever
traded away for a tidier bound.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FAILED = []
RAN = []


def check(name, ok, detail=""):
    # ⚠️ COUNT WHAT RAN. A hand-written total is a literal that rots the moment
    # a check is added — the r383/CHK.6 lesson, one file over.
    RAN.append(name)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        FAILED.append(name)


def main():
    import ssh_util

    check("P1 ssh_util.ssh_map exists", hasattr(ssh_util, "ssh_map"))
    if not hasattr(ssh_util, "ssh_map"):
        print("RED — ssh_map absent; nothing else can be exercised")
        return 1

    real = ssh_util.ssh_run
    try:
        # ── P2 — CONCURRENCY, ON THE CLOCK ────────────────────────────────
        # ⚠️ N IS THE FLEET, NOT A ROUND NUMBER. A test at 10 proves
        # workers>=10 and says NOTHING about 15 — and the bound is
        # ceil(N/workers) x per-box timeout, so a pool narrower than the fleet
        # silently doubles the worst case. The test must match what deploys.
        DELAY, N = 0.6, 15

        def _slow(ip, command, timeout=None):
            time.sleep(DELAY)
            return 0, f"ok {ip}", ""

        ssh_util.ssh_run = _slow
        targets = [(f"S{i}", f"10.0.0.{i}") for i in range(N)]
        t0 = time.monotonic()
        res = ssh_util.ssh_map(targets, "echo hi", timeout=5)
        el = time.monotonic() - t0
        serial = DELAY * N
        check("P2 N slow boxes finish in ~ONE box's time, not N",
              el < serial / 3.0, f"{el:.2f}s for {N}x{DELAY}s (serial={serial:.1f}s)")
        check("P2b every target answered", len(res) == N, f"{len(res)}/{N}")
        # 🔴 P2d — THE BOUND ITSELF. "The phase costs MAX(per-box)" is true ONLY
        # at one wave. This is the check that stops that claim being quoted
        # after someone lowers DTP_FANOUT_WORKERS or the fleet grows past it.
        check("P2d ONE WAVE at fleet width — the MAX(per-box) bound is real",
              ssh_util.ssh_map.last_waves == 1,
              f"workers={ssh_util.ssh_map.last_workers} "
              f"waves={ssh_util.ssh_map.last_waves} for N={N}")
        # P2e — AND THE WAVE COUNT IS HONEST WHEN IT IS NOT 1.
        narrow = ssh_util.ssh_map(targets, "echo hi", timeout=5, workers=4)
        check("P2e a narrow pool REPORTS its waves rather than claiming one",
              ssh_util.ssh_map.last_waves == 4 and len(narrow) == N,
              f"waves={ssh_util.ssh_map.last_waves} (expect 4 for {N}/4)")
        check("P2c results are keyed by the CALLER's key, not completion order",
              sorted(res) == sorted(k for k, _ in targets))

        # ── P3 — A RAISING BOX IS ITS OWN FAILURE, NEVER COLLECTIVE ───────
        def _boom(ip, command, timeout=None):
            if ip.endswith(".3"):
                raise RuntimeError("box on fire")
            return 0, "fine", ""

        ssh_util.ssh_run = _boom
        res = ssh_util.ssh_map(targets, "echo hi", timeout=5)
        check("P3 one raising box does not cost the others their answers",
              len(res) == N and res["S3"][0] == 255 and res["S0"][0] == 0,
              f"S3={res.get('S3', ('?',))[0]} S0={res.get('S0', ('?',))[0]}")
        check("P3b and its reason is NAMED, not blank",
              "box on fire" in (res["S3"][2] or ""), res["S3"][2][:48])
        # 🔴 P3c — THE INVARIANT, STATED AS AN INVARIANT. len(result) ==
        # len(targets), ALWAYS, whatever any worker does. This is the classic
        # parallelisation regression and it fails DIFFERENTLY from serial: a
        # serial loop that dies at box k still leaves boxes 1..k-1 collected,
        # whereas an unguarded gather propagates at result() time and can lose
        # the WHOLE dict — turning one box's failure into a fleet-wide phase
        # failure. Raised by the OTV4TEST review as the first thing it would
        # look for in code it could not see.
        check("P3c INVARIANT — one tuple per target, ALWAYS",
              len(res) == len(targets)
              and all(isinstance(v, tuple) and len(v) == 3 for v in res.values()),
              f"{len(res)}/{len(targets)} targets, all 3-tuples")

        def _all_boom(ip, command, timeout=None):
            raise RuntimeError("total fleet failure")

        ssh_util.ssh_run = _all_boom
        res_all = ssh_util.ssh_map(targets, "echo hi", timeout=5)
        check("P3d EVERY box failing still returns a full, keyed result",
              len(res_all) == len(targets)
              and all(v[0] == 255 for v in res_all.values()),
              f"{len(res_all)}/{len(targets)} all rc=255")

        # ── P4 — EMPTY IS A LEGITIMATE INPUT, NOT A CRASH ─────────────────
        check("P4 no targets returns {} rather than raising",
              ssh_util.ssh_map([], "echo hi") == {})
    finally:
        ssh_util.ssh_run = real

    # ── P5 — THE PURGE PHASE DISPATCHES ALL BOXES ─────────────────────────
    src = open(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "eod_conductor_v2.py")).read()
    purge = src[src.index("_order, _held_debt = _purge_order"):]
    purge = purge[:purge.index("_save_purge_debt")]
    check("P5 the purge phase dispatches through ssh_map",
          "ssh_util.ssh_map(" in purge)
    check("P5b and no longer calls ssh_run inside its own loop",
          "ssh_util.ssh_run(" not in purge)

    # ── P6 — CONTROL: THE PER-BOX TIMEOUT IS UNTOUCHED (C8) ───────────────
    check("P6 CONTROL — each box still gets the FULL VERIFY_TIMEOUT_S",
          "timeout=VERIFY_TIMEOUT_S" in purge)
    check("P6b CONTROL — the budget and the debt rotation both survive",
          "PURGE_BUDGET_S" in purge and "_skipped" in purge)

    print(("RED — " + ", ".join(FAILED)) if FAILED
          else f"GREEN — {len(RAN)} checks")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
