#!/usr/bin/env bash
# day_trader_pro/devtools.sh — v1.30
# v1.30 — 2026-08-14 — 58) REPLAY SIM REMOVED. It drove tests/replay_sim.py,
#         which duplicated tests/replay_confluence.py (as-of replay over
#         deterministic tape, --warm-sessions since v1.2 2026-07-21) and lacked
#         the frame caps v2.2 added on 08-01 — so it would have shown the replay
#         MORE history than live ever receives. One owner per file
#         (WORKING_AGREEMENT 7); the duplicate is gone.
# v1.28 — 2026-08-11 — ask_scope tolerates "SPX, PLTR, GLD" (spaces after the
#         commas). It did not merely reject that input — the helper's output is
#         consumed UNQUOTED, so a space SPLIT the argument and fleet.py silently
#         ran on a TRUNCATED symbol list. A wrong scope with no error and a
#         normal-looking run, which is the failure class this project keeps
#         paying for. Whitespace is stripped, repeated commas squeezed, leading
#         and trailing commas trimmed. Covers every one/all/some prompt (15, 16,
#         17, the DEBUG block, 24/25) since they all route through this helper.
#         NOT changed: option 32's repoint prompt has its own inline `read` with
#         the same weakness — named rather than folded in.
# v1.27
# v1.27 — 2026-08-10 — OPTION 57: THE FIT REPORT. Fitting a ramp, a stop or an
#         entry gate needs the trade breakdown, the excursion read, the regime
#         diary and the calibration telemetry TOGETHER — four menu options, four
#         screenfuls, and on mobile that meant screenshotting each one. Worse
#         than slow: it made it easy to fit against numbers drawn from different
#         windows without noticing. 57 runs all six as subprocesses and writes
#         ONE text file to reports/. It re-implements nothing, so there is still
#         exactly one source of truth per number.
#         The file leads with PROVENANCE (both repos' git HEAD + dirty flag, the
#         resolved interpreters, the range) and, when the range spans a dated
#         fleet bake, a warning ABOVE every number that per-regime statistics
#         either side of it are not the same measurement.
# v1.26 — 2026-08-01 — 56 REPORTED 29/29 SUCCESS WHILE DOING NOTHING AT ALL.
#         Two defects, and the second is the dangerous one.
#         (1) INTERPRETER. The fan-out ran bare `python3`, which on the boxes is
#         system python — no pandas, no tastytrade. blind_alert_selftest imports
#         data.market_data, so it died at IMPORT on all 29 boxes. Third
#         interpreter mismatch of the day. Now uses venv/bin/python explicitly.
#         (2) THE GREEN WAS LAUNDERED. The command ended in `; true` to satisfy
#         the exit-0 fan-out convention, so the drill's real return code was
#         discarded and the menu printed "29/29 succeeded". stderr was not
#         captured either, so the traceback vanished and every box showed
#         "(no output)" — a perfect health report from a tool that never ran.
#         That is precisely the silent-failure class the blind alert exists to
#         catch, committed inside the drill built to test it.
#         Now: stderr captured with 2>&1, and the tail shows the script's OWN
#         "DRILL PASSED" / "DRILL FAILED" line. `; true` still keeps the
#         fan-out from discarding output, but it is no longer the thing
#         reporting success. Read the per-box verdict, not the 29/29.
# v1.25 — 2026-08-01 — +56 "Blind-alert DRILL (fleet)". Fires the real
#         blind-alert path on the boxes — recorder -> latch -> AlertManager ->
#         Telegram — so the alarm that pages when the bot can still run but can
#         no longer SEE is exercised on purpose rather than discovered broken
#         during an outage. Runs tests/blind_alert_selftest.py on each box via
#         the option-14 fan-out; every message it sends is prefixed DRILL - NOT
#         REAL, because Telegram is an emergency-services channel and a test
#         that looks real is itself a false alarm.
#         Both version strings bumped together, per v1.24's own lesson.
# v1.24 — 2026-07-30 — the MENU HEADER still printed v1.22 after v1.23 added
#         item 55: the file-header version and the displayed banner are two
#         separate strings and only one was bumped. Synced, and noted here so
#         the next bump changes BOTH. A version you read off the screen that
#         disagrees with the file is worse than no version at all.
# v1.23 — 2026-07-29 — +55 "Verify control IAM role sees the fleet". check_iam.py
#         was sitting UNTRACKED in ~/market-brief despite its own header reading
#         `day_trader_pro/check_iam.py` — wrong repo, in no repo, and reachable
#         only by remembering it existed. It is the control-plane counterpart of
#         54 (which verifies the BOXES' credentials): STS identity check, then
#         describe_instances on tag:Project=day_trader in us-east-2, and it
#         distinguishes "no role attached" from "role attached but missing
#         ec2:DescribeInstances". Read-only — never starts or stops anything.
# v1.22 — 2026-07-23 — FIX: v1.21 defined VALIDATE_SH from $OTV3_DIR one line
#          BEFORE OTV3_DIR was set; with `set -uo pipefail` that is an unbound
#          variable and the menu refused to launch. Assignment order corrected.
# v1.21 — 2026-07-23 — repoint VALIDATE_SH at the repo copy (options 42-46);
#          drop the dead HARVEST_DIR var (retired data/harvest layout).
# v1.20 — 2026-07-23 — menu colour: border rules and section titles BLUE,
#          banner text WHITE. _colorize post-filter; heredoc stays quoted so
#          nothing in the body expands; TTY-gated so pipes stay clean.
# v1.19 — 2026-07-22 — RESTORED two items clobbered by the v1.18 renumber (which
#        was cut from a pre-HALT copy of the menu): (a) item 27 is the EMERGENCY
#        STOP again — HALT-gated, no EOD, no pycache, RTH-exempt (the v1.18 label
#        "Shutdown only (EOD + stop)" was a stale mislabel: the dispatched
#        wake_and_bake --shutdown-only has been the emergency stop since
#        2026-07-18 and the label said the opposite of what the button does);
#        (b) item 54 Verify fleet credentials (rotate_tokens.py --verify) —
#        menu line + case handler had been dropped entirely.
# v1.18 — 2026-07-22 — RENUMBERED the whole menu into sequential order (items had
#        drifted as features were appended: 45 sat above 40, 52 sat below 44).
#        Section order is unchanged; only the numbers moved. NEW item 41: cross-day
#        trade breakdown (trade_report.py) — ranks net/win%/avg/hold by regime,
#        strategy, setup type, setup grade and exit reason, plus the regime x
#        strategy cross-cut and winner-vs-loser hold/MFE/MAE. Shortened item 52
#        (was 50) — dropped the inline prompt description from the label.
#        Old -> new: 45->40, 40->42, 41->43, 42->44, 43->45, 44->46, 52->47,
#        46->48, 47->49, 48->50, 49->51, 50->52, 51->53. 1-39 unchanged.
# v1.17 — 2026-07-22 — NEW item 52: A2 co-occurrence + HTF-conditioned drift
#        (options-trader-v3 tests/a2_cooccurrence.py). Read-only, offline: reads the
#        replay tick logs validate_regime.sh already writes under reports/ and reports
#        (a) which label L2 committed when TRENDING and RANGING are both >0.5,
#        (b) forward drift bucketed by HTF direction, (c) a RANGE_ONLY control.
#        Runs in a subshell so the parent shell's cwd is untouched.
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
OTV3_DIR="$HOME/options-trader-v3"          # control-box checkout (boxes use ~/options-trader)
OTV3_PY="$OTV3_DIR/venv/bin/python"
# 2026-07-23: canonical copy lives in the otv3 repo. Nothing operational
# should sit loose in /home/ubuntu. MUST be defined AFTER OTV3_DIR —
# `set -uo pipefail` (line 112) makes a forward reference fatal at load.
VALIDATE_SH="$OTV3_DIR/validate_regime.sh"

