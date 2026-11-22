#!/usr/bin/env python3
"""
day_trader_pro/tools/runaway_watch.py  v1.0
v1.0  2026-11-22  dtp r575 / RWATCH.1 — THE RUNAWAY EQUITY WATCH LIST AND ITS TREND BARS, SCORED THE ONE FROZEN WAY.
      The operator, 2026-11-22: "I would keep any poor performers on runaway on notice to potentially be cut", and "Can
      you put a trend bar for runaway on the equities to see if they are trending in the right direction or the wrong
      direction for that setup?" The list and the cut bar are FROZEN in ~/reviews/runaway_watch_20261122/WATCH.md
      (sealed 2026-11-22T18:05:32Z before the 11-23 open, sha256 in SEAL.txt beside it; WATCH_SHA below). This file only
      measures; it never re-fits the list or moves the bar:
        on notice      NVDA, AMD, META (in-sample 10-26..11-20 gross EV a trade -$86.95, -$59.54, -$32.11 at the mark;
                       net after fees -$95.90, -$61.42, -$35.03)
        RECOMMEND CUT  a watch-list symbol whose Runaway trades from 2026-11-23 on number >= CUT_MIN_N (8) AND whose net
                       EV a trade (pnl_usd - fee, at the mark, after fees) is below zero; past trades never count
        OFF THE LIST   >= 8 forward trades with net EV a trade >= 0
        ON NOTICE      fewer than 8 forward trades
      The bar is read at every scoring on all of the symbol's forward trades through the day scored. Any cut needs the
      operator's yes: the bar only triggers the recommendation. Half days are non-trading days (the operator,
      2026-11-22: "just treat them as bank holidays. No trading."): never a session; a Runaway trade dated on one would
      be a defect (OTV5 r145 opens nothing then), so it is counted and named.
      Per equity (every non-index symbol; the indexes are QQQ and SPX): n, gross, fees, net, net EV a trade, the
      cumulative net P&L by trade since 2026-10-26 with the 2026-11-23 forward marker (a text sparkline; the daily recap
      PDF draws the same series), and DIRECTION: the net EV a trade of the last DIRECTION_N (8) trades against the
      earlier ones, each with n (up = the recent trades do better; n/a below 9 trades). Report only, never a qualifier.
      Source ~/reviews/trades/<day>.csv (already mainline, OTV4TEST out), strategy RunawayContinuation, the day = the
      file's date; a blank fee is estimated with tools/review_kit.est_fee and counted. Standard library and dtp modules
      only (market_calendar, review_kit); read-only; never prints an environment, never touches a box or a bot.

Usage:
  python3 tools/runaway_watch.py [--through YYYY-MM-DD] [--trades DIR] [--json F] [--md F]
  python3 tools/runaway_watch.py --check-seal        WATCH.md against its sealed sha256 (exit 1 on a mismatch)
"""
import argparse
import csv
import glob
import hashlib
import json
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
import market_calendar  # noqa: E402
import review_kit as RK  # noqa: E402  (est_fee: one fee estimate for a blank cell)

