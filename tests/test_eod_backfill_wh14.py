#!/usr/bin/env python3
# day_trader_pro/tests/test_eod_backfill_wh14.py — v1.0
"""
Pins the WH.14 conductor behaviour in eod_backfill v1.3.

CHANGELOG
    v1.0 — 2026-08-16 — alongside eod_backfill v1.3.

WHAT IS WORTH ASSERTING HERE
    Not that the happy path works — that it fails CORRECTLY. The operator's
    instruction was "fail loudly & skip to the next", and both halves can break
    silently in opposite directions: an alert that never fires, or a failure
    that stalls the remaining boxes. So the failure case is the test.

    Also pinned: batches stay SEQUENTIAL (an earlier cross-batch pipeline idea
    of mine was wrong and must not creep back in), and the scp pull is
    severable by config rather than by editing code.
"""

import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
os.environ.setdefault("DTP_MOCK_AWS", "1")
os.environ["OT_EOD_DRAIN_SPACING"] = "0"     # no real sleeping in tests

FAILS = []


def check(name, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + name +
          ("" if cond else "  <- " + str(detail)))
    if not cond:
        FAILS.append(name)


import config  # noqa: E402
config.MOCK_AWS = True
import eod_backfill as EB  # noqa: E402

SRC = open(os.path.join(os.path.dirname(HERE), "eod_backfill.py"),
           encoding="utf-8").read()

print("\n=== eod_backfill v1.3 — WH.14 ===\n")

RECS = {s: {"instance_id": "i-%d" % n, "private_ip": "10.0.0.%d" % n}
        for n, s in enumerate(["AAPL", "GLD", "IWM", "TLT", "XOM"], start=1)}

# ── the failure path is the point ───────────────────────────────────────────
sent = []
EB.notify = types.SimpleNamespace(send=lambda m: sent.append(m))

# two boxes short, three fine
def _ssh(ip, cmd, timeout=None):
    last = ip.rsplit(".", 1)[-1]
    if last in ("2", "4"):
        return 0, "DRAIN host=x sym=y drained=yes short=3 SHORT", ""
    return 0, "DRAIN host=x sym=y drained=yes short=0 OK", ""


EB.ssh_util = types.SimpleNamespace(ssh_run=_ssh, scp_pull=lambda *a, **k: None)
res = EB._drain_verify(RECS, dry=False)
check("every box in the batch is verified", len(res) == 5, res)
check("the two SHORT boxes are identified BY NAME",
      sorted(k for k, v in res.items() if v != "OK") == ["GLD", "TLT"], res)
check("the three clear boxes report OK",
      sorted(k for k, v in res.items() if v == "OK") == ["AAPL", "IWM", "XOM"], res)
check("a SHORT box does NOT abort the loop — the rest still ran",
      len(res) == 5, res)

# ── loud: it must reach Telegram, not just the log ──────────────────────────
check("the alert goes through the conductor's existing notify path",
      "notify.send(msg)" in SRC)
check("the alert names the boxes", 'join(sorted(not_clear))' in SRC)
check("the alert says the data is stranded, not lost",
      "stranded on them until" in SRC)
check("a Telegram failure cannot stop the pass",
      "telegram failed" in SRC)

# ── skip on: the box still stops ────────────────────────────────────────────
# NOTE: match the CALL SITE by its indentation — a bare "_stop(recs, dry)"
# also matches "def _stop(recs, dry):", which sits earlier in the file and made
# this assertion pass/fail for the wrong reason.
_CALL = "\n        _stop(recs, dry)"
check("_stop is called after the alert, not conditionally on it",
      SRC.index(_CALL) > SRC.index("notify.send(msg)"),
      (SRC.index(_CALL), SRC.index("notify.send(msg)")))

# ── severable pull ──────────────────────────────────────────────────────────
check("the scp pull is behind a config flag", "PULL_ENABLED" in SRC)
check("the flag defaults to ON (dual-write is still the safety net)",
      'os.environ.get("OT_EOD_PULL", "1") != "0"' in SRC)
check("severing is announced, not silent", "the warehouse is the only" in SRC)

# ── batches stay sequential ─────────────────────────────────────────────────
check("drain kicks are spaced deliberately", "DRAIN_SPACING" in SRC)
check("no threading/pool crept in — batches remain sequential",
      "ThreadPool" not in SRC and "concurrent.futures" not in SRC)
check("the batch loop still stops group A before group B wakes",
      SRC.index(_CALL) > SRC.index("_wake(group, mapping, dry)"))

# ── dry run stays inert ─────────────────────────────────────────────────────
sent.clear()
res_dry = EB._drain_verify(RECS, dry=True)
check("dry run verifies nothing and sends nothing",
      all(v == "OK" for v in res_dry.values()) and sent == [], (res_dry, sent))

print("\n" + ("ALL CHECKS PASSED" if not FAILS else "FAILURES: " + ", ".join(FAILS)))
sys.exit(1 if FAILS else 0)
