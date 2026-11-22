#!/usr/bin/env python3
"""
day_trader_pro/tools/weekly_facts.py  v1.1  -  the Saturday brief's numbers (spec v3.0 sections 1A, 1B, 1C, 2A).
v1.1  2026-11-22  dtp r575 / HALF.2 - A 13:00 HALF DAY IS NOT A SESSION. The operator, 2026-11-22: "Yes, just treat them
      as bank holidays. No trading." (OTV5 r145 opens nothing on one; the boxes record data only). week_days() leaves
      out market_calendar.is_half_day the way cash_books.sessions() does (r574), so the brief's session count agrees
      with the C1-C4 scoreboard (the week of 2026-11-23 is three sessions: 11-26 closed, 11-27 a half day). The week's
      trades are every trade dated Monday..Friday, so a trade that opened on a half day anyway (a defect) still sits in
      every total and is named on its own DEFECT line; the warehouse read covers the half day too. The header names
      the sessions and the half days. Nothing else changes.
v1.0  2026-11-21  dtp r570 / SAT.10 - THE BRIEF IS THE OPERATOR'S NEW LAYOUT, AND ITS NUMBERS HAVE ONE RIGHT ANSWER. The
      operator, 2026-11-21: "1) Trading- A. Summary of the week's trades, our EV per trade, gross and net totals by
      strategy after fees. MFE/MAE ... B. A breakdown of our give-back on exits and never right on entries, and how
      each's strategy type fared the previous week vs its historical performance C. Our EPOCH (otv5) cumulative metrics.
      Is our performance improved or worsening? Is it consistent?" and "2) Our edge- A) What are our top earning setup
      conditions". Every figure in those sections that has exactly one right answer is computed here, so the 03:00
      session writes prose around numbers it did not compute ad hoc (review_kit's rule, one level up). The session
      quotes weekly_facts.md; it never re-derives a figure printed there. It reuses review_kit (est_fee, the
      bootstrap's seed and draws, the trade-CSV shape) and strategy_registry (LIVE, OTV5_SINCE); the daily recap's
      daily_brief.py helpers need its own venv (matplotlib, reportlab), so the tape reads the daily candles instead.

Usage:
  /home/ubuntu/day_trader_pro/venv/bin/python -I tools/weekly_facts.py --fri 2026-11-20 --out <WORK> [--no-warehouse]

READ-ONLY. Reads ~/reviews/trades/<day>.csv (written nightly by review_kit `trades`: S3 warehouse rows through
warehouse_source.mainline(), the fee from the control fee model), the week's warehouse rows (OTV5
tests/warehouse_source.load_trades -> mainline(), for MAE, capital and the exit ladder), and TastyTrade's daily
candles for QQQ, SPX and VIX (S3 raw/candles_full/interval=1d) for the tape; --no-warehouse skips every S3 read and
the tables that need one say NOT MEASURED or n/a. Writes
<out>/weekly_facts.json and <out>/weekly_facts.md, and nothing else. No box, no broker, no S3 write, no service
Environment.

THE RULES IT ENFORCES (the operator's):
  · the basis is the mark: pnl_usd, the ladder's fill (mark or better). The ask/bid figure (pnl_exec_usd) is a
    trailing table column only ("x gross"), never a headline.
  · fees BESIDE EV, never inside it: EV is gross a trade; "net" = gross - fees is its own column next to gross.
  · OTV4TEST out: the CSVs are mainline() rows; the warehouse read runs mainline() again and names what it dropped.
  · a setup that no longer trades (strategy_registry: not LIVE) is never named: its epoch rows are ONE line,
    "setups no longer trading (history)", so every total still adds up from the rows shown.
  · EV always with n and a day-bootstrap 95% interval (review_kit.boot's draws, seed 7: identical numbers).
"""
import argparse
import csv
import glob
import json
import os
import random
import statistics as st
import sys
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
sys.path.insert(0, REPO)
import market_calendar          # noqa: E402
import review_kit as RK         # noqa: E402  (est_fee, BOOT_N/SEED, REVIEWS, OTV5_TESTS: one answer each)
import strategy_registry as SR  # noqa: E402  (LIVE vs history; OTV5_SINCE, the epoch's first day)

ET = ZoneInfo("America/New_York")
COMFORT_USD = 25000 / 4        # the operator: about a quarter of $25k deployed in a day
INDEX = ("QQQ", "SPX")
CELL_MIN_N = 8                 # a condition cell is listed only with n >= 8 (a thin cell is a mechanism, not a finding)
OUTLAY_USD = 500.0             # OGAP vs PARK: each row scaled to $500 of premium outlay (spec v2.13, kept)


def epoch_start():
    """The first trading day on or after the fleet's OTV5 repoint (strategy_registry.OTV5_SINCE): 2026-10-26."""
    d = date.fromisoformat(min(SR.OTV5_SINCE.values()))
    while not market_calendar.is_trading_day(d):
        d += timedelta(days=1)
    return d.isoformat()


