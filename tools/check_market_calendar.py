#!/usr/bin/env python3
"""
day_trader_pro/tools/check_market_calendar.py  v1.1
v1.1  2026-09-07  dtp r318 - records that D5 makes the LAND ORDER load-bearing:
otv4 must land first, because this check reads otv4's list off disk during dtp's
half. Not a code change - a constraint discovered by a refused land, written
down where the next reader will see it.
v1.0  2026-09-07  dtp r317 / DEP.11 + DEP.13 — THE LIST IS VERIFIED ARITHMETIC,
AND THE TWO REPOS ARE COMPARED.

Two jobs, and the second is the one DEP.11 was opened for.

1. REGENERATE every standard closure from the NYSE rules and fail on a single
   wrong date. A hardcoded list is a transcription, and transcriptions have
   typos. The rules live here, control-side, and never run on the live path.

2. 🔴 DIFF THIS SET AGAINST otv4's. Two lists in two repos that cannot import
   each other WILL diverge the first year only one is refreshed — and the
   symptoms differ by side, which is what makes it hard to spot: control
   mis-scopes a report, the fleet arms on a closed market. **This was already
   true when the check was written**: dtp's list ended at 2026 while otv4's
   reached 2027, and nothing had ever compared them.

⚠️ THE otv4 DIFF IS SKIPPED, NOT FAILED, WHEN THAT REPO IS ABSENT. A gate that
goes red because a sibling checkout is missing is red for an ENVIRONMENT reason,
which is the CV.1 failure — it teaches you to skip red runs. SKIP and NOT
APPLICABLE must not look like PASS, so it says which it is.

⚠️ `pandas_market_calendars` IS A CROSS-CHECK HERE AND DECIDES NOTHING. Until
r317 it OVERRODE the list at runtime, so which source answered depended on
whether a pip package happened to be installed. Where it is available it is the
one thing genuinely better than the rules: it knows the ad-hoc closures no
algorithm produces. It reports; it does not rule.

🔴 D5 MAKES THE LAND ORDER LOAD-BEARING: otv4 MUST LAND FIRST. This check
runs during dtp's half and reads otv4's list OFF DISK, so if dtp goes first D5
compares the new list against otv4's OLD one and correctly reports divergence,
failing the delivery. Found the hard way on 2026-09-07: dtp was ORDER 1 and the
land refused. The check was right; the ordering was wrong.
⚠️ DO NOT LOOSEN D5 TO TOLERATE THIS. Telling 'otv4 is mid-land' apart from
'the two lists really diverged' is exactly the judgement D5 exists to make, and
a check that shrugs at a mismatch is the CV.1 failure. Any delivery touching
both calendars carries ORDER with otv4 first.

Run:  python3 tools/check_market_calendar.py
"""
from __future__ import annotations

import datetime as d
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import market_calendar as mc                                     # noqa: E402

F: list = []


def check(n, ok, det=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {n}" + (f"  — {det}" if det else ""))
    if not ok:
        F.append(n)


def _nth(y, m, wd, n):
    x = d.date(y, m, 1)
    x += d.timedelta((wd - x.weekday()) % 7)
    return x + d.timedelta(7 * (n - 1))


def _last(y, m, wd):
    x = d.date(y, m + 1, 1) - d.timedelta(1)
    return x - d.timedelta((x.weekday() - wd) % 7)


def _easter(y):
    a = y % 19
    b, c = divmod(y, 100)
    e, f = divmod(b, 4)
    g = (8 * b + 13) // 25
    h = (19 * a + b - e - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * f + 2 * i - h - k) % 7
    m = (a + 11 * h + 19 * l) // 433
    mo = (h + l - 7 * m + 90) // 25
    da = (h + l - 7 * m + 33 * mo + 19) % 32
    return d.date(y, mo, da)


def _obs(x):
    # NYSE's rule, not the federal one: Columbus Day and Veterans Day are
    # federal holidays and the exchange TRADES.
    if x.weekday() == 5:
        return x - d.timedelta(1)
    if x.weekday() == 6:
        return x + d.timedelta(1)
    return x


def rules_for(y):
    return {_obs(d.date(y, 1, 1)), _nth(y, 1, 0, 3), _nth(y, 2, 0, 3),
            _easter(y) - d.timedelta(2), _last(y, 5, 0),
            _obs(d.date(y, 6, 19)), _obs(d.date(y, 7, 4)),
            _nth(y, 9, 0, 1), _nth(y, 11, 3, 4), _obs(d.date(y, 12, 25))}


def main() -> int:
    print("\ncheck_market_calendar (dtp)\n")
    listed = set(mc.HOLIDAYS_US) - set(mc.AD_HOC_CLOSURES)
    years = sorted({x.year for x in listed})
    lo, hi = years[0], years[-1]

    gen = set()
    for y in range(lo, hi + 2):          # +1 for the NYD spill-in
        gen |= rules_for(y)
    gen = {x for x in gen if lo <= x.year <= hi}
    inr = {x for x in listed if lo <= x.year <= hi}

    check("D1  every hardcoded date is produced by the rules",
          not (inr - gen), f"unexplained: {sorted(inr - gen)}")
    check("D2  every rule-produced date is in the list",
          not (gen - inr), f"missing: {sorted(gen - inr)}")
    check("D3  coverage runs at least 5 years ahead",
          hi >= d.date.today().year + 5, f"covers {lo}-{hi}")
    # 🔴 ANCHORED ON THE AST, NOT ON A STRING. The first cut searched the
    # source for "return lib" and went RED on r317's OWN CHANGELOG COMMENT,
    # which names it while explaining that it was removed — WA §20, and the
    # FIFTH time this session that a canary matched the prose Rule 5 requires.
    # What matters is whether `is_trading_day` CALLS `_via_library`, which is a
    # property of the tree and not of any spelling.
    import ast
    src = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "market_calendar.py")
    tree = ast.parse(open(src).read())
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "is_trading_day"),
              None)
    calls = {c.func.id for c in ast.walk(fn) if isinstance(c, ast.Call)
             and isinstance(c.func, ast.Name)} if fn else set()
    check("D4  is_trading_day does NOT call _via_library — the list decides",
          fn is not None and "_via_library" not in calls,
          f"calls: {sorted(calls)}")

    # ── DEP.11 — the two repos must agree ───────────────────────────────────
    otv4 = os.environ.get("DTP_OTV4_DIR", os.path.expanduser("~/options-trader-v4"))
    other = os.path.join(otv4, "utils", "market_calendar.py")
    if not os.path.exists(other):
        print(f"  SKIP  D5  otv4 not present at {otv4} — cross-repo diff NOT "
              f"RUN (this is a skip, not a pass)")
    else:
        ns: dict = {}
        exec(compile(open(other).read(), other, "exec"), ns)      # noqa: S102
        theirs = set(ns["US_MARKET_HOLIDAYS"]) - set(ns["AD_HOC_CLOSURES"])
        mine = {x.isoformat() for x in listed}
        check("D5  otv4 and dtp hold the SAME standard closures",
              mine == theirs,
              f"dtp-only: {sorted(mine - theirs)[:3]} "
              f"otv4-only: {sorted(theirs - mine)[:3]}")

    print(f"  NOTE  AD_HOC_CLOSURES: {sorted(mc.AD_HOC_CLOSURES) or 'none'}")
    print()
    if F:
        print(f"check_market_calendar: FAIL ({len(F)}): {', '.join(F)}")
        return 1
    print(f"check_market_calendar: ALL PASS — {len(inr)} closures {lo}-{hi}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
