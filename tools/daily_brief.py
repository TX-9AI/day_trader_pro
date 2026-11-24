#!/usr/bin/env python3
"""
day_trader_pro/tools/daily_brief.py  v1.8  -  the post-trading-day brief (PDF) for any session.
v1.8  2026-11-24  dtp r584 / RECS.1 — SECTION 8, "RECOMMENDATIONS — FOR APPROVAL", THE LAST SECTION. The operator,
      2026-11-24: "I would like the final section to contain a summary of the recommendations so we can get those
      approved & scheduled." After section 7 (only the Sources list follows): one numbered table from
      ~/reviews/schedule/recommendations.tsv (--recs; tools/daily_recap.rec_section, read only): id, what, why, type,
      touches, the proposed slot (the next free fitting window from tools/calendar_view.build over seven days) and the
      status (NEW, CARRIED from an earlier day, APPROVED-scheduled with its slot, DECLINED). The recap appends; the
      coordinator records each answer; this file never writes the ledger. The validator's refusals are named under the
      table. A failed read prints NOT READ with the reason. Sections 1-7 are unchanged.
v1.7  2026-11-24  dtp r583 / CASHBOOK.3 — SECTION 5b SHOWS C5 BESIDE C1-C4. tools/cash_books.py v1.6 scores a fifth book,
      C5 (frozen 2026-11-24 in ~/reviews/cash_candidate_c5_20261124/PREREG.md; its equity list was chosen in hindsight).
      cash_books_rows lists every book the scorer scored; C5's Fwd columns are its own forward window (from 2026-11-24,
      "forward_c5", "-" until then), never C1-C4's (from 11-23); its Day column is "-" before 11-24; the head line says
      C5's combined figure is hindsight, reference only. C1-C4's rows are unchanged.
v1.6  2026-11-23  dtp r581 — SPX IS BACK ON $5,000. The operator, 2026-11-23: "I'm going to just bump it back up to $5K for
      consistency's sake" (applied 18:41 ET). cash_budget: SPX $5,000 an entry, except $4,200 on 2026-11-23 ONLY
      (CASH_BUDGET_DATED, inclusive windows); QQQ $1,050 unchanged.
v1.5  2026-11-23  dtp r580 / CAL.1 + RECAP.3 — THE SPX CASH BUDGET IS DATE-AWARE: cash_budget(sym, day) is $5,000 an SPX
      entry before 2026-11-23 and $4,200 from it (QQQ $1,050 unchanged); section 5's re-scale and its sizing line use the
      day's figure (it was a flat $5,000 every day). SECTION 7, THE SCHEDULE. The operator, 2026-11-23: "We just want to prevent
      unscheduled work from colliding with planned jobs." One table from tools/calendar_view.py (read only), built when
      the PDF is built: now to tomorrow 17:00 ET, control's timers, the box windows (wake + sweep, RTH, the close, the
      study dispatch) and ~/reviews/schedule/planned.tsv, a COLLISION flag on a planned box row that overlaps one, and
      the one-line load summary. A failed read prints NOT READ with the reason; nothing else in the brief changes.
v1.4  2026-11-22  dtp r578 / CAP.11 (control's half of OTV5 r151) — THE BRIEF HEADLINES "AS CASH WOULD HAVE TRADED". OTV5
      r151 makes the daily catastrophic cap record only on a paper box (the operator, 2026-11-22: "there's no harm in
      letting paper run & we can just note if the breaker would have popped"): the box trades on and tags what it
      opens after the would-be trip after_cap = 1; and a cash box books OGAP paper beside its cash rows (OTV5 r150).
      load_day_trades gives every row its book (tools/review_kit.split, the one rule, with review_kit.box_modes: a paper row on a cash box's day - its
      Service mode line in the conductor's extract, else a cash row - is paper_on_cash, else an after_cap row is after_cap, else headline). compute()'s trades, every
      total, table, chart and the cash re-scale are the HEADLINE rows; the extras are carried beside (c["after_cap"],
      c["paper_on_cash"]) and the day's would-pop records come from ~/reviews/breaker/DAY.csv (review_kit `trades`,
      the nightly review). Section 1 prints, under the day totals, one "extra paper after the breaker" line (n, net,
      fees beside, each would-pop record: box, time, day net) and one line for OGAP's paper rows on a cash box (OGAP's
      own evaluation, never in the cash figures), each only when it has something; --facts carries all three always
      (after_cap, paper_on_cash, would_pop: a list, or null when the breaker file was not written). A day with neither
      builds the same pages as v1.3.
v1.3  2026-11-22  dtp r575 / HALF.2 + RWATCH.1 — THE HALF-DAY LINE AND SECTION 5c, THE RUNAWAY EQUITY WATCH.
      (1) A 13:00 half day (market_calendar.is_half_day) is a non-trading day by the operator's ruling (2026-11-22: "Yes,
      just treat them as bank holidays. No trading."; OTV5 r145 opens nothing): under the title the brief says so
      plainly (zero trades expected, data recorded only), names any trade that opened anyway as a DEFECT, and section 3
      says no study is proposed from a non-trading day.
      (2) Section 5c (the operator, 2026-11-22: "I would keep any poor performers on runaway on notice to potentially be
      cut"; "Can you put a trend bar for runaway on the equities ..."): from tools/runaway_watch.py (the one scorer,
      WATCH.md frozen and sealed): the watch-list table (forward n, net, EV a trade against the bar, status), one small
      trend line per equity (cumulative net by Runaway trade since 2026-10-26, the 2026-11-23 forward marker, this
      file's palette), and the per-equity table with the DIRECTION arrow (last 8 vs earlier, n beside); then the
      session's "runaway_watch" commentary, or the validator's reason when it was withheld. Report only. A scorer
      failure prints NOT MEASURED and the brief builds.
v1.2  2026-11-22  dtp r572 / CASHBOOK.1 — SECTION 5b, THE CASH CANDIDATE BOOKS C1-C4. The operator, 2026-11-22: "On
      C1-C4, I would like some commentary on the daily and weekly recaps as to how each of them is performing". After
      section 5, one table from tools/cash_books.py (the one scorer, PREREG frozen; ~/reviews/trades CSVs, the mark,
      fees beside): per book the day's n and net, the forward window to date (n, gross, fees, net, EV with its 95%
      day-bootstrap interval, gross without the two largest winners ALWAYS beside gross without the two largest losers,
      concentration context only (amendment 1), the trades fired beside a Hunt/OGAP position) and the
      combined window; then the session's "cash_books" commentary, or the validator's reason when it was withheld.
      Report only: never in the window EV or the theories. A scorer failure prints NOT MEASURED and the brief builds.
v1.1  2026-11-21  dtp r569 / RECAP.1 — THE GENERATOR MOVES INTO dtp AND THE DAILY RECAP TIMER DRIVES IT. The operator,
      2026-11-21: "Yes, we are going to begin firming up our system, our trading & our analysis". Moved from
      ~/otv5_builds/daily_brief/daily_brief.py (v1.0, outside any repo); tools/daily_recap.sh runs it at the end of
      each trading day. Changes from v1.0:
      · the notes default to ~/reviews/daily_brief/notes/<date>.json (never beside this file: the repo holds no
        day's judgement); --notes still overrides.
      · --facts PATH writes the data pass (trades, totals, tape per symbol, VIX, the cash re-scale) as JSON and builds
        no PDF: the recap session reads it, so its figures are the PDF's own.
      · --summary-json PATH writes the run summary (day P&L at the mark, fees beside, pages) beside the PDF.
      · section 3 labels its evidence by the day ("What MM-DD showed", was "11-20" for every day) and names each
        proposal's queue id (WS.<n>) when the recap appended it; section 6 is the day's ONE maintenance proposal for
        a yes (backlog id, what, risk, weekday or Sunday).
      · a day with no mainline trades still builds (totals of zero, no charts) instead of stopping.
      · a paragraph list written as one string is read as one paragraph (normalize_notes), never letter by letter.
      · the chart's time axis ends at the session's close (13:00 on a half day such as 2026-11-27), from dtp
        market_calendar.
      THE VENV LIVES OUTSIDE THE REPO: /home/ubuntu/venvs/daily_brief (matplotlib, reportlab, boto3, pypdfium2; pinned
      in tools/daily_brief.requirements.txt), created once by tools/install_daily_recap.sh. dtp's own venv is not
      touched.
v1.0  2026-11-21  the first build, by hand, outside the repo (the 11-20 brief).

Usage:
  /home/ubuntu/venvs/daily_brief/bin/python -I tools/daily_brief.py --date 2026-11-20 \
      [--notes ~/reviews/daily_brief/notes/2026-11-20.json] [--out ~/reviews/daily_brief] \
      [--facts FILE.json] [--summary-json FILE.json] [--recs ~/reviews/schedule/recommendations.tsv]

READ-ONLY. Reads the S3 warehouse (control's read-only role) and local files; writes one PDF
(<out>/daily_brief_<date>.pdf), or with --facts one JSON file, and nothing else. No box, no broker, no service
Environment.

Data rules (the operator's):
  - trades: OTV5 tests/warehouse_source.load_trades -> mainline() (drops the OTV4TEST fleet's rows)
  - P&L is pnl_usd, the mark basis (the entry ladder never fills worse than the mark)
  - fees: the warehouse rows carry no fee column, so fees come from the control fee model
    (OTV5 tests/fees.py fees_for, the same model review_kit uses); always BESIDE P&L, never inside it
  - candles: TastyTrade-sourced 1m bars from S3 raw/candles/dt=<D>/sym=<S>/interval=1m/
    (latest pushed_at wins per bar); RTH 09:30-15:59 ET only; no yfinance
  - cash re-scale: contracts = floor(budget / (entry mark x 100)), QQQ $1,050 and SPX $5,000 per entry ($4,200 on 2026-11-23 only);
    a trade whose single contract costs more than its budget is refused (0 contracts)

Narrative: per-symbol synopses and sections 2-4 come from the --notes JSON (written by the analyst).
Without a notes file every section is still produced from the data: tape facts, the trades, the
totals and the cash table, with the judgement paragraphs marked "no notes supplied".
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import math
import os
import re
import sys
from collections import defaultdict
from zoneinfo import ZoneInfo

OTV5 = os.path.expanduser(os.environ.get("DTP_CONTROL_REPO", "~/OTV5"))
DTP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTES_DIR = os.path.expanduser("~/reviews/daily_brief/notes")
sys.path.insert(0, os.path.join(OTV5, "tests"))
import warehouse_source as ws          # noqa: E402
import fees as feemodel                # noqa: E402
sys.path.append(DTP_ROOT)
import market_calendar                 # noqa: E402  (dtp: the 13:00 close of a half day)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import review_kit as RK                # noqa: E402  (v1.4: split, the one as-cash rule; read_breaker)

import matplotlib                      # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt        # noqa: E402
import matplotlib.dates as mdates      # noqa: E402
from matplotlib import font_manager    # noqa: E402

from reportlab.lib import colors       # noqa: E402
from reportlab.lib.enums import TA_LEFT  # noqa: E402
from reportlab.lib.pagesizes import letter  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import inch   # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph,  # noqa: E402
                                SimpleDocTemplate, Spacer, Table, TableStyle)

ET = ZoneInfo("America/New_York")
INDEX_FIRST = ("SPX", "QQQ")
CASH_BUDGET = {"QQQ": 1050.0, "SPX": 5000.0}            # every day outside a dated window below
CASH_BUDGET_DATED = {"SPX": (("2026-11-23", "2026-11-23", 4200.0),)}   # v1.6: (from, to inclusive, usd): 11-23 only


def cash_budget(sym, day):
    """v1.6 -> the per-entry cash budget for `sym` on `day` (ISO date)."""
    for lo, hi, usd in CASH_BUDGET_DATED.get(sym, ()):
        if lo <= day <= hi:
            return usd
    return CASH_BUDGET[sym]
CASH_STRATEGIES = ("PARK", "RunawayContinuation", "LiquidityHunt", "OGAP")
WINDOW_SETUPS = ("PARK", "RunawayContinuation", "LiquidityHunt")   # OGAP is its own line
SHORT = {"RunawayContinuation": "Runaway", "LiquidityHunt": "Hunt", "PARK": "PARK", "OGAP": "OGAP"}
ENTRY_WINDOWS = [("09:35", "10:30", "Runaway / Hunt"), ("09:46", "10:32", "OGAP"), ("11:01", "11:03", "PARK")]

# palette (dataviz reference instance): neutral ink + status good/critical for win/loss
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#8a8984", "#e4e3df"
SURFACE = "#fcfcfb"
WIN, LOSS = "#0ca30c", "#d03b3b"
CANDLE_UP, CANDLE_DN = "#b9b8b2", "#52514e"
ACCENT = "#2a78d6"

# ── fonts: DejaVu from matplotlib's own data dir (the base-14 fonts lack the minus sign) ────────────
_FD = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
pdfmetrics.registerFont(TTFont("DV", os.path.join(_FD, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DVB", os.path.join(_FD, "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFont(TTFont("DVI", os.path.join(_FD, "DejaVuSans-Oblique.ttf")))
pdfmetrics.registerFont(TTFont("DVBI", os.path.join(_FD, "DejaVuSans-BoldOblique.ttf")))
from reportlab.pdfbase.pdfmetrics import registerFontFamily  # noqa: E402
registerFontFamily("DV", normal="DV", bold="DVB", italic="DVI", boldItalic="DVBI")
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "axes.edgecolor": MUTED,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                     "axes.facecolor": SURFACE, "figure.facecolor": "white"})


# ── helpers ───────────────────────────────────────────────────────────────────────────────────────
def money(x, sign=True, dec=2):
    if x is None:
        return "n/a"
    s = f"{abs(x):,.{dec}f}"
    if not sign:
        return f"${s}"
    if round(x, dec) == 0:
        return f"${s}"
    return f"{'+' if x > 0 else '−'}${s}"


def pct(x, dec=2):
    return "n/a" if x is None else f"{'+' if x > 0 else '−' if x < 0 else ''}{abs(x):.{dec}f}%"


def to_et(s):
    if not s:
        return None
    t = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return t.astimezone(ET)


def esc(s):
    s = str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = s.replace(" -- ", " – ")
    return s


def fee_of(row, contracts=None):
    r = dict(row)
    if contracts is not None:
        r["contracts"] = contracts
    res = feemodel.fees_for(r)
    return None if isinstance(res, feemodel.Unpriced) else float(res.total)


def contract_label(r):
    side = str(r.get("option_side") or "").upper()[:1] or ("P" if "P" in str(r.get("option_symbol"))[-10:] else "C")
    k = r.get("strike")
    try:
        k = f"{float(k):g}"
    except (TypeError, ValueError):
        k = "?"
    exp = str(r.get("expiry") or "")[:10]
    tag = "0DTE" if exp == r["_day"] else exp[5:]
    d = str(r.get("direction") or "").lower()
    return f"{d} {k}{side} {tag}".strip()


# ── data ──────────────────────────────────────────────────────────────────────────────────────────
def load_day_trades(day):
    rows, meta = ws.load_trades([day])
    kept, dropped = ws.mainline(rows, lambda r: day)
    out = []
    for r, bk in zip(kept, RK.split(kept, sym_key="symbol", modes=RK.box_modes(day))):    # v1.4 (CAP.11): the row's book
        r = dict(r)
        r["_book"] = bk
        r["_day"] = day
        r["_in"] = to_et(r.get("entry_time"))
        r["_out"] = to_et(r.get("exit_time"))
        r["_fee"] = fee_of(r)
        r["_pnl"] = float(r["pnl_usd"]) if r.get("pnl_usd") not in (None, "") else None
        out.append(r)
    out.sort(key=lambda r: (r["_in"] or dt.datetime.max.replace(tzinfo=ET)))
    return out, meta, dropped


def load_bars(day, symbols, s3=None):
    """-> {sym: [(et_datetime, o, h, l, c, v)]} RTH 1m, latest push wins per bar; and meta per symbol."""
    s3 = s3 or ws.client()
    out, info = {}, {}
    for sym in symbols:
        prefix = f"{ws.PREFIX}/candles/dt={day}/sym={sym}/interval=1m/"
        best = {}
        n_obj = 0
        pg = s3.get_paginator("list_objects_v2")
        for page in pg.paginate(Bucket=ws.BUCKET, Prefix=prefix):
            for o in page.get("Contents", []) or []:
                n_obj += 1
                try:
                    env = json.loads(s3.get_object(Bucket=ws.BUCKET, Key=o["Key"])["Body"].read())
                except Exception:                                   # noqa: BLE001
                    continue
                stamp = str(env.get("pushed_at_utc") or "")
                for b in env.get("record") or []:
                    if not isinstance(b, dict) or b.get("interval") not in (None, "1m"):
                        continue
                    ts = b.get("ts_epoch_ms")
                    if ts is None:
                        continue
                    if ts not in best or stamp >= best[ts][0]:
                        best[ts] = (stamp, b)
        bars = []
        for ts, (_s, b) in sorted(best.items()):
            t = dt.datetime.fromtimestamp(ts / 1000, tz=dt.timezone.utc).astimezone(ET)
            if not (dt.time(9, 30) <= t.time() < dt.time(16, 0)):
                continue
            bars.append((t, float(b["open"]), float(b["high"]), float(b["low"]), float(b["close"]),
                         float(b.get("volume") or 0)))
        out[sym] = bars
        info[sym] = {"objects": n_obj, "bars": len(bars)}
    return out, info


VOL_PROXY = {"SPX": "SPY"}   # an index prints no volume; its panel shows the ETF's (TastyTrade 1m, CAP.9 capture)


def load_proxy_volume(day, sym, s3=None):
    """-> {et_minute: volume} for `sym` on `day` from raw/candles_full/interval=1m/sym=<sym>/ (csv.gz, every pull)."""
    import csv, gzip
    s3 = s3 or ws.client()
    prefix = f"{ws.PREFIX}/candles_full/interval=1m/sym={sym}/"
    vol = {}
    pg = s3.get_paginator("list_objects_v2")
    for page in pg.paginate(Bucket=ws.BUCKET, Prefix=prefix):
        for o in page.get("Contents", []) or []:
            try:
                raw = gzip.decompress(s3.get_object(Bucket=ws.BUCKET, Key=o["Key"])["Body"].read()).decode()
            except Exception:                                       # noqa: BLE001
                continue
            for r in csv.DictReader(io.StringIO(raw)):
                try:
                    t = dt.datetime.fromtimestamp(int(r["time"]) / 1000, tz=dt.timezone.utc).astimezone(ET)
                    v = float(r["volume"] or 0)
                except (KeyError, ValueError):
                    continue
                if t.date().isoformat() == day and dt.time(9, 30) <= t.time() < dt.time(16, 0) and v > 0:
                    vol[t.replace(second=0, microsecond=0)] = v
    return vol


def bar_at(bars, t):
    """The 1m bar that contains time t (or the last bar before it)."""
    best = None
    for b in bars:
        if b[0] <= t:
            best = b
        else:
            break
    return best


def tape_stats(bars):
    if not bars:
        return None
    o = bars[0][1]
    c = bars[-1][4]
    hi = max(bars, key=lambda b: b[2])
    lo = min(bars, key=lambda b: b[3])

    def close_at(hhmm):
        h, m = map(int, hhmm.split(":"))
        b = [x for x in bars if x[0].time() <= dt.time(h, m)]
        return b[-1][4] if b else None
    c1030, c1545 = close_at("10:30"), close_at("15:45")
    o11 = [x for x in bars if x[0].time() >= dt.time(11, 0)]
    c1100 = o11[0][1] if o11 else None          # the 11:00 bar's open (the nightly review's construction)
    return {"open": o, "close": c, "oc": (c / o - 1) * 100, "high": hi[2], "high_t": hi[0], "low": lo[3],
            "low_t": lo[0], "fh": (c1030 / o - 1) * 100 if c1030 else None,
            "mid": (c1545 / c1100 - 1) * 100 if (c1100 and c1545) else None, "n": len(bars)}


def spikes(bars, k=0.03):
    """1m bars whose high or low sits more than k (fraction) away from both neighbours' closes: bad prints."""
    bad = []
    for i in range(1, len(bars) - 1):
        ref = (bars[i - 1][4] + bars[i + 1][4]) / 2
        if bars[i][2] > ref * (1 + k) or bars[i][3] < ref * (1 - k):
            bad.append(bars[i][0])
    return bad


