#!/usr/bin/env python3
# tests/regime_diary.py — options_trader_v3
# v1.2 — 2026-07-14 — LAYOUT CONSOLIDATION: --harvest default retired in favor
#   of --reports (the replay jsonl lives at reports/regime_replay_<date>.jsonl
#   now); --diary-dir default moves to ~/day_trader_pro/reports. Old flags kept
#   working. Digest logic unchanged.
# v1.1 — 2026-07-12 — LAYER-2 digest (backward compatible) + first push to GitHub
#   (v1.0 lived only on the control box — this file was never in the repo).
#   When a tick log carries "l2" fields (replay_confluence v2.0+), each diary
#   entry gains an "l2" object — emitted-label dominance, label switches vs
#   L1-argmax flips (churn ratio), stale% — and one extra line in the md block.
#   Logs without l2 digest exactly as before; old diary rows are untouched.
# v1.0 — 2026-07-11 — NEW FILE. Rolling Layer-1 regime diary.
#   Reads a day's saved per-tick log (regime_replay_<date>.jsonl), distills it into
#   ONE digest entry, and UPSERTS that entry (by date) into two rolling files:
#       regime_diary.jsonl  — one JSON object per day (machine record)
#       regime_diary.md     — one human-readable block per day (the scroll)
#
#   Server-count AGNOSTIC: it reports whatever symbols the log actually contains
#   (2, 5, 17, all) as a fact — it never assumes a fleet size or reports "missing".
#   One entry per date: re-running a day OVERWRITES that date's entry in place,
#   never duplicates. New date appends; existing date replaces.
#
#   Layer-1 + (optional) Layer-2: reads the tick log and NOTHING else.
#   No trades, no P&L — ever.
#
#   Usage:
#     python -m tests.regime_diary --log  <path/to/regime_replay_<date>.jsonl>
#     python -m tests.regime_diary --date 2026-07-10 --harvest ~/day_trader_pro/data/harvest
#     python -m tests.regime_diary --view [--diary-dir <dir>]   # print the whole diary
#
#   The digest is derived from the same fields the replay report uses, so a diary
#   row and that day's --report-only report always agree.

from __future__ import annotations
import argparse, json, os, sys
from typing import Dict, List, Optional

REGIMES = ("TRENDING_BULL", "TRENDING_BEAR", "RANGING",
           "BREAKOUT_VOLATILE", "COMPRESSION", "SWEEP_REVERSAL")


def _pct(n, d):
    return round(100.0 * n / d, 1) if d else 0.0


