# day_trader_pro/strategy_registry.py — v1.0
# v1.0 (2026-09-25) — r426 / OPS.50. ONE REGISTRY FOR TWO ENGINES.
#   Operator, 2026-09-24, on inheriting the TEST boxes: *"we also have
#   different trading strategies that you're going to have to enumerate in the
#   rollup reports. They officially become part of this corpus because they're
#   going to be managed and monitored here."*
#
#   🔴 STRATEGY NAME IS NOT A KEY ANY MORE, AND THAT IS MEASURED RATHER THAN
#   FEARED. Six strategy names exist in BOTH engines and every one of them is
#   different code — md5 differs on all six and the sizes differ by 14-44% in
#   both directions (sweep_credit_spread 106,283B MAIN vs 59,356B TEST;
#   gex_pin_butterfly 51,640B vs 62,858B). TEST also carries a whole *_plan
#   family MAIN does not have. Summing `ORBS` across lineages pools two
#   different designs, which is exactly the error r421 recorded for pre- and
#   post-epoch TrendCreditSpread — except there it was a risk and here the
#   hashes make it a certainty. EVERY per-strategy row is keyed
#   (lineage, code) and the two are NEVER added together.
#
#   🔑 WHY A CODE AT ALL: r202/dtp-r268 — the reader is a phone, Termius wraps
#   at ~60 characters and the trade row is 43. The codes were already here and
#   already four-ish characters; this makes them uniformly FOUR so the column
#   is fixed width, and gives the TEST strategies codes of their own.
#
#   ⚠️ THE TWO COPIES HAD ALREADY DRIFTED. `_STRAT_ABBR` lived in BOTH
#   dtp/trade_report.py (8 entries) and otv4/query.py (10) — the shared 8
#   agreed, but CondorManagement/CMGT and CreditRoll/ROLL existed only in otv4.
#   Nothing noticed. This module is the owner; otv4 mirrors it and
#   check_strategy_registry R5 pins them, the same way test_panel_mirror pins
#   UNIVERSE across three repos.
#
#   ⚠️ AND THE OLD FALLBACK IS THE DEFECT THIS CHANGE EXISTS TO CLOSE. r202's
#   rule is right — an unknown name is TRUNCATED, NEVER DROPPED, because a
#   blank column hides a strategy nobody registered. But `n[:4].upper()` was
#   safe with ONE engine and is not with two: LiquidityHunt renders `LIQU` and
#   Breakout renders `BREA` — not blank, not flagged, just quietly not the code
#   the operator assigned. A WRONG BUT PLAUSIBLE CODE IS WORSE THAN AN OBVIOUS
#   UNKNOWN, so the fallback still renders (never blank) and now renders
#   VISIBLY unregistered, and the rollup names the unmapped set out loud.
"""The strategy corpus: what exists, what it is called, and which engine made it."""

# ── lineages ────────────────────────────────────────────────────────────────
# 🔑 LINEAGE NAMES THE ENGINE. The tag is TEST by the operator's decision
# (2026-09-24), and the tradeoff is recorded here rather than re-argued: I
# proposed LABS because "test" reads as a STATUS, and a status can change — if
# a TEST box is later promoted to live trading, every trade already written
# keeps a tag that now describes the box wrongly. The operator chose TEST for
# legibility, which is the stronger day-to-day argument. ⚠️ THE CONSEQUENCE TO
# WATCH: if a TEST box goes live, do NOT retag its history — the tag records
# WHICH ENGINE produced the trade, and that never changes. Add a new lineage
# instead.
MAIN = "MAIN"          # options-trader-v4 — the production engine
TEST = "TEST"          # options-trader    — the second engine (SOFI, AAL)
# 🔴 "TEST" IS NOT A LICENCE TO FILTER. The TEST tree is intended to
# SUPERSEDE mainline in place, at which point this tag will label REAL
# PRODUCTION TRADES — correct by this module's own definition, since the tag
# names which ENGINE produced a trade and that never changes, but a trap for
# any reader that reads "TEST" as "not real" and drops it. Nothing here does:
# rows are KEYED by lineage and never excluded, and lineage_block enumerates
# rather than filters. Do not add a "skip TEST" anywhere without the
# operator saying so explicitly — a silently dropped lineage is a silently
# wrong P&L.
UNKNOWN = "UNKN"
LINEAGES = (MAIN, TEST)