def resample(bars, minutes=5):
    out = []
    cur = None
    for t, o, h, l, c, v in bars:
        key = t.replace(minute=t.minute - t.minute % minutes, second=0, microsecond=0)
        if cur is None or cur[0] != key:
            if cur:
                out.append(tuple(cur))
            cur = [key, o, h, l, c, v]
        else:
            cur[2] = max(cur[2], h)
            cur[3] = min(cur[3], l)
            cur[4] = c
            cur[5] += v
    if cur:
        out.append(tuple(cur))
    return out


CHART_H = 4.0   # inches: price panel over a volume panel (the operator, 2026-11-21: volume bars under every chart)

# ── chart ─────────────────────────────────────────────────────────────────────────────────────────
def chart(sym, bars, trades, day, minutes=5, vol_src=None):
    fig, (ax, axv) = plt.subplots(2, 1, figsize=(7.4, CHART_H), dpi=200, sharex=True,
                                  gridspec_kw={"height_ratios": [3.2, 1], "hspace": 0.04})
    b5 = resample(bars, minutes)
    w = minutes / 1440 * 0.72
    xs = [mdates.date2num(b[0]) for b in b5]
    for x, (t, o, h, l, c, v) in zip(xs, b5):
        col = CANDLE_UP if c >= o else CANDLE_DN
        ax.vlines(x + minutes / 2880, l, h, color=col, linewidth=0.7, zorder=2)
        ax.add_patch(plt.Rectangle((x + minutes / 2880 - w / 2, min(o, c)), w, max(abs(c - o), 1e-9),
                                   facecolor=col, edgecolor=col, linewidth=0.4, zorder=3))
        axv.bar(x + minutes / 2880, v, width=w, color=col, linewidth=0, zorder=3)
    vmax = max((b[5] for b in b5), default=0)
    if vmax <= 0:
        axv.text(0.5, 0.5, "no volume for an index", transform=axv.transAxes, ha="center", va="center",
                 fontsize=6.8, color=MUTED)
        axv.set_yticks([])
    else:
        axv.yaxis.set_major_formatter(plt.FuncFormatter(
            lambda y, _: f"{y/1e6:.1f}M" if y >= 1e6 else (f"{y/1e3:.0f}k" if y >= 1e3 else f"{y:.0f}")))
        axv.yaxis.set_major_locator(plt.MaxNLocator(3))
        axv.set_ylim(0, vmax * 1.08)
    axv.set_ylabel(f"{vol_src} vol ({minutes}m)" if vol_src else f"vol ({minutes}m)", fontsize=6.5, color=MUTED)
    axv.tick_params(axis="y", labelsize=6.3)
    d0 = dt.datetime.fromisoformat(day).replace(tzinfo=ET)
    used = set()
    for a, b, lab in ENTRY_WINDOWS:
        if not any(SHORT.get(r.get("strategy"), "") in lab for r in trades):
            continue
        ta = d0.replace(hour=int(a[:2]), minute=int(a[3:]))
        tb = d0.replace(hour=int(b[:2]), minute=int(b[3:]))
        ax.axvspan(mdates.date2num(ta), mdates.date2num(tb), color=ACCENT, alpha=0.06, zorder=0, linewidth=0)
        used.add(lab)
    lo = min(b[3] for b in bars)
    hi = max(b[2] for b in bars)
    span = hi - lo
    offs = [0.10, 0.20, 0.30, 0.15, 0.25]
    for i, r in enumerate(trades):
        tin, tout = r["_in"], r["_out"]
        if tin is None:
            continue
        uin = r.get("underlying_entry")
        uin = float(uin) if uin not in (None, "") else (bar_at(bars, tin) or [0, 0, 0, 0, 0])[4]
        bo = bar_at(bars, tout) if tout else None
        uout = bo[4] if bo else None
        win = (r["_pnl"] or 0) > 0
        col = WIN if win else LOSS
        bull = contract_label(r).split()[1].endswith("C") if len(contract_label(r).split()) > 1 else True
        xi = mdates.date2num(tin)
        axv.axvline(xi, color=col, linewidth=0.7, linestyle=":", zorder=4)
        ax.scatter([xi], [uin], marker="^" if bull else "v", s=46, color=col, edgecolor="white",
                   linewidth=0.9, zorder=6)
        if uout is not None:
            xo = mdates.date2num(tout)
            ax.plot([xi, xo], [uin, uout], color=col, linewidth=1.1, linestyle="--", zorder=5, alpha=0.9)
            ax.scatter([xo], [uout], marker="o" if win else "X", s=40, color=col, edgecolor="white",
                       linewidth=0.9, zorder=6)
        n = r["_n"]
        up = bull
        dy = span * offs[i % len(offs)]
        ty = uin + dy if up else uin - dy
        dx = (0.0 if len(trades) == 1 else (-1 if i % 2 == 0 else 1) * 7 / 1440)
        ax.annotate(f"#{n} {SHORT.get(r.get('strategy'), r.get('strategy'))}", xy=(xi, uin), xytext=(xi + dx, ty),
                    fontsize=6.8, color=INK, ha="center", va="bottom" if up else "top",
                    arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=0.5), zorder=7,
                    bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="none", alpha=0.85))
    ax.set_ylim(lo - span * 0.36, hi + span * 0.36)
    ch = 13 if market_calendar.is_half_day(d0.date()) else 16
    ax.set_xlim(mdates.date2num(d0.replace(hour=9, minute=28)), mdates.date2num(d0.replace(hour=ch, minute=2)))
    axv.xaxis.set_major_locator(mdates.HourLocator(tz=ET))
    axv.xaxis.set_minor_locator(mdates.MinuteLocator(byminute=[30], tz=ET))
    axv.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=ET))
    ax.tick_params(axis="x", labelbottom=False)
    ax.grid(True, axis="y", color=GRID, linewidth=0.5)
    for a_ in (ax, axv):
        a_.grid(True, axis="x", which="both", color=GRID, linewidth=0.4)
        for s in ("top", "right"):
            a_.spines[s].set_visible(False)
    ax.set_title(f"{sym}  ·  {day}  ·  {minutes}m candles, RTH (ET)  ·  markers at the underlying",
                 fontsize=8.5, color=INK, loc="left")
    # legend (identity never colour-only: shape + text)
    from matplotlib.lines import Line2D
    h = [Line2D([], [], marker="^", color="w", markerfacecolor=MUTED, markersize=7, label="entry, call"),
         Line2D([], [], marker="v", color="w", markerfacecolor=MUTED, markersize=7, label="entry, put"),
         Line2D([], [], marker="o", color="w", markerfacecolor=WIN, markersize=6, label="exit, win"),
         Line2D([], [], marker="X", color="w", markerfacecolor=LOSS, markersize=6, label="exit, loss")]
    if used:
        h.append(plt.Rectangle((0, 0), 1, 1, color=ACCENT, alpha=0.12, label="entry window(s): " + ", ".join(sorted(used))))
    ax.legend(handles=h, loc="upper right", fontsize=6.3, frameon=True, framealpha=0.9, edgecolor=GRID, ncol=3)
    fig.tight_layout(pad=0.4)
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf


