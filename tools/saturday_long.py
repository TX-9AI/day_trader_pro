#!/usr/bin/env python3
"""
day_trader_pro/tools/saturday_long.py  v1.0  -  the Saturday brief's long form: what the nightly recap leaves out.
v1.0  2026-11-27  dtp r586 / SATLONG.1 (REC-20261126-4). The operator, 2026-11-26: "that Saturday report should be the
      long form version of what was left out of the nightly reports to keep them lightweight & relevant". The first two
      additions, each one scorer here so the 03:00 session quotes figures it did not compute ad hoc:
      (a) PAPER VS CASH - EDGE TRANSFER (2A), <WORK>/edge_transfer.md. Every box that ran in CASH mode on a day of the
          week (review_kit.box_modes: the day's "Service mode: LIVE" start line; else a cash row that day, review_kit's
          own fallback) is listed; per symbol, its cash trades (paper_trade = 0) against a COMPARATOR for the same fire:
          the row's PAPER TWIN when one exists (a paper row on the same box and day, same setup and side, opened within
          TWIN_JOIN_S, nearest first, each used once), else the strict-fill model's prediction for that trade_id
          (MODEL_SOURCES: C5_STRICT v1.1 at the 1 s headline delay first, then RUNAWAY_LIVEFILL_CHECK's headline
          variant; with neither, that study's own model code computes it here, read only and hash-checked, on the
          trade's cached quote window: see "the live-fill model, computed"), else NOT MEASURED by trade_id, for a data
          failure only, with its reason. Beside it: the slippage against the mark recorded on the row's own
          warehouse record (entry: the fill against the midpoint of the quote the contract was chosen on; exit: the
          fill against exit_mark_at_trigger, else that quote's midpoint), so cash = the same fire at its marks - entry
          slip - exit slip; fees beside, never inside EV; and the CUMULATIVE book per symbol from its own cash start
          (the first day it ran in cash mode), with the day-bootstrap interval (review_kit.boot) and a BELOW BASELINE
          flag when the cumulative net EV a trade is under MIN_EDGE_EV_PER_TRADE_USD. A week with none: "No cash trades
          this week."
      (b) LEADS - FULL LEDGER (2B), <WORK>/leads_full.md. Every row of the coordinator's leads ledger
          (~/reviews/schedule/leads.tsv, read with daily_recap.read_leads, the recap's own reader), not only the week's
          movers, grouped by status (daily_recap.LEAD_ORDER, then the rest, CLOSED last) with its evidence, next step
          and decision read; then, for each FORWARD / FORWARD-SHADOW lead, every forward scorer summary
          (FORWARD*SUMMARY*.md, never a *_TEST* dry run) in each study folder its source_study names
          (daily_recap.lead_study_dirs): its Status line and its full cumulative block, dated with the file's own ET
          time. A missing ledger or bad header is NOT READ; a malformed row is skipped and named.
      READ ONLY: the trade CSVs, the conductor's bot-log extracts, the warehouse rows (S3 reads, as weekly_facts), the
      model studies' outputs and the leads ledger; it writes only under --out. No config or env knob.

Run (the Saturday brief prompt, 2A and 2B):
  /home/ubuntu/day_trader_pro/venv/bin/python -I tools/saturday_long.py --fri <this Friday> --out <WORK> [--no-warehouse]
Writes <WORK>/edge_transfer.md, <WORK>/leads_full.md and <WORK>/saturday_long.json.
"""
import argparse
import csv
import glob
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

# ── the live-fill model, computed (v1.0 SATLONG.1b) ─────────────────────────────────────────────────────────────────
# A cash trade with no paper twin and no precomputed model row is priced here by RUNAWAY_LIVEFILL_CHECK_20261126's own
# model code, IMPORTED READ ONLY with a hash check (never copied): code/fill_v2.py (the headline: post at booking + 1 s,
# OTV5 r162 FILL.4 fresh rung 1, strict touch on the ~1.5 s raw/quote_series stream; exits per r144 floor / walk; it
# seal-checks C5_STRICT's fillmodel_v1_1 itself) and HOLD_ARM_VALIDATION_20261127/code/qx.py (its S3 quote reader).
# It runs in a CHILD interpreter (this file with --livefill-worker, before any dtp import), because the model's vendored
# OTV5 tree imports a module named `config` and dtp has its own. Each trade's quote window is cached under
# <WORK>/livefill_cache/<trade_id>.json. NOT MEASURED is kept for a genuine data failure only (no warehouse row or option
# symbol, no quotes, a hash mismatch), and says which.
STUDIES_HOME = os.path.expanduser("~/reviews/studies")
LIVEFILL_CODE = os.path.join("RUNAWAY_LIVEFILL_CHECK_20261126", "code", "fill_v2.py")
LIVEFILL_SHA = "d9aa35b69acc1335aa4e8a03853457cb7f6943425fdae548bf29ad7abd3674e8"
QX_CODE = os.path.join("HOLD_ARM_VALIDATION_20261127", "code", "qx.py")
QX_SHA = "a8589eef4627fc1d31a153f96f9e6f0fc54667a827515e5a416a1655e1396656"
LIVEFILL_DELAY_S, LIVEFILL_MODE, LIVEFILL_START = 1.0, "strict", "post"     # the study's HEAD variant
LIVEFILL_PRE_S = 180                                                         # the study's window: entry - 180 s ..
LIVEFILL_LABEL = "model RUNAWAY_LIVEFILL headline, computed (FILL.4, 1 s strict)"


