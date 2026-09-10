#!/usr/bin/env python3
"""
day_trader_pro/tests/check_verify_line_fields.py  v1.0
v1.0  2026-09-10  dtp r347 / S3.26 — the VERIFY line must carry the field that
      explains the verdict.

🔴 WHY. `DRAIN_RE` captures nine fields and the panel printed four. The one it
discarded is `failed`, which decides WHY a box is SHORT:

  · r180's auto-heal runs ONLY when `total_failed == 0`
  · ANY single stage raising counts as one failure and blocks healing for the
    WHOLE box

So SHORT means either drift the heal could not reach (a prefix S3 has no
objects for) or a drain that failed and stopped the heal before it began —
two different faults with two different fixes, and no report could tell them
apart. On 2026-09-10 seven boxes came back SHORT the day after a fleet
reconcile and the question "did the heal run?" was unanswerable.

  V1  the parser still captures all nine fields (the regex is the contract)
  V2  the rendered VERIFY line carries failed, pushed AND drained
  V3  a missing field renders as '?' — never blank, never 0, because "we do
      not know" and "zero" are different claims
  V4  the existing fields survive: verdict, short, local, s3
"""
import io
import os
import sys
from contextlib import redirect_stdout

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
FAILS = []


def check(name, ok, detail=""):
    print("  {:<4} {}  {}".format(name, "PASS" if ok else "FAIL", detail))
    if not ok:
        FAILS.append(name)


LINE = ("DRAIN host=ip-172-31-41-118 sym=NVDA drained=yes pushed=2 failed=0 "
        "prefixes=637 local=117708 s3=117484 short=26 SHORT")


def main():
    try:
        import eod_conductor_v2 as C
    except Exception as exc:                                    # noqa: BLE001
        print("  FAIL  conductor did not import: {}".format(exc))
        return 1

    m = C.DRAIN_RE.search(LINE)
    g = m.groupdict() if m else {}
    check("V1", m is not None and {"drained", "pushed", "failed", "short",
                                   "local", "s3", "verdict"} <= set(g),
          "captured {}".format(sorted(g)) if m else "regex did not match")

    buf = io.StringIO()
    with redirect_stdout(buf):
        C._log("VERIFY", "{:<6} {:<10} short={} local={} s3={} drained={} "
                         "pushed={} failed={}".format(
                             "NVDA", g.get("verdict"), g.get("short"),
                             g.get("local"), g.get("s3"), g.get("drained"),
                             g.get("pushed"), g.get("failed")))
    rendered = buf.getvalue()

    # the REAL line, from the file, not a reconstruction
    src = open(os.path.join(REPO, "eod_conductor_v2.py"), encoding="utf-8").read()
    body = src.split('_log("VERIFY", f"{sym:<6}', 1)[-1][:600]
    have = [f for f in ("failed=", "pushed=", "drained=") if f in body]
    check("V2", len(have) == 3, "line carries {}".format(have))

    check("V3", "'?'" in body or '"?"' in body,
          "missing fields render as '?'")

    keep = [f for f in ("short=", "local=", "s3=", "verdict")
            if f in body]
    check("V4", len(keep) == 4, "still carries {}".format(keep))

    print("")
    if FAILS:
        print("FAILED: {}".format(", ".join(FAILS)))
        return 1
    print("ALL PASS (4)  sample: {}".format(rendered.strip()[:96]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
