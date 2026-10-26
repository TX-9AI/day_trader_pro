# day_trader_pro/fleet.py — v0.16.1
# v0.16.1 (2026-10-25) — (OPS.16) — A FAILED `update --wake` FAILS: NAMED, AND EXIT 1. `_wake()` caught its own error,
#   printed a warning and returned; the run then deployed to an EMPTY list and printed `Done. 0/0 deployed cleanly`
#   with exit 0 - an explicitly requested wake that did not happen read as success. cmd_update now names every box
#   that --wake was asked to bring up and that is not running and SSH-reachable afterwards (`🚨 WAKE FAILED: ...`),
#   deploys to the ones that are, and returns 1. `_wake()` returns whether the start was issued. (The region half of
#   OPS.16 was already closed by r424: `_wake` routes through ec2ops.start(), which reads config.REGION.)
# v0.16.0 (2026-10-25) — r507 / OPS.72 — `repoint --sha` (MENU 43) IS THE FLEET REPOINT TO OTV5: THE MANAGED REPOINT, THEN
#   THE FULL INSTALL ON EVERY BOX. The operator, 2026-10-25: "Option 43 ... We've done it once before from otv3 to otv4";
#   "If 43 can't do it, we should fix it. This is the use-case for it". A pinned repoint whose pinned tree's
#   bootstrap.example.sh carries OT_INSTALL_MODE (OTV5 r17 on) now runs PHASE 3 after phase 2: reinstall's own box
#   script (_reinstall_cmd: drain, the box's own credentials into the controller-mode bootstrap, run detached, judged
#   by INSTALL OK <pin>) on every box that repointed cleanly, INSTALL_WORKERS at a time (ssh_util.ssh_map), each box's
#   result printed as it lands; a box that fails is named and the others go on. --no-install keeps the git-only
#   managed repoint; a pin whose tree predates the mode does the git-only repoint and SAYS so; a pin whose template
#   cannot be read (no local checkout of the repo holding it) is REFUSED unless --no-install. `reinstall` is now this
#   with one box. Gate: tests/check_repoint_install.py.
# v0.15.0 (2026-10-25) — r506 / OPS.71 — `flash` INSTALLS OTV5 ON A BLANK, TAGGED INSTANCE FROM CONTROL. The operator,
#   2026-10-25, after the proof of concept: control kickstarting a blank box is preferred over a hand-edited bootstrap;
#   "Should we add 'Flash a new instance' to devtools under the repoint header?"; "Great, send it". ONE instance per run:
#   `flash <url> --sha <pin> --only NAME --seed SYM [--symbol SYM] [--wake] [--yes]`.
#     1. NAME is the new instance's Name tag (Project=day_trader); it must be running (--wake starts it) and BLANK: a
#        box that already has ~/options-trader is refused (rc 20) - flash never overwrites an install.
#     2. The pin is resolved to its full SHA (it must be a commit the local checkout of that repo holds).
#     3. CREDENTIALS: the five (TT_CLIENT_SECRET, TT_REFRESH_TOKEN, TT_ACCOUNT_NUMBER, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
#        stream from the SEED box's own optionsbot unit through an ssh pipe straight into ~/.flash_creds (umask 077)
#        on the new box: control's Python never reads them, nothing is printed, nothing lands on control's disk; only a
#        line count comes back. Every fleet box shares one login, so any running box seeds.
#     4. On the new box: the pinned bootstrap.example.sh (raw GitHub at the full SHA) is filled with those credentials,
#        OT_INSTRUMENT (--symbol, default NAME), OT_INSTALL_MODE=controller, Claude installed NOT raised at boot,
#        pull-only settings; the credentials file is shredded at once; the install runs exactly as reinstall's does
#        (detached in tmux, judged by "INSTALL OK <pin>", bootstrap shredded after it exits).
#   The operator then runs configure.sh and Done. Gate: tests/check_fleet_flash.py.
# v0.14.0 (2026-10-25) — r505 / OPS.70 — `reinstall` RUNS THE INSTALLER IN ITS CONTROLLER MODE (OTV5 r17, BOOT.14) AND
#   JUDGES IT BY ITS RESULT LINE. r504's first run (NVDA) completed the install and exited 2: setup_ec2 reattached
#   control's tmux terminal, its closing login shell waited for input (closed by hand), and it shredded bootstrap.sh
#   while bash was still reading it. The operator: "Yes, that way each one is clean and intentional". The bootstrap now
#   carries OT_INSTALL_MODE=controller (a tree whose template has no such line predates the mode and is REFUSED, rc 8),
#   so setup_ec2 attaches no terminal, prints no account number, leaves the shred to control and ends with exactly
#   "INSTALL OK <sha>"; the box script requires that line naming the pin, and the install's exit 0, and shreds the
#   bootstrap itself once the install has exited. The log is written line by line (sed -u). Gate:
#   tests/check_fleet_reinstall.py v1.1.
# v0.13.0 (2026-10-25) — r504 / OPS.69 — `reinstall --sha` IS A REPOINT PLUS THE FULL BOOTSTRAP INSTALL, IN PLACE.
#   The operator, 2026-10-25: "Shouldn't the repoint consist of a full bootstrap install and then I just go in to make
#   the env changes, clear cache & restart services?"; "That's how it was done in the past"; "Yes, before we do NVDA".
#   NVDA (a mainline-built box) repointed to OTV5 had none of what an OTV5 install adds (boot sweep, open scan, Claude,
#   the candle logger) and its units were the mainline template's. ONE box per run (--only SYM):
#     1. the managed repoint (cmd_repoint --sha: refuses open trades, stops the bot, the feed and the timer writers,
#        resets to the pin, deps, import check, never starts anything);
#     2. ON THE BOX: refuses a running bot/feed or an open trade again; DRAINS the box's rows under its own label if its
#        push is installed (a drain that is not OK stops here: the install would switch the push to standalone);
#     3. ON THE BOX: builds ~/bootstrap.sh (umask 077) from the tree's own bootstrap.example.sh with OT_GIT_REF = the
#        full pinned SHA and, from the box's OWN optionsbot unit, OT_INSTRUMENT and the five credentials
#        (TT_CLIENT_SECRET, TT_REFRESH_TOKEN, TT_ACCOUNT_NUMBER, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID). Nothing secret
#        leaves the box, is printed, or passes through control; a missing TastyTrade credential refuses (rc 17);
#     4. runs it unattended (install.sh -> setup_ec2.sh: venv from the lock, units from OTV5's template installed
#        DISABLED and STOPPED, the suite, Claude with the observe-only settings NOT raised at boot, push standalone,
#        ~/.optbot); the bootstrap is shredded on exit, the log keeps the account number redacted;
#     5. reports HEAD, the units' state and the log's last lines. Every store (trades.db, data/*.db) is kept: setup_ec2
#        copies the tree over without deleting and never copies trades.db or bot.log.
#   The operator then runs configure.sh (symbol, risk, switches, item 14 managed) and Done. Gate:
#   tests/check_fleet_reinstall.py.
# v0.12.0 (2026-10-14) — r489 / OPS.67 — `repoint --sha` IS THE MANAGED REPOINT. Operator 10-13:
#   the fleet moves to OTV4TEST on Saturday, keeping its symbols, "with a script that addresses the
#   services, the stores, the git, and the env defaults". The two trees share their units byte for
#   byte, their stores adopt in place, TEST stamps its lineage in code and every box's symbol is
#   already in its unit, so this is the EXISTING repoint plus four things. A pinned SHA (not
#   origin/main). Phase 1 also refuses a box with an open trade or one whose fetch lacks the SHA,
#   and the whole run aborts, as for a collision. Phase 2 stops optionsbot and candle-feed, and the
#   timer-launched writers (s3-push, candle-logger, self-close, watchdog; a running push finishes,
#   it is not killed) BEFORE the reset, starts the timers that were on again only after the import
#   check, records then disables the shadow units on a tree without shadow/ (re-enables the
#   recorded ones on a tree with it, so the same command at otv4's SHA is the rollback), installs
#   the new tree's requirements (requirements.lock on 3.14 when present), import-checks the entry
#   points (venv and system python, as each unit runs them) with OT_LOG_FILE off the live log, and NEVER starts the bot or feed: start is the bake's start step,
#   one box first. NO BACKUPS (operator: "We have s3 & the GitHub repository"): s3_push pushes
#   trades SELECT *, and both trees are on GitHub. tools/shadow_watch.py v1.2 skips a box with no
#   shadow/ in its tree instead of paging it dark. Critiqued by OTV4TEST (MSG-QQQ-1014-02).
#   Gate: tests/check_repoint_pinned.py.
# v0.11.1 (2026-10-11) — r479 / OPS.22 — zone "US/Eastern" -> "America/New_York": the legacy link tzdata 2026c moved out of the default install. Same rules; no behaviour change.
# v0.11.0 (2026-10-03) — r457 / OPS.64. THE SAFETY NET NO LONGER NEEDS THE LIST.
#   r427 scoped the close as tagged UNION UNIVERSE so a listed box that lost its
#   tag would still be stopped. That kept every RETIRED box in scope until a
#   list edit removed it (MU/PLTR reported no-answer at the 09-29 close). The
#   net is now: tagged, UNION any box that was in the last saved instance map or
#   the list AND IS RUNNING RIGHT NOW. An untagged box that is stopped or gone
#   drops out with no edit; one that is somehow still running is still closed.
#   ⚠️ The asymmetry r427 named is kept: if discovery fails, scope is the whole
#   list, never nothing. Operator: "so it truly is completely automatic".
# v0.10.0 (2026-09-25) — r427 / OPS.51. THE CLOSE IS SCOPED BY THE INSTANCE MAP,
#   NOT BY config.UNIVERSE. Operator: *"I want the conductor to do the close
#   using the instance map."*
#   🔴 r423 MOVED THE WAKE TO TAG DISCOVERY AND LEFT THIS BEHIND, which is the
#   same divergence r423 itself fixed inside eod_report — caught there, missed
#   here. A box carrying Project=day_trader but ABSENT from UNIVERSE would be
#   WOKEN at 09:15 and NEVER STOPPED: it runs, bills and trades all night, and
#   the close reports success because it never knew the box existed.
#   🔑 THE UNION, NOT A REPLACEMENT, AND THE ASYMMETRY IS THE WHOLE POINT. For a
#   SHUTDOWN path the two errors are not equal: including a box that is already
#   down costs one no-op API call, while omitting one leaves it running until
#   somebody notices. So scope is every name EITHER source knows, and a
#   discovery failure FALLS BACK TO UNIVERSE rather than to nothing — a close
#   that declines to stop anything is the failure this file exists to prevent.
#   ⚠️ IT SAYS WHICH SOURCE IT USED, every time (§0.5). "discovery unavailable,
#   falling back to UNIVERSE" is a fact the next reader needs; silence is not.
# v0.9.1 (2026-09-24) — r424 / OPS.48. `_wake()` NO LONGER CALLS boto3 ITSELF.
#   It was a SECOND way to power a box, and a second way is a way past the
#   ledger: a wake issued here left no row anywhere, so "who started this box"
#   was unanswerable for precisely the path someone reaches for when the
#   orchestrator is not what they want. It now routes through ec2ops.start().
#   The dead registry-starter probe is removed with it — see _wake's docstring
#   for why a hole that opens on a future unrelated edit is the worse kind.
# v0.9.0 (2026-09-21) — r412 / OPS.37. THE PING BOARD SHOWS THE PUBLIC IP.
#   Operator, 2026-09-21, from a phone at 15:24: *"add the public IP to
#   report number eight"* — and [[OPS.20]] already recorded why it matters:
#   **the address changes on every stop/start**, so reaching a misbehaving
#   box meant fighting the AWS console and its two-factor login at exactly
#   the moment he needed to be ON the box.
#   🔴 NEW `get_fleet_ext()` RATHER THAN A WIDER `get_fleet()`. That tuple
#   is unpacked as `(symbol, ip, state)` at TWENTY-ONE call sites across
#   EIGHT files — eod_conductor_v2, orchestrator, rotate_tokens,
#   shadow_watch, fleet_reconcile, orb_budget_fleet and seven more inside
#   this file. Widening it was one line here and a ValueError in every one
#   of them, at 09:15 or at the close. §23, and the half-sweep SH.2,
#   DEP.11 and CFG.2 each record. `get_fleet` now delegates and drops the
#   fourth field, so nothing pays a second EC2 round trip either.
#   ⚠️ AN ABSENT ADDRESS IS NAMED, NEVER BLANK (§0.5, and OPS.20 learned it
#   on this same field): `(none)` on a RUNNING box is a real finding, `-`
#   on a stopped one is expected because AWS releases it on stop.
#   ✅ VERIFIED BEFORE SHIPPING, the way r387 did: all 15 boxes asked for
#   their own IMDSv2 `public-ipv4` and MATCHED the control-side answer
#   15/15, 2026-09-21 15:29 ET.
# v0.8.0 (2026-09-21) — r406 / OPS.32. `run --timeout N` — A PER-BOX COMMAND
#   BUDGET, AND THE BANNER NOW STATES IT.
#   `_exec` passed no timeout, so every menu fan-out inherited ssh_util's
#   default — which was itself derived from the CONNECT timeout, bounding every
#   command at 22s. The manifold board took 38s and reported `rc=255 ssh
#   timeout`, which reads as a dead box rather than as a budget.
#   ⚠️ `cmd_run` IS STILL SERIAL, so the worst case is N x the budget.
#   `ssh_util.ssh_map` exists and this caller was deliberately NOT moved onto
#   it — FAN.1's own precedent, one change at a time on the path that drives
#   the fleet.
# v0.7.0 (2026-08-18) — REPOINT WILL NOT SILENTLY UN-FORK THE FLEET.
#   The fleet now holds two repos: the QQQ box runs options_trader_smc, the
#   other 28 run options_trader_v3. `repoint <url>` with no --only rewrites
#   origin on EVERY running box, so one unscoped run — or one Enter on
#   devtools' old pre-filled default — ends the SMC experiment with no error
#   and no obvious trace. Repoint now SURVEYS the remotes first; if more than
#   one distinct repo is in play it refuses unless the run is scoped (--only)
#   or the operator passes --all-repos, and it names every box that would be
#   overwritten and what it would be overwritten FROM.
#   ⚠️ `update` is untouched and was never the risk: it runs push.sh --deploy,
#   which parses the repo from the box's own remote.
# v0.6.1 (2026-07-23) — correct stale data/harvest path references (layout retired; now reports/ + ohlc/ + trades/)
"""
Fleet SSH fan-out. Pulls every monitored box's private IP from its tag and
reaches each one, one at a time, from the control server.

This is the general-purpose management plane: connectivity checks, ad-hoc
commands, deploy verification, health pings — anything you'd otherwise SSH
into the boxes by hand to do.

Targets RUNNING boxes by default (you can't SSH a stopped instance); use
--all to also list the stopped ones as skipped.

CLI:
    python fleet.py list                          # symbol -> IP -> state (no SSH)
    python fleet.py ping                          # SSH echo-test each running box
    python fleet.py ping --all                    # include stopped (shown skipped)
    python fleet.py run "uptime"                  # run a command on each running box
    python fleet.py run "systemctl is-active optionsbot"

    # standardized fleet deploy — each bot runs its own push.sh --deploy
    # (fetch + hard-reset to origin + restart + verify; the download half of
    # the same push.sh used to publish up):
    python fleet.py update                         # deploy to running boxes
    python fleet.py update --wake                  # start stopped boxes first, then deploy
    python fleet.py update --no-restart            # deploy without restarting the service
    python fleet.py update --only SPX,QQQ,NVDA     # scope to specific symbols

    # repoint the WHOLE fleet from the current repo to a NEW repo URL (e.g.
    # migrating options_trader_v2 -> options_trader_v3), collision-guarded so a
    # live untracked secret is never clobbered by the new repo's tracked files:
    python fleet.py repoint https://github.com/TX-9AI/options_trader_v3.git
    python fleet.py repoint <url> --check-only     # phase 1 only: report collisions, change nothing
    python fleet.py repoint <url> --wake           # start stopped boxes first
    python fleet.py repoint <url> --no-restart     # sync but don't restart the service
    python fleet.py repoint <url> --only SPX,QQQ   # scope to specific symbols

    # pull files back into the consolidated dated roots trades/<date>/ and
    # ohlc/<date>/ (identical
    # layout + names to harvest, so hand-pulls and harvested files interleave):
    python fleet.py pull db                         # every box's trades.db -> today's folder
    python fleet.py pull db --only IWM,SPX          # scoped
    python fleet.py pull db --day 2026-07-10        # force the target date folder
    python fleet.py pull ohlc --day 2026-07-10      # that day's OHLC csv per box
    python fleet.py pull ohlc --day 2026-07-10 --only IWM

Add --mock to preview offline.

repoint is TWO-PHASE and fails safe:
  Phase 1 (CHECK — non-mutating): on every targeted box, fetch the new repo
    into FETCH_HEAD (origin is NOT touched) and list any file the new repo
    TRACKS that currently exists here as an UNTRACKED file — i.e. anything a
    hard reset would overwrite. Live per-symbol secrets that live in the
    systemd environment are outside the repo and cannot be reached by a reset;
    the only way to lose a secret is if it sits as an untracked file whose name
    collides with something the new repo tracks. Phase 1 finds exactly that.
  Phase 2 (COMMIT — only if EVERY targeted box is clean): set origin -> new
    URL, fetch, hard-reset to origin/main, repair *.sh +x, restart + verify.
  If ANY box reports a collision in phase 1, the whole run ABORTS before phase
  2 — no box is repointed, nothing is reset, so you never end up with a
  half-migrated (split-brain) fleet. Resolve the flagged files, then re-run.

NOTE: after a successful repoint, ongoing `fleet.py update` calls the bot's
own push.sh --deploy. The v1.6 push.sh hardcodes REPO=options_trader_v2 in its
deploy path, so make sure the NEW repo ships a push.sh that targets the new
repo — the reset pulls it in automatically and keeps future deploys correct.

Changelog:
  v0.5.0 (2026-07-10)
    * `pull db|ohlc` lands IDENTICALLY to harvest: trades/<date>/ and ohlc/<date>/
      with names <SYM>_trades_<date>.db / <SYM>_OHLC_<date>.csv (was: flat
      ~/day_trader_pro/pulls/ with a dateless trades.db). A hand-pull and a
      harvested pull are now interchangeable and consolidate_trades.py picks up
      either. db pulls WAL-checkpoint the box's trades.db before copying (clean
      snapshot, same as harvest); date defaults to today, or --day to override.
  v0.4.0 (2026-07-10)
    * NEW action `pull db|ohlc`: download trades.db or a day's OHLC csv from
      one/all/some boxes. Uses ssh_util.scp_pull (v0.2.0). --day selects the date.
  v0.3.0 (2026-07-09)
    * NEW action `repoint <new_repo_url>`: migrate the fleet from the current
      repo to a new one. Two-phase, collision-guarded (see above), fail-safe
      (aborts before any mutation if any box would lose an untracked file).
    * --check-only runs phase 1 alone (read-only audit against the new repo).
    * Token for a private new repo is read from each box's systemd env
      (GITHUB_TOKEN), same source push.sh uses; falls back to the plain URL.
    * repoint does its own fetch/reset (does NOT delegate to push.sh, whose
      deploy path is pinned to options_trader_v2 and would drag boxes back).
  v0.2.1
    * Fleet update via push.sh --deploy; list / ping / run management plane.
"""

