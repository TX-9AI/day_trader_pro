#!/usr/bin/env python3
"""
day_trader_pro/tests/check_refusals.py — v1.0
v1.0  2026-11-23  dtp r581 / REFUSE.1 (review_kit v1.8 `refusals`, the nightly review prompt v1.11). The 11-23 review read
      the refused fires as possible fill failures: each refused Runaway fire became a plan ending "superseded — never
      filled" and the last of each chain stayed TRIGGERED with no trade_ids (QQQ cfe099c9 09:53:48, SPX e1fe67d1
      09:41:48), while the refusal reasons sat in S3 signal_journal dispositions. Hermetic: fixtures only, no S3.

  F1  fired_unfilled keeps exactly the plans that fired and booked no trade: TRIGGERED, "superseded — never filled",
      WIPED_BY_RESTART, each with no trade_ids; a CLOSED plan with a trade and a TRIGGERED plan WITH a trade are out
  F2  refusal_rows joins each to its own tick's disposition (same box, setup and side, within JOIN_S): the QQQ
      cfe099c9 09:53:48 TRIGGERED plan reads gate_block:commit_abandoned, the SPX superseded plan reads
      sizing_rejected insufficient_capital: need $4340.00/contract, risk=$4200.00; a disposition of another setup,
      another side or 5 s away does not join
  F3  "no fill" ONLY where the tick has no disposition (the Hunt fixture); never on a joined row
  F4  OTV4TEST rows and a plan fired on another ET day are left out
  F5  cmd_refusals writes ~/reviews/refusals/DAY.csv (REFUSAL_COLS) under DTP_REVIEWS_DIR and prints one line per box,
      setup and side with each reason kind and its count and the last plan's state
  F6  the nightly review prompt runs `refusals DAY` as step 5 and says: quote its reason, "no fill" only where it
      prints "no fill", a refusal is not a fill failure; the prompt is v1.11
BORN RED on 5621ada (r580): review_kit has no `refusals`.

Run:  python3 tests/check_refusals.py
"""
import csv
import importlib
import io
import os
import re
import shutil
import sys
import tempfile
from contextlib import redirect_stdout
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)
ET = ZoneInfo("America/New_York")
FAILS, RAN = [], []


def ck(n, ok, msg=""):
    RAN.append(n)
    print(f"  {n:<3} {'PASS' if ok else 'FAIL'}  {msg}")
    if not ok:
        FAILS.append(n)


def ep(hms, day="2026-11-23"):
    return datetime.fromisoformat("%sT%s" % (day, hms)).replace(tzinfo=ET).timestamp() + 0.19


def plan(pid, sym, strat, dr, hms, state, term=None, tids=None, day="2026-11-23"):
    return {"plan_id": pid, "symbol": sym, "strategy": strat, "direction": dr, "created_ts": ep(hms, day),
            "state": state, "terminal_reason": term, "trade_ids": tids}


def disp(box, strat, dr, hms, outcome):
    return {"box": box, "ts_et": "2026-11-23T%s-05:00" % hms, "event": "disposition", "outcome": outcome,
            "signal": {"strategy": strat, "direction": dr}}


SUP = "superseded — never filled"
PLANS = [
    plan("cfe099c9a0994546", "QQQ", "RunawayContinuation", "short", "09:53:48", "TRIGGERED", None, None),
    plan("11c422bb00000000", "QQQ", "RunawayContinuation", "short", "09:53:33", "EXPIRED", SUP, "[]"),
    plan("f2369b9000000000", "SPX", "RunawayContinuation", "short", "09:40:33", "EXPIRED", SUP, None),
    plan("e1fe67d1f9b242d3", "SPX", "RunawayContinuation", "short", "09:41:48", "CANCELLED", "WIPED_BY_RESTART", "[]"),
    plan("f56c267400000000", "NVDA", "LiquidityHunt", "long", "10:29:48", "TRIGGERED", None, None),
    plan("aaaa000000000001", "TSLA", "RunawayContinuation", "long", "10:28:33", "TRIGGERED", None, None),
    plan("bbbb000000000002", "AMD", "RunawayContinuation", "long", "10:00:04", "CLOSED", "orb_trail_stop",
         '["t-1"]'),
    plan("cccc000000000003", "META", "RunawayContinuation", "short", "09:40:04", "TRIGGERED", None, '["t-2"]'),
    plan("dddd000000000004", "AAL", "RunawayContinuation", "long", "09:45:04", "TRIGGERED", None, None),
    plan("eeee000000000005", "QQQ", "RunawayContinuation", "long", "09:45:04", "TRIGGERED", None, None,
         day="2026-11-20"),
]
DISP = [
    disp("QQQ", "RunawayContinuation", "short", "09:53:48", "gate_block:commit_abandoned"),
    disp("QQQ", "RunawayContinuation", "short", "09:53:33", "gate_block:commit_abandoned"),
    disp("SPX", "RunawayContinuation", "short", "09:40:33",
         "sizing_rejected insufficient_capital: need $4340.00/contract, risk=$4200.00"),
    disp("SPX", "RunawayContinuation", "short", "09:41:48", "gate_block:commit_abandoned"),
    disp("NVDA", "RunawayContinuation", "long", "10:29:48", "pin_proximity 0.075 EM"),    # another setup: no join
    disp("TSLA", "RunawayContinuation", "short", "10:28:33", "gate_block:x"),              # another side: no join
    disp("TSLA", "RunawayContinuation", "long", "10:28:38", "gate_block:y"),               # 5 s away: no join
    disp("AAL", "RunawayContinuation", "long", "09:45:04", "gate_block:commit_abandoned"),
]


