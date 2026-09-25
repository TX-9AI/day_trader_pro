#!/usr/bin/env python3
"""
tests/check_crashloop_session.py  v1.0
v1.0  2026-09-25  r429 / OPS.53 — A LOOP WHOSE PERIOD IS THE WINDOW.

  🔑 S1 IS THE INCIDENT ITSELF AND IT IS THE SHIP-BLOCKER. AAL's optionsbot
  self-shut-down and restarted at 14:11, 15:11 and 16:07 UTC on 2026-09-25 —
  about SIXTY minutes apart against WINDOW_S=3600. The sentinel logged
  "in-window=2" then "in-window=1" as each event aged out, never reached
  THRESHOLD, and sent ZERO alerts while the box sat blind for roughly 23
  minutes across two episodes in prime RTH. S1 drives that exact timeline and
  demands an alert.

  ⚠️ THE ARITHMETIC WAS NEVER WRONG, AND I DIAGNOSED IT BACKWARDS FIRST.
  `hist + [now] * delta` already credits every restart between two polls, so a
  BURST always alerted. I reported "under-counts fast loops" from the summary
  numbers before reading the evaluator, and told both the operator and the peer
  session the opposite of the truth. S2 exists to keep me honest about that: it
  pins that the burst rule STILL WORKS, so the fix cannot quietly trade one
  blind spot for another.

  🔑 S4 GUARDS THE OTHER DIRECTION. Each box already sends its own "STARTED |
  service restart" message on every restart, so this alert's value is naming
  the PATTERN. Firing it every poll would be the cry-wolf §17 exists for.
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


def _ep(y, mo, d, h, mi):
    import datetime
    return datetime.datetime(y, mo, d, h, mi,
                             tzinfo=datetime.timezone.utc).timestamp()


def _replay(CS, marks, start, end, step=300, state=None):
    """Poll every `step` from start to end; NRestarts increments at `marks`."""
    state = state if state is not None else {}
    fired = []
    t = start
    while t <= end:
        n = sum(1 for m in marks if t >= m)
        state, alerts = CS.evaluate(state, {"AAL": {"restarts": n,
                                                    "sub": "running",
                                                    "err": ""}}, t)
        for a in alerts:
            fired.append((t, a["kind"], a["count"]))
        t += step
    return state, fired


def main():
    try:
        import crashloop_sentinel as CS
    except Exception as exc:                                   # noqa: BLE001
        for t in ("S1", "S2", "S3", "S4", "S5"):
            ck(t, False, f"cannot import crashloop_sentinel ({exc})")
        print(f"\nRED — {len(_fails)} check(s) failed: {' '.join(_fails)}")
        return 1

    # ⚠️ S2 RUNS FIRST AND UNCONDITIONALLY, because it is the one check that
    # must pass at HEAD: it proves the burst rule already worked, which is the
    # evidence that my first diagnosis ("under-counts fast loops") was wrong.
    # ── S2 — REGRESSION: the burst rule still works ────────────────────────
    burst = [_ep(2026, 9, 25, 14, 1), _ep(2026, 9, 25, 14, 2),
             _ep(2026, 9, 25, 14, 3)]
    try:
        _st2, fired2 = _replay(CS, burst, _ep(2026, 9, 25, 13, 50),
                               _ep(2026, 9, 25, 14, 30))
        kinds = {f[1] for f in fired2}
        ck("S2", "loop" in kinds,
           f"a 3-restart BURST still trips the rolling-window rule "
           f"(fired {sorted(kinds)}) — the arithmetic was never the defect")
    except Exception as exc:                                   # noqa: BLE001
        ck("S2", False, f"burst replay failed ({type(exc).__name__}: {exc})")

    # ⚠️ ONE LINE PER CHECK. r428's gate reported a check twice when a guard
    # and the probe below it both fired, and a gate that double-counts its own
    # failures has untrustworthy totals. The guard RETURNS rather than falling
    # through into probes that would fail again for the same reason.
    if not hasattr(CS, "SESSION_THRESHOLD"):
        for t in ("S1", "S3", "S4", "S5"):
            ck(t, False, "SESSION_THRESHOLD absent — only the rolling window "
                         "exists, so an hourly loop is still invisible")
        print(f"\nRED — {len(_fails)} check(s) failed: {' '.join(_fails)}")
        return 1

    # ── S1 — SHIP-BLOCKER: AAL's real timeline must alert ──────────────────
    marks = [_ep(2026, 9, 25, 14, 11), _ep(2026, 9, 25, 15, 11),
             _ep(2026, 9, 25, 16, 7)]
    try:
        _st, fired = _replay(CS, marks, _ep(2026, 9, 25, 13, 0),
                             _ep(2026, 9, 25, 16, 20))
        ck("S1", bool(fired),
           f"AAL's actual 14:11/15:11/16:07 UTC timeline fires {[f[1] for f in fired]}"
           if fired else
           "AAL's ACTUAL timeline fires NOTHING — three crash loops and ~23 "
           "blind minutes would pass unremarked again")
    except Exception as exc:                                   # noqa: BLE001
        ck("S1", False, f"replay failed ({type(exc).__name__}: {exc})")

    # ── S3 — the session tally resets on the ET trading day ────────────────
    try:
        st = {"AAL": {"restarts": 5, "events": [], "last_alert": 0, "level": 0,
                      "unreachable": 0, "session_day": "2026-09-24",
                      "session_restarts": 9, "session_alerted": True}}
        st2, _a = CS.evaluate(st, {"AAL": {"restarts": 5, "sub": "running",
                                           "err": ""}},
                              _ep(2026, 9, 25, 14, 0))
        got = st2["AAL"].get("session_restarts")
        ck("S3", got == 0 and st2["AAL"].get("session_day") == "2026-09-25",
           f"yesterday's tally does not leak into today (session_restarts={got}, "
           f"day={st2['AAL'].get('session_day')})")
    except Exception as exc:                                   # noqa: BLE001
        ck("S3", False, f"reset probe failed ({type(exc).__name__}: {exc})")

    # ── S4 — it fires ONCE per ET day, not every poll (§17) ────────────────
    try:
        _st3, fired3 = _replay(CS, marks, _ep(2026, 9, 25, 13, 0),
                               _ep(2026, 9, 25, 19, 0))
        sess = [f for f in fired3 if f[1] == "session_loop"]
        ck("S4", len(sess) <= 1,
           f"the repeat-restart alert fires {len(sess)}× across a 6-hour "
           f"session — each box already telegraphs its own restart, so "
           f"repeating the pattern every poll is cry-wolf")
    except Exception as exc:                                   # noqa: BLE001
        ck("S4", False, f"repeat probe failed ({type(exc).__name__}: {exc})")

    # ── S5 — an unreachable poll must not wipe the session tally ───────────
    try:
        st = {"AAL": {"restarts": 2, "events": [], "last_alert": 0, "level": 0,
                      "unreachable": 0, "session_day": "2026-09-25",
                      "session_restarts": 1, "session_alerted": False}}
        st2, _a = CS.evaluate(st, {"AAL": {"restarts": None, "sub": "",
                                           "err": ""}},
                              _ep(2026, 9, 25, 14, 30))
        kept = st2["AAL"].get("session_restarts")
        ck("S5", kept == 1,
           f"an unreadable poll preserves the tally (kept={kept}) — a box that "
           f"is briefly unreachable and then restarts again is the same loop")
    except Exception as exc:                                   # noqa: BLE001
        ck("S5", False, f"unreachable probe failed ({type(exc).__name__}: {exc})")

    if _fails:
        print(f"\nRED — {len(_fails)} check(s) failed: {' '.join(_fails)}")
        return 1
    print("\nGREEN — bursts and hourly loops both alert, once per day, and an "
          "unreadable poll forgets nothing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
