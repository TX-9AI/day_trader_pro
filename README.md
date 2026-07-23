# day_trader_pro

Autonomous control layer that unifies **market_brief_v1** (the morning research
brief) and the **options_trader_v3** trading fleet into one supervised daily
system. It runs on the always-on **reporter box (`1-REPORTER`)**, which doubles
as the control server.

The repos stay independent. day_trader_pro ties them together at runtime through
thin seams: a `report.json` file (produced by the brief, read by the
orchestrator), EC2 instance tags (`Project=day_trader`), and the EOD
harvest/replay chain that pulls each box's tape and trade DB back to control.
Nothing is merged. The control checkout of the trading engine
(`~/options-trader-v3`) is an **inert library** — no credentials, no live path —
pulled fresh so the offline replay scores tape with the same engines the fleet
runs (**the parity invariant**).

---

## What it does, once a day

```
 09:15 ET  market_brief runs -> Telegram report + writes report.json
 09:17 ET  orchestrator (dtp-morning.timer): ALWAYS_ON (SPX+QQQ) + EXACTLY
           MAX_DISCRETIONARY (13) names — model concurs/swaps on the brief's
           move_ranked, deterministic backfill guarantees the count -> start
           EXACTLY 15 boxes -> push each box its signed move-strength
           (~/brief_flags.json, the setup-score nudge) -> Telegram wake msg
           (rank + score per pick, plus the "just missed" list)
 staged    wake_and_bake: staged small-group wake of the NON-trading boxes to
           pull candles (wake -> git bake -> restart -> STOP), so every symbol's
           feed store stays warm without running 29 bots
 all day   bots trade their own symbol, standalone; entry/exit alerts direct
 15:45 ET  bots flatten (0DTE hard close: 15:40 mark-limit window -> 15:45
           MARKET) — nothing carries overnight
 15:50 ET  each bot writes ~/eod/pnl_today.json (final P&L + orphan check)
 15:55 ET  eod_report: SSH-pull every running box's P&L -> aggregate -> stop
           them all -> ONE unified Telegram (per-symbol P&L + net + stopped)
 after     eod_conductor (v1.3.0, timer chain): backfill -> harvest OHLC to
           ohlc/<date>/ + trades/<date>/<SYM>_<date>_trades.db -> consolidate
           fleet_trades -> REGIME REPLAY (validate_regime.sh -> Layer-1 diary)
           -> excursion report (phase 7, Telegrams the headline). Always-run,
           warn-never-stop.
 manual    label_day.sh — the Tier-B labeling habit (see below)
```

Boxes are **stopped, never terminated** — config, EBS, and paper/live settings
persist for the next wake.

**Status 2026-07-18 →:** this full unattended cycle runs **flawlessly** —
morning startup, report, staged candle wake, trading day, wind-down, EOD
aggregation. Protect it (see "Protect the EOD chain" below).

---

## Design rules (why it's built this way)

- **State-driven, not memory-driven.** The EOD sweep stops whatever is *running*
  under the tag right now — including boxes hand-started mid-day. No manifest,
  no ownership tracking.
- **Report from the box, stop from control.** P&L lives in each bot's DB, so the
  bot writes it. Control has the fleet view + authority, so it stops. A crashed
  box that never wrote still gets stopped (shown as "P&L missing").
- **Bots are always standalone.** Control only ever *starts a box*, *reads a
  file*, and *pushes a flags file*. It never injects what to trade. Any bot runs
  by hand, anytime — "deco mode."
- **Untrusted model output.** The selector treats the model's picks like a
  broker fill: strict schema, EXACTLY-N contract with deterministic backfill
  from `move_ranked`, forced SPX+QQQ floor, fallback to floor-only on any error.
  Worst case is a 2-box day, never an over-exposed one.
- **Keyless where it counts.** AWS actions use an IAM instance role. SSH pulls
  use one locked-down `.pem` on control.
- **Parity invariant.** Fleet boxes (`~/options-trader`) and the control
  checkout (`~/options-trader-v3`) must run the same engine commit — pull +
  `check_versions.sh` on control right after any fleet deploy.
- **Protect the EOD chain.** It is finally flawless. The pending offline-replay
  **bookmark** (rolling HTF bar window, options_trader_v3 defect S) must be
  built and proven inert on the tester before it is grafted onto
  `validate_regime.sh`.

---

## Selection logic (current: exactly-15)

