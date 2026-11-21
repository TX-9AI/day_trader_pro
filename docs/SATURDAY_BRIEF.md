# THE SATURDAY BRIEF — spec v3.0

**v3.0 · 2026-11-21 · dtp r570 (SAT.10)**: THE BRIEF IS THE OPERATOR'S NEW LAYOUT: FOUR SECTIONS, TEN PARTS. The operator, 2026-11-21, verbatim: *"1) Trading- A. Summary of the week's trades, our EV per trade, gross and net totals by strategy after fees. MFE/MAE, and any other performance commentary. B. A breakdown of our give-back on exits and never right on entries, and how each's strategy type fared the previous week vs its historical performance C. Our EPOCH (otv5) cumulative metrics. Is our performance improved or worsening? Is it consistent? Anything noteworthy in the sample worth mentioning? 2) Our edge- A) What are our top earning setup conditions & where should we be looking for edge improvements? B) What are the results of the week's studies? Are any of the results actionable? Do we need to dig deeper anywhere? 3) Bot performance- A) Any errors or issues this week? B) How effective were the previous week's fixes? C) how's our backlog coming along? 4) Recommendations"*, and *"the things I forgot to mention should be worked into whichever section they best fit into"*. The numbers of 1A, 1B, 1C and 2A that have one right answer come from the new `tools/weekly_facts.py` v1.0 (the session quotes `<WORK>/weekly_facts.md`, never re-derives it); the tape for 1C is TastyTrade's daily candles for QQQ, SPX and VIX (S3 `raw/candles_full/interval=1d`, CAP.6), read by the same tool. It reuses dtp `tools/review_kit.py` (the fee estimate, the bootstrap's seed and draws) and `strategy_registry` (which setups trade today, the epoch's first day); the daily recap's `daily_brief.py` helpers need that tool's own venv (matplotlib, reportlab), so they are not imported. How and when the brief runs is unchanged (timer, run order, Friday dispatch, collection, CLOSE). Every old item has a new home or is retired by name:

| old (v2.17) | new (v3.0) |
|---|---|
| §1.1 EV benchmark 10-26..11-27 (window_ev.csv, theories.csv) | **1C**, through the brief of 2026-11-28 (its final score); from 2026-12-05 it is gone and the epoch metrics replace it |
| §1.2 by setup, side, day, symbol; best and worst five; entry-time buckets | **1A** (from `weekly_facts.md`, net = gross − fees beside gross) |
| §1.3 missed and under-captured moves | **1B** |
| §1.4 giveback (`giveback.csv`) | **1B**, with the by-setup split and "never right" from `weekly_facts.md` |
| §1.5 the PARK late-day shadow | **1B** (still writing rows: three PARK trades on 11-16..11-20). The rest of old §1.5 was already empty |
| §1.6 fees | **1A** (per day and week; fees beside EV, the net column next to gross) |
| §1.7 R ledger BOOK line, setup × side rows, excursions, `fit_readiness` | **1A** (MFE/MAE and performance commentary) |
| §1.7 P&L by exit rule, selection vs extension | **1B** |
| §1.8 QQQ cash size table (until 12-05) | **4.2** (a reference table in section 4, never an R-item) |
| §1.9 OGAP, its own line | **2A**, decisions in progress, through 2026-12-04 |
| §1.10 OGAP vs PARK and its fixed rule | **2A**, decisions in progress (rule unchanged, verbatim) |
| §1.11 Runaway O08 would-be | **RETIRED** (the operator agreed to drop it, 2026-11-21) |
| §2 issues from the bot logs | **3A** |
| §3 fleet health (sweep by check ID, S3 parity, disk days to full, code and services) | **3A** |
| §4 documentation corrections | **3C**, each written as a backlog item |
| §5 code hygiene (and the RETIRED-SEARCH block) | **3C**, each written as a backlog item |
| §6 counterfactual evidence (stop sweep, exit replay, edge scan) | **2A** (where to look for edge) |
| §6 R6 no-progress lead, the study queue, standing studies, new proposals (at most five) | **2B** |
| §7 recommendations, "Still open from last week" | **4.1** |
| new | 1A risk (worst day, losing streaks, drawdown from the peak, peak capital deployed vs ~$6,250), ladder fill quality, the QQQ-only view, the exclusions line · 1B never right, each setup vs its history · 1C the epoch with intervals and tape context · 2A top and bottom condition cells, the Hunt line · 2B the coming Friday's queue · 3B last week's fixes with live evidence · 3C backlog progress · 4.3 the 12-04 readiness checklist · 4.4 next week's calendar · 4.5 the Sunday work list (the brief ends with it) |

The wrapper `tools/saturday_brief.sh` v2.2 changes labels only (the STUDIES and TREES lines name 2B and 3A). Gate `tests/check_saturday_brief.py` v2.0 (S10, S22, S26, S28-S33). The section numbers in the changelog entries below are the old layout's.

**v2.17 · 2026-11-21 · dtp r569 (RECAP.1)**: the study queue is FED DAILY and the Friday dispatch STARTS AFTER FRIDAY'S RECAP. The operator, 2026-11-21: every trading day the daily recap (`dtp-daily-recap`, `tools/daily_recap.sh`, 17:00 ET) proposes studies to improve P&L and appends them to `~/reviews/WEEKEND_STUDIES.md` as full OPEN items (`tools/daily_recap.py append`: next free ids, a .bak first, proven with `parse_queue`), plus ONE backlog maintenance proposal for a yes; Friday evening, after the recap and the drain, the week's studies run; Saturday's brief compiles the results; Sundays implement. `tools/friday_studies.sh` v1.2 waits for the conductor and then for today's recap (its ledger line, up to 2 h) before it claims a box. Nothing else in this brief changes; an item whose `- Source:` names a daily recap is an ordinary queue item.

**v2.16 · 2026-11-19 · dtp r566 (MARK.1)**: THE MARK IS THE ONLY BASIS. The operator, 2026-11-19: "I don't give a rat shit what the bid-ask is. Mark is the worst buy or sell we accept." and "I just want the brief to reflect how we actually trade—which is the ladder." The entry ladder never fills worse than the mark, so every headline, sentence, EV, interval, theory ranking, PARK / setup summary, §1.9, §1.10 and §1.11 is on `pnl_usd`, the ladder's fill (mark or better), and the theories are sorted by the mark EV. v2.12's executable lead, its spread-cost line and its unpriced list are withdrawn, and the brief never calls the mark a paper assumption or something live fills do not get. Columns are never dropped: the ask/bid figure (window_ev.csv / theories.csv `*_exec*`, `pnl_exec_usd`) may appear only as the last, trailing column of a data table, never in prose. Fees beside, never inside EV. In every table the total adds up from the rows shown, on one basis.

**v2.15 · 2026-11-16 · dtp r565 (O08)**: §1.11, RUNAWAY O08 WOULD-BE every Saturday (report only, never in the window EV or the theories): the Runaway trades from 2026-11-16 re-scored as if O08 were on (skip the entry when the contract's spread at entry, (`entry_ask` − `entry_bid`) / mid, is more than 5% of mid; the 11-16 Runaway variant study's one sealed-holdout finalist), kept vs skipped, the Δ with its interval (at the mark since v2.16), every skipped $200+ winner named as a cost, and a decision note fixed today and stated verbatim each week. The operator, 2026-11-16: "Consider O08 as a candidate after we get more paper trades" and "Include its 'would be' in the weekend briefs." Not in the nightly review.

**v2.14 · 2026-11-15 · dtp r564 (HYG.28)**: §1.8 names the ramp max by its new key, `OT_BREAKOUT_BUDGET_USD` (OTV5 r125 renamed
`OT_ORB_BUDGET_USD`, named after the retired ORB trade). Nothing else changes.

