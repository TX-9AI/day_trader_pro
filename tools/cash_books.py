#!/usr/bin/env python3
"""
day_trader_pro/tools/cash_books.py  v1.5
v1.5  2026-11-23  dtp r581 — SPX IS BACK ON $5,000. The operator, 2026-11-23: "I'm going to just bump it back up to $5K for
      consistency's sake" (applied 18:41 ET). SIZES is a base size and dated windows: SPX $5,000, except $4,200 on
      2026-11-23 ONLY; the Entry sizes line names the size of the scored day (through) and the window beside it, and
      figures() holds every size printed. Report only: no book, window or metric changes, PREREG's sha holds.
v1.4  2026-11-23  dtp r580 / RECAP.3 — THE SCOREBOARD PRINTS ITS SIZE BASIS. The daily recap prompt asks the C1-C4
      commentary to name the SPX size change ($4,200 an entry from 2026-11-23, was $5,000), and the validator withheld the
      11-23 commentary for quoting $4,200 and $5,000, figures the scorer never printed. score() now carries "sizes"
      (SIZES: the per-entry sizes the boxes trade; paper is sized as cash) and render_md prints them as one "Entry sizes"
      line; figures() includes them. Report only: no book, window or metric changes, PREREG's sha holds.
v1.3  2026-11-22  dtp r578 / CAP.11, AMENDMENT 3 (proposed; to be written in AMENDMENTS.txt before any after_cap trade
      exists, PREREG.md unchanged, its sha still holds). The books measure what CASH would have done. OTV5 r151 makes the
      daily catastrophic cap record only on a paper box (the operator, 2026-11-22: "there's no harm in letting paper
      run & we can just note if the breaker would have popped"): a paper box trades on past the would-be trip and tags
      what it opens then after_cap = 1; and on a cash box OGAP books paper beside the cash rows (OTV5 r150). load()
      gives every row its book through review_kit.split, the one rule (per file: a paper row on a cash box's day - its
      Service mode line in the conductor's extract, else a cash row - is paper_on_cash, else an after_cap row is after_cap, else headline); the books and every PREREG metric
      read the headline rows only, so a trade cash would never have opened is never in a book. Each window also counts
      the extra paper after the breaker per book (n, gross: extras) and the md prints one line for it under a window
      that has any; nothing prints when none exists, so every scoreboard before the first after_cap trade is
      byte-identical (the in-sample block and --check-prereg included). The displaced-fire count reads every row as before.
v1.2  2026-11-22  dtp r574 / CASHBOOK.2, AMENDMENT 2 (~/reviews/cash_candidates_20261121/AMENDMENTS.txt, written before
      any forward data; PREREG.md unchanged, its sha still holds). The operator, 2026-11-22: "I want the best risk to
      reward balance, the highest earning combination with as low as we can get drawdowns". (a) Every book and window
      gets RETURN TO DRAWDOWN, rtd = net / |max drawdown on the daily equity curve| (net after fees, at the mark; None,
      printed "no drawdown", when the window never drew down). It RANKS, it never filters: every table lists the books in
      the order of the COMBINED window's rtd (highest first; PREREG's C1-C4 order breaks ties and a book with no
      drawdown goes first), and a ranking line above the tables names each book's combined and forward rtd. Every
      PREREG metric is printed unchanged. (b) Half days are non-trading days (the operator, 2026-11-22: "just treat them
      as bank holidays. No trading."): sessions() leaves out market_calendar.is_half_day, so the forward window is 7
      sessions (11-27 out). (c) amendment_lines(): the first line of EVERY amendment (was amendment 1's only);
      amendment_line() is kept and returns the first.
v1.1  2026-11-22  dtp r572 / CASHBOOK.1, AMENDMENT 1 (~/reviews/cash_candidates_20261121/AMENDMENTS.txt; PREREG.md
      unchanged, its sha still holds). The operator, 2026-11-22: "Our trading sample is already small. I don't know if
      I'm on board with cutting the 2 best trades to qualify. You want to cut the 2 worst as well? I didn't think so."
      "Gross without the two largest winners" is never shown alone: every table prints it only beside the new "gross
      without the two largest losers" (gross_ex_bottom2), both labelled CONCENTRATION CONTEXT, never a qualifier, a pass
      bar or a ranking input. --check-prereg still reproduces PREREG's table as recorded (its ex-top-2 column
      included) and prints the amendment's first line; an amendment never fails the sha check.
v1.0  2026-11-22  dtp r572 / CASHBOOK.1 — THE FOUR CASH CANDIDATE BOOKS, SCORED THE ONE PRE-REGISTERED WAY. The
      operator, 2026-11-22: "On C1-C4, I would like some commentary on the daily and weekly recaps as to how each of
      them is performing". The books, the metrics and the windows are FROZEN in
      ~/reviews/cash_candidates_20261121/PREREG.md (sealed 2026-11-21T23:57:18Z, sha256 in SEAL.txt beside it; PREREG_SHA
      below). This file only measures them; it never re-fits a book, prunes a symbol or moves a threshold:
        C1  QQQ and SPX only: Runaway and PARK
        C2  all 14 symbols: PARK and Runaway
        C3  all 14: PARK on the indexes (QQQ, SPX), Runaway on the 12 equities
        C4  all 14: PARK and Runaway on the indexes, Runaway only on the equities
      Source ~/reviews/trades/<day>.csv (already mainline, OTV4TEST out). Basis the mark (pnl_usd); fees (fee) BESIDE,
      never inside EV. Per book and window: n, gross, fees, net = gross - fees, EV a trade with a 95% day-bootstrap
      interval (5,000 draws, seed 1; whole trade days of the book resampled), up days out of the sessions (a session's
      gross > 0), worst day, max drawdown on the daily equity curve (from 0 at the window's start), gross without the
      book's two largest winners. Windows: in-sample 2026-10-26..11-20 (20 sessions, hindsight), forward 2026-11-23..
      12-03 (8 sessions; after 12-03 the forward line keeps going, cumulative), combined, and on request one day and
      one week. The in-sample block reproduces PREREG's baseline table exactly (`--check-prereg`;
      tests/check_cash_books.py C1). The displaced-fire count (PREREG's caveat): the forward book trades that fired
      while a LiquidityHunt or OGAP position was open on the same box (entry <= fire < exit, from the trade files'
      times). A fire that never became a trade is not in the trade files, so it cannot be counted: NOT MEASURED.
      REPORT ONLY: the books are never in the window EV or the theories, and the choice of book is the operator's.
      Standard library and dtp market_calendar (v1.3: and review_kit.split) only; read-only; never prints an environment.

Usage:
  python3 tools/cash_books.py --through YYYY-MM-DD [--day D] [--week-start D] [--trades DIR] [--json F] [--md F]
  python3 tools/cash_books.py --check-prereg       the in-sample block against PREREG's table (exit 1 on a mismatch)
"""
import argparse
import csv
import glob
import hashlib
import json
import os
import random
import re
import sys
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import market_calendar  # noqa: E402
sys.path.insert(0, HERE)
import review_kit as RK  # noqa: E402  (v1.3: split, the one as-cash rule)

