"""
tests/test_fit_report.py — v1.0 — 2026-08-10

Pins the fit report's two non-obvious guarantees (fit_report v1.0).

The report's VALUE is not that it runs six tools — it is that it refuses to let
a fit be made against numbers that cannot legitimately be pooled, and that it
never hides a section that failed. Both of those are silent failures if they
break: the file still renders, still looks complete, and is wrong.

1. **THE BAKE BOUNDARY.** Engine bakes change WHICH TRADES FIRE. A range that
   spans one holds two different measurements wearing one label. If this warning
   stops firing, the report becomes an invitation to pool across it.
2. **A FAILED SECTION IS WRITTEN, NOT SWALLOWED.** A missing section would be
   fitted around without the reader knowing anything was absent.

Deliberate-failure check performed when written: emptying BAKE_DATES turns
test_a_range_spanning_a_bake_is_flagged red; making section() re-raise turns
test_a_failing_section_does_not_abort_the_run red.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fit_report as FR                                        # noqa: E402


def test_a_range_spanning_a_bake_is_flagged():
    assert FR.spanned_bakes("2026-07-23", "2026-08-10"), \
        "a range crossing a fleet bake MUST warn — pooling across it compares " \
        "two different engines under one label"


def test_a_range_starting_at_the_bake_is_not_flagged():
    """The boundary is exclusive at the low end: 08-08 onward is one basis."""
    assert not FR.spanned_bakes("2026-08-08", "2026-08-10")


def test_a_single_day_is_never_flagged():
    assert not FR.spanned_bakes(None, "2026-08-10")
    assert not FR.spanned_bakes(None, "2026-08-08")


def test_bake_dates_are_populated():
    assert FR.BAKE_DATES, \
        "an empty table silently disables the only guard against cross-basis fits"


def test_a_failing_section_does_not_abort_the_run():
    rc, out = FR.sh([sys.executable, "-c", "import sys; print('partial'); sys.exit(3)"])
    assert rc == 3 and "partial" in out, \
        "a non-zero tool must return its OUTPUT and its code — the report writes " \
        "both and continues, because a missing section is worse than a failed one"


def test_replay_files_respect_the_range():
    """v1.1 — sections 5-6 must answer the SAME window as sections 1-4.

    v1.0 auto-discovered the corpus and read 21 files back to 07-13 inside a
    report headed 2026-08-10. A report that says one date must mean it
    throughout, or it invites the cross-window fit the bake warning exists to
    prevent.
    """
    import os
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        for d in ("2026-07-13", "2026-08-07", "2026-08-10"):
            open(os.path.join(td, f"replay_{d}.jsonl"), "w").close()
        old, FR.REPORTS_DIR = FR.REPORTS_DIR, td
        try:
            one = FR.replay_files(None, "2026-08-10")
            rng = FR.replay_files("2026-08-07", "2026-08-10")
            allf = FR.replay_files("2026-07-13", "2026-08-10")
        finally:
            FR.REPORTS_DIR = old
    assert len(one) == 1, "a single-day report must read ONE replay file"
    assert len(rng) == 2
    assert len(allf) == 3


def test_a_missing_tool_is_reported_not_raised():
    rc, out = FR.sh(["/definitely/not/a/binary"])
    assert rc != 0 and "NOT FOUND" in out