**v2.13 · 2026-11-14 · dtp (OGAP.1)**: §1.9, OGAP on its own line every Saturday (Park's friend's opening-gap trade, QQQ paper, OTV5 OGAP.1; never in the window EV or the theories), and §1.10, OGAP VS PARK like for like (index rows, $500 of outlay a row; at the mark since v2.16) with a decision rule fixed today and stated verbatim each week, report only until its point. The operator, 2026-11-14: "let's design & paper trade the OGAP on QQQ" and "compare them".

**v2.12 · 2026-11-14 · dtp r557 (AM.1's reporting half)**: §1's EV benchmark leads with the EXECUTABLE basis (bought at the ask, sold at the bid; window_ev.csv `realized_exec`, `ev_exec_per_trade`, `ev_exec_lo/hi`, theories.csv `*_exec_ev`, from OTV5 r111's `pnl_exec_usd` and `~/reviews/exec_basis_backfill.csv` for earlier rows) with the mark beside it, the spread cost on its own line, and every unpriced trade named (never priced at the mark). Fees stay beside, never in EV. **Withdrawn by v2.16: the mark is the only basis.** The operator, 2026-11-14: "fix the top 10 today".

**v2.11 · 2026-11-14 · dtp r555 (AM.9, the brief 2026-11-14 R4)**: the study seal is the dispatcher's. `study_dispatch.py` v1.3 writes each item's `SEAL.txt` on control before the agent starts, records and acks `FROZEN.json` on control, and accepts a result only on control's own record of the order (box mtimes decide nothing); fixes after the freeze go to `AMENDMENTS.txt`. The prompt's FALLBACK 2 on control logs each file's sha256 and UTC time in `CONTROL_LOG.txt`. The operator, 2026-11-14: "Yes" (R4) and "fix the top 10 today".

**v2.10 · 2026-11-14 · dtp r554 (the brief 2026-11-14 §4, items 1 and carried 7)**: the Friday timer spec v2.9 names is installed by the operator (`sudo bash tools/install_study_dispatch.sh`), not by the land; until it is, the brief's fallback runs the queue. 2026-11-13's two Friday runs were started by hand from the control Claude session (SAT.9). The Output row no longer says the 09-26..10-31 briefs "still sit" in `handoffs/`: every brief is in `~/reviews/weekly/`.

**v2.9 · 2026-11-13 · dtp r552 (SAT.9)**: the study queue runs FRIDAY NIGHT. The control timer `dtp-study-dispatch` (`tools/friday_studies.sh`, Friday 17:15 ET, after the 16:05 conductor and the 16:40 nightly review; not Persistent) runs `study_dispatch.py` into this brief's `<WORK>/study_dispatch` with the deadline Saturday 02:30 ET, so the 03:00 brief collects finished results instead of starting them. An item may name `- Depends:` items (WS.9, the combined Hunt gate): it runs in a second round after them, with their results and folders, and is DONE "nothing passed, not run" when none passed. Study boxes hold the midnight halt (a hold flag the cleanup removes only when it is the dispatcher's) and are acknowledged to the hourly power audit. The brief starts the dispatch itself only when Friday's run is missing or broken. The operator, 2026-11-13: "Yes, don't wait until Sunday to do that study. Add it to the rest".

**v2.8 · 2026-11-11 · dtp r551 (CASH.1)**: §1.8's sizing rule corrected to the code (OTV5 `size_for`): Breakout's risk count has the at-least-1 floor, max(1, floor(base / ((entry − stop premium) × 100))), and without a usable stop premium it falls back to the geometry count max(1, floor(width / distance)) instead of NOT MEASURED; the deploy cap is named off (`OT_SIZE_ON_RISK` default). r550's text would have refused Breakout trades the bot takes. The operator said yes to the fix, 2026-11-11.

**v2.7 · 2026-11-11 · dtp r550 (CASH.1)**: §1.8, the QQQ cash size table, every Saturday until the cash start (last run 12-05; from 2026-12-07 the brief skips it). Every QQQ trade since 10-26 is re-sized under A) base $250 / ramp max $500 and B) base $500 / ramp max $750, the per-trade cap at the ramp max. Report only; the operator sets the size, ramp and cap themselves at activation. The operator, 2026-11-11: "On the weekend prior, let's do a table of $250/$500 & $500/$750 with a cap at the ramp max", then "I think adding it to the Saturday brief is probably sufficient & just brief it every weekend until the date arrives".

**v2.6 · 2026-11-11 · dtp r549 (SAT.8)**: the study queue runs ON THE BOXES, IN PARALLEL. `tools/study_dispatch.py` gives each OPEN item (a sub-item such as WS.6a is its own) its own stopped box (never CRM, never a box someone else claimed) and a bounded headless study agent there; it copies each SEAL.txt to control the moment it appears, pulls each study to `~/reviews/studies/<ID>_<YYYYMMDD>/`, validates it (seal unchanged, SEAL ≤ FROZEN ≤ RESULT), cleans and stops every box, and marks the queue. The brief starts it after the box reads and collects it in §6; the fleet is CLOSED only after it finishes. r548 ran the queue on control in about 30 minutes; this runs up to one item per box for about three hours. The operator, 2026-11-11: "What about just waking more boxes at the 0300 to run these studies in parallel?"

**v2.5 · 2026-11-11 · dtp r548 (SAT.7)**: §6 runs the standing study queue `~/reviews/WEEKEND_STUDIES.md` every week. Each OPEN item is run blind (seal first, freeze, run once), after sections 1–5, one heavy job at a time, and stops 45 minutes before the deadline. Unfinished items go to NOT MEASURED and stay OPEN. The verdicts (TUNE or TRIM) go to §7. The operator, 2026-11-10: "Make sure you add whatever we want to study to the 0300 weekend activity."

**v2.4 · 2026-11-08 · dtp r538 (RETIRE.3)** — §1.5: the TCS shadow is gone (OTV5 r88 deleted it; the operator, 2026-11-08: "Delete"), so the section reads only the PARK late-day shadow, through `_envelopes` on `check_name`; §5's remnant note no longer keeps the TCS.

**Status: the operator's spec, as of 2026-11-21 (v3.0; first written 2026-10-31).** It replaces `options-trader-v4/handoffs/SATURDAY_BRIEF.md`
and `SATURDAY_RUNBOOK.md` (2026-09-19). Those were written for another fleet, two engines and ORB. The fleet is now
one engine (OTV5) on the boxes the instance map names. This file is tracked in `day_trader_pro/docs/`. The
timer's prompt is `tools/saturday_brief.prompt`, and `tests/check_saturday_brief.py` checks that the prompt matches
this spec. Backlog row: **SAT.4** (OTV5 `docs/BACKLOG.md`, section I — "The box: install, services, menus and the agent"; v2.3 corrects "section H").

## THE OPERATOR'S RULINGS (2026-10-31 and 2026-11-21, verbatim)

- *"Re-do the entire brief. It should include issues from the bot logs, trading summaries, documentation
  corrections, code hygiene issues, proposed studies to increase P&L, and recommendations."*
- On the old Saturday-run items: *"Keep what's useful & retire the rest".*
- *"don't list the retired strategies either. They're no longer relevant to this repo."*
- On a retired box: *"I don't think AAL's retirement is announcement worthy... nobody cares".* So the brief
  reports no non-events.
- Earlier: the brief is **prepared at 03:00 and delivered on request, one section at a time.**
- Still in force from 2026-09-19: *"Check each of these things and do a report, but don't take any action yet."*
- 2026-11-21, the layout: *"1) Trading- A. ... B. ... C. ... 2) Our edge- A) ... B) ... 3) Bot performance- A) ...
  B) ... C) ... 4) Recommendations"* (in full in v3.0 above), and *"the things I forgot to mention should be worked
  into whichever section they best fit into"*.

---

## WHEN, WHERE, AND HOW IT IS DELIVERED

