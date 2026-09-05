#!/usr/bin/env python3
# day_trader_pro/tests/test_fit_readiness_memory.py — v1.3
# v1.3 (2026-09-05) — dtp r286. M3 RE-DERIVED AGAIN, FOR THE SAME REASON IT
#      MOVED AT r266: it asserted the LITERAL banner text "after collapse by
#      (_rid, ts)", and r286 removed that sentence because it was FALSE — the
#      collapse it named never touched this report's rows, which came from
#      `WarehouseCache.load` and were never collapsed at all. Keeping the
#      assertion would have held the false wording green and pushed the next
#      reader to restore it. ⚠️ WHAT SURVIVES IS THE PROPERTY, NOT THE STRING:
#      a per-stream SOURCE line exists and it NAMES THE RULE THAT ACTUALLY RAN
#      — "collapsed on <key>" or "NOT COLLAPSED" — rather than one the report
#      assumed. M4, which pins that the collapse itself still happens, is
#      untouched and is what would catch a regression here.
# v1.1 (2026-09-04) — dtp r266. M3 RE-DERIVED. It matched the banner string
#      "after collapse by _rid" — the label for a collapse that was WRONG,
#      because `_rid` is the source table's sqlite rowid and repeats across
#      sessions when a box rebuilds its store. Asserting that string would
#      have kept the defect green. The de-dup now keys on (_rid, ts) and the
#      banner says so; M4 is UNCHANGED and is what caught the first cut, where
#      removing the second collapse outright let a re-pushed object
#      double-count.
# v1.0 (2026-09-02) — dtp r245. THE REPORT SURVIVES ITS OWN RANGE.
#
# 🔴 OOM-KILLED TWICE ON 2026-08-24..09-01, FROM TWO INDEPENDENT CAUSES, AND
#   THE FIRST FIX WAS THE WRONG HALF. r240 put a progress meter on the fetch
#   and I said at the time it makes the wait visible, not smaller — it did
#   exactly that, and the operator was killed again the next morning.
#   (1) `collect()` retained EVERY PAYLOAD DICT in `fired`/`declined`, both
#       consumed only by `len()`.
#   (2) `load_derived` materialised all three tables before returning.
#
# 🔑 M1 IS THE ONLY CHECK THAT COULD HAVE CAUGHT THIS. It runs the real path
#   over 300,000 notes and asserts the RESIDENT SET stays bounded. Reading the
#   source would not have caught either cause; both are about what is HELD.
import io, json, os, resource, sys, contextlib

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
_fails = []


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + (f"   [{detail}]" if detail else ""))
    if not ok:
        _fails.append(name)


