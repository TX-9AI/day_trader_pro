# day_trader_pro/market_calendar.py — v0.1.0
"""
Trading-day gate. Keeps the orchestrator from waking the fleet on weekends
and market holidays.

Prefers a real exchange calendar if `pandas_market_calendars` is installed;
otherwise falls back to a weekend check plus a maintained US market holiday
set. Extend HOLIDAYS_US each year, or install the library for full accuracy:

    pip install pandas_market_calendars
"""

from datetime import date

# US equity market full-closure holidays. Extend annually.
# (Early-close days are intentionally treated as normal trading days.)
HOLIDAYS_US = {
    # 2026
    date(2026, 1, 1),   # New Year's Day
    date(2026, 1, 19),  # MLK Jr. Day
    date(2026, 2, 16),  # Presidents' Day
    date(2026, 4, 3),   # Good Friday
    date(2026, 5, 25),  # Memorial Day
    date(2026, 6, 19),  # Juneteenth
    date(2026, 7, 3),   # Independence Day (observed)
    date(2026, 9, 7),   # Labor Day
    date(2026, 11, 26), # Thanksgiving
    date(2026, 12, 25), # Christmas
}


def _via_library(d):
    try:
        import pandas_market_calendars as mcal
        sched = mcal.get_calendar("XNYS").schedule(
            start_date=d.isoformat(), end_date=d.isoformat())
        return not sched.empty
    except Exception:  # noqa: BLE001 — library optional; fall through
        return None


def is_trading_day(d=None):
    d = d or date.today()
    lib = _via_library(d)
    if lib is not None:
        return lib
    if d.weekday() >= 5:      # Sat/Sun
        return False
    return d not in HOLIDAYS_US


if __name__ == "__main__":
    today = date.today()
    print(f"{today.isoformat()} trading_day={is_trading_day(today)}")
