#!/usr/bin/env python3
"""day_trader_pro/tests/test_plan_dupe_probe.py — v1.2
v1.2  2026-09-05 — dtp r297. P5 pins that a restart wipe is reported but does
not set the exit code. All 31 overlaps in the first real run were
`WIPED_BY_RESTART` on one session, spanning five to six hours, because a wipe
stamps `closed_ts` on every live plan at one instant — five wiped plans make ten
pairs. ⚠️ REPORTED, NOT SUPPRESSED: r199's lesson is that hiding duplication is
what left RPT.5 open for weeks.

v1.1  2026-09-05 — dtp r296. RE-DERIVED ONTO OVERLAP, BECAUSE v1.0's KEY WAS
WRONG AND THESE CASES CERTIFIED IT.

🔴 v1.0 clustered on (symbol, strategy, trigger_price) and my fixtures shared a
price, so every case passed while the probe was measuring the wrong thing. The
first real run said 32 clusters "unexplained", including META
RunawayContinuation @ 594.10 with **27 rows — 27 separate completed trades**,
each with its own exit and P&L. A trigger price is a SESSION LEVEL, not an
event: re-entering it is what these strategies do all session.

🔑 THE CASES NOW BUILD FIXTURES THAT DIFFER IN THE THING THAT MATTERS — whether
two plans of one strategy were live at the same time — and one of them is a
long series of clean re-entries at ONE price, which v1.0 would have called a
defect and v1.1 must not.

v1.0  2026-09-05 — dtp r295 / RPT.5. THE PROBE MUST TELL THE TWO CASES APART.

🔴 THE WHOLE POINT OF RPT.5 IS THAT TWO ROWS FOR ONE TRIGGER HAVE TWO OPPOSITE
EXPLANATIONS, AND A DISPLAY COLLAPSE MAKES THEM LOOK IDENTICAL:
  · the earlier row was closed `superseded — never filled` — r212's designed
    path, the strategy re-armed after an entry was refused, and the ledger is
    CORRECT;
  · the earlier row is still LIVE, or terminal for some other reason — a
    genuine double-write, and the ledger is WRONG.
A probe that reported "2 duplicates" for both would be r199's collapse again
with more steps.

⚠️ SO THE CASES DRIVE THE REAL FIXTURE THROUGH THE REAL CACHE — a fake S3
client over `WarehouseCache`, the path every report takes — rather than calling
the verdict logic directly. Testing the classification in isolation would pass
against a probe that never reads the right column.
"""
import io
import json
import os
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
FAILED = []
ET = ZoneInfo("America/New_York")
DAY = "2026-09-04"


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        FAILED.append(name)


def _ts(hhmm, sec=0):
    return datetime.strptime(f"{DAY} {hhmm}", "%Y-%m-%d %H:%M").replace(
        tzinfo=ET).timestamp() + sec


class _S3:
    def __init__(self, rows):
        self.objs = {}
        for i, r in enumerate(rows):
            key = f"raw/derived_plan_ledger/dt={DAY}/sym={r['symbol']}/{i}.json"
            self.objs[key] = {"pushed_at_utc": "2026-09-04T21:00:00Z",
                              "record": [r]}

    def get_paginator(self, _op):
        outer = self

        class _P:
            def paginate(self, **kw):
                pre = kw.get("Prefix", "")
                yield {"Contents": [{"Key": k, "Size": 1}
                                    for k in sorted(outer.objs) if k.startswith(pre)]}
        return _P()

    def get_object(self, Bucket=None, Key=None):
        return {"Body": io.BytesIO(json.dumps(self.objs[Key]).encode())}


def _row(pid, sym, strat, state, ts, price, reason=None, closed=None):
    return {"plan_id": pid, "symbol": sym, "strategy": strat, "state": state,
            "created_ts": ts, "closed_ts": closed, "trigger_price": price,
            "direction": "long", "terminal_reason": reason}


def _run(rows):
    """Run the probe against a planted bucket. -> (rc, stdout)."""
    import textwrap
    prog = textwrap.dedent(f"""
        import sys, json
        sys.path.insert(0, {_root!r})
        sys.path.insert(0, {os.path.dirname(os.path.abspath(__file__))!r})
        import test_plan_dupe_probe as T
        import warehouse_reader as WR
        rows = json.loads({json.dumps(rows)!r})
        WR._client = lambda *a, **k: T._S3(rows)
        sys.argv = ["p", "--from", {DAY!r}]
        import tools.plan_dupe_probe as P
        sys.exit(P.main())
    """)
    r = subprocess.run([sys.executable, "-c", prog], capture_output=True,
                       text=True, cwd=_root)
    return r.returncode, r.stdout + r.stderr


