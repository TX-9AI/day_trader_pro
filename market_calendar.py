# day_trader_pro/market_calendar.py — v0.4.0
# v0.4.0 (2026-09-07) — dtp r318 / DEP.13. THE HORIZON GOES TO 2050, in lockstep
#   with otv4 r310. 250 closures. 2035 was an arbitrary ten-year prior; the list
#   is GENERATED and the oracle verifies every date, so extending costs bytes.
#   The only exposure is a RULES change (Juneteenth, 2022) making later years
#   wrong — which fails toward TRADING.
#   ⚠️ BOTH REPOS MOVE TOGETHER OR D5 GOES RED. That is the check working: two
#   lists meaning one thing must never be extended singly.
# v0.3.0 (2026-09-07) — dtp r317 / DEP.11+DEP.13. HOLIDAYS_US runs to 2050 and
#   is AUTHORITATIVE. 🔴 It ended at 2026, so the cliff was NEXT YEAR — otv4's
#   copy reached 2027 and nothing compared the two, which is DEP.11 found by
#   looking rather than by it biting. 🔴 And `_via_library` USED TO OVERRIDE the
#   list, so which source decided depended on whether a pip package happened to
#   be installed. It is now a cross-check for the checker only.
#   Dates generated from the NYSE rules offline and pinned by a checker that
#   regenerates them AND diffs this set against otv4's.
# v0.2.0 (2026-09-05) — dtp r287 / TZ.1 — the naive `today` here asked a UTC box and rolled at 20:00 ET
#   (19:00 in winter), so anything run after that silently asked for TOMORROW and came
#   back empty. It now goes through `ettime`, the one ET/UTC boundary.
"""
Trading-day gate. Keeps the orchestrator from waking the fleet on weekends
and market holidays.

HOLIDAYS_US is AUTHORITATIVE and runs to 2050. `pandas_market_calendars`, if
installed, is used only as a CROSS-CHECK by tools/check_market_calendar.py — it
no longer overrides the list at runtime, because which source decided must not
depend on what happens to be pip-installed.
"""

from datetime import date
import ettime                                            # noqa: E402

