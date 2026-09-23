#!/usr/bin/env python3
# day_trader_pro/tests/check_forward_scan_series.py — v1.0
# v1.0 (2026-09-23) — r417 / WH.20. THE FORWARD SCAN REACHES THE STREAMS THAT
#   NEED IT.
#   🔴 THE DEFECT. `warehouse_cache.load()` has scanned a forward window and
#   kept rows by their OWN ET day since r290/S3.21 — but it gated that on
#   `dt.startswith("derived_")`, justified by "a raw stream is partitioned by
#   the day it describes". That is TRUE of `candles`, `ohlc` and `trades`,
#   whose pushers derive `dt=` from the row, and FALSE of every
#   `push_series` table, which stamped `dt=` from `datetime.now(ET)` at PUSH
#   time. So the correction was denied to precisely the streams carrying the
#   skew.
#   📊 MEASURED IN THE BUCKET 2026-09-23, NOT INFERRED: 566 of 224,336 raw
#   series objects sat in the wrong `dt=` — `quote_series` 389,
#   `surface_series` 146 — and QQQ's 2026-09-22 session was split 6 objects
#   into dt=2026-09-22 and 50 into dt=2026-09-23.
#   ⚠️ `surface_series` IS THE ONE THAT PROVES THE NAME TEST CANNOT WORK: it is
#   pushed with ns="dseries" and still writes `raw/surface_series/`, so
#   `startswith("derived_")` missed it. The namespace and the key prefix are
#   different things, and only the key decides what a reader lists.
#   🔑 F3 IS A DECLARED CONTROL: `candles` and `ohlc` must KEEP fwd=0. A
#   forward scan there would pull genuinely later sessions in, and the fix
#   must not trade one silent wrong number for another.
"""Gate: the forward window covers push-day-filed streams, and only those.

F1   PUSH_DAY_FILED matches s3_push's SERIES_TABLES + DERIVED_SERIES_TABLES
F2   quote_series / surface_series GET the forward window
F3   candles / ohlc / trades keep fwd=0                          [control]
F4   an unknown datatype defaults to 0 rather than scanning      [control]
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

OTV4 = os.environ.get("OT_V4_ROOT", os.path.expanduser("~/options-trader-v4"))

_fails = []


def ck(tag, ok, msg=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {tag}  {msg}")
    if not ok:
        _fails.append(tag)


def _tables_from_source():
    """SERIES_TABLES + DERIVED_SERIES_TABLES, read out of otv4's s3_push."""
    path = os.path.join(OTV4, "warehouse", "s3_push.py")
    src = open(path, encoding="utf-8").read()
    got = set()
    for name in ("SERIES_TABLES", "DERIVED_SERIES_TABLES"):
        m = re.search(name + r"\s*=\s*\((.*?)\)", src, re.S)
        if not m:
            raise RuntimeError(f"{name} not found in {path}")
        got |= set(re.findall(r'"([A-Za-z_]+)"', m.group(1)))
    return got


def main():
    try:
        import warehouse_cache as WC
    except Exception as exc:
        ck("F0", False, f"cannot import warehouse_cache ({exc})")
        print("\nRED — 1 check(s) failed: F0")
        return 1

    filed = getattr(WC, "PUSH_DAY_FILED", None)
    fw = getattr(WC, "forward_window", None)

    # ── F1 — the list must not drift from the pusher's own tables ────────
    if filed is None:
        ck("F1", False, "PUSH_DAY_FILED is absent")
    else:
        try:
            want = _tables_from_source()
            missing = want - set(filed)
            extra = set(filed) - want
            ck("F1", not missing and not extra,
               f"missing={sorted(missing)} extra={sorted(extra)}")
        except Exception as exc:
            ck("F1", False, f"could not read otv4 s3_push ({exc}); "
                            f"set OT_V4_ROOT")

    if fw is None:
        ck("F2", False, "forward_window is absent")
        ck("F3", False, "forward_window is absent")
        ck("F4", False, "forward_window is absent")
    else:
        # ── F2 — the skewed streams get the window ──────────────────────
        got = {t: fw(t, 3) for t in ("quote_series", "surface_series",
                                     "prints", "indicator_series")}
        ck("F2", all(v == 3 for v in got.values()), f"{got} (want all 3)")

        # ── F3 — CONTROL: row-partitioned raw streams keep 0 ────────────
        got = {t: fw(t, 3) for t in ("candles", "ohlc", "trades",
                                     "circuit_breaker")}
        ck("F3", all(v == 0 for v in got.values()), f"{got} (want all 0)")

        # ── F4 — CONTROL: derived_ still works, unknown defaults to 0 ───
        ck("F4", fw("derived_plan_tick", 3) == 3 and fw("who_knows", 3) == 0,
           f"derived_plan_tick={fw('derived_plan_tick', 3)} "
           f"who_knows={fw('who_knows', 3)}")

    if _fails:
        print(f"\nRED — {len(_fails)} check(s) failed: {' '.join(_fails)}")
        return 1
    print("\nGREEN — the forward window covers the push-day-filed streams")
    return 0


if __name__ == "__main__":
    sys.exit(main())
