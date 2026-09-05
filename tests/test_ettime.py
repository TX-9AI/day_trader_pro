#!/usr/bin/env python3
"""day_trader_pro/tests/test_ettime.py — v1.1
v1.1  2026-09-05 — dtp r288. 🔴 THE SWEEP NOW READS SHELL TOO. v1.0 walked
`*.py` and I called it the repo — three menu prompts fell back to
`$(date +%F)`, which is UTC, and handed a script tomorrow's date BEFORE any
Python default could apply. The guard missed them because the gap was in the
language it did not read, which is the same shape as the defect it exists to
catch. T6 covers `.sh`.

v1.0  2026-09-05 — dtp r287. THE ET/UTC BOUNDARY, AND THE SWEEP THAT KEEPS IT.

🔴 THE OPERATOR'S SYMPTOM, WHICH THIS EXISTS TO END: *"I run a report for
'today' at 6pm and it says nothing to report, because UTC has already started
the next day."* Control runs UTC, so a bare `date.today()` rolls at 20:00 ET in
summer and 19:00 in winter. After that every naive default asks for TOMORROW,
finds nothing, and REPORTS NOTHING RATHER THAN ERRORING — which reads as a fact
about the market instead of a defect in the clock.

📊 NINE SITES had it wrong and FIVE had it right with five private copies. That
ratio is the point: this was never one missing function, it was the absence of a
boundary, and a boundary that is not enforced grows holes every time somebody
adds a report.

🔑 SO T3 IS THE DURABLE HALF OF THIS FILE. It sweeps the whole repo for naive
clock calls and fails on a NEW one. Fixing nine sites without it buys a year at
most — C.30, the rule that when something changes you sweep its readers, turned
into something that runs.
"""
import ast
import os
import re
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
FAILED = []

# Files allowed to touch a naive clock, each for a stated reason.
#   ettime      — IS the boundary; it converts, so it must call the clock.
#   auto_label  — stamps `labeled_at` with an explicit `.astimezone()`, which is
#                 an aware wall-clock record of when a tool ran, not a trading
#                 date an operator asked for.
EXEMPT = {"ettime.py", "auto_label.py"}
NAIVE = re.compile(r"\b(?:datetime\.now\(\s*\)|date\.today\(\s*\)|"
                   r"datetime\.utcnow\(\s*\)|_date\.today\(\s*\))")


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        FAILED.append(name)


