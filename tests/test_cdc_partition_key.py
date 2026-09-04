#!/usr/bin/env python3
"""day_trader_pro/tests/test_cdc_partition_key.py — v1.0
v1.0  2026-09-04 — dtp r266. THE CDC COLLAPSE KEY MUST CARRY THE PARTITION.

🔴 `_rid` is the SOURCE TABLE'S sqlite `rowid` (otv4 `warehouse/s3_push.py:945`,
`SELECT rowid AS _rid, *`). It is unique only within ONE box's table at ONE
moment — boxes purge and rebuild their derived stores, so rowids RESTART every
session. Collapsing on `(symbol, _rid)` across a multi-day range therefore
folds DIFFERENT SESSIONS' ROWS TOGETHER and the later `pushed_at_utc` wins.
Measured 08-31..09-04: strategy_note 325,762 rows -> 37,584, and the fit report
read 2 fired GEX butterflies where the trade log has 20.

⚠️ THE COLLAPSE ITSELF IS CORRECT AND STAYS. CDC pushes the same row repeatedly
and only its latest state should survive. What was wrong is the SCOPE.
"""
import ast
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FAILED = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        FAILED.append(name)


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # ══ C1 — THE COLLISION, AS ARITHMETIC ═════════════════════════════════
    # Two sessions, same symbol, rowid 1 in each. The old key loses one.
    rows = [("2026-09-01", "QQQ", 1, "session A"),
            ("2026-09-04", "QQQ", 1, "session B")]
    old = {(sym, rid) for _d, sym, rid, _v in rows}
    new = {(sym, d, rid) for d, sym, rid, _v in rows}
    check("C1 the old (symbol, _rid) key collapses two sessions into one",
          len(old) == 1, str(old))
    check("C1b the partition-scoped key keeps both", len(new) == 2)

    # ══ C2 — THE READER USES THE SCOPED KEY ═══════════════════════════════
    # ⚠️ AST, not a string search: the file's own comment explains the OLD key,
    # so grepping for it would match the explanation (§20).
    src = open(os.path.join(root, "warehouse_reader.py"), encoding="utf-8").read()
    keys = []
    for node in ast.walk(ast.parse(src)):
        if (isinstance(node, ast.Assign)
                and any(getattr(t, "id", "") == "key" for t in node.targets)
                and isinstance(node.value, ast.Tuple)):
            keys.append(len(node.value.elts))
    check("C2 load_derived's collapse key is 3-part (sym, partition, _rid)",
          keys and all(k == 3 for k in keys), f"arities {keys}")

    # ══ C3 — AND IT IS NOT RE-COLLAPSED DOWNSTREAM ════════════════════════
    # 🔴 fit_readiness ran a SECOND collapse in SQL — `GROUP BY _rid` — which
    # cannot carry the partition and would silently undo the fix. That was the
    # collapse the report actually printed.
    # ⚠️ ANCHORED ON THE SQL STRING, NOT THE PHRASE. The first cut matched
    # "GROUP BY _rid" anywhere outside a `#` comment and went RED against the
    # FIXED file — the docstring explaining the removal still says the words,
    # and a docstring is not a comment line. §20 in my own checker: the canary
    # cannot match the prose that documents the change.
    fr = open(os.path.join(root, "fit_readiness.py"), encoding="utf-8").read()
    check("C3 fit_readiness no longer re-collapses with GROUP BY _rid",
          'FROM "{t}" GROUP BY _rid' not in fr)
    # ⚠️ THE DE-DUP RETURNS, ON A KEY THAT CANNOT FOLD TWO SESSIONS. Removing
    # it outright let a re-pushed object double-count (caught by
    # test_fit_readiness_memory M4) — and a double-count is a different wrong
    # number, not a right one. `_rid` alone repeats across sessions; (_rid, ts)
    # does not.
    check("C3b the de-dup key carries the timestamp, not _rid alone",
          "GROUP BY _rid, {_DEDUP_TS[t]}" in fr and "_DEDUP_TS = {" in fr)

    print()
    if FAILED:
        print(f"RED — {len(FAILED)} failed: {', '.join(FAILED)}")
        return 1
    print("GREEN — 5 checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