def week_days(fri):
    """The week's SESSIONS, Monday..`fri`: trading days (dtp market_calendar) that are not 13:00 half days (v1.1)."""
    f = date.fromisoformat(fri)
    mon = f - timedelta(days=f.weekday())
    return [(mon + timedelta(days=i)).isoformat() for i in range(5)
            if market_calendar.is_trading_day(mon + timedelta(days=i)) and mon + timedelta(days=i) <= f
            and not market_calendar.is_half_day(mon + timedelta(days=i))]


def week_half_days(fri):
    """v1.1: the week's 13:00 half days, Monday..`fri` - non-trading days by the operator's ruling, never sessions."""
    f = date.fromisoformat(fri)
    mon = f - timedelta(days=f.weekday())
    return [(mon + timedelta(days=i)).isoformat() for i in range(5)
            if mon + timedelta(days=i) <= f and market_calendar.is_trading_day(mon + timedelta(days=i))
            and market_calendar.is_half_day(mon + timedelta(days=i))]


def _et(s):
    if not s:
        return None
    d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(ET)


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def side_of(direction):
    d = str(direction or "").lower()
    return "call" if d in ("long", "call", "c", "bull") else "put" if d in ("short", "put", "p", "bear") else d or "?"


def bucket(t):
    m = t.hour * 60 + t.minute
    return "09:30-10:00" if m < 600 else "10:00-10:30" if m < 630 else "10:30-11:30" if m < 690 else "after 11:30"


def load_rows(start, fri, reviews=None):
    """-> (rows, excluded): every closed trade in ~/reviews/trades/<day>.csv, start..fri, in one shape."""
    reviews = reviews or RK.REVIEWS
    rows, excl = [], {"blank_pnl": [], "otv4test": 0}
    bf = RK.load_exec_backfill(os.path.join(reviews, "exec_basis_backfill.csv"))   # load_window's own source
    for fn in sorted(glob.glob(os.path.join(reviews, "trades", "20*.csv"))):
        day = os.path.basename(fn)[:10]
        if not (start <= day <= fri):
            continue
        for r in csv.DictReader(open(fn)):
            if r.get("sym") in RK.OTV4TEST_SYMS:
                excl["otv4test"] += 1
                continue
            if r.get("pnl_usd") in (None, "") or not r.get("entry_time"):
                excl["blank_pnl"].append(r.get("trade_id") or "?")
                continue
            c = _f(r.get("contracts")) or 0.0
            ep, mfe = _f(r.get("entry_premium")), _f(r.get("mfe_premium"))
            fee, est = (_f(r["fee"]), False) if r.get("fee") not in (None, "") else (RK.est_fee(r["sym"], c), True)
            ti = _et(r["entry_time"])
            x = dict(day=day, tid=r.get("trade_id") or "", sym=r["sym"], strat=r["strategy"],
                     side=side_of(r.get("direction")), c=c, ep=ep, pnl=float(r["pnl_usd"]), fee=fee, est=est,
                     t_in=ti, t_out=_et(r.get("exit_time")), reason=r.get("exit_reason") or "",
                     mfe_usd=((mfe - ep) * c * 100 if mfe is not None and ep is not None else None),
                     pnl_exec=(_f(r.get("pnl_exec_usd")) if r.get("pnl_exec_usd") not in (None, "")
                               else (bf.get(r.get("trade_id") or "") or (None, ""))[0]),
                     live=(SR.status(r["strategy"]) == SR.LIVE))
            x["bucket"] = bucket(ti) if ti else "?"
            rows.append(x)
    rows.sort(key=lambda x: (x["t_out"] or x["t_in"] or datetime.max.replace(tzinfo=ET)))
    return rows, excl


def boot(rows, key="pnl", n=RK.BOOT_N, seed=RK.BOOT_SEED):
    """review_kit.boot's interval with the same draws (seed, day order, one rnd.choice per day), from day sums."""
    days = sorted({x["day"] for x in rows})
    if len(days) < 2:
        return None, None
    s = {d: 0.0 for d in days}
    k = {d: 0 for d in days}
    for x in rows:
        s[x["day"]] += x[key]
        k[x["day"]] += 1
    rnd = random.Random(seed)
    out = []
    for _ in range(n):
        pick = [rnd.choice(days) for _ in days]
        out.append(sum(s[d] for d in pick) / sum(k[d] for d in pick))
    out.sort()
    return out[int(.025 * n)], out[int(.975 * n)]


def agg(rows, n_boot=RK.BOOT_N):
    n = len(rows)
    g = sum(x["pnl"] for x in rows)
    fees = sum(x["fee"] for x in rows)
    lo, hi = boot(rows, n=n_boot) if (n and n_boot) else (None, None)
    ex = [x["pnl_exec"] for x in rows if x["pnl_exec"] is not None]
    return dict(n=n, w=sum(1 for x in rows if x["pnl"] > 0), l=sum(1 for x in rows if x["pnl"] < 0),
                gross=round(g, 2), ev=(round(g / n, 2) if n else None), lo=_r(lo), hi=_r(hi), fees=round(fees, 2),
                fees_est=round(sum(x["fee"] for x in rows if x["est"]), 2), net=round(g - fees, 2),
                days=len({x["day"] for x in rows}), x_n=len(ex), x_gross=round(sum(ex), 2))