def main():
    try:
        RK = importlib.import_module("review_kit")
    except Exception as e:                                       # noqa: BLE001
        print("review_kit import failed: %s" % e)
        return 1
    have = all(hasattr(RK, n) for n in ("fired_unfilled", "refusal_rows", "refusal_lines", "cmd_refusals"))
    fu = {p["plan_id"][:8] for p in RK.fired_unfilled(PLANS)} if have else set()
    ck("F1", fu == {"cfe099c9", "11c422bb", "f2369b90", "e1fe67d1", "f56c2674", "aaaa0000", "dddd0000", "eeee0000"},
       "fired-unfilled %s" % sorted(fu))
    rows = RK.refusal_rows("2026-11-23", PLANS, DISP) if have else []
    by = {r["plan_id"][:8]: r for r in rows}
    ck("F2", have and by.get("cfe099c9", {}).get("reason") == "gate_block:commit_abandoned"
       and by["cfe099c9"]["fired_et"] == "09:53:48" and by["cfe099c9"]["state"] == "TRIGGERED"
       and by.get("f2369b90", {}).get("reason")
       == "sizing_rejected insufficient_capital: need $4340.00/contract, risk=$4200.00"
       and by.get("e1fe67d1", {}).get("reason") == "gate_block:commit_abandoned"
       and by.get("f56c2674", {}).get("reason") == "no fill" and by.get("aaaa0000", {}).get("reason") == "no fill",
       "%s" % {k: v["reason"] for k, v in by.items()})
    nf = sorted(k for k, v in by.items() if v["reason"] == "no fill")
    ck("F3", have and nf == ["aaaa0000", "f56c2674"] and all(v["outcome"] for k, v in by.items() if k not in nf),
       "no fill on %s" % nf)
    ck("F4", have and "dddd0000" not in by and "eeee0000" not in by and len(rows) == 6, "rows %s" % sorted(by))
    out, txt, hdr, n5 = "", "", [], -1
    if have:
        tmp = tempfile.mkdtemp(prefix="check_refusals_")
        old = RK.REVIEWS
        RK.REVIEWS = tmp
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                RK.cmd_refusals("2026-11-23", source=lambda d: (PLANS, DISP))
            out = buf.getvalue()
            p = os.path.join(tmp, "refusals", "2026-11-23.csv")
            if os.path.exists(p):
                rd = list(csv.reader(open(p, encoding="utf-8")))
                hdr, n5 = rd[0], len(rd) - 1
        finally:
            RK.REVIEWS = old
            shutil.rmtree(tmp, ignore_errors=True)
    ck("F5", have and hdr == RK.REFUSAL_COLS and n5 == 6
       and "6 fire(s) that booked no trade, 4 with a refusal reason, 2 no fill (no disposition)" in out
       and "SPX RunawayContinuation short: 2 fire(s) 09:40:33-09:41:48, none traded; " in out
       and "sizing_rejected x1 (first: sizing_rejected insufficient_capital: need $4340.00/contract, risk=$4200.00)" in out
       and "last plan e1fe67d1 CANCELLED WIPED_BY_RESTART" in out
       and "QQQ RunawayContinuation short: 2 fire(s) 09:53:33-09:53:48, none traded; gate_block:commit_abandoned x2; "
           "last plan cfe099c9 TRIGGERED" in out
       and "NVDA LiquidityHunt long: 1 fire(s) 10:29:48-10:29:48, none traded; no fill x1" in out,
       "csv %s rows; out:\n%s" % (n5, out))
    pr = re.sub(r"\s+", " ", open(os.path.join(ROOT, "tools", "nightly_review.prompt"), encoding="utf-8").read())
    ck("F6", "nightly_review.prompt v1.11" in pr and "5. python $K refusals DAY" in pr
       and "A FIRE THAT DID NOT TRADE IS A REFUSAL, NOT A FILL FAILURE" in pr
       and 'write "no fill" ONLY where step 5 prints "no fill"' in pr
       and "refusals DAY" in open(os.path.join(ROOT, "tools", "review_kit.py"), encoding="utf-8").read().split('"""')[1],
       "the prompt's step 5 and rule")
    print()
    if FAILS:
        print(f"RED — {len(FAILS)} of {len(RAN)} check(s) failed: {' '.join(FAILS)}")
        return 1
    print(f"GREEN — {len(RAN)} checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