def _sha(path):
    import hashlib
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _streamer(osym):
    """OCC 'QQQ   261130C00606000' -> the dxFeed streamer symbol '.QQQ261130C606' (RUNAWAY_LIVEFILL_CHECK pop.streamer)."""
    s = str(osym or "")
    if s.startswith("."):
        return s
    root, d, cp, k = s[:6].strip(), s[6:12], s[12], int(s[13:]) / 1000
    return ".%s%s%s%s" % (root, d, cp, "%g" % k)


def _livefill_worker():
    """stdin: {"studies", "cache", "fetch", "trades": [..]} -> stdout {trade_id: {"pnl", "filled"} | {"err"}}."""
    sys.dont_write_bytecode = True        # the study folders are read only: no __pycache__ written into them
    req = json.load(sys.stdin)
    studies, cache, fetch = req["code_root"], req["cache"], req.get("fetch", True)
    out = {}
    fv, qxp = os.path.join(studies, LIVEFILL_CODE), os.path.join(studies, QX_CODE)
    bad = [n for n, pth, want in (("fill_v2.py", fv, LIVEFILL_SHA), ("qx.py", qxp, QX_SHA))
           if not os.path.exists(pth) or _sha(pth) != want]
    if bad:
        return _emit({t["trade_id"]: {"err": "model code missing or changed (sha256: %s)" % ", ".join(bad)}
                      for t in req["trades"]})
    try:
        sys.path.insert(0, os.path.dirname(fv))
        import fill_v2 as F               # noqa: E402  (asserts C5_STRICT fillmodel_v1_1's seal on import)
    except Exception as e:
        return _emit({t["trade_id"]: {"err": "model import failed (%s)" % type(e).__name__} for t in req["trades"]})
    QX = None
    os.makedirs(cache, exist_ok=True)
    for t in req["trades"]:
        tid = t["trade_id"]
        try:
            osym = _streamer(t["option_symbol"])
            day = t["day"]
            y, mo, d = map(int, day.split("-"))
            at = lambda h, m: datetime(y, mo, d, h, m, tzinfo=ZoneInfo("America/New_York")).timestamp()  # noqa: E731
            cp = os.path.join(cache, re.sub(r"[^A-Za-z0-9_.-]", "_", tid) + ".json")
            if os.path.exists(cp):
                qs = json.load(open(cp))["q"]
            elif not fetch:
                out[tid] = {"err": "no cached quotes and no S3 read"}
                continue
            else:
                if QX is None:
                    sys.path.insert(0, os.path.dirname(qxp))
                    import qx as QX       # noqa: E402
                got, _meta = QX.extract("quote_series", day, t["symbol"], [osym], t["te"] - LIVEFILL_PRE_S, at(15, 57))
                qs = got.get(osym) or []
                with open(cp + ".tmp", "w") as fh:
                    json.dump({"trade_id": tid, "osym": osym, "q": qs}, fh)
                os.replace(cp + ".tmp", cp)
            qs = [tuple(x) for x in qs if x[1] is not None and x[2] is not None and x[2] > 0]
            if len(qs) < 2:
                out[tid] = {"err": "no quotes for %s (%d)" % (osym, len(qs))}
                continue
            o = F.score(F.Book(qs), t["symbol"], t["te"], t["tx"], t["eb"], t["ea"], t["xb"], t["xa"], t["reason"],
                        at(10, 30), at(15, 55), LIVEFILL_DELAY_S, LIVEFILL_MODE, LIVEFILL_START)
            out[tid] = {"filled": bool(o["filled"]),
                        "pnl": round((o["lx"] - o["le"]) * 100 * t["n"], 2) if o["filled"] else 0.0}
        except Exception as e:            # one trade's data failure is that trade's NOT MEASURED
            out[tid] = {"err": "%s: %s" % (type(e).__name__, str(e)[:100])}
    return _emit(out)