def _r(v):
    return None if v is None else round(v, 2)


def by(rows, key):
    g = {}
    for x in rows:
        g.setdefault(key(x), []).append(x)
    return g


def strat_label(x):
    return x["strat"] if x["live"] else "setups no longer trading (history)"


def excursions(rows, wh):
    """MFE from the CSV (mfe_premium), MAE from the warehouse row (mae_premium): dollars over the whole position."""
    mfe = [x["mfe_usd"] for x in rows if x["mfe_usd"] is not None]
    mae = []
    for x in rows:
        w = wh.get(x["tid"])
        if w and _f(w.get("mae_premium")) is not None and x["ep"] is not None:
            mae.append((_f(w["mae_premium"]) - x["ep"]) * x["c"] * 100)
    cap = [x["pnl"] / x["mfe_usd"] for x in rows if x["mfe_usd"] and x["mfe_usd"] > 0]
    return dict(mfe_n=len(mfe), mfe_med=_r(st.median(mfe)) if mfe else None, mae_n=len(mae),
                mae_med=_r(st.median(mae)) if mae else None, capture_med=(round(st.median(cap), 2) if cap else None))


def giveback(rows):
    """Row basis (the CSV's mfe_premium): given back = peak open $ - booked $, on trades whose peak was above entry.
    NEVER RIGHT = the trade never traded above its entry (peak open $ <= 0). GREEN-TO-RED = peaked above, booked red.
    ~/reviews/giveback.csv (the 15 s tick definition) stays the headline; this splits it by setup."""
    up = [x for x in rows if x["mfe_usd"] is not None and x["mfe_usd"] > 0]
    nr = [x for x in rows if x["mfe_usd"] is not None and x["mfe_usd"] <= 0]
    g2r = [x for x in up if x["pnl"] < 0]
    peak = sum(x["mfe_usd"] for x in up)
    given = sum(max(0.0, x["mfe_usd"] - x["pnl"]) for x in up)
    return dict(peak=round(peak, 2), given=round(given, 2), given_pct=(round(100 * given / peak, 1) if peak else None),
                never_right_n=len(nr), never_right_usd=round(sum(x["pnl"] for x in nr), 2),
                g2r_n=len(g2r), g2r_usd=round(sum(x["pnl"] for x in g2r), 2),
                no_mfe=sum(1 for x in rows if x["mfe_usd"] is None))


def streaks(rows):
    """Longest run of losing trades (exit order) and of red days, and the run standing at the end."""
    def runs(seq):
        best = cur = 0
        for v in seq:
            cur = cur + 1 if v else 0
            best = max(best, cur)
        return best, cur
    tl, tc = runs([x["pnl"] < 0 for x in rows])
    days = by(rows, lambda x: x["day"])
    dseq = [sum(x["pnl"] for x in days[d]) < 0 for d in sorted(days)]
    dl, dc = runs(dseq)
    return dict(loss_trades_max=tl, loss_trades_now=tc, red_days_max=dl, red_days_now=dc)


def drawdown(rows):
    days = by(rows, lambda x: x["day"])
    eq, peak, peak_d, dd, dd_from, dd_to = 0.0, 0.0, None, 0.0, None, None
    for d in sorted(days):
        eq += sum(x["pnl"] for x in days[d])
        if eq > peak:
            peak, peak_d = eq, d
        if peak - eq > dd:
            dd, dd_from, dd_to = peak - eq, peak_d, d
    return dict(equity=round(eq, 2), peak=round(peak, 2), peak_day=peak_d, max_dd=round(dd, 2), max_dd_from=dd_from,
                max_dd_to=dd_to, dd_now=round(peak - eq, 2))


def deployed(wrows, syms=None):
    """Peak premium outlay open at one time, per ET day (sum of total_cost, else entry x contracts x 100)."""
    out = {}
    for d, rs in by(wrows, lambda r: r["_day"]).items():
        ev = []
        for r in rs:
            if syms and r.get("symbol") not in syms:
                continue
            cost = _f(r.get("total_cost")) or ((_f(r.get("entry_premium")) or 0) * (_f(r.get("contracts")) or 0) * 100)
            a, b = _et(r.get("entry_time")), _et(r.get("exit_time"))
            if a and b:
                ev += [(a, 1, cost), (b, 0, -cost)]
        ev.sort(key=lambda e: (e[0], e[1]))
        cur = top = 0.0
        at = None
        for t, _o, c in ev:
            cur += c
            if cur > top:
                top, at = cur, t
        out[d] = dict(peak=round(top, 2), at=(at.strftime("%H:%M") if at else None), over=top > COMFORT_USD)
    return out


