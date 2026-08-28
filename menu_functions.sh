# ── v1.39 (2026-08-28) — NEW SENSORS ITEM "DECISIONS NOW" (r170) ────────────
# The per-tick plan record had readers only for AGGREGATES (PLAN BOARD counts
# verdicts; the ledger counts outcomes); nothing answered "what is every bot
# about to do RIGHT NOW". mi_sensor_decisions_now runs the box's own
# `query.py --decisions` across the chosen scope — one formatter, on the box,
# shared with anyone standing in a shell there. Registry gains the item under
# SENSORS after PLAN BOARD; numbers assign at render as ever.
# ── v1.38 (2026-08-27) — OPTION 60 ASKS WHICH SYMBOLS (one / some / all) ─────
# The OHLC backfill handler only ever asked for a BATCH SIZE, so a two-symbol
# gap woke five boxes. Operator: *"It wants to do them in groups of 5. We're not
# doing that. I just want those 2 only."* `eod_backfill.py --only` has existed
# all along (line 495); the menu never passed it. ENTER still means ALL; a list
# means exactly those, and the batch now DEFAULTS TO THE COUNT NAMED rather
# than padding to five. Accepts "CVX,UNH", "CVX, UNH" or "cvx unh".
#
# ── v1.37 (2026-08-22) — THE OBSOLETE VALIDATION SECTION IS DELETED ──────────
# Six handlers went with it: the Layer-1 confluence replay (today / pick-a-date
# / view report / view diary / backfill gaps) and the A2 co-occurrence tool.
# All six shelled into ~/options-trader-v3, a checkout that is not present, so
# every one printed "missing ... is ~/options-trader-v3 checked out?" — a menu
# section whose every entry was a dead end.
#
# ⚠️ DELETED, NOT REPOINTED. The confluence premise is what otv4 retired; there
# is nothing in v4 for these to validate. Operator, 2026-08-22: "Delete the
# entire validation section — I'm tired of seeing that term." If any of
# this analysis is wanted again it is REBUILT on v4's own data under a
# different name, so it cannot be mistaken for the artifact.
#
# The numbering is safe: devtools.sh assigns numbers at render from list
# position, so removing a section cannot desynchronise anything.
#!/usr/bin/env bash
# day_trader_pro/menu_functions.sh — GENERATED from devtools.sh — v1.2
# v1.2  2026-08-23  R SUITE section: two on-demand decision tools. Both run ON
#   CONTROL against the otv4 checkout's tests/ (S3 source; the tools print
#   their own SOURCE line, so an empty day and a broken read cannot look
#   alike). Neither touches a box, neither is scheduled — the operator's
#   ruling: decision tools run when a question is being asked, and the
#   scheduled pair (r_ledger nightly, edge_scan Fridays) belongs to
#   eod_analysis, not to a timer.
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
# Retire (stop the fleet)   (one/all/some)
mi_retire_one_all_some() {
    # r202 (2026-08-25) — REPLACES "Dry-run", which the operator never used.
    # ⚠️ THE OPERATOR WAS FORCED THROUGH OPTION 34 (FULL wake->bake->restart->
    # STOP) TO DO NOTHING BUT STOP THE FLEET — a whole cycle, including a
    # resync and a restart of every box, when all he wanted was the shutdown at
    # the end of it. `--shutdown-only` ALREADY EXISTED in wake_and_bake.py and
    # had no menu item, so the capability was there and unreachable.
    #
    # ⚠️ THIS IS NOT THE EOD PATH. --shutdown-only clears pycache and stops the
    # boxes cleanly with NO EOD and NO P&L harvest. Use it after maintenance or
    # a check, not at the close — the conductor owns the close because
    # chain_snapshots cannot be reconstructed after 16:00.
    echo
    echo "  RETIRE — OFF-HOURS clean stop. No EOD, no P&L harvest, no resync."
    echo "  For after maintenance or a check, outside the session."
    echo "  During RTH use option 38 (EMERGENCY STOP) — same mechanism,"
    echo "  different intent, and it warns about open positions."
    echo "  The CONDUCTOR owns the close: chain_snapshots cannot be"
    echo "  reconstructed after 16:00, so never use this at 15:59."
    SC=$(ask_scope)
    $PY wake_and_bake.py --shutdown-only $SC
    pause
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
    # r202 — SCOPE ADDED. This ran unscoped, so the only way to kill ONE
    # misbehaving box mid-session was to stop all fifteen.
    #
    # ⚠️ 33 AND 38 CALL THE SAME MECHANISM (--shutdown-only) AND THAT IS FINE —
    # the difference is INTENT AND TIMING, not plumbing. 33 is the off-hours
    # tidy-up; 38 is mid-session and abandons live positions. The banner below
    # is the difference that matters, because the mechanism will not warn you.
    #
    # ⚠️ VERIFIED IN SOURCE, NOT ASSUMED: the RTH guard at wake_and_bake.py:424
    # applies to `mode == "full"` ONLY, so --shutdown-only genuinely IS
    # RTH-exempt and needs no --force mid-session. (The module docstring at
    # line 82 claims the guard blocks shutdown-only — that line is WRONG and
    # would have someone believe an emergency stop is unavailable during a
    # session.)
    echo
    echo "  🔴 EMERGENCY STOP — RUNS DURING RTH, NO --force NEEDED."
    echo "  Stops by INSTANCE ID, not SSH: a box that cannot answer still dies."
    echo "  ⚠️ NO EOD. NO P&L HARVEST. ANY OPEN POSITION IS ABANDONED AT THE"
    echo "     BROKER — it does not get flattened, it is simply no longer"
    echo "     watched. You own it manually from that moment."
    echo "  For an orderly off-hours stop use option 33 (Retire) instead."
    SC=$(ask_scope)
    $PY wake_and_bake.py --shutdown-only $SC
    pause
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

# Trade breakdown (cross-day: strategy/grade/setup)
# ⚠️ LABEL AND HANDLER RENAMED r203 (2026-08-25). The old name promised a
# breakdown by a column that otv4 PHYSICALLY DROPPED in r65 — a query against
# it now RAISES rather than returning empty, so the promise was not merely
# stale, it was a crash waiting for the first person who selected it against a
# post-r65 trades.db.
# ⚠️ THE UNDERLYING trade_report.py STILL GROUPS BY THAT COLUMN — 8 live lines
# — and this rename does NOT fix that. It stops the MENU lying; the report
# itself is part of the day_trader_pro sweep still owed (125 live lines across
# 12 files, incl. fit_report.py and warehouse_reader.py).
mi_trade_breakdown_cross_day() {
    echo; read -rp "Since date (YYYY-MM-DD, ENTER=all): " SD; if [ -n "$SD" ]; then $PY trade_report.py --since "$SD"; else $PY trade_report.py; fi; pause
}

# FIT REPORT — everything for fitting in ONE text file (1 day or a range)
# FIT READINESS — per setup type: taken vs skipped, and is it fittable yet
mi_fit_readiness() {
    # r209 — REPLACES the old FIT REPORT, which is obsolete.
    # ⚠️ THAT REPORT SOURCED EVERYTHING FROM `trades` — the population that
    # FIRED. The question "is this setup ready to fit?" is mostly answered by
    # the population that did NOT, and strategy_note / gate_disposition /
    # plan_ledger did not exist when it was written. One of its four sections
    # had also never produced a number: it shelled into an otv3 checkout that
    # is not present, printing "SKIPPED, rc 127" in every report ever made.
    # 🔑 THE TEST IS COVERAGE, NOT VOLUME. A setup with 245 evaluations is NOT
    # fittable if 96% of its declines land on one rung — every observation sits
    # on one side of the boundary, so the data says where the line IS and
    # nothing about where it should be.
    echo
    echo "  Fit readiness — per setup type, TAKEN vs SKIPPED, with the"
    echo "  derived vector on both sides. Reads the derived store."
    read -rp "  Date (YYYY-MM-DD, ENTER=today), or START of a range: " D1
    read -rp "  END of range (ENTER = single day): " D2
    read -rp "  One setup only (ENTER = all): " SU
    read -rp "  Derived store path (ENTER = ~/options-trader/data/derived_store.db): " DB
    ARGS=""
    if [ -n "$D1" ] && [ -n "$D2" ]; then ARGS="--from $D1 --to $D2"
    elif [ -n "$D1" ];               then ARGS="--date $D1"; fi
    [ -n "$SU" ] && ARGS="$ARGS --setup $SU"
    [ -n "$DB" ] && ARGS="$ARGS --db $DB"
    $PY fit_readiness.py $ARGS
    pause
}

# Run replay - today
# Run replay - pick a date
# View a day's report
# View the diary (all days)
# Backfill missing days      (fills diary gaps that have tape)
# A2 co-occurrence + HTF drift  (read-only; auto-finds replay logs)
# Live P&L standings (read-only)
mi_live_p_l_standings_read_only() {
    echo; read -rp "Push to Telegram too? [y/N]: " S; if [ "$S" = "y" ]; then $PY standings.py --send; else $PY standings.py; fi; pause
}

# S3 SWEEP — warehouse hygiene (lists first; --apply required)
mi_s3_sweep() {
    # r212 — DELETE LIVES ON CONTROL ONLY. The traders write and never delete,
    # so a compromised or buggy box cannot destroy the warehouse.
    # ⚠️ IT LISTS BEFORE IT DELETES, ALWAYS. Deletion is the one irreversible
    # act in this system.
    echo
    echo "  1) Legacy-hash duplicates  (self-verifying: keeps the object whose"
    echo "     key == sha of its own record; a one-time migration artifact)"
    echo "  2) Culled symbols          (the 14 terminated 2026-08-20 — trades"
    echo "     AND tape; panel symbols are refused by a hard guard)"
    read -rp "  Choose 1 or 2 (ENTER = cancel): " C
    [ -z "$C" ] && { pause; return 0; }
    case "$C" in
      1) $PY s3_sweep.py --dups ;;
      2) $PY s3_sweep.py --culled ;;
      *) echo "  no."; pause; return 0 ;;
    esac
    echo
    read -rp "  Delete the objects listed above? Type DELETE to confirm: " OK
    if [ "$OK" = "DELETE" ]; then
        case "$C" in
          1) $PY s3_sweep.py --dups --apply ;;
          2) $PY s3_sweep.py --culled --apply ;;
        esac
    else
        echo "  cancelled — nothing deleted."
    fi
    pause
}

