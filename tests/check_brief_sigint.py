#!/usr/bin/env python3
"""
day_trader_pro/tests/check_brief_sigint.py  v1.0
v1.0  2026-09-10  dtp r337 / BRF.2 — the land gate for the SIGINT board.

The board's whole value is that it withholds calls, so its failure modes are
the ones that quietly widen what it endorses:

  G1  the floor is INCLUSIVE — a call exactly at 0.640 is actionable, and a
      hair under is not
  G2  a NULL conviction is its own bucket, never "below the floor" (that
      would assert something the brief never said)
  G3  NEUTRAL is never actionable at any conviction
  G4  a panel name absent from the brief is reported as NOT SCORED, distinct
      from NEUTRAL — the r332/r334 lesson: an absence must not read as a value
  G5  the post-hoc provenance is on every board (it is the reason this is
      advisory and not wiring)
  G6  an empty day says so instead of rendering an empty board
  G7  the floor constant matches the measurement it cites
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
sys.path.insert(0, REPO)
FAILS = []


def check(name, ok, detail=""):
    print("  {:<4} {}  {}".format(name, "PASS" if ok else "FAIL", detail))
    if not ok:
        FAILS.append(name)


def main():
    try:
        import brief_sigint as b
    except Exception as exc:                                    # noqa: BLE001
        print("  FAIL  tools/brief_sigint.py did not import: {}".format(exc))
        return 1

    f = b.CONVICTION_FLOOR
    rows = [("AT", "LONG", 1.0, f), ("UNDER", "SHORT", 1.0, f - 0.001),
            ("OVER", "SHORT", 1.0, f + 0.2)]
    act, below, _u, _n = b.triage(rows)
    names = [r[0] for r in act]
    check("G1", "AT" in names and "OVER" in names
          and [r[0] for r in below] == ["UNDER"],
          "actionable={} below={}".format(names, [r[0] for r in below]))

    act, below, unk, _n = b.triage([("X", "LONG", 1.0, None)])
    check("G2", [r[0] for r in unk] == ["X"] and not below and not act,
          "None -> unk={} below={}".format([r[0] for r in unk], len(below)))

    act, _b, _u, neut = b.triage([("N", "NEUT", 1.0, 0.99)])
    check("G3", not act and [r[0] for r in neut] == ["N"],
          "NEUT at conv 0.99 actionable={}".format(len(act)))

    b.PANEL = {"SPX", "AT"}
    txt = b.board("2026-09-10", [("AT", "LONG", 1.0, f)])
    check("G4", "NOT SCORED" in txt and "SPX" in txt
          and "not the same as NEUTRAL" in txt,
          "absent panel name reported")

    check("G5", "POST-HOC" in txt and "Advisory only" in txt,
          "provenance + advisory footer present")

    check("G6", "no brief for this date" in b.board("2026-09-10", []),
          "empty day named")

    src = open(os.path.join(REPO, "tools", "brief_sigint.py")).read()
    check("G7", "{:.3f}".format(f) in src and "r336" in b.FLOOR_SOURCE,
          "floor={:.3f} source={}".format(f, b.FLOOR_SOURCE))

    print("")
    if FAILS:
        print("FAILED: {}".format(", ".join(FAILS)))
        return 1
    print("ALL PASS (7)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
