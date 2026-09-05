#!/usr/bin/env python3
"""day_trader_pro/tests/test_cache_collapse.py — v1.0
v1.0  2026-09-05 — dtp r286 / S3.11. THE CDC COLLAPSE, DRIVEN THROUGH THE PATH
REPORTS ACTUALLY TAKE.

🔴 WHY THIS FILE HAD TO EXIST SEPARATELY FROM `test_natural_key`. That checker
proves `warehouse_reader.load_derived` collapses correctly, and it is right —
but `load_derived` has NO PRODUCTION CALLERS. Every report reaches the warehouse
through `WarehouseCache.load`, which collapsed nothing. A correct fix on a road
nobody drives (r230's shape), and the existing checker stayed green throughout
because it calls the dead function directly. **A test that exercises the wrong
entrypoint cannot fail for the right reason.**

⚠️ SO EVERY CASE HERE GOES THROUGH `cache.load` AND COUNTS ROWS IN THE SQLITE
TABLE — never through the reader, and never against a return value that a
future refactor could satisfy without touching the data.
"""
import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
FAILED = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        FAILED.append(name)


class _S3:
    """Minimal paginator + getter over an in-memory {key: envelope} store."""

    def __init__(self, store):
        self.store = store

    def get_paginator(self, _op):
        outer = self

        class _P:
            def paginate(self, **kw):
                pre = kw.get("Prefix", "")
                yield {"Contents": [{"Key": k, "Size": 1}
                                    for k in sorted(outer.store) if k.startswith(pre)]}
        return _P()

    def get_object(self, Bucket=None, Key=None):
        import io
        import json
        body = json.dumps(self.store[Key]).encode()
        return {"Body": io.BytesIO(body)}


def _env(rows, pushed):
    return {"pushed_at_utc": pushed, "record": rows}


