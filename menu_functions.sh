#!/usr/bin/env bash
# day_trader_pro/menu_functions.sh — GENERATED from devtools.sh — v1.1
# One function per menu item, body copied verbatim from the case block.
# Sourced by devtools.sh; named by menu_registry.sh. No numbers here.
#
# v1.1  2026-08-18  The six REPOINT items now ABORT when ask_url() returns
#       non-zero (empty answer). Without this the aborted prompt would pass an
#       empty string straight to `fleet.py repoint ""`, which prints a usage
#       error — recoverable, but it reads like a bug rather than like the
#       cancellation the operator asked for. Pairs with devtools v1.36.
# v1.0  2026-08-16  Extracted from devtools.sh v1.32 (the menu is data).

# Full spool-up (mock)
mi_full_spool_up_mock() {
    echo; DTP_MOCK=1 $PY orchestrator.py --mock --no-gate; pause
}

# EOD aggregate (mock)
mi_eod_aggregate_mock() {
    echo; DTP_MOCK=1 $PY eod_report.py --mock; pause
}

# Reset mock state
mi_reset_mock_state() {
    echo; reset_mock_state; pause
}

# Dry-run spool-up (real reads)
mi_dry_run_spool_up_real_reads() {
    echo; $PY orchestrator.py --dry-run --no-gate; pause
}

# Dry-run EOD aggregate (real reads)
mi_dry_run_eod_aggregate_real_reads() {
    echo; $PY eod_report.py --dry-run; pause
}

# Instance map
mi_instance_map() {
    echo; $PY instance_registry.py show; pause
}

# Reconcile map
mi_reconcile_map() {
    echo; $PY instance_registry.py reconcile; pause
}

# Swap / pin instance ID
mi_swap_pin_instance_id() {
    echo; $PY instance_registry.py swap; pause
}

# Control status
mi_control_status() {
    echo; $PY control_state.py status; pause
}

# ENABLE control
mi_enable_control() {
    echo; $PY control_state.py enable; pause
}

# DISABLE control
mi_disable_control() {
    echo; $PY control_state.py disable; pause
}

# Fleet list
mi_fleet_list() {
    echo; $PY fleet.py list; pause
}

# Fleet ping
mi_fleet_ping() {
    echo; $PY fleet.py ping; pause
}

# Run command (all running)
mi_run_command_all_running() {
    echo; read -rp "Command to run on all running boxes: " fc; $PY fleet.py run "$fc"; pause
}

# status.py + query.py      (one/all/some)
mi_status_py_query_py_one_all_some() {
    echo; SC=$(ask_scope); $PY fleet.py run "cd $INSTALL_DIR; python status.py; echo; python query.py" $SC; pause
}

# Pull trades.db            (one/all/some)
mi_pull_trades_db_one_all_some() {
    echo; SC=$(ask_scope); $PY fleet.py pull db $SC; pause
}

# Pull OHLC for a day       (one/all/some)
mi_pull_ohlc_for_a_day_one_all_some() {
    echo; SC=$(ask_scope); read -rp "Day (YYYY-MM-DD, ENTER=today): " D; D="${D:-$(date +%F)}"; $PY fleet.py pull ohlc --day "$D" $SC; pause
}

# Service status (bot + candle-feed)
mi_service_status_bot_candle_feed() {
    echo; SC=$(ask_scope); $PY fleet.py run 'echo "optionsbot=$(systemctl is-active optionsbot) candle-feed=$(systemctl is-active candle-feed)"' $SC; pause
}

# Journal tail (last N)
mi_journal_tail_last_n() {
    echo; SC=$(ask_scope); read -rp "How many journal lines [20]: " N; N="${N:-20}"; $PY fleet.py run "journalctl -u optionsbot -n ${N} --no-pager" $SC; pause
}

# Feed health (store freshness)
mi_feed_health_store_freshness() {
    echo; SC=$(ask_scope); $PY fleet.py run "echo \"candle-feed=\$(systemctl is-active candle-feed) store_write_age_s=\$(( \$(date +%s) - \$(stat -c %Y ${FEED_DB}-wal 2>/dev/null || stat -c %Y ${FEED_DB} 2>/dev/null || echo 0) ))\"" $SC; pause
}

