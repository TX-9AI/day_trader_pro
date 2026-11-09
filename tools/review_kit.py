#!/usr/bin/env python3
"""
day_trader_pro/tools/review_kit.py — v1.2
v1.2  2026-11-09  dtp r544 / RETIRE.5 — T3's label is said plainly: the GEX pin butterfly is removed (OTV5 r103), so
      "T3 no GEXPin/PARK" now drops PARK and the fly's window history (its last trade 2026-11-03). The key stays
      byte-identical (it is ~/reviews/scripts/theories.py's label and theories.csv's t3_ev column); no number moves.
v1.1  2026-11-07  dtp r525 / RPT.37 — TWO NIGHTLY TRACKS: GIVEBACK WITHOUT PARK, AND HUNT BY CALL AND PUT. The operator,
      2026-11-07: "Yes, to 2 & 3" (the Saturday recap: the giveback ratio both with and without PARK's green-to-red
      trades - 49% overall, nearer 40% without; and Hunt calls +$6,842 / 71% win against puts -$196 / 39%).
      giveback.csv gains six columns AFTER its seven (every old column kept, in place): giveback_pct,
      giveback_ex_park_usd, peak_open_ex_park_usd, giveback_ex_park_pct, green_to_red_ex_park_n,
      green_to_red_ex_park_usd. A file still on the seven-column header is migrated in place (old rows keep their
      cells; the new ones are filled by `backfill` or left empty). NEW hunt DAY: LiquidityHunt split by side (long =
      call, short = put), the day and the window to date: n, net, win %, EV a trade, fees BESIDE (never inside;
      estimated where the row has none, counted in fees_est); upserts hunt_side.csv. NEW backfill FROM TO: every
      day with a trades CSV - the new giveback columns appended to the RECORDED row (its seven cells are never
      rewritten; a recomputed cell that differs is printed as a MISMATCH) and the hunt rows.
v1.0  2026-11-07  dtp r524 / RPT.36 — THE NIGHTLY REVIEW'S MECHANICAL HALF, SO AN UNATTENDED SESSION CANNOT DRIFT ON IT.
      The nightly post-RTH review (~/reviews/YYYY-MM-DD.md) was a session-only CronCreate job: it expired after 7 days
      (last fire 11-02) and was fixed in UTC, so after the 11-01 DST change it fired at 15:20 ET, before the close.
      11-04/11-05 were written late by hand and 11-06 not at all. tools/nightly_review.sh (the systemd timer's
      script) now runs the review headless; this file is every number in it that has exactly one right answer, so
      the session writes prose around figures it did not compute ad hoc. The operator, 2026-11-07: "Yes, on the timer".

SUBCOMMANDS (every one reads only; the CSV writers REPLACE the day's rows, so a re-run never double-appends):
  due [--now ISO]      the trading session whose review is due: the latest trading day D (market_calendar, 7 days
                       back) with now_et >= close(D) + DUE_AFTER_MIN (close 16:00 ET, 13:00 on a half day). Prints D,
                       or nothing (exit 1) when none is due. A weekend, a holiday and a pre-close run name the
                       previous session, never "today".
  trades DAY           the day's closed trades from the S3 warehouse (OTV5 tests/warehouse_source.load_trades,
                       OTV4TEST rows dropped by warehouse_source.mainline), exit date in ET == DAY, written to
                       ~/reviews/trades/DAY.csv (the existing columns, in order, plus mfe_premium at the end); the
                       fee column from the control fee model (fees_bridge.trade_fee, the figure the 10-26..11-03
                       window rows carry), empty when the model cannot price a row.
  window DAY           the window 10-26..DAY from ~/reviews/trades/20*.csv: n, realized, EV a trade with a
                       day-bootstrap 95% interval (seed 7, 20,000 draws), fees BESIDE (the row's fee, else the
                       estimate $1.25 a contract, $2.47 on SPX, marked estimated), EV ex the worst setup and ex the
                       worst symbol, without 10-26, post-decay (11-02..), and every theories.py filter. Upserts the
                       day's row in window_ev.csv and theories.csv.
  giveback DAY         the daily giveback (operator 2026-10-29) from ~/reviews/trades/DAY.csv; upserts giveback.csv.
                       Same formula as ~/reviews/scripts/giveback.py v1.0.
  hunt DAY             v1.1: LiquidityHunt by side (call = long, put = short), the day and the window to date, fees
                       beside; upserts hunt_side.csv.
  backfill FROM TO     v1.1: for every day FROM..TO with ~/reviews/trades/DAY.csv: the six ex-PARK giveback columns
                       onto the recorded giveback row (recorded cells kept; differences printed) and the hunt rows.
  upsert FILE DAY ROWS  replace FILE's rows whose first column is DAY with the CSV rows in ROWS (header included,
                       must match FILE's header exactly). The one door for the other nightly CSVs. A row whose first
                       cell is not a date (giveback.csv's '--help' row, 11-07) is dropped on every rewrite.

NEVER: a box read, a wake, an S3 write, a network call except the S3 read in `trades`, or a fee inside EV.
"""
import csv
import glob
import os
import random
import statistics as st
import sys
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
import market_calendar  # noqa: E402

