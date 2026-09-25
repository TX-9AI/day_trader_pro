#!/usr/bin/env python3
"""
tests/check_strategy_registry.py  v1.0
v1.0  2026-09-25  r426 / OPS.50 — TWO ENGINES, ONE CORPUS, ONE REGISTRY.

  🔑 R6 IS THE SHIP-BLOCKER. An untagged trade dated on or after TEST_EPOCH
  must resolve to UNKN, never to MAIN. Defaulting-to-mine is how a corpus gets
  contaminated, and the whole point of the lineage tag is that a row we cannot
  attribute is SAID so rather than quietly added to the production numbers.

  🔴 R5 IS THE DRIFT CATCHER, AND IT IS BORN FROM A DRIFT THAT ALREADY
  HAPPENED. `_STRAT_ABBR` lived in dtp/trade_report.py (8 entries) AND
  otv4/query.py (10); the shared 8 agreed but CondorManagement/CMGT and
  CreditRoll/ROLL existed only in otv4, and nothing noticed. query.py runs on a
  BOX and cannot import control, so a mirrored copy is unavoidable — a gate
  pinning them is the answer, exactly as test_panel_mirror pins UNIVERSE across
  three repos.

  ⚠️ R3 GUARDS A RULE THAT CHANGED MEANING. r202: an unknown strategy is
  TRUNCATED, NEVER DROPPED, because a blank column hides it. True — but
  `n[:4].upper()` was safe with one engine and is not with two, where
  LiquidityHunt -> "LIQU" and Breakout -> "BREA" read as real codes. R3 demands
  the fallback stay non-blank AND stay obviously unregistered.
"""
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

OTV4 = os.environ.get("OT_OTV4_ROOT", os.path.expanduser("~/options-trader-v4"))

# 📊 MEASURED from the SOFI box 2026-09-25, not assumed: the strategy names
# TEST declares. If TEST adds one, R2 goes red until it is registered — which
# is the point, since a new TEST strategy entering the corpus unannounced is
# now the expected case rather than the exotic one (r421 / IronCondorStrategy).
# 📊 From the TEST tree's own admission table (position_manager._DEFAULT_RULES)
# plus every strategy="..." literal and SELECT strategy FROM trades on that box,
# supplied by the peer session 2026-09-25 at OTV4TEST r139 / 252b44d.
# ⚠️ I FIRST READ THESE OFF CLASS NAMES AND TWO WERE WRONG: the strings that
# tree actually WRITES are "VOLT" and "ATPButterfly", not "VoltStrategy" and
# "ATPButterflyStrategy". A registry keyed on a class name matches nothing a
# producer emits, which would have shown every VOLT trade as unregistered.
TEST_DECLARED = ("ORBStrategy", "RunawayContinuation", "GEXPinButterfly",
                 "SweepCreditSpread", "TrendCreditSpread", "IronCondorStrategy",
                 "LiquidityHunt", "VOLT", "ATPButterfly", "Breakout")

_fails = []


