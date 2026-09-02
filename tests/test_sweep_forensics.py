#!/usr/bin/env python3
# day_trader_pro/tests/test_sweep_forensics.py — v1.0
# v1.0 (2026-09-02) — dtp r252.
#
# 🔴 F2 IS THE CHECK THAT CARRIES THE WEIGHT. A CALL spread is breached UPWARD
#   and a PUT spread DOWNWARD, and the direction comes from the STRUCTURE —
#   `long_strike` above `short_strike` means a call spread. Read it backwards
#   and every penetration is measured on the wrong side of the level, so a
#   spread that was run over reads as never touched and the report says the
#   opposite of the truth in a confident voice.
#
# 🔑 F3: ACCEPTANCE IS THE LONGEST RUN OF CONSECUTIVE CLOSES, not a count.
#   Five scattered closes across an hour is noise; five consecutive is the
#   level failing. The fixture plants both shapes and requires them to differ.
import io, json, os, sys, contextlib
from datetime import datetime
from zoneinfo import ZoneInfo

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
ET = ZoneInfo("US/Eastern")
_fails = []


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + (f"   [{detail}]" if detail else ""))
    if not ok:
        _fails.append(name)


def _ep(h, m, s=0):
    return datetime(2026, 8, 31, h, m, s, tzinfo=ET).timestamp()


def _run(store, args):
    import warehouse_reader as WR

    class _B:
        def __init__(s, b): s.b = b
        def read(s): return s.b

    class _P:
        def __init__(s, st): s.st = st
        def paginate(s, Bucket=None, Prefix=None):
            yield {"Contents": [{"Key": k, "Size": len(v)}
                                for k, v in s.st.items() if k.startswith(Prefix)]}

    class _S3:
        def __init__(s, st): s.st = st
        def get_paginator(s, _): return _P(s.st)
        def get_object(s, Bucket=None, Key=None): return {"Body": _B(s.st[Key])}

    WR._client = lambda *a, **k: _S3(store)
    import importlib.util as u
    sp = u.spec_from_file_location(
        "sf", os.path.join(_root, "tests", "screen_sweep_forensics.py"))
    m = u.module_from_spec(sp)
    try:
        sp.loader.exec_module(m)
    except SystemExit:
        pass
    m.WCACHE.WR._client = lambda *a, **k: _S3(store)
    buf = io.StringIO()
    devnull = open(os.devnull)
    old, sys.stdin = sys.stdin, devnull
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            m.main(["x"] + args)
    except SystemExit:
        pass
    finally:
        sys.stdin = old
        devnull.close()
    return buf.getvalue()


def _store(trades, checks, bars):
    st = {}
    for n, r in enumerate(trades):
        st[f"raw/trades/dt=2026-08-31/sym=QQQ/{n}.json"] = json.dumps(
            {"symbol": "QQQ", "record": r}).encode()
    st["raw/derived_plan_check/dt=2026-08-31/sym=QQQ/1.json"] = json.dumps(
        {"symbol": "QQQ", "record": checks}).encode()
    st["raw/candles/dt=2026-08-31/sym=QQQ/interval=1m/1.json"] = json.dumps(
        {"symbol": "QQQ", "record": bars}).encode()
    return st


def _trade(tid, short, long_, pnl, reason):
    return {"trade_id": tid, "strategy": "SweepCreditSpread",
            "setup_type": "sweep_credit", "status": "closed",
            "entry_time": "2026-08-31 12:00:00",
            "exit_time": "2026-08-31 12:30:00", "entry_premium": 1.30,
            "exit_premium": 1.60, "contracts": 5, "pnl_usd": pnl,
            "pnl_pct": -0.11, "exit_reason": reason, "mfe_premium": 1.70,
            "mfe_bars": 5, "mae_premium": 1.25, "mae_bars": 2,
            "credit_received": 1.30, "spread_width": 2.5,
            "short_strike": short, "long_strike": long_}