ET = ZoneInfo("America/New_York")
REVIEWS = os.environ.get("DTP_REVIEWS_DIR", os.path.expanduser("~/reviews"))
OTV5_TESTS = os.environ.get("DTP_OTV5_TESTS", os.path.expanduser("~/OTV5/tests"))
WINDOW_START = "2026-10-26"
POST_DECAY = "2026-11-02"
OUTLIER_DAY = "2026-10-26"      # the operator's outlier day, reported "without" beside the window
DUE_AFTER_MIN = 40               # the review is due 40 min after the close (16:40 ET, 13:40 on a half day)
LOOKBACK_DAYS = 7
BOOT_N, BOOT_SEED = 20000, 7
FEE_EST, FEE_EST_SPX = 1.25, 2.47
TRADE_COLS = ["sym", "trade_id", "strategy", "direction", "contracts", "entry_premium", "exit_premium", "pnl_usd",
              "entry_time", "exit_time", "exit_reason", "fee", "mfe_premium"]
WINDOW_HDR = "date,trades,realized,fees,ev_per_trade,ev_ex_worst_setup,worst_setup,ev_ex_worst_symbol,worst_symbol"
THEORY_HDR = "date,baseline_n,baseline_ev,t1_ev,t2_ev,t3_ev,t1t2_ev,t1t3_ev,all3_ev"
GIVEBACK_HDR_V1 = "date,trades,giveback_usd,peak_open_usd,realized_on_green_usd,green_to_red_n,green_to_red_usd"
GIVEBACK_HDR = GIVEBACK_HDR_V1 + (",giveback_pct,giveback_ex_park_usd,peak_open_ex_park_usd,giveback_ex_park_pct,"
                                  "green_to_red_ex_park_n,green_to_red_ex_park_usd")          # v1.1: six appended
PARK = "PARK"
HUNT = "LiquidityHunt"
HUNT_HDR = ("date,side,n,net,win_pct,ev_per_trade,fees,fees_est,cum_n,cum_net,cum_win_pct,cum_ev_per_trade,cum_fees,"
            "cum_fees_est")
OTV4TEST_SYMS = ("AAL",)        # warehouse_source.mainline already drops OTV4TEST at `trades`; a guard for old CSVs


def _day(s):
    """An ISO date or SystemExit(2) naming what was passed - never a row keyed on '--help' (giveback.csv, 11-07)."""
    try:
        return date.fromisoformat(s).isoformat()
    except (TypeError, ValueError):
        raise SystemExit("review_kit: not a date (YYYY-MM-DD): %r" % (s,))


# ── due ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
def close_et(d):
    return datetime.combine(d, time(13, 0) if market_calendar.is_half_day(d) else time(16, 0), ET)


def due(now=None):
    """-> the ISO trading day whose review is due at `now` (aware datetime), or None."""
    now = (now or datetime.now(ET)).astimezone(ET)
    for back in range(LOOKBACK_DAYS + 1):
        d = now.date() - timedelta(days=back)
        if market_calendar.is_trading_day(d) and now >= close_et(d) + timedelta(minutes=DUE_AFTER_MIN):
            return d.isoformat()
    return None