import argparse
import os
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import config
import ec2ops
import instance_registry
import ssh_util

INSTALL_DIR = "~/options-trader"
SERVICE     = "optionsbot"
# Ad-hoc pulls land in the SAME dated layout harvest uses, so a hand-pulled file
# is indistinguishable from a harvested one:
#   trades/<date>/<SYM>_<date>_trades.db  and  ohlc/<date>/<SYM>_ohlc_<date>.csv
_ET         = ZoneInfo("America/New_York")
# Remote paths for scp are relative to the box's home dir (no leading ~/).
REMOTE_HOME_REL = "options-trader"


def _today_et():
    return datetime.now(_ET).strftime("%Y-%m-%d")


def default_scope():
    """Every box the close must cover — the INSTANCE MAP, plus a safety net.

    🔑 r457 — tagged boxes, UNION any box the last saved map or config.UNIVERSE
    knows that is RUNNING right now (an untagged box that is still up must still
    be stopped). A known box that is untagged and stopped/terminated is NOT in
    scope: that is a retirement, and it needs no list edit.
    ⚠️ NEVER RETURNS EMPTY. If discovery raises or comes back with nothing, the
    result is UNIVERSE and the reason is printed (r427's asymmetry, kept).
    """
    universe = list(getattr(config, "UNIVERSE", ()) or ())
    try:
        discovered = list(instance_registry.discover_fleet() or {})
    except Exception as exc:                                   # noqa: BLE001
        print(f"  [scope] discovery unavailable ({type(exc).__name__}); "
              f"falling back to UNIVERSE ({len(universe)})")
        return sorted(universe)
    if not discovered:
        print(f"  [scope] discovery returned NOTHING; falling back to "
              f"UNIVERSE ({len(universe)})")
        return sorted(universe)
    try:
        cached = list((instance_registry.load_map() or {}).get("instances", {}))
    except Exception:                                          # noqa: BLE001
        cached = []
    known = sorted((set(cached) | set(universe)) - set(discovered))
    running_untagged = []
    if known:
        try:
            states = ec2ops.describe_by_names(known)
            states.pop("_ambiguous", None)
            running_untagged = sorted(s for s, r in states.items()
                                      if (r or {}).get("state") in ("running", "pending"))
        except Exception as exc:                               # noqa: BLE001
            # Cannot see their state: keep them all, as r427 did. Over-cover.
            print(f"  [scope] could not read state of {len(known)} known but "
                  f"untagged box(es) ({type(exc).__name__}); kept in scope")
            running_untagged = known
    extra = sorted(set(discovered) - set(universe))
    if extra:
        print(f"  [scope] tagged but NOT in UNIVERSE, included: {extra}")
    if running_untagged:
        print(f"  [scope] UNTAGGED but RUNNING, included so they are stopped: "
              f"{running_untagged}")
    return sorted(set(discovered) | set(running_untagged))


