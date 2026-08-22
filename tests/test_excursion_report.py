"""
day_trader_pro/tests/test_excursion_report.py — v1.0 — 2026-08-03

Guards the four v2.3 defects. Every one of them was invisible: the report
rendered a full, well-formed page while reading the wrong source, counting the
wrong stop, and covering one flavor under a heading that promised all of them.
So each test asserts on the thing ARRIVING, not on the code path existing.

Run (day_trader_pro's venv has no pytest — use the other repo's interpreter):
  cd ~/day_trader_pro && PYTHONPATH=. ~/options-trader-v3/venv/bin/python \
      -m pytest tests/test_excursion_report.py -q
"""

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import excursion_report as er  # noqa: E402

DAY = "2026-08-03"

COLUMNS = ("status", "paper_trade", "entry_premium", "pnl_usd",
           "max_premium_seen", "min_premium_seen", "contracts", "strategy",
           "exit_reason", "entry_time")


def row(reason, *, entry=1.00, hi=1.30, lo=0.90, pnl=10.0, strat="Continuation",
        entry_time=f"{DAY}T14:31:00+00:00"):
    return {"status": "closed", "paper_trade": 1, "entry_premium": entry,
            "pnl_usd": pnl, "max_premium_seen": hi, "min_premium_seen": lo,
            "contracts": 1, "strategy": strat, "exit_reason": reason,
            "entry_time": entry_time}


def _write_db(folder, name, rows):
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)
    conn = sqlite3.connect(path)
    conn.execute(f"CREATE TABLE trades ({','.join(COLUMNS)})")
    for r in rows:
        conn.execute(
            f"INSERT INTO trades ({','.join(COLUMNS)}) "
            f"VALUES ({','.join('?' * len(COLUMNS))})",
            tuple(r[c] for c in COLUMNS))
    conn.commit()
    conn.close()
    return path


# ── defect 1: the DB source had never loaded ────────────────────────────────

def test_db_source_loads_harvests_actual_filename(tmp_path, monkeypatch):
    """harvest.py:166 writes <SYM>_trades_<date>.db. The pre-v2.3 glob was
    "*_trades.db", which requires the name to END there and matched nothing —
    so every run silently used the single-day fallback."""
    monkeypatch.setattr(er, "TRADES_DIR", str(tmp_path))
    _write_db(os.path.join(str(tmp_path), DAY), f"AAPL_trades_{DAY}.db",
              [row("continuation_trail")])
    rows, src = er._rows_from_dbs(DAY)
    assert rows is not None and len(rows) == 1, \
        "the dated DB filename must be found; None here is the old defect"
    assert "(1 DBs)" in src, f"src must mark a DB-backed read, got {src!r}"
    assert rows[0]["_box"] == "AAPL"


def test_bare_trades_db_name_is_not_what_harvest_writes(tmp_path, monkeypatch):
    """Deliberate-failure companion: a file named the way the OLD glob expected
    must NOT be picked up, or the fix would be indistinguishable from luck."""
    monkeypatch.setattr(er, "TRADES_DIR", str(tmp_path))
    _write_db(os.path.join(str(tmp_path), DAY), "AAPL_trades.db",
              [row("continuation_trail")])
    rows, src = er._rows_from_dbs(DAY)
    assert rows is None and src is None


def test_empty_folder_returns_none_so_fallback_engages(tmp_path, monkeypatch):
    monkeypatch.setattr(er, "TRADES_DIR", str(tmp_path))
    os.makedirs(os.path.join(str(tmp_path), DAY), exist_ok=True)
    assert er._rows_from_dbs(DAY) == (None, None)


# ── defect 2: the fallback only announced itself on an empty report ─────────

def test_fallback_source_is_announced_even_when_rows_exist():
    text = er.build_report([row("bos_exit")], DAY,
                           f"/x/reports/fleet_trades_{DAY}.json", 0, "PAPER")
    assert "SOURCE DEGRADED" in text
    assert "ONE session" in text


def test_db_backed_source_carries_no_degraded_banner():
    text = er.build_report([row("bos_exit")], DAY, f"trades/{DAY} (29 DBs)",
                           0, "PAPER")
    assert "SOURCE DEGRADED" not in text


# ── defect 3: LEASH VERDICT covered one flavor under a plural heading ──────

def test_leash_covers_the_flavors_the_engine_actually_emits():
    rows = [row("continuation_trail"), row("orb_trail_stop", strat="ORBStrat"),
            row("bos_exit"), row("theta_bleed")]
    text = er.build_report(rows, DAY, f"trades/{DAY} (29 DBs)", 0, "PAPER")
    leash = text.split("LEASH VERDICT")[1]
    for flavor in ("continuation_trail", "orb_trail_stop", "bos_exit",
                   "theta_bleed"):
        assert flavor in leash, f"{flavor} missing from the leash block"


def test_unlisted_trail_flavor_is_named_not_dropped():
    text = er.build_report([row("some_new_trail")], DAY,
                           f"trades/{DAY} (29 DBs)", 0, "PAPER")
    leash = text.split("LEASH VERDICT")[1]
    assert "some_new_trail" in leash
    assert "not in TRAIL_FLAVORS" in leash


