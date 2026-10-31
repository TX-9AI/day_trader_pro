#!/usr/bin/env python3
# day_trader_pro/tools/genesis_find.py — v1.1
# v1.1 (2026-10-31) — dtp r519 / OPS.36. IT SEARCHES THE LEDGERS THAT HOLD THE OPEN WORK. v1.0 read only
#   ~/options-trader-v4/docs/{GENESIS,BACKLOG}.md. Since 2026-10-24 (otv4 r510) the open work is in ~/OTV5/docs/
#   BACKLOG.md and the trading revisions are in ~/OTV5/docs/GENESIS.md; otv4's open rows were replaced by "MOVED to
#   OTV5" pointers, so OPS.18 lost the word "sparse" and check_genesis_find G1 went red - and for anything filed only
#   in OTV5 the tool answered "a real absence" when it had not looked (Saturday brief 2026-10-31 §0.1, R1). Now FOUR
#   ledgers: OTV5 GENESIS and BACKLOG first (the live tree), then otv4's (still the history). Each section names its
#   tree, because revision ids repeat across the two (OTV5 r39 is not otv4 r39). Trees resolve under DTP_OTV5_DIR
#   (default ~/OTV5) and DTP_OTV4_DIR (default ~/options-trader-v4), as eod_analysis and brief_sigint read them. And a
#   ledger that could not be read now voids the "real absence" line by name instead of sitting on stderr beside it.
#   Gate tests/check_genesis_find.py v1.1 G1 (re-anchored), G3, G5. Operator: "Concur" (2026-10-31, R1).
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

OTV4 = os.environ.get("DTP_OTV4_DIR", os.path.expanduser("~/options-trader-v4"))
OTV5 = os.environ.get("DTP_OTV5_DIR", os.path.expanduser("~/OTV5"))

GENESIS_ROW = re.compile(r"^\| \*\*(r[\w.\-]+)\*\* \|")
BACKLOG_ROW = re.compile(r"^\| \*\*([A-Z]+\.\d+)\*\* \|")

# v1.1 — (label, path, row pattern), searched in this order. OTV5 first: it is where the open work and the trading
# revisions have lived since 2026-10-24. otv4 stays: it is the history, and GENESIS there is what SETTLED most of it.
SOURCES = (
    ("OTV5 GENESIS — why it was done (trading tree)", os.path.join(OTV5, "docs", "GENESIS.md"), GENESIS_ROW),
    ("OTV5 BACKLOG — what is open", os.path.join(OTV5, "docs", "BACKLOG.md"), BACKLOG_ROW),
    ("otv4 GENESIS — history", os.path.join(OTV4, "docs", "GENESIS.md"), GENESIS_ROW),
    ("otv4 BACKLOG — history (open rows MOVED to OTV5 2026-10-24)",
     os.path.join(OTV4, "docs", "BACKLOG.md"), BACKLOG_ROW),
)

WIDTH = 150          # characters of context shown per hit
DEFAULT_MAX = 6      # hits per source before the tail is summarised


def _rows(path, pattern):
    """[(id, text)] for every ledger row — one GENESIS revision or BACKLOG row — or None if the file is unreadable."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return [(m.group(1), line) for line in f for m in [pattern.match(line)] if m]
    except OSError as e:
        print(f"  COULD NOT READ {path}: {e}", file=sys.stderr)
        return None


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
    """-> hit count, or None when the ledger could not be read (v1.1: said, never folded into 'no match')."""
    rows = _rows(path, pattern)
    if rows is None:
        print(f"\n=== {label} — NOT SEARCHED ===")
        print(f"  COULD NOT READ {path} (set DTP_OTV5_DIR / DTP_OTV4_DIR)")
        return None
    hits = []
    for rid, text in rows:
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
              f"({len(rows)} rows searched)")
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
    unread = []
    for label, path, pattern in SOURCES:
        got = search(path, pattern, a.terms, label, limit)
        if got is None:
            unread.append(path)
        else:
            n += got
    print()
    if n:
        print(f"  {n} row(s) already touch this. READ THEM before you "
              f"call it a finding.")
    if unread:
        # 🔴 v1.1 — AN UNREAD LEDGER IS NOT AN ABSENCE. Say which, on stdout, where the answer is read.
        print(f"  ⚠️ {len(unread)} of {len(SOURCES)} ledgers NOT READ: {', '.join(unread)}. "
              f"An empty result here is NOT a real absence.")
    elif not n:
        print(f"  Nothing in any of the {len(SOURCES)} ledgers (OTV5 and otv4). That is a real "
              f"absence, not a failed search — every file was read.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
