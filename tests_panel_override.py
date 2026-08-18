#!/usr/bin/env python3
"""
tests_panel_override.py — v1.0 — 2026-08-17

A FIXED TRADING PANEL, SO THE SEPARATION TEST STOPS MEASURING THE SELECTOR.

    cd ~/day_trader_pro && python3 tests_panel_override.py

⚠️ WHY THIS EXISTS, and it is a MEASUREMENT reason not a P&L one. Today every
trade in the sample is conditioned on *"the selector approved this symbol this
morning."* If that preference correlates with outcome, P0.1's separation test is
measuring the SELECTOR'S TASTE alongside the primitive it is trying to evaluate.
A fixed panel removes the confounder outright.

⚠️ TRADING ONLY. Every box still wakes, collects and pushes — the candle tape,
chain snapshots and S3 corpus keep their full 29-symbol breadth. Only the trade
set is pinned.

⚠️ THE RANKING RULE IS NEUTRAL, AND THAT WAS CHECKED RATHER THAN ASSUMED.
Ranked by TRADE COUNT, never P&L — ranking on profitability would select on the
very outcome the retool is trying to predict. Measured across ~1,045 closed
trades: the top 15 by count contain both the WORST performer (SPX −$4,270) and
among the best (AVGO +$3,744). Count and profit are uncorrelated.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config                                                   # noqa: E402
import selector                                                 # noqa: E402

PANEL = selector.PANEL      # the module IS the source of truth now
FAILS = []


def check(name, cond):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}")
    if not cond:
        FAILS.append(name)


def main():
    print("PANEL OVERRIDE\n")

    # ⚠️ NO ENV VAR IS SET ANYWHERE IN THIS TEST. v0.3.0 read
    # `OT_PANEL_OVERRIDE`; the operator's answer was that a variable which must
    # be exported before each run is a manual pre-run step, and **a manual
    # pre-run step never happens.** The panel is hardcoded — it is simply how
    # the fleet is configured, indefinitely, and changing it is a commit.
    os.environ.pop("OT_PANEL_OVERRIDE", None)
    r = selector.select({})
    check("returns exactly the panel", r["final"] == PANEL)
    check("flags itself as an override", r.get("panel_override") is True)
    check("does NOT report fallback (it is deliberate, not a failure)",
          r["fallback"] is False and r["error"] is None)
    check("keeps the ALWAYS_ON floor",
          all(s in r["final"] for s in config.ALWAYS_ON))
    check("ranked[] is populated so the wake message still renders",
          len(r["ranked"]) == len(PANEL))

    # ALWAYS_ON is injected even if the panel omits it — the daily floor is not
    # negotiable, and an edit to PANEL must not leave the fleet without SPX/QQQ.
    _saved = selector.PANEL
    selector.PANEL = ["NVDA", "PLTR"]
    r2 = selector.select({})
    check("injects ALWAYS_ON when the panel omits it",
          all(s in r2["final"] for s in config.ALWAYS_ON))

    # An unknown symbol is DROPPED AND NAMED, never silently traded.
    selector.PANEL = ["NVDA", "NOTAREALSYM"]
    r3 = selector.select({})
    check("drops an unknown symbol rather than waking a box that is not there",
          "NOTAREALSYM" not in r3["final"])

    # PANEL = [] is the documented way back to discretionary selection.
    selector.PANEL = []
    r4 = selector.select({})
    check("PANEL=[] restores normal discretionary selection",
          r4.get("panel_override") is None)
    selector.PANEL = _saved

    # ⚠️ The announcement is the whole safeguard: a fixed panel is otherwise
    # INDISTINGUISHABLE from a selector that happens to keep picking the same
    # names — the failure shape of every silent gate this project has hit.
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "selector.py"), encoding="utf-8").read()
    check("announces itself loudly", "FIXED PANEL" in src)
    check("uses print, not a logger this module does not have",
          "log.warning" not in src)
    # ⚠️ ASSERT ON CODE, NOT PROSE. The name still appears in the comment that
    # RECORDS why the env var was removed — and that comment is worth keeping.
    # A naive substring search fails on its own documentation.
    check("no env var is READ — the panel is hardcoded",
          "environ.get(\"OT_PANEL_OVERRIDE" not in src
          and "environ[\"OT_PANEL_OVERRIDE" not in src)
    check("PANEL is a module constant",
          isinstance(getattr(selector, "PANEL", None), list))

    print(f"\n{'ALL PASS' if not FAILS else str(len(FAILS)) + ' FAILED: ' + ', '.join(FAILS)}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