def test_leash_says_so_when_no_trail_exits_present():
    text = er.build_report([row("flip_exit (SOME_LABEL)")], DAY,
                           f"trades/{DAY} (29 DBs)", 0, "PAPER")
    assert "no trail-flavor exits in this window" in text


# ── defect 4: FLOOR VERDICT counted ORB's stop and missed the real floor ────

def test_floor_stops_count_max_loss_floor_rows():
    """2026-08-03 shipped 5 max_loss_floor_25pct rows and 1 hard_stop_41%;
    the report said 'floor stops taken 1'."""
    rows = [row("max_loss_floor_25pct", hi=0.98, lo=0.73, pnl=-25.0)
            for _ in range(5)]
    rows.append(row("hard_stop_41% pnl=-45.0%", hi=0.94, lo=0.55, pnl=-45.0,
                    strat="ORBStrat"))
    text = er.build_report(rows, DAY, f"trades/{DAY} (29 DBs)", 0, "PAPER")
    line = [ln for ln in text.splitlines() if "floor stops taken" in ln][0]
    assert line.split()[-5] == "6" or " 6 " in line, \
        f"all six floor exits must be counted, got: {line}"


def test_floor_labels_interpolate_thresholds_rather_than_narrate_them():
    text = er.build_report([row("bos_exit")], DAY, f"trades/{DAY} (29 DBs)",
                           0, "PAPER", tight_floor=0.30, wide_floor=0.50)
    assert "-30%" in text and "-50%" in text
    assert "saved by 40%" not in text, \
        "the stale prose asserted 40% while testing another threshold"


# ── defect 2b: --since over the fallback must refuse, not mislabel ──────────

def test_since_over_single_day_fallback_exits_nonzero():
    tmp = tempfile.mkdtemp()
    try:
        shutil.copy(er.__file__.replace(".pyc", ".py"),
                    os.path.join(tmp, "excursion_report.py"))
        os.makedirs(os.path.join(tmp, "reports"), exist_ok=True)
        with open(os.path.join(tmp, "reports",
                               f"fleet_trades_{DAY}.json"), "w") as fh:
            json.dump([row("bos_exit")], fh)
        proc = subprocess.run(
            [sys.executable, "excursion_report.py", "--date", DAY,
             "--since", "2026-07-23"],
            cwd=tmp, capture_output=True, text=True)
        assert proc.returncode == 2, \
            f"--since over the fallback must refuse; rc={proc.returncode}"
        assert "REFUSED" in proc.stderr
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_no_since_over_fallback_still_reports():
    tmp = tempfile.mkdtemp()
    try:
        shutil.copy(er.__file__.replace(".pyc", ".py"),
                    os.path.join(tmp, "excursion_report.py"))
        os.makedirs(os.path.join(tmp, "reports"), exist_ok=True)
        with open(os.path.join(tmp, "reports",
                               f"fleet_trades_{DAY}.json"), "w") as fh:
            json.dump([row("bos_exit")], fh)
        proc = subprocess.run(
            [sys.executable, "excursion_report.py", "--date", DAY],
            cwd=tmp, capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        assert "SOURCE DEGRADED" in proc.stdout
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))


# ── v2.4: grouping dimensions, session power, floor sweep ──────────────────

def _r(strat, _unused, mae, mfe, real, date):
    return {"status": "closed", "paper_trade": 1, "entry_premium": 1.0,
            "pnl_usd": real * 100, "max_premium_seen": 1 + mfe,
            "min_premium_seen": 1 + mae, "contracts": 1, "strategy": strat,
            "exit_reason": "continuation_trail",
            "entry_time": f"{date}T14:31:00+00:00"}


_D = ["2026-07-24", "2026-07-28", "2026-07-29", "2026-07-31", "2026-08-03"]


# ⚠️ A per-cell separation test was DELETED r204 — it asserted a grouping
# dimension built on a column otv4 physically dropped in r65. The tests below
# KEEP their assertions (underpowered refusal, too-few-sessions flag) and only
# change the VEHICLE to a dimension that still exists.


def test_thin_cell_is_refused_not_reported_as_a_null():
    rows = [_r("Cont", "RANGING", -0.30, 0.0, -0.27, _D[i % 5])
            for i in range(10)]
    text = er.build_report(rows, "d", "trades/d (29 DBs)", 0, "PAPER",
                           group_by="strategy")
    assert "UNDERPOWERED" in text
    assert "REFUSED" in text
    assert "not a null" in text


def test_cell_from_too_few_sessions_is_flagged_even_when_n_is_large():
    """The 2026-08-03 lesson: 67% of a 'cumulative' was two sessions."""
    rows = [_r("Cont", "TRENDING_BULL", -0.08, 0.32, 0.14, _D[i % 2])
            for i in range(60)]
    text = er.build_report(rows, "d", "trades/d (29 DBs)", 0, "PAPER",
                           group_by="strategy")
    assert "2 SESSION(S)" in text
    assert "REFUSED" in text, "a 2-session cell must not get a floor sweep"


