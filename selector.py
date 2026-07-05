# day_trader_pro/selector.py — v0.1.0
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
You are given a pre-market sentiment/analysis brief. Choose the symbols with the
highest-probability intraday setups for TODAY.

Rules:
- Choose ONLY from the provided universe list.
- Choose at most {max_disc} symbols. Fewer is fine — quality over quantity.
- Do NOT include SPX or QQQ; they always trade and are added automatically.
- Base picks on the brief's signals: composite score, catalysts, and any
  event risk flagged. Prefer names with a clear, high-conviction edge.

Respond with RAW JSON ONLY. No markdown, no code fences, no prose. Schema:
{{"selected_symbols": ["TICK", ...],
  "rationale": {{"TICK": "one short sentence", ...}},
  "confidence": {{"TICK": 0.0-1.0, ...}}}}"""


def _strip_fences(text):
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1] if "\n" in t else t
        if t.endswith("```"):
            t = t.rsplit("```", 1)[0]
    return t.strip()


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

    user_msg = (
        f"UNIVERSE (choose only from these): {', '.join(universe)}\n\n"
        f"PRE-MARKET BRIEF (JSON):\n{json.dumps(report, indent=2)}"
    )

    resp = client.messages.create(
        model=config.MODEL,
        max_tokens=config.MODEL_MAX_TOKENS,
        system=sys_prompt,
        messages=[{"role": "user", "content": user_msg}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    return json.loads(_strip_fences(text))


def _mock_select(report):
    """
    Deterministic offline stand-in: rank the brief's per-ticker composite
    scores and take the top MAX_DISCRETIONARY (excluding ALWAYS_ON).
    """
    scores = report.get("scores", {})
    ranked = sorted(
        ((s, v) for s, v in scores.items() if s not in config.ALWAYS_ON),
        key=lambda kv: kv[1], reverse=True,
    )
    picks = [s for s, _ in ranked[:config.MAX_DISCRETIONARY]]
    return {
        "selected_symbols": picks,
        "rationale": {s: f"top composite score ({scores[s]})" for s in picks},
        "confidence": {s: round(min(0.99, scores[s] / 100.0), 2) for s in picks},
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
    clean = clean[:config.MAX_DISCRETIONARY]
    rationale = raw.get("rationale", {}) if isinstance(raw, dict) else {}
    confidence = raw.get("confidence", {}) if isinstance(raw, dict) else {}
    return clean, rationale, confidence


def select(report):
    """
    Main entry. Returns a dict:
      {"final": [...], "discretionary": [...], "always_on": [...],
       "rationale": {...}, "confidence": {...}, "fallback": bool, "error": str|None}
    Never raises; falls back to ALWAYS_ON only on failure.
    """
    fallback, error = False, None
    try:
        raw = _mock_select(report) if config.MOCK_LLM else _call_anthropic(report)
        disc, rationale, confidence = _validate(raw)
    except Exception as exc:  # noqa: BLE001 — selection must never crash the run
        fallback, error = True, f"{type(exc).__name__}: {exc}"
        disc, rationale, confidence = [], {}, {}

    final = list(config.ALWAYS_ON) + [s for s in disc if s not in config.ALWAYS_ON]
    return {
        "final": final,
        "discretionary": disc,
        "always_on": list(config.ALWAYS_ON),
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
