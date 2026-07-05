#!/usr/bin/env bash
# day_trader_pro/push.sh — v0.1.0
# Single entry point for all git operations (matches repo convention).
set -euo pipefail
cd "$(dirname "$0")"
MSG="${1:-update}"
git add -A
git commit -m "$MSG"
git push
