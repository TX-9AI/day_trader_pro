# day_trader_pro/eod_backfill.py — v1.1.1
# v1.1.1 (2026-07-23) — correct stale data/harvest path references (layout retired; now reports/ + ohlc/ + trades/)
# v1.1.0 (2026-07-11) — canonical layout: reads/writes ohlc/<date>/<SYM>_ohlc_<date>.csv
#   (was data/harvest/). Detection accepts legacy _OHLC_ too.
"""
EOD candle backfill for sat-out symbols.

Stream capacity caps live trading at ~N boxes/day, so the symbols that sat out
never wrote their 1-min OHLC — leaving gaps in the tape the regime diary needs.
This walks the day's harvest folder, finds which symbols are MISSING their CSV,
and brings them up in small capacity-safe batches to fetch the candles:

  detect missing  →  for each batch of --batch symbols:
      wake  →  produce (pull_today_ohlc.sh: candle_feed --once from 09:30)
            →  poll --check until bars land
            →  pull the CSV to ohlc/<date>/<SYM>_ohlc_<date>.csv
            →  stop the batch (wait 'stopped' so streams + vCPU are freed)
  →  next batch, until every symbol's candles are on the control server.

Missing = symbol in config.UNIVERSE whose ohlc/<date>/<SYM>_ohlc_<date>.csv
is absent or has 0 data rows. Each symbol is attempted once; anything still short
or missing at the end is reported (e.g. DXFeed history gone if run next-day).

Capacity guard: refuses to start if (bot boxes already running) + --batch would
exceed --stream-cap (default 10), so it can't blow the DXFeed cap or the 32-vCPU
ceiling. Because each batch is stopped before the next starts, only one batch's
worth of streams is ever open.

CLI:
  python eod_backfill.py                              # today, batch 5, cap 10
  python eod_backfill.py --date 2026-07-10 --batch 5
  python eod_backfill.py --dry-run                     # show missing + the batch plan
  python eod_backfill.py --only IWM,SPX,MU             # limit to specific missing syms
  python eod_backfill.py --stream-cap 10               # your concurrent-stream ceiling
"""

import argparse
import os
import re
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import config
import ec2ops
import instance_registry
import ssh_util

_ET = ZoneInfo("US/Eastern")
REMOTE_REPO = "options-trader"
PRODUCE_CMD = f"bash ~/{REMOTE_REPO}/pull_today_ohlc.sh"
CHECK_CMD   = f"bash ~/{REMOTE_REPO}/pull_today_ohlc.sh --check"

SSH_READY_TIMEOUT = 150      # s to wait for a booted box to answer SSH
PRODUCE_TIMEOUT   = 210      # s to wait for a box to write its CSV
POLL_EVERY        = 15       # s between --check polls
FULL_SESSION_BARS = 380      # soft "complete" threshold (RTH ≈ 390)

# 2026-08-03 — the "is it missing?" test was `bars <= 0`, i.e. ANY content counted
# as present. A failed DXFeed fetch writes a HEADER-ONLY csv, so a symbol whose
# backfill returned nothing looked harvested. Found because LLY sat at 2 lines
# (header + one bar) and was never in the missing list, while seven header-only
# files from the same night were.
# WHY NOT REUSE FULL_SESSION_BARS (380) HERE: that is the COMPLETE threshold. Using
# it in _missing would flag every partial session as missing and re-fetch the fleet
# nightly. This floor only has to separate a PHANTOM from a short-but-real session.
# Measured over the banked tape: real sessions run min 48 / p10 241 / p50 391 bars.
# Nothing genuine has ever landed under 48; every phantom is 0-1. Ten is clear of
# both edges by a wide margin, so it cannot reclassify a session we have seen.
MIN_REAL_BARS = 10

_BARS_RE = re.compile(r"(\d+)\s+bars")


def _today_et():
    return datetime.now(_ET).strftime("%Y-%m-%d")


def _csv_bars(path):
    """Data rows in an OHLC csv (minus header); -1 if the file is absent."""
    if not os.path.exists(path):
        return -1
    try:
        with open(path) as fh:
            return max(0, sum(1 for _ in fh) - 1)
    except OSError:
        return -1


def _missing(date, only=None):
    day_dir = os.path.join(config.OHLC_DIR, date)
    uni = config.UNIVERSE if not only else [s for s in config.UNIVERSE if s in only]
    def _bars(s):
        lo = _csv_bars(os.path.join(day_dir, f"{s}_ohlc_{date}.csv"))
        up = _csv_bars(os.path.join(day_dir, f"{s}_OHLC_{date}.csv"))
        return max(lo, up)
    return [s for s in uni if _bars(s) < MIN_REAL_BARS]


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def _log(tag, msg):
    print(f"[{tag:<8}] {msg}", flush=True)


