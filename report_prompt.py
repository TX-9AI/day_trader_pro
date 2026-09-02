#!/usr/bin/env python3
# day_trader_pro/report_prompt.py — v1.1
# v1.1 (2026-09-02) — dtp r247. The menu LOOPS: the caller can take several
#   cuts off one pull, because a 49-second S3 read should not be repeated to
#   look at a second strategy. `q` quits, and quit is a SENTINEL rather than
#   None — None already means ALL types, and reusing it would silently run an
#   ALL-types report on the way out.
# v1.0 (2026-09-01) — dtp r244. THE PROMPTS BOTH EXCURSION REPORTS SHARE.
#
# Operator, 2026-09-01: a custom report evaluating entries that prompts for
# start and end date, has a numbered menu for trade type selection and a
# progress bar for both the pull and the report generation — and a companion
# report with the same features for evaluating stops.
#
# 🔑 THE MENU IS BUILT FROM THE DATA, NEVER FROM A LIST. A hardcoded strategy
#   list rots exactly the way r35's allow-list did: it held three names, two of
#   which had been deleted, while the live strategy was silently absent and
#   therefore exempt. Here the failure would be quieter still — an option that
#   selects zero trades, or a strategy that never appears as a choice.
#   So: pull first (it is cheap — raw/trades is the whole 0.022 GB), then offer
#   what is actually THERE, with its count beside it.
#
# ⚠️ AND THE COUNT IN THE MENU IS ITSELF THE ANSWER TO "DO WE HAVE ENOUGH YET".
#   The operator asked whether ~100 TrendCreditSpread trades exist; his 09-01
#   QQQ board showed ONE on that box. The menu settles it before any analysis
#   is designed on top of a number nobody checked.
"""Shared date/type prompting for the excursion reports."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("US/Eastern")


def ask_dates(argv_from=None, argv_to=None):
    """START and END, ET. Returns the inclusive list of ISO dates."""
    try:
        a = argv_from or input("  START (YYYY-MM-DD): ").strip()
        b = (argv_to
             or input("  END   (YYYY-MM-DD, ENTER = same day): ").strip() or a)
    except EOFError:
        raise SystemExit("\n  no input available — pass --from and --to "
                         "when running non-interactively")
    try:
        d0 = datetime.strptime(a, "%Y-%m-%d").date()
        d1 = datetime.strptime(b, "%Y-%m-%d").date()
    except ValueError:
        raise SystemExit("  dates must be YYYY-MM-DD")
    # ⚠️ REVERSED RANGES ARE REFUSED BY NAME. An END before START produced an
    # empty list that raised IndexError four frames down inside the cache
    # (dtp r242); the library guards it now and so does the caller.
    if d1 < d0:
        raise SystemExit("  END is earlier than START")
    out = []
    while d0 <= d1:
        out.append(d0.isoformat())
        d0 += timedelta(days=1)
    return out


# Sentinel: "the operator is done", distinct from None which means ALL types.
# ⚠️ None ALREADY MEANS SOMETHING HERE. Reusing it for quit would silently run
# an ALL-types report on the way out.
_QUIT = object()
QUIT = _QUIT


def choose_type(counts, preselected=None):
    """A numbered menu of the trade types PRESENT, with their counts.

    `counts` is [(label, n), ...] already sorted. Returns the chosen label, or
    None for "all types".

    ⚠️ THE COUNTS ARE SHOWN BECAUSE THE SAMPLE SIZE IS THE FIRST FINDING. A
    type with 6 trades cannot answer what separates a good entry from a bad one
    however good the report is, and seeing 6 next to the name says so before
    any effort is spent.
    """
    if preselected and preselected.upper() == "ALL":
        return None
    if preselected:
        for lab, _n in counts:
            if lab.lower() == preselected.lower():
                return lab
        raise SystemExit(f"  no trades of type {preselected!r} in this range")
    if not counts:
        raise SystemExit("  no closed trades with excursion telemetry in range")
    total = sum(n for _l, n in counts)
    print()
    print("  TRADE TYPE")
    print(f"   0) ALL types  ({total} trades)")
    for i, (lab, n) in enumerate(counts, start=1):
        # ⚠️ THE WARNING RIDES THE MENU LINE, not a footnote. The smaller
        # outcome class is what limits the analysis, and a count under ~30 is
        # a hypothesis generator at best.
        flag = "   <- too few to separate anything" if n < 30 else ""
        print(f"  {i:2d}) {lab:<28} {n:>5} trades{flag}")
    print()
    # ⚠️ A CLOSED STDIN IS NOT A SELECTION OF ZERO. Piped or cron'd, `input()`
    # raises EOFError; defaulting silently to ALL would run a different report
    # than anyone asked for and label it with the wrong type. Say so and stop —
    # `--type` is the non-interactive path and the message names it.
    try:
        raw = input("  Select [0], or q to quit: ").strip() or "0"
    except EOFError:
        raise SystemExit("\n  no input available — pass --type NAME "
                         "(or --type ALL) when running non-interactively")
    # ⚠️ QUIT IS AN OPTION, NOT AN ERROR. The caller loops on this so the
    # operator can take several cuts off ONE pull — a 49-second S3 read should
    # not be repeated to look at a second strategy — and there has to be a way
    # out that is not Ctrl-C.
    if raw.lower() in ("q", "quit", "exit"):
        return _QUIT
    if not raw.isdigit() or int(raw) > len(counts):
        print("  not a listed option")
        return choose_type(counts)
    idx = int(raw)
    return None if idx == 0 else counts[idx - 1][0]


# ── the shared trades pull ──────────────────────────────────────────────
# ⚠️ THIS LIVES HERE, NOT IN entry_report, because `tools/` HAS NO __init__.py
# and `from tools.entry_report import ...` fails at import. Caught before the
# first run — but the deeper reason is §7: two reports sharing a loader should
# both import the shared module, not have one import the other and inherit its
# argument parsing, its constants and its failure modes.
# ⚠️ NO "symbol" HERE — `warehouse_cache.load` supplies it as the first column
# of every table it builds, so listing it again is a duplicate-column error at
# CREATE TABLE. Found on the first run against a fixture, which is the cheapest
# place to find it.
COLS = ["trade_id", "strategy", "setup_type", "status",
        "entry_time", "exit_time", "entry_premium", "exit_premium",
        "contracts", "pnl_usd", "pnl_pct", "exit_reason",
        "mfe_premium", "mfe_bars", "mae_premium", "mae_bars",
        "credit_received", "spread_width"]


def load_trades(cache, dates):
    """raw/trades for the range. The whole stream is 0.022 GB — cheap."""
    cache.load("trades", dates, COLS, datatype="trades")
    cache.conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_tr ON trades(strategy, status)")
    cache.conn.commit()


def type_counts(cache, need="mfe_premium"):
    """Closed trades per strategy that HAVE the telemetry the report needs.

    ⚠️ FILTERED ON THE TELEMETRY, not just on status. A menu offering
    "TrendCreditSpread (112 trades)" that yields six scored rows because the
    rest have no excursion recorded would be worse than no menu — it answers
    the sample-size question wrongly, which is the one question being asked.
    """
    rows = cache.query(
        f'SELECT COALESCE(strategy,"?") lab, COUNT(*) n FROM "trades"'
        f' WHERE status = ? AND {need} IS NOT NULL'
        f' GROUP BY lab ORDER BY n DESC', ("closed",))
    return [(r["lab"], r["n"]) for r in rows]


def pct(v):
    return "   n/a" if v is None or v != v else f"{v:+6.1f}%"


def money(v):
    if v is None or v != v:
        return "    n/a"
    return f"{'+' if v >= 0 else '-'}${abs(v):,.0f}"