| | |
|---|---|
| Start | cron, Saturday 08:00 UTC: 03:00 EST (04:00 EDT from March); the watchdog at 12:45 UTC, after the deadline. `tools/saturday_brief.sh` runs it. (Installed with SAT.4; before that the crontab read 07:17 UTC) |
| Deadline | **07:30 ET.** The wrapper kills the session then (`timeout`, rc 124). Have the file written well before that |
| Output | `~/reviews/weekly/saturday_<YYYY-MM-DD>.md`, beside the daily reviews. It is **not** written to `options-trader-v4/handoffs/` (gitignored; `check_scratch_purge` P12). Every brief since 09-19 is in `~/reviews/weekly/`; `handoffs/` holds none |
| Working files | `~/reviews/weekly/saturday_<date>_work/`: `sweep/`, `botlog/`, `disk.json`, `weekly_facts.{md,json}`, `backlog.json`, tool outputs. **Next week diffs against these**, so keep them |
| Prior | the wrapper passes last week's brief and its `_work/` folder |
| Delivery | nothing is sent. When the operator asks, the session shows the **index** first, then **one section at a time** (or one part, 1A..4, when they ask for a part), in order |

The output file has this shape, so a session can print one section, or one part, on its own:

    # SATURDAY BRIEF — <date>  ·  week <Mon>..<Fri>  ·  <N> boxes  ·  OTV5 <sha>
    ## INDEX              one line per part (1A..4): its headline, or "nothing to report"
    ## 1. TRADING
    ### 1A. THE WEEK'S TRADES
    ### 1B. GIVEBACK ON EXITS, NEVER RIGHT ON ENTRIES, AND EACH SETUP AGAINST ITS HISTORY
    ### 1C. THE EPOCH (OTV5)
    ## 2. OUR EDGE
    ### 2A. TOP EARNING SETUP CONDITIONS, AND WHERE TO LOOK FOR EDGE
    ### 2B. THE WEEK'S STUDIES
    ## 3. BOT PERFORMANCE
    ### 3A. ERRORS AND ISSUES THIS WEEK
    ### 3B. HOW LAST WEEK'S FIXES DID
    ### 3C. THE BACKLOG
    ## 4. RECOMMENDATIONS
    ## NOT MEASURED       by name, with the reason

Each part starts with its headline in one or two sentences and stands on its own (no "see above"). Section 4 ends
with the Sunday work list; NOT MEASURED is the only thing after it.

---

## RULES FOR EVERY BRIEF

1. **Plain language.** Short sentences. Use the symbol, the dollar figure and n. Use "they/them" for the operator.
2. **No retired strategies.** The brief reports only setups that closed a trade or wrote a shadow row in the
   week. A setup that no longer trades is never named: its epoch rows are one line, "setups no longer trading
   (history)", so every total still adds up. 3C's hygiene items are the only place retired code comes up, as
   **code to remove**, never as a strategy to report on.
3. **No non-events.** Leave out anything that did not happen or did not change: a box that was retired, a series
   with no new data, a check that is still green. Each part ends with one line, `Checked, nothing to report:`,
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
8. **Say n every time** (§12), and give every EV its day-bootstrap 95% interval. A thin sample shows a mechanism,
   never a conclusion. Edge is judged over the horizon, never on one day: a bad day is variance unless something broke.
9. **The basis is the mark** (v2.16, MARK.1): `pnl_usd`, the ladder's fill (mark or better). The ask/bid figure
   (`pnl_exec_usd`, `x gross`, the `*_exec*` columns) appears only as the last, trailing column of a data table,
   never in prose. **Fees are reported beside EV, never inside it**: EV is gross a trade; net = gross − fees is its
   own column next to gross. In every table the total adds up from the rows shown, on one basis.
