#!/usr/bin/env bash
# day_trader_pro/menu_registry.sh — v1.13
# v1.13 (2026-09-06) — dtp r305 / DEV.5. TWO MOVES AND A RENAME, operator's.
#   · ORB budget & spot -> FLEET, directly after status.py + query.py. It reads
#     LIVE box state, so it sat oddly in DIAGNOSTICS beside an external data
#     fetch; next to the per-box status view it is the same kind of question.
#   · OHLC 21-day fetch (yfinance) -> the alert-path section, which is RENAMED
#     **EXTERNAL RESOURCES**. 🔑 The rename is the point: Telegram and yfinance
#     are both THIRD PARTIES the fleet depends on, and the section now means
#     "prove an outside path still works" rather than "alerting".
#   · DIAGNOSTICS is REMOVED — both its items moved out and an empty heading is
#     a line on a menu scrolled on a phone.
#   🔴 THE LAND ITEM MOVES AGAIN: 41 -> 42. Item count is unchanged at 71, but
#   ORB crossed from BELOW LAND to ABOVE it, so everything from LAND down shifts
#   by one. (yfinance moved entirely below LAND and changes nothing.)
# v1.12 (2026-09-06) — dtp r304 / DEV.4 — THE MENU REORGANISED: 86 ITEMS -> 71.
#   A full pass with the operator, item by item. TEN CUT: the four mock/offline
#   items (spool-up, EOD aggregate, reset mock state, repoint mock preview, test
#   selection) which prove the code runs and say nothing about the fleet; the
#   dry-run EOD aggregate, which dry-ran a report DISABLED in the live chain;
#   the two box->control PULLS, on the operator's *"it would be a strange thing
#   to pull candles onto control after we spent so much time severing those
#   connections"* — the S3-native rebuild already exists; RETIRE, which ran the
#   BYTE-IDENTICAL command to EMERGENCY STOP; and the LAND dry run.
#   THREE MERGES, each a flag matrix rendered as menu lines: four repoint items
#   (FULL / +wake / no-restart / scoped) -> one that prompts; two S3 compares
#   (one date / every date) -> one where ENTER means every; and the warehouse
#   trade breakdown, which passed `--bundles-dir` explicitly — r187 had ALREADY
#   MADE THE WAREHOUSE THE DEFAULT, so it was the same report with a redundant
#   argument, not a second source.
#   🔑 MAINTENANCE IS NOW IN PREREQUISITE ORDER, not by force: Wake -> Bake ->
#   Leave-on -> Hotfix -> FULL -> EMERGENCY STOP. Operator: *"they have to be
#   awake to synch, hence wake is before them."* Reading top to bottom now tells
#   you what each item ASSUMES.
#   ⚠️ NINE MENU-NUMBER CITATIONS FIXED, AND EVERY ONE WAS ALREADY WRONG —
#   labels and comments citing "option 33", "option 38", "option 14", "run 40 &
#   41". Numbers are assigned by `menu_render` from a loop and are guaranteed to
#   move; items now cite each other BY LABEL. REPORT PARITY's label no longer
#   names two numbers that had rotted twice over.
#   ⚠️ UTILITIES WAS A DUMPING GROUND — eleven items across four subjects. It is
#   now CREDENTIALS (read first, write last), ALERT PATHS, SESSION TOGGLES and
#   DIAGNOSTICS, with disk usage moved to S3 WAREHOUSE where the disk ceiling
#   work lives.
#   🔴 THE LAND ITEM MOVES: 54 -> 41. Everything cut sat above it.
# — v1.11 (2026-09-06) — dtp r303. Label only: "(bot + candle-feed)" ->
#   "(bot + feed + shadow)". 🔑 NO ITEM ADDED OR REMOVED, so `menu_render`
#   assigns exactly the same numbers as before — **the LAND item does not
#   move.** The function name is unchanged too: renaming it would touch the
#   registry, the dispatcher and every citation for a cosmetic gain, and the
#   operator cites items BY LABEL, which is what changed.
# — v1.10 (2026-09-05) — dtp r278. LAND A TARBALL, and its dry run, in the
#   CONTROL REPO section beside the two GitHub force-syncs — the same
#   subject: this checkout against the remote.
#   🔑 IT PASSES THE r242 TEST rather than dodging it. That ruling removed
#   three items because a STUDY is run once to answer a question and belongs
#   on the CLI. A deploy is the opposite: it is the single most repeated act
#   in this project, done by hand every session since r235, and it is exactly
#   what "items here are things run to fly the fleet — status, DEPLOYS, EOD,
#   warehouse hygiene" already names.
#   ⚠️ AND IT REVERSES LAND.1 AT THE OPERATOR'S OWN REQUEST (2026-09-05).
#   That ruling assumed an installer would call the lander; none ever did.
#   Numbers shift again — cite items by LABEL, never by number (C.15).
# — v1.9 (2026-09-04) — dtp r274. Stop forensics registered in SENSORS. It asks
#   a question no other item can: for a stopped-out trade, what was the BEST
#   mark it ever reached.
# — v1.8 (2026-09-04) — dtp r270. PLAN GATES registered in the SENSORS block,
#   beside PLAN BOARD and Plan ledger. It answers a question neither of those
#   can: which rungs FAIL, as a rate, with the pass count beside them.
#   ⚠️ THIS IS NOT THE r242 CASE. r242 removed three items because a STUDY is
#   run once to answer a question and belongs in tools/ with real arguments.
#   This is a SENSOR — the same shape as PLAN BOARD, which is already an item —
#   and it is how you find out why a strategy has not fired.
# — v1.7 (2026-09-01) — r242. 🔴 THE THREE ITEMS r238/r241 ADDED ARE REMOVED.
# Operator, 2026-09-01: "don't keep adding more shit to devtools. We run those
# as separate studies from the CLI."
# 🔑 THE LINE: THIS MENU IS THE OPERATING LOOP, NOT A TOOL DRAWER. Items here
# are things run to fly the fleet — status, deploys, EOD, warehouse hygiene.
# A STUDY is run once to answer a question and then argued about; it belongs
# on the CLI where it can take real arguments, be piped, and be re-run with a
# different range without a prompt in between. Same ruling as LAND.1, where
# land.sh got no menu item: "installer scripts should call it, not me manually
# running it."
# ⚠️ EVERY ITEM COSTS THE OPERATOR A SCAN OF AN 84-LINE MENU on a phone, so
# an item that earns its place must be one he reaches for repeatedly.
# — v1.6 (2026-09-01) — r241. Butterfly PIN STUDY: which condition refuses,
# pin_em_fraction by hour WITHIN each day, and |charm| by hour beside it.
# — v1.5 (2026-09-01) — r238. Two S3 items added: WAREHOUSE MAP, which
# regenerates docs/WAREHOUSE_MAP.md from the bucket, and BUTTERFLY REACH, a
# one-day probe that proves the fetch-to-local-cache path and leaves only its
# report behind. Item numbers shift, which is why items are cited by LABEL
# and never by number (C.15).
# v1.4 (2026-09-01) — r206. NEW ITEM "ORB budget & spot (every running box)".
#   The two Warehouse inventory rows merge into one that prompts for the
#   version pass. ⚠️ ITEM NUMBERS SHIFT AGAIN — second renumber in two days,
#   which is why items are cited by LABEL and never by number.
# v1.3 (2026-08-31) — r202. NEW ITEM "TRADES TAKEN" beside the cross-day
#   breakdown: one line per trade, phone width.
# v1.2 (2026-08-29) — r189 / dtp r230. THE EXCURSION REPORT IS RETIRED AND THE
#   R LEDGER TAKES ITS PLACE. Operator concurred with the r188 recommendation.
#   BOTH excursion items go — the local one and its FROM THE WAREHOUSE twin —
#   because they are one script and retiring a report means retiring it from
#   both sources, not moving it to the other one.
#   🔴 THE SCRIPT ITSELF IS NOT DELETED. `excursion_report.py` still has one
#   caller, `tools/report_parity.py`, and the nightly `eod_analysis` phase
#   r186 just repointed. Deleting it would break a tool whose own fate is a
#   separate question (RPT.3). A retired MENU ITEM and a deleted FILE are
#   different decisions and collapsing them is how a working caller breaks.
#   NEW: R ledger — R, expectancy, capture, giveback, and the never-favourable
#   split that was the excursion report's one unique measurement. It already
#   ran nightly inside the conductor and could not be asked for on demand
#   (RPT.2); `_r_tool` takes it with no new plumbing.
#   ALSO: the S3 WAREHOUSE section no longer says "runs ALONGSIDE the local
#   reports" (C.16). After r184-r188 there is no local report left to run
#   alongside — same stale-framing class the R SUITE qualifier had.
# day_trader_pro/menu_registry.sh — v1.1
# v1.1 (2026-08-29) — r188 / dtp r229. TRADES DATA and R SUITE ARE ONE SECTION.
#   Operator: "TRADES DATA should be merged with R SUITE", and "the control
#   side comment is unnecessary — I'm aware our data is on s3 and we are
#   presently repointing or eliminating." Both were reports over the same
#   closed-trade population, split only by which project built them, and the
#   parenthetical described a migration that is nearly finished rather than a
#   property of the items. "S3 WAREHOUSE (read-only; runs ALONGSIDE the local
#   reports)" carries the same stale framing and is left for a separate call.
#   ⚠️ FREE BY CONSTRUCTION, AND THAT IS THE POINT OF THIS FILE. Every number
#   shifts — the two R items move from 31/32 into the thirties beside the
#   trade reports, and everything after moves up two — and nothing anywhere
#   stores, compares or writes down a menu number, so a reorder cannot
#   desynchronise anything. That property was bought by the v1.35 conversion
#   after the July 22 incident, and this is the first change to spend it.
#   ⚠️ CONSEQUENCE FOR PROSE, WHICH THE CODE CANNOT ENFORCE: any document or
#   changelog naming an item BY NUMBER is now wrong. Refer to items by LABEL.
#   Also: the Trade breakdown LABEL still advertised a "grade" dimension that
#   r187 removed (every v4 row is UNGRADED). A menu label is the only
#   description most items ever get, so a stale one is a stale doc.
# day_trader_pro/menu_registry.sh — GENERATED DRAFT, review before use
# Generated by tools/menu_extract.py from devtools.sh.
#
# THERE ARE NO NUMBERS IN THIS FILE. devtools.sh assigns them at
# render time from list position, so reordering this list, inserting
# a section, or deleting an item cannot desynchronise anything.
#
# Each ITEM names a function in menu_functions.sh — bodies are kept
# verbatim there, so multi-line handlers are not flattened.