def _emit(obj):
    json.dump(obj, sys.stdout)
    return 0


if __name__ == "__main__" and sys.argv[1:2] == ["--livefill-worker"]:
    sys.exit(_livefill_worker())

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
sys.path.insert(0, REPO)
import review_kit as RK         # noqa: E402  (split / box_modes / is_paper: the one as-cash rule; boot; est_fee)
import weekly_facts as WF       # noqa: E402  (week_days, epoch_start, warehouse_week: the brief's own week)
import daily_recap as DR        # noqa: E402  (read_leads, lead_study_dirs, LEAD_ORDER: the recap's own lead readers)

ET = ZoneInfo("America/New_York")

# THE MINIMUM-EDGE BASELINE. A symbol's cumulative cash book (from its own cash start) is flagged BELOW BASELINE when
# its net EV a trade (cash fills, after fees) is under this many dollars.
# TODO(operator): the value is the operator's call (REC-20261126-4: "flagged against a minimum-edge baseline"); 0 is a
# placeholder until they set it. It is a named constant on purpose, never a config or env knob (no study toggles in
# config); changing it is a one-line land.
MIN_EDGE_EV_PER_TRADE_USD = 0.0

TWIN_JOIN_S = 120              # a paper twin opened within this many seconds of the cash entry (same box, day, setup, side)
MODEL_SOURCES = (              # (label, path under studies, kind), first match by trade_id wins
    ("model C5_STRICT v1.1, 1 s strict", os.path.join("C5_STRICT_20261124", "results_v1_1.csv"), "c5"),
    ("model RUNAWAY_LIVEFILL headline (FILL.4, 1 s strict)",
     os.path.join("RUNAWAY_LIVEFILL_CHECK_20261126", "data", "scored.json"), "livefill"),
)
LIVEFILL_HEAD = "post|1.0|strict"
NO_CASH = "No cash trades this week."


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _et(s):
    return WF._et(s)


def _usd(v, sign=True):
    if v is None:
        return "-"
    return ("%+.0f" if sign else "%.0f") % v if abs(v) >= 100 else ("%+.2f" if sign else "%.2f") % v


def _cell(v):
    return str(v).replace("|", "/").replace("\n", " ")


def _table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(_cell(c) for c in r) + " |" for r in rows]
    return out


# ── (a) paper vs cash ───────────────────────────────────────────────────────────────────────────────────────────────
def load_csv_rows(start, fri, reviews):
    """-> [row] every trade CSV row start..fri, each with _day, _book (review_kit.split, per file) and _modes."""
    out = []
    for fn in sorted(glob.glob(os.path.join(reviews, "trades", "20??-??-??.csv"))):
        day = os.path.basename(fn)[:10]
        if not (start <= day <= fri):
            continue
        try:
            raw = list(csv.DictReader(open(fn)))
        except OSError:
            continue
        for r, bk in zip(raw, RK.split(raw, modes=RK.modes_for_file(fn))):
            if r.get("sym") in RK.OTV4TEST_SYMS:
                continue
            r = dict(r)
            r["_day"], r["_book"] = day, bk
            out.append(r)
    return out


def cash_days(start, fri, reviews, rows):
    """-> {SYM: [day]} the days each box ran in CASH mode, start..fri: box_modes LIVE, or a cash row that day."""
    out = {}
    root = os.path.join(reviews, "daily_brief", "botlogs")
    try:
        days = sorted(d for d in os.listdir(root) if re.match(r"^\d{4}-\d\d-\d\d$", d) and start <= d <= fri)
    except OSError:
        days = []
    for d in days:
        for sym, mode in RK.box_modes(d, root).items():
            if mode == "LIVE":
                out.setdefault(sym.upper(), set()).add(d)
    for r in rows:
        if not RK.is_paper(r):
            out.setdefault(str(r.get("sym") or "").upper(), set()).add(r["_day"])
    return {k: sorted(v) for k, v in out.items() if k}


def load_models(studies):
    """-> {trade_id: (pnl, filled, label)} the strict-fill model's predictions, first source wins. Never raises."""
    out = {}
    for label, rel, kind in MODEL_SOURCES:
        p = os.path.join(studies, rel)
        try:
            if kind == "c5":
                for r in csv.DictReader(open(p)):
                    if _f(r.get("delay")) != 1.0 or str(r.get("scorable", "1")).strip() not in ("1", "1.0"):
                        continue
                    tid = r.get("trade_id") or ""
                    filled = str(r.get("filled", "")).strip() in ("1", "1.0")
                    pnl = (_f(r.get("strict_pnl")) or 0.0) if filled else 0.0
                    if tid and tid not in out:
                        out[tid] = (pnl, filled, label)
            else:
                for t in json.load(open(p)):
                    v = t.get(LIVEFILL_HEAD) or {}
                    tid = t.get("trade_id") or ""
                    if tid and tid not in out and v and t.get("scorable", 1):
                        out[tid] = (float(v.get("live") or 0.0), bool(v.get("filled")), label)
        except (OSError, ValueError, TypeError, AttributeError):
            continue
    return out


