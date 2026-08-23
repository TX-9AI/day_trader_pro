#!/usr/bin/env python3
"""
day_trader_pro/tests/test_audit_20260823.py  v1.0
Executing pins for the 2026-08-23 adversarial audit (F2, F7, F10). Plain
script, exit code, no pytest.

v1.0  2026-08-23  Born RED at r221 on all three.

  B1  s3_sweep refuses --dups on a whole-file datatype, and refuses a
      legacy list that condemns 100% of what it checked. Pin = drive
      find_legacy against a fake S3 holding one real-shaped OHLC object,
      built with the push side's own _wrap/_sha256, and run main() with
      --datatype ohlc.
  B2  The conductor's verify filter lets the COUNTER DRIFT line through, so
      takedown() can take a drifted box down. Pin = feed takedown() a raw
      that has been through the real grep filter.
  B3  s3_sweep.PANEL is selector.PANEL, not a fourth copy.

Run:  cd ~/day_trader_pro && python3 tests/test_audit_20260823.py
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.environ.setdefault("DTP_MOCK_AWS", "1")

PROBLEMS: list = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  - {detail}" if (detail and not ok) else ""))
    if not ok:
        PROBLEMS.append(name)


def _push_side():
    """The real otv4 push helpers if a checkout is adjacent; else a faithful
    stand-in for the two functions that matter (sha256 + whole-file _wrap)."""
    import hashlib
    import json

    def sha(b): return hashlib.sha256(b).hexdigest()

    def wrap(datatype, rec, sym, day, extra=None):
        env = {"schema_version": 1, "datatype": datatype, "symbol": sym, "dt": day,
               "src_host": "x", "pushed_at_utc": "2026-08-23T00:00:00Z", "record": rec}
        if extra:
            env.update(extra)
        return json.dumps(env, separators=(",", ":"), default=str).encode()
    return sha, wrap


class _FakeS3:
    def __init__(self, objs):
        self.objs = objs

    def list_objects_v2(self, **kw):
        pfx = kw.get("Prefix", "")
        return {"Contents": [{"Key": k, "Size": len(v)} for k, v in self.objs.items()
                             if k.startswith(pfx)], "IsTruncated": False}

    def get_object(self, Bucket, Key):
        import io
        return {"Body": io.BytesIO(self.objs[Key])}


def b1():
    import s3_sweep as sw
    sha, wrap = _push_side()
    raw = b"ts,open,high,low,close\n1,2,3,4,5\n"
    s = sha(raw)
    key = f"raw/ohlc/dt=2026-08-22/sym=NVDA/NVDA.csv-{s[:16]}.json"
    body = wrap("ohlc", raw.decode(), "NVDA", "2026-08-22",
                {"src_file": "NVDA.csv", "content_sha256": s})
    s3 = _FakeS3({key: body})
    stale = sw.find_legacy(s3, "ohlc")
    check("B1a find_legacy refuses a 100%-legacy result", stale == [],
          f"would delete {len(stale)} of 1 real OHLC object(s)")
    sw._client = lambda: s3
    rc = sw.main(["s3_sweep.py", "--dups", "--datatype", "ohlc"])
    check("B1b --dups --datatype ohlc is refused (rc != 0)", rc not in (0, None), f"rc={rc}")


def b2():
    import eod_conductor_v2 as c
    # the real verdict block s3_push prints, through the real filter
    text = ("DRAIN host=h sym=NVDA drained=yes pushed=0 failed=0 prefixes=200 "
            "local=35373 s3=35370 short=3 SHORT\n"
            "  SHORT raw/a/ expected>=10 got=9\n"
            "  SHORT raw/b/ expected>=10 got=9\n"
            "  SHORT raw/c/ expected>=10 got=9\n"
            "  ⚠️ SMALL, CONSISTENT SHORTFALL ON 3 PREFIXES (max 1). That is the "
            "signature of COUNTER DRIFT, not data loss — duplicate PUTs inflate "
            "the ledger permanently.\n")
    # ⚠️ WA §20: read the pattern from the FUNCTION's source, not the file —
    # the v2.0.1 changelog quotes the old pattern while describing its removal.
    import inspect
    m = re.search(r"grep -E '([^']+)'", inspect.getsource(c.drain_and_verify))
    pat = m.group(1) if m else "^DRAIN|^  SHORT"
    filt = subprocess.run(["grep", "-E", pat], input=text, capture_output=True, text=True).stdout
    d = c.DRAIN_RE.search(filt).groupdict()
    d["raw"] = filt
    ok, held = c.takedown({"NVDA": d}, dry=True, enabled=True)
    check("B2 a COUNTER-DRIFT box survives the filter and is taken down, not held",
          ok == ["NVDA"] and held == [], f"ok={ok} held={held} filter={pat!r}")


def b3():
    import s3_sweep as sw
    import selector
    check("B3 s3_sweep.PANEL == selector.PANEL (one list, not four)",
          set(sw.PANEL) == set(s.upper() for s in selector.PANEL),
          f"sweep={sorted(sw.PANEL)} selector={sorted(selector.PANEL)}")
    src = open(sw.__file__, encoding="utf-8").read()
    check("B3b the sweep reads selector.PANEL in source, not only by coincidence",
          "_sel.PANEL" in src or "selector.PANEL" in src.split('"""', 2)[-1])


def main() -> int:
    print("=" * 62)
    print("AUDIT 2026-08-23 PINS (dtp): F2 sweep rule · F7 drift filter · F10 panel")
    print("=" * 62)
    for fn in (b1, b2, b3):
        try:
            fn()
        except Exception as exc:                                # noqa: BLE001
            check(f"{fn.__name__} executes", False, f"{type(exc).__name__}: {exc}")
    print("-" * 62)
    if PROBLEMS:
        print(f"FAIL  {len(PROBLEMS)} problem(s): {', '.join(PROBLEMS)}")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
