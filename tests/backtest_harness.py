"""
tests/backtest_harness.py — offline multi-day backtest over spliced 1-minute tape.
v1.0 — 2026-07-11

Drives the REAL deployed engines over a multi-day 1-minute OHLC file (per symbol),
the way the bot would see them, and reports what would have fired and how it would
have resolved. Reads-only. Sits beside replay_confluence.py and reuses its loader.

WHAT IS EXACT (drives the actual modules, no reimplementation):
  - Regime labels               (regime_classifier + the four analysis engines)
  - v3 confluence scores         (regime_confluence — uncalibrated, informational)
  - ORB setups / stops           (orb_engine v3.2 — impulsive-origin stop, origin gate)
  - Entry gate                   (main.py v3.2 logic: ORB_FIRES_REGARDLESS_OF_REGIME)
  - Setup grade / B-threshold    (setup_scorer)
  - Structure-stop outcome       (exit_engine v3.1 rule, evaluated on the underlying)
  - VIX no-entry gate + macro dim (real VIX series)

WHAT IS MODELED (clearly not exact — no option chain in an OHLC file):
  - Option premium & dollar P&L via Black-Scholes off the VIX level. Enable with
    --model-premium. Assumptions, all documented at PremiumModel:
      * 0DTE by default (expiry 16:00 same session); --dte N for N-day expiry.
      * vol = VIX/100. Apt for index ORBs (SPX/QQQ/DIA). For SINGLE STOCKS the
        single-name IV differs from VIX, so single-stock premium P&L is a rough
        proxy — treat it as relative, not a fill-accurate statement.
      * European BS, no smirk, no bid/ask, no early-fill slippage.
    The signal/regime/ORB/structure layer is exact regardless of this flag.

FIDELITY NOTES:
  - Intraday timeframes (1m/5m/15m) are SESSION-SCOPED (reset each session), matching
    the live feed's "never padded across the overnight gap." Higher timeframes
    (1h/4h/1d) use full continuous multi-day history, matching the feed store. This
    is why multi-day tape is required: on one session 1h is starved and direction
    collapses to NEUTRAL. ~15+ sessions gives 1h real depth.
  - 1d/4h are synthesized from the tape; over a ~month they are short (<55 bars) and
    contribute NEUTRAL, same as the live feed's thin daily backfill.
  - macro.is_fed_day defaults False (no FOMC calendar here); pass --fed-days to mark.

USAGE:
  python tests/backtest_harness.py --symbol CVX_1m_30d.csv --vix VIX_1m_30d.csv
  python tests/backtest_harness.py --symbol CVX_1m_30d.csv --vix VIX_1m_30d.csv --model-premium --dte 0
"""
import sys, os, argparse
from datetime import time as dtime, datetime
from zoneinfo import ZoneInfo
from collections import Counter
import math
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.replay_confluence import load_ohlc, resample
import analysis.orb_engine as OE
from analysis.volatility_engine import get_volatility_engine
from analysis.trend_engine import get_trend_engine
from analysis.structure_analyzer import get_structure_analyzer
from analysis.liquidity_mapper import get_liquidity_mapper
from analysis.regime_classifier import get_regime_classifier, Regime
try:
    from analysis.regime_confluence import RegimeConfluenceScorer
    _HAS_CONFLUENCE = True
except Exception:
    _HAS_CONFLUENCE = False
from config import (REGIME_REASSESS_MINUTES, ORB_FIRES_REGARDLESS_OF_REGIME,
                    VIX_NO_ENTRY_THRESHOLD, VIX_LOW_THRESHOLD,
                    VIX_ELEVATED_THRESHOLD, VIX_CRISIS_THRESHOLD)

ET = ZoneInfo("America/New_York")
_CLOCK = {"t": None}
OE.now_et = lambda: _CLOCK["t"]
OE.is_past_entry_cutoff = lambda: (_CLOCK["t"].hour, _CLOCK["t"].minute) >= (11, 0)

