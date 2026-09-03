#!/usr/bin/env python3
"""day_trader_pro/tests/test_level_quality.py — v1.0
v1.0  2026-09-03 — dtp r265. Selftest for screen_sweep_forensics panel 8.

⚠️ IT DRIVES THE REAL FUNCTIONS (C.23). `_level_join` and `_level_report` were
extracted from the panel precisely so this file calls them rather than a copy
— the r181 sizing checker stayed green for two days re-implementing the
arithmetic it was meant to pin.

⚠️ THE FIXTURES CARRY KNOWN, DIFFERENT ANSWERS PER BUCKET, so a join that
silently collapsed them, or a report that averaged them, moves a printed
number and the test names which.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FAILED = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        FAILED.append(name)


class _Cache:
    """Stands in for WarehouseCache.iter over fire_snapshot only."""
    def __init__(self, rows):
        self._rows = rows

    def iter(self, _sql):
        return iter(self._rows)


def _walk(above=(), below=()):
    f = lambda t: [{"price": p, "touches": n, "provenance": pv, "live": False}
                   for p, n, pv in t]
    return json.dumps({"levels": {"above": f(above), "below": f(below)},
                       "price": 100.0})


def main():
    import tests.screen_sweep_forensics as S

    # ⚠️ DEGRADE TO A NAMED FAILURE, NEVER A TRACEBACK (r206/r212). At a HEAD
    # without the extracted helpers every check would die on one
    # AttributeError, and "the checker crashed" and "the invariant is
    # violated" must not look alike.
    for _fn in ("_level_join", "_level_report", "_level_bucket"):
        if not hasattr(S, _fn):
            check(f"E0 screen_sweep_forensics exposes {_fn}", False,
                  "panel 8 helpers are not extracted — nothing to test")
            print()
            print(f"RED — {len(FAILED)} failed: helpers absent")
            return 1

    # ── J1 — the pool is matched, not merely the nearest rung ─────────────
    # The nearest level to spot is 101 (1 touch); the level SOLD is 105
    # (4 touches). A join that took "nearest to price" returns 1 and is wrong.
    cache = _Cache([{"trade_id": "t1",
                     "payload": _walk(above=((101.0, 1, "NY High"),
                                             (105.0, 4, "PDH")))}])
    recs = [{"tid": "t1", "pool": 105.0, "anchor": 106.0,
             "pen": -0.5, "acc": 0, "pnl": 12.0}]
    m, cov = S._level_join(cache, recs)
    check("J1 the join keys on pool_price, not proximity to spot",
          len(m) == 1 and m[0]["touches"] == 4,
          str([x["touches"] for x in m]))

    # ── J2 — anchor is the fallback when pool_price is null ───────────────
    recs2 = [{"tid": "t1", "pool": None, "anchor": 101.0,
              "pen": 1.0, "acc": 2, "pnl": -80.0}]
    m2, _ = S._level_join(cache, recs2)
    check("J2 a null pool_price falls back to the short anchor",
          len(m2) == 1 and m2[0]["touches"] == 1, str(m2))

    # ── J3 — a pool OUTSIDE the 3-rung walk is UNMEASURED, not one-touch ──
    # 🔴 The failure this exists to prevent: counting an absent level as a
    # weak one turns missing instrumentation into a finding about levels.
    recs3 = [{"tid": "t1", "pool": 140.0, "anchor": 141.0,
              "pen": 2.0, "acc": 3, "pnl": -90.0}]
    m3, cov3 = S._level_join(cache, recs3)
    check("J3 a pool outside the walk counts as UNMEASURED, never 1 touch",
          not m3 and cov3["no_rung"] == 1, f"{m3} {cov3}")

    # ── J4 — the three coverage causes stay distinct ──────────────────────
    cache4 = _Cache([{"trade_id": "b", "payload": json.dumps({"price": 100.0})}])
    m4, cov4 = S._level_join(
        cache4, [{"tid": "a", "pool": 105.0, "anchor": 106.0},
                 {"tid": "b", "pool": 105.0, "anchor": 106.0}])
    check("J4 no-payload and levels=null are counted separately",
          cov4["no_payload"] == 1 and cov4["no_walk"] == 1, str(cov4))

    # ── R1 — A DEGENERATE DISTRIBUTION SAYS SO ────────────────────────────
    # Every level one touch: the report must refuse to compare, not print a
    # flat table that reads as "the count does not matter".
    med = lambda v: sorted(v)[len(v) // 2] if v else float("nan")
    flat = [{"touches": 1, "pen": -1.0, "acc": 0, "pnl": 5.0, "prov": "PDH"},
            {"touches": 1, "pen": 2.0, "acc": 3, "pnl": -9.0, "prov": "PDL"}]
    txt = "\n".join(S._level_report(flat, med))
    check("R1 one bucket is reported as UNTESTABLE, not as a null result",
          "CANNOT test" in txt and "bucket" not in txt, txt[:70])

    # ── R2 — two buckets DO get compared, and `held` is pen <= 0 ──────────
    mixed = flat + [{"touches": 4, "pen": -3.0, "acc": 0, "pnl": 20.0,
                     "prov": "PDH"}]
    txt2 = "\n".join(S._level_report(mixed, med))
    check("R2 a real distribution produces the bucket table",
          "bucket" in txt2 and "3+ touches" in txt2)
    check("R2b `held` counts penetration <= 0 (never reached the strike)",
          "1/1" in txt2, [l for l in txt2.split("\n") if "3+" in l])

    # ── R3 — nothing joined is not a null result either ───────────────────
    check("R3 an empty join says UNTESTED rather than printing a table",
          "UNTESTED" in "\n".join(S._level_report([], med)))

    print()
    if FAILED:
        print(f"RED — {len(FAILED)} failed: {', '.join(FAILED)}")
        return 1
    print("GREEN — 8 checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
