# day_trader_pro/config.py — v0.1.0
"""
Central configuration for the day_trader_pro control server (orchestrator).

Nothing secret lives in this file. Secrets are read from environment
variables at runtime (see the ENV section). This file only holds the
non-secret knobs: the trading universe, region, caps, timing, paths, and
the mock switches used for offline development.

Design intent:
  - The control server auto-discovers instances by their tag "Name".
    You never hardcode instance IDs here; the registry resolves them.
  - SPX and QQQ always trade. The model may add up to MAX_DISCRETIONARY more.
  - Everything can run end-to-end with zero real credentials via MOCK_MODE.
"""

import os

# --------------------------------------------------------------------------
# Region
# --------------------------------------------------------------------------
# Ohio == us-east-2 (matches the console screenshot). Override with DTP_REGION.
REGION = os.environ.get("DTP_REGION", "us-east-2")

# --------------------------------------------------------------------------
# Trading universe  (tag "Name" on each dedicated EC2 instance == the ticker)
# --------------------------------------------------------------------------
# NOTE: Confirmed-known names from market_brief_v1 are listed first. The list
# is currently short of 30 on purpose — paste your full 30-symbol universe here
# so the tag filter matches your fleet exactly. Order does not matter.
UNIVERSE = [
    "SPX", "QQQ", "SPY",
    "AAPL", "MU", "NVDA", "MSFT", "TSLA", "NFLX", "META", "ORCL",
    # TODO(Jason): add the remaining ~19 tickers from the live universe here.
]

# The reporter / control server's own tag Name. It is never woken or stopped.
REPORTER_TAG = os.environ.get("DTP_REPORTER_TAG", "1-REPORTER")

# --------------------------------------------------------------------------
# Selection policy
# --------------------------------------------------------------------------
# These two always trade regardless of what the model returns.
ALWAYS_ON = ["SPX", "QQQ"]
# Max additional discretionary picks the model is allowed to wake.
# Total running fleet is therefore between len(ALWAYS_ON) and
# len(ALWAYS_ON) + MAX_DISCRETIONARY  (i.e. 2..6 by default).
MAX_DISCRETIONARY = 4

# --------------------------------------------------------------------------
# Anthropic model used for the selection call
# --------------------------------------------------------------------------
# Publicly available strings: claude-opus-4-8, claude-sonnet-5,
# claude-haiku-4-5-20251001. Sonnet-5 is a good balance for reasoning over the
# brief; bump to opus-4-8 if you want maximum reasoning at higher cost.
MODEL = os.environ.get("DTP_MODEL", "claude-sonnet-5")
MODEL_MAX_TOKENS = int(os.environ.get("DTP_MODEL_MAX_TOKENS", "1500"))

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
INSTANCE_MAP_PATH = os.path.join(DATA_DIR, "instance_map.json")
MOCK_STATE_PATH = os.path.join(DATA_DIR, "mock_state.json")

# Where market_brief_v1 writes its machine-readable report (via --emit-json).
# Override with DTP_REPORT_JSON to point at the reporter's output location.
REPORT_JSON_PATH = os.environ.get(
    "DTP_REPORT_JSON", os.path.join(DATA_DIR, "report.json")
)

# --------------------------------------------------------------------------
# Timing / behavior
# --------------------------------------------------------------------------
# Seconds to wait for instances to reach "running" after start before paging.
START_CONFIRM_TIMEOUT = int(os.environ.get("DTP_START_TIMEOUT", "180"))
START_POLL_INTERVAL = 10

# --------------------------------------------------------------------------
# Environment variable NAMES for secrets (values never stored here)
# --------------------------------------------------------------------------
ENV_ANTHROPIC_KEY = "ANTHROPIC_API_KEY"
ENV_TELEGRAM_TOKEN = "DTP_TELEGRAM_TOKEN"
ENV_TELEGRAM_CHAT = "DTP_TELEGRAM_CHAT_ID"

# --------------------------------------------------------------------------
# Mock switches  (offline development / devtools spool-up)
# --------------------------------------------------------------------------
# MOCK_MODE flips all three sub-mocks on. Individual overrides let you, e.g.,
# use the REAL Anthropic API while faking EC2. Any value that isn't "1"/"true"
# is treated as off.
def _flag(name, default="0"):
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes")

MOCK_MODE = _flag("DTP_MOCK", "0")
MOCK_AWS = MOCK_MODE or _flag("DTP_MOCK_AWS", "0")
MOCK_LLM = MOCK_MODE or _flag("DTP_MOCK_LLM", "0")
MOCK_TELEGRAM = MOCK_MODE or _flag("DTP_MOCK_TELEGRAM", "0")


def set_mock(on: bool = True):
    """Force all mocks on/off at runtime (used by devtools / CLI --mock)."""
    global MOCK_MODE, MOCK_AWS, MOCK_LLM, MOCK_TELEGRAM
    MOCK_MODE = MOCK_AWS = MOCK_LLM = MOCK_TELEGRAM = bool(on)
