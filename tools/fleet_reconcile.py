#!/usr/bin/env python3
"""
day_trader_pro/tools/fleet_reconcile.py  v1.0
v1.0  2026-09-09  dtp r325 / S3.24 — RESET THE FLEET'S PREFIX COUNTERS TO THE
      S3 TRUTH, FROM CONTROL, IN ONE PLACE.

🔑 THIS HOLDS NO RECONCILE LOGIC AND MUST NEVER GROW ANY. The flag already
exists: `warehouse/s3_push.py --reconcile` has walked a box's prefixes and
reset each counter to what S3 actually holds since WH.6. What has never
existed is a CONTROL-SIDE CALLER — grepping day_trader_pro, the only
`reconcile` was `instance_registry.py reconcile`, which is the EC2 instance
map and unrelated, plus a comment in `eod_conductor_v2.takedown()` telling the
operator to go and run the box flag by hand. So this is transport and
reporting only, the same shape as `drain_and_verify`, and R6 fails the board
if it ever imports boto3 or lists a bucket itself. Two implementations of one
count is the drift this repo keeps finding in its own code.

🔴 WHY IT IS NEEDED AT ALL, 2026-09-09. `tools/trades_epoch_strip.py` (r314)
severed 8,313 pre-09-01 trade objects from `raw/trades/` on the operator's
instruction — and NOTHING TOLD THE BOXES. Each box's `prefix_counters.json`
still claims objects that were deliberately removed, so `--verify` reports
`got=0` on 14-31 prefixes per box and the r180 heal correctly REFUSES them: a
prefix S3 knows nothing about is exactly the loss signature, and heal cannot
tell an authorised strip from a real one. The fleet is therefore HELD every
night, on all fifteen boxes, for bookkeeping — which is the same overnight
hold r171 and r180 each fixed for a different cause, arriving a third time by
a third route.

⚠️ THE SAME SHAPE FOLLOWED THE 2026-08-25 `raw/shadow` PURGE (S3.13): the
bucket changed under the fleet and the ledgers were never told. **Any future
deletion from `raw/` re-creates this**, which is why S3.25 asks the strip tool
to call this itself rather than leaving it to whoever notices the holds.

⚠️ WHAT IT COSTS, STATED UP FRONT. `--reconcile` resets EVERY prefix on the
box, not only the ones a strip emptied, so a genuine gap elsewhere is silently
agreed with and its alarm never fires again. That is acceptable when the cause
is known and deliberate; it is NOT a routine hygiene run, and the menu item
says so and demands the word typed out. Ordinary counter drift needs nothing
from this file — r180's heal already fixes it nightly.

🔴 THE INTERPRETER IS `/usr/bin/python3`, NEVER THE VENV, and it is pinned by
R1. The bot venv has no boto3: F1 in the 2026-08-23 audit found `self_close`
spawning the pusher under it, which aborted the verifier and would have held
every box; the operator hit the identical `ModuleNotFoundError` by hand on
2026-09-09. The s3-push unit's own interpreter is the only one that works.

⚠️ TIMEOUT CUSHION, AND WHY IT IS LARGER THAN VERIFY'S. `fleet._exec` runs at
`SSH_CONNECT_TIMEOUT + 10` = 22 SECONDS, and a reconcile is a full LIST walk
of ~640 prefixes — MINUTES. That ceiling is exactly what made `--verify`
return NO_ANSWER on NVDA in r221 and is why the operator's standing rule says
`--verify` must not go through the fleet fan-out. Verify got 900s; this gets
**1800s by default** (`DTP_RECONCILE_TIMEOUT`), because the walk is the same
and a generous budget costs nothing on success while a short one produces a
NO_ANSWER indistinguishable from a broken box. R2 pins the floor at 900.

⚠️ A BOX THAT DOES NOT ANSWER IS NAMED, NEVER COUNTED AS DONE. No parseable
`reconcile:` line means the reset is unproven, and an unproven reset that
reads as success is how the next verify surprises you. Those boxes make the
exit code non-zero.

Usage (CONTROL, in ~/day_trader_pro):
    python3 tools/fleet_reconcile.py --dry-run
    python3 tools/fleet_reconcile.py
    python3 tools/fleet_reconcile.py --only UNH,QQQ
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config                                                   # noqa: E402
import fleet                                                    # noqa: E402
import ssh_util                                                 # noqa: E402

INSTALL_DIR = getattr(config, "INSTALL_DIR", "~/options-trader")

# ⚠️ 1800, not 900. See the header: same LIST walk as --verify, double the
# cushion, because the failure mode of a short budget is a NO_ANSWER that
# looks exactly like a dead box.
RECONCILE_TIMEOUT_S = int(os.environ.get("DTP_RECONCILE_TIMEOUT", "1800"))

# 🔴 /usr/bin/python3 — the s3-push unit's interpreter. The venv has no boto3.
REMOTE_CMD = ("cd {} && /usr/bin/python3 warehouse/s3_push.py --reconcile 2>&1"
              .format(INSTALL_DIR))

# `reconcile: N prefix counter(s) reset to the S3 truth`
RECON_RE = re.compile(r"^reconcile:\s+(\d+)\s+prefix counter", re.M)


def parse_reset(text):
    """The number of counters this box reset, or None if it did not answer.

    None is not zero. A box that printed nothing parseable has not been shown
    to have done anything, and reporting that as `0 reset` would make a
    transport failure read as a clean no-op.
    """
    m = RECON_RE.search(text or "")
    return int(m.group(1)) if m else None


def targets(only=None):
    """Running boxes only. A stopped box cannot reconcile and is not a fault."""
    return [(s, ip) for s, ip, st in fleet.get_fleet(only) if st == "running"]


def run(only=None, dry=False, runner=None, out=print):
    """Fan out sequentially. Returns (answered, no_answer) symbol lists."""
    runner = runner or ssh_util.ssh_run
    boxes = targets(only)
    if not boxes:
        out("no running boxes — nothing to reconcile")
        return [], []

    out("{} box(es): {}".format(len(boxes), ", ".join(s for s, _ in boxes)))
    out("remote: {}".format(REMOTE_CMD))
    out("timeout: {}s per box (DTP_RECONCILE_TIMEOUT)".format(RECONCILE_TIMEOUT_S))
    if dry:
        out("[dry-run] nothing was run and no counter was touched.")
        return [], []

    answered, silent = [], []
    for i, (sym, ip) in enumerate(boxes, 1):
        out("")
        out("[{}/{}] {} — reconciling, this walks every prefix..."
            .format(i, len(boxes), sym))
        _rc, text, err = runner(ip, REMOTE_CMD, timeout=RECONCILE_TIMEOUT_S)
        n = parse_reset(text)
        if n is None:
            silent.append(sym)
            # ⚠️ NAMED, with whatever came back. Silence is the one outcome
            # that must never be summarised away.
            out("  {}: NO ANSWER — counters NOT proven reset. {}"
                .format(sym, (text or err or "").strip()[:160] or "(no output)"))
            continue
        answered.append(sym)
        out("  {}: {} prefix counter(s) reset".format(sym, n))
        for ln in (text or "").splitlines():
            if ln.startswith("  ") and "->" in ln:
                out("  {}".format(ln.strip()))

    out("")
    out("RECONCILE done — {} answered, {} did not.".format(len(answered), len(silent)))
    if silent:
        out("  NOT RECONCILED: {}".format(", ".join(silent)))
        out("  Those boxes will still be HELD by the conductor tonight.")
    else:
        out("  Re-run the EOD verify to confirm short=0 before the next close.")
    return answered, silent


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Reset every box's S3 prefix counters to the bucket's truth.")
    ap.add_argument("--only", default=None, help="comma-separated symbols")
    ap.add_argument("--dry-run", action="store_true",
                    help="name the boxes and the remote command; run nothing")
    a = ap.parse_args(argv if argv is not None else sys.argv[1:])
    only = ([s.strip().upper() for s in a.only.split(",") if s.strip()]
            if a.only else None)
    _ok, silent = run(only=only, dry=a.dry_run)
    return 1 if silent else 0


if __name__ == "__main__":
    sys.exit(main())
