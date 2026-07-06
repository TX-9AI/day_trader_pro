# day_trader_pro

Autonomous control layer that unifies **market_brief_v1** (the morning research
brief) and **options_trader_v2** (the trading bots) into one supervised daily
system. It runs on the always-on **reporter box (`1-REPORTER`)**, which doubles
as the control server.

The three repos stay independent. day_trader_pro ties them together at runtime
through two thin seams: a `report.json` file (produced by the brief, read by the
orchestrator) and EC2 instance tags (`Project=day_trader`). Nothing is merged.

---

## What it does, once a day

```
 09:15 ET  market_brief runs -> Telegram report + writes report.json
 09:17 ET  orchestrator: read report.json -> ask Claude which names to wake
           -> start SPX + QQQ (floor) + up to 4 discretionary -> Telegram wake msg
 all day   bots trade their own symbol, standalone; entry/exit alerts direct
 15:45 ET  bots flatten (0DTE hard close) — nothing carries overnight
 15:50 ET  each bot writes ~/eod/pnl_today.json (final P&L + orphan check)
 15:55 ET  control server: SSH-pull every running box's P&L -> aggregate
           -> stop them all -> ONE unified Telegram (per-symbol P&L + net + stopped)
```

Boxes are **stopped, never terminated** — config, EBS, and paper/live settings
persist for the next wake.

---

## Design rules (why it's built this way)

- **State-driven, not memory-driven.** The EOD sweep stops whatever is *running*
  under the tag right now — including boxes you hand-started mid-day for a news
  catalyst. No manifest, no ownership tracking. Whatever's up gets pulled + swept.
- **Report from the box, stop from control.** P&L lives in each bot's DB, so the
  bot writes it. The control server has the fleet view + authority, so it stops.
  A crashed box that never wrote still gets stopped (shown as "P&L missing").
- **Bots are always standalone.** The control server only ever *starts a box* and
  *reads a file*. It never injects what to trade. Run any bot by hand, anytime,
  with or without the control layer — that's "deco mode."
- **Untrusted model output.** The selector treats Claude's picks like a broker
  fill: strict schema, hard cap of 4, forced SPX+QQQ floor, deterministic
  fallback to floor-only on any error. Worst case is never over-exposed.
- **Keyless where it counts.** AWS actions use an IAM instance role (no keys on
  disk). SSH P&L pulls use one locked-down `.pem` on the control server.

---

## The three notification types

1. **Morning wake** (control server): which servers are starting, floor vs pick,
   each instance ID + confirmed running state.
2. **Per-bot real-time** (each bot, direct & unchanged): startup, shutdown, trade
   entered, trade exited. These stay per-bot on purpose — instant, no dependency.
3. **EOD unified** (control server): one message with every symbol's P&L, the net,
   orphan/missing flags, and "N/N servers stopped".

The six individual daily-P&L messages are intentionally replaced by the single
EOD rollup. `alert_manager.send_daily_summary()` remains as a per-box manual/
fallback tool (`eod_summary.py --send`).

---

## Files

| File | Role |
|------|------|
| `config.py` | universe (29), region, caps, SSH settings, paths, mock switches |
| `control_state.py` | master switch (ENABLED / DISABLED) |
| `instance_registry.py` | tag -> instance-ID discovery, cache, reconcile, swap/pin |
| `ec2ops.py` | all EC2 calls (describe/start/stop) + private IPs + mock |
| `selector.py` | Anthropic selection call, validation, floor + fallback |
| `orchestrator.py` | morning wake flow |
| `eod_report.py` | EOD: SSH-pull all P&L, stop all, one unified message |
| `shutdown_manager.py` | manual/backstop stop sweep (no P&L) |
| `ssh_util.py` | shared SSH helper (used by eod_report + fleet) |
| `fleet.py` | fleet SSH fan-out: list / ping / run |
| `notify.py` | control-server Telegram |
| `market_calendar.py` | trading-day gate |
| `check_iam.py` | verify the IAM role sees the fleet |
| `devtools.sh` | interactive menu (mock spool-up, EOD, fleet, switch) |

On the **bot boxes** (options_trader_v2): `eod_summary.py` (writes the P&L file)
and `notifications/alert_manager.py` (v1.3, adds the summary formatter).
In **market_brief**: `report/emit.py` (writes `report.json`).

---

## Command cheat-sheet (run from `~/day_trader_pro`)

```
# fleet
python fleet.py list                 # symbol -> private IP -> state
python fleet.py ping                  # SSH echo-test running boxes
python fleet.py run "uptime"          # run a command on all running boxes

# registry
python instance_registry.py reconcile # rebuild map from live tags
python instance_registry.py show
python instance_registry.py swap       # pin a symbol to a specific instance ID

# master switch
python control_state.py status
python control_state.py enable | disable

# daily flow (manual)
python orchestrator.py --no-gate       # wake the fleet now
python eod_report.py --dry-run          # pull + aggregate, stop nothing
python eod_report.py                     # pull + aggregate + stop all + one msg

# safety / verify
python check_iam.py                     # role can see the 29 boxes?
python notify.py --test                  # Telegram works?
```

Add `--mock` to orchestrator / eod_report / fleet for a fully offline dry run
(no AWS, no API, no Telegram). `./devtools.sh` wraps all of this in a menu.

---

## Selection logic

The floor (`SPX`, `QQQ`) always trades. The model may add up to
`MAX_DISCRETIONARY = 4` more, chosen from the brief's ranked composites. The flat
`scores` map in `report.json` is signal *magnitude*, so a strong bearish setup
ranks as high as a strong bullish one; `tickers[].score` carries the signed value
and direction for the model to reason over. Total running fleet: 2–6 boxes.

If the API errors, the key is missing, or output is malformed, selection returns
**floor-only** — never nothing, never over-exposed.

---

## Environment (control server)

Stored in `~/day_trader_pro/.env` (gitignored), loaded via `.bashrc`:

```
DTP_TELEGRAM_TOKEN=...        # control-server bot (shared with the brief bot)
DTP_TELEGRAM_CHAT_ID=6075312586
DTP_REPORT_JSON=/home/ubuntu/day_trader_pro/data/report.json
ANTHROPIC_API_KEY=...         # same key the brief uses; enables real selection
```

SSH pull settings (defaults usually fine): `DTP_SSH_KEY=~/.ssh/tx-9.pem`,
`DTP_SSH_USER=ubuntu`, private IP, 12s connect timeout.

---

## Current status (2026-07-05)

**Working & proven:** IAM role, tag discovery, private-IP resolution, SSH reach
(fleet ping 7/7), orchestrator wake, EOD aggregate + unified message, master
switch, bot-side P&L writer (tested vs a real SQLite schema), emit -> selector
chain (tested end to end).

**Remaining to full autonomy:** deploy `eod_summary.py` + `alert_manager.py` to
the bot boxes; wire `emit.py` into the brief; set `ANTHROPIC_API_KEY` +
`DTP_REPORT_JSON` in the orchestrator env; then add the systemd timers. Until the
timers exist, the daily flow is run by hand — which is the intended way to watch
the first live day.