# ── pdf ───────────────────────────────────────────────────────────────────────────────────────────
S = {
    "title": ParagraphStyle("title", fontName="DVB", fontSize=17, leading=21, textColor=INK, spaceAfter=4),
    "sub": ParagraphStyle("sub", fontName="DV", fontSize=9.5, leading=13, textColor=INK2, spaceAfter=8),
    "h1": ParagraphStyle("h1", fontName="DVB", fontSize=13.5, leading=17, textColor=INK, spaceBefore=6,
                         spaceAfter=6),
    "h2": ParagraphStyle("h2", fontName="DVB", fontSize=10.5, leading=13.5, textColor=INK, spaceBefore=6,
                         spaceAfter=3),
    "body": ParagraphStyle("body", fontName="DV", fontSize=8.6, leading=11.6, textColor=INK, spaceAfter=4,
                           alignment=TA_LEFT),
    "small": ParagraphStyle("small", fontName="DV", fontSize=7.2, leading=9.4, textColor=INK2, spaceAfter=2),
    "cell": ParagraphStyle("cell", fontName="DV", fontSize=7.0, leading=8.6, textColor=INK),
    "cellb": ParagraphStyle("cellb", fontName="DVB", fontSize=7.0, leading=8.6, textColor=INK),
    "lab": ParagraphStyle("lab", fontName="DVB", fontSize=8.6, leading=11.6, textColor=INK),
}


