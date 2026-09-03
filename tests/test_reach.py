#!/usr/bin/env python3
# day_trader_pro/tests/test_reach.py — v1.0
# v1.0 (2026-09-03) — dtp r260.
#
# 🔴 R1 IS THE REASON THIS TOOL EXISTS. Every calibration before it measured
#   PREMIUM excursion, which is the underlying move MULTIPLIED BY the strike we
#   happened to pick — so "did it run" was never a clean statement about the
#   tape. Reach is measured on the UNDERLYING, in ATR, and the strike is
#   compared to it rather than embedded in it.
#
# ⚠️ R3 GUARDS THE ATR SOURCE. An ATR computed over the POST-fill bars is
#   inflated by the very travel it is meant to normalise, which would shrink
#   every reach figure toward 1.0 and hide both failure modes at once.
import io, json, os, sys, contextlib
from datetime import datetime, timezone

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
_fails = []


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + (f"   [{detail}]" if detail else ""))
    if not ok:
        _fails.append(name)


def _ep(h, m):
    return datetime(2026, 8, 31, h, m, tzinfo=timezone.utc).timestamp()


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
    sp = u.spec_from_file_location("sr", os.path.join(_root, "tests",
                                                      "screen_reach.py"))
    m = u.module_from_spec(sp)
    try:
        sp.loader.exec_module(m)
    except SystemExit as exc:
        return f"REFUSED: {exc}"
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


def _store(strikes, side="call"):
    # 15 chop bars, fill at 13:15, then a 3-point advance
    cl = [100 + ((i % 3) - 1) * .05 for i in range(15)] + \
         [100 + i * .20 for i in range(1, 16)]
    if side == "put":
        cl = [200 - (c - 100) for c in cl]
    rec = [{"interval": "1m", "ts_epoch_ms": int(_ep(13, i) * 1000),
            "open": c, "high": c + .06, "low": c - .06, "close": c}
           for i, c in enumerate(cl)]
    st = {"raw/candles/dt=2026-08-31/sym=QQQ/interval=1m/1.json":
          json.dumps({"symbol": "QQQ", "record": rec}).encode()}
    spot = 100.0 if side == "call" else 200.0
    n = 0
    for k in strikes:
        for _ in range(6):
            t = {"trade_id": f"t{n}", "strategy": "RunawayContinuation",
                 "setup_type": "r", "status": "closed",
                 "entry_time": "2026-08-31 13:15:00",
                 "exit_time": "2026-08-31 13:29:00", "entry_premium": 1.0,
                 "exit_premium": 1.2, "contracts": 5, "pnl_usd": 50,
                 "pnl_pct": .1, "exit_reason": "x", "mfe_premium": 1.3,
                 "mfe_bars": 4, "mae_premium": 0.9, "mae_bars": 2,
                 "credit_received": 0, "spread_width": 0,
                 "option_side": side, "strike": k, "underlying_entry": spot}
            st[f"raw/trades/dt=2026-08-31/sym=QQQ/{n}.json"] = json.dumps(
                {"symbol": "QQQ", "record": t}).encode()
            n += 1
    return st


def main():
    base = ["--from", "2026-08-31", "--to", "2026-08-31",
            "--type", "RunawayContinuation"]
    src = open(os.path.join(_root, "tests", "screen_reach.py"),
               encoding="utf-8").read()

    # ── R1 — REACH IS THE UNDERLYING, NOT THE PREMIUM ───────────────────
    check("R1 reach is measured on the underlying, not on premium",
          "underlying_entry" in src and "mfe_premium" not in
          src.split("def _render")[1],
          "premium excursion is the move x the strike we picked")

    # ── R2 — REACHABLE AND UNREACHABLE STRIKES ARE SEPARATED ────────────
    # 🔑 THE QUESTION THAT CAN INVALIDATE THE DELTA IDEA: if most strikes sat
    # beyond where the tape went, the selector is the binding constraint and
    # no trigger improvement fixes it.
    out = _run(_store([101.0, 104.0]), base)
    check("R2 half-reachable strikes report as 50%",
          "strike reached by the underlying : 6/12  (50%)" in out,
          [l for l in out.splitlines() if "reached by" in l][:1])
    check("R2b the shortfall is stated in ATR",
          "fell short by a median" in out and "ATR" in out)

    # ── R2c — ALL REACHABLE, AND ALL NOT ────────────────────────────────
    near = _run(_store([100.5]), base)
    far = _run(_store([110.0]), base)
    check("R2c every strike reachable reports 100%",
          "(100%)" in near, [l for l in near.splitlines() if "reached by" in l][:1])
    check("R2d no strike reachable reports 0%",
          "(0%)" in far, [l for l in far.splitlines() if "reached by" in l][:1])

    # ── R3 — ATR COMES FROM BEFORE THE FILL ─────────────────────────────
    # 🔴 An ATR over the POST-fill bars is inflated by the travel it is meant
    # to normalise — it would pull every reach figure toward 1.0 and hide both
    # failure modes at once.
    check("R3 ATR is computed from the pre-fill window only",
          "ATR COMES FROM THE PRE-FILL WINDOW" in src
          and "e_ms - (TRIG_WINDOW + 5)" in src)

    # ── R4 — THE PUT SIDE MIRRORS ───────────────────────────────────────
    # ⚠️ Not assumed. A flipped sign would report every put as unreachable.
    puts = _run(_store([199.0], side="put"), base)
    check("R4 a PUT with a reachable strike reports reached",
          "(100%)" in puts,
          [l for l in puts.splitlines() if "reached by" in l][:1])

    # ── R5 — THE FORWARD-LOOKING CAVEAT IS STATED ───────────────────────
    # ⚠️ Reach is a post-entry fact. It is fine in a STUDY and fatal in a gate,
    # and the report has to say which it is.
    check("R5 the report names reach as forward-looking",
          "REACH IS FORWARD-LOOKING" in out
          and "not" in out and "gate" in out)

    print()
    if _fails:
        print(f"FAILED {len(_fails)}: " + ", ".join(_fails))
        return 1
    print("test_reach: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
