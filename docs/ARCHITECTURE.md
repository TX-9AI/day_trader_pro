# day_trader_pro/docs/ARCHITECTURE.md — v1.0 — 2026-07-29

**Day_Trader_Pro is the over-arching project.** `market_brief` and
`options_trader` are modules of it, not peers of it. This document records the
target layout, the contract that keeps each module independently installable,
and — because it is the reason this file exists — what the 2026-07-29 outage
taught about the seams between them.

---

## 1. Current layout (control server, 2026-07-29)

Flat. Every project is a sibling in `$HOME`, and each is its own git repo:

    ~/day_trader_pro/      control plane   (github.com/TX-9AI/day_trader_pro)
    ~/market-brief/        reporter        (github.com/TX-9AI/market_brief_v1)
    ~/options-trader-v3/   bot checkout    (github.com/TX-9AI/options_trader_v3)
    ~/shadow/  ~/deploy/  ~/backtest_data/  ~/snapshots/  ~/pre_v2_backup/

Note the bot boxes use `~/options-trader` (no `-v3` suffix); only the control
checkout carries it. That asymmetry has already cost real time and is worth
retiring when the layout moves.

## 2. Target layout

`day_trader_pro` becomes the parent, with the modules nested as siblings
underneath it:

    ~/day_trader_pro/
        <control plane: harvest, orchestrator, conductor, selector, fleet…>
        market_brief/          module (own repo, own venv, own .env)
        options_trader/        module (own repo, own venv, own .env)

Each module stays a **standalone installation**: it can be cloned on its own
box, installed by its own `install.sh`, and run with no knowledge that a control
plane exists. The control plane can be coupled or de-coupled without editing
either module's code.

## 3. The modularity contract

What "modular" has to mean concretely, or the nesting is cosmetic:

1. **A module never hard-codes a path outside its own tree.** Anything it needs
   from outside arrives by environment variable or CLI argument, with a
   documented default. `market_brief`'s `DTP_REPORT_JSON` is the model — and its
   failure mode is section 5.
2. **A module never imports from a sibling.** All cross-module traffic is files
   or SSH, never Python imports. This already holds and must keep holding.
3. **The control plane may read a module's outputs; a module never reads the
   control plane's state.** One-directional, so a module runs fine alone.
4. **Every module owns its own git remote, venv and secrets.** Nesting the
   directory does not nest the repo — no submodules, no vendoring. A module is
   cloned into place.
5. **De-coupling is deleting a directory.** If removing `market_brief/` breaks
   the control plane rather than degrading it, the seam is wrong. The morning
   wake should fall back to `ALWAYS_ON` and say so, not fail.

## 4. The coupling seams (all of them, as of 2026-07-29)

Every point where a module and the control plane actually touch:

| Seam | Direction | Mechanism |
|---|---|---|
| morning report | brief → control | `report.json`, path from `$DTP_REPORT_JSON` |
| sentiment nudge | control → bot boxes | `~/brief_flags.json` pushed over SSH |
| code deploy | control → bot boxes | `git pull` on each box, driven by control |
| tape + trades | bot boxes → control | `scp` pull into `ohlc/ trades/ signal_journal/ chain_snapshots/` |
| fleet lifecycle | control → boxes | EC2 start/stop + `systemctl` over SSH |

Five seams. Four are SSH-mediated and fail loudly when they break. The one that
is a **file handoff between two independently-scheduled processes** is the one
that failed silently for 23 days.

## 5. What 2026-07-29 taught about the seams

`market_brief` wrote its report every morning. `day_trader_pro` read a report
every morning. They were **different files**, and nothing noticed for 23 days.
`$DTP_REPORT_JSON` was never set, so `emit.py` used its `os.getcwd()` fallback;
the control plane meanwhile read `config.DATA_DIR/report.json`, frozen at
2026-07-06. The same 13 boxes woke every day, and the brief's signed sentiment
reached the bot as a hardcoded `0.3` constant — a fully wired pipeline
delivering a default.

Three rules follow, and they generalise to every future seam:

- **A file seam must carry its own freshness stamp, and the consumer must check
  it.** `orchestrator.py` v0.3.0 now audits the report's `date` and its
  `move_ranked` shape, alerts on either, and stamps provenance onto the result.
  A seam that can be stale must be *checkable* as stale.
- **A default must point at the real consumer, never at the current working
  directory.** `os.getcwd()` is how a producer silently writes into the void.
- **Configuration in a gitignored file is not a fix.** `install.sh` overwrites
  `.env` wholesale, so a hand-edit dies at the next reinstall. Anything
  load-bearing lives in committed code or in the installer's own heredoc.

## 6. Migration notes (not scheduled)

Nesting is a move plus a re-point, and the risky part is neither:

- Both modules' `install.sh` write absolute systemd units; those get regenerated,
  not edited.
- `day_trader_pro/config.py` derives `BASE_DIR` from `__file__`, so the control
  plane is move-safe. The modules' installers are not audited for this yet.
- `push.sh` in `options_trader` locates its target by scanning `$HOME` for the
  first directory containing `main.py` + `config.py` — nesting two modules under
  one parent makes that scan ambiguous. **Fix `push.sh` before migrating**
  (tracked as backlog item V).
- Bot boxes are unaffected: they run a single module in `~/options-trader` and
  never see this layout.

Do the migration on a day with no deploy pending and the fleet stopped, and
verify with `check_versions.sh` parity plus one full EOD conductor dry-run.
