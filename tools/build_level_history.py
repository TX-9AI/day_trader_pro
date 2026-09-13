#!/usr/bin/env python3
"""
day_trader_pro/tools/build_level_history.py  v1.0
v1.0  2026-09-13  r379 / LVL.17 — CONSTRUCT THE LEVEL BOOKS FROM BANKED TAPE.

OPERATOR, 2026-09-12/13: *"I'm not saying the bots would 'pull' from s3. I'm
saying we could construct their ledgers from that data."* And on the shape:
*"there's no reference for '3 up & 3 down' so just walk the tape and pull the
historical levels against spot or last close on the underlying."*

🔑 SO THIS DOES NOT RECONSTRUCT THE MAPPER'S LADDER. The `(R1)/(R2)/(R3)` rungs
and the Asia/London/NY naming are a LIVE derivation with no historical
reference — and [[LVL.15]] found the names are not even unique inside one book.
What survives across sessions is a PRICE, so this walks the tape, takes every
level a session LEAVES BEHIND — its high and low, its open and close, the opening
range's extremes, and the swing pivots inside it — and measures how every LATER
session tested each one. Each zone records the SOURCES that formed it, because
the operator ruled the level TYPE drives the fit: *"the level type should
determine how we fit the contact gates."*

🔴 WHY REPLAY AND NOT IMPORT, which is the whole reason this file exists.
[[LVL.13]]: the banked counters were produced by a HALF-PLANE contact test, so
every bar beyond a level re-counted as a fresh touch and a fresh breach — AMZN
2026-09-09 recorded 389 touches and 389 breaches of a PDL price never reached.
Those numbers cannot be un-inflated after the fact. The TAPE is intact, so the
honest route is to recount it.

🔑 ONE DEFINITION OF A VISIT, AND IT IS otv4's. The counting comes from
`analysis.liquidity_ledger.on_closed_bar` in the trading repo, imported rather
than reimplemented. A second implementation here would be a second answer to
"what is a test", which is the lineage split WORKING_AGREEMENT §7 forbids — and
it is exactly how the store and the strategy came to disagree in the first place.
⚠️ THE IMPORT IS SAFE BECAUSE THAT MODULE IS STDLIB-ONLY (json/os/tempfile/
typing/logging). It does NOT import `config`, so putting otv4 on the path cannot
shadow dtp's own `config` — the collision that broke an earlier replay.

🔴 HISTORY SEEDS DURABILITY AND NEVER SEEDS AN EVENT. The output carries
`prior_touches`/`prior_holds`/`prior_breaches`/`prior_sessions` and NOTHING else:
no `last_result`, no `last_touch`, no session counters. A hold from three days ago
must never fire a trade today, and the only way to guarantee that is for the
artifact to be incapable of expressing one. `check_level_visits` V9 pins the
other half, in the bot.

⚠️ A VISIT NEVER SPANS THE OVERNIGHT GAP. Each session is fed to a fresh visit
state while the cumulative counters carry, so a level price sat on into the bell
and again at the next open is TWO tests, not one continuing one. Leaving the
state open across the gap would have made every multi-day zone a single visit.

⚠️ NO DISTANCE THRESHOLD IS INVENTED. Every zone is emitted with its `dist_pct`
from the last close and the consumer filters; a cutoff here would be a number
nobody chose (C.44), and the files are tens of zones, not thousands.
"""
import argparse
import io
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

DTP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OTV4 = os.environ.get("OT_REPO", "/home/ubuntu/options-trader-v4")
sys.path.insert(0, DTP)

# 🔴 otv4 GOES ON THE **END** OF THE PATH, NOT THE FRONT, AND THE CHECKER FOUND
# OUT WHY. An earlier cut used `insert(0, OTV4)` on the reasoning that
# `liquidity_ledger` is stdlib-only and imports no `config`, so it could not
# shadow dtp's. That is true OF THAT MODULE and irrelevant to the hazard: with
# otv4 at position 0, EVERY LATER `import config` in this process resolves to
# **otv4's** config — `check_level_history` H6 imported `ssh_util` after this
# module and got an otv4 config with no `SSH_CONNECT_TIMEOUT`. Appending keeps
# `analysis` reachable (dtp has no package by that name) while dtp's own modules
# keep winning, which is the collision that broke an earlier replay, avoided at
# the root instead of survived by luck.
sys.path.append(OTV4)
from analysis.liquidity_ledger import (                         # noqa: E402
    LiquidityLedger, Level, TOUCH_TOL_PCT, SCHEMA_VERSION as LEDGER_SCHEMA)

# 🔑 THE WAREHOUSE AND THE CHDIR ARE DEFERRED INTO main(), SO THE DERIVATION IS
# TESTABLE WITHOUT S3. `candidates()`, `cluster()` and `measure()` are pure
# functions of a tape, and a land gate that cannot run them offline is a land
# gate that cannot run at all — which is how a tool ships with no CHECK (§15).