HOME = os.path.expanduser("~")
TRADES = os.path.join(HOME, "reviews", "trades")
WATCH = os.path.join(HOME, "reviews", "runaway_watch_20261122", "WATCH.md")
WATCH_SHA = "eeb225665a2b73e8e71089c50a05c06abf56645ddfa90e9ab8aa43bdb2e6930c"
WATCH_LIST = ("NVDA", "AMD", "META")         # frozen in WATCH.md
INDEX = ("QQQ", "SPX")
RUNAWAY = "RunawayContinuation"
HISTORY_START = "2026-10-26"
FORWARD_START = "2026-11-23"
CUT_MIN_N = 8
DIRECTION_N = 8
OTV4TEST_SYMS = RK.OTV4TEST_SYMS             # a guard for old CSVs (mainline already dropped them)
ON_NOTICE, CUT, OFF = "ON NOTICE", "RECOMMEND CUT", "OFF THE LIST"
SPARK = "▁▂▃▄▅▆▇█"
SMALL = "the bar needs %d forward trades, and even %d trades is a small sample" % (CUT_MIN_N, CUT_MIN_N)


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def load(through, trades_dir=TRADES):
    """-> (rows, est_n): every Runaway row on a non-index symbol from HISTORY_START through `through`, in (day, entry)
    order. A row: day, sym, pnl (the mark), fee, net, est (fee estimated), entry, half (dated on a half day)."""
    rows, est = [], 0
    for p in sorted(glob.glob(os.path.join(trades_dir, "20??-??-??.csv"))):
        d = os.path.basename(p)[:10]
        if not (HISTORY_START <= d <= through):
            continue
        with open(p, encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                sym = (r.get("sym") or "").upper()
                if r.get("strategy") != RUNAWAY or sym in INDEX or sym in OTV4TEST_SYMS:
                    continue
                pnl = _f(r.get("pnl_usd"))
                if pnl is None:
                    continue
                fee = _f(r.get("fee"))
                e = fee is None
                if e:
                    fee = RK.est_fee(sym, r.get("contracts") or 0)
                    est += 1
                rows.append({"day": d, "sym": sym, "pnl": pnl, "fee": fee, "net": pnl - fee, "est": e,
                             "entry": r.get("entry_time") or "", "half": market_calendar.is_half_day(date.fromisoformat(d))})
    rows.sort(key=lambda x: (x["day"], x["entry"], x["sym"]))
    return rows, est


def agg(v):
    n = len(v)
    g = sum(x["pnl"] for x in v)
    f = sum(x["fee"] for x in v)
    return {"n": n, "gross": round(g, 2), "fees": round(f, 2), "net": round(g - f, 2),
            "ev_net": round((g - f) / n, 2) if n else None}


def direction(v):
    """-> {arrow, word, last, earlier}: the last DIRECTION_N trades' net EV against the earlier ones'."""
    if len(v) <= DIRECTION_N:
        return {"arrow": "·", "word": "n/a", "last": agg(v[-DIRECTION_N:]), "earlier": agg([]),
                "why": "n/a (n %d: needs %d+ trades for an earlier set)" % (len(v), DIRECTION_N + 1)}
    last, earlier = agg(v[-DIRECTION_N:]), agg(v[:-DIRECTION_N])
    d = last["ev_net"] - earlier["ev_net"]
    arrow, word = ("↑", "up") if d > 0 else (("↓", "down") if d < 0 else ("→", "flat"))
    return {"arrow": arrow, "word": word, "last": last, "earlier": earlier, "why": ""}


def status(fwd):
    if fwd["n"] < CUT_MIN_N:
        return ON_NOTICE
    return CUT if fwd["ev_net"] < 0 else OFF


def sparkline(series, marker):
    """A text trend bar of the cumulative net series; '|' sits before the first forward trade (index `marker`)."""
    if not series:
        return ""
    lo, hi = min(series + [0.0]), max(series + [0.0])
    span = (hi - lo) or 1.0
    ch = [SPARK[min(len(SPARK) - 1, int((v - lo) / span * (len(SPARK) - 1) + 0.5))] for v in series]
    if marker is not None:
        ch.insert(marker, "|")
    return "".join(ch)


def score(through, trades_dir=TRADES):
    rows, est = load(through, trades_dir)
    syms = sorted({x["sym"] for x in rows} | set(WATCH_LIST))
    out = {"through": through, "watch": WATCH, "watch_sha": WATCH_SHA, "watch_list": list(WATCH_LIST),
           "forward_start": FORWARD_START, "cut_min_n": CUT_MIN_N, "direction_n": DIRECTION_N,
           "basis": "the mark (pnl_usd); net = pnl_usd - fee, after fees", "fees_estimated": est,
           "forward_sessions": forward_sessions(through), "equities": {}}
    for s in syms:
        v = [x for x in rows if x["sym"] == s]
        fv = [x for x in v if x["day"] >= FORWARD_START]
        cum, c = [], 0.0
        for x in v:
            c += x["net"]
            cum.append(round(c, 2))
        mk = next((i for i, x in enumerate(v) if x["day"] >= FORWARD_START), None)
        e = dict(agg(v), forward=agg(fv), direction=direction(v), cum=cum, days=[x["day"] for x in v],
                 forward_index=mk, spark=sparkline(cum, mk), watch=s in WATCH_LIST,
                 half_day_trades=sorted({x["day"] for x in v if x["half"]}))
        if e["watch"]:
            e["status"] = status(e["forward"])
            e["forward_needed"] = max(0, CUT_MIN_N - e["forward"]["n"])
        out["equities"][s] = e
    return out


def forward_sessions(through):
    """The sessions from FORWARD_START through `through` (dtp market_calendar; a half day is not a session)."""
    out, x = [], date.fromisoformat(FORWARD_START)
    end = date.fromisoformat(through)
    while x <= end:
        if market_calendar.is_trading_day(x) and not market_calendar.is_half_day(x):
            out.append(x.isoformat())
        x = date.fromordinal(x.toordinal() + 1)
    return out


def _m(x, dec=0):
    if x is None:
        return "-"
    s = "{:,.%df}" % dec
    return ("−" if x < 0 else "+" if x > 0 else "") + "$" + s.format(abs(x))


def dir_text(d):
    if d["word"] == "n/a":
        return "· " + d["why"]
    return "%s %s: last %d %s a trade vs earlier %s (n %d)" % (d["arrow"], d["word"], d["last"]["n"],
                                                               _m(d["last"]["ev_net"]), _m(d["earlier"]["ev_net"]),
                                                               d["earlier"]["n"])


def watch_rows(sc):
    """-> [(sym, forward n, forward net, forward EV, bar text, status)] for the watch list, in WATCH_LIST order."""
    out = []
    for s in WATCH_LIST:
        e = sc["equities"][s]
        f = e["forward"]
        bar = ("%d more forward trade(s) needed" % e["forward_needed"]) if f["n"] < CUT_MIN_N else (
            "EV %s %s 0 (n %d >= %d)" % (_m(f["ev_net"]), "<" if f["ev_net"] < 0 else ">=", f["n"], CUT_MIN_N))
        out.append((s, f["n"], f["net"], f["ev_net"], bar, e["status"]))
    return out


def render_md(sc):
    L = ["# Runaway equity watch, through %s" % sc["through"], "",
         "Frozen in %s (sha256 %s). Basis: the mark (pnl_usd), net = pnl_usd − fee, after fees. Report only: nothing "
         "here changes trading; any cut needs the operator's yes." % (sc["watch"], sc["watch_sha"][:12]), "",
         "**Cut bar:** a watch-list symbol is RECOMMENDED for cutting from Runaway when its Runaway trades from %s on "
         "number at least %d AND their net EV a trade is below zero; at %d+ with net EV >= 0 it comes OFF THE LIST; "
         "past trades never count. Forward sessions so far: %d (half days are not sessions)." % (
             sc["forward_start"], sc["cut_min_n"], sc["cut_min_n"], len(sc["forward_sessions"])), "",
         "## The watch list", "",
         "| symbol | forward n | forward net | forward EV a trade | against the bar | status |", "|---|---|---|---|---|---|"]
    for s, n, net, ev, bar, st in watch_rows(sc):
        L.append("| %s | %d | %s | %s | %s | **%s** |" % (s, n, _m(net) if n else "-", _m(ev), bar, st))
    if any(r[1] < CUT_MIN_N for r in watch_rows(sc)):
        L += ["", "Below %d forward trades a symbol stays ON NOTICE: %s." % (CUT_MIN_N, SMALL)]
    L += ["", "## Every equity, Runaway since %s (the trend bar: cumulative net by trade, `|` = %s)" % (
        HISTORY_START, sc["forward_start"]), "",
        "| symbol | n | gross | fees | net | net EV a trade | direction (last %d vs earlier, n beside) | trend | watch |"
        % sc["direction_n"], "|---|---|---|---|---|---|---|---|---|"]
    for s, e in sc["equities"].items():
        L.append("| %s | %d | %s | %s | %s | %s | %s | `%s` | %s |" % (
            s, e["n"], _m(e["gross"]), _m(e["fees"]).lstrip("+"), _m(e["net"]), _m(e["ev_net"]),
            dir_text(e["direction"]), e["spark"] or "-", e.get("status", "-")))
    half = {s: e["half_day_trades"] for s, e in sc["equities"].items() if e["half_day_trades"]}
    L += ["", "Fees estimated (blank fee cells): %d." % sc["fees_estimated"]]
    if half:
        L += ["DEFECT: Runaway trades dated on a half day (OTV5 r145 opens nothing then): %s." % "; ".join(
            "%s %s" % (s, ", ".join(d)) for s, d in half.items())]
    L += ["Direction is report only, never a qualifier; with %d or fewer trades there is no earlier set (n/a)."
          % sc["direction_n"], ""]
    return "\n".join(L) + "\n"


def figures(sc):
    """Every dollar figure the scorer prints, rounded to the dollar (a commentary may quote only these)."""
    out = set()
    for e in sc["equities"].values():
        for m in (e, e["forward"], e["direction"]["last"], e["direction"]["earlier"]):
            for k in ("gross", "fees", "net", "ev_net"):
                if m.get(k) is not None:
                    out.add(round(abs(m[k])))
    return out


def seal_sha(path=WATCH):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser(description="the Runaway equity watch list, scored as WATCH.md froze it")
    ap.add_argument("--through", default=None, help="the last day scored (default: the newest trade file)")
    ap.add_argument("--trades", default=TRADES)
    ap.add_argument("--json", default=None)
    ap.add_argument("--md", default=None)
    ap.add_argument("--check-seal", action="store_true")
    ap.add_argument("--watch", default=WATCH)
    a = ap.parse_args(argv)
    if a.check_seal:
        try:
            sha = seal_sha(a.watch)
        except OSError as e:
            print("WATCH unreadable: %s" % e)
            return 1
        ok = sha == WATCH_SHA
        print("WATCH %s (%s)" % ("SEALED" if ok else "CHANGED: sha256 %s is not the sealed %s" % (sha, WATCH_SHA),
                                 a.watch))
        return 0 if ok else 1
    through = a.through
    if not through:
        days = sorted(os.path.basename(p)[:10] for p in glob.glob(os.path.join(a.trades, "20??-??-??.csv")))
        through = days[-1] if days else FORWARD_START
    sc = score(through, a.trades)
    md = render_md(sc)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(sc, fh, indent=1, ensure_ascii=False)
    if a.md:
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write(md)
    if not a.json and not a.md:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
