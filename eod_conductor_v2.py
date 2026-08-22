#!/usr/bin/env python3
"""
day_trader_pro/eod_conductor_v2.py — v2.0.0
STOP TRADING → FILL THE BUCKET → VERIFY IT LANDED → TAKE THEM DOWN.

v2.0.0  2026-08-25  Operator's statement of intent, verbatim in effect:
"the boxes stop trading, fill the bucket. Conductor verifies data landed &
takes them down orderly."

🔴 WHAT THIS REPLACES AND WHY. v1.16 ran ELEVEN phases and the shutdown sat in
the MIDDLE of them, bound to a P&L report:

    gate → harvest → archive-recovery → REPORT(stops boxes) → backfill →
    daily-bars → archive-report → consolidate → label → excursion → coverage

⚠️ THE BOXES WERE STOPPED BY A PHASE WHOSE JOB WAS PRINTING P&L. Nothing
between "harvest ran" and "kill the boxes" checked that anything had ARRIVED.
`phase_report`'s only failure branch warns that a box may not have STOPPED —
it never asks whether the data got out first. That is the assumption this
rewrite removes.

⚠️ AND THE COMPLETENESS CHECK RAN LAST, AFTER THE BOXES WERE DEAD. Correct for
in-flight S3 objects, fatally late for anything else: chain snapshots CANNOT be
reconstructed after 16:00, so a gap found at 16:20 is a gap forever.

⚠️ ANALYSIS DOES NOT BELONG IN A SHUTDOWN SEQUENCE. backfill, daily-bars,
archive-report, consolidate, label and excursion are all REPORTS. They are out
of this file entirely and run on their own timer against the bucket, where they
cannot race a box that is being stopped and cannot delay a stop that should
already have happened.

🔑 THE VERIFIER WAS ALREADY BUILT AND WAS NEVER WIRED. otv4's
`warehouse/s3_push.py --verify` drains, then reconciles the box's own
per-prefix counters against what S3 actually holds, on COUNT and BYTES, and
prints one machine-readable line. Its own docstring says: *"This is what the
EOD conductor gates a box's shutdown on, so the box answers for itself instead
of control modelling the box's local state."* It said that for twelve days
while the conductor stopped boxes blind.

🔴 THE BOX ANSWERS FOR ITSELF. Control cannot know how many rows a box wrote;
only the box knows. Any verification control invents is control's MODEL of the
box, and a model that disagrees with reality fails silently in whichever
direction the model was wrong.

⚠️ A BOX THAT FAILS VERIFICATION STAYS UP, and that is a deliberate behaviour
change — v1.16 stopped everything regardless. A box left running overnight
costs money, so the failure is ALERTED, not merely logged.

Run:  python3 eod_conductor_v2.py                 # live
      python3 eod_conductor_v2.py --dry-run       # plan only, stops nothing
      python3 eod_conductor_v2.py --no-takedown   # verify only, leave all up
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config                                                   # noqa: E402
import ec2ops                                                   # noqa: E402
import fleet                                                    # noqa: E402
import instance_registry                                        # noqa: E402
try:
    import notify                                               # noqa: E402
except Exception:                                               # noqa: BLE001
    notify = None

INSTALL_DIR = getattr(config, "INSTALL_DIR", "~/options-trader")

# ⚠️ ONE LINE PER BOX, PARSED. Not scraped prose — s3_push prints a stable
# key=value line precisely so this can be machine-read.
DRAIN_RE = re.compile(
    r"DRAIN host=(?P<host>\S+) sym=(?P<sym>\S+) drained=(?P<drained>\S+) "
    r"pushed=(?P<pushed>\d+) failed=(?P<failed>\d+) prefixes=(?P<prefixes>\d+) "
    r"local=(?P<local>\d+) s3=(?P<s3>\d+) short=(?P<short>\d+) (?P<verdict>\S+)")


def _log(tag: str, msg: str) -> None:
    print(f"[{tag:<10}] {msg}", flush=True)


def _notify(msg: str) -> None:
    if notify is None:
        return
    try:
        notify.send(msg[:900])
    except Exception:                                           # noqa: BLE001
        pass


# ── STEP 0 — TAKE OWNERSHIP OF THE CLOSE. ──────────────────────────────────
def quiesce(symbols, dry: bool) -> None:
    """Stop every OTHER writer before the conductor touches anything.

    🔴 THE CLOSE HAS NO OWNER TODAY, AND THAT IS THE ROOT OF A WHOLE CLASS OF
    PROBLEM. At 16:05 the candle-logger fires on the boxes, the conductor
    starts on control, the s3-push timer keeps firing every five minutes, and
    eod_bot ran at 16:01 — four things acting on the same boxes and the same
    S3 prefixes with nothing arbitrating between them.

    ⚠️ THE DUPLICATE-OBJECT PROBLEM IN THE BUCKET HAS THIS SHAPE. Two objects
    for one record, same epoch-ms, same byte size, different hash, written on
    different runs. A day already pushed gets pushed again by a second writer
    and lands under a new key. Whatever makes the hash unstable is a separate
    bug — but a single writer removes the CONDITIONS it needs.

    ⚠️ STOPPING THE TIMER IS NOT STOPPING THE PUSHER. `systemctl stop
    s3-push.timer` prevents FUTURE firings; a push already in flight keeps
    running, which is why the drain below takes the same flock the timer does
    rather than assuming the field is clear.

    ⚠️ AND THE TIMER MUST COME BACK. A conductor that disarms a timer and dies
    leaves the box with no pusher until someone notices — so re-arming happens
    in a finally, not at the end of the happy path.
    """
    if dry:
        _log("QUIESCE", f"[dry] would stop s3-push.timer + candle-logger.timer "
                        f"on {len(symbols)} box(es)")
        return
    _log("QUIESCE", "stopping other writers — the conductor owns the close")
    for sym, ip, _st in fleet.get_fleet(list(symbols)):
        fleet._exec(sym, ip,
                    "sudo systemctl stop s3-push.timer candle-logger.timer "
                    "2>/dev/null; echo quiesced")


def rearm(symbols, dry: bool) -> None:
    """Put the other writers back. ALWAYS RUNS, even on failure."""
    if dry:
        _log("REARM", f"[dry] would restart s3-push.timer + candle-logger.timer")
        return
    _log("REARM", "re-arming s3-push.timer + candle-logger.timer")
    for sym, ip, _st in fleet.get_fleet(list(symbols)):
        fleet._exec(sym, ip,
                    "sudo systemctl start s3-push.timer candle-logger.timer "
                    "2>/dev/null; echo rearmed")


# ── STEP 1 — STOP TRADING. THE BOXES STAY UP. ───────────────────────────────
def stop_trading(symbols, dry: bool) -> list:
    """Stop the bot on each box. The FEED and the machine stay up.

    ⚠️ STOPPING THE BOT IS NOT STOPPING THE BOX. The distinction is the whole
    design: a stopped bot places no orders, while a live machine can still
    flush its stores and answer for what it pushed. v1.16 conflated the two
    and lost the ability to ask.

    ⚠️ THE FEED IS LEFT RUNNING ON PURPOSE. A candle that closes at 16:00 is
    still arriving at 16:05, and killing the feed here would truncate the very
    session this chain exists to preserve.
    """
    if dry:
        _log("STOP", f"[dry] would stop optionsbot on {len(symbols)} box(es)")
        return list(symbols)
    _log("STOP", f"stopping optionsbot on {len(symbols)} box(es) — "
                 f"feed and machine STAY UP")
    for sym, ip, _st in fleet.get_fleet(list(symbols)):
        rc, out, err = fleet._exec(sym, ip, "sudo systemctl stop optionsbot; echo stopped")
        if rc != 0:
            _log("STOP", f"  {sym}: rc={rc} {err.strip()[:60]}")
    return list(symbols)


# ── STEP 2 + 3 — FILL THE BUCKET, AND SAY WHAT LANDED. ──────────────────────
def drain_and_verify(symbols, dry: bool) -> dict:
    """Each box drains to S3 then reconciles its own counters against S3.

    Returns {symbol: {...parsed DRAIN line...}}.

    ⚠️ THIS IS ONE SSH ROUND TRIP, NOT TWO. `--verify` drains first and
    verifies after, so there is no window between "pushed" and "checked" for
    the 5-minute timer to slip into.

    ⚠️ IT ALWAYS EXITS 0 BY DESIGN, so a SHORT box cannot make the fleet
    runner discard the output — the very failure that made three `grep -c`
    calls report "0/29 succeeded" and throw away the counts. The VERDICT IS IN
    THE LINE, never in the exit code.
    """
    if dry:
        _log("DRAIN", f"[dry] would run s3_push --verify on {len(symbols)} box(es)")
        return {s: {"verdict": "OK", "short": "0", "dry": True} for s in symbols}

    _log("DRAIN", f"draining + verifying {len(symbols)} box(es) against S3")
    cmd = (f"cd {INSTALL_DIR} && python3 warehouse/s3_push.py --verify 2>&1 | "
           f"grep -E '^DRAIN|^  SHORT' || true")
    results = {}
    for sym, ip, _st in fleet.get_fleet(list(symbols)):
        rc, text, err = fleet._exec(sym, ip, cmd)
        m = DRAIN_RE.search(text or "")
        if not m:
            # ⚠️ NO LINE IS NOT "OK". A box that did not answer has not been
            # verified, and an unverified box is not taken down.
            results[sym] = {"verdict": "NO_ANSWER", "short": "?",
                            "raw": (text or err or "")[:200]}
            continue
        d = m.groupdict()
        d["raw"] = text
        results[sym] = d
    return results


# ── STEP 4 — TAKE DOWN, PER BOX, ONLY ON ITS OWN VERIFICATION. ──────────────
def takedown(results: dict, dry: bool, enabled: bool) -> tuple:
    """Stop the instances that verified. Leave the rest UP, and say why.

    🔴 PER BOX, NOT FLEET-WIDE. One short box must not keep fourteen good ones
    running, and fourteen good ones must not carry one short box down with
    them.
    """
    # 🔴 DRIFT IS NOT LOSS, AND HOLDING A BOX FOR DRIFT IS WORSE THAN THE BUG.
    # `--verify` already classifies its own shortfall and prints the verdict:
    # a SMALL, CONSISTENT shortfall across several prefixes is the counter-drift
    # signature (duplicate PUTs inflate the ledger permanently and the objects
    # are all present); a VARYING one is possible real loss.
    # ⚠️ AN EARLIER DRAFT HELD ON ANY short>0. Ledger drift is a known and
    # EXPECTED condition on this fleet — measured 2026-08-25, every one of 15
    # boxes carried it — so that rule would have left the whole fleet running
    # overnight, every night, for a bookkeeping artifact. A gate that fires on
    # the normal case is not a gate.
    ok, held = [], []
    for s, r in results.items():
        raw = r.get("raw") or ""
        if r.get("verdict") == "OK" and str(r.get("short")) == "0":
            ok.append(s)
        elif "COUNTER DRIFT" in raw:
            # Verified-present objects, inflated counter. Safe to take down,
            # and SAID OUT LOUD so it cannot pass unnoticed.
            _log("VERIFY", f"  {s}: shortfall is COUNTER DRIFT — objects are "
                           f"present; taking down and flagging for --reconcile")
            ok.append(s)
        else:
            held.append(s)

    if not enabled:
        _log("TAKEDOWN", f"skipped (--no-takedown) — {len(ok)} verified, "
                         f"{len(held)} short")
        return ok, held
    if dry:
        _log("TAKEDOWN", f"[dry] would stop {len(ok)} verified box(es); "
                         f"would HOLD {len(held)}")
        return ok, held

    if ok:
        # ⚠️ STOP BY INSTANCE ID, NOT BY SSH. A box whose sshd is wedged still
        # needs to come down, and the registry already holds the ids.
        _log("TAKEDOWN", f"stopping {len(ok)} verified box(es)")
        mapping, _ = instance_registry.discover(ok)
        ids = [r["instance_id"] for s, r in mapping.items()
               if s in ok and r.get("instance_id")]
        if ids:
            ec2ops.stop(ids)
            ec2ops.wait_state(ids, "stopped")
    if held:
        # ⚠️ ALERTED, NOT JUST LOGGED. A held box runs all night and costs
        # money; the operator has to learn about it this evening, not at 09:15.
        for s in held:
            r = results.get(s, {})
            _log("HELD", f"{s} — verdict={r.get('verdict')} "
                         f"short={r.get('short')} — LEFT RUNNING")
    return ok, held


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-takedown", action="store_true",
                    help="verify only; leave every box up")
    ap.add_argument("--only", default=None, help="comma-separated symbols")
    ap.add_argument("--settle", type=int, default=45,
                    help="seconds between stopping the bot and draining")
    a = ap.parse_args(argv[1:] if argv else None)

    date = datetime.now().strftime("%Y-%m-%d")
    dry = a.dry_run
    _log("START", f"EOD conductor v2 — {date}" + ("  [DRY-RUN]" if dry else ""))

    only = ([s.strip().upper() for s in a.only.split(",")] if a.only else None)
    running = [s for s, _ip, st in fleet.get_fleet(only) if st == "running"]
    if not running:
        _log("START", "no boxes running — nothing to do")
        return 0
    _log("START", f"{len(running)} box(es): {', '.join(sorted(running))}")

    # 0 ─ take ownership: no other writer touches these boxes until we are done
    # ⚠️ EVERYTHING FROM HERE IS INSIDE try/finally. The timers MUST come back
    # even if the drain raises, the SSH dies, or the operator interrupts —
    # a box left with no pusher is a box quietly not warehousing.
    quiesce(running, dry)
    try:
        return _run_close(running, date, dry, a)
    finally:
        rearm(running, dry)


def _run_close(running, date, dry, a) -> int:
    # 1 ─ stop trading
    stop_trading(running, dry)

    # ⚠️ A SETTLE PAUSE, NOT A GUESS AT COMPLETION. The bot flushes its stores
    # on shutdown; draining the instant the stop command returns can race that
    # flush. This waits, then VERIFIES — it never assumes the wait was enough.
    if not dry and a.settle:
        _log("SETTLE", f"{a.settle}s for the bots to flush their stores")
        time.sleep(a.settle)

    # 2+3 ─ fill the bucket, and answer for it
    results = drain_and_verify(running, dry)
    for sym in sorted(results):
        r = results[sym]
        _log("VERIFY", f"{sym:<6} {r.get('verdict','?'):<10} "
                       f"short={r.get('short','?')} "
                       f"local={r.get('local','?')} s3={r.get('s3','?')}")

    # 4 ─ take down what verified
    ok, held = takedown(results, dry, not a.no_takedown)

    # ── P&L, FROM THE WAREHOUSE, AFTER THE BOXES ARE OFF ────────────────
    # 🔴 THE OLD CHAIN COMPUTED P&L TWICE: eod_summary on each box at 15:50 and
    # eod_report on control at 16:15. Two answers to one question, and if they
    # disagreed nothing noticed. One source now, and it reads S3 — so it works
    # with every box already stopped, which is the whole point.
    if not dry:
        try:
            import pnl_s3
            dates = [date]
            per_day, per_sym, tot = pnl_s3.collect(dates)
            text = pnl_s3.render(dates, per_day, per_sym, tot)
            print(text.replace("*", "").replace("`", ""))
            _notify(text)
        except Exception as exc:                               # noqa: BLE001
            # ⚠️ A P&L FAILURE MUST NOT MASK THE CLOSE. The takedown already
            # happened and its verdict is the important one; this says the
            # report failed rather than pretending the day was flat.
            _log("PNL", f"warehouse P&L unavailable: {exc}")
            _notify(f"⚠️ EOD {date}: boxes closed, but the warehouse P&L "
                    f"could not be read: {exc}")

    _log("DONE", f"{len(ok)} verified and stopped · {len(held)} HELD UP")
    if held and not dry:
        _notify(f"⚠️ EOD {date}: {len(held)} box(es) HELD UP — data not "
                f"verified in S3: {', '.join(sorted(held))}. They are still "
                f"running.")
    elif not dry:
        _log("DONE", f"all {len(ok)} box(es) verified against S3 and stopped")
    # ⚠️ NON-ZERO ONLY WHEN A BOX IS HELD. A held box is the one condition that
    # needs a human tonight.
    return 1 if held else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