def exit_fills(wrows):
    st_ = [_f(r.get("exit_ladder_steps")) for r in wrows if _f(r.get("exit_ladder_steps")) is not None]
    lat = sorted(_f(r.get("exit_latency_ms")) for r in wrows if _f(r.get("exit_latency_ms")) is not None)
    return dict(n=len(wrows), steps_med=(st.median(st_) if st_ else None), steps_max=(max(st_) if st_ else None),
                latency_ms_med=(st.median(lat) if lat else None),
                latency_ms_p90=(lat[int(.9 * (len(lat) - 1))] if lat else None),
                escalated=sum(1 for r in wrows if str(r.get("exit_escalated") or "0") not in ("0", "", "None", "False")))


def daily_bars(syms, start, end):
    """-> {sym: {ET day: (open, high, low, close)}} from TastyTrade's daily candles in S3
    (raw/candles_full/interval=1d/sym=<SYM>/*.csv.gz, CAP.6: DXLink `{=d,tho=true}`, regular hours; every pull is kept,
    so a bar seen twice is deduped on its time, the latest pulled_at winning). One small object per pull."""
    import gzip
    import io
    sys.path.insert(0, RK.OTV5_TESTS)
    import warehouse_source as ws
    s3 = ws.client()
    out = {}
    for sym in syms:
        best = {}
        pre = "%s/candles_full/interval=1d/sym=%s/" % (ws.PREFIX, sym)
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=ws.BUCKET, Prefix=pre):
            for o in page.get("Contents", []) or []:
                raw = gzip.decompress(s3.get_object(Bucket=ws.BUCKET, Key=o["Key"])["Body"].read()).decode()
                for r in csv.DictReader(io.StringIO(raw)):
                    try:
                        d = datetime.fromtimestamp(int(r["time"]) / 1000, tz=timezone.utc).date().isoformat()
                        bar = tuple(float(r[k]) for k in ("open", "high", "low", "close"))
                    except (KeyError, ValueError, TypeError):
                        continue
                    if start <= d <= end and (d not in best or str(r.get("pulled_at")) >= best[d][0]):
                        best[d] = (str(r.get("pulled_at")), bar)
        out[sym] = {d: v[1] for d, v in best.items()}
    return out


def tape(bars):
    """Per day: QQQ and SPX open-close %, range %, the trend efficiency |close - open| / (high - low), and the VIX
    close. Labels are descriptive only: efficiency >= 0.6 trend, <= 0.3 chop, else mixed; VIX < 15 low, 15-20
    normal, 20-30 elevated, >= 30 high."""
    out = {}
    for s in INDEX:
        for d, (o, h, l, c) in (bars.get(s) or {}).items():
            if h > l and o:
                eff = abs(c - o) / (h - l)
                out.setdefault(d, {})[s] = dict(oc=round((c / o - 1) * 100, 2), range=round((h / l - 1) * 100, 2),
                                                eff=round(eff, 2),
                                                label=("trend" if eff >= 0.6 else "chop" if eff <= 0.3 else "mixed"))
    for d, (_o, _h, _l, v) in (bars.get("VIX") or {}).items():
        out.setdefault(d, {})["VIX"] = dict(close=round(v, 2), label=("low" if v < 15 else "normal" if v < 20
                                                                      else "elevated" if v < 30 else "high"))
    return out


def scaled(rows):
    """OGAP vs PARK like for like: index rows, each scaled to $500 of premium outlay."""
    out = []
    for x in rows:
        if x["sym"] in INDEX and x["ep"] and x["c"]:
            y = dict(x)
            y["pnl"] = x["pnl"] * OUTLAY_USD / (x["ep"] * x["c"] * 100)
            out.append(y)
    return out


def corr(a, b):
    if len(a) < 3:
        return None
    try:
        return round(st.correlation(a, b), 2)
    except (st.StatisticsError, ValueError):
        return None


def warehouse_week(days):
    sys.path.insert(0, RK.OTV5_TESTS)
    import warehouse_source as ws
    rows, meta = ws.load_trades(days)

    def day_of(r):
        e = _et(r.get("entry_time"))
        return e.date().isoformat() if e else None
    kept, dropped = ws.mainline(rows, day_of)
    out = []
    for r in kept:
        r = dict(r)
        r["_day"] = day_of(r)
        if r["_day"] in days:
            out.append(r)
    return out, dropped, meta.banner()


