#!/usr/bin/env python3
"""
tests/backtest_sweep.py — v1.3 — 2026-07-31 (+--json pooling for item AH)
v1.3 — `--json PATH` passes `--all --json` through to harness v1.2, pooling every
       fired trade across all 29 symbols into one jsonl. Item AH cannot be
       answered without it: the harness caps its text listing at 8 trades per
       symbol, and the first 8 chronologically is not a random sample.

Run tests/backtest_harness.py across EVERY symbol that has harvested OHLC, and
print one comparison table.

WHY
    The harness is single-symbol. On 2026-07-30 a single CVX run produced a
    striking result — ORB fired 10 times, 7 of them under a RANGING label, with
    -1.56R expectancy and 8 of 10 exits at STRUCTURE_STOP. That is a mechanism
    worth taking seriously (an opening-range BREAKOUT firing inside a
    mean-reverting regime), but it is one symbol and ten trades, and CVX happened
    to be 51% RANGING over the window — unusually range-bound. The finding could
    equally be describing CVX. Twenty-nine symbols answers it; one does not.

WHY IT SPLICES EVERY SESSION, NOT JUST THE LAST TWO
    backtest_harness's own header: intraday frames (1m/5m/15m) are SESSION-SCOPED
    and reset each day, but HIGHER timeframes are CONTINUOUS — "on one session 1h
    is starved and direction collapses to NEUTRAL. ~15+ sessions gives 1h real
    depth." Feed it two days and every regime label is computed on starved HTF,
    which is precisely the input that decides TRENDING vs RANGING. So the splice
    is the full corpus; the recent sessions appear inside it.

WHY NOT ONE BIG CROSS-SYMBOL TAPE
    Tempting, since the engines are mostly symbol-agnostic — they read bar
    relationships, not tickers. But the HTF series is continuous, so splicing
    CVX at $195 onto QQQ at $560 puts a 65% step inside the exact 1h/1d window
    the multi-day splice exists to build. Per symbol, pooled after.

OUTPUT
    Full harness output per symbol -> <out>/backtest_<SYM>_<date>.txt
    A summary table across all symbols, and an ORB-by-regime pooled roll-up,
    which is the AH question.

USAGE
    python3 tests/backtest_sweep.py
    python3 tests/backtest_sweep.py --symbols CVX,QQQ,SPX
    python3 tests/backtest_sweep.py --since 2026-07-16

Read-only against the OHLC archive. Writes only into --out.
"""

import argparse
import collections
import glob
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OHLC_ROOT = os.environ.get("DTP_OHLC_ROOT", os.path.join(REPO, "ohlc"))
OTV3 = os.environ.get("DTP_OTV3_DIR", os.path.expanduser("~/options-trader-v3"))


def find_vix():
    """The harness needs a 1m VIX CSV. devtools 51 writes ^VIX_1m_30d.csv."""
    for pat in ("^VIX_1m_30d.csv", "*VIX*1m*.csv", "*vix*.csv"):
        hits = sorted(glob.glob(os.path.join(REPO, pat)))
        if hits:
            return hits[0]
    return None


def sessions_for(sym, since=None):
    files = sorted(glob.glob(os.path.join(OHLC_ROOT, "*", f"{sym}_ohlc_*.csv")))
    if since:
        files = [f for f in files if os.path.basename(os.path.dirname(f)) >= since]
    return files


def discover(since=None):
    syms = set()
    for f in glob.glob(os.path.join(OHLC_ROOT, "*", "*_ohlc_*.csv")):
        base = os.path.basename(f)
        m = re.match(r"^([A-Z.^]+)_ohlc_\d{4}-\d{2}-\d{2}\.csv$", base)
        if m:
            syms.add(m.group(1))
    return sorted(s for s in syms if sessions_for(s, since))


def splice(sym, files, dest):
    """Header from the first file, data rows from all, in date order."""
    with open(dest, "w") as out:
        with open(files[0]) as fh:
            head = fh.readline()
        out.write(head)
        rows = 0
        for f in files:
            with open(f) as fh:
                fh.readline()                       # skip each header
                for line in fh:
                    if line.strip():
                        out.write(line)
                        rows += 1
    return rows


# ── harness output parsing ───────────────────────────────────────────────────
RX = {
    "sessions": re.compile(r"—\s*(\d+)\s+sessions"),
    "orb_line": re.compile(r"setups detected:\s*(\d+)\s+fired:\s*(\d+)\s+"
                           r"blocked by regime gate:\s*(\d+)"),
    "exp": re.compile(r"underlying expectancy:\s*([-+]?[\d.]+)R"),
    "exits": re.compile(r"exits:\s+(.*)"),
}