def _ep(s):
    d = _et(s)
    return d.timestamp() if d else None


def compute_models(cash, wh, cache, fetch=True, code_root=None, timeout=1500):
    """-> {trade_id: (pnl, filled, label) | ("ERR", reason)} for the cash rows given (no twin, no precomputed row):
    the live-fill model run in a child interpreter on each trade's warehouse record. Never raises."""
    out, job = {}, []
    for c in cash:
        tid = c.get("trade_id") or ""
        w = wh.get(str(tid))
        if not w:
            out[tid] = ("ERR", "no warehouse row")
            continue
        te, tx = _ep(w.get("entry_time") or c.get("entry_time")), _ep(w.get("exit_time") or c.get("exit_time"))
        if not w.get("option_symbol") or te is None or tx is None:
            out[tid] = ("ERR", "no option symbol or times on the warehouse row")
            continue
        job.append(dict(trade_id=tid, day=c["_day"], symbol=str(c.get("sym")).upper(), option_symbol=w["option_symbol"],
                        te=te, tx=tx, eb=_f(w.get("entry_bid")), ea=_f(w.get("entry_ask")), xb=_f(w.get("exit_bid")),
                        xa=_f(w.get("exit_ask")), reason=str(w.get("exit_reason") or c.get("exit_reason") or ""),
                        n=int(_f(c.get("contracts")) or 0)))
    if not job:
        return out
    import subprocess
    try:
        r = subprocess.run([sys.executable, "-I", os.path.abspath(__file__), "--livefill-worker"],
                           input=json.dumps(dict(code_root=code_root or STUDIES_HOME, cache=cache, fetch=fetch, trades=job)),
                           capture_output=True, text=True, timeout=timeout)
        got = json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else {}
        why = "model run failed (rc=%s %s)" % (r.returncode, (r.stderr or "").strip()[-120:])
    except Exception as e:
        got, why = {}, "model run failed (%s)" % type(e).__name__
    for t in job:
        g = got.get(t["trade_id"])
        if not g:
            out[t["trade_id"]] = ("ERR", why)
        elif "err" in g:
            out[t["trade_id"]] = ("ERR", g["err"])
        else:
            out[t["trade_id"]] = (float(g["pnl"]), bool(g["filled"]), LIVEFILL_LABEL)
    return out


def _mid(b, a):
    b, a = _f(b), _f(a)
    return (b + a) / 2.0 if b is not None and a is not None and b > 0 and a > 0 else None


def marks(w):
    """-> (entry_mark, exit_mark) from a warehouse record: the midpoint of the quote the contract was chosen on, and
    exit_mark_at_trigger (else the exit quote's midpoint). None when not recorded."""
    if not w:
        return None, None
    xm = _f(w.get("exit_mark_at_trigger"))
    return _mid(w.get("entry_bid"), w.get("entry_ask")), (xm if xm and xm > 0 else _mid(w.get("exit_bid"), w.get("exit_ask")))


def pair_twins(cash, paper):
    """-> {cash trade_id: paper row} one paper twin per cash row: same box, day, setup and side, opened within
    TWIN_JOIN_S of the cash entry, nearest first, each paper row used once."""
    cands = []
    for c in cash:
        tc = _et(c.get("entry_time"))
        for p in paper:
            if (str(p.get("sym")).upper(), p["_day"], p.get("strategy"), WF.side_of(p.get("direction"))) != \
               (str(c.get("sym")).upper(), c["_day"], c.get("strategy"), WF.side_of(c.get("direction"))):
                continue
            tp = _et(p.get("entry_time"))
            if tc is None or tp is None:
                continue
            gap = abs((tp - tc).total_seconds())
            if gap <= TWIN_JOIN_S:
                cands.append((gap, c.get("trade_id"), p.get("trade_id"), p))
    out, used = {}, set()
    for gap, ct, pt, p in sorted(cands, key=lambda x: (x[0], str(x[1]), str(x[2]))):
        if ct in out or pt in used:
            continue
        out[ct] = p
        used.add(pt)
    return out


