#!/usr/bin/env python3
# day_trader_pro/tests/check_fit_trades.py — v1.1
# v1.1 (2026-11-08) — dtp r532 / OTV4DEP.1. T11: the report lists only strategy_registry's LIVE setups. A retired
#   strategy (TrendCreditSpread) and a management plan (CreditRoll) with rows in the window are not named; one line
#   counts them, names and rows, so nothing vanishes silently. The operator, 2026-10-31: "don't list the retired
#   strategies either."
# v1.0 (2026-11-08) — dtp r531 / FIT.3 (Saturday brief 11-07 D7). READY FLOORS CLOSED TRADES, NEVER SIGNAL ROWS.
#   fit_readiness v1.8 floored `fired`, the count of strategy_note rows whose evaluation fired (one per tick while a
#   plan stays armed), so 11-02..11-06 printed LiquidityHunt READY on 4,383 "fired" against 32 closed trades and
#   RunawayContinuation on 8,114 against 39. v1.9 counts closed trades per strategy, drops OTV4TEST rows, and fails
#   closed when the trade source cannot be read.
#
# ⚠️ A PLAIN SCRIPT WITH AN EXIT CODE (dtp's venv has no pytest). No network: the warehouse path runs on a fake S3.
# Run:  venv/bin/python tests/check_fit_trades.py
"""Gate for fit_readiness v1.9: the READY floor reads closed trades."""
import json
import os
import sqlite3
import sys
import tempfile
from collections import Counter

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
FAILED = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        FAILED.append(name)


def _t(tid, strat, entry, status="closed", sym="QQQ", lineage="OTV5"):
    return {"trade_id": tid, "strategy": strat, "entry_time": entry, "status": status,
            "symbol": sym, "lineage": lineage}


def _distributed():
    # two entry rungs, neither above MAX_RUNG_SHARE, well above MIN_DECLINED
    return Counter({"entry_window": 60, "adx_floor": 50})


class _B:
    def __init__(s, b): s.b = b
    def read(s): return s.b


class _P:
    def __init__(s, st): s.st = st
    def paginate(s, Bucket=None, Prefix=None):
        yield {"Contents": [{"Key": k, "Size": len(v)} for k, v in s.st.items() if k.startswith(Prefix)]}


class _S3:
    def __init__(s, st): s.st = st
    def get_paginator(s, _): return _P(s.st)
    def get_object(s, Bucket=None, Key=None): return {"Body": _B(s.st[Key])}


