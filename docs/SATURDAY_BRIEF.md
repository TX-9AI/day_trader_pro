# THE SATURDAY BRIEF — spec v2.6

**v2.6 · 2026-11-11 · dtp r549 (SAT.8)**: the study queue runs ON THE BOXES, IN PARALLEL. `tools/study_dispatch.py` gives each OPEN item (a sub-item such as WS.6a is its own) its own stopped box (never CRM, never a box someone else claimed) and a bounded headless study agent there; it copies each SEAL.txt to control the moment it appears, pulls each study to `~/reviews/studies/<ID>_<YYYYMMDD>/`, validates it (seal unchanged, SEAL ≤ FROZEN ≤ RESULT), cleans and stops every box, and marks the queue. The brief starts it after the box reads and collects it in §6; the fleet is CLOSED only after it finishes. r548 ran the queue on control in about 30 minutes; this runs up to one item per box for about three hours. The operator, 2026-11-11: "What about just waking more boxes at the 0300 to run these studies in parallel?"

**v2.5 · 2026-11-11 · dtp r548 (SAT.7)**: §6 runs the standing study queue `~/reviews/WEEKEND_STUDIES.md` every week. Each OPEN item is run blind (seal first, freeze, run once), after sections 1–5, one heavy job at a time, and stops 45 minutes before the deadline. Unfinished items go to NOT MEASURED and stay OPEN. The verdicts (TUNE or TRIM) go to §7. The operator, 2026-11-10: "Make sure you add whatever we want to study to the 0300 weekend activity."

**v2.4 · 2026-11-08 · dtp r538 (RETIRE.3)** — §1.5: the TCS shadow is gone (OTV5 r88 deleted it; the operator, 2026-11-08: "Delete"), so the section reads only the PARK late-day shadow, through `_envelopes` on `check_name`; §5's remnant note no longer keeps the TCS.

**Status: the operator's spec, as of 2026-10-31.** It replaces `options-trader-v4/handoffs/SATURDAY_BRIEF.md`
and `SATURDAY_RUNBOOK.md` (2026-09-19). Those were written for seventeen boxes, two engines and ORB. The fleet is now
one engine (OTV5) on the boxes the instance map names. This file is tracked in `day_trader_pro/docs/`. The
timer's prompt is `tools/saturday_brief.prompt`, and `tests/check_saturday_brief.py` checks that the prompt matches
this spec. Backlog row: **SAT.4** (OTV5 `docs/BACKLOG.md`, section I — "The box: install, services, menus and the agent"; v2.3 corrects "section H").

## THE OPERATOR'S RULINGS (2026-10-31, verbatim)

- *"Re-do the entire brief. It should include issues from the bot logs, trading summaries, documentation
  corrections, code hygiene issues, proposed studies to increase P&L, and recommendations."*
- On the old Saturday-run items: *"Keep what's useful & retire the rest".*
- *"don't list the retired strategies either. They're no longer relevant to this repo."*
- On a retired box: *"I don't think AAL's retirement is announcement worthy... nobody cares".* So the brief
  reports no non-events.
- Earlier: the brief is **prepared at 03:00 and delivered on request, one section at a time.**
- Still in force from 2026-09-19: *"Check each of these things and do a report, but don't take any action yet."*

---

## WHEN, WHERE, AND HOW IT IS DELIVERED

| | |
|---|---|
| Start | cron, Saturday 08:00 UTC: 03:00 EST (04:00 EDT from March); the watchdog at 12:45 UTC, after the deadline. `tools/saturday_brief.sh` runs it. (Installed with SAT.4; before that the crontab read 07:17 UTC) |
| Deadline | **07:30 ET.** The wrapper kills the session then (`timeout`, rc 124). Have the file written well before that |
| Output | `~/reviews/weekly/saturday_<YYYY-MM-DD>.md`, beside the daily reviews. It is **not** written to `options-trader-v4/handoffs/` (gitignored; `check_scratch_purge` P12). The briefs of 09-26 to 10-31 still sit there until they are moved |
| Working files | `~/reviews/weekly/saturday_<date>_work/`: `sweep/`, `botlog/`, `disk.json`, tool outputs. **Next week diffs against these**, so keep them |
| Prior | the wrapper passes last week's brief and its `_work/` folder |
| Delivery | nothing is sent. When the operator asks, the session shows the **index** first, then **one section at a time**, in order, as they ask for each one |