10. **The OTV4TEST fleet's rows are filtered** out of every warehouse measurement, using
    `OTV5 tests/warehouse_source.mainline()` (the record's lineage first, then the box and date). 1A's exclusions
    line names what the filter and every other exclusion dropped, every week, so the totals are known complete.
11. **Nothing unmeasured is stated as fact** (§0, §0.1). A measurement that could not be taken goes in NOT
    MEASURED with its reason. If a tool caused the gap, say so: the gap is the tool's, not the tape's.
12. **Interpreter: `/home/ubuntu/day_trader_pro/venv/bin/python`.** A red under a bare `python3` is an environment
    red (CHK.9/11).
13. **Market data is TastyTrade's** (S3 `raw/candles`, `raw/ohlc`, `raw/market_metrics`). yfinance only ever for NQ/ES
    study inputs, never here.
14. **Never proposed:** a config knob or study toggle, a resting take-profit (a closed topic), a new order rule.

---

## RUN ORDER AND TIME BUDGET (03:00 → 07:30 ET)

| ET | step | fleet |
|---|---|---|
| 03:00 | read the spec, last week's brief, OTV5 `docs/BACKLOG.md` (open rows), `docs/GENESIS.md` tail; set the week | down |
| 03:05 | **WAKE** | up |
| 03:10 | 3A box reads (bot-log scan, code, services, disk, box-vs-S3 trades); the QQQ box's loss-limit banner (4.3) | up |
| ~03:45 | Friday night's study dispatch is finished (Fri 17:15 → Sat 02:30 ET); read its summary. Only if it is missing or broken, **START the study dispatch** (`study_dispatch.py run`, nohup, `<WORK>/study_dispatch_sat`) | down (study boxes up only on the fallback) |
| 03:45 | checker sweep (about 25 min), then the R suite (the exit replay takes about 25 min), one heavy job at a time in the background | study boxes up |
| 04:15 | `weekly_facts.py`, then 1A, 1B, 1C from it, S3, the bundles and `~/reviews/` | study boxes up |
| 05:15 | 3B and 3C (read the ledgers and the trees) | study boxes up |
| 06:15 | 2A, 2B (bars written first, cheap studies run; the queue's results from `study_dispatch.py wait`), section 4 | fallback study boxes finish by DEADLINE − 25 min |
| ≤ 07:05 | `study_dispatch.py cleanup`, then **CLOSE** and verify `N/N reached 'stopped'` | down |
| ≤ 07:15 | the file is written; then INDEX and NOT MEASURED are finished | down |

    WAKE   cd /home/ubuntu/day_trader_pro && ./venv/bin/python wake_and_bake.py --wake-only --yes
    CLOSE  cd /home/ubuntu/day_trader_pro && ./venv/bin/python wake_and_bake.py --shutdown-only --yes

`--wake-only` means wake and ping only. The bare `wake_and_bake.py` runs the full cycle, and a bake is an action.
Both read the fleet from the instance map, so never use a hard-coded count. Never wake during RTH
(09:30–16:00 ET); a hand run inside RTH leaves the box reads NOT MEASURED. Long jobs run with `nohup … > file 2>&1;
echo rc=$? >> file` and a `timeout`, each heavy one as `flock /tmp/claude-heavy.lock env HEAVY_MAX=2500M
/home/ubuntu/bin/heavy …` (control has 3.8 GB), one at a time. Never pipe them through `tail` in an `&&` chain.

**The week** is the week's sessions, Monday to Friday, read through `market_calendar` so that half days and
holidays are handled. **The epoch** is OTV5's record from its first session, 2026-10-26 (the fleet's repoint,
`strategy_registry.OTV5_SINCE`, 2026-10-25), through the Friday. State both once and use them everywhere.

**The numbers (v3.0).** Before writing section 1 (about 30 s; S3 reads only):

    /home/ubuntu/day_trader_pro/venv/bin/python -I /home/ubuntu/day_trader_pro/tools/weekly_facts.py --fri <Fri> --out <WORK>

`weekly_facts.py` reads `~/reviews/trades/<day>.csv` (review_kit `trades`: warehouse rows through `mainline()`, the
control fee model) for the epoch, the week's warehouse rows (`load_trades` → `mainline()`) for MAE, capital and
the exit ladder, and the daily candles for the tape. It writes `<WORK>/weekly_facts.md` and `.json`. **Quote it;
never re-derive a figure it prints.** A day without a daily candle leaves that day's tape NOT MEASURED; a failed
`weekly_facts.py` leaves 1A-1C's tables NOT MEASURED, by name, and the brief says so at the top of section 1.

---

## 1. TRADING

**Purpose:** what the week made and lost, where and why, and whether the epoch is getting better.

### 1A. THE WEEK'S TRADES

**Lead:** the week's n, gross, EV a trade with its interval, fees beside, and net (gross − fees).

**From `weekly_facts.md` §1A, quoted:**
- **by setup**: n, W-L, gross, EV a trade, its 95% day-bootstrap interval, fees, net (gross − fees), and the
  trailing `x gross` column; then setup × side; by day (n, gross, net, and what decided the day, in one clause); by
  symbol (sorted); entries by time bucket (09:30–10:00, 10:00–10:30, 10:30–11:30, later); the five best and five
  worst trades with their exit reason. Fees per day and for the week are the by-day table's fees column (old §1.6).
- **MFE/MAE**: per setup the median MFE and MAE in dollars over the position (MFE from the trade CSV's `mfe_premium`,
  MAE from the warehouse row's `mae_premium`) and the median capture (P&L / MFE).
- **the QQQ-only view** beside the fleet totals (the 12-04 cash test is QQQ only): the same row, QQQ trades only.
- **risk**: the worst day; the longest losing-trade streak this week and in the epoch (and the one standing now); the
  longest red-day streak; the epoch's drawdown from its peak (equity, peak and its day, the largest drawdown with
  its dates, how far below the peak it stands now); **peak capital deployed** per day (the most premium open at one
  time, fleet and QQQ), each against the operator's comfort of about a quarter of $25k a day (~$6,250), with every
  day over it named.
- **the exclusions line, every week** (rule 10): OTV4TEST rows dropped by `mainline()`, blank-P&L or not-closed
  rows, trades only in the CSV or only in the warehouse, P&L mismatches, estimated fees, missing MFE. Also check the
  week against `reports/warehouse/fleet_trades_<day>.json` (deduped by trade_id) and name any day on which they
  disagree. "0 dropped" is a line here, not a non-event: it is how the operator knows the totals are complete.

**Also in 1A:**
- **ladder fill quality.** Entries: fills are the trades; misses are 3A's `ladder` refusal class and abandoned walks
  (`[ladder] … REFUSED`, `the walk on … is abandoned`) from `botlog_scan`, per box; time to fill from the bot.log
  `[ladder] … BUY` and fill lines where the scan or a brief read of one box gives them, else NOT MEASURED. Exits:
  `weekly_facts`' exit-ladder line (steps, submit-to-fill, escalations). Paper exits fill at the first rung, so say
  so beside the figure: it is the paper record, not a live fill rate.
- **the R ledger and excursions** (performance commentary):

      /home/ubuntu/day_trader_pro/venv/bin/python /home/ubuntu/OTV5/tests/r_ledger.py --from <Mon> --to <Fri>
      /home/ubuntu/day_trader_pro/venv/bin/python /home/ubuntu/day_trader_pro/excursion_report.py --since <Mon> --date <Fri>

  The BOOK line (n, net, R, e/t, capture) and setup × side rows. The R ledger's R is average win over |average
  loss|; say so beside any R figure. Excursions are BUNDLE-sourced (OTV5 has no `excursions.py` yet; a 3C item).
  `fit_readiness.py` (dtp, `--from/--to`) is used **only** to name a setup that crossed a fittability line this week;
  its "READY" counts signal rows, not trades (D7), so it is never reported as readiness.

### 1B. GIVEBACK ON EXITS, NEVER RIGHT ON ENTRIES, AND EACH SETUP AGAINST ITS HISTORY

**Lead:** how much of the week's peak open profit was given back, how many entries were never right, and which
setup did worse (or better) than its own history.

- **Giveback** (old §1.4): `~/reviews/giveback.csv` (the daily study's definition: peak sampled per 15 s tick) is the
  headline: the week's total given back out of peak open profit, the green-to-red count and dollars, the worst day.
  The **by-setup split** is `weekly_facts.md`'s giveback table (row basis, the CSV's `mfe_premium`: peak open $,
  given back, %, green-to-red n and $), labelled row basis beside the tick figure.
- **Never right on entries**: per setup, the trades that never traded above their entry (peak open $ ≤ 0), n and
  dollars, from the same table. These are entry problems, not exit problems: say which setup has the most.
- **P&L by exit rule** and **selection vs extension** from the R ledger (never "favourable vs was favourable").
- **The PARK late-day shadow (never in EV)** (old §1.5): `raw/derived_plan_check/` rows whose check starts with
  `park_late_` (OTV5 r63, `park_late_would_exit`). For each PARK trade it touched: would-exit time and mark against
  the actual exit, and the dollar difference. Total and n. Read it through OTV5 `tests/warehouse_source.py` (§36a on
  OTV5; never a hand-rolled paginator), folding `raw/derived_plan_check/` one object at a time (`_envelopes`;
  `load_derived` materialises the week and runs out of memory on control) and filtering on the `check_name` column.
  If no row is found, put it in NOT MEASURED and say whether the boxes have the code (3A). `raw/shadow/` is a
  different, older stream (its last day is 2026-09-11).
- **Each setup against its own history**: `weekly_facts.md`'s table: this week's n, EV and interval beside the same
  setup's epoch record before this week. A week inside the history's interval is variance; say so, and name only a
  week that sits outside it, or a setup whose history interval excludes zero.
- **Missed and under-captured moves** (old §1.3): from S3 5-minute RTH bars (`raw/candles/…/interval=5m`, deduped on
  `ts_epoch_ms`; `warehouse_source.stream_series`), cross-checked against 1m `raw/ohlc`: box-days that took no trade
  on a range at or above the symbol's median, and traded days where the book captured little of a large move. For
  each: one line on what happened. Use 3A's refusal counts to say **why** a box sat out where the log shows it.

### 1C. THE EPOCH (OTV5)

**Lead:** the epoch's n, gross, EV a trade with its interval, fees beside, net; and in one sentence whether it is
improving or worsening, read against the tape.

**From `weekly_facts.md` §1C, quoted:**
- **the epoch by setup**: the 1A columns over every epoch day; setups that no longer trade are the one unnamed
  history line (rule 2); the **live book** (setups trading today) on its own line with its interval.
- **week by week**: n, gross, EV with its interval, fees, green days, the **tape** (QQQ's trend efficiency,
  |close − open| / (high − low), averaged over the week with each day's label: trend ≥ 0.6, chop ≤ 0.3, else mixed;
  the median VIX close: low < 15, normal 15–20, elevated 20–30, high ≥ 30; from the daily candles), and the epoch
  EV to date after that week. Improving or worsening is read against this: a better week on a trend tape is not yet
  a better book. Say what the intervals say (overlapping weeks are not a trend).
- **consistency**: green days of all days; the first half against the second half of the epoch (EV, interval, n);
  the best three days' share of the gross, and the EV without them.
- **noteworthy in the sample**: name anything a reader should weigh: a total carried by one setup or a few days, a
  setup whose n is too thin to judge, a regime the epoch has not yet seen. Say n each time.

**The EV benchmark window 2026-10-26 → 11-27 (old §1.1), through the brief of 2026-11-28 only.** Its final score is
in the 11-28 brief; **from 2026-12-05 the brief skips it and does not mention it** (the epoch replaces it). Until
then: `~/reviews/window_ev.csv` (window-to-date: trades, realized, fees, EV a trade, EV without the worst setup and
without the worst symbol) and `~/reviews/theories.csv` (the operator's pre-cash theories, scored nightly by
`~/reviews/scripts/theories.py`): window-to-date EV and its two exclusions; the week's change in each; the theories
table as of Friday, **sorted by the mark EV**, with its leader and its n; the pre-decay days (10-26..10-30) and the
post-decay days (from 11-02) apart. **The basis is the mark (v2.16):** `realized`, `ev_per_trade` and the theories'
`*_ev` columns; the ask/bid columns are trailing data only, never discussed. OGAP is never in the window EV, the
theories or "ex worst setup" (review_kit `load_window` leaves it out). These files belong to the daily review: **read
them and never write them.** A missing day's row goes in NOT MEASURED; a day whose trades or realized disagree with
the bundles is reported.

---

## 2. OUR EDGE

**Purpose:** where the money comes from, where it leaks, and what the studies say to do about it.

### 2A. TOP EARNING SETUP CONDITIONS, AND WHERE TO LOOK FOR EDGE

**Lead:** the best and worst condition cells over the epoch, and the one or two places most worth a study.

- **Condition cells** from `weekly_facts.md` §2A: live setups by setup × side × entry time and by setup × symbol, each
  cell with n ≥ 8, sorted by EV with its interval; the top six and the bottom six. A cell is a lead, never a finding:
  a top cell whose interval spans zero is said to span zero, and no cell is called an edge on one week.
- **Where to look for edge improvements**: the bottom cells, 1B's never-right and giveback leaders, and the
  counterfactual half of the R suite (OTV5 `tests/`, dtp venv, `--from <Mon> --to <Fri>`):

      stop_sweep.py      the stop/TP surface over recorded excursions (n ≥ 20 surfaces only)
      exit_replay.py     trail and stop alternatives on real premium paths (~25 min; positive control must reconcile)
      edge_scan.py       features against the pre-registered bar (prints its FLEET line)

  The exit replay's positive control comes first. If replayed trades do not reconcile, every alternative is
  suspect, and the brief says so. When the two tools disagree, report the disagreement; do not pick one. A lead
  becomes a study (2B), never a code change: a candidate needs a sealed-holdout pass before code.

**Decisions in progress (every Saturday brief dated on or before 2026-12-04).** The operator decides the Hunt and
OGAP before the 12-04 cash test; until then 2A shows the numbers they decide on. From 2026-12-05 the OGAP line and
the Hunt line leave the brief; OGAP vs PARK stays every Saturday until its rule's decision point or the operator's
OGAP decision, whichever comes first. None of the three makes an R-item in section 4; 4.3 carries the decisions as
readiness items.

**OGAP, its own line** (old §1.9; OTV5 OGAP.1, OTV5 `docs/OGAP_SPEC.md`): Park's friend's opening-gap trade, a
faithful paper copy on the QQQ box only. The operator, 2026-11-14: "let's design & paper trade the OGAP on QQQ". It
is NEVER in the 10-26..11-27 window EV, the theories or "ex worst setup". Every OGAP row to date (strategy `OGAP`
in `~/reviews/trades/*.csv`; `weekly_facts.md`'s OGAP line): n, W-L, the P&L at the mark (`pnl_usd`, the ladder's
fill, mark or better), fees beside and never in; EV a row with a day-bootstrap 95% interval; signals before vs
after 10:00; calls vs puts; exit reasons; the gate-G shadows (`data/counterfactual/ogap_shadow.jsonl`, plan check
`ogap_gateg_shadow`), labelled SHADOW and never in EV; the status of the bars (OGAP_SPEC §11).

**OGAP vs PARK** (old §1.10). The operator, 2026-11-14: "compare them". Like for like: index rows only (QQQ, SPX), at
the mark (`pnl_usd`, the ladder's fill, mark or better), each row scaled to $500 of premium outlay (P&L x 500 /
(entry premium x contracts x 100)), fees beside, never in EV. Per setup: n, EV a trade with a day-bootstrap 95%
interval, the worst day, the largest loss. Overlap days (both fired the same session): the count, the share on the
same side, and the correlation of daily P&L on the days both traded (`weekly_facts.md`'s OGAP vs PARK line). **The
decision rule, fixed 2026-11-14 and stated verbatim every week:** "Decide when each has >= 20 index trades, or at
2026-12-31, whichever comes first. Keep the better one if their daily P&L correlation is >= 0.5. Keep both if both
have EV > 0 and correlation < 0.5. Keep neither if neither clears zero." Until that point is reached it is REPORT
ONLY: the brief says how many index trades each has and makes no recommendation in section 4.

**The Hunt line.** The Hunt stays on paper; the operator decides it before the 12-04 cash test. From
`weekly_facts.md` (and `~/reviews/hunt_side.csv`): LiquidityHunt by side (call, put), the week and the epoch: n,
gross, EV a trade with its interval, fees beside, net; the latest study verdicts that name the Hunt (2B), one line
each with their ids. REPORT ONLY: the decision is theirs.

### 2B. THE WEEK'S STUDIES

**Lead:** how many studies ran, how many PASSED, FAILED or were VOID, and what is actionable.

**The week's results.** Per item: id and title, the blind n, EV a trade with its 95% interval, the window EV with
its interval, and the verdict **PASS, FAIL or VOID** against the item's own bar, unedited (VOID: the dispatcher's
invalid or unfinished result, or a NOT MEASURED; the item stays OPEN). Then **actionable?** (a TUNE or TRIM goes to
section 4 as an operator decision; a trading change under the freeze only if the code is broken) and **dig deeper?**
(one line on where, when a result is thin, carried by one trade, or reversed by another sample). Say when Friday's
run started and finished (its `state.json`) and which started it.

**The coming Friday's queue, so the operator can strike any before they run.** The OPEN items as of this brief:

    cd /home/ubuntu/day_trader_pro && ./venv/bin/python tools/study_dispatch.py plan

Per item: id, title, the hypothesis in one line, and its pass bar in one line. Say that the daily recap adds items
during the week (up to three a day), so Friday's list can be longer. A struck item is the operator's call; the
brief never edits the queue except the dispatcher's own status marks.

**The study queue (standing, every week, v2.6):** `~/reviews/WEEKEND_STUDIES.md` holds the studies the
operator and the sessions have agreed to run, each with its hypothesis, data, seal rule and pass bar written
before testing. Every item marked OPEN is run blind, and since v2.6 they run ON THE BOXES, IN PARALLEL
(`tools/study_dispatch.py`, SAT.8), and since v2.9 on FRIDAY NIGHT (SAT.9):
- The control timer `dtp-study-dispatch` runs `tools/friday_studies.sh` Friday 17:15 ET (not Persistent; the script
  refuses off Friday evening, waits for the conductor and, since v2.17, for Friday's daily recap). **The timer is installed by the operator
  (`sudo bash tools/install_study_dispatch.sh`); the land does not install it, and until then the brief's fallback runs
  the queue.** (2026-11-13's two Friday runs were started by hand from the control Claude session; SAT.9.) It runs `study_dispatch.py run --deadline 02:30 --out
  <WORK>/study_dispatch` for Saturday's WORK, then `study_dispatch.py cleanup`; ledger `~/friday_studies.ledger`.
  The brief collects it. Only when it is missing or broken (no `state.json`, a log ending in REFUSED or ERROR, or
  no "finished") does the brief start `study_dispatch.py run` itself, right after the box reads, into
  `<WORK>/study_dispatch_sat`, and say so at the top of NOT MEASURED.
- An item with a `- Depends: WS.a, WS.b` line runs in a second round: only after every item it names has finished
  (in this run or closed earlier in the queue), on the box the last one frees, with each dependency's verdict, one
  line, recommendation and study folder in its brief and kit. When none of them PASSED it is marked DONE "nothing
  passed, not run" and uses no box; a dependency that failed or is invalid leaves it OPEN and NOT MEASURED.
- Every box halts itself at 00:00 ET (OTV5 `midnight_halt.py`) unless `~/options-trader/data/NO_MIDNIGHT_HALT`
  exists: the runner writes that flag (content `study_dispatch`, only if none exists) and the cleanup removes it only
  when it is the dispatcher's. Each held box is acknowledged in `logs/power_ack.txt` for each ET day, so the hourly
  power audit does not page for a study box.
- The dispatcher refuses inside the trading window
  (Mon–Fri 08:45–16:50 ET). One OPEN item per box; a sub-item such as WS.6a is its own item. A box with someone
  else's claim in `~/reviews/box_claims` is skipped. It writes its own claim per box, and
  every power call goes through ec2ops under `flock /tmp/claude-fleet.lock`. Unused, unclaimed boxes are stopped.
- On each box it stops optionsbot and candle-feed and runs a bounded headless `claude -p` study agent (the
  research token is read from SSM with the box's own role; never printed, never copied from control). The agent
  reads the warehouse with the box's own role, writes nothing outside its work dir and never writes S3.
- Since v2.11 (dtp r555, AM.9) the seal is never self-attested. The DISPATCHER writes `SEAL.txt` (a `SEALED_AT` UTC
  line, `ITEM_SHA256`, the item's text) on control before the kit ships, and the box copy is read-only. The agent
  writes `FROZEN.json` before any sealed-day outcome; the first poll that sees it pulls it to control
  (`FROZEN.control.json`), records its sha and control's time, and writes `FROZEN.ack`, which the agent waits for
  before the single blind run; `RESULT.json` comes last. A result is accepted only if the returned SEAL and FROZEN
  are byte-identical to control's, FROZEN was seen at an earlier poll than RESULT, and seal < frozen < result on
  control's clock. Box mtimes are recorded, never trusted. A code fix after the freeze is appended to
  `AMENDMENTS.txt`; SEAL and FROZEN never change. The study lands in `~/reviews/studies/<ID>_<YYYYMMDD>/`, with the
  control copy as `SEAL.control.txt`. On control (FALLBACK 2) the session follows the queue's HOW block: SEAL, then
  FROZEN, each logged with its sha256 and UTC time in `CONTROL_LOG.txt` as it is written.
- Cleanup on every exit path, including timeout and failure: the session is killed, `~/study_<run>` and the run's
  `~/.claude/projects` transcripts are removed, S3 scratch is deleted, the box is stopped and the claim released.
  A freed box takes the next queued item while at least 45 minutes remain. Every box is killed 25 minutes before
  the deadline. The wrapper exports the deadline (`STUDY_DISPATCH_DEADLINE_ET`) and runs `study_dispatch.py
  cleanup` after the session as a safety net.
- The dispatcher marks each item DONE or FORWARD in the queue file; invalid or unfinished items stay OPEN and are
  listed in its summary's NOT MEASURED. The brief collects it with `study_dispatch.py wait` in 2B: per item the
  blind n, EV a trade with its 95% interval, the window EV with its interval, and PASS or FAIL against the item's
  own bar, unedited. The TUNE or TRIM verdict goes to section 4. When the brief started the dispatch (the fallback), the fleet
  is CLOSED only after the dispatcher finishes.
- Last fallback, only if the brief's own dispatch also refused or failed before launching anything: the brief runs OPEN items on
  control, blind as above, one heavy job at a time through `flock /tmp/claude-heavy.lock /home/ubuntu/bin/heavy`,
  no new item in the last 45 minutes before the deadline, and lists the failure under NOT MEASURED.

Queued items don't count against the cap of five new proposals. Sessions add items by appending to the file
(IDs WS.<n>, never reused); nothing in this spec needs to change when they do.

**The R6 no-progress lead (standing, every week):** `/home/ubuntu/day_trader_pro/venv/bin/python -I
/home/ubuntu/reviews/scripts/noprog_lead.py 2026-11-02 <this Friday>` (timeout 3600 s); quote
`~/reviews/studies/noprog_<this Friday>.md`'s D10-vs-BASE table, its five P1-P5 lines and its verdict verbatim, with
no edits to the bar and no softened FAIL; if the run fails, it goes under NOT MEASURED. A PASS goes to section 4 as
an operator decision.

**Standing studies (kept from the old Saturday rows):**
- **GIVE.2, fleet:** exits that give back profit. 1B's giveback is its weekly input, and the exit families
  (no-progress cut, trails, decay stop from 11-02) are its candidates.
- **CUT.1, fleet:** OTV5 ends Runaway and Breakout entries at 10:29 (`RUNAWAY_END`, `BREAKOUT_END`) and records
  later fires LOG-ONLY (OBS.1). The bar is the row's own: RIGHT = blocked net ≤ 0; WRONG = ≥ 10 blocked fires,
  net > 0, and losing days not made worse. It needs a tool that prices a LOG-ONLY fire on its option's quotes. Until
  one exists it is NOT MEASURED, with the build as the study's cost.
- **PIN.3 (absorbs PIN.1):** what the directional pin gate's refusals would have made, from the refusal lines
  (3A) and the tape. Losing days first; name the cost case (a pinned open that breaks away).
- **DAY.1, final score:** E = |price − open| / (high − low) at 09:45 on QQQ and SPX from `raw/ohlc`, 10-07 to the
  window's end, scored against the row's frozen terms. It is scored once, then closed by its result.

**New proposals (at most five, ranked by expected $).** Each has these five fields, written **before** any number is
looked at:

| field | content |
|---|---|
| Hypothesis | one sentence that can be false |
| Data | S3 prefixes or files, window, n expected |
| Pass bar | the rule that decides it, written before the test. Give the hold-out (losing days first, top winner kept, fit then validate on unseen days) |
| Expected $ effect | the estimate before the test, with the arithmetic (e.g. "saves 30% of the no-progress losses, about $3.7k a week") |
| Cost | tooling to build, runtime, and whether it touches trading code (the freeze) |

A bar written after the data was seen is labelled **post hoc** and cannot pass anything. Before proposing a study,
search OTV5 `docs/BACKLOG.md` (STR.1, the 10-24 studies), `~/giv_study/`, the queue and last week's brief for the
same idea, so a study that already failed is not proposed again as new.

---

## 3. BOT PERFORMANCE

**Purpose:** is the fleet sound for Monday, did last week's fixes work, and is the backlog shrinking.

### 3A. ERRORS AND ISSUES THIS WEEK

**Lead:** new error signatures, anything that refused or blinded a box, and any fleet-health finding.

**The bot logs** (old §2):

    /home/ubuntu/day_trader_pro/venv/bin/python /home/ubuntu/day_trader_pro/tools/botlog_scan.py \
        --from <Mon> --to <Fri> --out <WORK>/botlog --prior <PRIOR_WORK>/botlog --by-day

`<PRIOR_WORK>` is the wrapper's PRIOR_WORK parameter (v2.2, wrapper v1.8): last week's `_work` folder from
`~/reviews/weekly/` only. When it reads `NONE - …`, run `botlog_scan` and `checker_sweep` without `--prior` and say
so in the part. The header's tree line is the wrapper's TREES parameter (OTV5's and dtp's HEADs), never otv4's.

`botlog_scan` sends one read-only script through `fleet.py run`. On each box it reads `~/options-trader/bot.log`
and its rotations, and nothing else. It counts per box and per day: ERROR, CRITICAL, Traceback (with the exception
line), refusals by class (v1.1, dtp r526: `pin`, `commit` (COMMIT.2), `sizing:<reason>`, `entry_end`, `orb_break`,
`gate:<Strategy>@<condition>`, `afd`, `park_starved`, `no_chain`, `ladder`, `pin_exempt_would_refuse`, `other:<tag>`),
blind/stale/reconnect feed lines, real cap hits (never the start-up banner), and service starts with their ET times
(`start_rth` counts a start between 09:30 and 16:00 ET). Every line is keyed by its ET day. `--by-day` prints each
box-day's refusal classes: a sat-out day in 1B is explained from it, by class and count. Each line is folded into a
signature, with token-shaped text redacted on the box. It diffs the signatures against last week's.

Report, in this order:
1. **New signatures** in CRITICAL, Traceback and ERROR: box(es), count, first and last time, and one line on what
   it is. Read the context on that one box, read-only and briefly (`fleet.py run --only SYM "grep -n -m5 -F
   '<literal>' ~/options-trader/bot.log | cut -c1-300"`). Never paste more than a few lines.
2. **Count jumps**: a class that doubled week on week, or any box with more than one service start on a
   session day (the 09:15 wake is the expected one).
3. **Feed episodes**: blind or stale stretches. Give the box, the day and how long, and say whether a trade was
   open during it.
4. **Gate refusals**: totals by class and box, and for each of 1B's sat-out days the `--by-day` line that explains
   it. A gate that refused every fire on a trend day is a finding, not a defect.
5. **Cap hits**: box, day, time, and what was refused after it.
6. **Anything else** a human would flag (a loop, an order rejected, a session reset during RTH).

A box the scan could not read is listed by name as NOT READ. Its silence is never counted as a zero.

**Fleet health** (old §3). Only findings get detail.
- **Checker sweep, diffed by check ID:**

      /home/ubuntu/day_trader_pro/venv/bin/python /home/ubuntu/day_trader_pro/tools/checker_sweep.py \
          --out <WORK>/sweep --prior <PRIOR_WORK>/sweep

  The sweep runs OTV5 and dtp (otv4 is frozen; add `--trees otv5,dtp,otv4` only if asked). Each checker gets its
  own scratch directory, with the lander's store paths (OTV5 `tools/land.sh`, the "r13 — CHECKS NEVER TOUCH THE
  BOX'S STORES" block; cited by its anchor because RETIRE.1 moved it once already). The sweep writes `sweep.json`
  and `diff.json`. Report: **NEWLY RED** (file and IDs; give the cause where you can read it), **GREEN THAT WAS
  RED**, and **STILL RED, IDS CHANGED**. Give the standing reds as one count. A newly red checker comes first. A red
  flagged `[env]` is an interpreter fault, not a verdict. On the first run there is no prior: say so.
- **S3 parity:** the week's nightly verdicts in `/home/ubuntu/day_trader_pro/logs/eod_conductor.log` (VERIFY, HELD,
  `series_lag_s`, dtp r517); box against bucket, trades: each box's `trades.db`, opened read-only, counted and summed
  per day, against the bundles (0 mismatches is one line in "Checked, nothing to report"); streams and tails, LIST
  only:

      /home/ubuntu/day_trader_pro/venv/bin/python /home/ubuntu/day_trader_pro/warehouse_coverage.py --streams --since <Mon>
      /home/ubuntu/day_trader_pro/venv/bin/python /home/ubuntu/day_trader_pro/warehouse_coverage.py --tail --since <Mon>

  Report a MISS or a TRUNCATED tail (newest `quote_series` before close − 15 min) as box, day and time. A parity gap
  may be a counter problem rather than a data problem (S3.24/S3.25). Say which before calling it either.
- **Disk, with days to full:** for every box, `df -B1 --output=size,used,avail /` and the five largest files on `/`.
  Rank WAL files in place: a `*.db` glob misses `.db-wal`. Save it to `<WORK>/disk.json` (`{box: {size, used, avail,
  top: [[bytes, path], …]}, "at": iso}`). **Days to full** = avail ÷ (growth in used per day since
  `<PRIOR_WORK>/disk.json`). Without a prior file, use last week's table and label the result rounded. Flag any box at
  or above 85%, any box under 30 days to full, and any file that doubled. The 92% guard pages on the crossing.
- **Every box on current code, and its services:** each box's `git -C ~/options-trader rev-parse --short HEAD` (the
  box path has no suffix; `|| echo REPO_MISSING`), checked against control's `~/OTV5` HEAD and origin. Say whether
  the revisions between them are docs-only. `systemctl is-active optionsbot candle-feed s3-push.timer
  optbot-emergency-watchdog.timer candle-logger.timer`, and nothing more.

### 3B. HOW LAST WEEK'S FIXES DID

**Lead:** how many fixes landed since last Saturday, and how many showed live evidence that they worked.

Source: the revisions between last week's TREES (the prior brief's header) and this week's: OTV5 `docs/GENESIS.md`
rows and dtp's rows (`tools/genesis_find.py <rev>` searches both ledgers), plus last week's section 4 items marked
done. For each fix that changes behaviour: what it fixed, in one line; the **live evidence** this week (a bot-log
signature gone or its count changed in 3A, a trade or a plan-check row showing the new behaviour, a checker now
green, a timer's ledger line); and a verdict, **WORKED**, **NOT YET EXERCISED** (no live case this week: name what
would show it), or **DID NOT WORK** (one reproducing case; it goes to section 4 as a DEFECT). Docs-only and test-only
revisions are one count line. Never call a fix worked on the strength of its own gate: a gate proves the code, the
week proves the fix.