def get_fleet_ext(only=None):
    """(symbol, private_ip, state, public_ip) — the FULL record.

    🔑 r412 — A SECOND ACCESSOR RATHER THAN A WIDER TUPLE, ON PURPOSE.
    `get_fleet` is unpacked as a 3-tuple at **21 call sites across 8 files**,
    including `eod_conductor_v2` (the close), `orchestrator` (the morning
    wake), `rotate_tokens` and `shadow_watch`. Widening it would have been a
    one-line edit here and a break in every one of them — §23, and the same
    half-sweep [[SH.2]], [[DEP.11]] and [[CFG.2]] each record.
    ⚠️ ONE `discover()` CALL EITHER WAY. `get_fleet` now delegates here and
    drops the fourth field, so nothing pays a second EC2 round trip for the
    convenience.
    """
    symbols = only or default_scope()
    mapping, _ = instance_registry.discover(symbols)
    out = []
    for s in sorted(mapping):
        rec = mapping[s]
        out.append((s, rec.get("private_ip", ""), rec.get("state", "?"),
                    rec.get("public_ip", "")))
    return out


def get_fleet(only=None):
    """Return sorted list of (symbol, ip, state) for the monitored universe.

    ⚠️ ITS SHAPE IS LOAD-BEARING — see `get_fleet_ext` for why it did not grow
    a fourth field. Every existing caller keeps the contract it was written
    against.
    """
    return [(s, ip, st) for s, ip, st, _pub in get_fleet_ext(only)]


def _targets(fleet, include_all):
    """Running boxes are SSH-able; stopped are returned separately if --all."""
    running = [(s, ip, st) for s, ip, st in fleet if st == "running"]
    skipped = [(s, ip, st) for s, ip, st in fleet if st != "running"]
    return running, (skipped if include_all else [])


def cmd_list(only=None):
    fleet = get_fleet(only)
    print(f"{'SYMBOL':<8}{'PRIVATE IP':<18}{'STATE':<10}")
    for s, ip, st in fleet:
        print(f"{s:<8}{ip or '-':<18}{st:<10}")
    running = sum(1 for _, _, st in fleet if st == "running")
    print(f"\n{running}/{len(fleet)} running")


def _exec(symbol, ip, command, timeout=None):
    if config.MOCK_AWS:
        return 0, f"[mock output for {symbol}: {command}]", ""
    if not ip:
        return 255, "", "no private IP"
    return ssh_util.ssh_run(ip, command, timeout=timeout)


def _pub(state, public_ip):
    """Render a public IP, NAMING an absence instead of printing a blank.

    🔴 §0.5, AND [[OPS.20]] LEARNED IT ON THIS EXACT FIELD: *"no IP field"*
    and *"lookup failed"* must not look alike. Three different facts here:
      · a running box WITH an address            -> the address
      · a running box WITHOUT one                -> `(none)`, which is a REAL
        finding — that box cannot be reached from outside at all
      · a stopped box                            -> `-`, expected, because
        AWS RELEASES the address on stop
    A blank in all three cases would render the anomaly as tidy.
    """
    if public_ip:
        return public_ip
    return "-" if state != "running" else "(none)"


def cmd_ping(only=None, include_all=False):
    fleet_ext = get_fleet_ext(only)
    pub = {s: p for s, _ip, _st, p in fleet_ext}
    state = {s: st for s, _ip, st, _p in fleet_ext}
    fleet = [(s, ip, st) for s, ip, st, _p in fleet_ext]
    running, skipped = _targets(fleet, include_all)
    print(f"Pinging {len(running)} running box(es) one by one...\n")
    ok = 0
    # ⚠️ PUBLIC IP SITS BESIDE THE PRIVATE ONE because it is what an operator
    # actually SSHes to from outside the VPC, and it CHANGES ON EVERY
    # STOP/START ([[OPS.20]]) — a copy taken yesterday is wrong today.
    print(f"{'SYMBOL':<8}{'PRIVATE IP':<18}{'PUBLIC IP':<18}RESULT")
    for s, ip, _ in running:
        rc, _out, err = _exec(s, ip, "echo OK")
        p = _pub(state.get(s, "running"), pub.get(s, ""))
        if rc == 0:
            ok += 1
            print(f"{s:<8}{ip:<18}{p:<18}✅ reachable")
        else:
            print(f"{s:<8}{ip:<18}{p:<18}🚨 {err.strip()[:40] or 'failed'}")
    for s, ip, st in skipped:
        print(f"{s:<8}{(ip or '-'):<18}{_pub(st, pub.get(s, '')):<18}"
              f"· skipped ({st})")
    print(f"\nReachable: {ok}/{len(running)} running box(es)")
    return 0 if ok == len(running) else 1


def cmd_run(command, only=None, include_all=False, timeout=None):
    """🔑 `timeout` IS THE PER-BOX COMMAND BUDGET (r406).

    A fan-out that needs longer than `config.SSH_COMMAND_TIMEOUT` asks for it
    here rather than moving the global — the manifold board took 38s against a
    22s bound and reported `rc=255 ssh timeout`, which reads as a dead box.
    ⚠️ THIS LOOP IS STILL SERIAL, so the worst case is N x the budget. That is
    [[FAN.1]]'s territory: `ssh_util.ssh_map` exists and this caller has not
    been moved onto it, deliberately — one change at a time on the path that
    drives the fleet.
    """
    fleet = get_fleet(only)
    running, skipped = _targets(fleet, include_all)
    budget = timeout or config.SSH_COMMAND_TIMEOUT
    print(f"Running on {len(running)} box(es): `{command}`"
          f"   [per-box budget {budget}s]\n")
    fails = 0
    for s, ip, _ in running:
        rc, out, err = _exec(s, ip, command, timeout=timeout)
        head = f"── {s} ({ip}) "
        print(head + "─" * max(0, 50 - len(head)))
        if rc == 0:
            print((out.rstrip() or "(no output)"))
        else:
            fails += 1
            # 🔴 STDOUT SURVIVES A NON-ZERO EXIT. It did not until 2026-08-24,
            # and the cost was total: every box ran manifold_health, computed a
            # full board, exited 1 BECAUSE THE BOARD WAS NOT GREEN — which is
            # the tool's job — and the runner printed `🚨 rc=1` and nothing
            # else. Fifteen correct reports discarded, and the operator was
            # left reading a fleet-wide failure that had not happened.
            # ⚠️ THE STANDING RULE SAID "MAKE COMMANDS EXIT 0", and that is
            # still right for the caller. But it puts the burden on every
            # command author forever, and a dozen sqlite3 menu items are one
            # missing table away from the same silence. **A non-zero rc means
            # "it failed", never "it said nothing" — so print what it said and
            # let the operator judge.**
            if out.rstrip():
                print(out.rstrip())
            print(f"🚨 rc={rc} {err.strip()[:200]}")
    for s, ip, st in skipped:
        print(f"── {s} ({ip or '-'}) · skipped ({st})")
    print(f"\nDone. {len(running) - fails}/{len(running)} succeeded.")
    return 0 if fails == 0 else 1


# ─── Fleet update (fresh pull + restart + verify) ────────────────────────────

def _wake(stopped):
    """Start stopped instances through ec2ops — the ONE power chokepoint.

    🔴 r424 / OPS.48 — THIS FUNCTION USED TO CALL boto3 start_instances ITSELF.
    That made it a second way to power a box, and a second way is a way past
    the ledger: a wake issued here would have left no row in
    logs/fleet_power.log, so "who started this box" would have been
    unanswerable for exactly the path an operator reaches for when the
    orchestrator is not what they want. It now routes through ec2ops.start(),
    which records every power change.

    ⚠️ THE REGISTRY-STARTER PROBE WAS ALSO REMOVED, and it is worth saying why
    rather than deleting it quietly: it looked up "start_instances", "start" or
    "wake" on instance_registry and used whichever existed. instance_registry
    defines NONE of them, so the loop has never once fired and its removal is
    behaviour-neutral today — but the day someone adds a `start()` helper to
    the registry it would have silently become the wake path and bypassed the
    ledger again. A hole that opens on an unrelated future edit is worse than
    one that is open now, because nothing will be looking.

    A failed wake does not raise: it continues with running boxes and RETURNS
    False, and cmd_update (OPS.16) fails the run for every requested box that
    is still not running and reachable — never `0/0 deployed cleanly`, rc 0.
    """
    symbols = [s for s, _, _ in stopped]
    if not symbols:
        return True
    print(f"Waking {len(symbols)} stopped box(es): {', '.join(symbols)}")
    if config.MOCK_AWS:
        print(f"  [mock] would start: {', '.join(symbols)}")
        return True

    try:
        mapping, _ = instance_registry.discover(symbols)
        ids = [mapping[s].get("instance_id")
               for s in symbols
               if mapping.get(s, {}).get("instance_id")]
        if not ids:
            print("  ⚠️  no instance_id in the registry — can't wake automatically.\n"
                  "     Start these in the EC2 console (or add instance_id to the\n"
                  "     registry), then re-run `update` without --wake.")
            return False
        ec2ops.start(ids)
        print(f"  ec2ops.start() issued for {len(ids)} instance(s) — logged to "
              f"{os.path.basename(ec2ops.POWER_LOG)}")
        return True
    except Exception as e:
        print(f"  ⚠️  wake failed ({e}); continuing with already-running boxes.")
        return False