def _ssh_ok(ip):
    rc, _o, _e = ssh_util.ssh_run(ip, "echo OK")
    return rc == 0


def _wake(group, mapping, dry):
    """Start the group's boxes, wait for 'running', then wait for SSH. Returns the
    refreshed {sym: rec} for the group (IPs can change across stop/start)."""
    ids = [mapping[s]["instance_id"] for s in group
           if mapping.get(s, {}).get("instance_id")]
    if dry:
        _log("WAKE", f"[dry] would start {group}")
        return {s: mapping.get(s, {}) for s in group}
    _log("WAKE", f"starting {len(ids)} box(es): {', '.join(group)}")
    ec2ops.start(ids)
    ec2ops.wait_state(ids, "running")
    fresh, _ = instance_registry.discover(config.UNIVERSE)
    mapping.update(fresh)
    # wait for SSH on each
    deadline = time.time() + SSH_READY_TIMEOUT
    pending = set(group)
    while pending and time.time() < deadline:
        for s in list(pending):
            ip = mapping.get(s, {}).get("private_ip", "")
            if ip and _ssh_ok(ip):
                pending.discard(s)
        if pending:
            time.sleep(POLL_EVERY)
    if pending:
        _log("WAKE", f"⚠ SSH not ready: {', '.join(sorted(pending))}")
    return {s: mapping.get(s, {}) for s in group}


def _produce(recs, dry):
    for s, rec in recs.items():
        ip = rec.get("private_ip", "")
        if dry:
            _log("PRODUCE", f"[dry] would run pull_today_ohlc.sh on {s}")
            continue
        if not ip:
            continue
        ssh_util.ssh_run(ip, PRODUCE_CMD)          # detaches on the box, returns fast
    if not dry:
        _log("PRODUCE", f"fired on {len(recs)} box(es); polling for bars…")


def _poll_bars(recs, dry):
    """Poll each box's --check until it reports bars or PRODUCE_TIMEOUT. Returns
    {sym: bars_seen_on_box}."""
    if dry:
        return {s: FULL_SESSION_BARS for s in recs}
    got = {}
    deadline = time.time() + PRODUCE_TIMEOUT
    pending = {s: rec.get("private_ip", "") for s, rec in recs.items()}
    while pending and time.time() < deadline:
        for s, ip in list(pending.items()):
            if not ip:
                got[s] = -1
                pending.pop(s)
                continue
            rc, out, _e = ssh_util.ssh_run(ip, CHECK_CMD)
            if rc == 0 and "✅" in out:
                m = _BARS_RE.search(out)
                got[s] = int(m.group(1)) if m else 0
                pending.pop(s)
        if pending:
            time.sleep(POLL_EVERY)
    for s in pending:                              # timed out
        got.setdefault(s, 0)
    return got


def _pull(recs, date, day_dir, dry):
    """scp each box's CSV into the shared dated folder. Returns {sym: local_bars}."""
    out = {}
    for s, rec in recs.items():
        local = os.path.join(day_dir, f"{s}_ohlc_{date}.csv")
        if dry:
            _log("PULL", f"[dry] would scp {s} OHLC -> {local}")
            out[s] = FULL_SESSION_BARS
            continue
        ip = rec.get("private_ip", "")
        if not ip:
            out[s] = -1
            continue
        remote = f"{REMOTE_REPO}/data/OHLC/{date}/{s}.csv"
        ssh_util.scp_pull(ip, remote, local)
        out[s] = _csv_bars(local)
    return out


def _stop(recs, dry):
    ids = [rec.get("instance_id") for rec in recs.values() if rec.get("instance_id")]
    if dry:
        _log("STOP", f"[dry] would stop {list(recs)}")
        return
    _log("STOP", f"stopping {len(ids)} box(es): {', '.join(recs)}")
    ec2ops.stop(ids)
    ec2ops.wait_state(ids, "stopped")              # ensure streams/vCPU are freed


