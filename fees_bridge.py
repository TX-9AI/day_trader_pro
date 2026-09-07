#!/usr/bin/env python3
"""
day_trader_pro/fees_bridge.py  v1.0
v1.0  2026-09-07  dtp r312 / FEE.7 — ONE OWNER FOR THE otv4 FEE IMPORT.

`fees.py` is control-only and lives in otv4/tests (WA §34); the reports that
consume it live here. r311 inlined the path resolution and the None-safe
wrapper into `trade_report.py`, and report 46 needs exactly the same two
things — so it moves here rather than being copied. Two copies of a path
resolution is the drift this repo keeps finding in its own code (§35's
two-documents-one-job, C.17's one-dedup-rule).

⚠️ `r_ledger.py` DOES NOT USE THIS and should not: it sits in otv4/tests
beside `fees.py` and imports it directly. A bridge exists to cross a repo
boundary, and adding a hop where there is no boundary is the same duplication
one level up.

🔴 IT FAILS LOUD. When the model cannot be imported `bucket_fees` returns
(None, len(rows)) — never (0.0, 0) — because "no fees" and "no fee model" are
different facts and the second one silently flatters the book. Callers render
None as `n/a` and must never coerce it.
"""
from __future__ import annotations

import os
import sys
from typing import List

_OTV4 = os.environ.get("DTP_OTV4_DIR", os.path.expanduser("~/options-trader-v4"))
_TESTS = os.path.join(_OTV4, "tests")
if _TESTS not in sys.path:
    sys.path.insert(0, _TESTS)

try:
    import fees as _fees
    FEES_ERR = None
except Exception as _e:                                          # noqa: BLE001
    _fees = None
    FEES_ERR = f"{type(_e).__name__}: {_e} (looked in {_TESTS})"


def available() -> bool:
    return _fees is not None


def bucket_fees(rows: List[dict]):
    """-> (total_fees_usd, n_unpriced), or (None, len(rows)) if unavailable.

    ⚠️ None IS NOT ZERO. Callers render it as `n/a`.
    """
    if _fees is None:
        return None, len(rows)
    roll = _fees.total_fees_usd(rows)
    return roll["total_fees"], roll["unpriced"]


def trade_fee(row: dict):
    """Fee for ONE trade, or None. Used where a running total is accumulated
    row by row rather than over a list."""
    if _fees is None:
        return None
    res = _fees.fees_for(row)
    return None if isinstance(res, _fees.Unpriced) else res.total
