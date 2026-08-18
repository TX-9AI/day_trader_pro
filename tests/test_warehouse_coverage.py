#!/usr/bin/env python3
"""
tests/test_warehouse_coverage.py — the verdicts, exercised. v1.1
v1.1 — 2026-08-18 — +the two NON-verdicts. v1.0 asserted the three failure/OK
       states and shipped a checker that called a SUNDAY a push defect: the
       real 08-16 run showed 🔴 PUSH_DEFECT for a day the market was closed,
       because one stray weekend object created a dt= partition. Adds: a
       non-session is NEVER a defect, a pre-collection date is NEVER counted
       as coverage, and neither is silently dropped from the report.
v1.0 — 2026-08-18 — INITIAL.

`warehouse_coverage.check_date` decides which of three things happened on a
date, and the whole value of the phase is that it never confuses them:

  OK           VIX 1m objects are in the bucket
  PUSH_DEFECT  SPX warehoused its own candles but no VIX — the data existed on
               the box and did not land. Actionable now.
  OWNER_DOWN   SPX pushed nothing at all — explained, still a gap, and the
               argument for a fallback writer.

A checker that reported "missing" for both would send you hunting a push bug
on a day the box was simply off — the cry-wolf class (CV.1).

So this drives the real function against a STUBBED S3 whose contents we
choose, and asserts the verdict. No bucket, no credentials, no network.

Run:  cd ~/day_trader_pro && python3 tests/test_warehouse_coverage.py
Deliberate-failure proof: OT_COV_SELFTEST=1 inverts one expectation; the suite
must go red.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import warehouse_coverage as WC          # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    if not ok:
        FAILS.append(name)
    print(f"  {'✅' if ok else '❌'} {name}{('  — ' + detail) if detail else ''}")


class _FakePaginator:
    def __init__(self, keys):
        self._keys = keys

    def paginate(self, Bucket=None, Prefix="", Delimiter=None):   # noqa: N803
        hits = [k for k in self._keys if k.startswith(Prefix)]
        if Delimiter:
            seen = []
            for k in hits:
                rest = k[len(Prefix):]
                if Delimiter in rest:
                    cp = Prefix + rest.split(Delimiter)[0] + Delimiter
                    if cp not in seen:
                        seen.append(cp)
            yield {"CommonPrefixes": [{"Prefix": p} for p in seen]}
            return
        yield {"Contents": [{"Key": k} for k in hits]}


class _FakeS3:
    def __init__(self, keys):
        self._keys = keys

    def get_paginator(self, _op):
        return _FakePaginator(self._keys)


def _keys_for(day, vix_1m=0, vix_1d=0, spx=0):
    ks = []
    for i in range(vix_1m):
        ks.append(f"raw/candles/dt={day}/sym=VIX/interval=1m/{i}-abc.json")
    for i in range(vix_1d):
        ks.append(f"raw/candles/dt={day}/sym=VIX/interval=1d/{i}-abc.json")
    for i in range(spx):
        ks.append(f"raw/candles/dt={day}/sym=SPX/interval=1m/{i}-abc.json")
    return ks


def main():
    day = "2026-08-18"

    r = WC.check_date(_FakeS3(_keys_for(day, vix_1m=3, vix_1d=1, spx=4)), day)
    expect_ok = "OK" if os.environ.get("OT_COV_SELFTEST", "0") != "1" else "OWNER_DOWN"
    check("VIX present → OK", r["verdict"] == expect_ok, r["verdict"])
    check("and the object counts are reported",
          r["VIX_1m"] == 3 and r["VIX_1d"] == 1, str(r))

    r = WC.check_date(_FakeS3(_keys_for(day, vix_1m=0, spx=4)), day)
    check("SPX pushed candles, no VIX → PUSH_DEFECT",
          r["verdict"] == "PUSH_DEFECT", r["verdict"])

    r = WC.check_date(_FakeS3(_keys_for(day, vix_1m=0, spx=0)), day)
    check("SPX pushed nothing → OWNER_DOWN", r["verdict"] == "OWNER_DOWN",
          r["verdict"])

    # a day with 1d but no 1m is still missing the tape the replay needs
    r = WC.check_date(_FakeS3(_keys_for(day, vix_1m=0, vix_1d=2, spx=4)), day)
    check("VIX daily without 1m is NOT coverage",
          r["verdict"] == "PUSH_DEFECT", r["verdict"])

    # another date's objects must never satisfy this date
    other = _FakeS3(_keys_for("2026-08-17", vix_1m=5, spx=5))
    r = WC.check_date(other, day)
    check("a different dt= does not count as coverage",
          r["verdict"] == "OWNER_DOWN", r["verdict"])

    # ── v1.1 — the two states that are explanations, not failures ──────────
    sunday = "2026-08-16"          # a real date this tool got wrong at v1.0
    r = WC.check_date(_FakeS3(_keys_for(sunday, vix_1m=0, spx=1)), sunday)
    check("a Sunday with a stray object is NOT a defect",
          r["verdict"] == "NOT_A_SESSION", r["verdict"])

    holiday = "2026-07-03"         # observed Independence Day
    r = WC.check_date(_FakeS3(_keys_for(holiday, vix_1m=0, spx=1)), holiday)
    check("a market holiday is NOT a defect", r["verdict"] == "NOT_A_SESSION",
          r["verdict"])

    early = "2026-08-10"           # before COLLECTION_START
    r = WC.check_date(_FakeS3(_keys_for(early, vix_1m=0, spx=2)), early)
    check("a pre-collection date is PARTIAL_BY_DESIGN, not a defect",
          r["verdict"] == "PARTIAL_BY_DESIGN", r["verdict"])

    r = WC.check_date(_FakeS3(_keys_for(early, vix_1m=9, spx=2)), early)
    check("and a pre-collection date is not counted as coverage either",
          r["verdict"] == "PARTIAL_BY_DESIGN", r["verdict"])

    # a real session with no VIX must still be caught — the guard must not
    # have been widened into an excuse
    r = WC.check_date(_FakeS3(_keys_for("2026-08-17", vix_1m=0, spx=9)),
                      "2026-08-17")
    check("a real Monday with no VIX is STILL a push defect",
          r["verdict"] == "PUSH_DEFECT", r["verdict"])

    # the partition lister must find the days that exist and only those
    days = WC._dt_days(_FakeS3(_keys_for("2026-08-17", vix_1m=1)
                               + _keys_for("2026-08-18", spx=1)), "candles")
    check("_dt_days finds every dt= partition",
          days == ["2026-08-17", "2026-08-18"], str(days))

    print()
    if FAILS:
        print(f"warehouse_coverage: {len(FAILS)} FAILED — " + "; ".join(FAILS))
        return 1
    print("warehouse_coverage: ALL PASS (OK · PUSH_DEFECT · OWNER_DOWN · "
          "1d≠coverage · date isolation · dt= list · Sunday · holiday · "
          "pre-collection · guard-not-widened)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