def P(t, st="body"):
    return Paragraph(esc(t), S[st])


def table(data, widths, header=True, bold_last=False, align_right=()):
    rows = []
    for i, row in enumerate(data):
        st = "cellb" if (header and i == 0) or (bold_last and i == len(data) - 1) else "cell"
        rows.append([Paragraph(esc(c), S[st]) if not isinstance(c, Paragraph) else c for c in row])
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    sty = [("VALIGN", (0, 0), (-1, -1), "TOP"),
           ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor(INK2)),
           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f3f0")]),
           ("TOPPADDING", (0, 0), (-1, -1), 1.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6),
           ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]
    if bold_last:
        sty.append(("LINEABOVE", (0, -1), (-1, -1), 0.6, colors.HexColor(INK2)))
    t.setStyle(TableStyle(sty))
    return t


def trade_table(trades):
    hdr = ["#", "Strategy", "Side / contract", "Qty", "Entry (ET) @ mark", "Exit (ET) @ mark", "Exit reason",
           "P&L (mark)", "Fees", "Net"]
    data = [hdr]
    for r in trades:
        fee = r["_fee"]
        reason = str(r.get("exit_reason") or "")
        if len(reason) > 70:
            reason = reason[:68] + "…"
        data.append([str(r["_n"]), SHORT.get(r.get("strategy"), r.get("strategy")), contract_label(r),
                     str(r.get("contracts")),
                     f"{r['_in']:%H:%M:%S} @ {float(r['entry_premium']):.3f}".rstrip("0").rstrip("."),
                     (f"{r['_out']:%H:%M:%S} @ {float(r['exit_premium']):.3f}".rstrip("0").rstrip(".")
                      if r["_out"] else "open"),
                     reason, money(r["_pnl"]), money(fee, sign=False),
                     money(r["_pnl"] - fee if fee is not None else None)])
    if len(trades) > 1:
        p = sum(r["_pnl"] for r in trades)
        f = sum(r["_fee"] or 0 for r in trades)
        data.append(["", "Symbol total", "", str(sum(int(r.get("contracts") or 0) for r in trades)), "", "", "",
                     money(p), money(f, sign=False), money(p - f)])
    w = [0.2, 0.6, 0.92, 0.28, 0.8, 0.8, 1.62, 0.76, 0.5, 0.76]
    return table(data, [x * inch for x in w], bold_last=len(trades) > 1)


def compute(day):
    """The data pass, shared by the PDF and --facts (v1.1): one place computes every figure both print."""
    every, tmeta, dropped = load_day_trades(day)
    trades = [r for r in every if r.get("_book", RK.HEADLINE) == RK.HEADLINE]   # v1.4: as cash would have traded
    after_cap = [r for r in every if r.get("_book") == RK.AFTER_CAP]
    paper_on_cash = [r for r in every if r.get("_book") == RK.PAPER_ON_CASH]
    by_sym = defaultdict(list)
    for r in trades:
        by_sym[r["symbol"]].append(r)
    for sym, rs in by_sym.items():
        for i, r in enumerate(rs, 1):
            r["_n"] = i
    sym_pnl = {s: sum(r["_pnl"] for r in rs) for s, rs in by_sym.items()}
    order = [s for s in INDEX_FIRST if s in by_sym] + sorted(
        [s for s in by_sym if s not in INDEX_FIRST], key=lambda s: -abs(sym_pnl[s]))
    bars, binfo = load_bars(day, order + ["VIX"])
    proxied = {}
    for _sym, _px in VOL_PROXY.items():
        if bars.get(_sym) and not any(b[5] for b in bars[_sym]):
            _pv = load_proxy_volume(day, _px)
            if _pv:
                bars[_sym] = [(t, o, h, l, c, _pv.get(t.replace(second=0, microsecond=0), 0.0))
                              for t, o, h, l, c, _v in bars[_sym]]
                proxied[_sym] = _px
    vix = tape_stats(bars.get("VIX") or [])

    tot_p = sum(r["_pnl"] for r in trades)
    tot_f = sum(r["_fee"] or 0 for r in trades)
    unpriced = [r["trade_id"] for r in trades if r["_fee"] is None]
    nwin = sum(1 for r in trades if r["_pnl"] > 0)

    # cash re-scale
    cash_rows = []
    for r in trades:
        if r["symbol"] not in CASH_BUDGET or r.get("strategy") not in CASH_STRATEGIES:
            continue
        budget = cash_budget(r["symbol"], day)
        prem = float(r["entry_premium"])
        n_cash = int(math.floor(budget / (prem * 100) + 1e-9))
        n_paper = int(r.get("contracts") or 0)
        per = r["_pnl"] / n_paper if n_paper else 0.0
        p_cash = per * n_cash
        f_cash = fee_of(r, n_cash) if n_cash > 0 else 0.0
        cash_rows.append((r, budget, prem, n_paper, n_cash, per, p_cash, f_cash))
    return {"trades": trades, "tmeta": tmeta, "dropped": dropped, "by_sym": by_sym, "sym_pnl": sym_pnl,
            "order": order, "bars": bars, "binfo": binfo, "proxied": proxied, "vix": vix, "tot_p": tot_p,
            "tot_f": tot_f, "unpriced": unpriced, "nwin": nwin, "cash_rows": cash_rows,
            "after_cap": after_cap, "paper_on_cash": paper_on_cash, "would_pop": would_pop(day)}


def would_pop(day):
    """v1.4: the day's would-pop records ([{sym, event_time, notes}]) from ~/reviews/breaker/DAY.csv, or None when
    the nightly review's `trades` did not write the file (NOT READ, never "none")."""
    try:
        rows = RK.read_breaker(day)
    except Exception:                                           # noqa: BLE001
        return None
    if rows is None:
        return None
    return [{"sym": r.get("sym"), "event_time": r.get("event_time"), "notes": r.get("notes")}
            for r in rows if r.get("reason") == RK.WOULD_POP]


def _extra(rs):
    return {"n": len(rs), "pnl_mark_usd": round(sum(r["_pnl"] or 0 for r in rs), 2),
            "fees_usd": round(sum(r["_fee"] or 0 for r in rs), 2), "trade_ids": [r.get("trade_id") for r in rs]}


def extras_lines(c):
    """v1.4: the section-1 lines beside the day totals (each only when it has something)."""
    out = []
    xa, wp = c.get("after_cap") or [], c.get("would_pop")
    if xa or wp:
        e = _extra(xa)
        pops = "; ".join("%s: %s" % (w["sym"], w["notes"]) for w in (wp or []))
        out.append("Extra paper after the breaker (paper boxes trade on past the would-be catastrophic cap; NOT in "
                   "the figures above, which are as cash would have traded): %d trade(s), %s at the mark, fees %s "
                   "beside.%s" % (e["n"], money(e["pnl_mark_usd"]), money(e["fees_usd"], sign=False),
                                  (" Would-pop record(s): " + pops + ".") if pops else ""))
    po = c.get("paper_on_cash") or []
    if po:
        e = _extra(po)
        out.append("Paper rows on a cash box (OGAP's own evaluation, never in the cash figures above): %d trade(s), %s "
                   "at the mark, fees %s beside (%s)." % (e["n"], money(e["pnl_mark_usd"]),
                                                          money(e["fees_usd"], sign=False),
                                                          ", ".join(sorted({"%s %s" % (r.get("symbol"), SHORT.get(
                                                              r.get("strategy"), r.get("strategy"))) for r in po}))))
    return out


def _jt(t):
    return t.strftime("%H:%M:%S") if t else None