# ── trades ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def et_date(iso):
    return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone(ET).date().isoformat()


def trade_rows(day, recs, fee_of=None):
    """Warehouse records -> the review CSV rows closed on `day` (ET), sorted by entry time. `fee_of(rec)` -> the
    fee model's figure (fees_bridge.trade_fee) or None; None leaves the cell empty and `window` estimates it."""
    out = []
    for r in recs:
        if r.get("pnl_usd") in (None, "") or not r.get("exit_time") or et_date(r["exit_time"]) != day:
            continue
        row = {c: r.get(c) for c in TRADE_COLS}
        row["sym"] = r.get("symbol")
        fee = fee_of(r) if fee_of else None
        row["fee"] = "" if fee is None else round(fee, 6)
        out.append({k: ("" if v is None else v) for k, v in row.items()})
    out.sort(key=lambda x: (str(x["entry_time"]), str(x["sym"])))
    return out


def cmd_trades(day, recs=None, fee_of=None):
    if fee_of is None:
        import fees_bridge
        fee_of = fees_bridge.trade_fee if fees_bridge.available() else (lambda r: None)
        if not fees_bridge.available():
            print("fee model unavailable (%s): fees left empty, estimated by `window`" % fees_bridge.FEES_ERR)
    if recs is None:
        sys.path.insert(0, OTV5_TESTS)
        import warehouse_source as ws
        # the dt= partition is the push date (UTC): a close after 19:00 ET lands in the next day's partition
        nxt = (date.fromisoformat(day) + timedelta(days=1)).isoformat()
        raw, _meta = ws.load_trades([day, nxt])
        recs, dropped = ws.mainline(raw)
        if dropped:
            print("OTV4TEST rows dropped: %s" % dropped)
    rows = trade_rows(day, recs, fee_of)
    path = os.path.join(REVIEWS, "trades", day + ".csv")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=TRADE_COLS)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)
    print("%s: %d closed trades -> %s" % (day, len(rows), path))
    return rows


# ── upsert ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def upsert(path, day, header, lines):
    """Replace every row of `day` in `path` with `lines` (CSV text rows, no header). Keeps every other row and the
    file's own header; refuses a header mismatch (a dropped or reordered column) rather than rewrite the file."""
    day = _day(day)
    old = open(path).read().splitlines() if os.path.exists(path) else [header]
    if old and old[0] != header:
        raise SystemExit("review_kit: %s header is %r, expected %r - not rewritten" % (path, old[0], header))
    keep = [l for l in old[1:] if l and l.split(",", 1)[0] != day and l.split(",", 1)[0][:1].isdigit()]
    rows = sorted(keep + list(lines), key=lambda l: l.split(",", 1)[0])
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        fh.write(header + "\n")
        for l in rows:
            fh.write(l + "\n")
    os.replace(tmp, path)
    return len(rows)


def cmd_upsert(path, day, rows_path):
    text = open(rows_path).read().splitlines()
    hdr = open(path).read().splitlines()[0] if os.path.exists(path) else text[0]
    if text[0] != hdr:
        raise SystemExit("review_kit: %s header %r does not match %s's %r" % (rows_path, text[0], path, hdr))
    lines = [l for l in text[1:] if l.strip()]
    bad = [l for l in lines if l.split(",", 1)[0] != _day(day)]
    if bad:
        raise SystemExit("review_kit: %d row(s) in %s are not for %s" % (len(bad), rows_path, day))
    n = upsert(path, day, hdr, lines)
    print("%s: %d row(s) for %s, %d rows total" % (path, len(lines), day, n))


# ── window ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def _theories():
    sys.path.insert(0, os.path.join(REVIEWS, "scripts"))
    import theories
    return theories