### 3C. THE BACKLOG

**Lead:** open rows now against last week, how many closed and opened, and the oldest item still owed.

- **Progress**: OTV5 `docs/BACKLOG.md` PART 1 (open rows): the count now, against last week's (`<PRIOR_WORK>/backlog.json`;
  write this week's as `<WORK>/backlog.json`, `{"at": iso, "open": [ids]}`); rows closed this week with their
  revision; rows opened this week; last week's Sunday work list, item by item: landed (rev), still waiting, dropped.
- **Documentation corrections, as backlog items** (old §4): docs that say something that is no longer true. Find them;
  do not fix them. Read OTV5 `docs/` (WORKING_AGREEMENT, HANDOFF, FILE_MAP, ENV, ROADMAP, TRADES, PLAN_SPEC) and dtp
  `docs/` (ARCHITECTURE, WAREHOUSE_MAP, MENU_INVENTORY.tsv), including this spec, against the code and the ledgers;
  the **strategy roster** (OTV5 `config.ENTRY_WINDOWS`, `strategy_registry` codes (dtp), the docs roster
  (`check_docs_roster`) and the menu labels: any name missing from one of them, or present in one only); **backlog
  against GENESIS** (an OPEN row whose fix GENESIS says landed, a DONE row with no revision, a row citing a file or
  path that no longer exists, a row whose inputs lived on a retired box); menu items that run a tool from a frozen
  tree. Each item is written as a proposed backlog row: `path:line`, what the document says, what is true (with the
  evidence), and a one-line correction. New items first, then a one-line count of those carried from last week.
