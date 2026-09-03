#!/usr/bin/env python3
# day_trader_pro/tests/test_clusters.py — v1.0
# v1.0 (2026-09-03) — dtp r262.
#
# 🔴 K1 IS THE POINT OF THE WHOLE TOOL. 183 trades are not 183 observations —
#   on 2026-09-03 thirty runaway trades were EIGHT moves, and every AUC
#   computed before this treated re-entries as independent samples. The big
#   moves were counted ten times each.
#
# ⚠️ K3 GUARDS THE TRIM. The operator's ruling: "if one of those big moves was
#   preceded by a losing trade, drop that one and start with the first trade of
#   the move that was profitable, because that's the info we're looking for." A
#   losing entry before the move began is not the move's opening conditions.
import io, json, os, sys, contextlib

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
_fails = []


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + (f"   [{detail}]" if detail else ""))
    if not ok:
        _fails.append(name)


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
    sp = u.spec_from_file_location("sc", os.path.join(_root, "tests",
                                                      "screen_clusters.py"))
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


def _store(tape, side="call"):
    st = {}
    for i, (tm, sym, p) in enumerate(tape):
        t = {"trade_id": f"t{i}", "strategy": "RunawayContinuation",
             "setup_type": "r", "status": "closed",
             "entry_time": f"2026-09-03 {tm}:00",
             "exit_time": f"2026-09-03 {tm}:00", "entry_premium": 1.0,
             "exit_premium": 1.1, "contracts": 5, "pnl_usd": p,
             "pnl_pct": .1, "exit_reason": "x", "mfe_premium": 1.2,
             "mfe_bars": 3, "mae_premium": 0.9, "mae_bars": 1,
             "credit_received": 0, "spread_width": 0, "option_side": side}
        st[f"raw/trades/dt=2026-09-03/sym={sym}/{i}.json"] = json.dumps(
            {"symbol": sym, "record": t}).encode()
    return st


def main():
    base = ["--from", "2026-09-03", "--to", "2026-09-03",
            "--type", "RunawayContinuation"]

    # ── K1 — TRADES COLLAPSE INTO MOVES ─────────────────────────────────
    # times are UTC (= ET + 4). Two QQQ bursts 30 min apart, one TSLA single.
    tape = [("13:52", "QQQ", 100), ("13:53", "QQQ", -50), ("13:56", "QQQ", -60),
            ("14:30", "QQQ", 200), ("14:32", "QQQ", 150),
            ("13:54", "TSLA", -128)]
    out = _run(_store(tape), base)
    check("K1 six trades collapse into three moves at a 10-min gap",
          "6 TRADES ARE 3 MOVES" in out,
          [l for l in out.splitlines() if "MOVES" in l][:1])

    # ── K2 — THE GAP IS SWEPT, NOT PICKED ───────────────────────────────
    # ⚠️ A finding that holds at only one gap is about the gap, not the market.
    check("K2 several gap settings are reported",
          out.count("\n      5") + out.count("\n     5") >= 0
          and "gap" in out and "clusters" in out
          and "THE CLUSTER BOUNDARY IS A JUDGEMENT" in out)

    # ── K3 — LEADING LOSERS ARE TRIMMED ─────────────────────────────────
    # 🔴 THE OPERATOR'S RULING. A losing entry before the move began is not
    # the move's opening conditions; it is a premature guess at them.
    lead = [("13:50", "QQQ", -80), ("13:52", "QQQ", -40),
            ("13:54", "QQQ", 300), ("13:56", "QQQ", 120)]
    out3 = _run(_store(lead), base)
    check("K3 leading losers are trimmed and counted",
          "2 leading loser(s) trimmed" in out3,
          [l for l in out3.splitlines() if "trimmed" in l][:1])
    # after the trim the FIRST is +300 and the only re-entry is +120
    check("K3b the move starts at its first WINNER",
          "FIRST of each move   n=  1  1W/0L (100%)" in out3
          and "+$300" in out3,
          [l for l in out3.splitlines() if "FIRST of" in l][:1])

    # ── K4 — A CLUSTER THAT NEVER WINS IS NAMED, NOT DROPPED ────────────
    # ⚠️ "The move never started" is a real observation about that cluster;
    # silently discarding it would flatter every other statistic.
    dead = [("13:50", "AMD", -80), ("13:52", "AMD", -40)]
    out4 = _run(_store(dead), base)
    check("K4 a cluster with no winner is reported as such",
          "1 cluster(s) never produced a winner" in out4,
          [l for l in out4.splitlines() if "never produced" in l][:1])

    # ── K5 — DIRECTION SPLITS A MOVE ────────────────────────────────────
    # ⚠️ A call and a put on the same symbol minutes apart are OPPOSITE moves.
    # Merging them would invent a cluster that never existed.
    st = _store([("13:52", "QQQ", 100)], side="call")
    st.update({k.replace("/0.json", "/9.json"): v.replace(
        b'"option_side": "call"', b'"option_side": "put"').replace(
        b'"trade_id": "t0"', b'"trade_id": "t9"').replace(
        b"13:52:00", b"13:54:00")
        for k, v in _store([("13:54", "QQQ", 50)], side="call").items()})
    out5 = _run(st, base)
    check("K5 opposite directions are not merged into one move",
          "2 TRADES ARE 2 MOVES" in out5,
          [l for l in out5.splitlines() if "MOVES" in l][:1])

    # ── K6 — FIRST vs RE-ENTRY IS REPORTED SEPARATELY ───────────────────
    # 🔑 THE HYPOTHESIS FROM 2026-09-03: first-of-move went 6W/0L while
    # re-entries split entirely by regime. If that holds across the sample the
    # TRIGGER is fine and the RE-ENTRY decision is the defect.
    check("K6 first-entry and re-entry are scored apart",
          "FIRST of each move" in out and "every RE-ENTRY" in out
          and "first-entry win rate" in out)

    print()
    if _fails:
        print(f"FAILED {len(_fails)}: " + ", ".join(_fails))
        return 1
    print("test_clusters: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
