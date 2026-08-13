#!/usr/bin/env python3
"""
day_trader_pro/excursion_report.py — v3.1 — MFE/MAE distributions from the
fleet's auto-collected per-symbol trade DBs.

v3.1 — 2026-08-13 — `insurance_stop` WAS REPORTED NOWHERE. It is the MIDDLE
       tier of continuation's three-stop precedence — BOS protected_level owns
       the trade, `insurance_stop` fires on a 1m close beyond the structural
       level while BOS has no level, and the 25%% premium floor is the disaster
       backstop. Tier 1 reached the LEASH VERDICT via `bos_exit`; tier 3
       reached the FLOOR VERDICT via FLOOR_REASON_PREFIXES; **tier 2 fell
       through all three lists and appeared only in the raw --by exit table,
       stripped of the giveback and MFE framing that make those sections mean
       anything.** The `unlisted` fallback did not catch it either, because it
       matches on the substring "trail" and a structural stop is not a trail.
       (a) `insurance_stop` added to TRAIL_FLAVORS, alongside `bos_exit` which
           was already carried as "leash-adjacent".
       (b) NEW: an UNREPORTED-REASONS audit. Any exit reason present in the
           window that reaches neither the leash block nor the floor block is
           now named explicitly. The failure class this fixes is the one this
           repo exists to prevent — output that renders cleanly while omitting
           the thing you would have looked for. A silent omission is worse
           than a missing section, because the report still looks complete.
v3.0 — 2026-08-07 — THE ONE-SESSION GUARD REFUSED AN ELEVEN-SESSION READ.
       The v2.7 guard tested `"1 session(s)" in src`, and
       "165 DBs across 11 session(s)" CONTAINS "1 session(s)" — so every
       cumulative run whose session count ENDS IN 1 (11, 21, 31, 41 ...) was
       refused as though the range had collapsed to a single folder. Found
       2026-08-07 when `--date 2026-08-06 --since 2026-07-23` was rejected
       while option 41 read the same span fine and returned 579 trades.
       The guard's INTENT stands — v2.7 added it after a --since silently read
       one folder and reported 96 trades as though cumulative, which is exactly
       the kind of clean-looking wrong answer this repo exists to prevent. Only
       the TEST was wrong. Now anchored on "across 1 session(s)" so the match
       cannot slide into a longer number.
       LESSON, and it is the same one as the changelog-matching canary caught
       the same day: a SUBSTRING test standing in for an EQUALITY test fails
       silently and in the direction that looks like correct caution.

v2.9 — 2026-08-06 — SCORE DISPERSION. The v2.8 columns showed SETUP.nf ==
       SETUP.ok at 0.96 on grade A (n=277) and 1.50 on ORB (n=97), and RGCV
       pegged 1.00/1.00 on TRENDING_BULL (n=206). Identical MEDIANS cannot
       distinguish "varies, same centre" from "constant" — and only the second
       makes a cutoff impossible. Percentiles settle it: p10 == p90 means the
       score is a constant wearing a continuous type, the same failure
       readiness_digest reports one layer down, surfacing at the trade level.
v2.8 — 2026-08-05 — TWO SCORE COLUMNS on the never-favorable composition table,
       each split nf vs the rest. Both have been on every trade row for weeks
       and neither surfaced here.
       SETUP = `setup_score`, the composite that AUTHORISED the trade (the A/B
       grade is its bucketing). This is the cutoff question.
       RGCV = `regime_conviction`, L2's confidence in the LABEL — a different
       question entirely: a tick can be 1.00-conviction TRENDING_BULL and still
       be a poor continuation entry.
       Carrying BOTH is the point: where setup_score separates and conviction
       does not, the grading works and the label does not, and vice versa. That
       says which layer to fix.
       MEDIAN not mean — conviction pegs at 1.00 often enough (measured on the
       A2 co-occurrence ticks) that a mean would be dragged by the peg.
       NOT the readiness track's `r`: that is log-only and gates nothing, so a
       threshold on it would change nothing that fires.
v2.7 — 2026-08-05 — cumulative reads EVERY dated folder in the range. The
       2026-08-05 trim gave each folder one trading day, so --since silently
       became single-day while the header still claimed the range.

v2.6 — 2026-08-04 — (a) PEAK TIMING from trade_logger v3.9's
       max_premium_seen_at: the winner-giveback block had been printing an
       instruction to add those timestamps, which shipped 2026-08-03 — so the
       report was asking for a column it already had and declining to answer a
       question it could. Early-peak vs late-peak separates a loose trail from a
       move that simply turned, and those need opposite fixes.
       (b) EXIT-REASON FAMILIES POOLED. `regime_flip (LABEL)` and
       `max_loss_floor_NNpct` fragmented every cell and each fragment then
       correctly reported itself UNDERPOWERED — output that looks right and can
       never conclude. On 2026-08-04 that was 12 regime_flips split 6/4/1/1.
       The detail is preserved by reason_detail(), not discarded.
v2.5 — 2026-08-03 — THE TWO-POPULATION SPLIT, per the operator's framing:
        separate the trades that were NEVER winners — not favorable for one
        tick, so there was never anything to manage — from the ones that DID
        work and gave some of it back. The first population is a selection
        problem, the second an extension problem, and pooling them is why
        "which exit is losing money" kept returning the wrong answer.
        NEVER FAVORABLE reports the population at three MFE thresholds rather
        than one, because the right cut is an empirical question and a single
        hardcoded epsilon would be a parameter smuggled in as a definition.
        Composition is reported as a RATE WITHIN each group, never as a share
        OF the never-favorable population. A group holding 30% of the bad
        trades means nothing if it is 30% of all trades — that is the same
        error as the birth rate presented as coverage. Lift is the group's
        rate over the overall rate.
        WINNER GIVEBACK reports capture = realized / MFE on winners only.
        LIMITATION, stated in the output because it decides what the block can
        conclude: trade_logger v3.8 records max_premium_seen and
        min_premium_seen as VALUES ONLY, with no timestamp. So giveback cannot
        distinguish "peaked early, then bled for twenty minutes" from "ran to
        the exit and reversed on the last tick" — which is exactly the
        difference between a trail that is too loose and a trail that is fine.
        Extending the winners needs that timestamp; the block says so instead
        of implying an answer it cannot reach.
v2.4 — 2026-08-03 — REGIME DIMENSION + FLOOR SWEEP. The pre-go-live question is
        which strategies are configured for which regimes and where the stop
        belongs for each — and NOTHING could answer it: this report crossed
        exit x strategy with excursion but had no regime dimension, while
        trade_report crossed regime x strategy but carried only P&L, no
        excursion. Neither could say whether a losing cell's trades ever went
        favorable at all. --by now groups the table by regime, strategy,
        strategy_x_regime, setup_type, setup_grade or regime_x_setup, so MFE
        and MAE can be read per cell.
        SESSIONS column added to every table, because on 2026-08-03 the
        07-23..08-03 "cumulative" turned out to be 67% two sessions (07-31 n=116
        and 08-03 n=88 of 303). A cell drawn from one or two dates is a day, not
        a regime finding, and nothing in the old output said so.
        FLOOR SWEEP answers the stop half WITHOUT needing exit-reason cells,
        which is what makes it reachable before the freeze: every trade
        contributes its MAE to the counterfactual regardless of which exit
        actually fired, so the sample cost is one cell instead of one cell per
        exit. Assumptions are printed with the block, not buried: fill AT the
        floor, no slippage, MAE sampled at the ~15s tick so an intra-tick spike
        through the level is invisible, and a terminal stop has no path after
        it (true for a floor, NOT true for trails or targets — this method
        cannot answer the trail question).
        It deliberately names NO best floor. Picking the in-sample argmax is
        overfitting, and this file exists because numbers that read cleanly
        while meaning something else have cost real time here.
v2.3 — 2026-08-03 — FOUR defects, all of the same class: the report rendered
v2.3 — 2026-08-03 — FOUR defects, all of the same class: the report rendered
        cleanly while meaning something other than it appeared.
        (1) THE DB SOURCE HAS NEVER LOADED. _rows_from_dbs globbed the
        UNDATED filename form, but harvest.py:166 writes
        trades/<date>/<SYM>_trades_<date>.db — the glob requires the name to
        END in _trades.db, so it has matched ZERO files since v2.0 and every
        run has silently fallen through to the fleet_trades_<date>.json
        fallback. consolidate_trades.py:178 and tests/gate_ledger.py:139 both
        glob "*_trades_<date>.db" correctly; this file was the outlier.
        CONSEQUENCE: --since has been a guaranteed no-op on every run ever
        made, because the fallback file holds ONE day (consolidate_trades v1.2
        filters rows to the day being consolidated) and --since is a filter
        over already-loaded rows, not a loader. Single-day reports were
        unaffected — the fallback is consolidated from the same DBs — so no
        past single-day number is wrong; only cumulative was impossible.
        Found 2026-08-03 when a "since 2026-07-23" run returned exactly that
        day's 88 rows.
        (2) THE FALLBACK ONLY ANNOUNCED ITSELF WHEN THE REPORT WAS EMPTY —
        the '(' not in src hint sat inside `if not rows:`. With rows present
        the degradation was invisible. Now a SOURCE line is emitted whenever
        the primary DB source is missing, populated or not, and --since over
        the fallback REFUSES (rc=2) instead of labelling one day cumulative.
        (3) LEASH VERDICT hardcoded four flavors, two of which the engine no
        longer emits, and `if not rs: continue` dropped the rest in silence —
        so a block headed "per trail flavor" printed bos_exit alone while
        continuation_trail, orb_trail_stop and condor_stop sat in the table
        above it. Flavor set now covers the real exit_engine vocabulary and
        any unlisted reason containing "trail" is caught and named.
        (4) FLOOR VERDICT counted the wrong stop: startswith("hard_stop")
        matched ORB's hard_stop_<pct> but NOT max_loss_floor_<pct>pct, the
        actual floor exit — on 2026-08-03 it reported 1 floor stop and missed
        5. Also relabelled: the line narrated one threshold in prose while
        testing against another, and the params were named after a floor move
        that has since reversed (the continuation backstop went 40%→25% on
        2026-07-22). Now tight_floor/wide_floor, with the thresholds
        interpolated instead of written into the prose.
v2.2 — 2026-07-16 — --live writes excursions_<date>_live.txt (own file, so
        the nightly paper report is never clobbered); ran automatically as
        EOD conductor phase 7 (v1.3.0) — devtools 45 remains the manual path.
v2.1 — 2026-07-16 — self-diagnosing empty states: says WHY a report is
        empty (ran intraday before the EOD chain lands trades/<date>/ at
        ~16:05 ET; live filter on a paper fleet; rows skipped for missing
        telemetry) instead of the misleading "deploy trade_logger v3.8" hint.
v2.0 — 2026-07-15 — READS trades/<date>/*_trades.db DIRECTLY (the raw per-box
        SQLite snapshots the EOD chain already lands on this server) — no
        consolidation step required; runnable the moment the DBs are down.
        Falls back to reports/fleet_trades_<date>.json/.csv only if a date has
        no DB folder. Each snapshot contains the box's FULL history, so
        --since turns a single day's snapshot into a cumulative report.
        Output unchanged: reports/excursions_<date>.txt.
v1.0 — 2026-07-15 — initial (consolidated-file reader); control-server
        companion to trade_logger v3.8 telemetry and the exit_engine v3.8
        runner refinements.

Usage:
    python3 excursion_report.py                        # today's trades only
    python3 excursion_report.py --date 2026-07-16
    python3 excursion_report.py --date 2026-07-18 --since 2026-07-16
                                                       # cumulative from the
                                                       # 07-18 snapshots
    python3 excursion_report.py --strategy ORB --live

Definitions (all % of entry premium, sign-correct for credit spreads):
  MFE   max favorable excursion — the best the trade EVER looked
  MAE   max adverse excursion  — the worst it EVER looked
  REAL  realized P&L pct (from pnl_usd, sign-correct)
  GIVE  giveback = MFE − REAL — how much the leash returned to the market

Verdicts answer the tuning questions directly:
  FLOOR — winners whose MAE breached −25% (saved by the 40% floor) vs winners
          that also breached −40% (would have died anyway; argues wider).
  LEASH — giveback per trail flavor: is the runner leash paying for itself?

NOTE: telemetry fills from the first session AFTER trade_logger v3.8 deploys.
Rows without max/min_premium_seen (all history before that) are counted and
skipped, not guessed at.
"""