def facts(day):
    """-> a JSON-ready dict of the data pass (v1.1, --facts): what the recap session quotes."""
    c = compute(day)
    keep = ("trade_id", "symbol", "strategy", "direction", "contracts", "entry_premium", "exit_premium",
            "entry_bid", "entry_ask", "mfe_premium", "underlying_entry", "exit_reason", "strike", "option_type",
            "expiration", "entry_time", "exit_time")
    rows = []
    for r in c["trades"]:
        d = {k: r.get(k) for k in keep if k in r}
        d.update({"n_on_symbol": r.get("_n"), "in_et": _jt(r["_in"]), "out_et": _jt(r["_out"]),
                  "pnl_mark_usd": r["_pnl"], "fee_usd": r["_fee"], "contract": contract_label(r)})
        rows.append(d)
    tape = {}
    for s in c["order"] + ["VIX"]:
        t = tape_stats(c["bars"].get(s) or [])
        if t:
            t = dict(t, high_t=_jt(t["high_t"]), low_t=_jt(t["low_t"]))
            t["bad_prints"] = [f"{x:%H:%M}" for x in spikes(c["bars"].get(s) or [])]
        tape[s] = t
    by_strat = defaultdict(lambda: {"n": 0, "pnl": 0.0, "fees": 0.0, "wins": 0})
    for r in c["trades"]:
        k = SHORT.get(r.get("strategy"), r.get("strategy"))
        by_strat[k]["n"] += 1
        by_strat[k]["pnl"] += r["_pnl"]
        by_strat[k]["fees"] += r["_fee"] or 0
        by_strat[k]["wins"] += r["_pnl"] > 0
    return {"day": day, "half_day": market_calendar.is_half_day(dt.date.fromisoformat(day)),
            "basis": "pnl_usd at the mark (the ladder's fill, mark or better); fees beside, never in it",
            "trades_n": len(c["trades"]), "wins": c["nwin"], "pnl_mark_usd": round(c["tot_p"], 2),
            "fees_usd": round(c["tot_f"], 2), "unpriced_fee_trades": c["unpriced"],
            "otv4test_dropped": dict(c["dropped"]) if c["dropped"] else {},
            "warehouse": {"listed": c["tmeta"].listed, "read": c["tmeta"].read, "bad": c["tmeta"].bad},
            "by_strategy": {k: {kk: round(vv, 2) if isinstance(vv, float) else vv for kk, vv in v.items()}
                            for k, v in by_strat.items()},
            "by_symbol": {s: {"n": len(c["by_sym"][s]), "pnl": round(c["sym_pnl"][s], 2),
                              "fees": round(sum(r["_fee"] or 0 for r in c["by_sym"][s]), 2)} for s in c["order"]},
            "tape": tape, "bars": {s: v["bars"] for s, v in c["binfo"].items()}, "volume_proxy": c["proxied"],
            "trades": rows,
            "as_cash": "every figure above is as cash would have traded: after_cap trades (paper past the would-be "
                       "catastrophic cap) and a cash box's paper rows are beside, never inside (OTV5 r151, dtp r578)",
            "after_cap": _extra(c["after_cap"]), "paper_on_cash": _extra(c["paper_on_cash"]),
            "would_pop": c["would_pop"],
            "cash": [{"symbol": x[0]["symbol"], "strategy": SHORT.get(x[0]["strategy"]), "budget": x[1],
                      "entry_mark": x[2], "paper_qty": x[3], "cash_qty": x[4], "pnl_per_contract": round(x[5], 2),
                      "cash_pnl": round(x[6], 2), "cash_fees": round(x[7], 2)} for x in c["cash_rows"]]}


PARA_KEYS = ("headline", "day_note", "section1_close", "studies_intro", "study_recs", "proposals_intro", "code_intro",
             "cash_verdict", "cash_books", "runaway_watch", "sources")
HALF_DAY_LINE = ("HALF DAY — a non-trading day. The market closed at 13:00 ET, and by the operator's ruling (2026-11-22: "
                 "\"Yes, just treat them as bank holidays. No trading.\") the bots open nothing (OTV5 r145); the boxes "
                 "woke and recorded data only. Zero trades is expected, never a defect.")


def normalize_notes(notes):
    """v1.1: a paragraph list given as one string is one paragraph (the first recap session wrote "headline": "..."
    and v1.0 iterated it letter by letter: 103 pages); the same for each study's and code item's "detail"."""
    notes = dict(notes or {})
    for k in PARA_KEYS:
        if isinstance(notes.get(k), str):
            notes[k] = [notes[k]]
    for k in ("studies", "code"):
        for it in notes.get(k) or []:
            if isinstance(it, dict) and isinstance(it.get("detail"), str):
                it["detail"] = [it["detail"]]
    return notes


def cash_books_rows(day, trades_dir=None):
    """v1.2 -> [str | table rows] for section 5b: the scorer's own numbers, never recomputed here."""
    try:
        sys.path.insert(0, os.path.join(DTP_ROOT, "tools"))
        import cash_books as CB                          # noqa: E402  (stdlib + market_calendar only)
        sc = CB.score(day, day=day, trades_dir=trades_dir or CB.TRADES)
    except Exception as e:                               # noqa: BLE001
        return ["C1-C4: NOT MEASURED (%s: %s)." % (type(e).__name__, e)]
    W = sc["windows"]
    fw = W.get("forward")
    fwc = W.get("forward_cumulative") or fw
    cb = W["combined"]

    def ev(m):
        if m["ev"] is None:
            return "-"
        ci = m.get("ci")
        return money(m["ev"], dec=0) + (" [%s, %s]" % (money(ci[0], dec=0), money(ci[1], dec=0)) if ci else "")
    data = [["Book", "Day n / net", "Fwd n", "Fwd gross", "Fwd fees", "Fwd net", "Fwd EV [95%]",
             "Fwd ex top-2 / ex bottom-2",
             "Beside H/O", "Comb. net"]]
    for b, _d in CB.BOOKS:
        if b not in sc["books"]:                         # v1.7: the books the scorer scored
            continue
        dm, cm = W["day"]["books"].get(b), cb["books"][b]
        src = W.get("forward_c5") if b == "C5" else fwc  # v1.7: C5's own forward window, never C1-C4's
        f = (src or {}).get("books", {}).get(b) if src else None
        data.append([b, "%d / %s" % (dm["n"], money(dm["net"], dec=0)) if dm else "-",
                     str(f["n"]) if f else "-", money(f["gross"], dec=0) if f else "-",
                     money(f["fees"], sign=False, dec=0) if f else "-", money(f["net"], dec=0) if f else "-",
                     ev(f) if f else "-",
                     ("%s / %s" % (money(f["gross_ex_top2"], dec=0), money(f["gross_ex_bottom2"], dec=0))) if f else "-",
                     str(f.get("displaced", "-")) if f else "-",
                     "%s (n %d, EV %s)" % (money(cm["net"], dec=0), cm["n"], ev(cm))])
    head = ("Frozen in PREREG (%s, sealed 2026-11-21): " % os.path.basename(sc["prereg"])
            + "; ".join("%s %s" % (b, d) for b, d in CB.BOOKS if b in CB.PREREG_BOOKS) + ". At the mark, fees beside, never inside EV. "
            "Forward %s..%s (%d of 8 sessions so far)" % (fwc["from"], fwc["to"], fwc["sessions"]) if fwc else
            "Frozen in PREREG (sealed 2026-11-21). The forward window starts 2026-11-23; until then only the in-sample "
            "(hindsight) figures exist")
    if sc.get("c5"):                                     # v1.7 (CASHBOOK.3)
        c5 = sc["c5"]
        head += (". C5 is frozen in its own PREREG (%s, sealed 2026-11-24 before the open%s): %s %s. Its equity list "
                 "was chosen in hindsight: its Comb. net is reference only, never evidence; its Fwd columns are its own "
                 "forward window from %s (%s), apart from C1-C4's" % (
                     os.path.basename(os.path.dirname(c5["prereg"])), "" if c5["sealed"] else "; SEAL BROKEN",
                     "C5", dict(CB.BOOKS)["C5"], c5["forward_from"],
                     ("%d session(s) so far" % W["forward_c5"]["sessions"]) if W.get("forward_c5") else "none yet"))
    note = ("'Ex top-2 / ex bottom-2': " + CB.CONCENTRATION + ". "
            + ("Amendment: " + sc["amendment"] + " " if sc.get("amendment") else "") +
            "'Beside H/O' counts the forward trades that fired while a Hunt or OGAP position was open on the same box; "
            "a fire that position kept from trading is not in the trade files (NOT MEASURED). Report only: never in "
            "the window EV or the theories; the choice of book is the operator's.")
    return [head + ".", data, note]


def runaway_watch_score(day, trades_dir=None):
    """v1.3 -> the scorer's dict, or (None, reason)."""
    try:
        sys.path.insert(0, os.path.join(DTP_ROOT, "tools"))
        import runaway_watch as RW                       # noqa: E402  (stdlib + market_calendar + review_kit only)
        return RW, RW.score(day, trades_dir=trades_dir or RW.TRADES), None
    except Exception as e:                               # noqa: BLE001
        return None, None, "%s: %s" % (type(e).__name__, e)


def schedule(now=None):
    """v1.5 -> (tools/calendar_view.build's dict, None) or (None, reason)."""
    try:
        sys.path.insert(0, os.path.join(DTP_ROOT, "tools"))
        import calendar_view as CV                       # noqa: E402  (stdlib + market_calendar only)
        return CV.build(now), None
    except Exception as e:                               # noqa: BLE001
        return None, "%s: %s" % (type(e).__name__, e)


RECS_DEFAULT = os.path.expanduser("~/reviews/schedule/recommendations.tsv")


