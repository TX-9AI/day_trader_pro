#!/usr/bin/env python3
"""
day_trader_pro/tests/check_runaway_watch.py — v1.0
v1.0  2026-11-22  dtp r575 / RWATCH.1 — new. tools/runaway_watch.py v1.0, the one scorer of the Runaway equity watch
      list frozen in ~/reviews/runaway_watch_20261122/WATCH.md (the operator, 2026-11-22: "I would keep any poor
      performers on runaway on notice to potentially be cut"; "Can you put a trend bar for runaway on the equities to
      see if they are trending in the right direction or the wrong direction for that setup?"). Read-only: it reads the
      trade CSVs and WATCH.md, and writes only in its own temp dir.

  W1  the seal: WATCH.md's sha256 is the scorer's WATCH_SHA and SEAL.txt's, and the list in it is NVDA, AMD, META
  W2  the cut bar on a fixture: under 8 forward trades ON NOTICE (whatever the EV), 8 with net EV < 0 RECOMMEND CUT,
      8+ with net EV = 0 or > 0 OFF THE LIST; in-sample trades never count (a huge in-sample loss changes nothing)
  W3  the basis: net = pnl_usd - fee (after fees, at the mark); a blank fee is estimated with review_kit.est_fee and
      counted; a fee alone can tip the bar (gross EV >= 0, net EV < 0 -> RECOMMEND CUT)
  W4  the population: strategy RunawayContinuation only, the equities are every symbol but QQQ and SPX (OTV4TEST's AAL
      out), a watch-list symbol with no trades still has a row
  W5  DIRECTION: last 8 trades' net EV against the earlier ones', n beside; up / down / flat, n/a at 8 or fewer
  W6  the trend bar: the cumulative net series by trade, the forward marker at the first 11-23+ trade, '|' in the
      sparkline there
  W7  half days are not sessions: 2026-11-27 is not a forward session; a trade dated on one is counted and named DEFECT
  W8  the markdown and figures(): statuses, the bar text, the small-sample line, every printed dollar figure in figures()
  W9  the real trade CSVs (when readable): in-sample NVDA / AMD / META gross EV -$86.95 / -$59.54 / -$32.11 and net
      -$95.90 / -$61.42 / -$35.03 a trade (the figures WATCH.md records), all ON NOTICE before 11-23
  W10 report only: no OTV5, no box, no network module imported; nothing written unless --md / --json is given
BORN RED on 928b0af (r574): there is no tools/runaway_watch.py.

Run:  python3 tests/check_runaway_watch.py
"""
import ast
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)
FAILS, RAN = [], []
ALL = ("W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8", "W9", "W10")


def ck(n, ok, msg=""):
    RAN.append(n)
    print(f"  {n:<3} {'PASS' if ok else 'FAIL'}  {msg}")
    if not ok:
        FAILS.append(n)


HDR = ("sym,trade_id,strategy,direction,contracts,entry_premium,exit_premium,pnl_usd,entry_time,exit_time,exit_reason,"
       "fee\n")


def row(sym, pnl, fee="1.0", strat="RunawayContinuation", ent="15:00", k=0):
    return f"{sym},t{k},{strat},long,2,1,1,{pnl},2026-01-01T{ent}:00+00:00,2026-01-01T16:00:00+00:00,x,{fee}\n"


def write_days(d, days):
    os.makedirs(d, exist_ok=True)
    for day, rows in days.items():
        with open(os.path.join(d, day + ".csv"), "w") as fh:
            fh.write(HDR + "".join(rows))


def fwd_days(n):
    """n forward trading days from 2026-11-23, skipping the holiday and the half day."""
    import market_calendar as mc
    from datetime import date, timedelta
    out, x = [], date(2026, 11, 23)
    while len(out) < n:
        if mc.is_trading_day(x) and not mc.is_half_day(x):
            out.append(x.isoformat())
        x += timedelta(days=1)
    return out


