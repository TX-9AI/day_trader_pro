#!/usr/bin/env python3
"""
tests/regime_census.py — v1.2 — 2026-07-30

WHAT IT ANSWERS
    Which regime labels were COMMITTED, by which engine, and — critically — was
    a given strategy's required regime ever live inside that strategy's entry
    window?

    Written for a specific question on 2026-07-30: the fleet took 4 trades on 15
    boxes (a normal day is ~20), and NOT ONE condor was attempted, which is
    unheard of. All four trades were ORB — the only strategy deliberately
    un-gated from regime. Every regime-gated strategy went silent on the day the
    regime engine changed (L2.5 committed its first live label ~09:55 ET).

    iron_condor_strategy.decide() line ~310:
        if regime.primary_regime != Regime.RANGING: return None
    That return is SILENT — no log, no journal event. So the ONLY way to know
    whether the regime gate refused is to read regime_log directly.

WHY TRANSITIONS ARE NOT THE ANSWER
    regime_log writes on CHANGE, not per tick. A box that sat in RANGING for two
    hours logs ONE row. So a raw count understates occupancy badly. This computes
    TIME IN REGIME from consecutive timestamps, which is what actually matters:
    condor needs RANGING to be live during 11:11-14:00, not merely entered.

ENGINE PROVENANCE
    main v4.8 stamps regime_log.engine with "L2" or "v13". 2026-07-30 is the
    FIRST day containing both on the same boxes and the same tape, so the two
    engines' label distributions can be compared directly instead of comparing
    across days and hoping nothing else moved. Rows written before v4.8 carry
    NULL — honest, since provenance for those is genuinely unknown at row level
    (though the reachability proof says all of them are v13).

USAGE
    python3 tests/regime_census.py                    # today
    python3 tests/regime_census.py --date 2026-07-30
    python3 tests/regime_census.py --window 11:11-14:00   # condor entry window
    python3 tests/regime_census.py --regime RANGING       # per-symbol detail

Read-only. stdlib only. Never writes to the DBs.
"""

import argparse
import collections
import datetime as dt
import glob
import os
import sqlite3
import sys
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# Resolve from THIS FILE's repo, not a hardcoded ~ — the tool has to work in a
# clone, a checkout, or a standalone install with no controller anywhere.
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRADES_ROOT = os.environ.get("DTP_TRADES_ROOT", os.path.join(_REPO, "trades"))