HOME = os.path.expanduser("~")
TRADES = os.path.join(HOME, "reviews", "trades")
PREREG = os.path.join(HOME, "reviews", "cash_candidates_20261121", "PREREG.md")
PREREG_SHA = "0bfddb1933bfaa94987f9d509c5944799866c8f4db85b21a90c81a94c09a086e"
AMENDMENTS = os.path.join(os.path.dirname(PREREG), "AMENDMENTS.txt")   # v1.1: amendment 1; v1.2: amendment 2
CONCENTRATION = ("concentration context, never a qualifier: gross without the two largest winners beside gross "
                 "without the two largest losers (amendment 1)")
INDEX = ("QQQ", "SPX")
PARK, RUNAWAY = "PARK", "RunawayContinuation"
HOLDERS = ("LiquidityHunt", "OGAP")          # the paper setups whose open position can sit beside a book's fire
IN_SAMPLE = ("2026-10-26", "2026-11-20")
FORWARD = ("2026-11-23", "2026-12-03")
BOOT_N, BOOT_SEED = 5000, 1
# v1.4 (RECAP.3): the per-entry sizes the boxes trade (paper is sized as cash): (symbol, dollars, since, was). Printed
# as the scoreboard's "Entry sizes" line so the commentary may quote them; nothing is re-scaled by them.
# v1.5: (symbol, base dollars, dated windows (from, to inclusive, dollars)).
SIZES = (("QQQ", 1050, ()), ("SPX", 5000, (("2026-11-23", "2026-11-23", 4200),)))