RTH_OPEN, RTH_CLOSE, HARD_CLOSE = dtime(9, 30), dtime(16, 0), dtime(15, 45)
RANGE_END, ORB_CUTOFF = dtime(9, 35), dtime(11, 0)


# ───────────────────────── data prep ─────────────────────────
def prep(path):
    df = load_ohlc(path)
    if df.index.tz is None:
        df.index = df.index.tz_localize(ET)
    df = df[(df.index.time >= RTH_OPEN) & (df.index.time <= RTH_CLOSE)]
    return df


def vix_asof(vix_df, ts):
    """Last VIX close at or before ts (as-of merge, one lookup)."""
    sub = vix_df.loc[:ts]
    return float(sub["close"].iloc[-1]) if len(sub) else float("nan")


def macro_from_vix(vix, fed=False):
    if vix >= VIX_CRISIS_THRESHOLD:      reg = "CRISIS"
    elif vix >= VIX_ELEVATED_THRESHOLD:  reg = "ELEVATED"
    elif vix < VIX_LOW_THRESHOLD:        reg = "LOW"
    else:                                reg = "NORMAL"
    from types import SimpleNamespace
    # macro_context (RISK_ON/RISK_OFF/NEUTRAL) comes from the macro calendar /
    # market_brief in production; not derivable from price+VIX alone, so NEUTRAL.
    return SimpleNamespace(vix=vix, vix_regime=reg, is_fed_day=fed,
                           macro_context="NEUTRAL",
                           vix_no_entry=(vix >= VIX_NO_ENTRY_THRESHOLD))


# ───────────────────────── premium model ─────────────────────────
class PremiumModel:
    """Black-Scholes premium off the VIX level. MODELED — see header caveats."""
    def __init__(self, dte=0, r=0.045):
        self.dte, self.r = dte, r

    def _t_years(self, now_ts):
        if self.dte > 0:
            return max(self.dte, 0.5) / 252.0
        # 0DTE: fraction of the RTH day remaining to 16:00, floored so theta is finite
        end = now_ts.replace(hour=16, minute=0, second=0)
        mins = max((end - now_ts).total_seconds() / 60.0, 5.0)
        return (mins / 390.0) / 252.0

    @staticmethod
    def _norm_cdf(x):
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    def price(self, S, K, vix, now_ts, call=True):
        T = self._t_years(now_ts)
        sig = max(vix, 1.0) / 100.0
        if T <= 0 or sig <= 0:
            intr = max(S - K, 0) if call else max(K - S, 0)
            return intr
        d1 = (math.log(S / K) + (self.r + sig * sig / 2) * T) / (sig * math.sqrt(T))
        d2 = d1 - sig * math.sqrt(T)
        if call:
            return S * self._norm_cdf(d1) - K * math.exp(-self.r * T) * self._norm_cdf(d2)
        return K * math.exp(-self.r * T) * self._norm_cdf(-d2) - S * self._norm_cdf(-d1)