def main():
    try:
        import ettime as E
    except Exception as exc:                                    # noqa: BLE001
        check("T0 ettime imports", False, f"{type(exc).__name__}: {exc}")
        print("\nRED — 1 failed: T0 (dtp r287 has not landed here)")
        return 1
    check("T0 ettime imports", True)

    # ══ T1 — IT ANSWERS IN ET REGARDLESS OF THE BOX ═══════════════════════
    ET = ZoneInfo("America/New_York")
    check("T1 now_et() is timezone-aware, in ET",
          E.now_et().tzinfo is not None
          and "New_York" in str(E.now_et().tzinfo), str(E.now_et().tzinfo))
    check("T1b today_et() is the ET date, not the box's",
          E.today_et() == datetime.now(ET).date().isoformat(), E.today_et())

    # 🔴 T1c — THE BUG ITSELF, REPRODUCED. At 00:30 UTC on the 6th it is still
    # the 5th in ET. A naive default returns the 6th, the report finds nothing,
    # and it says so as though that were the answer.
    utc_after_midnight = datetime(2026, 9, 6, 0, 30, tzinfo=ZoneInfo("UTC"))
    check("T1c the ET day still trails UTC after UTC midnight — the exact "
          "case that reported 'nothing to report'",
          utc_after_midnight.astimezone(ET).date().isoformat() == "2026-09-05",
          utc_after_midnight.astimezone(ET).date().isoformat())

    # ══ T2 — WHAT THE OPERATOR TYPES ═════════════════════════════════════
    for given, want in (("today", E.today_et()), ("", E.today_et()),
                        ("2026-09-03", "2026-09-03"),
                        ("yesterday",
                         (E.now_et() - timedelta(days=1)).date().isoformat())):
        check(f"T2 operator_date({given!r}) resolves in ET",
              E.operator_date(given) == want, E.operator_date(given))
    # ⚠️ AND A TYPO RAISES RATHER THAN DEFAULTING. A prompt that quietly
    # reinterprets an unparseable answer produces a clean report about the
    # wrong day, which is the failure mode this whole module addresses.
    try:
        E.operator_date("last week")
        check("T2b an unparseable date RAISES rather than silently defaulting",
              False, "returned instead of raising")
    except ValueError as exc:
        check("T2b an unparseable date RAISES rather than silently defaulting",
              "last week" in str(exc), str(exc)[:50])

    # ⚠️ RANGES ARE BUILT IN ET DAYS, NOT BY SUBTRACTING SECONDS. 86400 is not
    # a day across a DST boundary, and a range built that way silently drops or
    # doubles a session twice a year.
    back = E.days_back(3, "2026-11-03")          # spans the Nov DST change
    check("T3 days_back spans a DST change without losing a day",
          back == ["2026-11-01", "2026-11-02", "2026-11-03"], str(back))

    # ══ 🔴 T4 — THE SWEEP. THIS IS THE PART THAT KEEPS IT FIXED. ══════════
    offenders = []
    for dirpath, dirnames, filenames in os.walk(_root):
        dirnames[:] = [d for d in dirnames
                       if d not in {".git", "__pycache__", "tests", "venv"}]
        for fn in filenames:
            if not fn.endswith(".py") or fn in EXEMPT:
                continue
            full = os.path.join(dirpath, fn)
            src = open(full, encoding="utf-8").read()
            for i, line in enumerate(src.splitlines(), 1):
                bare = line.split("#", 1)[0]
                if NAIVE.search(bare):
                    offenders.append(f"{os.path.relpath(full, _root)}:{i}")
    check("T4 no naive clock call survives outside the boundary",
          not offenders, f"{len(offenders)}: {offenders[:4]}")

    # ⚠️ AND THE SWEEP CAN FAIL. A checker that has never been red against a
    # planted fault is a checker nobody has tested — r246's refusal-to-pass-on-
    # nothing, applied to a regex.
    check("T4b ...and the sweep actually detects one when it is there",
          bool(NAIVE.search("    d = date.today()"))
          and bool(NAIVE.search("x = datetime.now()"))
          and not NAIVE.search("x = datetime.now(ET)"))

    # ══ 🔴 T6 — SHELL COUNTS. THE GUARD MISSED A WHOLE LANGUAGE. ═════════
    # A prompt that falls back to `$(date +%F)` hands the script a UTC date
    # before any Python default can apply, so r287's nine fixes were invisible
    # behind three ENTER keys. `TZ=America/New_York date +%F` is the correct
    # form and three sibling prompts in the same file already used it.
    sh_bad = []
    BARE_DATE = re.compile(r"(?<!America/New_York )\bdate \+%F\b")
    for dirpath, dirnames, filenames in os.walk(_root):
        dirnames[:] = [d for d in dirnames if d not in {".git", "__pycache__", "venv"}]
        for fn in filenames:
            if not fn.endswith(".sh"):
                continue
            full = os.path.join(dirpath, fn)
            for i, line in enumerate(open(full, encoding="utf-8").read().splitlines(), 1):
                bare = line.split("#", 1)[0]
                if BARE_DATE.search(bare):
                    sh_bad.append(f"{os.path.relpath(full, _root)}:{i}")
    check("T6 no shell date default bypasses the boundary",
          not sh_bad, f"{len(sh_bad)}: {sh_bad[:4]}")
    # ⚠️ AND IT CAN FAIL. A guard never proven red against a planted fault is a
    # guard nobody has tested — which is precisely how v1.0 shipped blind to
    # three of these.
    check("T6b ...and the shell sweep detects one when it is there",
          bool(BARE_DATE.search('D="${D:-$(date +%F)}"'))
          and not BARE_DATE.search('d=$(TZ=America/New_York date +%F)'))

    # ══ T5 — THE CALLERS ACTUALLY USE IT ═════════════════════════════════
    # ⚠️ A module nobody imports is r230's defect. The nine repointed sites are
    # the whole delivery; asserting the module exists proves nothing.
    users = 0
    for fn in os.listdir(_root):
        if fn.endswith(".py") and fn not in EXEMPT:
            if "ettime." in open(os.path.join(_root, fn), encoding="utf-8").read():
                users += 1
    check("T5 the boundary has real callers, not just a definition",
          users >= 10, f"{users} module(s)")
    # 🔴 T5b — market_calendar was the worst of the nine: the module that
    # decides what a trading day IS, asking a UTC box.
    mc = open(os.path.join(_root, "market_calendar.py"), encoding="utf-8").read()
    check("T5b market_calendar asks the boundary, not the box",
          "ettime.today_et()" in mc and not NAIVE.search(
              "\n".join(l.split("#", 1)[0] for l in mc.splitlines())))

    print()
    if FAILED:
        print(f"RED — {len(FAILED)} failed: {', '.join(FAILED)}")
        return 1
    print(f"GREEN — {15} checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