def size_on(sym, day):
    """v1.5 -> the per-entry size of `sym` on `day` (ISO date), or None for a symbol not in SIZES."""
    for a, base, dated in SIZES:
        if a == sym:
            for lo, hi, usd in dated:
                if lo <= day <= hi:
                    return usd
            return base
    return None
BOOKS = (
    ("C1", "QQQ and SPX only: Runaway and PARK"),
    ("C2", "All 14 symbols: PARK and Runaway"),
    ("C3", "All 14: PARK on the indexes (QQQ, SPX), Runaway on the 12 equities"),
    ("C4", "All 14: PARK and Runaway on the indexes, Runaway only on the equities"),
)


def in_book(book, sym, strat):
    """PREREG's four definitions, word for word; nothing else decides membership."""
    idx = sym in INDEX
    if book == "C1":
        return idx and strat in (PARK, RUNAWAY)
    if book == "C2":
        return strat in (PARK, RUNAWAY)
    if book == "C3":
        return (idx and strat == PARK) or (not idx and strat == RUNAWAY)
    if book == "C4":
        return (idx and strat in (PARK, RUNAWAY)) or (not idx and strat == RUNAWAY)
    raise ValueError(book)


def _t(s):
    try:
        return datetime.fromisoformat(s) if s else None
    except ValueError:
        return None


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def load(trades_dir=TRADES):
    """-> (rows, days with a trade file). A row: day, sym, strat, pnl (the mark), fee, entry, exit."""
    rows, days = [], []
    for p in sorted(glob.glob(os.path.join(trades_dir, "20??-??-??.csv"))):
        d = os.path.basename(p)[:10]
        days.append(d)
        with open(p, encoding="utf-8", newline="") as fh:
            raw = list(csv.DictReader(fh))
        for r, bk in zip(raw, RK.split(raw, modes=RK.modes_for_file(p))):            # v1.3 (CAP.11): the row's book, per the file's day
            rows.append({"day": d, "sym": r.get("sym", ""), "strat": r.get("strategy", ""),
                         "pnl": _f(r.get("pnl_usd")), "fee": _f(r.get("fee")),
                         "entry": _t(r.get("entry_time")), "exit": _t(r.get("exit_time")), "book": bk})
    return rows, days


def sessions(lo, hi, file_days):
    """The trading days in [lo, hi] (dtp market_calendar), and those of them with no trade file yet. v1.2 (amendment
    2): a 13:00 half day is a non-trading day, never a session."""
    out, x, end = [], date.fromisoformat(lo), date.fromisoformat(hi)
    while x <= end:
        if market_calendar.is_trading_day(x) and not market_calendar.is_half_day(x):
            out.append(x.isoformat())
        x += timedelta(days=1)
    have = set(file_days)
    return [d for d in out if d in have], [d for d in out if d not in have]


def boot(rows, n=BOOT_N, seed=BOOT_SEED):
    """Day-bootstrap 95% interval of EV a trade: the book's trade days resampled whole (review_kit.boot's method)."""
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


