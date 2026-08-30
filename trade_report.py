# day_trader_pro/trade_report.py — v1.10
# v1.10 (2026-08-29) — r190 / dtp r231. THE DEDUP SHIM IS GONE, AND WHAT
#   REPLACES IT IS A DETECTOR (backlog S3.6).
#   🔑 IT WAS NEVER A DESIGN FEATURE. Its own v1.1 changelog (2026-07-22)
#   says so: before consolidate_trades v1.2 added a date filter on 07-28,
#   harvest scp'd each box's ENTIRE trades.db and consolidate did a bare
#   SELECT *, so every fleet_trades_<date>.json held that box's FULL HISTORY
#   and pooling N bundles counted each trade up to N times. The dedup existed
#   solely to survive those cumulative archives sitting in the glob. r187
#   moved the default source to reports/warehouse, where every bundle is
#   built by warehouse_reader.build() from ONE dt= partition and is already
#   collapsed by latest_per_trade(). There is nothing left to de-duplicate.
#   🔴 AND KEEPING IT WAS THE ACTUAL DEFECT, NOT MERELY DEAD CODE. TWO
#   DEDUP RULES RAN ON THE SAME DATA WITH DIFFERENT TIE-BREAKS:
#   warehouse_reader.latest_per_trade() keeps the newest `pushed_at_utc`;
#   this file kept the MOST-FILLED row (`_filled()`, a count of non-empty
#   columns). They have agreed so far because the newest state also happened
#   to be the most-filled one. **That is luck.** A trade whose final CDC row
#   nulls a column would have been silently resolved differently by each,
#   and nothing anywhere compared them — report parity could not catch it,
#   because parity runs BOTH sides through this same rule.
#   ⚠️ SO IT IS NOT DELETED, IT IS INVERTED. Silently collapsing a
#   duplicate now hides the only two conditions that can still produce one:
#   a legacy CUMULATIVE bundle in an explicit --bundles-dir, or two bundles
#   for the same date. Both are real problems and both used to be absorbed
#   without a word. Duplicates are now FIRST-WINS by sorted filename
#   (deterministic, not arbitrary) and REPORTED BY trade_id AND BY FILE.
#   ⚠️ `_filled()` is removed entirely rather than left unused. An
#   orphaned tie-break helper is exactly what gets re-wired by the next
#   person who needs 'a way to pick between two rows'.
# v1.9 (2026-08-29) — r187 / dtp r228. THREE CHANGES, backlog S3.5.
#   (1) THE DEFAULT SOURCE IS THE WAREHOUSE. The old default globbed
#       reports/fleet_trades_*.json at the repo root — a directory NOTHING
#       WRITES ANY MORE. eod_analysis v1.2 builds its bundle into
#       reports/warehouse/, and install_eod_v2.sh disabled dtp-harvest.timer,
#       so whatever sits at the root is a frozen snapshot of a pipeline that
#       stopped running (backlog C.12). A default pointing at a folder nobody
#       fills does not fail — it QUIETLY REPORTS OLD NUMBERS, which is worse.
#       --bundles-dir still overrides, and report_parity passes both sides
#       explicitly so it is unaffected.
#   (2) 🔴 AN ENGINE EPOCH, DEFAULTING TO 2026-08-25. Operator, that day:
#       "today is day one and anything prior to today was the old engines."
#       Every bundle in the warehouse reaches back to July, so an unqualified
#       cross-day run POOLS TWO DIFFERENT TRADING SYSTEMS in one table with
#       nothing marking the boundary. That has already produced one wrong
#       conclusion quoted as evidence. The floor is now the default and
#       --all-history is the explicit override.
#       ⚠️ IT IS LOUD, NOT SILENT. The count of excluded pre-epoch
#       trades prints on every run. A filter you cannot see is how you end up
#       arguing about a number that was never in the sample.
#   (3) BY SETUP GRADE IS REMOVED. Every v4 write path hardcodes
#       setup_grade="UNGRADED" (entry_engine:212, main:2135, condor_roll:789,
#       base_strategy:127) and nothing writes setup_score at all — r152
#       deleted the scorer because it SELECTED LOSERS (A-grade -$8,244 vs
#       B-grade +$1,893 over 619 trades). The section had exactly one bucket.
#       ⚠️ The COLUMN stays (check_conviction_removed S6 pins it) and the
#       field still rides on every row; only the dimension is gone, replaced
#       by one line of fact so its absence is stated rather than mysterious.
# v1.8 (2026-08-16) — --out, so a caller can name the JSON exactly. The parity
#   tool had been picking the newest trade_report_<stamp>.json by MTIME, which
#   is a guess: it read a stale full-fleet run instead of the restricted one it
#   had just produced, and reported 25 sessions against 1 as a warehouse
#   divergence. Identifying a file by "probably the newest" is not identifying
#   it.
# v1.7 (2026-08-16) — a warehouse-sourced run writes trade_report_warehouse_*
#   and records its source in the payload. v1.6 wrote the same stamped filename
#   for both sources, so the two were distinguishable only by mtime — and a
#   comparison you can only make by checking timestamps is one you will get
#   wrong once.
# v1.6 (2026-08-16) — --bundles-dir, for WH.11. Lets this report run against
#   warehouse-sourced bundles in reports/warehouse/ so the OUTPUTS of both
#   sources can be diffed — bundle-level equivalence does not establish that
#   the reports agree. Default is unchanged; the local path is byte-identical
#   to v1.5. ⚠️ Note the glob it depends on: reports/fleet_trades_*.json is
#   this report's INPUT, so anything written beside those files becomes its
#   data whether or not that was intended.
# v1.5 (2026-08-04) — HEADLINE stops printing false sentences. rank() now
#   returns how many buckets cleared the sample floor, and the printer refuses
#   the word "worst" when there is only one (it was naming the SAME bucket as
#   best and worst — day_of_week: Tuesday twice, on a single-session report) and
#   flags it as LOWEST-not-a-loss when every eligible bucket is positive
#   (2026-08-04 announced a "worst ... net +1041.50", the
#   second-best bucket, on a profit). Arithmetically right, semantically false —
#   and it is the section people skim.
# v1.4 — 2026-08-03 — EXIT SPREAD + a contaminated verdict fenced off.
#        (a) by_exit_reason and by_session_date existed as separate marginals,
#        which cannot answer the question they get asked: is an exit reason a
#        STANDING pattern or ONE session? The 2026-08-03 cumulative showed
#        bos_exit/Continuation at n=21 over nine sessions — the same 21 the
#        single-day run showed, i.e. possibly every one of them on one day,
#        while every other exit grew 3-6x. Marginals hide that; a cross shows
#        it. New EXIT REASON x SESSION SPREAD block reports, per exit reason,
#        how many distinct sessions it fired on and what share landed on its
#        heaviest one, flagging >=80% as SINGLE-SESSION. exit_x_date is also
#        written to the JSON in full.
#        (b) flag_runners_cut_early was computed over EVERY row including the
#        sub-minute flicker (main.py pre-v5.0: median hold 0.8 min, p25 12
#        SECONDS — 44 of 88 rows on 2026-08-03 alone). Those exits were a
#        DEFECT, not exit behaviour, and they drag both medians toward zero, so
#        a ratio built on them is evidence about a bug rather than about
#        leashes. Nothing is silently dropped — the ratio is now reported both
#        ways with the sub-minute count stated, and the "runners cut early"
#        NOTE is withheld when sub-minute rows exceed 10% of the sample, since
#        at that point the ratio is measuring the flicker.
# v1.3 — 2026-08-03 — +SENTIMENT dimension, and the cross that actually answers
#        the operator's question. Idea: "I didn't think it would be wise to short
#        into positive tailwinds or fire longs into headwinds." That is a claim
#        about sentiment x DIRECTION, so `sentiment_x_direction` is the cross that
#        matters — sentiment x strategy would not test it.
#        SOURCE: reports/morning_report_<date>.json, archived nightly by
#        eod_conductor v1.12.0 phase 5c. data/report.json is overwritten every
#        09:15, so before that phase the day's scores were destroyed before they
#        could be joined to that day's outcomes. Joined by (session date, symbol),
#        the same shape gap_pct uses — the score is per SYMBOL PER DAY, so every
#        trade on a symbol-day inherits one value.
#        READ THE COVERAGE LINE FIRST. `brief_strength` was a hardcoded 0.30 for
#        EVERY name every day until the DTP_REPORT_JSON fix landed after the close
#        on 2026-07-30, and archiving only began 2026-08-03 — so there is almost
#        no data yet and this dimension will be empty or trivial for weeks. It
#        prints how many trades actually carried a score rather than silently
#        ranking a handful. Expect it to become readable around 2026-09-05.
#        SELECTION TRUNCATES THE RANGE, which is worth remembering when reading
#        any result: sentiment already chooses which 13 discretionary boxes wake,
#        so only high-scoring symbols trade at all. The bands below therefore see
#        the TOP of the distribution, not its spread, and a null here is weaker
#        evidence than a null on an untruncated variable would be.
# v1.2 — 2026-07-22 — Machine-readable artifact + new dimensions. Writes
#        reports/trade_report_<last-session>.json containing every bucket with
#        full stats plus a FINDINGS block (best/worst strategy, setup,
#        symbol, hour, weekday, exit reason, and the single
#        best/worst trade). New display dimensions: by symbol, by hour (ET), by
#        weekday, by session phase, by session date. Best/worst claims only
#        consider buckets with n >= --min-n so a 1-trade bucket cannot win.
# v1.1 — 2026-07-22 — CRITICAL FIX: de-duplicate by trade_id. harvest.py scp's
#        each box's ENTIRE trades.db and consolidate_trades.py does a bare
#        SELECT * with no date filter, so every fleet_trades_<date>.json holds
#        that box's FULL history — pooling N bundles counted each trade up to N
#        times. Now keyed on trade_id; session dates derived from entry_time.
#        Also normalises exit_reason (strips ' pnl=...'), matching
#        excursion_report.norm_reason.
# v1.0 — 2026-07-22 — NEW. Cross-day trade breakdown ranked by net.
"""
Cross-day trade breakdown — what actually made and lost money, ranked.

Read-only. Pools every closed trade from the fleet_trades_<date>.json bundles
consolidate_trades.py writes, de-duplicates, and ranks across every dimension
that matters. Prints a summary and writes a data-rich JSON for further analysis
(or to hand to Claude).

Timestamps in the DB are UTC ISO (ts_for_db); hour-of-day and weekday are
converted to ET so "the 10 o'clock hour" means the market's 10 o'clock.

Usage:
    python trade_report.py                     # all banked sessions
    python trade_report.py --since 2026-07-14
    python trade_report.py --min-n 10          # thin-bucket threshold (default 8)
    python trade_report.py --live | --paper
    python trade_report.py --no-json           # display only
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    import config
    REPORTS_DIR = getattr(config, "REPORTS_DIR",
                          os.path.expanduser("~/day_trader_pro/reports"))
except Exception:                                     # standalone
    REPORTS_DIR = os.path.expanduser("~/day_trader_pro/reports")

BUNDLE_GLOB = os.path.join(REPORTS_DIR, "fleet_trades_*.json")

# v1.9 — the warehouse-sourced bundles eod_analysis writes nightly. This is
# the DEFAULT now; BUNDLE_GLOB survives only as the explicit legacy path.
WAREHOUSE_DIR = os.path.join(REPORTS_DIR, "warehouse")

# 🔴 DAY ONE. Operator, 2026-08-25: "today is day one and anything prior to
# today was the old engines. Those are not gonna be included in any study that
# we do." Overridable by env for a deliberate archaeology run, but the DEFAULT
# must be the honest one — a contaminated pool is the one mistake this report
# has already been used to make.
ENGINE_EPOCH = os.environ.get("DTP_ENGINE_EPOCH", "2026-08-25")

try:
    from zoneinfo import ZoneInfo
    _ET = ZoneInfo("America/New_York")
except Exception:                                     # no tzdata
    _ET = None

_DOW = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
        "Saturday", "Sunday"]


# ── helpers ──────────────────────────────────────────────────────────────────
# Fixed bands rather than per-run terciles, so a bucket means the same thing
# across runs and two reports can be compared. Chosen against the 2026-08-03
# wake spread (MSFT 1.00 .. XOM 0.30): HIGH ~7 names, MID ~5, LOW ~1.
SENTIMENT_BANDS = ((0.70, "HIGH >=0.70"), (0.40, "MID 0.40-0.70"))
SENTIMENT_LOW = "LOW <0.40"


def sentiment_band(score) -> str:
    if score is None:
        return "no score"
    for lo, label in SENTIMENT_BANDS:
        if score >= lo:
            return label
    return SENTIMENT_LOW


def load_sentiment(reports_dir) -> Dict[str, Dict[str, float]]:
    """{date: {SYMBOL: strength}} from the archived morning reports.

    Returns {} when nothing has been archived yet, which is the normal state
    until eod_conductor v1.12.0 phase 5c has run a few times. Callers must treat
    an empty result as "not measured yet", never as "no relationship".
    """
    out: Dict[str, Dict[str, float]] = {}
    for path in glob.glob(os.path.join(reports_dir, "morning_report_*.json")):
        m = re.search(r"(20\d\d-\d\d-\d\d)", os.path.basename(path))
        if not m:
            continue
        try:
            payload = json.load(open(path))
        except Exception:                                         # noqa: BLE001
            continue
        # the brief exposes per-symbol strength under a couple of shapes; take
        # whichever is present rather than assuming one and silently finding none
        src = (payload.get("strength_by_sym") or payload.get("strength")
               or payload.get("scores") or {})
        if isinstance(src, dict):
            out[m.group(1)] = {str(k).upper(): _f(v) for k, v in src.items()
                               if _f(v) is not None}
    return out


def norm_reason(reason) -> str:
    """exit_reason carries a ' pnl=...' suffix — strip it, or one reason
    shatters into dozens of thin buckets. Matches excursion_report."""
    r = (reason or "unknown").strip()
    if r.startswith("hard_close"):
        return "hard_close"
    return r.split(" pnl=")[0].split(":")[0].strip() or "unknown"


def _truthy(v) -> bool:
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "t", "1.0")
    return bool(v)


def _f(v) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _dt(v) -> Optional[datetime]:
    if not v:
        return None
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def to_et(v) -> Optional[datetime]:
    d = _dt(v)
    if d is None:
        return None
    return d.astimezone(_ET) if _ET else d - timedelta(hours=4)


def hold_minutes(row) -> Optional[float]:
    a, b = _dt(row.get("entry_time")), _dt(row.get("exit_time"))
    if not a or not b:
        return None
    m = (b - a).total_seconds() / 60.0
    return m if m >= 0 else None


def session_phase(et: Optional[datetime]) -> str:
    if et is None:
        return "(unknown)"
    m = et.hour * 60 + et.minute
    if m < 10 * 60:
        return "1 open 09:30-10:00"
    if m < 11 * 60:
        return "2 morning 10:00-11:00"
    if m < 14 * 60:
        return "3 midday 11:00-14:00"
    if m < 15 * 60 + 30:
        return "4 afternoon 14:00-15:30"
    return "5 close 15:30-16:00"


# ── loading ──────────────────────────────────────────────────────────────────
def load_trades(since, mode, bundles_dir=None):
    """Closed trades pooled from the bundles in `bundles_dir` (default: S3-sourced).

    -> (trades, by_day, raw_rows, duplicates). `duplicates` is a list of
    (trade_id, first_file, later_file) and SHOULD ALWAYS BE EMPTY: each bundle
    is one dt= partition already collapsed by warehouse_reader.latest_per_trade.
    A non-empty list means a legacy cumulative bundle is in the glob, or two
    bundles cover the same date — both worth knowing, neither worth absorbing.
    """
    seen: Dict[str, dict] = {}
    origin: Dict[str, str] = {}
    dupes = []
    raw = 0
    pattern = (os.path.join(bundles_dir, "fleet_trades_*.json")
               if bundles_dir else BUNDLE_GLOB)
    for path in sorted(glob.glob(pattern)):
        try:
            with open(path) as fh:
                bundle = json.load(fh)
        except Exception as exc:                       # noqa: BLE001
            print(f"  ! skipped {os.path.basename(path)}: {exc}", file=sys.stderr)
            continue
        rows = [r for r in (bundle.get("trades") or [])
                if (r.get("status") or "") == "closed"]
        if mode == "live":
            rows = [r for r in rows if not _truthy(r.get("paper_trade"))]
        elif mode == "paper":
            rows = [r for r in rows if _truthy(r.get("paper_trade"))]
        raw += len(rows)
        base = os.path.basename(path)
        for r in rows:
            tid = str(r.get("trade_id") or "") or \
                  f"{r.get('box')}|{r.get('entry_time')}|{r.get('strike')}"
            if tid in seen:
                # FIRST WINS, by sorted filename, so the result is deterministic
                # rather than dependent on which row happened to look fuller.
                dupes.append((tid, origin[tid], base))
                continue
            seen[tid] = r
            origin[tid] = base

    trades = list(seen.values())
    by_day: Dict[str, int] = defaultdict(int)
    for r in trades:
        et = to_et(r.get("entry_time"))
        r["_date"] = et.strftime("%Y-%m-%d") if et else "(no date)"
        r["_hour_et"] = f"{et.hour:02d}:00 ET" if et else "(unknown)"
        r["_dow"] = _DOW[et.weekday()] if et else "(unknown)"
        r["_phase"] = session_phase(et)
        r["_hold"] = hold_minutes(r)
        r["_sym"] = str(r.get("symbol") or r.get("box") or "(none)")
        by_day[r["_date"]] += 1
    if since:
        trades = [r for r in trades if r["_date"] >= since]
        by_day = {d: n for d, n in by_day.items() if d >= since}
    return trades, sorted(by_day.items()), raw, dupes


# ── aggregation ──────────────────────────────────────────────────────────────
def bucket(trades: List[dict], key: str) -> Dict[str, dict]:
    agg: Dict[str, list] = defaultdict(list)
    for t in trades:
        if _f(t.get("pnl_usd")) is None:
            continue
        if key == "exit_reason":
            k = norm_reason(t.get("exit_reason"))
        elif key.startswith("_"):
            k = t.get(key) or "(none)"
        else:
            k = t.get(key) or "(none)"
        agg[str(k)].append(t)
    return {k: stats_of(v) for k, v in agg.items()}


def stats_of(rows: List[dict]) -> dict:
    pnls = [_f(r.get("pnl_usd")) for r in rows]
    pnls = [p for p in pnls if p is not None]
    holds = [r["_hold"] for r in rows if r.get("_hold") is not None]
    wins = [p for p in pnls if p > 0]
    n = len(pnls)
    return {
        "n": n,
        "wins": len(wins),
        "losses": n - len(wins),
        "win_rate": round(len(wins) / n, 4) if n else 0.0,
        "net": round(sum(pnls), 2),
        "avg": round(sum(pnls) / n, 2) if n else 0.0,
        "median": round(statistics.median(pnls), 2) if pnls else 0.0,
        "stdev": round(statistics.stdev(pnls), 2) if len(pnls) > 1 else 0.0,
        "best": round(max(pnls), 2) if pnls else 0.0,
        "worst": round(min(pnls), 2) if pnls else 0.0,
        "gross_win": round(sum(wins), 2),
        "gross_loss": round(sum(p for p in pnls if p <= 0), 2),
        "median_hold_min": round(statistics.median(holds), 1) if holds else None,
    }


def cross(trades: List[dict], k1: str, k2: str) -> Dict[str, dict]:
    agg: Dict[str, list] = defaultdict(list)
    for t in trades:
        if _f(t.get("pnl_usd")) is None:
            continue
        a = norm_reason(t.get(k1)) if k1 == "exit_reason" else (t.get(k1) or "(none)")
        b = norm_reason(t.get(k2)) if k2 == "exit_reason" else (t.get(k2) or "(none)")
        agg[f"{a} / {b}"].append(t)
    return {k: stats_of(v) for k, v in agg.items()}


def rank(d: Dict[str, dict], min_n: int, worst: bool = False):
    """Best/worst by NET among buckets meeting the sample floor.

    v1.5 — returns `n_elig` so the caller can refuse to say "worst" when the
    word would be a lie. On 2026-08-04 only TWO buckets in one dimension cleared
    the floor and BOTH were positive, so the report announced a
    `worst ... net +1041.50` — the second-BEST bucket, on a
    positive number, labelled worst. With one eligible bucket it printed the
    SAME bucket as both best and worst (day_of_week: Tuesday twice). The ranking
    was arithmetically correct and the sentence was false, which is the class of
    output this repo keeps paying for.
    """
    elig = {k: v for k, v in d.items() if v["n"] >= min_n}
    if not elig:
        return None
    k = (min if worst else max)(elig, key=lambda x: elig[x]["net"])
    return {"key": k, "n_elig": len(elig), **elig[k]}


def trade_extremes(trades: List[dict]) -> Tuple[Optional[dict], Optional[dict]]:
    scored = [t for t in trades if _f(t.get("pnl_usd")) is not None]
    if not scored:
        return None, None
    # ⚠️ THE RETIRED CLASSIFIER'S COLUMN IS GONE FROM THIS LIST (r204). otv4
    # PHYSICALLY DROPPED it in r65, so reading it on a post-r65 row is
    # not merely empty — the column does not exist, and a SELECT naming it
    # RAISES. Carrying it here produced a column of Nones at best.
    keys = ("trade_id", "_date", "_sym", "strategy", "setup_type", "setup_grade",
            "pnl_usd", "exit_reason", "contracts", "entry_premium",
            "exit_premium", "entry_time", "exit_time", "_hold")
    def slim(t):
        return {k: t.get(k) for k in keys}
    return (slim(max(scored, key=lambda t: _f(t["pnl_usd"]))),
            slim(min(scored, key=lambda t: _f(t["pnl_usd"]))))


def exit_behaviour(trades: List[dict]) -> dict:
    wh, lh, mfe, mae = [], [], [], []
    for t in trades:
        p = _f(t.get("pnl_usd"))
        if p is None:
            continue
        h, e = t.get("_hold"), _f(t.get("entry_premium"))
        mx, mn = _f(t.get("max_premium_seen")), _f(t.get("min_premium_seen"))
        if p > 0:
            if h is not None:
                wh.append(h)
            if e and mx:
                mfe.append((mx - e) / e)
        else:
            if h is not None:
                lh.append(h)
            if e and mn:
                mae.append((mn - e) / e)
    med = lambda v: round(statistics.median(v), 4) if v else None   # noqa: E731
    out = {
        "winner_median_hold_min": round(statistics.median(wh), 1) if wh else None,
        "loser_median_hold_min": round(statistics.median(lh), 1) if lh else None,
        "winner_median_mfe_pct": med(mfe),
        "loser_median_mae_pct": med(mae),
        "n_winners": len(wh), "n_losers": len(lh),
    }
    if wh and lh and statistics.median(lh) > 0:
        r = statistics.median(wh) / statistics.median(lh)
        out["winner_loser_hold_ratio"] = round(r, 2)
        out["flag_runners_cut_early"] = r < 1.2
    # Sub-minute holds are not exit behaviour. The pre-v5.0 flicker
    # closed positions in a median 0.8 min (p25 12 seconds); pooling those with
    # real exits pulls both medians toward zero and makes the ratio a statement
    # about a defect. Reported alongside, never substituted, never dropped.
    sub = sum(1 for t in trades
              if (t.get("_hold") is not None and t["_hold"] < 1.0))
    n_held = len(wh) + len(lh)
    out["sub_minute_rows"] = sub
    out["sub_minute_share"] = round(sub / n_held, 3) if n_held else None
    wh2 = [h for h in wh if h >= 1.0]
    lh2 = [h for h in lh if h >= 1.0]
    if wh2 and lh2 and statistics.median(lh2) > 0:
        r2 = statistics.median(wh2) / statistics.median(lh2)
        out["winner_loser_hold_ratio_ex_submin"] = round(r2, 2)
        out["n_winners_ex_submin"] = len(wh2)
        out["n_losers_ex_submin"] = len(lh2)
    return out


def exit_concentration(trades: List[dict], min_n: int) -> Dict[str, dict]:
    """Per exit reason: how many sessions did it fire on, and how much of it
    landed on its heaviest one? A reason that is 100% one date is a single-day
    event wearing a cumulative label."""
    by_reason: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for t in trades:
        by_reason[norm_reason(t.get("exit_reason"))][t.get("_date") or "(none)"] += 1
    out = {}
    for reason, dates in by_reason.items():
        total = sum(dates.values())
        top_date, top_n = max(dates.items(), key=lambda kv: kv[1])
        out[reason] = {
            "n": total, "sessions": len(dates), "top_date": top_date,
            "top_n": top_n, "top_share": round(top_n / total, 3),
            "single_session": (top_n / total) >= 0.80 and total >= min_n,
        }
    return out


# ── display ──────────────────────────────────────────────────────────────────
def show(title: str, d: Dict[str, dict], min_n: int, width: int = 26) -> None:
    if not d:
        return
    print(f"\n{title}")
    print(f"  {'':<{width}}{'N':>5}{'WIN%':>7}{'NET $':>11}{'AVG $':>9}{'HOLD m':>7}")
    for k, a in sorted(d.items(), key=lambda kv: -kv[1]["net"]):
        h = f"{a['median_hold_min']:>7.1f}" if a["median_hold_min"] is not None else "      -"
        flag = "  <- thin" if a["n"] < min_n else ""
        print(f"  {k[:width]:<{width}}{a['n']:>5}{a['win_rate']:>7.0%}"
              f"{a['net']:>11.2f}{a['avg']:>9.2f}{h}{flag}")


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description="cross-day trade breakdown")
    ap.add_argument("--since", help="only sessions on/after YYYY-MM-DD")
    ap.add_argument("--min-n", type=int, default=8,
                    help="thin-bucket flag AND best/worst sample floor (default 8)")
    ap.add_argument("--no-json", action="store_true", help="display only")
    ap.add_argument("--out", default=None,
                    help="write the JSON here instead of the stamped default")
    ap.add_argument("--bundles-dir", default=None,
                    help=f"read bundles from here (default {WAREHOUSE_DIR}); "
                         f"pass {REPORTS_DIR} for the legacy root bundles")
    ap.add_argument("--all-history", action="store_true",
                    help=f"drop the {ENGINE_EPOCH} engine epoch and pool every "
                         f"session, INCLUDING pre-v4 records")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--live", action="store_true")
    g.add_argument("--paper", action="store_true")
    args = ap.parse_args(argv[1:])
    mode = "live" if args.live else ("paper" if args.paper else "all")

    src_dir = args.bundles_dir or WAREHOUSE_DIR
    # ⚠️ THE FLOOR IS RESOLVED HERE AND PRINTED, NEVER APPLIED QUIETLY.
    if args.all_history:
        since, floor_note = args.since, "NO EPOCH FLOOR (--all-history)"
    elif args.since:
        since = args.since
        floor_note = (f"--since {args.since}" +
                      ("   🔴 EARLIER THAN THE ENGINE EPOCH " + ENGINE_EPOCH +
                       " — THIS POOL MIXES v3 AND v4 RECORDS"
                       if args.since < ENGINE_EPOCH else ""))
    else:
        since, floor_note = ENGINE_EPOCH, f"engine epoch {ENGINE_EPOCH} (default)"

    trades, used, raw, dupes = load_trades(since, None if mode == "all" else mode,
                                           bundles_dir=src_dir)
    # How much the floor removed, so the filter is visible rather than inferred.
    _all, _allday, _, _ = load_trades(None, None if mode == "all" else mode,
                                      bundles_dir=src_dir)
    dropped = len(_all) - len(trades)

    print(f"SOURCE: {src_dir}/fleet_trades_*.json")
    print(f"WINDOW: {floor_note}")
    if dropped:
        # 🔴 SAY IT EVERY RUN. A filter you cannot see is how you end up
        # arguing about a number that was never in the sample.
        print(f"        {dropped} closed trade(s) EXCLUDED as pre-epoch "
              f"(--all-history to include them)")
    if not trades:
        if _all:
            print(f"No closed trades on/after {since} in {src_dir} — but "
                  f"{len(_all)} exist before it. Pre-epoch data only.")
        else:
            print(f"No closed trades found in {src_dir}/fleet_trades_*.json")
        return 2

    print(f"{raw} row(s) across bundles -> {len(trades)} unique trade(s)")
    if dupes:
        # 🔴 LOUD, AND NAMED. Each bundle is one already-collapsed dt=
        # partition, so a repeated trade_id means a legacy CUMULATIVE bundle is
        # in this glob or two bundles cover the same date. v1.9 and earlier
        # absorbed both without a word.
        print(f"\n  🔴 {len(dupes)} DUPLICATE trade_id(s) ACROSS BUNDLES. Each "
              f"bundle should be ONE already-collapsed session, so this means")
        print(f"     either a legacy CUMULATIVE bundle is in {src_dir}, or two "
              f"bundles cover the same date. First occurrence wins (sorted by")
        print("     filename); the counts below EXCLUDE the repeats.")
        for tid, first, later in dupes[:8]:
            print(f"       {tid:<28} kept from {first}, also in {later}")
        if len(dupes) > 8:
            print(f"       ... and {len(dupes) - 8} more")
    print(f"{len(used)} session(s), dated from entry_time:")
    for d, n in used:
        print(f"   {d}   {n:>5} closed trades")

    # ── sentiment stamp (v1.3) ──────────────────────────────────────────────
    sentiment = load_sentiment(config.REPORTS_DIR)
    n_scored = 0
    for t in trades:
        sc = sentiment.get(t.get("_date") or "", {}).get(str(t.get("_sym", "")).upper())
        t["_sentiment"] = sentiment_band(sc)
        t["_sentiment_raw"] = sc
        if sc is not None:
            n_scored += 1

    dims = {
        "by_strategy":      bucket(trades, "strategy"),
        "by_setup_type":    bucket(trades, "setup_type"),
        "by_exit_reason":   bucket(trades, "exit_reason"),
        "by_symbol":        bucket(trades, "_sym"),
        "by_hour_et":       bucket(trades, "_hour_et"),
        "by_day_of_week":   bucket(trades, "_dow"),
        "by_session_phase": bucket(trades, "_phase"),
        "by_session_date":  bucket(trades, "_date"),
        "by_sentiment":     bucket(trades, "_sentiment"),
    }
    crosses = {
        "symbol_x_strategy": cross(trades, "_sym", "strategy"),
        "phase_x_strategy":  cross(trades, "_phase", "strategy"),
        # THE cross for the operator's question: does a bullish morning help
        # longs and hurt shorts? sentiment x strategy would not test that.
        "sentiment_x_direction": cross(trades, "_sentiment", "direction"),
        # Is an exit reason a standing pattern or one session? Marginals cannot say.
        "exit_x_date": cross(trades, "exit_reason", "_date"),
    }
    overall = stats_of(trades)

    # v1.3 — say how much sentiment data actually exists BEFORE any bucket is
    # ranked. Archiving began 2026-08-03 and brief_strength was a constant 0.30
    # before 2026-07-30, so for weeks the honest answer is "not measured yet" and
    # a ranked table over a handful of trades would read as a finding.
    if not sentiment:
        print("\nSENTIMENT: no morning_report_*.json archived yet "
              "(eod_conductor v1.12.0 phase 5c).\n  Nothing to compare — this is "
              "NOT a null result, it is an absent measurement.")
    else:
        pct = 100.0 * n_scored / max(len(trades), 1)
        print(f"\nSENTIMENT: {len(sentiment)} archived report(s); "
              f"{n_scored}/{len(trades)} trades carry a score ({pct:.0f}%).")
        if n_scored < 200:
            print("  THIN — brief_strength was a constant 0.30 for every name "
                  "until 2026-07-30 and\n  archiving began 2026-08-03. Expect this "
                  "to become readable around 2026-09-05.\n  Read sentiment_x_direction "
                  "as provisional until then.")
    best_t, worst_t = trade_extremes(trades)

    findings = {"min_n_applied": args.min_n}
    for label, d in [("strategy", dims["by_strategy"]),
                     ("setup_type", dims["by_setup_type"]),
                     ("exit_reason", dims["by_exit_reason"]),
                     ("symbol", dims["by_symbol"]), ("hour_et", dims["by_hour_et"]),
                     ("day_of_week", dims["by_day_of_week"]),
                     ("session_phase", dims["by_session_phase"]),
                     ("session_date", dims["by_session_date"]),
                     ("symbol_x_strategy", crosses["symbol_x_strategy"])]:
        findings[f"best_{label}"] = rank(d, args.min_n)
        findings[f"worst_{label}"] = rank(d, args.min_n, worst=True)
    findings["best_trade"] = best_t
    findings["worst_trade"] = worst_t

    print("\n" + "=" * 74)
    print(f"TRADE BREAKDOWN — {overall['n']} closed trades [{mode.upper()}]")
    print("=" * 74)
    print(f"  net {overall['net']:+.2f}   win rate {overall['win_rate']:.0%}   "
          f"avg {overall['avg']:+.2f}   best {overall['best']:+.2f}   "
          f"worst {overall['worst']:+.2f}")
    if overall["median_hold_min"] is not None:
        print(f"  median hold {overall['median_hold_min']} min")

    show("BY STRATEGY", dims["by_strategy"], args.min_n)
    show("BY SYMBOL", dims["by_symbol"], args.min_n)
    show("BY SETUP TYPE", dims["by_setup_type"], args.min_n)
    # v1.9 — the dimension is gone; the FACT is stated once. An absent
    # section with no explanation reads as an oversight and gets re-added.
    print("\n  (no BY SETUP GRADE section: every v4 row is UNGRADED by\n   construction — r152 deleted the scorer, which had selected losers.)")
    show("BY EXIT REASON", dims["by_exit_reason"], args.min_n)
    show("BY SESSION PHASE (ET)", dims["by_session_phase"], args.min_n)
    show("BY HOUR (ET)", dims["by_hour_et"], args.min_n)
    show("BY DAY OF WEEK", dims["by_day_of_week"], args.min_n)

    conc = exit_concentration(trades, args.min_n)
    print("\nEXIT REASON x SESSION SPREAD")
    print(f"  {'':<26}{'N':>5}{'SESS':>6}{'TOP DATE':>13}{'SHARE':>7}")
    for reason, c in sorted(conc.items(), key=lambda kv: -kv[1]["n"]):
        flag = "  <- SINGLE-SESSION" if c["single_session"] else (
            "  <- thin" if c["n"] < args.min_n else "")
        print(f"  {reason[:26]:<26}{c['n']:>5}{c['sessions']:>6}"
              f"{c['top_date']:>13}{c['top_share']:>7.0%}{flag}")
    print(f"  SINGLE-SESSION = >=80% of that exit's trades on one date "
          f"(and n >= {args.min_n}).\n  Such a reason is a one-day event, not a "
          f"standing pattern — do not read it as a rate.")

    eb = exit_behaviour(trades)
    print("\nEXIT BEHAVIOUR")
    print(f"  winners n={eb['n_winners']:<5} median hold "
          f"{eb['winner_median_hold_min']} min   MFE {eb['winner_median_mfe_pct']}")
    print(f"  losers  n={eb['n_losers']:<5} median hold "
          f"{eb['loser_median_hold_min']} min   MAE {eb['loser_median_mae_pct']}")
    sub_share = eb.get("sub_minute_share")
    if sub_share is not None:
        print(f"  sub-minute holds {eb['sub_minute_rows']} ({sub_share:.0%}) — "
              f"ratio {eb.get('winner_loser_hold_ratio')} all rows, "
              f"{eb.get('winner_loser_hold_ratio_ex_submin')} excluding them")
    if eb.get("flag_runners_cut_early"):
        if sub_share is not None and sub_share > 0.10:
            print("  NOTE hold ratio is under 1.2, but sub-minute rows are "
                  f"{sub_share:.0%} of the sample —")
            print("       that ratio is measuring those exits, not the leashes. "
                  "Verdict WITHHELD.")
        else:
            print("  NOTE winners are not held meaningfully longer than losers —")
            print("       exits may be cutting runners as fast as mistakes.")

    print("\nHEADLINE")
    for lab in ("strategy", "symbol", "session_phase", "day_of_week"):
        b, w = findings.get(f"best_{lab}"), findings.get(f"worst_{lab}")
        if b:
            print(f"  best {lab:<14} {b['key'][:30]:<30} net {b['net']:>+10.2f} (n={b['n']})")
        # v1.5 — "worst" is only a word worth printing when there is something
        # to be worst THAN, and when it is not simply the lowest of several
        # winners. One eligible bucket prints itself as both; all-positive
        # eligibles make "worst" read as a loss that did not happen.
        if w:
            n_elig = w.get("n_elig", 2)
            if n_elig < 2:
                print(f"  worst {lab:<13} — only 1 bucket cleared the n>={args.min_n} "
                      f"floor, so best and worst are the same one")
            else:
                lowest = w["net"] < 0
                tag = "" if lowest else f"  <- LOWEST of {n_elig}, not a loss"
                print(f"  worst {lab:<13} {w['key'][:30]:<30} "
                      f"net {w['net']:>+10.2f} (n={w['n']}){tag}")

    if not args.no_json:
        payload = {
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "scope": {"mode": mode, "since": args.since,
                      "sessions": [d for d, _ in used],
                      "first_session": used[0][0] if used else None,
                      "last_session": used[-1][0] if used else None},
            "dedup": {"raw_rows": raw, "unique_trades": len(trades)},
            "overall": overall,
            "findings": findings,
            "dimensions": dims,
            "crosses": crosses,
            "exit_behaviour": eb,
            "exit_concentration": conc,
        }
        os.makedirs(REPORTS_DIR, exist_ok=True)
        stamp = used[-1][0] if used else datetime.now().strftime("%Y-%m-%d")
        tag = "warehouse_" if args.bundles_dir else ""
        payload["source"] = ("warehouse:" + src_dir
                             if src_dir == WAREHOUSE_DIR
                             else "bundles:" + src_dir)
        payload["engine_epoch"] = None if args.all_history else since
        payload["pre_epoch_excluded"] = dropped
        out = (args.out if args.out
               else os.path.join(REPORTS_DIR, f"trade_report_{tag}{stamp}.json"))
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        tmp = out + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(payload, fh, indent=2, default=str)
        os.replace(tmp, out)
        print(f"\nwrote {out}")

    print(f"\nSorted by NET. '<- thin' = fewer than {args.min_n} trades (noise, "
          f"not signal).\nBest/worst above ignore buckets under that floor.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