# EOD ANALYSIS — the reports, from S3, boxes stay off
mi_eod_analysis() {
    # r208 — the REPORTS half of the EOD split. eod_conductor_v2 owns the
    # CLOSE; this owns the reports and the two never overlap.
    # ⚠️ SAFE TO RE-RUN AND SAFE TO RUN LATE. Nothing here touches a box, so a
    # failed night can simply be run again tomorrow against the same bucket.
    echo
    echo "  EOD analysis — P&L, bundle, daily bars, label, excursion, coverage."
    echo "  Reads S3 and control-side state only. No boxes are woken."
    read -rp "  Date (YYYY-MM-DD, ENTER=today): " D
    read -rp "  Dry-run first? [Y/n]: " DR
    ARGS=""; [ -n "$D" ] && ARGS="--date $D"
    if [ "$DR" != "n" ]; then
        $PY eod_analysis.py $ARGS --dry-run
        echo
        read -rp "  Proceed for real? [y/N]: " GO
        [ "$GO" = "y" ] || { pause; return 0; }
    fi
    $PY eod_analysis.py $ARGS
    pause
}

# P&L from the WAREHOUSE (day or range; boxes not involved)
mi_pnl_from_warehouse() {
    # r207 — reads S3, never the boxes.
    # ⚠️ ITEM 54 (standings.py) SSHes INTO EVERY BOX, so seeing YESTERDAY's P&L
    # meant WAKING FIFTEEN MACHINES to answer a question about data already
    # sitting in the bucket. Its SQL is also hardcoded to today, so a past
    # session was unaskable at any price. 54 stays for the LIVE intraday read;
    # this is for everything else.
    echo
    echo "  P&L from the S3 warehouse. Boxes stay off."
    read -rp "  Date (YYYY-MM-DD, ENTER=today), or START of a range: " D1
    read -rp "  END of range (ENTER = single day): " D2
    read -rp "  Push to Telegram too? [y/N]: " S
    ARGS=""
    if [ -n "$D1" ] && [ -n "$D2" ]; then ARGS="--from $D1 --to $D2"
    elif [ -n "$D1" ];               then ARGS="--date $D1"; fi
    [ "$S" = "y" ] && ARGS="$ARGS --send"
    $PY pnl_s3.py $ARGS
    pause
}