def parse(text):
    d = {"sessions": None, "setups": 0, "fired": 0, "blocked": 0,
         "exp": None, "exits": "", "regime_mix": {}, "orb_by_regime": {}}
    m = RX["sessions"].search(text)
    if m:
        d["sessions"] = int(m.group(1))
    m = RX["orb_line"].search(text)
    if m:
        d["setups"], d["fired"], d["blocked"] = (int(x) for x in m.groups())
    m = RX["exp"].search(text)
    if m:
        d["exp"] = float(m.group(1))
    m = RX["exits"].search(text)
    if m:
        d["exits"] = m.group(1).strip()

    # REGIME DISTRIBUTION block
    blk = text.split("REGIME DISTRIBUTION")
    if len(blk) > 1:
        for ln in blk[1].split("\n")[1:12]:
            mm = re.match(r"\s+([A-Z_]+)\s+(\d+)\s+(\d+)%", ln)
            if mm:
                d["regime_mix"][mm.group(1)] = int(mm.group(3))

    # v1.1 — STRATEGY ATTEMPTS block (harness v1.1). Occurrence, not P&L.
    d["strategies"] = {}
    blk = text.split("STRATEGY ATTEMPTS")
    if len(blk) > 1:
        for ln in blk[1].split("\n")[1:14]:
            mm = re.match(r"\s+(\w+)\s+evals\s+(\d+)\s+setups\s+(\d+)\s*\("
                          r"\s*([\d.]+)%\)\s+valid\s+(\d+)\s+invalid\s+(\d+)"
                          r"\s+raised\s+(\d+)", ln)
            if mm:
                d["strategies"][mm.group(1)] = {
                    "evals": int(mm.group(2)), "setups": int(mm.group(3)),
                    "valid": int(mm.group(5)), "invalid": int(mm.group(6)),
                    "raised": int(mm.group(7))}

    # "fired under which regime label:" block — the AH question
    blk = text.split("fired under which regime label")
    if len(blk) > 1:
        for ln in blk[1].split("\n")[1:10]:
            mm = re.match(r"\s+([A-Z_]+)\s+(\d+)\s*$", ln)
            if mm:
                d["orb_by_regime"][mm.group(1)] = int(mm.group(2))
            elif ln.strip() and not ln.startswith("  "):
                break
    return d


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="", help="comma list; default = all found")
    ap.add_argument("--since", default="", help="only sessions on/after YYYY-MM-DD")
    ap.add_argument("--vix", default="", help="1m VIX csv (default: auto-find)")
    ap.add_argument("--out", default=os.path.join(REPO, "reports", "backtests"))
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--json", default="",
                    help="pool EVERY fired trade across all symbols into this "
                         "jsonl (harness v1.2 --all/--json). This is what item "
                         "AH needs: per-trade R by regime, pooled, untruncated.")
    a = ap.parse_args(argv[1:])

    vix = a.vix or find_vix()
    if not vix or not os.path.isfile(vix):
        print("No 1m VIX csv found. Run devtools 51 (default ^VIX), then re-run")
        print(f"or pass --vix <path>. Looked in {REPO}")
        return 2

    harness = os.path.join(OTV3, "tests", "backtest_harness.py")
    if not os.path.isfile(harness):
        print(f"harness not found at {harness} — set DTP_OTV3_DIR")
        return 2

    since = a.since or None
    syms = ([s.strip().upper() for s in a.symbols.split(",") if s.strip()]
            if a.symbols else discover(since))
    if not syms:
        print(f"no symbols with OHLC under {OHLC_ROOT}")
        return 2

    os.makedirs(a.out, exist_ok=True)
    if a.json and os.path.exists(a.json):
        # The harness APPENDS. Truncate once here rather than in the harness, so
        # a partial sweep can be resumed by omitting this flag on the re-run.
        os.remove(a.json)
        print(f"  (removed existing {a.json} — harness appends)")
    tmpdir = os.path.join(a.out, "_tape")
    os.makedirs(tmpdir, exist_ok=True)
    print(f"symbols: {len(syms)}   vix: {os.path.basename(vix)}   out: {a.out}")

    rows, failures, degraded = [], [], []
    pooled_fired = collections.Counter()
    pooled_mix = collections.Counter()
    pooled_strat = collections.defaultdict(collections.Counter)

    for i, sym in enumerate(syms, 1):
        files = sessions_for(sym, since)
        if not files:
            continue
        tape = os.path.join(tmpdir, f"{sym}_multi.csv")
        nrows = splice(sym, files, tape)
        print(f"  [{i:>2}/{len(syms)}] {sym:<6} {len(files):>3} sessions "
              f"{nrows:>6} bars … ", end="", flush=True)
        try:
            proc = subprocess.run(
                [sys.executable, harness, "--symbol", tape, "--vix", vix]
                + (["--all", "--json", a.json] if a.json else []),
                capture_output=True, text=True, timeout=a.timeout, cwd=OTV3,
                env={**os.environ, "PYTHONPATH": OTV3})
        except subprocess.TimeoutExpired:
            print("TIMEOUT")
            failures.append((sym, "timeout"))
            continue
        out = (proc.stdout or "") + (proc.stderr or "")
        with open(os.path.join(a.out, f"backtest_{sym}.txt"), "w") as fh:
            fh.write(out)
        if proc.returncode != 0 and "BACKTEST" not in out:
            first = next((l for l in out.split("\n") if l.strip()), "")
            print(f"rc={proc.returncode} {first[:50]}")
            failures.append((sym, first[:70]))
            continue
        d = parse(out)
        d["sym"] = sym
        # v1.2 — a DEGRADED run must never look like a clean one. The first
        # sweep (2026-07-30) had the census disabled on all 29 symbols
        # (ModuleNotFoundError: tastytrade under control's venv); the harness
        # said so per symbol, but this file printed no census section at all —
        # indistinguishable from "the section exists and is all zeros".
        _dis = re.search(r"census disabled — (.+?)\)", out)
        if _dis:
            degraded.append((sym, _dis.group(1)[:60]))
        rows.append(d)
        pooled_fired.update(d["orb_by_regime"])
        for _n, _v in d.get("strategies", {}).items():
            for _k in ("evals", "setups", "valid", "invalid", "raised"):
                pooled_strat[_n][_k] += _v[_k]
        for k, v in d["regime_mix"].items():
            pooled_mix[k] += v
        print(f"{d['fired']} fired  exp {d['exp'] if d['exp'] is not None else '?'}R")

    # ── summary ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 86)
    print("  ORB PER SYMBOL")
    print("=" * 86)
    print(f"  {'SYM':<7}{'SESS':>5}{'SETUP':>7}{'FIRED':>7}{'BLKD':>6}"
          f"{'EXPECT':>9}   {'TOP REGIME (share of evals)':<28}")
    for d in sorted(rows, key=lambda r: (r["exp"] is None, r["exp"] or 0)):
        top = sorted(d["regime_mix"].items(), key=lambda kv: -kv[1])[:2]
        tops = " ".join(f"{k[:9]}{v}%" for k, v in top)
        exp = f"{d['exp']:+.2f}R" if d["exp"] is not None else "    n/a"
        print(f"  {d['sym']:<7}{d['sessions'] or 0:>5}{d['setups']:>7}"
              f"{d['fired']:>7}{d['blocked']:>6}{exp:>9}   {tops:<28}")

    tot_fired = sum(d["fired"] for d in rows)
    exps = [d["exp"] for d in rows if d["exp"] is not None]
    if exps:
        print(f"\n  totals: {len(rows)} symbols · {tot_fired} ORB trades · "
              f"mean expectancy {sum(exps)/len(exps):+.2f}R "
              f"(across {len(exps)} symbols that fired)")
    else:
        print(f"\n  totals: {len(rows)} symbols · {tot_fired} ORB trades · "
              f"no expectancy reported (no symbol fired)")

    print("\n" + "-" * 86)
    print("  ORB FIRED UNDER WHICH REGIME — POOLED (this is the AH question)")
    print("-" * 86)
    tot = sum(pooled_fired.values()) or 1
    for rg, n in pooled_fired.most_common():
        share_of_evals = (pooled_mix.get(rg, 0) / max(1, len(rows)))
        print(f"    {rg:<20}{n:>5} trades  {100.0*n/tot:>5.1f}% of fires"
              f"   (regime was ~{share_of_evals:.0f}% of evals)")
    print("\n  Read: if ORB fires disproportionately in RANGING RELATIVE to how")
    print("  often RANGING occurs, that is selection, not just exposure. If the")
    print("  two shares track each other, ORB is simply firing where the tape is.")

    if degraded:
        print("\n" + "!" * 86)
        print(f"  CENSUS DISABLED on {len(degraded)}/{len(syms)} symbols — the "
              f"non-ORB numbers below are INCOMPLETE or absent")
        print(f"    reason: {degraded[0][1]}")
        print(f"  ORB results are unaffected. Fix the import and re-run before "
              f"reading any strategy attempt figure.")
        print("!" * 86)

    if pooled_strat:
        print("\n" + "-" * 86)
        print("  NON-ORB STRATEGY ATTEMPTS — POOLED (occurrence, NOT P&L)")
        print("-" * 86)
        print(f"    {'STRATEGY':<16}{'EVALS':>8}{'SETUPS':>8}{'RATE':>8}"
              f"{'VALID':>8}{'INVALID':>9}{'RAISED':>8}")
        for n, c in sorted(pooled_strat.items()):
            rate = 100.0 * c["setups"] / max(1, c["evals"])
            print(f"    {n:<16}{c['evals']:>8}{c['setups']:>8}{rate:>7.2f}%"
                  f"{c['valid']:>8}{c['invalid']:>9}{c['raised']:>8}")
        print("\n  INVALID is the one to watch — a strategy returning a signal")
        print("  that fails is_valid() is silently untradeable, which is exactly")
        print("  how continuation ran for weeks with strike=0. RAISED is a defect.")
        print("  Butterfly is absent by design: it needs a GEX pin.")

    if failures:
        print(f"\n  {len(failures)} symbol(s) failed:")
        for sym, why in failures:
            print(f"    {sym:<7} {why}")
    print(f"\n  full output per symbol: {a.out}/backtest_<SYM>.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
