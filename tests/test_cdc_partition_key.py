#!/usr/bin/env python3
"""day_trader_pro/tests/test_cdc_partition_key.py — v1.1
v1.1  2026-09-05 — dtp r276. RE-DERIVED, NOT PATCHED. C2 asserted that the
collapse key is 3-part `(sym, partition, _rid)` — which is the exact shape r276
replaces, so leaving it would CERTIFY THE DEFECT ON EVERY RUN. That is the trap
r234 named three times in one file and r233 named again: a fixture that pins the
rule being retired is worse than no fixture, because it goes green while the
thing it guards is wrong.
🔑 THE HISTORY IN C1/C1b STAYS. The rowid collision was real and the arithmetic
that shows it is still the reason `_rid` is not an identity. What changes is the
CONCLUSION drawn from it: the answer was never a better scope for a rowid, it
was the primary key the box already enforces. C2 now pins that the partition-
scoped rid survives ONLY as the fallback for a table with no natural key.
⚠️ The behavioural proof lives in `tests/test_natural_key.py`, which EXECUTES
`load_derived`; this file stays a structural companion to it.

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

    # ══ C2 — THE READER KEYS ON THE TABLE'S OWN PRIMARY KEY ══════════════
    # ⚠️ EXECUTED, not read as source text. r276's `collapse_key` is a module
    # function precisely so a checker can drive it rather than re-implement the
    # arithmetic beside it (C.23), and the file's own comments discuss BOTH the
    # old key and the new one, so any string search would match the prose (§20).
    import warehouse_reader as wr
    if not hasattr(wr, "collapse_key"):
        check("C2 the reader exposes collapse_key", False,
              "absent — r276 has not landed in this checkout")
    else:
        pk, keyed = wr.collapse_key(
            "plan_check", "QQQ", "2026-09-04",
            {"_rid": 1, "ts_epoch": 1788364800.0, "symbol": "QQQ",
             "strategy": "SweepCreditSpread", "direction": "short",
             "check_name": "age"})
        check("C2 a keyed table collapses on its PRIMARY KEY, not on _rid",
              keyed and "2026-09-04" not in str(pk) and 1 not in pk,
              str(pk))
        # 🔑 AND THE r266 KEY IS NOT DELETED — it is demoted to the fallback for
        # the one table with no identity of its own (`character_ledger`, whose
        # `id INTEGER PRIMARY KEY AUTOINCREMENT` IS the rowid). Two different
        # answers for two different situations, which is why this is a demotion
        # rather than a reversal.
        fb, keyed_fb = wr.collapse_key("character_ledger", "QQQ", "2026-09-04",
                                       {"_rid": 1, "ts_epoch": 1.0})
        check("C2b the partition-scoped _rid survives as the fallback",
              (not keyed_fb) and "2026-09-04" in str(fb), str(fb))

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
    print("GREEN — 6 checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