def trade_view(c, twin, model, w):
    ctr = _f(c.get("contracts")) or 0.0
    pnl = _f(c.get("pnl_usd")) or 0.0
    fee = _f(c.get("fee")) if c.get("fee") not in (None, "") else RK.est_fee(c.get("sym"), ctr)
    ep, xp = _f(c.get("entry_premium")), _f(c.get("exit_premium"))
    em, xm = marks(w)
    es = (ep - em) * ctr * 100 if ep is not None and em is not None else None       # + = paid above the mark
    xs = (xm - xp) * ctr * 100 if xp is not None and xm is not None else None       # + = sold below the mark
    if twin is not None:
        cmp_, src = _f(twin.get("pnl_usd")), "paper twin %s" % str(twin.get("trade_id"))[:8]
    elif model is not None and model[0] != "ERR":
        cmp_, src = model[0], model[2] + ("" if model[1] else " (no fill: $0)")
    else:
        cmp_, src = None, "NOT MEASURED (no paper twin; model: %s)" % (model[1] if model else "not run")
    return dict(day=c["_day"], tid=c.get("trade_id") or "", sym=str(c.get("sym")).upper(), strat=c.get("strategy"),
                side=WF.side_of(c.get("direction")), c=ctr, ep=ep, xp=xp, em=em, xm=xm, entry_slip=es, exit_slip=xs,
                mark_pnl=(pnl + es + xs if es is not None and xs is not None else None), pnl=pnl, fee=fee,
                net=pnl - fee, cmp=cmp_, cmp_src=src, diff=(pnl - cmp_ if cmp_ is not None else None))


def _sum(xs, k):
    v = [x[k] for x in xs if x[k] is not None]
    return round(sum(v), 2) if v else None


def sym_block(ts):
    n = len(ts)
    g = round(sum(t["pnl"] for t in ts), 2)
    fees = round(sum(t["fee"] for t in ts), 2)
    withc = [t for t in ts if t["cmp"] is not None]
    lo, hi = RK.boot(ts, key="pnl") if n else (None, None)
    return dict(n=n, gross=g, fees=fees, net=round(g - fees, 2), ev=(round(g / n, 2) if n else None),
                net_ev=(round((g - fees) / n, 2) if n else None), lo=lo, hi=hi, days=len({t["day"] for t in ts}),
                n_cmp=len(withc), cmp=_sum(withc, "cmp"), cash_on_cmp=_sum(withc, "pnl"), diff=_sum(withc, "diff"),
                n_twin=sum(1 for t in withc if t["cmp_src"].startswith("paper twin")),
                entry_slip=_sum(ts, "entry_slip"), exit_slip=_sum(ts, "exit_slip"), mark=_sum(ts, "mark_pnl"),
                n_slip=sum(1 for t in ts if t["entry_slip"] is not None and t["exit_slip"] is not None))


def flag(block, baseline=None):
    baseline = MIN_EDGE_EV_PER_TRADE_USD if baseline is None else baseline
    if not block["n"]:
        return "no cash trade yet"
    return "BELOW BASELINE" if block["net_ev"] < baseline else "at or above"


