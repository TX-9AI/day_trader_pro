#!/usr/bin/env python3
# day_trader_pro/tests/test_screen_entry_vectors.py — v1.0
# v1.0 (2026-09-02) — dtp r251.
#
# 🔴 V2 IS THE CHECK THAT CARRIES THE WEIGHT. `mfe_premium` is the HIGHEST mark
#   seen — exit_engine._track_excursion keeps it on `px > best` — so for a
#   CREDIT vertical, which profits as the mark FALLS, the favourable extreme is
#   `mae_premium`. Read from source, not recalled. With the debit convention a
#   credit that tightened from 1.30 to 0.90 (a +31% winner) scores as NEVER
#   GREEN, and the screen would then hand back a confident, inverted answer
#   about what makes a credit entry work. r214 found this same inversion in
#   query.py's unrealized line.
#
# 🔑 V1 PLANTS A SEPARATION AND REQUIRES THE SCREEN TO FIND IT, and plants
#   noise beside it and requires the screen NOT to. A screener that cannot tell
#   a planted signal from planted noise cannot tell a real one.
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
    sp = u.spec_from_file_location(
        "sv", os.path.join(_root, "tests", "screen_entry_vectors.py"))
    m = u.module_from_spec(sp)
    try:
        sp.loader.exec_module(m)
    except SystemExit:
        pass
    m.WCACHE.WR._client = lambda *a, **k: _S3(store)
    buf, note = io.StringIO(), ""
    devnull = open(os.devnull)
    old, sys.stdin = sys.stdin, devnull
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            m.main(["x"] + args)
    except SystemExit as exc:
        note = str(exc.code) if exc.code not in (0, None) else ""
    finally:
        sys.stdin = old
        devnull.close()
    return buf.getvalue() + note, m


def _trade(tid, strat, e, mfe, mae, credit=0, setup="x"):
    return {"trade_id": tid, "strategy": strat, "setup_type": setup,
            "status": "closed", "entry_time": "2026-08-31 12:00:00",
            "exit_time": "2026-08-31 12:30:00", "entry_premium": e,
            "exit_premium": mfe, "contracts": 10, "pnl_usd": 1.0,
            "pnl_pct": 0.1, "exit_reason": "x", "mfe_premium": mfe,
            "mfe_bars": 4, "mae_premium": mae, "mae_bars": 2,
            "credit_received": credit, "spread_width": 0}


def _store(trades, snaps):
    st = {}
    for n, r in enumerate(trades):
        st[f"raw/trades/dt=2026-08-31/sym=QQQ/{n}.json"] = json.dumps(
            {"symbol": "QQQ", "record": r}).encode()
    if snaps:
        st["raw/derived_fire_snapshot/dt=2026-08-31/sym=QQQ/1.json"] = json.dumps(
            {"symbol": "QQQ", "record": snaps}).encode()
    return st


