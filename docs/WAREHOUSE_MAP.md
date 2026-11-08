# WAREHOUSE_MAP.md — what is in the bucket, and where

**Generated 2026-11-08 05:42 ET by `tools/warehouse_map.py`. Do not hand-edit.**

🔑 **GENERATED FROM THE BUCKET, NOT FROM THE WRITERS.** A map derived from the push code states what we INTENDED to store; this states what is actually there. When they disagree, that disagreement is the finding — `--check` fails on it rather than quietly re-rendering.

⚠️ **KEY LAYOUT IS HIVE-STYLE AND FIXED:** `raw/<datatype>/dt=<YYYY-MM-DD>/sym=<SYM>/<epoch_ms>-<sha16>.json`. `dt=` is the **ET trading day** in every stream — if it ever meant something different in one of them, joins across streams would return silently wrong rows rather than none.

⚠️ **`raw/` NEVER DELETES.** Retention purging happens on the BOX (r81/r162); the bucket is the durable copy. Noncurrent versions accumulate with no lifecycle rule — `warehouse_cost.py --versions` counts them.

**Totals:** 4,725,186 objects · 517.98 GB

| prefix | objects | GB | days | first | last | written by | holds |
|---|---:|---:|---:|---|---|---|---|
| `fleet/dxlink_nodes` | 14 | 0.000 | 0 |  |  | `share_dxlink_nodes (OTV5 s3_push v5.6, FEED.13)` | each box's dxlink node book, merged fleet-wide |
| `probe/fieldtest-20261025` | 14 | 0.000 | 0 |  |  | `the 2026-10-25 post-repoint PUT probe` | 14 probe objects a box role cannot delete; inert |
| `raw/candles` | 351,516 | 0.287 | 74 | 2026-08-12 | 2026-11-06 | `push_candles <- feed_store.db` | OHLC per tenor; sym=<SYM>_EXT holds non-RTH bars |
| `raw/chain_snapshots` | 75,964 | 3.083 | 76 | 2026-07-24 | 2026-11-06 | `push_file (DATATYPE 'chain_snapshot' + 's')` | option chain marks at fire time |
| `raw/character_axis_sample` | 59,099 | 0.034 | 63 | 2026-09-06 | 2026-11-08 | `push_series ns=dseries (r270)` | tape character axis samples, append-only on (symbol, ts_epoch) |
| `raw/circuit_breaker` | 2 | 0.000 | 2 | 2026-10-27 | 2026-10-30 | `push_table <- trades.db:circuit_breaker_events` | breaker trips |
| `raw/derived_character_ledger` | 43 | 0.000 | 1 | 2026-09-11 | 2026-09-11 | `push_derived` | tape character state with duration |
| `raw/derived_exit_counterfactual` | 3,903 | 0.017 | 25 | 2026-10-05 | 2026-11-06 | `push_derived` | flow exits that WOULD have fired; acts on nothing |
| `raw/derived_fire_snapshot` | 1,623 | 0.004 | 53 | 2026-08-25 | 2026-11-06 | `push_derived` | the derived vector at every fill |
| `raw/derived_gate_disposition` | 20,428 | 0.014 | 72 | 2026-08-24 | 2026-11-06 | `push_derived` | which rung refused a strategy, edge-triggered |
| `raw/derived_level_event` | 937 | 0.001 | 32 | 2026-09-25 | 2026-11-06 | `push_derived (DERIVED_TABLES, r128)` | level lifecycle events, NEVER_PURGE on the box |
| `raw/derived_level_ledger` | 48,551 | 0.101 | 75 | 2026-08-24 | 2026-11-07 | `push_derived` | liquidity levels, operator lifecycle |
| `raw/derived_plan_check` | 46,430 | 7.579 | 70 | 2026-08-26 | 2026-11-06 | `push_derived` | long format: one row per VARIABLE per plan per tick |
| `raw/derived_plan_ledger` | 2,900 | 0.016 | 58 | 2026-08-24 | 2026-11-07 | `push_derived` | plan lifecycle — intent, terminal state, trade join |
| `raw/derived_plan_tick` | 72,477 | 2.331 | 74 | 2026-08-26 | 2026-11-08 | `push_derived` | the spine: one row per plan per tick |
| `raw/derived_strategy_note` | 62,355 | 7.191 | 73 | 2026-08-24 | 2026-11-06 | `push_derived` | one row per strategy EVALUATION |
| `raw/eod` | 1,434 | 0.007 | 55 | 2026-08-07 | 2026-10-23 | `push_whole_files <- ~/eod` | end-of-day artifacts written by the EOD chain |
| `raw/fork_series` | 72,316 | 0.262 | 71 | 2026-08-29 | 2026-11-08 | `push_series ns=dseries` | pitchfork state per tenor, with reject reasons |
| `raw/greeks_series` | 71,966 | 26.729 | 76 | 2026-08-24 | 2026-11-08 | `push_series` | per-contract greeks, full fidelity |
| `raw/indicator_series` | 72,315 | 0.755 | 71 | 2026-08-29 | 2026-11-08 | `push_series ns=dseries` | ADX / ATR / EMA / VWAP accumulators |
| `raw/last_trade` | 75,687 | 8.746 | 76 | 2026-08-24 | 2026-11-08 | `push_series` | Trade events |
| `raw/liquidity_ledger` | 51,645 | 0.129 | 50 | 2026-08-14 | 2026-10-23 | `push_whole_files <- ~/options-trader/data/liquidity_ledger/*.json` | the liquidity map as the box wrote it |
| `raw/ohlc` | 1,313 | 0.031 | 90 | 2026-07-08 | 2026-11-06 | `push_whole_files <- ~/options-trader/data/OHLC/*.csv` | CSV OHLC exports; NOT the same stream as raw/candles |
| `raw/orb_range` | 55 | 0.000 | 2 | 2026-08-13 | 2026-08-14 | `RETIRED — s3_push v1.8, 2026-08-16` | stopped growing; nothing consumed it and the range recomputes from candles |
| `raw/prints` | 70,001 | 74.024 | 63 | 2026-08-24 | 2026-11-06 | `push_series` | TimeAndSale, with the venue's aggressor tag |
| `raw/quote_series` | 70,695 | 371.624 | 76 | 2026-08-24 | 2026-11-08 | `push_series` | per-contract bid/ask/sizes |
| `raw/session_summary` | 14,900 | 0.036 | 76 | 2026-08-24 | 2026-11-08 | `push_series` | Summary events (prev-day close) |
| `raw/shadow` | 325,957 | 0.285 | 15 | 2026-08-24 | 2026-09-11 | `push_jsonl_tree <- ~/options-trader/data/shadow` | sweep-precursor velocity primitives |
| `raw/signal_journal` | 3,068,226 | 1.656 | 97 | 2026-07-20 | 2026-11-06 | `push_jsonl_tree <- ~/options-trader/data/signal_journal` | per-event signal journal |
| `raw/surface_series` | 60,253 | 12.947 | 68 | 2026-08-24 | 2026-11-08 | `push_series ns=dseries` | charm, vanna, GEX |
| `raw/theo_series` | 117 | 0.024 | 2 | 2026-08-24 | 2026-08-25 | `push_series` | TheoPrice — writer retained, unsubscribed at r118 |
| `raw/trades` | 22,022 | 0.069 | 85 | 2026-07-06 | 2026-11-06 | `push_trades <- trades.db` | closed + open trade rows, per box |
| `study/candles_1d` | 28 | 0.001 | 0 |  |  | `daily_candles_study/box_study_upload.py (box role)` | cleaned 1d candles for studies; never read by a bot |

**Documented but ABSENT from the bucket.** Each of these has a live writer in `s3_push.py` (or a recorded retirement) and has produced NO objects. That is a finding, not a gap in this file: `push_derived` skips a table that is absent on the box, so a stream configured to push and never seen here has either no table or no rows — and nothing says which without looking.

- `raw/orb_state` — captured ZERO objects in thirty days  (writer: `RETIRED — s3_push v1.8, 2026-08-16`)
- `raw/underlying_series` — Underlying — published nothing on either symbol space  (writer: `push_series`)
