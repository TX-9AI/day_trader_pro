#!/usr/bin/env python3
"""
day_trader_pro/tests/check_cash_books.py — v1.1
v1.1  2026-11-22  dtp r572 / PREREG amendment 1 (the operator, 2026-11-22: "You want to cut the 2 worst as well? I
      didn't think so."). NEW B7: every window carries gross without the two largest losers beside gross without the
      two largest winners, the markdown prints them in ONE column labelled concentration context, the scorer reads and
      prints AMENDMENTS.txt's first line, and the PREREG reproduction (B1, its ex-top-2 column as recorded) still holds.
v1.0  2026-11-22  dtp r572 / CASHBOOK.1 — new. tools/cash_books.py v1.0, the one scorer of the four cash candidate books
      frozen in ~/reviews/cash_candidates_20261121/PREREG.md (the operator, 2026-11-22: "On C1-C4, I would like some
      commentary on the daily and weekly recaps as to how each of them is performing"). Read-only: it reads the trade
      CSVs and PREREG, writes only in its own temp dir.

  B1  it REPRODUCES PREREG's in-sample baseline table exactly (n, gross, fees, net, EV and its interval, up days,
      worst day, max drawdown, gross ex top-2 for C1-C4) from ~/reviews/trades, and PREREG's sha256 is the sealed one
  B2  the four books are PREREG's definitions word for word: on a fixture of every (index/equity x setup) cell, each
      book takes exactly its cells (Hunt, OGAP and other setups never)
  B3  the metrics on a fixture: net = gross - fees (fees beside, never inside EV: EV = gross / n), up days and the
      worst day over every session (a no-trade session counts as flat), max drawdown from 0 at the window's start,
      gross without the two largest winners, the interval with 5,000 draws and seed 1
  B4  the windows: in-sample 10-26..11-20, forward 11-23..12-03 then cumulative past it, combined, the day and the week;
      a trading day with no trade file yet is named, never scored as flat
  B5  the displaced-fire count: a forward book trade that fired while a Hunt or OGAP position was open on the same box
      counts; one on another box, before the entry or after the exit does not; missing times are unmeasurable
  B6  report only: neither the window EV (review_kit) nor the theories read it, and it writes nothing unless asked
BORN RED on b02c6b9 (r571): there is no tools/cash_books.py.

Run:  python3 tests/check_cash_books.py
"""
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
FAILS, RAN = [], []


def ck(n, ok, msg=""):
    RAN.append(n)
    print(f"  {n:<3} {'PASS' if ok else 'FAIL'}  {msg}")
    if not ok:
        FAILS.append(n)


HDR = ("sym,trade_id,strategy,direction,contracts,entry_premium,exit_premium,pnl_usd,entry_time,exit_time,exit_reason,"
       "fee\n")


def row(sym, strat, pnl, fee=1.0, ent="2026-11-23T15:00:00+00:00", ext="2026-11-23T16:00:00+00:00"):
    return f"{sym},t,{strat},long,1,1,1,{pnl},{ent},{ext},x,{fee}\n"


