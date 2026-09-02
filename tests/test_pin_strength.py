#!/usr/bin/env python3
# day_trader_pro/tests/test_pin_strength.py — v1.0
# v1.0 (2026-09-01) — dtp r243. THE STUDY RECOVERS A PLANTED ANSWER.
#
# 🔴 P1 IS A REGRESSION GUARD ON A FANOUT THAT MANUFACTURED ITS OWN RESULT.
#   plan_check writes ~4 rows a minute (a tick is ~15s), so joining pin to
#   concentration minute-on-minute fanned out 4x4: a planted 240-row day
#   reported n=960 and EVERY CROSSING WAS COUNTED FOUR TIMES. Crossings are the
#   metric this study turns on, so the fanout would have manufactured exactly
#   the pull it exists to detect. Caught by the fixture, not by reading.
#
# 🔑 P2/P3: a PINNED symbol (price oscillating across the strike, converging)
#   and a TRENDING one (passing through once, diverging) must come out
#   different in the direction the theory predicts. A study that cannot
#   separate a planted magnet from a planted waypoint cannot separate a real
#   one either.
import io, json, math, os, sys, contextlib
from datetime import datetime
from zoneinfo import ZoneInfo
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
ET = ZoneInfo("US/Eastern")
_fails = []


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + (f"   [{detail}]" if detail else ""))
    if not ok:
        _fails.append(name)


def _fake_store():
    def ep(d, h, mi, sc=0):
        return datetime(2026, int(d[5:7]), int(d[8:10]), h, mi, sc, tzinfo=ET).timestamp()
    store = {}
    for d in ("2026-08-31",):
        for sym, pin, conc, pinned in (("QQQ", 710.0, 0.62, True),
                                       ("TSLA", 340.0, 0.18, False)):
            pc, pt, fk, sf = [], [], [], []
            for i in range(240):
                t = ep(d, 12, i % 60, (i // 60) * 15)
                px = (pin + math.sin(i / 3.0) * (3.0 * (1 - i / 300.0))
                      if pinned else pin - 5 + i * 0.05)
                pc.append({"ts_epoch": t, "strategy": "GEXPinButterfly",
                           "check_name": "pinning", "value": pin})
                pc.append({"ts_epoch": t, "strategy": "GEXPinButterfly",
                           "check_name": "pin_concentration", "value": conc})
                pt.append({"ts_epoch": t, "strategy": "GEXPinButterfly",
                           "underlying": px, "verdict": "D"})
                fk.append({"ts_epoch": t, "interval": "1h", "built": 1,
                           "upper": pin + 8, "median": pin, "lower": pin - 8,
                           "containment": 0.95})
                sf.append({"ts_epoch": t, "strike": pin,
                           "charm": -(4.0 if pinned else 0.4)})
            for nm, recs in (("derived_plan_check", pc), ("derived_plan_tick", pt),
                             ("fork_series", fk), ("surface_series", sf)):
                store[f"raw/{nm}/dt={d}/sym={sym}/1.json"] = json.dumps(
                    {"symbol": sym, "record": recs}).encode()
    return store


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

    store = _fake_store()
    WR._client = lambda *a, **k: _S3(store)
    import importlib.util as u
    sp = u.spec_from_file_location("ps", os.path.join(_root, "tools",
                                                      "pin_strength_study.py"))
    m = u.module_from_spec(sp)
    try:
        sp.loader.exec_module(m)
    except SystemExit:
        pass
    m.WCACHE.WR._client = lambda *a, **k: _S3(store)
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            m.main(["x", "--from", "2026-08-31", "--to", "2026-08-31"])
    except SystemExit:
        pass
    text = buf.getvalue()

    rows = {}
    for ln in text.splitlines():
        p = ln.split()
        if len(p) >= 8 and p[0].startswith("2026-") and p[1] in ("QQQ", "TSLA"):
            rows[p[1]] = p

    # ── P1 — 240 planted rows over 60 minutes must NOT report 960 ────────
    check("P1 the minute join does not fan out",
          all(int(r[2].replace(",", "")) == 60 for r in rows.values()),
          str({k: v[2] for k, v in rows.items()}))

    # ── P2 — the magnet crosses repeatedly, the waypoint does not ───────
    ok = ("QQQ" in rows and "TSLA" in rows
          and int(rows["QQQ"][3]) > int(rows["TSLA"][3]))
    check("P2 a planted PINNED symbol shows more crossings than a trending one",
          ok, f"QQQ={rows.get('QQQ',[None]*4)[3]} TSLA={rows.get('TSLA',[None]*4)[3]}")

    # ── P3 — and it converges while the other diverges ─────────────────
    ok3 = ("QQQ" in rows and "TSLA" in rows
           and float(rows["QQQ"][4]) < 1.0 < float(rows["TSLA"][4]))
    check("P3 the pinned symbol converges (<1) and the trending one diverges",
          ok3, f"QQQ={rows.get('QQQ',[None]*5)[4]} TSLA={rows.get('TSLA',[None]*5)[4]}")

    # ── P4 — a thin sample says NOT RESOLVED rather than printing an r ──
    # Operator: resolved either conclusively or not, but resolved either way.
    check("P4 a 2-group sample reports NOT RESOLVED, not a correlation",
          "NOT RESOLVED" in text, "an r on two points is not an answer")

    print()
    if _fails:
        print(f"FAILED {len(_fails)}: " + ", ".join(_fails))
        return 1
    print("test_pin_strength: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
