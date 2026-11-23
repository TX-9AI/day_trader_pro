#!/usr/bin/env python3
"""
day_trader_pro/tests/check_live_setups_wording.py — v1.0
v1.0  2026-11-23  dtp r580 / TRIM.2 wording (control's prompts after OTV5 r153; the operator, 2026-11-23: "The hunt & OGAP
      are trash. Retire them both after this session today."). Wording only; the full report purge is a later land.

  W1  tools/daily_recap.prompt, tools/nightly_review.prompt and tools/saturday_brief.prompt each say the live setups are
      PARK and RunawayContinuation ONLY, that the Hunt and OGAP were retired by OTV5 r153 on 2026-11-23, and that a day
      with zero Hunt or OGAP trades is expected, never a defect
  W2  no prompt still names LiquidityHunt as a live plan ("The live plans are RunawayContinuation (Runaway),
      LiquidityHunt" / "The live plans are RunawayContinuation, LiquidityHunt")
  W3  the Saturday brief prompt says its standing Hunt and OGAP items report history and make no R-item
BORN RED on 613fb1d (r579): every prompt still lists LiquidityHunt as live.

Run:  python3 tests/check_live_setups_wording.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPTS = ("daily_recap.prompt", "nightly_review.prompt", "saturday_brief.prompt")
FAILS, RAN = [], []


def ck(n, ok, msg=""):
    RAN.append(n)
    print(f"  {n:<3} {'PASS' if ok else 'FAIL'}  {msg if not ok else ''}")
    if not ok:
        FAILS.append(n)


def main():
    txt = {p: re.sub(r"\s+", " ", open(os.path.join(ROOT, "tools", p), encoding="utf-8").read()) for p in PROMPTS}
    need = ("THE LIVE SETUPS ARE PARK AND RunawayContinuation", "ONLY", "OTV5 r153",
            "so a day with zero Hunt or OGAP trades is EXPECTED, never a defect",
            "a Hunt or OGAP trade after 2026-11-23 is a DEFECT")
    miss = {p: [n for n in need if n not in t] for p, t in txt.items()}
    ck("W1", not any(miss.values()), f"missing {miss}")
    old = ("The live plans are RunawayContinuation (Runaway), LiquidityHunt",
           "The live plans are RunawayContinuation, LiquidityHunt")
    left = {p: [o for o in old if o in t] for p, t in txt.items()}
    ck("W2", not any(left.values()), f"still live: {left}")
    ck("W3", "The standing Hunt and OGAP items below report their history to 2026-11-23 and say RETIRED; they make no "
             "R-item" in txt["saturday_brief.prompt"])
    print()
    if FAILS:
        print(f"FAILED: {' '.join(FAILS)}")
        return 1
    print(f"ALL {len(RAN)} PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