# US equity market full-closure holidays. Extend annually.
# (Early-close days are intentionally treated as normal trading days.)
# ── THE STANDARD CLOSURES, HARDCODED THROUGH 2050 ───────────────────────────
# Operator, 2026-09-07: *"If we know the standard days, then hard code them. I
# can manually account for 1-offs."*
#
# 🔴 THIS LIST ENDED AT 2026, SO THE CLIFF WAS NEXT YEAR, NOT 2028. otv4's copy
# reached 2027; this one did not, and nothing compared them — which is DEP.11
# exactly, found by looking rather than by it biting.
#
# 🔑 GENERATED FROM THE NYSE RULES, NOT TYPED, and `tools/check_market_calendar.py`
# REGENERATES them and fails on a single wrong date. Nine of ten closures are
# fixed-date or nth-weekday; Good Friday is Easter minus two, which has an exact
# closed form. The rules never run here — only in the checker.
#
# ⚠️ NOTE 2027-12-31: New Year's Day 2028 falls on a Saturday, so the observed
# close lands in the PREVIOUS year — exactly where a year-organised list drops it.
HOLIDAYS_US = {
    # 2026
    date(2026, 1, 1),         # New Year's Day
    date(2026, 1, 19),        # MLK Jr. Day
    date(2026, 2, 16),        # Presidents' Day
    date(2026, 4, 3),         # Good Friday
    date(2026, 5, 25),        # Memorial Day
    date(2026, 6, 19),        # Juneteenth
    date(2026, 7, 3),         # Independence Day (observed)
    date(2026, 9, 7),         # Labor Day
    date(2026, 11, 26),       # Thanksgiving
    date(2026, 12, 25),       # Christmas
    # 2027
    date(2027, 1, 1),         # New Year's Day
    date(2027, 1, 18),        # MLK Jr. Day
    date(2027, 2, 15),        # Presidents' Day
    date(2027, 3, 26),        # Good Friday
    date(2027, 5, 31),        # Memorial Day
    date(2027, 6, 18),        # Juneteenth (observed)
    date(2027, 7, 5),         # Independence Day (observed)
    date(2027, 9, 6),         # Labor Day
    date(2027, 11, 25),       # Thanksgiving
    date(2027, 12, 24),       # Christmas (observed)
    # 2028
    date(2027, 12, 31),       # New Year's Day (observed)
    date(2028, 1, 17),        # MLK Jr. Day
    date(2028, 2, 21),        # Presidents' Day
    date(2028, 4, 14),        # Good Friday
    date(2028, 5, 29),        # Memorial Day
    date(2028, 6, 19),        # Juneteenth
    date(2028, 7, 4),         # Independence Day
    date(2028, 9, 4),         # Labor Day
    date(2028, 11, 23),       # Thanksgiving
    date(2028, 12, 25),       # Christmas
    # 2029
    date(2029, 1, 1),         # New Year's Day
    date(2029, 1, 15),        # MLK Jr. Day
    date(2029, 2, 19),        # Presidents' Day
    date(2029, 3, 30),        # Good Friday
    date(2029, 5, 28),        # Memorial Day
    date(2029, 6, 19),        # Juneteenth
    date(2029, 7, 4),         # Independence Day
    date(2029, 9, 3),         # Labor Day
    date(2029, 11, 22),       # Thanksgiving
    date(2029, 12, 25),       # Christmas
    # 2030
    date(2030, 1, 1),         # New Year's Day
    date(2030, 1, 21),        # MLK Jr. Day
    date(2030, 2, 18),        # Presidents' Day
    date(2030, 4, 19),        # Good Friday
    date(2030, 5, 27),        # Memorial Day
    date(2030, 6, 19),        # Juneteenth
    date(2030, 7, 4),         # Independence Day
    date(2030, 9, 2),         # Labor Day
    date(2030, 11, 28),       # Thanksgiving
    date(2030, 12, 25),       # Christmas
    # 2031
    date(2031, 1, 1),         # New Year's Day
    date(2031, 1, 20),        # MLK Jr. Day
    date(2031, 2, 17),        # Presidents' Day
    date(2031, 4, 11),        # Good Friday
    date(2031, 5, 26),        # Memorial Day
    date(2031, 6, 19),        # Juneteenth
    date(2031, 7, 4),         # Independence Day
    date(2031, 9, 1),         # Labor Day
    date(2031, 11, 27),       # Thanksgiving
    date(2031, 12, 25),       # Christmas
    # 2032
    date(2032, 1, 1),         # New Year's Day
    date(2032, 1, 19),        # MLK Jr. Day
    date(2032, 2, 16),        # Presidents' Day
    date(2032, 3, 26),        # Good Friday
    date(2032, 5, 31),        # Memorial Day
    date(2032, 6, 18),        # Juneteenth (observed)
    date(2032, 7, 5),         # Independence Day (observed)
    date(2032, 9, 6),         # Labor Day
    date(2032, 11, 25),       # Thanksgiving
    date(2032, 12, 24),       # Christmas (observed)
    # 2033
    date(2032, 12, 31),       # New Year's Day (observed)
    date(2033, 1, 17),        # MLK Jr. Day
    date(2033, 2, 21),        # Presidents' Day
    date(2033, 4, 15),        # Good Friday
    date(2033, 5, 30),        # Memorial Day
    date(2033, 6, 20),        # Juneteenth (observed)
    date(2033, 7, 4),         # Independence Day
    date(2033, 9, 5),         # Labor Day
    date(2033, 11, 24),       # Thanksgiving
    date(2033, 12, 26),       # Christmas (observed)
    # 2034
    date(2034, 1, 2),         # New Year's Day (observed)
    date(2034, 1, 16),        # MLK Jr. Day
    date(2034, 2, 20),        # Presidents' Day
    date(2034, 4, 7),         # Good Friday
    date(2034, 5, 29),        # Memorial Day
    date(2034, 6, 19),        # Juneteenth
    date(2034, 7, 4),         # Independence Day
    date(2034, 9, 4),         # Labor Day
    date(2034, 11, 23),       # Thanksgiving
    date(2034, 12, 25),       # Christmas
    # 2035
    date(2035, 1, 1),         # New Year's Day
    date(2035, 1, 15),        # MLK Jr. Day
    date(2035, 2, 19),        # Presidents' Day
    date(2035, 3, 23),        # Good Friday
    date(2035, 5, 28),        # Memorial Day
    date(2035, 6, 19),        # Juneteenth
    date(2035, 7, 4),         # Independence Day
    date(2035, 9, 3),         # Labor Day
    date(2035, 11, 22),       # Thanksgiving
    date(2035, 12, 25),       # Christmas
    # 2036
    date(2036, 1, 1),         # New Year's Day
    date(2036, 1, 21),        # MLK Jr. Day
    date(2036, 2, 18),        # Presidents' Day
    date(2036, 4, 11),        # Good Friday
    date(2036, 5, 26),        # Memorial Day
    date(2036, 6, 19),        # Juneteenth
    date(2036, 7, 4),         # Independence Day
    date(2036, 9, 1),         # Labor Day
    date(2036, 11, 27),       # Thanksgiving
    date(2036, 12, 25),       # Christmas
    # 2037
    date(2037, 1, 1),         # New Year's Day
    date(2037, 1, 19),        # MLK Jr. Day
    date(2037, 2, 16),        # Presidents' Day
    date(2037, 4, 3),         # Good Friday
    date(2037, 5, 25),        # Memorial Day
    date(2037, 6, 19),        # Juneteenth
    date(2037, 7, 3),         # Independence Day (observed)
    date(2037, 9, 7),         # Labor Day
    date(2037, 11, 26),       # Thanksgiving
    date(2037, 12, 25),       # Christmas
    # 2038
    date(2038, 1, 1),         # New Year's Day
    date(2038, 1, 18),        # MLK Jr. Day
    date(2038, 2, 15),        # Presidents' Day
    date(2038, 4, 23),        # Good Friday
    date(2038, 5, 31),        # Memorial Day
    date(2038, 6, 18),        # Juneteenth (observed)
    date(2038, 7, 5),         # Independence Day (observed)
    date(2038, 9, 6),         # Labor Day
    date(2038, 11, 25),       # Thanksgiving
    date(2038, 12, 24),       # Christmas (observed)
    # 2039
    date(2038, 12, 31),       # New Year's Day (observed)
    date(2039, 1, 17),        # MLK Jr. Day
    date(2039, 2, 21),        # Presidents' Day
    date(2039, 4, 8),         # Good Friday
    date(2039, 5, 30),        # Memorial Day
    date(2039, 6, 20),        # Juneteenth (observed)
    date(2039, 7, 4),         # Independence Day
    date(2039, 9, 5),         # Labor Day
    date(2039, 11, 24),       # Thanksgiving
    date(2039, 12, 26),       # Christmas (observed)
    # 2040
    date(2040, 1, 2),         # New Year's Day (observed)
    date(2040, 1, 16),        # MLK Jr. Day
    date(2040, 2, 20),        # Presidents' Day
    date(2040, 3, 30),        # Good Friday
    date(2040, 5, 28),        # Memorial Day
    date(2040, 6, 19),        # Juneteenth
    date(2040, 7, 4),         # Independence Day
    date(2040, 9, 3),         # Labor Day
    date(2040, 11, 22),       # Thanksgiving
    date(2040, 12, 25),       # Christmas
    # 2041
    date(2041, 1, 1),         # New Year's Day
    date(2041, 1, 21),        # MLK Jr. Day
    date(2041, 2, 18),        # Presidents' Day
    date(2041, 4, 19),        # Good Friday
    date(2041, 5, 27),        # Memorial Day
    date(2041, 6, 19),        # Juneteenth
    date(2041, 7, 4),         # Independence Day
    date(2041, 9, 2),         # Labor Day
    date(2041, 11, 28),       # Thanksgiving
    date(2041, 12, 25),       # Christmas
    # 2042
    date(2042, 1, 1),         # New Year's Day
    date(2042, 1, 20),        # MLK Jr. Day
    date(2042, 2, 17),        # Presidents' Day
    date(2042, 4, 4),         # Good Friday
    date(2042, 5, 26),        # Memorial Day
    date(2042, 6, 19),        # Juneteenth
    date(2042, 7, 4),         # Independence Day
    date(2042, 9, 1),         # Labor Day
    date(2042, 11, 27),       # Thanksgiving
    date(2042, 12, 25),       # Christmas
    # 2043
    date(2043, 1, 1),         # New Year's Day
    date(2043, 1, 19),        # MLK Jr. Day
    date(2043, 2, 16),        # Presidents' Day
    date(2043, 3, 27),        # Good Friday
    date(2043, 5, 25),        # Memorial Day
    date(2043, 6, 19),        # Juneteenth
    date(2043, 7, 3),         # Independence Day (observed)
    date(2043, 9, 7),         # Labor Day
    date(2043, 11, 26),       # Thanksgiving
    date(2043, 12, 25),       # Christmas
    # 2044
    date(2044, 1, 1),         # New Year's Day
    date(2044, 1, 18),        # MLK Jr. Day
    date(2044, 2, 15),        # Presidents' Day
    date(2044, 4, 15),        # Good Friday
    date(2044, 5, 30),        # Memorial Day
    date(2044, 6, 20),        # Juneteenth (observed)
    date(2044, 7, 4),         # Independence Day
    date(2044, 9, 5),         # Labor Day
    date(2044, 11, 24),       # Thanksgiving
    date(2044, 12, 26),       # Christmas (observed)
    # 2045
    date(2045, 1, 2),         # New Year's Day (observed)
    date(2045, 1, 16),        # MLK Jr. Day
    date(2045, 2, 20),        # Presidents' Day
    date(2045, 4, 7),         # Good Friday
    date(2045, 5, 29),        # Memorial Day
    date(2045, 6, 19),        # Juneteenth
    date(2045, 7, 4),         # Independence Day
    date(2045, 9, 4),         # Labor Day
    date(2045, 11, 23),       # Thanksgiving
    date(2045, 12, 25),       # Christmas
    # 2046
    date(2046, 1, 1),         # New Year's Day
    date(2046, 1, 15),        # MLK Jr. Day
    date(2046, 2, 19),        # Presidents' Day
    date(2046, 3, 23),        # Good Friday
    date(2046, 5, 28),        # Memorial Day
    date(2046, 6, 19),        # Juneteenth
    date(2046, 7, 4),         # Independence Day
    date(2046, 9, 3),         # Labor Day
    date(2046, 11, 22),       # Thanksgiving
    date(2046, 12, 25),       # Christmas
    # 2047
    date(2047, 1, 1),         # New Year's Day
    date(2047, 1, 21),        # MLK Jr. Day
    date(2047, 2, 18),        # Presidents' Day
    date(2047, 4, 12),        # Good Friday
    date(2047, 5, 27),        # Memorial Day
    date(2047, 6, 19),        # Juneteenth
    date(2047, 7, 4),         # Independence Day
    date(2047, 9, 2),         # Labor Day
    date(2047, 11, 28),       # Thanksgiving
    date(2047, 12, 25),       # Christmas
    # 2048
    date(2048, 1, 1),         # New Year's Day
    date(2048, 1, 20),        # MLK Jr. Day
    date(2048, 2, 17),        # Presidents' Day
    date(2048, 4, 3),         # Good Friday
    date(2048, 5, 25),        # Memorial Day
    date(2048, 6, 19),        # Juneteenth
    date(2048, 7, 3),         # Independence Day (observed)
    date(2048, 9, 7),         # Labor Day
    date(2048, 11, 26),       # Thanksgiving
    date(2048, 12, 25),       # Christmas
    # 2049
    date(2049, 1, 1),         # New Year's Day
    date(2049, 1, 18),        # MLK Jr. Day
    date(2049, 2, 15),        # Presidents' Day
    date(2049, 4, 16),        # Good Friday
    date(2049, 5, 31),        # Memorial Day
    date(2049, 6, 18),        # Juneteenth (observed)
    date(2049, 7, 5),         # Independence Day (observed)
    date(2049, 9, 6),         # Labor Day
    date(2049, 11, 25),       # Thanksgiving
    date(2049, 12, 24),       # Christmas (observed)
    # 2050
    date(2049, 12, 31),       # New Year's Day (observed)
    date(2050, 1, 17),        # MLK Jr. Day
    date(2050, 2, 21),        # Presidents' Day
    date(2050, 4, 8),         # Good Friday
    date(2050, 5, 30),        # Memorial Day
    date(2050, 6, 20),        # Juneteenth (observed)
    date(2050, 7, 4),         # Independence Day
    date(2050, 9, 5),         # Labor Day
    date(2050, 11, 24),       # Thanksgiving
    date(2050, 12, 26),       # Christmas (observed)
}
# One-off exchange closures — presidential funerals, 9/11, Sandy. No algorithm
# produces these; hand-maintained by operator ruling.
# ⚠️ A WRONG ENTRY HERE CLOSES THE MARKET. The calendar fails toward TRADING for
# dates it does not know, but a date wrongly PRESENT is an explicit close.
AD_HOC_CLOSURES: set = set()

HOLIDAYS_US |= AD_HOC_CLOSURES

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
    # 🔴 r317 — THE LIST IS AUTHORITATIVE; THE LIBRARY NO LONGER OVERRIDES IT.
    # This used to `return lib` whenever `_via_library` answered, so WHICH
    # SOURCE DECIDED depended on whether `pandas_market_calendars` happened to
    # be pip-installed — and nothing on the page said so. Two answers to one
    # question, selected by an environment nobody documents, is the class this
    # codebase keeps finding in its own code.
    # ⚠️ `_via_library` SURVIVES as a CROSS-CHECK for the checker, which is the
    # one thing it is genuinely better at: it knows the ad-hoc closures no rule
    # produces. It informs; it does not decide.
    if d.weekday() >= 5:      # Sat/Sun
        return False
    return d not in HOLIDAYS_US


if __name__ == "__main__":
    today = date.fromisoformat(ettime.today_et())
    print(f"{today.isoformat()} trading_day={is_trading_day(today)}")
