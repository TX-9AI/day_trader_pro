#!/usr/bin/env python3
# day_trader_pro/tests/test_emergency_stop.py — v1.0
"""
Pins the EMERGENCY STOP (devtools 27 / wake_and_bake --shutdown-only).

CHANGELOG
    v1.0 — 2026-08-16 — alongside wake_and_bake v1.3 (WH.7).

WHY THIS FILE EXISTS AT ALL
    Twice now this exact item has been damaged without anyone noticing: the
    July 22 v1.18 renumber clobbered its LABEL, and the SSH pre-ping made it
    hang for ~5 minutes with no output. Both were silent. A kill switch that
    fails quietly is worse than one that is absent, because you only find out
    while using it.

    So this asserts the safety properties BY NAME — the July 22 rule, applied
    to code rather than to a menu. Position over name is exactly what failed
    before; nothing here is checked by ordering or by counting.

THE ONE THAT MATTERS
    `test_shutdown_never_touches_ssh` fails against v1.2. It patches _exec to
    raise, so any SSH attempt in the shutdown path is an immediate error rather
    than a five-minute wait — the bug made visible in milliseconds.
"""

import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
os.environ.setdefault("DTP_MOCK_AWS", "1")

FAILS = []


def check(name, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + name +
          ("" if cond else "  <- " + str(detail)))
    if not cond:
        FAILS.append(name)


import config  # noqa: E402
config.MOCK_AWS = True
import wake_and_bake as W  # noqa: E402

SRC = open(os.path.join(os.path.dirname(HERE), "wake_and_bake.py"),
           encoding="utf-8").read()

print("\n=== emergency stop (devtools 27) — safety properties ===\n")

# ── 1. THE FIX ──────────────────────────────────────────────────────────────
_ssh_calls = []


def _boom(ip, cmd):
    _ssh_calls.append((ip, cmd))
    raise AssertionError("shutdown must not SSH")


W._exec = _boom
W._discover = lambda only: {
    s: {"instance_id": "i-%03d" % n, "private_ip": "10.0.0.%d" % n}
    for n, s in enumerate(["SPX", "QQQ", "NVDA", "TLT", "XOM"], start=1)}
W.notify = types.SimpleNamespace(send=lambda *a, **k: None)

rc = W.run(assume_yes=True, mode="shutdown")
check("shutdown returns 0 in mock", rc == 0, rc)
check("shutdown made ZERO ssh calls (this is the v1.2 hang)",
      _ssh_calls == [], _ssh_calls[:2])

# a full run SHOULD still ping — the fix must be scoped to shutdown only
_ssh_calls.clear()
W._exec = lambda ip, cmd: (0, "OK", "")
check("stage_ping still exists for the modes that need it",
      callable(getattr(W, "stage_ping", None)))
check("only the shutdown branch skips it",
      'if mode == "shutdown":' in SRC and "stage_ping(only, expected, dry)" in SRC)

# ── 2. THE SAFETY PROPERTIES, BY NAME (July 22 rule) ────────────────────────
check("HALT gate string is intact", 'Type "HALT" to proceed' in SRC)
check("HALT is compared exactly (not lowercased/starts-with)",
      'ans != "HALT"' in SRC)
check("position-abandonment warning is intact",
      "Open Positions will no longer be managed" in SRC)
check("live-fleet in-RTH escalation is intact",
      "abandoned at the broker" in SRC)
check("RTH guard still blocks FULL only, leaving shutdown exempt",
      'if mode == "full" and _in_rth(now)' in SRC)
check("shutdown still does no EOD and no pycache",
      "no EOD/pyclear" in SRC)
check("mode description still says EMERGENCY STOP",
      "EMERGENCY STOP the fleet NOW" in SRC)

# ── 3. IT MUST NEVER LOOK SILENT AGAIN ─────────────────────────────────────
check("it announces that it is skipping reachability",
      "skipping SSH reachability" in SRC)
check("it announces the stop request before waiting",
      "stop requested — polling" in SRC)

# ── 4. STOPPING NEEDS IDS, NOT IPS ─────────────────────────────────────────
check("_ids() reads instance_id only",
      W._ids({"A": {"instance_id": "i-1", "private_ip": "x"}}) == ["i-1"])
check("_ids() tolerates a record with no IP at all",
      W._ids({"A": {"instance_id": "i-1"}}) == ["i-1"])

print("\n" + ("ALL CHECKS PASSED" if not FAILS else "FAILURES: " + ", ".join(FAILS)))
sys.exit(1 if FAILS else 0)
