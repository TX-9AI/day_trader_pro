#!/usr/bin/env python3
"""
day_trader_pro/tools/check_level_history.py  v1.0
v1.0  2026-09-13  r379 / LVL.17 — THE HISTORY BUILDER'S DERIVATION, DRIVEN.

The builder reads S3 and the pusher needs boxes, so neither can be a land gate
as a whole. But the DERIVATION is pure — `candidates()`, `cluster()` and
`measure()` are functions of a tape — and those are where the answers come from.
This drives them on synthetic tape, offline, so the half ships with a CHECK that
actually runs (§15: a half that ships code and declares no CHECK is refused, and
the realistic failure is a forgotten check rather than a broken one).

  H1  every source is derived: session high/low, open/close, OR high/low, pivots
  H2  a level is NEVER counted on the session that FORMED it
  H3  `cluster()` merges inside `TOUCH_TOL_PCT` and keeps the UNION of sources
  H4  a defended zone counts holds; a zone price never reached counts NOTHING
  H5  a visit does NOT span the overnight gap — two sessions is two tests
  H6  `scp_push` builds an UPLOAD argv (local BEFORE remote). A swapped pair is
      a silent DOWNLOAD that overwrites the file control just built.
  H7  the counting rule comes from otv4, not from a copy in this repo (§7)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DTP = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, DTP)
FAILS = []


def check(n, ok, d=""):
    print("  {:<4} {}  {}".format(n, "PASS" if ok else "FAIL", d))
    if not ok:
        FAILS.append(n)


def main():
    print("check_level_history — the derivation, driven on synthetic tape")
    try:
        import build_level_history as B
    except Exception as exc:                                    # noqa: BLE001
        print("  FAIL  build_level_history did not import: {}".format(exc))
        return 1

    # ── a session: 90 one-minute bars. Price opens at 100, runs to 105, comes
    # back to 101 and closes at 102, with a clean swing low at 99 early on.
    def bar(h, l, c):
        return (0, h, l, c)

    def session(t0=0):
        bars = []
        bars.append((t0, 100.2, 99.8, 100.0))                  # open
        bars += [(t0 + i, 100.5, 99.0, 99.5) for i in range(1, 20)]
        bars[10] = (t0 + 10, 100.4, 99.00, 99.6)               # the swing low
        bars += [(t0 + i, 105.0, 104.0, 104.5) for i in range(20, 55)]
        bars += [(t0 + i, 102.5, 101.0, 101.5) for i in range(55, 89)]
        bars.append((t0 + 89, 102.2, 101.8, 102.0))            # close
        return bars

    sessions = {"2026-09-08": session(0)}
    cands = B.candidates(sessions)
    srcs = {c[3] for c in cands}
    want = {"session_high", "session_low", "session_open", "session_close",
            "or_high", "or_low", "pivot_high", "pivot_low"}
    check("H1", want <= srcs,
          "derived {} of {}: missing {}".format(len(srcs & want), len(want),
                                                sorted(want - srcs)) or "all")

    # ── H2 — formed on the ONLY session present, so nothing is testable.
    zones = B.cluster(cands)
    z0 = zones[0]
    m = B.measure(z0, sessions)
    check("H2", m["prior_sessions"] == 0 and m["prior_touches"] == 0,
          "one session: sessions={} tests={} (the forming day is never a test)"
          .format(m["prior_sessions"], m["prior_touches"]))

    # ── H3 — two candidates a hair apart become ONE zone carrying both sources.
    merged = B.cluster([("2026-09-08", 100.00, "low", "session_low"),
                        ("2026-09-08", 100.05, "low", "pivot_low"),
                        ("2026-09-08", 120.00, "low", "session_open")])
    one = [z for z in merged if abs(z["price"] - 100.0) < 0.5]
    check("H3", len(merged) == 2 and len(one) == 1
          and one[0]["sources"] == {"session_low", "pivot_low"},
          "{} zone(s); the merged one carries {}".format(
              len(merged), sorted(one[0]["sources"]) if one else None))

    # ── H4 — a later session that tests a zone and retreats, versus a zone the
    # tape never reaches. The second is the control: under the HALF-PLANE this
    # would have scored a touch and a breach on every bar (LVL.13).
    later = {"2026-09-08": session(0), "2026-09-09": session(1000)}
    defended = {"kind": "low", "price": 99.0, "first_seen": "2026-09-08", "n": 1,
                "sources": {"pivot_low"}}
    unreached = {"kind": "low", "price": 50.0, "first_seen": "2026-09-08", "n": 1,
                 "sources": {"pivot_low"}}
    md = B.measure(defended, later)
    mu = B.measure(unreached, later)
    check("H4", md["prior_touches"] > 0 and md["prior_holds"] > 0
          and mu["prior_touches"] == 0 and mu["prior_breaches"] == 0,
          "defended tests={} holds={} | unreached tests={} breaches={}".format(
              md["prior_touches"], md["prior_holds"],
              mu["prior_touches"], mu["prior_breaches"]))

    # ── H5 — THE OVERNIGHT GAP. A zone in contact at each session's end must be
    # two tests, not one visit spanning the close. The tape ends both sessions
    # sitting on 101.8-102.5, so a zone at 102.0 is in contact at both bells.
    gapz = {"kind": "high", "price": 102.0, "first_seen": "2026-09-07", "n": 1,
            "sources": {"session_close"}}
    three = {"2026-09-07": session(0), "2026-09-08": session(1000),
             "2026-09-09": session(2000)}
    mg = B.measure(gapz, three)
    check("H5", mg["prior_sessions"] == 2 and mg["prior_touches"] >= 2,
          "two eligible sessions -> sessions={} tests={} (a visit must not "
          "cross the bell)".format(mg["prior_sessions"], mg["prior_touches"]))

    # ── H6 — scp_push must UPLOAD. Captured, not run.
    try:
        import ssh_util
        import subprocess as _sp
        seen = {}

        class _P:
            returncode = 0
            stdout = ""
            stderr = ""

        def _fake(cmd, **kw):
            seen["cmd"] = list(cmd)
            return _P()

        _real, _sp.run = _sp.run, _fake
        try:
            ssh_util.scp_push("10.0.0.1", "/local/AMD.json",
                              "options-trader/data/level_history/AMD.json")
        finally:
            _sp.run = _real
        cmd = seen.get("cmd", [])
        li = next((i for i, x in enumerate(cmd) if x == "/local/AMD.json"), -1)
        ri = next((i for i, x in enumerate(cmd)
                   if x.endswith(":options-trader/data/level_history/AMD.json")), -1)
        check("H6", li >= 0 and ri >= 0 and li < ri,
              "argv order local({}) before remote({})".format(li, ri))
    except Exception as exc:                                    # noqa: BLE001
        check("H6", False, "scp_push not drivable: {}".format(exc))

    # ── H7 — ONE COUNTING RULE, AND IT LIVES IN otv4. If this ever resolves
    # inside day_trader_pro, a second definition of "a test" has appeared and
    # the store and the strategy can drift apart again — the split §7 forbids
    # and the one that produced LVL.13 in the first place.
    src_file = getattr(sys.modules[B.LiquidityLedger.__module__], "__file__", "")
    check("H7", "day_trader_pro" not in os.path.abspath(src_file)
          and src_file.endswith("liquidity_ledger.py"),
          "counting rule from {}".format(src_file))

    print()
    if FAILS:
        print("FAILED: {}".format(", ".join(FAILS)))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