def _mins(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def load(date):
    """-> {symbol: [(minute_of_day, regime, engine, raw_ts), ...]} plus skips."""
    pat = os.path.join(TRADES_ROOT, date, f"*_trades_{date}.db")
    files = sorted(glob.glob(pat))
    if not files:                       # tolerate the other observed naming
        files = sorted(glob.glob(os.path.join(TRADES_ROOT, date, "*trades*.db")))
    out, skipped = {}, []
    for f in files:
        sym = os.path.basename(f).split("_")[0]
        try:
            con = sqlite3.connect(f"file:{f}?mode=ro", uri=True)
            cols = [r[1] for r in con.execute("PRAGMA table_info(regime_log)")]
            if not cols:
                skipped.append(f"{sym}(no regime_log)")
                con.close()
                continue
            has_eng = "engine" in cols
            # v1.1 — MUST filter by date. trades.db is CUMULATIVE: regime_log
            # holds every session the box has ever run. v1.0 selected the whole
            # table and only parsed HH:MM, silently stacking ~10 days on top of
            # each other — 56,534 minutes reported against a 5,850-minute
            # ceiling (15 boxes x 390-minute session). The per-symbol verdict was
            # therefore cross-day and not today's answer at all.
            col = "engine" if has_eng else "NULL"
            q = (f"SELECT logged_at, regime, {col} FROM regime_log "
                 "WHERE logged_at LIKE ? ORDER BY logged_at")
            rows = []
            for ts, rg, en in con.execute(q, (date[:8] + "%",)):
                # v1.2 — TIMESTAMPS ARE UTC. trade_logger writes ISO-8601 with an
                # explicit offset ("2026-07-30T13:30:16.112594+00:00"). v1.1
                # sliced ts[11:16] and treated it as ET, so an 11:11-14:00 ET
                # window actually measured 11:11-14:00 UTC = 07:11-10:00 ET —
                # pre-market plus the first half hour. Every window figure and
                # the per-symbol verdict were reading the wrong three hours.
                # Convert properly; DST is handled by the zone, not by a
                # hardcoded -4 that would silently break in November.
                if not ts:
                    continue
                try:
                    dtv = dt.datetime.fromisoformat(ts)
                except ValueError:
                    continue
                if dtv.tzinfo is None:          # older naive rows: assume UTC
                    dtv = dtv.replace(tzinfo=dt.timezone.utc)
                loc = dtv.astimezone(ET)
                if loc.strftime("%Y-%m-%d") != date:
                    continue                    # UTC row that lands on another ET day
                rows.append((loc.hour * 60 + loc.minute, rg or "?",
                             en or "NULL", loc.strftime("%H:%M")))
            con.close()
            if rows:
                out[sym] = rows
        except Exception as exc:        # noqa: BLE001
            skipped.append(f"{sym}({type(exc).__name__})")
    return out, skipped, files


def occupancy(rows, lo=None, hi=None, day_end=16 * 60):
    """Minutes spent in each (engine, regime), clipped to [lo, hi] if given.

    Each row holds until the NEXT row; the last holds to day_end. This is the
    honest measure — regime_log records transitions, so counting rows would say
    a two-hour RANGING stretch is worth the same as a one-minute one.
    """
    acc = collections.Counter()
    for i, (m0, rg, en, _) in enumerate(rows):
        m1 = rows[i + 1][0] if i + 1 < len(rows) else day_end
        a, b = m0, m1
        if lo is not None:
            a, b = max(a, lo), min(b, hi)
        if b > a:
            acc[(en, rg)] += b - a
    return acc


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.datetime.now().strftime("%Y-%m-%d"))
    ap.add_argument("--window", default="11:11-14:00",
                    help="entry window to slice (default = condor's)")
    ap.add_argument("--regime", default="RANGING",
                    help="regime to report per-symbol (default RANGING = condor)")
    a = ap.parse_args(argv[1:])

    data, skipped, files = load(a.date)
    print(f"date {a.date} — {len(files)} db(s), {len(data)} with regime_log"
          + (f", skipped: {', '.join(skipped)}" if skipped else ""))
    if not data:
        print(f"\nNo regime_log rows found under {TRADES_ROOT}/{a.date}/")
        return 1

    lo, hi = (_mins(x) for x in a.window.split("-"))

    allday, inwin = collections.Counter(), collections.Counter()
    engrows = collections.Counter()
    for sym, rows in data.items():
        for _, _, en, _ in rows:
            engrows[en] += 1
        allday.update(occupancy(rows))
        inwin.update(occupancy(rows, lo, hi))

    print(f"\nregime_log ROWS by engine (transitions, not time): {dict(engrows)}")

    def table(title, acc):
        tot = sum(acc.values()) or 1
        print(f"\n  {title}")
        print(f"    {'ENGINE':<7}{'REGIME':<20}{'MINUTES':>9}{'SHARE':>8}")
        for (en, rg), mins in sorted(acc.items(), key=lambda kv: -kv[1])[:12]:
            print(f"    {en:<7}{rg:<20}{mins:>9}{100.0*mins/tot:>7.1f}%")

    table("TIME IN REGIME — whole session (minutes, summed across boxes)", allday)
    table(f"TIME IN REGIME — {a.window} (the entry window)", inwin)

    # ── the decisive per-symbol answer ──────────────────────────────────────
    print(f"\n  {'='*62}\n  WAS {a.regime} LIVE IN {a.window}?  (per symbol, minutes)\n  {'='*62}")
    any_live = False
    for sym in sorted(data):
        acc = occupancy(data[sym], lo, hi)
        mins = {en: m for (en, rg), m in acc.items() if rg == a.regime}
        if mins:
            any_live = True
            detail = "  ".join(f"{en}={m}m" for en, m in sorted(mins.items()))
            print(f"    {sym:<6} YES   {detail}")
        else:
            top = sorted(acc.items(), key=lambda kv: -kv[1])[:1]
            held = f"(mostly {top[0][0][1]})" if top else "(no rows in window)"
            print(f"    {sym:<6} no    {held}")

    print()
    if not any_live:
        print(f"  VERDICT: {a.regime} was NEVER the committed label in {a.window}")
        print(f"  on ANY box. A strategy gated on it could not fire — and for the")
        print(f"  condor that gate returns SILENTLY, so nothing in bot.log or the")
        print(f"  journal would say so. The regime engine is the mechanism.")
    else:
        print(f"  VERDICT: {a.regime} WAS live in the window on the boxes marked")
        print(f"  YES. The regime gate is NOT the blocker there — check bot.log on")
        print(f"  those boxes for 'no liquid strike beyond dual floor' (strike")
        print(f"  selection) or a condor_plan journal event with no condor_leg")
        print(f"  (the trigger never approached).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
