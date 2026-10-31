#!/usr/bin/env python3
"""
day_trader_pro/tests/check_series_tail.py  v1.0
v1.0  2026-10-31  dtp r517 / SER.1 — a series backlog is held, not waved through, and a stream that stops early is graded.
      On 2026-10-30 S3's SPX quote_series stopped at 13:53 ET and QQQ's at 14:38 (the box-side pusher shipped one
      50,000-row object per 5-minute run), the VERIFY lines read OK short=0 and STREAMS was green.
      Operator: "yes to all of the prepared solutions" (2026-10-31).

  T1  eod_conductor_v2.series_lag reads OTV5 s3_push v5.4's `  SERIES_LAG <ns|table> series_lag_s=N` lines
  T2  ... and an older pusher's output (no such line) is None, never 0
  T3  takedown HOLDS a box whose series lag is above 0 even when its output carries the COUNTER DRIFT diagnosis
  T4  CONTROL: drift with lag 0, and drift from an older pusher ("?"), still go down as before
  T5  warehouse_coverage.check_tail: last key 13:53 -> TRUNCATED, 15:50 -> OK, no objects -> MISSING
  T6  a half day is close-anchored: 2026-11-27 needs 12:45, so 12:50 is OK
  T7  report_tail exits 1 on a truncated box and 0 when every box reaches the close
  T8  eod_analysis runs warehouse_coverage --tail as its TAIL phase

Born red on 9aadf1a.  Run:  python3 tests/check_series_tail.py
"""
import io
import os
import sys
from contextlib import redirect_stdout
from datetime import datetime
from zoneinfo import ZoneInfo

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
ET = ZoneInfo("America/New_York")
FAILS = []


def check(name, ok, detail=""):
    print("  {:<4} {}  {}".format(name, "PASS" if ok else "FAIL", detail))
    if not ok:
        FAILS.append(name)


V54 = ("  SERIES_LAG series|greeks_series series_lag_s=0\n"
       "  SERIES_LAG series|quote_series series_lag_s=7620 BEHIND (rows still on this box; ...)\n"
       "DRAIN host=x sym=SPX drained=yes pushed=7 failed=0 prefixes=600 local=10 s3=9 short=1 SHORT\n"
       "  SHORT raw/x/dt=2026-10-30/sym=SPX/ expected>=10 got=9\n"
       "  ⚠️ SMALL, CONSISTENT SHORTFALL ON 1 PREFIXES (max 1). That is the signature of COUNTER DRIFT\n")
V53 = ("DRAIN host=x sym=SPX drained=yes pushed=7 failed=0 prefixes=600 local=10 s3=9 short=1 SHORT\n"
       "  ⚠️ SMALL, CONSISTENT SHORTFALL ON 1 PREFIXES (max 1). That is the signature of COUNTER DRIFT\n")


class FakeS3:
    def __init__(self, keys):
        self.keys = keys

    def get_paginator(self, _n):
        keys = self.keys

        class _P:
            def paginate(self, Bucket=None, Prefix=""):
                yield {"Contents": [{"Key": k, "Size": 1} for k in keys if k.startswith(Prefix)]}
        return _P()


def _key(stream, day, sym, hh, mm):
    d = datetime.fromisoformat(day)
    t = datetime(d.year, d.month, d.day, hh, mm, tzinfo=ET).timestamp()
    return f"raw/{stream}/dt={day}/sym={sym}/{int(t * 1000)}-abcdef0123456789.json"


def main():
    try:
        import eod_conductor_v2 as C
    except Exception as exc:                                    # noqa: BLE001
        print("  FAIL  conductor did not import: {}".format(exc))
        return 1
    import warehouse_coverage as W

    f = getattr(C, "series_lag", None)
    try:
        mx, behind = f(V54)
        check("T1", mx == 7620 and behind == [("series|quote_series", 7620)], f"max {mx} behind {behind}")
    except Exception as exc:                                    # noqa: BLE001
        check("T1", False, f"raised {exc!r}")
    try:
        mx, behind = f(V53)
        check("T2", mx is None and behind == [], f"max {mx!r} behind {behind}")
    except Exception as exc:                                    # noqa: BLE001
        check("T2", False, f"raised {exc!r}")

    def _res(raw, lag):
        m = C.DRAIN_RE.search(raw)
        d = m.groupdict()
        d["raw"] = raw
        d["series_lag_s"] = lag
        return d

    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            ok, held = C.takedown({"SPX": _res(V54, 7620)}, True, True)
        check("T3", held == ["SPX"] and ok == [], f"ok {ok} held {held}")
    except Exception as exc:                                    # noqa: BLE001
        check("T3", False, f"raised {exc!r}")
    try:
        with redirect_stdout(buf):
            ok1, held1 = C.takedown({"SPX": _res(V54, 0)}, True, True)
            ok2, held2 = C.takedown({"SPX": _res(V53, "?")}, True, True)
        check("T4", ok1 == ["SPX"] and ok2 == ["SPX"] and not held1 and not held2,
              f"lag 0: ok {ok1}; older pusher: ok {ok2}")
    except Exception as exc:                                    # noqa: BLE001
        check("T4", False, f"raised {exc!r}")

    day = "2026-10-30"
    s3 = FakeS3([_key("quote_series", day, "SPX", 9, 30), _key("quote_series", day, "SPX", 13, 53),
                 _key("quote_series", day, "AMD", 15, 50)])
    try:
        d = W.check_tail(s3, day, ["SPX", "AMD", "UNH"])
        v = {r["box"]: r["verdict"] for r in d["rows"]}
        check("T5", v == {"SPX": "TRUNCATED", "AMD": "OK", "UNH": "MISSING"}, f"{v}")
    except Exception as exc:                                    # noqa: BLE001
        check("T5", False, f"raised {exc!r}")
    try:
        hd = "2026-11-27"
        d = W.check_tail(FakeS3([_key("quote_series", hd, "SPX", 12, 50)]), hd, ["SPX"])
        v = d["rows"][0]["verdict"] if d.get("rows") else d.get("verdict")
        check("T6", v == "OK" and d["need"].strftime("%H:%M") == "12:45",
              f"verdict {v}, need {d.get('need')}")
    except Exception as exc:                                    # noqa: BLE001
        check("T6", False, f"raised {exc!r}")
    try:
        with redirect_stdout(io.StringIO()) as o:
            rc_bad = W.report_tail(s3, [day], want=["SPX", "AMD"])
            rc_ok = W.report_tail(s3, [day], want=["AMD"])
        check("T7", rc_bad == 1 and rc_ok == 0, f"truncated rc {rc_bad} (want 1), clean rc {rc_ok} (want 0)")
    except Exception as exc:                                    # noqa: BLE001
        check("T7", False, f"raised {exc!r}")

    src = open(os.path.join(REPO, "eod_analysis.py"), encoding="utf-8").read()
    check("T8", '"--tail"' in src and '("TAIL", _tail,' in src, "TAIL phase runs warehouse_coverage --tail")

    if FAILS:
        print("\nRED — {} check(s) failed: {}".format(len(FAILS), " ".join(FAILS)))
        return 1
    print("\nGREEN — a lagging box is held, and a stream that stops early is graded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