- **Code hygiene, as backlog items** (old §5): code that costs attention or hides defects. Report it; do not change it.
  Look for **dead code** (functions, flags and menu handlers with no caller; grep the name across the tree;
  `menu_extract.py --check` for the menu); **retired-strategy remnants** (code paths, config keys, env switches, tests
  and menu items that still name a strategy the operator retired; search for the terms in the block below; a
  remnant is reported as **code to remove**, the strategy is never described or scored; the ORB *engine* stays:
  Runaway reads it); **stale tests and fixtures** (hard-coded dates that act as "today" or as an expiry, `EXP =
  "2026-…"`, `--date 2026-…`, and fixtures that will go red within 14 days of the brief; name each file and line);
  **duplicated constants** (the bucket name, epoch dates, box lists, session times or caps defined in more than one
  place across dtp and OTV5); **frozen-repo dependencies** (any dtp or OTV5 path that reads `~/options-trader-v4` or
  `DTP_OTV4_DIR`; known ones: `menu_functions.sh _r_tool`, `tools/brief_sigint.py`, `tools/genesis_find.py`; check
  each is still there); **interpreter-sensitive scripts** (`#!/usr/bin/env python3` that import numpy, pytz or
  tastytrade). Each item as a proposed backlog row: `path:line`, why it matters (the failure it can cause), the
  proposed change, and its size (lines, gates). At most ten new items; carry the rest as a count.