def main():
    try:
        import cash_books as CB
    except ImportError as e:
        for n in ("B1", "B2", "B3", "B4", "B5", "B6", "B7"):
            ck(n, False, f"no tools/cash_books.py ({e})")
        print("\nRED — " + ", ".join(FAILS))
        return 1
    tmp = tempfile.mkdtemp(prefix="ckcb_")
    try:
        # B1
        real = os.path.isdir(CB.TRADES) and os.path.exists(CB.PREREG)
        if real:
            sc = CB.score(CB.IN_SAMPLE[1])
            bad = CB.check_prereg(sc)
            sha = CB.prereg_sha()
            ck("B1", not bad and sha == CB.PREREG_SHA and len(CB.prereg_table()) == 4,
               f"PREREG reproduced, sha {str(sha)[:12]}; mismatches {bad[:4]}")
        else:
            ck("B1", False, f"PREREG or the trade CSVs are not readable here ({CB.PREREG}, {CB.TRADES})")

        # B2
        cells = [(s, t) for s in ("QQQ", "SPX", "AMD", "NVDA") for t in ("PARK", "RunawayContinuation",
                                                                          "LiquidityHunt", "OGAP", "Breakout")]
        got = {b: sorted((s, t) for s, t in cells if CB.in_book(b, s, t)) for b, _d in CB.BOOKS}
        idx, eq = ("QQQ", "SPX"), ("AMD", "NVDA")
        want = {"C1": sorted((s, t) for s in idx for t in ("PARK", "RunawayContinuation")),
                "C2": sorted((s, t) for s in idx + eq for t in ("PARK", "RunawayContinuation")),
                "C3": sorted([(s, "PARK") for s in idx] + [(s, "RunawayContinuation") for s in eq]),
                "C4": sorted([(s, t) for s in idx for t in ("PARK", "RunawayContinuation")]
                             + [(s, "RunawayContinuation") for s in eq])}
        pre = open(CB.PREREG, encoding="utf-8").read() if os.path.exists(CB.PREREG) else ""
        ck("B2", got == want and CB.INDEX == ("QQQ", "SPX")
           and all(("| %s | %s |" % (b, d)) in pre for b, d in CB.BOOKS),
           "each book takes exactly PREREG's cells, and the descriptions are PREREG's rows")

        # B3 + B4 fixture
        tr = os.path.join(tmp, "trades")
        os.makedirs(tr)
        open(os.path.join(tr, "2026-11-20.csv"), "w").write(HDR + row("QQQ", "PARK", 100, 2, "2026-11-20T16:00:00+00:00",
                                                                       "2026-11-20T17:00:00+00:00"))
        open(os.path.join(tr, "2026-11-23.csv"), "w").write(
            HDR + row("QQQ", "PARK", 500, 3) + row("AMD", "RunawayContinuation", -300, 2)
            + row("SPX", "RunawayContinuation", 50, 1) + row("AMD", "LiquidityHunt", 999, 9,
                                                              "2026-11-23T14:30:00+00:00", "2026-11-23T15:30:00+00:00"))
        open(os.path.join(tr, "2026-11-24.csv"), "w").write(HDR)                         # a flat session
        open(os.path.join(tr, "2026-11-25.csv"), "w").write(HDR + row("QQQ", "PARK", -400, 2))
        open(os.path.join(tr, "2026-12-04.csv"), "w").write(HDR + row("SPX", "PARK", 70, 1))
        sc = CB.score("2026-11-25", day="2026-11-25", week_start="2026-11-23", trades_dir=tr)
        f2 = sc["windows"]["forward"]["books"]["C2"]
        ok3 = (f2["n"] == 4 and f2["gross"] == -150 and f2["fees"] == 8 and f2["net"] == -158 and f2["ev"] == -37.5
               and f2["up"] == 1 and f2["sessions"] == 3 and f2["worst_day"] == -400 and f2["max_dd"] == -400
               and f2["gross_ex_top2"] == -700 and f2["ci"] is not None
               and CB.BOOT_N == 5000 and CB.BOOT_SEED == 1)
        ck("B3", ok3, f"forward C2 {f2}")
        w = sc["windows"]
        sc2 = CB.score("2026-12-04", trades_dir=tr)
        w2 = sc2["windows"]
        ok4 = (set(w) == {"in_sample", "forward", "combined", "week", "day"}
               and w["in_sample"]["books"]["C1"]["n"] == 1 and w["forward"]["books"]["C1"]["n"] == 3
               and w["combined"]["books"]["C1"]["n"] == 4 and w["day"]["books"]["C1"]["n"] == 1
               and w["forward"]["to"] == "2026-11-25"
               and w2["forward"]["to"] == "2026-12-03" and w2["forward_cumulative"]["to"] == "2026-12-04"
               and w2["forward_cumulative"]["books"]["C1"]["n"] == 4 and w2["forward"]["books"]["C1"]["n"] == 3
               and "2026-12-01" in w2["forward"]["missing_trade_files"]
               and "2026-11-27" in w2["forward"]["missing_trade_files"]
               and "2026-11-26" not in w2["forward"]["missing_trade_files"])
        ck("B4", ok4, "windows %s; forward to %s; cumulative %s; missing %s" % (
            sorted(w), w["forward"]["to"], w2.get("forward_cumulative", {}).get("to"),
            w2["forward"]["missing_trade_files"]))

        # B5
        f3 = w["forward"]["books"]["C3"]           # AMD Runaway 15:00 inside the AMD Hunt 14:30-15:30 -> 1
        f1 = w["forward"]["books"]["C1"]           # QQQ / SPX trades: no Hunt open on those boxes -> 0
        open(os.path.join(tr, "2026-11-23.csv"), "a").write(row("SPX", "OGAP", 1, 1, "2026-11-23T16:00:00+00:00", ""))
        sc3 = CB.score("2026-11-25", trades_dir=tr)
        ck("B5", f3["displaced"] == 1 and f1["displaced"] == 0 and f3["displaced_unmeasurable"] == 0
           and sc3["windows"]["forward"]["books"]["C1"]["displaced_unmeasurable"] >= 1
           and "NOT MEASURED" in CB.render_md(sc),
           f"C3 {f3.get('displaced')} C1 {f1.get('displaced')}; an OGAP with no exit time is unmeasurable")

        # B6
        rk = open(os.path.join(ROOT, "tools", "review_kit.py"), encoding="utf-8").read()
        th = "".join(open(os.path.join(ROOT, "tools", f), encoding="utf-8").read()
                     for f in os.listdir(os.path.join(ROOT, "tools")) if f.startswith("theories") and f.endswith(".py"))
        before = set(os.listdir(tmp))
        CB.main(["--through", "2026-11-25", "--trades", tr])
        ck("B6", "cash_books" not in rk and "cash_books" not in th and set(os.listdir(tmp)) == before
           and "Report only" in CB.render_md(sc) and "paper size" not in open(CB.__file__).read().lower(),
           "the window EV and the theories never read the books; a plain run writes nothing")
        # B7 (amendment 1): the top-two figure only ever beside the bottom-two
        f2b = f2.get("gross_ex_bottom2")
        md = CB.render_md(sc)
        hdr = [ln for ln in md.splitlines() if ln.startswith("| book |")]
        amend = getattr(CB, "amendment_line", lambda: None)()
        real_amend = os.path.exists(os.path.join(os.path.dirname(CB.PREREG), "AMENDMENTS.txt"))
        ck("B7", f2b == 550 and all("ex top-2 winners / ex bottom-2 losers (context)" in h for h in hdr) and hdr
           and all(" / " in ln.split("|")[10] for ln in md.splitlines() if ln.startswith("| C"))
           and "never a qualifier" in md and "never a qualifier" in getattr(CB, "CONCENTRATION", "")
           and (not real_amend or (amend and amend.startswith("2026-11-22T") and "AMENDMENT 1" in amend
                                   and ("Amendment: " + amend) in CB.render_md(CB.score(CB.IN_SAMPLE[1]))))
           and all("gross_ex_bottom2" in m for w in sc["windows"].values() for m in w["books"].values()),
           f"ex bottom-2 {f2b} (want 550 = -150 - (-400 - 300)); headers {hdr[:1]}; amendment {str(amend)[:40]}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print()
    if FAILS:
        print("RED — %s" % ", ".join(FAILS))
        return 1
    print("GREEN — %d checks" % len(RAN))
    return 0


if __name__ == "__main__":
    sys.exit(main())
