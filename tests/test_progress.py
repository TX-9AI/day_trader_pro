#!/usr/bin/env python3
# day_trader_pro/tests/test_progress.py — v1.0
# v1.0 (2026-09-01) — dtp r240. THE METER IS ON STDERR AND ON THE FETCH PATH.
#
# Operator, 2026-09-01: "The S3 options in devtools need a progress meter. Some
# of them run long." The butterfly probe measured 53.5s for ONE date, so a
# 7-day range is about six minutes of apparently-nothing.
#
# 🔴 P1 IS THE ONE THAT MATTERS. `tools/report_parity.py` diffs these reports'
#   OUTPUT across sources; a carriage-return meter on stdout would land inside
#   the comparison and every parity run would fail on animation rather than on
#   a real divergence — a false alarm that trains the reader to ignore the
#   check (CV.1).

import contextlib
import io
import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)

_fails = []


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + (f"   [{detail}]" if detail else ""))
    if not ok:
        _fails.append(name)


def main():
    import progress

    # ── P1 — NOTHING reaches stdout ─────────────────────────────────────
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        t = progress.Ticker("p", total=50, every=0.0)
        for _ in range(50):
            t.step(1, 1_000)
        t.done("fin")
    check("P1 the meter writes nothing to stdout",
          out.getvalue() == "", repr(out.getvalue()[:40]))
    check("P1b and it does write to stderr", "p:" in err.getvalue())

    # ── P2 — it always ends with a persistent summary line ──────────────
    # ⚠️ A METER THAT ERASES ITSELF LEAVES NO RECORD of what the read did, and
    # "0 objects" from an empty session must never look like "0 objects" from
    # an unreachable bucket (warehouse_reader's WhMeta rule, applied to fetch).
    tail = err.getvalue().rsplit("\r", 1)[-1]
    check("P2 done() leaves a persistent one-line summary",
          "50 object(s)" in tail and tail.endswith("\n"), repr(tail[-48:]))

    # ── P3 — no ETA until there is a rate worth extrapolating ───────────
    e2 = io.StringIO()
    with contextlib.redirect_stderr(e2):
        t = progress.Ticker("q", total=1000, every=0.0)
        for _ in range(5):
            t.step(1)
    check("P3 no ETA is shown from a handful of samples",
          "eta" not in e2.getvalue(), "an ETA off five objects would be wrong "
          "and believed")

    # ── P4 — DTP_NO_PROGRESS silences it completely ─────────────────────
    import importlib
    os.environ["DTP_NO_PROGRESS"] = "1"
    importlib.reload(progress)
    e3 = io.StringIO()
    try:
        with contextlib.redirect_stderr(e3):
            t = progress.Ticker("r", total=10, every=0.0)
            for _ in range(10):
                t.step(1)
            t.done()
    finally:
        os.environ.pop("DTP_NO_PROGRESS", None)
        importlib.reload(progress)
    check("P4 DTP_NO_PROGRESS=1 silences it for clean captures",
          e3.getvalue() == "", repr(e3.getvalue()[:40]))

    # ── P5 — it is on the SHARED fetch path, not bolted to one report ───
    # 🔑 fit_readiness, pnl_s3, warehouse_coverage and eod_analysis had no
    # meter of their own and all four pull through `read_prefix`. One wiring
    # covers every consumer, present and future.
    wr = open(os.path.join(_root, "warehouse_reader.py"), encoding="utf-8").read()
    wc = open(os.path.join(_root, "warehouse_cache.py"), encoding="utf-8").read()
    check("P5 read_prefix and the streaming cache both tick",
          "Ticker(" in wr and "Ticker(" in wc)

    # ── P6 — a multi-day cache read counts ALL days up front ────────────
    # ⚠️ Otherwise the percentage restarts at 0% on each date and a seven-day
    # read looks stuck seven times.
    check("P6 the cache totals every date before fetching",
          "plan.append" in wc and "total=len(plan)" in wc)

    print()
    if _fails:
        print(f"FAILED {len(_fails)}: " + ", ".join(_fails))
        return 1
    print("test_progress: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
