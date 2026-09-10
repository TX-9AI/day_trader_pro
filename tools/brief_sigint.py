#!/usr/bin/env python3
"""
day_trader_pro/tools/brief_sigint.py  v1.1
v1.1  2026-09-10  dtp r339 - SPX GETS A ROW. Operator: *"we cannot have our
      largest net symbol be silent on that brief."* market_brief's _NON_EQUITY
      never polls it, so the row is DERIVED from the thirteen constituents that
      ARE scored, using `composite_call` IMPORTED from otv4's brief_bias_join -
      the same function the study scores against the tape. A local copy would
      let the board advertise a signal nobody measured, so a failed import
      OMITS the row and says so rather than computing one here.
      ⚠️ PRINTED, NOT ENDORSED: labelled DERIVED and UNVALIDATED on every run
      (n=44 sessions, ~1.4 SE). SPX also comes out of the TRADED BUT NOT SCORED
      list, since it now has a row of its own kind.
v1.0  2026-09-10  dtp r337 / BRF.2 — TURN THE BRIEF INTO SOMETHING WORTH
      READING BEFORE ANYTHING IS WIRED DOWNSTREAM OF IT.

🔑 WHAT THIS IS. The morning brief prints a direction for ~29 tickers every
day and, measured against 50 sessions of tape, **half of those calls are
worse than useless.** This board applies the one thing the measurement
actually established — a CONVICTION FLOOR — and shows only the calls that
cleared it. Everything below the floor is named and set aside, not hidden.

🔴 THE MEASUREMENT, r336, 2026-07-05..2026-09-10, n=529 scored calls:

      called   q      n    hit%     edge vs that direction's base rate
      LONG     q1    64   45.3%    -2.7%
      LONG     q2    93   45.2%    -2.9%
      LONG     q3   118   49.2%    +1.1%
      LONG     q4    81   55.6%    +7.5%
      SHORT    q1    23   47.8%    -4.2%
      SHORT    q2    51   47.1%    -4.9%
      SHORT    q3    53   66.0%   +14.1%
      SHORT    q4    46   67.4%   +15.4%

**The gradient is monotonic in BOTH directions and the sign flips at the
median, 0.640.** Below it, both directions score WORSE than simply assuming
the base rate; above it, both beat it. That is why the floor — not the
direction — is the first actionable thing the brief has ever produced.

⚠️ AND THE AGGREGATE HID IT. Table A read LONG +0.9% overall, which looked
like "the bullish half carries nothing". It was two real signals of opposite
sign averaged into mush. A pooled number can conceal a working one.

🔴 THIS IS POST-HOC AND THE BOARD SAYS SO ON EVERY RUN. The quartile scheme
and the 0.640 cut were both chosen AFTER seeing the data they describe.
The gradient is hard to fake, but the honest status is UNCONFIRMED until
forward-tested — so the floor is frozen HERE, in one constant, with its
provenance, and the footer states it. **Nothing downstream reads this file
yet, deliberately** (WA §5: what gets traded is the operator's call).

⚠️ SPX IS NOT IN THE BRIEF AT ALL. It sits in market_brief's `_NON_EQUITY`
and is never polled, so it can never appear on this board — while being the
largest money in the book. The board prints that absence rather than letting
a missing row read as "no call today".

Run (CONTROL):
    python3 tools/brief_sigint.py                 # today
    python3 tools/brief_sigint.py --date 2026-09-09
    python3 tools/brief_sigint.py --send          # push to Telegram
    python3 tools/brief_sigint.py --selftest
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ettime                                                   # noqa: E402

try:
    import notify
except Exception:                                               # noqa: BLE001
    notify = None

DB = os.environ.get("SCREENER_DB", os.path.expanduser("~/market-brief/screener.db"))

# 🔴 ONE CONSTANT, WITH ITS PROVENANCE. The median of the conviction
# distribution over 2026-07-05..2026-09-10 (r336). Below it BOTH directions
# underperform the base rate. Changing this number is changing what the board
# calls actionable, so it moves only with a fresh measurement cited.
CONVICTION_FLOOR = 0.640
FLOOR_SOURCE = "r336 · 2026-07-05..2026-09-10 · n=529 · POST-HOC, unconfirmed"

# The panel actually traded (day_trader_pro/selector.py PANEL). A brief call on
# a name we never trade is information, not an instruction — it is shown apart.
try:
    from selector import PANEL as _PANEL
    PANEL = set(_PANEL)
except Exception:                                               # noqa: BLE001
    PANEL = set()

DIR_MAP = {"BULLISH": "LONG", "BEARISH": "SHORT", "NEUTRAL": "NEUT"}

OTV4_DIR = os.environ.get("DTP_OTV4_DIR", os.path.expanduser("~/options-trader-v4"))


def load_composite():
    """The ONE weighting rule, imported from the study that measures it.

    🔴 NO LOCAL COPY, AND NO FALLBACK. `brief_bias_join` scores this composite
    against the tape; if the board weighted its constituents differently the
    board would be advertising a signal nobody has measured. If the import
    fails the SPX row is OMITTED and SAID SO — a silent local reimplementation
    is how the two drift.
    """
    if OTV4_DIR not in sys.path:
        sys.path.insert(0, os.path.join(OTV4_DIR, "tests"))
    try:
        from brief_bias_join import composite_call, SPX_PROXY
        return composite_call, SPX_PROXY
    except Exception:                                           # noqa: BLE001
        return None, ()


def load_day(day, db=None):
    """[(ticker, LONG|SHORT|NEUT, score, conviction)] for one report date."""
    db = db or DB
    if not os.path.exists(db):
        raise SystemExit("  🔴 brief db not found: {} (set SCREENER_DB)".format(db))
    con = sqlite3.connect("file:{}?mode=ro".format(db), uri=True)
    con.row_factory = sqlite3.Row
    rows = {}
    # ORDER so the LAST composite of the day wins — a day can carry more than
    # one report tier and the latest call is the one that stood at the bell.
    for r in con.execute(
            "SELECT ticker, score, direction, conviction FROM composites "
            "WHERE report_date = ? ORDER BY id", (day,)):
        rows[r["ticker"]] = (r["ticker"],
                             DIR_MAP.get(str(r["direction"] or "").upper(), "?"),
                             r["score"], r["conviction"])
    con.close()
    return list(rows.values())


def triage(rows, floor=CONVICTION_FLOOR):
    """-> (actionable, below_floor, no_conviction, neutral).

    ⚠️ A MISSING CONVICTION IS ITS OWN BUCKET. Treating None as 0.0 would
    file an unmeasured call under 'below the floor', which asserts something
    the brief never said.
    """
    act, below, unk, neut = [], [], [], []
    for t, d, score, conv in rows:
        if d == "NEUT":
            neut.append((t, d, score, conv))
        elif d not in ("LONG", "SHORT"):
            unk.append((t, d, score, conv))
        elif conv is None:
            unk.append((t, d, score, conv))
        elif conv >= floor:
            act.append((t, d, score, conv))
        else:
            below.append((t, d, score, conv))
    act.sort(key=lambda r: (-r[3], r[0]))
    below.sort(key=lambda r: (-(r[3] or 0), r[0]))
    return act, below, unk, neut


def board(day, rows, floor=CONVICTION_FLOOR):
    act, below, unk, neut = triage(rows, floor)
    L = ["🧭 BRIEF SIGINT {} — floor {:.3f}".format(day, floor)]
    if not rows:
        L.append("no brief for this date.")
        return "\n".join(L)

    if act:
        L.append("")
        L.append("ACTIONABLE ({}):".format(len(act)))
        for t, d, _s, c in act:
            tag = "" if not PANEL or t in PANEL else "  (not traded)"
            L.append("  {:<6} {:<5} conv {:.2f}{}".format(t, d, c, tag))
    else:
        L.append("")
        L.append("ACTIONABLE (0): nothing cleared the floor today.")

    if below:
        L.append("")
        L.append("BELOW FLOOR ({}) — these scored WORSE than the base rate"
                 .format(len(below)))
        L.append("  in both directions over the measured window:")
        L.append("  " + ", ".join("{} {} {:.2f}".format(t, d, c or 0)
                                  for t, d, _s, c in below))
    if neut:
        L.append("")
        L.append("NEUTRAL ({}): {}".format(
            len(neut), ", ".join(t for t, _d, _s, _c in neut)))
    if unk:
        L.append("")
        L.append("⚠️ NO CONVICTION ({}): {} — unmeasured, NOT below the floor"
                 .format(len(unk), ", ".join(t for t, _d, _s, _c in unk)))

    # ── SPX: DERIVED, because the brief never calls it ───────────────────
    # 🔴 OPERATOR'S REQUIREMENT, 2026-09-10: *"we cannot have our largest net
    # symbol be silent on that brief."* SPX is in market_brief's _NON_EQUITY
    # and is never polled, so this row is BUILT from the constituents that are
    # scored — and it is labelled DERIVED and UNVALIDATED every single day.
    # ⚠️ IT IS PRINTED, NOT ENDORSED. Measured over 44 SPX sessions (r338):
    # floor-gated LONG 61.3% vs a 52.5% base at n=31, SHORT 77.8% vs 47.5% at
    # n=9 — about 1 and 1.4 standard errors. Directionally encouraging and
    # statistically nothing yet. The label carries that, so a reader cannot
    # mistake this row for the measured ones above it.
    cc, members = load_composite()
    L.append("")
    if cc is None:
        L.append("⚠️ SPX: composite unavailable — brief_bias_join did not "
                 "import from")
        L.append("   {} (set DTP_OTV4_DIR). NO SPX row rather than a "
                 "locally-computed one.".format(OTV4_DIR))
    else:
        call, avg, k = cc(rows, floor, members)
        if not k:
            L.append("SPX  DERIVED: no constituent cleared the floor today "
                     "(0 of {}).".format(len(members)))
        else:
            L.append("SPX  {:<5} conv {:+.2f} from {} constituent(s)  "
                     "— DERIVED".format(call, avg, k))
        L.append("   ⚠️ UNVALIDATED: equal-weight, n=44 sessions, ~1.4 SE. "
                 "Not a measured call.")

    seen = {t for t, _d, _s, _c in rows}
    missing = sorted((PANEL - seen) - {"SPX"}) if PANEL else []
    if missing:
        L.append("")
        L.append("⚠️ TRADED BUT NOT SCORED ({}): {}".format(
            len(missing), ", ".join(missing)))
        L.append("   A name absent from the brief has NO call — that is not "
                 "the same as NEUTRAL.")
    L.append("")
    L.append("floor: {}".format(FLOOR_SOURCE))
    L.append("⚠️ Nothing downstream reads this. Advisory only.")
    return "\n".join(L)


def selftest() -> int:
    ok = True
    rows = [("A", "LONG", 0.9, 0.80), ("B", "SHORT", 0.7, 0.50),
            ("C", "LONG", 0.6, None), ("D", "NEUT", 0.1, 0.99),
            ("E", "SHORT", 0.8, 0.640)]
    act, below, unk, neut = triage(rows)
    ok &= [r[0] for r in act] == ["A", "E"]          # >= floor, incl. the edge
    ok &= [r[0] for r in below] == ["B"]
    ok &= [r[0] for r in unk] == ["C"]               # None is NOT below-floor
    ok &= [r[0] for r in neut] == ["D"]
    txt = board("2026-09-10", rows)
    ok &= "ACTIONABLE (2)" in txt and "NO CONVICTION (1)" in txt
    ok &= "POST-HOC" in txt
    # an empty day says so rather than printing an empty board
    ok &= "no brief for this date" in board("2026-09-10", [])
    print("brief_sigint selftest:", "ALL PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", default=None, help="ET date (default: today)")
    ap.add_argument("--floor", type=float, default=CONVICTION_FLOOR)
    ap.add_argument("--send", action="store_true", help="push to Telegram")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    day = ettime.operator_date(a.date)
    msg = board(day, load_day(day), a.floor)
    print(msg)
    if a.send:
        if notify is None:
            print("  🔴 notify unavailable — NOT sent")
            return 1
        print("  sent={}".format(bool(notify.send(msg))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