def digest_from_log(log_path: str) -> dict:
    """Distill one day's tick log into a diary entry. Reads only what's in the file."""
    recs: List[dict] = []
    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    if not recs:
        raise ValueError(f"empty tick log: {log_path}")

    n = len(recs)
    symbols = sorted({r.get("sym") for r in recs if r.get("sym")})
    # infer the date from the records' filename-independent content if present,
    # else fall back to the filename.
    date = None
    base = os.path.basename(log_path)
    for token in base.replace(".jsonl", "").split("_"):
        if len(token) == 10 and token[4] == "-" and token[7] == "-":
            date = token
            break

    def sc(r, k):
        v = r["scores"].get(k)
        return v if v is not None else 0.0

    # per-regime: % of ticks scoring >0, and % of ticks where it is the argmax (>0)
    dom_counts = {k: 0 for k in REGIMES}
    nz_counts = {k: 0 for k in REGIMES}
    allzero = 0
    for r in recs:
        vals = {k: sc(r, k) for k in REGIMES}
        top = max(vals, key=vals.get)
        if vals[top] > 0:
            dom_counts[top] += 1
        else:
            allzero += 1
        for k in REGIMES:
            if vals[k] > 0:
                nz_counts[k] += 1

    dominance = {k: _pct(dom_counts[k], n) for k in REGIMES}
    nonzero = {k: _pct(nz_counts[k], n) for k in REGIMES}
    allzero_pct = _pct(allzero, n)

    # flat-angle spread (RANGING path, else COMPRESSION path) — the calibration signal
    angles = []
    for r in recs:
        a = r.get("breakdown", {}).get("RANGING", {}).get("angle")
        if a is None:
            a = r.get("breakdown", {}).get("COMPRESSION", {}).get("angle")
        if a is not None:
            angles.append(a)
    angles.sort()
    def q(p):
        return round(angles[min(len(angles) - 1, int(p * len(angles)))], 1) if angles else None
    angle_p50, angle_p90 = q(.50), q(.90)

    # acceptance (mirrors the harness's Tier-A checks, recomputed from the log)
    a1 = all(0.0 <= v <= 1.0 for r in recs for v in r["scores"].values() if v is not None)
    a2 = not any((sc(r, "TRENDING_BULL") > .5 or sc(r, "TRENDING_BEAR") > .5) and sc(r, "RANGING") > .5 for r in recs)
    a3 = not any(sc(r, "BREAKOUT_VOLATILE") > .5 and sc(r, "COMPRESSION") > .5 for r in recs)
    a4 = not any(sc(r, "TRENDING_BULL") > 0 and
                 r["breakdown"].get("TRENDING", {}).get("structure_sequence") == "LH_LL" for r in recs)
    a5 = allzero_pct < 15.0
    checks = {"A1": a1, "A2": a2, "A3": a3, "A4": a4, "A5": a5}
    accept = f"{sum(checks.values())}/5"

    # plain character tag — descriptive only, no thresholds to tune yet
    trend = dominance["TRENDING_BULL"] + dominance["TRENDING_BEAR"]
    flat = dominance["RANGING"] + dominance["COMPRESSION"]
    if trend >= 25:
        tag = "DIRECTIONAL"
    elif dominance["SWEEP_REVERSAL"] >= 10:
        tag = "SWEEP-ACTIVE"
    elif flat >= 60:
        tag = "CHOP"
    else:
        tag = "MIXED"

    entry = {
        "date": date,
        "ticks": n,
        "symbols": symbols,
        "n_symbols": len(symbols),
        "dominance": dominance,
        "nonzero": nonzero,
        "all_zero_pct": allzero_pct,
        "flat_angle_p50": angle_p50,
        "flat_angle_p90": angle_p90,
        "acceptance": accept,
        "acceptance_detail": checks,
        "tag": tag,
    }

    # ── v1.1: LAYER-2 digest (only when the log carries l2 fields) ────────────
    l2recs = [r for r in recs if r.get("l2")]
    if l2recs:
        m = len(l2recs)
        emitted: Dict[str, int] = {}
        for r in l2recs:
            lab = r["l2"].get("regime", "")
            if lab:
                emitted[lab] = emitted.get(lab, 0) + 1
        # switches / L1-argmax flips, counted WITHIN each symbol's own sequence
        by_sym: Dict[str, List[dict]] = {}
        for r in l2recs:
            by_sym.setdefault(r.get("sym", "?"), []).append(r)
        def _top1(r):
            return max(REGIMES, key=lambda k: sc(r, k))
        switches = flips = 0
        for rs in by_sym.values():
            switches += sum(1 for a, b in zip(rs, rs[1:])
                            if a["l2"]["regime"] != b["l2"]["regime"])
            flips += sum(1 for a, b in zip(rs, rs[1:]) if _top1(a) != _top1(b))
        stale_pct = _pct(sum(1 for r in l2recs if r["l2"].get("stale")), m)
        entry["l2"] = {
            "dominance": {k: _pct(v, m) for k, v in emitted.items()},
            "switches": switches,
            "l1_flips": flips,
            "stale_pct": stale_pct,
        }

    return entry


def _md_block(e: dict) -> str:
    d = e["dominance"]
    dom_line = "  ".join(f"{k.split('_')[0][:4]} {d[k]:.0f}%" for k in REGIMES if d[k] > 0) or "—"
    syms = ",".join(e["symbols"])
    if len(syms) > 90:
        syms = syms[:87] + "…"
    block = (
        f"### {e['date']}   [{e['tag']}]   acceptance {e['acceptance']}\n"
        f"- {e['n_symbols']} symbols · {e['ticks']} ticks\n"
        f"- dominance: {dom_line}\n"
        f"- all-zero: {e['all_zero_pct']:.1f}%   flat-angle p50/p90: "
        f"{e['flat_angle_p50']}/{e['flat_angle_p90']}°\n"
        f"- symbols: {syms}\n"
    )
    # v1.1 — one extra line when the day's log carried Layer-2 tracks
    l2 = e.get("l2")
    if l2:
        dom2 = "  ".join(f"{k.split('_')[0][:4]} {v:.0f}%"
                         for k, v in sorted(l2["dominance"].items(), key=lambda kv: -kv[1])) or "—"
        block += (f"- L2: {dom2}   switches {l2['switches']} "
                  f"(L1 flips {l2['l1_flips']})   stale {l2['stale_pct']:.1f}%\n")
    return block


