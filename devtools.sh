#!/usr/bin/env bash
# day_trader_pro/devtools.sh — v1.2
# v1.2 — 2026-07-10 — NEW TRADES DATA item 39: consolidate a day's raw per-box
#        trades.db into fleet_trades_<date>.json (+ .csv) via consolidate_trades.py
#        (prompts for date, ENTER=today). Appended (not renumbered) so 12-38 keep
#        their numbers.
# v1.1 — 2026-07-10 — Wake (24) now scoped one/all/some (prompts for symbols,
#        passes --only) so you can wake a single box like IWM after hours.
#        Re-added CONTROL REPO force-sync: PUSH (37) / PULL (38).
# Interactive operations menu for the control server (mobile-friendly / Termius:
# single-key selections, prompts default sensibly so you rarely type).
#
# Streamlines the most-used capabilities of the helper scripts:
#   fleet.py         list / ping / run / pull / repoint  (SSH management plane)
#   wake_and_bake.py wake / bake / restart / shutdown modes
#   push.sh          (via fleet update)
# plus a remote debug/log toolkit and a gitignore-aware snapshot.
#
# v1.0 — 2026-07-10 — major overhaul. Reorganized into sections. NEW:
#        FLEET status.py+query.py on one/all/some (15); pull trades.db (16) and
#        pull OHLC for a day (17) via `fleet.py pull`. DEBUG/LOGS toolkit:
#        service status (18), journal tail (19), feed health (20), bot-log tail
#        (21). REPOINT section (28-33). SNAPSHOT: gitignore-aware repo-ready
#        tarball (34). Corrected bake-only label (no restart; RTH-safe).
# v0.6.0 — added REPOINT entries (never shipped).
# v0.5.0 — MAINTENANCE for wake_and_bake modes.

set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
PY="${PYTHON:-python3}"
DEFAULT_V3="https://github.com/TX-9AI/options_trader_v3.git"
INSTALL_DIR="~/options-trader"
FEED_DB="~/options-trader/data/feed_store.db"

pause() { read -rp $'\nPress Enter to continue...' _; }

# Symbol scope: ENTER = all running boxes; else `--only SYM,SYM`.
ask_scope() {
  local sc
  read -rp "Symbols (ENTER = ALL, or comma-sep e.g. IWM,SPX): " sc
  [ -n "$sc" ] && echo "--only $sc" || echo ""
}

# Repoint target URL, defaulting to the v3 repo (just press Enter).
ask_url() {
  local u
  read -rp "New repo URL [Enter = ${DEFAULT_V3}]: " u
  echo "${u:-$DEFAULT_V3}"
}

reset_mock_state() { rm -f data/mock_state.json; echo "[devtools] cleared mock EC2 state."; }

# Gitignore-aware, repo-ready tarball of a directory -> ~/snapshots/.
snapshot_dir() {
  local src out name tarball
  read -rp "Directory to snapshot [Enter = ${SCRIPT_DIR}]: " src
  src="${src:-$SCRIPT_DIR}"
  src="${src/#\~/$HOME}"
  if [ ! -d "$src" ]; then echo "  Not a directory: $src"; return 1; fi
  out="$HOME/snapshots"; mkdir -p "$out"
  name="$(basename "$src")_$(date +%Y-%m-%d_%H%M).tar.gz"
  tarball="$out/$name"
  if [ -d "$src/.git" ]; then
    ( cd "$src" && git ls-files --cached --others --exclude-standard -z \
        | tar czf "$tarball" --null -T - )
    echo "  repo-ready (gitignore-aware): $tarball"
  else
    tar czf "$tarball" --exclude=.git --exclude=__pycache__ --exclude='*.pyc' \
        -C "$(dirname "$src")" "$(basename "$src")" 2>/dev/null
    echo "  tarball (no git repo; basic excludes): $tarball"
  fi
  ls -lh "$tarball" 2>/dev/null
}

# Force-sync THIS control-server day_trader_pro checkout with GitHub.
# PUSH = server is source of truth (overwrites GitHub).
# PULL = GitHub is source of truth (discards local changes). Both confirm first.
repo_push_force() {
  cd "$SCRIPT_DIR" || return 1
  echo "  PUSH (force): make THIS SERVER the source of truth — overwrites the"
  echo "  day_trader_pro repo on GitHub with this checkout's state."
  local c; read -rp "  Type PUSH to confirm: " c
  [ "$c" = "PUSH" ] || { echo "  cancelled."; return 0; }
  local br; br="$(git branch --show-current 2>/dev/null || echo main)"
  git add -A
  git commit -m "control-server sync $(date '+%Y-%m-%d %H:%M')" 2>/dev/null \
    || echo "  (nothing new to commit — pushing current HEAD)"
  if git push --force origin "$br"; then
    echo "  ✅ force-pushed — GitHub now matches this server ($br)."
  else
    echo "  🚨 push failed — check errors above."
  fi
}

repo_pull_force() {
  cd "$SCRIPT_DIR" || return 1
  echo "  PULL (force): make GITHUB the source of truth — DISCARDS any local"
  echo "  changes in this checkout (git reset --hard to origin)."
  local c; read -rp "  Type PULL to confirm: " c
  [ "$c" = "PULL" ] || { echo "  cancelled."; return 0; }
  local br; br="$(git branch --show-current 2>/dev/null || echo main)"
  if git fetch origin && git reset --hard "origin/$br"; then
    echo "  ✅ reset to GitHub state ($br) — local changes discarded."
  else
    echo "  🚨 pull failed — check errors above."
  fi
}

