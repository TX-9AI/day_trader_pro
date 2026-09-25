#!/usr/bin/env python3
"""
tests/check_close_scope.py  v1.0
v1.0  2026-09-25  r427 / OPS.51 — THE CLOSE IS NEVER NARROWER THAN THE WAKE.

  🔑 C2 AND C3 ARE THE SHIP-BLOCKERS, AND BOTH GUARD THE SAME ASYMMETRY. For a
  SHUTDOWN path the two errors are not equal: including a box that is already
  down costs one no-op API call; OMITTING one leaves it running, billing and
  holding positions until a human notices. So scope may over-cover freely and
  may never under-cover — C2 pins that a UNIVERSE box missing from discovery
  stays in scope, and C3 pins that a discovery FAILURE falls back to UNIVERSE
  rather than to nothing.

  🔴 C1 IS THE DEFECT ITSELF. r423 moved the wake to tag discovery and left the
  close on config.UNIVERSE — the same divergence r423 fixed inside eod_report
  and missed here. A tagged box absent from UNIVERSE was woken at 09:15 and
  never stopped, and the close reported success because it never knew the box
  existed. That is the plausible-silence class this repo keeps paying for.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_fails = []


def ck(tag, ok, msg=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {tag}  {msg}")
    if not ok:
        _fails.append(tag)


def main():
    try:
        import config
        import fleet
        import instance_registry
    except Exception as exc:                                   # noqa: BLE001
        for t in ("C1", "C2", "C3", "C4", "C5"):
            ck(t, False, f"import failed ({exc})")
        print(f"\nRED — {len(_fails)} check(s) failed: {' '.join(_fails)}")
        return 1

    if not hasattr(fleet, "default_scope"):
        for t in ("C1", "C2", "C3", "C4"):
            ck(t, False, "fleet.default_scope() is absent — the close still "
                         "scopes by config.UNIVERSE alone")
    else:
        real_disc, real_uni = instance_registry.discover_fleet, config.UNIVERSE
        try:
            # ── C1 — a TAGGED box absent from UNIVERSE is still closed ──────
            config.UNIVERSE = ["SPX", "QQQ"]
            instance_registry.discover_fleet = lambda *a, **k: {
                "SPX": {}, "QQQ": {}, "GHOST": {}}
            sc = fleet.default_scope()
            ck("C1", "GHOST" in sc,
               f"a tagged box missing from UNIVERSE is IN SCOPE — got {sorted(sc)}. "
               f"Without this it wakes at 09:15 and is never stopped")

            # ── C2 — SHIP-BLOCKER: discovery must never SHRINK the close ────
            config.UNIVERSE = ["SPX", "QQQ", "LISTED"]
            instance_registry.discover_fleet = lambda *a, **k: {"SPX": {}}
            sc = fleet.default_scope()
            ck("C2", {"SPX", "QQQ", "LISTED"} <= set(sc),
               f"a UNIVERSE box missing from discovery STAYS in scope — got "
               f"{sorted(sc)}. Over-covering costs a no-op; under-covering "
               f"strands a running box")

            # ── C3 — SHIP-BLOCKER: a discovery FAILURE falls back, not empty ─
            config.UNIVERSE = ["SPX", "QQQ"]
            def _boom(*a, **k):
                raise RuntimeError("EC2 unavailable")
            instance_registry.discover_fleet = _boom
            sc = fleet.default_scope()
            ck("C3", sorted(sc) == ["QQQ", "SPX"],
               f"discovery raising falls back to UNIVERSE, never to nothing — "
               f"got {sorted(sc)}")

            # and the empty-but-no-exception case
            instance_registry.discover_fleet = lambda *a, **k: {}
            sc2 = fleet.default_scope()
            ck("C4", sorted(sc2) == ["QQQ", "SPX"],
               f"discovery returning EMPTY also falls back to UNIVERSE — got "
               f"{sorted(sc2)} (a close that scopes to nothing stops nothing)")
        finally:
            instance_registry.discover_fleet, config.UNIVERSE = real_disc, real_uni

    # ── C5 — DECLARED CONTROL: an explicit scope still wins ────────────────
    src = open(os.path.join(ROOT, "fleet.py"), encoding="utf-8").read()
    ck("C5", "symbols = only or default_scope()" in src,
       "an explicit --only still overrides the default scope (the operator can "
       "always narrow the close by hand)")

    if _fails:
        print(f"\nRED — {len(_fails)} check(s) failed: {' '.join(_fails)}")
        return 1
    print("\nGREEN — the close covers everything either source knows, and never "
          "scopes to nothing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