# ───────────────────────── regime timeline ─────────────────────────
def build_regime_timeline(df, vix_df, fed_days, cadence_min):
    """Returns {timestamp -> (regime_label, RegimeState, confluence_dict)} at cadence."""
    d5c, d15c, d1hc = resample(df, "5min"), resample(df, "15min"), resample(df, "1h")
    d4hc, d1dc = resample(df, "4h"), resample(df, "1D")
    volE, trE, stE, lqE = (get_volatility_engine(), get_trend_engine(),
                           get_structure_analyzer(), get_liquidity_mapper())
    clf = get_regime_classifier()
    conf = RegimeConfluenceScorer() if _HAS_CONFLUENCE else None
    idx = df.index
    days = sorted(set(idx.date))
    timeline = {}
    for d in days:
        sess_start = pd.Timestamp(datetime.combine(d, RTH_OPEN), tz=ET)
        sess = [t for t in idx if t.date() == d and RANGE_END <= t.time() <= RTH_CLOSE]
        fed = d in fed_days
        for i, t in enumerate(sess):
            if i % cadence_min != 0:
                continue
            _CLOCK["t"] = t.to_pydatetime()
            price = float(df.loc[t, "close"])
            # intraday session-scoped; HTF continuous
            s5  = d5c[(d5c.index >= sess_start) & (d5c.index <= t)]
            s15 = d15c[(d15c.index >= sess_start) & (d15c.index <= t)]
            s1h = d1hc[d1hc.index <= t]
            s4h = d4hc[d4hc.index <= t]
            s1d = d1dc[d1dc.index <= t]
            if len(s5) < 5:
                continue
            vix = vix_asof(vix_df, t)
            macro = macro_from_vix(vix, fed)
            try:
                vs = volE.analyze(s5, s1h if len(s1h) else s5, price)
                tr = trE.analyze({"1m": df[(df.index >= sess_start) & (df.index <= t)],
                                  "5m": s5, "15m": s15, "1h": s1h, "4h": s4h, "1d": s1d})
                st = stE.analyze(s5, s15, s1h if len(s1h) else None, price)
                lq = lqE.analyze(s5, s15, price)
                rc = clf.classify(vs, tr, st, lq, macro=macro, trigger="backtest")
            except Exception:
                continue
            cdict = None
            if conf is not None:
                try:
                    cdict = conf.score(vs, tr, st, lq)
                except Exception:
                    cdict = None
            timeline[t] = (rc.primary_regime, rc, vs, st, lq, macro, cdict)
    return timeline


def regime_at(timeline, ts):
    """Nearest prior regime evaluation to ts (the label the bot would hold)."""
    prior = [k for k in timeline if k <= ts]
    return timeline[max(prior)] if prior else None


# ───────────────────────── ORB engine per session ─────────────────────────
def orb_setups(df):
    idx = df.index
    days = sorted(set(idx.date))
    out = []
    for d in days:
        sess = df[df.index.date == d]
        ix = sess.index
        first = sess[(ix.time >= RTH_OPEN) & (ix.time < RANGE_END)]
        if len(first) == 0:
            continue
        oh, ol = float(first["high"].max()), float(first["low"].min())
        if oh - ol <= 0:
            continue
        e = OE.ORBEngine()
        e._data.orb_high, e._data.orb_low, e._data.orb_width = oh, ol, oh - ol
        e._range_date = ix[0].strftime("%Y-%m-%d")
        e._data.state = OE.ORBState.RANGING
        for k in range(2, len(sess) + 1):
            sub = sess.iloc[:k]
            _CLOCK["t"] = ix[k - 1].to_pydatetime()
            dd = e.update(None, sub, float(sub["close"].iloc[-1]), regime=None)
            if dd.state in (OE.ORBState.OPEN_LONG, OE.ORBState.OPEN_SHORT):
                out.append(dict(
                    day=d, t=ix[k - 1],
                    long=(dd.state == OE.ORBState.OPEN_LONG),
                    entry=float(sub["close"].iloc[-2]),
                    stop=dd.stop_level,
                    target=dd.target_100pct,
                    orb_high=oh, orb_low=ol,
                ))
                e.notify_position_closed()
    return out


# ───────────────────────── gate + structure outcome ─────────────────────────
def orb_fires(regime_label):
    ok = (Regime.TRENDING_BULL, Regime.TRENDING_BEAR, Regime.BREAKOUT_VOLATILE,
          Regime.RANGING, Regime.COMPRESSION)
    if regime_label in ok:
        return True
    return ORB_FIRES_REGARDLESS_OF_REGIME and regime_label in (Regime.UNKNOWN, Regime.SWEEP_REVERSAL)


