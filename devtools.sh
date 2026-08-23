#!/usr/bin/env bash
# day_trader_pro/devtools.sh — v1.54
# v1.54 (2026-08-23) — THE CONDUCTOR VERIFY WAS TIMING OUT AT 22 SECONDS.
# ssh_util.ssh_run uses SSH_CONNECT_TIMEOUT(12)+10, and --verify walks 200+
# prefixes against S3 — minutes of work. NVDA returned NO_ANSWER because the
# TRANSPORT gave up, not the box: a timeout is indistinguishable from a silent
# box, so the conductor correctly refused to take it down for a reason that did
# not exist. Now 900s via DTP_VERIFY_TIMEOUT. The operator standing rule
# already said "--verify must NOT go through option 14" — same ceiling; I built
# on fleet._exec without carrying it across. Also: the DAILY_BARS phase label
# said "yfinance" when it rebuilds from the 1m tape.
# v1.53 (2026-08-25) — the conductor item now leads with VERIFY ONE BOX. The
# fabricated --dry-run was in the first slot, so the default reach was the
# check that CANNOT FAIL: it stamps OK on every box without SSHing, and on
# 2026-08-22 it reported 15/15 verified minutes before a real run on NVDA came
# back SHORT. The live path no longer prints a fake preview and then disclaims
# it — that trains the operator to click past a green screen.
# v1.52 (2026-08-25) — --manifest now works on --dups. It was wired into the
# culled and dead-stream branches and not that one, so the SLOWEST sweep (one
# GET per object, ~35 min over 40k chain snapshots) printed "12,003 legacy" and
# threw the list away.
# v1.51 (2026-08-25) — THE REPORTS ARE ORDERED, NOT SCHEDULED. eod_conductor_v2
# now invokes eod_analysis itself once the boxes are down, and the 16:30 timer
# is DISABLED (unit kept on disk for item 56 and --rollback). The gap was a
# clock standing in for a dependency: "a slow report must not delay the close"
# is satisfied by ORDER, since the reports begin after takedown. Consequence,
# stated plainly: control disabled = no reports. The BOXES still self-close at
# 16:45 on their own timer, which is the part that must not depend on control.
# v1.50 (2026-08-25) — THE EOD CHAIN SWITCHES OVER. install_eod_v2.sh repoints
# the 16:05 unit to eod_conductor_v2 (stop trading, drain, verify, take down
# per box), adds the 16:30 analysis timer, and DISABLES dtp-harvest (15:55) and
# dtp-eod (16:15) — the conductor drains to S3 itself and P&L now comes from
# the warehouse. Disabled, not deleted: --rollback re-arms the old chain in one
# command. Menu item 58 repointed to v2 with three modes, and it now SAYS that
# --dry-run fabricates its verification instead of letting a column of green
# imply otherwise.
# v1.49 (2026-08-25) — THE METER GOES ON EVERY LONG LOOP, not just the one
# that got complained about. r215 put progress on the DELETE loop and left the
# SCAN silent — and the scan is the part that takes minutes (~900 sequential
# LIST calls for a full-bucket walk), so the operator hit Ctrl-C on a healthy
# run because a working scan and a hung one looked identical. _iter_keys now
# reports objects/pages/elapsed, and --dups (one GET per object, the slowest
# path here) reports checked/legacy/rate.
# v1.48 (2026-08-25) — the sweep SHOWS PROGRESS and summarises BY PREFIX. A
# 500k-key delete printed nothing between 1,000-key batches, so a working run
# and a wedged one looked identical — the operator had to ask. Now one
# refreshing line with count, rate and ETA. And the pre-delete listing is a
# per-prefix breakdown instead of 25 sample keys, which was neither a review
# nor useful: the manifest is the review surface.
# v1.47 (2026-08-25) — THE MANIFEST NOW CARRIES ITS RULE. A dead-stream purge
# deletes by PREFIX (raw/shadow/ is dead whatever symbol is in the path) but
# --from-manifest re-applied the SYMBOL guard and refused 359,123 shadow keys
# under sym=QQQ, sym=NVDA etc — half the purge silently did not happen. The
# manifest header records rule=prefix or rule=symbol so the delete applies the
# guard that rule needs; a header-less (hand-edited) manifest defaults to the
# SAFE setting, never the permissive one.
# v1.46 (2026-08-25) — S3 SWEEP HARDENED after a dry run proposed deleting
# 321,835 objects INCLUDING THE EXTENDED-HOURS TAPE OF EVERY PANEL SYMBOL and
# VIX: the guard matched PANEL exactly, so "NVDA_EXT" != "NVDA" passed through.
# Now normalises _EXT to the base symbol and keeps VIX unconditionally (the
# session guard and condor read it). Adds --dead-streams (raw/shadow is 43% of
# the bucket and was never installed; raw/regime_log was retired in r65) and a
# MANIFEST workflow, because control has DeleteObject but NOT PutObject so a
# quarantine-by-move is unavailable without undoing that separation.
# v1.45 (2026-08-25) — NEW S3 SWEEP item: legacy-hash duplicates and culled-
# symbol data. Delete lives on CONTROL only — traders write and never delete.
# The duplicate rule is SELF-VERIFYING: an object is current if its key suffix
# equals sha256(canon(record)); proven 2026-08-25 by fetching a pair whose
# records were byte-identical and differed only in pushed_at_utc, which the
# canonicaliser excludes. Lists before deleting, and requires typing DELETE.
# v1.44 (2026-08-25) — FIT REPORT REPLACED BY FIT READINESS. The old report
# sourced everything from `trades` — the population that FIRED — while the
# question "is this setup ready to fit?" is mostly answered by the population
# that did NOT. Its section 3 had also never produced a number, shelling into
# an otv3 checkout that is not present. The new report sections by SETUP TYPE
# and puts TAKEN beside SKIPPED with the derived vector on both sides. Its
# verdict is COVERAGE, not volume: 245 evaluations are not fittable if 96% of
# declines land on one rung. fit_report.py and its test are deleted.
# v1.43 (2026-08-25) — NEW item 56 "EOD analysis — all reports from S3 (boxes
# off)", and install_eod_analysis.sh puts it on a 16:30 timer. This is the
# REPORTS half of the EOD split: eod_conductor_v2 owns the CLOSE (stop trading,
# drain, verify, take down per box) and is done by ~16:08; the reports run 20
# minutes later against the bucket, so a slow report can never delay a close
# and a slow close can never collide with the reports.
# v1.42 (2026-08-25) — NEW item 55 "P&L from WAREHOUSE (day or range; boxes
# off)". Item 54 SSHes into every box, so seeing YESTERDAY P&L meant WAKING
# FIFTEEN MACHINES to ask about data already in the bucket — and its SQL is
# hardcoded to today, so a past session was unaskable at any price. 54 keeps
# its place for the LIVE intraday read and now says so in its label.
# v1.41 (2026-08-25) — the retired classifier is GONE from day_trader_pro:
# 298 mentions -> 0. Five dead files deleted: two shell scripts and a census
# tool for the retired engine, plus the v3 backtest harness and its sweep,
# which imported analysis modules that do not exist in otv4 at all. Report
# generators lost a grouping dimension and a score column built on a database
# column otv4 PHYSICALLY DROPPED in r65 — a query naming it now RAISES.
# fit_report section 3 deleted: it shelled into an absent v3 checkout and had
# only ever printed "SKIPPED, rc 127".
# v1.40 (2026-08-25) — the rendered banner DERIVES its version from this
# header instead of a literal typed in menu_registry.sh; it had read "v1.35"
# against a v1.39 header, and drifted the same way at v1.26/v1.28. Guarded by
# tests/test_menu_banner.py, which RENDERS the menu rather than grepping it and
# fails if a version literal returns. Item 52 relabelled and its handler
# renamed: it promised a breakdown by a column otv4 DROPPED in r65, so a query
# now RAISES rather than returning empty.
# v1.39 (2026-08-25) — MAINTENANCE: item 33 "Dry-run" REPLACED by "Retire —
# off-hours stop (one/all/some)", and item 38 EMERGENCY STOP GAINS SCOPE. The
# operator was forced through option 34 (FULL wake->bake->restart->STOP) just to
# stop boxes after a check — a full resync and restart to reach the shutdown at
# the end. wake_and_bake --shutdown-only ALREADY EXISTED with no menu item.
# 33 and 38 share that mechanism deliberately; the difference is INTENT AND
# TIMING — 33 is the off-hours tidy-up, 38 is mid-session and ABANDONS OPEN
# POSITIONS at the broker. 38 ran unscoped, so killing one misbehaving box
# mid-session meant stopping all fifteen. Both stop by instance ID, not SSH.
# v1.38 (2026-08-25) — NEW SENSORS section (items 19-28): manifold health board,
# strategy notes, plan ledger, exit counterfactual, fire snapshot, surface
# (charm/vanna/GEX), indicators, forks with reject reasons, levels, order flow.
# r61-r70 laid down ten derived tables and two tools with NO WAY TO READ ANY OF
# THEM — a sensor nobody can query is a sensor that does not exist. DEBUG/LOGS
# moves to 29-32; numbers are assigned at render from list position.
# v1.37 (2026-08-22) — menu: obsolete validation section deleted (6 dead items);
# NEW item 18 "Hotfix launcher (repo synch & flush)" at the end of FLEET. Numbers
# are assigned at render from list position, so DEBUG/LOGS simply moves to 19-22.
# v1.36  2026-08-18  REPOINT NO LONGER OFFERS THE PARENT REPO AS A ONE-KEY
#        DEFAULT. ask_url() pre-filled options_trader_v3 and took a bare Enter
#        as consent, which was harmless while all 29 boxes shared one repo and
#        is not harmless now: the QQQ box runs the options_trader_smc fork, so
#        Enter on any REPOINT item would drag it back and silently end the
#        experiment. The URL must now be typed; an empty answer aborts. The
#        old default is printed as a REFERENCE line, not a value — visible to
#        copy, impossible to select by accident.
# v1.35  2026-08-16  Found by DRIVING THE MENU rather than the shell, which is
#        the path the operator actually uses: items 65/66 passed a RELATIVE
#        --bundles-dir. devtools cd's to SCRIPT_DIR at line 51 so it resolved
#        today, but it violated the cwd-independence rule and would break the
#        moment a handler ran from anywhere else. Now "$SCRIPT_DIR/reports/
#        warehouse". ⚠️ --diff correctly flags these two as COMMAND CHANGED —
#        that is the tool working, not a false alarm; the baseline was refreshed
#        deliberately after reviewing both lines.
# v1.34  2026-08-16  REPORT PARITY item added (67). Runs reports 40 and 41 from
#        BOTH sources and diffs their OUTPUTS — WH.11's real gate, since bundle
#        equivalence is necessary and not sufficient. Still additive: 0 labels
#        removed, 0 commands changed.
# v1.33  2026-08-16  S3 WAREHOUSE section added (8 items, 59-66). ADDITIVE:
#        nothing is replaced and no existing report changes its source. The
#        warehouse variants of the excursion report and the trade breakdown run
#        ALONGSIDE the local ones precisely so their OUTPUTS can be diffed —
#        a menu item that quietly switched a report's source would destroy the
#        comparison it exists to make. `--diff` across this change: 0 labels
#        removed, 0 commands changed, 8 added.
#        ⚠️ Adding a whole section moved NO existing number, because the section
#        went last. That is luck, not design — the number is still arbitrary.
# v1.32  2026-08-16  THE MENU IS DATA. The heredoc + case block are gone,
#        replaced by menu_registry.sh (SECTION/LABEL/FUNCTION, in display order)
#        and menu_functions.sh (one function per item, body copied VERBATIM).
#        NUMBERS EXIST IN NEITHER FILE: menu_render assigns them from a loop
#        counter and menu_dispatch matches the same counter, so reordering,
#        inserting a section or deleting an item cannot desynchronise anything.
#        The July 22 v1.18 incident happened because numbers were maintained by
#        hand in two places that had to agree; that class of failure is now
#        structurally impossible rather than merely watched for.
#        ⚠️ EQUIVALENCE VERIFIED, NOT ASSUMED: `tools/menu_extract.py --diff`
#        shows all 57 labels surviving with identical commands across the swap.
#        ⚠️ SIXTEEN NUMBERS MOVED. Identity is the label, but muscle memory is
#        not, so: FIT REPORT 57 -> 42 (it always displayed inside TRADES DATA,
#        out of numeric order), and everything from 42 to 56 shifts up by one.
#        1-41 and 58 are unchanged. EMERGENCY STOP is still 27.
#        ⚠️ `0` now calls `exit 0`, not `return` — the caller is
#        `while true; do menu; done`, so a return looped forever. Found by
#        RUNNING it; reading it had looked fine.
#        ⚠️ AND IT FIXES A PRE-EXISTING DRIFT: the file header read v1.31 while
#        the rendered menu still said "v1.26 Service Menu". Same class as the
#        title-vs-changelog drift the house rule exists for. Both now v1.32,
#        and the version now lives in ONE place (menu_render) instead of two.
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── THE MENU IS DATA (2026-08-16) ────────────────────────────────────────────
# menu_functions.sh holds one function per item, body verbatim from the old
# case block. menu_registry.sh lists (SECTION, LABEL, FUNCTION) in display
# order. NUMBERS APPEAR IN NEITHER: menu_render assigns them from a loop
# counter and menu_dispatch matches the same counter, so reordering the list,
# inserting a section or deleting an item cannot desynchronise anything.
# The July 22 renumber damaged this file precisely because numbers were
# maintained by hand in two places that had to agree.
source "$SCRIPT_DIR/menu_functions.sh"
source "$SCRIPT_DIR/menu_registry.sh"
cd "$SCRIPT_DIR"
PY="${PYTHON:-python3}"
DEFAULT_V3="https://github.com/TX-9AI/options_trader_v3.git"
# 2026-08-18: the fleet is no longer single-repo. Reference values only —
# neither is ever used as an automatic answer (see ask_url).
SMC_FORK_URL="https://github.com/TX-9AI/options_trader_smc.git"
INSTALL_DIR="~/options-trader"
FEED_DB="~/options-trader/data/feed_store.db"
OTV3_DIR="$HOME/options-trader-v3"          # control-box checkout (boxes use ~/options-trader)
OTV3_PY="$OTV3_DIR/venv/bin/python"
# 2026-07-23: canonical copy lives in the otv3 repo. Nothing operational
# should sit loose in /home/ubuntu. MUST be defined AFTER OTV3_DIR —
# `set -uo pipefail` (line 112) makes a forward reference fatal at load.

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

