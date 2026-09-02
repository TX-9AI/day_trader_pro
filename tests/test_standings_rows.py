#!/usr/bin/env python3
# day_trader_pro/tests/test_standings_rows.py — v1.3
# v1.3 (2026-09-02) — dtp r249. S10 now passes the path AS A TILDE with a fake
#   HOME, because REMOTE_DB is "~/..." and Python does not expand it — the
#   shell had been doing that silently for months. S12 GENERATES a real
#   traceback and requires the picked line to name the fault: it chose the
#   caret at v1.1 and the traceback HEADER at r248, twice hiding the answer.
# v1.2 (2026-09-02) — dtp r248. S10-S12: the query is EXECUTED through a real
#   shell against a real sqlite, the payload is checked for metacharacters,
#   the connection is proven read-only, and the error line is required to be
#   the named fault rather than the last line. S9 stubbed ssh_run, so the SQL
#   was never run at all and this file stayed green while all fifteen boxes
#   returned a parse caret.
# v1.1 (2026-09-01) — dtp r237. 🔴 S9 ADDED: THE LIVE PATH IS EXECUTED.
#   Every case in v1.0 ran under `config.set_mock(True)`, so all eight took the
#   `_mock_query` branch and the REAL `_query` was never called. r236 changed
#   `_query`'s signature, updated the mock call site and missed the live one,
#   and this file stayed green over a report that raised TypeError on its first
#   box. A test that only exercises the simulated path certifies the simulated
#   path.
#   ⚠️ SAME SHAPE AS r195's STANDING OFFER, where the checks drove
#   `resting_orders` directly and never went through `_place_single_leg` in
#   paper — so the whole mechanism was unreachable behind a green board.
# v1.0 (2026-09-01) — dtp r236. THE ROLLUP'S ROWS, AND THE TWO SIGNS.
#
# Operator, 2026-09-01: show what the open positions ARE, and the day's closed
# trades below them, ordered by time.
#
# 🔴 THE CHECK THAT CARRIES THE WEIGHT IS S2. A credit vertical's
#   `current_premium` is the spread's CURRENT VALUE and the position profits as
#   that FALLS, so its P&L is (credit - now) — the mirror of a debit's
#   (now - cost). otv4's query.py:268 applies the debit formula to everything,
#   so its Unrealized line is sign-inverted on every credit spread (filed
#   RPT.6). Copying that to make the two reports agree would have been agreeing
#   on the wrong number.
#
# Run: python3 tests/test_standings_rows.py

import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)

_fails = []


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + (f"   [{detail}]" if detail else ""))
    if not ok:
        _fails.append(name)


