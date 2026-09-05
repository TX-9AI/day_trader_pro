#!/usr/bin/env python3
"""day_trader_pro/tests/test_plan_dupe_probe.py — v1.0
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


def _row(pid, sym, strat, state, ts, price, reason=None):
    return {"plan_id": pid, "symbol": sym, "strategy": strat, "state": state,
            "created_ts": ts, "trigger_price": price, "direction": "long",
            "terminal_reason": reason}


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
    # ══ 🔴 P1 — THE DESIGNED PATH IS NOT A FINDING ════════════════════════
    # r212 closes the previous unfilled plan before opening the next. Two rows
    # here are two genuine intents, and the probe must NOT call that a defect —
    # a study that flags its own system's correct behaviour gets ignored.
    ok_rows = [
        _row("a1", "CRM", "RunawayContinuation", "CLOSED", _ts("10:15"),
             259.38, "superseded — never filled"),
        _row("a2", "CRM", "RunawayContinuation", "TRIGGERED", _ts("10:15", 45),
             259.38),
    ]
    rc, out = _run(ok_rows)
    check("P1 a supersession cluster is explained, not flagged",
          "supersession" in out and rc == 0, f"rc={rc}")
    check("P1b ...and it still PRINTS, so the duplication stays visible",
          "259.38" in out and "2 rows" in out)

    # ══ 🔴 P2 — A GENUINE DOUBLE-WRITE IS CALLED ONE ══════════════════════
    # Earlier row still LIVE means nothing closed it: two intents exist at once
    # for one strategy at one trigger, which is what RPT.5 suspected.
    bad_rows = [
        _row("b1", "CRM", "RunawayContinuation", "TRIGGERED", _ts("10:15"),
             259.38),
        _row("b2", "CRM", "RunawayContinuation", "TRIGGERED", _ts("10:15", 30),
             259.38),
    ]
    rc2, out2 = _run(bad_rows)
    check("P2 an earlier row still LIVE is reported as a double-write",
          "double-write" in out2, out2.strip().splitlines()[-1][:60])
    # ⚠️ AND IT EXITS NON-ZERO ONLY FOR THE UNEXPLAINED ONES. Supersession is
    # the designed path and must not read as a failure, or the exit code stops
    # meaning anything.
    check("P2b ...and only the unexplained case exits non-zero",
          rc2 != 0 and rc == 0, f"bad={rc2} good={rc}")

    # ══ ⚠️ P3 — A SAME-SECOND PAIR CONTRADICTS r212's OWN REASONING ═══════
    # "take() and the entry attempt happen on the SAME tick, so by the time the
    # next one fires the previous has resolved." Two rows in the same second
    # means that assumption did not hold, whatever the states say — so it is
    # called out even when supersession explains the states.
    same_tick = [
        _row("c1", "CRM", "RunawayContinuation", "CLOSED", _ts("10:15"),
             259.38, "superseded — never filled"),
        _row("c2", "CRM", "RunawayContinuation", "TRIGGERED", _ts("10:15", 0.2),
             259.38),
    ]
    rc3, out3 = _run(same_tick)
    check("P3 a same-second pair is called out even when the states explain it",
          "SAME-SECOND" in out3, "flagged" if "SAME-SECOND" in out3 else out3[-80:])

    # ══ P4 — AND A CLEAN RANGE SAYS SO ═══════════════════════════════════
    clean = [_row("d1", "CRM", "RunawayContinuation", "TRIGGERED",
                  _ts("10:15"), 259.38),
             _row("d2", "CRM", "RunawayContinuation", "TRIGGERED",
                  _ts("11:00"), 261.10)]
    rc4, out4 = _run(clean)
    check("P4 distinct triggers are not clustered together",
          "no duplicate-trigger clusters" in out4 and rc4 == 0, f"rc={rc4}")

    print()
    if FAILED:
        print(f"RED — {len(FAILED)} failed: {', '.join(FAILED)}")
        return 1
    print("GREEN — 6 checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