def run(date=None, batch=5, stream_cap=10, only=None, dry=False):
    date = date or _today_et()
    day_dir = os.path.join(config.OHLC_DIR, date)
    os.makedirs(day_dir, exist_ok=True)
    only_set = set(only) if only else None

    missing = _missing(date, only_set)
    total = len(config.UNIVERSE if not only_set else only_set)
    if not missing:
        print(f"✅ {date}: nothing to backfill — all targeted symbols already have candles.")
        return 0

    mapping, _err = instance_registry.discover(config.UNIVERSE)

    # Pre-flight capacity check: bot boxes already running must leave room for a batch.
    baseline = sum(1 for r in mapping.values() if r.get("state") == "running")
    print(f"{date}: {len(missing)}/{total} symbols missing candles: "
          f"{', '.join(missing)}")
    # name the phantoms explicitly — a header-only file is not the same problem as
    # a symbol that never wrote anything, and the distinction is invisible from
    # the count alone
    phantoms = [s for s in missing
                if 0 < _csv_bars(os.path.join(config.OHLC_DIR, date,
                                              f"{s}_ohlc_{date}.csv")) < MIN_REAL_BARS]
    if phantoms:
        print(f"  ({len(phantoms)} of those have a PHANTOM file — content but "
              f"< {MIN_REAL_BARS} bars: {', '.join(phantoms)})")
        # 2026-08-04 — name the CAUSE, not just the symptom. A header-only csv
        # from the RTH guard and one from a dead DXFeed fetch look identical
        # here, and they have opposite responses: re-run after the close vs
        # investigate entitlement. pull_today_ohlc v1.3 makes the first case
        # rebuild instead of writing a phantom, so a phantom on a POST-CLOSE run
        # now means something genuinely failed.
        print("   cause: a phantom written DURING RTH is the pull script's "
              "guard (pre-v1.3 it\n"
              "   refused the rebuild on any live feed, cold store or not) — "
              "re-run after 16:00 ET.\n"
              "   A phantom from a POST-CLOSE run is a real fetch failure: "
              "check the box's\n"
              "   pull_today_ohlc.log for entitlement or DXFeed reach.")
    print(f"plan: batches of {batch}, stream cap {stream_cap}, "
          f"{baseline} bot box(es) currently running")
    if baseline + batch > stream_cap:
        print(f"🚨 capacity: {baseline} running + a {batch}-box batch exceeds the "
              f"{stream_cap} stream cap. Stop {baseline + batch - stream_cap} box(es) "
              f"first (e.g. today's trading boxes), then re-run.")
        return 2

    batches = list(_chunks(missing, batch))
    if dry:
        for i, g in enumerate(batches, 1):
            print(f"  batch {i}/{len(batches)}: {', '.join(g)}")
        print("(dry-run — no instances touched)")
        return 0

    fetched, short, still = [], [], []
    for i, group in enumerate(batches, 1):
        _log("BATCH", f"{i}/{len(batches)}: {', '.join(group)}")
        recs = _wake(group, mapping, dry)
        _produce(recs, dry)
        _poll_bars(recs, dry)
        local = _pull(recs, date, day_dir, dry)
        _stop(recs, dry)
        for s in group:
            b = local.get(s, -1)
            if b >= FULL_SESSION_BARS:
                fetched.append(s)
            elif b > 0:
                short.append((s, b))
            else:
                still.append(s)
        mapping, _ = instance_registry.discover(config.UNIVERSE)   # refresh states

    print("\n──────── backfill summary ────────")
    print(f"date {date}: {len(fetched)} full, {len(short)} short, {len(still)} still missing")
    if short:
        print("short (got some bars): " + ", ".join(f"{s}={b}" for s, b in short))
    if still:
        print("STILL MISSING: " + ", ".join(still)
              + "  (DXFeed history may be gone — same-evening only)")
    return 0 if not still else 1


def main(argv):
    p = argparse.ArgumentParser(description="EOD candle backfill for sat-out symbols")
    p.add_argument("--date", default=None, help="YYYY-MM-DD (default: today ET)")
    p.add_argument("--batch", type=int, default=5, help="boxes per batch (default 5)")
    p.add_argument("--stream-cap", type=int, default=10,
                   help="max concurrent boxes/streams allowed (default 10)")
    p.add_argument("--only", default=None,
                   help="comma-separated symbols to limit to (default: all missing)")
    p.add_argument("--dry-run", action="store_true", help="show the plan, touch nothing")
    p.add_argument("--mock", action="store_true", help="offline demo (mock AWS)")
    args = p.parse_args(argv[1:])
    if args.mock:
        config.set_mock(True)
    only = [s.strip().upper() for s in args.only.split(",")] if args.only else None
    return run(date=args.date, batch=args.batch, stream_cap=args.stream_cap,
               only=only, dry=args.dry_run)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