HISTORY_SCHEMA = 1
RTH_OPEN_MIN = 9 * 60 + 30          # 09:30 ET
RTH_CLOSE_MIN = 16 * 60            # 16:00 ET
# The opening range, in minutes from the bell. 30 rather than 60 because the
# operator's ORB work already anchors on the early range; this is the LEVEL it
# leaves behind, not a trigger.
OPENING_RANGE_MIN = 30
# A swing pivot needs this many bars either side to count. 15 makes it a
# 31-minute swing on a 1m chart — a real turn rather than a wiggle.
# ⚠️ RECORDED IN THE OUTPUT so it can be refitted without guessing what built
# the file, and so a zone's `sources` say which scale found it.
PIVOT_WINDOW = 15


def _et_parts(ms):
    """(YYYY-MM-DD, minutes-since-midnight) in ET for an epoch-ms stamp."""
    import ettime
    day = ettime.et_day(ms / 1000.0)
    # ettime owns the ET conversion; derive the clock from the same instant so
    # the two can never disagree about which day a bar belongs to.
    dt = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).astimezone(
        ettime.ET if hasattr(ettime, "ET") else timezone.utc)
    return day, dt.hour * 60 + dt.minute


def sessions_from_tape(rows):
    """Group RTH 1m bars by ET session day. rows: (ms, high, low, close)."""
    out = defaultdict(list)
    for ms, h, l, c in rows:
        day, mins = _et_parts(ms)
        if mins < RTH_OPEN_MIN or mins >= RTH_CLOSE_MIN:
            continue
        out[day].append((ms, float(h), float(l), float(c)))
    return {d: sorted(v) for d, v in out.items() if v}


def candidates(sessions):
    """Every level a session LEAVES BEHIND, walked off its own tape.

    A level is testable only from the NEXT session on: counting the day it was
    formed would score the move that made it as a test of it.

    🔑 SIX SOURCES, because session high/low alone is far too thin — four
    sessions produced six zones and the operator's answer was *"If there's more
    than 6 levels we don't mind. There's plenty of room for more!"*:
      · `session_high` / `session_low`  — the day's extremes (PDH/PDL next day)
      · `session_open` / `session_close` — the day's first and last RTH print;
        the prior close is one of the most watched prices there is
      · `or_high` / `or_low`            — the opening range's extremes
      · `pivot_high` / `pivot_low`      — swing turns inside the session
    ⚠️ EVERY CANDIDATE CARRIES ITS SOURCE, and a zone keeps the SET that formed
    it. That is the operator's ruling made measurable: *"the level type should
    determine how we fit the contact gates"* — a zone that is a prior-day high
    AND a pivot is not the same object as one loose pivot, and without the source
    on the row there is nothing to fit per type.
    ⚠️ A CLOSE AND AN OPEN ARE NOT DIRECTIONAL, so each is emitted BOTH ways: it
    can act as a floor or a ceiling depending on which side price approaches
    from, and the counting is per `kind`.
    """
    cands = []
    for day in sorted(sessions):
        bars = sessions[day]
        highs = [b[1] for b in bars]
        lows = [b[2] for b in bars]
        cands.append((day, max(highs), "high", "session_high"))
        cands.append((day, min(lows), "low", "session_low"))
        # open and close act as either side — emitted as both
        for px, tag in ((bars[0][3], "session_open"), (bars[-1][3], "session_close")):
            cands.append((day, px, "high", tag))
            cands.append((day, px, "low", tag))
        orb = bars[:OPENING_RANGE_MIN]
        if orb:
            cands.append((day, max(b[1] for b in orb), "high", "or_high"))
            cands.append((day, min(b[2] for b in orb), "low", "or_low"))
        w = PIVOT_WINDOW
        for i in range(w, len(bars) - w):
            if highs[i] == max(highs[i - w:i + w + 1]):
                cands.append((day, highs[i], "high", "pivot_high"))
            if lows[i] == min(lows[i - w:i + w + 1]):
                cands.append((day, lows[i], "low", "pivot_low"))
    return cands


def cluster(cands):
    """Collapse candidates into price ZONES within the ledger's own tolerance.

    ⚠️ THE TOLERANCE IS `TOUCH_TOL_PCT`, IMPORTED, not a local constant. A zone
    wider than the band the counting uses would merge levels the bot treats
    separately, and narrower would split one level into two half-histories.
    """
    zones = []
    for day, px, kind, source in sorted(cands, key=lambda c: (c[2], c[1])):
        hit = None
        for z in zones:
            if z["kind"] == kind and abs(z["price"] - px) <= abs(px) * TOUCH_TOL_PCT:
                hit = z
                break
        if hit is None:
            zones.append({"kind": kind, "price": px, "first_seen": day, "n": 1,
                          "sources": {source}})
        else:
            hit["price"] = (hit["price"] * hit["n"] + px) / (hit["n"] + 1)
            hit["n"] += 1
            hit["first_seen"] = min(hit["first_seen"], day)
            hit["sources"].add(source)
    for z in zones:
        z["price"] = round(z["price"], 4)
    return zones