def main():
    # ══ 🔴 P1 — CLEAN RE-ENTRY AT ONE LEVEL IS NOT A DEFECT ═══════════════
    # This is what v1.0 got wrong and what the first real run exposed: META
    # traded ONE Runaway level 27 times in 82 minutes, each with its own exit,
    # and the probe called it duplication. Every plan here closes before the
    # next opens — a trade log, not a finding.
    t = _ts("10:00")
    clean = []
    for i in range(8):
        clean.append(_row(f"c{i}", "META", "RunawayContinuation", "CLOSED",
                          t + i * 300, 594.10,
                          "orb_trail_stop pnl=12.0%", closed=t + i * 300 + 120))
    rc, out = _run(clean)
    check("P1 eight clean re-entries at ONE level are not reported at all",
          "no overlapping live plans" in out and rc == 0, f"rc={rc}")

    # ══ 🔴 P2 — TWO LIVE AT ONCE IS THE ACTUAL QUESTION ═══════════════════
    # A plan opened while an earlier one of the same strategy was still live.
    over = [
        _row("o1", "CRM", "RunawayContinuation", "TRIGGERED", t, 259.38,
             closed=t + 600),
        _row("o2", "CRM", "RunawayContinuation", "TRIGGERED", t + 60, 259.38,
             closed=t + 700),
    ]
    rc2, out2 = _run(over)
    check("P2 a plan opened while another was live is reported",
          "overlapping" in out2 and rc2 != 0, f"rc={rc2}")
    check("P2b ...with the overlap measured, not just named",
          "overlap 540" in out2 or "overlap" in out2,
          [l for l in out2.splitlines() if "overlap" in l][:1])

    # ══ 🔴 P3 — AN EARLIER PLAN THAT NEVER CLOSED IS THE r212 LEAK ════════
    # `close_unfilled` exists precisely so a fired-but-unfilled plan cannot
    # stay live all session. One still open when the next fires is that leak.
    leak = [
        _row("l1", "CRM", "RunawayContinuation", "TRIGGERED", t, 259.38),
        _row("l2", "CRM", "RunawayContinuation", "TRIGGERED", t + 900, 259.38,
             closed=t + 1000),
    ]
    rc3, out3 = _run(leak)
    check("P3 an earlier plan that NEVER closed is called out by name",
          "NEVER CLOSED" in out3 and rc3 != 0, f"rc={rc3}")

    # ⚠️ P4 — AND DIFFERENT STRATEGIES ARE NEVER COMPARED. Two strategies live
    # at once on one symbol is normal; the ledger separates them on purpose.
    cross = [
        _row("x1", "CRM", "ORBStrategy", "TRIGGERED", t, 259.38,
             closed=t + 900),
        _row("x2", "CRM", "RunawayContinuation", "TRIGGERED", t + 60, 259.38,
             closed=t + 800),
    ]
    rc4, out4 = _run(cross)
    check("P4 two DIFFERENT strategies live at once is not an overlap",
          "no overlapping live plans" in out4 and rc4 == 0, f"rc={rc4}")

    # ══ 🔴 P5 — A RESTART WIPE IS AN ARTIFACT, NOT A FINDING ═════════════
    t2 = _ts("10:16")
    wipe_close = _ts("16:08")
    wiped = [_row(f"w{i}", "QQQ", "RunawayContinuation", "CANCELLED",
                  t2 + i * 420, 708.43, "WIPED_BY_RESTART", closed=wipe_close)
             for i in range(5)]
    rc5, out5 = _run(wiped)
    check("P5 wipe-closed pairs do not set the exit code", rc5 == 0, f"rc={rc5}")
    # ⚠️ AND THEY STILL PRINT. Hiding duplication is what left RPT.5 open.
    check("P5b ...but are reported, with the count and the boxes",
          "WIPED_BY_RESTART" in out5 and "pair(s)" in out5,
          [l for l in out5.splitlines() if "WIPED" in l][:1])

    print()
    if FAILED:
        print(f"RED — {len(FAILED)} failed: {', '.join(FAILED)}")
        return 1
    print("GREEN — 7 checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