def main():
    import random
    random.seed(11)
    base = ["--from", "2026-08-31", "--to", "2026-08-31"]

    # ── V1 — a planted separation is found; planted noise is not ────────
    tr, sn = [], []
    for i in range(60):
        g = i % 2 == 0
        tr.append(_trade(f"t{i}", "RunawayContinuation", 1.00,
                         1.30 if g else 1.02, 0.80))
        sn.append({"trade_id": f"t{i}", "fired_ts": 1.0, "payload": json.dumps(
            {"adx": (35 + random.random() * 5) if g else (15 + random.random() * 5),
             "atr": 1.0 + random.random(),
             "session_fraction_remaining": 0.6, "schema": "v1"})})
    out, _m = _run(_store(tr, sn), base + ["--type", "RunawayContinuation"])
    rows = {}
    for ln in out.splitlines():
        p = ln.split()
        if len(p) >= 6 and p[0] in ("adx", "atr", "session_fraction_remaining"):
            rows[p[0]] = float(p[1])
    check("V1 the planted separating vector ranks at the top",
          rows.get("adx", 0) > 0.9, f"adx AUC {rows.get('adx')}")
    # 🔴 ORDINAL, NOT ABSOLUTE — AND THE FIXTURE IS WHY. `atr` here is PURE
    # NOISE (uniform random, independent of the outcome) and it scored AUC
    # 0.69 on 30 against 30. That is not a flaw in the screen; it is the exact
    # arithmetic the report warns about, reproduced on demand. An absolute
    # tolerance would have to be so loose it proved nothing, so the check is
    # that the planted SIGNAL outranks the planted NOISE by a wide margin.
    # ⚠️ AND IT IS THE STRONGEST ARGUMENT AGAINST ACTING ON THIS REPORT
    # DIRECTLY: a 0.69 here means a 0.69 in the real output can be nothing.
    check("V1b the planted signal outranks planted noise by a wide margin",
          rows.get("adx", 0) - rows.get("atr", 0.5) > 0.25,
          f"adx {rows.get('adx')} vs pure-noise atr {rows.get('atr')} "
          f"— noise reaching {rows.get('atr')} on 30v30 is the point")

    # ── V2 — A CREDIT THAT TIGHTENED IS GREEN ───────────────────────────
    # 🔴 mfe_premium is the HIGHEST mark. A credit entered at 1.30 that fell to
    # 0.90 is a +31% WINNER, and its favourable extreme is mae_premium. With
    # the debit convention it would read (1.36-1.30)/1.30 = +5% at best and be
    # mislabelled — inverting the entire screen for every credit strategy.
    tr2, sn2 = [], []
    for i in range(40):
        g = i % 2 == 0
        tr2.append(_trade(f"c{i}", "SweepCreditSpread", 1.30,
                          1.36, 0.90 if g else 1.29,
                          credit=1.30, setup="sweep_credit"))
        sn2.append({"trade_id": f"c{i}", "fired_ts": 1.0,
                    "payload": json.dumps({"adx": 30.0 if g else 12.0})})
    out2, _ = _run(_store(tr2, sn2), base + ["--type", "SweepCreditSpread"])
    check("V2 a credit vertical that tightened counts as GREEN",
          "GREEN (>= 5%)      : 20" in out2,
          [l for l in out2.splitlines() if "GREEN (" in l][:1])

    # ── V3 — THE JOIN RATE IS THE FIRST FINDING ─────────────────────────
    # ⚠️ fire_snapshot only writes when a trade FIRES, and the warehouse holds
    # 165 objects over 6 days against 250 closed trades. A screen over a third
    # of the book is a different claim from a screen over the book, and saying
    # so is not a caveat — it is the result's scope.
    out3, _ = _run(_store(tr[:60], sn[:20]), base + ["--type", "RunawayContinuation"])
    check("V3 a partial join is reported and flagged, not silently narrowed",
          "NO snapshot (cannot screen)" in out3
          and "THE SAMPLE IS THE JOINED SUBSET" in out3)

    # ── V4 — the screen declares itself a screen ────────────────────────
    check("V4 the number screened is printed beside the results",
          "VECTORS SCREENED AGAINST A LIMITING CLASS" in out
          and "NOTHING HERE IS A FINDING" in out)

    # ── V5 — too few to rank refuses rather than ranking ────────────────
    tr5 = [_trade(f"s{i}", "IronCondorStrategy", 1.0, 1.3 if i < 3 else 1.01, 0.9)
           for i in range(12)]
    sn5 = [{"trade_id": f"s{i}", "fired_ts": 1.0,
            "payload": json.dumps({"adx": 20.0 + i})} for i in range(12)]
    out5, _ = _run(_store(tr5, sn5), base + ["--type", "IronCondorStrategy"])
    check("V5 a limiting class under 10 refuses to rank anything",
          "TOO FEW TO RANK ANYTHING" in out5)

    print()
    if _fails:
        print(f"FAILED {len(_fails)}: " + ", ".join(_fails))
        return 1
    print("test_screen_entry_vectors: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
