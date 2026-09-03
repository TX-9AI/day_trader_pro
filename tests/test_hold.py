#!/usr/bin/env python3
# day_trader_pro/tests/test_hold.py — v1.0
# v1.0 (2026-09-03) — dtp r263.
#
# 🔑 H1-H3 ARE THE THREE SHAPES THE OPERATOR NAMED: "did the momentum PERSIST,
#   or did it STALL AND START AGAIN, or STALL AND GIVE BACK." MFE and NET alone
#   cannot tell the first two apart — both finish high — so the path is walked
#   and the LEG COUNT separates them.
#
# 🔴 H4 IS THE CASE MOM.1 MUST NOT BREAK: a move that ROUND-TRIPPED while the
#   TRADES still netted positive. Those are the moves where the stops earned
#   their keep, and holding through would have handed the money back.
import io, json, os, sys, contextlib
from datetime import datetime, timezone

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
_fails = []


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + (f"   [{detail}]" if detail else ""))
    if not ok:
        _fails.append(name)


def _ms(mn):
    return int(datetime(2026, 9, 3, 13, mn, tzinfo=timezone.utc).timestamp() * 1000)


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
    sp = u.spec_from_file_location("sh", os.path.join(_root, "tests",
                                                      "screen_hold.py"))
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


def _tape(store, sym, closes):
    store[f"raw/candles/dt=2026-09-03/sym={sym}/interval=1m/1.json"] = json.dumps(
        {"symbol": sym, "record": [
            {"interval": "1m", "ts_epoch_ms": _ms(i),
             "high": c + .05, "low": c - .05} for i, c in enumerate(closes)]}
    ).encode()


def _trades(store, sym, pnls, side="call", n0=0):
    for j, p in enumerate(pnls):
        t = {"trade_id": f"{sym}{j}", "strategy": "RunawayContinuation",
             "setup_type": "r", "status": "closed",
             "entry_time": f"2026-09-03 13:{12 + j*4:02d}:00",
             "exit_time": f"2026-09-03 13:{34 if j == len(pnls)-1 else 14+j*4:02d}:00",
             "entry_premium": 1.0, "exit_premium": 1.1, "contracts": 5,
             "pnl_usd": p, "pnl_pct": .1, "exit_reason": "x",
             "mfe_premium": 1.2, "mfe_bars": 3, "mae_premium": 0.9,
             "mae_bars": 1, "credit_received": 0, "spread_width": 0,
             "option_side": side}
        store[f"raw/trades/dt=2026-09-03/sym={sym}/{n0+j}.json"] = json.dumps(
            {"symbol": sym, "record": t}).encode()


def main():
    base = ["--from", "2026-09-03", "--to", "2026-09-03",
            "--type", "RunawayContinuation"]
    st = {}
    # one clean advance / stall-then-resume / made it early and gave it back
    _tape(st, "QQQ", [100 + .02*i for i in range(10)]
          + [100.2 + .25*i for i in range(30)])
    _tape(st, "AMD", [100 + .02*i for i in range(10)]
          + [100.2 + .25*i for i in range(10)]
          + [102.7 - .10*i for i in range(8)]
          + [101.9 + .30*i for i in range(12)])
    _tape(st, "NVDA", [100 + .02*i for i in range(10)]
          + [100.2 + .30*i for i in range(12)]
          + [103.8 - .28*i for i in range(18)])
    _trades(st, "QQQ", [300, 150, 200])
    _trades(st, "AMD", [400, -100, 250])
    _trades(st, "NVDA", [500, -150, -120])
    out = _run(st, base)

    def _row(sym):
        for ln in out.splitlines():
            p = ln.split()
            if p and p[0] == sym:
                return ln
        return ""

    # ── H1 — ONE ADVANCE, STILL GOING ───────────────────────────────────
    check("H1 a single advance still running reads PERSISTED",
          "PERSISTED" in _row("QQQ"), _row("QQQ").strip()[:80])

    # ── H2 — STALLED, THEN NEW GROUND ───────────────────────────────────
    # 🔑 MFE AND NET CANNOT SEE THIS — the resumed move finishes high, exactly
    # like the one that never stalled. Only the LEG COUNT separates them.
    check("H2 a stall followed by new ground reads RESUMED, legs > 1",
          "RESUMED" in _row("AMD") and " 2 " in _row("AMD"),
          _row("AMD").strip()[:80])

    # ── H3 — MADE IT EARLY, HANDED IT BACK ──────────────────────────────
    # ⚠️ The peak column is the tell: 45% through the window, not 100%.
    check("H3 an early peak with a large giveback reads GAVE BACK",
          "GAVE BACK" in _row("NVDA"), _row("NVDA").strip()[:80])

    # ── H4 — THE CASE MOM.1 MUST NOT BREAK ──────────────────────────────
    # 🔴 A move that ROUND-TRIPPED while the TRADES still netted positive. The
    # stops earned their keep there, and holding would have given it back.
    check("H4 a round-trip that still netted positive is called out",
          "STILL netted" in out and "stops earned their keep" in out)

    # ── H5 — NO TRIM ────────────────────────────────────────────────────
    # ⚠️ screen_clusters trims leading losers, which made "the first entry won"
    # true BY CONSTRUCTION. This tool must NOT, or it answers a different
    # question than the one asked.
    src = open(os.path.join(_root, "tests", "screen_hold.py"),
               encoding="utf-8").read()
    check("H5 clusters are measured whole, with no trim",
          "NO TRIM" in src and "_trim" not in src,
          "the operator asked about the move regardless of how it opened")

    # ── H6 — THE SHORT SIDE ─────────────────────────────────────────────
    # ⚠️ A short move's favourable travel is DOWN. One shared formula would
    # report every short as an instant round-trip.
    st2 = {}
    _tape(st2, "SPX", [100 - .02*i for i in range(10)]
          + [99.8 - .25*i for i in range(30)])
    _trades(st2, "SPX", [300, 150, 200], side="put")
    out2 = _run(st2, base)
    check("H6 a falling tape on PUTs reads as a move, not a round-trip",
          "PERSISTED" in out2 or "RESUMED" in out2,
          [l for l in out2.splitlines() if l.strip().startswith("SPX")][:1])

    # ── H7 — THE UNDERLYING-ONLY LIMIT IS STATED ────────────────────────
    # 🔴 The cluster's trades are DIFFERENT CONTRACTS, so a held position's
    # option P&L is not reconstructible here. Saying so is the difference
    # between a measurement and an overclaim.
    check("H7 the report states it measures the underlying only",
          "UNDERLYING ONLY" in out and "DIFFERENT CONTRACTS" in out)

    print()
    if _fails:
        print(f"FAILED {len(_fails)}: " + ", ".join(_fails))
        return 1
    print("test_hold: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
