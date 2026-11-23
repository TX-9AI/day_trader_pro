#!/usr/bin/env python3
"""
day_trader_pro/tests/check_as_cash.py  v1.1
v1.1  2026-11-23  dtp r580 — A9 reads the prompts' own versions (daily recap v1.8, nightly review v1.10: the live-setup
      wording after OTV5 r153). Same checks otherwise.
v1.0  2026-11-22  dtp r578 / CAP.11 (control's half of OTV5 r151) — new. THE REPORTS HEADLINE "AS CASH WOULD HAVE TRADED".
      OTV5 r151 makes the daily catastrophic cap record only on a paper box (the operator, 2026-11-22: "Is there any way
      we can make the catastrophic cap only apply to cash? As in, there's no harm in letting paper run & we can just note
      if the breaker would have popped."; "Yes"): it writes one daily_cap_would_pop row, keeps trading and tags what it
      opens after it after_cap = 1; and a cash box books OGAP paper (paper_trade = 1) beside its cash rows (OTV5 r150).
      Every report reads one rule (tools/review_kit.split) and headlines the HEADLINE rows. Driven on scratch fixtures:
      FULL (a paper day past the would-be cap: NVDA Runaway -1,100 headline, a Hunt +300 and an OGAP +50 after_cap;
      a cash QQQ day: PARK +400 cash, OGAP -80 paper on the cash box, AMD Runaway -50 after_cap; an old-format day with
      neither column) against STRIPPED (the same files with every after_cap and paper-on-cash row removed).

  A1  THE RULE: review_kit.split books a cash row and a paper row on a box with no cash row HEADLINE, a paper row on
      a box with a cash row that day PAPER_ON_CASH, an after_cap row AFTER_CAP, and a row with neither column (a CSV
      before this revision) HEADLINE; a blank paper_trade is paper (the schema's default), never cash
  A2  THE TRADE CSV: TRADE_COLS is r577's seventeen columns, in order, then paper_trade and after_cap (nothing dropped);
      `trades` writes both from the warehouse record; with a breaker source it writes ~/reviews/breaker/DAY.csv (the
      would-pop row, the day's ET date only, an OTV4TEST box dropped) and never a file in the trades folder
  A3  review_kit: window() on FULL equals window() on STRIPPED in every headline figure (n, total, EV, interval, fees,
      ex worst, theories, exec block); FULL's extra (the non-OGAP after_cap rows) is n 2 net +250, on 12-04 n 1 net
      -50; the OGAP line holds the cash box's OGAP paper row and not the after_cap OGAP (its own extra, n 1 +50);
      giveback and hunt on FULL equal STRIPPED; the window_ev / theories CSV rows equal
  A4  cash_books: every book metric of every window equal FULL vs STRIPPED; FULL carries extras (C2 combined n 1
      gross -50) and its md one "Extra paper after the breaker" line, STRIPPED's md none and otherwise FULL's md
  A5  runaway_watch: every equity's figures, status and trend equal FULL vs STRIPPED; FULL's AMD carries extra n 1
      net -50 (after the fee) and its md the extras line; a NOTES.txt beside WATCH.md prints its NOTE first lines
      ("Note: ...") and no file prints none; --check-seal unchanged (the sealed sha constant is r577's)
  A6  weekly_facts: week_book, week_by_strategy and the OGAP vs PARK block equal FULL vs STRIPPED; FULL's F carries
      extra_after_cap (week n 2) and its md the extras line; STRIPPED's md none
  A7  daily_brief (its own venv, /home/ubuntu/venvs/daily_brief): compute() on the FULL cash day's records headlines
      the HEADLINE rows only (QQQ PARK +400 and SPX Runaway +100, total +500), carries after_cap (AMD -50) and
      paper_on_cash (QQQ OGAP -80) beside, reads the would-pop record from the breaker file, and extras_lines says
      both; --facts carries after_cap, paper_on_cash and would_pop
  A8  daily_recap context: the "As cash" block names the extra, the paper row on a cash box and the would-pop record;
      NOT READ when the breaker file is missing
  A9  the prompts: the daily recap (v1.7), nightly review (v1.9) and Saturday brief prompts carry the as-cash rule
      (headline as cash, the extra beside never added in, the would-pop record, OGAP's paper on a cash box on OGAP's
      own line)
  A10 the OTV5 tree this control reads (~/OTV5 HEAD, by text: nothing of OTV5 imported) has the after_cap column
      and the daily_cap_would_pop reason, so the names this file reads are the ones the boxes write
  A11 A CASH BOX THAT TRADED NOTHING CASH IS STILL A CASH BOX: review_kit.box_modes reads each box's day from the
      conductor's extract (the last "Service mode: LIVE|PAPER" line, else the "OptionsBot [MODE] STARTED" marker; a box
      with neither is absent); split puts a paper row on a LIVE box's day PAPER_ON_CASH with zero cash rows, keeps it
      HEADLINE on a PAPER box's day and with no extract (the cash-row fallback), and a cash row stays decisive; the
      trade CSV readers pick the extract up beside the file (modes_for_file); on 12-07 (QQQ live, only an OGAP paper
      trade) the daily recap's As cash block names it and the daily brief's QQQ row is gone (cash only) while OGAP's
      paper row sits beside
BORN RED on 9014b1f (r577): A1-A9, A11 (no split, no after_cap column, no breaker file, no extras); A10 red until OTV5 r151
lands - so OTV5 r151 lands FIRST.
Run:  python3 tests/check_as_cash.py
"""
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
sys.path.insert(0, TOOLS)
sys.path.insert(0, ROOT)
FAILS, RAN = [], []
ALL = ("A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "A10", "A11")
OTV5 = os.path.expanduser(os.environ.get("DTP_CONTROL_REPO", "~/OTV5"))
BRIEF_PY = "/home/ubuntu/venvs/daily_brief/bin/python"
R577_COLS = ["sym", "trade_id", "strategy", "direction", "contracts", "entry_premium", "exit_premium", "pnl_usd",
             "entry_time", "exit_time", "exit_reason", "fee", "mfe_premium", "entry_exec_premium",
             "exit_exec_premium", "pnl_exec_usd", "would_fill_live"]


def ck(n, ok, msg=""):
    RAN.append(n)
    print(f"  {n:<4} {'PASS' if ok else 'FAIL'}  {msg}")
    if not ok:
        FAILS.append(n)


# (day, sym, id, strategy, direction, contracts, entry, exit, mfe, pnl, entry ET, fee, paper_trade, after_cap, extra?)
OLD_DAY = "2026-11-23"
PAPER_DAY = "2026-11-24"
CASH_DAY = "2026-12-04"
ROWS = [
    (PAPER_DAY, "NVDA", "t1", "RunawayContinuation", "long", 5, 2.0, 0.0, 2.2, -1100.0, "T09:40:00-05:00", "6.00", 1, "", 0),
    (PAPER_DAY, "NVDA", "t2", "LiquidityHunt", "long", 3, 1.0, 2.0, 2.5, 300.0, "T10:20:00-05:00", "4.00", 1, 1, 1),
    (PAPER_DAY, "NVDA", "t3", "OGAP", "short", 2, 1.5, 1.75, 1.9, 50.0, "T10:21:00-05:00", "", 1, 1, 1),
    (PAPER_DAY, "AMD", "t4", "RunawayContinuation", "long", 4, 1.0, 1.5, 1.6, 200.0, "T09:36:00-05:00", "5.00", 1, "", 0),
    (CASH_DAY, "QQQ", "t5", "PARK", "long", 1, 4.0, 8.0, 8.5, 400.0, "T11:01:00-05:00", "1.50", 0, "", 0),
    (CASH_DAY, "QQQ", "t6", "OGAP", "short", 1, 4.2, 3.4, 4.5, -80.0, "T09:50:00-05:00", "1.50", 1, "", 1),
    (CASH_DAY, "SPX", "t7", "RunawayContinuation", "long", 1, 10.0, 11.0, 12.0, 100.0, "T09:37:00-05:00", "2.50", 1, "", 0),
    (CASH_DAY, "AMD", "t8", "RunawayContinuation", "long", 2, 1.0, 0.75, 1.1, -50.0, "T10:05:00-05:00", "2.00", 1, 1, 1),
]
OLD = [(OLD_DAY, "AMD", "t9", "RunawayContinuation", "long", 2, 1.0, 1.1, 1.2, 20.0, "T09:38:00-05:00", "2.00"),
       (OLD_DAY, "SPX", "t10", "PARK", "long", 1, 30.0, 25.0, 33.0, -500.0, "T11:01:00-05:00", "")]


def write_fixture(d, K, stripped):
    os.makedirs(os.path.join(d, "trades"), exist_ok=True)
    os.makedirs(os.path.join(d, "scripts"), exist_ok=True)
    live = os.path.join(os.path.expanduser("~"), "reviews", "scripts", "theories.py")
    if os.path.exists(live):
        shutil.copy(live, os.path.join(d, "scripts"))
    else:
        with open(os.path.join(d, "scripts", "theories.py"), "w") as fh:
            fh.write("from datetime import datetime\nfrom zoneinfo import ZoneInfo\nET = ZoneInfo('America/New_York')\n"
                     "FILTERS = [(l, (lambda x: True)) for l in ('baseline', 'T1 no SPX', 'T2 no entries after 10:01',"
                     " 'T3 no GEXPin/PARK', 'T1+T2', 'T1+T3', 'T1+T2+T3')]\n"
                     "def norm(sym, strat, pnl, entry_iso):\n"
                     "    t = datetime.fromisoformat(entry_iso.replace('Z', '+00:00')).astimezone(ET)\n"
                     "    return dict(sym=sym, strat=strat, pnl=float(pnl), day=t.date().isoformat(),"
                     " sec=t.hour * 3600 + t.minute * 60 + t.second)\n")
    for day in (PAPER_DAY, CASH_DAY):
        with open(os.path.join(d, "trades", day + ".csv"), "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=R577_COLS + ["paper_trade", "after_cap"])   # this revision's CSV
            w.writeheader()
            for (dd, s, tid, st, di, c, e, x, mf, p, t, fee, pt, ac, extra) in ROWS:
                if dd != day or (stripped and extra):
                    continue
                w.writerow(dict(sym=s, trade_id=tid, strategy=st, direction=di, contracts=c, entry_premium=e,
                                exit_premium=x, pnl_usd=p, entry_time=dd + t, exit_time=dd + t, exit_reason="x",
                                fee=fee, mfe_premium=mf, paper_trade=pt, after_cap=ac))
    with open(os.path.join(d, "trades", OLD_DAY + ".csv"), "w", newline="") as fh:     # the r577 header: 17 columns
        w = csv.DictWriter(fh, fieldnames=R577_COLS)
        w.writeheader()
        for (dd, s, tid, st, di, c, e, x, mf, p, t, fee) in OLD:
            w.writerow(dict(sym=s, trade_id=tid, strategy=st, direction=di, contracts=c, entry_premium=e,
                            exit_premium=x, pnl_usd=p, entry_time=dd + t, exit_time=dd + t, exit_reason="x", fee=fee,
                            mfe_premium=mf))
    os.makedirs(os.path.join(d, "breaker"), exist_ok=True)
    with open(os.path.join(d, "breaker", PAPER_DAY + ".csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=getattr(K, "BREAKER_COLS", ["sym", "event_time", "reason", "session_losses",
                                                                      "notes"]))
        w.writeheader()
        w.writerow(dict(sym="NVDA", event_time=PAPER_DAY + "T15:15:00+00:00", reason="daily_cap_would_pop",
                        session_losses=1, notes="breaker would have popped at 10:15 ET, day net -$1,100.00 (limit "
                        "$1,050.00; paper: record only, trading continues, later entries tagged after_cap)"))


def strip_extra_line(md):
    return "\n".join(ln for ln in md.splitlines() if ln.strip() and "Extra paper after the breaker" not in ln
                     and "extra paper after the breaker" not in ln)


def main():
    tmp = tempfile.mkdtemp(prefix="check_as_cash_")
    try:
        try:
            import review_kit as K
        except Exception as e:                                   # noqa: BLE001
            for n in ALL:
                ck(n, False, "review_kit import failed: %s" % e)
            return 1
        full, strp = os.path.join(tmp, "full"), os.path.join(tmp, "stripped")
        write_fixture(full, K, False)
        write_fixture(strp, K, True)

        # ── A1 the rule ──
        try:
            rows = [dict(sym="QQQ", paper_trade="0", after_cap=""), dict(sym="QQQ", paper_trade="1", after_cap=""),
                    dict(sym="NVDA", paper_trade="1", after_cap="1"), dict(sym="NVDA", paper_trade="1", after_cap=""),
                    dict(sym="AMD"), dict(sym="SPX", paper_trade="", after_cap=None),
                    dict(sym="TSLA", paper_trade=""), dict(sym="TSLA", paper_trade="1")]
            got = K.split(rows)
            want = [K.HEADLINE, K.PAPER_ON_CASH, K.AFTER_CAP, K.HEADLINE, K.HEADLINE, K.HEADLINE, K.HEADLINE,
                    K.HEADLINE]
            ck("A1", got == want, "split -> %s" % got)
        except Exception as e:                                   # noqa: BLE001
            ck("A1", False, "%s: %s" % (type(e).__name__, e))

        # ── A2 the trade CSV and the breaker file ──
        try:
            rv = os.path.join(tmp, "a2")
            os.makedirs(rv)
            K.REVIEWS = rv
            recs = [dict(symbol="QQQ", trade_id="c1", strategy="PARK", direction="long", contracts=1,
                         entry_premium=4.0, exit_premium=8.0, pnl_usd=400.0, entry_time="2026-12-04T16:01:00+00:00",
                         exit_time="2026-12-04T17:00:00+00:00", exit_reason="x", paper_trade=0),
                    dict(symbol="NVDA", trade_id="p1", strategy="LiquidityHunt", direction="long", contracts=1,
                         entry_premium=1.0, exit_premium=2.0, pnl_usd=100.0, entry_time="2026-12-04T15:20:00+00:00",
                         exit_time="2026-12-04T16:00:00+00:00", exit_reason="x", paper_trade=1, after_cap=1)]
            brk = [dict(box="NVDA", event_time="2026-12-04T15:15:00+00:00", reason="daily_cap_would_pop",
                        session_losses=1, notes="breaker would have popped at 10:15 ET, day net -$1,100.00"),
                   dict(box="NVDA", event_time="2026-12-04T15:15:00+00:00", reason="daily_cap_would_pop",
                        session_losses=1, notes="breaker would have popped at 10:15 ET, day net -$1,100.00"),
                   dict(box="AAL", event_time="2026-12-04T15:00:00+00:00", reason="daily_cap_hit", notes="x"),
                   dict(box="SPX", event_time="2026-12-05T06:00:00+00:00", reason="daily_cap_hit", notes="next ET day")]
            K.cmd_trades(CASH_DAY, recs=recs, fee_of=lambda r: None, breaker_of=lambda day: brk)
            tr = list(csv.DictReader(open(os.path.join(rv, "trades", CASH_DAY + ".csv"))))
            hdr = open(os.path.join(rv, "trades", CASH_DAY + ".csv")).readline().strip().split(",")
            bk = list(csv.DictReader(open(os.path.join(rv, "breaker", CASH_DAY + ".csv"))))
            in_trades = sorted(os.listdir(os.path.join(rv, "trades")))
            ok = (K.TRADE_COLS == R577_COLS + ["paper_trade", "after_cap"] and hdr == K.TRADE_COLS
                  and [(r["trade_id"], r["paper_trade"], r["after_cap"]) for r in tr] == [("p1", "1", "1"), ("c1", "0", "")]
                  and [(r["sym"], r["reason"]) for r in bk] == [("NVDA", "daily_cap_would_pop")]
                  and in_trades == [CASH_DAY + ".csv"] and K.read_breaker(CASH_DAY)[0]["reason"] == K.WOULD_POP)
            ck("A2", ok, "cols=%s rows=%s breaker=%s trades dir=%s" % (
                K.TRADE_COLS[17:], [(r["trade_id"], r["paper_trade"], r["after_cap"]) for r in tr],
                [(r["sym"], r["reason"]) for r in bk], in_trades))
        except Exception as e:                                   # noqa: BLE001
            ck("A2", False, "%s: %s" % (type(e).__name__, e))

        # ── A3 review_kit window / OGAP / giveback / hunt ──
        try:
            import importlib
            res = {}
            for tag, d in (("full", full), ("strp", strp)):
                os.environ["DTP_REVIEWS_DIR"] = d
                K.REVIEWS = d
                sys.modules.pop("theories", None)
                w = K.window(CASH_DAY)
                head = {k: v for k, v in w.items() if k not in ("after_cap",)}
                og = [(x["sym"], x["pnl"]) for x in K.ogap_rows(CASH_DAY)]
                ox = [(x["sym"], x["pnl"]) for x in K.extra_rows(CASH_DAY, ogap=True)]
                gb = [K.cmd_giveback(day, write=False) for day in (PAPER_DAY, CASH_DAY)]
                gb = [{k: v for k, v in g.items() if k != "rows"} for g in gb]
                hu = [K.hunt(day) for day in (PAPER_DAY, CASH_DAY)]
                K.cmd_window(CASH_DAY, write=True)
                csvs = [open(os.path.join(d, f)).read() for f in ("window_ev.csv", "theories.csv")]
                res[tag] = dict(head=json.dumps(head, sort_keys=True, default=str), extra=w["after_cap"], og=og, ox=ox,
                                gb=gb, hu=json.dumps(hu, sort_keys=True), csvs=csvs)
            F, S = res["full"], res["strp"]
            xa = F["extra"]
            ok = (F["head"] == S["head"] and F["gb"] == S["gb"] and F["hu"] == S["hu"] and F["csvs"] == S["csvs"]
                  and xa["n"] == 2 and abs(xa["total"] - 250.0) < 1e-9 and xa["day_n"] == 1
                  and abs(xa["day_total"] + 50.0) < 1e-9
                  and F["og"] == [("QQQ", -80.0)] and F["ox"] == [("NVDA", 50.0)] and S["og"] == [] and S["ox"] == []
                  and S["extra"]["n"] == 0)
            ck("A3", ok, "headline equal=%s extra=%s ogap=%s ogap_extra=%s giveback equal=%s hunt equal=%s csv equal=%s"
               % (F["head"] == S["head"], xa, F["og"], F["ox"], F["gb"] == S["gb"], F["hu"] == S["hu"],
                  F["csvs"] == S["csvs"]))
        except Exception as e:                                   # noqa: BLE001
            import traceback
            ck("A3", False, "%s: %s %s" % (type(e).__name__, e, traceback.format_exc()[-600:]))

        # ── A4 cash_books ──
        try:
            import cash_books as CB
            sf, ss = CB.score(CASH_DAY, day=CASH_DAY, trades_dir=os.path.join(full, "trades")), \
                CB.score(CASH_DAY, day=CASH_DAY, trades_dir=os.path.join(strp, "trades"))
            same = all(sf["windows"][w]["books"] == ss["windows"][w]["books"] for w in ss["windows"])
            ext = (sf["windows"].get("combined") or {}).get("extras") or {}
            mf, ms = CB.render_md(sf), CB.render_md(ss)
            ok = (same and set(sf["windows"]) == set(ss["windows"]) and ext.get("C2", {}).get("n") == 1
                  and ext["C2"]["gross"] == -50.0 and "Extra paper after the breaker" in mf
                  and "Extra paper after the breaker" not in ms and strip_extra_line(mf) == strip_extra_line(ms)
                  and not any("extras" in w for w in ss["windows"].values()) and 50 in CB.figures(sf))
            ck("A4", ok, "books equal=%s extras=%s md line full=%s stripped=%s" % (
                same, ext, "Extra paper after the breaker" in mf, "Extra paper after the breaker" in ms))
        except Exception as e:                                   # noqa: BLE001
            ck("A4", False, "%s: %s" % (type(e).__name__, e))

        # ── A5 runaway_watch ──
        try:
            import runaway_watch as RW
            nf = os.path.join(tmp, "notes", "NOTES.txt")
            RW.NOTES = nf                                        # no file yet
            rf, rs = RW.score(CASH_DAY, os.path.join(full, "trades")), RW.score(CASH_DAY, os.path.join(strp, "trades"))
            eq = all({k: v for k, v in rf["equities"][s].items() if k != "extra"} == rs["equities"][s]
                     for s in rs["equities"]) and set(rf["equities"]) == set(rs["equities"])
            ax = rf["equities"]["AMD"].get("extra")
            m0, ms = RW.render_md(rf), RW.render_md(rs)
            os.makedirs(os.path.dirname(nf))
            with open(nf, "w") as fh:
                fh.write("2026-11-23T00:00Z NOTE 1 (before any after_cap trade). The watch reads as cash.\nmore\n")
            m1 = RW.render_md(rf)
            ok = (eq and ax == {"n": 1, "net": -52.0} and "Extra paper after the breaker" in m0
                  and "Extra paper after the breaker" not in ms and "Note:" not in m0
                  and "Note: 2026-11-23T00:00Z NOTE 1 (before any after_cap trade). The watch reads as cash." in m1
                  and "more" not in m1.split("## The watch list")[0] and RW.WATCH_SHA.startswith("eeb225665a2b")
                  and 52 in RW.figures(rf))
            ck("A5", ok, "equities equal=%s AMD extra=%s md extras full=%s stripped=%s note=%s" % (
                eq, ax, "Extra paper after the breaker" in m0, "Extra paper after the breaker" in ms, "Note:" in m1))
        except Exception as e:                                   # noqa: BLE001
            ck("A5", False, "%s: %s" % (type(e).__name__, e))

        # ── A6 weekly_facts ──
        try:
            import weekly_facts as WF
            Ff = WF.compute("2026-11-27", use_wh=False, reviews=full)
            Fs = WF.compute("2026-11-27", use_wh=False, reviews=strp)
            keys = [k for k in Fs if k not in ("excluded",)]
            eqk = [k for k in keys if json.dumps(Ff.get(k), sort_keys=True, default=str)
                   != json.dumps(Fs.get(k), sort_keys=True, default=str)]
            mdf, mds = WF.render(Ff), WF.render(Fs)
            xa = (Ff.get("extra_after_cap") or {}).get("week") or {}
            ok = (eqk == [] and xa.get("n") == 2 and abs(xa.get("gross", 0) - 350.0) < 1e-9
                  and "Extra paper after the breaker" in mdf and "Extra paper after the breaker" not in mds
                  and "extra_after_cap" not in Fs)
            ck("A6", ok, "keys that differ=%s extra week=%s md full=%s stripped=%s" % (
                eqk, xa, "Extra paper after the breaker" in mdf, "Extra paper after the breaker" in mds))
        except Exception as e:                                   # noqa: BLE001
            import traceback
            ck("A6", False, "%s: %s %s" % (type(e).__name__, e, traceback.format_exc()[-500:]))

        # ── A7 daily_brief, in its own venv ──
        try:
            if not os.path.exists(BRIEF_PY):
                ck("A7", False, "the brief's venv %s is missing (install_daily_recap.sh builds it)" % BRIEF_PY)
            else:
                recs = []
                for (dd, s, tid, st, di, c, e, x, mf, p, t, fee, pt, ac, extra) in ROWS:
                    if dd == CASH_DAY:
                        recs.append(dict(symbol=s, trade_id=tid, strategy=st, direction=di, contracts=c,
                                         entry_premium=e, exit_premium=x, mfe_premium=mf, pnl_usd=p,
                                         entry_time=dd + t, exit_time=dd + t, exit_reason="x", status="closed",
                                         paper_trade=pt, after_cap=ac))
                bdir = os.path.join(tmp, "a7")
                os.makedirs(os.path.join(bdir, "breaker"))
                with open(os.path.join(bdir, "breaker", CASH_DAY + ".csv"), "w", newline="") as fh:
                    w = csv.DictWriter(fh, fieldnames=K.BREAKER_COLS)
                    w.writeheader()
                    w.writerow(dict(sym="AMD", event_time=CASH_DAY + "T15:00:00+00:00", reason=K.WOULD_POP,
                                    session_losses=1, notes="breaker would have popped at 10:00 ET, day net -$1,060.00"))
                script = os.path.join(tmp, "a7.py")
                with open(script, "w") as fh:
                    fh.write(
                        "import json, sys\n"
                        "sys.path.insert(0, %r)\n"
                        "import daily_brief as DB\n"
                        "recs = json.loads(%r)\n"
                        "class M: listed = read = 1; bad = 0\n"
                        "DB.ws.load_trades = lambda days, *a, **k: (recs, M())\n"
                        "DB.load_bars = lambda day, syms, s3=None: ({}, {})\n"
                        "DB.fee_of = lambda r, contracts=None: 1.0\n"
                        "DB.RK.REVIEWS = %r\n"
                        "c = DB.compute(%r)\n"
                        "f = DB.facts(%r)\n"
                        "print(json.dumps(dict(head=sorted(r['trade_id'] for r in c['trades']), tot=c['tot_p'],\n"
                        "  xa=[r['trade_id'] for r in c['after_cap']], po=[r['trade_id'] for r in c['paper_on_cash']],\n"
                        "  wp=c['would_pop'], lines=DB.extras_lines(c), facts=dict(after_cap=f.get('after_cap'),\n"
                        "  paper_on_cash=f.get('paper_on_cash'), would_pop=f.get('would_pop'), n=f['trades_n']))))\n"
                        % (TOOLS, json.dumps(recs), bdir, CASH_DAY, CASH_DAY))
                env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": os.path.expanduser("~"),
                       "LANG": "C.UTF-8", "MPLCONFIGDIR": os.path.join(tmp, "mpl")}
                pr = subprocess.run([BRIEF_PY, script], capture_output=True, text=True, timeout=300, env=env,
                                    cwd=tmp)
                out = json.loads(pr.stdout.strip().splitlines()[-1]) if pr.returncode == 0 and pr.stdout.strip() else {}
                ln = " ".join(out.get("lines") or [])
                fa = out.get("facts") or {}
                ok = (out.get("head") == ["t5", "t7"] and abs((out.get("tot") or 0) - 500.0) < 1e-9
                      and out.get("xa") == ["t8"] and out.get("po") == ["t6"] and len(out.get("wp") or []) == 1
                      and "Extra paper after the breaker" in ln and "AMD: breaker would have popped at 10:00 ET" in ln
                      and "Paper rows on a cash box" in ln and "QQQ OGAP" in ln
                      and (fa.get("after_cap") or {}).get("n") == 1 and (fa.get("paper_on_cash") or {}).get("n") == 1
                      and len(fa.get("would_pop") or []) == 1 and fa.get("n") == 2)
                ck("A7", ok, "rc=%s out=%s err=%s" % (pr.returncode, json.dumps(out)[:400], pr.stderr[-400:]))
        except Exception as e:                                   # noqa: BLE001
            ck("A7", False, "%s: %s" % (type(e).__name__, e))

        # ── A8 daily_recap context ──
        try:
            import daily_recap as DR
            a = DR.as_cash_lines(PAPER_DAY, os.path.join(full, "trades"))
            b = DR.as_cash_lines(CASH_DAY, os.path.join(full, "trades"))
            t = "\n".join(a)
            u = "\n".join(b)
            ok = ("extra paper after the breaker (beside the headline, never in it): n 2, +$350.00" in t
                  and "NVDA LiquidityHunt" in t and "NVDA OGAP" in t
                  and "would-pop records: NVDA: breaker would have popped at 10:15 ET, day net -$1,100.00" in t
                  and "paper rows on a cash box (OGAP's own line, never a cash figure): n 1, -$80.00" in u
                  and "would-pop records: NOT READ" in u)
            ck("A8", ok, "%s || %s" % (t.replace("\n", " | ")[:500], u.replace("\n", " | ")[:300]))
        except Exception as e:                                   # noqa: BLE001
            ck("A8", False, "%s: %s" % (type(e).__name__, e))

        # ── A9 the prompts ──
        try:
            pr_ = {n: open(os.path.join(TOOLS, n)).read() for n in ("daily_recap.prompt", "nightly_review.prompt",
                                                                     "saturday_brief.prompt")}
            need = ("AS CASH WOULD HAVE TRADED IS THE HEADLINE", "after_cap", "would-pop", "OGAP",
                    "never added in", "there's no harm")
            miss = {n: [x for x in need if x not in t] for n, t in pr_.items()}
            ok = (all(not v for v in miss.values()) and "daily_recap.prompt v1.8" in pr_["daily_recap.prompt"]
                  and "nightly_review.prompt v1.10" in pr_["nightly_review.prompt"]
                  and "breaker/" in pr_["nightly_review.prompt"] and "breaker/" in pr_["saturday_brief.prompt"])
            ck("A9", ok, "missing=%s" % miss)
        except Exception as e:                                   # noqa: BLE001
            ck("A9", False, "%s: %s" % (type(e).__name__, e))

        # ── A11 a cash box with no cash trade ──
        try:
            D11 = "2026-12-07"
            root = os.path.join(tmp, "a11")
            bl = os.path.join(root, "daily_brief", "botlogs", D11)
            os.makedirs(bl)
            os.makedirs(os.path.join(root, "trades"))
            open(os.path.join(bl, "QQQ.txt"), "w").write(
                "# QQQ extract\n2026-12-07 09:15:02 [INFO ] __main__: Service mode: PAPER | QQQ | a stale start\n"
                "2026-12-07 09:20:02 [INFO ] __main__: Service mode: LIVE | QQQ | risk=$1050/trade\n")
            open(os.path.join(bl, "NVDA.txt"), "w").write(
                "2026-12-07 09:15:02 [INFO ] __main__: Service mode: PAPER | NVDA | risk=$1050/trade\n")
            open(os.path.join(bl, "AMD.txt"), "w").write(
                "2026-12-07 09:15:01 [INFO ] alerts: ALERT: OptionsBot [LIVE] STARTED | AMD | service restart\n")
            open(os.path.join(bl, "SPX.txt"), "w").write("# SPX 2026-12-07 NOT READ: ssh rc=255\n")
            md = K.box_modes(D11, os.path.join(root, "daily_brief", "botlogs"))
            og = dict(sym="QQQ", paper_trade="1", after_cap="")
            c1 = K.split([og], modes=md)
            c2 = K.split([dict(og)])
            c3 = K.split([dict(og, sym="NVDA")], modes=md)
            c4 = K.split([dict(sym="NVDA", paper_trade="0"), dict(sym="NVDA", paper_trade="1")], modes=md)
            c5 = K.split([dict(og, sym="SPX")], modes=md)
            with open(os.path.join(root, "trades", D11 + ".csv"), "w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=R577_COLS + ["paper_trade", "after_cap"])
                w.writeheader()
                w.writerow(dict(sym="QQQ", trade_id="q1", strategy="OGAP", direction="short", contracts=1,
                                entry_premium=4.2, exit_premium=3.4, pnl_usd=-80.0, entry_time=D11 + "T09:50:00-05:00",
                                exit_time=D11 + "T10:30:00-05:00", exit_reason="x", fee="1.50", paper_trade=1))
                w.writerow(dict(sym="SPX", trade_id="s1", strategy="RunawayContinuation", direction="long",
                                contracts=1, entry_premium=10.0, exit_premium=11.0, pnl_usd=100.0,
                                entry_time=D11 + "T09:37:00-05:00", exit_time=D11 + "T10:00:00-05:00",
                                exit_reason="x", fee="2.50", paper_trade=1))
            books = [r["_book"] for r in K._csv_rows(os.path.join(root, "trades", D11 + ".csv"))]
            import daily_recap as DR
            ctx = "\n".join(DR.as_cash_lines(D11, os.path.join(root, "trades")))
            brief = {}
            if os.path.exists(BRIEF_PY):
                for tag, rev in (("live", root), ("nolog", os.path.join(tmp, "a11_nolog"))):
                    recs = [dict(symbol="QQQ", trade_id="q1", strategy="OGAP", direction="short", contracts=1,
                                 entry_premium=4.2, exit_premium=3.4, pnl_usd=-80.0, entry_time=D11 + "T14:50:00+00:00",
                                 exit_time=D11 + "T15:30:00+00:00", exit_reason="x", status="closed", paper_trade=1),
                            dict(symbol="SPX", trade_id="s1", strategy="RunawayContinuation", direction="long",
                                 contracts=1, entry_premium=10.0, exit_premium=11.0, pnl_usd=100.0,
                                 entry_time=D11 + "T14:37:00+00:00", exit_time=D11 + "T15:00:00+00:00",
                                 exit_reason="x", status="closed", paper_trade=1)]
                    sc = os.path.join(tmp, "a11_%s.py" % tag)
                    with open(sc, "w") as fh:
                        fh.write("import json, sys\nsys.path.insert(0, %r)\nimport daily_brief as DB\n"
                                 "recs = json.loads(%r)\nclass M: listed = read = 1; bad = 0\n"
                                 "DB.ws.load_trades = lambda days, *a, **k: (recs, M())\n"
                                 "DB.load_bars = lambda day, syms, s3=None: ({}, {})\n"
                                 "DB.fee_of = lambda r, contracts=None: 1.0\nDB.RK.REVIEWS = %r\n"
                                 "c = DB.compute(%r)\nprint(json.dumps(dict(syms=sorted(c['by_sym']), "
                                 "po=[r['trade_id'] for r in c['paper_on_cash']], tot=c['tot_p'])))\n"
                                 % (TOOLS, json.dumps(recs), rev, D11))
                    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": os.path.expanduser("~"),
                           "LANG": "C.UTF-8", "MPLCONFIGDIR": os.path.join(tmp, "mpl")}
                    pr = subprocess.run([BRIEF_PY, sc], capture_output=True, text=True, timeout=300, env=env, cwd=tmp)
                    brief[tag] = (json.loads(pr.stdout.strip().splitlines()[-1]) if pr.returncode == 0
                                  and pr.stdout.strip() else {"err": pr.stderr[-300:]})
            ok = (md == {"QQQ": "LIVE", "NVDA": "PAPER", "AMD": "LIVE"} and c1 == [K.PAPER_ON_CASH]
                  and c2 == [K.HEADLINE] and c3 == [K.HEADLINE] and c4 == [K.HEADLINE, K.PAPER_ON_CASH]
                  and c5 == [K.HEADLINE] and books == [K.PAPER_ON_CASH, K.HEADLINE]
                  and "paper rows on a cash box (OGAP's own line, never a cash figure): n 1, -$80.00 at the mark "
                      "(QQQ OGAP)" in ctx
                  and brief.get("live") == {"syms": ["SPX"], "po": ["q1"], "tot": 100.0}
                  and brief.get("nolog") == {"syms": ["QQQ", "SPX"], "po": [], "tot": 20.0})
            ck("A11", ok, "modes=%s split=%s %s %s %s %s csv=%s brief=%s ctx=%s" % (
                md, c1, c2, c3, c4, c5, books, brief, ctx.replace("\n", " | ")[:300]))
        except Exception as e:                                   # noqa: BLE001
            import traceback
            ck("A11", False, "%s: %s %s" % (type(e).__name__, e, traceback.format_exc()[-500:]))

        # ── A10 the OTV5 tree writes these names ──
        try:
            tl = open(os.path.join(OTV5, "database", "trade_logger.py")).read()
            rm = open(os.path.join(OTV5, "risk", "risk_manager.py")).read()
            ee = open(os.path.join(OTV5, "execution", "entry_engine.py")).read()
            ok = ('("after_cap",' in tl and '"daily_cap_would_pop"' in rm and 'record["after_cap"] = 1' in ee
                  and "SELECT * FROM trades" in open(os.path.join(OTV5, "warehouse", "s3_push.py")).read())
            ck("A10", ok, "%s: after_cap column=%s would-pop reason=%s tag=%s" % (
                OTV5, '("after_cap",' in tl, '"daily_cap_would_pop"' in rm, 'record["after_cap"] = 1' in ee))
        except Exception as e:                                   # noqa: BLE001
            ck("A10", False, "%s: %s" % (type(e).__name__, e))
    finally:
        if tmp.startswith(tempfile.gettempdir()) and os.path.basename(tmp).startswith("check_as_cash_"):
            shutil.rmtree(tmp, ignore_errors=True)
    miss = [n for n in ALL if n not in RAN]
    if FAILS or miss:
        print("RED — %d of %d: %s%s" % (len(FAILS), len(ALL), ", ".join(FAILS), (" (not run: %s)" % miss) if miss else ""))
        return 1
    print("GREEN — %d checks: every report headlines as cash would have traded, the extras beside" % len(ALL))
    return 0


if __name__ == "__main__":
    sys.exit(main())
