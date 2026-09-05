#!/usr/bin/env python3
"""day_trader_pro/tests/test_confirm_and_cap.py — v1.0
v1.0  2026-09-05 — dtp r283. THE TWO THINGS THAT SILENTLY REFUSED A REAL RUN.

🔴 BOTH WERE MEASURED ON 2026-09-05, NOT IMAGINED. The operator asked for a
one-box OHLC backfill against a 15-box fleet and got two refusals in a row:
the `--stream-cap` default of 10 is 29-box arithmetic and hard-stops (`return
2`), and then the menu's confirm compared against lowercase `y` only, so his
`Y` fell through with no error and no message.

⚠️ C1 EXECUTES `_yes` IN A REAL SHELL rather than grepping for the comparison.
The failure was behavioural — an answer that should have matched and did not —
and a source check would pass against any spelling that happens to parse.

⚠️ AND C3 IS THE ONE THAT MATTERS MOST: it asserts NO lowercase-only confirm
survives ANYWHERE in the menu. Fixing the site that bit and leaving five others
is how this returns, and C.30 already names it — when a rule changes, sweep its
readers.
"""
import os
import re
import subprocess
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
FAILED = []


_names = []


def check(name, ok, detail=""):
    _names.append(name)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        FAILED.append(name)


def _yes(answer):
    """Run the REAL helper out of devtools.sh, in a shell, with that answer."""
    # ⚠️ THE DEFINITION IS EXTRACTED, NEVER SOURCED. `devtools.sh` ends in an
    # interactive menu loop, so sourcing it here would launch the menu inside a
    # test — a fixture with a side effect on the operator's terminal.
    src = open(os.path.join(_root, "devtools.sh"), encoding="utf-8").read()
    m = re.search(r"^_yes\(\).*$", src, re.M)
    if not m:
        return None
    r = subprocess.run(
        ["bash", "-c", f"{m.group(0)}\n_yes {answer!r} && echo YES || echo NO"],
        capture_output=True, text=True)
    return (r.stdout or "").strip().endswith("YES")


def main():
    dv = os.path.join(_root, "devtools.sh")
    src = open(dv, encoding="utf-8").read()
    if "_yes()" not in src:
        check("C0 devtools.sh defines _yes", False,
              "absent — r283 has not landed in this checkout")
        print("\nRED — 1 failed: C0")
        return 1
    check("C0 devtools.sh defines _yes", True)

    # ══ C1 — THE ANSWER THAT WAS THROWN AWAY ══════════════════════════════
    # 🔴 `Y` at the LIVE backfill prompt did nothing on 2026-09-05.
    for a in ("y", "Y", "yes", "YES", "Yes"):
        check(f"C1 {a!r} is accepted", _yes(a))
    # ⚠️ AND IT MUST STILL REFUSE EVERYTHING ELSE. A confirm loosened into
    # "anything non-empty" would be worse than the bug it replaces: these
    # prompts wake boxes, stop trading and delete rows.
    for a in ("", "n", "N", "no", "sure", "ye"):
        check(f"C1b {a!r} is refused", not _yes(a))

    # ══ C2 — A DESTRUCTIVE DECLINE SAYS SO ════════════════════════════════
    # The whole failure was silence: no error, no message, just the next
    # prompt, indistinguishable from a run that did nothing.
    mf = open(os.path.join(_root, "menu_functions.sh"), encoding="utf-8").read()
    bf = mf[mf.index("mi_backfill_missing_ohlc"):][:2500]
    check("C2 a declined LIVE backfill says what it declined",
          "declined" in bf and "nothing was woken" in bf)

    # ══ C3 — AND NO LOWERCASE-ONLY CONFIRM SURVIVES ANYWHERE ══════════════
    # 🔑 C.30: when a rule changes, sweep its readers. Six sites had this and
    # fixing only the one that bit is how it comes back.
    stragglers = re.findall(r'\[\s*"\$\w+"\s*=\s*"[yY]"\s*\]', mf)
    check("C3 no confirm in the menu compares against a single spelling",
          not stragglers, f"{len(stragglers)} left: {stragglers[:3]}")

    # ══ K1 — THE STREAM CAP IS OFF 29-BOX ARITHMETIC ══════════════════════
    # 🔴 A ONE-box backfill against a 15-box fleet was REFUSED — and it is a
    # hard stop (`return 2`), not a warning. r53 retired the fleet-wide copy of
    # this same guard after the 08-20 pare; this one was never swept.
    import eod_backfill as eb
    check("K1 the default cap admits the whole fleet plus a batch",
          eb.STREAM_CAP >= 16, f"{eb.STREAM_CAP}")
    # ⚠️ RESOLVED THROUGH THE REAL PATH, not read off the constant: the parser
    # default is what a menu run actually gets.
    # ⚠️ THE PARSER DEFAULT IS WHAT A MENU RUN ACTUALLY GETS, so it is read
    # from the real `add_argument` rather than assumed to match the constant —
    # a constant nobody wired is the r230 defect exactly.
    ebsrc = open(os.path.join(_root, "eod_backfill.py"), encoding="utf-8").read()
    check("K1b the argparse default is the constant, not a second number",
          re.search(r'--stream-cap"[^)]*default=STREAM_CAP', ebsrc, re.S)
          is not None)
    check("K1c and it stays env-overridable for a one-off",
          "OT_STREAM_CAP" in open(
              os.path.join(_root, "eod_backfill.py"), encoding="utf-8").read())

    print()
    if FAILED:
        print(f"RED — {len(FAILED)} failed: {', '.join(FAILED)}")
        return 1
    print(f"GREEN — {len(_names)} checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