def measure(zone, sessions):
    """Replay every session AFTER the zone was formed through otv4's counter."""
    led = LiquidityLedger("HIST")
    led.date = "history"
    lv = Level(zone["price"], zone["kind"], "", True, zone["first_seen"])
    led.levels = [lv]
    eligible = 0
    for day in sorted(sessions):
        if day <= zone["first_seen"]:
            continue
        eligible += 1
        # ⚠️ A VISIT DOES NOT SURVIVE THE OVERNIGHT GAP — see the header.
        lv.visit_open = False
        lv.visit_bars = 0
        lv.visit_started = ""
        for ms, h, l, c in sessions[day]:
            led.on_closed_bar(h, l, c, ts="%s|%d" % (day, ms))
    return {"prior_touches": lv.touches, "prior_holds": lv.holds,
            "prior_breaches": lv.breaches, "prior_sessions": eligible,
            "contact_bars": lv.contact_bars}


def main():
    ap = argparse.ArgumentParser(description="build per-symbol level history "
                                             "from banked tape")
    ap.add_argument("--start", required=True, help="first session YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="last session YYYY-MM-DD")
    ap.add_argument("--syms", default="", help="comma list; default config.UNIVERSE")
    ap.add_argument("--out", required=True, help="output directory")
    a = ap.parse_args()

    # deferred so importing this module costs no S3 client and no chdir
    os.chdir(DTP)
    import warehouse_cache as W
    import config as DTPCFG

    syms = [s.strip().upper() for s in a.syms.split(",") if s.strip()] or \
        list(getattr(DTPCFG, "UNIVERSE", []))
    if not syms:
        print("no symbols — pass --syms or set config.UNIVERSE")
        return 1
    d0 = datetime.strptime(a.start, "%Y-%m-%d").date()
    d1 = datetime.strptime(a.end, "%Y-%m-%d").date()
    if d1 < d0:
        print("END is before START")
        return 1
    dates = []
    d = d0
    while d <= d1:
        dates.append(d.isoformat())
        d = d.fromordinal(d.toordinal() + 1)

    os.makedirs(a.out, exist_ok=True)
    cache = W.WarehouseCache("levelhist")
    written = 0
    try:
        cache.load("candles", dates,
                   ["interval", "ts_epoch_ms", "open", "high", "low", "close"],
                   datatype="candles", syms=syms)
        for sym in syms:
            rows = [tuple(r) for r in cache.conn.execute(
                "SELECT ts_epoch_ms, high, low, close FROM candles "
                "WHERE symbol=? AND interval='1m' AND high IS NOT NULL "
                "ORDER BY ts_epoch_ms", (sym,))]
            sess = sessions_from_tape(rows)
            if len(sess) < 2:
                # ⚠️ SAID OUT LOUD. One session cannot measure a level's
                # durability: the level is formed and never tested, so the file
                # would be a list of zeros indistinguishable from a defended
                # level nobody challenged.
                print("  %-6s SKIPPED — %d session(s) of RTH tape, need >= 2"
                      % (sym, len(sess)))
                continue
            zones = cluster(candidates(sess))
            last_day = sorted(sess)[-1]
            last_close = sess[last_day][-1][3]
            out = []
            for z in zones:
                m = measure(z, sess)
                if m["prior_sessions"] <= 0:
                    continue          # formed on the last session: untestable
                out.append({
                    "price": z["price"], "kind": z["kind"],
                    "first_seen": z["first_seen"],
                    # the level TYPE, which the operator ruled the fit turns on
                    "sources": sorted(z["sources"]),
                    "formed_count": z["n"],
                    "dist_pct": round((z["price"] - last_close) / last_close * 100.0, 3),
                    **m})
            out.sort(key=lambda z: abs(z["dist_pct"]))
            payload = {
                "history_schema": HISTORY_SCHEMA,
                "ledger_schema": LEDGER_SCHEMA,
                "symbol": sym,
                "built_at_utc": datetime.now(timezone.utc).isoformat(),
                "window": {"start": sorted(sess)[0], "end": last_day,
                           "sessions": len(sess)},
                "touch_tol_pct": TOUCH_TOL_PCT,
                "pivot_window": PIVOT_WINDOW,
                "opening_range_min": OPENING_RANGE_MIN,
                "last_close": round(last_close, 4),
                # 🔴 DURABILITY ONLY. No last_result, no last_touch, no session
                # counters — the artifact cannot express an event, by design.
                "zones": out,
            }
            path = os.path.join(a.out, "%s.json" % sym)
            with io.open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=1, sort_keys=True)
            written += 1
            tested = sum(1 for z in out if z["prior_touches"] > 0)
            defended = sum(z["prior_holds"] for z in out)
            broken = sum(z["prior_breaches"] for z in out)
            print("  %-6s %2d sessions  %3d zones  %3d tested  "
                  "%4d holds / %4d breaches  last_close %.2f"
                  % (sym, len(sess), len(out), tested, defended, broken, last_close))
    finally:
        cache.close()
    print()
    print("wrote %d file(s) to %s" % (written, a.out))
    return 0 if written else 1


if __name__ == "__main__":
    sys.exit(main())
