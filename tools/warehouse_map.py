#!/usr/bin/env python3
# day_trader_pro/tools/warehouse_map.py — v1.1
# v1.1 (2026-09-01) — dtp r239. 🔴 v1.0's MEANING TABLE WAS WRITTEN FROM MEMORY
#   AND 12 OF 25 PREFIXES WERE WRONG. The operator ran it and the generator
#   printed the whole list back. Every entry now cites the FUNCTION that writes
#   it, which is what forces the read: an entry cannot be added without opening
#   the pusher. Corrected against s3_push.py's twelve-stage drain and the
#   2026-09-01 scan.
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
# ─────────────────────────────────────────────────────────────────────────────
# 🔴 EVERY ROW CITES THE FUNCTION THAT WRITES IT, AND THAT IS NOT DECORATION.
# v1.0 of this table was written from MEMORY and twelve of twenty-five prefixes
# were wrong. Seven were one mistake repeated: the derived tables live under
# `raw/derived_<table>/`, not `raw/<table>/` — `warehouse_reader.load_derived`
# says `read_prefix(s3, "derived_%s" % table, d)` and I had READ that line in
# the same session before writing the table anyway. The other five —
# `raw/eod`, `raw/liquidity_ledger`, `raw/ohlc`, `raw/orb_range`,
# `raw/signal_journal` — I simply never enumerated: I listed three constants
# (SERIES_TABLES, DERIVED_TABLES, DERIVED_SERIES_TABLES) and treated that as
# the whole pusher, while `push_file`, `push_jsonl_tree`, `push_whole_files`
# and `push_candles` each build their own keys.
# ⚠️ WORKING_AGREEMENT §0.1: anything readable from the repo is READ before it
# is used, and guessing costs the operator a round trip that he is the one
# running. The writer citation is what forces the read — an entry cannot be
# added without opening the function that produces the objects.
# ⚠️ SOURCE OF TRUTH: options_trader_v4 warehouse/s3_push.py, the `stages` list
# in the drain (twelve stages), verified against the 2026-09-01 bucket scan.
# ─────────────────────────────────────────────────────────────────────────────
MEANING = {
    # ── the book ────────────────────────────────────────────────────────
    "raw/trades": ("push_trades <- trades.db",
                   "closed + open trade rows, per box"),
    "raw/circuit_breaker": ("push_table <- trades.db:circuit_breaker_events",
                            "breaker trips"),
    # ── whole files, shipped as they sit on the box ─────────────────────
    "raw/eod": ("push_whole_files <- ~/eod",
                "end-of-day artifacts written by the EOD chain"),
    "raw/ohlc": ("push_whole_files <- ~/options-trader/data/OHLC/*.csv",
                 "CSV OHLC exports; NOT the same stream as raw/candles"),
    "raw/liquidity_ledger": ("push_whole_files <- "
                             "~/options-trader/data/liquidity_ledger/*.json",
                             "the liquidity map as the box wrote it"),
    # ── databases, high-water or CDC ────────────────────────────────────
    "raw/candles": ("push_candles <- feed_store.db",
                    "OHLC per tenor; sym=<SYM>_EXT holds non-RTH bars"),
    "raw/chain_snapshots": ("push_file (DATATYPE 'chain_snapshot' + 's')",
                            "option chain marks at fire time"),
    # ── SERIES_TABLES: feed_store.db, high-water on ts ──────────────────
    "raw/greeks_series": ("push_series", "per-contract greeks, full fidelity"),
    "raw/quote_series": ("push_series", "per-contract bid/ask/sizes"),
    "raw/prints": ("push_series", "TimeAndSale, with the venue's aggressor tag"),
    "raw/last_trade": ("push_series", "Trade events"),
    "raw/session_summary": ("push_series", "Summary events (prev-day close)"),
    "raw/theo_series": ("push_series",
                        "TheoPrice — writer retained, unsubscribed at r118"),
    "raw/underlying_series": ("push_series",
                              "Underlying — published nothing on either "
                              "symbol space"),
    # ── DERIVED_SERIES_TABLES: derived_store.db, append-only on ts_epoch ─
    "raw/fork_series": ("push_series ns=dseries",
                        "pitchfork state per tenor, with reject reasons"),
    "raw/indicator_series": ("push_series ns=dseries",
                             "ADX / ATR / EMA / VWAP accumulators"),
    "raw/surface_series": ("push_series ns=dseries", "charm, vanna, GEX"),
    # ── DERIVED_TABLES: derived_store.db lifecycle, CDC by rowid ────────
    # ⚠️ THESE CARRY THE `derived_` PREFIX IN THE KEY. That is the mistake v1.0
    # made seven times over.
    "raw/derived_fire_snapshot": ("push_derived",
                                  "the derived vector at every fill"),
    "raw/derived_strategy_note": ("push_derived",
                                  "one row per strategy EVALUATION"),
    "raw/derived_plan_ledger": ("push_derived",
                                "plan lifecycle — intent, terminal state, "
                                "trade join"),
    "raw/derived_plan_tick": ("push_derived",
                              "the spine: one row per plan per tick"),
    "raw/derived_plan_check": ("push_derived",
                               "long format: one row per VARIABLE per plan "
                               "per tick"),
    "raw/derived_gate_disposition": ("push_derived",
                                     "which rung refused a strategy, "
                                     "edge-triggered"),
    "raw/derived_character_ledger": ("push_derived",
                                     "tape character state with duration"),
    "raw/derived_level_ledger": ("push_derived",
                                 "liquidity levels, operator lifecycle"),
    "raw/derived_exit_counterfactual": ("push_derived",
                                        "flow exits that WOULD have fired; "
                                        "acts on nothing"),
    # ── JSONL trees ─────────────────────────────────────────────────────
    "raw/shadow": ("push_jsonl_tree <- ~/options-trader/data/shadow",
                   "sweep-precursor velocity primitives"),
    "raw/signal_journal": ("push_jsonl_tree <- "
                           "~/options-trader/data/signal_journal",
                           "per-event signal journal"),
    # ── retired, kept because raw/ never deletes ────────────────────────
    "raw/orb_range": ("RETIRED — s3_push v1.8, 2026-08-16",
                      "stopped growing; nothing consumed it and the range "
                      "recomputes from candles"),
    "raw/orb_state": ("RETIRED — s3_push v1.8, 2026-08-16",
                      "captured ZERO objects in thirty days"),
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
        "| prefix | objects | GB | days | first | last | written by | holds |",
        "|---|---:|---:|---:|---|---|---|---|",
    ]
    for name, n, b, nd, first, last in rows:
        writer, holds = MEANING.get(
            name, ("**NO WRITER TRACED**", "**UNDOCUMENTED — trace it first**"))
        out.append(f"| `{name}` | {n:,} | {b / GB:.3f} | {nd} | {first} | "
                   f"{last} | `{writer}` | {holds} |")
    known = set(MEANING)
    seen = {r[0] for r in rows}
    missing = sorted(known - seen)
    if missing:
        out += ["", "**Documented but ABSENT from the bucket.** Each of these "
                "has a live writer in `s3_push.py` (or a recorded retirement) "
                "and has produced NO objects. That is a finding, not a gap in "
                "this file: `push_derived` skips a table that is absent on the "
                "box, so a stream configured to push and never seen here has "
                "either no table or no rows — and nothing says which without "
                "looking.", ""]
        out += [f"- `{m}` — {MEANING[m][1]}  (writer: `{MEANING[m][0]}`)"
            for m in missing]
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