import argparse
import csv
import json
import os
import re
import sys
from datetime import date, datetime
from statistics import mean, median
from typing import Optional

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR  = os.path.join(SCRIPT_DIR, "reports")
TRADES_DIR   = os.path.join(SCRIPT_DIR, "trades")
CONTRACT_MULTIPLIER = 100

# Exit vocabulary, read from options_trader_v3's exit_engine rather than
# remembered. Anything the engine emits with "trail" in the name is caught by
# substring below even if it is missing here, so a new flavor cannot vanish.
TRAIL_FLAVORS = (
    "continuation_trail",       # ContinuationStrategy runner leash
    "orb_trail_stop",           # ORB
    "orb_fvg_trail_stop",       # ORB, FVG-anchored
    "post_target_trail",
    "trail_stop_hit",
    "adopted_trail",            # positions adopted at restart
    "bos_exit",                 # structure break — leash-adjacent, kept
    "insurance_stop",           # v3.1 — continuation's STRUCTURAL stop (tier 2
                                # of three). Reported nowhere before: not a
                                # trail by name, not a floor by prefix, and the
                                # "trail"-substring fallback could not see it.
    "theta_bleed",
)

# The floor exits. max_loss_floor_<pct>pct is the blanket/continuation floor;
# hard_stop_<pct> is ORB's. Matching only "hard_stop" missed the former.
FLOOR_REASON_PREFIXES = ("hard_stop", "max_loss_floor")