def displaced(book_rows, all_rows):
    """-> (count, unmeasurable): book trades fired while a Hunt or OGAP position was open on the same box."""
    hold = [o for o in all_rows if o["strat"] in HOLDERS]
    k = bad = 0
    for b in book_rows:
        if b["entry"] is None:
            bad += 1
            continue
        for o in hold:
            if o["sym"] != b["sym"] or o["day"] != b["day"]:
                continue
            if o["entry"] is None or o["exit"] is None:
                bad += 1
                break
            if o["entry"] <= b["entry"] < o["exit"]:
                k += 1
                break
    return k, bad


def metrics(rows, sess):
    n = len(rows)
    gross = sum(x["pnl"] for x in rows)
    fees = sum(x["fee"] for x in rows)
    daily = {d: 0.0 for d in sess}
    for x in rows:
        daily[x["day"]] = daily.get(x["day"], 0.0) + x["pnl"]
    eq = peak = dd = 0.0
    for d in sorted(daily):
        eq += daily[d]
        peak = max(peak, eq)
        dd = min(dd, eq - peak)
    lo, hi = boot(rows)
    top2 = sorted((x["pnl"] for x in rows), reverse=True)[:2]
    bottom2 = sorted(p for p in (x["pnl"] for x in rows) if p < 0)[:2]      # v1.1: the two largest losers
    return {"n": n, "gross": round(gross, 2), "fees": round(fees, 2), "net": round(gross - fees, 2),
            "ev": round(gross / n, 2) if n else None, "ci": [round(lo, 2), round(hi, 2)] if lo is not None else None,
            "up": sum(1 for v in daily.values() if v > 0), "sessions": len(daily),
            "worst_day": round(min(daily.values()), 2) if daily else None, "max_dd": round(dd, 2),
            "gross_ex_top2": round(gross - sum(top2), 2), "gross_ex_bottom2": round(gross - sum(bottom2), 2),
            "rtd": rtd(gross - fees, dd)}


def rtd(net, max_dd):
    """v1.2 (amendment 2): return to drawdown, net / |max drawdown|, to 0.01; None when the window never drew down."""
    return round(net / abs(max_dd), 2) if max_dd and max_dd < 0 else None


def ranking(sc):
    """v1.2 (amendment 2): the books in the order of the COMBINED window's rtd, highest first. No drawdown ranks first;
    PREREG's order breaks ties. -> [book]."""
    comb = (sc.get("windows", {}).get("combined") or {}).get("books") or {}
    order = [b for b, _d in BOOKS]

    def key(b):
        r = (comb.get(b) or {}).get("rtd")
        return (0 if r is None and (comb.get(b) or {}).get("n") else 1, -(r if r is not None else 0), order.index(b))
    return sorted(order, key=key)


def score(through, day=None, week_start=None, trades_dir=TRADES):
    """-> dict: per window, per book, the PREREG metrics (+ the forward displaced-fire count)."""
    rows, file_days = load(trades_dir)
    wins = [("in_sample", IN_SAMPLE[0], min(IN_SAMPLE[1], through))]
    if through >= FORWARD[0]:
        wins.append(("forward", FORWARD[0], min(FORWARD[1], through)))
        if through > FORWARD[1]:
            wins.append(("forward_cumulative", FORWARD[0], through))
    wins.append(("combined", IN_SAMPLE[0], through))
    if week_start:
        wins.append(("week", week_start, through))
    if day:
        wins.append(("day", day, day))
    out = {"through": through, "prereg": PREREG, "prereg_sha": PREREG_SHA, "basis": "the mark (pnl_usd); fees beside",
           "amendment": amendment_line(), "amendments": amendment_lines(), "concentration": CONCENTRATION,
           "books": dict(BOOKS), "windows": {},
           "sizes": [{"sym": a, "usd": size_on(a, through), "base": u,
                      "dated": [{"from": lo, "to": hi, "usd": x} for lo, hi, x in dated]} for a, u, dated in SIZES]}
    for name, lo, hi in wins:
        sess, missing = sessions(lo, hi, file_days)
        w = {"from": lo, "to": hi, "sessions": len(sess), "missing_trade_files": missing, "books": {}}
        extras = {}
        for b, _desc in BOOKS:
            inb = [x for x in rows if lo <= x["day"] <= hi and x["day"] in sess and in_book(b, x["sym"], x["strat"])]
            br = [x for x in inb if x.get("book", RK.HEADLINE) == RK.HEADLINE]      # v1.3: as cash would have traded
            xa = [x for x in inb if x.get("book") == RK.AFTER_CAP]
            if xa:
                extras[b] = {"n": len(xa), "gross": round(sum(x["pnl"] for x in xa), 2),
                                  "fees": round(sum(x["fee"] for x in xa), 2)}
            m = metrics(br, sess)
            if name.startswith("forward") or name in ("week", "day"):
                k, bad = displaced(br, [x for x in rows if lo <= x["day"] <= hi])
                m["displaced"] = k
                m["displaced_unmeasurable"] = bad
            w["books"][b] = m
        if extras:                                   # v1.3: the key exists only when a window has an extra
            w["extras"] = extras
        out["windows"][name] = w
    out["ranking"] = ranking(out)
    return out