# Backfill missing OHLC (auto-batched)
# 🔴 v1.38 — ASKS WHICH SYMBOLS. Operator, 2026-08-27: *"It wants to do them in
# groups of 5. We're not doing that. I just want those 2 only."* The handler
# only ever offered a BATCH SIZE, so a two-symbol gap woke five boxes. He had to
# be handed the raw `eod_backfill.py --only CVX,UNH --batch 2` line instead.
# ⚠️ `--only` HAS ALWAYS EXISTED (eod_backfill.py:495, "comma-separated symbols
# to limit to") — the menu simply never passed it.
# ⚠️ THE BATCH DEFAULTS TO THE NUMBER OF SYMBOLS NAMED, so picking two runs them
# as one batch of two rather than padding to five.
mi_backfill_missing_ohlc_auto_batched() {
    echo
    read -rp "Backfill date (YYYY-MM-DD, ENTER=today): " D; D="${D:-$(date +%F)}"
    echo
    echo "  Which boxes?"
    echo "    ENTER  = ALL symbols missing candles for that date"
    echo "    a list = only these, e.g.  CVX,UNH   or   CVX, UNH   or   cvx unh"
    read -rp "Symbols: " SY
    # normalise: strip spaces, split on commas or whitespace, upper-case
    SY="$(echo "$SY" | tr 'a-z' 'A-Z' | tr -s ', \t' ',' | sed 's/^,//; s/,$//')"
    if [ -n "$SY" ]; then
        ONLY="--only $SY"
        # one batch, sized to what was asked for — never pad to five
        DEF_B="$(echo "$SY" | tr ',' '\n' | grep -c .)"
        echo "  -> $DEF_B symbol(s): $SY"
    else
        ONLY=""
        DEF_B=5
        echo "  -> ALL missing symbols"
    fi
    read -rp "Batch size (ENTER=$DEF_B): " B; B="${B:-$DEF_B}"
    echo
    $PY eod_backfill.py --date "$D" $ONLY --batch "$B" --dry-run
    echo
    # ⚠️ THE LIVE RUN WAKES AND STOPS BOXES — that is why the dry run always
    # prints first and the confirm is explicit.
    read -rp "Proceed with LIVE backfill (wakes/stops boxes)? [y/N]: " GO
    [ "$GO" = "y" ] && $PY eod_backfill.py --date "$D" $ONLY --batch "$B"
    pause
}

# EOD conductor - full gated EOD (dry-run preview -> confirm -> run)
mi_eod_conductor_full_gated_eod_dry_run_preview() {
    # r217 — REPOINTED to eod_conductor_v2. Same preview-then-confirm shape the
    # operator already had; only the conductor underneath changed.
    #
    # ⚠️ THE DRY RUN HERE PROVES PLUMBING, NOT VERIFICATION. --dry-run never
    # SSHes and never drains, so it FABRICATES an OK verdict for every box —
    # a column of green that means nothing. Verified 2026-08-22: the dry run
    # showed 15/15 verified; a real --no-takedown run on NVDA immediately
    # returned SHORT. Use option (2) below to actually verify.
    #
    # ⚠️ AND (2) IS THE SAFE ONE TO EXPLORE WITH. --no-takedown drains and
    # verifies for real and stops NOTHING, so it can be run mid-session
    # without consequence — except that it stops the BOT on each box it
    # touches, which is why it is scoped to one symbol here.
    # ⚠️ VERIFY-ONLY IS OPTION 1 BECAUSE IT IS THE REAL PREVIEW. --dry-run
    # never SSHes, so it stamps "OK short=0" on every box whatever the truth
    # is — measured 2026-08-22: it reported 15/15 verified minutes before a
    # real run on NVDA came back SHORT. Leaving the fabricated one in the
    # first slot points the default reach at the check that cannot fail.
    echo
    echo "  1) VERIFY ONE BOX  — REAL drain + verify. Stops nothing. THE preview."
    echo "  2) LIVE CLOSE      — stop trading, drain, verify, take down per box"
    echo "  3) plumbing check  — enumerates the fleet; VERIFICATION IS FAKED"
    read -rp "  Choose 1/2/3 (ENTER = cancel): " C
    case "$C" in
      1) read -rp "  Symbol [NVDA]: " S; S="${S:-NVDA}"
         $PY eod_conductor_v2.py --no-takedown --only "$S" ;;
      # ⚠️ NO FAKE PREVIEW BEFORE THE LIVE RUN. Printing a fabricated OK and
      # then disclaiming it is theatre — it trains the operator to click past
      # a green screen. Option 1 is the preview; this asks for the word.
      2) echo
         echo "  This STOPS TRADING on every running box, drains to S3,"
         echo "  verifies, and takes down the ones that verified."
         read -rp "  Type CLOSE to confirm: " GO
         [ "$GO" = "CLOSE" ] && $PY eod_conductor_v2.py || echo "  cancelled." ;;
      3) echo "  (plumbing only — every OK below is fabricated)"
         $PY eod_conductor_v2.py --dry-run ;;
      *) echo "  cancelled." ;;
    esac
    pause
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