def compute(fri, use_wh=True, reviews=None):
    E = epoch_start()
    W = week_days(fri)
    H = week_half_days(fri)                  # v1.1: not sessions; a trade on one is a defect, still counted
    mon = (date.fromisoformat(fri) - timedelta(days=date.fromisoformat(fri).weekday())).isoformat()
    rows, excl = load_rows(E, fri, reviews)
    wk = [x for x in rows if mon <= x["day"] <= fri]
    prior = [x for x in rows if x["day"] < mon]
    wh, wrows, dropped, banner = {}, [], {}, "not read (--no-warehouse)"
    if use_wh and (W or H):
        wrows, dropped, banner = warehouse_week(sorted(W + H))
        wh = {r.get("trade_id"): r for r in wrows}
    ids_csv = {x["tid"] for x in wk}
    nonclosed = [r.get("trade_id") for r in wrows if str(r.get("status") or "") != "closed"]
    closed_ids = {r.get("trade_id") for r in wrows if str(r.get("status") or "") == "closed"}
    mism = [x["tid"] for x in wk if x["tid"] in wh and _f(wh[x["tid"]].get("pnl_usd")) is not None
            and round(_f(wh[x["tid"]]["pnl_usd"]), 2) != round(x["pnl"], 2)]
    F = dict(fri=fri, epoch_start=E, week=W, half_days=H,
             half_day_trades=[dict(day=x["day"], sym=x["sym"], strat=strat_label(x)) for x in wk if x["day"] in H],
             basis="pnl_usd at the mark (the ladder's fill, mark or better); fees "
             "beside, never inside EV; net = gross - fees", warehouse=banner)
    F["excluded"] = dict(otv4test_dropped_warehouse=dropped, otv4test_rows_csv=excl["otv4test"],
                         blank_pnl_csv=excl["blank_pnl"], warehouse_not_closed=nonclosed,
                         only_in_csv=(sorted(ids_csv - closed_ids) if use_wh else None),
                         only_in_warehouse=(sorted(closed_ids - ids_csv) if use_wh else None),
                         pnl_mismatch=mism, fees_estimated_week=sum(1 for x in wk if x["est"]),
                         mfe_missing_week=sum(1 for x in wk if x["mfe_usd"] is None))
    # 1A: the week
    F["week_book"] = agg(wk)
    F["week_by_strategy"] = {k: dict(agg(v, 4000), **excursions(v, wh))
                             for k, v in sorted(by(wk, strat_label).items(), key=lambda kv: -sum(x["pnl"] for x in kv[1]))}
    F["week_by_strategy_side"] = {k: agg(v, 2000) for k, v in by(wk, lambda x: "%s %s" % (strat_label(x), x["side"])).items()}
    F["week_by_day"] = {k: agg(v, 0) for k, v in sorted(by(wk, lambda x: x["day"]).items())}
    F["week_by_symbol"] = dict(sorted(((k, agg(v, 2000)) for k, v in by(wk, lambda x: x["sym"]).items()),
                                      key=lambda kv: -kv[1]["gross"]))
    F["week_by_bucket"] = {k: agg(v, 2000) for k, v in sorted(by(wk, lambda x: x["bucket"]).items())}
    F["week_excursions"] = excursions(wk, wh)
    srt = sorted(wk, key=lambda x: x["pnl"])
    line = lambda x: dict(day=x["day"], sym=x["sym"], strat=strat_label(x), side=x["side"], pnl=round(x["pnl"], 2),
                          at=x["t_in"].strftime("%H:%M") if x["t_in"] else None, reason=x["reason"][:80])
    F["week_best"] = [line(x) for x in srt[::-1][:5]]
    F["week_worst"] = [line(x) for x in srt[:5]]
    F["week_qqq"] = dict(book=agg([x for x in wk if x["sym"] == "QQQ"], 4000),
                         by_strategy={k: agg(v, 2000) for k, v in by([x for x in wk if x["sym"] == "QQQ"], strat_label).items()})
    dwk = {k: sum(x["pnl"] for x in v) for k, v in by(wk, lambda x: x["day"]).items()}
    F["risk"] = dict(worst_day=(min(dwk.items(), key=lambda kv: kv[1]) if dwk else None),
                     week_streaks=streaks(wk), epoch_streaks=streaks(rows), epoch_drawdown=drawdown(rows),
                     comfort_usd=COMFORT_USD,
                     deployed=(deployed(wrows) if use_wh else None),
                     deployed_qqq=(deployed(wrows, ("QQQ",)) if use_wh else None))
    F["exit_fills"] = exit_fills(wrows) if use_wh else None
    # 1B: exits and entries, and the week against each setup's own history
    F["giveback_week"] = dict(book=giveback(wk), by_strategy={k: giveback(v) for k, v in by(wk, strat_label).items()})
    F["vs_history"] = {k: dict(week=agg([x for x in wk if strat_label(x) == k], 4000),
                               before=agg([x for x in prior if strat_label(x) == k], 4000))
                       for k in sorted({strat_label(x) for x in wk})}
    # 1C: the epoch
    F["epoch_book"] = agg(rows)
    F["epoch_live_book"] = agg([x for x in rows if x["live"]])
    F["epoch_by_strategy"] = {k: dict(agg(v, 4000), **giveback(v))
                              for k, v in sorted(by(rows, strat_label).items(), key=lambda kv: -sum(x["pnl"] for x in kv[1]))}
    tp = tape(daily_bars(INDEX + ("VIX",), E, fri)) if use_wh else {}
    wkey = lambda d: (date.fromisoformat(d) - timedelta(days=date.fromisoformat(d).weekday())).isoformat()
    series, cum = [], []
    for wmon, v in sorted(by(rows, lambda x: wkey(x["day"])).items()):
        cum += v
        days = sorted({x["day"] for x in v})
        dsum = {d: sum(x["pnl"] for x in v if x["day"] == d) for d in days}
        t = [tp.get(d, {}) for d in days]
        effs = [x["QQQ"]["eff"] for x in t if x.get("QQQ")]
        vix = [x["VIX"]["close"] for x in t if x.get("VIX")]
        series.append(dict(week=wmon, **agg(v, 4000), green_days=sum(1 for d in days if dsum[d] > 0),
                           qqq_eff_mean=(round(st.mean(effs), 2) if effs else None),
                           qqq_labels=[x["QQQ"]["label"] for x in t if x.get("QQQ")],
                           vix_median=(round(st.median(vix), 2) if vix else None),
                           tape_days=len(effs), cum_ev=round(sum(x["pnl"] for x in cum) / len(cum), 2)))
    F["epoch_weeks"] = series
    F["tape_days"] = {d: tp[d] for d in sorted(tp) if E <= d <= fri}
    ds = sorted({x["day"] for x in rows})
    half = ds[len(ds) // 2] if ds else None
    dsum = {d: sum(x["pnl"] for x in rows if x["day"] == d) for d in ds}
    top3 = sorted(dsum, key=dsum.get, reverse=True)[:3]
    F["consistency"] = dict(days=len(ds), green_days=sum(1 for v in dsum.values() if v > 0),
                            first_half=agg([x for x in rows if half and x["day"] < half], 4000),
                            second_half=agg([x for x in rows if half and x["day"] >= half], 4000),
                            split_day=half, top3_days=top3, top3_days_usd=round(sum(dsum[d] for d in top3), 2),
                            top3_share_pct=(round(100 * sum(dsum[d] for d in top3) / F["epoch_book"]["gross"], 1)
                                            if F["epoch_book"]["gross"] > 0 else None),
                            ex_top3_days=agg([x for x in rows if x["day"] not in top3], 4000))
    # 2A: conditions (live setups only), and the decisions in progress
    live = [x for x in rows if x["live"]]
    cells = {}
    for name, key in (("setup x side x entry time", lambda x: "%s %s %s" % (x["strat"], x["side"], x["bucket"])),
                      ("setup x symbol", lambda x: "%s %s" % (x["strat"], x["sym"]))):
        for k, v in by(live, key).items():
            if len(v) >= CELL_MIN_N:
                cells["%s · %s" % (name, k)] = agg(v, 2000)
    rk = sorted(cells.items(), key=lambda kv: -kv[1]["ev"])
    F["cells_min_n"] = CELL_MIN_N
    F["cells_top"] = dict(rk[:6])
    F["cells_bottom"] = dict(rk[-6:][::-1]) if len(rk) > 6 else {}
    hunt = [x for x in rows if x["strat"] == RK.HUNT]
    F["hunt"] = dict(epoch={s: agg([x for x in hunt if x["side"] == s], 4000) for s in ("call", "put")},
                     week={s: agg([x for x in hunt if x["side"] == s and mon <= x["day"] <= fri], 4000)
                           for s in ("call", "put")})
    og = [x for x in rows if x["strat"] == RK.OGAP]
    F["ogap"] = dict(agg(og, 4000), before_1000=sum(1 for x in og if x["t_in"] and x["t_in"].hour < 10),
                     calls=sum(1 for x in og if x["side"] == "call"), puts=sum(1 for x in og if x["side"] == "put"),
                     exits={k: len(v) for k, v in by(og, lambda x: x["reason"].split(":")[0][:30]).items()})
    ov = {}
    for s in (RK.OGAP, RK.PARK):
        v = scaled([x for x in rows if x["strat"] == s])
        dd = {k: sum(x["pnl"] for x in g) for k, g in by(v, lambda x: x["day"]).items()}
        ov[s] = dict(agg(v, 4000), worst_day=(min(dd.items(), key=lambda kv: kv[1]) if dd else None),
                     largest_loss=(round(min(x["pnl"] for x in v), 2) if v and min(x["pnl"] for x in v) < 0 else None),
                     daily=dd,
                     sides={k: {x["side"] for x in g} for k, g in by(v, lambda x: x["day"]).items()})
    both = sorted(set(ov[RK.OGAP]["daily"]) & set(ov[RK.PARK]["daily"]))
    same = sum(1 for d in both if ov[RK.OGAP]["sides"][d] & ov[RK.PARK]["sides"][d])
    F["ogap_vs_park"] = dict({s: {k: v for k, v in ov[s].items() if k not in ("daily", "sides")} for s in ov},
                             overlap_days=len(both), same_side=same,
                             corr=corr([ov[RK.OGAP]["daily"][d] for d in both], [ov[RK.PARK]["daily"][d] for d in both]))
    return F


# ── markdown ────────────────────────────────────────────────────────────────────────────────────────────────────────
def m(v):
    return "n/a" if v is None else ("−$%s" % format(-v, ",.2f") if v < 0 else "+$%s" % format(v, ",.2f"))


def usd(v):
    return "$%s" % format(v, ",.2f")


def wday(t):
    return "%s %s" % (t[0], m(t[1])) if t else "n/a"


def ci(a):
    return "n/a (one day)" if a.get("lo") is None else "[%s, %s]" % (m(a["lo"]), m(a["hi"]))


HDR = "| | n | W-L | gross | EV a trade | 95% day-bootstrap | fees | net (gross − fees) | x gross |"
SEP = "|---|---|---|---|---|---|---|---|---|"


def arow(k, a):
    return "| %s | %d | %d-%d | %s | %s | %s | %s | %s | %s |" % (k, a["n"], a["w"], a["l"], m(a["gross"]), m(a["ev"]),
                                                              ci(a), usd(a["fees"]), m(a["net"]), m(a["x_gross"]))


def table(title, d, total=None):
    out = ["", "**%s**" % title, "", HDR, SEP] + [arow(k, a) for k, a in d.items()]
    if total:
        out.append(arow("**total**", total))
    return out


def render(F):
    L = ["# WEEKLY FACTS — week %s..%s · epoch from %s" % (F["week"][0] if F["week"] else "?", F["fri"],
                                                            F["epoch_start"]),
         "", "Basis: %s. `x gross` is the ask/bid figure, a trailing data column only." % F["basis"],
         "Warehouse: %s" % F["warehouse"],
         "Sessions this week: %d%s" % (len(F["week"]), (" · half days (13:00 close, non-trading days by the operator's "
                                                         "ruling, not sessions): " + ", ".join(F["half_days"]))
                                       if F.get("half_days") else "")]
    if F.get("half_day_trades"):
        L += ["**DEFECT: trades dated on a half day (OTV5 r145 opens nothing then):** " + "; ".join(
            "%s %s %s" % (t["day"], t["sym"], t["strat"]) for t in F["half_day_trades"])]
    e = F["excluded"]
    L += ["", "**Excluded / completeness:** OTV4TEST dropped by mainline(): warehouse %s, CSV %d · blank-P&L rows %d %s · "
          "warehouse rows not closed %d %s · only in CSV %s · only in warehouse %s · P&L mismatches %s · fees estimated "
          "%d · MFE missing %d" % (e["otv4test_dropped_warehouse"] or 0, e["otv4test_rows_csv"], len(e["blank_pnl_csv"]),
                                    e["blank_pnl_csv"] or "", len(e["warehouse_not_closed"]),
                                    e["warehouse_not_closed"] or "", e["only_in_csv"], e["only_in_warehouse"],
                                    e["pnl_mismatch"], e["fees_estimated_week"], e["mfe_missing_week"])]
    L += ["", "## 1A the week"]
    L += table("By setup", F["week_by_strategy"], F["week_book"])
    L += ["", "| setup | MFE median $ (n) | MAE median $ (n) | capture median |", "|---|---|---|---|"]
    for k, a in F["week_by_strategy"].items():
        L.append("| %s | %s (%d) | %s (%d) | %s |" % (k, m(a["mfe_med"]), a["mfe_n"], m(a["mae_med"]), a["mae_n"],
                                                     a["capture_med"]))
    L += table("By setup and side", F["week_by_strategy_side"])
    L += table("By day", F["week_by_day"])
    L += table("By symbol", F["week_by_symbol"])
    L += table("By entry time", F["week_by_bucket"])
    L += table("QQQ only (the cash test is QQQ only)", F["week_qqq"]["by_strategy"], F["week_qqq"]["book"])
    L += ["", "**Best 5:** " + " · ".join("%s %s %s %s %s (%s)" % (b["day"][5:], b["sym"], b["strat"], b["side"],
                                                                  m(b["pnl"]), b["reason"][:40]) for b in F["week_best"]),
          "**Worst 5:** " + " · ".join("%s %s %s %s %s (%s)" % (b["day"][5:], b["sym"], b["strat"], b["side"],
                                                                   m(b["pnl"]), b["reason"][:40]) for b in F["week_worst"])]
    r = F["risk"]
    dd = r["epoch_drawdown"]
    L += ["", "**Risk:** worst day %s · losing-trade streak this week %d (epoch max %d, standing %d) · red-day streak "
          "epoch max %d (standing %d) · epoch equity %s, peak %s on %s, max drawdown %s (%s → %s), now %s below the peak"
          % (wday(r["worst_day"]), r["week_streaks"]["loss_trades_max"], r["epoch_streaks"]["loss_trades_max"],
             r["epoch_streaks"]["loss_trades_now"], r["epoch_streaks"]["red_days_max"],
             r["epoch_streaks"]["red_days_now"], m(dd["equity"]), m(dd["peak"]), dd["peak_day"],
             "$%s" % format(dd["max_dd"], ",.2f"), dd["max_dd_from"], dd["max_dd_to"], "$%s" % format(dd["dd_now"], ",.2f"))]
    if r["deployed"] is not None:
        L += ["", "| day | peak premium open at once (fleet) | at | QQQ only | over the ~$%s comfort |" % format(int(r["comfort_usd"]), ","),
              "|---|---|---|---|---|"]
        for d, v in sorted(r["deployed"].items()):
            q = (r["deployed_qqq"] or {}).get(d, {})
            L.append("| %s | $%s | %s | $%s | %s |" % (d, format(v["peak"], ",.0f"), v["at"],
                                                      format(q.get("peak", 0), ",.0f"), "YES" if v["over"] else "no"))
    if F["exit_fills"]:
        x = F["exit_fills"]
        L += ["", "**Exit ladder (warehouse rows, n %d):** steps median %s, max %s · submit-to-fill median %s ms, p90 %s ms"
              " · escalated %d" % (x["n"], x["steps_med"], x["steps_max"], x["latency_ms_med"], x["latency_ms_p90"],
                                   x["escalated"])]
    L += ["", "## 1B exits, entries, and the week against each setup's history"]
    gb = F["giveback_week"]
    L += ["", "| setup | peak open $ | given back | % | never right n | never right $ | green-to-red n | green-to-red $ |",
          "|---|---|---|---|---|---|---|---|"]
    for k, g in list(gb["by_strategy"].items()) + [("**book**", gb["book"])]:
        L.append("| %s | %s | %s | %s | %d | %s | %d | %s |" % (k, m(g["peak"]), m(g["given"]), g["given_pct"],
                                                                g["never_right_n"], m(g["never_right_usd"]), g["g2r_n"],
                                                                m(g["g2r_usd"])))
    L += ["", "| setup | this week n | EV | 95% | before this week n | EV | 95% |", "|---|---|---|---|---|---|---|"]
    for k, v in F["vs_history"].items():
        L.append("| %s | %d | %s | %s | %d | %s | %s |" % (k, v["week"]["n"], m(v["week"]["ev"]), ci(v["week"]),
                                                          v["before"]["n"], m(v["before"]["ev"]), ci(v["before"])))
    L += ["", "## 1C the epoch (OTV5, from %s)" % F["epoch_start"]]
    L += table("Epoch by setup", F["epoch_by_strategy"], F["epoch_book"])
    a = F["epoch_live_book"]
    L += ["", "**Live book (setups trading today):** n %d, EV %s %s" % (a["n"], m(a["ev"]), ci(a))]
    L += ["", "| week of | n | gross | EV | 95% | fees | green days | QQQ tape (efficiency, days) | VIX median | epoch EV to date |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for w in F["epoch_weeks"]:
        L.append("| %s | %d | %s | %s | %s | %s | %d/%d | %s %s | %s | %s |" % (
            w["week"], w["n"], m(w["gross"]), m(w["ev"]), ci(w), usd(w["fees"]), w["green_days"], w["days"],
            w["qqq_eff_mean"] if w["qqq_eff_mean"] is not None else "NOT MEASURED", ",".join(w["qqq_labels"]),
            w["vix_median"] if w["vix_median"] is not None else "NOT MEASURED", m(w["cum_ev"])))
    c = F["consistency"]
    L += ["", "**Consistency:** green days %d of %d · first half (before %s) EV %s %s n %d · second half EV %s %s n %d · "
          "the best 3 days %s (%s%% of gross) · without them EV %s %s n %d" % (
              c["green_days"], c["days"], c["split_day"], m(c["first_half"]["ev"]), ci(c["first_half"]),
              c["first_half"]["n"], m(c["second_half"]["ev"]), ci(c["second_half"]), c["second_half"]["n"],
              m(c["top3_days_usd"]), c["top3_share_pct"], m(c["ex_top3_days"]["ev"]), ci(c["ex_top3_days"]),
              c["ex_top3_days"]["n"])]
    L += ["", "## 2A conditions (live setups, cells with n >= %d; a cell is a lead, never a finding)" % F["cells_min_n"]]
    L += table("Top cells by EV", F["cells_top"]) + table("Bottom cells by EV", F["cells_bottom"])
    L += table("Hunt by side, epoch", F["hunt"]["epoch"]) + table("Hunt by side, this week", F["hunt"]["week"])
    o = F["ogap"]
    L += ["", "**OGAP (its own line):** n %d, %d-%d, gross %s, EV %s %s, fees %s beside · before 10:00 %d · calls %d"
          " puts %d · exits %s" % (o["n"], o["w"], o["l"], m(o["gross"]), m(o["ev"]), ci(o), usd(o["fees"]), o["before_1000"],
                                   o["calls"], o["puts"], o["exits"])]
    ov = F["ogap_vs_park"]
    L += ["", "**OGAP vs PARK (index rows, each scaled to $500 of outlay):** " + " · ".join(
        "%s n %d (index rows) EV %s %s worst day %s largest loss %s fees %s" % (
            s, ov[s]["n"], m(ov[s]["ev"]), ci(ov[s]), wday(ov[s]["worst_day"]), m(ov[s]["largest_loss"]),
            usd(ov[s]["fees"]))
        for s in (RK.OGAP, RK.PARK)) + " · overlap days %d, same side %d, daily P&L correlation %s" % (
            ov["overlap_days"], ov["same_side"], ov["corr"])]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--fri", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-warehouse", action="store_true")
    a = ap.parse_args(argv)
    fri = RK._day(a.fri)
    F = compute(fri, not a.no_warehouse)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "weekly_facts.json"), "w") as fh:
        json.dump(F, fh, indent=1, default=str)
    md = render(F)
    with open(os.path.join(a.out, "weekly_facts.md"), "w") as fh:
        fh.write(md)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