# Bot log tail (last 20)
mi_bot_log_tail_last_20() {
    echo; SC=$(ask_scope); $PY fleet.py run "tail -20 ${INSTALL_DIR}/bot.log" $SC; pause
}

# Dry-run
mi_dry_run() {
    echo; $PY wake_and_bake.py --dry-run; pause
}

# FULL (wake->bake->restart->STOP)
mi_full_wake_bake_restart_stop() {
    echo; $PY wake_and_bake.py; pause
}

# Wake (one/all/some)
mi_wake_one_all_some() {
    echo; SC=$(ask_scope); $PY wake_and_bake.py --wake-only $SC; pause
}

# Bake only (sync, no restart - RTH-safe)
mi_bake_only_sync_no_restart_rth_safe() {
    echo; $PY wake_and_bake.py --bake-only; pause
}

# Leave on (skip shutdown)
mi_leave_on_skip_shutdown() {
    echo; $PY wake_and_bake.py --leave-running; pause
}

# EMERGENCY STOP (no EOD, no pycache, RTH-exempt, HALT-gated)
mi_emergency_stop_no_eod_no_pycache_rth_exempt() {
    echo; $PY wake_and_bake.py --shutdown-only; pause
}

# Check only
mi_check_only() {
    echo; U=$(ask_url) || { pause; return 0; }; $PY fleet.py repoint "$U" --check-only; pause
}

# FULL
mi_full() {
    echo; U=$(ask_url) || { pause; return 0; }; $PY fleet.py repoint "$U"; pause
}

# Full + wake
mi_full_wake() {
    echo; U=$(ask_url) || { pause; return 0; }; $PY fleet.py repoint "$U" --wake; pause
}

# No restart
mi_no_restart() {
    echo; U=$(ask_url) || { pause; return 0; }; $PY fleet.py repoint "$U" --no-restart; pause
}

# Scoped
mi_scoped() {
    echo; U=$(ask_url) || { pause; return 0; }; read -rp "Symbols (comma-sep, e.g. SPX,QQQ): " SY; $PY fleet.py repoint "$U" --only "$SY"; pause
}

# Mock preview
mi_mock_preview() {
    echo; U=$(ask_url) || { pause; return 0; }; $PY fleet.py repoint "$U" --mock --yes; pause
}

# Snapshot dir -> repo-ready tarball
mi_snapshot_dir_repo_ready_tarball() {
    echo; snapshot_dir; pause
}

# Test selection (mock)
mi_test_selection_mock() {
    echo; $PY selector.py --test; pause
}

# Test Telegram (real)
mi_test_telegram_real() {
    echo; $PY notify.py --test; pause
}

# PUSH -> GitHub  (FORCE; this server is source of truth)
mi_push_github_force_this_server_is_source_of_t() {
    echo; repo_push_force; pause
}

# PULL <- GitHub  (FORCE; GitHub is source of truth)
mi_pull_github_force_github_is_source_of_truth() {
    echo; repo_pull_force; pause
}

# Re-run consolidation -> fleet_trades_<date>.json (+ .csv)
mi_re_run_consolidation_fleet_trades_date_json() {
    echo; read -rp "Day to consolidate (YYYY-MM-DD, ENTER=today): " D; D="${D:-$(date +%F)}"; $PY consolidate_trades.py --date "$D"; pause
}

# Excursion report (MFE/MAE) -> reports/excursions_<date>.txt
mi_excursion_report_mfe_mae_reports_excursions() {
    echo; read -rp "Day (YYYY-MM-DD, ENTER=today): " D; D="${D:-$(date +%F)}"; \
        read -rp "Cumulative since (YYYY-MM-DD, ENTER=that day only): " S; \
        read -rp "Live rows? [y/N]: " LV; \
        ARGS="--date $D"; [ -n "$S" ] && ARGS="$ARGS --since $S"; [ "$LV" = "y" ] && ARGS="$ARGS --live"; \
        $PY excursion_report.py $ARGS; pause
}

