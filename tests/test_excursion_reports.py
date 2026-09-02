#!/usr/bin/env python3
# day_trader_pro/tests/test_excursion_reports.py — v1.1
# v1.1 (2026-09-02) — dtp r247. E1b RE-DERIVED and E1d added. E1b required
#   the fav-first / heat-first split AND ITS WIN RATE; r247 removed that panel
#   as near-tautological — a winner's favourable peak IS essentially its exit
#   — so E1b now REQUIRES THE PANEL TO CARRY NO WIN RATE, which stops a later
#   edit quietly reintroducing a predictor claim the data cannot support.
#   E1d pins that the S3 pull happens ONCE and the menu loops.
# v1.0 (2026-09-01) — dtp r244. BOTH REPORTS RECOVER A PLANTED ANSWER.
#
# 🔴 E3 IS THE ONE THAT MATTERS. Credit verticals profit as the mark FALLS, so
#   their FAVOURABLE excursion is the LOW mark and their ADVERSE is the HIGH —
#   the mirror of a debit. r214 found this exact sign inverted in query.py's
#   unrealized line. Get it wrong here and every sweep and TCS row reports its
#   best moment as its worst, which would make the stop look perfectly placed
#   on precisely the trades it was cutting.
#
# 🔑 E1/E2 plant a known split — winners peak early and take 18% heat, losers
#   take 40% and peak late — and require the reports to recover it. A report
#   that cannot separate a planted good entry from a planted bad one cannot
#   separate a real one.
import io, json, os, sys, contextlib

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
_fails = []


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + (f"   [{detail}]" if detail else ""))
    if not ok:
        _fails.append(name)


def _store(extra=()):
    def ts(h, m): return f"2026-08-31 {h:02d}:{m:02d}:00"
    recs = []
    for i in range(40):
        won = i % 2 == 0
        recs.append({"trade_id": f"t{i}", "strategy": "TrendCreditSpread",
                     "setup_type": "tcs", "status": "closed",
                     "entry_time": ts(12, i % 60), "exit_time": ts(13, i % 60),
                     "entry_premium": 1.00,
                     "exit_premium": 1.35 if won else 0.60, "contracts": 10,
                     "pnl_usd": 300 if won else -250,
                     "pnl_pct": 30 if won else -25,
                     "exit_reason": "target_hit" if won else "hard_stop_25%",
                     "mfe_premium": 1.35 if won else 1.05,
                     "mfe_bars": 4 if won else 9,
                     "mae_premium": 0.82 if won else 0.60,
                     "mae_bars": 9 if won else 3,
                     "credit_received": 0, "spread_width": 0})
    recs.extend(extra)
    return {"raw/trades/dt=2026-08-31/sym=QQQ/1.json":
            json.dumps({"symbol": "QQQ", "record": recs}).encode()}


def _run(tool, store, args):
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
    sp = u.spec_from_file_location("t", os.path.join(_root, "tools", tool))
    m = u.module_from_spec(sp)
    try:
        sp.loader.exec_module(m)
    except SystemExit:
        pass
    m.WCACHE.WR._client = lambda *a, **k: _S3(store)
    # ⚠️ STDIN IS CLOSED, DELIBERATELY. Without this the first run of this file
    # BLOCKED on `input()` reading the live terminal — a test that hangs is
    # worse than one that fails, because it stalls the suite with no verdict.
    # ⚠️ AND THE SystemExit MESSAGE IS RETURNED, not discarded: catching
    # SystemExit swallows the text the interpreter would have printed, so a
    # check on a refusal message would look at an empty buffer and fail for
    # the wrong reason.
    buf, note = io.StringIO(), ""
    devnull = open(os.devnull, "r")
    old_stdin, sys.stdin = sys.stdin, devnull
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            m.main(["x"] + args)
    except SystemExit as exc:
        note = str(exc.code) if exc.code not in (0, None) else ""
    finally:
        sys.stdin = old_stdin
        devnull.close()
    return buf.getvalue() + note


