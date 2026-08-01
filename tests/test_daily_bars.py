"""
tests/test_daily_bars.py — v1.0 — 2026-08-01.

Tests for day_trader_pro/daily_bars.py — the daily OHLC series the pitchfork's
daily fork anchors on (item AP).

WHY THESE PROPERTIES AND NOT OTHERS
    The fork is a PERSISTENT object whose determinism rests on being
    reconstructible from tape. That puts the weight on the series being
    trustworthy rather than on the aggregation arithmetic being clever:

      IDEMPOTENT      Rebuilding must produce byte-identical output. The phase
                      runs nightly and recomputes everything; if a rebuild could
                      drift, the fork's anchors could move without the tape
                      changing, which is exactly the failure the determinism
                      requirement exists to prevent.
      SELF-HEALING    A session backfilled late must appear on the next rebuild.
                      This is the whole reason it rebuilds instead of appending.
      HONEST ABOUT    A session built from short tape has a high and low that are
      PARTIAL TAPE    not the session's. Flagged, never silently dropped — a
                      dropped session is a hole nobody can see, and a fractal
                      pivot anchored on an artifact is worse than no fork.
      ATOMIC          A reader mid-rebuild sees the old series or the new one,
                      never half a file.
      UNIX ENDINGS    csv.writer defaults to CRLF, which puts a literal \\r on the
                      last field of every row so `awk -F, '$8==1'` compares
                      against "1\\r" and silently never matches. Found while
                      verifying the partial flag, which WAS set and looked as if
                      it were not.

Run: PYTHONPATH=. pytest tests/test_daily_bars.py -v
"""

import csv
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import daily_bars  # noqa: E402

SYMS = ("SPX", "QQQ")
DATES = [f"2026-07-{d:02d}" for d in
         (13, 14, 15, 16, 17, 20, 21, 22, 23, 24, 27, 28, 29, 30, 31)]


def _write_session(root, date, sym, rows=390, base=100.0):
    d = os.path.join(root, date)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{sym}_ohlc_{date}.csv")
    with open(path, "w", newline="") as fh:
        fh.write("timestamp,open,high,low,close,volume\n")
        px = base
        for i in range(rows):
            px += 0.01
            fh.write(f"{date}T09:30:00-04:00,{px:.2f},{px + 0.5:.2f},"
                     f"{px - 0.5:.2f},{px + 0.1:.2f},100\n")
    return path


@pytest.fixture
def tape(tmp_path):
    root = tmp_path / "ohlc"
    for i, date in enumerate(DATES):
        for sym in SYMS:
            # QQQ on the 4th session is deliberately short — a late start or a
            # feed outage, the case the partial flag exists for.
            rows = 120 if (sym == "QQQ" and i == 3) else 390
            _write_session(str(root), date, sym, rows=rows, base=100.0 + i)
    return str(root), str(tmp_path / "daily")


def _read(daily_dir, sym):
    with open(os.path.join(daily_dir, f"{sym}.csv"), newline="") as fh:
        return list(csv.DictReader(fh))


def test_builds_one_bar_per_session_per_symbol(tape):
    root, daily = tape
    written = daily_bars.rebuild(root, daily)
    assert set(written) == set(SYMS)
    assert all(n == len(DATES) for n in written.values()), written


def test_ohlc_is_the_session_aggregate(tape):
    """Open from the first minute, close from the last, high/low the extremes."""
    root, daily = tape
    daily_bars.rebuild(root, daily)
    bar = _read(daily, "SPX")[0]
    assert float(bar["open"]) == pytest.approx(100.01, abs=0.01)
    assert float(bar["high"]) > float(bar["open"])
    assert float(bar["low"]) < float(bar["high"])
    assert float(bar["close"]) > float(bar["open"])   # fixture ramps up
    assert int(bar["minute_rows"]) == 390


def test_rebuild_is_idempotent(tape):
    """Byte-identical on a second run. If a rebuild could drift, fork anchors
    could move without the tape changing."""
    root, daily = tape
    daily_bars.rebuild(root, daily)
    first = open(os.path.join(daily, "SPX.csv"), "rb").read()
    daily_bars.rebuild(root, daily)
    assert open(os.path.join(daily, "SPX.csv"), "rb").read() == first


