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
    text = er.build_report([row("regime_flip (RANGING)")], DAY,
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