# Trade breakdown (cross-day: regime/strategy/grade + regime x strategy)
mi_trade_breakdown_cross_day_regime_strategy_gr() {
    echo; read -rp "Since date (YYYY-MM-DD, ENTER=all): " SD; if [ -n "$SD" ]; then $PY trade_report.py --since "$SD"; else $PY trade_report.py; fi; pause
}

# FIT REPORT — everything for fitting in ONE text file (1 day or a range)
mi_fit_report_everything_for_fitting_in_one_tex() {
    echo; read -rp "Day, or END of range (YYYY-MM-DD, ENTER=today): " D; D="${D:-$(date +%F)}"; \
        read -rp "Cumulative since (YYYY-MM-DD, ENTER=that day only): " S; \
        read -rp "Skip the slow replay-corpus sections (ramps, A2 drift)? [y/N]: " NS; \
        ARGS="--date $D"; [ -n "$S" ] && ARGS="$ARGS --since $S"; [ "$NS" = "y" ] && ARGS="$ARGS --no-slow"; \
        echo "Running — the replay-corpus sections take minutes; output is a FILE, not this screen."; \
        $PY fit_report.py $ARGS; pause
}

# Run replay - today
mi_run_replay_today() {
    echo; if [ -x "$VALIDATE_SH" ]; then "$VALIDATE_SH"; else echo "missing/non-exec $VALIDATE_SH (chmod +x $OTV3_DIR/validate_regime.sh?)"; fi; pause
}

# Run replay - pick a date
mi_run_replay_pick_a_date() {
    echo; read -rp "Date (YYYY-MM-DD, ENTER=today): " D; D="${D:-$(date +%F)}"; if [ -x "$VALIDATE_SH" ]; then "$VALIDATE_SH" "$D"; else echo "missing/non-exec $VALIDATE_SH"; fi; pause
}

# View a day's report
mi_view_a_day_s_report() {
    echo; D_DEF="$(date +%F)"; read -rp "Date to view (YYYY-MM-DD, ENTER=${D_DEF}): " D; D="${D:-$D_DEF}"; if [ -x "$VALIDATE_SH" ]; then "$VALIDATE_SH" --report "$D"; else echo "missing/non-exec $VALIDATE_SH"; fi; pause
}

# View the diary (all days)
mi_view_the_diary_all_days() {
    echo; if [ -x "$VALIDATE_SH" ]; then "$VALIDATE_SH" --diary; else echo "missing/non-exec $VALIDATE_SH"; fi; pause
}

# Backfill missing days      (fills diary gaps that have tape)
mi_backfill_missing_days_fills_diary_gaps_that() {
    echo; read -rp "Rebuild ALL dated tapes (else only fill gaps)? [y/N]: " RB; if [ -x "$VALIDATE_SH" ]; then if [ "$RB" = "y" ]; then "$VALIDATE_SH" --backfill --rebuild; else "$VALIDATE_SH" --backfill; fi; else echo "missing/non-exec $VALIDATE_SH"; fi; pause
}

# A2 co-occurrence + HTF drift  (read-only; auto-finds replay logs)
mi_a2_co_occurrence_htf_drift_read_only_auto_fi() {
    echo; if [ -x "$OTV3_PY" ]; then (cd "$OTV3_DIR" && "$OTV3_PY" -m tests.a2_cooccurrence); else echo "missing $OTV3_PY (is ~/options-trader-v3 checked out with its venv?)"; fi; pause
}

# Live P&L standings (read-only)
mi_live_p_l_standings_read_only() {
    echo; read -rp "Push to Telegram too? [y/N]: " S; if [ "$S" = "y" ]; then $PY standings.py --send; else $PY standings.py; fi; pause
}

# Backfill missing OHLC (auto-batched)
mi_backfill_missing_ohlc_auto_batched() {
    echo; read -rp "Backfill date (YYYY-MM-DD, ENTER=today): " D; D="${D:-$(date +%F)}"; read -rp "Batch size (ENTER=5): " B; B="${B:-5}"; echo; $PY eod_backfill.py --date "$D" --batch "$B" --dry-run; echo; read -rp "Proceed with LIVE backfill (wakes/stops boxes)? [y/N]: " GO; [ "$GO" = "y" ] && $PY eod_backfill.py --date "$D" --batch "$B"; pause
}