def edge_transfer(fri, reviews=None, studies=None, wh_rows=None, use_wh=True, cache=None, fetch=None, code_root=None):
    """-> dict for the 2A part. wh_rows (warehouse records, by trade_id) may be injected; else read when use_wh."""
    reviews = reviews or RK.REVIEWS
    studies = studies or os.path.join(reviews, "studies")
    week = WF.week_days(fri)
    f = date.fromisoformat(fri)
    mon = (f - timedelta(days=f.weekday())).isoformat()
    epoch = WF.epoch_start()
    rows = load_csv_rows(epoch, fri, reviews)
    cd = cash_days(epoch, fri, reviews, rows)
    start_of = {s: d[0] for s, d in cd.items()}
    week_boxes = sorted(s for s, d in cd.items() if any(mon <= x <= fri for x in d))
    cash = [r for r in rows if not RK.is_paper(r) and str(r.get("sym")).upper() in start_of
            and r["_day"] >= start_of[str(r.get("sym")).upper()]]
    paper = [r for r in rows if RK.is_paper(r)]
    twins = pair_twins(cash, paper)
    models = load_models(studies)
    wh, wh_note = {}, "not read (--no-warehouse)"
    if wh_rows is not None:
        wh, wh_note = {str(w.get("trade_id")): w for w in wh_rows}, "injected (%d rows)" % len(wh_rows)
    elif use_wh and cash:
        try:
            days = sorted({r["_day"] for r in cash})
            got, _drop, banner = WF.warehouse_week(days)
            wh, wh_note = {str(w.get("trade_id")): w for w in got}, banner
        except Exception as e:                                   # an S3 failure is NOT MEASURED, never a crash
            wh_note = "NOT READ (%s: %s)" % (type(e).__name__, str(e)[:120])
    need = [c for c in cash if c.get("trade_id") not in twins and (c.get("trade_id") or "") not in models]
    if cache is None:                        # never under ~/reviews: the brief passes <WORK>/livefill_cache
        import tempfile
        cache = tempfile.mkdtemp(prefix="satlong_livefill_")
    models.update(compute_models(need, wh, cache, fetch=(use_wh if fetch is None else fetch), code_root=code_root))
    views = [trade_view(c, twins.get(c.get("trade_id")), models.get(c.get("trade_id") or ""),
                        wh.get(str(c.get("trade_id")))) for c in cash]
    views.sort(key=lambda t: (t["day"], t["sym"], t["tid"]))
    wk = [t for t in views if mon <= t["day"] <= fri]
    per = []
    for s in sorted(set(week_boxes) | {t["sym"] for t in wk}):
        ws = [t for t in wk if t["sym"] == s]
        cum = [t for t in views if t["sym"] == s]
        cb = sym_block(cum)
        per.append(dict(sym=s, cash_start=start_of.get(s), cash_days_week=[d for d in cd.get(s, []) if mon <= d <= fri],
                        week=sym_block(ws), cum=cb, flag=flag(cb)))
    not_measured = [t["tid"] for t in wk if t["cmp"] is None]
    no_slip = [t["tid"] for t in wk if t["entry_slip"] is None or t["exit_slip"] is None]
    return dict(fri=fri, monday=mon, sessions=week, baseline=MIN_EDGE_EV_PER_TRADE_USD, cash_boxes=week_boxes,
                symbols=per, trades=wk, not_measured=not_measured, no_slip=no_slip, warehouse=wh_note,
                twin_join_s=TWIN_JOIN_S, models=[m[0] for m in MODEL_SOURCES] + [LIVEFILL_LABEL],
                empty=(not wk))


def render_edge(E):
    L = ["# Paper vs cash - edge transfer (2A), week of %s to %s" % (E["monday"], E["fri"]), "",
         "Cash boxes this week (Service mode LIVE, or a cash row): %s. Comparator per cash trade: its paper twin (same "
         "box, day, setup and side, opened within %d s), else the strict-fill model for that trade_id (%s), else NOT "
         "MEASURED. Slippage is against the mark recorded on the row's own warehouse record (entry: the selection "
         "quote's midpoint; exit: the mark at the exit trigger); + is a cost. Fees beside, never inside EV. Warehouse: %s."
         % (", ".join(E["cash_boxes"]) or "none", E["twin_join_s"], "; then ".join(E["models"]), E["warehouse"]),
         "", "Minimum-edge baseline: net EV a trade below $%.2f is flagged BELOW BASELINE (MIN_EDGE_EV_PER_TRADE_USD; "
         "the value is the operator's call, a placeholder until they set it)." % E["baseline"], ""]
    if E["empty"]:
        L += [NO_CASH, ""]
        if E["cash_boxes"]:
            L += ["Boxes in cash mode with no cash trade: %s." % ", ".join(E["cash_boxes"]), ""]
    else:
        L += ["## The week, per symbol", ""]
        rows = []
        for s in E["symbols"]:
            w = s["week"]
            rows.append([s["sym"], w["n"], _usd(w["gross"]), _usd(w["ev"]), _usd(w["fees"], False), _usd(w["net"]),
                         "%d (%d twin)" % (w["n_cmp"], w["n_twin"]), _usd(w["cash_on_cmp"]), _usd(w["cmp"]),
                         _usd(w["diff"]), "%s (%d)" % (_usd(w["mark"]), w["n_slip"]), _usd(w["entry_slip"]), _usd(w["exit_slip"])])
        L += _table(["sym", "n", "cash gross", "EV/trade", "fees", "net", "with comparator", "cash on those",
                     "comparator", "cash - comparator", "same fills at the mark (n with a mark)", "entry slip", "exit slip"], rows)
        L += ["", "## The week's cash trades", ""]
        L += _table(["day", "sym", "setup", "side", "x", "cash in -> out", "mark in -> out", "entry slip", "exit slip",
                     "cash P&L", "comparator", "source", "cash - comparator", "fee"],
                    [[t["day"], t["sym"], t["strat"], t["side"], "%g" % t["c"],
                      "%s -> %s" % (t["ep"], t["xp"]),
                      "%s -> %s" % (("%.3f" % t["em"]) if t["em"] is not None else "-",
                                    ("%.3f" % t["xm"]) if t["xm"] is not None else "-"),
                      _usd(t["entry_slip"]), _usd(t["exit_slip"]), _usd(t["pnl"]), _usd(t["cmp"]), t["cmp_src"],
                      _usd(t["diff"]), _usd(t["fee"], False)] for t in E["trades"]])
        L += [""]
    cum = [s for s in E["symbols"] if s["cum"]["n"] or s["cash_start"]]
    if cum:
        L += ["## Cumulative since each symbol's cash start", ""]
        L += _table(["sym", "cash start", "sessions", "n", "cash gross", "EV/trade [95%]", "fees", "net",
                     "net EV/trade", "cash - comparator (n)", "entry slip", "exit slip", "vs baseline"],
                    [[s["sym"], s["cash_start"] or "-", s["cum"]["days"], s["cum"]["n"], _usd(s["cum"]["gross"]),
                      "%s [%s, %s]" % (_usd(s["cum"]["ev"]), _usd(s["cum"]["lo"]), _usd(s["cum"]["hi"])),
                      _usd(s["cum"]["fees"], False), _usd(s["cum"]["net"]), _usd(s["cum"]["net_ev"]),
                      "%s (%d)" % (_usd(s["cum"]["diff"]), s["cum"]["n_cmp"]), _usd(s["cum"]["entry_slip"]),
                      _usd(s["cum"]["exit_slip"]), s["flag"]] for s in cum])
        L += [""]
    if E["not_measured"]:
        L += ["NOT MEASURED (no comparator): %s." % ", ".join(E["not_measured"])]
    if E["no_slip"]:
        L += ["NOT MEASURED (no warehouse mark for the slippage): %s." % ", ".join(E["no_slip"])]
    return "\n".join(L).rstrip() + "\n"