MENU=(

  "SECTION|REGISTRY & MASTER SWITCH"
  "ITEM|Instance map|mi_instance_map"
  "ITEM|Reconcile map|mi_reconcile_map"
  "ITEM|Swap / pin instance ID|mi_swap_pin_instance_id"
  "ITEM|Control status|mi_control_status"
  "ITEM|ENABLE control|mi_enable_control"
  "ITEM|DISABLE control|mi_disable_control"

  "SECTION|FLEET (inspect & fan-out)"
  "ITEM|Fleet list|mi_fleet_list"
  "ITEM|Fleet ping|mi_fleet_ping"
  "ITEM|Run command (all running)|mi_run_command_all_running"
  "ITEM|status.py + query.py      (one/all/some)|mi_status_py_query_py_one_all_some"
  "ITEM|ORB budget & spot (every running box)|mi_orb_budget_fleet"
  "ITEM|Dry-run spool-up (real reads)|mi_dry_run_spool_up_real_reads"

  "SECTION|SENSORS (derived stores; read-only, one/all/some)"
  "ITEM|Manifold health board|mi_manifold_health_board"
  "ITEM|Strategy notes        (what each engine SAW - signals, not trades)|mi_sensor_strategy_notes"
  "ITEM|PLAN BOARD            (every plan, every check, per tick)|mi_sensor_plan_board"
  "ITEM|DECISIONS NOW         (enter on / exit on, live snapshot)|mi_sensor_decisions_now"
  "ITEM|Plan ledger           (intent + terminal reason)|mi_sensor_plan_ledger"
  "ITEM|PLAN GATES            (every rung, PASS and FAIL, from S3)|mi_sensor_plan_gates"
  "ITEM|Stop forensics        (did the stop cut winners or limit losers?)|mi_sensor_stop_forensics"
  "ITEM|Exit counterfactual   (flow vs the stop)|mi_sensor_exit_counterfactual"
  "ITEM|Fire snapshot         (derived vector at entry)|mi_sensor_fire_snapshot"
  "ITEM|Surface               (charm / vanna / GEX)|mi_sensor_surface"
  "ITEM|Indicators            (ADX / ATR / VWAP series)|mi_sensor_indicators"
  "ITEM|Forks                 (built vs reject reason)|mi_sensor_forks"
  "ITEM|Levels                (touches + retirements)|mi_sensor_levels"
  "ITEM|Order flow            (aggression + depth)|mi_sensor_order_flow"

  "SECTION|DEBUG / LOGS (remote; one/all/some)"
  "ITEM|Service status (bot + feed + shadow)|mi_service_status_bot_candle_feed"
  "ITEM|Journal tail (last N)|mi_journal_tail_last_n"
  "ITEM|Feed health (store freshness)|mi_feed_health_store_freshness"
  "ITEM|Bot log tail (last 20)|mi_bot_log_tail_last_20"

  "SECTION|MAINTENANCE (wake_and_bake) - prerequisite order"
  "ITEM|Wake|mi_wake_one_all_some"
  "ITEM|Bake only (sync, no restart - RTH-safe)|mi_bake_only_sync_no_restart_rth_safe"
  "ITEM|Leave on (wake, sync, restart - fleet stays up)|mi_leave_on_skip_shutdown"
  "ITEM|Hotfix launcher (repo synch & flush)|mi_hotfix_launcher_repo_synch_flush"
  "ITEM|FULL (wake->bake->restart->STOP)|mi_full_wake_bake_restart_stop"
  "ITEM|EMERGENCY STOP — mid-session, abandons positions (one/all/some)|mi_emergency_stop_no_eod_no_pycache_rth_exempt"

  "SECTION|REPOINT (migrate fleet -> new repo)"
  "ITEM|Snapshot dir -> tarball (the held state before a repoint)|mi_snapshot_dir_repo_ready_tarball"
  "ITEM|Check only|mi_check_only"
  "ITEM|REPOINT the fleet (asks scope, wake, restart)|mi_repoint"

  "SECTION|CONTROL REPO (this checkout <-> GitHub, force sync)"
  "ITEM|PUSH -> GitHub  (FORCE; this server is source of truth)|mi_push_github_force_this_server_is_source_of_t"
  "ITEM|PULL <- GitHub  (FORCE; GitHub is source of truth)|mi_pull_github_force_github_is_source_of_truth"
  "ITEM|LAND a tarball from /home/ubuntu (verify -> commit -> push -> clean)|mi_land_tarball"

  "SECTION|TRADE REPORTS"
  "ITEM|Trade breakdown FROM THE WAREHOUSE (cross-day, day one onward)|mi_trade_breakdown_cross_day"
  "ITEM|TRADES TAKEN  (one line per trade, phone width)|mi_trades_taken"
  "ITEM|Live P&L standings (reads the BOXES; must be up)|mi_live_p_l_standings_read_only"
  "ITEM|P&L from WAREHOUSE (day or range; boxes off)|mi_pnl_from_warehouse"

  "SECTION|R SUITE (fitting)"
  "ITEM|FIT READINESS — per setup: taken vs skipped, is it fittable yet|mi_fit_readiness"
  "ITEM|Stop / TP sweep       (R surface over excursions)|mi_r_stop_sweep"
  "ITEM|Exit replay           (trail fit on real premium paths)|mi_r_exit_replay"
  "ITEM|R LEDGER              (R, expectancy, capture + selection vs extension)|mi_r_ledger"

  "SECTION|EOD & DATA REPAIR"
  "ITEM|Re-run consolidation -> fleet_trades_<date>.json (+ .csv)|mi_re_run_consolidation_fleet_trades_date_json"
  "ITEM|EOD analysis — all reports from S3 (boxes off)|mi_eod_analysis"
  "ITEM|Backfill missing OHLC (auto-batched)|mi_backfill_missing_ohlc_auto_batched"
  "ITEM|EOD conductor v2 (verify one box / live close / plumbing)|mi_eod_conductor_full_gated_eod_dry_run_preview"

  "SECTION|CREDENTIALS (read first, write last)"
  "ITEM|Audit fleet credentials (read-only; shows which vars are set, no values)|mi_audit_fleet_credentials_read_only_shows_whic"
  "ITEM|Verify fleet credentials WORK (TT SDK, Telegram, GitHub)|mi_verify_fleet_credentials_work_tt_sdk_telegra"
  "ITEM|Verify control IAM role sees the fleet (read-only; no start/stop)|mi_verify_control_iam_role_sees_the_fleet_read"
  "ITEM|Rotate fleet tokens/secrets (pushes to running boxes)|mi_rotate_fleet_tokens_secrets_pushes_to_runnin"

  "SECTION|EXTERNAL RESOURCES (Telegram, market data — prove the path)"
  "ITEM|Test Telegram (real)|mi_test_telegram_real"
  "ITEM|Blind-alert DRILL on the fleet (sends REAL Telegram, marked DRILL)|mi_blind_alert_drill_on_the_fleet_sends_real_te"
  "ITEM|OHLC 21-day fetch from yfinance (prompts symbol, default ^VIX)|mi_ohlc_21_day_fetch_from_yfinance_prompts_symb"

  "SECTION|SESSION TOGGLES"
  "ITEM|Feed maintenance window (fleet up, nothing on the wire) - currently OFF|mi_feed_maintenance_window_fleet_up_nothing_on"
  "ITEM|Pre-open rehearsal — ask the fleet, then turn it on/off|mi_rehearsal_toggle"
  "ITEM|Debug logging — ask the fleet, then turn it on/off|mi_debug_log_toggle"


  "SECTION|S3 WAREHOUSE (inventory, hygiene, rebuilds and parity)"
  "ITEM|S3 SWEEP — hygiene (dups / culled symbols; lists first)|mi_s3_sweep"
  "ITEM|Warehouse inventory & cost (asks about noncurrent versions)|mi_warehouse_inventory_cost"
  "ITEM|Rebuild a day's bundle FROM S3 -> reports/warehouse/|mi_warehouse_rebuild_bundle"
  "ITEM|Compare S3 vs local (ENTER = every in-coverage date)|mi_warehouse_compare"
  "ITEM|Explain a date's divergence (lists trade_ids)|mi_warehouse_explain_date"
  "ITEM|REPORT PARITY - trade breakdown from BOTH sources, diff OUTPUTS|mi_warehouse_report_parity"
  "ITEM|Disk usage — top consumers per box (one/all/some)|mi_disk_usage"
)

