#!/usr/bin/env python3
# day_trader_pro/progress.py — v1.0
# v1.0 (2026-09-01) — dtp r240. ONE TICKER, ON THE FETCH PATH.
#
# Operator, 2026-09-01: "The S3 options in devtools need a progress meter. Some
# of them run long." Measured that day: the butterfly probe took 53.5s for ONE
# date, so a 7-day range is about six minutes of apparently-nothing.
#
# 🔑 WIRED INTO THE FETCH, NOT INTO SIX REPORTS. `warehouse_cost.py` and
#   `s3_sweep.py` already had their own meters; `fit_readiness`, `pnl_s3`,
#   `warehouse_coverage` and `eod_analysis` had none — and all four pull
#   through `warehouse_reader.read_prefix`. Putting it there covers every
#   consumer, present and future, instead of four retrofits that drift apart
#   (§7, and the same argument as the lander: one implementation beats two).
#
# ⚠️ STDERR, ALWAYS, AND NEVER STDOUT. These reports have their output redirected
#   and diffed (`report_parity.py` compares OUTPUTS across sources), so a
#   carriage-return meter on stdout would land inside the thing being compared
#   and every parity run would fail on animation.
#
# ⚠️ THROTTLED BY TIME, NOT BY COUNT. A per-item print on 750,540 signal_journal
#   objects is itself a cost, and at 542 bytes an object the meter would out-
#   write the payload.
"""A single-line progress meter for long S3 reads."""

from __future__ import annotations

import os
import sys
import time

# Set DTP_NO_PROGRESS=1 for a clean capture (cron, redirection to a file that
# is later diffed).
_OFF = os.environ.get("DTP_NO_PROGRESS", "") not in ("", "0")


def _fmt(sec: float) -> str:
    sec = int(max(0, sec))
    return f"{sec // 60}m{sec % 60:02d}s" if sec >= 60 else f"{sec}s"


class Ticker:
    """Report progress on one line, and always finish with a newline.

    ⚠️ THE FINAL LINE IS NOT THE METER. `done()` prints a persistent summary,
    because a meter that erases itself leaves no record of what the read
    actually did — and "0 objects" from an empty session and "0 objects" from
    an unreachable bucket must never look the same (warehouse_reader's WhMeta
    rule; this is the same rule for the fetch that feeds it).
    """

    def __init__(self, label: str, total: int = 0, every: float = 0.5):
        self.label = label
        self.total = int(total or 0)
        self.every = every
        self.n = 0
        self.bytes = 0
        self.t0 = time.time()
        self._last = 0.0
        self._painted = False

    def step(self, n: int = 1, nbytes: int = 0):
        self.n += n
        self.bytes += nbytes
        now = time.time()
        if _OFF or (now - self._last) < self.every:
            return
        self._last = now
        el = now - self.t0
        rate = self.n / el if el > 0 else 0
        if self.total:
            pct = 100.0 * self.n / self.total
            # ⚠️ ETA ONLY ONCE THERE IS A RATE TO EXTRAPOLATE. An ETA computed
            # off two objects is a number that will be wrong and believed.
            eta = (f"  eta {_fmt((self.total - self.n) / rate)}"
                   if rate > 0 and self.n > 20 else "")
            msg = (f"  {self.label}: {self.n:,}/{self.total:,} ({pct:.0f}%)"
                   f"  {self.bytes / 1e6:.0f} MB{eta}")
        else:
            msg = (f"  {self.label}: {self.n:,}  {self.bytes / 1e6:.0f} MB"
                   f"  {_fmt(el)}")
        sys.stderr.write("\r" + msg.ljust(78))
        sys.stderr.flush()
        self._painted = True

    def done(self, note: str = ""):
        if _OFF:
            return
        el = time.time() - self.t0
        if self._painted:
            sys.stderr.write("\r" + " " * 78 + "\r")
        sys.stderr.write(f"  {self.label}: {self.n:,} object(s)  "
                         f"{self.bytes / 1e6:.0f} MB  in {_fmt(el)}"
                         f"{('  ' + note) if note else ''}\n")
        sys.stderr.flush()