# ── (b) the leads ledger in full ────────────────────────────────────────────────────────────────────────────────────
STATUS_GROUPS = ("RECOMMEND",) + tuple(s for s in DR.LEAD_ORDER if s != "RECOMMEND")


def _group(st):
    if st.startswith("RECOMMEND"):
        return 0
    if st.startswith("CLOSED"):
        return len(STATUS_GROUPS) + 1
    return STATUS_GROUPS.index(st) if st in STATUS_GROUPS else len(STATUS_GROUPS)


def forward_files(folder, studies):
    """-> (real, dry): every FORWARD*SUMMARY*.md in a study folder, real scorers and *_TEST* dry runs apart."""
    every = sorted(p for p in glob.glob(os.path.join(studies, folder, "FORWARD*SUMMARY*.md")) if os.path.isfile(p))
    return [p for p in every if "TEST" not in os.path.basename(p).upper()], \
           [p for p in every if "TEST" in os.path.basename(p).upper()]


def forward_block(path):
    """-> dict(file, dated, title, status, block): the scorer's Status line and its whole cumulative block (every
    '## Cumulative' / '## Counted' section, to the next '## '), dated with the file's own ET time. Never raises."""
    out = dict(file=path, dated=None, title="", status=None, block=[], err=None)
    try:
        txt = open(path, encoding="utf-8", errors="replace").read()
        out["dated"] = datetime.fromtimestamp(os.path.getmtime(path), ET).strftime("%Y-%m-%d %H:%M ET")
    except OSError as e:
        out["err"] = "%s NOT READ (%s)" % (os.path.basename(path), type(e).__name__)
        return out
    lines = txt.splitlines()
    out["title"] = next((ln[2:].strip() for ln in lines if ln.startswith("# ")), "")
    m = re.search(r"^\*\*Status:\*\*\s*(.+)$", txt, re.M)
    out["status"] = m.group(1).strip() if m else None
    keep = False
    for ln in lines:
        if ln.startswith("## "):
            keep = bool(re.match(r"^## (Cumulative|Counted)\b", ln))
        if keep:
            out["block"].append("#### " + ln[3:] if ln.startswith("## ") else ln)   # nested under the brief's own heads
    while out["block"] and not out["block"][-1].strip():
        out["block"].pop()
    return out


def leads_full(ledger=None, studies=None):
    ledger = ledger or DR.LEADS
    studies = studies or DR.STUDIES
    rows, problems, err = DR.read_leads(ledger)
    out = dict(ledger=ledger, err=err, problems=problems, groups=[], scorers=[])
    if err:
        return out
    seen = {}
    for r in sorted(rows, key=lambda r: (_group(r["status"]), rows.index(r))):
        g = r["status"] or "?"
        if not out["groups"] or out["groups"][-1]["status"] != g:
            out["groups"].append(dict(status=g, rows=[]))
        out["groups"][-1]["rows"].append(r)
        if r["status"] in DR.LEAD_FORWARD:
            dirs = DR.lead_study_dirs(r["source_study"], studies)
            if not dirs:
                out["scorers"].append(dict(lead=r["id"], folder=None, files=[], dry=[],
                                           note="no study folder found for %r" % r["source_study"][:80]))
            for d in dirs:
                if d in seen:
                    seen[d]["leads"].append(r["id"])
                    continue
                real, dry = forward_files(d, studies)
                s = dict(leads=[r["id"]], folder=d, files=[forward_block(p) for p in real],
                         dry=[os.path.basename(p) for p in dry], note=None)
                seen[d] = s
                out["scorers"].append(s)
    return out


