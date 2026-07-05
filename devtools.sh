#!/usr/bin/env bash
# day_trader_pro/devtools.sh — v0.1.0
# Interactive debugging / operations menu for the control server.
# Mobile-friendly (Termius): single-key selections, no arguments needed.

set -uo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"

pause() { read -rp $'\nPress Enter to continue...' _; }

reset_mock_state() {
  rm -f data/mock_state.json
  echo "[devtools] cleared mock EC2 state."
}

menu() {
  clear
  cat <<'EOF'
======================================================
  day_trader_pro — devtools
======================================================
  MOCK (safe, no AWS / no API / no Telegram):
    1) Full spool-up  (report -> select -> wake)   [start->finish]
    2) EOD shutdown sweep  (stop running boxes)
    3) Reset mock fleet state

  LIVE-ADJACENT (real reads, NO start/stop):
    4) Dry-run spool-up          (real describe, no start)
    5) Dry-run shutdown sweep     (real describe, no stop)

  REGISTRY:
    6) Show instance map
    7) Reconcile map  (scan fleet by tag Name)
    8) Swap / pin an instance ID for a tag

  COMPONENT TESTS:
    9) Test selection on sample report   (mock model)
   10) Test Telegram send                (REAL send)

    0) Exit
======================================================
EOF
  read -rp "Select: " choice
  case "$choice" in
    1) echo; DTP_MOCK=1 $PY orchestrator.py --mock --no-gate; pause ;;
    2) echo; DTP_MOCK=1 $PY shutdown_manager.py --mock; pause ;;
    3) echo; reset_mock_state; pause ;;
    4) echo; $PY orchestrator.py --dry-run --no-gate; pause ;;
    5) echo; $PY shutdown_manager.py --dry-run; pause ;;
    6) echo; $PY instance_registry.py show; pause ;;
    7) echo; $PY instance_registry.py reconcile; pause ;;
    8) echo; $PY instance_registry.py swap; pause ;;
    9) echo; $PY selector.py --test; pause ;;
   10) echo; $PY notify.py --test; pause ;;
    0) exit 0 ;;
    *) echo "Invalid selection."; sleep 1 ;;
  esac
}

while true; do menu; done