def load_window(cut):
    T = _theories()
    rows = []
    for f in sorted(glob.glob(os.path.join(REVIEWS, "trades", "20*.csv"))):
        for r in csv.DictReader(open(f)):
            if r.get("pnl_usd") in (None, "") or not r.get("entry_time"):
                continue
            x = T.norm(r["sym"], r["strategy"], r["pnl_usd"], r["entry_time"])
            if not (WINDOW_START <= x["day"] <= cut):
                continue
            if r.get("fee") not in (None, ""):
                x["fee"], x["est"] = float(r["fee"]), False
            else:
                c = float(r["contracts"])
                x["fee"], x["est"] = c * (FEE_EST_SPX if r["sym"] == "SPX" else FEE_EST), True
            rows.append(x)
    return rows


def boot(rows, n=BOOT_N, seed=BOOT_SEED):
    """Day-bootstrap 95% interval of EV a trade (whole days resampled with replacement)."""
    days = sorted({x["day"] for x in rows})
    if len(days) < 2:
        return None, None
    by = {d: [x["pnl"] for x in rows if x["day"] == d] for d in days}
    rnd = random.Random(seed)
    s = []
    for _ in range(n):
        v = [p for d in (rnd.choice(days) for _ in days) for p in by[d]]
        s.append(sum(v) / len(v))
    s.sort()
    return s[int(.025 * n)], s[int(.975 * n)]


def _ex_worst(rows, key):
    g = {}
    for x in rows:
        g[x[key]] = g.get(x[key], 0.0) + x["pnl"]
    worst = min(g, key=g.get)
    rest = [x for x in rows if x[key] != worst]
    return worst, (sum(x["pnl"] for x in rest) / len(rest) if rest else 0.0)


def window(cut):
    """-> dict of the window figures through `cut` (fees beside, never inside)."""
    cut = _day(cut)
    T = _theories()
    rows = load_window(cut)
    if not rows:
        raise SystemExit("review_kit: no trades in the window through %s" % cut)
    n, tot = len(rows), sum(x["pnl"] for x in rows)
    lo, hi = boot(rows)
    ws, evs = _ex_worst(rows, "strat")
    wy, evy = _ex_worst(rows, "sym")
    th = {}
    for lab, f in T.FILTERS:
        p = [x["pnl"] for x in rows if f(x)]
        th[lab] = (len(p), (st.mean(p) if p else 0.0), sum(p))
    no = [x for x in rows if x["day"] != OUTLIER_DAY]
    pd = [x for x in rows if x["day"] >= POST_DECAY]
    return dict(cut=cut, n=n, total=tot, ev=tot / n, lo=lo, hi=hi, fees=sum(x["fee"] for x in rows),
                fees_est=sum(x["fee"] for x in rows if x["est"]), worst_setup=ws, ev_ex_setup=evs, worst_sym=wy,
                ev_ex_sym=evy, theories=th, no_outlier=(len(no), sum(x["pnl"] for x in no)),
                post_decay=(len(pd), sum(x["pnl"] for x in pd)), days=len({x["day"] for x in rows}))


def _ev(th, lab):
    return th[lab][1]


def cmd_window(cut, write=True):
    w = window(cut)
    th = w["theories"]
    lo = "n/a" if w["lo"] is None else "%+.2f" % w["lo"]
    hi = "n/a" if w["hi"] is None else "%+.2f" % w["hi"]
    print("window %s..%s: %d trades over %d days, realized %+.2f, EV %+.2f a trade, 95%% day-bootstrap [%s, %s]"
          % (WINDOW_START, w["cut"], w["n"], w["days"], w["total"], w["ev"], lo, hi))
    print("  fees beside (never inside): %.2f, of which estimated %.2f" % (w["fees"], w["fees_est"]))
    print("  ex worst setup (%s) %+.2f | ex worst symbol (%s) %+.2f" % (w["worst_setup"], w["ev_ex_setup"],
                                                                         w["worst_sym"], w["ev_ex_sym"]))
    n0, t0 = w["no_outlier"]
    n1, t1 = w["post_decay"]
    print("  without %s: n=%d %+.2f EV %+.2f | post-decay (%s..): n=%d %+.2f EV %+.2f" % (
        OUTLIER_DAY, n0, t0, (t0 / n0 if n0 else 0), POST_DECAY, n1, t1, (t1 / n1 if n1 else 0)))
    for lab, (n, ev, tot) in th.items():
        print("  %-38s n=%4d EV %+8.2f total %+10.2f" % (lab, n, ev, tot))
    if write:
        upsert(os.path.join(REVIEWS, "window_ev.csv"), w["cut"], WINDOW_HDR, [
            "%s,%d,%.2f,%.2f,%.2f,%.2f,%s,%.2f,%s" % (w["cut"], w["n"], w["total"], w["fees"], w["ev"],
                                                      w["ev_ex_setup"], w["worst_setup"], w["ev_ex_sym"],
                                                      w["worst_sym"])])
        upsert(os.path.join(REVIEWS, "theories.csv"), w["cut"], THEORY_HDR, [
            "%s,%d,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f" % (
                w["cut"], w["n"], w["ev"], _ev(th, "T1 no SPX"), _ev(th, "T2 no entries after 10:01"),
                _ev(th, "T3 no GEXPin/PARK"),   # v1.2: the fly is history (OTV5 r103) - T3 = no PARK, no fly history
                _ev(th, "T1+T2"), _ev(th, "T1+T3"), _ev(th, "T1+T2+T3"))])
        print("  window_ev.csv and theories.csv: row %s replaced" % w["cut"])
    return w