# Pre-open rehearsal — ask the fleet, then turn it on/off
# The flag itself still lives on each BOX at data/REHEARSAL_OFF, read LIVE by
# main.py every pass (no restart, survives a bake). Its PRESENCE disables, so a
# fresh or rebuilt box rehearses — the default catches things.
mi_rehearsal_toggle() {
    # r110 — ASK THE FLEET, THEN OFFER. No marker, no colour, no state on
    # control at all.
    #
    # 🔴 THREE REVISIONS WERE SPENT KEEPING A COPY HONEST. r108 mirrored item
    # 67: a marker file on CONTROL standing in for a flag that lives on the
    # BOXES, so the menu could be drawn instantly. 67's own comment admits the
    # weakness — "the marker is a HINT, not the truth" — and 67 at least has a
    # separate option that verifies against the boxes. 68 had none, and the
    # first time the two disagreed the row cheerfully reported the opposite of
    # reality: fifteen boxes OFF, the line saying ON, because control had never
    # been told. r109 then corrected the COLOUR of a label that was reading the
    # wrong machine, which fixed nothing.
    #
    # ⚠️ THE FAULT WAS A SECOND SOURCE OF TRUTH FOR A FACT THAT ALREADY EXISTS.
    # The boxes know. Nothing else needs to, and anything else that thinks it
    # does will eventually be wrong. So this option holds no state: it asks,
    # prints what came back, and only then offers to change it.
    #
    # ⚠️ THE COST, STATED: there is no at-a-glance row any more. You must select
    # 68 to learn the state. A menu line cannot poll fifteen machines on every
    # draw — that is real, and it is why 67 is built the way it is — so the
    # choice was between a line that is sometimes wrong and no line at all.
    # A line that is wrong is worse than a line that is absent.
    echo
    echo "Asking the fleet for the CURRENT rehearsal state..."
    echo
    _RS=$($PY fleet.py run "cd $INSTALL_DIR; echo REHEARSAL=\$([ -f data/REHEARSAL_OFF ] && echo OFF || echo ON)" --all)
    printf '%s\n' "$_RS"
    _ON=$(printf '%s' "$_RS" | grep -c "REHEARSAL=ON" || true)
    _OFF=$(printf '%s' "$_RS" | grep -c "REHEARSAL=OFF" || true)
    echo
    echo "  ON: $_ON     OFF: $_OFF"
    if [ "$_ON" -gt 0 ] && [ "$_OFF" -gt 0 ]; then
      echo "  ${_RED}🚩 THE FLEET DISAGREES WITH ITSELF - some boxes rehearse, some do not.${_RST}"
      echo "  Whichever way you answer below applies to ALL of them and settles it."
    fi
    echo
    echo "  ON  = the trading path runs outside RTH against live inputs and"
    echo "        PLACES NOTHING (entries_open() refuses; is_rth() AND"
    echo "        is_orb_complete() are both required, in paper AND live)."
    echo "  OFF = the trading path is dormant until 09:30, so a build that"
    echo "        cannot reach a decision is discovered AT THE BELL."
    echo
    read -rp "Set the rehearsal [on/off/enter=leave as is]: " _WANT
    case "$_WANT" in
      on|ON|y|Y)
        $PY fleet.py run "rm -f $INSTALL_DIR/data/REHEARSAL_OFF; echo REHEARSAL=\$([ -f $INSTALL_DIR/data/REHEARSAL_OFF ] && echo OFF || echo ON)" --all
        echo; echo "Every line above must read ON. Read them - this option asserts nothing."
        ;;
      off|OFF|n|N)
        $PY fleet.py run "mkdir -p $INSTALL_DIR/data && touch $INSTALL_DIR/data/REHEARSAL_OFF; echo REHEARSAL=\$([ -f $INSTALL_DIR/data/REHEARSAL_OFF ] && echo OFF || echo ON)" --all
        echo; echo "Every line above must read OFF. Read them - this option asserts nothing."
        ;;
      *) echo; echo "Left unchanged." ;;
    esac
    read -rp "Enter to continue..." _
}

