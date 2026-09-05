# day_trader_pro/market_calendar.py — v0.2.0
# v0.2.0 (2026-09-05) — dtp r287 / TZ.1 — the naive `today` here asked a UTC box and rolled at 20:00 ET
#   (19:00 in winter), so anything run after that silently asked for TOMORROW and came
#   back empty. It now goes through `ettime`, the one ET/UTC boundary.
"""
Trading-day gate. Keeps the orchestrator from waking the fleet on weekends
and market holidays.

Prefers a real exchange calendar if `pandas_market_calendars` is installed;
otherwise falls back to a weekend check plus a maintained US market holiday
set. Extend HOLIDAYS_US each year, or install the library for full accuracy:

    pip install pandas_market_calendars
"""

from datetime import date
import ettime                                            # noqa: E402

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
    # 🔴 r287 — `date.today()` HERE WAS THE WORST OF THE NINE. This is the
    # module that decides what a trading day IS, and it was asking a UTC box.
    # After 20:00 ET (19:00 in winter) it answered for TOMORROW, so a Friday
    # evening question about "today" was silently answered about Saturday —
    # False, and indistinguishable from a real holiday.
    d = d or date.fromisoformat(ettime.today_et())
    lib = _via_library(d)
    if lib is not None:
        return lib
    if d.weekday() >= 5:      # Sat/Sun
        return False
    return d not in HOLIDAYS_US


if __name__ == "__main__":
    today = date.fromisoformat(ettime.today_et())
    print(f"{today.isoformat()} trading_day={is_trading_day(today)}")