<!-- RETIRED-SEARCH: the hygiene search terms only. Never print these as strategies in a brief. -->
    ORBStrategy  ORBS  orb_budget  ORB_BUDGET      PARC  OT_PARC  parc_       VOLT  OT_VOLT
    SweepCreditSpread  SWPT  OT_SWEEP_CS           OpeningRangeCreditSpread  ORCS  OT_ORCS
    ATPButterfly  ATPB  OT_ATP_BUTTERFLY           minimum-stop veto  min_stop  OTV4 vs TEST  proxy
    GEXPinButterfly  GEXB  TrendCreditSpread  TCST  TCS
<!-- /RETIRED-SEARCH -->

---

## 4. RECOMMENDATIONS

**Purpose:** what the operator should decide, ranked, and what next week holds. The section ends with the Sunday
work list.

**4.1 Ranked recommendations.** Each, ranked by dollars at stake, then by risk:

    R<n> · <what, in one line>
      Why:       the evidence, with n and $, citing the part (1A..3C)
      Class:     DEFECT (one reproducing case) · CALIBRATION (statistical; deep tape, a sealed holdout first) · DIAGNOSTIC · DOCS · HYGIENE
      Touches:   control only · OTV5 research/tools · OTV5 trading code (the freeze: only if broken) · a box
      Decision:  the yes/no question for the operator, and what happens on yes