# ── giveback ────────────────────────────────────────────────────────────────────────────────────────────────────────
def giveback(day, rows):
    """Operator 2026-10-29. peak = max(mfe_premium, exit_premium); giveback = (max(peak, entry) - max(exit, entry))
    x contracts x 100; peak_open = max(0, peak - entry) x contracts x 100; green-to-red = peak above entry and a loss."""
    out = []
    for r in rows:
        if not r.get("exit_premium") or r.get("pnl_usd") in ("", None):
            continue
        e, x, c = float(r["entry_premium"]), float(r["exit_premium"]), int(float(r["contracts"]))
        pk = max(float(r.get("mfe_premium") or x), x)
        pnl = float(r["pnl_usd"])
        out.append(dict(sym=r["sym"], strat=r["strategy"], pnl=pnl, peak_open=max(0.0, pk - e) * c * 100,
                        giveback=(max(pk, e) - max(x, e)) * c * 100, g2r=(pk > e and pnl < 0)))
    g2r = [r for r in out if r["g2r"]]
    xp = [r for r in out if r["strat"] != PARK]
    xg = [r for r in xp if r["g2r"]]
    gb, pk = sum(r["giveback"] for r in out), sum(r["peak_open"] for r in out)
    xgb, xpk = sum(r["giveback"] for r in xp), sum(r["peak_open"] for r in xp)
    return dict(n=len(out), giveback=gb, peak_open=pk,
                kept=sum(r["pnl"] for r in out if r["peak_open"] > 0), g2r_n=len(g2r),
                g2r_usd=sum(r["pnl"] for r in g2r), rows=out,
                pct=(100.0 * gb / pk if pk else None), x_giveback=xgb, x_peak_open=xpk,
                x_pct=(100.0 * xgb / xpk if xpk else None), x_g2r_n=len(xg), x_g2r_usd=sum(r["pnl"] for r in xg))


def _pct(v):
    return "" if v is None else "%.2f" % v


def giveback_cells_v1(day, g):
    return "%s,%d,%.2f,%.2f,%.2f,%d,%.2f" % (day, g["n"], g["giveback"], g["peak_open"], g["kept"], g["g2r_n"],
                                            g["g2r_usd"])


def giveback_cells_new(g):
    return "%s,%.2f,%.2f,%s,%d,%.2f" % (_pct(g["pct"]), g["x_giveback"], g["x_peak_open"], _pct(g["x_pct"]),
                                        g["x_g2r_n"], g["x_g2r_usd"])


def migrate_giveback(path):
    """v1.1 — a giveback.csv on the seven-column header gains the six new columns, empty, every row kept as it was.
    Any other header that is not the current one is refused (upsert's rule)."""
    if not os.path.exists(path):
        return False
    lines = open(path).read().splitlines()
    if not lines or lines[0] != GIVEBACK_HDR_V1:
        return False
    extra = "," * (GIVEBACK_HDR.count(",") - GIVEBACK_HDR_V1.count(","))
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        fh.write(GIVEBACK_HDR + "\n")
        for l in lines[1:]:
            if l and l.split(",", 1)[0][:1].isdigit():
                fh.write(l + extra + "\n")
    os.replace(tmp, path)
    print("  giveback.csv: migrated to the v1.1 header (six columns appended, %d rows kept)" % (len(lines) - 1))
    return True