def recommendations(day, ledger=None, now=None):
    """v1.8 -> (tools/daily_recap.rec_section's dict, None) or (None, reason). Read only."""
    try:
        sys.path.insert(0, os.path.join(DTP_ROOT, "tools"))
        import daily_recap as DR                         # noqa: E402  (stdlib + dtp modules only)
        import calendar_view as CV                       # noqa: E402
        try:
            cal, cerr = CV.build(now, 7), None
        except Exception as e:                           # noqa: BLE001 - the table still prints, slots say NOT READ
            cal, cerr = None, "%s: %s" % (type(e).__name__, e)
        return DR.rec_section(day, ledger or RECS_DEFAULT, cal, cerr, now), None
    except Exception as e:                               # noqa: BLE001
        return None, "%s: %s" % (type(e).__name__, e)


def watch_chart(RW, sc):
    """v1.3: one small trend line per equity, cumulative net by Runaway trade, the forward marker dashed."""
    eq = list(sc["equities"].items())
    cols = 4
    rows_ = max(1, math.ceil(len(eq) / cols))
    fig, axes = plt.subplots(rows_, cols, figsize=(7.4, 1.05 * rows_ + 0.2), dpi=200, squeeze=False)
    for k, ax in enumerate(axes.flat):
        if k >= len(eq):
            ax.axis("off")
            continue
        sym, e = eq[k]
        ys = [0.0] + list(e["cum"])
        xs = list(range(len(ys)))
        col = LOSS if (e["net"] or 0) < 0 else WIN
        ax.axhline(0, color=GRID, linewidth=0.6, zorder=1)
        if e["forward_index"] is not None:
            ax.axvline(e["forward_index"] + 0.5, color=ACCENT, linewidth=0.7, linestyle="--", zorder=2)
        ax.plot(xs, ys, color=col, linewidth=1.1, zorder=3)
        if len(ys) > 1:
            ax.scatter([xs[-1]], [ys[-1]], s=8, color=col, zorder=4)
        d = e["direction"]
        tag = " · watch" if e.get("watch") else ""
        ax.set_title("%s %s n %d · %s%s" % (sym, d["arrow"] if d["word"] != "n/a" else "", e["n"], money(e["net"], dec=0),
                                           tag), fontsize=6.4, color=INK, loc="left",
                     fontweight="bold" if e.get("watch") else "normal")
        ax.tick_params(labelsize=5.2, length=2)
        ax.set_xticks([])
        ax.yaxis.set_major_locator(plt.MaxNLocator(3))
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y/1e3:.1f}k" if abs(y) >= 1e3 else f"{y:.0f}"))
        for s_ in ("top", "right"):
            ax.spines[s_].set_visible(False)
    fig.tight_layout(pad=0.3, h_pad=0.6, w_pad=0.6)
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf, 1.05 * rows_ + 0.2