# Repoint target URL. v1.36: NO DEFAULT — repoint rewrites `origin` on every
# box it touches, and since 2026-08-18 the fleet holds two repos (the QQQ box
# runs options_trader_smc). A pre-filled Enter-default is one keystroke from
# un-forking the fleet with no error and no obvious trace, so the URL is typed
# or the operation aborts. Prompts and notices go to STDERR because callers
# capture this function's stdout with $( ).
ask_url() {
  local u
  {
    echo "  repoint rewrites origin on every box in scope. Type the URL."
    echo "  for reference — legacy fleet: ${DEFAULT_V3}"
    echo "                  SMC fork:     ${SMC_FORK_URL}"
  } >&2
  read -rp "New repo URL (no default; empty aborts): " u
  u="$(echo "$u" | tr -d '[:space:]')"
  if [ -z "$u" ]; then
    echo "  aborted — no URL given, nothing was repointed." >&2
    return 1
  fi
  echo "$u"
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
_RED=$'\033[1;31m'
_RST=$'\033[0m'

# ── FEED.1 (2026-08-15) — MAINTENANCE WINDOW INDICATOR ───────────────────────
# The flag lives on each BOX (data/FEED_MAINTENANCE, checked live by
# candle_feed's gate). Control keeps its own marker purely so the menu can be
# drawn INSTANTLY and while boxes are STOPPED — polling 29 boxes on every menu
# draw would be slow and would fail exactly when the fleet is down.
# ⚠️ THE MARKER IS A HINT, NOT THE TRUTH. Option 58 verifies against the boxes
# and prints the real count; if they disagree, believe the boxes.
# ⚠️ SCRIPT_DIR (line ~198), NOT $DIR - which does not exist. This file's own
# header records the same failure at v1.2x: a forward reference before the dir
# var is set is FATAL AT LOAD under `set -uo pipefail`, and it takes the whole
# menu down rather than one option.
_MAINT_MARK="$SCRIPT_DIR/data/FLEET_MAINTENANCE"
_maint_on() { [ -f "$_MAINT_MARK" ]; }
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
  menu_render | _colorize
  read -rp "Select: " choice
  # 0 EXITS THE PROGRAM. `return` here would only leave menu(); the caller is
  # `while true; do menu; done`, which would loop forever — which is exactly
  # what happened the first time I wrote this.
  if [ "$choice" = "0" ]; then exit 0; fi
  menu_dispatch "$choice" || true
}

while true; do menu; done