# Debug logging — ask the fleet, then turn it on/off
# Same shape as the rehearsal above: ASK, then offer. No state on control.
# The flag lives on each BOX at data/DEBUG_LOG and main.py applies it at import
# AND on every tick, so it overrides however a box came to be in DEBUG — an
# edited config, a systemd Environment=, a library that called basicConfig —
# and removing it genuinely restores config.LOG_LEVEL.
mi_debug_log_toggle() {
    echo
    echo "Asking the fleet for the CURRENT log level..."
    echo
    _DS=$($PY fleet.py run "cd $INSTALL_DIR; echo LOG=\$([ -f data/DEBUG_LOG ] && echo DEBUG || grep -m1 '^LOG_LEVEL' config.py | sed 's/.*\"\\(.*\\)\".*/\\1/')" --all)
    printf '%s\n' "$_DS"
    _DBG=$(printf '%s' "$_DS" | grep -c "LOG=DEBUG" || true)
    _NRM=$(printf '%s' "$_DS" | grep -cE "LOG=(INFO|WARNING|ERROR)" || true)
    echo
    echo "  DEBUG: $_DBG     normal: $_NRM"
    if [ "$_DBG" -gt 0 ] && [ "$_NRM" -gt 0 ]; then
      echo "  ${_RED}🐞 THE FLEET DISAGREES WITH ITSELF - some boxes are verbose, some are not.${_RST}"
    fi
    echo
    echo "  DEBUG is not free: 2026-08-24 ran ~300k lines a box, most of it raw"
    echo "  DXFeed payloads, and it BURIES the decision lines a postmortem needs."
    echo "  Turn it on to chase something; turn it off when you are done."
    echo
    read -rp "Set debug logging [on/off/enter=leave as is]: " _WANT
    case "$_WANT" in
      on|ON|y|Y)
        $PY fleet.py run "mkdir -p $INSTALL_DIR/data && touch $INSTALL_DIR/data/DEBUG_LOG; echo LOG=\$([ -f $INSTALL_DIR/data/DEBUG_LOG ] && echo DEBUG || echo normal)" --all
        echo; echo "Every line above must read DEBUG. Applies on the next tick - no restart."
        ;;
      off|OFF|n|N)
        $PY fleet.py run "rm -f $INSTALL_DIR/data/DEBUG_LOG; echo LOG=\$([ -f $INSTALL_DIR/data/DEBUG_LOG ] && echo DEBUG || echo normal)" --all
        echo; echo "Every line above must read normal. The bot forces config.LOG_LEVEL on"
        echo "the next tick, whatever had put the box in DEBUG."
        ;;
      *) echo; echo "Left unchanged." ;;
    esac
    read -rp "Enter to continue..." _
}