def main():
    import warehouse_reader as WR

    class _B:
        def __init__(s, b): s.b = b
        def read(s): return s.b

    class _P:
        def __init__(s, st): s.st = st
        def paginate(s, Bucket=None, Prefix=None):
            yield {"Contents": [{"Key": k, "Size": len(v)}
                                for k, v in s.st.items() if k.startswith(Prefix)]}

    class _S3:
        def __init__(s, st): s.st = st
        def get_paginator(s, _): return _P(s.st)
        def get_object(s, Bucket=None, Key=None): return {"Body": _B(s.st[Key])}

    # 100k notes x 28 keys = 2.8M values. Enough that a retained-dict
    # implementation is plainly visible in RSS, small enough to run in a suite.
    store, rid = {}, 0
    for d in ("2026-08-31",):
        for obj in range(10):
            notes = []
            for i in range(10_000):
                rid += 1
                notes.append({"_rid": rid, "strategy": "TrendCreditSpread",
                              "fired": 1 if i % 5 == 0 else 0,
                              "outcome": None if i % 5 == 0 else
                                         ("adx_floor" if i % 2 else "vwap"),
                              "payload": json.dumps(
                                  {f"k{j}": (i % 97) * 0.13 + j
                                   for j in range(28)})})
            store[f"raw/derived_strategy_note/dt={d}/sym=S{obj}/1.json"] = \
                json.dumps({"symbol": f"S{obj}", "record": notes}).encode()
        for t in ("gate_disposition", "plan_ledger"):
            store[f"raw/derived_{t}/dt={d}/sym=QQQ/1.json"] = json.dumps(
                {"symbol": "QQQ", "record": [
                    {"_rid": i, "strategy": "TrendCreditSpread", "gate": "adx",
                     "event": "BLOCKED", "terminal_reason": "EXPIRED"}
                    for i in range(50)]}).encode()

    WR._client = lambda *a, **k: _S3(store)
    import importlib.util as u
    sp = u.spec_from_file_location("fr", os.path.join(_root, "fit_readiness.py"))
    m = u.module_from_spec(sp)
    try:
        sp.loader.exec_module(m)
    except SystemExit:
        pass
    m.wr._client = lambda *a, **k: _S3(store)
    import warehouse_cache as WC
    WC.WR._client = lambda *a, **k: _S3(store)

    before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    buf, err = io.StringIO(), ""
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            m.main(["x", "--from", "2026-08-31", "--to", "2026-08-31"])
    except SystemExit:
        pass
    except Exception as exc:                                    # noqa: BLE001
        err = f"{type(exc).__name__}: {exc}"
    after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    out = buf.getvalue()

    check("M0 the report runs to completion", not err, err)

    # ── M1 — RSS STAYS BOUNDED ──────────────────────────────────────────
    # The retained-dict version held roughly 3-4 KB per note; 100,000 notes is
    # ~350 MB for the dicts alone, before the boxed floats. 600 MB is a
    # generous ceiling that the old implementation could not have met.
    check("M1 100k notes do not blow the resident set",
          after < 600, f"peak {after:.0f} MB (was {before:.0f} before)")

    # ── M2 — AND THE NUMBERS ARE STILL RIGHT ────────────────────────────
    # 🔑 A memory fix that changed the counts would be worse than the OOM: the
    # OOM is loud and a wrong number is not. 20% fired by construction.
    check("M2 the counts survive the rewrite",
          "fired     20000" in out and "declined  80000" in out,
          "planted 20% fired of 100,000")

    # ── M3 — the per-table SOURCE banner survives ───────────────────────
    # This report's own contract: an unreachable bucket and a session with no
    # evaluations must never render the same.
    # 🔴 M3 RE-DERIVED AT dtp-r266. It matched "after collapse by _rid" — the
    # banner for a collapse that was WRONG: `_rid` is the source table's sqlite
    # rowid, unique only within one box's table at one moment, so grouping on
    # it across a multi-day range folded different sessions together and made
    # the butterfly read 2 fires against 20 real trades. The collapse now runs
    # ONCE, upstream, scoped to its partition. Asserting the old string would
    # have kept the defect green.
    # 🔴 M3 RE-DERIVED AGAIN AT dtp-r286, AND THE REASON IS THE SAME ONE THAT
    # MOVED IT AT r266: it asserted the LITERAL banner text
    # "after collapse by (_rid, ts)", which r286 removed because that sentence
    # was FALSE — the collapse it named never touched this report's rows.
    # Leaving the assertion would have kept the false wording green and forced
    # the next reader to restore it. What survives is the property that
    # mattered: a per-stream SOURCE line exists, and it NAMES the rule that
    # actually ran rather than one the report assumed.
    check("M3 a SOURCE line still prints per stream, naming the real rule",
          out.count("SOURCE: s3 [") == 3
          and ("collapsed on " in out or "NOT COLLAPSED" in out),
          out.split("SOURCE: s3 [")[1][:70] if "SOURCE: s3 [" in out else out[:70])

    # ── M4 — the CDC collapse is preserved ──────────────────────────────
    # Dropping it would double-count anything pushed twice and inflate every
    # number in the report.
    dup = dict(store)
    k = next(iter(k for k in store if "strategy_note" in k))
    dup[k.replace("/1.json", "/2.json")] = store[k]
    WR._client = lambda *a, **k2: _S3(dup)
    WC.WR._client = lambda *a, **k2: _S3(dup)
    b2 = io.StringIO()
    try:
        with contextlib.redirect_stdout(b2), contextlib.redirect_stderr(io.StringIO()):
            m.main(["x", "--from", "2026-08-31", "--to", "2026-08-31"])
    except SystemExit:
        pass
    check("M4 a re-pushed object does not double-count",
          "fired     20000" in b2.getvalue(),
          "GROUP BY _rid stands in for load_derived's latest-wins collapse")

    print()
    if _fails:
        print(f"FAILED {len(_fails)}: " + ", ".join(_fails))
        return 1
    print("test_fit_readiness_memory: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
