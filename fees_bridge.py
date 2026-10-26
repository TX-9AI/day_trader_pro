#!/usr/bin/env python3
"""
day_trader_pro/fees_bridge.py  v1.1
v1.1  2026-10-25  (OTV5 paths) — THE FEE MODEL IS IMPORTED FROM ~/OTV5/tests, THE FLEET'S REPO. It read
      ~/options-trader-v4/tests/fees.py, the retired tree; OTV5's tests/fees.py is the same code (diff: the v5.0
      header line only), so every fee figure is unchanged. The checkout is `DTP_CONTROL_REPO` (default ~/OTV5),
      the one name orchestrator's parity line already uses for it - DTP_OTV4_DIR no longer moves the fee model.
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

_REPO = os.path.expanduser(os.environ.get("DTP_CONTROL_REPO", "~/OTV5"))   # v1.1: was ~/options-trader-v4
_TESTS = os.path.join(_REPO, "tests")
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