# Grouping keys for --by. "exit" is the pre-v2.4 behaviour and stays default.
GROUP_KEYS = {
    "exit":              ("exit_reason", "strategy"),
    "strategy":          ("strategy",),
    "regime":            ("regime",),
    "strategy_x_regime": ("strategy", "regime"),
    "setup_type":        ("setup_type",),
    "setup_grade":       ("setup_grade",),
    "regime_x_setup":    ("regime", "setup_type"),
}

# Pre-registered refusal floors. A cell under either is reported as
# UNDERPOWERED, which is not a null — the distinction the operator insists on.
MIN_CELL_N = 40          # reads roughly a 0.20 R effect at this sample
MIN_SESSIONS = 3         # 1-2 dates is a day, not a regime

FLOOR_CANDIDATES = (0.15, 0.20, 0.25, 0.30, 0.40, 0.50)

# "Never favorable" is not one number. Reported at three cuts so the choice of
# epsilon is visible rather than baked in. 0% = never traded above entry at all.
NEVER_FAVORABLE_CUTS = (0.00, 0.02, 0.05)

# Dimensions the split is broken out by. entry_time is UTC and the tape is
# ET-offset, so hour-of-day is deliberately ABSENT here — trade_report already
# does that conversion with ZoneInfo and duplicating it half-done is how the
# 2026-07 verdict got inverted.
SPLIT_DIMS = ("regime", "strategy", "setup_type", "setup_grade", "symbol")

MIN_GROUP_N = 15         # a group under this is not rated, only counted


# ── input: per-symbol DB snapshots (primary), consolidated file (fallback) ──

def _rows_from_dbs(day: str, since: str = ""):
    """trades/<date>/<SYM>_trades_<date>.db — every closed row in the range.

    v2.7 — READS EVERY DATED FOLDER FROM `since` TO `day`, not just `day`.
    The old docstring said "snapshots hold full history; date filtering happens
    later", and that WAS true: each folder held a copy of the box's cumulative
    DB, so reading the last folder happened to yield every session. The
    2026-08-05 trim gave each folder exactly one trading day — which is correct
    and was the point — and cumulative mode silently became single-day. A
    "since 2026-07-23" run over ten sessions returned 96 trades from one.
    Fixing the duplication broke the feature that had been living on it.
    Nothing announced the change: the header still said "since 2026-07-23".
    """
    if since and since < day:
        folders = sorted(d for d in os.listdir(TRADES_DIR)
                         if len(d) == 10 and since <= d <= day
                         and os.path.isdir(os.path.join(TRADES_DIR, d)))
    else:
        folders = [day]
    rows, n_paths, n_folders = [], 0, 0
    for f_day in folders:
        _r, _n = _rows_one_folder(f_day)
        if _r is None:
            continue
        rows.extend(_r)
        n_paths += _n
        n_folders += 1
    if not n_folders:
        return None, None
    span = folders[0] if n_folders == 1 else f"{folders[0]}..{folders[-1]}"
    return rows, f"trades/{span} ({n_paths} DBs across {n_folders} session(s))"


def _rows_one_folder(day: str):
    import glob
    import sqlite3
    folder = os.path.join(TRADES_DIR, day)
    # harvest.py:166 writes <SYM>_trades_<date>.db — the same pattern
    # consolidate_trades.py:178 and tests/gate_ledger.py:139 use. A bare
    # The undated form requires the name to END there and matches nothing.
    paths = sorted(glob.glob(os.path.join(folder, f"*_trades_{day}.db")))
    if not paths:
        return None, None
    rows = []
    for p in paths:
        try:
            conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            for r in conn.execute(
                    "SELECT * FROM trades WHERE status='closed'"):
                d = dict(r)
                d["_box"] = os.path.basename(p).split("_")[0]
                rows.append(d)
            conn.close()
        except Exception as e:
            print(f"  ! {os.path.basename(p)}: {e}", file=sys.stderr)
    return rows, len(paths)