def cmd_giveback(day, write=True):
    day = _day(day)
    path = os.path.join(REVIEWS, "trades", day + ".csv")
    rows = list(csv.DictReader(open(path)))
    if rows and "mfe_premium" not in rows[0]:
        raise SystemExit("review_kit: %s has no mfe_premium column - run `review_kit.py trades %s` first" % (path, day))
    g = giveback(day, rows)
    print("%s: n=%d giveback $%.2f of a $%.2f peak open profit (%s%%), realized on those $%.2f; green-to-red %d for $%.2f"
          % (day, g["n"], g["giveback"], g["peak_open"], _pct(g["pct"]) or "n/a", g["kept"], g["g2r_n"],
             g["g2r_usd"]))
    print("  without PARK: giveback $%.2f of $%.2f (%s%%); green-to-red %d for $%.2f"
          % (g["x_giveback"], g["x_peak_open"], _pct(g["x_pct"]) or "n/a", g["x_g2r_n"], g["x_g2r_usd"]))
    by = {}
    for r in g["rows"]:
        by.setdefault(r["strat"], [0, 0.0])
        by[r["strat"]][0] += 1
        by[r["strat"]][1] += r["giveback"]
    print("  by setup: " + "; ".join("%s $%.0f (n %d)" % (k, v[1], v[0]) for k, v in
                                     sorted(by.items(), key=lambda kv: -kv[1][1])))
    if write:
        gp = os.path.join(REVIEWS, "giveback.csv")
        migrate_giveback(gp)
        upsert(gp, day, GIVEBACK_HDR, [giveback_cells_v1(day, g) + "," + giveback_cells_new(g)])
    return g


# ── hunt by side (v1.1) ─────────────────────────────────────────────────────────────────────────────────────────────
def _trade_files(cut):
    return [f for f in sorted(glob.glob(os.path.join(REVIEWS, "trades", "20*.csv")))
            if WINDOW_START <= os.path.basename(f)[:10] <= cut]


def hunt_rows(cut):
    """-> [{day, side, pnl, fee, est}] for every closed LiquidityHunt trade 10-26..cut, side call (long) / put (short)."""
    out = []
    for f in _trade_files(cut):
        day = os.path.basename(f)[:10]
        for r in csv.DictReader(open(f)):
            if r.get("strategy") != HUNT or r.get("pnl_usd") in (None, "") or r.get("sym") in OTV4TEST_SYMS:
                continue
            d = (r.get("direction") or "").lower()
            side = "call" if d in ("long", "call") else "put" if d in ("short", "put") else None
            if side is None:
                raise SystemExit("review_kit: %s %s has direction %r - neither long nor short" % (f, r.get("trade_id"),
                                                                                                    d))
            if r.get("fee") not in (None, ""):
                fee, est = float(r["fee"]), False
            else:
                fee, est = float(r["contracts"]) * (FEE_EST_SPX if r.get("sym") == "SPX" else FEE_EST), True
            out.append(dict(day=day, side=side, pnl=float(r["pnl_usd"]), fee=fee, est=est))
    return out


def _agg(xs):
    n = len(xs)
    net = sum(x["pnl"] for x in xs)
    return dict(n=n, net=net, win=(100.0 * sum(1 for x in xs if x["pnl"] > 0) / n if n else None),
                ev=(net / n if n else None), fees=sum(x["fee"] for x in xs),
                fees_est=sum(x["fee"] for x in xs if x["est"]))


def hunt(day):
    day = _day(day)
    rows = hunt_rows(day)
    res = {}
    for side in ("call", "put"):
        res[side] = (_agg([x for x in rows if x["side"] == side and x["day"] == day]),
                     _agg([x for x in rows if x["side"] == side]))
    return res