def main():
    base = ["--from", "2026-08-31", "--to", "2026-08-31"]
    A = 100.0
    chk = [{"ts_epoch": _ep(11, 59), "strategy": "SweepCreditSpread",
            "check_name": "short_anchor", "value": A, "direction": "call"},
           {"ts_epoch": _ep(11, 59), "strategy": "SweepCreditSpread",
            "check_name": "side_of_pool", "value": -0.4, "direction": "call"}]

    # ── F1 — a CALL spread run over upward ──────────────────────────────
    up = [{"interval": "1m", "ts_epoch_ms": int(_ep(12, m) * 1000),
           "high": (100.6 + m * .05) + .2, "low": (100.6 + m * .05) - .2,
           "close": 100.6 + m * .05} if m >= 5 else
          {"interval": "1m", "ts_epoch_ms": int(_ep(12, m) * 1000),
           "high": 99.7, "low": 99.3, "close": 99.5} for m in range(30)]
    out = _run(_store([_trade("a", A, A + 2.5, -150, "hard_stop_15%")], chk, up), base)
    check("F1 a call spread run over reports positive penetration",
          "price traded BEYOND the short strike on 1/1" in out,
          [l for l in out.splitlines() if "traded BEYOND" in l][:1])
    check("F1b and 25 consecutive closes past it reads as accepted",
          "10+ bars (accepted)" in out)

    # ── F2 — THE SAME TAPE, A PUT SPREAD ────────────────────────────────
    # 🔴 Price rising through 100 is a BREACH for a call spread and a WIN for
    # a put spread. If direction were taken from anything but the structure,
    # this case would report the same as F1 — which is the bug.
    # ⚠️ A TAPE THAT NEVER DIPS BELOW THE ANCHOR. The F1 tape opens at 99.5 —
    # BELOW 100 — which is a genuine breach for a put spread, so reusing it
    # here would have failed the code for being right. My fixture's fault,
    # caught by the check.
    up_only = [{"interval": "1m", "ts_epoch_ms": int(_ep(12, m) * 1000),
                "high": (100.6 + m * .05) + .2, "low": (100.6 + m * .05) - .2,
                "close": 100.6 + m * .05} for m in range(30)]
    out2 = _run(_store([_trade("b", A, A - 2.5, 90, "vertical_hold")],
                       chk, up_only), base)
    check("F2 an up-tape on a PUT spread is NOT a breach",
          "price traded BEYOND the short strike on 0/1" in out2,
          [l for l in out2.splitlines() if "traded BEYOND" in l][:1])

    # ── F2b — and the SAME up-only tape IS a breach for the call spread ──
    # 🔑 Both directions on one tape is what proves the structure is being
    # read, rather than a constant being returned that happens to be right.
    out2b = _run(_store([_trade("b2", A, A + 2.5, -150, "hard_stop_15%")],
                        chk, up_only), base)
    check("F2b the same up-tape on a CALL spread IS a breach",
          "price traded BEYOND the short strike on 1/1" in out2b,
          [l for l in out2b.splitlines() if "traded BEYOND" in l][:1])

    # ── F3 — ACCEPTANCE IS A RUN, NOT A COUNT ───────────────────────────
    # ⚠️ Six closes past the level, never two in a row. A COUNT would call this
    # acceptance; a RUN calls it what it is — chop around the level.
    alt = []
    for m in range(30):
        past = (m % 2 == 0) and m >= 10
        c = 100.4 if past else 99.6
        alt.append({"interval": "1m", "ts_epoch_ms": int(_ep(12, m) * 1000),
                    "high": c + .2, "low": c - .2, "close": c})
    out3 = _run(_store([_trade("c", A, A + 2.5, -150, "hard_stop_15%")], chk, alt), base)
    check("F3 alternating closes are 1 bar, not acceptance",
          "1 bar (wick)" in out3 and "10+ bars (accepted)" not in out3,
          [l for l in out3.splitlines() if "bar" in l][:2])

    # ── F4 — a trade with no candles is EXCLUDED, not counted as zero ────
    # ⚠️ Unmeasurable and zero are different facts. Counting a missing window
    # as "never penetrated" would make the level look stronger than it is.
    out4 = _run(_store([_trade("d", A, A + 2.5, -150, "hard_stop_15%")], chk, []), base)
    check("F4 a trade with no candles is named, not scored zero",
          "NO 1m candles" in out4 and "excluded below, not counted as zero" in out4)

    print()
    if _fails:
        print(f"FAILED {len(_fails)}: " + ", ".join(_fails))
        return 1
    print("test_sweep_forensics: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