def amendment_line(path=AMENDMENTS):
    """v1.1: the first line of PREREG's AMENDMENTS.txt (amendment 1), or None when there is none."""
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.readline().strip() or None
    except OSError:
        return None


def amendment_lines(path=AMENDMENTS):
    """v1.2: the first line of every amendment in AMENDMENTS.txt (a line holding "AMENDMENT <n> ("), oldest first."""
    try:
        with open(path, encoding="utf-8") as fh:
            return [ln.strip() for ln in fh if re.search(r"\bAMENDMENT \d+ \(", ln)]
    except OSError:
        return []


def prereg_sha(path=PREREG):
    try:
        return hashlib.sha256(open(path, "rb").read()).hexdigest()
    except OSError:
        return None


def _num(s):
    s = s.replace("−", "-").replace(",", "").strip()
    return float(s)


def prereg_table(path=PREREG):
    """PREREG's in-sample baseline table -> {book: {n, gross, fees, net, ev, ci, up, worst_day, max_dd, ex_top2}}."""
    txt = open(path, encoding="utf-8").read()
    part = txt.split("## In-sample baseline", 1)[1]
    out = {}
    for ln in part.splitlines():
        m = re.match(r"^\| (C\d) \| (.*)\|\s*$", ln)
        if not m:
            continue
        c = [x.strip() for x in m.group(2).split("|")]
        ev = re.match(r"([−\-\d.,]+) \[([−\-\d.,]+), ([−\-\d.,]+)\]", c[4])
        up = c[5].split("/")
        out[m.group(1)] = {"n": int(c[0]), "gross": _num(c[1]), "fees": _num(c[2]), "net": _num(c[3]),
                           "ev": _num(ev.group(1)), "ci": [_num(ev.group(2)), _num(ev.group(3))],
                           "up": int(up[0]), "sessions": int(up[1]), "worst_day": _num(c[6]), "max_dd": _num(c[7]),
                           "gross_ex_top2": _num(c[8])}
    return out


def check_prereg(sc, path=PREREG):
    """-> [mismatch] between the scorer's in-sample block and PREREG's table (dollars to the dollar, EV to 0.1)."""
    want = prereg_table(path)
    got = sc["windows"]["in_sample"]["books"]
    bad = []
    for b, w in want.items():
        g = got.get(b) or {}
        pairs = [("n", g.get("n"), w["n"], 0), ("up", g.get("up"), w["up"], 0),
                 ("sessions", g.get("sessions"), w["sessions"], 0), ("ev", g.get("ev"), w["ev"], 0.05)]
        for k in ("gross", "fees", "net", "worst_day", "max_dd", "gross_ex_top2"):
            pairs.append((k, round(g.get(k) or 0), w[k], 0))
        ci = g.get("ci") or [None, None]
        pairs += [("ci_lo", round(ci[0]) if ci[0] is not None else None, w["ci"][0], 0),
                  ("ci_hi", round(ci[1]) if ci[1] is not None else None, w["ci"][1], 0)]
        for k, a, e, tol in pairs:
            if a is None or abs(a - e) > tol:
                bad.append("%s %s: scorer %s, PREREG %s" % (b, k, a, e))
    return bad


