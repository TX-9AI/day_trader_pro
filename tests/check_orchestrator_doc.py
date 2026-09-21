#!/usr/bin/env python3
# day_trader_pro/tests/check_orchestrator_doc.py — v1.0
# v1.0 (2026-09-20) — r409 / DOC.27. THE MORNING SPOOL-UP'S DOCSTRING SAID IT
#   WAKES TWO BOXES. IT WAKES FIFTEEN, AND THE FILE CONTRADICTED ITSELF.
#   `orchestrator.py` is the file that decides what the fleet does at 09:15 ET.
#   Its prose block carried "DISCRETIONARY SELECTION RETIRED (v0.2.0) ... the
#   orchestrator now wakes ONLY SPX + QQQ; start any additional names by hand"
#   while its OWN CHANGELOG four lines below recorded v0.3.0 RESTORING
#   report-driven selection — and the file is at v0.6.0. Measured at r409:
#   ALWAYS_ON = [SPX, QQQ] + MAX_DISCRETIONARY = 13, so the wake is FIFTEEN,
#   the whole fleet.
#   🔑 WHY IT IS NOT COSMETIC. §32 makes this block mandatory reading BEFORE
#   the file is edited, and §38.2 records that the habit it protects against
#   is reading a summary instead of the code. A reader who believed it would
#   conclude thirteen boxes were down on purpose and start them by hand — or,
#   worse, not notice thirteen boxes that failed to wake, because the document
#   says that is normal. It is the same class as [[OPS.31]]: not a wrong
#   number, a wrong CLAIM, stated where it will be believed.
#
#   SCOPING (§20). O1 and O2 read the PROSE ONLY — the docstring above its
#   `Changelog:` marker. The changelog legitimately records "v0.2.0 — retire
#   discretionary selection" as history, and §5 requires it to keep saying so,
#   so a canary over the whole docstring would fire on the record it is the
#   version discipline's job to preserve.
#   🔑 AND O1 IS ANCHORED ON THE CODE, NOT ON A STRING. It asks the AST
#   whether `main()` actually calls `_load_selection()`, and only then judges
#   the prose. A grep-only check would pin today's wording; this one goes red
#   the day the CODE and the DESCRIPTION diverge, whichever of the two moved.
"""Gate: orchestrator.py's mandatory-reading block must describe the wake
the code performs.

O1   prose does not claim baseline-only while main() loads a selection
O2   prose names the governing constants rather than a frozen symbol list
O3   CONTROL — the constants exist and resolve (green at HEAD by design)
"""
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "orchestrator.py")

rc = 0


def report(tag, ok, msg):
    global rc
    print(f"{'PASS' if ok else 'FAIL'} {tag}: {msg}")
    if not ok:
        rc = 1


def main():
    global rc
    if not os.path.exists(SRC):
        report("O1", False, f"orchestrator.py not found at {SRC}")
        return 1
    src = open(SRC, encoding="utf-8", errors="replace").read()
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        report("O1", False, f"orchestrator.py does not parse: {e}")
        return 1

    doc = ast.get_docstring(tree) or ""
    prose = re.split(r"\n\s*Changelog:", doc)[0]
    # 🔴 §20 FIRED ON THIS GATE'S OWN FIRST RUN, WHICH IS WHY THE SCOPE IS HERE.
    # §5 requires the corrected block to RECORD what it superseded, and an
    # honest record of "it used to say: wakes ONLY SPX + QQQ" necessarily
    # contains the exact tokens O1 matches. The canary is wrong, not the prose
    # (§20's corollary), so a paragraph MARKED SUPERSEDED is excluded — the
    # struck record is history under r240's precedent, not a live claim.
    # ⚠️ BORN-RED IS UNAFFECTED: the paragraph this gate was written to catch
    # carried no such marker, and re-proving that against HEAD is part of the
    # revision rather than an assumption.
    prose = "\n\n".join(
        para for para in prose.split("\n\n")
        if "SUPERSEDED" not in para.upper()
    )

    # Does the CODE select, or not? Asked of the AST, never of the prose.
    selects = any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "_load_selection"
        for n in ast.walk(tree)
    )

    # ── O1 — the prose may not deny what the code does ─────────────────────
    denies = re.findall(
        r"(?i)(SELECTION RETIRED|only\s+SPX\s*\+\s*QQQ|"
        r"wakes?\s+ONLY\s|baseline[- ]only\s+wake\b|no model is called)",
        prose)
    if selects:
        report("O1", not denies,
               "prose agrees with the code: main() selects and the prose "
               "does not deny it"
               if not denies else
               f"main() CALLS _load_selection() but the prose claims "
               f"{sorted(set(d.strip() for d in denies))} — the file "
               f"contradicts itself")
    else:
        report("O1", not prose.strip() == "",
               "code does NOT select; prose must say so (inverted case)")

    # ── O2 — name the constants, not a frozen list ─────────────────────────
    names = ("ALWAYS_ON" in prose) and ("MAX_DISCRETIONARY" in prose)
    report("O2", names,
           "prose names ALWAYS_ON and MAX_DISCRETIONARY, so it cannot rot "
           "when either moves"
           if names else
           "prose does not name both governing constants — a hardcoded "
           "wake list rots the next time either changes")

    # ── O3 — CONTROL. Green at HEAD by design; it pins the premise. ────────
    cfg = os.path.join(ROOT, "config.py")
    try:
        ctext = open(cfg, encoding="utf-8", errors="replace").read()
        always = re.search(r"^ALWAYS_ON\s*=\s*(\[[^\]]*\])", ctext, re.M)
        maxd = re.search(r"^MAX_DISCRETIONARY\s*=\s*(\d+)", ctext, re.M)
        if always and maxd:
            n = len(ast.literal_eval(always.group(1))) + int(maxd.group(1))
            report("O3", True,
                   f"CONTROL — ALWAYS_ON={always.group(1)} + "
                   f"MAX_DISCRETIONARY={maxd.group(1)} => wakes {n}")
        else:
            report("O3", False,
                   "CONTROL — could not read ALWAYS_ON / MAX_DISCRETIONARY "
                   "from config.py; the premise O2 rests on is unreadable")
    except OSError as e:
        report("O3", False, f"CONTROL — config.py unreadable: {e}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