The output file has this shape, so a session can print one section on its own:

    # SATURDAY BRIEF — <date>  ·  window <Mon>..<Fri>  ·  <N> boxes  ·  OTV5 <sha>
    ## INDEX              one line per section: its headline, or "nothing to report"
    ## 1. TRADING SUMMARY
    ## 2. ISSUES FROM THE BOT LOGS
    ## 3. FLEET HEALTH
    ## 4. DOCUMENTATION CORRECTIONS
    ## 5. CODE HYGIENE
    ## 6. PROPOSED STUDIES TO INCREASE P&L
    ## 7. RECOMMENDATIONS
    ## NOT MEASURED       by name, with the reason

Each section starts with its headline in one or two sentences and stands on its own (no "see above").

---

## RULES FOR EVERY BRIEF

1. **Plain language.** Short sentences. Use the symbol, the dollar figure and n. Use "they/them" for the operator.
2. **No retired strategies.** The brief reports only setups that closed a trade or wrote a shadow row in the
   window. Section 5 is the only place retired code comes up, as **code to remove**, never as a strategy to report on.
3. **No non-events.** Leave out anything that did not happen or did not change: a box that was retired, a series
   with no new data, a check that is still green. Each section ends with one line, `Checked, nothing to report:`,
   that names what came back clean, so a clean check is not mistaken for a missed one (§0.5). That line is the
   only place clean results appear.
4. **No credentials, no environment blocks.** Never print `systemctl show` without a property filter, `systemctl cat`,
   `env`, `/proc/*/environ`, `.env`, `~/.flash_creds`, a bootstrap, or a unit's `Environment=`. Service state comes from
   `systemctl is-active <unit>` only.
5. **Read-only on the boxes.** Reads only: no restart, bake, pull, reconcile, purge, delete, `chmod` or edit.
   SQLite is opened with `mode=ro`.
6. **Wake and stop the fleet only with `wake_and_bake.py`** (below). **The fleet must be stopped before the brief
   ends**, failures included.
7. **Land nothing, send nothing.** No commit, push, `deploy.sh`, `land.sh`, Telegram or pager. The wrapper exports
   `VERTIGO_UNATTENDED=1` and the lander refuses it.