def upsert(entry: dict, diary_dir: str):
    """One entry per date. Re-running a date OVERWRITES its row; never duplicates."""
    os.makedirs(diary_dir, exist_ok=True)
    jsonl = os.path.join(diary_dir, "regime_diary.jsonl")
    md = os.path.join(diary_dir, "regime_diary.md")

    # load existing entries keyed by date (dedup key = date, pure)
    by_date: Dict[str, dict] = {}
    if os.path.isfile(jsonl):
        with open(jsonl) as f:
            for line in f:
                line = line.strip()
                if line:
                    e = json.loads(line)
                    if e.get("date"):
                        by_date[e["date"]] = e

    existed = entry["date"] in by_date
    by_date[entry["date"]] = entry            # set-or-replace

    ordered = [by_date[k] for k in sorted(by_date)]
    tmp = jsonl + ".tmp"
    with open(tmp, "w") as f:
        for e in ordered:
            f.write(json.dumps(e) + "\n")
    os.replace(tmp, jsonl)

    tmp_md = md + ".tmp"
    with open(tmp_md, "w") as f:
        f.write("# Regime Diary — Layer-1 confluence (+ Layer-2 when present), one entry per session\n")
        f.write("# Tape-only. No trades, no P&L. Server-count agnostic (reports what the log holds).\n\n")
        for e in ordered:
            f.write(_md_block(e) + "\n")
    os.replace(tmp_md, md)

    print(f"diary {'updated' if existed else 'appended'}: {entry['date']}  "
          f"[{entry['tag']}]  {entry['n_symbols']} sym  all-zero {entry['all_zero_pct']:.1f}%  "
          f"accept {entry['acceptance']}")
    print(f"  {jsonl}")
    return jsonl, md


def view(diary_dir: str):
    md = os.path.join(diary_dir, "regime_diary.md")
    if not os.path.isfile(md):
        print(f"no diary yet at {md} — run a replay (40/41) to create the first entry")
        return 1
    with open(md) as f:
        sys.stdout.write(f.read())
    return 0


def main():
    ap = argparse.ArgumentParser(description="Rolling regime diary (upsert by date)")
    ap.add_argument("--log", help="path to a regime_replay_<date>.jsonl to digest + upsert")
    ap.add_argument("--date", help="with --harvest: locate the day's log automatically")
    ap.add_argument("--reports", "--harvest", dest="reports",
                    default=os.path.expanduser("~/day_trader_pro/reports"),
                    help="reports root (holds regime_replay_<date>.jsonl)")
    ap.add_argument("--diary-dir", default=os.path.expanduser("~/day_trader_pro/reports"),
                    help="where regime_diary.{jsonl,md} live")
    ap.add_argument("--view", action="store_true", help="print the whole diary and exit")
    args = ap.parse_args()

    if args.view:
        sys.exit(view(args.diary_dir))

    log_path = args.log
    if not log_path and args.date:
        log_path = os.path.join(args.reports, f"regime_replay_{args.date}.jsonl")
    if not log_path:
        ap.error("give --log <jsonl>, or --date <YYYY-MM-DD> (+ --reports), or --view")
    if not os.path.isfile(log_path):
        print(f"no tick log at {log_path} — run the replay for that date first"); sys.exit(1)

    entry = digest_from_log(log_path)
    if not entry.get("date"):
        print("could not infer date from log filename; pass --date"); sys.exit(1)
    upsert(entry, args.diary_dir)
    sys.exit(0)


if __name__ == "__main__":
    main()