# Disk usage — top consumers per box (one/all/some)
# Added 2026-08-25 after SPX filled its 6.7G root mid-bake and the failure read
# as "fatal: unable to write loose object file" — a git error for a disk
# problem. Three guesses were spent on the repo, /var and the journal before
# anyone measured the ROOT FILESYSTEM, which is where the answer was: /usr
# 2.4G, /swapfile 2.1G, /home 1.2G. This is that measurement, one keystroke.
# ⚠️ `du -x` STAYS ON ONE FILESYSTEM. Without it the walk descends into /proc,
# /sys and every snap loopback mount and the numbers become nonsense.
# ⚠️ EXITS 0 REGARDLESS. `2>/dev/null` swallows the permission noise from
# directories even root skips, and the pipeline's status comes from head — so a
# box with an unreadable path still reports what it CAN see rather than having
# its output discarded by the runner (the 2026-07-29 grep -c lesson).
mi_disk_usage() {
    echo
    SC=$(ask_scope)
    echo "Root filesystem usage, then the top consumers:"
    echo
    $PY fleet.py run 'df -h / | tail -1 | awk "{print \"DISK \"\$5\" used, \"\$4\" free of \"\$2}"; sudo du -xsh /* 2>/dev/null | sort -rh | head -6' $SC
    pause
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

mi_hotfix_launcher_repo_synch_flush() {
    # v1.37 (2026-08-22) — promoted from a notepad paste the operator ran
    # through option 14 nearly every session. A command typed by hand daily is
    # a command that will eventually be typed WRONG on the day it matters, and
    # this one stops trading services on 15 live boxes.
    #
    # ⚠️ `git checkout -- config.py` IS NOT OPTIONAL. Boxes carry a sed-dirty
    # config.py whenever LOG_LEVEL has been flipped to DEBUG, and `git pull`
    # REFUSES to overwrite a dirty file — the pull fails, the services restart
    # on the OLD code, and every surface reports success. That is exactly how
    # r59 sat on control all Friday while the boxes ran the bug it fixed.
    # Restoring config.py first also returns LOG_LEVEL to INFO.
    #
    # ⚠️ FEED FIRST, THEN A 5s GAP, THEN THE BOT. The bot's first tick reads
    # the store; starting it against a feed that has not connected gives it an
    # empty frame at the worst possible moment.
    echo
    echo "  Hotfix launcher — stop services, restore config.py, pull, purge"
    echo "  __pycache__, restart feed-then-bot, and report both states."
    echo "  Runs on RUNNING boxes only."
    read -rp "  Symbols (ENTER = ALL, or comma-sep e.g. NVDA,SPX): " hf_scope
    local hf_cmd='sudo systemctl stop optionsbot candle-feed; cd ~/options-trader && git checkout -- config.py && git pull --ff-only; find ~/options-trader -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null; sudo systemctl start candle-feed && sleep 5 && sudo systemctl start optionsbot && systemctl is-active candle-feed optionsbot'
    if [ -n "$hf_scope" ]; then
        $PY fleet.py run "$hf_cmd" --only "$hf_scope"
    else
        $PY fleet.py run "$hf_cmd"
    fi
    pause
}

# ── SENSORS (r201, 2026-08-25) ───────────────────────────────────────────────
# The r61-r70 work laid down ten new tables and two tools and gave the operator
# NO WAY TO READ ANY OF THEM. A sensor nobody can query is a sensor that does
# not exist — which is the same failure as the silent gates it was built to
# replace.
#
# ⚠️ EVERY ITEM IS READ-ONLY AND SCOPE-SELECTABLE. These run on the boxes where
# the data lives; nothing is pulled to control (the warehouse holds the
# archive, and the conductor redesign is what will read it).
#
# ⚠️ EACH ONE STATES ITS SOURCE TABLE. When a report is empty the next question
# is always "is the sensor broken or is the answer genuinely nothing", and
# naming the table is what lets the operator go look.

# Manifold health board          (one/all/some)
mi_manifold_health_board() {
    echo; echo "  Per-stream bulbs from tools/manifold_health.py."
    echo "  GREEN fresh · AMBER stale · RED missing · WHITE idle (outside RTH)"
    SC=$(ask_scope)
    # 🔴 `|| true` IS LOad-BEARING. manifold_health exits 1 whenever the board
    # is not GREEN — which is its JOB — and the fleet runner treats non-zero as
    # a failed box and DISCARDS STDOUT. Measured 2026-08-24 07:35: all 15 boxes
    # printed `rc=1` with NO OUTPUT, and the board they had computed was thrown
    # away. The tool was working perfectly; the menu was eating the answer.
    # ⚠️ THIS IS THE 2026-07-29 RULE IN A NEW PLACE: a fleet command must exit 0
    # REGARDLESS OF FINDINGS, or a legitimate red result is indistinguishable
    # from a crash. A health board is the worst possible place for that, because
    # "not green" is the exact case it exists to report.
    # ⚠️ AND `2>&1` — without it a traceback vanishes and rc=1 says nothing about
    # why. venv python for the same reason as everywhere else: bare python3
    # resolves outside the repo venv.
    $PY fleet.py run "cd $INSTALL_DIR && venv/bin/python tools/manifold_health.py 2>&1 || true" $SC
    pause
}

# Strategy notes: what each engine SAW   (one/all/some)
_r_tool() {  # $1 = tool filename under otv4 tests/
    local OTV4="${DTP_OTV4_DIR:-$HOME/options-trader-v4}"
    local TOOL="$OTV4/tests/$1"
    if [ ! -f "$TOOL" ]; then
        echo "  🔴 $TOOL missing — set DTP_OTV4_DIR (path fault, not an empty day)"
        pause; return
    fi
    read -rp "  Date (YYYY-MM-DD, blank = today) or range (A..B): " d
    local ARGS=()
    if [[ "$d" == *..* ]]; then ARGS=(--from "${d%%..*}" --to "${d##*..}");
    elif [ -n "$d" ]; then ARGS=(--date "$d"); fi
    "$PY" "$TOOL" "${ARGS[@]}"
    pause
}

# Stop / TP sweep — R surface over recorded excursions (S3)
mi_r_stop_sweep() {
    echo; echo "  Bounds, not points: a cell matters only when its PESSIMISTIC"
    echo "  net beats the recorded book. Reads the S3 warehouse from control."
    _r_tool stop_sweep.py
}

# Exit replay — trail fit on real premium paths (S3, the expensive one)
mi_r_exit_replay() {
    echo; echo "  Rebuilds each trade's premium path from the quote_series"
    echo "  batches and replays trail/stop/TP ladders. Expensive by design —"
    echo "  run it when a specific exit question is being asked."
    _r_tool exit_replay.py
}

# 🔴 r124 (2026-08-25) — THE COLUMN IS `signalled`, NOT `fired`.
# Operator, reading this report: "Those have not fired at all." He was right,
# and the header was telling him otherwise. Traced to ONE LINE in main.py:
#     w.writer.write(name, ctx, fired=signal is not None)
# `fired` means THE STRATEGY RETURNED A SIGNAL OBJECT. Nothing about dispatch,
# the pairing gate, the position check, or an order. So NFLX's TrendCS2nd|499
# is 499 ticks on which TC.6 produced a signal and was refused downstream every
# single time — and CRM's CondorLeg2nd|406|0|406 is a live second-leg plan
# re-signalling on 406 consecutive ticks with a position already open.
# ⚠️ THE OLD HEADER READ "fired AND declined", WHICH SCANS AS TRADED-VS-NOT.
# The gap between "signalled" and "traded" is exactly where every dispatch gate
# lives — the space the operator is trying to see into — and the report was
# collapsing it silently. Same failure class as the repo's own named enemy:
# output that renders cleanly while meaning something other than it appears.
# ⚠️ AND THE COUNTS ARE TICK-INFLATED. A persisted setup is re-read every tick,
# so ONE event counts hundreds of times (recorded 2026-08-11 about the
# predecessor: "liq_map.recent_sweep PERSISTS once set"). `signalled` is a
# count of TICKS, never of trades. The header now says so.

# ── ET DAY BOUNDS, COMPUTED ON CONTROL ────────────────────────────────────────
# 🔴 r125 (2026-08-25) — THE REPORTS WERE BUCKETING BY THE BOX'S DAY, AND THE
# BOXES RUN UTC. `date(ts,'unixepoch','localtime')` reads localtime as UTC on
# the fleet, so everything after 20:00 ET filed under TOMORROW. Operator, who
# had been living with it: "Any time I run a report for 'today' after the
# session ends it fails." That is this, exactly — and it means last night's
# whole evening of work was filed under 08-25 while we read it as 08-24.
# ⚠️ NOT AN OFFSET. The first fix written here was `'-4 hours'`, which is EDT
# and silently becomes wrong in November — the same DST trap that argues
# against setting the boxes to Eastern at all. `date` on control consults the
# tz database, so these bounds are correct on both sides of a DST change and
# on the two days a year when an ET day is 23 or 25 hours long.
# ⚠️ AND IT FILTERS RAW EPOCH. No conversion happens on the box, so the query
# is immune to whatever timezone any individual box is set to.
_et_bounds() {
    # ⚠️ THE NEXT DAY IS COMPUTED AS A DATE, THEN CONVERTED. Writing
    # `date -d "$1 00:00:00 +1 day"` looks right and is not: GNU date parses
    # the `+1` as a TIMEZONE OFFSET, not an increment, and returns a 19-hour
    # "day". Caught by asserting the span, which is why the span is asserted.
    _nxt=$(date -d "$1 +1 day" +%F 2>/dev/null)
    ET_FROM=$(TZ=America/New_York date -d "$1 00:00:00" +%s 2>/dev/null)
    ET_TO=$(TZ=America/New_York date -d "$_nxt 00:00:00" +%s 2>/dev/null)
    if [ -z "$ET_FROM" ] || [ -z "$ET_TO" ]; then
        echo "  bad date: $1 (expected YYYY-MM-DD)"; return 1
    fi
    return 0
}

mi_sensor_strategy_notes() {
    echo; echo "  Source: derived_store.db -> strategy_note"
    echo "  One row per strategy EVALUATION."
    echo "  ⚠️ signalled = the strategy RETURNED A SIGNAL on that tick."
    echo "     It is NOT a trade: dispatch, the pairing gate, the position"
    echo "     check and the entry gate all sit downstream. And a persisted"
    echo "     setup re-signals every tick, so one event counts many times."
    echo "     For trades taken, read trades.db - not this table."
    read -rp "  Date (YYYY-MM-DD, blank = today): " d
    [ -z "$d" ] && d=$(TZ=America/New_York date +%F)
    _et_bounds "$d" || { pause; return 0; }
    SC=$(ask_scope)
    $PY fleet.py run "cd $INSTALL_DIR; sqlite3 data/derived_store.db \"SELECT strategy, SUM(fired) AS signalled, COUNT(*)-SUM(fired) AS quiet, COUNT(*) AS looks FROM strategy_note WHERE ts_epoch >= $ET_FROM AND ts_epoch < $ET_TO GROUP BY strategy ORDER BY looks DESC;\" 2>&1; echo ok" $SC
    pause
}

# 🔴 r126b — THE PLAN BOARD. Ticks across, variables down — the operator's own
# picture of it: "a table with a column of ticks and rows of variables it is
# checking". Reads plan_tick (the spine: what fires it, what kills it, what it
# pays) joined to plan_check (long format: one row per VARIABLE per plan).
# ⚠️ DECLINES ARE THE POINT. A plan that never fired is the counterfactual arm
# the fit needs most, and it is exactly what strategy_note cannot express —
# that table records only that a strategy was ASKED.
mi_sensor_plan_board() {
    echo; echo "  Source: derived_store.db -> plan_tick + plan_check"
    echo "  Every plan, every cycle: verdict, R, and each variable it checked."
    echo "  ⚠️ A plan is not a trade. TAKE means the plan qualified, not that"
    echo "     anything was bought — the engine is OBSERVE-ONLY."
    read -rp "  Date (YYYY-MM-DD, blank = today): " d
    [ -z "$d" ] && d=$(TZ=America/New_York date +%F)
    _et_bounds "$d" || { pause; return 0; }
    SC=$(ask_scope)
    $PY fleet.py run "cd $INSTALL_DIR; sqlite3 -header -column data/derived_store.db \"SELECT strategy, verdict, COUNT(*) n, ROUND(MIN(r_now),2) r_lo, ROUND(MAX(r_now),2) r_hi, ROUND(AVG(underlying),2) px FROM plan_tick WHERE ts_epoch >= $ET_FROM AND ts_epoch < $ET_TO GROUP BY strategy, verdict ORDER BY strategy, verdict;\" 2>&1; echo; echo 'WHICH CHECK FAILED, AND HOW OFTEN:'; sqlite3 -header -column data/derived_store.db \"SELECT strategy, check_name, verdict, COUNT(*) n, ROUND(MIN(value),2) lo, ROUND(MAX(value),2) hi FROM plan_check WHERE ts_epoch >= $ET_FROM AND ts_epoch < $ET_TO GROUP BY strategy, check_name, verdict ORDER BY strategy, check_name, verdict;\" 2>&1; echo ok" $SC
    pause
}

# DECISIONS NOW: enter on / exit on, the live snapshot   (one/all/some)
# r170 (2026-08-28). Operator: "I need a reader outfitted in devtools and have
# query.py snapshot active trade decisions 'enter on' and 'exit on' for active
# plans." The FORMATTER LIVES ON THE BOX (otv4 query.py v4.2 --decisions) so
# this reader and a shell on the box always show the same thing; this item is
# fleet transport only. ENTER ON = the newest plan_tick row per strategy (the
# PREPARED trade and what it waits on, or the fault); EXIT ON = the newest
# <Strategy>/manage row per open position ("if this or this, out"); rows older
# than 5 minutes are flagged STALE by the box itself.
mi_sensor_decisions_now() {
    echo; echo "  Source: on-box query.py --decisions (plan_tick incl. /manage rows)"
    echo "  What every plan would do on the NEXT tick, as of the last one."
    echo "  ⚠️ A plan is not a trade: HOLD 'PREPARED' means armed, not filled."
    SC=$(ask_scope)
    $PY fleet.py run "cd $INSTALL_DIR; python query.py --decisions 2>&1; echo ok" $SC
    pause
}

# Plan ledger: intent and its outcome    (one/all/some)
mi_sensor_plan_ledger() {
    echo; echo "  Source: derived_store.db -> plan_ledger"
    echo "  Plans are INTENT. A plan can produce no trade at all, or two."
    echo "  WIPED_BY_RESTART is its own category - the cost of deploying"
    echo "  mid-session, which cost four boxes their setups on 2026-08-21."
    read -rp "  Date (YYYY-MM-DD, blank = today): " d
    [ -z "$d" ] && d=$(TZ=America/New_York date +%F)
    _et_bounds "$d" || { pause; return 0; }
    SC=$(ask_scope)
    $PY fleet.py run "cd $INSTALL_DIR; sqlite3 -header -column data/derived_store.db \"SELECT strategy, state, COALESCE(terminal_reason,'(live)') AS reason, COUNT(*) AS n FROM plan_ledger WHERE created_ts >= $ET_FROM AND created_ts < $ET_TO GROUP BY strategy, state, reason ORDER BY n DESC;\" 2>&1; echo ok" $SC
    pause
}

# Exit counterfactual: would a flow exit have beaten the stop?
mi_sensor_exit_counterfactual() {
    echo; echo "  Source: derived_store.db -> exit_counterfactual"
    echo "  RECORDS ONLY - the mechanical stop is untouched. bos_exit measured"
    echo "  34% / -\$7,085 against the trail's 96% / +\$30,696, so this idea"
    echo "  gets MEASURED before it is trusted."
    SC=$(ask_scope)
    $PY fleet.py run "cd $INSTALL_DIR; sqlite3 -header -column data/derived_store.db \"SELECT trade_id, strategy, reason, COUNT(*) AS evals, MAX(threat) AS peak_threat, MAX(would_fire) AS would_have FROM exit_counterfactual GROUP BY trade_id, strategy, reason ORDER BY peak_threat DESC LIMIT 25;\" 2>&1; echo ok" $SC
    pause
}

# Fire snapshot: the derived vector at entry
mi_sensor_fire_snapshot() {
    echo; echo "  Source: derived_store.db -> fire_snapshot (joins trades on trade_id)"
    echo "  Everything derived at the INSTANT a trade fired. Pre-r61 trades"
    echo "  have no row - that is honest, they genuinely had none."
    SC=$(ask_scope)
    $PY fleet.py run "cd $INSTALL_DIR; sqlite3 data/derived_store.db \"SELECT trade_id, datetime(fired_ts,'unixepoch') AS fired_utc, substr(payload,1,160) FROM fire_snapshot ORDER BY fired_ts DESC LIMIT 10;\" 2>&1; echo ok" $SC
    pause
}

# Surface: charm / vanna / GEX through the session
mi_sensor_surface() {
    echo; echo "  Source: derived_store.db -> surface_series"
    echo "  CHARM = dDelta/dt, VANNA = dDelta/dVol. Neither was computable"
    echo "  before the greeks series existed - chain_marks overwrote one row"
    echo "  per symbol, so there was no series to difference."
    SC=$(ask_scope)
    $PY fleet.py run "cd $INSTALL_DIR; sqlite3 -header -column data/derived_store.db \"SELECT strike, ROUND(AVG(charm),4) AS charm, ROUND(AVG(vanna),4) AS vanna, ROUND(MAX(gex)/1e6,2) AS gex_m, COUNT(*) AS n FROM surface_series WHERE ts_epoch > strftime('%s','now','-1 day') GROUP BY strike ORDER BY n DESC LIMIT 20;\" 2>&1; echo ok" $SC
    pause
}

# Indicators: ADX / ATR / VWAP series
mi_sensor_indicators() {
    echo; echo "  Source: derived_store.db -> indicator_series"
    echo "  ⚠️ THE ADX WOBBLE QUESTION. Friday's logs showed ADX swinging"
    echo "  16 -> 48 on the same symbols. Some real, some possibly window"
    echo "  artifact - and adx_at_entry is a column on every trade while"
    echo "  CONT_BREAKOUT_MIN_ADX is a live gate. This is how you tell."
    SC=$(ask_scope)
    $PY fleet.py run "cd $INSTALL_DIR; sqlite3 -header -column data/derived_store.db \"SELECT interval, COUNT(*) AS n, ROUND(MIN(adx),1) AS adx_lo, ROUND(MAX(adx),1) AS adx_hi, ROUND(AVG(adx),1) AS adx_avg, ROUND(AVG(vwap),2) AS vwap FROM indicator_series WHERE ts_epoch > strftime('%s','now','-1 day') GROUP BY interval;\" 2>&1; echo ok" $SC
    pause
}

# Forks: built vs rejected, WITH the reason
mi_sensor_forks() {
    echo; echo "  Source: derived_store.db -> fork_series"
    echo "  Six named reject reasons exist and none of them used to reach a"
    echo "  log - 'rails=absent' was ONE message covering six problems, which"
    echo "  is why the r59 diagnosis took two wrong turns."
    SC=$(ask_scope)
    $PY fleet.py run "cd $INSTALL_DIR; sqlite3 -header -column data/derived_store.db \"SELECT interval, CASE built WHEN 1 THEN 'BUILT' ELSE COALESCE(reject_reason,'?') END AS outcome, COUNT(*) AS n, ROUND(AVG(containment),3) AS contain FROM fork_series WHERE ts_epoch > strftime('%s','now','-1 day') GROUP BY interval, outcome ORDER BY n DESC;\" 2>&1; echo ok" $SC
    pause
}

# Levels: touch counts and retirements
mi_sensor_levels() {
    echo; echo "  Source: derived_store.db -> level_ledger"
    echo "  A touch is a HOLD; a close through RETIRES the level. Bodies"
    echo "  decide, wicks test."
    SC=$(ask_scope)
    $PY fleet.py run "cd $INSTALL_DIR; sqlite3 -header -column data/derived_store.db \"SELECT provenance, kind, COUNT(*) AS levels, SUM(touch_count) AS touches, SUM(CASE WHEN retired_ts IS NULL THEN 0 ELSE 1 END) AS retired FROM level_ledger GROUP BY provenance, kind ORDER BY touches DESC;\" 2>&1; echo ok" $SC
    pause
}

# Order flow: aggression and depth from the tape
mi_sensor_order_flow() {
    echo; echo "  Source: feed_store.db -> prints / quote_series"
    echo "  aggressor_side is buy vs sell INITIATED. bid_size/ask_size is depth"
    echo "  at the touch - the signal FRC.1 needed and never had."
    SC=$(ask_scope)
    $PY fleet.py run "cd $INSTALL_DIR; sqlite3 -header -column data/feed_store.db \"SELECT COALESCE(aggressor_side,'(untagged)') AS side, COUNT(*) AS prints, ROUND(SUM(size)) AS volume FROM prints WHERE ts_epoch > strftime('%s','now','-1 day') GROUP BY side;\" 2>&1; sqlite3 -header -column data/feed_store.db \"SELECT COUNT(*) AS quote_rows, ROUND(AVG(bid_size)) AS avg_bid_sz, ROUND(AVG(ask_size)) AS avg_ask_sz FROM quote_series WHERE ts_epoch > strftime('%s','now','-1 day');\" 2>&1; echo ok" $SC
    pause
}
