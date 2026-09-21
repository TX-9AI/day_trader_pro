#!/usr/bin/env python3
# day_trader_pro/tools/genesis_find.py — v1.0
# v1.0 (2026-09-21) — r411 / OPS.36. HAS THIS ALREADY BEEN FOUND? THE QUESTION
#   COST 188k TOKENS TO ASK, SO IT DID NOT GET ASKED.
#   🔴 THE FAILURE THIS EXISTS FOR, IN FULL, BECAUSE IT IS MINE. On 2026-09-21
#   I reported `docs/` and `tests/` reaching the boxes as a live finding, off a
#   `git diff --name-status` listing from a bake. [[OPS.18]] had SETTLED that
#   three weeks of revisions earlier — r402 measured it by fan-out (AMD, 168
#   test files, `core.sparseCheckout` unset), r407 established the cause, r303
#   had already examined sparse granularity. I had READ OPS.18's row the night
#   before; its title says "THE COSMETIC ARTEFACT HYPOTHESIS IS REFUTED,
#   MEASURED". And my evidence was worthless either way: a sparse checkout
#   still prints `M docs/BACKLOG.md` in a diff while `docs/` is absent from its
#   working tree — driven in a throwaway repo, not reasoned.
#   🔑 SO THE DEFECT WAS NOT IGNORANCE OF THE RECORD. I had the record. The
#   defect was that CHECKING cost a re-read of a 188k-token ledger at the
#   moment of speaking, and a cost that high converts a rule into a wish.
#   §0.6 in one line: a rule changes the odds, a cheap action changes the
#   outcome. This makes the check three seconds.
#   ⚠️ IT SEARCHES BOTH LEDGERS BY DESIGN. GENESIS says WHY a thing was done,
#   which is what tells you a question is SETTLED; BACKLOG says what is OPEN.
#   "Has this been found before" needs both, and a tool that answered half
#   would send the reader away reassured.
#   ⚠️ AND IT NEVER SAYS "NO". A term with no hits prints NO MATCH and names
#   what it searched, because an empty result that looks like an answer is the
#   plausible-silence class this repo keeps finding in its own instruments
#   (§0.5, [[S3.31]], [[GEX.1]]).
"""Search the ledgers before claiming a finding.

    python3 tools/genesis_find.py sparse
    python3 tools/genesis_find.py "US/Eastern" tzdata --all
"""
import argparse
import os
import re
import sys

OTV4 = os.path.expanduser("~/options-trader-v4")
GENESIS = os.path.join(OTV4, "docs", "GENESIS.md")
BACKLOG = os.path.join(OTV4, "docs", "BACKLOG.md")

WIDTH = 150          # characters of context shown per hit
DEFAULT_MAX = 6      # hits per source before the tail is summarised


def _rows(path, pattern):
    """(id, text) for every ledger row — one GENESIS revision or BACKLOG row."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                m = pattern.match(line)
                if m:
                    yield m.group(1), line
    except OSError as e:
        print(f"  COULD NOT READ {path}: {e}", file=sys.stderr)


def _score(text, terms):
    low = text.lower()
    return sum(low.count(t.lower()) for t in terms)


def _excerpt(text, terms):
    """The window around the FIRST hit — the sentence, not the row's opening."""
    low = text.lower()
    pos = min((low.find(t.lower()) for t in terms if t.lower() in low),
              default=0)
    start = max(0, pos - WIDTH // 3)
    out = text[start:start + WIDTH].replace("\n", " ")
    return ("…" if start else "") + re.sub(r"\s+", " ", out).strip() + "…"


def search(path, pattern, terms, label, limit):
    hits = []
    for rid, text in _rows(path, pattern):
        s = _score(text, terms)
        if s:
            hits.append((s, rid, text))
    hits.sort(key=lambda h: -h[0])
    print(f"\n=== {label} — {len(hits)} row(s) mention "
          f"{' / '.join(terms)} ===")
    if not hits:
        # 🔑 NEVER A BARE EMPTY LINE. See the header: an absence that renders
        # as silence is indistinguishable from a tool that did not run.
        print(f"  NO MATCH in {os.path.basename(path)} "
              f"({sum(1 for _ in _rows(path, pattern))} rows searched)")
        return 0
    for s, rid, text in hits[:limit]:
        print(f"  {rid:<10} ({s:>2} hit{'s' if s > 1 else ' '})  "
              f"{_excerpt(text, terms)}")
    if len(hits) > limit:
        print(f"  … and {len(hits) - limit} more: "
              f"{', '.join(h[1] for h in hits[limit:limit + 12])}")
    return len(hits)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("terms", nargs="+")
    ap.add_argument("--all", action="store_true",
                    help="show every hit, not just the strongest")
    a = ap.parse_args()
    limit = 10_000 if a.all else DEFAULT_MAX

    n = 0
    n += search(GENESIS, re.compile(r"^\| \*\*(r[\w.\-]+)\*\* \|"),
                a.terms, "GENESIS — why it was done", limit)
    n += search(BACKLOG, re.compile(r"^\| \*\*([A-Z]+\.\d+)\*\* \|"),
                a.terms, "BACKLOG — what is open", limit)
    print()
    if n:
        print(f"  {n} row(s) already touch this. READ THEM before you "
              f"call it a finding.")
    else:
        print("  Nothing in either ledger. That is a real absence, not a "
              "failed search — both files were read.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