No history recap: give the proposal, why, and what follows a yes. A trading change during the freeze is only
recommended if the code is broken (not to spec or malfunctioning). **"Nothing to recommend"** is a valid answer. At
the foot, a short table **Still open from last week**: one line per open recommendation, id and status (still open
/ superseded / done by r…). A recommendation that is done is listed once, then dropped.

**4.2 The QQQ cash size table (every Saturday until 2026-12-07; the last run is 12-05).** The operator, 2026-11-11:
"On the weekend prior, let's do a table of $250/$500 & $500/$750 with a cap at the ramp max", and "just brief it
every weekend until the date arrives". **On or after 2026-12-07 the brief skips this item and does not mention it.**
Source: every QQQ trade in `~/reviews/trades/*.csv` from 2026-10-26 through the Friday (OTV4TEST rows out), with
Breakout's stop premium from the warehouse trade row (`load_trades`, `stop_premium`). Two schemes, the per-trade cap
equal to the ramp max (`OT_BREAKOUT_BUDGET_USD`; `OT_ORB_BUDGET_USD` before OTV5 r125) in both:

| Scheme | Base (`OT_RISK_USD`) | Ramp max = cap (`OT_BREAKOUT_BUDGET_USD`) |
|---|---|---|
| A | $250 | $500 |
| B | $500 | $750 |

The sizing rule is OTV5 `risk/risk_manager.py` `size_for`, as the code runs it today. The grade multiplier is 1.0,
and `OT_SIZE_ON_RISK` is off by default, so there is no deploy cap and no risk-to-stop denominator.

| Setup | Rule | Contracts | Refused when |
|---|---|---|---|
| Hunt, Runaway, PARK | `_size_budget` | floor(base / (entry × 100)) | under 1 (`insufficient_capital`) |
| Breakout | `_size_geometry` (the ramp) | min(by_risk, by_budget) | by_budget under 1 (the ramp-max refusal) |

For Breakout, by_budget = floor(ramp max / (entry × 100)), and by_risk = **max(1,** floor(base / ((entry − stop
premium) × 100))**)** when 0 < stop premium < entry; without a usable stop premium, by_risk is the geometry count
max(1, floor(width / distance)), with width = `orb_range_high` − `orb_range_low` and distance = |`underlying_entry` −
`underlying_stop`|. A stop wider than the range (distance > width) sizes min(by_risk, by_budget) with a usable stop
premium, and 1 contract without one. Every input is on the warehouse trade row (`load_trades`). A refused trade is
never rounded up to one contract. Each kept trade's P&L and fee scale by new contracts / actual
contracts. Report, per scheme and per setup (Hunt, Runaway, Breakout, PARK): entries traded vs refused; contracts
min / median / max; the re-sized P&L with fees beside it, never in it; EV per trade with a day-bootstrap 95%
interval; the worst day; the largest single-trade loss. Lead with each scheme's window EV and its interval. A
Breakout trade with neither a usable stop premium nor width and distance goes to NOT MEASURED by trade_id.
**Report only:** the operator sets the size, the ramp and the cap themselves when they activate cash. It is not a
study (never in `WEEKEND_STUDIES.md`), and it is a reference table in section 4, never an R-item.

**4.3 The 12-04 cash-test readiness checklist (every Saturday brief dated on or before 2026-12-04).** The cash test is
QQQ only, the normal budget, one RTH session, with a careful log review after. One line per item, each marked
**DONE** (with the evidence), **OPEN**, or **WAITING ON THE OPERATOR**:
1. **`OT_DAILY_LOSS_LIMIT` confirmed** for the QQQ box: the value the bot runs with, read from the QQQ box's start-up
   banner in bot.log (`catastrophic_loss_cap=`; `grep -m1 -F` on the box, the line only), beside OTV5 `config.py`'s
   default (one trade's risk). Never from `.env` or a unit's Environment. The operator confirms the value.
2. **The tastytrade auto-exercise cut-off**: what the broker does with an in-the-money long option held into the
   close, set against the fleet's own end of day (entries stop 15:40, the 15:50 ladder, the 15:55 cross); say
   whether any position was still open after 15:50 this week. The operator confirms the broker's rule.
3. **The Hunt decision** and 4. **the OGAP decision**: the operator's, from 2A's numbers. WAITING ON THE OPERATOR until
   they decide.
5. **The test-day log checklist**: the reads the careful review after the test day makes (every entry's ladder walk and
   fill, every exit's ladder, refusals and caps, feed episodes, the loss-limit state, order rejects, the 15:50/15:55
   close, the broker's fills against the bot's record). Written once in full, then carried with its status.
Anything else the week showed that would stop the test goes here as an OPEN item with its evidence.

**4.4 Next week's calendar.** The sessions from `market_calendar` (holidays and half days: 2026-11-26 is closed,
Thanksgiving; 2026-11-27 is a half day, the close at 13:00 ET); the Fed and CPI: high-impact USD events from the
bot's own economic-calendar source (OTV5 `config.FOREX_FACTORY_URL`); it carries the current week only, so on
Saturday it shows the week just ended: read its `ff_calendar_nextweek.json` sibling when it answers, else NOT
MEASURED with that reason (the Monday wake's Fed-day read is the live check); earnings on our symbols: each box
symbol's `earnings.expected-report-date` (and time of day) from the Friday's S3 `raw/market_metrics/dt=<Fri>/sym=<SYM>/`
(TastyTrade), listed when it falls in the next week. Index symbols have none.

**4.5 The Sunday work list (the brief ENDS with it).** Every item for a yes, from 4.1, 3B, 3C and 2B, one line
each: id, what lands, its gate, its size, and **DELICATE** (the live order path, entries, exits, sizing, a box
service, anything that trades) or **ROUTINE** (control-only tools, docs, studies, tests). DELICATE items first. It is
the last thing in the brief; only NOT MEASURED follows it.

---

## WHAT THIS SPEC RETIRED, AND WHY

| old item | disposition |
|---|---|
| the minimum-stop veto (old §5, 2026-10-31) | retired: the strategy it measured is retired, so the series cannot grow |
| the two-engine comparison (old §6, 2026-10-31) | retired: one engine on the fleet; the two populations closed 10-23 |
| the tape-proxy correlation (old §7, 2026-10-31) | retired: its premise (a test box standing in for an index) is gone |
| R-suite pooling across engines (D5) | retired: one lineage |
| PARC in any table | retired: *"It was an idea. It failed. It's done."* |
| VERD.1 | closed, superseded: its verdict file and scorer were on the retired QQQ-TEST box, never in S3; OTV5's box agents are off at boot |
| PIN.1 | merged into PIN.3 (OTV5's own pin gate) |
| CUT.1, GIVE.2 | re-scoped to the OTV5 fleet; their QQQ-TEST halves closed |
| DAY.1 | one final score, then closed by its result |
| v2.15 §1.11 RUNAWAY O08 WOULD-BE (2026-11-21) | retired: the operator agreed to drop it; its decision note stands in the v2.15 changelog entry |
| the v2.x section numbering (2026-11-21) | retired: v3.0's four sections and ten parts; the map is in the v3.0 changelog entry |
| the 10-26..11-27 benchmark framing (from 2026-12-05) | retires after its final score in the 11-28 brief; the epoch metrics (1C) replace it |

The old runbook's lessons that still apply are kept above: diff by check ID, per-checker scratch, the box path has
no suffix, a fan-out must fail loudly, a WAL needs ranking in place, S3 is read through the one sanctioned reader (§36a), never pipe a long job
through `tail` in an `&&` chain, and a parity gap may be a counter problem.