# 🔴 THE TEST BOXES FIRST EXISTED ON THIS ET DAY. Before it, every trade in the
# corpus came from MAIN by construction, so an untagged old row is provably
# MAIN. On or after it, an untagged row cannot be dated into an engine.
TEST_EPOCH = "2026-09-25"

# ── which engine each box runs — DECLARED, and a STOPGAP ────────────────────
# 🔑 Neither producer writes a `lineage` field yet. Until they do, this map is
# how a row written TODAY gets attributed, and without it every trade from
# 2026-09-25 onward would read UNKN — correct but useless.
# ⚠️ THIS IS A DECLARATION, NOT AN INFERENCE, and the difference matters. It is
# not "SOFI sounds like a test symbol"; it is the operator's statement of which
# boxes run which engine, written down where it can be grepped and corrected.
# The fleet is small and fully enumerated, so this is the instance map's engine
# column and nothing cleverer.
# 🔴 IT IS SUPERSEDED THE MOMENT THE PRODUCERS TAG. resolve_lineage checks the
# RECORD FIRST, so a tagged row ignores this map entirely — which means this
# becomes vestigial rather than wrong, and that is the point. A box that
# changes engine must be moved here until then.
# ⚠️ A BOX THAT IS IN NEITHER LIST RESOLVES TO UNKN AND IS REPORTED. A new box
# nobody declared must not be silently counted as production (§0.5).
TEST_BOXES = ("SOFI", "AAL")
MAIN_BOXES = ("SPX", "QQQ", "NVDA", "TSLA", "META", "AMZN", "GOOGL", "AMD",
              "AVGO", "MU", "PLTR", "NFLX", "CRM", "UNH", "CVX", "SMH")

LIVE, RETIRED = "live", "retired"

# ── the registry ────────────────────────────────────────────────────────────
# code, status, which engines declare it, and what replaced it if retired.
REGISTRY = {
    "ORBStrategy":          ("ORBS", LIVE,    (MAIN, TEST), None),
    "RunawayContinuation":  ("RWAY", LIVE,    (MAIN, TEST), None),
    "GEXPinButterfly":      ("GEXB", LIVE,    (MAIN, TEST), None),
    "SweepCreditSpread":    ("SWPT", LIVE,    (MAIN, TEST), None),
    "TrendCreditSpread":    ("TCST", LIVE,    (MAIN, TEST), None),
    "IronCondorStrategy":   ("CNDR", LIVE,    (MAIN, TEST), None),
    "LiquidityHunt":        ("HUNT", LIVE,    (TEST,),      None),
    "VOLT":                 ("VOLT", LIVE,    (TEST,),      None),
    "ATPButterfly":         ("ATPB", LIVE,    (TEST,),      None),
    "Breakout":             ("BRKO", LIVE,    (TEST,),      None),
    # ⚠️ RETIRED, NOT DELETED (r240). Both still carry P&L in the corpus —
    # ContinuationStrategy 9 trades, SweepReversal 1 — and both were SUPERSEDED
    # by a live strategy rather than abandoned, which is the fact a reader
    # comparing them needs. Struck from the live set, kept enumerable.
    "SweepReversal":        ("SWPR", RETIRED, (MAIN,), "SweepCreditSpread"),
    "ContinuationStrategy": ("CONT", RETIRED, (MAIN,), "RunawayContinuation"),
}

