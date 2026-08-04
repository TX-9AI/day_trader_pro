#!/usr/bin/env python3
"""
day_trader_pro/excursion_report.py — v2.3 — MFE/MAE distributions from the
fleet's auto-collected per-symbol trade DBs.
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
import sys
from datetime import date
from statistics import mean, median

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
    "theta_bleed",
)

# The floor exits. max_loss_floor_<pct>pct is the blanket/continuation floor;
# hard_stop_<pct> is ORB's. Matching only "hard_stop" missed the former.
FLOOR_REASON_PREFIXES = ("hard_stop", "max_loss_floor")


# ── input: per-symbol DB snapshots (primary), consolidated file (fallback) ──

def _rows_from_dbs(day: str):
    """trades/<date>/*_trades.db — SELECT every closed row from each box's
    snapshot. Snapshots hold full history; date filtering happens later."""
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
    return rows, f"trades/{day} ({len(paths)} DBs)"


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


def load_day(day: str):
    rows, src = _rows_from_dbs(day)
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


def norm_reason(reason) -> str:
    r = (reason or "unknown").strip()
    if r.startswith("hard_close"):
        return "hard_close"
    return r.split(" pnl=")[0].split(":")[0].strip() or "unknown"


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
                 tight_floor=0.25, wide_floor=0.40) -> str:
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

    buckets = {}
    for r in rows:
        buckets.setdefault((norm_reason(r.get("exit_reason")),
                            r.get("strategy") or "?"), []).append(r)

    w("")
    w(f"{'EXIT REASON':<22}{'STRAT':<8}{'N':>4}{'WIN%':>6}"
      f"{'REAL':>7}{'MFE':>7}{'MAE':>7}{'GIVE':>7}")
    w("-" * 68)
    for (reason, strat), rs in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
        ex    = [excursions(r) for r in rs]
        reals = [e[2] for e in ex]
        wins  = sum(1 for r in rs if (fnum(r, "pnl_usd") or 0) > 0)
        give  = mean(e[0] - e[2] for e in ex)
        w(f"{reason:<22}{strat[:7]:<8}{len(rs):>4}{wins/len(rs):>6.0%}"
          f"{mean(reals):>7.0%}{mean(e[0] for e in ex):>7.0%}"
          f"{mean(e[1] for e in ex):>7.0%}{give:>7.0%}")

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
    ap.add_argument("--live", action="store_true",
                    help="live rows (default: paper)")
    args = ap.parse_args()

    all_rows, src = load_day(args.date)
    if all_rows is None:
        print(f"No trades/{args.date}/*_trades.db and no "
              f"fleet_trades_{args.date}.json/.csv — nothing collected for "
              f"that day yet.", file=sys.stderr)
        sys.exit(1)

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
                        "LIVE" if args.live else "PAPER", hints=hints)
    print(text)

    os.makedirs(REPORTS_DIR, exist_ok=True)
    suffix = "_live" if args.live else ""
    out_path = os.path.join(REPORTS_DIR, f"excursions_{args.date}{suffix}.txt")
    with open(out_path, "w") as f:
        f.write(text)
    print(f"Report written: {out_path}")


if __name__ == "__main__":
    main()