# ── render + dispatch, the whole of it ──────────────────────────────
# The number is a loop counter. It is never stored, never compared, and never
# written down anywhere — which is the entire point.
# One item's label is LIVE, not static: the feed-maintenance row turns red when
# the flag is on. It used to be printed between two heredocs for exactly this
# reason. Here it is a label override, so the item stays in the list like any
# other and nothing special-cases its position.
_menu_label() {
  case "$1" in
    "Feed maintenance window"*)
      if _maint_on; then
        printf '%s' "${_RED}*** FEED MAINTENANCE IS ACTIVE - no tape is being collected ***${_RST}"
      else
        printf '%s' "Feed maintenance window (fleet up, nothing on the wire) - currently OFF"
      fi ;;
    *) printf '%s' "$1" ;;
  esac
}

# ── 🔴 THE BANNER READS ITS VERSION FROM devtools.sh, IT IS NOT TYPED HERE ──
# It said "v1.35" against a v1.39 header on 2026-08-25 — FOUR revisions stale,
# and it had drifted before: the file's own v1.28 note records the banner
# reading v1.26 while the header had moved on.
#
# ⚠️ THE CAUSE IS THAT THE BANNER LIVES IN A DIFFERENT FILE FROM THE HEADER IT
# QUOTES. Bumping devtools.sh cannot move a literal in menu_registry.sh, so the
# standing "title == newest changelog entry" rule was being followed and the
# banner still lied. A rule that a careful person can obey while the output
# stays wrong is not a rule, it is a trap.
#
# ⚠️ DERIVED, NOT DUPLICATED. There is now ONE place the version is written.
_devtools_version() {
  local d="${BASH_SOURCE%/*}/devtools.sh"
  sed -n 's/^# day_trader_pro\/devtools\.sh — \(v[0-9.]*\).*/\1/p' "$d" \
    2>/dev/null | head -1
}

menu_render() {
  local _ver
  _ver="$(_devtools_version)"
  [ -z "$_ver" ] && _ver="(version unreadable)"
  printf '======================================================\n'
  printf '  Day Trader Pro — devtools  %s Service Menu\n' "$_ver"
  printf '======================================================\n'
  local i=0 kind rest label
  for entry in "${MENU[@]}"; do
    IFS='|' read -r kind rest <<< "$entry"
    if [ "$kind" = "SECTION" ]; then
      printf '\n %s:\n' "$rest"
    else
      i=$((i+1)); label="$(_menu_label "${rest%%|*}")"
      printf '  %2d) %s\n' "$i" "$label"
    fi
  done
  printf '\n   0) Exit\n'
  printf '======================================================\n'
}

menu_dispatch() {
  local want="$1" i=0 kind rest
  [ "$want" = "0" ] && return 9
  for entry in "${MENU[@]}"; do
    IFS='|' read -r kind rest <<< "$entry"
    [ "$kind" = "SECTION" ] && continue
    i=$((i+1))
    if [ "$i" = "$want" ]; then eval "${rest#*|}"; return 0; fi
  done
  echo "no such option: $want"; return 1
}