8. **Say n every time** (§12). A thin sample shows a mechanism, never a conclusion.
9. **Fees are reported on their own line, never inside EV** (EV benchmark ruling).
10. **The OTV4TEST fleet's rows are filtered** out of every warehouse measurement, using
    `OTV5 tests/warehouse_source.mainline()` (the record's lineage first, then the box and date). Mention the
    filter only when it dropped rows.
11. **Nothing unmeasured is stated as fact** (§0, §0.1). A measurement that could not be taken goes in NOT
    MEASURED with its reason. If a tool caused the gap, say so: the gap is the tool's, not the tape's.
12. **Interpreter: `/home/ubuntu/day_trader_pro/venv/bin/python`.** A red under a bare `python3` is an environment
    red (CHK.9/11).

---

## RUN ORDER AND TIME BUDGET (03:00 → 07:30 ET)

| ET | step | fleet |
|---|---|---|
| 03:00 | read the spec, last week's brief, OTV5 `docs/BACKLOG.md` (open rows), `docs/GENESIS.md` tail; set the window | down |
| 03:05 | **WAKE** | up |
| 03:10 | section 2 (bot-log scan), section 3 box reads (code, services, disk, box-vs-S3 trades) | up |
| ~03:45 | **START the study dispatch** (`study_dispatch.py run`, nohup): one OPEN queue item per box; it stops the boxes it does not use | study boxes up |
| 03:45 | checker sweep (about 25 min) and the R suite (the exit replay takes about 25 min) in the background | study boxes up |
| 04:15 | section 1 from S3, the bundles and `~/reviews/` | study boxes up |
| 05:15 | sections 4 and 5 (read the trees) | study boxes up |
| 06:15 | section 6 (bars written first, cheap studies run; then `study_dispatch.py wait` collects the queue), section 7 | study boxes finish by DEADLINE − 25 min |
| ≤ 07:05 | `study_dispatch.py cleanup`, then **CLOSE** and verify `N/N reached 'stopped'` | down |
| ≤ 07:15 | the file is written; then INDEX and NOT MEASURED are finished | down |

    WAKE   cd /home/ubuntu/day_trader_pro && ./venv/bin/python wake_and_bake.py --wake-only --yes
    CLOSE  cd /home/ubuntu/day_trader_pro && ./venv/bin/python wake_and_bake.py --shutdown-only --yes

`--wake-only` means wake and ping only. The bare `wake_and_bake.py` runs the full cycle, and a bake is an action.
Both read the fleet from the instance map, so never use a hard-coded count. Never wake during RTH
(09:30–16:00 ET); a hand run inside RTH leaves the box reads NOT MEASURED. Long jobs run with `nohup … > file 2>&1;
echo rc=$? >> file` and a `timeout`. Never pipe them through `tail` in an `&&` chain.

**The window** is the week's sessions, Monday to Friday, read through `market_calendar` so that half days and
holidays are handled. State it once and use it everywhere.

---

## 1. TRADING SUMMARY

**Purpose:** what the week made and lost, and where, measured against the EV benchmark.

**1.1 The EV benchmark (window 2026-10-26 → 11-27).** Read `~/reviews/window_ev.csv` (one row per day,
window-to-date: trades, realized, fees, EV per trade, EV without the worst setup and without the worst symbol) and
`~/reviews/theories.csv` (the operator's pre-cash theories, scored nightly by `~/reviews/scripts/theories.py`).
Report: window-to-date EV and its two exclusions; the week's change in each; the theories table as of Friday, with
its leader and its n. Show the pre-decay days (10-26..10-30) and the post-decay days (from 11-02) separately.
These files belong to the daily review. **Read them and never write them.** If a day's row is missing, that day goes
in NOT MEASURED. Check each day's trades and realized figures against the bundles (1.2). Report a mismatch.

**1.2 The week by setup, side, day and symbol.** Source: OTV5 `tests/warehouse_source.load_trades(dates)`, then
`mainline()` (rule 10). Check it against `reports/warehouse/fleet_trades_<day>.json` (deduped by trade_id) and name
any day on which the two disagree. Tables: by setup (n, win %, net,
median hold); setup × side; by day (n, net, and what decided the day, in one clause); by symbol (net, n), sorted.
Also the five best and five worst trades with their exit reason, and entries by time bucket (09:30–10:00,
10:00–10:30, 10:30–11:30, later).

**1.3 Missed and under-captured moves.** From S3 5-minute RTH bars (`raw/candles/…/interval=5m`, deduped on
`ts_epoch_ms`; `warehouse_source.stream_series`), cross-checked against 1m `raw/ohlc`: box-days that took no trade on a range at or above the symbol's
median, and traded days where the book captured little of a large move. For each: one line on what happened. Use
section 2's refusal counts to say **why** a box sat out where the log shows it.

**1.4 Giveback.** `~/reviews/giveback.csv` (the daily study's definition: peak sampled per 15 s tick). The week's
total given back out of peak open profit, the green-to-red count and dollars, the worst day, and the setup that
gave back most.

**1.5 The shadow (never in EV).** (The TCS shadow, `raw/shadow_trades`, was deleted by OTV5 r88 RETIRE.3 on the
operator's 2026-11-08 "Delete": it never fired. Not read, not scored.)
- **PARK late-day shadow**: `raw/derived_plan_check/` rows whose check starts with `park_late_` (OTV5 r63,
  `park_late_would_exit`). For each PARK trade it touched: would-exit time and mark against the actual exit, and the
  dollar difference. Total and n.
Read it through OTV5 `tests/warehouse_source.py` (§36a on OTV5; never a hand-rolled paginator), folding
`raw/derived_plan_check/` one object at a time (`_envelopes`; `load_derived` materialises the week and runs out of
memory on control) and filtering on the `check_name` column. If no row is found, put it in NOT MEASURED and say
whether the boxes have the code (3.4). `raw/shadow/` is a different, older stream (its last day is 2026-09-11).

**1.6 Fees.** Per day and week, from `window_ev.csv`'s `fees` column. Reported beside the P&L, never subtracted
from EV.

**1.7 The R ledger and excursions (the useful half of the R suite).**

    /home/ubuntu/day_trader_pro/venv/bin/python /home/ubuntu/OTV5/tests/r_ledger.py --from <Mon> --to <Fri>
    /home/ubuntu/day_trader_pro/venv/bin/python /home/ubuntu/day_trader_pro/excursion_report.py --since <Mon> --date <Fri>

Report: the BOOK line (n, net, R, e/t, capture); setup × side rows; P&L by exit rule; selection vs extension (never
favourable vs was favourable). The R ledger is OTV5's copy (dtp r518 moved the Friday runner to `~/OTV5/tests`).
Excursions are BUNDLE-sourced, because OTV5 has no `excursions.py` yet (that is a section 5 item). The R ledger's R
is average win over |average loss|. Say so beside any R figure.

`fit_readiness.py` is run (dtp, `--from/--to`). Its output is used **only** to name a setup that crossed a
fittability line this week. Its "READY" counts signal rows, not trades (D7), so it is never reported as readiness.

---

## 2. ISSUES FROM THE BOT LOGS

**Purpose:** what went wrong on the boxes that the trade record does not show.

    /home/ubuntu/day_trader_pro/venv/bin/python /home/ubuntu/day_trader_pro/tools/botlog_scan.py \
        --from <Mon> --to <Fri> --out <WORK>/botlog --prior <PRIOR_WORK>/botlog --by-day

`<PRIOR_WORK>` is the wrapper's PRIOR_WORK parameter (v2.2, wrapper v1.8): last week's `_work` folder from
`~/reviews/weekly/` only. When it reads `NONE - …`, run `botlog_scan` and `checker_sweep` without `--prior` and say
so in the section. The header's tree line is the wrapper's TREES parameter (OTV5's and dtp's HEADs), never otv4's.

`botlog_scan` sends one read-only script through `fleet.py run`. On each box it reads `~/options-trader/bot.log`
and its rotations, and nothing else. It counts per box and per day: ERROR, CRITICAL, Traceback (with the exception
line), refusals by class (v1.1, dtp r526: `pin`, `commit` (COMMIT.2), `sizing:<reason>`, `entry_end`, `orb_break`,
`gate:<Strategy>@<condition>`, `afd`, `park_starved`, `no_chain`, `pin_exempt_would_refuse`, `other:<tag>`),
blind/stale/reconnect feed lines, real cap hits (never the start-up banner), and service starts with their ET times
(`start_rth` counts a start between 09:30 and 16:00 ET). Every line is keyed by its ET day. `--by-day` prints each
box-day's refusal classes: a sat-out day in 1.3 is explained from it, by class and count. Each line is folded into a signature, with token-shaped text redacted on the box. It diffs the
signatures against last week's.

Report, in this order:
1. **New signatures** in CRITICAL, Traceback and ERROR: box(es), count, first and last time, and one line on what
   it is. Read the context on that one box, read-only and briefly (`fleet.py run --only SYM "grep -n -m5 -F
   '<literal>' ~/options-trader/bot.log | cut -c1-300"`). Never paste more than a few lines.
2. **Count jumps**: a class that doubled week on week, or any box with more than one service start on a
   session day (the 09:15 wake is the expected one).
3. **Feed episodes**: blind or stale stretches. Give the box, the day and how long, and say whether a trade was
   open during it.
4. **Gate refusals**: totals by class and box, and for each of 1.3's sat-out days the `--by-day` line that explains it. A gate that refused every fire on a
   trend day is a finding, not a defect.
5. **Cap hits**: box, day, time, and what was refused after it.
6. **Anything else** a human would flag (a loop, an order rejected, a session reset during RTH).

A box the scan could not read is listed by name as NOT READ. Its silence is never counted as a zero.

---

## 3. FLEET HEALTH

**Purpose:** is the fleet sound for Monday. Only findings get detail.

**3.1 Checker sweep, diffed by check ID.**

    /home/ubuntu/day_trader_pro/venv/bin/python /home/ubuntu/day_trader_pro/tools/checker_sweep.py \
        --out <WORK>/sweep --prior <PRIOR_WORK>/sweep

The sweep runs OTV5 and dtp (otv4 is frozen; add `--trees otv5,dtp,otv4` only if asked). Each checker gets its
own scratch directory, with the lander's store paths (OTV5 `tools/land.sh`, the "r13 — CHECKS NEVER TOUCH THE BOX'S STORES" block; line 656-665 at OTV5 r81 — cited by its anchor because RETIRE.1 moved it once already). The sweep writes `sweep.json`
and `diff.json`. Report: **NEWLY RED** (file and IDs; give the cause where you can read it), **GREEN THAT WAS
RED**, and **STILL RED, IDS CHANGED**. Give the standing reds as one count. A newly red checker comes first in this
section. A red flagged `[env]` is an interpreter fault, not a verdict. On the first run there is no prior: say so.

**3.2 S3 parity.**
- The week's nightly verdicts in `/home/ubuntu/day_trader_pro/logs/eod_conductor.log`: VERIFY, HELD, and
  `series_lag_s` (dtp r517).
- Box against bucket, trades: each box's `trades.db`, opened read-only, counted and summed per day, against the
  bundles. 0 mismatches is one line in "Checked, nothing to report".
- Streams and tails, LIST only:

      /home/ubuntu/day_trader_pro/venv/bin/python /home/ubuntu/day_trader_pro/warehouse_coverage.py --streams --since <Mon>
      /home/ubuntu/day_trader_pro/venv/bin/python /home/ubuntu/day_trader_pro/warehouse_coverage.py --tail --since <Mon>

  Report a MISS or a TRUNCATED tail (newest `quote_series` before close − 15 min) as box, day and time. A
  parity gap may be a counter problem rather than a data problem (S3.24/S3.25). Say which before calling it either.

**3.3 Disk, with days to full.** For every box, read `df -B1 --output=size,used,avail /` and the five largest
files on `/`. Rank WAL files in place: a `*.db` glob misses `.db-wal`. Save it to `<WORK>/disk.json`
(`{box: {size, used, avail, top: [[bytes, path], …]}, "at": iso}`). **Days to full** = avail ÷ (growth in used per
day since `<PRIOR_WORK>/disk.json`). Without a prior file, use last week's table and label the result rounded.
Flag any box at or above 85%, any box under 30 days to full, and any file that doubled. The 92% guard pages on
the crossing.

**3.4 Code and services.** Each box's `git -C ~/options-trader rev-parse --short HEAD` (the box path has no suffix;
`|| echo REPO_MISSING`), checked against control's `~/OTV5` HEAD and origin. Say whether the revisions between them
are docs-only. `systemctl is-active optionsbot candle-feed s3-push.timer optbot-emergency-watchdog.timer
candle-logger.timer`, and nothing more.

---

## 4. DOCUMENTATION CORRECTIONS

**Purpose:** docs that say something that is no longer true. Find them; do not fix them.

Read these against the code and the ledgers:
- OTV5 `docs/` (WORKING_AGREEMENT, HANDOFF, FILE_MAP, ENV, ROADMAP, TRADES, PLAN_SPEC) and dtp `docs/`
  (ARCHITECTURE, WAREHOUSE_MAP, MENU_INVENTORY.tsv), including this spec;
- the **strategy roster**: OTV5 `config.ENTRY_WINDOWS`, `strategy_registry` codes (dtp), the docs roster
  (`check_docs_roster`) and the menu labels. Any name missing from one of them, or present in one only;
- **backlog against GENESIS**: an OPEN row whose fix GENESIS says landed, a DONE row with no revision, a row citing
  a file or path that no longer exists, a row whose inputs lived on a retired box;
- menu items that run a tool from a frozen tree.

Each item: `path:line`, what the document says, what is true (with the evidence), and a one-line correction. Give
the new items first, then a one-line count of the ones carried from last week. Do not repeat their text.

---

## 5. CODE HYGIENE

**Purpose:** code that costs attention or hides defects. Report it; do not change it.

Look for:
- **dead code**: functions, flags and menu handlers with no caller (grep the name across the tree; `menu_extract.py
  --check` for the menu);
- **retired-strategy remnants**: code paths, config keys, env switches, tests and menu items that still name a
  strategy the operator retired. Search for the terms in the block below. A remnant is reported as **code to
  remove**. The strategy is never described or scored. (The ORB *engine* stays: Runaway reads it. The TCS and its
  shadow are removed, OTV5 r88.)
- **stale tests and fixtures**: hard-coded dates that act as "today" or as an expiry (`EXP = "2026-…"`,
  `--date 2026-…`), and fixtures that will go red within 14 days of the brief. Name each file and line. The
  10-30 `check_tcs_shadow` I4 red was this kind of failure;
- **duplicated constants**: the bucket name, epoch dates, box lists, session times or caps defined in more than
  one place across dtp and OTV5;
- **frozen-repo dependencies**: any dtp or OTV5 path that reads `~/options-trader-v4` or `DTP_OTV4_DIR`. Known
  ones: `menu_functions.sh _r_tool`, `tools/brief_sigint.py`, `tools/genesis_find.py`. Check each is still there;
- **interpreter-sensitive scripts** (`#!/usr/bin/env python3` that import numpy, pytz or tastytrade).

Each item: `path:line`, why it matters (the failure it can cause), the proposed change, and its size (lines, gates).
Show at most ten new items; carry the rest as a count.

<!-- RETIRED-SEARCH: the hygiene search terms only. Never print these as strategies in a brief. -->
    ORBStrategy  ORBS  orb_budget  ORB_BUDGET      PARC  OT_PARC  parc_       VOLT  OT_VOLT
    SweepCreditSpread  SWPT  OT_SWEEP_CS           OpeningRangeCreditSpread  ORCS  OT_ORCS
    ATPButterfly  ATPB  OT_ATP_BUTTERFLY           minimum-stop veto  min_stop  OTV4 vs TEST  proxy
<!-- /RETIRED-SEARCH -->

---

## 6. PROPOSED STUDIES TO INCREASE P&L

**Purpose:** the next measurements most likely to move EV. A study is a proposal unless the brief can run it
cheaply tonight on data already in hand.

Every study has these five fields, written **before** any number is looked at:

| field | content |
|---|---|
| Hypothesis | one sentence that can be false |
| Data | S3 prefixes or files, window, n expected |
| Pass bar | the rule that decides it, written before the test. Give the hold-out (losing days first, top winner kept, fit then validate on unseen days) |
| Expected $ effect | the estimate before the test, with the arithmetic (e.g. "saves 30% of the no-progress losses, about $3.7k a week") |
| Cost | tooling to build, runtime, and whether it touches trading code (the benchmark freeze) |

A bar written after the data was seen is labelled **post hoc** and cannot pass anything. Before proposing a study,
search OTV5 `docs/BACKLOG.md` (STR.1, the 10-24 studies), `~/giv_study/` and last week's brief for the same idea,
so a study that already failed is not proposed again as new. **At most five studies**, ranked by expected $.

Evidence comes from the counterfactual half of the R suite (OTV5 `tests/`, dtp venv, `--from <Mon> --to <Fri>`):

    stop_sweep.py      the stop/TP surface over recorded excursions (n ≥ 20 surfaces only)
    exit_replay.py     trail and stop alternatives on real premium paths (~25 min; positive control must reconcile)
    edge_scan.py       features against the pre-registered bar (prints its FLEET line)

The exit replay's positive control comes first. If replayed trades do not reconcile, every alternative is
suspect, and the study says so. When the two tools disagree, report the disagreement; do not pick one.

**The study queue (standing, every week, v2.6):** `~/reviews/WEEKEND_STUDIES.md` holds the studies the
operator and the sessions have agreed to run, each with its hypothesis, data, seal rule and pass bar written
before testing. Every item marked OPEN is run blind, and since v2.6 they run ON THE BOXES, IN PARALLEL
(`tools/study_dispatch.py`, SAT.8):
- The brief starts `study_dispatch.py run` right after the box reads. It refuses inside the trading window
  (Mon–Fri 08:45–16:50 ET). One OPEN item per box; a sub-item such as WS.6a is its own item. CRM is never used,
  and a box with someone else's claim in `~/reviews/box_claims` is skipped. It writes its own claim per box, and
  every power call goes through ec2ops under `flock /tmp/claude-fleet.lock`. Unused, unclaimed boxes are stopped.
- On each box it stops optionsbot and candle-feed and runs a bounded headless `claude -p` study agent (the
  research token is read from SSM with the box's own role; never printed, never copied from control). The agent
  reads the warehouse with the box's own role, writes nothing outside its work dir and never writes S3.
- The agent writes `SEAL.txt` (with a `SEALED_AT` UTC line) before any outcome, then `FROZEN.json`, then runs once
  and writes `RESULT.json` last. The dispatcher copies `SEAL.txt` to control the moment it appears; a result is
  accepted only if the seal is unchanged and SEAL ≤ FROZEN ≤ RESULT. The study lands in
  `~/reviews/studies/<ID>_<YYYYMMDD>/`, with the control copy as `SEAL.control.txt`.
- Cleanup on every exit path, including timeout and failure: the session is killed, `~/study_<run>` and the run's
  `~/.claude/projects` transcripts are removed, S3 scratch is deleted, the box is stopped and the claim released.
  A freed box takes the next queued item while at least 45 minutes remain. Every box is killed 25 minutes before
  the deadline. The wrapper exports the deadline (`STUDY_DISPATCH_DEADLINE_ET`) and runs `study_dispatch.py
  cleanup` after the session as a safety net.
- The dispatcher marks each item DONE or FORWARD in the queue file; invalid or unfinished items stay OPEN and are
  listed in its summary's NOT MEASURED. The brief collects it with `study_dispatch.py wait` in §6: per item the
  blind n, EV a trade with its 95% interval, the window EV with its interval, and PASS or FAIL against the item's
  own bar, unedited. The TUNE or TRIM verdict goes to §7. The fleet is CLOSED only after the dispatcher finishes.
- Fallback, only if the dispatch refused or failed before launching anything: the brief runs OPEN items on
  control, blind as above, one heavy job at a time through `flock /tmp/claude-heavy.lock /home/ubuntu/bin/heavy`,
  no new item in the last 45 minutes before the deadline, and lists the failure under NOT MEASURED.

Queued items don't count against the cap of five new proposals. Sessions add items by appending to the file
(IDs WS.<n>, never reused); nothing in this spec needs to change when they do.

**Standing studies (kept from the old Saturday rows):**
- **GIVE.2, fleet:** exits that give back profit. 1.4's giveback is its weekly input, and the exit families
  (no-progress cut, trails, decay stop from 11-02) are its candidates.
- **CUT.1, fleet:** OTV5 ends Runaway and Breakout entries at 10:29 (`RUNAWAY_END`, `BREAKOUT_END`) and records
  later fires LOG-ONLY (OBS.1). The bar is the row's own: RIGHT = blocked net ≤ 0; WRONG = ≥ 10 blocked fires,
  net > 0, and losing days not made worse. It needs a tool that prices a LOG-ONLY fire on its option's quotes. Until
  one exists it is NOT MEASURED, with the build as the study's cost.
- **PIN.3 (absorbs PIN.1):** what the directional pin gate's refusals would have made, from the refusal lines
  (section 2) and the tape. Losing days first; name the cost case (a pinned open that breaks away).
- **DAY.1, final score:** E = |price − open| / (high − low) at 09:45 on QQQ and SPX from `raw/ohlc`, 10-07 to the
  window's end, scored against the row's frozen terms. It is scored once, then closed by its result.

---

## 7. RECOMMENDATIONS

**Purpose:** what the operator should decide, ranked.

Each recommendation, ranked by dollars at stake, then by risk:

    R<n> · <what, in one line>
      Why:       the evidence, with n and $, citing the section
      Class:     DEFECT (one reproducing case) · CALIBRATION (statistical; deep tape, shadow first) · DIAGNOSTIC · DOCS · HYGIENE
      Touches:   control only · OTV5 research/tools · OTV5 trading code (benchmark freeze: only if broken) · a box
      Decision:  the yes/no question for the operator, and what happens on yes

No history recap: give the proposal, why, and what follows a yes. A trading change during the benchmark is only
recommended if the code is broken (not to spec or malfunctioning). Anything else waits for 11-27, or becomes a
shadow. **"Nothing to recommend"** is a valid section.

At the foot, a short table **Still open from last week** has one line per open recommendation: id, status
(still open / superseded / done by r…). A recommendation that is done is listed once, then dropped.

---

## WHAT THIS SPEC RETIRED (2026-10-31), AND WHY

| old item | disposition |
|---|---|
| the minimum-stop veto (old §5) | retired: the strategy it measured is retired, so the series cannot grow |
| the two-engine comparison (old §6) | retired: one engine on the fleet; the two populations closed 10-23 |
| the tape-proxy correlation (old §7) | retired: its premise (a test box standing in for an index) is gone |
| R-suite pooling across engines (D5) | retired: one lineage |
| PARC in any table | retired: *"It was an idea. It failed. It's done."* |
| VERD.1 | closed, superseded: its verdict file and scorer were on the retired QQQ-TEST box, never in S3; OTV5's box agents are off at boot |
| PIN.1 | merged into PIN.3 (OTV5's own pin gate) |
| CUT.1, GIVE.2 | re-scoped to the OTV5 fleet; their QQQ-TEST halves closed |
| DAY.1 | one final score, then closed by its result |

The old runbook's lessons that still apply are kept above: diff by check ID, per-checker scratch, the box path has
no suffix, a fan-out must fail loudly, a WAL needs ranking in place, S3 is read through the one sanctioned reader (§36a), never pipe a long job
through `tail` in an `&&` chain, and a parity gap may be a counter problem.
