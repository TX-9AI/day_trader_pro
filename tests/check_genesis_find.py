#!/usr/bin/env python3
# day_trader_pro/tests/check_genesis_find.py — v1.1
# v1.1 (2026-10-31) — dtp r519 / OPS.36. G1 IS RE-ANCHORED WHERE THE ROWS NOW LIVE, AND STAYS A REAL TEST. It
#   asserted `sparse` -> r402 and OPS.18 anywhere in the output; otv4 r510 (10-24) replaced OPS.18's otv4 row with a
#   "MOVED to OTV5" pointer, so G1 went red (Saturday brief 2026-10-31 §0.1). OPS.18's text is in OTV5 docs/
#   BACKLOG.md, so G1 now demands OPS.18 IN THE OTV5 BACKLOG SECTION and r402 IN THE otv4 GENESIS SECTION - the
#   live tree and the history, both. G3 demands all four ledgers. G5 (new, hermetic): fixture trees under DTP_OTV5_DIR
#   / DTP_OTV4_DIR - a term filed only in OTV5's backlog is found there, and a missing ledger voids the "real
#   absence" line on stdout. Born red on 5d1ff71 at G1, G3, G5. Operator: "Concur" (2026-10-31, R1).
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

G1   it finds the case it was written for (sparse -> OPS.18 in OTV5's BACKLOG, r402 in otv4's GENESIS) (v1.1)
G2   an absent term prints NO MATCH and names what was searched (§0.5)
G3   it searches FOUR ledgers: GENESIS and BACKLOG in OTV5 and in otv4 (v1.1)
G4   it exits 0 on no hits — a lookup is not a gate
G5   hermetic (v1.1): a row filed only in OTV5's backlog is found there; a ledger it cannot read is named on stdout
     and the "real absence" line is not printed
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tools", "genesis_find.py")

_fails = []


def ck(tag, ok, msg=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {tag}  {msg}")
    if not ok:
        _fails.append(tag)


def run(*args, timeout=180, env=None):
    return subprocess.run([sys.executable, TOOL, *args],
                          capture_output=True, text=True, timeout=timeout,
                          env=env)


def sections(out):
    """{section header line: body text} from the tool's `=== <label> — ... ===` blocks."""
    got, cur = {}, None
    for line in out.splitlines():
        m = re.match(r"^=== (.*?) — ", line)
        if m:
            cur = line
            got[cur] = ""
        elif cur:
            got[cur] += line + "\n"
    return got


def body_of(secs, prefix):
    return "".join(v for k, v in secs.items() if k.startswith("=== " + prefix))


def main():
    if not os.path.exists(TOOL):
        ck("G1", False, f"tools/genesis_find.py is MISSING at {TOOL}")
        print(f"\nFAILED {len(_fails)}: {', '.join(_fails)}")
        return 1

    # ── G1 — the motivating case. Anchored on the ROW IDS the record holds,
    # not on wording: r402 measured it, OPS.18 carries it. If either stops
    # being found, the tool has stopped answering the question §0.7 asks.
    # v1.1 — and anchored on WHERE each row lives now: OPS.18's text moved to OTV5's backlog (otv4 r510 left a
    # "MOVED to OTV5" pointer), r402 is otv4 history. A tool reading one tree fails it.
    r = run("sparse")
    secs = sections(r.stdout)
    in5 = re.search(r"^\s+OPS\.18\s", body_of(secs, "OTV5 BACKLOG"), re.M) is not None
    in4 = re.search(r"^\s+r402\s", body_of(secs, "otv4 GENESIS"), re.M) is not None
    ck("G1", in5 and in4,
       f"'sparse' finds OPS.18 in the OTV5 BACKLOG and r402 in the otv4 GENESIS "
       f"(OTV5 OPS.18={in5}, otv4 r402={in4}, rc={r.returncode})")

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
    want = ("OTV5 GENESIS", "OTV5 BACKLOG", "otv4 GENESIS", "otv4 BACKLOG")
    heads = list(sections(o2))
    have = [w for w in want if any(h.startswith("=== " + w) for h in heads)]
    ck("G3", len(have) == len(want),
       f"searches GENESIS and BACKLOG in OTV5 and otv4 in one call (found {have})")

    # ── G4 — a lookup is not a gate. Returning non-zero on "no hits" would
    # make it unusable inside any chain and would read as a failure.
    ck("G4", r2.returncode == 0,
       f"exits 0 when nothing matches (rc={r2.returncode})")

    # ── G5 (v1.1) — hermetic. Fixture trees, so it cannot pass on live ledger wording.
    tmp = tempfile.mkdtemp(prefix="gfind_")
    try:
        t5, t4 = os.path.join(tmp, "OTV5"), os.path.join(tmp, "otv4")
        for t in (t5, t4):
            os.makedirs(os.path.join(t, "docs"))
        with open(os.path.join(t5, "docs", "BACKLOG.md"), "w") as f:
            f.write("| **ZZT.1** | the qqzzfixtureterm row, filed in OTV5 only | ⬜ |\n")
        with open(os.path.join(t5, "docs", "GENESIS.md"), "w") as f:
            f.write("| **r1** | an OTV5 revision | x |\n")
        with open(os.path.join(t4, "docs", "GENESIS.md"), "w") as f:
            f.write("| **r1** | an otv4 revision | x |\n")
        # otv4 BACKLOG deliberately absent: the unreadable-ledger case.
        env = dict(os.environ, DTP_OTV5_DIR=t5, DTP_OTV4_DIR=t4)
        r5 = run("qqzzfixtureterm", env=env)
        found = re.search(r"^\s+ZZT\.1\s", body_of(sections(r5.stdout), "OTV5 BACKLOG"), re.M) is not None
        r6 = run("zzqqxxnotarealtermanywhere", env=env)
        named = "NOT READ" in r6.stdout and os.path.join(t4, "docs", "BACKLOG.md") in r6.stdout
        no_false = "real absence, not" not in r6.stdout
        ck("G5", found and named and no_false and r6.returncode == 0,
           f"fixture: OTV5-only row found={found}; missing otv4 BACKLOG named on stdout={named}; "
           f"no 'real absence' claim={no_false}; rc={r6.returncode}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if _fails:
        print(f"FAILED {len(_fails)}: {', '.join(_fails)}")
        return 1
    print("check_genesis_find: all checks pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
