#!/usr/bin/env bash
# day_trader_pro/devtools.sh — v1.16
# v1.16 — 2026-07-18 — NEW item 51: read-only fleet credential AUDIT
#        (rotate_tokens.py --audit). Reports which of the 8 bootstrap vars are set
#        per box — non-secrets in full, secrets as SET/MISSING + len/last-4
#        fingerprint (never the value) — and flags TT_* drift between the bot and
#        candle-feed units. No changes, no restarts.
# v1.15 — 2026-07-18 — NEW item 50: fleet token/secret rotation (rotate_tokens.py).
#        Prompts once per variable (TT client secret / refresh / account, Telegram
#        token / chat ID, GitHub owner-repo / token); <ENTER> leaves a var unchanged.
#        Secrets go straight to the boxes over SSH stdin — never written to a file on
#        control, never passed as an argument. Updates the inline Environment= lines
#        in optionsbot.service + candle-feed.service, daemon-reloads, restarts both.
# v1.14 — 2026-07-17 — REMOVED items 50/51 (local cd-to-repo shortcuts) and the
#        open_in_tmux helper. A menu item runs as a child process and cannot change
#        the parent shell's directory; the workarounds (TIOCSTI keystroke inject —
#        blocked on this kernel — or a .bashrc launcher function) weren't worth the
#        complexity. Use a shell alias instead:
#          alias otv3='cd ~/options-trader-v3 && source venv/bin/activate'
# v1.12 — 2026-07-17 — REDO the items 50/51 fix. v1.11 over-engineered it
#        (detached create + send-keys/switch-client) and nested tmux-in-tmux,
#        dropping you back at a day_trader_pro prompt with [exited]. Correct fix:
#        outside tmux, kill any STALE same-named session then plain
#        `new-session -c <dir>` and attach; inside tmux, `new-window -c <dir>`.
#        Verified in a sandbox: stale opt-v3 in the wrong dir no longer wins.
# v1.11 — 2026-07-17 — fix items 50/51: open_in_tmux forced the working dir on
#        create but not on attach — `new-session -A` re-attached a stale same-named
#        session (opt-v3 was landing in day_trader_pro). Now creates detached with
#        -c, or cd's an existing session, then attaches/switch-clients.
# v1.10 — 2026-07-17 — shorten item 49 label (drop "ohlc_fetch.py") so it fits one line.
# v1.9 — 2026-07-17 — relabel item 49 to "OHLC 21-day fetch from yfinance".
# v1.8 — 2026-07-17 — NEW UTILITIES section: 49 fetch 1m OHLC CSV (tests/ohlc_fetch.py,
#        prompts symbol, default ^VIX); 50/51 open a shell in the options-trader-v3 /
#        market-brief checkout via tmux (a menu item can't cd the parent shell). Item
#        47 broken onto its own line (was wrapping on mobile). In-menu header synced to
#        the real version (was still printing v1.6).
# v1.7 — 2026-07-16 — MERGE: restored items lost to a v1.6 collision with a parallel
#        edit — 46 live P&L standings (standings.py), 47 OHLC backfill (eod_backfill.py),
#        48 EOD conductor (eod_conductor.py). Fable's 45 excursion report kept as-is.
# v1.6 — 2026-07-15 — (parallel edit) NEW TRADES DATA item 45: MFE/MAE excursion report
# v1.6 — 2026-07-15 — item 45 repointed at the AUTO-COLLECTED per-symbol DBs
#        (trades/<date>/*_trades.db, landed by the EOD chain) — no
#        consolidation prerequisite; runnable the moment the DBs are down.
#        Optional since-date prompt turns a snapshot into a CUMULATIVE report
#        (each snapshot holds full history). Item 39 relabeled: consolidation
#        is automatic; 39 is the manual re-run.
# v1.5 — 2026-07-15 — NEW TRADES DATA item 45: MFE/MAE excursion report for a
#        day via excursion_report.py, reading the consolidated fleet file.
#        Appended so 12-44 keep their numbers.
# v1.4 — 2026-07-11 — REGIME VALIDATION expanded: 42 now reprints the SAVED report
#        (not a line count) via validate_regime.sh --report; NEW 43 view diary,
#        44 backfill missing days (disk-driven, skip-occupied, --rebuild option).
#        All items are thin wrappers; validate_regime.sh is the single brain.
# v1.3 — 2026-07-11 — NEW REGIME VALIDATION section (40-42): run the Layer-1
#        confluence replay over a day's harvested OHLC via ~/validate_regime.sh
#        (manual/on-demand). 40=today, 41=pick date, 42=view latest tick log.
#        Thin wrappers — validate_regime.sh stays the single source of truth.
#        Appended so 12-39 keep their numbers.
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
VALIDATE_SH="$HOME/validate_regime.sh"
HARVEST_DIR="$HOME/day_trader_pro/data/harvest"

