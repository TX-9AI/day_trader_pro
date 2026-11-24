#!/usr/bin/env python3
"""
day_trader_pro/tests/check_cash_books.py — v1.3
v1.3  2026-11-24  dtp r583 / CASHBOOK.3 — C5 (the operator, 2026-11-24: "Google in, with plan C4"), frozen in
      ~/reviews/cash_candidate_c5_20261124/PREREG.md. B2-B8 score C1-C4 alone (score(books=PREREG_BOOKS)), so their
      meaning is the v1.2 one; B2's descriptions are read from the PREREG each book is frozen in. NEW B9-B12:
  B9  C5's membership is exactly as frozen: on every (14 symbols x setup) cell, C5 takes PARK and Runaway on QQQ/SPX and
      Runaway only on UNH, AMZN, TSLA, SOFI, CVX, NFLX, GOOGL (never PARK on an equity, never NVDA/AMD/META/CRM/AVGO,
      never Hunt/OGAP/other); its description is C5's PREREG row word for word
  B10 the seal: C5_PREREG_SHA is the literal below, the file's sha256 and SEAL.txt's; --check-prereg prints C5 SEALED
      (rc 0) and a changed copy reads SEAL BROKEN (rc 1); score() carries sealed=True and the md says "seal verified"
  B11 C1-C4 UNCHANGED: score(books=PREREG_BOOKS), render_md and the CLI (--books C1,C2,C3,C4: --md, --json and
      --check-prereg) are byte-for-byte the v1.5 scorer at 926bf64 (r582), on the real trades and on a fixture; and
      in the default run (C5 in) every C1-C4 figure of every window equals the C1-C4-only run's
  B12 C5's windows: its own forward window (forward_c5) from 2026-11-24 holding C5 alone; C1-C4's forward windows never
      hold C5; in-sample and combined hold C5 with the hindsight note; the day and week count C5 from 2026-11-24 only;
      the ranking line carries C5 with "(hindsight list; forward from 11-24)"; no forward_c5 before 11-24
      BORN RED on 926bf64 (r582): no C5 (B9-B12; B2-B8 green there).
v1.2  2026-11-22  dtp r574 / CASHBOOK.2, PREREG amendment 2 (the operator, 2026-11-22: "I want the best risk to reward
      balance, the highest earning combination with as low as we can get drawdowns"; "just treat them as bank
      holidays. No trading."). B4: 2026-11-27 (a 13:00 half day) is no longer a forward session. B7: the concentration
      column moved one right. NEW B8: rtd = net / |max DD| on every book and window (None with no drawdown, printed
      "no drawdown"), the tables list the books in the combined window's rtd order, a ranking line names them, and
      amendment_lines() carries both amendments when the real AMENDMENTS.txt is readable.
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
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
FAILS, RAN = [], []
BASE_REV = "926bf64"           # r582: tools/cash_books.py v1.5, the C1-C4 scorer B11 holds the omitted-C5 output to
C5_SHA = "693bb7338bf9cc67d252d8c395dcde971f4db280e3015b66d90abf16ad4327ec"     # SEAL.txt, 2026-11-24T13:55:24Z
C5_ROW = ("| C5 | C4's structure with a narrower equity list: PARK and Runaway on the indexes (QQQ, SPX); Runaway only "
          "on UNH, AMZN, TSLA, SOFI, CVX, NFLX and GOOGL |")
EQ12 = ("NVDA", "AMD", "META", "CRM", "AVGO", "GOOGL", "UNH", "AMZN", "TSLA", "SOFI", "CVX", "NFLX")
C5_EQ = ("UNH", "AMZN", "TSLA", "SOFI", "CVX", "NFLX", "GOOGL")


def ck(n, ok, msg=""):
    RAN.append(n)
    print(f"  {n:<3} {'PASS' if ok else 'FAIL'}  {msg}")
    if not ok:
        FAILS.append(n)


HDR = ("sym,trade_id,strategy,direction,contracts,entry_premium,exit_premium,pnl_usd,entry_time,exit_time,exit_reason,"
       "fee\n")


def row(sym, strat, pnl, fee=1.0, ent="2026-11-23T15:00:00+00:00", ext="2026-11-23T16:00:00+00:00"):
    return f"{sym},t,{strat},long,1,1,1,{pnl},{ent},{ext},x,{fee}\n"


def b9(CB):
    """C5's membership exactly as frozen."""
    try:
        setups = ("PARK", "RunawayContinuation", "LiquidityHunt", "OGAP", "Breakout", "TCS")
        cells = [(s, t) for s in ("QQQ", "SPX") + EQ12 for t in setups]
        got = sorted(c for c in cells if CB.in_book("C5", *c))
        want = sorted([(s, t) for s in ("QQQ", "SPX") for t in ("PARK", "RunawayContinuation")]
                      + [(s, "RunawayContinuation") for s in C5_EQ])
        pre = open(CB.C5_PREREG, encoding="utf-8").read() if os.path.exists(CB.C5_PREREG) else ""
        desc = dict(CB.BOOKS).get("C5")
        ok = (got == want and tuple(CB.C5_EQUITIES) == C5_EQ and "C5" in dict(CB.BOOKS)
              and ("| C5 | %s |" % desc) == C5_ROW and C5_ROW in pre
              and "equity set {UNH, AMZN, TSLA, SOFI, CVX, NFLX, GOOGL}" in pre and "index set {QQQ, SPX}" in pre
              and not any(CB.in_book("C5", s, t) for s in ("NVDA", "AMD", "META", "CRM", "AVGO") for t in setups)
              and not any(CB.in_book("C5", s, "PARK") for s in EQ12))
        ck("B9", ok, "C5 takes %d cells (want %d); missing %s extra %s; PREREG row %s" % (
            len(got), len(want), sorted(set(want) - set(got))[:3], sorted(set(got) - set(want))[:3],
            "matches" if C5_ROW in pre and desc and ("| C5 | %s |" % desc) == C5_ROW else "DIFFERS or unreadable"))
    except Exception as e:                                   # noqa: BLE001 (HEAD: no C5)
        ck("B9", False, "%s: %s" % (type(e).__name__, e))