def main():
    base = ["--from", "2026-08-31", "--to", "2026-08-31"]

    # ── E1 — the entry report separates the planted populations ─────────
    t = _run("entry_report.py", _store(), base + ["--type", "TrendCreditSpread"])
    # ⚠️ PARSED, NOT STRING-MATCHED. The first draft asserted the literal "12%"
    # and went red when the fixture's loser MFE changed — a check pinned to a
    # fixture's arithmetic rather than to the claim it is making (§24, the same
    # class as a canary pinned to a version string).
    def _row(text, label):
        for ln in text.splitlines():
            p = ln.split()
            if len(p) >= 4 and p[0] == label:
                return [float(x.rstrip("%")) for x in p[2:4]]
        return None
    won_r, lost_r = _row(t, "won"), _row(t, "lost")
    check("E1 winners' favourable excursion beats losers'",
          won_r and lost_r and won_r[0] > lost_r[0],
          f"won fav {won_r and won_r[0]}  lost fav {lost_r and lost_r[0]}")
    check("E1c and losers took more heat than winners",
          won_r and lost_r and lost_r[1] > won_r[1],
          f"won adv {won_r and won_r[1]}  lost adv {lost_r and lost_r[1]}")
    # 🔴 E1b USED TO REQUIRE THE fav-first / heat-first SPLIT AND ITS WIN
    # RATE. r247 removed that panel because it was near-tautological — a
    # winner's favourable peak IS essentially its exit — and the operator's
    # real run made it obvious: 0% for fav-first against 56% for heat-first,
    # a striking number that mostly restates the outcome. The check now
    # REQUIRES THE PANEL TO CARRY NO WIN RATE, so a future edit cannot quietly
    # reintroduce a predictor claim the data cannot support.
    check("E1b the shape panel is descriptive and shows no win rate",
          "THE SHAPE OF THE TRADE" in t and "bars to peak" in t
          and "NO WIN RATE IS SHOWN" in t
          and "fav first" not in t and "heat first" not in t)

    # ── E1d — the menu loops off ONE pull ───────────────────────────────
    # ⚠️ Operator: return to the numbered menu without re-running the report.
    # The S3 read is 49 seconds; repeating it to look at a second strategy is
    # the cost this removes.
    src = open(os.path.join(_root, "tools", "entry_report.py"),
               encoding="utf-8").read()
    check("E1d the pull happens once and the menu loops",
          "while True:" in src and "RP.QUIT" in src
          and src.count("RP.load_trades") == 1)

    # ── E2 — the sample limit is stated BEFORE the numbers ─────────────
    # The operator's question was whether there is enough data yet; a report
    # that answers it only in a footnote has not answered it.
    check("E2 the limiting outcome class is named up front",
          "LIMITING SAMPLE IS THE SMALLER OUTCOME CLASS" in t
          and t.index("LIMITING SAMPLE") < t.index("WHAT THE ENTRY OFFERED"))

    # ── E3 — CREDIT VERTICALS ARE SIGNED THE OTHER WAY ─────────────────
    # 🔴 A credit that tightened from 1.30 to 0.90 WON. Its mae_premium (0.90)
    # is its BEST moment and its mfe_premium (1.70) its worst. If the report
    # used the debit convention it would score this trade as never-favourable.
    credit = [{"trade_id": "c1", "strategy": "SweepCreditSpread",
               "setup_type": "sweep", "status": "closed",
               "entry_time": "2026-08-31 12:00:00",
               "exit_time": "2026-08-31 13:00:00",
               "entry_premium": 1.30, "exit_premium": 0.90, "contracts": 5,
               "pnl_usd": 200, "pnl_pct": 31, "exit_reason": "target_hit",
               "mfe_premium": 1.70, "mfe_bars": 8,
               "mae_premium": 0.90, "mae_bars": 3,
               "credit_received": 1.30, "spread_width": 2.5}]
    tc = _run("entry_report.py", _store(credit),
              base + ["--type", "SweepCreditSpread"])
    # favourable = (1.30-0.90)/1.30 = 31%; the debit convention would give
    # (1.70-1.30)/1.30 = 31% too — so assert on the NEVER-FAVOURABLE count,
    # which the wrong sign cannot get right for a winner.
    check("E3 a winning credit vertical is not scored never-favourable",
          "never favourable (peak <= +2% of premium): 0" in tc,
          "the debit convention would invert its best and worst moment")

    # ── E4 — the stop report finds the cents problem ────────────────────
    tiny = [{"trade_id": f"b{i}", "strategy": "GEXPinButterfly",
             "setup_type": "gex", "status": "closed",
             "entry_time": "2026-08-31 12:00:00",
             "exit_time": "2026-08-31 12:01:00", "entry_premium": 0.17,
             "exit_premium": 0.13, "contracts": 30, "pnl_usd": -120,
             "pnl_pct": -25, "exit_reason": "hard_stop_25%",
             "mfe_premium": 0.175, "mfe_bars": 1, "mae_premium": 0.128,
             "mae_bars": 1, "credit_received": 0, "spread_width": 1.0}
            for i in range(12)]
    s = _run("stop_report.py", _store(tiny), base + ["--type", "ALL"])
    check("E4 the stop report prices the stop in cents, not percent",
          "under $0.25" in s and "0.043" in s,
          "25% of $0.17 is 4.3c — the 2026-09-01 butterfly failure")
    check("E4b and it reports the heat winners survived",
          "HEAT THE WINNERS SURVIVED" in s and "18%" in s)

    # ── E5 — a closed stdin is refused by name, not defaulted ──────────
    check("E5 non-interactive without --type is refused, not defaulted",
          "no input available" in _run("stop_report.py", _store(), base),
          "defaulting to ALL would run a different report than was asked for")

    print()
    if _fails:
        print(f"FAILED {len(_fails)}: " + ", ".join(_fails))
        return 1
    print("test_excursion_reports: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