def main():
    try:
        import runaway_watch as RW
    except ImportError as e:
        for n in ALL:
            ck(n, False, f"no tools/runaway_watch.py ({e})")
        print("\nRED — " + ", ".join(FAILS))
        return 1
    tmp = tempfile.mkdtemp(prefix="ckrw_")
    try:
        # W1 — the seal
        seal = os.path.join(os.path.dirname(RW.WATCH), "SEAL.txt")
        if os.path.exists(RW.WATCH) and os.path.exists(seal):
            sha = RW.seal_sha()
            sl = open(seal).read().split()
            txt = open(RW.WATCH, encoding="utf-8").read()
            ck("W1", sha == RW.WATCH_SHA and sl[0] == sha and RW.WATCH_LIST == ("NVDA", "AMD", "META")
               and "| NVDA | 11 |" in txt and "| AMD | 14 |" in txt and "| META | 9 |" in txt
               and "at least 8" in txt and "below zero" in txt and RW.main(["--check-seal"]) == 0,
               f"WATCH.md sha {sha[:12]} = scorer {RW.WATCH_SHA[:12]} = SEAL {sl[0][:12]}")
        else:
            ck("W1", False, f"WATCH.md or SEAL.txt is not readable here ({RW.WATCH})")

        # W2 — the cut bar
        F = fwd_days(9)
        tr = os.path.join(tmp, "w2")
        days = {"2026-11-02": [row("NVDA", -5000, k=0), row("AMD", -5000, k=1), row("META", +5000, k=2)]}
        for i, d in enumerate(F[:8]):
            days[d] = [row("NVDA", -50 if i < 7 else +20, "0", k=i)]          # 8 fwd: EV < 0 -> CUT
            days[d].append(row("AMD", +10 if i < 4 else -10, "0", k=i))       # 8 fwd: EV = 0 -> OFF
        for i, d in enumerate(F[:7]):
            days[d].append(row("META", -300, "0", k=i))                        # 7 fwd: ON NOTICE
        write_days(tr, days)
        s7 = RW.score(F[7], tr)
        st = {k: s7["equities"][k]["status"] for k in RW.WATCH_LIST}
        days2 = dict(days)
        days2[F[8]] = [row("AMD", +1, "0", k=99), row("META", +5000, "0", k=98)]
        write_days(os.path.join(tmp, "w2b"), days2)
        s8 = RW.score(F[8], os.path.join(tmp, "w2b"))
        st2 = {k: s8["equities"][k]["status"] for k in RW.WATCH_LIST}
        ck("W2", st == {"NVDA": RW.CUT, "AMD": RW.OFF, "META": RW.ON_NOTICE}
           and s7["equities"]["AMD"]["forward"]["ev_net"] == 0 and s7["equities"]["NVDA"]["forward"]["n"] == 8
           and s7["equities"]["META"]["forward_needed"] == 1
           and st2 == {"NVDA": RW.CUT, "AMD": RW.OFF, "META": RW.OFF},
           f"7 fwd ON NOTICE, 8 at EV<0 CUT, 8 at EV=0 OFF, the in-sample -$5,000 ignored: {st}; one more day: {st2}")

        # W3 — the basis
        tr = os.path.join(tmp, "w3")
        days = {d: [row("NVDA", +5, "10", k=i)] for i, d in enumerate(F[:8])}
        days[F[0]].append(row("AMD", 100, "", k=50))
        write_days(tr, days)
        s3 = RW.score(F[7], tr)
        import review_kit as RK
        a = s3["equities"]["AMD"]
        ck("W3", s3["equities"]["NVDA"]["status"] == RW.CUT and s3["equities"]["NVDA"]["forward"]["ev_net"] == -5.0
           and s3["equities"]["NVDA"]["gross"] / 8 > 0 and s3["fees_estimated"] == 1
           and abs(a["fees"] - round(RK.est_fee("AMD", 2), 2)) < 0.01 and abs(a["net"] - (100 - RK.est_fee("AMD", 2))) < 0.01,
           f"gross EV +$5 with a $10 fee is net -$5 -> CUT; a blank fee estimated ({a['fees']}) and counted")

        # W4 — the population
        tr = os.path.join(tmp, "w4")
        write_days(tr, {"2026-11-02": [row("QQQ", 100, k=1), row("SPX", 100, k=2), row("AAL", 100, k=3),
                                       row("TSLA", 100, k=4), row("TSLA", 999, strat="PARK", k=5),
                                       row("CVX", 50, strat="LiquidityHunt", k=6)]})
        s4 = RW.score("2026-11-20", tr)
        eq = set(s4["equities"])
        ck("W4", eq == {"TSLA", "NVDA", "AMD", "META"} and s4["equities"]["TSLA"]["n"] == 1
           and s4["equities"]["NVDA"]["n"] == 0 and RW.INDEX == ("QQQ", "SPX"),
           f"Runaway only, index and OTV4TEST out, the watch list always present: {sorted(eq)}")

        # W5 — direction
        tr = os.path.join(tmp, "w5")
        days = {}
        import market_calendar as mc
        from datetime import date, timedelta
        x, k = date(2026, 10, 26), 0
        seq = [-100] * 4 + [50] * 8              # earlier 4 at -100, last 8 at +50 -> up
        while k < len(seq):
            if mc.is_trading_day(x) and not mc.is_half_day(x):
                days[x.isoformat()] = [row("CRM", seq[k], "0", k=k), row("SOFI", -seq[k], "0", k=k)]
                if k < 8:
                    days[x.isoformat()].append(row("UNH", 10, "0", k=k))
                if k < 10:
                    days[x.isoformat()].append(row("CVX", 10, "0", k=k))
                k += 1
            x += timedelta(days=1)
        write_days(tr, days)
        s5 = RW.score("2026-11-20", tr)
        c, so, u, cv = (s5["equities"][s]["direction"] for s in ("CRM", "SOFI", "UNH", "CVX"))
        ck("W5", c["word"] == "up" and c["arrow"] == "↑" and c["earlier"]["n"] == 4 and c["last"]["n"] == 8
           and c["last"]["ev_net"] == 50.0 and c["earlier"]["ev_net"] == -100.0 and so["word"] == "down"
           and u["word"] == "n/a" and cv["word"] == "flat" and "(n 4)" in RW.dir_text(c),
           f"CRM {RW.dir_text(c)}; SOFI {so['word']}; UNH (n 8) {u['word']}; CVX {cv['word']}")

        # W6 — the trend bar
        tr = os.path.join(tmp, "w6")
        write_days(tr, {"2026-11-19": [row("AVGO", 100, "0", k=1)], "2026-11-20": [row("AVGO", -50, "0", k=2)],
                        F[0]: [row("AVGO", 25, "0", k=3)]})
        s6 = RW.score(F[0], tr)
        e = s6["equities"]["AVGO"]
        ck("W6", e["cum"] == [100.0, 50.0, 75.0] and e["forward_index"] == 2 and e["spark"].index("|") == 2
           and len(e["spark"]) == 4 and e["forward"]["n"] == 1,
           f"cum {e['cum']}, forward marker {e['forward_index']}, spark {e['spark']}")

        # W7 — half days
        tr = os.path.join(tmp, "w7")
        write_days(tr, {"2026-11-27": [row("NVDA", -10, "0", k=1)]})
        s7h = RW.score("2026-11-30", tr)
        md7 = RW.render_md(s7h)
        ck("W7", "2026-11-27" not in s7h["forward_sessions"] and len(s7h["forward_sessions"]) == 4
           and s7h["equities"]["NVDA"]["forward"]["n"] == 1 and s7h["equities"]["NVDA"]["half_day_trades"] == ["2026-11-27"]
           and "DEFECT" in md7 and "NVDA 2026-11-27" in md7,
           f"forward sessions through 11-30: {s7h['forward_sessions']}; the half-day trade counted and named")

        # W8 — markdown and figures
        md = RW.render_md(s7)
        figs = RW.figures(s7)
        ck("W8", "**RECOMMEND CUT**" in md and "**OFF THE LIST**" in md and "**ON NOTICE**" in md
           and "1 more forward trade(s) needed" in md and "small sample" in md and "(n 8 >= 8)" in md
           and round(abs(s7["equities"]["NVDA"]["forward"]["net"])) in figs
           and round(abs(s7["equities"]["META"]["net"])) in figs and "any cut needs the operator's yes" in md,
           "statuses, the bar text, the small-sample line; figures() holds the printed dollars")

        # W9 — the real CSVs
        if os.path.isdir(RW.TRADES) and os.path.exists(os.path.join(RW.TRADES, "2026-11-20.csv")):
            r = RW.score("2026-11-20")
            got = {s: (round(r["equities"][s]["gross"] / r["equities"][s]["n"], 2), r["equities"][s]["ev_net"],
                       r["equities"][s]["status"]) for s in RW.WATCH_LIST}
            want = {"NVDA": (-86.95, -95.9, RW.ON_NOTICE), "AMD": (-59.54, -61.42, RW.ON_NOTICE),
                    "META": (-32.11, -35.03, RW.ON_NOTICE)}
            ck("W9", got == want and len(r["equities"]) == 12, f"{got}; {len(r['equities'])} equities")
        else:
            ck("W9", False, f"the trade CSVs are not readable here ({RW.TRADES})")

        # W10 — report only
        src = open(os.path.join(ROOT, "tools", "runaway_watch.py"), encoding="utf-8").read()
        mods = set()
        for n in ast.walk(ast.parse(src)):
            if isinstance(n, ast.Import):
                mods |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                mods.add((n.module or "").split(".")[0])
        allowed = {"argparse", "csv", "glob", "hashlib", "json", "os", "sys", "datetime", "market_calendar",
                   "review_kit"}
        out = os.path.join(tmp, "w10")
        os.makedirs(out)
        before = set(os.listdir(out))
        rc = RW.main(["--through", F[7], "--trades", os.path.join(tmp, "w2"), "--md", os.path.join(out, "a.md"),
                      "--json", os.path.join(out, "a.json")])
        j = json.load(open(os.path.join(out, "a.json")))
        ck("W10", mods <= allowed and rc == 0 and before == set() and sorted(os.listdir(out)) == ["a.json", "a.md"]
           and j["equities"]["NVDA"]["status"] == RW.CUT and "os.environ" not in src and "printenv" not in src,
           f"imports {sorted(mods)}; writes only what it is asked to")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print()
    if FAILS:
        print("RED — %d of %d: %s" % (len(FAILS), len(RAN), ", ".join(FAILS)))
        return 1
    print("GREEN — %d checks" % len(RAN))
    return 0


if __name__ == "__main__":
    sys.exit(main())