def build(day, notes, out_dir, recs=None):
    c = compute(day)
    trades, tmeta, dropped, by_sym = c["trades"], c["tmeta"], c["dropped"], c["by_sym"]
    sym_pnl, order, bars, binfo, proxied, vix = (c["sym_pnl"], c["order"], c["bars"], c["binfo"], c["proxied"],
                                                 c["vix"])
    tot_p, tot_f, unpriced, nwin, cash_rows = c["tot_p"], c["tot_f"], c["unpriced"], c["nwin"], c["cash_rows"]

    notes = normalize_notes(notes)
    snotes = notes.get("symbols", {})
    rev = notes.get("revision", "")

    path = os.path.join(out_dir, f"daily_brief_{day}.pdf")
    os.makedirs(out_dir, exist_ok=True)
    sources = notes.get("sources") or []

    pages = [0]

    def on_page(c, d):
        pages[0] = d.page
        c.saveState()
        c.setFont("DV", 6.6)
        c.setFillColor(colors.HexColor(MUTED))
        c.drawString(0.55 * inch, 0.36 * inch,
                     f"OTV5 daily brief {day} · paper, P&L at the mark, fees beside · sources: S3 warehouse, "
                     f"OTV5 fees.py, ~/reviews (list on the last page)")
        c.drawRightString(letter[0] - 0.55 * inch, 0.36 * inch, f"page {d.page}")
        c.restoreState()

    doc = SimpleDocTemplate(path, pagesize=letter, leftMargin=0.55 * inch, rightMargin=0.55 * inch,
                            topMargin=0.55 * inch, bottomMargin=0.6 * inch,
                            title=f"OTV5 daily brief {day}", author="OTV5 control (read-only)")
    st = []
    wd = dt.date.fromisoformat(day).strftime("%A")
    st.append(P(f"OTV5 daily brief — {wd} {day}", "title"))
    by_strat = defaultdict(lambda: [0, 0.0, 0.0, 0])
    for r in trades:
        k = SHORT.get(r.get("strategy"), r.get("strategy"))
        by_strat[k][0] += 1
        by_strat[k][1] += r["_pnl"]
        by_strat[k][2] += r["_fee"] or 0
        by_strat[k][3] += r["_pnl"] > 0
    cash_p = sum(x[6] for x in cash_rows)
    cash_f = sum(x[7] for x in cash_rows)
    st.append(P(f"{rev}  ·  {len(trades)} trades on {len(by_sym)} symbols  ·  paper day **{money(tot_p)}** at the "
                f"mark, fees {money(tot_f, sign=False)} beside (net {money(tot_p - tot_f)})  ·  "
                f"if cash (QQQ/SPX only): **{money(cash_p)}**, fees {money(cash_f, sign=False)} beside", "sub"))
    half_day = market_calendar.is_half_day(dt.date.fromisoformat(day))
    if half_day:                                          # v1.3: the operator's ruling, stated plainly
        st.append(P("**" + HALF_DAY_LINE + "**"))
        if trades:
            st.append(P(f"**DEFECT: {len(trades)} trade(s) on a half day** (OTV5 r145 / HALF.1 should have refused every "
                        f"opening): " + ", ".join(f"{r.get('symbol')} {SHORT.get(r.get('strategy'), r.get('strategy'))}"
                                                  for r in trades) + "."))
    if notes.get("headline"):
        for h in notes["headline"]:
            st.append(P(h))
    # day totals table
    data = [["Strategy", "Trades", "Wins", "P&L at the mark", "Fees (beside)", "Net after fees"]]
    for k in ("PARK", "Runaway", "Hunt", "OGAP"):
        if k in by_strat:
            n, p, f, w = by_strat[k]
            data.append([k + (" (own line, not in the benchmark)" if k == "OGAP" else ""), str(n), str(w),
                         money(p), money(f, sign=False), money(p - f)])
    for k, (n, p, f, w) in by_strat.items():
        if k not in ("PARK", "Runaway", "Hunt", "OGAP"):
            data.append([k, str(n), str(w), money(p), money(f, sign=False), money(p - f)])
    data.append(["Day total", str(len(trades)), str(nwin), money(tot_p), money(tot_f, sign=False),
                 money(tot_p - tot_f)])
    st.append(table(data, [x * inch for x in (2.6, 0.6, 0.55, 1.2, 1.1, 1.2)], bold_last=True))
    if any(k == "OGAP" for k in by_strat):
        n, p, f, w = by_strat["OGAP"]
        st.append(P(f"Benchmark setups only (PARK, Runaway, Hunt): {money(tot_p - p)} on {len(trades) - n} trades, "
                    f"fees {money(tot_f - f, sign=False)} beside.", "small"))
    for _ln in extras_lines(c):                          # v1.4 (CAP.11): beside the as-cash totals, never inside
        st.append(P(_ln, "small"))
    if unpriced:
        st.append(P(f"Fee model could not price {len(unpriced)} trade(s): {', '.join(map(str, unpriced))}.", "small"))
    # by symbol summary
    data = [["Symbol", "Trades", "P&L at the mark", "Fees", "Net", "Open → close", "Day range"]]
    for s in order:
        ts_ = tape_stats(bars.get(s) or [])
        f = sum(r["_fee"] or 0 for r in by_sym[s])
        data.append([s, str(len(by_sym[s])), money(sym_pnl[s]), money(f, sign=False), money(sym_pnl[s] - f),
                     pct(ts_["oc"]) if ts_ else "no bars",
                     f"{ts_['low']:,.2f} – {ts_['high']:,.2f}" if ts_ else "no bars"])
    data.append(["Total", str(len(trades)), money(tot_p), money(tot_f, sign=False), money(tot_p - tot_f), "", ""])
    st.append(Spacer(1, 4))
    st.append(table(data, [x * inch for x in (0.8, 0.6, 1.15, 0.8, 1.0, 1.0, 1.6)], bold_last=True))
    if vix:
        st.append(P(f"VIX (1m, S3): open {vix['open']:.2f}, high {vix['high']:.2f} at {vix['high_t']:%H:%M}, "
                    f"low {vix['low']:.2f} at {vix['low_t']:%H:%M}, last RTH bar {vix['close']:.2f}.", "small"))
    if notes.get("day_note"):
        st.append(Spacer(1, 4))
        for h in notes["day_note"]:
            st.append(P(h))

    # ── Section 1 ──
    st.append(PageBreak())
    st.append(P("1. Trading", "h1"))
    st.append(P("Each chart: 5-minute candles built from the warehouse 1m bars (RTH). Entry markers sit at the row's "
                "underlying_entry; exit markers at the close of the 1m bar holding the exit time (the rows carry no "
                "underlying at exit). Green = the trade made money, red = it lost; the dashed line links entry to exit. "
                "Trade numbers match the table below each chart.", "small"))
    gaps = []
    for s in order:
        block = [P(f"{s}  ·  {len(by_sym[s])} trade(s)  ·  {money(sym_pnl[s])} at the mark", "h2")]
        if bars.get(s):
            block.append(Image(chart(s, bars[s], by_sym[s], day, vol_src=proxied.get(s)), width=7.4 * inch, height=CHART_H * inch))
            sp = spikes(bars[s])
            if sp:
                block.append(P(f"Possible bad prints (a bar 3% off both neighbours): {', '.join(f'{t:%H:%M}' for t in sp)}.",
                               "small"))
        else:
            gaps.append(s)
            block.append(P(f"No 1m bars in S3 for {s} on {day} (raw/candles/dt={day}/sym={s}/interval=1m/: "
                           f"{binfo.get(s, {}).get('objects', 0)} objects). Chart omitted.", "small"))
        block.append(Spacer(1, 3))
        block.append(trade_table(by_sym[s]))
        st.append(KeepTogether(block))
        ts_ = tape_stats(bars.get(s) or [])
        sn = snotes.get(s, {})
        auto_tape = (f"Open {ts_['open']:,.2f}, close {ts_['close']:,.2f} ({pct(ts_['oc'])}); high {ts_['high']:,.2f} at "
                     f"{ts_['high_t']:%H:%M}, low {ts_['low']:,.2f} at {ts_['low_t']:%H:%M}; first hour "
                     f"{pct(ts_['fh'])}, 11:00→15:45 {pct(ts_['mid'])}.") if ts_ else "No bars."
        parts = [("Tape", sn.get("tape") or auto_tape),
                 ("Our bots", sn.get("bots") or "; ".join(
                     f"#{r['_n']} {SHORT.get(r.get('strategy'))} {contract_label(r)} {money(r['_pnl'])}" for r in by_sym[s])),
                 ("Went well", sn.get("well") or "no notes supplied"),
                 ("Could have been better", sn.get("better") or "no notes supplied")]
        if sn.get("tape"):
            st.append(P(auto_tape, "small"))
        for lab, txt in parts:
            st.append(Paragraph(f"<b>{esc(lab)}.</b> {esc(txt)}", S["body"]))
        st.append(Spacer(1, 8))
    st.append(P("Day totals", "h2"))
    st.append(P(f"{len(trades)} trades, {nwin} winners: **{money(tot_p)}** at the mark; fees "
                f"{money(tot_f, sign=False)} beside; net {money(tot_p - tot_f)}. The symbol totals above add to this "
                f"figure: " + " ".join(f"{s} {money(sym_pnl[s])}" for s in order) + "."))
    for h in notes.get("section1_close", []):
        st.append(P(h))

    # ── Section 2 ──
    st.append(PageBreak())
    st.append(P("2. Study results", "h1"))
    for h in notes.get("studies_intro", []):
        st.append(P(h))
    if notes.get("studies"):
        data = [["Study", "Verdict", "Result (at the mark, fees beside)"]]
        for s_ in notes["studies"]:
            data.append([s_["title"], s_["verdict"], s_["result"]])
        st.append(table(data, [x * inch for x in (1.9, 0.95, 4.55)]))
        for s_ in notes["studies"]:
            if s_.get("detail"):
                st.append(P(s_["title"], "h2"))
                for h in s_["detail"]:
                    st.append(P(h))
    else:
        st.append(P("No study notes supplied for this day."))
    if notes.get("study_recs"):
        st.append(P("Recommendations from the studies", "h2"))
        for i, h in enumerate(notes["study_recs"], 1):
            st.append(P(f"{i}. {h}"))

    # ── Section 3 ──
    st.append(PageBreak())
    st.append(P("3. Proposed new studies to improve P&L", "h1"))
    for h in notes.get("proposals_intro", []):
        st.append(P(h))
    for i, pr in enumerate(notes.get("proposals", []), 1):
        qid = f" — queued as {pr['ws_id']}" if pr.get("ws_id") else ""
        blk = [P(f"P{i}. {pr['title']}{qid}", "h2")]
        for lab, key in (("Hypothesis", "hypothesis"), (f"What {day[5:]} showed", "evidence"), ("Data", "data"),
                         ("Blind test", "blind"), ("What it would change", "change")):
            if pr.get(key):
                blk.append(Paragraph(f"<b>{lab}.</b> {esc(pr[key])}", S["body"]))
        st.append(KeepTogether(blk))
    if not notes.get("proposals"):
        st.append(P("No study is proposed from a half day: it is a non-trading day (the operator's ruling)."
                    if half_day else "No proposals supplied for this day."))

    # ── Section 4 ──
    st.append(PageBreak())
    st.append(P("4. Code performance", "h1"))
    for h in notes.get("code_intro", []):
        st.append(P(h))
    if notes.get("code"):
        data = [["Item", "When / where", "Effect on the day", "Status"]]
        for c in notes["code"]:
            data.append([c["title"], c["when"], c["effect"], c["status"]])
        st.append(table(data, [x * inch for x in (2.0, 1.45, 2.65, 1.3)]))
        for c in notes["code"]:
            if c.get("detail"):
                st.append(P(c["title"], "h2"))
                for h in c["detail"]:
                    st.append(P(h))
    else:
        st.append(P("No code notes supplied for this day."))
    if gaps:
        st.append(P("Data gaps: no 1m bars for " + ", ".join(gaps) + ".", "small"))

    # ── Section 5 ──
    st.append(PageBreak())
    st.append(P("5. If this had been cash", "h1"))
    st.append(P(f"Sizing assumption: only QQQ and SPX trade cash, strategies PARK, Runaway, Hunt and OGAP. Each "
                f"{day} QQQ/SPX trade is re-sized to contracts = floor(budget ÷ (entry mark × 100)) at "
                f"the operator's per-entry budgets, QQQ {money(cash_budget('QQQ', day), sign=False, dec=0)} and SPX "
                f"{money(cash_budget('SPX', day), sign=False, dec=0)}. That is the bot's budget rule "
                f"(risk_manager._size_budget, SIZE_ON_RISK off, grade multiplier 1.0) and OGAP's own rule "
                f"(floor(RISK_PER_TRADE_USD ÷ (mark × 100)), r131/r136); Runaway, Hunt, PARK and OGAP size on "
                f"OT_RISK_USD alone (Saturday brief 11-21, R5: the ramp top sizes nothing live). "
                f"A trade whose one contract costs more than its budget is refused. P&L scales per contract at "
                f"the same entry and exit marks; fees are re-run through the fee model at the new count.", "small"))
    data = [["Sym", "Strategy", "Contract", "Entry mark", "Budget", "Paper qty", "Cash qty", "P&L / contract",
             "Cash P&L (mark)", "Fees", "Net"]]
    for (r, budget, prem, n_paper, n_cash, per, p_cash, f_cash) in cash_rows:
        data.append([r["symbol"], SHORT.get(r.get("strategy")), contract_label(r), f"{prem:.2f}",
                     money(budget, sign=False, dec=0), str(n_paper), str(n_cash) if n_cash else "0 (refused)",
                     money(per), money(p_cash), money(f_cash, sign=False), money(p_cash - f_cash)])
    data.append(["Total", "", "", "", "", str(sum(x[3] for x in cash_rows)), str(sum(x[4] for x in cash_rows)), "",
                 money(cash_p), money(cash_f, sign=False), money(cash_p - cash_f)])
    st.append(table(data, [x * inch for x in (0.38, 0.6, 1.05, 0.55, 0.55, 0.52, 0.62, 0.72, 0.82, 0.5, 0.65)],
                    bold_last=True))
    paper_idx = sum(x[0]["_pnl"] for x in cash_rows)
    st.append(P(f"Paper P&L on the same {len(cash_rows)} trades: {money(paper_idx)} (the paper boxes already size "
                f"close to these budgets). The other {len(trades) - len(cash_rows)} trades ({money(tot_p - paper_idx)} "
                f"on paper) are on equity boxes that do not trade cash.", "small"))
    for h in notes.get("cash_verdict", []):
        st.append(P(h))

    # ── Section 5b (v1.2): the cash candidate books C1-C4 (v1.7: and C5), scored by tools/cash_books.py ──
    st.append(Spacer(1, 8))
    st.append(P("5b. The cash candidate books C1-C4 and C5", "h1"))
    for row in cash_books_rows(day):
        if isinstance(row, str):
            st.append(P(row, "small"))
        else:
            st.append(table(row, [x * inch for x in (0.35, 0.7, 0.4, 0.7, 0.55, 0.65, 1.15, 0.65, 0.5, 1.45)]))
    for h in notes.get("cash_books", []):
        st.append(P(h))
    if notes.get("cash_books_withheld"):
        st.append(P("Commentary withheld by the recap's validator: " + notes["cash_books_withheld"] + ".", "small"))
    elif not notes.get("cash_books"):
        st.append(P("No commentary supplied for this day.", "small"))

    # ── Section 5c (v1.3): the Runaway equity watch, scored by tools/runaway_watch.py ──
    st.append(Spacer(1, 8))
    st.append(P("5c. The Runaway equity watch", "h1"))
    RW, wsc, werr = runaway_watch_score(day)
    if wsc is None:
        st.append(P(f"Runaway watch: NOT MEASURED ({werr}).", "small"))
    else:
        st.append(P(f"Frozen in {wsc['watch']} (sealed 2026-11-22, before any forward data): on notice "
                    f"{', '.join(wsc['watch_list'])}. A watch-list symbol is RECOMMENDED for cutting from Runaway when "
                    f"its Runaway trades from {wsc['forward_start']} on number at least {wsc['cut_min_n']} and their "
                    f"net EV a trade (at the mark, after fees) is below zero; at {wsc['cut_min_n']}+ with EV at or above "
                    f"zero it comes off the list. Past trades never count. Any cut needs the operator's yes. "
                    f"Forward sessions so far: {len(wsc['forward_sessions'])} (half days are not sessions).", "small"))
        data = [["Symbol", "Fwd n", "Fwd net", "Fwd EV / trade", "Against the bar", "Status"]]
        for s_, n_, net_, ev_, bar_, stt in RW.watch_rows(wsc):
            data.append([s_, str(n_), money(net_, dec=0) if n_ else "-", money(ev_, dec=0) if ev_ is not None else "-",
                         bar_, stt])
        st.append(table(data, [x * inch for x in (0.7, 0.55, 0.85, 1.0, 2.6, 1.3)]))
        img, h_in = watch_chart(RW, wsc)
        st.append(Spacer(1, 3))
        st.append(Image(img, width=7.4 * inch, height=h_in * inch))
        st.append(P("Each line: the equity's cumulative net P&L (after fees, at the mark) by Runaway trade since "
                    "2026-10-26; the dashed line is the 2026-11-23 forward marker; red ends below zero, green above; "
                    "the arrow is the DIRECTION (the last 8 trades' net EV a trade against the earlier ones').", "small"))
        data = [["Symbol", "n", "Net", "Net EV / trade", "Direction (last 8 vs earlier, n beside)", "Watch"]]
        for s_, e in wsc["equities"].items():
            data.append([s_, str(e["n"]), money(e["net"], dec=0), money(e["ev_net"], dec=0) if e["ev_net"] is not None
                         else "-", RW.dir_text(e["direction"]), e.get("status", "-")])
        st.append(table(data, [x * inch for x in (0.6, 0.4, 0.8, 0.9, 3.4, 0.95)]))
        if wsc.get("fees_estimated"):
            st.append(P(f"Fees estimated for {wsc['fees_estimated']} blank fee cell(s) (review_kit.est_fee).", "small"))
    for h in notes.get("runaway_watch", []):
        st.append(P(h))
    if notes.get("runaway_watch_withheld"):
        st.append(P("Commentary withheld by the recap's validator: " + notes["runaway_watch_withheld"] + ".", "small"))
    elif not notes.get("runaway_watch"):
        st.append(P("No commentary supplied for this day.", "small"))

    # ── Section 6 (v1.1): the day's ONE maintenance proposal, for a yes ──
    mt = notes.get("maintenance")
    if mt:
        st.append(Spacer(1, 8))
        st.append(P("6. Maintenance proposal (for a yes)", "h1"))
        when = str(mt.get("when", "")).strip()
        st.append(P(f"**{mt.get('id', '?')}** ({mt.get('backlog', '?')} backlog) — {mt.get('title', '')}"))
        for lab, key in (("What", "what"), ("Why now", "why"), ("Risk", "risk"), ("Proof", "proof")):
            if mt.get(key):
                st.append(Paragraph(f"<b>{lab}.</b> {esc(mt[key])}", S["body"]))
        st.append(Paragraph(f"<b>When.</b> {esc(when or '?')}"
                            + (f" — {esc(mt['when_reason'])}" if mt.get("when_reason") else ""), S["body"]))
        st.append(P("Nothing is built until the operator says yes.", "small"))

    # ── Section 7 (v1.5): the schedule, now to tomorrow 17:00 ET (tools/calendar_view.py, read only) ──
    st.append(Spacer(1, 8))
    st.append(P("7. The schedule, now to tomorrow 17:00 ET", "h1"))
    cal, cerr = schedule()
    if cal is None:
        st.append(P(f"Schedule: NOT READ ({cerr}).", "small"))
    else:
        CV = sys.modules["calendar_view"]
        st.append(P(cal["summary"] + (f" · COLLISIONS: {len(cal['collisions'])}" if cal["collisions"] else ""), "body"))
        for pr_ in cal["problems"]:
            st.append(P("Note: " + pr_, "small"))
        st.append(table(CV.table_rows(cal), [x * inch for x in (1.05, 0.7, 3.0, 0.6, 1.05, 1.0)]))
        st.append(P("Planned work is ~/reviews/schedule/planned.tsv (the coordinator's file). A planned row that "
                    "touches the boxes and overlaps RTH, the close, the wake + sweep, the study dispatch or another "
                    "planned box row is flagged COLLISION. Report only: nothing here runs or moves a job.", "small"))

    # ── Section 8 (v1.8): the recommendations, for approval — the LAST section (only the Sources list follows) ──
    st.append(PageBreak())
    st.append(P("8. Recommendations — for approval", "h1"))
    st.append(P("Each line is for a yes or a no, by its id. The recap appends its own proposals to "
                "~/reviews/schedule/recommendations.tsv as NEW and never marks one approved; the coordinator records "
                "each answer there (APPROVED with its slot, or DECLINED). An open item carries forward on every recap "
                "until it is decided. The proposed slot is the calendar's next free fitting window (section 7's "
                "sources over seven days): a study runs in the next study dispatch, control work in a free weekday "
                "evening hour, box work on a Sunday. The cash-readiness review runs at about 17:45 ET, after this "
                "recap: its problems and fixes appear on the next trading day's recap as CARRIED.", "small"))
    rsec, rerr = recommendations(day, recs)
    if rsec is None:
        st.append(P(f"Recommendations: NOT READ ({rerr}).", "small"))
    else:
        if len(rsec["rows"]) > 1:
            st.append(table(rsec["rows"], [x * inch for x in (0.2, 0.92, 1.8, 1.93, 0.76, 0.55, 0.78, 0.46)]))
        else:
            st.append(P("No recommendation is open, and none was decided since the last recap."))
        for pr_ in rsec["problems"]:
            st.append(P("Note: " + pr_, "small"))
    for rf_ in notes.get("recommendations_refused") or []:
        st.append(P("Refused by the recap's validator (not in the ledger): " + rf_ + ".", "small"))

    # ── sources ──
    st.append(Spacer(1, 10))
    st.append(P("Sources", "h2"))
    base_src = [f"Trades: S3 raw/trades/dt={day} via OTV5 tests/warehouse_source.load_trades + mainline() "
                f"({tmeta.listed} objects listed, {tmeta.read} read, {tmeta.bad} unreadable; OTV4TEST rows dropped: "
                f"{sum(dropped.values()) if dropped else 0}).",
                "Fees: OTV5 tests/fees.py fees_for (control fee model; the warehouse rows carry no fee column).",
                "Candles: S3 raw/candles/dt=<day>/sym=<S>/interval=1m (TastyTrade feed, latest push per bar): " +
                ", ".join(f"{s} {binfo[s]['bars']}" for s in order + ["VIX"] if s in binfo) + " RTH bars."]
    for s_ in base_src + sources:
        st.append(P("· " + s_, "small"))
    doc.build(st, onFirstPage=on_page, onLaterPages=on_page)
    return path, {"day": day, "pdf": path, "pages": pages[0], "trades": len(trades), "paper": tot_p, "fees": tot_f,
                  "cash": cash_p, "cash_fees": cash_f,
                  "symbols": order, "gaps": gaps, "bars": binfo,
                  "cash_rows": [(x[0]["symbol"], SHORT.get(x[0]["strategy"]), x[3], x[4], round(x[6], 2),
                                 round(x[7], 2)) for x in cash_rows]}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--date", required=True)
    ap.add_argument("--notes", default=None, help="analyst notes JSON (default ~/reviews/daily_brief/notes/<date>.json)")
    ap.add_argument("--out", default=os.path.expanduser("~/reviews/daily_brief"))
    ap.add_argument("--facts", default=None, help="write the data pass to this JSON file and build no PDF")
    ap.add_argument("--summary-json", default=None, help="also write the run summary to this JSON file")
    ap.add_argument("--recs", default=None, help="the recommendations ledger (default %s)" % RECS_DEFAULT)
    a = ap.parse_args()
    day = ws._valid(a.date)
    if a.facts:
        with open(a.facts, "w", encoding="utf-8") as fh:
            json.dump(facts(day), fh, indent=1, default=str)
        print(a.facts)
        return
    npath = a.notes or os.path.join(NOTES_DIR, f"{day}.json")
    notes = json.load(open(npath)) if os.path.exists(npath) else None
    print(f"notes: {npath if notes else 'none (data-only brief)'}")
    path, summ = build(day, notes, a.out, a.recs)
    print(path)
    print(json.dumps(summ, indent=1, default=str))
    if a.summary_json:
        with open(a.summary_json, "w", encoding="utf-8") as fh:
            json.dump(summ, fh, indent=1, default=str)


if __name__ == "__main__":
    main()
