#!/usr/bin/env python3
"""
tests/check_r_excludes_fees.py  v1.0
v1.0  2026-09-25  r428 / OPS.52 — R IS GROSS OF FEES, BY RULING, AND R IS
      SIZE-INVARIANT, BY ARITHMETIC.

  🔑 G1 EXISTS BECAUSE THE CORRECT BEHAVIOUR LOOKS LIKE A BUG. Operator,
  2026-09-25: *"We have to leave fees out because that distorts small
  contracts. In some cases, the fees will exceed the contract values simply
  because it's such small numbers, but the R value shouldn't be diminished
  because of this."* A future reader who finds R ignoring a populated FEES
  column will reach for the obvious fix. This gate refuses it and names the
  ruling, which is the only thing that survives the thread.

  🔑 G4 PROVES THE PREMISE THE WHOLE CHANGE RESTS ON. The operator sizes the
  TEST boxes at ~10% nominal and reads R because R should not care. That is an
  arithmetic claim and it is testable: the SAME trades at 1x and at 10x
  contracts must give the IDENTICAL R. If they ever diverge, R has stopped
  being comparable across lineages and every TEST-vs-MAIN conclusion drawn
  from it is void.

  ⚠️ G1 AND G3 ARE DECLARED REGRESSION GUARDS, NOT BORN-RED FINDINGS. Nothing
  nets fees into R today; these pin it so nothing starts. Saying so matters —
  a gate that passed the moment it was written is evidence of intent, not of a
  bug fixed, and blurring the two is how a green sweep stops meaning anything.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_fails = []


def ck(tag, ok, msg=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {tag}  {msg}")
    if not ok:
        _fails.append(tag)


def _trade(contracts, entry, exit_, stop):
    """One synthetic closed trade. pnl scales with contracts, as the real
    pusher writes it (verified against premium math on 2026-09-24)."""
    return {
        "contracts": contracts,
        "entry_premium": entry,
        "exit_premium": exit_,
        "stop_premium": stop,
        "pnl_usd": (exit_ - entry) * contracts * 100,
        "max_loss": abs(entry - stop) * contracts * 100,
        "total_cost": entry * contracts * 100,
        "strategy": "ORBStrategy",
        "symbol": "TEST",
    }


def main():
    try:
        import trade_report as TR
    except Exception as exc:                                   # noqa: BLE001
        for t in ("G1", "G2", "G3", "G4"):
            ck(t, False, f"cannot import trade_report ({exc})")
        print(f"\nRED — {len(_fails)} check(s) failed: {' '.join(_fails)}")
        return 1

    src = open(os.path.join(ROOT, "trade_report.py"), encoding="utf-8").read()

    # ── G1 — DECLARED GUARD: no fee term inside the R path ─────────────────
    # ⚠️ AST, NOT REGEX, AND THE FIRST CUT PROVED WHY. A regex over the function
    # body matched `_bucket_r`'s OWN DOCSTRING — the one that explains "GROSS OF
    # FEES" and "nothing here nets fees into it". The documentation of the
    # ruling tripped the gate enforcing the ruling. That is the FIFTH checker
    # self-match recorded this session (r420 P2, r417 §20, r426 P5, the r423
    # creep predicate), and the lesson has not changed: ask the AST what the
    # CODE does, never the text what it says.
    import ast as _ast
    bad = []
    _tree = _ast.parse(src)
    _fns = {n.name: n for n in _ast.walk(_tree)
            if isinstance(n, _ast.FunctionDef)}
    for fn in ("_bucket_r", "modified_r", "r_value"):
        node = _fns.get(fn)
        if node is None:
            bad.append(f"{fn} missing")
            continue
        # every NAME and ATTRIBUTE the executable body touches — docstrings and
        # comments are not nodes, so they cannot be matched
        names = set()
        for sub in _ast.walk(node):
            if isinstance(sub, _ast.Name):
                names.add(sub.id.lower())
            elif isinstance(sub, _ast.Attribute):
                names.add(sub.attr.lower())
            elif isinstance(sub, _ast.Constant) and isinstance(sub.value, str):
                pass                      # a string literal is data, not a call
        if any("fee" in n for n in names):
            bad.append(f"{fn} CALLS something fee-related: "
                       f"{sorted(n for n in names if 'fee' in n)}")
    ck("G1", not bad,
       "no fee term appears in _bucket_r / modified_r / r_value — R stays "
       "GROSS per the operator's ruling (declared guard, not born red)"
       if not bad else f"FEES LEAKED INTO R: {bad}")

    # ── G2 — an unmeasurable R prints '-', never a fabricated 0.000 ────────
    # ⚠️ EVERY PROBE IS GUARDED. The first cut called TR._r_cell directly, so at
    # HEAD — where the helper does not exist yet — the gate died with an
    # AttributeError and reported ONLY G1, leaving G2-G4 unstated. A born-red
    # run that crashes says less than one that fails, and "the gate errored" is
    # not the same finding as "the check failed". Each probe now reports its
    # own absence.
    try:
        cell_none = TR._r_cell({"r_gross": None, "r_n": 0, "n": 5})
        cell_real = TR._r_cell({"r_gross": 0.25, "r_n": 5, "n": 5})
        ck("G2", cell_none.strip() == "-" and "0.25" in cell_real,
           f"no-basis bucket renders {cell_none.strip()!r} (must be '-', because "
           f"zero R and unmeasurable R are different facts)")
    except Exception as exc:                                   # noqa: BLE001
        ck("G2", False, f"_r_cell unusable ({type(exc).__name__}: {exc})")

    # ── G3 — DECLARED GUARD: strategy is ranked WITHIN a lineage ───────────
    ck("G3", 'findings[f"best_strategy@{_lin}"]' in src
             and "cross-lineage dollar comparison" in src,
       "the headline ranks strategy per lineage and says why — at 10% nominal "
       "a TEST bucket can never place on dollars")

    # ── G4 — 🔑 R IS SIZE-INVARIANT. The premise, proven. ──────────────────
    small = [_trade(1, 1.00, 1.30, 0.80), _trade(2, 0.40, 0.30, 0.20)]
    big = [_trade(10, 1.00, 1.30, 0.80), _trade(20, 0.40, 0.30, 0.20)]
    try:
        rs = TR._bucket_r(small)
        rb = TR._bucket_r(big)
    except Exception as exc:                                   # noqa: BLE001
        # ⚠️ ONE CHECK, ONE LINE. The first cut reported G4 TWICE on a missing
        # helper — once here and once below — and a gate that double-counts its
        # own failures is a gate whose totals cannot be trusted.
        ck("G4", False, f"_bucket_r unusable ({type(exc).__name__}: {exc})")
        rs = rb = None
    if rs is None:
        pass
    else:
        same = (rs["r_gross"] is not None and rs["r_gross"] == rb["r_gross"])
        ck("G4", same,
           f"the same trades at 1x and 10x contracts give the SAME R "
           f"({rs['r_gross']} vs {rb['r_gross']}) — so the TEST boxes' 10% "
           f"sizing cannot flatter or penalise them"
           if same else
           f"R CHANGED WITH SIZE: {rs['r_gross']} vs {rb['r_gross']} — R is no "
           f"longer comparable across lineages and every TEST-vs-MAIN read is "
           f"void")

    if _fails:
        print(f"\nRED — {len(_fails)} check(s) failed: {' '.join(_fails)}")
        return 1
    print("\nGREEN — R is gross by ruling, size-invariant by arithmetic, and "
          "never ranked across lineages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
