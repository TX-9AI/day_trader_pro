#!/usr/bin/env bash
# day_trader_pro/devtools.sh — v0.5.0
# Interactive debugging / operations menu for the control server.
# Mobile-friendly (Termius): single-key selections, no arguments needed.
# v0.5.0 — 2026-07-09 — MAINTENANCE expanded for wake_and_bake v1.1 modes:
#          added Wake only (17), Bake only (18), Leave on (19),
#          Shutdown only (20). Component tests renumbered 17/18 -> 21/22.
# v0.4.0 — 2026-07-07 — added MAINTENANCE section: wake_and_bake (dry-run + real);
#          component-test items renumbered 15/16 -> 17/18.

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
    1) Full spool-up  (report -> select -> wake)
    2) EOD aggregate  (pull P&L -> stop -> ONE message)
    3) Reset mock fleet state

  LIVE-ADJACENT (real reads, NO start/stop):
    4) Dry-run spool-up          (real describe, no start)
    5) Dry-run EOD aggregate      (real pull, no stop)

  REGISTRY:
    6) Show instance map
    7) Reconcile map  (scan fleet by tag Name)
    8) Swap / pin an instance ID for a tag

  MASTER SWITCH:
    9) Control status
   10) ENABLE control   (automation on)
   11) DISABLE control  (deco mode - run bots by hand)

  FLEET (SSH management plane):
   12) Fleet list        (symbol -> private IP -> state)
   13) Fleet ping        (SSH echo-test running boxes)
   14) Fleet run cmd     (prompt for a command, run on all running)

  MAINTENANCE (wake_and_bake v1.1):
   15) Wake & bake - DRY RUN   (plan only, changes nothing)
   16) Wake & bake - FULL      (wake -> bake -> restart -> STOP)
   17) Wake only               (start fleet + ping, leave running)
   18) Bake only               (ping -> git sync -> restart, no wake/stop)
   19) Leave on                (full run: pycache+restart, SKIP shutdown)
   20) Shutdown only           (pycache clear -> EOD report -> STOP)

  COMPONENT TESTS:
   21) Test selection on sample report   (mock model)
   22) Test Telegram send                (REAL send)

    0) Exit
======================================================
EOF
  read -rp "Select: " choice
  case "$choice" in
    1)  echo; DTP_MOCK=1 $PY orchestrator.py --mock --no-gate; pause ;;
    2)  echo; DTP_MOCK=1 $PY eod_report.py --mock; pause ;;
    3)  echo; reset_mock_state; pause ;;
    4)  echo; $PY orchestrator.py --dry-run --no-gate; pause ;;
    5)  echo; $PY eod_report.py --dry-run; pause ;;
    6)  echo; $PY instance_registry.py show; pause ;;
    7)  echo; $PY instance_registry.py reconcile; pause ;;
    8)  echo; $PY instance_registry.py swap; pause ;;
    9)  echo; $PY control_state.py status; pause ;;
    10) echo; $PY control_state.py enable; pause ;;
    11) echo; $PY control_state.py disable; pause ;;
    12) echo; $PY fleet.py list; pause ;;
    13) echo; $PY fleet.py ping; pause ;;
    14) echo; read -rp "Command to run on all running boxes: " fc; $PY fleet.py run "$fc"; pause ;;
    15) echo; $PY wake_and_bake.py --dry-run; pause ;;
    16) echo; $PY wake_and_bake.py; pause ;;
    17) echo; $PY wake_and_bake.py --wake-only; pause ;;
    18) echo; $PY wake_and_bake.py --bake-only; pause ;;
    19) echo; $PY wake_and_bake.py --leave-running; pause ;;
    20) echo; $PY wake_and_bake.py --shutdown-only; pause ;;
    21) echo; $PY selector.py --test; pause ;;
    22) echo; $PY notify.py --test; pause ;;
    0)  exit 0 ;;
    *)  echo "Invalid selection."; sleep 1 ;;
  esac
}

while true; do menu; done
