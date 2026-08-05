#!/usr/bin/env python3
"""
day_trader_pro/trim_trade_dbs.py — v1.0 — 2026-08-05

ONE-SHOT: trim every historical `trades/<date>/<SYM>_trades_<date>.db` down to
the rows that actually belong to that date.

WHY THESE FILES ARE WRONG. A box's `trades.db` is CUMULATIVE and correctly so —
it is the bot's own working record (position reconciliation across restarts,
the daily-loss halt, the circuit breaker). Nothing on the box appends old
sessions. The fault was in `harvest`, which copied that whole growing file into
a DATED folder: the date in the path meant "when it was pulled", not "what is
inside". Reading 22 dated folders read the same trades 22 times.

Measured 2026-08-05: **2,502 of 3,298 rows (76%) were duplicates**, and the
inflated n made every Wilson interval about 1.7x too narrow — the ORB grade A/B
split read as decisive and dissolved once de-duplicated.

`harvest` v0.6.3 trims on pull, so this only exists for the backlog of files
already on disk.

SAFETY. Only touches CONTROL-SIDE COPIES under trades/. Never connects to a box
and never touches a box's own DB. Defaults to a DRY RUN. Takes a `.bak`
alongside each file before writing unless --no-backup, so a bad trim is
reversible.

A ROW WITH NO `entry_time` IS KEPT, NOT DELETED. It cannot be attributed to a
day, and deleting unattributable rows would silently shrink the corpus in a way
nobody could audit afterwards — the opposite of the problem being fixed. They
are counted and reported instead.

USAGE
    python3 trim_trade_dbs.py                 # dry run, shows what it would do
    python3 trim_trade_dbs.py --apply         # do it, with .bak files
"""

import argparse
import glob
import os
import re
import sqlite3
import sys

TRADES_DIR = os.path.expanduser("~/day_trader_pro/trades")
DATE_DIR = re.compile(r"(20\d\d-\d\d-\d\d)$")


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trades-dir", default=TRADES_DIR)
    ap.add_argument("--apply", action="store_true",
                    help="actually write; without it this is a dry run")
    ap.add_argument("--no-backup", action="store_true")
    a = ap.parse_args(argv[1:])

    days = sorted(d for d in glob.glob(os.path.join(a.trades_dir, "*"))
                  if os.path.isdir(d) and DATE_DIR.search(d))
    if not days:
        print(f"no dated folders under {a.trades_dir}")
        return 2

    tot_before = tot_after = tot_undated = 0
    touched = 0
    print(f"{'DRY RUN — nothing written' if not a.apply else 'APPLYING'}   "
          f"{len(days)} dated folder(s) under {a.trades_dir}\n")
    for day in days:
        date = DATE_DIR.search(day).group(1)
        dbs = sorted(glob.glob(os.path.join(day, "*_trades*.db")))
        d_before = d_after = d_undated = 0
        for db in dbs:
            try:
                con = sqlite3.connect(db)
                before = con.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
                keep = con.execute(
                    "SELECT COUNT(*) FROM trades WHERE "
                    "substr(entry_time,1,10) = ?", (date,)).fetchone()[0]
                undated = con.execute(
                    "SELECT COUNT(*) FROM trades WHERE entry_time IS NULL "
                    "OR entry_time = ''").fetchone()[0]
                if a.apply and before != keep + undated:
                    if not a.no_backup and not os.path.exists(db + ".bak"):
                        import shutil
                        shutil.copy2(db, db + ".bak")
                    con.execute(
                        "DELETE FROM trades WHERE entry_time IS NOT NULL "
                        "AND entry_time <> '' AND substr(entry_time,1,10) <> ?",
                        (date,))
                    con.commit()
                    con.execute("VACUUM")
                    touched += 1
                con.close()
            except sqlite3.Error as e:
                print(f"  ! {os.path.basename(db)}: {e}", file=sys.stderr)
                continue
            d_before += before
            d_after += keep + undated
            d_undated += undated
        if d_before:
            drop = d_before - d_after
            print(f"  {date}  {len(dbs):>3} db(s)  {d_before:>7,} -> "
                  f"{d_after:>6,} row(s)"
                  + (f"   (-{drop:,}, {drop / d_before:.0%})" if drop else "")
                  + (f"   [{d_undated} undated KEPT]" if d_undated else ""))
        tot_before += d_before
        tot_after += d_after
        tot_undated += d_undated

    drop = tot_before - tot_after
    print(f"\n  TOTAL  {tot_before:,} -> {tot_after:,} row(s)"
          + (f"   removing {drop:,} duplicate(s) "
             f"({drop / tot_before:.0%})" if tot_before else ""))
    if tot_undated:
        print(f"  {tot_undated} row(s) have no entry_time and were KEPT — they "
              f"cannot be attributed to a day,\n  and deleting unattributable "
              f"rows would shrink the corpus in a way nobody could audit.")
    if not a.apply:
        print("\n  DRY RUN. Re-run with --apply to write (a .bak is taken "
              "alongside each file).")
    else:
        print(f"\n  wrote {touched} file(s). Re-run conditional_tables — the "
              f"de-dup line should now report ~0%.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
