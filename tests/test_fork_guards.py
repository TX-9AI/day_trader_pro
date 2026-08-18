#!/usr/bin/env python3
"""
tests/test_fork_guards.py — the fleet holds two repos now. v1.0
v1.0 — 2026-08-18 — INITIAL.

Two guards, both exercised by CALLING the decision function and asserting on
the decision it returns — never by grepping the source:

  1. wake_and_bake.verify_convergence — a heterogeneous fleet must read GREEN
     when each repo group is internally converged, and RED when a group
     disagrees, a box fails, or a box never reports.
  2. fleet.repoint_refusal — an unscoped repoint across a mixed-remote fleet
     must be REFUSED and must name the box that would lose its remote.

Also asserts the property that makes the fork deployable at all: BAKE names no
repo. That one IS a source check, deliberately — it is an assertion about what
must NOT appear in a command string, and there is no way to ask it of a
running fleet from here.

Run:  cd ~/day_trader_pro && python3 tests/test_fork_guards.py
Deliberate-failure proof: OT_GUARD_SELFTEST=1 inverts one expectation; the
suite must go red.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fleet                       # noqa: E402
import wake_and_bake as wb         # noqa: E402

FAILS = []
SELFTEST = os.environ.get("OT_GUARD_SELFTEST", "0") == "1"


def check(name, ok, detail=""):
    if not ok:
        FAILS.append(name)
    print(f"  {'✅' if ok else '❌'} {name}{('  — ' + detail) if detail else ''}")


V3, SMC = "options_trader_v3", "options_trader_smc"


def main():
    # ── 1. VERIFY, grouped by repo ─────────────────────────────────────────
    heads = {s: "aaaa1111" for s in ("SPX", "NVDA", "AMD")}
    heads["QQQ"] = "bbbb2222"
    repos = {"SPX": V3, "NVDA": V3, "AMD": V3, "QQQ": SMC}

    ok, lines, note = wb.verify_convergence(heads, repos, [], 4)
    if SELFTEST:
        ok = not ok
    check("mixed fleet, each group internally converged → GREEN", ok, note)
    check("and the note names both groups",
          "options_trader_smc" in note and "options_trader_v3" in note, note)

    # a real divergence inside a group is still red
    bad = dict(heads)
    bad["AMD"] = "cccc3333"
    ok2, lines2, note2 = wb.verify_convergence(bad, repos, [], 4)
    check("one box off inside a group → RED", not ok2, note2)
    check("and the failing REPO is named, not just the box",
          any(V3 in t for _l, t in lines2 if _l == "err"))

    # a box that never answered is still red, even if the rest agree
    short = {k: v for k, v in heads.items() if k != "NVDA"}
    ok3, _l3, note3 = wb.verify_convergence(short, repos, [], 4)
    check("a box that did not report → RED", not ok3, note3)

    # a bake failure is still red
    ok4, _l4, _n4 = wb.verify_convergence(heads, repos, ["AMD"], 4)
    check("a bake failure → RED", not ok4)

    # single-repo fleet still behaves exactly as before
    ok5, _l5, note5 = wb.verify_convergence(
        {s: "aaaa1111" for s in ("SPX", "QQQ")},
        {"SPX": V3, "QQQ": V3}, [], 2)
    check("homogeneous fleet unchanged → GREEN", ok5, note5)

    # ── 2. repoint refusal ────────────────────────────────────────────────
    rmap = {"SPX": V3, "NVDA": V3, "QQQ": SMC}

    msg = fleet.repoint_refusal(rmap, V3, only=None, all_repos=False)
    check("unscoped repoint on a mixed fleet → REFUSED", msg is not None)
    check("and the refusal names the box that would be overwritten",
          bool(msg) and "QQQ" in msg, (msg or "").splitlines()[-3:][0]
          if msg else "")
    check("and names what it would lose",
          bool(msg) and SMC in msg)

    check("scoped repoint (--only) → allowed",
          fleet.repoint_refusal(rmap, V3, only=["QQQ"], all_repos=False) is None)
    check("explicit --all-repos → allowed",
          fleet.repoint_refusal(rmap, V3, only=None, all_repos=True) is None)
    check("single-repo fleet → allowed (guard is inert pre-fork)",
          fleet.repoint_refusal({"SPX": V3, "QQQ": V3}, V3, None, False) is None)
    check("an UNKNOWN remote counts as its own group → REFUSED",
          fleet.repoint_refusal({"SPX": V3, "QQQ": "?"}, V3, None, False)
          is not None)

    # ── 3. BAKE still names no repo ───────────────────────────────────────
    check("BAKE_CMD contains no repo URL or name",
          "github.com" not in wb.BAKE_CMD
          and "options_trader" not in wb.BAKE_CMD)
    check("BAKE_CMD reports the remote so VERIFY can group by it",
          "git remote get-url origin" in wb.BAKE_CMD)

    print()
    if FAILS:
        print(f"fork_guards: {len(FAILS)} FAILED — " + "; ".join(FAILS))
        return 1
    print("fork_guards: ALL PASS (verify grouping · repoint refusal · "
          "bake names no repo)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