def test_floor_sweep_counts_stops_and_cut_winners():
    rows = [_r("Cont", "TRENDING_BULL", -0.30, 0.05, -0.45, _D[i % 5])
            for i in range(40)]
    rows += [_r("Cont", "TRENDING_BULL", -0.30, 0.60, 0.50, _D[i % 5])
             for i in range(10)]
    text = er.build_report(rows, "d", "trades/d (29 DBs)", 0, "PAPER",
                           group_by="strategy")
    sweep = text.split("FLOOR SWEEP")[1]
    line = [l for l in sweep.splitlines() if l.strip().startswith("25%")][0]
    assert " 50 " in line, "all 50 rows breach -25% and must count as stopped"
    assert " 10 " in line, "the 10 winners must be counted as cut"


def test_floor_sweep_never_names_a_best_floor():
    rows = [_r("Cont", "TRENDING_BULL", -0.30, 0.05, -0.45, _D[i % 5])
            for i in range(45)]
    text = er.build_report(rows, "d", "trades/d (29 DBs)", 0, "PAPER",
                           group_by="strategy")
    assert "NO BEST FLOOR IS NAMED" in text
    assert "overfit" in text


def test_default_grouping_is_unchanged_from_v23():
    rows = [_r("Cont", "TRENDING_BULL", -0.08, 0.32, 0.14, _D[0])]
    text = er.build_report(rows, "d", "trades/d (29 DBs)", 0, "PAPER")
    assert "EXIT REASON" in text


# ── v2.5: the two-population split ─────────────────────────────────────────

def _n(mfe, real, bucket="A", strat="Cont", date="2026-07-24"):
    return {"status": "closed", "paper_trade": 1, "entry_premium": 1.0,
            "pnl_usd": real * 100, "max_premium_seen": 1 + mfe,
            "min_premium_seen": 0.75, "contracts": 1, "strategy": strat,
            "setup_type": "s", "setup_grade": bucket,
            "symbol": "X", "exit_reason": "continuation_trail",
            "entry_time": f"{date}T14:31:00+00:00"}


def test_never_favorable_counted_at_every_cut():
    rows = [_n(0.00, -0.27) for _ in range(20)]
    rows += [_n(0.03, -0.20) for _ in range(10)]
    rows += [_n(0.40, 0.20) for _ in range(20)]
    text = er.build_report(rows, "d", "trades/d (29 DBs)", 0, "PAPER")
    blk = text.split("NEVER FAVORABLE")[1].split("COMPOSITION")[0]
    zero = [l for l in blk.splitlines() if l.strip().startswith("0%")][0]
    five = [l for l in blk.splitlines() if l.strip().startswith("5%")][0]
    assert " 20 " in zero, "only the 20 flat trades are never-favorable at 0%"
    assert " 30 " in five, "the 3% trades join at the 5% cut"


def test_composition_is_a_rate_within_the_group_not_a_share_of_the_pile():
    """A group can hold most of the bad trades purely by being most of the
    sample. The rate is what distinguishes; the share is the trap."""
    rows = [_n(0.00, -0.27, bucket="A") for _ in range(60)]
    rows += [_n(0.40, 0.20, bucket="A") for _ in range(60)]
    rows += [_n(0.00, -0.27, bucket="B") for _ in range(20)]
    text = er.build_report(rows, "d", "trades/d (29 DBs)", 0, "PAPER")
    # ⚠️ r204: the fixture's buckets moved to setup_grade A/B when the old
    # grouping dimension was removed. The ASSERTION IS UNCHANGED — A holds 60
    # of the 80 bad trades but its RATE is 50%, while B holds fewer and every
    # one is bad. That contrast is the whole point of the test.
    big = [l for l in text.splitlines()
           if l.strip().startswith("A") and "%" in l][0]
    small = [l for l in text.splitlines()
             if l.strip().startswith("B") and "%" in l][0]
    assert "50%" in big, "A holds 60 of 80 bad trades but its RATE is 50%"
    assert "100%" in small, "B holds fewer but every one of them is bad"


def test_small_group_is_not_given_a_lift_number():
    rows = [_n(0.00, -0.27, strat="Cont") for _ in range(40)]
    rows += [_n(0.00, -0.27, strat="Rare") for _ in range(3)]
    text = er.build_report(rows, "d", "trades/d (29 DBs)", 0, "PAPER")
    rare = [l for l in text.splitlines() if l.strip().startswith("Rare")][0]
    assert "n<" in rare and "1.00" not in rare


def test_winner_giveback_states_the_timestamp_limitation():
    rows = [_n(0.40, 0.20) for _ in range(20)]
    text = er.build_report(rows, "d", "trades/d (29 DBs)", 0, "PAPER")
    assert "CANNOT CONCLUDE FROM THIS ALONE" in text
    assert "NO TIMESTAMP" in text


def test_capture_ratio_is_realized_over_mfe():
    rows = [_n(0.40, 0.20) for _ in range(20)]
    text = er.build_report(rows, "d", "trades/d (29 DBs)", 0, "PAPER")
    cap = [l for l in text.splitlines() if "median capture" in l][0]
    assert "50%" in cap, "0.20 realized on a 0.40 peak is 50% capture"