def main():
    import fit_readiness as F
    days = ["2026-11-02", "2026-11-03"]

    # ══ T1 — closed trades on an ET entry day inside the window ═══════════════════════════════════════════════
    rows = [
        _t(1, "LiquidityHunt", "2026-11-02T14:40:00+00:00"),
        _t(2, "LiquidityHunt", "2026-11-03T01:00:00+00:00"),     # 20:00 ET on 11-02: an 11-02 trade
        _t(3, "LiquidityHunt", "2026-11-04T01:30:00+00:00"),     # 20:30 ET on 11-03: inside
        _t(4, "LiquidityHunt", "2026-11-04T14:40:00+00:00"),     # 11-04: outside
        _t(5, "LiquidityHunt", "2026-11-02T15:00:00+00:00", status="open"),
        _t(6, "RunawayContinuation", "2026-11-02T14:45:00"),     # untagged stamp: the box's UTC
    ]
    c, dropped = F.trade_counts(rows, days)
    check("T1 closed trades counted by ET entry day (UTC 01:00 is the previous ET day)",
          c.get("LiquidityHunt") == 3, str(dict(c)))
    check("T1b an open trade is not an outcome", c.get("LiquidityHunt") == 3 and dropped == 0)
    check("T1c an untagged UTC stamp is read as UTC", c.get("RunawayContinuation") == 1, str(dict(c)))

    # ══ T2 — OTV4TEST rows never count toward an OTV5 setup ═══════════════════════════════════════════════════
    rows2 = [
        _t(10, "RunawayContinuation", "2026-10-20T14:40:00+00:00", sym="SOFI", lineage=""),   # pre-OTV5 SOFI
        _t(11, "RunawayContinuation", "2026-10-21T14:40:00+00:00", sym="AAL", lineage=""),
        _t(12, "RunawayContinuation", "2026-11-02T14:40:00+00:00", sym="SOFI", lineage=""),   # SOFI on OTV5
    ]
    c2, d2 = F.trade_counts(rows2, ["2026-10-20", "2026-10-21", "2026-11-02"])
    check("T2 OTV4TEST rows (SOFI before 10-25, AAL) are dropped and counted",
          c2.get("RunawayContinuation") == 1 and d2 == 2, f"{dict(c2)} dropped={d2}")

    # ══ T3 — thousands of fired signal rows on few trades -> NOT READY (v1.8 said READY on the 4,383) ═════════
    rec = {"fired": 4383, "declined": 9000, "rungs": _distributed(), "trades": 12}
    v, why = F.verdict(rec)
    check("T3 4,383 fired signal rows on 12 trades is NOT READY", v == "NOT READY", why[:80])
    check("T3b the sentence names closed trades, not fired rows", "12 closed trade(s)" in why, why[:80])
    # the floor sits on trades: one under it is NOT READY however many signal rows fired, at it is judged on rungs
    v3c, _ = F.verdict({**rec, "trades": F.MIN_TRADES - 1, "fired": 10 ** 6})
    v3d, _ = F.verdict({**rec, "trades": F.MIN_TRADES, "fired": 0})
    check("T3c the floor is MIN_TRADES closed trades, independent of fired rows",
          v3c == "NOT READY" and v3d == "READY", f"{v3c} / {v3d}")

    # ══ T4 — FAILS CLOSED: an unreadable trade source is never READY ══════════════════════════════════════════
    rec4 = {"fired": 90000, "declined": 9000, "rungs": _distributed(), "trades": None}
    v4, why4 = F.verdict(rec4)
    check("T4 no trade count -> NOT READY, reason named", v4 == "NOT READY" and "unreadable" in why4, why4[:80])

    # ══ T5 — enough trades and a populated surface -> READY, with the trade count in the sentence ═════════════
    rec5 = {"fired": 5000, "declined": 9000, "rungs": _distributed(), "trades": 40}
    v5, why5 = F.verdict(rec5)
    check("T5 40 trades + distributed rungs is READY", v5 == "READY", why5[:80])
    check("T5b READY states the trades and the signal rows apart",
          "40 closed trade(s)" in why5 and "5000 fired signal row(s)" in why5, why5[:80])

    # ══ T6 — nothing dropped from the report: trades, fired and declined all print ════════════════════════════
    txt = F.render({"LiquidityHunt": {**rec, "plans": Counter(), "vec_fired": {}, "vec_declined": {}}},
                   days)
    check("T6 the report prints the trades line", "trades       12" in txt, "")
    check("T6b fired still prints, labelled as signal rows", "fired      4383" in txt and "NOT trades" in txt)
    check("T6c declined still prints", "declined   9000" in txt)

    # ══ T11 — v1.10: only LIVE setups are listed; the rest are counted, never named ══════════════════════════
    _blank = {"plans": Counter(), "vec_fired": {}, "vec_declined": {}}
    txt11 = F.render({"LiquidityHunt": {**rec, **_blank},
                      "TrendCreditSpread": {**rec, **_blank, "fired": 7, "declined": 3},
                      "CreditRoll": {**rec, **_blank, "fired": 0, "declined": 5}}, days)
    check("T11 a retired strategy and a management plan are not listed",
          "TrendCreditSpread" not in txt11 and "CreditRoll" not in txt11, "")
    check("T11b the live setup still is", "  LiquidityHunt" in txt11, "")
    check("T11c the hidden names are COUNTED, with their rows",
          "Not listed: 2 retired or non-strategy name(s) with 15 row(s)" in txt11,
          txt11.split("Not listed:")[1][:70] if "Not listed:" in txt11 else "no count line")

    # ══ T7 — collect(): a read source gives 0 to a setup that never traded; an unread one leaves None ═════════
    src = {"strategy_note": [{"strategy": "Breakout", "fired": 1, "payload": "{}", "outcome": None}],
           "gate_disposition": [], "plan_ledger": []}
    out = F.collect(src, days, {"LiquidityHunt": 7})
    check("T7 a strategy seen only in the derived rows gets 0 trades, not None",
          out["Breakout"]["trades"] == 0 and out["LiquidityHunt"]["trades"] == 7,
          f"{out['Breakout']['trades']} / {out['LiquidityHunt']['trades']}")
    out2 = F.collect(src, days, None)
    check("T7b an unread trade source leaves None (verdict fails closed)", out2["Breakout"]["trades"] is None)

    # ══ T8 — --db reads the trades.db beside the derived store, and names a missing one ═══════════════════════
    with tempfile.TemporaryDirectory() as td:
        ddb = os.path.join(td, "derived_store.db")
        open(ddb, "w").close()
        r_none, note = F._trades_sqlite(ddb)
        check("T8 no trades.db beside --db -> None, named", r_none is None and "NO trades.db" in note, note[:70])
        tc = sqlite3.connect(os.path.join(td, "trades.db"))
        tc.execute("CREATE TABLE trades (trade_id, strategy, entry_time, status, symbol, lineage)")
        tc.execute("INSERT INTO trades VALUES (1,'PARK','2026-11-02T16:01:00+00:00','closed','QQQ','OTV5')")
        tc.commit()
        tc.close()
        r8, note8 = F._trades_sqlite(ddb)
        check("T8b the box's trades.db is read", r8 is not None and len(r8) == 1, note8[:70])

    # ══ T9 — warehouse path: one count per trade_id, next-day partition read, OTV4TEST dropped ════════════════
    def env(rec, stamp):
        return json.dumps({"pushed_at_utc": stamp, "record": rec}).encode()
    st = {
        # an open state, then the closed state of the same trade, pushed later
        "raw/trades/dt=2026-11-02/sym=QQQ/1.json": env(_t(20, "PARK", "2026-11-02T16:01:00+00:00", status="open"),
                                                       "2026-11-02T16:02:00Z"),
        "raw/trades/dt=2026-11-02/sym=QQQ/2.json": env(_t(20, "PARK", "2026-11-02T16:01:00+00:00"),
                                                       "2026-11-02T20:46:00Z"),
        # the same closed state RE-PUSHED (a CDC re-send): still one trade
        "raw/trades/dt=2026-11-02/sym=QQQ/2b.json": env(_t(20, "PARK", "2026-11-02T16:01:00+00:00"),
                                                        "2026-11-02T20:51:00Z"),
        # a late close: pushed after midnight UTC, filed under the NEXT day's partition
        "raw/trades/dt=2026-11-04/sym=QQQ/3.json": env(_t(21, "PARK", "2026-11-03T16:01:00+00:00"),
                                                       "2026-11-04T00:30:00Z"),
        "raw/trades/dt=2026-11-02/sym=AAL/4.json": env(_t(22, "PARK", "2026-11-02T16:01:00+00:00", sym="AAL",
                                                          lineage=""), "2026-11-02T20:46:00Z"),
    }
    c9, note9 = F._trades_warehouse(days, s3=_S3(st))
    check("T9 three push states of one trade count once; the next-day partition is read",
          c9 is not None and c9.get("PARK") == 2, f"{dict(c9 or {})}  {note9[:60]}")
    check("T9b the warehouse note names the OTV4TEST drop", "1 OTV4TEST row(s) dropped" in note9, note9)

    class _Boom:
        def get_paginator(s, _): raise RuntimeError("no credentials")
    c10, note10 = F._trades_warehouse(days, s3=_Boom())
    check("T10 an unreachable bucket is None and says so", c10 is None and "UNREADABLE" in note10, note10[:70])

    print()
    if FAILED:
        print(f"RED — {len(FAILED)} failed: {', '.join(FAILED)}")
        return 1
    print("GREEN — check_fit_trades")
    return 0


if __name__ == "__main__":
    sys.exit(main())
