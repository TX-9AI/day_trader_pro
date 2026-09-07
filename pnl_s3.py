#!/usr/bin/env python3
"""
day_trader_pro/pnl_s3.py  v1.2
v1.2  2026-09-07 - dtp r312 / FEE.7 - GROSS, FEES, NET AFTER FEES, side by side.
      Operator: *"I want the fees next to the gross, then a column that shows
      the net after that, keep the number of trades and w/l that are already a
      part of this report."*
      ⚠️ THE `net` KEY IS STILL THE GROSS SUM and is deliberately not renamed.
      Every banked report, every prior screenshot and the Telegram history all
      carry that number under that word; redefining it in place would make the
      series discontinuous at exactly the revision that added the column. The
      new figure is `net_after` and it is labelled as such.
      🔴 FEES ARE ACCUMULATED PER TRADE, NOT RE-DERIVED FROM A TOTAL, so a row
      the model cannot price is counted as unpriced rather than as zero-fee -
      and `unpriced` prints whenever it is non-zero. A fee column that hides
      how many rows it could not price understates itself silently.
      ⚠️ TELEGRAM SAFE: the added lines carry no `<`, `>` or `&`. r290 cost a
      day to a single less-than character in an HTML-parse-mode message.
v1.1  2026-09-05 — dtp r287 / TZ.1 — the naive `today` here asked a UTC box and rolled at 20:00 ET (19:00 in winter), so a report run after that silently asked for
      TOMORROW and came back empty. It now goes through `ettime`, the one ET/UTC boundary.

P&L for a day or a range, read FROM THE WAREHOUSE. No boxes involved.

v1.0  2026-08-25  Operator: "I want the P&L to come from S3 and notify via
telegram. Also a devtools menu item to display and/or push the P&L report for
a day or range from the S3 store."

🔴 WHY THIS REPLACES `standings.py` FOR EVERYTHING BUT LIVE.
`standings.py` SSHes into every box and runs sqlite against the box's own
trades.db. That is correct for a LIVE intraday reading and useless for any
other question: **to see yesterday's P&L you had to wake fifteen boxes** —
paying EC2 time and several minutes of waking to answer a question about data
that was already sitting in S3.

⚠️ AND IT COULD ONLY EVER ANSWER "TODAY". The SQL is hardcoded to
`date('now','-4 hours')`, so there was no way to ask about a past session at
all without waking the fleet AND editing the query.

⚠️ THE WAREHOUSE IS THE AUTHORITY AFTER THE CLOSE. The boxes keep their local
stores and cannot delete them, so a box is still a recovery path — but it is
not the READ path. One source, queryable, boxes off.

⚠️ DEDUPE IS NOT OPTIONAL HERE. A trade row is pushed on every state change, so
S3 holds several objects for one trade_id. `latest_per_trade` keeps the newest
by pushed_at — without it a trade that opened, updated and closed would be
counted three times and the P&L would be silently inflated.

⚠️ OPEN TRADES ARE COUNTED BUT NEVER SUMMED. An open position has no realised
P&L; adding a mark-to-market number to a realised total produces one figure
that means two things. They are reported as a count, separately.

Run:  python3 pnl_s3.py                       # today
      python3 pnl_s3.py --date 2026-08-21
      python3 pnl_s3.py --from 2026-08-17 --to 2026-08-21
      python3 pnl_s3.py --date 2026-08-21 --send      # + Telegram
"""

from __future__ import annotations

import argparse
import sys
from datetime import date as _date, datetime, timedelta

import config                                                   # noqa: E402
import warehouse_reader as wr                                   # noqa: E402
import ettime                                            # noqa: E402
from fees_bridge import trade_fee, FEES_ERR                      # noqa: E402

try:
    import notify
except Exception:                                               # noqa: BLE001
    notify = None


def _money(v) -> str:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "—"
    return f"{'-' if v < 0 else '+'}${abs(v):,.2f}"


def _fee(x) -> str:
    """Fees as a NEGATIVE deduction, or n/a when no row could be priced."""
    if FEES_ERR or (x["unpriced"] and not x["fees"]):
        return "n/a"
    return _money(-x["fees"])


def _net_after(x) -> str:
    if FEES_ERR or (x["unpriced"] and not x["fees"]):
        return "n/a"
    return _money(x["net"] - x["fees"])


def _dates(a) -> list:
    """Resolve the requested window to a list of ISO dates.

    ⚠️ WEEKENDS AND HOLIDAYS ARE NOT FILTERED OUT. A date with no objects
    reports as a date with no objects — which is the honest answer and also
    how a MISSING session becomes visible instead of being silently skipped.
    """
    if a.date:
        return [a.date]
    if a.frm and a.to:
        d0 = datetime.strptime(a.frm, "%Y-%m-%d").date()
        d1 = datetime.strptime(a.to, "%Y-%m-%d").date()
        if d1 < d0:
            d0, d1 = d1, d0
        out, d = [], d0
        while d <= d1:
            out.append(d.isoformat())
            d += timedelta(days=1)
        return out
    return [ettime.today_et()]