def _result(outcome, t, xp, bars, setup, risk, prem_entry, prem_exit):
    long = setup["long"]
    under_R = (((xp - setup["entry"]) if long else (setup["entry"] - xp)) / risk) if risk > 0 else 0.0
    prem_pct = None
    if prem_entry is not None and prem_entry > 1e-6:
        prem_pct = (prem_exit - prem_entry) / prem_entry * 100
    return dict(outcome=outcome, exit_ts=t, exit_price=xp, bars=bars,
                under_R=under_R, prem_entry=prem_entry, prem_exit=prem_exit,
                prem_pnl_pct=prem_pct)


def simulate_trade(df, vix_df, setup, pm=None):
    """Faithful two-stop AND exit on the underlying + (optional) modeled premium.
    Per bar, in order: structure stop (1m close beyond impulsive origin),
    −25% premium floor (modeled premium ≤ 75% of entry), target (intrabar).
    Whichever fires first. Matches exit_engine v3.1 (structure) + the −25% floor."""
    idx = df.index
    ki = list(idx).index(setup["t"])
    stop, tgt, long, entry = setup["stop"], setup["target"], setup["long"], setup["entry"]
    risk = (entry - stop) if long else (stop - entry)
    K = tgt  # bot buys near the projected-target strike
    prem_entry = floor = None
    if pm is not None:
        prem_entry = pm.price(entry, K, vix_asof(vix_df, setup["t"]),
                              setup["t"].to_pydatetime(), call=long)
        floor = 0.75 * prem_entry
    for j in range(ki + 1, len(df)):
        t = idx[j]
        if t.date() != setup["day"] or t.time() >= HARD_CLOSE:
            break
        c = float(df["close"].iloc[j]); hi = float(df["high"].iloc[j]); lo = float(df["low"].iloc[j])
        prem_c = pm.price(c, K, vix_asof(vix_df, t), t.to_pydatetime(), call=long) if pm else None
        # 1) −25% premium floor (theta / retracement / mix) — tick-level in life,
        #    so it front-runs the close-based structure stop; modeled fill AT the
        #    floor (a 1m bar can close past it, but the stop would have caught -25%).
        if pm is not None and prem_entry and prem_entry > 1e-6 and prem_c <= floor:
            return _result("PREMIUM_FLOOR", t, c, j - ki, setup, risk, prem_entry, floor)
        # 2) structure stop — close beyond the impulsive origin (premium here is
        #    guaranteed above -25%, since the floor above did not fire)
        if (long and c < stop) or ((not long) and c > stop):
            return _result("STRUCTURE_STOP", t, c, j - ki, setup, risk, prem_entry, prem_c)
        # 3) target — intrabar reach of the 100% projection
        if (long and hi >= tgt) or ((not long) and lo <= tgt):
            prem_t = pm.price(tgt, K, vix_asof(vix_df, t), t.to_pydatetime(), call=long) if pm else None
            return _result("TARGET", t, tgt, j - ki, setup, risk, prem_entry, prem_t)
    # flatten at 15:45
    day_df = df[(df.index.date == setup["day"]) & (df.index.time < HARD_CLOSE)]
    xt = day_df.index[-1] if len(day_df) else setup["t"]
    xp = float(day_df["close"].iloc[-1]) if len(day_df) else entry
    prem_x = pm.price(xp, K, vix_asof(vix_df, xt), xt.to_pydatetime(), call=long) if pm else None
    return _result("EOD_FLAT", xt, xp, 0, setup, risk, prem_entry, prem_x)


