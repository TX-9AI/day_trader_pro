#!/usr/bin/env python3
"""
day_trader_pro/eod_conductor_v2.py — v2.3
STOP TRADING → FILL THE BUCKET → VERIFY IT LANDED → TAKE THEM DOWN.

v2.3    2026-09-05  🔴 `head -3` ATE THE CAUSE OF EVERY PURGE FAILURE. The phase
        piped the remote purge through `head -3`, which was sized for the old
        one-line summary. On 2026-09-05 four boxes raised inside the purge and
        all the operator saw was `Traceback (most recent call last): | File
        ".../retention_purge.py", line 598, in <mo` — the OUTERMOST frame, with
        the exception type and the raising line cut off. It cost three round
        trips to learn it was `database is locked` on `DELETE FROM candles`.
        ⚠️ A TRACEBACK PUTS ITS CAUSE LAST, so `tail` is the only correct end
        of the pipe. And the reclaim line prints AFTER the deletion counts, so
        `head` guaranteed the checkpoint verdict was invisible on every box,
        every night — the one line that says whether a 1.6 GB WAL came back.
        ⚠️ THE PARTIAL-PURGE EXIT CODE IS READ (r256 returns 4). "removed 1,452
        rows" and "removed 1,452 rows and failed on four tables" are different
        facts, and only one needs an operator; the phase now says PARTIAL per
        box rather than letting it read as done.

v2.2    2026-09-05  RELEASE THE STORES BEFORE RECLAIMING THEM. The purge has
        run since v2.1 with `optionsbot` and `candle-feed` STILL RUNNING, and
        that is fine for deleting rows and fatal for getting the space back.
        🔴 MEASURED, NOT REASONED (otv4 tests/check_purge_reclaim.py R2/R2b):
        `wal_checkpoint(TRUNCATE)` returns **busy** while any other connection
        holds a read mark, and the WAL is only partly reclaimed — 7.1MB fell to
        4.4MB with a reader open and to 0 with none. That is almost certainly
        why MU carried a **1.6 GB `feed_store.db-wal`** beside a 2.3 GB store on
        2026-09-05, with META at 1.1 GB and AMD at 963 MB.
        `stop_services()` stops both units on the VERIFIED list only, between
        the verdict and the purge.
        ⚠️ ON `ok` ONLY, NEVER ON `held`. A held box is up for the operator to
        troubleshoot (his 2026-08-25 ruling), and it keeps everything until its
        next wake proves the push — taking its writers down would change what he
        is looking at.
        ⚠️ AFTER THE DRAIN, NOT BEFORE. Stopping first would make the drain
        cleaner still, but it would stop services on boxes that then get HELD,
        and a held box left with its services down is a different state from the
        one the ruling describes. The drain is unchanged; only the reclaim
        needed the release.
        ⚠️ AND IT NEVER BLOCKS THE HALT — a failed stop is logged and stepped
        over, the same rule the purge already follows: a box left running all
        night costs money and a large file does not.

v2.1    2026-08-27  THE RETENTION PURGE IS A CONDUCTOR PHASE. It was called
from warehouse/self_close.py, which fires at 16:45 — but this conductor stops
the boxes by ~16:08, so on any NORMAL night that timer fired into a stopped
machine and THE PURGE NEVER RAN. It executed only on nights the conductor had
already failed. Two months of "dry runs" were therefore also two months of no
runs at all: feed_store.db reached 1.5-1.8 GB per box, the 6.7 GiB roots hit
100%, and the fleet went blind MID-SESSION on 2026-08-27. `purge_verified()`
now runs inside takedown(), AFTER the verified list is built and BEFORE
ec2ops.stop() — the operator's words: "immediately after the s3 drain is
confirmed & BEFORE the go down command." It runs on `ok` ONLY, so a HELD box is
never purged and no day is deleted while it exists only locally. It reports the
row count PER BOX and shouts if a run comes back dry, because the original
failure was a log line that never changed. It never blocks the halt, and it does
NOT vacuum — that stalls the shutdown for minutes and is a manual operation.
Pinned by tests/check_conductor_purge.py (C2/C3 mutation-proven).

v2.0.1  2026-08-23  AUDIT F7: the COUNTER-DRIFT exception in takedown() was
DEAD CODE. drain_and_verify filtered the box's output with
`grep -E '^DRAIN|^  SHORT'`; the drift line s3_push prints begins
`  ⚠️ SMALL, CONSISTENT SHORTFALL…`, which matches neither, so "COUNTER DRIFT"
never reached `raw` and every drifted box was HELD — the exact overnight-fleet
outcome the v2.0.0 docstring says an earlier draft was rewritten to avoid.
Meanwhile otv4's self_close reads the FULL output and halts on the same
signal, so the two close paths disagreed despite sharing one verifier. The
filter now keeps the drift/variance lines too. Fail direction unchanged: a
box with no parseable DRAIN line is still NO_ANSWER and still held.

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
import ssh_util                                                 # noqa: E402
try:
    import notify                                               # noqa: E402
except Exception:                                               # noqa: BLE001
    notify = None

INSTALL_DIR = getattr(config, "INSTALL_DIR", "~/options-trader")

# ⚠️ A DRAIN+VERIFY IS MINUTES OF WORK, NOT SECONDS. Generous on purpose: the
# cost of waiting is a slower close, the cost of timing out is a box held up
# for a transport failure that looks exactly like a data failure.
VERIFY_TIMEOUT_S = int(os.environ.get("DTP_VERIFY_TIMEOUT", "900"))

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
    # v2.0.1 — F7: the drift/variance verdict lines MUST survive the filter,
    # or takedown()'s drift exception can never fire. Keep the whole verdict
    # block: the DRAIN line, the SHORT samples and the two-space diagnosis.
    cmd = (f"cd {INSTALL_DIR} && python3 warehouse/s3_push.py --verify 2>&1 | "
           f"grep -E '^DRAIN|^  ' || true")
    results = {}
    # 🔴 THE DEFAULT SSH TIMEOUT KILLS THIS. `ssh_util.ssh_run` uses
    # SSH_CONNECT_TIMEOUT (12s) + 10 = 22 SECONDS, and `--verify` walks 200+
    # prefixes against S3 — MINUTES of work. Measured 2026-08-23: NVDA came
    # back NO_ANSWER because the transport gave up, not because the box failed.
    # ⚠️ THE VERDICT LOGIC WAS RIGHT AND THE TRANSPORT WAS WRONG, which is the
    # worse shape: a timeout is INDISTINGUISHABLE from a silent box, so it
    # correctly refused to take a box down for a reason that did not exist.
    # ⚠️ AND THE OPERATOR'S STANDING RULE ALREADY SAID SO — "`--verify` must NOT
    # go through option 14" names this exact ceiling. I built on fleet._exec
    # without carrying the constraint across.
    for sym, ip, _st in fleet.get_fleet(list(symbols)):
        rc, text, err = ssh_util.ssh_run(ip, cmd, timeout=VERIFY_TIMEOUT_S)
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
def stop_services(ok: list, dry: bool) -> dict:
    """Stop the writers on the verified boxes, so the reclaim can do its job.

    🔴 WHY IT EXISTS (v2.2). `retention_purge` checkpoints and vacuums, and
    BOTH are blocked by a live connection: `wal_checkpoint(TRUNCATE)` returns
    busy while another connection holds a read mark and the WAL is only partly
    reclaimed. Measured in otv4 `tests/check_purge_reclaim.py` R2/R2b — 7.1MB
    to 4.4MB with a reader, 7.1MB to 0 without. The fleet's evidence is MU's
    1.6 GB `feed_store.db-wal` beside a 2.3 GB database.

    ⚠️ `ok` ONLY. A HELD box keeps its services, because it is up for the
    operator to look at and its data is still the only copy.
    ⚠️ NEVER BLOCKS THE HALT. A stop that fails is logged and stepped over.
    ⚠️ NOT `disable` — the units must come back on the next wake. This stops
    the RUNNING service and touches nothing about whether it starts again.
    """
    out = {}
    if not ok:
        return out
    if dry:
        _log("STOP", f"[dry] would stop optionsbot + candle-feed on "
                     f"{len(ok)} verified box(es) before the purge")
        return out
    _log("STOP", f"releasing the stores on {len(ok)} verified box(es)")
    cmd = ("sudo systemctl stop optionsbot candle-feed 2>&1; "
           "echo STOPPED $(systemctl is-active optionsbot) "
           "$(systemctl is-active candle-feed)")
    for sym, ip, _st in fleet.get_fleet(list(ok)):
        rc, text, err = ssh_util.ssh_run(ip, cmd, timeout=VERIFY_TIMEOUT_S)
        line = (text or err or "").strip().replace("\n", " | ")
        out[sym] = line
        _log("STOP", f"  {sym}: {line or 'no output'}")
    return out


def purge_verified(ok: list, dry: bool) -> dict:
    """Retention purge on the boxes that VERIFIED, before they are stopped.

    🔴 OPERATOR, 2026-08-27: *"It needs to be immediately after the s3 drain is
    confirmed & BEFORE the go down command."*

    ⚠️ WHY IT HAS TO LIVE HERE AND NOT IN `self_close`. The purge WAS called
    from `warehouse/self_close.py`, which fires at **16:45** — but the conductor
    stops the boxes by ~**16:08**, so on any normal night the 16:45 timer fires
    into a stopped machine and the purge NEVER RUNS. It ran only on nights the
    conductor failed. That is why two months of dry runs also happened to be two
    months of no runs at all, and why the fleet reached 100% disk and went blind
    mid-session on 2026-08-27.
    ⚠️ THIS IS THE OPERATOR'S STANDING RULE, RESTATED: anything that must happen
    before the boxes go down is a CONDUCTOR PHASE, never a separate timer and
    never a manual step.

    ⚠️ ORDERING IS THE SAFETY PROPERTY. It runs on `ok` — the list `takedown()`
    just built from boxes whose data is CONFIRMED IN S3 — so nothing is ever
    deleted from a box whose day is still only local. A HELD box is not purged;
    it keeps everything until its next wake proves the push.

    ⚠️ AND IT NEVER BLOCKS THE HALT. A purge failure is logged and stepped over;
    the box still comes down, because a box left running all night costs money
    and a large file does not.

    🔴 v2.2 — THE RECLAIM NOTE THAT STOOD HERE WAS WRONG AND IS REPLACED. It
    read "SQLite reuses freed pages and the store reaches steady state", which
    is true and not the same as the space coming back: steady state is a plateau
    at the HIGH-WATER MARK. Measured fleet-wide 2026-09-05, every `feed_store`
    carried 18-34% free pages while four boxes ran out of disk. The reclaim now
    lives in `retention_purge` — one implementation, both close paths — and it
    is GATED on free disk exceeding the live size, with `SQLITE_TMPDIR` on the
    data directory because `/tmp` is a 476M tmpfs and a 1.8G rewrite cannot fit
    in it (learned on MU, NVDA and QQQ, 2026-08-27).
    ⚠️ THIS PHASE STILL RUNS NOTHING OF ITS OWN. A second reclaim here would be
    two answers to one question and would bypass that gate.
    """
    out = {}
    if not ok:
        return out
    if dry:
        _log("PURGE", f"[dry] would purge {len(ok)} verified box(es) "
                      f"before takedown")
        return out
    _log("PURGE", f"retention purge on {len(ok)} verified box(es)")
    # 🔴 v2.3 — `tail`, NOT `head`. A traceback puts its cause LAST, and the
    # reclaim verdict prints after the deletion counts, so `head -3` truncated
    # both — the checkpoint result was invisible every night and a failure
    # showed only its outermost frame. 12 lines covers a summary plus a real
    # exception; the purge's own output is bounded.
    # ⚠️ REDIRECTED, NOT PIPED — `echo rc=$?` after a pipeline reports TAIL's
    # exit code, not the purge's, which is the swallowed-exit-code trap this
    # project already names for pytest. The full output also stays on the box
    # for a follow-up read, which is what `head -3` made impossible.
    cmd = (f"cd {INSTALL_DIR} && python3 warehouse/retention_purge.py "
           f"--apply > /tmp/retention_purge.out 2>&1; rc=$?; "
           f"tail -12 /tmp/retention_purge.out; echo rc=$rc")
    for sym, ip, _st in fleet.get_fleet(list(ok)):
        rc, text, err = ssh_util.ssh_run(ip, cmd, timeout=VERIFY_TIMEOUT_S)
        line = (text or err or "").strip().replace("\n", " | ")
        out[sym] = line
        # ⚠️ SAY WHAT WAS REMOVED, PER BOX. The two-month failure was a log line
        # that never changed; a per-box row count is the thing that would have
        # made "WOULD remove" visible on night one.
        _log("PURGE", f"  {sym}: {line[:120] or 'no output'}")
        if "WOULD remove" in line:
            _log("PURGE", f"  ⚠️ {sym}: PURGE RAN DRY — nothing was deleted. "
                          f"The store will keep growing.")
    return out


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

    # ── 🔴 v2.2 — RELEASE THE STORES, THEN PURGE, THEN HALT ─────────────
    # The order is the whole point: a checkpoint cannot truncate a WAL that a
    # live connection is holding, so the reclaim inside the purge is worth
    # whatever the bot and the feed have let go of.
    stop_services(ok, dry)

    # ── 🔴 PURGE BEFORE THE HALT, ON THE VERIFIED LIST ONLY ─────────────
    # Operator, 2026-08-27: *"immediately after the s3 drain is confirmed &
    # BEFORE the go down command."* `ok` is exactly that list.
    purge_verified(ok, dry)

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

    # ── P&L headline, before the full report run ────────────────────────
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

    # ── 5 ─ THE REPORTS, ORDERED, NOT TIMED ─────────────────────────────
    # 🔑 THE CONDUCTOR KNOWS WHEN THE CLOSE IS DONE, so it starts the reports
    # itself. An earlier version left them on a 16:30 timer with a 25-minute
    # gap "so a slow report cannot delay the close" — but ORDERING already
    # guarantees that: the reports begin AFTER takedown, when the close is
    # finished by definition. The gap was a clock standing in for a dependency.
    # ⚠️ IF CONTROL IS DISABLED, NO REPORTS RUN — and that is correct. Reports
    # are a control function; the BOXES still close themselves at 16:45 on
    # their own timer, which is the part that must not depend on control.
    # ⚠️ A REPORT FAILURE MUST NOT CHANGE THE CLOSE'S VERDICT. The takedown
    # already happened and its result is the one that matters, so this is
    # wrapped and its rc is not propagated.
    if not dry:
        try:
            import eod_analysis
            _log("REPORTS", "starting the analysis run (reads S3; boxes are off)")
            eod_analysis.run(date, dry=False)
        except Exception as exc:                               # noqa: BLE001
            _log("REPORTS", f"analysis failed: {exc}")
            _notify(f"⚠️ EOD {date}: the close completed, but the report run "
                    f"failed: {exc}. Re-run devtools item 56 — it reads S3 and "
                    f"is safe to run any time.")

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
