#!/usr/bin/env python3
"""
day_trader_pro/tests/test_panel_mirror.py — v1.0

One fleet, named in three repositories. This pins them together.

v1.0  2026-08-20  Written with config v0.1.5 (UNIVERSE pruned 29 -> 15).

WHY. `config.UNIVERSE`, `selector.PANEL` and `market_brief_v1/config.py::PANEL`
all name the same fifteen boxes. Whichever gets updated becomes the truth and
the others rot — the failure this project keeps finding in its own code. A
comment saying "keep these in sync" is not a mechanism.

⚠️ THE SECOND HALF IS THE ONE THAT MATTERS, AND IT EXECUTES.
`eod_backfill._missing()` iterates config.UNIVERSE and returns every symbol with
no OHLC csv for the date. While UNIVERSE carried the 14 terminated boxes, that
function reported them short EVERY NIGHT and handed them to the sat-out wake —
the exact phase the fleet resize was meant to retire. C3 drives the real
function against an empty tape directory and asserts no terminated name comes
back. A list-equality check alone would not have proven the wake is gone.

⚠️ AND IT ASSERTS THE PHASE'S REAL JOB SURVIVES. Pruning must not turn
_missing() into a function that can never report anything: a PANEL box whose
harvest genuinely failed still has to surface. C4 pins that.

BORN RED, verified 2026-08-20 against pristine HEAD a50a104:
  C1 -> "UNIVERSE has 29 names, expected 15"
  C3 -> "_missing() returned terminated boxes: AAPL, COST, DIA, ..."

Run:  cd ~/day_trader_pro && python3 tests/test_panel_mirror.py
"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config          # noqa: E402
import selector        # noqa: E402

# Terminated 2026-08-20. Not "deprioritised" — the instances are gone from EC2.
TERMINATED = ["AAPL", "COST", "DIA", "GLD", "GS", "IWM", "JPM", "LLY",
              "MSFT", "ORCL", "SMCI", "SMH", "TLT", "XOM"]

PROBLEMS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  - {detail}" if (detail and not ok) else ""))
    if not ok:
        PROBLEMS.append(name)


def main() -> int:
    print("=" * 68)
    print("PANEL MIRROR: one fleet, three repos, and no ghost wakes")
    print("=" * 68)

    uni = list(config.UNIVERSE)
    panel = list(selector.PANEL)

    # ── C1/C2 the mirror ─────────────────────────────────────────────────
    check("C1 UNIVERSE size", len(uni) == 15,
          f"UNIVERSE has {len(uni)} names, expected 15")
    check("C1 UNIVERSE == selector.PANEL", set(uni) == set(panel),
          f"only in UNIVERSE={sorted(set(uni) - set(panel))} "
          f"only in PANEL={sorted(set(panel) - set(uni))}")
    ghosts = sorted(set(TERMINATED) & set(uni))
    check("C1 no terminated box in UNIVERSE", not ghosts, f"still listed: {ghosts}")
    check("C2 ALWAYS_ON is inside the universe",
          set(config.ALWAYS_ON) <= set(uni),
          f"ALWAYS_ON names missing from UNIVERSE: "
          f"{sorted(set(config.ALWAYS_ON) - set(uni))}")
    # MAX_DISCRETIONARY + ALWAYS_ON must still describe a reachable fleet, or a
    # restored discretionary selector would ask for more boxes than exist.
    check("C2 ALWAYS_ON + MAX_DISCRETIONARY does not exceed the fleet",
          len(config.ALWAYS_ON) + config.MAX_DISCRETIONARY <= len(uni),
          f"{len(config.ALWAYS_ON)} + {config.MAX_DISCRETIONARY} > {len(uni)}")

    # ── C3/C4 the sat-out wake, driven for real ──────────────────────────
    import eod_backfill

    with tempfile.TemporaryDirectory() as tmp:
        real_ohlc = config.OHLC_DIR
        try:
            config.OHLC_DIR = tmp                 # empty tape: nothing landed
            eod_backfill.config.OHLC_DIR = tmp
            missing_all = eod_backfill._missing("2026-08-20")
        finally:
            config.OHLC_DIR = real_ohlc
            eod_backfill.config.OHLC_DIR = real_ohlc

    ghost_wakes = sorted(set(missing_all) & set(TERMINATED))
    check("C3 _missing() never returns a terminated box", not ghost_wakes,
          f"_missing() returned terminated boxes: {', '.join(ghost_wakes)} — "
          f"these get handed to the sat-out WAKE every night")
    check("C4 _missing() still reports a real gap",
          set(missing_all) == set(uni),
          f"an empty tape directory should leave every panel box short; got "
          f"{len(missing_all)} of {len(uni)} — the phase can no longer see a "
          f"failed harvest")

    print("=" * 68)
    if PROBLEMS:
        print(f"  {len(PROBLEMS)} problem(s): {PROBLEMS}")
        print("  The control repo and the fleet disagree about which boxes")
        print("  exist. Every phase that wakes, counts or scans reads this.")
        return 1
    print(f"  ALL GREEN - {len(uni)} boxes, mirrored, no ghost wakes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