def collect(dates: list) -> tuple:
    """Return (per_day, per_symbol, totals). Reads S3 only."""
    s3 = wr._client()
    per_day, per_sym = {}, {}
    tot = {"closed": 0, "open": 0, "net": 0.0, "wins": 0, "losses": 0,
           "fees": 0.0, "unpriced": 0}

    for d in dates:
        objs = wr.read_prefix(s3, "trades", d)
        # ⚠️ DEDUPE FIRST, ALWAYS. See the header.
        trades = wr.latest_per_trade(objs)
        day = {"closed": 0, "open": 0, "net": 0.0, "wins": 0, "losses": 0,
               "fees": 0.0, "unpriced": 0}
        for t in trades:
            sym = t.get("symbol") or t.get("_sym") or "?"
            st = (t.get("status") or "").lower()
            s = per_sym.setdefault(sym, {"closed": 0, "open": 0, "net": 0.0,
                                        "fees": 0.0, "unpriced": 0})
            if st == "open":
                day["open"] += 1
                s["open"] += 1
                continue
            if st != "closed":
                continue
            try:
                p = float(t.get("pnl_usd") or 0.0)
            except (TypeError, ValueError):
                p = 0.0
            day["closed"] += 1
            day["net"] += p
            day["wins" if p > 0 else "losses"] += 1
            s["closed"] += 1
            s["net"] += p
            # ⚠️ PER TRADE, and None is counted as UNPRICED rather than as a
            # zero fee. Summing a None into a running total is the exact
            # coercion the model refuses to make on the way out.
            _f = trade_fee(t)
            if _f is None:
                day["unpriced"] += 1
                s["unpriced"] += 1
            else:
                day["fees"] += _f
                s["fees"] += _f
        per_day[d] = day
        for k in ("closed", "open", "net", "wins", "losses",
                  "fees", "unpriced"):
            tot[k] += day[k]
    return per_day, per_sym, tot


def render(dates, per_day, per_sym, tot) -> str:
    span = dates[0] if len(dates) == 1 else f"{dates[0]} → {dates[-1]}"
    L = [f"*VERTIGO — P&L from the warehouse*  ({span})", ""]

    if len(dates) > 1:
        L.append("*By day*")
        # ⚠️ HEADER WIDTHS MIRROR THE ROW FORMAT EXACTLY. The first cut eyeballed
        # them and sat 4 characters left of the column it labelled.
        L.append(f"`{'':<10} {'GROSS':>11} {'FEES':>11} {'NET':>11}`")
        for d in dates:
            x = per_day[d]
            if not x["closed"] and not x["open"]:
                # ⚠️ SAID, NOT SKIPPED. A silent gap in a range is how a
                # missing session hides.
                L.append(f"`{d}`  —  no trades in the warehouse")
                continue
            L.append(f"`{d} {_money(x['net']):>11} {_fee(x):>11} "
                     f"{_net_after(x):>11}`  "
                     f"({x['closed']}t, {x['wins']}W/{x['losses']}L)")
        L.append("")

    if per_sym:
        L.append("*By symbol*")
        L.append(f"`{'':<5}{'GROSS':>11} {'FEES':>11} {'NET':>11}`")
        for sym in sorted(per_sym, key=lambda s: per_sym[s]["net"], reverse=True):
            x = per_sym[sym]
            if not x["closed"]:
                continue
            L.append(f"`{sym:<5}{_money(x['net']):>11} {_fee(x):>11} "
                     f"{_net_after(x):>11}`  ({x['closed']}t)")
        L.append("")

    wr_pct = (100.0 * tot["wins"] / tot["closed"]) if tot["closed"] else 0.0
    L.append("──────────────")
    L.append(f"*Gross: {_money(tot['net'])}*   {tot['closed']} closed  "
             f"({tot['wins']}W/{tot['losses']}L, {wr_pct:.0f}%)")
    L.append(f"*Fees:  {_fee(tot)}*   *Net after fees: {_net_after(tot)}*")
    if tot["unpriced"]:
        # ⚠️ ALWAYS SAID WHEN NON-ZERO. A fee total that hides its unpriced
        # count understates itself and looks precise doing it.
        L.append(f"_{tot['unpriced']} trade(s) the fee model could not "
                 f"price - excluded from Fees_")
    if FEES_ERR:
        L.append(f"_fee model unavailable: {FEES_ERR}_")
    if tot["open"]:
        # ⚠️ COUNTED, NEVER ADDED. Realised and unrealised are different units.
        L.append(f"_{tot['open']} still open — not included in Net_")
    if not tot["closed"] and not tot["open"]:
        L.append("_No trades found in the warehouse for this window._")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="single day YYYY-MM-DD")
    ap.add_argument("--from", dest="frm", help="range start YYYY-MM-DD")
    ap.add_argument("--to", dest="to", help="range end YYYY-MM-DD")
    ap.add_argument("--send", action="store_true", help="push to Telegram")
    a = ap.parse_args(argv[1:] if argv else None)

    dates = _dates(a)
    try:
        per_day, per_sym, tot = collect(dates)
    except Exception as exc:                                    # noqa: BLE001
        # ⚠️ A WAREHOUSE THAT CANNOT BE READ IS SAID PLAINLY, never rendered as
        # a zero. "$0.00 net" and "could not reach S3" must not look alike.
        msg = f"P&L unavailable — could not read the warehouse: {exc}"
        print(msg)
        if a.send and notify:
            try:
                notify.send(msg)
            except Exception:                                   # noqa: BLE001
                pass
        return 1

    text = render(dates, per_day, per_sym, tot)
    print(text.replace("*", "").replace("`", ""))
    if a.send:
        if notify is None:
            print("\n(notify unavailable — not sent)")
            return 1
        try:
            notify.send(text)
            print("\nsent to Telegram")
        except Exception as exc:                                # noqa: BLE001
            print(f"\ntelegram send failed: {exc}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