# ───────────────────────── main ─────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True, help="per-symbol 1m OHLC CSV")
    ap.add_argument("--vix", required=True, help="1m VIX CSV, same window")
    ap.add_argument("--model-premium", action="store_true", help="add modeled BS premium P&L")
    ap.add_argument("--dte", type=int, default=0, help="days to expiry for the premium model (0=0DTE)")
    ap.add_argument("--fed-days", default="", help="comma YYYY-MM-DD FOMC dates")
    args = ap.parse_args()

    sym = os.path.splitext(os.path.basename(args.symbol))[0].split("_")[0]
    df = prep(args.symbol)
    vix_df = prep(args.vix)
    fed_days = set()
    for s in [x.strip() for x in args.fed_days.split(",") if x.strip()]:
        fed_days.add(datetime.strptime(s, "%Y-%m-%d").date())
    days = sorted(set(df.index.date))

    print(f"\n{'='*66}\nBACKTEST — {sym} — {len(days)} sessions "
          f"({days[0]} → {days[-1]})\n{'='*66}")
    vlo, vhi = float(vix_df['close'].min()), float(vix_df['close'].max())
    print(f"VIX {vlo:.1f}–{vhi:.1f} (no-entry ≥{VIX_NO_ENTRY_THRESHOLD}: "
          f"{'never triggers' if vhi < VIX_NO_ENTRY_THRESHOLD else 'TRIGGERS on some bars'})")

    # 1) regime timeline
    cad = max(REGIME_REASSESS_MINUTES, 1)
    timeline = build_regime_timeline(df, vix_df, fed_days, cad)
    dist = Counter(v[0] for v in timeline.values())
    tot = sum(dist.values())
    print(f"\n── REGIME DISTRIBUTION ({tot} evals @ {cad}-min) ──")
    for k, v in dist.most_common():
        print(f"  {str(k):20}{v:5}  {100*v/max(tot,1):4.0f}%")

    # 2) ORB setups + gate + structure outcome
    setups = orb_setups(df)
    pm = PremiumModel(dte=args.dte) if args.model_premium else None
    fired, blocked = [], 0
    for s in setups:
        r = regime_at(timeline, s["t"])
        label = r[0] if r else Regime.UNKNOWN
        s["regime"] = label
        if not orb_fires(label):
            blocked += 1
            continue
        res = simulate_trade(df, vix_df, s, pm=pm)
        s.update(res)
        fired.append(s)

    print(f"\n── ORB (gate applied) ──")
    print(f"  setups detected: {len(setups)}   fired: {len(fired)}   blocked by regime gate: {blocked}")
    if fired:
        wins = sum(1 for s in fired if s["outcome"] == "TARGET")
        stru = sum(1 for s in fired if s["outcome"] == "STRUCTURE_STOP")
        flr  = sum(1 for s in fired if s["outcome"] == "PREMIUM_FLOOR")
        eod  = sum(1 for s in fired if s["outcome"] == "EOD_FLAT")
        print(f"  long/short: {sum(s['long'] for s in fired)}/{sum(not s['long'] for s in fired)}")
        print(f"  exits:  TARGET {wins}  STRUCTURE_STOP {stru}  PREMIUM_FLOOR {flr}  EOD_FLAT {eod}")
        import statistics as st
        print(f"  underlying expectancy: {st.mean([s['under_R'] for s in fired]):+.2f}R  "
              f"median {st.median([s['under_R'] for s in fired]):+.2f}R")
        print(f"  fired under which regime label:")
        for k, v in Counter(s["regime"] for s in fired).most_common():
            print(f"     {str(k):18}{v}")
        if pm:
            pnls = [s["prem_pnl_pct"] for s in fired]
            print(f"  MODELED premium P&L (BS off VIX, {'0DTE' if args.dte==0 else str(args.dte)+'DTE'}): "
                  f"mean {st.mean(pnls):+.0f}%  median {st.median(pnls):+.0f}%  "
                  f"[modeled — not fill-accurate; VIX-vol proxy]")
        print(f"\n  sample fired setups:")
        for s in fired[:8]:
            extra = f" prem {s['prem_pnl_pct']:+.0f}%" if pm else ""
            print(f"    {s['t'].strftime('%m-%d %H:%M')} {'L' if s['long'] else 'S'} "
                  f"{str(s['regime']):16} entry={s['entry']:.2f} stop={s['stop']:.2f} "
                  f"-> {s['outcome']:14} {s['under_R']:+.2f}R{extra}")


if __name__ == "__main__":
    main()
