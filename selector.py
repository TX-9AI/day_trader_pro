# day_trader_pro/selector.py  v0.4.1
# v0.3.1 (2026-08-17)  THE PANEL IS HARDCODED, NOT AN ENV VAR. v0.3.0 read
#   OT_PANEL_OVERRIDE; the operator's answer  "I'm not setting jack shit in
#   the morning"  is the correct one: a variable that must be exported before
#   each run is a MANUAL PRE-RUN STEP, and a manual pre-run step never happens.
#   Same class as the FEED.1 maintenance flag, which was built and never used.
#   `PANEL` is now a module constant. It stays that way indefinitely; changing
#   the panel is a commit, and `PANEL = []` restores discretionary selection.
# v0.3.0 (2026-08-17)  PANEL OVERRIDE. `OT_PANEL_OVERRIDE=SYM,SYM,...` pins the
#   trading panel and BYPASSES the discretionary selection entirely.
#   TRADING ONLY  every box still wakes, collects and pushes; the candle tape,
#   chain snapshots and S3 corpus keep their full 29-symbol breadth.
#   WHY (measurement, not P&L): every trade in the sample is currently
#   conditioned on "the selector approved this symbol this morning". If that
#   preference correlates with outcome, P0.1's separation test measures the
#   SELECTOR'S TASTE alongside the primitive. A fixed panel removes it.
#   THE RANKING RULE IS NEUTRAL AND IT WAS CHECKED: ranked by TRADE COUNT,
#   never P&L  ranking on profit would select on the outcome the retool is
#   trying to predict. Across ~1,045 closed trades the top 15 by count hold
#   both the WORST performer (SPX -$4,270) and among the best (AVGO +$3,744).
#   TSLA (34) is ONE trade behind AMD (35)  the 15/16 cut is a coin flip.
#   ALWAYS_ON is injected regardless; unknown symbols are DROPPED AND NAMED;
#   and it ANNOUNCES ITSELF, because a fixed panel is otherwise
#   indistinguishable from a selector that keeps picking the same names.
# v0.2.1 (2026-07-21) — add ranked[] to select(): the full discretionary universe as
#   the reporter ranked it (symbol, strength, score, rank, selected). Powers
#   the wake message's per-pick scores and near-miss cutoff view. No change to
#   selection logic itself.
# v0.2.0 (2026-07-15) — EXACTLY-N discretionary (was up-to-N) + consume the
#   brief's move_ranked sidecar. The reporter (market_brief_v1 emit v1.3.0)
#   now pre-ranks the top names by open-move probability; the model's job is
#   to CONCUR or SWAP with justification, not pick from scratch. select()
#   ALWAYS returns exactly MAX_DISCRETIONARY discretionary names, backfilled
#   deterministically from move_ranked/scores if the model returns fewer, so
#   the fleet wakes to a fixed size every day. Emits per-name signed strength
#   for the bot's setup-score nudge (Stage 3).', tag='hdr
"""
Turns a finished market brief into a validated list of symbols to wake.

The model's output is treated as UNTRUSTED input, exactly like a broker fill:
  - strict JSON schema, markdown fences stripped defensively
  - every symbol intersected against the known universe (unknowns dropped)
  - discretionary picks hard-capped at MAX_DISCRETIONARY
  - ALWAYS_ON (SPX, QQQ) injected regardless of what the model says
  - deterministic fallback to ALWAYS_ON-only on ANY error

So the worst case is never "over-exposed" or "nothing running" — it is
"exactly SPX + QQQ", which is your intended daily floor.

CLI:
    python selector.py --test      # runs against a built-in sample report
"""

import json
import os
import sys

import config


SYSTEM_PROMPT = """You are the trade-selection stage of an automated day-trading suite.
The pre-market brief already RANKED its top names by probability of a tradable
move at the open (field: move_ranked). Your job is to CONCUR with that ranking
or SWAP names you judge weaker, using the brief's signals — not to pick from
scratch.

Rules:
- Return EXACTLY {max_disc} symbols. This is a fixed fleet size, not a maximum.
- Choose ONLY from the provided universe list.
- Do NOT include SPX or QQQ; they always trade and are added automatically.
- Start from move_ranked (already ordered best-first). Keep it unless the brief's
  composite score, direction, conviction, earnings, or landmines give you a
  concrete reason to swap a name for another universe name with a better edge.
- Prefer a clear directional or event catalyst likely to move the name early.

Respond with RAW JSON ONLY. No markdown, no code fences, no prose. Schema:
{{"selected_symbols": ["TICK", ...],   // EXACTLY {max_disc}, best-first
  "rationale": {{"TICK": "one short sentence", ...}},
  "confidence": {{"TICK": 0.0-1.0, ...}}}}"""


