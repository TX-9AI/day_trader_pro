#!/usr/bin/env python3
# day_trader_pro/tests/check_stream_exemptions.py — v1.0
# v1.0 (2026-09-21) — r413 / OPS.38. A STREAM MAY ONLY BE CALLED DEAD WITH ITS
#   REASON ATTACHED, BECAUSE THIS PROJECT HAS ACTED ON A WRONG ONE.
#   🔴 E2 IS THE CHECK THAT OUTLIVES THIS ROW, AND THE HISTORY IS WHY.
#   [[S3.13]] deleted **492,945 raw/shadow objects** on a reading that the
#   stream was dead. It was not. [[DOC.25]] then found `WRITE_MAP`'s
#   dead-weight list naming **EIGHT LIVE STREAMS** — a list whose own document
#   says a table nobody reads is where that question gets asked. And r280
#   REFUSED an earlier attempt to mark `shadow` dead, on evidence: QQQ held 32
#   date dirs with the unit live ([[ASK.2]]).
#   🔑 SO THE DANGEROUS ENTRY IS THE UNDOCUMENTED ONE. A board showing zeros
#   is not grounds; a RULING is. E2 requires every DEAD classification to
#   carry a revision or a date in its reason, so the next author cannot retire
#   a stream on a quiet afternoon and leave nothing for the person who has to
#   decide, a year later, whether the silence was ordered or an outage.
#   ⚠️ E1 IS THE ROW'S OWN CASE AND WILL AGE; E2 WILL NOT.
"""Gate: DEAD is a documented decision, never an observed absence.

E1   shadow is DEAD and says WHO decided and WHEN
E2   CONTROL — every DEAD entry carries a revision or a date
E3   DEAD is not among the verdicts that count as a gap
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
SRC = os.path.join(ROOT, "warehouse_coverage.py")

_fails = []


def ck(tag, ok, msg=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {tag}  {msg}")
    if not ok:
        _fails.append(tag)


# A reason earns its DEAD by naming a revision (r123 / v1.8) or an ISO date.
# ⚠️ THE SUFFIX IS PART OF THE REVISION. The first cut was `\br\d{2,4}\b`,
# which REJECTED `r125b` — a real citation on `underlying_series` — because
# the trailing letter denies the word boundary. The check was wrong and the
# data was right, found by running it. A canary that flags correct provenance
# is the shape that gets loosened until it misses the real thing (§20).
PROV = re.compile(r"\br\d{2,4}[a-z]?\b|\bv\d+\.\d+\b|\d{4}-\d{2}-\d{2}")


def main():
    try:
        import warehouse_coverage as wc
    except Exception as e:                                      # noqa: BLE001
        ck("E1", False, f"warehouse_coverage did not import: {e}")
        print(f"\nFAILED {len(_fails)}: {', '.join(_fails)}")
        return 1

    streams = getattr(wc, "STREAM_POLICY", None)
    if not isinstance(streams, dict):
        ck("E1", False, "STREAM_POLICY table not found — the classification moved")
        print(f"\nFAILED {len(_fails)}: {', '.join(_fails)}")
        return 1

    # ── E1 — this row's own case.
    cls = streams.get("shadow", (None, None, ""))
    ck("E1", cls[0] == "DEAD" and PROV.search(cls[2] or ""),
       f"shadow -> {cls[0]}, reason carries provenance="
       f"{bool(PROV.search(cls[2] or ''))}")

    # ── E2 — CONTROL, green at HEAD, and the one that generalises.
    dead = {k: v for k, v in streams.items() if v[0] == "DEAD"}
    undocumented = [k for k, v in dead.items()
                    if not PROV.search(v[2] or "")]
    ck("E2", not undocumented,
       f"CONTROL — all {len(dead)} DEAD entries carry a revision or date"
       if not undocumented else
       f"DEAD without provenance: {undocumented} — a stream retired with no "
       f"record is indistinguishable from an outage nobody chased (S3.13)")

    # ── E3 — DEAD must not count as a gap.
    # ⚠️ SOURCE-ANCHORED AND SAID SO. The gap counter's verdict tuple is
    # inline in the renderer, so this asserts the tuple rather than driving a
    # full S3 walk. The BEHAVIOURAL proof is the live board, recorded in the
    # row: after this change the run reports 0 gaps with shadow rendering `·`
    # beside its reason. A check that needed the network would be skipped.
    src = open(SRC, encoding="utf-8", errors="replace").read()
    m = re.search(r'r\["verdict"\]\s+in\s+\(([^)]*)\)\s*:\s*\n\s*bad\s*\+=', src)
    tup = m.group(1) if m else ""
    ck("E3", bool(m) and '"DEAD"' not in tup,
       f"gap counter keys on ({tup.strip()}) — DEAD excluded"
       if m else "could not locate the gap counter — it moved, re-anchor E3")

    print()
    if _fails:
        print(f"FAILED {len(_fails)}: {', '.join(_fails)}")
        return 1
    print("check_stream_exemptions: all checks pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
