#!/usr/bin/env python3
# day_trader_pro/tests/check_genesis_find.py — v1.0
# v1.0 (2026-09-21) — r411 / OPS.36. THE TOOL §0.7 SENDS EVERY THREAD TO.
#   🔑 GATED BECAUSE DOCTRINE NAMING A COMMAND IS A PROMISE. §25 pointed at a
#   `docs/README.md` that was never ported, FOR MONTHS — the one rule whose
#   job is stopping documents going unread was itself routing to a missing
#   file. §0.7 now names `genesis_find`, so this proves the command resolves,
#   RUNS, and answers the case it was written for.
#   🔴 G2 IS THE ONE THAT MATTERS. A lookup whose empty result renders as
#   silence is worse than no lookup: the reader concludes "nothing is known"
#   from a tool that may simply have failed. That is the plausible-silence
#   class this repo has found in `warehouse_source` ([[S3.31]] — a stream name
#   that does not exist read as "a real, empty result"), in `gex_from_chains`
#   ([[GEX.1]]), and in the fan-out that printed `15/15 succeeded` over fifteen
#   empty fields. A NO MATCH must NAME what it searched.
"""Gate: the ledger search §0.7 mandates exists, runs, and cannot go silent.

G1   it finds the case it was written for (sparse -> OPS.18 / r402)
G2   an absent term prints NO MATCH and names what was searched (§0.5)
G3   it searches BOTH ledgers, not one
G4   it exits 0 on no hits — a lookup is not a gate
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tools", "genesis_find.py")

_fails = []


def ck(tag, ok, msg=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {tag}  {msg}")
    if not ok:
        _fails.append(tag)


def run(*args, timeout=180):
    return subprocess.run([sys.executable, TOOL, *args],
                          capture_output=True, text=True, timeout=timeout)


def main():
    if not os.path.exists(TOOL):
        ck("G1", False, f"tools/genesis_find.py is MISSING at {TOOL}")
        print(f"\nFAILED {len(_fails)}: {', '.join(_fails)}")
        return 1

    # ── G1 — the motivating case. Anchored on the ROW IDS the record holds,
    # not on wording: r402 measured it, OPS.18 carries it. If either stops
    # being found, the tool has stopped answering the question §0.7 asks.
    r = run("sparse")
    out = r.stdout
    ck("G1", "r402" in out and "OPS.18" in out,
       f"finds r402 and OPS.18 for 'sparse' (rc={r.returncode})")

    # ── G2 — §0.5. An absence must be STATED, with its scope.
    r2 = run("zzqqxxnotarealtermanywhere")
    o2 = r2.stdout
    said = "NO MATCH" in o2
    scoped = "rows searched" in o2
    ck("G2", said and scoped,
       "an absent term prints NO MATCH and names how many rows it searched"
       if (said and scoped) else
       f"NO MATCH={said} scope-named={scoped} — a silent empty result is "
       f"indistinguishable from a tool that did not run")

    # ── G3 — both ledgers, because half an answer sends the reader away
    # reassured. GENESIS says WHY (settled); BACKLOG says what is OPEN.
    ck("G3", "GENESIS" in o2 and "BACKLOG" in o2,
       "searches GENESIS and BACKLOG in one call")

    # ── G4 — a lookup is not a gate. Returning non-zero on "no hits" would
    # make it unusable inside any chain and would read as a failure.
    ck("G4", r2.returncode == 0,
       f"exits 0 when nothing matches (rc={r2.returncode})")

    print()
    if _fails:
        print(f"FAILED {len(_fails)}: {', '.join(_fails)}")
        return 1
    print("check_genesis_find: all checks pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
