# day_trader_pro — v0.1.0

Control-server orchestration layer that marries `market_brief_v1` (the report)
and `options_trader_v2` (the bots) into an autonomous daily suite.

The reporter box (`1-REPORTER`) is the **always-on control server**. Every
trading morning it: reads the finished brief, asks Claude which discretionary
symbols to wake, resolves those symbols to EC2 instances **by tag Name**, and
starts them. At day's end a control-server sweep **stops** (never terminates)
whatever is still running.

`SPX` and `QQQ` always trade. The model may add up to **4** more.

## Files
| File | Role |
|---|---|
| `config.py` | universe, region, caps, paths, mock switches |
| `ec2ops.py` | all AWS EC2 calls + mock state machine |
| `instance_registry.py` | tag→ID discovery, cache, reconcile, swap/pin |
| `selector.py` | Anthropic selection call, validation, fallback |
| `notify.py` | control-server Telegram alerts |
| `market_calendar.py` | trading-day gate |
| `orchestrator.py` | morning wake flow |
| `shutdown_manager.py` | EOD stop sweep |
| `devtools.sh` | interactive menu (incl. full mock spool-up) |

## Try it with zero credentials
```bash
./devtools.sh        # pick 1 for the full mock spool-up
# or:
DTP_MOCK=1 python3 orchestrator.py --mock --no-gate
```

## Go-live checklist
1. Put your full 30-symbol universe in `config.py` (`UNIVERSE`).
2. Attach an IAM **instance role** to the reporter with
   `ec2:DescribeInstances`, `ec2:StartInstances`, `ec2:StopInstances`
   (ideally scoped by a tag condition). No access keys on disk.
3. Export secrets on the reporter:
   ```bash
   export ANTHROPIC_API_KEY=...
   export DTP_TELEGRAM_TOKEN=...
   export DTP_TELEGRAM_CHAT_ID=6075312586
   ```
4. Point `DTP_REPORT_JSON` at where `market_brief_v1 --emit-json` writes.
5. `python3 instance_registry.py reconcile` to build the map from your tags.
6. Dry runs: `orchestrator.py --dry-run --no-gate`,
   `shutdown_manager.py --dry-run`.
7. Add two systemd timers on the reporter: orchestrator pre-market,
   shutdown sweep ~16:00 ET.

## Repo coupling (kept minimal / optional)
- `market_brief_v1`: add `--emit-json` → writes `report.json`. That's all this
  layer needs; the brief still runs standalone.
- `options_trader_v2`: add a 15:50 EOD task (orphan check + per-symbol P&L
  Telegram) on the box's own timer. The box owns its P&L; this layer only
  issues the stop. Bots still run standalone.
