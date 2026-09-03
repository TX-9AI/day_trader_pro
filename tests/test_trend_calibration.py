#!/usr/bin/env python3
# day_trader_pro/tests/test_trend_calibration.py — v1.0
# v1.0 (2026-09-03) — dtp r257.
#
# 🔑 C1 IS THE CHECK THAT MAKES THE CALIBRATION MEAN ANYTHING: the calibrator
#   must import the REAL meter from options_trader_v4. If it reimplemented the
#   maths, a threshold set here would not mean the same thing live — and every
#   fixture would agree with its own bug, which is how check_plan_prepares
#   certified the bid/ask basis mismatch for the life of the strategy.
#
# 🔴 C2 GUARDS THE UTC PARSE. `entry_time` is stored UTC (trade_logger says so
#   three times). Reading it as ET was a four-hour error in sweep forensics
#   that walked the join off the front of the session and made ONE stale
#   evaluation look like a constant across seventeen trades.
#
# ⚠️ C3 GUARDS THE CREDIT SIGN. `mfe_premium` is the HIGHEST mark seen
#   (exit_engine._track_excursion), so a credit vertical's favourable extreme
#   is `mae_premium`. Backwards, every winning credit trade scores as
#   never-green and the calibration inverts.
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
    sp = u.spec_from_file_location(
        "ct", os.path.join(_root, "tests", "calibrate_trend_strength.py"))
    m = u.module_from_spec(sp)
    try:
        sp.loader.exec_module(m)
    except SystemExit as exc:
        return f"IMPORT REFUSED: {exc}", None
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
    return buf.getvalue(), m


def _tape(closes, hi, lo):
    return [{"interval": "1m", "ts_epoch_ms": int(_ep(13, i) * 1000),
             "open": c, "high": c + hi, "low": c - lo, "close": c}
            for i, c in enumerate(closes)]


def _store(trades, tapes):
    st = {}
    for sym, rows in tapes.items():
        st[f"raw/candles/dt=2026-08-31/sym={sym}/interval=1m/1.json"] = \
            json.dumps({"symbol": sym, "record": rows}).encode()
    for i, (sym, t) in enumerate(trades):
        st[f"raw/trades/dt=2026-08-31/sym={sym}/{i}.json"] = json.dumps(
            {"symbol": sym, "record": t}).encode()
    return st


def _trade(strat="RunawayContinuation", mfe=1.30, mae=0.90, credit=0.0,
           side="call", bound_hi=100.0, bound_lo=98.0, entry="13:24:00"):
    return {"trade_id": f"x{mfe}{mae}{credit}{side}{entry}",
            "strategy": strat, "setup_type": "s", "status": "closed",
            "entry_time": f"2026-08-31 {entry}",
            "exit_time": "2026-08-31 13:50:00",
            "entry_premium": 1.00, "exit_premium": 1.10, "contracts": 5,
            "pnl_usd": 10.0, "pnl_pct": 0.1, "exit_reason": "x",
            "mfe_premium": mfe, "mfe_bars": 4, "mae_premium": mae,
            "mae_bars": 2, "credit_received": credit, "spread_width": 5.0,
            "orb_range_high": bound_hi, "orb_range_low": bound_lo,
            "option_side": side}


def main():
    base = ["--from", "2026-08-31", "--to", "2026-08-31"]
    rip = [99.5] + [100.2 + i * 0.20 for i in range(24)]
    creep = [99.5, 100.2]
    for i in range(23):
        creep.append(creep[-1] + (0.40 if i % 3 else -0.40))
    tapes = {"QQQ": _tape(rip, 0.03, 0.15), "AMD": _tape(creep, 0.10, 0.10)}

    tr = []
    for i in range(48):
        sym = "QQQ" if i % 2 == 0 else "AMD"
        tr.append((sym, _trade(mfe=1.30 if i % 2 == 0 else 1.01)))
    out, mod = _run(_store(tr, tapes), base + ["--type", "RunawayContinuation"])

    # ── C1 — THE REAL METER, NOT A COPY ─────────────────────────────────
    src = open(os.path.join(_root, "tests", "calibrate_trend_strength.py"),
               encoding="utf-8").read()
    check("C1 the calibrator imports the meter from options_trader_v4",
          "from analysis.trend_strength import measure" in src
          and "CANNOT FIND" in src,
          "and fails loudly rather than falling back to a local copy")

    # ── C2 — UTC, not ET ────────────────────────────────────────────────
    check("C2 entry_time is parsed as UTC",
          "tzinfo=UTC" in src and 'ZoneInfo("UTC")' in src)

    # ── C3 — the credit sign ────────────────────────────────────────────
    # a credit entered at 1.00 whose mark FELL to 0.90 is a +10% winner; its
    # favourable extreme is mae_premium, not mfe_premium.
    ctr = [("QQQ", _trade(strat="SweepCreditSpread", mfe=1.02, mae=0.90,
                          credit=1.00)) for _ in range(6)]
    ctr += [("AMD", _trade(strat="SweepCreditSpread", mfe=1.02, mae=0.995,
                           credit=1.00)) for _ in range(6)]
    out3, _ = _run(_store(ctr, tapes), base + ["--type", "SweepCreditSpread"])
    check("C3 a credit vertical that tightened counts as GREEN",
          "GREEN (>= 5%)  : 6" in out3,
          [l for l in out3.splitlines() if "GREEN (" in l][:1])

    # ── C4 — it separates the planted split ─────────────────────────────
    rows = {}
    for ln in out.splitlines():
        p = ln.split()
        if len(p) >= 4 and p[0] in ("score", "efficiency", "acceptance",
                                    "shallowness", "pace"):
            rows[p[0]] = float(p[1])
    check("C4 the planted rip/creep split is recovered",
          rows.get("score", 0) > 0.9, f"score AUC {rows.get('score')}")

    # ── C5 — the noise floor and the kept column are BOTH printed ───────
    # 🔴 AN AUC WITHOUT ITS NOISE FLOOR READS AS A FINDING, and a threshold
    # without the kept count reads as a gate when it is a halt.
    check("C5 the noise floor is printed beside the result",
          "NOISE FLOOR AT THIS SAMPLE" in out and "0.69" in out)
    check("C5b the threshold sweep reports what it would REFUSE",
          "kept" in out and "IS NOT A GATE, IT IS A HALT" in out)

    # ── C6 — an unreadable window is excluded, not scored weak ──────────
    # ⚠️ A short window scoring 0.0 would read as "flaccid" and drag the
    # never-green median down, manufacturing separation from missing data.
    short_tape = {"QQQ": _tape(rip[:6], 0.03, 0.15)}
    str_ = [("QQQ", _trade())] * 4
    out6, _ = _run(_store(str_, short_tape), base + ["--type", "RunawayContinuation"])
    check("C6 a too-short window is counted as unreadable, not weak",
          "window too short to read" in out6
          and "NOT scored weak" in out6)

    print()
    if _fails:
        print(f"FAILED {len(_fails)}: " + ", ".join(_fails))
        return 1
    print("test_trend_calibration: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
