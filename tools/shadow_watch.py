#!/usr/bin/env python3
# day_trader_pro/tools/shadow_watch.py — v1.1
# v1.1 (2026-09-10) — dtp r329 / SHD.3. 🔴 THE GUARD PAGED ON ITS OWN BUG.
#   Its remote line built the filename from `$OT_INSTRUMENT`, a systemd
#   `Environment=` value that does not exist in the non-login shell `_exec`
#   opens — so it expanded to EMPTY, the path became `.../<date>/.jsonl`, and
#   every box answered `rows=0 scored=0`. On 2026-09-10 it paged "the fitting
#   corpus is empty" while all fifteen boxes held ~141 rows written that
#   morning and the observer logged no warning at all.
#   🔑 IT MANUFACTURED THE ABSENCE IT REPORTED — the same plausible-silence
#   class this guard exists to close, arriving inside the guard.
#   FIX: glob the day's directory instead of naming the file, and report
#   `file=none` DISTINCTLY from `rows=0` — no file and an empty file are
#   different faults and the alert now says which.
#   ⚠️ TELEGRAM IS AN EMERGENCY CHANNEL (§17), so a false page is not a
#   cosmetic defect: it is the one thing that teaches an operator to ignore
#   the channel. Five sessions of it would have been worse than silence.
# v1.0 (2026-09-05) — dtp r299 / SHD.2. IF SHADOW IS NOT SCORING BY 09:40 ET,
#   SAY SO ONCE. Operator: *"I'm going to assume it runs. If it's ever not
#   running by 0930, alert me."*
#
#   🔴 WHY THIS NEEDS A WATCHER AT ALL. Stage 2 runs `scorer.score()` per tick
#   INSIDE RTH only, and the tick handler catches and warns — so a scorer that
#   throws produces `scores: []`, **the same shape stage 1 wrote for seven
#   weeks.** The service is `active`, the log is quiet, the jsonl has rows, and
#   the fitting corpus is empty. Nothing in the fleet notices, because nothing
#   distinguishes "no scores" from "scores that are all empty".
#
#   ⚠️ TELEGRAM IS AN EMERGENCY CHANNEL (§17). This is SILENT on success — no
#   nightly "shadow fine", because an operator who gets one learns to skip it
#   and then misses the one that matters. It speaks only when a box is dark.
#
#   ⚠️ AND IT MUST NOT PAGE FOR AN EXPECTED CONDITION. It exits silently when
#   the day is not a trading day (Labor Day 2026-09-08 is why this was written
#   rather than run by hand), and when `control_state` is disabled — a fleet
#   deliberately stopped is not a fault.
#
#   ⚠️ EVERY FLEET COMMAND EXITS 0 OR ITS OUTPUT IS DISCARDED. `grep -c`
#   returns 1 on a zero count, which once marked all 29 boxes failed and threw
#   away stdout. The remote line echoes its own count and ends `|| true`, and
#   the PARSE decides — never the exit code.
#
# Run:  python3 tools/shadow_watch.py            # the guard, as the timer runs it
#       python3 tools/shadow_watch.py --drill  # REAL send, marked DRILL
#       python3 tools/shadow_watch.py --dry      # print, never send
#       python3 tools/shadow_watch.py --date 2026-09-08
"""Alert if any box is not writing scored shadow rows during RTH."""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date as _date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import control_state                                        # noqa: E402
import ettime                                               # noqa: E402
import fleet                                                # noqa: E402
import market_calendar                                      # noqa: E402

try:
    import notify
except Exception:                                           # noqa: BLE001
    notify = None