# Open an interactive shell in a directory via tmux (a menu item can't cd the
# parent shell). Inside tmux -> new window; otherwise attach-or-create a session.
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
  day_trader_pro — devtools  v1.14
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
   39) Re-run consolidation -> fleet_trades_<date>.json (+ .csv)
       (EOD chain does this automatically; manual re-run only)
   45) Excursion report (MFE/MAE) -> reports/excursions_<date>.txt
       (reads trades/<date>/*_trades.db — auto-collected, ready now)

 REGIME VALIDATION (Layer-1 confluence; manual, tape-only):
   40) Run replay - today        41) Run replay - pick a date
   42) View a day's report       43) View the diary (all days)
   44) Backfill missing days      (fills diary gaps that have tape)

 EOD CONDUCTOR, BACKFILL & LIVE P&L:
   46) Live P&L standings (read-only)
   47) Backfill missing OHLC (auto-batched)
   48) EOD conductor - full gated EOD (dry-run preview -> confirm -> run)

 UTILITIES:
   49) OHLC 21-day fetch from yfinance (prompts symbol, default ^VIX)
   50) Rotate fleet tokens/secrets (prompts each; <ENTER>=no change; pushes to running boxes)
   51) Audit fleet credentials (read-only; shows which vars are set, no values)

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
    40) echo; if [ -x "$VALIDATE_SH" ]; then "$VALIDATE_SH"; else echo "missing/non-exec $VALIDATE_SH (chmod +x ~/validate_regime.sh?)"; fi; pause ;;
    41) echo; read -rp "Date (YYYY-MM-DD, ENTER=today): " D; D="${D:-$(date +%F)}"; if [ -x "$VALIDATE_SH" ]; then "$VALIDATE_SH" "$D"; else echo "missing/non-exec $VALIDATE_SH"; fi; pause ;;
    42) echo; D_DEF="$(date +%F)"; read -rp "Date to view (YYYY-MM-DD, ENTER=${D_DEF}): " D; D="${D:-$D_DEF}"; if [ -x "$VALIDATE_SH" ]; then "$VALIDATE_SH" --report "$D"; else echo "missing/non-exec $VALIDATE_SH"; fi; pause ;;
    43) echo; if [ -x "$VALIDATE_SH" ]; then "$VALIDATE_SH" --diary; else echo "missing/non-exec $VALIDATE_SH"; fi; pause ;;
    44) echo; read -rp "Rebuild ALL dated tapes (else only fill gaps)? [y/N]: " RB; if [ -x "$VALIDATE_SH" ]; then if [ "$RB" = "y" ]; then "$VALIDATE_SH" --backfill --rebuild; else "$VALIDATE_SH" --backfill; fi; else echo "missing/non-exec $VALIDATE_SH"; fi; pause ;;
    45) echo; read -rp "Day (YYYY-MM-DD, ENTER=today): " D; D="${D:-$(date +%F)}"; \
        read -rp "Cumulative since (YYYY-MM-DD, ENTER=that day only): " S; \
        read -rp "Live rows? [y/N]: " LV; \
        ARGS="--date $D"; [ -n "$S" ] && ARGS="$ARGS --since $S"; [ "$LV" = "y" ] && ARGS="$ARGS --live"; \
        $PY excursion_report.py $ARGS; pause ;;
    46) echo; read -rp "Push to Telegram too? [y/N]: " S; if [ "$S" = "y" ]; then $PY standings.py --send; else $PY standings.py; fi; pause ;;
    47) echo; read -rp "Backfill date (YYYY-MM-DD, ENTER=today): " D; D="${D:-$(date +%F)}"; read -rp "Batch size (ENTER=5): " B; B="${B:-5}"; echo; $PY eod_backfill.py --date "$D" --batch "$B" --dry-run; echo; read -rp "Proceed with LIVE backfill (wakes/stops boxes)? [y/N]: " GO; [ "$GO" = "y" ] && $PY eod_backfill.py --date "$D" --batch "$B"; pause ;;
    48) echo; read -rp "Backfill batch size (ENTER=5): " B; B="${B:-5}"; echo; $PY eod_conductor.py --batch "$B" --dry-run; echo; read -rp "Run the LIVE EOD conductor now (gate->harvest->P&L+stop->backfill->consolidate->diary)? [y/N]: " GO; [ "$GO" = "y" ] && $PY eod_conductor.py --batch "$B"; pause ;;
    49) echo; read -rp "Symbol [^VIX]: " SY; SY="${SY:-^VIX}"; $PY tests/ohlc_fetch.py --symbol "$SY"; pause ;;
    50) echo; read -rp "Rotate against a SUBSET of symbols? (ENTER=all running): " SUBSET; \
        if [ -n "$SUBSET" ]; then $PY rotate_tokens.py --only $SUBSET; else $PY rotate_tokens.py; fi; pause ;;
    51) echo; read -rp "Audit a SUBSET of symbols? (ENTER=all running): " SUBSET; \
        if [ -n "$SUBSET" ]; then $PY rotate_tokens.py --audit --only $SUBSET; else $PY rotate_tokens.py --audit; fi; pause ;;
    0)  exit 0 ;;
    *)  echo "Invalid selection."; sleep 1 ;;
  esac
}

while true; do menu; done