# EOD conductor - full gated EOD (dry-run preview -> confirm -> run)
mi_eod_conductor_full_gated_eod_dry_run_preview() {
    echo; read -rp "Backfill batch size (ENTER=5): " B; B="${B:-5}"; echo; $PY eod_conductor.py --batch "$B" --dry-run; echo; read -rp "Run the LIVE EOD conductor now (gate->harvest->P&L+stop->backfill->consolidate->diary)? [y/N]: " GO; [ "$GO" = "y" ] && $PY eod_conductor.py --batch "$B"; pause
}

# OHLC 21-day fetch from yfinance (prompts symbol, default ^VIX)
mi_ohlc_21_day_fetch_from_yfinance_prompts_symb() {
    echo; read -rp "Symbol [^VIX]: " SY; SY="${SY:-^VIX}"; $PY tests/ohlc_fetch.py --symbol "$SY"; pause
}

# Rotate fleet tokens/secrets (pushes to running boxes)
mi_rotate_fleet_tokens_secrets_pushes_to_runnin() {
    echo; read -rp "Rotate against a SUBSET of symbols? (ENTER=all running): " SUBSET; \
        if [ -n "$SUBSET" ]; then $PY rotate_tokens.py --only $SUBSET; else $PY rotate_tokens.py; fi; pause
}

# Audit fleet credentials (read-only; shows which vars are set, no values)
mi_audit_fleet_credentials_read_only_shows_whic() {
    echo; read -rp "Audit a SUBSET of symbols? (ENTER=all running): " SUBSET; \
        if [ -n "$SUBSET" ]; then $PY rotate_tokens.py --audit --only $SUBSET; else $PY rotate_tokens.py --audit; fi; pause
}

# Verify fleet credentials WORK (TT SDK, Telegram, GitHub)
mi_verify_fleet_credentials_work_tt_sdk_telegra() {
    echo; read -rp "Verify a SUBSET of symbols? (ENTER=all running): " SUBSET; \
        if [ -n "$SUBSET" ]; then $PY rotate_tokens.py --verify --only $SUBSET; else $PY rotate_tokens.py --verify; fi; pause
}

# Verify control IAM role sees the fleet (read-only; no start/stop)
mi_verify_control_iam_role_sees_the_fleet_read() {
    echo; $PY check_iam.py; pause
}

# Blind-alert DRILL on the fleet (sends REAL Telegram, marked DRILL)
mi_blind_alert_drill_on_the_fleet_sends_real_te() {
    echo; echo "Fires the REAL blind-alert path on every RUNNING box."; \
        echo "Each box sends TWO Telegram messages, both prefixed DRILL - NOT REAL."; \
        echo "READ THE PER-BOX 'DRILL PASSED/FAILED' LINE, NOT the 29/29 tally —"; \
        echo "the tally cannot see the drill's exit code (v1.26)."; \
        read -rp "Send for real? (n = dry-run, no Telegram) [y/N]: " GO; \
        if [ "$GO" = "y" ]; then \
          $PY fleet.py run "cd ~/options-trader && venv/bin/python tests/blind_alert_selftest.py 2>&1 | tail -4; true"; \
        else \
          $PY fleet.py run "cd ~/options-trader && venv/bin/python tests/blind_alert_selftest.py --no-send 2>&1 | tail -4; true"; \
        fi; pause
}

