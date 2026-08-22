#!/usr/bin/env python3
"""
day_trader_pro/tests/test_conductor_recovery.py — v1.0

Phase 2b still runs after phase 4b was deleted.

v1.0  2026-08-20  Written with eod_conductor v1.15.0 (sat-out recovery removed).

WHY THIS EXACT TEST. Deleting the `scope` parameter leaves seven format strings
that used to interpolate it. A single missed `{scope}` raises NameError — and
NOTHING catches it before runtime: the module imports clean, and phase 2b is
wrapped in the conductor's warn-never-stop discipline, so the failure would
surface as a nightly warning about archive recovery rather than as a stack
trace anyone reads.

⚠️ THIS IS NOT A HYPOTHETICAL. The same edit shape — dropping a parameter and
leaving one interpolation behind — was made in options_trader_v4's candle_feed
on this same evening, passed `import`, and was caught only by a check that drove
the branch. WORKING_AGREEMENT 21: a test that reads source proves nothing about
runtime.

So every branch that formats a message is DRIVEN here: no gaps, dry-run with
gaps, and a live run whose recovery partly fails.

BORN RED: against a v1.14.0 tree, C1 fails ("still takes `scope`").

Run:  cd ~/day_trader_pro && python3 tests/test_conductor_recovery.py
"""

from __future__ import annotations

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import eod_conductor as ec   # noqa: E402

PROBLEMS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  - {detail}" if (detail and not ok) else ""))
    if not ok:
        PROBLEMS.append(name)


def main() -> int:
    print("=" * 68)
    print("CONDUCTOR RECOVERY: phase 2b survives the phase 4b deletion")
    print("=" * 68)

    # ── C1 the signature ─────────────────────────────────────────────────
    params = list(inspect.signature(ec.phase_archive_recovery).parameters)
    check("C1 scope parameter is gone", params == ["dry", "warns"],
          f"signature is {params} - still takes `scope`")

    # ── C2 the sat-out call site is gone from run() ──────────────────────
    run_src = inspect.getsource(ec.run)
    check("C2 run() calls recovery exactly once",
          run_src.count("phase_archive_recovery(") == 1,
          f"{run_src.count('phase_archive_recovery(')} call sites in run()")
    check("C2 phase_backfill is still called", "phase_backfill(" in run_src,
          "backfill was removed too - a panel box whose harvest FAILED now "
          "has nothing to fetch it")

    # ── C3/C4/C5 drive every message-formatting branch ───────────────────
    # 🔴 notify IS STUBBED, AND THIS IS A BUG FIX, NOT HYGIENE. C5 drives the
    # PARTIAL-FAILURE branch on purpose, and that branch sends a Telegram — so
    # every run of this test fired a REAL alert at the operator's phone.
    # It runs in every deploy gate, so the operator received
    # "EOD conductor [RECOVER] 2026-08-18: 2 pull(s) FAILED" on EVERY COMMIT,
    # for dates that were nothing but the fixture literals on the C4 line below.
    # ⚠️ AND IT TRAINED THE CHANNEL TO BE IGNORED — the exact harm the standing
    # rule names: Telegram is an EMERGENCY channel, and a test that pages on
    # success is worse than a test that does not run.
    # ⚠️ CAPTURING IS STRONGER THAN SILENCING. The stub RECORDS what would have
    # been sent, so the test now ASSERTS the alert was composed — which the old
    # version never checked, it merely caused it.
    real_gaps, real_harvest = ec._archive_gaps, ec.harvest
    real_notify_send = ec.notify.send
    sent: list = []
    ec.notify.send = lambda m: sent.append(m)

    class _FakeHarvest:
        """Stands in for harvest.backharvest — no fleet, no network."""
        def __init__(self, result):
            self._result = result

        def backharvest(self, date, quiet=True, artifacts=()):
            return self._result

    try:
        # C3 — the empty path.
        ec._archive_gaps = lambda: {}
        warns: list = []
        ec.phase_archive_recovery(False, warns)
        check("C3 no-gaps path runs clean", warns == [], f"warned: {warns}")

        # C4 — the dry path, with gaps to format.
        ec._archive_gaps = lambda: {"signal_journal": ["2026-08-18", "2026-08-19"],
                                    "chain_snapshots": ["2026-08-19"]}
        warns = []
        ec.phase_archive_recovery(True, warns)
        check("C4 dry path with gaps runs clean", warns == [], f"warned: {warns}")

        # C5 — the live path, with a PARTIAL failure so the warn branch formats.
        ec.harvest = _FakeHarvest({
            "journal": {"ok": ["NVDA", "SPX"], "failed": ["MU"]},
            "chains":  {"ok": [], "failed": ["QQQ"]},
        })
        warns = []
        ec.phase_archive_recovery(False, warns)
        check("C5 live path formats its failure warnings", len(warns) >= 1,
              "a partial failure produced no warning - the operator would "
              "never learn a pull failed")
        check("C5 warnings name the date, not a dead scope tag",
              all("scope" not in w for w in warns), f"warns={warns}")
        # C5b — the alert was COMPOSED. Asserting on the captured message is
        # STRONGER than the old behaviour, which merely CAUSED a real send and
        # never checked what it said.
        check("C5b partial failure composes a Telegram alert",
              any("FAILED" in m for m in sent),
              f"the failure branch sent nothing alert-shaped: {sent}")

        # C6 — a deferred recovery (no boxes running) must not warn.
        ec.harvest = _FakeHarvest(None)
        warns = []
        ec.phase_archive_recovery(False, warns)
        check("C6 deferred recovery does not warn", warns == [],
              f"a deferral is not a defect; warned: {warns}")
    except NameError as exc:
        check("C3-C6 every branch executes", False,
              f"NameError: {exc} - a format string still references the "
              f"deleted parameter")
    finally:
        ec._archive_gaps, ec.harvest = real_gaps, real_harvest
        ec.notify.send = real_notify_send

    print("=" * 68)
    if PROBLEMS:
        print(f"  {len(PROBLEMS)} problem(s): {PROBLEMS}")
        return 1
    print("  ALL GREEN - 2b intact, 4b gone, every branch executed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