def b10(CB, tmp):
    """C5's seal, hard-coded and verified like PREREG_SHA."""
    try:
        seal = os.path.join(os.path.dirname(CB.C5_PREREG), "SEAL.txt")
        fsha = hashlib.sha256(open(CB.C5_PREREG, "rb").read()).hexdigest()
        ssha = open(seal, encoding="utf-8").read().split()[0]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = CB.main(["--check-prereg"])
        bad = os.path.join(tmp, "C5_PREREG_changed.md")
        open(bad, "wb").write(open(CB.C5_PREREG, "rb").read() + b"\n")
        out2 = io.StringIO()
        with contextlib.redirect_stdout(out2):
            rc2 = CB.main(["--check-prereg", "--c5-prereg", bad])
        sc = CB.score("2026-11-20")
        ok = (CB.C5_PREREG_SHA == C5_SHA == fsha == ssha and rc == 0 and "C5 PREREG SEALED" in out.getvalue()
              and rc2 == 1 and "C5 PREREG SEAL BROKEN" in out2.getvalue()
              and sc["c5"]["sealed"] is True and sc["c5"]["prereg_sha"] == C5_SHA
              and "seal verified" in CB.render_md(sc))
        ck("B10", ok, "constant %s file %s SEAL.txt %s; --check-prereg rc %s / changed copy rc %s" % (
            CB.C5_PREREG_SHA[:12], fsha[:12], ssha[:12], rc, rc2))
    except Exception as e:                                   # noqa: BLE001
        ck("B10", False, "%s: %s" % (type(e).__name__, e))


def _base_module(tmp):
    src = subprocess.run(["git", "-C", ROOT, "show", BASE_REV + ":tools/cash_books.py"], capture_output=True,
                         text=True, check=True).stdout
    assert "cash_books.py  v1.5" in src, "the base is not v1.5"
    p = os.path.join(tmp, "cash_books_v15.py")
    open(p, "w", encoding="utf-8").write(src)
    spec = importlib.util.spec_from_file_location("cash_books_v15", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)                               # market_calendar / review_kit already imported
    return m