def _rows_from_json(path):
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if isinstance(data.get("trades"), list):
            return data["trades"]
        rows = []
        for v in data.values():          # {host: [rows]} shape
            if isinstance(v, list):
                rows.extend(v)
        return rows
    return []


def _rows_from_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def load_day(day: str, since: str = ""):
    rows, src = _rows_from_dbs(day, since)
    if rows is not None:
        return rows, src
    j = os.path.join(REPORTS_DIR, f"fleet_trades_{day}.json")
    c = os.path.join(REPORTS_DIR, f"fleet_trades_{day}.csv")
    if os.path.exists(j):
        return _rows_from_json(j), j
    if os.path.exists(c):
        return _rows_from_csv(c), c
    return None, None


def _entry_date(row) -> str:
    return str(row.get("entry_time") or "")[:10]


# ── field coercion (JSON gives types; CSV gives strings) ─────────────────────

def fnum(row, key, default=None):
    v = row.get(key)
    if v is None or v == "":
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def flag(row, key):
    v = row.get(key)
    return str(v).strip() in ("1", "1.0", "True", "true")


def credit_signed(row) -> bool:
    return flag(row, "is_condor_leg") \
        or (row.get("strategy") or "") == "IronCondorStrategy" \
        or flag(row, "is_short_position")


def peak_fraction(row) -> Optional[float]:
    """Where in the hold the MFE landed, as a fraction of entry->exit.

    None when the v3.9 timestamps are absent (every row entered before
    2026-08-03) or unparseable. NEVER imputed: a missing peak time is not a
    peak at time zero, and treating it as one would manufacture the exact
    "peaked early" signal this measure exists to detect.
    All three stamps are UTC ISO from ts_for_db — the same base, deliberately,
    because comparing a UTC field against an ET-offset one has already inverted
    one verdict in this repo.
    """
    t0, tp, t1 = (row.get("entry_time"), row.get("max_premium_seen_at"),
                  row.get("exit_time"))
    if not (t0 and tp and t1):
        return None
    try:
        a = datetime.fromisoformat(str(t0))
        b = datetime.fromisoformat(str(tp))
        c = datetime.fromisoformat(str(t1))
    except Exception:                                            # noqa: BLE001
        return None
    span = (c - a).total_seconds()
    if span <= 0:
        return None
    return max(0.0, min(1.0, (b - a).total_seconds() / span))


def norm_reason(reason) -> str:
    """Collapse an exit reason to its FAMILY.

    v2.6 — two families were fragmenting the sample and every fragment then
    honestly reported itself UNDERPOWERED, which is the worst possible failure
    mode: correct-looking output that can never reach a verdict.
      `regime_flip (BREAKOUT_VOLATILE)` — the label rides in PARENTHESES, which
        survived the old strip. 2026-08-04: twelve regime_flip trades became
        four cells of 6/4/1/1, all REFUSED. Pooled they are one cell of 12 and
        reach n=40 in about four sessions.
      `max_loss_floor_25pct` / `..._24pct` — the percentage varies with config,
        so the same exit splits by its own setting. 2 and 1 instead of 3.
    The detail is NOT discarded — `reason_detail()` returns it, so a pooled cell
    can still be split when it has the n to support one. Same principle as
    gap_outcome_join's `--pool`: collapse for power, keep the split available.
    """
    r = (reason or "unknown").strip()
    if r.startswith("hard_close"):
        return "hard_close"
    r = r.split(" pnl=")[0].split(":")[0].strip() or "unknown"
    if r.startswith("regime_flip"):
        return "regime_flip"
    if r.startswith("max_loss_floor"):
        return "max_loss_floor"
    return r


def reason_detail(reason) -> str:
    """The part norm_reason() pools away: the regime label, or the floor pct.

    Kept so pooling never destroys information — only defers it.
    """
    r = (reason or "").split(" pnl=")[0].strip()
    m = re.search(r"\(([^)]+)\)", r)
    if m:
        return m.group(1)
    m = re.search(r"max_loss_floor_(\d+pct)", r)
    return m.group(1) if m else ""


def usable(row, paper: bool) -> bool:
    if (row.get("status") or "") != "closed":
        return False
    pt = row.get("paper_trade")
    is_paper = True if pt in (None, "",) else str(pt).strip() in ("1", "1.0", "True", "true")
    if is_paper != paper:
        return False
    return (fnum(row, "entry_premium", 0) or 0) > 0 \
        and fnum(row, "pnl_usd") is not None \
        and fnum(row, "max_premium_seen") is not None \
        and fnum(row, "min_premium_seen") is not None


def excursions(row):
    entry = fnum(row, "entry_premium")
    hi    = fnum(row, "max_premium_seen")
    lo    = fnum(row, "min_premium_seen")
    qty   = fnum(row, "contracts", 1) or 1
    real  = fnum(row, "pnl_usd") / (entry * qty * CONTRACT_MULTIPLIER)
    if credit_signed(row):
        return (entry - lo) / entry, (entry - hi) / entry, real
    return (hi - entry) / entry, (lo - entry) / entry, real


def pct(x):
    return f"{x:+.0%}"


# ── the report ───────────────────────────────────────────────────────────────

