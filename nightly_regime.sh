#!/usr/bin/env bash
# day_trader_pro/nightly_regime.sh — v1.4
# v1.4 — 2026-07-23 — repoint validate_regime.sh at the repo copy (was $HOME/validate_regime.sh — a
#          loose duplicate whose deletion would silently break the EOD
#          conductor's regime phase). Nothing operational lives in /home/ubuntu.
# v1.3 — 2026-07-14 — invoke validate_regime.sh via `bash` (GitHub web uploads
#        strip the exec bit; direct execution died rc=126 Permission denied).
#        Exec permissions are now irrelevant forever.
# v1.2 — 2026-07-14 — LAYOUT CONSOLIDATION: tape lives in ohlc/<date>/, all
#        products (replay jsonl + rolling diary) in reports/. Paths only.
# v1.1 — 2026-07-14 — surgical rewrite: no fleet pull (dtp-harvest at 15:55
#        already collects tape before dtp-eod stops the fleet at 16:15); this
#        runner reads LOCAL files only, at 16:30 via dtp-regime.timer.
# v1.0 — 2026-07-14 — initial (superseded same day, never deployed).
#
#   1. validate_regime.sh <today>    — replay ohlc/<today> through the real
#      engines WITH Layer-2 tracks; upsert today's diary row in reports/.
#   2. validate_regime.sh --backfill — self-heal any gap days that have tape.
# Holiday/weekend safe. Output -> journald (dtp-regime unit).
set -uo pipefail
D="$(TZ=America/New_York date +%F)"
# 2026-07-23: repointed at the REPO copy. Nothing operational lives loose in
# /home/ubuntu — a duplicate there drifts, and deleting it silently breaks the
# EOD conductor's regime phase (this script is called by eod_conductor.py).
VALIDATE_SH="$HOME/options-trader-v3/validate_regime.sh"
OHLC="$HOME/day_trader_pro/ohlc"

if [ ! -d "$OHLC/$D" ]; then
  echo "[dtp-regime] $D — no tape folder yet (holiday, or dtp-harvest failed); backfill catches it tomorrow"
else
  echo "[dtp-regime] $D — replay + diary from $OHLC/$D"
  bash "$VALIDATE_SH" "$D" || echo "[dtp-regime] replay rc=$? (rc=2 = acceptance-check fail, still diaried)"
fi

echo "[dtp-regime] backfill sweep (gap days with tape)"
bash "$VALIDATE_SH" --backfill

echo "[dtp-regime] done — diary: $HOME/day_trader_pro/reports/regime_diary.md"
