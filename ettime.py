#!/usr/bin/env python3
# day_trader_pro/ettime.py — v1.0
# v1.0 (2026-09-05) — dtp r287. ONE TRANSLATOR BETWEEN WHAT THE OPERATOR MEANS
#   AND WHAT THE MACHINE STORES.
#
#   🔴 THE OPERATOR'S LONG-STANDING SYMPTOM, IN HIS WORDS: *"It's incredibly
#   annoying when I run a report for 'today' at 6pm and it says nothing to
#   report, because UTC has already started the next day."* Every control box
#   runs UTC. A bare `date.today()` therefore rolls at **20:00 ET in summer,
#   19:00 in winter** — the instant UTC midnight lands — and after that every
#   naive default silently asks for TOMORROW. Tomorrow has no data, so the
#   report does not error; it says nothing to report, which reads as a finding
#   about the market rather than a defect in the clock. That is the worst shape
#   of bug this project has.
#
#   📊 MEASURED ACROSS THE CONTROL REPO, 2026-09-05, BEFORE WRITING A LINE:
#   NINE sites handed out a naive "today" — eod_analysis, eod_conductor_v2,
#   fit_readiness, pnl_s3, excursion_report, orchestrator, tools/report_parity,
#   trade_report, and **market_calendar, which is the module that decides what
#   a trading day IS**. Against those, FIVE more had it right and each carried
#   its own private three-line copy: standings, harvest, consolidate_trades,
#   eod_report, orchestrator's other function.
#   🔑 SO THIS WAS NEVER A MISSING TRANSLATOR. It was five of them and nine
#   places that never got one, which is how the count grows every time somebody
#   adds a report.
#
#   ⚠️ THE RULE IT ENCODES, restated from the operator's standing instruction:
#   **backend, storage and epochs render UTC; anything the OPERATOR reads or
#   types renders ET.** The third category is the one that causes bugs — a
#   PREDICATE about the market ("is the exchange open", "what is today's
#   trading date") is an EXCHANGE fact and must be asked in ET, however the box
#   is configured.
#
#   ⚠️ AND THE FIX IS NOT "SET THE BOXES TO EASTERN". That would make every
#   stored epoch ambiguous across a DST transition and break the warehouse's
#   whole premise. Storage stays UTC. This module is the boundary.
#
#   🔑 `et_day` AND `et_bounds` ARE NOT REIMPLEMENTED HERE. They live in
#   `warehouse_reader` and are re-exported, because two definitions of "which
#   ET day does this epoch belong to" is exactly the failure this module
#   exists to end. If they ever move, they move once.
"""One boundary between operator time (ET) and machine time (UTC).

    from ettime import today_et, now_et, operator_date, et_day, et_bounds

Every date an operator types, sees, or gets as a default goes through here.
Every epoch stored anywhere stays UTC.
"""
from __future__ import annotations

import os          # noqa: F401  (kept: callers import os via this module's env)
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

# 🔴 THIS MODULE IMPORTS NOTHING FROM THIS REPO, ON PURPOSE. A first cut had it
# re-export `et_day`/`et_bounds` FROM `warehouse_reader`, and that closed a
# cycle immediately: `warehouse_reader` imports `market_calendar`, which now
# asks this module what "today" is. The boundary cannot depend on one of its
# own consumers. So the two functions live HERE and `warehouse_reader`
# re-exports them for its existing callers — one implementation, and the
# dependency points one way.


def et_day(ts) -> str:
    """A unix epoch -> the ET TRADING DAY it belongs to.

    ⚠️ THE PREDICATE IS AN EXCHANGE FACT, NOT A DISPLAY CHOICE. Every stored
    ts_epoch is UTC seconds and the control box runs UTC, so a naive
    `datetime.fromtimestamp(ts).date()` rolls the day at 20:00 ET — the
    long-standing symptom that a report for "today" run after the close comes
    back empty. Convert explicitly; never lean on the ambient clock.
    """
    try:
        return (datetime.fromtimestamp(float(ts), tz=UTC)
                .astimezone(ET).date().isoformat())
    except (TypeError, ValueError, OSError, OverflowError):
        return ""


def et_bounds(d0: str, d1: str) -> tuple:
    """[start, end) epoch seconds spanning the ET days d0..d1 inclusive."""
    a = datetime.strptime(d0, "%Y-%m-%d").replace(tzinfo=ET)
    b = datetime.strptime(d1, "%Y-%m-%d").replace(tzinfo=ET) + timedelta(days=1)
    return a.timestamp(), b.timestamp()


def now_et() -> datetime:
    """The current moment as the operator experiences it. Always aware."""
    return datetime.now(ET)


def today_et() -> str:
    """The ET trading date an operator means by "today". `YYYY-MM-DD`.

    🔴 THIS IS THE FUNCTION THE NINE NAIVE SITES SHOULD HAVE CALLED. On a UTC
    box `date.today()` becomes tomorrow at 20:00 ET (19:00 in winter) and the
    report that follows finds nothing — silently, and in the direction that
    looks like an answer.
    ⚠️ IT IS DELIBERATELY *NOT* CALENDAR-AWARE. On a Sunday this returns
    Sunday, because "what day is it" and "was there a session" are different
    questions and conflating them is how a weekend read starts lying about a
    Friday. `market_calendar` answers the second one, and it now asks this
    module for the first.
    """
    return now_et().date().isoformat()


def operator_date(value: str | None, default_today: bool = True) -> str:
    """Whatever the operator typed -> an ET trading date.

    Accepts an ISO date, `today`, `yesterday`, or an empty answer (ENTER at a
    prompt) which means today. Anything else raises with the value quoted,
    because a prompt that silently reinterprets a typo is how you get a clean
    report about the wrong day.

    ⚠️ `yesterday` IS CALENDAR-YESTERDAY, NOT THE PREVIOUS SESSION. Monday's
    "yesterday" is Sunday and will legitimately hold nothing; ask
    `market_calendar` for the previous session when that is the question.
    Making one word mean two things is the ambiguity this module removes.
    """
    v = (value or "").strip().lower()
    if not v:
        if default_today:
            return today_et()
        raise ValueError("no date given and no default allowed here")
    if v == "today":
        return today_et()
    if v == "yesterday":
        return (now_et() - timedelta(days=1)).date().isoformat()
    try:
        return datetime.strptime(v, "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise ValueError(
            f"{value!r} is not a date I understand — use YYYY-MM-DD, "
            f"'today' or 'yesterday'") from None


def days_back(n: int, end: str | None = None) -> list:
    """The `n` ET dates ending at `end` (default today), oldest first.

    Report ranges are written in ET days, never by subtracting seconds from an
    epoch: `86400` is not a day across a DST boundary and a range built that
    way is off by an hour twice a year, in the direction that quietly drops the
    first or last session.
    """
    last = datetime.strptime(end or today_et(), "%Y-%m-%d").date()
    return [(last - timedelta(days=i)).isoformat() for i in range(n - 1, -1, -1)]


def stamp_et(ts) -> str:
    """A stored UTC epoch -> `YYYY-MM-DD HH:MM ET`, for anything a human reads."""
    try:
        return (datetime.fromtimestamp(float(ts), tz=UTC)
                .astimezone(ET).strftime("%Y-%m-%d %H:%M ET"))
    except (TypeError, ValueError, OSError, OverflowError):
        return "(no time)"
