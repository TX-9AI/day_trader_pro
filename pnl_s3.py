#!/usr/bin/env python3
"""
day_trader_pro/pnl_s3.py  v1.1
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
    tot = {"closed": 0, "open": 0, "net": 0.0, "wins": 0, "losses": 0}

    for d in dates:
        objs = wr.read_prefix(s3, "trades", d)
        # ⚠️ DEDUPE FIRST, ALWAYS. See the header.
        trades = wr.latest_per_trade(objs)
        day = {"closed": 0, "open": 0, "net": 0.0, "wins": 0, "losses": 0}
        for t in trades:
            sym = t.get("symbol") or t.get("_sym") or "?"
            st = (t.get("status") or "").lower()
            s = per_sym.setdefault(sym, {"closed": 0, "open": 0, "net": 0.0})
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
        per_day[d] = day
        for k in ("closed", "open", "net", "wins", "losses"):
            tot[k] += day[k]
    return per_day, per_sym, tot


def render(dates, per_day, per_sym, tot) -> str:
    span = dates[0] if len(dates) == 1 else f"{dates[0]} → {dates[-1]}"
    L = [f"*VERTIGO — P&L from the warehouse*  ({span})", ""]

    if len(dates) > 1:
        L.append("*By day*")
        for d in dates:
            x = per_day[d]
            if not x["closed"] and not x["open"]:
                # ⚠️ SAID, NOT SKIPPED. A silent gap in a range is how a
                # missing session hides.
                L.append(f"`{d}`  —  no trades in the warehouse")
                continue
            L.append(f"`{d}`  {_money(x['net']):>11}  "
                     f"({x['closed']}t, {x['wins']}W/{x['losses']}L)")
        L.append("")

    if per_sym:
        L.append("*By symbol*")
        for sym in sorted(per_sym, key=lambda s: per_sym[s]["net"], reverse=True):
            x = per_sym[sym]
            if not x["closed"]:
                continue
            L.append(f"`{sym:<5}` {_money(x['net']):>11}  ({x['closed']}t)")
        L.append("")

    wr_pct = (100.0 * tot["wins"] / tot["closed"]) if tot["closed"] else 0.0
    L.append("──────────────")
    L.append(f"*Net: {_money(tot['net'])}*   {tot['closed']} closed  "
             f"({tot['wins']}W/{tot['losses']}L, {wr_pct:.0f}%)")
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