def _m(x, dec=0):
    if x is None:
        return "-"
    s = "{:,.%df}" % dec
    return ("−" if x < 0 else "") + "$" + s.format(abs(x))


def render_md(sc):
    """The scoreboard as markdown: one table per window, the mark as the basis, fees beside."""
    lab = {"in_sample": "In-sample (seen, hindsight)", "forward": "Forward (unseen; 7 sessions, amendment 2)",
           "forward_cumulative": "Forward, cumulative past 12-03", "combined": "Combined", "week": "The week",
           "day": "The day"}
    L = ["# Cash candidate books C1-C4, through %s" % sc["through"], "",
         "Frozen in %s (sha256 %s). Basis: the mark (pnl_usd); fees beside, never inside EV. Report only: never in the "
         "window EV or the theories; the choice of book is the operator's." % (sc["prereg"], sc["prereg_sha"][:12]), ""]
    if size_line(sc):                                        # v1.4 (RECAP.3)
        L += [size_line(sc), ""]
    for a in sc.get("amendments") or ([sc["amendment"]] if sc.get("amendment") else []):
        L += ["Amendment: " + a, ""]
    comb = (sc["windows"].get("combined") or {}).get("books") or {}
    fwd = (sc["windows"].get("forward") or {}).get("books") or {}

    def _r(m):
        if not m:
            return "-"
        return "no drawdown" if m.get("rtd") is None else "%.2f" % m["rtd"]
    rank = sc.get("ranking") or [b for b, _d in BOOKS]
    L += ["**Ranking, return to drawdown (net / |max DD|, amendment 2; higher is better), combined window:** "
          + " > ".join("%s %s%s" % (b, _r(comb.get(b)), (" (forward %s)" % _r(fwd.get(b))) if fwd else "")
                       for b in rank), ""]
    L += ["Ex top-2 / ex bottom-2: " + CONCENTRATION + ".", ""]
    for b, d in BOOKS:
        L.append("- %s: %s" % (b, d))
    for name in ("day", "week", "forward", "forward_cumulative", "in_sample", "combined"):
        w = sc["windows"].get(name)
        if not w:
            continue
        L += ["", "## %s, %s..%s (%d session(s)%s)" % (lab[name], w["from"], w["to"], w["sessions"],
                                                      "; NO trade file yet for " + ", ".join(w["missing_trade_files"])
                                                      if w["missing_trade_files"] else ""), ""]
        disp = name.startswith("forward") or name in ("week", "day")
        L.append("| book | n | gross | fees | net | EV [95%] | up | worst day | max DD | net / max DD | "
                 "gross ex top-2 winners / ex bottom-2 losers (context) |"
                 + (" fired beside a Hunt/OGAP position |" if disp else ""))
        L.append("|---|---|---|---|---|---|---|---|---|---|---|" + ("---|" if disp else ""))
        for b in rank:
            m = w["books"][b]
            ev = "-" if m["ev"] is None else "%s [%s, %s]" % (_m(m["ev"], 1), _m(m["ci"][0]) if m["ci"] else "-",
                                                              _m(m["ci"][1]) if m["ci"] else "-")
            row = "| %s | %d | %s | %s | %s | %s | %d/%d | %s | %s | %s | %s / %s |" % (
                b, m["n"], _m(m["gross"]), _m(m["fees"]), _m(m["net"]), ev, m["up"], m["sessions"],
                _m(m["worst_day"]), _m(m["max_dd"]), _r(m), _m(m["gross_ex_top2"]), _m(m["gross_ex_bottom2"]))
            if disp:
                row += " %d%s |" % (m["displaced"], " (+%d unmeasurable)" % m["displaced_unmeasurable"]
                                    if m["displaced_unmeasurable"] else "")
            L.append(row)
        if w.get("extras"):                         # v1.3 (CAP.11): only a window that has any
            L += ["", "Extra paper after the breaker (paper boxes trade on past the would-be cap; not in the book "
                      "figures above, which are as cash would have traded): " + "; ".join(
                          "%s n=%d gross %s" % (b, w["extras"][b]["n"], _m(w["extras"][b]["gross"]))
                          for b in rank if b in w["extras"]) + "."]
    L += ["", "Displaced fires: the count is the book's trades that fired while a Hunt or OGAP position was open on "
              "the same box. A fire that a Hunt or OGAP position kept from becoming a trade is not in the trade files: "
              "NOT MEASURED.", ""]
    return "\n".join(L) + "\n"