menu() {
  clear
  cat <<'EOF'
======================================================
  day_trader_pro — devtools  v1.0
======================================================
 ORCHESTRATION:
    1) Full spool-up (mock)       2) EOD aggregate (mock)
    3) Reset mock state           4) Dry-run spool-up (real reads)
    5) Dry-run EOD aggregate (real reads)

 REGISTRY & MASTER SWITCH:
    6) Instance map               7) Reconcile map
    8) Swap / pin instance ID     9) Control status
   10) ENABLE control            11) DISABLE control

 FLEET (inspect & fan-out):
   12) Fleet list                13) Fleet ping
   14) Run command (all running)
   15) status.py + query.py      (one/all/some)
   16) Pull trades.db            (one/all/some)
   17) Pull OHLC for a day       (one/all/some)

 DEBUG / LOGS (remote; one/all/some):
   18) Service status (bot + candle-feed)
   19) Journal tail (last N)     20) Feed health (store freshness)
   21) Bot log tail (last 20)

 MAINTENANCE (wake_and_bake):
   22) Dry-run                   23) FULL (wake->bake->restart->STOP)
   24) Wake (one/all/some)       25) Bake only (sync, no restart - RTH-safe)
   26) Leave on (skip shutdown)  27) Shutdown only (EOD + stop)

 REPOINT (migrate fleet -> new repo):
   28) Check only                29) FULL
   30) Full + wake               31) No restart
   32) Scoped                    33) Mock preview

 SNAPSHOT & TESTS:
   34) Snapshot dir -> repo-ready tarball
   35) Test selection (mock)     36) Test Telegram (real)

 CONTROL REPO (this checkout <-> GitHub, force sync):
   37) PUSH -> GitHub  (FORCE; this server is source of truth)
   38) PULL <- GitHub  (FORCE; GitHub is source of truth)

 TRADES DATA:
   39) Consolidate a day's trades -> fleet_trades_<date>.json (+ .csv)

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
    15) echo; SC=$(ask_scope); $PY fleet.py run "cd $INSTALL_DIR; python status.py; echo; python query.py" $SC; pause ;;
    16) echo; SC=$(ask_scope); $PY fleet.py pull db $SC; pause ;;
    17) echo; SC=$(ask_scope); read -rp "Day (YYYY-MM-DD, ENTER=today): " D; D="${D:-$(date +%F)}"; $PY fleet.py pull ohlc --day "$D" $SC; pause ;;
    18) echo; SC=$(ask_scope); $PY fleet.py run 'echo "optionsbot=$(systemctl is-active optionsbot) candle-feed=$(systemctl is-active candle-feed)"' $SC; pause ;;
    19) echo; SC=$(ask_scope); read -rp "How many journal lines [20]: " N; N="${N:-20}"; $PY fleet.py run "journalctl -u optionsbot -n ${N} --no-pager" $SC; pause ;;
    20) echo; SC=$(ask_scope); $PY fleet.py run "echo \"candle-feed=\$(systemctl is-active candle-feed) store_write_age_s=\$(( \$(date +%s) - \$(stat -c %Y ${FEED_DB}-wal 2>/dev/null || stat -c %Y ${FEED_DB} 2>/dev/null || echo 0) ))\"" $SC; pause ;;
    21) echo; SC=$(ask_scope); $PY fleet.py run "tail -20 ${INSTALL_DIR}/bot.log" $SC; pause ;;
    22) echo; $PY wake_and_bake.py --dry-run; pause ;;
    23) echo; $PY wake_and_bake.py; pause ;;
    24) echo; SC=$(ask_scope); $PY wake_and_bake.py --wake-only $SC; pause ;;
    25) echo; $PY wake_and_bake.py --bake-only; pause ;;
    26) echo; $PY wake_and_bake.py --leave-running; pause ;;
    27) echo; $PY wake_and_bake.py --shutdown-only; pause ;;
    28) echo; U=$(ask_url); $PY fleet.py repoint "$U" --check-only; pause ;;
    29) echo; U=$(ask_url); $PY fleet.py repoint "$U"; pause ;;
    30) echo; U=$(ask_url); $PY fleet.py repoint "$U" --wake; pause ;;
    31) echo; U=$(ask_url); $PY fleet.py repoint "$U" --no-restart; pause ;;
    32) echo; U=$(ask_url); read -rp "Symbols (comma-sep, e.g. SPX,QQQ): " SY; $PY fleet.py repoint "$U" --only "$SY"; pause ;;
    33) echo; U=$(ask_url); $PY fleet.py repoint "$U" --mock --yes; pause ;;
    34) echo; snapshot_dir; pause ;;
    35) echo; $PY selector.py --test; pause ;;
    36) echo; $PY notify.py --test; pause ;;
    37) echo; repo_push_force; pause ;;
    38) echo; repo_pull_force; pause ;;
    39) echo; read -rp "Day to consolidate (YYYY-MM-DD, ENTER=today): " D; D="${D:-$(date +%F)}"; $PY consolidate_trades.py --date "$D"; pause ;;
    0)  exit 0 ;;
    *)  echo "Invalid selection."; sleep 1 ;;
  esac
}

while true; do menu; done