def ck(tag, ok, msg=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {tag}  {msg}")
    if not ok:
        _fails.append(tag)


def _mirror_map(path):
    s = open(path, encoding="utf-8", errors="replace").read()
    m = re.search(r"_STRAT_ABBR\s*=\s*\{(.*?)\n\}", s, re.S)
    if not m:
        return None
    return dict(re.findall(r'"([^"]+)"\s*:\s*"([^"]+)"', m.group(1)))


def main():
    try:
        import strategy_registry as SR
    except Exception as exc:                                   # noqa: BLE001
        for t in ("R1", "R2", "R3", "R4", "R5", "R6", "R7"):
            ck(t, False, f"strategy_registry absent ({exc})")
        print(f"\nRED — {len(_fails)} check(s) failed: {' '.join(_fails)}")
        return 1

    # ── R1 — codes are unique and uniformly four characters ────────────────
    codes = SR.CODES
    dupes = {c for c in codes.values() if list(codes.values()).count(c) > 1}
    wrong = {n: c for n, c in codes.items() if len(c) != 4}
    ck("R1", not dupes and not wrong,
       f"{len(codes)} code(s), all unique and 4 chars"
       if not dupes and not wrong
       else f"duplicates={sorted(dupes)} wrong-width={wrong}")

    # ── R2 — every strategy either engine declares is registered ───────────
    missing = []
    try:
        import glob
        decl = set()
        for f in glob.glob(os.path.join(OTV4, "strategy", "*.py")):
            src = open(f, encoding="utf-8", errors="replace").read()
            decl |= set(re.findall(r'name\s*=\s*"([A-Za-z0-9_]+)"', src))
        decl = {d for d in decl if d and d[0].isupper()}
        missing = sorted((decl | set(TEST_DECLARED)) - set(codes))
    except Exception as exc:                                   # noqa: BLE001
        missing = [f"(could not scan: {exc})"]
    ck("R2", not missing,
       "every declared strategy in MAIN's tree and TEST's measured set is "
       "registered" if not missing else f"UNREGISTERED: {missing}")

    # ── R3 — an unknown name renders non-blank AND obviously unregistered ──
    got = SR.code("LiquidityHuntNewThing")
    blank = SR.code("")
    ck("R3", got.startswith(SR.UNREGISTERED_PREFIX) and got != "" and blank != "",
       f"unregistered renders {got!r} (r202: never blank; r426: never a "
       f"plausible code like 'LIQU')")

    # ── R4 — a retired entry names the live strategy that replaced it ──────
    bad = []
    for n, (c, st, lins, sup) in SR.REGISTRY.items():
        if st == SR.RETIRED:
            if not sup or sup not in SR.REGISTRY or SR.REGISTRY[sup][1] != SR.LIVE:
                bad.append(f"{n}->{sup!r}")
    ck("R4", not bad,
       "every RETIRED strategy points at a LIVE successor (r240: struck, not "
       "deleted)" if not bad else f"dangling supersession: {bad}")

    # ── R5 — THE MIRROR. dtp registry == otv4 query.py ─────────────────────
    qp = os.path.join(OTV4, "query.py")
    mirror = _mirror_map(qp) if os.path.exists(qp) else None
    if mirror is None:
        ck("R5", False, f"cannot read _STRAT_ABBR from {qp} — the mirror is "
                        f"unverifiable, which is not the same as agreeing")
    else:
        diff = {k: (codes.get(k), mirror.get(k))
                for k in set(codes) | set(mirror) if codes.get(k) != mirror.get(k)}
        ck("R5", not diff,
           f"dtp registry and otv4/query.py agree on all {len(codes)} codes"
           if not diff else f"DRIFT: {diff}")

    # ── R6 — SHIP-BLOCKER: untagged + on/after TEST_EPOCH is NEVER MAIN ────
    after = SR.resolve_lineage({"strategy": "ORBStrategy"}, "2026-09-26")
    before = SR.resolve_lineage({"strategy": "ORBStrategy"}, "2026-09-10")
    tagged = SR.resolve_lineage({"strategy": "ORBStrategy", "lineage": "TEST"},
                                "2026-09-26")
    ck("R6", after == SR.UNKNOWN and before == SR.MAIN and tagged == SR.TEST,
       f"untagged after {SR.TEST_EPOCH} -> {after} (must be UNKN, never MAIN); "
       f"untagged before -> {before}; tagged -> {tagged}")

    # ── R7 — the rollup keys on (lineage, code), asked of the SOURCE ───────
    tr = os.path.join(ROOT, "trade_report.py")
    src = open(tr, encoding="utf-8", errors="replace").read()
    bare = re.search(r'bucket\(trades,\s*"strategy"\)', src)
    keyed = 'bucket(trades, "_strat_key")' in src
    ck("R7", keyed and not bare,
       "by_strategy buckets on the lineage-qualified key"
       if keyed and not bare
       else f"keyed={keyed} bare_strategy_bucket={bool(bare)} — a bare "
            f"strategy bucket sums MAIN and TEST into one row")

    # ── R8 — every fleet box is declared to an engine ─────────────────────
    # 🔴 THE MAP IS A STOPGAP AND STOPGAPS ROT SILENTLY. Until both producers
    # write a lineage field, an undeclared box's trades read UNKN. That is the
    # correct failure but a useless report, so a box added to UNIVERSE and not
    # classified here must go RED rather than quietly produce UNKN rows. This
    # is the same shape as OPS.47's F4: the fleet grows on its own now.
    try:
        import config
        uni = set(getattr(config, "UNIVERSE", ()))
        declared = set(SR.MAIN_BOXES) | set(SR.TEST_BOXES)
        overlap = set(SR.MAIN_BOXES) & set(SR.TEST_BOXES)
        missing = sorted(uni - declared)
        ck("R8", not missing and not overlap,
           f"all {len(uni)} UNIVERSE box(es) declared to an engine "
           f"(TEST={list(SR.TEST_BOXES)})"
           if not missing and not overlap
           else f"undeclared={missing} in-both={sorted(overlap)} — their trades "
                f"would read UNKN")
    except Exception as exc:                                   # noqa: BLE001
        ck("R8", False, f"cannot compare against config.UNIVERSE ({exc})")

    if _fails:
        print(f"\nRED — {len(_fails)} check(s) failed: {' '.join(_fails)}")
        return 1
    print("\nGREEN — one registry, mirrored, and no row can pool two engines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
