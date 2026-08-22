#!/usr/bin/env bash
# day_trader_pro/migrate_data_layout.sh — v1.0 — 2026-07-14
# ONE-SHOT migration to the consolidated layout (idempotent; re-run safe):
#   data/harvest/<date>/<SYM>_OHLC_<date>.csv   -> ohlc/<date>/<SYM>_ohlc_<date>.csv
#   data/harvest/<date>/<SYM>_trades_<date>.db  -> trades/<date>/<SYM>_<date>_trades.db
#   data/harvest/<date>/{daily,fleet}_trades_*  -> reports/
#   data/harvest/<date>/replay_*.jsonl          -> reports/
#   data/daily_trades_*.json                    -> reports/
#   pulls/<SYM>_OHLC_<date>.csv                 -> ohlc/<date>/... ; dateless
#   pulls/*_trades.db (no date in name)         -> trades/_undated_legacy/
# data/ keeps operational state (instance_map, mock_state, selection_log, report.json).
set -uo pipefail
DTP="$HOME/day_trader_pro"; cd "$DTP"
mkdir -p ohlc trades reports
moved=0
mv_v() { mkdir -p "$(dirname "$2")"; if [ -e "$2" ]; then echo "  skip (exists): $2"; else mv "$1" "$2" && echo "  $1 -> $2" && moved=$((moved+1)); fi; }

shopt -s nullglob
for daydir in data/harvest/*/; do
  d="$(basename "$daydir")"
  for f in "$daydir"*_OHLC_*.csv "$daydir"*_ohlc_*.csv; do
    sym="${f##*/}"; sym="${sym%%_*}"
    mv_v "$f" "ohlc/$d/${sym}_ohlc_${d}.csv"
  done
  for f in "$daydir"*_trades_*.db; do
    sym="${f##*/}"; sym="${sym%%_*}"
    mv_v "$f" "trades/$d/${sym}_${d}_trades.db"
  done
  for f in "$daydir"daily_trades_*.json "$daydir"fleet_trades_*.json "$daydir"fleet_trades_*.csv "$daydir"replay_*.jsonl; do
    mv_v "$f" "reports/$(basename "$f")"
  done
  rmdir "$daydir" 2>/dev/null && echo "  removed empty $daydir"
done
rmdir data/harvest 2>/dev/null && echo "  removed empty data/harvest"

for f in data/daily_trades_*.json; do
  [ -e "$f" ] && mv_v "$f" "reports/$(basename "$f")"
done

for f in pulls/*_OHLC_*.csv pulls/*_ohlc_*.csv; do
  base="${f##*/}"; sym="${base%%_*}"; d="${base##*_}"; d="${d%.csv}"
  mv_v "$f" "ohlc/$d/${sym}_ohlc_${d}.csv"
done
for f in pulls/*_trades.db; do
  mv_v "$f" "trades/_undated_legacy/$(basename "$f")"
done
rmdir pulls 2>/dev/null && echo "  removed empty pulls/"

echo "migration done — $moved file(s) moved. Layout: ohlc/ trades/ reports/ (+ data/ = state only)"