# Feed maintenance window (fleet up, nothing on the wire) - currently OFF
mi_feed_maintenance_window_fleet_up_nothing_on() {
    echo; \
        if _maint_on; then \
          echo "Feed maintenance is currently ACTIVE."; \
          echo "Turning it OFF lets every box feed again on its next gate check."; \
          read -rp "Turn maintenance OFF? [y/N]: " GO; \
          if [ "$GO" = "y" ]; then \
            $PY fleet.py run "rm -f ~/options-trader/data/FEED_MAINTENANCE; echo MAINT=\$([ -f ~/options-trader/data/FEED_MAINTENANCE ] && echo ON || echo OFF)" --all; \
            rm -f "$_MAINT_MARK"; \
            echo; echo "Read the per-box MAINT= lines above - every one must say OFF."; \
            echo "A box still reading ON is still feed-silent and will trade blind."; \
          fi; \
        else \
          echo "Brings the fleet into a MAINTENANCE window: boxes can be up and"; \
          echo "worked on (option 14, bakes, pushes) with NOTHING on the wire."; \
          echo; \
          echo "The flag is checked live by candle_feed - no restart needed, and"; \
          echo "it SURVIVES a bake. Nothing removes it but you."; \
          echo "!! A box left flagged at 09:15 trades blind. The menu line stays RED."; \
          read -rp "Turn maintenance ON? [y/N]: " GO; \
          if [ "$GO" = "y" ]; then \
            $PY fleet.py run "mkdir -p ~/options-trader/data && touch ~/options-trader/data/FEED_MAINTENANCE; echo MAINT=\$([ -f ~/options-trader/data/FEED_MAINTENANCE ] && echo ON || echo OFF)" --all; \
            mkdir -p "$SCRIPT_DIR/data" && touch "$_MAINT_MARK"; \
            echo; echo "Read the per-box MAINT= lines above - every one must say ON."; \
            echo "A box that missed it is STILL FEEDING during your maintenance."; \
          fi; \
        fi; \
        read -rp "Enter to continue..." _
}

# ── S3 WAREHOUSE (added 2026-08-16, WH.11 — ADDITIVE, nothing replaced) ─────
# These sit ALONGSIDE the local reports, they do not replace them. The whole
# point of this stage is to run both sources and diff the OUTPUTS; a menu item
# that quietly switched a report's source would destroy the comparison.

# Warehouse inventory & cost
mi_warehouse_inventory_cost() {
    echo; $PY warehouse_cost.py; pause
}

# Warehouse inventory & cost (+ noncurrent versions)
mi_warehouse_inventory_versions() {
    echo; $PY warehouse_cost.py --versions; pause
}

# Rebuild a day's bundle FROM S3 -> reports/warehouse/
mi_warehouse_rebuild_bundle() {
    echo; read -rp "Date (YYYY-MM-DD, blank = today): " WD
    if [ -z "$WD" ]; then $PY warehouse_reader.py; else $PY warehouse_reader.py --date "$WD"; fi
    pause
}

# Compare S3 vs local for ONE date
mi_warehouse_compare_date() {
    echo; read -rp "Date (YYYY-MM-DD): " WD
    if [ -n "$WD" ]; then $PY warehouse_reader.py --date "$WD" --compare; fi
    pause
}

# Compare EVERY in-coverage date
mi_warehouse_compare_all() {
    echo; $PY warehouse_reader.py --all; pause
}

# Explain a date's divergence (lists the differing trade_ids)
mi_warehouse_explain_date() {
    echo; read -rp "Date (YYYY-MM-DD): " WD
    if [ -n "$WD" ]; then $PY warehouse_reader.py --date "$WD" --explain; fi
    pause
}

# Excursion report FROM THE WAREHOUSE (forces the bundle source)
mi_warehouse_excursion_report() {
    echo; read -rp "Date (YYYY-MM-DD): " WD
    if [ -n "$WD" ]; then
      $PY warehouse_reader.py --date "$WD" && \
      $PY excursion_report.py --date "$WD" --bundles-dir "$SCRIPT_DIR/reports/warehouse"
    fi
    pause
}

# Trade breakdown FROM THE WAREHOUSE (cross-day)
mi_warehouse_trade_report() {
    echo; echo "Reads reports/warehouse/ — run the rebuild for the dates you want first."
    $PY trade_report.py --bundles-dir "$SCRIPT_DIR/reports/warehouse"; pause
}

# Report PARITY - run 40 & 41 from BOTH sources and diff the OUTPUTS
mi_warehouse_report_parity() {
    echo; read -rp "Date (YYYY-MM-DD, blank = --since range): " WD
    if [ -n "$WD" ]; then
      $PY tools/report_parity.py --date "$WD"
    else
      read -rp "Since (YYYY-MM-DD): " WS
      if [ -n "$WS" ]; then $PY tools/report_parity.py --since "$WS"; fi
    fi
    pause
}