# ── management plans, NOT strategies ────────────────────────────────────────
# 🔑 Operator, 2026-09-25: *"condor management & roll are not separate
# strategies, they are management plans."* They share the strategy column and
# must keep their codes, but they never own a P&L row of their own — a
# management action adjusts a position some STRATEGY opened.
#
# 🔴 AND NO CONDOR HAS EVER FORMED. The operator: *"previously the first leg
# used to count as part of the condor — while technically correct, a vertical
# spread is not a condor."* He is right, and it is measured. All 8
# IronCondorStrategy rows in the pre-epoch warehouse corpus are SINGLE
# VERTICALS: setup_type is 1h_fork_put_credit_spread (5) or
# 1h_fork_call_credit_spread (3); condor_leg_num is 0 on EVERY row so no second
# leg was ever written; upper_strike, lower_strike and center_strike are None on
# every row; ZERO rows carry a four-leg structure; and two rows' exit_reason
# says "(lone 15%)" in the system's own words.
# ⚠️ SO CNDR's 8 TRADES ARE CREDIT VERTICALS WEARING THE CONDOR'S NAME, and
# anyone reading them as condor performance is measuring something else. This
# also explains CMGT and ROLL cleanly: management has never fired because there
# has never been a condor to manage.
# 📊 CMGT and ROLL: 0 occurrences across 20 fleet bundles / 725 trades, in BOTH
# repos. ⚠️ THE TWO CODES ARE THEREFORE UNEXERCISED — carried because dropping a
# code that has never fired is how it comes back wrong, but nothing has ever
# validated them end to end.
MANAGEMENT = {"CondorManagement": "CMGT", "CreditRoll": "ROLL"}

CODES = {n: v[0] for n, v in REGISTRY.items()}
CODES.update(MANAGEMENT)

UNREGISTERED_PREFIX = "?"


def code(name) -> str:
    """The 4-char code, or a VISIBLY unregistered tag — never blank (r202)."""
    n = str(name or "?").strip()
    if n in CODES:
        return CODES[n]
    return (UNREGISTERED_PREFIX + n[:3].upper()) if n else "?"


def is_registered(name) -> bool:
    return str(name or "").strip() in CODES


def status(name) -> str:
    e = REGISTRY.get(str(name or "").strip())
    return e[1] if e else UNKNOWN


def lineages_for(name):
    e = REGISTRY.get(str(name or "").strip())
    return e[2] if e else ()


def superseded_by(name):
    e = REGISTRY.get(str(name or "").strip())
    return e[3] if e else None


def resolve_lineage(rec, entry_day=None) -> str:
    """The engine that produced a trade.

    🔑 ORDER MATTERS AND IS DELIBERATE:
      1. the record's own tag — always wins, and makes everything below dead
         code the moment both producers ship it;
      2. the DECLARED box->engine map — a fact, not a guess;
      3. the epoch — provable for history, since the TEST boxes did not exist;
      4. UNKN, reported, never silently MAIN.
    ⚠️ Defaulting-to-mine is how a corpus gets contaminated, so there is no
    step that guesses MAIN for a row that could be either.
    """
    rec = rec or {}
    lin = str(rec.get("lineage") or "").strip().upper()
    if lin in LINEAGES:
        return lin
    box = str(rec.get("symbol") or rec.get("box") or "").strip().upper()
    if box in TEST_BOXES:
        return TEST
    if box in MAIN_BOXES:
        return MAIN
    day = str(entry_day or rec.get("_date") or "").strip()[:10]
    if day and day < TEST_EPOCH:
        return MAIN
    return UNKNOWN


def row_key(rec, entry_day=None):
    """(lineage, code) — the ONLY safe key for a per-strategy row."""
    return (resolve_lineage(rec, entry_day), code((rec or {}).get("strategy")))


def label(rec, entry_day=None) -> str:
    """'MAIN/ORBS' — what a rollup row is called."""
    lin, c = row_key(rec, entry_day)
    return f"{lin}/{c}"
