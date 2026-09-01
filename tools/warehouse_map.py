#!/usr/bin/env python3
# day_trader_pro/tools/warehouse_map.py — v1.0
# v1.0 (2026-09-01) — dtp r238. THE BUCKET'S LAYOUT, GENERATED FROM THE BUCKET.
#
# Operator, 2026-09-01: map the files and folders of the bucket and store it in
# the repo for reference — "all the artifacts that we're storing there now have
# their own place and that's not gonna change."
#
# 🔑 GENERATED, NEVER HAND-KEPT, and that is the whole design. r33 records what
#   a hand-maintained map does: v3's FILE_MAP said in its own header "it is a
#   snapshot, and it will drift" — and it did, until a module was nearly
#   excised on a reading of its imports while the map recorded its fan-in as
#   the third highest in the codebase. The same rule applies to a bucket that
#   grows a new prefix every time a stream is added.
#
# ⚠️ IT REUSES `warehouse_cost.scan_current` RATHER THAN WALKING THE BUCKET
#   AGAIN. That function already paginates every object and aggregates per
#   prefix with the dt= days seen; a second walker would be a second set of
#   numbers that agree until they don't (§7, and §13 — check whether the menu
#   already does it before writing a one-off).
#
# Run:  python3 tools/warehouse_map.py            # rewrite docs/WAREHOUSE_MAP.md
#       python3 tools/warehouse_map.py --check    # rc=1 if the bucket moved
"""Generate (or verify) the warehouse layout reference."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)

import config                                            # noqa: E402
import warehouse_cost as WC                              # noqa: E402

ET = ZoneInfo("US/Eastern")
DOC = os.path.join(_root, "docs", "WAREHOUSE_MAP.md")
GB = 1024 ** 3

# What each prefix HOLDS. The counts come from the bucket; this says what the
# rows mean, which a listing cannot. A prefix absent from here is reported as
# UNDOCUMENTED rather than skipped — that is the point of the check.
MEANING = {
    "raw/trades":            "closed + open trade rows, per box (the book)",
    "raw/candles":           "OHLC per tenor; SYM_EXT holds non-RTH bars",
    "raw/chain_snapshots":   "option chain marks at fire time",
    "raw/greeks_series":     "per-contract greeks, full fidelity",
    "raw/quote_series":      "per-contract bid/ask/sizes",
    "raw/prints":            "TimeAndSale, with the venue's aggressor tag",
    "raw/last_trade":        "Trade events",
    "raw/session_summary":   "Summary events (prev-day close, etc.)",
    "raw/theo_series":       "TheoPrice — writer retained, unsubscribed at r118",
    "raw/underlying_series": "Underlying — published nothing on either symbol space",
    "raw/fork_series":       "pitchfork state per tenor, with reject reasons",
    "raw/indicator_series":  "ADX / ATR / EMA / VWAP accumulators",
    "raw/surface_series":    "charm, vanna, GEX",
    "raw/fire_snapshot":     "the derived vector at every fill",
    "raw/strategy_note":     "one row per strategy EVALUATION",
    "raw/plan_ledger":       "plan lifecycle — intent, terminal state, trade join",
    "raw/plan_tick":         "the spine: one row per plan per tick",
    "raw/plan_check":        "long format: one row per VARIABLE per plan per tick",
    "raw/gate_disposition":  "which rung refused a strategy, edge-triggered",
    "raw/character_ledger":  "tape character state with duration",
    "raw/level_ledger":      "liquidity levels, operator lifecycle",
    "raw/exit_counterfactual": "flow exits that WOULD have fired; acts on nothing",
    "raw/shadow":            "sweep-precursor velocity primitives",
}


def build(quiet=False):
    s3 = WC._client() if hasattr(WC, "_client") else __import__("boto3").client("s3")
    per, total = WC.scan_current(s3, quiet=quiet)
    rows = []
    for name in sorted(per):
        r = per[name]
        days = sorted(r["days"])
        rows.append((name, r["objects"], r["bytes"], len(days),
                     (days[0] if days else ""), (days[-1] if days else "")))
    return rows, total


def render(rows, total) -> str:
    now = datetime.now(ET).strftime("%Y-%m-%d %H:%M ET")
    out = [
        "# WAREHOUSE_MAP.md — what is in the bucket, and where",
        "",
        f"**Generated {now} by `tools/warehouse_map.py`. Do not hand-edit.**",
        "",
        "🔑 **GENERATED FROM THE BUCKET, NOT FROM THE WRITERS.** A map derived "
        "from the push code states what we INTENDED to store; this states what "
        "is actually there. When they disagree, that disagreement is the "
        "finding — `--check` fails on it rather than quietly re-rendering.",
        "",
        "⚠️ **KEY LAYOUT IS HIVE-STYLE AND FIXED:** "
        "`raw/<datatype>/dt=<YYYY-MM-DD>/sym=<SYM>/<epoch_ms>-<sha16>.json`. "
        "`dt=` is the **ET trading day** in every stream — if it ever meant "
        "something different in one of them, joins across streams would return "
        "silently wrong rows rather than none.",
        "",
        "⚠️ **`raw/` NEVER DELETES.** Retention purging happens on the BOX "
        "(r81/r162); the bucket is the durable copy. Noncurrent versions "
        "accumulate with no lifecycle rule — `warehouse_cost.py --versions` "
        "counts them.",
        "",
        f"**Totals:** {total['objects']:,} objects · "
        f"{total['bytes'] / GB:.2f} GB",
        "",
        "| prefix | objects | GB | days | first | last | holds |",
        "|---|---:|---:|---:|---|---|---|",
    ]
    for name, n, b, nd, first, last in rows:
        holds = MEANING.get(name, "**UNDOCUMENTED — add it to MEANING**")
        out.append(f"| `{name}` | {n:,} | {b / GB:.3f} | {nd} | {first} | "
                   f"{last} | {holds} |")
    known = set(MEANING)
    seen = {r[0] for r in rows}
    missing = sorted(known - seen)
    if missing:
        out += ["", "**Documented but ABSENT from the bucket** — a stream that "
                "never wrote, or one that was retired:", ""]
        out += [f"- `{m}` — {MEANING[m]}" for m in missing]
    out.append("")
    return "\n".join(out)


def main(argv):
    ap = argparse.ArgumentParser(description="warehouse layout reference")
    ap.add_argument("--check", action="store_true",
                    help="rc=1 if the live bucket no longer matches the doc")
    a = ap.parse_args(argv[1:])
    rows, total = build(quiet=a.check)
    text = render(rows, total)
    if a.check:
        # ⚠️ COMPARE THE TABLE, NOT THE WHOLE FILE — the generated timestamp
        # and the byte totals move on every push, so a naive diff would cry
        # wolf on every run and teach the reader to skip it (CV.1).
        def _sig(s):
            return [ln.split("|")[1].strip() for ln in s.splitlines()
                    if ln.startswith("| `")]
        old = open(DOC, encoding="utf-8").read() if os.path.exists(DOC) else ""
        if _sig(old) != _sig(text):
            print("WAREHOUSE MAP DRIFT — prefixes changed. Regenerate:")
            print("  python3 tools/warehouse_map.py")
            return 1
        undoc = [r[0] for r in rows if r[0] not in MEANING]
        if undoc:
            print("UNDOCUMENTED prefixes in the bucket: " + ", ".join(undoc))
            return 1
        print("warehouse map is current")
        return 0
    os.makedirs(os.path.dirname(DOC), exist_ok=True)
    with open(DOC, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"wrote {DOC}  ({len(rows)} prefixes, "
          f"{total['objects']:,} objects, {total['bytes'] / GB:.2f} GB)")
    undoc = [r[0] for r in rows if r[0] not in MEANING]
    if undoc:
        print("⚠️  UNDOCUMENTED prefixes — add them to MEANING: "
              + ", ".join(undoc))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
