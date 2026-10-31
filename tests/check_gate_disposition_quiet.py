#!/usr/bin/env python3
"""tests/check_gate_disposition_quiet.py — v1.0
A GATE-DISPOSITION DAY WITH NO GATE CHANGE IS SILENT, NOT A GAP.

v1.0  2026-10-31 — dtp r519 (warehouse_coverage v1.11). The gate_disposition writer is edge-triggered (a row on
      BLOCKED, CHANGED or CLEARED, never per tick). On 2026-10-30 SPX's loss cap halted entries at 10:00, no gate
      changed verdict, its derived_store held 0 rows for the day, and --streams printed
      `derived_gate_disposition MISS: SPX`. Operator: "Agree" (2026-10-31, R7: grade it as derived_level_event's
      "silent on a quiet tape").

  Q1  SPX absent from derived_gate_disposition while it pushed every other derived stream -> CONDITIONAL, no
      missing box, so it does not count among the stream-days that need an answer
  Q2  the policy row says why (edge-triggered, silent on a day with no gate change), and it is printed on the board
  Q3  CONTROL: the same pusher's EVERY streams still catch a stopped pusher - SPX absent from derived_plan_tick is
      a GAP naming SPX
  Q4  CONTROL: a box that pushed nothing at all is BOX_SILENT, not quietly excused by Q1

Drives the real check_streams against the FakeS3 from test_stream_coverage. Born red on 5d1ff71 at Q1, Q2.
Run:  python3 tests/check_gate_disposition_quiet.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
FAILED = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))
    if not ok:
        FAILED.append(name.split()[0])


def main():
    import warehouse_coverage as wc
    from test_stream_coverage import FakeS3

    DAY = "2026-10-30"                       # the Friday SPX capped at 10:00
    want = ["SPX", "QQQ"]

    def full(*syms):
        return {DAY: {s: 3 for s in syms}}
    bucket = {
        "derived_plan_tick":        full("SPX", "QQQ"),
        "derived_plan_check":       full("SPX", "QQQ"),
        "derived_strategy_note":    full("SPX", "QQQ"),
        "derived_level_ledger":     full("SPX", "QQQ"),
        "derived_gate_disposition": full("QQQ"),           # QQQ 21 rows, SPX none
    }
    d = wc.check_streams(FakeS3(bucket), DAY, want)
    by = {r["stream"]: r for r in d["rows"]}
    g = by.get("derived_gate_disposition", {})
    check("Q1 SPX with no gate change -> not a gap",
          g.get("verdict") == "CONDITIONAL" and not g.get("missing")
          and g.get("verdict") not in ("GAP", "UNDECLARED", "RESOLVED"),
          f"verdict={g.get('verdict')} missing={g.get('missing')}")

    note = (wc.STREAM_POLICY.get("derived_gate_disposition") or ("", "", ""))[2].lower()
    check("Q2 the row says why it may be silent",
          "edge-triggered" in note and "no gate change" in note, f"note={note!r}")

    b3 = dict(bucket, derived_plan_tick=full("QQQ"))
    r3 = {r["stream"]: r for r in wc.check_streams(FakeS3(b3), DAY, want)["rows"]}.get("derived_plan_tick", {})
    check("Q3 CONTROL: a stopped pusher is still a GAP on derived_plan_tick",
          r3.get("verdict") == "GAP" and "SPX" in (r3.get("missing") or []),
          f"verdict={r3.get('verdict')} missing={r3.get('missing')}")

    b4 = {k: {DAY: {s: n for s, n in v[DAY].items() if s != "SPX"}} for k, v in bucket.items()}
    d4 = wc.check_streams(FakeS3(b4), DAY, want)
    check("Q4 CONTROL: a box that pushed nothing is BOX_SILENT", "SPX" in d4.get("silent", []),
          f"silent={d4.get('silent')}")

    print("GREEN" if not FAILED else f"RED — {len(FAILED)} failed: {', '.join(FAILED)}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