def render_leads(Lf):
    L = ["# Leads - full ledger (2B)", "", "Ledger: %s." % Lf["ledger"], ""]
    if Lf["err"]:
        return "\n".join(L + ["Leads ledger NOT READ (%s)." % Lf["err"]]) + "\n"
    n = sum(len(g["rows"]) for g in Lf["groups"])
    L += ["%d lead(s): %s." % (n, ", ".join("%d %s" % (len(g["rows"]), g["status"]) for g in Lf["groups"]) or "none"),
          ""]
    for g in Lf["groups"]:
        L += ["## %s (%d)" % (g["status"], len(g["rows"])), ""]
        L += _table(["id", "opened", "lead", "source study", "evidence", "next step", "decision read", "last progress"],
                    [[r["id"], r["opened"] or "-", r["lead"], r["source_study"] or "-", r["evidence"] or "-",
                      r["next_step"] or "-", r["decision_read"] or "-",
                      "%s: %s" % (r["last_progress"] or "-", r["progress_note"] or "-")] for r in g["rows"]])
        L += [""]
    if Lf["problems"]:
        L += ["Skipped (malformed): " + "; ".join(Lf["problems"]) + ".", ""]
    L += ["## Forward scorers (FORWARD and FORWARD-SHADOW leads)", ""]
    if not Lf["scorers"]:
        L += ["No FORWARD or FORWARD-SHADOW lead.", ""]
    for s in Lf["scorers"]:
        if s["folder"] is None:
            L += ["### %s" % s["lead"], "", s["note"] + ".", ""]
            continue
        L += ["### %s (leads %s)" % (s["folder"], ", ".join(s["leads"])), ""]
        if not s["files"]:
            L += ["No forward summary yet%s." % (" (dry run only: %s)" % ", ".join(s["dry"]) if s["dry"] else ""), ""]
        for fb in s["files"]:
            if fb["err"]:
                L += [fb["err"] + ".", ""]
                continue
            L += ["**%s**, dated %s%s" % (os.path.basename(fb["file"]), fb["dated"],
                                          (": " + fb["title"]) if fb["title"] else ""), "",
                  "Status: %s" % (fb["status"] or "no Status line in the file"), ""]
            L += (fb["block"] or ["(no cumulative block in the file)"]) + [""]
        if s["dry"] and s["files"]:
            L += ["Dry runs in the folder (never counted, not shown): %s." % ", ".join(s["dry"]), ""]
    return "\n".join(L).rstrip() + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="the Saturday brief's long form (edge transfer, full leads ledger)")
    ap.add_argument("--fri", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-warehouse", action="store_true")
    ap.add_argument("--reviews", default=None, help="the reviews root (default review_kit.REVIEWS)")
    ap.add_argument("--leads", default=None, help="the leads ledger (default ~/reviews/schedule/leads.tsv)")
    ap.add_argument("--studies", default=None, help="the study folders (default ~/reviews/studies)")
    a = ap.parse_args(argv)
    fri = RK._day(a.fri)
    os.makedirs(a.out, exist_ok=True)
    reviews = a.reviews or RK.REVIEWS
    studies = a.studies or (os.path.join(reviews, "studies") if a.reviews else DR.STUDIES)
    E = edge_transfer(fri, reviews, studies, use_wh=not a.no_warehouse, cache=os.path.join(a.out, "livefill_cache"))
    Lf = leads_full(a.leads or (os.path.join(reviews, "schedule", "leads.tsv") if a.reviews else DR.LEADS), studies)
    with open(os.path.join(a.out, "edge_transfer.md"), "w") as fh:
        fh.write(render_edge(E))
    with open(os.path.join(a.out, "leads_full.md"), "w") as fh:
        fh.write(render_leads(Lf))
    with open(os.path.join(a.out, "saturday_long.json"), "w") as fh:
        json.dump(dict(edge_transfer=E, leads=Lf), fh, indent=1, default=str)
    print("saturday_long: %s cash trade(s) this week on %s; %d lead(s), %d forward scorer folder(s) -> %s" % (
        len(E["trades"]), ",".join(E["cash_boxes"]) or "no cash box",
        sum(len(g["rows"]) for g in Lf["groups"]), len(Lf["scorers"]), a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
