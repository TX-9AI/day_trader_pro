#!/usr/bin/env python3
# day_trader_pro/tests/test_warehouse_cost.py — v1.2
"""
Pins warehouse_cost v1.0 (WH.9a).

CHANGELOG
    v1.2 — 2026-08-16 — the DEGRADATION test. `--versions` hit AccessDenied on
           the real bucket and threw away a completed whole-bucket scan with
           it. An optional extra must never cost the caller work that already
           succeeded, so that is now asserted rather than hoped for.
    v1.1 — 2026-08-16 — alongside warehouse_cost v1.1. Adds the check that
           would have caught the two-minute silence: progress must reach
           STDERR, and must NOT contaminate stdout, or --json stops being
           machine-readable.
    v1.0 — 2026-08-16 — alongside warehouse_cost v1.0.

WHY BOTHER TESTING A REPORT SCRIPT
    Because its output is going to decide whether we spend effort on Parquet
    compaction. A cost report that double-counts, or that divides by the wrong
    number of days, produces a confident wrong number — and a confident wrong
    number is exactly what gets acted on. The arithmetic is asserted against a
    stub whose totals are known by construction.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

FAILS = []


def check(name, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + name +
          ("" if cond else "  <- " + str(detail)))
    if not cond:
        FAILS.append(name)


import warehouse_cost as WC  # noqa: E402

print("\n=== warehouse_cost v1.0 ===\n")

MB = 1024 * 1024
OBJS = (
    # 2 days of trades, 1 MB each
    ("raw/trades/dt=2026-08-14/sym=SPX/1-a.json", 1 * MB),
    ("raw/trades/dt=2026-08-14/sym=QQQ/2-b.json", 1 * MB),
    ("raw/trades/dt=2026-08-15/sym=SPX/3-c.json", 1 * MB),
    # chains: fewer objects, far more bytes — the point of showing both
    ("raw/chain_snapshots/dt=2026-08-14/sym=SPX/4-d.json", 90 * MB),
    ("raw/chain_snapshots/dt=2026-08-15/sym=SPX/5-e.json", 90 * MB),
    # journal: many objects, few bytes
    *[("raw/signal_journal/dt=2026-08-14/sym=MU/%d-f.json" % i, 1024)
      for i in range(100)],
)


class Stub:
    def __init__(self, objs, versions=None):
        self.objs = objs
        self.versions = versions or []

    def get_paginator(self, op):
        objs, versions = self.objs, self.versions

        class _P:
            def paginate(self, Bucket=None, Prefix="", **kw):
                if op == "list_objects_v2":
                    yield {"Contents": [{"Key": k, "Size": s} for k, s in objs
                                        if k.startswith(Prefix)]}
                else:
                    yield {"Versions": versions, "DeleteMarkers": [{"Key": "x"}]}
        return _P()


s3 = Stub(OBJS)
out = WC.report(s3, do_versions=False, as_json=False)

check("object count is exact", out["objects"] == 105, out["objects"])
expect_gb = (3 * MB + 180 * MB + 100 * 1024) / WC.GB
# NOTE: report() rounds gb to 4 decimals for display, so the tolerance must
# match that rounding — asserting 1e-6 against a rounded value fails for a
# reason that has nothing to do with the arithmetic being wrong.
check("byte total is exact", abs(out["gb"] - expect_gb) < 5e-5, (out["gb"], expect_gb))
check("distinct dt= days counted once across prefixes",
      out["distinct_days"] == 2, out["distinct_days"])
check("per-day rate divides by DAYS, not by objects",
      abs(out["per_day"]["objects"] - 52.5) < 0.1, out["per_day"])

pf = out["prefixes"]
check("prefixes are grouped at raw/<datatype>", set(pf) == {
    "raw/trades", "raw/chain_snapshots", "raw/signal_journal"}, set(pf))
check("chains dominate BYTES while journal dominates OBJECTS — the whole point",
      pf["raw/chain_snapshots"]["gb"] > pf["raw/signal_journal"]["gb"]
      and pf["raw/signal_journal"]["objects"] > pf["raw/chain_snapshots"]["objects"],
      {k: (v["objects"], v["gb"]) for k, v in pf.items()})
check("prefixes are ordered by bytes, biggest first",
      list(pf)[0] == "raw/chain_snapshots", list(pf))
check("avg KB is per-object, not per-prefix",
      abs(pf["raw/signal_journal"]["avg_kb"] - 1.0) < 0.01,
      pf["raw/signal_journal"]["avg_kb"])
check("athena scan cost scales with bytes at $5/TB",
      abs(pf["raw/chain_snapshots"]["athena_full_scan_usd"]
          - (180 * MB / WC.GB / 1024 * 5.0)) < 1e-4,
      pf["raw/chain_snapshots"]["athena_full_scan_usd"])

# year-1 average must be HALF the year-end balance, not the peak
py = out["projected_year"]
check("year-1 average storage is half the year-end balance (billing is on average)",
      abs(py["storage_usd_mo_year1_avg"] * 2 - py["storage_usd_mo_at_year_end"]) < 0.02,
      py)

# noncurrent accounting
# Sized so the noncurrent cost is VISIBLE at the printed precision. A 1 MB
# stub rounds to $0.000 and would "pass" a >0 check only by luck — the point of
# this line item is that it becomes material while nobody is watching.
s3v = Stub(OBJS, versions=[
    {"Key": "raw/trades/dt=2026-08-14/sym=SPX/1-a.json", "Size": 1024 * MB, "IsLatest": True},
    {"Key": "raw/trades/dt=2026-08-14/sym=SPX/1-a.json", "Size": 1024 * MB, "IsLatest": False},
    {"Key": "raw/trades/dt=2026-08-14/sym=SPX/1-a.json", "Size": 1024 * MB, "IsLatest": False},
])
out2 = WC.report(s3v, do_versions=True, as_json=False)
v = out2["versions"]
check("current vs NONCURRENT versions are separated",
      v["current"]["n"] == 1 and v["noncurrent"]["n"] == 2, v)
check("delete markers are counted", v["delete_markers"] == 1, v)
check("noncurrent carries its own monthly cost, at the printed precision",
      v["noncurrent"]["usd_mo"] >= 0.045, v)   # 2 GB x $0.023

# an empty bucket must not divide by zero
out3 = WC.report(Stub(()), do_versions=False, as_json=False)
check("an empty bucket reports zero, not a ZeroDivisionError",
      out3["objects"] == 0 and out3["per_day"]["objects"] == 0, out3["per_day"])


# progress: visible on stderr, absent from stdout
import io
import contextlib

buf_out, buf_err = io.StringIO(), io.StringIO()
with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
    WC.report(Stub(OBJS), do_versions=False, as_json=False, quiet=False)
check("progress goes to STDERR", "scanning s3://" in buf_err.getvalue(),
      buf_err.getvalue()[:80])
check("progress does NOT contaminate stdout",
      "scanning s3://" not in buf_out.getvalue())

buf_out2, buf_err2 = io.StringIO(), io.StringIO()
with contextlib.redirect_stdout(buf_out2), contextlib.redirect_stderr(buf_err2):
    WC.report(Stub(OBJS), do_versions=False, as_json=True, quiet=True)
check("--json emits parseable JSON and nothing else",
      json.loads(buf_out2.getvalue())["objects"] == 105)
check("--quiet silences progress entirely", buf_err2.getvalue() == "",
      buf_err2.getvalue()[:60])


# an optional extra must not discard work that already succeeded
class VersionsBoom(Stub):
    def get_paginator(self, op):
        if op == "list_objects_v2":
            return Stub.get_paginator(self, op)

        class _P:
            def paginate(self_inner, **kw):
                raise RuntimeError(
                    "An error occurred (AccessDenied) when calling the "
                    "ListObjectVersions operation: ... s3:ListBucketVersions")
        return _P()


bufo, bufe = io.StringIO(), io.StringIO()
with contextlib.redirect_stdout(bufo), contextlib.redirect_stderr(bufe):
    outv = WC.report(VersionsBoom(OBJS), do_versions=True, quiet=True)
txt = bufo.getvalue()
check("a --versions failure does NOT discard the completed scan",
      outv["objects"] == 105 and "WAREHOUSE INVENTORY" in txt, outv.get("objects"))
check("the failure is reported, not swallowed", "versions_error" in outv)
check("it names the exact missing permission",
      "s3:ListBucketVersions" in txt)
check("it says the rest of the report still stands", "still stands" in txt)

print("\n" + ("ALL CHECKS PASSED" if not FAILS else "FAILURES: " + ", ".join(FAILS)))
sys.exit(1 if FAILS else 0)