def _wait_running_and_ssh(only=None, timeout=180, interval=10):
    """After a wake, poll until boxes are 'running' AND answer SSH. Re-discovers
    each pass (state flips as instances boot). Returns the SSH-ready list."""
    deadline = time.time() + timeout
    ready = []
    while time.time() < deadline:
        fleet = get_fleet(only)
        running = [(s, ip, st) for s, ip, st in fleet if st == "running" and ip]
        ready = []
        for s, ip, _ in running:
            rc, _o, _e = _exec(s, ip, "echo OK")
            if rc == 0:
                ready.append((s, ip, "running"))
        if running and len(ready) == len(running):
            return ready
        print(f"  …waiting for SSH ({len(ready)}/{len(running)} ready)")
        time.sleep(interval)
    return ready


def cmd_update(only=None, restart=True, wake=False):
    fleet = get_fleet(only)
    stopped = [(s, ip, st) for s, ip, st in fleet if st != "running"]

    if wake and stopped:
        _wake(stopped)
        running = _wait_running_and_ssh(only)
    else:
        running = [(s, ip, st) for s, ip, st in fleet if st == "running" and ip]

    # The bots own the git logic. push.sh --deploy fetches, hard-resets to the
    # remote branch it detects, repairs .sh perms, restarts the service and
    # verifies it — the download counterpart of push.sh's upload. fleet just
    # wakes boxes and fans the command out.
    flag = "" if restart else " --no-restart"
    cmd = f"bash {INSTALL_DIR}/push.sh --deploy{flag}"

    print(f"\nDeploying to {len(running)} box(es) via `push.sh --deploy`"
          f"{' (no restart)' if not restart else ''}\n")
    fails = 0
    for s, ip, _ in running:
        head = f"── {s} ({ip}) "
        print(head + "─" * max(0, 50 - len(head)))
        rc, out, err = _exec(s, ip, cmd)
        print((out.rstrip() or err.rstrip() or "(no output)"))
        if rc != 0:
            fails += 1
            print(f"  🚨 rc={rc}")

    if not wake:
        for s, ip, st in stopped:
            print(f"── {s} ({ip or '-'}) · skipped ({st}; use --wake to start)")

    print(f"\nDone. {len(running) - fails}/{len(running)} deployed cleanly.")
    # 🔴 OPS.16 — --wake was ASKED FOR: a box it was to bring up that is still
    # not running and reachable is a failure, named, whatever the tally says.
    if wake and stopped:
        up = {s for s, _, _ in running}
        unwoken = [s for s, _, _ in stopped if s not in up]
        if unwoken:
            print(f"🚨 WAKE FAILED: {len(unwoken)} requested box(es) not running/reachable: "
                  f"{', '.join(unwoken)} — they were NOT deployed.")
            return 1
    return 0 if fails == 0 else 1


# ─── Fleet repoint (migrate to a new repo, collision-guarded) ────────────────

import re

_SENTINEL_FETCH_FAIL = "__REPOINT_FETCH_FAILED__"
_SENTINEL_OK = "__REPOINT_OK__"
# v0.12.0 — pinned (managed) repoint
_SENTINEL_NO_SHA = "__REPOINT_NO_SHA__"
_SENTINEL_OPEN = "__REPOINT_OPEN_TRADES__"
_SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
_SHADOW_UNITS = ("shadow-observer.service", "shadow-start.timer", "shadow-stop.timer")
_SHADOW_RECORD = "~/.repoint_shadow_units"
# timer-launched writers: one firing during the reset would import a
# half-swapped tree (s3-push WRITES to S3). Stopped first, the ones that were
# active are started again only after the import check passes.
_TIMERS = ("s3-push.timer", "candle-logger.timer", "optbot-self-close.timer",
           "optbot-emergency-watchdog.timer")
_TIMER_JOBS = "s3-push.service candle-logger.service optbot-self-close.service"


# v0.13.0 — the in-place bootstrap install, one box, as ONE shell template (@NAME@ slots, nothing else interpolated).
_SENTINEL_REINSTALL_OK = "__REINSTALL_OK__"
_REINSTALL_KEYS = ("OT_INSTRUMENT", "TT_CLIENT_SECRET", "TT_REFRESH_TOKEN", "TT_ACCOUNT_NUMBER",
                   "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID")
_BOOTSTRAP_PY = r"""
import os, re, shlex, sys
env = {}
for line in sys.stdin:
    m = re.match(r'^Environment="?([A-Z0-9_]+)=(.*?)"?\s*$', line.rstrip("\n"))
    if m:
        env[m.group(1)] = m.group(2)
need = ("TT_CLIENT_SECRET", "TT_REFRESH_TOKEN", "TT_ACCOUNT_NUMBER")
if not all(env.get(k) for k in need) or not env.get("OT_INSTRUMENT"):
    sys.exit(17)
keys = set(os.environ["KEYS"].split())
tpl = open(os.environ["TPL"]).read().splitlines()
out = []
mode_set = False
for l in tpl:
    m = re.match(r'^export ([A-Z0-9_]+)=', l)
    if m and m.group(1) in keys:
        l = "export %s=%s" % (m.group(1), shlex.quote(env.get(m.group(1), "")))
    elif m and m.group(1) == "OT_GIT_REF":
        l = "export OT_GIT_REF=%s" % shlex.quote(os.environ["SHA"])
    elif m and m.group(1) == "OT_CLAUDE_AT_BOOT":
        l = 'export OT_CLAUDE_AT_BOOT="0"'
    elif m and m.group(1) == "OT_CLAUDE_SETTINGS":
        l = 'export OT_CLAUDE_SETTINGS="pull-only"'
    elif m and m.group(1) == "OT_INSTALL_MODE":
        l = 'export OT_INSTALL_MODE="controller"'
        mode_set = True
    out.append(l)
if not mode_set:
    sys.exit(18)
sys.stdout.write("\n".join(out) + "\n")
"""
_REINSTALL_SCRIPT = r"""
cd @DIR@ || exit 9
[ "$(systemctl is-active @SERVICE@)" != active ] && [ "$(systemctl is-active candle-feed)" != active ] \
  || { echo "the bot or the feed is running - refused"; exit 10; }
O=$(sqlite3 trades.db "SELECT count(*) FROM trades WHERE status='open'" 2>/dev/null)
[ "$O" = "0" ] || { echo "open trade(s): ${O:-unreadable} - refused"; exit 10; }
SHA=$(git rev-parse HEAD)
case "$SHA" in @SHA@*) ;; *) echo "HEAD $SHA is not the pin @SHA@ - refused"; exit 7 ;; esac
[ -f bootstrap.example.sh ] || { echo "no bootstrap.example.sh in this tree - refused"; exit 8; }
SYM=$(sudo grep -oP '^Environment="?OT_INSTRUMENT=\K[A-Z0-9_]+' /etc/systemd/system/@SERVICE@.service | head -1)
if systemctl is-enabled -q s3-push.timer 2>/dev/null; then
  D=$(env OT_INSTRUMENT="$SYM" /usr/bin/python3 warehouse/s3_push.py --verify 2>&1 | grep -E "^DRAIN ")
  echo "$D" | grep -qE "^DRAIN .* OK$" || { echo "drain of $SYM did not report OK - refused: $D"; exit 15; }
  echo "drained $SYM: $D"
fi
umask 077
rm -f ~/bootstrap.sh
PYF=$(mktemp)
cat > "$PYF" <<'__REINSTALL_PY__'
@PY@
__REINSTALL_PY__
sudo cat /etc/systemd/system/@SERVICE@.service | SHA="$SHA" TPL="$HOME/options-trader/bootstrap.example.sh" KEYS="@KEYS@" \
  python3 "$PYF" > ~/bootstrap.sh
rc=$?
rm -f "$PYF"
if [ $rc -ne 0 ]; then shred -u ~/bootstrap.sh 2>/dev/null; rm -f ~/bootstrap.sh
  [ $rc -eq 17 ] && { echo "the unit lacks OT_INSTRUMENT or a TastyTrade credential - refused"; exit 16; }
  [ $rc -eq 18 ] && { echo "this tree's bootstrap.example.sh has no OT_INSTALL_MODE (it predates OTV5 r17) - refused"; exit 8; }
  echo "bootstrap build failed rc=$rc"; exit 16; fi
echo "bootstrap built for $SYM at $SHA (credentials from this box's own unit; never printed)"
# detached in tmux: a dropped SSH connection cannot kill the install halfway (and tmux sets $TMUX, so the template
# does not re-exec itself into an attached session); stdin is /dev/null, so setup_ec2's closing login shell exits
rm -f ~/reinstall.rc
cat > ~/reinstall_run.sh <<'__REINSTALL_RUN__'
cd ~ && bash ~/bootstrap.sh < /dev/null 2>&1 | sed -u -E 's/(TT Account: *).*/\1<redacted>/' > ~/reinstall.log
echo "${PIPESTATUS[0]}" > ~/reinstall.rc
shred -u ~/bootstrap.sh 2>/dev/null; rm -f ~/bootstrap.sh ~/install.sh ~/reinstall_run.sh
__REINSTALL_RUN__
tmux kill-session -t reinstall 2>/dev/null
if command -v tmux >/dev/null 2>&1; then tmux new-session -d -s reinstall "bash $HOME/reinstall_run.sh"
else TMUX=none bash ~/reinstall_run.sh; fi
n=0; while [ ! -f ~/reinstall.rc ]; do n=$((n+1))
  [ $n -gt 600 ] && { echo "the install is still running after 50 min: tmux attach -t reinstall on the box"; exit 19; }
  sleep 5; done
shred -u ~/bootstrap.sh 2>/dev/null; rm -f ~/bootstrap.sh
chmod 600 ~/reinstall.log
RC=$(cat ~/reinstall.rc 2>/dev/null)
tail -n 25 ~/reinstall.log | grep -vE "TT_|TELEGRAM_|SECRET|TOKEN"
echo "units: @SERVICE@=$(systemctl is-enabled @SERVICE@)/$(systemctl is-active @SERVICE@) candle-feed=$(systemctl is-enabled candle-feed)/$(systemctl is-active candle-feed) claude-boot=$(systemctl is-enabled optbot-claude-boot.service 2>/dev/null || echo absent)"
echo "head: $(git -C @DIR@ rev-parse --short HEAD)"
LAST=$(grep -E "^INSTALL (OK|FAILED)" ~/reinstall.log | tail -1)
echo "result: ${LAST:-none}"
[ "$LAST" = "INSTALL OK $SHA" ] && [ "${RC:-1}" = 0 ] && echo "@OK@ $SHA" \
  || { echo "install rc=${RC:-?}, result '${LAST:-none}' - see ~/reinstall.log on the box"; exit 18; }
"""