`ALWAYS_ON = [SPX, QQQ]` always trades. `MAX_DISCRETIONARY = 13` — the model
concurs on or swaps within the brief's `move_ranked`; deterministic backfill
guarantees exactly 13 discretionary names even on partial/invalid model output.
Total running fleet: **exactly 15** (or 2, on selection fallback). Each waked
box receives its signed move-strength via `~/brief_flags.json` for the bot's
setup-score nudge.

History, because it explains the code's changelog: v0.2.0 (07-10) **retired**
model selection (a week of running all 29 showed the strongest-R trades were
not the model's picks); v0.3.0 (07-15) **restored** report-driven selection at a
fixed fleet size — the difference is the model no longer *originates* picks, it
concurs/swaps on the reporter's own ranking, and the count is deterministic.

---

## The three notification types

1. **Morning wake** (control): which servers are starting, floor vs pick with
   reporter rank + signal score, near-miss list, instance IDs + confirmed
   running state.
2. **Per-bot real-time** (each bot, direct & unchanged): startup, shutdown,
   trade entered, trade exited.
3. **EOD unified** (control): one message with every symbol's P&L, the net,
   orphan/missing flags, "N/N stopped" — plus the conductor's excursion
   headline.

---

## Files

| File | Role |
|------|------|
| `config.py` | universe (29), ALWAYS_ON, MAX_DISCRETIONARY=13, region, caps, SSH settings, paths, mock switches |
| `control_state.py` | master switch (ENABLED / DISABLED) |
| `instance_registry.py` | tag → instance-ID discovery, cache, reconcile, swap/pin |
| `ec2ops.py` | all EC2 calls (describe/start/stop) + private IPs + mock |
| `selector.py` | v0.2.0 — EXACTLY-N concur/swap selection over `move_ranked`, validation, floor + fallback |
| `orchestrator.py` | v0.2.1 — morning wake flow (rank/score transparency in the wake message) |
| `wake_and_bake.py` | v1.2 — staged small-group wake→git-bake→restart→STOP of non-trading boxes (the candle-warm pass; also the full-fleet deploy vehicle, devtools option 23) |
| `eod_report.py` | EOD: SSH-pull all P&L, stop all, one unified message |
| `eod_conductor.py` | v1.3.0 — EOD chain conductor: backfill → harvest → consolidate → regime replay → excursion (phase 7). Always-run, warn-never-stop |
| `eod_backfill.py` | re-pulls any box's missing EOD artifacts |
| `harvest.py` | v0.4.0 — canonical harvest to `data/harvest/<date>/`: OHLC tape → `ohlc/<date>/`, per-symbol trade DBs → `trades/<date>/` |
| `consolidate_trades.py` | v1.1.0 — fleet_trades JSON/CSV rollup from the harvested DBs |
| `excursion_report.py` | v2.2 — MFE/MAE excursion report from the per-symbol DB snapshots; `--since` cumulative; live variant via `DTP_EXCURSION_LIVE=1` |
| `trade_report.py` / `standings.py` | trade and standings views over the consolidated data |
| `shutdown_manager.py` | manual/backstop stop sweep (no P&L) |
| `ssh_util.py` | shared SSH helper |
| `fleet.py` | v0.6.0 — fleet SSH fan-out: list / ping / run (uses `pull_today_ohlc.sh` on-box for long pulls) |
| `notify.py` | control-server Telegram |
| `market_calendar.py` | trading-day gate |
| `label_day.sh` | v1.0 — **EOD Tier-B session labeler**: tags each day's trend/sweep/pin/breakout symbols → `reports/session_labels.jsonl`; `--gaps` prints the Layer-1 Tier-B shopping list |
| `nightly_regime.sh` | timer wrapper for the nightly regime replay |
| `sync_control_replay.py` | keeps the control replay checkout in sync (parity invariant) |
| `rotate_env_remote.sh` | v1.3 — fleet-wide .env/credential rotation (adds missing vars, audit sudo-grep) |
| `rotate_tokens.py` / `verify_creds_remote.py` | token rotation (comma/space subsets) + remote credential verification |
| `migrate_data_layout.sh` | one-time migration to the canonical `data/harvest/<date>/` layout |
| `install_morning_timer.sh` / `install_eod_timer.sh` / `install_eod_conductor.sh` / `install_regime_timer.sh` | systemd timer installers for the daily chain |
| `devtools.sh` | **v1.19** — the operator menu: mock spool-up, EOD, fleet ops, option 23 FULL wake→bake→restart→STOP deploy, **27 EMERGENCY STOP**, 39 manual consolidation re-run, 45 excursion report, 49 OHLC 21-day fetch, 52 A2 co-occurrence audit, 54 Verify. (Menu items run as child processes — they cannot `cd` your shell; use `alias otv3='cd ~/options-trader-v3 && source venv/bin/activate'`.) |
| `tests/` | `backtest_harness.py` (21-day 1m tape harness), `ohlc_fetch.py` |

Also control-side but living in the **options_trader_v3 repo**:
`validate_regime.sh` (the Layer-1 regime replay the conductor calls — inert
code library + read-only replay over the harvest tape; tape-only, never reads
trades).

On the **bot boxes** (options_trader_v3): `eod_summary.py` (writes the P&L
file) and `notifications/alert_manager.py`. In **market_brief**:
`report/emit.py` (writes `report.json`).

---

## Command cheat-sheet (run from `~/day_trader_pro`)

```
# fleet
python fleet.py list                  # symbol -> private IP -> state
python fleet.py ping                  # SSH echo-test running boxes
python fleet.py run "uptime"          # run a command on all running boxes

# registry
python instance_registry.py reconcile # rebuild map from live tags
python instance_registry.py show
python instance_registry.py swap      # pin a symbol to a specific instance ID

# master switch
python control_state.py status
python control_state.py enable | disable

# daily flow (manual)
python orchestrator.py --no-gate      # wake the exactly-15 fleet now
python eod_report.py --dry-run        # pull + aggregate, stop nothing
python eod_report.py                  # pull + aggregate + stop all + one msg
python eod_conductor.py               # run the full EOD chain by hand

# safety / verify
python notify.py --test               # Telegram works?
./devtools.sh                         # menu (23 deploy, 27 EMERGENCY STOP, 54 verify)

# regime validation + Tier-B labeling (control-side, tape-only)
~/options-trader-v3/validate_regime.sh              # replay TODAY's tape -> diary
~/options-trader-v3/validate_regime.sh 2026-07-21   # a specific date
./label_day.sh                        # EOD: tag trend/sweep/pin/breakout symbols
./label_day.sh --gaps                 # Tier-B shopping list
```

Add `--mock` to orchestrator / eod_report / fleet for a fully offline dry run.

**Shell-script deploy convention:** push new `.sh` files to GitHub **from the
control instance** so the execute bit is preserved ("control-server sync"
commits are exactly this); files arriving via SFTP need `chmod +x` before
commit.

---

## Environment (control server)

Stored in `~/day_trader_pro/.env` (gitignored), loaded via `.bashrc`:

```
DTP_TELEGRAM_TOKEN=...        # control-server bot (shared with the brief bot)
DTP_TELEGRAM_CHAT_ID=...
DTP_REPORT_JSON=/home/ubuntu/day_trader_pro/data/report.json
ANTHROPIC_API_KEY=...         # enables the concur/swap selection call
DTP_EXCURSION_LIVE=1          # optional: add the live excursion report
```

SSH pull settings (defaults usually fine): `DTP_SSH_KEY=~/.ssh/tx-9.pem`,
`DTP_SSH_USER=ubuntu`, private IP, 12s connect timeout.

**Analysis offload:** heavy replay/calibration work runs on a separate 4-vCPU
EC2 analysis box with `options_trader_v3` cloned — only the OHLC tape at
`~/day_trader_pro/ohlc/` needs copying over (no day_trader_pro repo, no `.env`,
no IAM). Replays parallelize across DATES (`xargs -P4`); a single day is
single-threaded (per-bar full-stack scoring is the bottleneck).

---

## Current status (2026-07-22)

- **The daily lifecycle runs unattended and clean** (since 2026-07-18):
  morning wake (exactly-15), staged candle wake, trading day, wind-down, EOD
  chain — attention has moved to strategy/regime work.
- **Regime workstream live on control:** the conductor's nightly replay + the
  A2/ramp-calibration tooling (devtools 52) drove the `regime_confluence` v1.2
  ramp de-saturation now deployed to the fleet (2026-07-22). The frozen-baseline
  window gets one week added to its back end to preserve a clean stretch.
- **The Monday habit:** after the conductor runs, `./label_day.sh` — this is
  what fills the Layer-1 Tier-B tape gaps (options_trader_v3 `ROADMAP.md` L1.7).
- **Known limitation (defect S upstream):** the offline replay is HTF-starved
  (one day-folder at a time), so the diary under-reports TRENDING until the
  bookmark lands — build it on the tester first; do not disturb the conductor.

### Historical status (2026-07-05) — the v2-era autonomy checklist, since met

IAM role, tag discovery, private-IP resolution, SSH reach, orchestrator wake,
EOD aggregate + unified message, master switch, bot-side P&L writer, emit →
selector chain — all proven; the systemd timers now exist and the daily flow is
fully scheduled.
