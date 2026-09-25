#!/usr/bin/env python3
"""
day_trader_pro/tools/fleet_power_audit.py  v1.1

v1.1  2026-09-25  r425 / OPS.49 — SELF-EXPIRING ACKNOWLEDGEMENTS, so a box that
      is up ON PURPOSE stops nagging without anyone muting the watcher.
      🔴 BUILT THE NIGHT v1.0 SHIPPED, because v1.0's first real run flagged two
      brand-new boxes the operator had just attached deliberately and would have
      repeated it hourly until 08:00 ET. An alert that fires ~12 times for a
      known-good condition is how a true alert gets ignored — §17, and the whole
      reason ALERT_SPEC exists in this repo.
      🔑 AN ACK IS DATED AND DIES BY ITSELF. It covers one ET day, so the
      quietening is never permanent and nobody has to remember to undo it; an
      expired ack is IGNORED AND SAID OUT LOUD rather than silently dropped,
      because "why did this stop alerting" must always have an answer on screen.

v1.0  2026-09-24  r424 / OPS.48 — WHO IS STILL UP, AND WHO LEFT THEM THAT WAY.

  🔴 THIS IS THE HALF THAT WOULD HAVE CAUGHT THE INCIDENT. On 2026-09-24 an
  agent woke SPX for a one-minute diagnostic, ran four commands against it and
  moved on; the box sat running for 2h40m after the conductor had already
  closed the day, and nothing anywhere noticed. The ledger in ec2ops answers
  "who started it" AFTER someone thinks to ask. This answers "is anything up
  that should not be" WITHOUT anyone asking, which is the difference between a
  record and a control.

  🔑 THE RULE IT ENFORCES: a box woken outside the conductor's cycle is the
  responsibility of whoever woke it, and stays visible until it is stopped.

  ⚠️ §0.5 — IT NAMES WHAT IT CANNOT SEE. The ledger only records power changes
  that went through ec2ops. A box started from the AWS console, from another
  identity, or by anything that never imported ec2ops leaves NO row, and this
  tool says so explicitly rather than reporting a confident "started by:
  unknown". An audit that cannot distinguish "nobody started it" from "I cannot
  see who started it" is the plausible-silence class this repo keeps paying for.

Exit codes:  0 = nothing running out of window   1 = orphan(s) found
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import config          # noqa: E402
import ec2ops          # noqa: E402

try:
    import ettime      # noqa: E402
except Exception:      # noqa: BLE001
    ettime = None

# The conductor closes the day at 16:05 ET. Anything still up well after that,
# on a day the fleet was meant to be down, is what we are hunting.
RTH_OPEN_MIN = 9 * 60 + 15      # 09:15 ET — the orchestrator's wake
RTH_DONE_MIN = 16 * 60 + 30     # 16:30 ET — conductor has had time to finish

ACK_PATH = os.environ.get(
    "OT_POWER_ACK", os.path.join(ROOT, "logs", "power_ack.txt"))

ROW = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ET\s+"
    r"(?P<action>START|STOP)(?P<mock>\s+MOCK)?\s+(?P<ids>\S+)\s+"
    r"caller=(?P<caller>\S+)\s+pid=(?P<pid>\d+)\s+argv=(?P<argv>.*)$")


def _now_et():
    if ettime is not None:
        return ettime.now_et()
    import datetime
    from zoneinfo import ZoneInfo
    return datetime.datetime.now(ZoneInfo("America/New_York"))


def read_acks(path, today):
    """-> ({symbol: reason} live today, [(symbol, day) expired]).

    Format, one per line:  SYMBOL  YYYY-MM-DD  free-text reason
    ⚠️ An ack for a PAST day is not silently discarded — it is returned so the
    audit can say it lapsed. A suppression that vanishes without a word is the
    same failure as an alert that never fires.
    """
    live, expired = {}, []
    if not os.path.exists(path):
        return live, expired
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            parts = line.split(None, 2)
            if len(parts) < 2:
                continue
            sym, day = parts[0].upper(), parts[1]
            reason = parts[2] if len(parts) > 2 else ""
            if day >= today:
                live[sym] = f"{day} {reason}".strip()
            else:
                expired.append((sym, day))
    return live, expired


def read_ledger(path):
    """-> {instance_id: [rows]} newest last. Missing file is NOT an error."""
    by_id = {}
    if not os.path.exists(path):
        return by_id, False
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = ROW.match(line.strip())
            if not m:
                continue
            for iid in m.group("ids").split(","):
                by_id.setdefault(iid, []).append(m.groupdict())
    return by_id, True


def last_power_event(rows):
    """The most recent START with no STOP after it, else None."""
    if not rows:
        return None
    last = rows[-1]
    return last if last["action"] == "START" else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--log", default=ec2ops.POWER_LOG, help="power ledger path")
    ap.add_argument("--quiet", action="store_true",
                    help="print only when something is wrong (timer-friendly)")
    ap.add_argument("--in-window-ok", action="store_true",
                    help="treat 09:15-16:30 ET as expected-up (default)")
    ap.add_argument("--notify", action="store_true",
                    help="send a Telegram alert when a box is up out of window")
    ap.add_argument("--ack", metavar="SYM[,SYM]",
                    help="acknowledge boxes as intentionally up FOR TODAY (ET)")
    ap.add_argument("--ack-reason", default="", help="why, recorded with --ack")
    ap.add_argument("--ack-file", default=ACK_PATH, help="acknowledgement file")
    a = ap.parse_args(argv)

    now = _now_et()
    today = f"{now:%Y-%m-%d}"

    if a.ack:
        d = os.path.dirname(a.ack_file)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(a.ack_file, "a", encoding="utf-8") as fh:
            for sym in [x.strip().upper() for x in a.ack.split(",") if x.strip()]:
                fh.write(f"{sym} {today} {a.ack_reason}\n".rstrip() + "\n")
                print(f"  acknowledged {sym} for {today} ET"
                      + (f" — {a.ack_reason}" if a.ack_reason else ""))
        print("  (acks cover ONE ET day and expire by themselves)")
        return 0

    minutes = now.hour * 60 + now.minute
    weekday = now.weekday() < 5
    in_window = weekday and RTH_OPEN_MIN <= minutes <= RTH_DONE_MIN

    config.MOCK_AWS = False
    fleet = ec2ops.describe_by_tag()
    running = {s: r for s, r in fleet.items()
               if isinstance(r, dict) and r.get("state") == "running"}

    ledger, ledger_exists = read_ledger(a.log)
    acks, expired = read_acks(a.ack_file, today)

    orphans, unexplained, acked = [], [], []
    for sym in sorted(running):
        iid = running[sym].get("instance_id", "")
        ev = last_power_event(ledger.get(iid, []))
        if in_window:
            continue                      # expected up; nothing to say
        if sym in acks:
            acked.append((sym, acks[sym]))
            continue
        if ev is None:
            unexplained.append((sym, iid))
        else:
            orphans.append((sym, iid, ev))

    # 🔴 `orphans or unexplained` WAS WRONG AND UNDERCOUNTED. Python's `or`
    # returns the FIRST TRUTHY OPERAND, so with 1 orphan and 1 unexplained box
    # this reported "1 box(es)" while printing two — a number that is correct
    # about the wrong object, which is OPS.43's exact shape and the hardest
    # kind to catch because nothing about it reads as broken.
    bad = orphans + unexplained
    if a.quiet and not bad:
        return 0

    print(f"fleet power audit — {now:%Y-%m-%d %H:%M} ET "
          f"({'INSIDE' if in_window else 'OUTSIDE'} the 09:15-16:30 ET window)")
    print(f"  fleet {len(fleet)} box(es) · running {len(running)}"
          + (f" · {', '.join(sorted(running))}" if running else ""))
    if not ledger_exists:
        print(f"  ⚠️  no ledger at {a.log} — it is written on the first power "
              f"change through ec2ops; nothing here is attributable yet")

    for sym, why in acked:
        print(f"  \u2713 {sym} running, ACKNOWLEDGED for today ({why})")
    for sym, day in expired:
        print(f"  \u26a0\ufe0f  ack for {sym} LAPSED on {day} — it covers one ET "
              f"day and is no longer suppressing anything")

    if in_window:
        print("  inside the trading window — running boxes are expected")
        return 0

    for sym, iid, ev in orphans:
        print(f"  🔴 {sym} ({iid}) STILL RUNNING, no stop since it was woken")
        print(f"       started {ev['ts']} ET by caller={ev['caller']} "
              f"pid={ev['pid']}")
        print(f"       argv: {ev['argv'][:140]}")
    for sym, iid in unexplained:
        print(f"  🔴 {sym} ({iid}) STILL RUNNING — and NOT IN THE LEDGER.")
        print("       Nothing that went through ec2ops started it: an AWS "
              "console start, another identity, or a path that bypasses the")
        print("       chokepoint. This is a gap in what the ledger can see, "
              "not proof that nobody started it.")

    if bad:
        print(f"\n  {len(bad)} box(es) running outside the window. Stop them, or "
              f"record why they are up.")
        if a.notify:
            # 🔑 A WATCHER, NOT A STATUS SCREEN. r422 built a footprint report
            # and DROPPED it for exactly this reason: a report you must
            # remember to open is the wrong shape for a failure that gives no
            # warning. The same logic that made the crash-loop sentinel push to
            # the phone applies here.
            try:
                # 🔴 A TEST OF AN ALERT PATH MUST NEVER REACH A REAL PHONE.
                # Proven the hard way on 2026-09-24: exercising --notify from a
                # heredoc sent a live Telegram with fabricated box names,
                # because notify._in_test() infers test-ness from argv[0] and a
                # heredoc's argv[0] is "-". The repo already HAS an explicit
                # switch (DTP_NOTIFY_CAPTURE=1) and I relied on inference
                # instead — §17, and the second time tonight I assumed a
                # mechanism rather than reading it.
                import notify
                lines = [f"\U0001F534 FLEET POWER — {len(bad)} box(es) up "
                         f"outside the window ({now:%H:%M} ET)"]
                for sym, iid, ev in orphans:
                    lines.append(f"\u2022 {sym} woken {ev['ts']} ET by "
                                 f"{ev['caller']} \u2014 never stopped")
                for sym, iid in unexplained:
                    lines.append(f"\u2022 {sym} running, NOT in the ledger "
                                 f"(console start or a path that bypasses ec2ops)")
                lines.append("Stop them, or record why they are up.")
                notify.send("\n".join(lines))
                print("  \u2705 notified")
            except Exception as exc:                           # noqa: BLE001
                # \u26a0\ufe0f NEVER let the alert path hide the finding: the
                # console output above is the primary record and stands whether
                # or not Telegram was reachable.
                print(f"  \u26a0\ufe0f notify failed ({type(exc).__name__}: {exc}) "
                      f"\u2014 the finding above still stands")
        return 1
    print("  nothing running outside the window")
    return 0


if __name__ == "__main__":
    sys.exit(main())