def _reinstall_cmd(sha):
    """v0.13.0 — fill _REINSTALL_SCRIPT for one box."""
    py = _BOOTSTRAP_PY.strip("\n")
    assert "__REINSTALL_PY__" not in py
    slots = {"@DIR@": INSTALL_DIR, "@SERVICE@": SERVICE, "@SHA@": sha, "@KEYS@": " ".join(_REINSTALL_KEYS),
             "@OK@": _SENTINEL_REINSTALL_OK, "@PY@": py}
    script = _REINSTALL_SCRIPT
    for k, v in slots.items():
        script = script.replace(k, v)
    return script.strip("\n")


def cmd_reinstall(new_url, only=None, sha=None, wake=False, assume_yes=False):
    """v0.13.0 — the managed repoint, then the full bootstrap install in place, for ONE box."""
    if not only or len(only) != 1:
        print("reinstall takes exactly one box: --only SYM")
        return 2
    if not sha or not _SHA_RE.match(sha.strip().lower()):
        print("reinstall needs --sha <7-40 hex>: the pin the box is repointed to and installed from")
        return 2
    sha = sha.strip().lower()
    # v0.16.0: the fleet repoint with one box - phase 3 (the install) runs inside cmd_repoint
    return cmd_repoint(new_url, only=only, wake=wake, assume_yes=assume_yes, sha=sha, install=True)


