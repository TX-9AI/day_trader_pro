#!/usr/bin/env python3
# day_trader_pro/tests/test_ratchet.py — v1.0
# v1.0 (2026-09-03) — dtp r264.
#
# 🔑 THE RULE, simplified to structure on the operator's ruling: "it can be as
#   simple as a new higher high (go long) or a new lower low (go short)."
#   Re-entry needs a 1m CLOSE above the running high of the move so far.
#
# 🔴 T3 IS THE ONE THAT MATTERS. A leg-count approximation of this rule
#   truncated NVDA from 10 entries to 5 on a move that made $1,520 — and in
#   that sequence the LAST entry made $1,020. Whether the refused entries are
#   the profitable ones is the only question, and only a bar-by-bar replay
#   answers it. These fixtures pin that a staircase loses nothing.
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
    sp = u.spec_from_file_location("sr", os.path.join(_root, "tests",
                                                      "screen_ratchet.py"))
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


def _tape(st, sym, closes):
    st[f"raw/candles/dt=2026-09-03/sym={sym}/interval=1m/1.json"] = json.dumps(
        {"symbol": sym, "record": [
            {"interval": "1m", "ts_epoch_ms": _ms(i), "high": c + .05,
             "low": c - .05, "close": c} for i, c in enumerate(closes)]}).encode()


def _tr(st, sym, pnls, side="call", n0=0):
    for j, p in enumerate(pnls):
        t = {"trade_id": f"{sym}{j}", "strategy": "RunawayContinuation",
             "setup_type": "r", "status": "closed",
             "entry_time": f"2026-09-03 13:{2 + j*6:02d}:00",
             "exit_time": f"2026-09-03 13:{5 + j*6:02d}:00",
             "entry_premium": 1.0, "exit_premium": 1.1, "contracts": 5,
             "pnl_usd": p, "pnl_pct": .1, "exit_reason": "x",
             "mfe_premium": 1.2, "mfe_bars": 3, "mae_premium": 0.9,
             "mae_bars": 1, "credit_received": 0, "spread_width": 0,
             "option_side": side}
        st[f"raw/trades/dt=2026-09-03/sym={sym}/{n0+j}.json"] = json.dumps(
            {"symbol": sym, "record": t}).encode()


def _row(out, sym):
    """Panel 3's per-move row, not panel 2's winners list.

    ⚠️ THE FIRST DRAFT MATCHED ANY LINE STARTING WITH THE SYMBOL and picked up
    the "biggest winners" list instead — six checks failed against the wrong
    line. Panel 3's rows carry eight fields (n, kept, cut, actual, ratchet,
    delta); panel 2's carry four.
    """
    for ln in out.splitlines():
        p = ln.split()
        if p and p[0] == sym and len(p) >= 8:
            return ln
    return ""


def main():
    base = ["--from", "2026-09-03", "--to", "2026-09-03",
            "--type", "RunawayContinuation"]
    st = {}
    _tape(st, "QQQ", [100 + .25*i for i in range(40)])                  # staircase
    _tape(st, "META", [100 + .30*i for i in range(8)]
          + [102.4 - .05*i for i in range(32)])                          # fade
    _tape(st, "SPX", [100 - .25*i for i in range(40)])                  # falling
    _tr(st, "QQQ", [300, 150, 200, 250])
    _tr(st, "META", [400, -150, -200, -180], n0=10)
    _tr(st, "SPX", [500, 200, 300, 150], side="put", n0=20)
    out = _run(st, base)

    # ── T1 — A STAIRCASE LOSES NOTHING ──────────────────────────────────
    # 🔴 THE FAILURE MODE THE LEG-COUNT ESTIMATE HAD: it truncated a 10-entry
    # move that made $1,520 down to 5, and the LAST entry of that sequence made
    # $1,020. A rule that refuses winners has done nothing but shrink the book.
    check("T1 a continuous staircase keeps every entry",
          "QQQ" in _row(out, "QQQ") and "    4    0 " in _row(out, "QQQ"),
          _row(out, "QQQ").strip()[:70])

    # ── T2 — A FADE IS TRUNCATED ────────────────────────────────────────
    # ⚠️ META's SECOND entry is legitimately KEPT — that tape was still making
    # higher highs when it fired. The refusals begin where the fade begins,
    # which is the rule working, not a gap in it.
    r = _row(out, "META")
    check("T2 a fading tape has its later re-entries refused",
          "    2    2 " in r, r.strip()[:70])
    check("T2b and refusing them turns the move positive",
          "+$250" in r and "-$130" in r, r.strip()[:70])

    # ── T3 — THE REFUSED ARE LOSERS ─────────────────────────────────────
    # 🔑 THE ONLY QUESTION THAT MATTERS. A rule that refuses winners and losers
    # in equal measure has just reduced the sample.
    check("T3 the refused entries are losers, not winners",
          "of the refused: 0 winners" in out,
          [l for l in out.splitlines() if "of the refused" in l][:1])

    # ── T4 — THE SHORT SIDE IS LOWER LOWS ───────────────────────────────
    # ⚠️ Not assumed. Comparing a put against a HIGHER high would refuse every
    # short entry on a correctly falling tape.
    check("T4 a falling tape on puts keeps every entry",
          "    4    0 " in _row(out, "SPX"), _row(out, "SPX").strip()[:70])

    # ── T5 — A CLOSE, NOT A TOUCH ───────────────────────────────────────
    # 🔴 A WICK ABOVE THE RUNNING HIGH RE-ARMS INTO THE FADE. This tape wicks
    # above the prior high on every bar and never closes above it.
    st2 = {}
    wick = []
    for i in range(40):
        base_px = 100 + .30*i if i < 8 else 102.4 - .05*i
        wick.append(base_px)
    st2[f"raw/candles/dt=2026-09-03/sym=AMD/interval=1m/1.json"] = json.dumps(
        {"symbol": "AMD", "record": [
            {"interval": "1m", "ts_epoch_ms": _ms(i),
             "high": c + 3.0, "low": c - .05, "close": c}
            for i, c in enumerate(wick)]}).encode()
    _tr(st2, "AMD", [400, -150, -200, -180])
    out2 = _run(st2, base)
    check("T5 wicks above the running high do not qualify",
          "    1    3 " in _row(out2, "AMD") or "    2    2 " in _row(out2, "AMD"),
          _row(out2, "AMD").strip()[:70])

    # ── T6 — THE FIRST ENTRY IS NEVER REFUSED ───────────────────────────
    # ⚠️ The ratchet governs RE-entry. What triggers the opening entry is a
    # separate question and this rule does not touch it.
    src = open(os.path.join(_root, "tests", "screen_ratchet.py"),
               encoding="utf-8").read()
    check("T6 the first entry of a move is never refused",
          "First entries are" in out and "never refused" in out
          and "if i == 0:" in src)

    # ── T7 — PER-ENTRY P&L, NOT A SIMULATION ────────────────────────────
    # 🔴 Refusing an entry removes that trade's realised P&L. It does NOT model
    # what a held position would have done instead — the trades are different
    # contracts. Saying so is the difference between a measurement and a claim.
    check("T7 the report states it is not a simulation",
          "NOT A SIMULATION" in out
          and "does NOT model what a held position" in out,
          "refusing an entry removes its P&L; it models nothing else")

    print()
    if _fails:
        print(f"FAILED {len(_fails)}: " + ", ".join(_fails))
        return 1
    print("test_ratchet: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