def hunt_lines(day, res):
    def f(v):
        return "" if v is None else "%.2f" % v
    out = []
    for side in ("call", "put"):
        a, c = res[side]
        out.append("%s,%s,%d,%.2f,%s,%s,%.2f,%.2f,%d,%.2f,%s,%s,%.2f,%.2f" % (
            day, side, a["n"], a["net"], f(a["win"]), f(a["ev"]), a["fees"], a["fees_est"],
            c["n"], c["net"], f(c["win"]), f(c["ev"]), c["fees"], c["fees_est"]))
    return out


def cmd_hunt(day, write=True):
    day = _day(day)
    res = hunt(day)
    for side in ("call", "put"):
        a, c = res[side]
        print("%s Hunt %-4s day: n=%d net %+.2f win %s%% EV %s | window: n=%d net %+.2f win %s%% EV %s | fees beside "
              "%.2f (window %.2f, est %.2f)" % (day, side, a["n"], a["net"], _pct(a["win"]) or "n/a",
                                                  _pct(a["ev"]) or "n/a", c["n"], c["net"], _pct(c["win"]) or "n/a",
                                                  _pct(c["ev"]) or "n/a", a["fees"], c["fees"], c["fees_est"]))
    if write:
        upsert(os.path.join(REVIEWS, "hunt_side.csv"), day, HUNT_HDR, hunt_lines(day, res))
    return res


# ── backfill (v1.1) ─────────────────────────────────────────────────────────────────────────────────────────────────
def cmd_backfill(frm, to):
    frm, to = _day(frm), _day(to)
    gp = os.path.join(REVIEWS, "giveback.csv")
    migrate_giveback(gp)
    rec = {}
    if os.path.exists(gp):
        for l in open(gp).read().splitlines()[1:]:
            if l and l[:1].isdigit():
                rec[l.split(",", 1)[0]] = l
    mism = []
    days = [os.path.basename(f)[:10] for f in _trade_files(to) if os.path.basename(f)[:10] >= frm]
    for day in days:
        rows = list(csv.DictReader(open(os.path.join(REVIEWS, "trades", day + ".csv"))))
        g = giveback(day, rows)
        mine = giveback_cells_v1(day, g)
        old = rec.get(day)
        if old:
            v1 = ",".join(old.split(",")[:GIVEBACK_HDR_V1.count(",") + 1])
            if v1 != mine:
                mism.append((day, v1, mine))
                print("  MISMATCH %s giveback: recorded %s | recomputed %s (recorded kept)" % (day, v1, mine))
        else:
            v1 = mine
        upsert(gp, day, GIVEBACK_HDR, [v1 + "," + giveback_cells_new(g)])
        upsert(os.path.join(REVIEWS, "hunt_side.csv"), day, HUNT_HDR, hunt_lines(day, hunt(day)))
        print("  %s: giveback ex-PARK %s%% of %s%%; hunt rows written" % (day, _pct(g["x_pct"]) or "n/a",
                                                                     _pct(g["pct"]) or "n/a"))
    print("backfill %s..%s: %d day(s), %d giveback mismatch(es)" % (frm, to, len(days), len(mism)))
    return days, mism


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    if not a or a[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd, rest = a[0], a[1:]
    if cmd == "due":
        now = None
        if rest[:1] == ["--now"] and len(rest) > 1:
            now = datetime.fromisoformat(rest[1])
            now = now if now.tzinfo else now.replace(tzinfo=ET)
        d = due(now)
        if d:
            print(d)
            return 0
        return 1
    if cmd == "trades" and len(rest) == 1:
        cmd_trades(_day(rest[0]))
        return 0
    if cmd == "window" and len(rest) == 1:
        cmd_window(rest[0])
        return 0
    if cmd == "giveback" and len(rest) == 1:
        cmd_giveback(rest[0])
        return 0
    if cmd == "hunt" and len(rest) == 1:
        cmd_hunt(rest[0])
        return 0
    if cmd == "backfill" and len(rest) == 2:
        cmd_backfill(rest[0], rest[1])
        return 0
    if cmd == "upsert" and len(rest) == 3:
        cmd_upsert(rest[0], rest[1], rest[2])
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
