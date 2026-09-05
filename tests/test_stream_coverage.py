#!/usr/bin/env python3
"""day_trader_pro/tests/test_stream_coverage.py — v1.1
v1.1  2026-09-05 — dtp r280. THE THREE CORRECTIONS THE FIRST REAL RUN FORCED,
PINNED ON BEHAVIOUR RATHER THAN ON THE TABLE.

⚠️ S12-S14 DO NOT ASSERT THAT `STREAM_POLICY` CONTAINS A PARTICULAR STRING.
A test that reads the map back is the map agreeing with itself (C.23) and would
pass against any typo that still parses. They drive `check_streams` and assert
the VERDICT: SPX absent from `prints` is not a gap while any other box is; a box
absent from `trades` is not a gap at all; `shadow` absent from a box IS one now.

v1.0  2026-09-05 — dtp r277. PER-STREAM COVERAGE, AND THE FOUR WAYS IT COULD
CRY WOLF.

🔑 THE CHECKS THAT CARRY THE WEIGHT ARE THE NEGATIVE ONES. Reporting a gap is
easy; the failure mode that matters is a board that goes red on a stream nobody
expects, because a permanent red is the one thing that stops a board being read
(the CV.1 lesson, and v1.1 of the tool under test already learned it once on a
Sunday). So S3-S6 pin that a CONDITIONAL stream, a DEAD stream, a silent box and
a non-session day each report as themselves and NONE of them counts as a defect.

🔴 AND S2 IS THE ONE THAT WOULD HAVE MADE THE TOOL USELESS. A box that pushed
nothing at all would otherwise show as MISSING on every EVERY-stream — twenty
red lines for one diagnosis, drowning a real single-stream gap on another box.
That is v1.0's own PUSH_DEFECT vs OWNER_DOWN split generalised, and without it
the first fleet-wide outage makes the report unreadable.

⚠️ IT DRIVES THE REAL FUNCTIONS against a fake S3 rather than reading source
(WA §21), and S10 COUNTS PAGINATOR CALLS rather than inspecting code, because
the cost claim — presence is delimited LIST, counts page over objects — is a
behaviour and dtp r253 already established that the way to pin a fetch cost is
to count fetches.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FAILED = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        FAILED.append(name)


# ── a fake bucket: {datatype: {day: {sym: n_objects}}} ─────────────────────
class FakePaginator:
    def __init__(self, bucket, log):
        self.b, self.log = bucket, log

    def paginate(self, Bucket=None, Prefix="", Delimiter=None):
        self.log.append((Prefix, Delimiter))
        parts = [p for p in Prefix.split("/") if p]
        if Delimiter:
            if len(parts) == 1:                      # raw/  -> datatypes
                yield {"CommonPrefixes": [{"Prefix": f"raw/{d}/"} for d in self.b]}
                return
            if len(parts) == 3:                      # raw/<dt>/dt=<day>/ -> syms
                dt, day = parts[1], parts[2][3:]
                syms = self.b.get(dt, {}).get(day, {})
                yield {"CommonPrefixes":
                       [{"Prefix": f"{Prefix}sym={s}/"} for s in syms]}
                return
            yield {}
            return
        # no delimiter -> objects (this is the EXPENSIVE path)
        dt, day, sym = parts[1], parts[2][3:], parts[3][4:]
        n = self.b.get(dt, {}).get(day, {}).get(sym, 0)
        yield {"Contents": [{"Key": f"{Prefix}{i}.json", "Size": 10}
                            for i in range(n)]}


class FakeS3:
    def __init__(self, bucket):
        self.bucket, self.calls = bucket, []

    def get_paginator(self, _name):
        return FakePaginator(self.bucket, self.calls)


def main():
    try:
        import warehouse_coverage as wc
    except Exception as exc:                                    # noqa: BLE001
        check("S0 warehouse_coverage is importable", False,
              f"{type(exc).__name__}: {exc}")
        print("\nRED — 1 failed: S0 (the checker could not run; NOT a verdict "
              "on coverage)")
        return 1
    for fn in ("check_streams", "report_streams", "STREAM_POLICY", "panel"):
        if not hasattr(wc, fn):
            check(f"S0 warehouse_coverage exposes {fn}", False,
                  "absent — r277 has not landed in this checkout")
            print("\nRED — 1 failed: S0")
            return 1
    check("S0 warehouse_coverage exposes the v1.2 surface", True)

    DAY = "2026-09-03"          # a Thursday, after COLLECTION_START
    want = ["NVDA", "SPX", "QQQ", "CVX"]

    # NVDA, SPX and QQQ push everything. CVX pushes NOTHING — one box down.
    # NVDA is missing from ONE stream only: a real, single-stream gap that must
    # stay visible underneath the silent box.
    def full(*syms):
        return {DAY: {s: 3 for s in syms}}
    bucket = {
        "trades":                full("NVDA", "SPX", "QQQ"),
        "signal_journal":        full("NVDA", "SPX", "QQQ"),
        "derived_plan_check":    full("SPX", "QQQ"),          # NVDA missing
        "derived_fire_snapshot": full("SPX"),                 # CONDITIONAL
        # ⚠️ r280 RE-DERIVED THIS FIXTURE. It used `shadow` as the DEAD
        # example, and shadow turned out to be LIVE — so the case would have
        # gone on asserting the very classification this revision corrects,
        # which is the r233/r234 trap. `theo_series` is still genuinely dead:
        # unsubscribed at r118 after it took SPX's whole chain down.
        "theo_series":           {DAY: {}},                   # DEAD
        "shadow":                full("NVDA", "SPX", "QQQ"),  # LIVE (r280)
        "chain_snapshots":       {DAY: {}},                   # CONDITIONAL
        "candles":               full("NVDA", "SPX", "QQQ", "NVDA_EXT", "VIX"),
        "sentiment_probe":       full("SPX"),                 # UNDECLARED
    }
    s3 = FakeS3(bucket)
    d = wc.check_streams(s3, DAY, want)
    by = {r["stream"]: r for r in d["rows"]}

    # ══ S1 — A REAL GAP IS NAMED ══════════════════════════════════════════
    pc = by.get("derived_plan_check", {})
    check("S1 a panel box absent from an EVERY stream is a GAP that names it",
          pc.get("verdict") == "GAP" and pc.get("missing") == ["NVDA"],
          f"{pc.get('verdict')} {pc.get('missing')}")

    # ══ S2 — AND A SILENT BOX IS ONE DIAGNOSIS, NOT TWENTY ════════════════
    check("S2 a box that pushed nothing is reported as BOX_SILENT",
          d["silent"] == ["CVX"], str(d["silent"]))
    leaked = [r["stream"] for r in d["rows"] if "CVX" in r["missing"]]
    check("S2b CVX is NOT counted missing against every stream",
          not leaked, f"leaked into {leaked}")
    gaps = {r["stream"]: r["missing"] for r in d["rows"]
            if r["verdict"] == "GAP"}
    check("S2c the single-stream gap survives underneath the silent box, "
          "naming ONLY the box that is really missing",
          gaps.get("derived_plan_check") == ["NVDA"],
          str(gaps.get("derived_plan_check")))
    check("S2d a stream every live box DID push is not in the gap set",
          "trades" not in gaps and "signal_journal" not in gaps,
          str(sorted(gaps)[:4]))
    # 🔑 AND A DECLARED EVERY-STREAM WITH NO PARTITION AT ALL IS A GAP FOR
    # EVERY LIVE BOX — a stream that stopped landing fleet-wide is the loudest
    # thing this report can find, and it must not be softened into silence just
    # because there is nothing under the prefix to iterate.
    check("S2e a declared EVERY stream absent from the bucket gaps for every "
          "LIVE box, and still not for the silent one",
          gaps.get("greeks_series") == ["NVDA", "SPX", "QQQ"],
          str(gaps.get("greeks_series")))

    # ══ S3/S4 — ABSENCE THAT IS NOT A DEFECT ══════════════════════════════
    check("S3 a CONDITIONAL stream with no boxes is not a gap",
          by.get("chain_snapshots", {}).get("verdict") == "CONDITIONAL")
    check("S3b a CONDITIONAL stream that DID land is still not graded",
          by.get("derived_fire_snapshot", {}).get("verdict") == "CONDITIONAL")
    check("S4 a DEAD stream is not a gap",
          by.get("theo_series", {}).get("verdict") == "DEAD")
    check("S4b ...and `shadow` is no longer one of them",
          by.get("shadow", {}).get("verdict") == "OK",
          by.get("shadow", {}).get("verdict"))

    # ══ S5 — AND NOTHING IS QUIETLY SKIPPED ═══════════════════════════════
    # A tool that shrinks its own scope is as misleading as one that
    # over-reports — v1.1's own finding, applied to an unknown stream.
    check("S5 a stream in the bucket that the policy does not declare is "
          "reported as UNDECLARED",
          by.get("sentiment_probe", {}).get("verdict") == "UNDECLARED")

    # ══ S6 — THE GRAIN IS THE POINT ═══════════════════════════════════════
    # 🔴 5,389 derived_plan_check objects sat beside 2.38M rows because an
    # object count on a batched stream was read as a row count. The label is
    # what stops that, and 'pusher' says the row cannot speak to completeness.
    check("S6 a derived stream is labelled 'pusher', never 'record'",
          by.get("derived_plan_check", {}).get("grain") == "pusher")
    check("S6b a per-record stream is labelled 'record'",
          by.get("signal_journal", {}).get("grain") == "record")
    check("S6c and the two labels differ, which is the whole distinction",
          by["derived_plan_check"]["grain"] != by["signal_journal"]["grain"])

    # ══ S7 — THE TWO EXPLANATIONS v1.1 ADDED STILL HOLD ═══════════════════
    sun = wc.check_streams(FakeS3(bucket), "2026-09-06", want)   # a Sunday
    check("S7 a non-session day is NOT_A_SESSION and grades nothing",
          sun["verdict"] == "NOT_A_SESSION" and not sun["rows"])
    early = wc.check_streams(FakeS3({"trades": {"2026-07-01": {"SPX": 1}}}),
                             "2026-07-01", want)
    check("S7b a pre-collection day is PARTIAL_BY_DESIGN, never a gap",
          early["verdict"] == "PARTIAL_BY_DESIGN"
          and all(r["verdict"] == "PARTIAL_BY_DESIGN" for r in early["rows"]),
          early["verdict"])

    # ══ S8 — _EXT IS THE SAME SYMBOL'S TAPE, NOT ANOTHER BOX ══════════════
    # 🔴 r194's guard matched a name FORMAT rather than an IDENTITY and
    # proposed deleting the extended tape of every panel symbol.
    check("S8 NVDA_EXT normalises to NVDA rather than counting as a box",
          wc._base("NVDA_EXT") == "NVDA" and wc._base("NVDA") == "NVDA")

    # ══ S9 — THE PANEL IS THE AUTHORITY'S, AND AN EMPTY ONE REFUSES ═══════
    import selector
    check("S9 panel() returns selector.PANEL, not a copy",
          wc.panel() == list(selector.PANEL), str(wc.panel()[:3]))
    saved = selector.PANEL
    selector.PANEL = []
    try:
        wc.panel()
        check("S9b an empty PANEL refuses rather than grading against a guess",
              False, "returned without raising")
    except Exception:
        check("S9b an empty PANEL refuses rather than grading against a guess",
              True)
    finally:
        selector.PANEL = saved

    # ══ S10 — THE COST CLAIM, COUNTED RATHER THAN ASSERTED ════════════════
    # dtp r253: the way to pin a fetch cost is to count fetches.
    cheap = FakeS3(bucket)
    wc.check_streams(cheap, DAY, want)
    undelimited = [p for p, delim in cheap.calls if delim is None]
    check("S10 presence does NOT page over objects",
          not undelimited, f"{len(undelimited)} object listing(s)")
    pricey = FakeS3(bucket)
    wc.check_streams(pricey, DAY, want, counts=True)
    check("S10b --counts is what pages objects, and only then",
          any(delim is None for _p, delim in pricey.calls))

    # ══ S11 — WIDTH, MEASURED ON THE REAL RENDERED LINE ═══════════════════
    # r210's Q11 rebuilt the format string inside the test and measured its own
    # copy (C.23); this captures the actual output. And r216 is the other half:
    # Q11 measured width and never VALUES, which is exactly how a units bug rode
    # along inside a formatting change — so S11b reads the numbers back too.
    import io, contextlib
    import selector as _sel
    _saved = _sel.PANEL
    _sel.PANEL = want
    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            wc.report_streams(FakeS3(bucket), [DAY], counts=True)
        lines = buf.getvalue().splitlines()
    finally:
        _sel.PANEL = _saved
    widest = max(len(l) for l in lines)
    check("S11 no rendered line exceeds 90 chars (Termius on a phone)",
          widest <= 90, f"widest {widest}")
    pc_line = [l for l in lines if "derived_plan_check" in l]
    check("S11b the plan_check row still names NVDA and its 6 objects, so a "
          "width change cannot silently alter what it says",
          pc_line and "NVDA" in pc_line[0] and "6o" in pc_line[0],
          pc_line[0].strip() if pc_line else "row not rendered")
    check("S11c a fleet-wide absence collapses rather than listing every box",
          any("MISS: ALL" in l for l in lines))

    # ══ S12-S14 — THE FIRST REAL RUN'S CORRECTIONS ════════════════════════
    # 2026-09-01..09-04 raised nine flags and SEVEN were my policy table.
    DAY2 = "2026-09-03"
    want2 = ["NVDA", "SPX", "QQQ"]
    b2 = {
        # SPX writes no prints (cash index, r95); the others do.
        "prints":  {DAY2: {"NVDA": 3, "QQQ": 3}},
        # nobody wrote trades — CDC, so nobody traded. Not a gap.
        "trades":  {DAY2: {}},
        # shadow is LIVE, so a box missing from it IS a gap now.
        "shadow":  {DAY2: {"NVDA": 3, "SPX": 3}},
        "candles": {DAY2: {s_: 1 for s_ in want2}},
    }
    d2 = wc.check_streams(FakeS3(b2), DAY2, want2)
    by2 = {r["stream"]: r for r in d2["rows"]}

    check("S12 SPX absent from `prints` is NOT a gap — a cash index publishes "
          "no TimeAndSale",
          by2.get("prints", {}).get("verdict") == "OK",
          f"{by2.get('prints', {}).get('verdict')} {by2.get('prints', {}).get('missing')}")
    # 🔑 AND THE EXCEPTION IS PER-BOX, NOT A LOOSENING OF THE STREAM. If the
    # excused symbol had simply switched the stream off, the report would stop
    # noticing the day the other fourteen went quiet — which is the whole
    # failure this stream exists to catch.
    d2b = wc.check_streams(FakeS3({**b2, "prints": {DAY2: {"NVDA": 3}}}),
                           DAY2, want2)
    pr = {r["stream"]: r for r in d2b["rows"]}["prints"]
    check("S12b ...but a NON-excused box absent from it still is",
          pr["verdict"] == "GAP" and pr["missing"] == ["QQQ"],
          f"{pr['verdict']} {pr['missing']}")

    check("S13 no box writing `trades` is NOT a gap — CDC, so nobody traded",
          by2.get("trades", {}).get("verdict") == "CONDITIONAL")

    # 🔴 S14 — `shadow` WAS DECLARED DEAD AND IS LIVE. Measured on QQQ
    # 2026-09-05: 32 date dirs, newest 09-04, shadow unit present; and 15 boxes
    # push it every session in the bucket. Under v1.2 this case returned DEAD.
    check("S14 a box absent from `shadow` is a gap — it is live, not dead",
          by2.get("shadow", {}).get("verdict") == "GAP"
          and by2.get("shadow", {}).get("missing") == ["QQQ"],
          f"{by2.get('shadow', {}).get('verdict')} {by2.get('shadow', {}).get('missing')}")

    print()
    if FAILED:
        print(f"RED — {len(FAILED)} failed: {', '.join(FAILED)}")
        return 1
    print("GREEN — 29 checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
