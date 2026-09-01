# WAREHOUSE_MAP.md — what is in the bucket, and where

**Generated 2026-09-01 19:02 ET by `tools/warehouse_map.py`. Do not hand-edit.**

🔑 **GENERATED FROM THE BUCKET, NOT FROM THE WRITERS.** A map derived from the push code states what we INTENDED to store; this states what is actually there. When they disagree, that disagreement is the finding — `--check` fails on it rather than quietly re-rendering.

⚠️ **KEY LAYOUT IS HIVE-STYLE AND FIXED:** `raw/<datatype>/dt=<YYYY-MM-DD>/sym=<SYM>/<epoch_ms>-<sha16>.json`. `dt=` is the **ET trading day** in every stream — if it ever meant something different in one of them, joins across streams would return silently wrong rows rather than none.

⚠️ **`raw/` NEVER DELETES.** Retention purging happens on the BOX (r81/r162); the bucket is the durable copy. Noncurrent versions accumulate with no lifecycle rule — `warehouse_cost.py --versions` counts them.

**Totals:** 1,116,870 objects · 66.79 GB

| prefix | objects | GB | days | first | last | holds |
|---|---:|---:|---:|---|---|---|
| `raw/candles` | 63,463 | 0.055 | 18 | 2026-08-12 | 2026-09-01 | OHLC per tenor; SYM_EXT holds non-RTH bars |
| `raw/chain_snapshots` | 25,173 | 1.159 | 28 | 2026-07-24 | 2026-09-01 | option chain marks at fire time |
| `raw/derived_fire_snapshot` | 165 | 0.000 | 6 | 2026-08-25 | 2026-09-01 | **UNDOCUMENTED — add it to MEANING** |
| `raw/derived_gate_disposition` | 3,450 | 0.002 | 9 | 2026-08-24 | 2026-09-01 | **UNDOCUMENTED — add it to MEANING** |
| `raw/derived_level_ledger` | 11,834 | 0.029 | 9 | 2026-08-24 | 2026-09-01 | **UNDOCUMENTED — add it to MEANING** |
| `raw/derived_plan_check` | 5,389 | 0.469 | 7 | 2026-08-26 | 2026-09-01 | **UNDOCUMENTED — add it to MEANING** |
| `raw/derived_plan_ledger` | 1,001 | 0.012 | 7 | 2026-08-24 | 2026-09-01 | **UNDOCUMENTED — add it to MEANING** |
| `raw/derived_plan_tick` | 7,189 | 0.330 | 7 | 2026-08-26 | 2026-09-01 | **UNDOCUMENTED — add it to MEANING** |
| `raw/derived_strategy_note` | 9,221 | 1.542 | 9 | 2026-08-24 | 2026-09-01 | **UNDOCUMENTED — add it to MEANING** |
| `raw/eod` | 372 | 0.002 | 17 | 2026-08-07 | 2026-09-01 | **UNDOCUMENTED — add it to MEANING** |
| `raw/fork_series` | 3,404 | 0.039 | 4 | 2026-08-29 | 2026-09-01 | pitchfork state per tenor, with reject reasons |
| `raw/greeks_series` | 11,123 | 4.036 | 9 | 2026-08-24 | 2026-09-01 | per-contract greeks, full fidelity |
| `raw/indicator_series` | 3,403 | 0.059 | 4 | 2026-08-29 | 2026-09-01 | ADX / ATR / EMA / VWAP accumulators |
| `raw/last_trade` | 12,304 | 1.201 | 9 | 2026-08-24 | 2026-09-01 | Trade events |
| `raw/liquidity_ledger` | 12,140 | 0.019 | 13 | 2026-08-14 | 2026-09-01 | **UNDOCUMENTED — add it to MEANING** |
| `raw/ohlc` | 599 | 0.014 | 40 | 2026-07-08 | 2026-09-01 | **UNDOCUMENTED — add it to MEANING** |
| `raw/orb_range` | 55 | 0.000 | 2 | 2026-08-13 | 2026-08-14 | **UNDOCUMENTED — add it to MEANING** |
| `raw/prints` | 11,642 | 9.463 | 9 | 2026-08-24 | 2026-09-01 | TimeAndSale, with the venue's aggressor tag |
| `raw/quote_series` | 9,143 | 46.058 | 9 | 2026-08-24 | 2026-09-01 | per-contract bid/ask/sizes |
| `raw/session_summary` | 2,472 | 0.005 | 9 | 2026-08-24 | 2026-09-01 | Summary events (prev-day close, etc.) |
| `raw/shadow` | 160,978 | 0.128 | 7 | 2026-08-24 | 2026-09-01 | sweep-precursor velocity primitives |
| `raw/signal_journal` | 750,540 | 0.407 | 34 | 2026-07-20 | 2026-09-01 | **UNDOCUMENTED — add it to MEANING** |
| `raw/surface_series` | 3,097 | 1.708 | 4 | 2026-08-29 | 2026-09-01 | charm, vanna, GEX |
| `raw/theo_series` | 117 | 0.024 | 2 | 2026-08-24 | 2026-08-25 | TheoPrice — writer retained, unsubscribed at r118 |
| `raw/trades` | 8,596 | 0.022 | 38 | 2026-07-06 | 2026-09-01 | closed + open trade rows, per box (the book) |

**Documented but ABSENT from the bucket** — a stream that never wrote, or one that was retired:

- `raw/character_ledger` — tape character state with duration
- `raw/exit_counterfactual` — flow exits that WOULD have fired; acts on nothing
- `raw/fire_snapshot` — the derived vector at every fill
- `raw/gate_disposition` — which rung refused a strategy, edge-triggered
- `raw/level_ledger` — liquidity levels, operator lifecycle
- `raw/plan_check` — long format: one row per VARIABLE per plan per tick
- `raw/plan_ledger` — plan lifecycle — intent, terminal state, trade join
- `raw/plan_tick` — the spine: one row per plan per tick
- `raw/strategy_note` — one row per strategy EVALUATION
- `raw/underlying_series` — Underlying — published nothing on either symbol space
