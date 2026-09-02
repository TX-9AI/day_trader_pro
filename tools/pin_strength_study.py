#!/usr/bin/env python3
# day_trader_pro/tools/pin_strength_study.py — v1.0
# v1.0 (2026-09-01) — dtp r243. DOES THE STRENGTH WE CAN SEE PREDICT THE
#   PULLING WE CANNOT?
#
# Operator, 2026-09-01: "what are the hallmarks of a 'strong' pin? A pin that's
# literally pulling price towards it" — and: we are not done until the charm
# question is resolved either conclusively or not, but resolved either way.
#
# 🔑 THE DESIGN IS THE POINT. What the engine calls strength is an ASSERTION:
#   `pin_concentration` and `pin_strike` come from GEXSnapshot — the strike with
#   the highest net GEX and how concentrated it is. That is a claim about DEALER
#   POSITIONING, i.e. about force that WOULD be exerted. It is anticipatory,
#   which is right, but it is not evidence of force.
#   Evidence of force is different and is also already on disk:
#     · CROSSINGS  — price PINNED to a strike oscillates ACROSS it, because
#       dealers sell above and buy below. Price merely passing through crosses
#       ONCE. This separates a magnet from a waypoint and nothing else does.
#     · PERSISTENCE — a pin that migrates is not a pin, it is a moving maximum.
#     · CONVERGENCE — |spot - pin| shrinking over the session.
#     · TERMINAL   — where price actually finished relative to the pin.
#   So: concentration, charm and fork position are PREDICTORS, knowable at noon.
#   Crossings, persistence, convergence and terminal distance are the OUTCOME,
#   knowable only after. The question is whether the first predicts the second.
#   If it does not, `pin_concentration` is a label rather than a measurement and
#   the butterfly is gated on an assertion.
#
# 🔴 THE PIN STRIKE LIVES UNDER `check_name='pinning'`, NOT 'pin_played'.
#   `prep.cond("pinning", pin or None, ...)` passes the strike as the check's
#   VALUE. `pin_played` is written ONLY on the already-played branch, so it is
#   absent from almost every evaluation — panel 1 of the 2026-09-01 run lists
#   `pinning` at 21,053 rows with ZERO unmeasured and no `pin_played` at all.
#   Read from the run, not assumed.
#
# ⚠️ CHARM IS READ AT THE PIN STRIKE, NOT AVERAGED OVER THE CHAIN. The first
#   attempt (bfly_pin_study panel 3) averaged all ~250 strikes: the median came
#   out 0.0000 (the deep-OTM tail where delta never moves) and the mean 2-5 (a
#   handful of near-the-money contracts). Neither describes the pin. Charm is
#   per-day scaled, so a 0.15 delta move in 20s is legitimately ~650/day —
#   `MIN_DT_SECONDS` IS enforced in `_pair`, so the large values are real
#   arithmetic, not a division blowup. Checked, not assumed.
#
# ⚠️ EVERY AGGREGATION IS IN SQL OR STREAMED PER GROUP. r242: this tool's
#   predecessor OOM'd on the analysis side after the fetch had worked.
#
# ⚠️ CLI ONLY — no menu item (r242). The menu is the operating loop.
#   Run:  python3 tools/pin_strength_study.py --from 2026-08-29 --to 2026-09-01
#         python3 tools/pin_strength_study.py --from ... --to ... --no-charm
"""Pin strength: what predicts a pin that actually pulls price."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)

import warehouse_cache as WCACHE                              # noqa: E402

ET = ZoneInfo("US/Eastern")
STRAT = "GEXPinButterfly"
FORK_INTERVAL = "1h"          # operator's choice, 2026-09-01


def _dates(a, b):
    d0 = datetime.strptime(a, "%Y-%m-%d").date()
    d1 = datetime.strptime(b, "%Y-%m-%d").date()
    if d1 < d0:
        raise SystemExit("END is earlier than START")
    out = []
    while d0 <= d1:
        out.append(d0.isoformat())
        d0 += timedelta(days=1)
    return out


def _q(c, sql, args=(), cap=200_000):
    return c.query(sql, args, max_rows=cap)


def main(argv):
    ap = argparse.ArgumentParser(description="pin strength study")
    ap.add_argument("--from", dest="d0", required=True)
    ap.add_argument("--to", dest="d1", required=True)
    ap.add_argument("--no-charm", action="store_true",
                    help="skip surface_series (1.8GB / ~4min) — everything "
                         "else runs in about a minute")
    a = ap.parse_args(argv[1:])
    dates = _dates(a.d0, a.d1)
    t0 = datetime.now(ET)
    cache = WCACHE.WarehouseCache("pinstr")
    try:
        cache.load("plan_check", dates,
                   ["ts_epoch", "strategy", "check_name", "value"])
        cache.load("plan_tick", dates,
                   ["ts_epoch", "strategy", "underlying", "verdict"])
        cache.load("fork_series", dates,
                   ["ts_epoch", "interval", "built", "upper", "median",
                    "lower", "containment"], datatype="fork_series")
        if not a.no_charm:
            cache.load("surface_series", dates,
                       ["ts_epoch", "strike", "charm"],
                       datatype="surface_series")

        off = cache.et_offset_hours()
        day = f"date(datetime(ts_epoch,'unixepoch','{off}'))"
        con = cache.conn

        # ── minute-keyed views. The three tables tick on different clocks, so
        # they join on the MINUTE, never on an exact float timestamp.
        con.executescript(f"""
        -- 🔴 ONE ROW PER (symbol, MINUTE) ON EVERY SIDE, AND THE FIXTURE IS
        -- WHAT CAUGHT IT. plan_check writes ~4 rows a minute (a tick is ~15s),
        -- so joining pin to conc minute-on-minute FANNED OUT 4x4: a planted
        -- 240-row day reported n=960, and every crossing was counted four
        -- times. An inflated crossing count is exactly the metric this study
        -- turns on, so the fanout would have manufactured the pull it exists
        -- to detect. Collapse each side FIRST, then join.
        CREATE TABLE pin AS SELECT symbol, {day} d,
               CAST(ts_epoch/60 AS INT) m, MIN(ts_epoch) ts_epoch,
               AVG(value) pin
          FROM "plan_check" WHERE strategy='{STRAT}' AND check_name='pinning'
           AND value IS NOT NULL AND value > 0
         GROUP BY symbol, m;
        CREATE TABLE conc AS SELECT symbol, CAST(ts_epoch/60 AS INT) m,
               AVG(value) conc FROM "plan_check"
         WHERE strategy='{STRAT}' AND check_name='pin_concentration'
           AND value IS NOT NULL
         GROUP BY symbol, m;
        CREATE TABLE spot AS SELECT symbol, CAST(ts_epoch/60 AS INT) m,
               AVG(underlying) px FROM "plan_tick"
         WHERE underlying IS NOT NULL AND underlying > 0
         GROUP BY symbol, m;
        CREATE INDEX ix_pin ON pin(symbol, d, ts_epoch);
        CREATE INDEX ix_conc ON conc(symbol, m);
        CREATE INDEX ix_spot ON spot(symbol, m);
        """)
        con.commit()

        out, w = [], None
        out = []
        w = out.append
        w(f"PIN STRENGTH STUDY — {dates[0]} .. {dates[-1]} ET")
        w("=" * 66)
        w(f"source: s3  ·  {cache.objects:,} objects  ·  {cache.rows:,} rows"
          f"  ·  {cache.bytes_seen / 1e6:.0f} MB"
          f"{'  (charm skipped)' if a.no_charm else ''}")
        w("")

        npin = _q(cache, "SELECT COUNT(*) n FROM pin")[0]["n"]
        nspot = _q(cache, "SELECT COUNT(*) n FROM spot")[0]["n"]
        if not npin or not nspot:
            w("⚠️ no joinable pin/spot rows — pin comes from plan_check")
            w("   check_name='pinning', spot from plan_tick.underlying.")
            w(f"   pin rows={npin:,}  spot minutes={nspot:,}")
            raise SystemExit(_emit(out, dates, t0))

        # ══ 1. IS THE PIN EVEN STABLE? ══════════════════════════════════
        # 🔑 The cheapest disqualifier, and it runs first for that reason. A
        # pin that names a different strike every twenty minutes is a moving
        # maximum, and no downstream measure of "strength" means anything.
        w("1. PIN PERSISTENCE  (a pin that migrates is not a pin)")
        w("-" * 66)
        rows = _q(cache,
                  "SELECT symbol, d, COUNT(*) ticks, COUNT(DISTINCT pin) pins,"
                  "       MIN(pin) lo, MAX(pin) hi"
                  "  FROM pin GROUP BY symbol, d ORDER BY d, symbol")
        w(f"  {'day':<11} {'sym':<6} {'ticks':>7} {'distinct':>9} "
          f"{'ticks/pin':>10} {'range':>14}")
        for r in rows:
            rng = f"{r['lo']:.0f}-{r['hi']:.0f}"
            w(f"  {r['d']:<11} {r['symbol'][:6]:<6} {r['ticks']:>7,} "
              f"{r['pins']:>9} {r['ticks'] / max(1, r['pins']):>10.0f} "
              f"{rng:>14}")
        w("")

        # ══ 2. DOES PRICE OSCILLATE ACROSS IT? ══════════════════════════
        # 🔴 THE MEASURE THAT SEPARATES A MAGNET FROM A WAYPOINT. Dealers long
        # gamma sell above the strike and buy below, so a PINNED price crosses
        # repeatedly. A price merely passing through crosses ONCE.
        # ⚠️ STREAMED PER (symbol, day) — never a fetchall over the join.
        w("2. CROSSINGS AND CONVERGENCE  (the observable pull)")
        w("   crossings = sign flips of (spot - pin). 1 = passed through.")
        w("   converge  = |spot-pin| second half vs first half; <1 = pulled in")
        w("-" * 66)
        groups = _q(cache, "SELECT DISTINCT symbol, d FROM pin ORDER BY d, symbol")
        w(f"  {'day':<11} {'sym':<6} {'n':>6} {'cross':>6} {'conv':>6} "
          f"{'|end-pin|':>10} {'conc':>6} {'charm@pin':>10}")
        summary = []
        for g in groups:
            joined = list(cache.iter(
                "SELECT p.ts_epoch t, p.pin pin, s.px px, c.conc conc"
                "  FROM pin p JOIN spot s ON s.symbol=p.symbol AND s.m=p.m"
                "  LEFT JOIN conc c ON c.symbol=p.symbol AND c.m=p.m"
                " WHERE p.symbol=? AND p.d=? ORDER BY p.ts_epoch",
                (g["symbol"], g["d"])))
            if len(joined) < 10:
                continue
            diffs = [(r["px"] - r["pin"]) for r in joined]
            cross = sum(1 for i in range(1, len(diffs))
                        if diffs[i - 1] and diffs[i]
                        and (diffs[i - 1] > 0) != (diffs[i] > 0))
            half = len(diffs) // 2
            f1 = sum(abs(x) for x in diffs[:half]) / max(1, half)
            f2 = sum(abs(x) for x in diffs[half:]) / max(1, len(diffs) - half)
            conv = (f2 / f1) if f1 else float("nan")
            endd = abs(diffs[-1])
            cs = [r["conc"] for r in joined if r["conc"] is not None]
            conc = sum(cs) / len(cs) if cs else float("nan")
            ch = float("nan")
            if not a.no_charm:
                cr = _q(cache,
                        "SELECT AVG(ABS(s.charm)) c FROM \"surface_series\" s"
                        " JOIN pin p ON p.symbol=s.symbol"
                        "   AND CAST(s.ts_epoch/60 AS INT)=p.m"
                        "   AND ABS(s.strike - p.pin) < 0.01"
                        " WHERE p.symbol=? AND p.d=?", (g["symbol"], g["d"]))
                ch = cr[0]["c"] if cr and cr[0]["c"] is not None else float("nan")
            summary.append((g["d"], g["symbol"], len(joined), cross, conv,
                            endd, conc, ch))
            w(f"  {g['d']:<11} {g['symbol'][:6]:<6} {len(joined):>6,} "
              f"{cross:>6} {conv:>6.2f} {endd:>10.2f} {conc:>6.2f} "
              f"{ch:>10.4f}")
        w("")

        # ══ 3. THE FORK CHANNEL ═════════════════════════════════════════
        # Operator: is a pin found INSIDE a pitchfork channel a better pin?
        # position = (pin - lower) / (upper - lower). 0.5 = on the median line,
        # outside [0,1] = the pin sits outside the channel entirely.
        # ⚠️ CONFOUND, STATED: the fork is fitted to recent price, so a pin near
        # the median is partly just "the pin is near where price has been" —
        # which is reachability wearing a different hat. Read alongside conc.
        w(f"3. PIN vs THE {FORK_INTERVAL} PITCHFORK CHANNEL")
        w("   position 0=lower tine, 0.5=median line, 1=upper tine")
        w("-" * 66)
        fk = _q(cache,
                "SELECT COUNT(*) n FROM \"fork_series\" WHERE interval=? AND built=1",
                (FORK_INTERVAL,))
        if not fk or not fk[0]["n"]:
            w(f"  (no BUILT {FORK_INTERVAL} forks in this window — "
              f"nothing to place the pin against)")
        else:
            con.executescript(f"""
            CREATE TABLE fk AS SELECT symbol, CAST(ts_epoch/60 AS INT) m,
                   AVG(upper) up, AVG(lower) lo, AVG(containment) cont
              FROM "fork_series" WHERE interval='{FORK_INTERVAL}' AND built=1
               AND upper IS NOT NULL AND lower IS NOT NULL
             GROUP BY symbol, m;
            CREATE INDEX ix_fk ON fk(symbol, m);
            """)
            con.commit()
            band = _q(cache,
                      "SELECT CASE"
                      "   WHEN (p.pin-f.lo)/(f.up-f.lo) < 0 THEN 'below channel'"
                      "   WHEN (p.pin-f.lo)/(f.up-f.lo) < 0.25 THEN '0.00-0.25'"
                      "   WHEN (p.pin-f.lo)/(f.up-f.lo) < 0.50 THEN '0.25-0.50'"
                      "   WHEN (p.pin-f.lo)/(f.up-f.lo) < 0.75 THEN '0.50-0.75'"
                      "   WHEN (p.pin-f.lo)/(f.up-f.lo) <= 1.0 THEN '0.75-1.00'"
                      "   ELSE 'above channel' END pos,"
                      " COUNT(*) n, AVG(c.conc) conc, AVG(f.cont) cont"
                      "  FROM pin p JOIN fk f ON f.symbol=p.symbol AND f.m=p.m"
                      "  LEFT JOIN conc c ON c.symbol=p.symbol AND c.m=p.m"
                      " WHERE f.up > f.lo GROUP BY pos ORDER BY pos")
            if not band:
                w("  (forks exist but none share a minute with a pin —")
                w("   the two are written on different cadences)")
            else:
                w(f"  {'position':<16} {'n':>8} {'mean conc':>10} "
                  f"{'mean containment':>18}")
                for r in band:
                    w(f"  {r['pos']:<16} {r['n']:>8,} "
                      f"{(r['conc'] if r['conc'] is not None else float('nan')):>10.2f} "
                      f"{(r['cont'] if r['cont'] is not None else float('nan')):>18.2f}")
        w("")

        # ══ 4. THE ANSWER, OR THE ABSENCE OF ONE ════════════════════════
        # 🔴 RESOLVED EITHER WAY. Operator: "we're not done until the charm
        # question is resolved either conclusively or not, but resolved either
        # way." So this states the correlation AND its sample size, and says
        # plainly when the sample cannot support a claim.
        w("4. DOES DECLARED STRENGTH PREDICT OBSERVED PULL?")
        w("-" * 66)
        if len(summary) < 3:
            w(f"  NOT RESOLVED — {len(summary)} symbol-day(s) with enough")
            w("  joined rows. A correlation needs more than this; widen the")
            w("  date range. This is an ANSWER, not a gap: the sample is")
            w("  named rather than a number being printed from it.")
        else:
            def _corr(xs, ys):
                pts = [(x, y) for x, y in zip(xs, ys)
                       if x == x and y == y]
                if len(pts) < 3:
                    return None, 0
                n = len(pts)
                mx = sum(p[0] for p in pts) / n
                my = sum(p[1] for p in pts) / n
                sxy = sum((p[0] - mx) * (p[1] - my) for p in pts)
                sxx = sum((p[0] - mx) ** 2 for p in pts)
                syy = sum((p[1] - my) ** 2 for p in pts)
                if sxx <= 0 or syy <= 0:
                    return None, n
                return sxy / (sxx * syy) ** 0.5, n

            conc_v = [s[6] for s in summary]
            charm_v = [s[7] for s in summary]
            cross_v = [float(s[3]) for s in summary]
            conv_v = [s[4] for s in summary]
            end_v = [s[5] for s in summary]
            for label, pred in (("pin_concentration", conc_v),
                                ("|charm| at pin", charm_v)):
                w(f"  {label}")
                for oname, ov in (("crossings", cross_v),
                                  ("convergence", conv_v),
                                  ("|end-pin|", end_v)):
                    r, n = _corr(pred, ov)
                    if r is None:
                        w(f"    vs {oname:<14} NOT RESOLVED (n={n}, no variance)")
                    else:
                        w(f"    vs {oname:<14} r = {r:+.2f}  (n={n})")
            w("")
            w("  ⚠️ r on a handful of symbol-days is DIRECTIONAL, NOT A FIT.")
            w("     Read the sign and the sample; do not fit a bound to it.")
        w("")
        w("⚠️ THIS MEASURES WHETHER PINS HOLD, NOT WHETHER BUTTERFLIES PAY.")
        w("   It runs on ~21,000 EVALUATIONS rather than a handful of fills,")
        w("   which is its strength — and its limit: construction is what")
        w("   r208 fixed, and none of that is visible here.")
        raise SystemExit(_emit(out, dates, t0))
    finally:
        cache.close()


def _emit(out, dates, t0):
    text = "\n".join(out) + "\n"
    path = WCACHE.report_path(f"pin_strength_{dates[0]}_{dates[-1]}.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)
    print(f"wrote {path}   "
          f"({(datetime.now(ET) - t0).total_seconds():.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