def _cli(mod, argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = mod.main(argv)
    return rc, out.getvalue()


def b11(CB, tmp, tr, P4, kw):
    """C1-C4 byte-for-byte unchanged when C5 is omitted; C5 never moves a C1-C4 figure."""
    try:
        if not kw:
            raise RuntimeError("no score(books=...): C5 cannot be omitted")
        OLD = _base_module(tmp)
        cases = [("2026-11-25", "2026-11-25", "2026-11-23", tr), ("2026-12-04", None, None, tr),
                 ("2026-11-24", "2026-11-24", None, tr)]
        if os.path.isdir(CB.TRADES):
            cases += [("2026-11-20", None, None, CB.TRADES), ("2026-11-23", "2026-11-23", "2026-11-23", CB.TRADES),
                      (sorted(os.listdir(CB.TRADES))[-1][:10], None, None, CB.TRADES)]
        diffs = []
        for thr, day, wk, d in cases:
            a = OLD.score(thr, day=day, week_start=wk, trades_dir=d)
            b = CB.score(thr, day=day, week_start=wk, trades_dir=d, books=P4)
            if json.dumps(a, sort_keys=False) != json.dumps(b, sort_keys=False):
                diffs.append("score %s %s" % (thr, os.path.basename(d)))
            if OLD.render_md(a) != CB.render_md(b):
                diffs.append("md %s %s" % (thr, os.path.basename(d)))
            full = CB.score(thr, day=day, week_start=wk, trades_dir=d)
            for wn, w in b["windows"].items():
                for bk in P4:
                    if full["windows"][wn]["books"].get(bk) != w["books"][bk]:
                        diffs.append("C5-in moves %s %s %s" % (bk, wn, thr))
            if full["ranking"] and [x for x in full["ranking"] if x != "C5"] != b["ranking"]:
                diffs.append("C5-in reorders C1-C4 %s" % thr)
            argv = ["--through", thr, "--trades", d] + (["--day", day] if day else []) + (
                ["--week-start", wk] if wk else [])
            for flag in ("--md", "--json"):
                po, pn = os.path.join(tmp, "o" + flag[2:]), os.path.join(tmp, "n" + flag[2:])
                OLD.main(argv + [flag, po])
                CB.main(argv + [flag, pn, "--books", "C1,C2,C3,C4"])
                if open(po, "rb").read() != open(pn, "rb").read():
                    diffs.append("cli %s %s" % (flag, thr))
                os.remove(po)
                os.remove(pn)
        if os.path.isdir(CB.TRADES):
            if _cli(OLD, ["--check-prereg"]) != _cli(CB, ["--check-prereg", "--books", "C1,C2,C3,C4"]):
                diffs.append("--check-prereg")
        ck("B11", not diffs and len(cases) >= 3, "%d case(s) against %s v1.5; differences %s" % (
            len(cases), BASE_REV, diffs[:5] or "none"))
    except Exception as e:                                   # noqa: BLE001
        ck("B11", False, "%s: %s" % (type(e).__name__, e))


def b12(CB, tmp):
    """C5's own forward window, the hindsight tag and note, the day and week from 11-24."""
    try:
        tr = os.path.join(tmp, "trades12")
        os.makedirs(tr)
        open(os.path.join(tr, "2026-11-20.csv"), "w").write(HDR + row("UNH", "RunawayContinuation", 300, 2,
                                                                       "2026-11-20T16:00:00+00:00",
                                                                       "2026-11-20T17:00:00+00:00"))
        open(os.path.join(tr, "2026-11-23.csv"), "w").write(HDR + row("QQQ", "PARK", 500, 3)
                                                            + row("GOOGL", "RunawayContinuation", -100, 1))
        open(os.path.join(tr, "2026-11-24.csv"), "w").write(
            HDR + row("SPX", "RunawayContinuation", 200, 2, "2026-11-24T15:00:00+00:00", "2026-11-24T16:00:00+00:00")
            + row("NVDA", "RunawayContinuation", -900, 2, "2026-11-24T15:00:00+00:00", "2026-11-24T16:00:00+00:00")
            + row("TSLA", "PARK", 777, 2, "2026-11-24T15:00:00+00:00", "2026-11-24T16:00:00+00:00"))
        open(os.path.join(tr, "2026-11-25.csv"), "w").write(
            HDR + row("CVX", "RunawayContinuation", -50, 1, "2026-11-25T15:00:00+00:00", "2026-11-25T16:00:00+00:00"))
        s23 = CB.score("2026-11-23", day="2026-11-23", week_start="2026-11-23", trades_dir=tr)
        sc = CB.score("2026-11-25", day="2026-11-25", week_start="2026-11-23", trades_dir=tr)
        W = sc["windows"]
        f5 = W.get("forward_c5") or {}
        md = CB.render_md(sc)
        rank = [ln for ln in md.splitlines() if ln.startswith("**Ranking")]
        sec = md.split("## C5 forward", 1)[-1].split("\n## ", 1)[0] if "## C5 forward" in md else ""
        ok = ("forward_c5" not in s23["windows"] and "C5" not in s23["windows"]["day"]["books"]
              and "C5" not in s23["windows"]["week"]["books"]
              and f5.get("from") == "2026-11-24" and f5.get("to") == "2026-11-25" and set(f5.get("books", {})) == {"C5"}
              and f5["books"]["C5"]["n"] == 2 and f5["books"]["C5"]["gross"] == 150 and f5["sessions"] == 2
              and "displaced" in f5["books"]["C5"]
              and "C5" not in W["forward"]["books"] and set(W["forward"]["books"]) == {"C1", "C2", "C3", "C4"}
              and W["in_sample"]["books"]["C5"]["n"] == 1 and W["combined"]["books"]["C5"]["n"] == 5
              and W["week"]["books"]["C5"]["n"] == 2 and W["week"]["books"]["C5"]["sessions"] == 2
              and W["day"]["books"]["C5"]["n"] == 1 and W["day"]["books"]["C5"]["gross"] == -50
              and len(sc["ranking"]) == 5 and rank and CB.C5_TAG == "(hindsight list; forward from 11-24)"
              and ("C5 " in rank[0] and CB.C5_TAG in rank[0])
              and "(forward %s) %s" % ("no drawdown" if f5["books"]["C5"]["rtd"] is None
                                       else "%.2f" % f5["books"]["C5"]["rtd"], CB.C5_TAG) in rank[0]
              and md.startswith("# Cash candidate books C1-C4 and C5, through 2026-11-25")
              and md.count(CB.HINDSIGHT_NOTE) == 2 and "| C5 |" in sec
              and not any(ln.startswith("| C1 |") for ln in sec.splitlines())
              and "never evidence" in md and "Report only" in md)
        ck("B12", ok, "forward_c5 %s..%s books %s n %s; week C5 n %s; day C5 n %s; ranking %s" % (
            f5.get("from"), f5.get("to"), sorted(f5.get("books", {})), (f5.get("books", {}).get("C5") or {}).get("n"),
            (W.get("week", {}).get("books", {}).get("C5") or {}).get("n"),
            (W.get("day", {}).get("books", {}).get("C5") or {}).get("n"), (rank or ["-"])[0][-120:]))
    except Exception as e:                                   # noqa: BLE001
        ck("B12", False, "%s: %s" % (type(e).__name__, e))


def main():
    try:
        import cash_books as CB
    except ImportError as e:
        for n in ("B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B9", "B10", "B11", "B12"):
            ck(n, False, f"no tools/cash_books.py ({e})")
        print("\nRED — " + ", ".join(FAILS))
        return 1
    tmp = tempfile.mkdtemp(prefix="ckcb_")
    P4 = tuple(getattr(CB, "PREREG_BOOKS", None) or [b for b, _d in CB.BOOKS])       # v1.3: C1-C4 alone
    kw = {"books": P4} if hasattr(CB, "PREREG_BOOKS") else {}
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
        got = {b: sorted((s, t) for s, t in cells if CB.in_book(b, s, t)) for b in P4}
        idx, eq = ("QQQ", "SPX"), ("AMD", "NVDA")
        want = {"C1": sorted((s, t) for s in idx for t in ("PARK", "RunawayContinuation")),
                "C2": sorted((s, t) for s in idx + eq for t in ("PARK", "RunawayContinuation")),
                "C3": sorted([(s, "PARK") for s in idx] + [(s, "RunawayContinuation") for s in eq]),
                "C4": sorted([(s, t) for s in idx for t in ("PARK", "RunawayContinuation")]
                             + [(s, "RunawayContinuation") for s in eq])}
        pre = open(CB.PREREG, encoding="utf-8").read() if os.path.exists(CB.PREREG) else ""
        ck("B2", got == want and CB.INDEX == ("QQQ", "SPX")
           and all(("| %s | %s |" % (b, d)) in pre for b, d in CB.BOOKS if b in P4),
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
        sc = CB.score("2026-11-25", day="2026-11-25", week_start="2026-11-23", trades_dir=tr, **kw)
        f2 = sc["windows"]["forward"]["books"]["C2"]
        ok3 = (f2["n"] == 4 and f2["gross"] == -150 and f2["fees"] == 8 and f2["net"] == -158 and f2["ev"] == -37.5
               and f2["up"] == 1 and f2["sessions"] == 3 and f2["worst_day"] == -400 and f2["max_dd"] == -400
               and f2["gross_ex_top2"] == -700 and f2["ci"] is not None
               and CB.BOOT_N == 5000 and CB.BOOT_SEED == 1)
        ck("B3", ok3, f"forward C2 {f2}")
        w = sc["windows"]
        sc2 = CB.score("2026-12-04", trades_dir=tr, **kw)
        w2 = sc2["windows"]
        ok4 = (set(w) == {"in_sample", "forward", "combined", "week", "day"}
               and w["in_sample"]["books"]["C1"]["n"] == 1 and w["forward"]["books"]["C1"]["n"] == 3
               and w["combined"]["books"]["C1"]["n"] == 4 and w["day"]["books"]["C1"]["n"] == 1
               and w["forward"]["to"] == "2026-11-25"
               and w2["forward"]["to"] == "2026-12-03" and w2["forward_cumulative"]["to"] == "2026-12-04"
               and w2["forward_cumulative"]["books"]["C1"]["n"] == 4 and w2["forward"]["books"]["C1"]["n"] == 3
               and "2026-12-01" in w2["forward"]["missing_trade_files"]
               and "2026-11-27" not in w2["forward"]["missing_trade_files"]
               and "2026-11-26" not in w2["forward"]["missing_trade_files"])
        ck("B4", ok4, "windows %s; forward to %s; cumulative %s; missing %s" % (
            sorted(w), w["forward"]["to"], w2.get("forward_cumulative", {}).get("to"),
            w2["forward"]["missing_trade_files"]))

        # B5
        f3 = w["forward"]["books"]["C3"]           # AMD Runaway 15:00 inside the AMD Hunt 14:30-15:30 -> 1
        f1 = w["forward"]["books"]["C1"]           # QQQ / SPX trades: no Hunt open on those boxes -> 0
        open(os.path.join(tr, "2026-11-23.csv"), "a").write(row("SPX", "OGAP", 1, 1, "2026-11-23T16:00:00+00:00", ""))
        sc3 = CB.score("2026-11-25", trades_dir=tr, **kw)
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
           and all(" / " in ln.split("|")[11] for ln in md.splitlines() if ln.startswith("| C"))
           and "never a qualifier" in md and "never a qualifier" in getattr(CB, "CONCENTRATION", "")
           and (not real_amend or (amend and amend.startswith("2026-11-22T") and "AMENDMENT 1" in amend
                                   and ("Amendment: " + amend) in CB.render_md(CB.score(CB.IN_SAMPLE[1], **kw))))
           and all("gross_ex_bottom2" in m for w in sc["windows"].values() for m in w["books"].values()),
           f"ex bottom-2 {f2b} (want 550 = -150 - (-400 - 300)); headers {hdr[:1]}; amendment {str(amend)[:40]}")
        # B8 (amendment 2): return to drawdown ranks the books; it never filters
        comb = sc["windows"]["combined"]["books"]
        rank = sc.get("ranking") or []
        rows8 = [ln.split("|")[1].strip() for ln in md.splitlines() if ln.startswith("| C")]
        want_rank = sorted(list(P4), key=lambda b: (
            0 if comb[b].get("rtd") is None and comb[b]["n"] else 1, -(comb[b].get("rtd") or 0), list(P4).index(b)))
        flat = CB.metrics([{"day": "2026-11-23", "pnl": 10.0, "fee": 1.0}], ["2026-11-23"])
        lines = getattr(CB, "amendment_lines", lambda: [])()
        ck("B8", f2.get("rtd") == -0.40 and CB.rtd(-158, -400) == -0.40 and CB.rtd(500, 0) is None
           and flat["rtd"] is None and rank == want_rank and len(rank) == 4
           and all(rows8[i:i + 4] == rank for i in range(0, len(rows8), 4)) and rows8
           and all("net / max DD" in h for h in hdr) and "Ranking, return to drawdown" in md
           and all("rtd" in m for w in sc["windows"].values() for m in w["books"].values())
           and all(m["n"] >= 0 for m in comb.values())
           and (not real_amend or (len(lines) >= 2 and "AMENDMENT 1" in lines[0] and "AMENDMENT 2" in lines[1])),
           f"forward C2 rtd {f2.get('rtd')} (want -0.40 = -158 / 400); ranking {rank} vs {want_rank}; "
           f"table rows {rows8[:4]}; amendments {len(lines)}")

        b9(CB)
        b10(CB, tmp)
        b11(CB, tmp, tr, P4, kw)
        b12(CB, tmp)
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