def _strip_fences(text):
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1] if "\n" in t else t
        if t.endswith("```"):
            t = t.rsplit("```", 1)[0]
    return t.strip()


_os_path_join = os.path.join


def _call_anthropic(report):
    """Real API call. Returns parsed dict or raises."""
    import anthropic

    key = os.environ.get(config.ENV_ANTHROPIC_KEY)
    if not key:
        raise RuntimeError(
            f"{config.ENV_ANTHROPIC_KEY} not set in environment")

    client = anthropic.Anthropic(api_key=key)
    universe = [s for s in config.UNIVERSE if s not in config.ALWAYS_ON]
    sys_prompt = SYSTEM_PROMPT.format(max_disc=config.MAX_DISCRETIONARY)

    move_ranked = report.get("move_ranked", [])
    pre = ", ".join(f"{r.get('ticker')}({r.get('strength')})" for r in move_ranked) or "(none)"
    user_msg = (
        f"UNIVERSE (choose only from these): {', '.join(universe)}\n\n"
        f"REPORTER'S PRE-RANKED TOP (move_ranked, best-first): {pre}\n\n"
        f"Return exactly {config.MAX_DISCRETIONARY} symbols — concur or swap.\n\n"
        f"PRE-MARKET BRIEF (JSON):\n{json.dumps(report, indent=2)}"
    )

    resp = client.messages.create(
        model=config.MODEL,
        max_tokens=config.MODEL_MAX_TOKENS,
        system=sys_prompt,
        messages=[{"role": "user", "content": user_msg}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    stop = getattr(resp, "stop_reason", "?")
    try:
        return json.loads(_strip_fences(text))
    except Exception as exc:                      # noqa: BLE001
        # 2026-07-30 — the parse failed with "Unterminated string ... (char 417)"
        # and ALL we had was that offset, so the cause had to be inferred from a
        # character position. The response itself is the evidence; keep it.
        # stop_reason is the single most diagnostic field: "max_tokens" means the
        # cap truncated us, "end_turn" means the model genuinely emitted bad JSON.
        try:
            import config as _c
            dump = _os_path_join(getattr(_c, "DATA_DIR", "."),
                                 "last_model_response.txt")
            with open(dump, "w") as fh:
                fh.write(f"# stop_reason={stop} chars={len(text)} "
                         f"max_tokens={config.MODEL_MAX_TOKENS} "
                         f"model={config.MODEL}\n{text}")
        except Exception:                         # noqa: BLE001
            dump = "(dump failed)"
        raise ValueError(
            f"{type(exc).__name__}: {exc} | stop_reason={stop} "
            f"chars={len(text)} max_tokens={config.MODEL_MAX_TOKENS} "
            f"| raw saved to {dump}") from exc


def _mock_select(report):
    """
    Deterministic offline stand-in: rank the brief's per-ticker composite
    scores and take the top MAX_DISCRETIONARY (excluding ALWAYS_ON).
    """
    mr = [r.get("ticker") for r in report.get("move_ranked", [])
          if r.get("ticker") not in config.ALWAYS_ON]
    scores = report.get("scores", {})
    if not mr:
        mr = [s for s, _ in sorted(
            ((s, v) for s, v in scores.items() if s not in config.ALWAYS_ON),
            key=lambda kv: kv[1], reverse=True)]
    picks = mr[:config.MAX_DISCRETIONARY]
    return {
        "selected_symbols": picks,
        "rationale": {s: "reporter move_ranked / composite" for s in picks},
        "confidence": {s: 0.6 for s in picks},
    }


def _validate(raw):
    """Sanitize model output into a clean discretionary list."""
    universe = set(config.UNIVERSE) - set(config.ALWAYS_ON)
    picks = raw.get("selected_symbols", []) if isinstance(raw, dict) else []
    clean, seen = [], set()
    for s in picks:
        if not isinstance(s, str):
            continue
        s = s.strip().upper()
        if s in universe and s not in seen:
            clean.append(s)
            seen.add(s)
    clean = clean[:config.MAX_DISCRETIONARY]   # hard cap; backfill in select() enforces the floor
    rationale = raw.get("rationale", {}) if isinstance(raw, dict) else {}
    confidence = raw.get("confidence", {}) if isinstance(raw, dict) else {}
    return clean, rationale, confidence


# ── THE FIXED TRADING PANEL (2026-08-17) ─────────────────────────────────────
# The 15 symbols with the MOST TRADE HISTORY, measured across ~1,045 closed
# trades. Set `PANEL = []` to restore discretionary selection.
#
# ⚠️ RANKED BY TRADE COUNT, NEVER BY P&L. Ranking on profitability would select
# on the very outcome the retool is trying to predict. Checked rather than
# assumed: the top 15 by count contain both the WORST performer (SPX −$4,270)
# and among the best (AVGO +$3,744) — count and profit are uncorrelated, so
# "most history" smuggles no preference in.
# ⚠️ TSLA (34) sits ONE trade behind AMD (35). The 15/16 boundary is a coin
# flip, not a verdict.
# ── PANEL v2, 2026-08-20 ────────────────────────────────────────────────────
# OUT: LLY, SMH, MSFT, ORCL      IN: META, NFLX, CVX, TSLA   (operator's call)
#
# ⚠️ THE PANEL IS TECH-HEAVY AND THAT IS A CORRELATION RISK, not a preference.
# Even after this swap: NVDA, MU, AVGO, PLTR, GOOGL, AMZN, META, NFLX, CRM, AMD
# plus QQQ - roughly two thirds move together on a semiconductor session, which
# is part of why the late-July 2026 selloff was hard to read across the fleet.
# UNH (healthcare), CVX (energy), TSLA (its own thing) and SPX are the only
# genuine diversifiers.
# TSLA over JPM was the call here: financials remain the largest liquid sector
# with NO representation, and it is the obvious next addition if a slot opens.
#
# ⚠️ THIS IS A POPULATION BOUNDARY. Any measurement spanning 2026-08-20 mixes
# two different trading panels, and a per-symbol result from before the change
# does not describe the fleet after it. Name the window or the numbers are not
# comparable - the archive now carries SIX such boundaries (pre-LIQ.1,
# post-LIQ.1, post-LIQ.6, post-FEED.2, post-STOP.1, post-PANEL.2).
#
# ⚠️ AND IT DOES NOT AFFECT COLLECTION. The panel decides which boxes TRADE;
# all 29 continue to collect. The open-interest accumulation started 2026-08-19
# for the GEX butterfly is fleet-wide and is NOT interrupted by this change.
# **A box that stopped collecting because it stopped trading would be a box
# whose pitchfork and ADX depth quietly dies** - WA §30.
PANEL = ["NVDA", "SPX", "PLTR", "MU", "QQQ", "GOOGL", "AMZN", "AVGO",
         "TSLA", "META", "NFLX", "CRM", "UNH", "CVX", "AMD"]


def select(report):
    """
    Main entry. Returns a dict:
      {"final": [...], "discretionary": [...], "always_on": [...],
       "rationale": {...}, "confidence": {...}, "fallback": bool, "error": str|None}
    Never raises; falls back to ALWAYS_ON only on failure.
    """
    # ── PANEL OVERRIDE (2026-08-17) — A FIXED TRADING PANEL ──────────────────
    # Operator: pin the 15 symbols with the most trade history and bypass the
    # discretionary selection entirely. **TRADING ONLY** — every box still
    # wakes, collects and pushes; only the trade set is fixed.
    #
    # WHY, and it is a measurement reason rather than a P&L one: today every
    # trade in the sample is conditioned on *"the selector approved this symbol
    # this morning."* If that preference correlates with outcome, the P0.1
    # separation test measures the SELECTOR'S TASTE alongside the primitive. A
    # fixed panel removes the confounder outright.
    #
    # ⚠️ THE RULE IS NEUTRAL, AND THAT WAS CHECKED, NOT ASSUMED. The panel is
    # ranked by TRADE COUNT, never by P&L — ranking on profitability would
    # select on the very outcome the retool is trying to predict. Measured
    # 2026-08-17 across ~1,045 closed trades: net is scattered through the
    # ranking (the top 15 contain both the WORST performer, SPX −$4,270, and
    # among the best, AVGO +$3,744), so count and profitability are
    # uncorrelated and "most history" smuggles nothing in.
    # ⚠️ TSLA (34) sits ONE TRADE behind AMD (35). The 15/16 boundary is a coin
    # flip, not a verdict — recorded so nobody later reads the cut as meaningful.
    #
    # ⚠️ IT ANNOUNCES ITSELF. A fixed panel is otherwise INDISTINGUISHABLE from
    # a selector that happens to keep choosing the same names — the failure
    # shape of every silent gate this project has hit.
    # ⚠️ HARDCODED, NOT AN ENV VAR. v0.3.0 read `OT_PANEL_OVERRIDE` and the
    # operator's answer was correct: a variable that must be exported before
    # each run is a manual pre-run step, and **a manual pre-run step never
    # happens.** Same class as the FEED.1 maintenance flag. The panel is now
    # simply how the fleet is configured; changing it is a commit.
    _panel = list(PANEL)
    if _panel:
        _known = set(getattr(config, "UNIVERSE", []) or _panel)
        _bad = [s for s in _panel if _known and s not in _known]
        _use = [s for s in _panel if not _known or s in _known]
        for s in config.ALWAYS_ON:          # the daily floor is not negotiable
            if s not in _use:
                _use.append(s)
        # ⚠️ `print`, not a logger: this module has none, and the caller
        # captures stdout. A logger call here would raise NameError inside the
        # selection path — which `select()` swallows by design, so the override
        # would silently fall through to the model and nobody would know.
        print("[panel] FIXED PANEL — trading "
              f"{len(_use)}: {','.join(_use)}. The discretionary selector was "
              "NOT consulted. Every box still wakes, collects and pushes; only "
              "the TRADE set is pinned."
              + (f" DROPPED as unknown: {','.join(_bad)}" if _bad else ""))
        return {
            "final": _use,
            "discretionary": [s for s in _use if s not in config.ALWAYS_ON],
            "always_on": list(config.ALWAYS_ON),
            "brief_strength": {},
            "ranked": [{"symbol": s, "strength": 0.0, "score": 0.0,
                        "rank": i + 1, "selected": True}
                       for i, s in enumerate(_use)],
            "rationale": {s: "fixed panel (selector.PANEL)" for s in _use},
            "confidence": {},
            "fallback": False,
            "error": None,
            "panel_override": True,
        }

    fallback, error = False, None
    try:
        raw = _mock_select(report) if config.MOCK_LLM else _call_anthropic(report)
        disc, rationale, confidence = _validate(raw)
    except Exception as exc:  # noqa: BLE001 — selection must never crash the run
        fallback, error = True, f"{type(exc).__name__}: {exc}"
        disc, rationale, confidence = [], {}, {}

    # EXACTLY-N: backfill from the reporter's move_ranked (then raw scores) so
    # the fleet wakes to a fixed size even if the model returned fewer.
    want = config.MAX_DISCRETIONARY
    universe = [s for s in config.UNIVERSE if s not in config.ALWAYS_ON]
    backfill_order = [r.get("ticker") for r in report.get("move_ranked", [])
                      if r.get("ticker") in universe]
    if len(backfill_order) < want:
        scores = report.get("scores", {})
        for s, _ in sorted(((s, v) for s, v in scores.items() if s in universe),
                           key=lambda kv: kv[1], reverse=True):
            if s not in backfill_order:
                backfill_order.append(s)
    seen = set(disc)
    for s in backfill_order:
        if len(disc) >= want:
            break
        if s not in seen:
            disc.append(s); seen.add(s)
            rationale.setdefault(s, "backfill: reporter rank")
            confidence.setdefault(s, 0.4)
    disc = disc[:want]

    # signed strength per discretionary name for the bot's setup nudge (Stage 3)
    strength_by_sym = {r.get("ticker"): r.get("strength", 0.0)
                       for r in report.get("move_ranked", [])}
    brief_strength = {s: round(float(strength_by_sym.get(s, 0.3)), 3) for s in disc}

    final = list(config.ALWAYS_ON) + [s for s in disc if s not in config.ALWAYS_ON]

    # Ranked view (for wake-message transparency + cutoff tuning): the full
    # discretionary universe as the reporter ranked it, each with signed
    # strength, composite score, rank, and whether it made the cut. Lets you
    # see exactly where the MAX_DISCRETIONARY line fell and what just missed.
    ranked, seen_r = [], set()
    for r in report.get("move_ranked", []):
        t = r.get("ticker")
        if t in universe and t not in seen_r:
            ranked.append({"symbol": t,
                           "strength": round(float(r.get("strength", 0.0)), 3),
                           "score": report.get("scores", {}).get(t),
                           "selected": t in disc})
            seen_r.add(t)
    for s, v in sorted(report.get("scores", {}).items(),
                       key=lambda kv: (kv[1] is not None, kv[1]), reverse=True):
        if s in universe and s not in seen_r:
            ranked.append({"symbol": s, "strength": None, "score": v,
                           "selected": s in disc})
            seen_r.add(s)
    for i, row in enumerate(ranked):
        row["rank"] = i + 1

    return {
        "final": final,
        "discretionary": disc,
        "always_on": list(config.ALWAYS_ON),
        "brief_strength": brief_strength,
        "ranked": ranked,
        "rationale": rationale,
        "confidence": confidence,
        "fallback": fallback,
        "error": error,
    }


# --------------------------------------------------------------------------
# Sample report (also used by orchestrator's mock path)
# --------------------------------------------------------------------------
def sample_report():
    return {
        "date": "2026-07-06",
        "scores": {
            "NVDA": 88, "MU": 81, "TSLA": 74, "META": 69, "AAPL": 63,
            "MSFT": 58, "NFLX": 55, "ORCL": 41, "SPY": 50,
        },
        "landmines": [{"event": "ISM Services", "time": "10:00 ET"}],
        "earnings_today": [],
        "notes": "Semis leading pre-market on AI capex headlines.",
    }


def main(argv):
    if "--test" in argv:
        config.MOCK_LLM = True
        out = select(sample_report())
        print(json.dumps(out, indent=2))
        return 0
    print("Usage: python selector.py --test")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
