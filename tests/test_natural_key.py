#!/usr/bin/env python3
"""day_trader_pro/tests/test_natural_key.py — v1.0
v1.0  2026-09-05 — dtp r276. THE CDC COLLAPSE KEYS ON THE TABLE'S OWN PRIMARY
KEY, AND THE KEY IS READ FROM otv4's SCHEMAS RATHER THAN DECLARED HERE.

🔴 WHAT THIS PINS. `_rid` is the source table's sqlite `rowid`
(otv4 `warehouse/s3_push.py:945`, `SELECT rowid AS _rid, *`). r266 scoped it to
the `dt=` partition because rowids collide across sessions — a real UNDER-count,
fixed. But `push_derived` files every CHANGED row under the PUSH day, so one CDC
row touched on two days lands in TWO partitions, and a partition-scoped key
keeps BOTH: an OVER-count, opened by the same edit that closed the under-count.
N1/N1b drive both errors on one fixture, which is what makes this a check and
not a restatement.

⚠️ IT EXECUTES `load_derived` AND `collapse_key` (WA §21). A test that read the
source text would pass against a file whose comment merely mentions the key —
and this repo has tripped §20 four times in one session doing exactly that.

⚠️ THE KEYS ARE DIFFED AGAINST THE REAL SCHEMAS. N4 parses otv4's own
`CREATE TABLE` statements and requires this module's `DERIVED_NATURAL_KEY` to
match them. A key table maintained by hand is a second definition of identity
(WA §35); if otv4 alters a PK, this goes red rather than silently collapsing on
a key the box no longer enforces. If the otv4 checkout cannot be found the check
FAILS LOUDLY rather than skipping — a schema check that skips reports success,
which is worth less than none (dtp r250).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FAILED = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        FAILED.append(name)


def _otv4_root():
    """The otv4 checkout, by marker file rather than by a guessed path (WA §3)."""
    cand = [os.environ.get("OTV4_ROOT", ""),
            os.path.expanduser("~/options-trader-v4"),
            os.path.expanduser("~/options_trader_v4"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))), "options_trader_v4")]
    for c in cand:
        if c and os.path.exists(os.path.join(c, "strategy", "plan.py")):
            return c
    return ""


def _pks(root):
    """Every `CREATE TABLE <t> (...) PRIMARY KEY ...` otv4 declares -> {t: cols}."""
    out = {}
    for sub, fn in (("data", "derived_store.py"), ("derived", "notes.py"),
                    ("derived", "plan_ledger.py"), ("strategy", "plan.py"),
                    ("analysis", "gate_report.py"),
                    ("derived", "counterfactual.py"),
                    ("derived", "character_engine.py")):
        p = os.path.join(root, sub, fn)
        if not os.path.exists(p):
            continue
        src = open(p, encoding="utf-8").read()
        for m in re.finditer(
                r"CREATE TABLE IF NOT EXISTS (\w+)\s*\((.*?)\)\s*;?\"\"\"",
                src, re.S):
            tbl, body = m.group(1), m.group(2)
            comp = re.search(r"PRIMARY KEY\s*\(([^)]*)\)", body)
            if comp:
                out[tbl] = tuple(c.strip() for c in comp.group(1).split(","))
                continue
            single = re.search(r"^\s*(\w+)\s+[A-Z]+[^,\n]*PRIMARY KEY",
                               body, re.M)
            if single:
                out[tbl] = (single.group(1),)
    return out


def main():
    # ⚠️ A CAPABILITY PROBE, not a bare import. A checker that dies on a
    # traceback is a red for a reason unrelated to what it checks, which is how
    # the operator learns to skim red runs (the CV.1 lesson). "The checker could
    # not run" and "the invariant is violated" must not look alike.
    try:
        import warehouse_reader as wr
    except Exception as exc:                                    # noqa: BLE001
        check("N0 warehouse_reader is importable", False,
              f"{type(exc).__name__}: {exc}")
        print()
        print("RED — 1 failed: N0 (the checker could not run; this is NOT a "
              "verdict on the collapse key)")
        return 1
    # ⚠️ A MISSING `collapse_key` DOES NOT SHORT-CIRCUIT THE RUN. N5 drives
    # `load_derived`, which exists at every revision, so against the old code it
    # goes red on the BEHAVIOUR — "one row pushed on two days loaded as 2" — and
    # not merely on the absence of a helper. A born-red that only says "the fix
    # is not installed" proves the fix was installed, never that it works.
    _have_ck = hasattr(wr, "collapse_key")
    check("N0 warehouse_reader exposes collapse_key", _have_ck,
          "" if _have_ck else "absent — r276 has not landed in this checkout")

    def ck(table, sym, part, row):
        if not _have_ck:
            return ("UNKEYED", id(row)), False
        return wr.collapse_key(table, sym, part, row)

    # ══ N1 — THE TWO ERRORS, ON ONE FIXTURE ═══════════════════════════════
    # ONE plan_check row, pushed twice: created Wednesday, re-pushed Friday
    # after the tick_id migration touched it. Same primary key, two partitions,
    # and — because the box's store was rebuilt in between — two rowids.
    row_a = {"_rid": 1, "ts_epoch": 1788364800.0,   # 2026-09-02 12:00 ET
             "symbol": "QQQ",
             "strategy": "SweepCreditSpread", "direction": "short",
             "check_name": "age", "verdict": "FAIL"}
    row_b = dict(row_a, _rid=7, verdict="PASS")

    old_rid_only = {("QQQ", r["_rid"]) for r in (row_a, row_b)}
    r266_scoped = {("QQQ", d, r["_rid"])
                   for d, r in (("2026-09-02", row_a), ("2026-09-04", row_b))}
    natural = {ck("plan_check", "QQQ", d, r)[0]
               for d, r in (("2026-09-02", row_a), ("2026-09-04", row_b))}

    check("N1 the pre-r266 key (sym, _rid) splits one row into two "
          "(it collided elsewhere; here it over-counts)",
          len(old_rid_only) == 2, str(sorted(map(str, old_rid_only))))
    check("N1b the r266 key (sym, dt, _rid) ALSO keeps both — the over-count "
          "the partition scope opened",
          len(r266_scoped) == 2)
    check("N1c the natural key resolves both copies to ONE row",
          len(natural) == 1, str(natural))

    # ══ N2 — AND IT STILL SEPARATES TWO GENUINELY DIFFERENT ROWS ══════════
    # The collapse must not become a merge. Two checks on the same plan at the
    # same instant are two rows, and only `check_name` tells them apart.
    other = dict(row_a, check_name="wing_r_best")
    two = {ck("plan_check", "QQQ", "2026-09-02", r)[0]
           for r in (row_a, other)}
    check("N2 two rungs on one tick stay two rows", len(two) == 2)
    # ... and two boxes are two stores, whatever the row says.
    boxes = {ck("plan_check", b, "2026-09-02", row_a)[0]
             for b in ("QQQ", "SPX")}
    check("N2b the writing box rides in the key", len(boxes) == 2)

    # ══ N3 — ABSENT IS `is None`, NEVER FALSINESS ═════════════════════════
    # 🔴 C.45. `direction` is NOT NULL DEFAULT '' and `ts_epoch` can be 0.0.
    # `x or FALLBACK` would rewrite both into the unkeyed path, which silently
    # reinstates the r266 key for the rows most likely to be edge cases.
    falsy = dict(row_a, direction="", ts_epoch=0.0)
    _k, keyed = ck("plan_check", "QQQ", "2026-09-02", falsy)
    check("N3 an empty direction and a 0.0 ts_epoch are VALUES, not absences",
          keyed, "fell back to _rid" if not keyed else "")
    missing = {k: v for k, v in row_a.items() if k != "check_name"}
    _k2, keyed2 = ck("plan_check", "QQQ", "2026-09-02", missing)
    check("N3b a genuinely missing component falls back and says so",
          not keyed2)
    # character_ledger has no key independent of _rid and must not pretend to.
    _k3, keyed3 = ck("character_ledger", "QQQ", "2026-09-02",
                                  {"_rid": 4, "ts_epoch": 1.0})
    check("N3c character_ledger keeps the partition-scoped _rid key",
          not keyed3)

    # ══ N4 — THE KEYS MATCH otv4's OWN SCHEMAS ════════════════════════════
    root = _otv4_root()
    check("N4 the otv4 checkout was found (set OTV4_ROOT if it is elsewhere)",
          bool(root), root or "not found")
    if root:
        real = _pks(root)
        nat = getattr(wr, "DERIVED_NATURAL_KEY", {})
        # ⚠️ AND IT REFUSES TO PASS ON NOTHING (r246). An empty or shrunken map
        # would make the diff below vacuously clean while collapsing every
        # table on `_rid`, which is the cheerful green this repo keeps finding.
        check("N4a the map covers every derived table that declares a PK",
              len(nat) == 8, f"{len(nat)} entries")
        bad = []
        for tbl, cols in nat.items():
            if tbl not in real:
                bad.append(f"{tbl}: no CREATE TABLE found")
            elif tuple(real[tbl]) != tuple(cols):
                bad.append(f"{tbl}: schema {real[tbl]} != map {cols}")
        check("N4b every declared natural key matches the box's own PRIMARY KEY",
              not bad, "; ".join(bad))
        # And the one deliberate omission is deliberate: character_ledger's PK
        # IS its rowid, so listing it would look like coverage and mean nothing.
        check("N4c character_ledger is absent from the map on purpose",
              nat and "character_ledger" not in nat
              and real.get("character_ledger") == ("id",),
              str(real.get("character_ledger")))

    # ══ N5 — DRIVEN THROUGH THE REAL load_derived ═════════════════════════
    # WA §21: a test that reads source text proves nothing about runtime.
    def fake_read_prefix(_s3, datatype, date):
        if datatype != "derived_plan_check":
            return []
        if date == "2026-09-02":
            return [("QQQ", {"symbol": "QQQ", "pushed_at_utc": "2026-09-02T20:00:00Z",
                             "record": [row_a]})]
        if date == "2026-09-04":
            return [("QQQ", {"symbol": "QQQ", "pushed_at_utc": "2026-09-04T20:00:00Z",
                             "record": [row_b]})]
        return []

    saved = wr.read_prefix
    wr.read_prefix = fake_read_prefix
    try:
        rows, meta = wr.load_derived("plan_check", ["2026-09-02"],
                                     s3=object(), forward=3)
        check("N5 one row pushed on two days loads as ONE row",
              len(rows) == 1, f"got {len(rows)}")
        # 🔑 AND THE LATEST STATE IS THE ONE THAT SURVIVES — the whole point of
        # a CDC collapse. Keeping the older push would be a different wrong
        # answer, not a right one.
        check("N5b the latest pushed_at_utc wins",
              rows and rows[0].get("verdict") == "PASS",
              rows[0].get("verdict") if rows else "no rows")
        check("N5c the banner names the collapse that ran",
              "check_name" in getattr(meta, "collapsed_by", ""), meta.banner())
        check("N5d nothing fell back on a fully-keyed table",
              getattr(meta, "unkeyed", -1) == 0,
              str(getattr(meta, "unkeyed", "absent")))
    finally:
        wr.read_prefix = saved

    print()
    if FAILED:
        print(f"RED — {len(FAILED)} failed: {', '.join(FAILED)}")
        return 1
    print("GREEN — 17 checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
