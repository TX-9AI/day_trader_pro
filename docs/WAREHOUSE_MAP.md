# WAREHOUSE_MAP.md — what is in the bucket, and where

**Generated 2026-09-01 19:18 ET by `tools/warehouse_map.py`. Do not hand-edit.**

🔑 **GENERATED FROM THE BUCKET, NOT FROM THE WRITERS.** A map derived from the push code states what we INTENDED to store; this states what is actually there. When they disagree, that disagreement is the finding — `--check` fails on it rather than quietly re-rendering.

⚠️ **KEY LAYOUT IS HIVE-STYLE AND FIXED:** `raw/<datatype>/dt=<YYYY-MM-DD>/sym=<SYM>/<epoch_ms>-<sha16>.json`. `dt=` is the **ET trading day** in every stream — if it ever meant something different in one of them, joins across streams would return silently wrong rows rather than none.

⚠️ **`raw/` NEVER DELETES.** Retention purging happens on the BOX (r81/r162); the bucket is the durable copy. Noncurrent versions accumulate with no lifecycle rule — `warehouse_cost.py --versions` counts them.

**Totals:** 1,117,583 objects · 66.80 GB

| prefix | objects | GB | days | first | last | written by | holds |
|---|---:|---:|---:|---|---|---|---|
| `raw/candles` | 63,555 | 0.055 | 18 | 2026-08-12 | 2026-09-01 | `push_candles <- feed_store.db` | OHLC per tenor; sym=<SYM>_EXT holds non-RTH bars |
| `raw/chain_snapshots` | 25,173 | 1.159 | 28 | 2026-07-24 | 2026-09-01 | `push_file (DATATYPE 'chain_snapshot' + 's')` | option chain marks at fire time |
| `raw/derived_fire_snapshot` | 165 | 0.000 | 6 | 2026-08-25 | 2026-09-01 | `push_derived` | the derived vector at every fill |
| `raw/derived_gate_disposition` | 3,450 | 0.002 | 9 | 2026-08-24 | 2026-09-01 | `push_derived` | which rung refused a strategy, edge-triggered |
| `raw/derived_level_ledger` | 11,879 | 0.030 | 9 | 2026-08-24 | 2026-09-01 | `push_derived` | liquidity levels, operator lifecycle |
| `raw/derived_plan_check` | 5,389 | 0.469 | 7 | 2026-08-26 | 2026-09-01 | `push_derived` | long format: one row per VARIABLE per plan per tick |
| `raw/derived_plan_ledger` | 1,001 | 0.012 | 7 | 2026-08-24 | 2026-09-01 | `push_derived` | plan lifecycle — intent, terminal state, trade join |
| `raw/derived_plan_tick` | 7,234 | 0.331 | 7 | 2026-08-26 | 2026-09-01 | `push_derived` | the spine: one row per plan per tick |
| `raw/derived_strategy_note` | 9,254 | 1.543 | 9 | 2026-08-24 | 2026-09-01 | `push_derived` | one row per strategy EVALUATION |
| `raw/eod` | 372 | 0.002 | 17 | 2026-08-07 | 2026-09-01 | `push_whole_files <- ~/eod` | end-of-day artifacts written by the EOD chain |
| `raw/fork_series` | 3,450 | 0.040 | 4 | 2026-08-29 | 2026-09-01 | `push_series ns=dseries` | pitchfork state per tenor, with reject reasons |
| `raw/greeks_series` | 11,161 | 4.044 | 9 | 2026-08-24 | 2026-09-01 | `push_series` | per-contract greeks, full fidelity |
| `raw/indicator_series` | 3,450 | 0.059 | 4 | 2026-08-29 | 2026-09-01 | `push_series ns=dseries` | ADX / ATR / EMA / VWAP accumulators |
| `raw/last_trade` | 12,350 | 1.202 | 9 | 2026-08-24 | 2026-09-01 | `push_series` | Trade events |
| `raw/liquidity_ledger` | 12,140 | 0.019 | 13 | 2026-08-14 | 2026-09-01 | `push_whole_files <- ~/options-trader/data/liquidity_ledger/*.json` | the liquidity map as the box wrote it |
| `raw/ohlc` | 599 | 0.014 | 40 | 2026-07-08 | 2026-09-01 | `push_whole_files <- ~/options-trader/data/OHLC/*.csv` | CSV OHLC exports; NOT the same stream as raw/candles |
| `raw/orb_range` | 55 | 0.000 | 2 | 2026-08-13 | 2026-08-14 | `RETIRED — s3_push v1.8, 2026-08-16` | stopped growing; nothing consumed it and the range recomputes from candles |
| `raw/prints` | 11,689 | 9.464 | 9 | 2026-08-24 | 2026-09-01 | `push_series` | TimeAndSale, with the venue's aggressor tag |
| `raw/quote_series` | 9,143 | 46.058 | 9 | 2026-08-24 | 2026-09-01 | `push_series` | per-contract bid/ask/sizes |
| `raw/session_summary` | 2,472 | 0.005 | 9 | 2026-08-24 | 2026-09-01 | `push_series` | Summary events (prev-day close) |
| `raw/shadow` | 160,978 | 0.128 | 7 | 2026-08-24 | 2026-09-01 | `push_jsonl_tree <- ~/options-trader/data/shadow` | sweep-precursor velocity primitives |
| `raw/signal_journal` | 750,776 | 0.407 | 34 | 2026-07-20 | 2026-09-01 | `push_jsonl_tree <- ~/options-trader/data/signal_journal` | per-event signal journal |
| `raw/surface_series` | 3,135 | 1.711 | 4 | 2026-08-29 | 2026-09-01 | `push_series ns=dseries` | charm, vanna, GEX |
| `raw/theo_series` | 117 | 0.024 | 2 | 2026-08-24 | 2026-08-25 | `push_series` | TheoPrice — writer retained, unsubscribed at r118 |
| `raw/trades` | 8,596 | 0.022 | 38 | 2026-07-06 | 2026-09-01 | `push_trades <- trades.db` | closed + open trade rows, per box |

**Documented but ABSENT from the bucket.** Each of these has a live writer in `s3_push.py` (or a recorded retirement) and has produced NO objects. That is a finding, not a gap in this file: `push_derived` skips a table that is absent on the box, so a stream configured to push and never seen here has either no table or no rows — and nothing says which without looking.

- `raw/circuit_breaker` — breaker trips  (writer: `push_table <- trades.db:circuit_breaker_events`)
- `raw/derived_character_ledger` — tape character state with duration  (writer: `push_derived`)
- `raw/derived_exit_counterfactual` — flow exits that WOULD have fired; acts on nothing  (writer: `push_derived`)
- `raw/orb_state` — captured ZERO objects in thirty days  (writer: `RETIRED — s3_push v1.8, 2026-08-16`)
- `raw/underlying_series` — Underlying — published nothing on either symbol space  (writer: `push_series`)