# ⚠️ THE REMOTE LINE IS THE MEASUREMENT, so it is written to be unambiguous.
# `scored` counts rows whose `scores` array is NOT the empty list — the exact
# distinction stage 1 could not make. `rows` is there so a dark box can be told
# apart from a box that wrote nothing at all: those are different faults.
REMOTE = (
    # 🔴 r329 — THE PATH IS GLOBBED, NOT BUILT FROM `$OT_INSTRUMENT`.
    # v1.0 interpolated that variable into the filename. It is a systemd
    # `Environment=` value: it exists for the UNITS and NOT for the non-login
    # shell `_exec` opens, so it expanded to EMPTY on every box and the path
    # became `.../<date>/.jsonl` — a file that cannot exist. `wc -l` found
    # nothing, `grep -c` found nothing, and all fifteen boxes reported
    # `rows=0 scored=0`. The guard paged "the fitting corpus is empty" on
    # 2026-09-10 while every box held ~141 rows written that morning.
    # 🔑 IT MANUFACTURED THE ABSENCE IT REPORTED. Proven, not inferred:
    # `echo "OT_INSTRUMENT=[$OT_INSTRUMENT]"` over the same fan-out returned
    # `[]` on all fifteen, and `wc -l` on the real file returned 141-142.
    # ⚠️ AND THE FAILURE WAS INDISTINGUISHABLE FROM THE ONE IT WATCHES FOR.
    # A dark box and a broken watcher both say `rows=0 scored=0`; that is the
    # same plausible-silence class the guard was written to close, arriving
    # inside the guard itself.
    r'd=$HOME/options-trader/data/shadow/$(TZ=America/New_York date +%F); '
    r'f=$(ls $d/*.jsonl 2>/dev/null | head -1); '
    r'echo "file=$(basename ${f:-none}) '
    r'rows=$(wc -l < "$f" 2>/dev/null || echo 0) '
    r'scored=$(grep -c "\"scores\": \[[^]]" "$f" 2>/dev/null || echo 0)"; true'
)
# `file=none` is NOT `rows=0`: no file at all is a different fault from a file
# with nothing in it, and the alert says which.
_PAT = re.compile(r"file=(\S+)\s+rows=(\d+)\s+scored=(\d+)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", default=None, help="ET date (default: today)")
    ap.add_argument("--dry", action="store_true",
                    help="print the verdict, never send")
    # 🔴 THE ALERT PATH MUST BE EXERCISED ON A DAY NOTHING IS WRONG. Without
    # this, the first real send would be the morning shadow is actually dark —
    # an untested path, at the worst moment. Modelled on the fleet's
    # blind-alert DRILL, which sends for real and marks itself so a test page
    # can never be mistaken for a live one.
    ap.add_argument("--drill", action="store_true",
                    help="send a REAL Telegram marked DRILL, then exit")
    a = ap.parse_args(argv)

    day = ettime.operator_date(a.date)

    if a.drill:
        # ⚠️ MARKED, ALWAYS. The fleet's blind-alert drill prefixes
        # "DRILL - NOT REAL" for the same reason: an unmarked test page trains
        # the operator to hesitate over a real one.
        msg = (f"DRILL - NOT REAL\n🕶️ shadow_watch alert path, {day}. "
               f"This is the message you would receive if a box stopped "
               f"writing scored shadow rows. No action needed.")
        print(msg)
        if notify is None:
            print("shadow_watch: notify unavailable — path NOT proven")
            return 1
        ok = notify.send(msg)
        print(f"shadow_watch: drill sent={bool(ok)}")
        return 0 if ok else 1

    # ── EXPECTED CONDITIONS EXIT SILENTLY ────────────────────────────────
    if not market_calendar.is_trading_day(_date.fromisoformat(day)):
        print(f"shadow_watch {day}: not a trading day — silent")
        return 0
    if not control_state.is_enabled():
        # A fleet the operator stopped on purpose is not a fault. Detection
        # stays honest; only the PAGE is gated (§17).
        print(f"shadow_watch {day}: control disabled — silent")
        return 0

    # ⚠️ `_exec` PER BOX, NOT `cmd_run`. `cmd_run` PRINTS and returns an int —
    # it does not hand back per-box output, so a guard built on it could only
    # know that something failed, never WHICH box is dark. Checked before
    # writing this rather than after it shipped.
    # 🔑 AND `_targets` IS THE GATE FOR A DELIBERATELY STOPPED BOX: a box that
    # is not running is skipped, not paged. An expected condition must never
    # reach the emergency channel (§17).
    running, skipped = fleet._targets(fleet.get_fleet(None), False)
    dark, silent_boxes, missing, seen = [], [], [], 0
    for sym, ip, _st in running:
        rc, out, err = fleet._exec(sym, ip, REMOTE)
        m = _PAT.search(out or "")
        if not m:
            # ⚠️ UNPARSEABLE IS NOT GREEN. A box that did not answer is a box
            # we know nothing about, and saying nothing would be the same
            # silent-empty failure this guard exists to catch.
            silent_boxes.append(sym)
            continue
        seen += 1
        fname, rows, scored = m.group(1), int(m.group(2)), int(m.group(3))
        if fname == "none":
            # ⚠️ NO FILE IS ITS OWN FACT. Reporting it as `0 rows` is exactly
            # the conflation that hid v1.0's own defect for five days.
            missing.append(sym)
        elif scored == 0:
            dark.append(f"{sym} ({rows} row(s), 0 scored)")

    print(f"shadow_watch {day}: {seen} box(es) answered, {len(dark)} dark, "
          f"{len(silent_boxes)} no answer, {len(missing)} no file, "
          f"{len(skipped)} not running (skipped)")
    if not dark and not silent_boxes and not missing:
        return 0

    lines = ["🕶️ SHADOW NOT SCORING — the fitting corpus is empty."]
    if dark:
        lines.append("dark: " + ", ".join(dark))
    if missing:
        lines.append("NO SHADOW FILE AT ALL: " + ", ".join(missing))
    if silent_boxes:
        lines.append("no answer: " + ", ".join(silent_boxes))
    lines.append("stage 2 writes `scores: []` when a scorer throws — same "
                 "shape as stage 1. Check: journalctl -u shadow-observer "
                 "--since 09:30 -p warning")
    msg = "\n".join(lines)
    print(msg)
    if a.dry or notify is None:
        return 1
    notify.send(msg)
    return 1


if __name__ == "__main__":
    sys.exit(main())