def main():
    import config
    config.set_mock(True)
    import standings as S

    # ⚠️ DEGRADE TO A NAMED FAILURE, NEVER AN AttributeError. r192: "the
    # checker crashed" and "the invariant is violated" must not look alike —
    # at r235 this file died on `S.open_pnl` missing and printed a traceback
    # with ZERO failing lines, which reads to a grep as a clean run.
    _missing = [n for n in ("open_pnl", "_et_offset", "_sql", "_abbr")
                if not hasattr(S, n)]
    if _missing:
        for n in _missing:
            check(f"S0 standings.{n} exists", False, "not implemented")
        print()
        print(f"FAILED {len(_fails)}: standings is pre-r236 "
              f"(missing {', '.join(_missing)})")
        return 1

    # ── S1 — a DEBIT gains when the mark rises ──────────────────────────
    # ⚠️ TOLERANCE, NOT EQUALITY. (0.55-0.42)*12*100 is 156.00000000000009 in
    # binary floating point; an exact-match assertion here fails on the
    # arithmetic rather than on the rule, which is a red that teaches you to
    # skip reds.
    _d = S.open_pnl("0.42", "0.55", "12", "0")
    check("S1 a debit's open P&L is (now - cost)",
          _d is not None and abs(_d - (0.55 - 0.42) * 12 * 100) < 1e-6, str(_d))

    # ── S2 — a CREDIT gains when the mark FALLS ─────────────────────────
    credit_win = S.open_pnl("1.30", "0.90", "5", "1.30")
    credit_lose = S.open_pnl("1.30", "1.70", "5", "1.30")
    check("S2 a credit vertical's open P&L is (credit - now), not the mirror",
          credit_win > 0 and credit_lose < 0
          and abs(credit_win - (1.30 - 0.90) * 5 * 100) < 1e-6,
          f"tighter={credit_win} wider={credit_lose}")

    # ── S3 — an unmarked position is UNMEASURED, never zero ─────────────
    check("S3 no live mark yields None, not a fabricated 0.00",
          S.open_pnl("0.42", "0", "12", "0") is None
          and S.open_pnl("0.42", None, "12", "0") is None)

    # ── S4 — the session offset follows the tz database ─────────────────
    # 🔴 v1.0 HARDCODED '-4 hours'. That is EDT: right for eight months of the
    # year and silently wrong for four, and the failure is a report filtering
    # on the wrong day rather than one that errors. r125 caught the identical
    # bug in the otv4 sensor reports.
    _ET = ZoneInfo("US/Eastern")
    real = S.datetime
    try:
        class _Sept:
            @staticmethod
            def now(tz=None): return datetime(2026, 9, 1, 12, 0, tzinfo=tz or _ET)
        S.datetime = _Sept
        edt = S._et_offset()
        class _Dec:
            @staticmethod
            def now(tz=None): return datetime(2026, 12, 1, 12, 0, tzinfo=tz or _ET)
        S.datetime = _Dec
        est = S._et_offset()
    finally:
        S.datetime = real
    check("S4 the offset is -4 in September and -5 in December",
          edt == "-4 hours" and est == "-5 hours", f"Sep={edt!r} Dec={est!r}")

    # ── S5 — closed trades order chronologically ACROSS boxes ───────────
    # ⚠️ THE POINT IS CROSS-BOX. Each box's own rows arrive sorted; interleaving
    # fifteen of them is what makes the list readable, and it is why the
    # Telegram exit alerts cannot be the source — they arrive by delivery order.
    import instance_registry, io, contextlib
    syms = ["QQQ", "SPX", "AMD", "NFLX", "CVX"]
    instance_registry.discover = lambda u=None: (
        {s: {"state": "running", "private_ip": "10.0.0.1"} for s in syms}, None)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        S.run(send=False)
    out = buf.getvalue().splitlines()
    try:
        i = next(n for n, l in enumerate(out) if l.startswith("CLOSED TODAY"))
        times = [l.split()[0] for l in out[i + 2:] if l.startswith("  ")]
    except StopIteration:
        times = []
    check("S5 closed trades render in time order across the whole fleet",
          times and times == sorted(times), str(times))

    # ── S6 — the report fits a phone ────────────────────────────────────
    check("S6 no line exceeds 43 characters (Termius on mobile)",
          max((len(l) for l in out), default=0) <= 43,
          f"widest {max((len(l) for l in out), default=0)}")

    # ── S7 — the menu no longer asks about Telegram ─────────────────────
    # Shape of the CALL, not a mention (§20): the changelog names the prompt
    # while explaining its removal.
    mf = open(os.path.join(_root, "menu_functions.sh"), encoding="utf-8").read()
    body = mf[mf.index("mi_live_p_l_standings_read_only()"):]
    body = body[:body.index("\n}")]
    live = "\n".join(l for l in body.splitlines() if not l.strip().startswith("#"))
    check("S7 the live P&L menu item runs standings with no prompt",
          "read -rp" not in live and "--send" not in live
          and "standings.py" in live, live.strip()[:60])

    # ── S8 — the mock is deterministic ──────────────────────────────────
    a, _ = S._mock_query("QQQ", "2026-09-01")
    b, _ = S._mock_query("QQQ", "2026-09-01")
    check("S8 the mock fleet is stable across calls (crc32, not hash())",
          a["net"] == b["net"] and a["closed"] == b["closed"],
          f"{a['net']} vs {b['net']}")

    # ── S9 — THE LIVE PATH, WITH THE SSH CALL STUBBED ───────────────────
    # 🔑 MOCK_AWS FALSE, so `run()` takes the `_query` branch and the real
    # parser sees a real tab-separated payload. This is the check that would
    # have caught r236: the arity mismatch is a TypeError the moment the
    # branch executes, and no amount of mock coverage reaches it.
    import instance_registry as _ir
    import ssh_util as _ssh
    _tab = chr(9)

    def _fake(ip, cmd, timeout=None):
        rows = [
            _tab.join(["O", f"{_today} 13:05:00", "CVX", "GEXPinButterfly",
                       "0.42", "0.55", "12", "", "0"]),
            _tab.join(["C", f"{_today} 10:00:00", "CVX", "ORBStrategy",
                       "1.20", "1.05", "4", "-60.0", "0"]),
        ]
        return 0, "\n".join(rows) + "\n", ""

    _today = datetime.now(ZoneInfo("US/Eastern")).strftime("%Y-%m-%d")
    _real_mock, _real_ssh = config.MOCK_AWS, _ssh.ssh_run
    try:
        config.MOCK_AWS = False
        _ssh.ssh_run = _fake
        _ir.discover = lambda u=None: (
            {"CVX": {"state": "running", "private_ip": "10.0.0.9"}}, None)
        buf2 = io.StringIO()
        with contextlib.redirect_stdout(buf2):
            S.run(send=False)
        live_out = buf2.getvalue()
        live_err = ""
    except Exception as exc:                                    # noqa: BLE001
        live_out, live_err = "", f"{type(exc).__name__}: {exc}"
    finally:
        config.MOCK_AWS = _real_mock
        _ssh.ssh_run = _real_ssh
    check("S9 the LIVE (non-mock) path runs and parses a real payload",
          not live_err and "OPEN POSITIONS" in live_out
          and "CLOSED TODAY" in live_out and "BFLY" in live_out,
          live_err or live_out.replace("\n", " | ")[:90])

    # ── S10 — THE QUERY IS EXECUTED, NOT JUST BUILT ─────────────────────
    # 🔴 S9 STUBBED ssh_run, SO THE SQL WAS NEVER RUN BY SQLITE AT ALL. It
    # proved the parser handled a canned payload; it could not and did not
    # prove the query was valid or that the command survived transport. On
    # 2026-09-02 ALL FIFTEEN BOXES returned a parse caret and this file was
    # green. A test that stops at the boundary certifies everything up to the
    # boundary — the same shape as r195's standing offer and r236's arity.
    # 🔑 SO THIS BUILDS THE REAL COMMAND AND RUNS IT, against a temp trades.db,
    # through an actual shell — which is where the fault was.
    import base64 as _b64
    import sqlite3 as _sq
    import subprocess
    import tempfile

    _d = tempfile.mkdtemp()
    _db = os.path.join(_d, "trades.db")
    _c = _sq.connect(_db)
    _c.execute("CREATE TABLE trades (symbol TEXT, strategy TEXT, entry_time TEXT,"
               " exit_time TEXT, entry_premium REAL, current_premium REAL,"
               " exit_price REAL, contracts INT, credit_received REAL,"
               " pnl_usd REAL, status TEXT)")
    _c.execute("INSERT INTO trades VALUES ('QQQ','ORBStrategy',"
               "'2026-09-02 14:00:00',NULL,1.2,1.3,NULL,4,0,NULL,'open')")
    _c.execute("INSERT INTO trades VALUES ('QQQ','SweepCreditSpread',"
               "'2026-09-02 13:00:00','2026-09-02 13:30:00',1.30,0,0.90,5,"
               "1.30,200,'closed')")
    _c.commit()
    _c.close()

    # 🔴 THE PATH IS PASSED AS A TILDE, THE WAY THE BOX ACTUALLY HAS IT.
    # `REMOTE_DB` is "~/options-trader/trades.db"; the sqlite3 CLI never had to
    # expand that because the REMOTE SHELL did it, and r248 moved the string
    # into a Python literal where nothing does. Every box failed to open a path
    # that had worked for months. S10 now builds the command with a tilde and a
    # fake HOME, so the expansion is exercised rather than assumed.
    _home = tempfile.mkdtemp()
    os.makedirs(os.path.join(_home, "options-trader"), exist_ok=True)
    _real_db = os.path.join(_home, "options-trader", "trades.db")
    os.replace(_db, _real_db)
    _tilde = "~/options-trader/trades.db"

    _off = S._et_offset()
    _prog = ("import sqlite3,base64,sys,os\n"
             "p=os.path.expanduser(%r)\n"
             "q=base64.b64decode('%s').decode()\n"
             "try:\n"
             "    c=sqlite3.connect('file:'+p+'?mode=ro',uri=True)\n"
             "    sys.stdout.write('\\n'.join(r[0] for r in c.execute(q)))\n"
             "except Exception as e:\n"
             "    sys.stderr.write('DBError: %%s: %%s (path=%%s exists=%%s)'\n"
             "                     %% (type(e).__name__, e, p, os.path.exists(p)))\n"
             "    raise SystemExit(1)\n"
             % (_tilde, _b64.b64encode(S._sql(_off).encode()).decode()))
    _payload = _b64.b64encode(_prog.encode()).decode()
    _cmd = "echo %s | base64 -d | python3 -" % _payload
    _env = dict(os.environ, HOME=_home)
    _r = subprocess.run(["bash", "-c", _cmd], capture_output=True, text=True,
                        env=_env)
    check("S10 the real command runs the real query through a real shell",
          _r.returncode == 0 and _r.stdout.count(chr(9)) >= 8,
          (_r.stderr or "").strip().splitlines()[:1] or f"rows={_r.stdout!r}"[:80])

    # ⚠️ AND THE PAYLOAD CARRIES NO SHELL METACHARACTERS. That is the property
    # doing the work: escaping can be got wrong, having nothing to escape
    # cannot.
    check("S10b the transported payload has nothing to escape",
          not any(ch in _payload for ch in "\"'`$\\|;&<>()"),
          "base64 removes the quoting problem rather than managing it")

    # ── S11 — THE REPORT MUST NOT BE ABLE TO WRITE TO THE BOOK ──────────
    _pw = _prog.replace("c.execute(q)", "c.execute('DELETE FROM trades')")
    _rw = subprocess.run(
        ["bash", "-c", "echo %s | base64 -d | python3 -"
         % _b64.b64encode(_pw.encode()).decode()],
        capture_output=True, text=True, env=_env)
    check("S11 the connection is read-only",
          _rw.returncode != 0 and "readonly" in (_rw.stderr or ""),
          "a report must never be able to write to trades.db")

    # ── S12 — an error surfaces its MESSAGE, not its caret ──────────────
    # 🔴 `[-1]` OF A MULTI-LINE SQLITE ERROR IS THE CARET. All fifteen boxes
    # reported "                    error here ---^" — the report hid its own
    # diagnosis behind its own formatting, and that is what turned a
    # ten-minute fix into a morning.
    _src = open(os.path.join(_root, "standings.py"), encoding="utf-8").read()
    # ── S12 — THE FAILURE LINE, RE-DERIVED TWICE NOW ────────────────────
    # 🔴 THIS PICKED THE WRONG LINE TWICE RUNNING. v1.1 took [-1], which for a
    # multi-line sqlite error is the CARET — fifteen boxes reported
    # "error here ---^". r248 took the FIRST named line and matched
    # "Traceback", which is the HEADER — fifteen boxes reported
    # "Traceback (most recent call last):". Both times the report printed its
    # own formatting instead of its own diagnosis.
    # 🔑 THE MOST SPECIFIC LINE IS LAST IN A TRACEBACK AND FIRST IN A CLI
    # ERROR, so taking the LAST line that NAMES a fault is correct for both.
    # EXECUTED, not read: a real traceback is generated and put through it.
    _pb = _prog.replace("os.path.expanduser(%r)" % _tilde,
                        "os.path.expanduser('~/nope/trades.db')")
    _rb = subprocess.run(
        ["bash", "-c", "echo %s | base64 -d | python3 -"
         % _b64.b64encode(_pb.encode()).decode()],
        capture_output=True, text=True, env=_env)
    _lines = [ln.strip() for ln in (_rb.stderr or "").splitlines() if ln.strip()]
    _named = [ln for ln in _lines
              if ("Error" in ln or "error:" in ln or "Exception" in ln)
              and not ln.startswith("Traceback")]
    _picked = (_named[-1] if _named else (_lines[-1] if _lines else ""))
    check("S12 a real failure surfaces the fault, not the traceback header",
          "unable to open database" in _picked
          and "path=" in _picked and "exists=False" in _picked,
          _picked[:100])
    check("S12b and standings uses that same selection",
          "named[-1] if named else" in _src
          and 'not ln.startswith("Traceback")' in _src)

    print()
    if _fails:
        print(f"FAILED {len(_fails)}: " + ", ".join(_fails))
        return 1
    print("test_standings_rows: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