# v0.15.0 — flash: the blank-instance install. Reuses reinstall's bootstrap builder (its input is Environment= lines)
# and its run-and-judge tail, so the two installs from control cannot drift apart.
_CRED_KEYS = ("TT_CLIENT_SECRET", "TT_REFRESH_TOKEN", "TT_ACCOUNT_NUMBER", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID")
_SEED_EXTRACT = ("sudo grep -E '^Environment=\"?(%s)=' /etc/systemd/system/%s.service"
                 % ("|".join(_CRED_KEYS), SERVICE))
_FLASH_RECEIVE = "umask 077; cat > ~/.flash_creds; wc -l < ~/.flash_creds"
_SYM_RE = re.compile(r"^[A-Z0-9_]{1,12}$")
_FLASH_HEAD = r"""
[ -e ~/options-trader ] && { echo "~/options-trader exists - not a blank instance - refused"; shred -u ~/.flash_creds 2>/dev/null; rm -f ~/.flash_creds; exit 20; }
[ -s ~/.flash_creds ] || { echo "no credentials arrived from the seed - refused"; rm -f ~/.flash_creds; exit 21; }
SHA=@FULLSHA@
umask 077
TPL=$(mktemp)
curl -fsSL "https://raw.githubusercontent.com/@REPO@/$SHA/bootstrap.example.sh" -o "$TPL" \
  || { echo "the pinned bootstrap template could not be fetched - refused"; shred -u ~/.flash_creds; rm -f "$TPL"; exit 22; }
PYF=$(mktemp)
cat > "$PYF" <<'__REINSTALL_PY__'
@PY@
__REINSTALL_PY__
{ cat ~/.flash_creds; echo "Environment=OT_INSTRUMENT=@SYM@"; } | SHA="$SHA" TPL="$TPL" KEYS="@KEYS@" python3 "$PYF" > ~/bootstrap.sh
rc=$?
shred -u ~/.flash_creds 2>/dev/null; rm -f ~/.flash_creds "$TPL" "$PYF"
if [ $rc -ne 0 ]; then shred -u ~/bootstrap.sh 2>/dev/null; rm -f ~/bootstrap.sh
  [ $rc -eq 17 ] && { echo "the seed's unit lacks a TastyTrade credential - refused"; exit 16; }
  [ $rc -eq 18 ] && { echo "the pinned bootstrap.example.sh has no OT_INSTALL_MODE (it predates OTV5 r17) - refused"; exit 8; }
  echo "bootstrap build failed rc=$rc"; exit 16; fi
echo "bootstrap built for @SYM@ at $SHA (credentials from the seed box; never printed)"
"""


def _run_judge_tail():
    """reinstall's run-and-judge tail (detached tmux, INSTALL OK <pin>, shred after exit), shared by flash."""
    return _REINSTALL_SCRIPT[_REINSTALL_SCRIPT.index("# detached in tmux"):]


def _flash_cmd(full_sha, repo_slug, symbol):
    """v0.15.0 — the new box's script: build the bootstrap from ~/.flash_creds, then reinstall's tail."""
    py = _BOOTSTRAP_PY.strip("\n")
    script = _FLASH_HEAD + _run_judge_tail()
    slots = {"@FULLSHA@": full_sha, "@REPO@": repo_slug, "@SYM@": symbol, "@PY@": py, "@DIR@": INSTALL_DIR,
             "@SERVICE@": SERVICE, "@SHA@": full_sha, "@KEYS@": " ".join(_REINSTALL_KEYS),
             "@OK@": _SENTINEL_REINSTALL_OK}
    for k, v in slots.items():
        script = script.replace(k, v)
    return script.strip("\n")


def _ssh_argv(ip, command):
    return ["ssh", "-i", config.SSH_KEY_PATH, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new",
            "-o", f"ConnectTimeout={config.SSH_CONNECT_TIMEOUT}", f"{config.SSH_USER}@{ip}", command]


def _pipe_creds(seed_ip, new_ip, timeout=120):
    """Seed unit -> new box, through an ssh pipe. Control's Python NEVER reads the seed's stdout; only the receiving
    side's line count comes back. -> (rc, lines)."""
    import subprocess
    p1 = subprocess.Popen(_ssh_argv(seed_ip, _SEED_EXTRACT), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    p2 = subprocess.Popen(_ssh_argv(new_ip, _FLASH_RECEIVE), stdin=p1.stdout, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, text=True)
    p1.stdout.close()
    try:
        out, _ = p2.communicate(timeout=timeout)
        p1.wait(timeout=timeout)
    except Exception:                                          # noqa: BLE001
        p1.kill()
        p2.kill()
        return 255, 0
    try:
        n = int((out or "0").strip().splitlines()[-1])
    except (ValueError, IndexError):
        n = 0
    return (0 if p2.returncode == 0 else p2.returncode), n


def _full_sha(repo, sha):
    """The pin's full SHA from the local checkout of `repo` under $HOME (fetched first), or None."""
    import subprocess
    path = os.path.expanduser(f"~/{repo}") if repo else ""
    if not path or not os.path.isdir(os.path.join(path, ".git")):
        return sha if re.match(r"^[0-9a-f]{40}$", sha) else None
    subprocess.run(["git", "-C", path, "fetch", "-q", "origin"], capture_output=True)
    r = subprocess.run(["git", "-C", path, "rev-parse", "--verify", "-q", f"{sha}^{{commit}}"],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def cmd_flash(new_url, only=None, sha=None, seed=None, symbol=None, wake=False, assume_yes=False):
    """v0.15.0 — install the pinned OTV5 on ONE blank, tagged instance, credentials streamed from a seed box."""
    if not only or len(only) != 1:
        print("flash takes exactly one new instance: --only NAME (its Name tag)")
        return 2
    name = only[0]
    if not seed:
        print("flash needs --seed SYM: a running fleet box whose unit holds the shared credentials")
        return 2
    seed = seed.strip().upper()
    if seed == name:
        print("the seed must be another box, not the instance being flashed")
        return 2
    symbol = (symbol or name).strip().upper()
    if not _SYM_RE.match(symbol):
        print(f"--symbol {symbol!r} is not a symbol")
        return 2
    if not sha or not _SHA_RE.match(sha.strip().lower()):
        print("flash needs --sha <7-40 hex>: the pin to install")
        return 2
    repo = _repo_name_from_url(new_url)
    m = re.search(r"github\.com[:/]+([^/]+/[^/]+?)(?:\.git)?/?$", new_url or "")
    if not repo or not m:
        print("flash needs a GitHub repo URL, e.g. https://github.com/TX-9AI/OTV5.git")
        return 2
    full = _full_sha(repo, sha.strip().lower())
    if not full:
        print(f"the pin {sha} could not be resolved to a full commit (no local checkout ~/{repo} holding it) - give all 40 hex")
        return 2
    boxes = get_fleet([name, seed])
    stopped = [(s, ip, st) for s, ip, st in boxes if st != "running"]
    if stopped and wake:
        _wake(stopped)
        boxes = _wait_running_and_ssh([name, seed])
    by = {s: (ip, st) for s, ip, st in boxes}
    for who in (name, seed):
        if who not in by or by[who][1] != "running" or not by[who][0]:
            print(f"{who} is not a running, reachable tagged instance (use --wake to start it) - nothing was done")
            return 1
    print(f"\nFlash target:  {name} ({by[name][0]}) as {symbol}\nRepo / pin:    {m.group(1)} {full}\n"
          f"Seed:          {seed} ({by[seed][0]}) - credentials stream box to box, never printed\n"
          f"Mode:          controller install; Claude installed, NOT raised at boot; every service STOPPED")
    if not assume_yes and not config.MOCK_AWS:
        if input(f"\nType the instance name ({name}) to flash it: ").strip().upper() != name:
            print("Confirmation did not match; nothing changed.")
            return 2
    if config.MOCK_AWS:
        print("[mock] flash previewed; nothing sent.")
        return 0
    rc, lines = _pipe_creds(by[seed][0], by[name][0])
    if rc != 0 or lines < 3:
        print(f"🚨 the credentials did not arrive (rc {rc}, {lines} line(s)) - nothing was installed.")
        _exec(name, by[name][0], "shred -u ~/.flash_creds 2>/dev/null; rm -f ~/.flash_creds")
        return 1
    print(f"credentials: {lines} line(s) streamed from {seed} to {name}")
    print(f"\n{'='*58}\nINSTALL — controller mode, on {name}\n{'='*58}")
    rc, out, err = _exec(name, by[name][0], _flash_cmd(full, m.group(1), symbol), timeout=3600)
    print(out.rstrip() or err.rstrip() or "(no output)")
    if rc != 0 or _SENTINEL_REINSTALL_OK not in out:
        print(f"\n🚨 {name}: the flash did not complete (rc {rc}). Nothing was started.")
        return 1
    print(f"\n✅ {name} flashed at {full}: every service installed and STOPPED.\n"
          f"   Next (the operator): ./configure.sh - symbol, risk, switches, item 14 - then Done.")
    return 0


def _repo_name_from_url(url):
    """https://github.com/OWNER/options_trader_v3.git -> options_trader_v3."""
    m = re.search(r"github\.com[:/]+[^/]+/([^/]+?)(?:\.git)?/?$", url)
    return m.group(1) if m else None


def _phase1_check_cmd(new_url, repo, sha=None):
    """Non-mutating: fetch the new repo into FETCH_HEAD (origin untouched) and
    print any untracked file on this box that the new repo TRACKS. Prints the
    fetch-fail sentinel if the new repo can't be reached.
    v0.12.0 — with `sha`: collisions are read against the PIN, and the box
    also prints the no-sha sentinel if the fetch lacks it and the open-trades
    sentinel unless trades.db reads exactly 0 open rows (unreadable = refused)."""
    repo_clause = (
        f'if [ -n "$TOKEN" ]; then '
        f'URL="https://TX-9AI:${{TOKEN}}@github.com/TX-9AI/{repo}.git"; '
        f'else URL="{new_url}"; fi; '
    ) if repo else f'URL="{new_url}"; '
    return (
        f"cd {INSTALL_DIR} || exit 9; "
        f"TOKEN=$(sudo systemctl show {SERVICE} --property=Environment 2>/dev/null "
        f"| grep -o 'GITHUB_TOKEN=[^ ]*' | cut -d= -f2); "
        f"{repo_clause}"
        f'git fetch "$URL" main -q 2>/dev/null || {{ echo {_SENTINEL_FETCH_FAIL}; exit 3; }}; '
        + (_pin_preflight(sha) if sha else "") +
        f"comm -12 <(git ls-tree -r --name-only {sha or 'FETCH_HEAD'} | sort) "
        f"<(git ls-files --others --exclude-standard | sort)"
    )


def _pin_preflight(sha):
    """v0.12.0 — phase 1's two extra refusals for a pinned repoint."""
    return (
        f'git cat-file -e "{sha}^{{commit}}" 2>/dev/null '
        f"|| {{ echo {_SENTINEL_NO_SHA}; exit 0; }}; "
        f"""O=$(sqlite3 trades.db "SELECT count(*) FROM trades WHERE status='open'" 2>/dev/null); """
        f'[ "$O" = "0" ] || echo "{_SENTINEL_OPEN} ${{O:-unreadable}}"; '
    )


def _phase2_commit_cmd(new_url, repo, restart, sha=None):
    """Mutating: point origin at the new repo, hard-reset to it, repair *.sh
    +x, optionally restart + verify. Leaves origin on a token-free new URL.
    v0.12.0 — with `sha`, see _pinned_commit_cmd."""
    if sha:
        return _pinned_commit_cmd(new_url, repo, sha)
    clean_url = f"https://github.com/TX-9AI/{repo}.git" if repo else new_url
    fetch_clause = (
        f'if [ -n "$TOKEN" ]; then '
        f'FURL="https://TX-9AI:${{TOKEN}}@github.com/TX-9AI/{repo}.git"; '
        f'else FURL="{new_url}"; fi; '
    ) if repo else f'FURL="{new_url}"; '
    restart_clause = (
        f"sudo systemctl restart {SERVICE} && sleep 3 && "
        f'echo "service: $(systemctl is-active {SERVICE})"'
    ) if restart else 'echo "(service not restarted — --no-restart)"'
    return (
        f"cd {INSTALL_DIR} || exit 9; "
        f"TOKEN=$(sudo systemctl show {SERVICE} --property=Environment 2>/dev/null "
        f"| grep -o 'GITHUB_TOKEN=[^ ]*' | cut -d= -f2); "
        f"{fetch_clause}"
        f'git remote set-url origin "$FURL" || exit 4; '
        f"git fetch origin main -q || exit 5; "
        f"OLD=$(git rev-parse --short HEAD 2>/dev/null); "
        f"git reset --hard origin/main -q || exit 6; "
        f'git remote set-url origin "{clean_url}"; '
        f"git ls-files '*.sh' | xargs -r chmod +x 2>/dev/null; "
        f"NEW=$(git rev-parse --short HEAD 2>/dev/null); "
        f'echo "{_SENTINEL_OK} $OLD -> $NEW"; '
        f"{restart_clause}"
    )


# v0.12.0 — the managed repoint, one box, as ONE shell template. @NAME@ slots
# are filled by _pinned_commit_cmd; nothing else in it is interpolated.
# Order matters: the writers stop before the tree changes under them, and
# nothing restarts (start is the bake's start step, one box first).
_PINNED_SCRIPT = r"""
cd @DIR@ || exit 9
sudo systemctl stop @SERVICE@ candle-feed || exit 10
[ "$(systemctl is-active @SERVICE@)" != active ] && [ "$(systemctl is-active candle-feed)" != active ] || exit 10
TIMERS_ON=$(for t in @TIMERS@; do systemctl is-active "$t" >/dev/null 2>&1 && echo "$t"; done | tr "\n" " ")
for t in @TIMERS@; do sudo systemctl stop "$t" >/dev/null 2>&1; done
# a push or a logger already running finishes; it is not killed mid-upload
n=0; while systemctl is-active -q @JOBS@ 2>/dev/null; do
  n=$((n+1)); [ $n -gt 60 ] && { echo "a timer job is still running after 120 s"; exit 13; }; sleep 2; done
TOKEN=$(sudo systemctl show @SERVICE@ --property=Environment 2>/dev/null | grep -o 'GITHUB_TOKEN=[^ ]*' | cut -d= -f2)
SYM=$(sudo systemctl show @SERVICE@ --property=Environment 2>/dev/null | grep -oP 'OT_INSTRUMENT=\K[A-Z0-9_]+')
@FETCH@
git remote set-url origin "$FURL" || exit 4
git fetch origin main -q || exit 5
git cat-file -e "@SHA@^{commit}" || exit 7
OLD=$(git rev-parse --short HEAD 2>/dev/null)
git reset --hard "@SHA@" -q || exit 6
git remote set-url origin "@CLEAN@"
git ls-files '*.sh' | xargs -r chmod +x 2>/dev/null
find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null
# shadow: a tree without shadow/ runs none (what was enabled is recorded first);
# a tree with shadow/ gets back exactly what was recorded - so the same command
# pinned at the old tree is the rollback
if [ -d shadow ]; then
  if [ -f @REC@ ]; then xargs -r sudo systemctl enable --now < @REC@ && rm -f @REC@; fi
else
  if [ ! -f @REC@ ]; then
    for u in @UNITS@; do systemctl is-enabled "$u" >/dev/null 2>&1 && echo "$u"; done > @REC@
  fi
  for u in @UNITS@; do sudo systemctl disable --now "$u" >/dev/null 2>&1; done
fi
echo "shadow: $(for u in @UNITS@; do printf '%s=%s ' "$u" "$(systemctl is-enabled "$u" 2>/dev/null || echo absent)"; done)"
# deps: the frozen lock on its reference interpreter, else the floors
REQ=requirements.txt
if [ -f requirements.lock ] && venv/bin/python -c 'import sys; sys.exit(sys.version_info[:2] != (3, 14))'; then REQ=requirements.lock; fi
venv/bin/pip install -q -r "$REQ" > /tmp/repoint_pip.log 2>&1 || { echo "pip FAILED ($REQ), see /tmp/repoint_pip.log"; exit 11; }
echo "deps: $REQ, tastytrade $(venv/bin/python -c 'import importlib.metadata as m; print(m.version("tastytrade"))')"
# import check: every entry point a unit or the conductor launches, under the
# interpreter that launches it; OT_LOG_FILE keeps main's handler off bot.log;
# a module the tree does not carry is skipped by name
for spec in @IMPORTS@; do
  py=${spec%%:*}; m=${spec#*:}; f=$(echo "$m" | tr . /).py
  [ -f "$f" ] || { echo "import skip: $m (not in this tree)"; continue; }
  [ "$py" = sys ] && PY=/usr/bin/python3 || PY=venv/bin/python
  env OT_LOG_FILE=/tmp/repoint_import.log OT_INSTRUMENT="$SYM" $PY -c "import sys; sys.path.insert(0, '.'); import $m" > /tmp/repoint_import.out 2>&1 \
    || { echo "import check FAILED: $m ($PY)"; tail -3 /tmp/repoint_import.out; exit 12; }
done
for t in $TIMERS_ON; do sudo systemctl start "$t" || { echo "timer $t did not start"; exit 14; }; done
echo "timers back: ${TIMERS_ON:-none}"
NEW=$(git rev-parse --short HEAD 2>/dev/null)
echo "@OK@ $OLD -> $NEW"
echo "(bot and feed not started - start is the bake start step, one box first)"
"""

# venv: the bot, the feed, the logger, the watchdog; sys: s3-push and the
# conductor's purge and self-close run under the SYSTEM interpreter
_IMPORT_SPECS = ("venv:main", "venv:data.candle_feed", "venv:data.candle_logger",
                 "venv:tools.emergency_watchdog", "venv:tools.eod_summary",
                 "sys:warehouse.s3_push", "sys:warehouse.retention_purge",
                 "sys:warehouse.self_close")


def _pinned_commit_cmd(new_url, repo, sha):
    """v0.12.0 — fill _PINNED_SCRIPT for one pinned repoint."""
    clean_url = f"https://github.com/TX-9AI/{repo}.git" if repo else new_url
    fetch = (
        f'if [ -n "$TOKEN" ]; then '
        f'FURL="https://TX-9AI:${{TOKEN}}@github.com/TX-9AI/{repo}.git"; '
        f'else FURL="{new_url}"; fi'
    ) if repo else f'FURL="{new_url}"'
    slots = {"@DIR@": INSTALL_DIR, "@SERVICE@": SERVICE, "@FETCH@": fetch,
             "@SHA@": sha, "@CLEAN@": clean_url, "@REC@": _SHADOW_RECORD,
             "@UNITS@": " ".join(_SHADOW_UNITS), "@TIMERS@": " ".join(_TIMERS),
             "@JOBS@": _TIMER_JOBS,
             "@IMPORTS@": " ".join(_IMPORT_SPECS), "@OK@": _SENTINEL_OK}
    script = _PINNED_SCRIPT
    for k, v in slots.items():
        script = script.replace(k, v)
    return script.strip("\n")


_REMOTE_PROBE = (f"cd {INSTALL_DIR} 2>/dev/null && "
                 f"basename \"$(git remote get-url origin 2>/dev/null)\" .git "
                 f"|| echo '?'")


def survey_remotes(running, exec_fn=None):
    """v0.7.0 — {symbol: repo-name} for the boxes we are about to touch.

    Read-only. A box that cannot be reached or has no remote reports '?',
    which counts as its own group — an unknown remote is not evidence of
    sameness.
    """
    ex = exec_fn or _exec
    out_map = {}
    for s, ip, _ in running:
        try:
            rc, out, _err = ex(s, ip, _REMOTE_PROBE)
            name = (out or "").strip().splitlines()[-1].strip() if out else ""
            out_map[s] = name if (rc == 0 and name) else "?"
        except Exception:                                  # noqa: BLE001
            out_map[s] = "?"
    return out_map


def repoint_refusal(remote_map, target_repo, only, all_repos):
    """v0.7.0 — should this unscoped repoint be REFUSED? Pure; returns the
    refusal message, or None to proceed.

    Refuse when the fleet holds more than one distinct repo and the run is
    neither scoped nor explicitly acknowledged. Naming the boxes matters more
    than the refusal: the operator needs to see WHICH box is about to lose
    its remote and what it is losing.
    """
    if only or all_repos:
        return None
    distinct = {r for r in remote_map.values()}
    if len(distinct) <= 1:
        return None
    losers = sorted(s for s, r in remote_map.items()
                    if target_repo and r != target_repo and r != "?")
    unknown = sorted(s for s, r in remote_map.items() if r == "?")
    lines = [
        "🛑 REFUSING an unscoped repoint: this fleet holds "
        f"{len(distinct)} distinct repos.",
        "   current: " + " · ".join(
            f"{r}×{sum(1 for v in remote_map.values() if v == r)}"
            for r in sorted(distinct)),
    ]
    if losers:
        lines.append("   would be OVERWRITTEN onto "
                     f"{target_repo}: " +
                     ", ".join(f"{s} (now {remote_map[s]})" for s in losers))
    if unknown:
        lines.append("   remote UNKNOWN (unreachable or no origin): "
                     + ", ".join(unknown))
    lines += [
        "   Scope it:      --only QQQ",
        "   Or say it out loud: --all-repos",
    ]
    return "\n".join(lines)


INSTALL_WORKERS = 4      # v0.16.0: boxes installing at once (apt, pip and the suite run ON the boxes; control waits)


def _pin_supports_controller(repo, sha):
    """v0.16.0 — True/False: does the pinned tree's bootstrap.example.sh carry OT_INSTALL_MODE (OTV5 r17 on)?
    None when it cannot be read (no local checkout ~/<repo> holding the pin)."""
    import subprocess
    path = os.path.expanduser(f"~/{repo}") if repo else ""
    if not path or not os.path.isdir(os.path.join(path, ".git")):
        return None
    subprocess.run(["git", "-C", path, "fetch", "-q", "origin"], capture_output=True)
    r = subprocess.run(["git", "-C", path, "show", f"{sha}:bootstrap.example.sh"], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return re.search(r"^export OT_INSTALL_MODE=", r.stdout, re.M) is not None


def cmd_repoint(new_url, only=None, restart=True, wake=False,
                check_only=False, assume_yes=False, all_repos=False, sha=None, install=None):
    if not new_url or "github.com" not in new_url:
        print(f"repoint needs a GitHub repo URL, e.g.:\n"
              f"  python fleet.py repoint https://github.com/TX-9AI/options_trader_v3.git")
        return 2
    if sha is not None:
        sha = sha.strip().lower()
        if not _SHA_RE.match(sha):
            print(f"--sha must be 7-40 hex characters, got {sha!r}")
            return 2
        restart = False          # v0.12.0 — a pinned repoint never starts anything
    repo = _repo_name_from_url(new_url)
    # v0.16.0 — does this pinned repoint also install? (install=None: when the pinned tree supports it)
    do_install = False
    if sha is not None and install is not False:
        sup = True if config.MOCK_AWS else _pin_supports_controller(repo, sha)
        if sup is None:
            print(f"cannot read the pin's bootstrap template (no local checkout ~/{repo} holding {sha}). "
                  f"Fetch it there, or pass --no-install for a git-only repoint.")
            return 2
        if sup is False and install is True:
            print(f"the pinned tree {sha} predates the controller install (no OT_INSTALL_MODE) - refused")
            return 2
        do_install = bool(sup)
        if not sup:
            print(f"note: the pinned tree {sha} predates the controller install - a git-only managed repoint.")

    fleet = get_fleet(only)
    stopped = [(s, ip, st) for s, ip, st in fleet if st != "running"]
    if wake and stopped:
        _wake(stopped)
        running = _wait_running_and_ssh(only)
    else:
        running = [(s, ip, st) for s, ip, st in fleet if st == "running" and ip]

    # ── v0.7.0 GUARD — survey before mutating ──────────────────────────────
    if running:
        remote_map = survey_remotes(running)
        refusal = repoint_refusal(remote_map, repo, only, all_repos)
        if refusal:
            print(refusal)
            return 3

    if not running:
        print("No running, SSH-reachable boxes to repoint. "
              "(Use --wake to start stopped boxes.)")
        return 1

    print(f"\nRepoint target: {new_url}")
    print(f"Detected repo:  {repo or '(could not parse — using URL verbatim)'}")
    if sha:
        print(f"Pinned SHA:     {sha}  (managed: stop, reset, deps, import check; no start)")
        print(f"Install:        " + ("THE FULL INSTALL on every box after its repoint (controller mode; the box's own "
                                     "credentials; services stay STOPPED for configure.sh)" if do_install
                                     else "none (git-only)"))
    print(f"Fleet:          {len(running)} running box(es)"
          + (f", {len(stopped)} stopped (skipped)" if stopped and not wake else ""))

    # ── PHASE 1 — collision check against the NEW repo (non-mutating) ──────────
    print(f"\n{'='*58}\nPHASE 1 — collision check vs new repo (nothing is changed)\n{'='*58}")
    check_cmd = _phase1_check_cmd(new_url, repo, sha)
    collisions, unreachable, refused = {}, [], {}
    for s, ip, _ in running:
        rc, out, err = _exec(s, ip, check_cmd)
        lines = [l for l in out.splitlines() if l.strip()]
        stops = [l for l in lines if l.startswith((_SENTINEL_NO_SHA, _SENTINEL_OPEN))]
        lines = [l for l in lines if l not in stops]
        if stops and not config.MOCK_AWS:
            refused[s] = stops
            why = "; ".join("pin not in the fetched repo" if l.startswith(_SENTINEL_NO_SHA)
                            else "open trade(s): " + l.split(" ", 1)[-1] for l in stops)
            print(f"{s:<8}{ip:<18}🚨 refused — {why}")
        elif _SENTINEL_FETCH_FAIL in out or rc == 3:
            unreachable.append(s)
            print(f"{s:<8}{ip:<18}🚨 could not fetch new repo (token/network?)")
        elif rc != 0:
            unreachable.append(s)
            print(f"{s:<8}{ip:<18}🚨 check failed rc={rc} {err.strip()[:40]}")
        elif lines:
            collisions[s] = lines
            print(f"{s:<8}{ip:<18}🚨 {len(lines)} collision(s): {', '.join(lines)}")
        else:
            print(f"{s:<8}{ip:<18}✅ clean")

    if collisions or unreachable or refused:
        print(f"\n{'='*58}")
        print("🚨 ABORT — phase 2 will NOT run. No box was repointed.")
        if refused:
            print("\nBoxes refused by the pinned-repoint preflight: "
                  + ", ".join(sorted(refused)))
        if collisions:
            print("\nBoxes with untracked files the new repo would OVERWRITE:")
            for s, files in collisions.items():
                for f in files:
                    print(f"    {s}: {f}")
            print("\nThese are likely live secrets/config. Move them into the\n"
                  "systemd env (or back them up) before repointing.")
        if unreachable:
            print(f"\nBoxes that couldn't reach the new repo: {', '.join(unreachable)}")
            print("Check the repo exists, is spelled right, and the box's\n"
                  "GITHUB_TOKEN can read it.")
        return 1

    print(f"\n✅ All {len(running)} box(es) clean — no untracked file collides "
          f"with the new repo.")

    if check_only:
        print("--check-only: stopping here. Re-run without it to migrate.")
        return 0

    # ── confirmation ──────────────────────────────────────────────────────────
    if not assume_yes and not config.MOCK_AWS:
        ans = input(f"\nProceed to REPOINT + hard-reset {len(running)} box(es) to "
                    f"{repo or new_url}?\nType the fleet size ({len(running)}) to "
                    f"confirm: ").strip()
        if ans != str(len(running)):
            print("Confirmation did not match; nothing changed.")
            return 2

    # ── PHASE 2 — commit the repoint (only reached if fully clean) ────────────
    print(f"\n{'='*58}\nPHASE 2 — repoint + sync"
          f"{' + restart' if restart else ''}\n{'='*58}")
    commit_cmd = _phase2_commit_cmd(new_url, repo, restart, sha)
    fails = 0
    repointed = []
    for s, ip, _ in running:
        head = f"── {s} ({ip}) "
        print(head + "─" * max(0, 50 - len(head)))
        rc, out, err = _exec(s, ip, commit_cmd)
        body = out.rstrip() or err.rstrip() or "(no output)"
        print(body)
        ok = (rc == 0) and (_SENTINEL_OK in out or config.MOCK_AWS)
        if restart and not config.MOCK_AWS and "service: active" not in out:
            ok = False
        if not ok:
            fails += 1
            print(f"  🚨 rc={rc} — box may be partially migrated; inspect before retry")
        else:
            repointed.append((s, ip))

    print(f"\nDone. {len(running) - fails}/{len(running)} repointed cleanly to "
          f"{repo or new_url}.")
    if do_install:
        # ── PHASE 3 (v0.16.0) — the full install, in place, on every box that repointed cleanly ──
        print(f"\n{'='*58}\nPHASE 3 — the full install on {len(repointed)} box(es), "
              f"{INSTALL_WORKERS} at a time\n{'='*58}")
        if fails:
            print(f"  (not installed: the {fails} box(es) whose repoint failed above)")
        ifails = []

        def _landed(key, res, done, total):
            rc_, out_, err_ = res
            good = rc_ == 0 and (_SENTINEL_REINSTALL_OK in (out_ or "") or config.MOCK_AWS)
            head_ = f"── {key}: {'INSTALLED' if good else 'INSTALL FAILED rc=%s' % rc_} ({done}/{total}) "
            print(head_ + "─" * max(0, 58 - len(head_)))
            print((out_ or err_ or "(no output)").rstrip())
            if not good:
                ifails.append(key)
        ssh_util.ssh_map(repointed, _reinstall_cmd(sha), timeout=3600, workers=INSTALL_WORKERS, on_result=_landed)
        print(f"\nInstalled: {len(repointed) - len(ifails)}/{len(repointed)}"
              + (f"; FAILED: {', '.join(sorted(ifails))} (the tree is on {sha}; nothing was started)" if ifails else ""))
        print("Next (the operator), box by box: ./configure.sh - symbol, risk, switches, item 14 managed - then Done.")
        return 0 if not fails and not ifails else 1
    if fails == 0:
        print("Ongoing deploys: ensure the new repo's push.sh targets it, then "
              "`fleet.py update` works as before.")
    return 0 if fails == 0 else 1


# ─── Fleet pull (download trades.db / OHLC back to the control server) ────────

def cmd_pull(what, only=None, day=None):
    """Download a box artifact into the shared dated harvest folder — IDENTICAL to
    what harvest produces, so a hand-pull and a harvested pull are interchangeable:
      what='db'   -> options-trader/trades.db  (WAL-checkpointed first)
                     -> trades/<date>/<SYM>_trades_<date>.db   (date = today, or --day)
      what='ohlc' -> options-trader/data/OHLC/<day>/<SYM>.csv
                     -> ohlc/<date>/<SYM>_ohlc_<date>.csv      (date = --day, required)
    """
    if what == "ohlc" and not day:
        print("pull ohlc needs --day YYYY-MM-DD, e.g.:\n"
              "  python fleet.py pull ohlc --day 2026-07-10 --only IWM")
        return 2
    date = day or _today_et()
    dest = os.path.join(config.TRADES_DIR if what == "db" else config.OHLC_DIR, date)
    os.makedirs(dest, exist_ok=True)

    fleet = get_fleet(only)
    running = [(s, ip, st) for s, ip, st in fleet if st == "running" and ip]
    if not running:
        print("No running, SSH-reachable boxes to pull from.")
        return 1

    label = "trades.db" if what == "db" else f"OHLC {date}"
    print(f"Pulling {label} from {len(running)} box(es) -> {dest}\n")
    ok = 0
    for s, ip, _ in running:
        if what == "db":
            remote = f"{REMOTE_HOME_REL}/trades.db"
            local  = os.path.join(dest, f"{s}_trades_{date}.db")
        else:
            remote = f"{REMOTE_HOME_REL}/data/OHLC/{day}/{s}.csv"
            local  = os.path.join(dest, f"{s}_ohlc_{date}.csv")
        if config.MOCK_AWS:
            print(f"{s:<8}[mock] would scp {remote} -> {local}")
            ok += 1
            continue
        # Checkpoint the WAL into the main db first so the copy is a complete
        # snapshot — the same way harvest pulls it.
        if what == "db":
            ssh_util.ssh_run(
                ip, f"sqlite3 ~/{REMOTE_HOME_REL}/trades.db "
                    "'PRAGMA wal_checkpoint(TRUNCATE);' 2>/dev/null || true")
        rc, _out, err = ssh_util.scp_pull(ip, remote, local)
        if rc == 0 and os.path.exists(local):
            size = os.path.getsize(local)
            print(f"{s:<8}✅ {os.path.basename(local)} ({size:,} bytes)")
            ok += 1
        else:
            msg = err.strip()[:60] or f"rc={rc}"
            print(f"{s:<8}🚨 {msg}")
    print(f"\nDone. {ok}/{len(running)} pulled into {dest}")
    return 0 if ok == len(running) else 1
    return 0 if ok == len(running) else 1


def main(argv):
    p = argparse.ArgumentParser(description="day_trader_pro fleet SSH fan-out")
    p.add_argument("action", choices=["list", "ping", "run", "update", "repoint", "reinstall", "flash", "pull"])
    p.add_argument("command", nargs="?", default=None,
                   help="command string (for 'run'), new repo URL (for 'repoint'), "
                        "or 'db'/'ohlc' (for 'pull')")
    p.add_argument("--only", default=None,
                   help="comma-separated symbols to target (e.g. SPX,QQQ)")
    p.add_argument("--all", action="store_true",
                   help="include stopped boxes (shown as skipped)")
    p.add_argument("--timeout", type=int, default=None,
                   help="per-box COMMAND budget in seconds for 'run' "
                        "(default config.SSH_COMMAND_TIMEOUT); the connect "
                        "timeout is separate and unaffected")
    p.add_argument("--day", default=None,
                   help="date YYYY-MM-DD: ohlc = which day's candles to fetch; "
                        "db = target harvest folder (defaults to today)")
    p.add_argument("--no-restart", action="store_true",
                   help="update/repoint: sync only, don't restart the service")
    p.add_argument("--wake", action="store_true",
                   help="update/repoint: start stopped boxes first, then act on them")
    p.add_argument("--check-only", action="store_true",
                   help="repoint: run phase-1 collision check only, change nothing")
    p.add_argument("--yes", action="store_true",
                   help="repoint: skip the confirmation prompt")
    p.add_argument("--all-repos", action="store_true",
                   help="repoint a fleet that holds MORE THAN ONE repo "
                        "(required for an unscoped run once a fork exists)")
    p.add_argument("--sha", default=None,
                   help="repoint: MANAGED repoint to this exact commit — stops the bot "
                        "and feed first, refuses open trades, handles shadow units, "
                        "installs deps, import-checks, and never restarts")
    p.add_argument("--seed", default=None,
                   help="flash: the running fleet box whose unit seeds the shared credentials")
    p.add_argument("--symbol", default=None,
                   help="flash: the symbol to install (default: the new instance's Name tag)")
    p.add_argument("--no-install", action="store_true",
                   help="repoint --sha: the git-only managed repoint, no install phase")
    p.add_argument("--mock", action="store_true", help="offline preview")
    args = p.parse_args(argv[1:])

    if args.mock:
        config.set_mock(True)
    only = [s.strip().upper() for s in args.only.split(",")] if args.only else None

    if args.action == "list":
        cmd_list(only)
        return 0
    if args.action == "ping":
        return cmd_ping(only, args.all)
    if args.action == "run":
        if not args.command:
            print("run needs a command, e.g.:  python fleet.py run \"uptime\"")
            return 2
        return cmd_run(args.command, only, args.all, timeout=args.timeout)
    if args.action == "update":
        return cmd_update(only, restart=not args.no_restart, wake=args.wake)
    if args.action == "repoint":
        if not args.command:
            print("repoint needs a new repo URL, e.g.:\n"
                  "  python fleet.py repoint https://github.com/TX-9AI/options_trader_v3.git")
            return 2
        return cmd_repoint(args.command, only=only, restart=not args.no_restart,
                           wake=args.wake, check_only=args.check_only,
                           assume_yes=args.yes, all_repos=args.all_repos,
                           sha=args.sha, install=False if args.no_install else None)
    if args.action == "reinstall":
        if not args.command:
            print("reinstall needs the repo URL, e.g.:\n"
                  "  python fleet.py reinstall https://github.com/TX-9AI/OTV5.git --sha <sha> --only NVDA")
            return 2
        return cmd_reinstall(args.command, only=only, sha=args.sha, wake=args.wake, assume_yes=args.yes)
    if args.action == "flash":
        if not args.command:
            print("flash needs the repo URL, e.g.:\n"
                  "  python fleet.py flash https://github.com/TX-9AI/OTV5.git --sha <sha> --only NEWBOX --seed SOFI")
            return 2
        return cmd_flash(args.command, only=only, sha=args.sha, seed=args.seed, symbol=args.symbol,
                         wake=args.wake, assume_yes=args.yes)
    if args.action == "pull":
        what = (args.command or "").lower()
        if what not in ("db", "ohlc"):
            print("pull needs 'db' or 'ohlc', e.g.:\n"
                  "  python fleet.py pull db --only IWM\n"
                  "  python fleet.py pull ohlc --day 2026-07-10 --only IWM")
            return 2
        return cmd_pull(what, only=only, day=args.day)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