def test_a_late_backfilled_session_appears_on_the_next_rebuild(tape):
    """The reason it rebuilds instead of appending."""
    root, daily = tape
    daily_bars.rebuild(root, daily)
    assert len(_read(daily, "SPX")) == len(DATES)
    _write_session(root, "2026-08-01", "SPX", rows=390, base=200.0)
    daily_bars.rebuild(root, daily)
    rows = _read(daily, "SPX")
    assert len(rows) == len(DATES) + 1
    assert rows[-1]["date"] == "2026-08-01"


def test_series_stays_sorted_when_a_gap_is_filled_out_of_order(tape):
    """A backfilled MIDDLE date must land in date order, not at the end."""
    root, daily = tape
    _write_session(root, "2026-07-18", "SPX", rows=390, base=150.0)
    daily_bars.rebuild(root, daily)
    dates = [r["date"] for r in _read(daily, "SPX")]
    assert dates == sorted(dates)
    assert "2026-07-18" in dates


def test_partial_sessions_are_flagged_not_dropped(tape):
    root, daily = tape
    daily_bars.rebuild(root, daily)
    rows = _read(daily, "QQQ")
    assert len(rows) == len(DATES), "a short session must not vanish"
    flagged = [r for r in rows if r["partial"] == "1"]
    assert len(flagged) == 1, [r["date"] for r in flagged]
    assert flagged[0]["date"] == DATES[3]
    assert int(flagged[0]["minute_rows"]) == 120


def test_full_sessions_are_not_flagged(tape):
    root, daily = tape
    daily_bars.rebuild(root, daily)
    assert all(r["partial"] == "0" for r in _read(daily, "SPX"))


def test_output_uses_unix_line_endings(tape):
    """CRLF would put a literal \\r on the last field, so shell filters on the
    partial column silently never match."""
    root, daily = tape
    daily_bars.rebuild(root, daily)
    raw = open(os.path.join(daily, "SPX.csv"), "rb").read()
    assert b"\r\n" not in raw


def test_no_temp_files_left_behind(tape):
    """Write-then-rename must leave no .tmp for the next reader to trip over."""
    root, daily = tape
    daily_bars.rebuild(root, daily)
    assert not [f for f in os.listdir(daily) if f.endswith(".tmp")]


def test_dry_run_writes_nothing(tape):
    root, daily = tape
    counts = daily_bars.rebuild(root, daily, dry_run=True)
    assert counts and not os.path.isdir(daily)


def test_non_tape_siblings_are_ignored(tape):
    """fleet_trades_*.csv and friends live in the same folders and are not tape."""
    root, daily = tape
    with open(os.path.join(root, DATES[0], "fleet_trades_2026-07-13.csv"), "w") as fh:
        fh.write("not,tape\n1,2\n")
    written = daily_bars.rebuild(root, daily)
    assert set(written) == set(SYMS), written


def test_empty_and_missing_roots_return_empty(tmp_path):
    assert daily_bars.rebuild(str(tmp_path / "nope"), str(tmp_path / "d")) == {}
    empty = tmp_path / "empty"
    empty.mkdir()
    assert daily_bars.rebuild(str(empty), str(tmp_path / "d2")) == {}


def test_unparseable_rows_are_skipped_not_guessed(tmp_path):
    root = tmp_path / "ohlc"
    d = root / "2026-07-13"
    d.mkdir(parents=True)
    with open(d / "SPX_ohlc_2026-07-13.csv", "w") as fh:
        fh.write("timestamp,open,high,low,close,volume\n")
        fh.write("t,100,101,99,100.5,10\n")
        fh.write("t,BAD,x,y,z,10\n")
        fh.write("t,102,103,101,102.5,10\n")
    daily_bars.rebuild(str(root), str(tmp_path / "daily"))
    bar = _read(str(tmp_path / "daily"), "SPX")[0]
    assert int(bar["minute_rows"]) == 2
    assert float(bar["high"]) == pytest.approx(103.0)
    assert float(bar["low"]) == pytest.approx(99.0)


def test_series_reaches_the_pitchfork_floor(tape):
    """A k=2 daily fork needs P2 confirmed at index 14, so ~15 sessions. This
    asserts the fixture's own arithmetic so the floor stays visible in the suite
    rather than living only in a comment."""
    root, daily = tape
    written = daily_bars.rebuild(root, daily)
    assert written["SPX"] >= 15
