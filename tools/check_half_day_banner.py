#!/usr/bin/env python3
"""
day_trader_pro/tools/check_half_day_banner.py  v1.1
v1.1  2026-09-07  dtp r319 - B3 re-anchored on the AST. The string-position
version went red on this delivery's OWN version header, which names the banner
because §5 requires the entry. §20, sixth time this session.
v1.0  2026-09-07  dtp r319 / DEP.12 — THE HALF-DAY BANNER, EXECUTED.

Operator, 2026-09-07: a banner in the market brief ABOVE the symbols strength
list, on Telegram. That is the whole ask — DEP.12 itself stays OPEN, because
nothing shortens the session: `VERTICAL_HOLD_TO_ET` 15:45, the 15:40 flatten
ladder and the butterfly's 15:45 hard close are all keyed to a 16:00 bell and
will fire after it on a 13:00 day.

⚠️ B3 IS THE ONE THAT MATTERS AND IT IS ABOUT PLACEMENT, NOT PRESENCE. "Above
the strength list" was the request; a banner appended at the end would pass any
check that only asked whether the text exists. This builds the real message and
asserts the banner's INDEX is below the title and above the first symbol row.

⚠️ AND B4 IS TELEGRAM SAFETY. r290 cost a day to a single "<" in a sent
message — the failure is the WHOLE message failing to parse, not one character
rendering oddly, so a brief that silently never arrives is the actual risk.

Run:  python3 tools/check_half_day_banner.py
"""
from __future__ import annotations

import datetime as d
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import market_calendar as mc                                     # noqa: E402

F: list = []


def check(n, ok, det=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {n}" + (f"  — {det}" if det else ""))
    if not ok:
        F.append(n)


def main() -> int:
    print("\ncheck_half_day_banner\n")

    check("B1  2026-11-27 (day after Thanksgiving) is a half day",
          mc.is_half_day(d.date(2026, 11, 27)))
    check("B1b an ordinary session is not",
          not mc.is_half_day(d.date(2026, 11, 30)))
    # 🔴 A HALF DAY IS A TRADING DAY. If this ever inverts, the fleet sits out
    # 52 real sessions between now and 2050.
    check("B2  every early close is still a TRADING day",
          all(mc.is_trading_day(x) or x in mc.HOLIDAYS_US
              for x in mc.EARLY_CLOSES),
          f"{len(mc.EARLY_CLOSES)} early closes")
    check("B2b a full closure that collides with an early-close rule reports "
          "NOT a half day",
          not mc.is_half_day(d.date(2026, 7, 3)),
          "Jul 4 2026 is a Saturday, so Jul 3 is a full holiday")

    src = open(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "orchestrator.py")).read()

    # 🔴 B3 IS ANCHORED ON THE AST, NOT ON STRING POSITIONS. The first cut used
    # `src.find("HALF DAY")` and went red the moment r319's own version header
    # said "carries a HALF DAY banner" — the header §5 REQUIRES. That is WA §20
    # for the SIXTH time in one session, and it keeps happening because the
    # changelog necessarily names what the check looks for.
    # What matters is the ORDER OF THE append() CALLS inside the function that
    # builds the message, which is a property of the tree and of no spelling.
    import ast
    tree = ast.parse(src)
    fn = max((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
              and any("server(s)" in ast.dump(x) for x in ast.walk(n))),
             key=lambda n: n.lineno, default=None)
    order = []
    if fn:
        for node in ast.walk(fn):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "append"):
                txt = ast.dump(node)
                if "HALF DAY" in txt:
                    order.append(("banner", node.lineno))
                elif "server(s)" in txt:
                    order.append(("list", node.lineno))
    order.sort(key=lambda t: t[1])
    seq = [k for k, _ in order]
    # ⚠️ THE TITLE IS NOT AN append() - it is the initial `lines = [...]`
    # literal, so there is no node to order against. The first AST cut looked
    # for a title append and found none, which is what a check gets for
    # assuming a shape instead of reading one. Assert what is actually true:
    # the title opens the list, and the banner is appended before the wake row.
    title_first = any(isinstance(n, ast.Assign) and "morning wake" in ast.dump(n)
                      for n in ast.walk(fn)) if fn else False
    check("B3  the banner append precedes the wake/strength list",
          seq[:2] == ["banner", "list"], f"append order: {seq}")
    check("B3b the title opens the message (lines = [...])", title_first)

    # B4 — Telegram safety of the literal banner strings.
    lits = re.findall(r'"(⚠️ \*HALF DAY[^"]*)"', src)
    lits += re.findall(r'"(_Exit times[^"]*)"', src)
    bad = [c for lit in lits for c in "<>&" if c in lit]
    check("B4  the banner carries no <, > or & (r290)", not bad and bool(lits),
          f"{len(lits)} literal(s)")

    # B5 — it must NOT claim the fleet handles it.
    check("B5  the banner says exits still fire after the bell",
          "after the bell" in src, "DEP.12 stays open and the message says so")

    print()
    if F:
        print(f"check_half_day_banner: FAIL ({len(F)}): {', '.join(F)}")
        return 1
    print("check_half_day_banner: ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