def figures(sc):
    """Every dollar figure the scoreboard prints, rounded to the dollar (the commentary may quote only these)."""
    out = set()
    for w in sc["windows"].values():
        for m in w["books"].values():
            for k in ("gross", "fees", "net", "ev", "worst_day", "max_dd", "gross_ex_top2", "gross_ex_bottom2"):
                if m.get(k) is not None:
                    out.add(round(abs(m[k])))
            for v in m.get("ci") or []:
                out.add(round(abs(v)))
        for x in (w.get("extras") or {}).values():          # v1.3: the extras line's figures
            out.add(round(abs(x["gross"])))
    for z in sc.get("sizes") or []:                          # v1.4: the Entry sizes line (v1.5: base + dated)
        for x in [z.get("usd"), z.get("base"), z.get("was")] + [d.get("usd") for d in z.get("dated") or []]:
            if x is not None:
                out.add(round(abs(x)))
    return out


def size_line(sc):
    """v1.4: the scoreboard's one "Entry sizes" line, or None for a scoreboard without sizes."""
    zs = sc.get("sizes") or []
    if not zs:
        return None
    def one(z):
        ds = z.get("dated") or []
        if not ds:
            return "%s %s" % (z["sym"], _m(z["usd"]))
        win = ", ".join("%s on %s only" % (_m(d["usd"]), d["from"]) if d["from"] == d["to"]
                        else "%s %s..%s" % (_m(d["usd"]), d["from"], d["to"]) for d in ds)
        if z["usd"] != z.get("base"):
            return "%s %s, %s every other day" % (z["sym"], win, _m(z["base"]))
        return "%s %s (%s)" % (z["sym"], _m(z["usd"]), win)
    return ("Entry sizes (per entry, as the boxes trade them; paper is sized as cash): " + "; ".join(one(z) for z in zs)
            + "; per contract unchanged.")


def main(argv=None):
    ap = argparse.ArgumentParser(description="the cash candidate books C1-C4, scored as PREREG fixed them")
    ap.add_argument("--through", default=None, help="the last session scored (default: the newest trade file)")
    ap.add_argument("--day", default=None)
    ap.add_argument("--week-start", default=None)
    ap.add_argument("--trades", default=TRADES)
    ap.add_argument("--json", default=None)
    ap.add_argument("--md", default=None)
    ap.add_argument("--check-prereg", action="store_true")
    ap.add_argument("--prereg", default=PREREG)
    a = ap.parse_args(argv)
    if a.check_prereg:
        sha = prereg_sha(a.prereg)
        sc = score(IN_SAMPLE[1], trades_dir=a.trades)
        bad = check_prereg(sc, a.prereg)
        if sha != PREREG_SHA:
            bad.insert(0, "PREREG sha256 %s is not the sealed %s" % (sha, PREREG_SHA))
        for b in bad:
            print("MISMATCH " + b)
        print("AMENDMENT %s" % (amendment_line() or "none"))
        print("PREREG %s" % ("REPRODUCED (4 books, in-sample)" if not bad else "NOT REPRODUCED"))
        return 1 if bad else 0
    through = a.through
    if not through:
        _r, days = load(a.trades)
        through = days[-1] if days else IN_SAMPLE[1]
    sc = score(through, day=a.day, week_start=a.week_start, trades_dir=a.trades)
    md = render_md(sc)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(sc, fh, indent=1)
    if a.md:
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write(md)
    if not a.json and not a.md:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