# Open an interactive shell in a directory via tmux (a menu item can't cd the
# parent shell). Inside tmux -> new window; otherwise attach-or-create a session.
pause() { read -rp $'\nPress Enter to continue...' _; }

# Symbol scope: ENTER = all running boxes; else `--only SYM,SYM`.
ask_scope() {
  local sc
  read -rp "Symbols (ENTER = ALL, or comma-sep e.g. IWM,SPX or IWM, SPX): " sc
  # v1.28 — TOLERATE SPACES AFTER COMMAS. "SPX, PLTR, GLD" is the natural way to
  # type a list and it used to break badly rather than obviously: the result is
  # echoed and consumed UNQUOTED by the caller, so a space split "--only SPX,"
  # from "PLTR," and fleet.py saw a truncated list — a WRONG scope, silently,
  # with no error and a perfectly normal-looking run on the wrong boxes.
  # Also squeeze repeated commas and strip leading/trailing ones, because a
  # trailing comma is the same typo class and yields an empty symbol.
  sc="${sc//[[:space:]]/}"          # "SPX, PLTR" -> "SPX,PLTR"
  while [[ "$sc" == *,,* ]]; do sc="${sc//,,/,}"; done
  sc="${sc#,}"; sc="${sc%,}"
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

# ── v1.20 menu colour ─────────────────────────────────────────────────────
# Border rules and every ALL-CAPS section header render in BLUE; the banner
# title line renders in WHITE. The menu heredoc stays QUOTED (<<'EOF') so nothing in the body can
# expand — colour is applied afterwards by a sed post-filter instead of by
# embedding escapes in the text. Section headers are matched structurally
# (one leading space, capital letter, trailing colon); menu items start with
# four spaces and a digit, so they never match.
# Colour is suppressed when stdout is not a TTY, so piping the menu to a file
# or a grep stays clean.
_BLUE=$'\033[1;34m'
_WHITE=$'\033[1;37m'
_RST=$'\033[0m'
_colorize() {
  if [ -t 1 ]; then
    sed -E -e "s/^(=+)$/${_BLUE}\1${_RST}/" \
           -e "s/^(  Day Trader Pro .*)$/${_WHITE}\1${_RST}/" \
           -e "s/^( [A-Z][^:]*:)$/${_BLUE}\1${_RST}/"
  else
    cat
  fi
}

menu() {
  clear
  cat <<'EOF' | _colorize
======================================================
  Day Trader Pro — devtools  v1.26 Service Menu
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
   26) Leave on (skip shutdown)
   27) EMERGENCY STOP (no EOD, no pycache, RTH-exempt, HALT-gated)

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
   40) Excursion report (MFE/MAE) -> reports/excursions_<date>.txt
   41) Trade breakdown (cross-day: regime/strategy/grade + regime x strategy)
   57) FIT REPORT — everything for fitting in ONE text file (1 day or a range)

 REGIME VALIDATION (Layer-1 confluence; manual, tape-only):
   42) Run replay - today        43) Run replay - pick a date
   44) View a day's report       45) View the diary (all days)
   46) Backfill missing days      (fills diary gaps that have tape)
   47) A2 co-occurrence + HTF drift  (read-only; auto-finds replay logs)

 EOD CONDUCTOR, BACKFILL & LIVE P&L:
   48) Live P&L standings (read-only)
   49) Backfill missing OHLC (auto-batched)
   50) EOD conductor - full gated EOD (dry-run preview -> confirm -> run)

 UTILITIES:
   51) OHLC 21-day fetch from yfinance (prompts symbol, default ^VIX)
   52) Rotate fleet tokens/secrets (pushes to running boxes)
   53) Audit fleet credentials (read-only; shows which vars are set, no values)
   54) Verify fleet credentials WORK (TT SDK, Telegram, GitHub)
   55) Verify control IAM role sees the fleet (read-only; no start/stop)
   56) Blind-alert DRILL on the fleet (sends REAL Telegram, marked DRILL)

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
    42) echo; if [ -x "$VALIDATE_SH" ]; then "$VALIDATE_SH"; else echo "missing/non-exec $VALIDATE_SH (chmod +x $OTV3_DIR/validate_regime.sh?)"; fi; pause ;;
    43) echo; read -rp "Date (YYYY-MM-DD, ENTER=today): " D; D="${D:-$(date +%F)}"; if [ -x "$VALIDATE_SH" ]; then "$VALIDATE_SH" "$D"; else echo "missing/non-exec $VALIDATE_SH"; fi; pause ;;
    44) echo; D_DEF="$(date +%F)"; read -rp "Date to view (YYYY-MM-DD, ENTER=${D_DEF}): " D; D="${D:-$D_DEF}"; if [ -x "$VALIDATE_SH" ]; then "$VALIDATE_SH" --report "$D"; else echo "missing/non-exec $VALIDATE_SH"; fi; pause ;;
    45) echo; if [ -x "$VALIDATE_SH" ]; then "$VALIDATE_SH" --diary; else echo "missing/non-exec $VALIDATE_SH"; fi; pause ;;
    46) echo; read -rp "Rebuild ALL dated tapes (else only fill gaps)? [y/N]: " RB; if [ -x "$VALIDATE_SH" ]; then if [ "$RB" = "y" ]; then "$VALIDATE_SH" --backfill --rebuild; else "$VALIDATE_SH" --backfill; fi; else echo "missing/non-exec $VALIDATE_SH"; fi; pause ;;
    47) echo; if [ -x "$OTV3_PY" ]; then (cd "$OTV3_DIR" && "$OTV3_PY" -m tests.a2_cooccurrence); else echo "missing $OTV3_PY (is ~/options-trader-v3 checked out with its venv?)"; fi; pause ;;
    40) echo; read -rp "Day (YYYY-MM-DD, ENTER=today): " D; D="${D:-$(date +%F)}"; \
        read -rp "Cumulative since (YYYY-MM-DD, ENTER=that day only): " S; \
        read -rp "Live rows? [y/N]: " LV; \
        ARGS="--date $D"; [ -n "$S" ] && ARGS="$ARGS --since $S"; [ "$LV" = "y" ] && ARGS="$ARGS --live"; \
        $PY excursion_report.py $ARGS; pause ;;
    41) echo; read -rp "Since date (YYYY-MM-DD, ENTER=all): " SD; if [ -n "$SD" ]; then $PY trade_report.py --since "$SD"; else $PY trade_report.py; fi; pause ;;
    57) echo; read -rp "Day, or END of range (YYYY-MM-DD, ENTER=today): " D; D="${D:-$(date +%F)}"; \
        read -rp "Cumulative since (YYYY-MM-DD, ENTER=that day only): " S; \
        read -rp "Skip the slow replay-corpus sections (ramps, A2 drift)? [y/N]: " NS; \
        ARGS="--date $D"; [ -n "$S" ] && ARGS="$ARGS --since $S"; [ "$NS" = "y" ] && ARGS="$ARGS --no-slow"; \
        echo "Running — the replay-corpus sections take minutes; output is a FILE, not this screen."; \
        $PY fit_report.py $ARGS; pause ;;
    48) echo; read -rp "Push to Telegram too? [y/N]: " S; if [ "$S" = "y" ]; then $PY standings.py --send; else $PY standings.py; fi; pause ;;
    49) echo; read -rp "Backfill date (YYYY-MM-DD, ENTER=today): " D; D="${D:-$(date +%F)}"; read -rp "Batch size (ENTER=5): " B; B="${B:-5}"; echo; $PY eod_backfill.py --date "$D" --batch "$B" --dry-run; echo; read -rp "Proceed with LIVE backfill (wakes/stops boxes)? [y/N]: " GO; [ "$GO" = "y" ] && $PY eod_backfill.py --date "$D" --batch "$B"; pause ;;
    50) echo; read -rp "Backfill batch size (ENTER=5): " B; B="${B:-5}"; echo; $PY eod_conductor.py --batch "$B" --dry-run; echo; read -rp "Run the LIVE EOD conductor now (gate->harvest->P&L+stop->backfill->consolidate->diary)? [y/N]: " GO; [ "$GO" = "y" ] && $PY eod_conductor.py --batch "$B"; pause ;;
    51) echo; read -rp "Symbol [^VIX]: " SY; SY="${SY:-^VIX}"; $PY tests/ohlc_fetch.py --symbol "$SY"; pause ;;
    52) echo; read -rp "Rotate against a SUBSET of symbols? (ENTER=all running): " SUBSET; \
        if [ -n "$SUBSET" ]; then $PY rotate_tokens.py --only $SUBSET; else $PY rotate_tokens.py; fi; pause ;;
    53) echo; read -rp "Audit a SUBSET of symbols? (ENTER=all running): " SUBSET; \
        if [ -n "$SUBSET" ]; then $PY rotate_tokens.py --audit --only $SUBSET; else $PY rotate_tokens.py --audit; fi; pause ;;
    54) echo; read -rp "Verify a SUBSET of symbols? (ENTER=all running): " SUBSET; \
        if [ -n "$SUBSET" ]; then $PY rotate_tokens.py --verify --only $SUBSET; else $PY rotate_tokens.py --verify; fi; pause ;;
    55) echo; $PY check_iam.py; pause ;;
    56) echo; echo "Fires the REAL blind-alert path on every RUNNING box."; \
        echo "Each box sends TWO Telegram messages, both prefixed DRILL - NOT REAL."; \
        echo "READ THE PER-BOX 'DRILL PASSED/FAILED' LINE, NOT the 29/29 tally —"; \
        echo "the tally cannot see the drill's exit code (v1.26)."; \
        read -rp "Send for real? (n = dry-run, no Telegram) [y/N]: " GO; \
        if [ "$GO" = "y" ]; then \
          $PY fleet.py run "cd ~/options-trader && venv/bin/python tests/blind_alert_selftest.py 2>&1 | tail -4; true"; \
        else \
          $PY fleet.py run "cd ~/options-trader && venv/bin/python tests/blind_alert_selftest.py --no-send 2>&1 | tail -4; true"; \
        fi; pause ;;
    0)  exit 0 ;;
    *)  echo "Invalid selection."; sleep 1 ;;
  esac
}

while true; do menu; done
