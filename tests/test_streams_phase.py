#!/usr/bin/env python3
"""day_trader_pro/tests/test_streams_phase.py — v1.0
v1.0  2026-09-05 — dtp r285 / S3.12. THE PER-STREAM BOARD IS A PHASE, AND IT
REPORTS ITS ROWS.

🔑 WHY THIS IS WIRED NOW AND NOT WHEN IT WAS BUILT. r277 shipped `--streams`
and left it unwired on purpose: the CONDITIONAL and DEAD classifications were
read out of `s3_push`'s stage list and never checked against a real bucket. The
first hand-run raised nine flags and SEVEN were the policy table. An alarm wired
before that would have cried wolf on night one and been ignored by night two —
which is the failure this whole family of checks exists to avoid.

⚠️ P3 IS THE ONE THAT MATTERS. `head -3` in the conductor's purge phase ate the
cause of every failure for weeks (dtp r282), one phase over from this one. A
summary that hides its rows is a summary nobody can act on, so the phase must
carry the flagged lines through — including the ACCEPTED-LOSS rows, which print
on a clean night too because r284's contract is that a closed absence stays
visible rather than disappearing.
"""
import ast
import os
import re
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
FAILED = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        FAILED.append(name)


def main():
    src = open(os.path.join(_root, "eod_analysis.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    fns = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}

    if "_streams" not in fns:
        check("P0 eod_analysis defines a _streams phase", False,
              "absent — dtp r285 has not landed in this checkout")
        print("\nRED — 1 failed: P0")
        return 1
    check("P0 eod_analysis defines a _streams phase", True)

    # ══ P1 — IT IS ACTUALLY IN THE PHASE LIST ═════════════════════════════
    # ⚠️ A function nobody calls is the r230 defect: a constant declared and
    # never wired. The phase list is what runs, not the def.
    m = re.search(r"for nm, fn, note in \((.*?)\)\):", src, re.S)
    order = re.findall(r'\("([A-Z_]+)"', m.group(1)) if m else []
    check("P1 STREAMS is in the phase list that actually runs",
          "STREAMS" in order, str(order))
    # ⚠️ AFTER COVERAGE, BEFORE THE R SUITE. Both read the warehouse; running
    # the board first means a gap is on screen before the numbers derived from
    # that same data.
    check("P1b ...directly after COVERAGE and before R_LEDGER",
          "STREAMS" in order and "COVERAGE" in order and "R_LEDGER" in order
          and order.index("COVERAGE") + 1 == order.index("STREAMS")
          < order.index("R_LEDGER"), str(order))

    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_streams")
    body = ast.unparse(fn)

    # ══ P2 — IT RUNS THE REAL FLAG, ON THE RUN'S DATE ═════════════════════
    check("P2 it invokes warehouse_coverage with --streams",
          "'--streams'" in body or '"--streams"' in body)
    check("P2b ...scoped to the date being processed, not a default window",
          "'--date'" in body or '"--date"' in body)
    # ⚠️ A SEPARATE PHASE, NOT FOLDED INTO COVERAGE. The VIX report answers a
    # different question and has its own exit code; two questions behind one
    # green is how a passing check stops meaning anything.
    cov = next(n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "_coverage")
    check("P2c ...and COVERAGE is left alone, still answering its own question",
          "--streams" not in ast.unparse(cov))

    # ══ 🔴 P3 — THE ROWS SURVIVE. THIS IS THE `head -3` LESSON. ═══════════
    # dtp r282, one phase over: a truncated report cost three round trips to
    # learn a purge was dying on a locked database.
    check("P3 the flagged rows are logged, not reduced to a count",
          "flagged" in body and "_log" in body)
    for mark, why in (("🔴", "a gap"), ("❗", "a stale exemption"),
                      ("▪", "an accepted loss — visible on a CLEAN night too"),
                      ("❓", "an undeclared stream")):
        check(f"P3b {mark} rows are carried through ({why})", mark in body)

    # ══ P4 — WARN, NEVER STOP ═════════════════════════════════════════════
    # ⚠️ A coverage gap is a fact about yesterday. A phase that aborted the run
    # would cost the R baseline over a missing OHLC file.
    check("P4 a failure warns rather than raising",
          "_warn" in body and "raise" not in body)
    check("P4b ...and a clean board says so explicitly rather than silently",
          "✅" in body)

    print()
    if FAILED:
        print(f"RED — {len(FAILED)} failed: {', '.join(FAILED)}")
        return 1
    print("GREEN — 12 checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