def build_report(rows, day, src, skipped, mode, hints=None,
                 tight_floor=0.25, wide_floor=0.40,
                 group_by="exit") -> str:
    out = []
    w = out.append
    w(f"EXCURSION REPORT — {day} [{mode}] — {len(rows)} trade(s) with telemetry")
    # (window note is appended by main via the source line below)
    w(f"source: {src if '(' in src else os.path.basename(src)}"
      + (f"   ({skipped} closed row(s) skipped: no telemetry — pre-v3.8)"
         if skipped else ""))
    if "(" not in src:
        w("SOURCE DEGRADED: per-box DBs absent — this is the single-day "
          "consolidated fallback, so cumulative (--since) is not available "
          "from it. Numbers below cover ONE session.")
    if not rows:
        w("")
        w("Nothing to report for this selection. Likely reasons:")
        for h in (hints or ["no closed trades with telemetry matched the filters"]):
            w(f"  • {h}")
        return "\n".join(out) + "\n"

    keys = GROUP_KEYS.get(group_by, GROUP_KEYS["exit"])
    buckets = {}
    for r in rows:
        k = tuple(norm_reason(r.get(f)) if f == "exit_reason"
                  else (r.get(f) or "?") for f in keys)
        buckets.setdefault(k, []).append(r)

    names = [k.replace("_", " ").upper() for k in keys]
    wide  = 30 if len(keys) == 1 else 22
    w("")
    if len(keys) > 1:
        w(f"{names[0][:wide]:<{wide}}{names[1][:11]:<12}{'N':>4}{'SESS':>5}"
          f"{'WIN%':>6}{'REAL':>7}{'MFE':>7}{'MAE':>7}{'GIVE':>7}")
        w("-" * (wide + 12 + 43))
    else:
        w(f"{names[0][:wide]:<{wide}}{'N':>4}{'SESS':>5}"
          f"{'WIN%':>6}{'REAL':>7}{'MFE':>7}{'MAE':>7}{'GIVE':>7}")
        w("-" * (wide + 43))
    for k, rs in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
        ex    = [excursions(r) for r in rs]
        wins  = sum(1 for r in rs if (fnum(r, "pnl_usd") or 0) > 0)
        sess  = len({_entry_date(r) for r in rs})
        pflag = ""
        if len(rs) < MIN_CELL_N:
            pflag = "  <- UNDERPOWERED"
        elif sess < MIN_SESSIONS:
            pflag = f"  <- {sess} SESSION(S)"
        head = (f"{str(k[0])[:wide]:<{wide}}{str(k[1])[:11]:<12}" if len(keys) > 1
                else f"{str(k[0])[:wide]:<{wide}}")
        w(f"{head}{len(rs):>4}{sess:>5}{wins/len(rs):>6.0%}"
          f"{mean(e[2] for e in ex):>7.0%}{mean(e[0] for e in ex):>7.0%}"
          f"{mean(e[1] for e in ex):>7.0%}{mean(e[0] - e[2] for e in ex):>7.0%}{pflag}")
    w(f"UNDERPOWERED = n < {MIN_CELL_N}; SESSION(S) = drawn from fewer than "
      f"{MIN_SESSIONS} dates.")
    w("Neither is a null result — it is an absent measurement. Do not read a "
      "direction off one.")

    directional = [r for r in rows
                   if not credit_signed(r) and not flag(r, "is_butterfly")]
    winners = [r for r in directional if (fnum(r, "pnl_usd") or 0) > 0]
    cut     = [r for r in winners if excursions(r)[1] <= -tight_floor]
    doomed  = [r for r in winners if excursions(r)[1] <= -wide_floor]
    w("")
    w("FLOOR VERDICT (directional winners only):")
    w(f"  winners total ............................ {len(winners)}")
    w(f"  MAE breached -{tight_floor:.0%} then WON "
      f"(a {tight_floor:.0%} floor would have cut them) {len(cut)}"
      + (f"  avg final {pct(mean(excursions(r)[2] for r in cut))}" if cut else ""))
    w(f"  MAE also breached -{wide_floor:.0%} "
      f"(would have died at {wide_floor:.0%} too)         {len(doomed)}")
    stops = [r for r in directional
             if norm_reason(r.get("exit_reason")).startswith(FLOOR_REASON_PREFIXES)]
    if stops:
        w(f"  floor stops taken ........................ {len(stops)}"
          f"  avg realized {pct(mean(excursions(r)[2] for r in stops))}"
          f"  avg MFE before dying {pct(mean(excursions(r)[0] for r in stops))}")

    w("")
    w("LEASH VERDICT (giveback = MFE - realized, per trail flavor):")
    present = sorted({norm_reason(r.get("exit_reason")) for r in rows})
    flavors = [f for f in TRAIL_FLAVORS if f in present]
    unlisted = [p for p in present if p not in TRAIL_FLAVORS and "trail" in p]
    if not flavors and not unlisted:
        w("  no trail-flavor exits in this window "
          f"(reasons present: {', '.join(present) or 'none'})")
    for flavor in flavors + unlisted:
        rs = [r for r in rows if norm_reason(r.get("exit_reason")) == flavor]
        if not rs:
            continue
        ex = [excursions(r) for r in rs]
        w(f"  {flavor:<20} n={len(rs):<4}"
          f" realized {pct(mean(e[2] for e in ex))}"
          f"  MFE {pct(mean(e[0] for e in ex))}"
          f"  giveback {pct(mean(e[0] - e[2] for e in ex))}"
          f"  (median real {pct(median(e[2] for e in ex))})")
    if unlisted:
        w(f"  ! not in TRAIL_FLAVORS, included on the \"trail\" substring: "
          f"{', '.join(unlisted)} — add them to the list or rename the exit")

    # v3.1 — UNREPORTED REASONS. An exit family that reaches neither block above
    # is invisible in every framed section of this report while still looking
    # present in the --by exit table. `insurance_stop` sat there for weeks.
    _covered = set(flavors) | set(unlisted) | {
        p for p in present if p.startswith(FLOOR_REASON_PREFIXES)}
    _orphans = [p for p in present if p not in _covered]
    if _orphans:
        w("")
        w("  ⚠️ EXIT REASONS REPORTED IN NO VERDICT BLOCK (neither leash nor floor):")
        for p in _orphans:
            _n = sum(1 for r in rows if norm_reason(r.get("exit_reason")) == p)
            w(f"       {p:<26} n={_n}")
        w("     These appear in the --by exit table above and NOWHERE else. If one")
        w("     is a stop or a trail, add it to TRAIL_FLAVORS or FLOOR_REASON_PREFIXES")
        w("     — an omission that renders cleanly is the failure class this repo")
        w("     exists to prevent.")

    # ── NEVER FAVORABLE / WINNER GIVEBACK ───────────────────────────────────
    ex_all = [(r, excursions(r)) for r in rows]
    w("")
    w("NEVER FAVORABLE (trades that never went in your favor)")
    w("  There was no moment to manage these. They are a SELECTION problem;")
    w("  no exit, stop or trail can reach a trade that never traded up.")
    w(f"  {'MFE CUT':>9}{'N':>6}{'SHARE':>7}{'NET $':>12}")
    for cut in NEVER_FAVORABLE_CUTS:
        nf = [(r, e) for r, e in ex_all if e[0] <= cut]
        net = sum(fnum(r, "pnl_usd") or 0 for r, _ in nf)
        w(f"  {cut:>8.0%}{len(nf):>6}{len(nf)/len(rows):>7.0%}{net:>12.2f}")

    base_cut = NEVER_FAVORABLE_CUTS[1]
    nf_rows = {id(r) for r, e in ex_all if e[0] <= base_cut}
    overall = len(nf_rows) / len(rows)
    w("")
    w(f"  COMPOSITION at the {base_cut:.0%} cut — overall rate {overall:.0%}.")
    w("  Read the RATE WITHIN each group, not its share of the bad pile: a")
    w("  group holding 30% of them means nothing if it is 30% of everything.")
    for dim in SPLIT_DIMS:
        groups = {}
        for r in rows:
            groups.setdefault(str(r.get(dim) or "?"), []).append(r)
        # v2.8 — MEDIAN CONVICTION, SPLIT NEVER vs REST. `regime_conviction`
        # has been on every trade row since 2026-07-24 and never appeared in
        # this table. The question it answers is the one the rate cannot: not
        # WHICH cells go wrong, but whether the engine was CONFIDENT when they
        # did. A never-favorable cell whose conviction sits BELOW the rest has a
        # threshold in the wrong place — a cutoff to find. One where the two are
        # equal says conviction does not separate outcomes in that cell at all,
        # which is a much larger finding and cannot be fixed by moving a bar.
        # MEDIAN, not mean: conviction pegs at 1.00 often enough (measured on
        # the A2 co-occurrence ticks) that a mean would be dragged by the peg.
        def _med(rs, field):
            v = [c for c in (fnum(r, field) for r in rs)
                 if c is not None and c > 0]
            return median(v) if v else None

        scored = []
        for v, rs in groups.items():
            nf = [r for r in rs if id(r) in nf_rows]
            ok = [r for r in rs if id(r) not in nf_rows]
            rated = len(rs) >= MIN_GROUP_N
            scored.append((v, len(rs), len(nf), len(nf) / len(rs), rated,
                           _med(nf, "setup_score"), _med(ok, "setup_score"),
                           _med(nf, "regime_conviction"),
                           _med(ok, "regime_conviction")))
        scored.sort(key=lambda t: (-t[4], -t[3]))
        w("")
        w(f"  by {dim}")
        w(f"    {'':<24}{'N':>5}{'NEVER':>7}{'RATE':>7}{'LIFT':>7}"
          f"{'SETUP.nf':>10}{'SETUP.ok':>10}"
          f"{'RGCV.nf':>9}{'RGCV.ok':>9}")
        for v, n, n_nf, rate, rated, s_nf, s_ok, c_nf, c_ok in scored:
            lift = (rate / overall) if overall else 0
            tail = f"{lift:>7.2f}" if rated else "      -"
            sn = f"{s_nf:>10.2f}" if s_nf is not None else f"{'—':>10}"
            so = f"{s_ok:>10.2f}" if s_ok is not None else f"{'—':>10}"
            cn = f"{c_nf:>9.2f}" if c_nf is not None else f"{'—':>9}"
            co = f"{c_ok:>9.2f}" if c_ok is not None else f"{'—':>9}"
            # NOT named `flag` — that is a module-level function used earlier
            # in this same scope, and binding the name locally makes Python
            # treat EVERY reference in build_report as local. The first crash
            # was at line ~500, hundreds of lines above this edit and in
            # unrelated code, before any of it ran.
            thin = "" if rated else "  <- n<%d" % MIN_GROUP_N
            w(f"    {v[:24]:<24}{n:>5}{n_nf:>7}{rate:>7.0%}{tail}"
              f"{sn}{so}{cn}{co}{thin}")
        w("    SETUP = median setup_score (THE NUMBER THAT AUTHORISED THE "
          "TRADE); RGCV = median")
        w("    regime_conviction (L2's confidence in the LABEL — a different "
          "question: a tick can")
        w("    be 1.00-conviction TRENDING_BULL and still be a poor entry). "
          "`.nf` is the")
        w("    never-favorable trades, `.ok` the rest.")
        w("    nf BELOW ok  -> a cutoff exists to find in that column.")
        w("    nf EQUAL ok  -> that score does not separate outcomes here and "
          "no threshold")
        w("                    will fix it — the same verdict a control arm "
          "gives.")
        w("    Split across the two columns tells you WHICH layer is at fault: "
          "setup grading")
        w("    or the label.")

    # ── v2.9 — IS THE SCORE A DIAL OR A SWITCH? ─────────────────────────────
    # The composition table showed SETUP.nf == SETUP.ok at 0.96 on grade A
    # (n=277) and 1.50 on ORB (n=97), with RGCV pegged at 1.00/1.00 on
    # TRENDING_BULL. Identical MEDIANS can mean two very different things: a
    # score that varies but happens to centre in the same place, or a score
    # that is CONSTANT for that population. Only the second makes a threshold
    # impossible, and the median cannot tell them apart.
    # So: percentiles. If p10 == p90, the score is a constant wearing a
    # continuous type — the same "pegged corroborator is a constant in new
    # clothes" failure readiness_digest reports one layer down, surfacing here
    # at the trade level. A score that cannot vary cannot discriminate, and no
    # cutoff exists to find no matter how much sample accrues.
    def _pcts(vals):
        v = sorted(x for x in vals if x is not None and x > 0)
        if len(v) < 8:
            return None
        def q(f):
            return v[min(int(f * len(v)), len(v) - 1)]
        return q(.10), q(.50), q(.90), v[-1]

    w("")
    w("SCORE DISPERSION (is the score a DIAL or a SWITCH?)")
    w("  Identical medians can mean 'varies, same centre' or 'constant'. Only")
    w("  the second makes a cutoff impossible — and the median cannot tell them")
    w("  apart. p10 == p90 means the score does not vary in that population.")
    for field, label in (("setup_score", "SETUP"), ("regime_conviction", "RGCV")):
        w("")
        w(f"  {label} by strategy")
        w(f"    {'':<26}{'N':>5}{'p10':>8}{'p50':>8}{'p90':>8}{'max':>8}"
          f"{'SPREAD':>9}")
        gs = {}
        for r in rows:
            gs.setdefault(str(r.get("strategy") or "?"), []).append(fnum(r, field))
        for v, vals in sorted(gs.items(), key=lambda kv: -len(kv[1])):
            p = _pcts(vals)
            if p is None:
                w(f"    {v[:26]:<26}{len(vals):>5}     — too few scored")
                continue
            p10, p50, p90, mx = p
            spread = p90 - p10
            note = "  <- CONSTANT" if spread < 0.01 else ""
            w(f"    {v[:26]:<26}{len(vals):>5}{p10:>8.2f}{p50:>8.2f}"
              f"{p90:>8.2f}{mx:>8.2f}{spread:>9.2f}{note}")
    w("")
    w("  A CONSTANT row is not a tuning problem. No threshold on that score can")
    w("  separate its outcomes, because the score has no variation to threshold.")
    w("  Fixing it means changing what the score MEASURES, not where the bar sits.")

    winners = [(r, e) for r, e in ex_all if (fnum(r, "pnl_usd") or 0) > 0]
    w("")
    w("WINNER GIVEBACK (capture = realized / MFE, winners only)")
    if winners:
        caps = [e[2] / e[0] for _, e in winners if e[0] > 0]
        if caps:
            w(f"  n={len(caps)}  median capture {median(caps):.0%}  "
              f"mean {mean(caps):.0%}  median MFE "
              f"{median(e[0] for _, e in winners):.0%}")
        for dim in ("strategy", "regime"):
            groups = {}
            for r, e in winners:
                if e[0] > 0:
                    groups.setdefault(str(r.get(dim) or "?"), []).append(e[2] / e[0])
            w(f"  by {dim}")
            for v, cs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
                mark = "" if len(cs) >= MIN_GROUP_N else f"  <- n<{MIN_GROUP_N}"
                w(f"    {v[:24]:<24}{len(cs):>5}  capture {median(cs):>5.0%}{mark}")
    else:
        w("  no winners in this window")
    # v2.6 — the question the block above used to declare unanswerable. It is
    # answerable now: trade_logger v3.9 (2026-08-03) added max_premium_seen_at /
    # min_premium_seen_at, so a winner's PEAK has a time and the fraction of the
    # hold it took to get there separates the two cases that call for OPPOSITE
    # fixes — peaked early and bled (the trail is too loose) from ran to the
    # exit and turned (the move simply ended).
    # NULL ON EVERY PRE-DEPLOY ROW, and that is reported rather than imputed:
    # v3.9 columns exist only for trades entered after it shipped, so a window
    # spanning the deploy will show partial coverage.
    peak_fracs, n_no_ts = [], 0
    for r, e in winners:
        f = peak_fraction(r)
        if f is None:
            n_no_ts += 1
        else:
            peak_fracs.append(f)
    w("")
    w("  PEAK TIMING (v3.9 timestamps) — when in the hold did MFE happen?")
    if len(peak_fracs) < MIN_GROUP_N:
        w(f"    n={len(peak_fracs)} REFUSED (under n={MIN_GROUP_N})"
          f"   [{n_no_ts} winner(s) predate the v3.9 columns]")
    else:
        pf = sorted(peak_fracs)
        early = sum(1 for x in pf if x <= 0.33) / len(pf)
        late = sum(1 for x in pf if x >= 0.67) / len(pf)
        w(f"    n={len(pf)}   median {median(pf):.0%} of the hold"
          f"   early(<=33%) {early:.0%}   late(>=67%) {late:.0%}"
          + (f"   [{n_no_ts} pre-v3.9]" if n_no_ts else ""))
        w("    A high EARLY share is a LOOSE TRAIL — the peak was available and")
        w("    the exit gave it back. A high LATE share is a move that ran to the")
        w("    exit and turned, which no trail setting recovers. They call for")
        w("    opposite fixes, and giveback alone cannot tell them apart.")

    # ── FLOOR SWEEP ─────────────────────────────────────────────────────────
    w("")
    w("FLOOR SWEEP (counterfactual: where should the stop sit, per cell?)")
    w("  Every trade contributes its MAE whether or not a floor exit fired, so")
    w("  this costs ONE cell of sample, not one per exit reason.")
    w("  ASSUMES: fill AT the floor, no slippage; MAE sampled at the ~15s tick")
    w("  so an intra-tick spike through the level is invisible; a terminal stop")
    w("  has no path after it. That last one holds for a FLOOR and NOT for a")
    w("  trail or a target — this method cannot answer the trail question.")
    for k, rs in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
        cell = " / ".join(str(x) for x in k)
        ex = [excursions(r) for r in rs]
        sess = len({_entry_date(r) for r in rs})
        w("")
        w(f"  {cell}   n={len(rs)}  sessions={sess}")
        if len(rs) < MIN_CELL_N or sess < MIN_SESSIONS:
            w(f"    REFUSED — n<{MIN_CELL_N} or sessions<{MIN_SESSIONS}. "
              f"Underpowered, not a null.")
            continue
        w(f"    {'FLOOR':>7}{'STOPPED':>9}{'WINNERS CUT':>13}{'NET DELTA':>11}")
        for f in FLOOR_CANDIDATES:
            stopped = [e for e in ex if e[1] <= -f]
            cut = [e for e in stopped if e[2] > 0]
            delta = sum((-f) - e[2] for e in stopped)
            w(f"    {f:>6.0%}{len(stopped):>9}{len(cut):>13}{delta:>+11.2f}")
        w("    NET DELTA is in units of entry premium, summed over the cell: "
          "positive")
        w("    means the floor would have kept money. NO BEST FLOOR IS NAMED — "
          "the")
        w("    in-sample argmax is overfit by construction. Pre-register a rule "
          "or")
        w("    hold out sessions before choosing.")
    w("")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description="MFE/MAE report from the "
                                             "consolidated fleet trades file")
    ap.add_argument("--date", default=date.today().isoformat(),
                    help="snapshot day, YYYY-MM-DD (default today)")
    ap.add_argument("--since",
                    help="cumulative: include trades entered ON/AFTER this "
                         "date (default: the snapshot day only)")
    ap.add_argument("--strategy", help="strategy substring filter")
    ap.add_argument("--by", default="exit", choices=sorted(GROUP_KEYS),
                    help="group the table and floor sweep by this dimension "
                         "(default exit = the pre-v2.4 exit x strategy view)")
    ap.add_argument("--live", action="store_true",
                    help="live rows (default: paper)")
    args = ap.parse_args()

    all_rows, src = load_day(args.date, args.since or "")
    if all_rows is None:
        print(f"No trades/{args.date}/*_trades.db and no "
              f"fleet_trades_{args.date}.json/.csv — nothing collected for "
              f"that day yet.", file=sys.stderr)
        sys.exit(1)

    # v2.7 — the refusal now also fires when the RANGE collapsed to one
    # session. Post-trim each folder holds one day, so a --since that reads a
    # single folder is not cumulative no matter what the header claims — and
    # that is exactly how "since 2026-07-23" reported 96 trades from one
    # session on 2026-08-05 while looking entirely normal.
    # v3.0 — SUBSTRING BUG. This read `"1 session(s)" in src`, and
    # "165 DBs across 11 session(s)" CONTAINS "1 session(s)" — so an 11-session
    # cumulative read was refused as if it had collapsed to one, and so would
    # 21, 31, 41 or any count ending in 1. The guard's INTENT is right (v2.7
    # added it after a --since silently read a single folder and reported 96
    # trades as though cumulative); the TEST was wrong. Anchor on the word
    # "across" so the match cannot slide into a longer number.
    if args.since and "(" in src and "across 1 session(s)" in src:
        print(f"REFUSED: --since {args.since} resolved to ONE session "
              f"({src}). Since the 2026-08-05 trim each dated folder holds a "
              f"single trading day, so a cumulative read needs the folders in "
              f"between to exist. Check trades/ for the range.", file=sys.stderr)
        sys.exit(2)
    if args.since and "(" not in src:
        print(f"REFUSED: --since {args.since} needs the per-box DBs in "
              f"trades/{args.date}/ — each snapshot carries that box's FULL "
              f"history, which is the only thing --since can widen. Only the "
              f"single-day fallback {os.path.basename(src)} was found, and "
              f"--since over it filters one session's rows while still "
              f"labelling the report cumulative. Re-run without --since, or "
              f"after harvest lands trades/{args.date}/*_trades_{args.date}.db.",
              file=sys.stderr)
        sys.exit(2)

    closed  = [r for r in all_rows if (r.get("status") or "") == "closed"]
    if args.since:
        closed = [r for r in closed if _entry_date(r) >= args.since]
    else:
        closed = [r for r in closed if _entry_date(r) == args.date]
    rows    = [r for r in closed if usable(r, paper=not args.live)]
    if args.strategy:
        rows = [r for r in rows if args.strategy.lower()
                in (r.get("strategy") or "").lower()]
    skipped = sum(1 for r in closed
                  if fnum(r, "max_premium_seen") is None
                  or fnum(r, "min_premium_seen") is None)

    hints = []
    if not rows:
        if "(" not in src:   # fell back to fleet_trades json/csv — DBs absent
            hints.append(f"trades/{args.date}/ per-symbol DBs not collected yet "
                         f"— the EOD chain lands them ~16:05 ET; re-run after "
                         f"the close (fallback file {os.path.basename(src)} "
                         f"had nothing usable)")
        other = [r for r in closed if usable(r, paper=args.live)]
        if other:
            want, have = ("LIVE", "PAPER") if args.live else ("PAPER", "LIVE")
            hints.append(f"{len(other)} telemetry row(s) exist but are {have}, "
                         f"not {want} — answer {'N' if args.live else 'y'} to "
                         f"the Live prompt")
        if skipped:
            hints.append(f"{skipped} closed row(s) have no telemetry "
                         f"(entered/closed before the v3.8 columns were live)")
        if not hints:
            hints.append("no trades closed in this window yet")
    window = (f"since {args.since}" if args.since else "that day only")
    text = build_report(rows, f"{args.date} ({window})", src, skipped,
                        "LIVE" if args.live else "PAPER", hints=hints,
                        group_by=args.by)
    print(text)

    os.makedirs(REPORTS_DIR, exist_ok=True)
    suffix = "_live" if args.live else ""
    out_path = os.path.join(REPORTS_DIR, f"excursions_{args.date}{suffix}.txt")
    with open(out_path, "w") as f:
        f.write(text)
    print(f"Report written: {out_path}")


if __name__ == "__main__":
    main()