def main():
    import warehouse_cache as WC
    import warehouse_reader as WR

    if not hasattr(WC, "_collapsible"):
        check("W0 warehouse_cache exposes the r286 collapse gate", False,
              "absent — dtp r286 has not landed in this checkout")
        print("\nRED — 1 failed: W0")
        return 1
    check("W0 warehouse_cache exposes the r286 collapse gate", True)

    DAY = "2026-09-02"
    base = {"ts_epoch": 1000.0, "strategy": "orb", "direction": "long",
            "check_name": "vwap", "verdict": "PASS", "value": 1.0, "_rid": 7}
    # The SAME logical row pushed three times — CDC's normal behaviour, and the
    # thing that inflated every count that reached a report.
    store = {
        f"raw/derived_plan_check/dt={DAY}/sym=QQQ/1.json": _env([base], "2026-09-02T20:00:00Z"),
        f"raw/derived_plan_check/dt={DAY}/sym=QQQ/2.json": _env([dict(base, verdict="FAIL")], "2026-09-02T20:05:00Z"),
        f"raw/derived_plan_check/dt={DAY}/sym=QQQ/3.json": _env([dict(base, verdict="BLOCK")], "2026-09-02T20:02:00Z"),
        # A genuinely different row: same everything but one key column.
        f"raw/derived_plan_check/dt={DAY}/sym=QQQ/4.json": _env(
            [dict(base, check_name="adx")], "2026-09-02T20:00:00Z"),
    }
    WR._client = lambda *a, **k: _S3(store)
    NEED = ["_rid", "ts_epoch", "strategy", "check_name", "verdict", "value",
            "direction"]

    c = WC.WarehouseCache("t_collapse")
    ret = c.load("plan_check", [DAY], NEED, syms=["QQQ"])
    n = c.query('SELECT COUNT(*) n FROM "plan_check"')[0]["n"]
    # 🔴 W1a — THE RETURN VALUE IS WHAT THE TABLE HOLDS, NOT WHAT WAS ATTEMPTED.
    # A first cut of r286 returned the INSERT count, so a caller printed "4
    # row(s), collapsed on ..." for two logical rows — the same false sentence
    # this revision exists to remove, one layer down. This checker's own detail
    # line is what exposed it.
    check("W1a load() returns the post-collapse row count, not the inserts",
          ret == 2, f"returned {ret}, table holds {n}")
    # 🔴 W1 — FOUR OBJECTS, TWO LOGICAL ROWS. Before r286 this table held four.
    check("W1 CDC duplicates collapse on the natural key, in the cache",
          n == 2, f"{n} row(s) from 4 objects")
    # ⚠️ AND A ROW THAT DIFFERS IN ONE KEY COLUMN SURVIVES. A collapse that
    # merged these would be losing data, not de-duplicating it.
    names = sorted(r["check_name"] for r in
                   c.query('SELECT check_name FROM "plan_check"'))
    check("W1b ...and a row differing in one key column is NOT merged",
          names == ["adx", "vwap"], str(names))

    check("W2 the banner names the rule that ran",
          "collapsed on" in c.collapse_note("plan_check"),
          c.collapse_note("plan_check"))

    # ══ 🔴 W3 — A PARTIAL KEY IS REFUSED, NOT APPLIED ═════════════════════
    # `load()` keeps only the columns a caller asks for. Collapsing on a SUBSET
    # of a primary key folds genuinely distinct rows together — silently, and
    # in the direction that makes a report look tidier. `plan_ledger`'s key IS
    # `plan_id`, and fit_readiness did not request it until this revision.
    check("W3 a projection missing part of the key does NOT collapse",
          WC._collapsible("plan_ledger",
                          ["_rid", "created_ts", "strategy"]) == ())
    check("W3b ...and the same table WITH its key does",
          WC._collapsible("plan_ledger", ["plan_id", "_rid"]) == ("plan_id",))

    store2 = {
        f"raw/derived_plan_ledger/dt={DAY}/sym=QQQ/1.json": _env(
            [{"plan_id": "p1", "_rid": 1, "created_ts": 1.0}], "2026-09-02T20:00:00Z"),
        f"raw/derived_plan_ledger/dt={DAY}/sym=QQQ/2.json": _env(
            [{"plan_id": "p2", "_rid": 1, "created_ts": 1.0}], "2026-09-02T20:01:00Z"),
    }
    WR._client = lambda *a, **k: _S3(store2)
    c2 = WC.WarehouseCache("t_partial")
    c2.load("plan_ledger", [DAY], ["_rid", "created_ts"], syms=["QQQ"])
    n2 = c2.query('SELECT COUNT(*) n FROM "plan_ledger"')[0]["n"]
    # 🔑 TWO DISTINCT PLANS, IDENTICAL IN EVERY PROJECTED COLUMN. Collapsing on
    # the available subset would have kept ONE and lost a plan. Uncollapsed is
    # the correct answer here, and the note has to admit it.
    check("W3c two distinct plans indistinguishable in the projection are "
          "BOTH kept", n2 == 2, f"{n2}")
    check("W3d ...and the banner says NOT COLLAPSED rather than implying a rule",
          "NOT COLLAPSED" in c2.collapse_note("plan_ledger"),
          c2.collapse_note("plan_ledger"))

    # ══ W4 — AND THE REPORT ASKS RATHER THAN ASSERTS ══════════════════════
    # fit_readiness printed "N after collapse by (_rid, ts)" while its rows
    # came from this class and were never collapsed: the number was real and
    # the sentence was false. The sentence is the worse half.
    fr = open(os.path.join(_root, "fit_readiness.py"), encoding="utf-8").read()
    check("W4 fit_readiness no longer claims a collapse it did not get",
          "after collapse by (_rid, ts)" not in fr)
    check("W4b ...and asks the cache which rule ran",
          "collapse_note(" in fr)
    # ⚠️ AND IT REQUESTS THE KEY IT NEEDS. Without `plan_id` the table above
    # cannot be collapsed at all.
    check("W4c ...and plan_ledger's projection carries its primary key",
          '"plan_ledger":      ["plan_id"' in fr)

    print()
    if FAILED:
        print(f"RED — {len(FAILED)} failed: {', '.join(FAILED)}")
        return 1
    print("GREEN — 12 checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
