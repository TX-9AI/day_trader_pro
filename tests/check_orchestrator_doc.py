#!/usr/bin/env python3
# day_trader_pro/tests/check_orchestrator_doc.py — v1.1
# v1.1 (2026-09-24) — r423 / OPS.47. REPOINTED: the wake is governed by
#   FLEET_TAG_KEY / FLEET_TAG_VALUE now, so O2 demands the prose name THOSE
#   rather than the retired baseline constants, and O3 becomes a CREEP
#   DETECTOR — it goes red if the wake list is ever derived from UNIVERSE
#   again. ⚠️ MY FIRST CREEP PREDICATE WAS WRONG AND IS RECORDED RATHER THAN
#   TIDIED: it tested whether any line mentioned both names, which flagged the
#   entirely correct reporting line that NAMES boxes missing from the brief.
#   It now tests the ASSIGNMENT. A substring is not a predicate; this was the
#   fourth checker self-match of the session (section 20).
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

    # ── O2 — name the constants THAT NOW GOVERN ────────────────────────────
    # 🔴 r423 — REPOINTED, NOT LOOSENED. This check asked for ALWAYS_ON and
    # MAX_DISCRETIONARY because those decided the wake. They no longer do: the
    # fleet is DISCOVERED by FLEET_TAG_KEY=FLEET_TAG_VALUE and config.UNIVERSE
    # is not consulted at all. Leaving the old assertion would have pinned the
    # prose to a policy the operator retired — a gate can rot the same way a
    # docstring can, and this one would have insisted the file keep describing
    # something untrue. The behavioural half now lives in
    # check_fleet_discovery.py F1-F5, which is stronger than any prose test.
    names = ("FLEET_TAG_KEY" in prose) or ("FLEET_TAG_VALUE" in prose)
    report("O2", names,
           "prose names the tag constants that govern the wake, so it cannot "
           "rot when they move"
           if names else
           "prose does not name FLEET_TAG_KEY/FLEET_TAG_VALUE — the wake is "
           "discovered by tag and a doc that does not say so rots on the next "
           "change")

    # ── O3 — CONTROL. The premise O2 now rests on is the TAG, not a count. ──
    cfg = os.path.join(ROOT, "config.py")
    try:
        ctext = open(cfg, encoding="utf-8", errors="replace").read()
        k = re.search(r"^FLEET_TAG_KEY\s*=", ctext, re.M)
        v = re.search(r"^FLEET_TAG_VALUE\s*=", ctext, re.M)
        # ⚠️ AND THE UNIVERSE MUST NOT BE BACK IN THE WAKE PATH. If a future
        # edit re-introduces config.UNIVERSE as the wake source, this says so.
        src = open(os.path.join(ROOT, "orchestrator.py"),
                   encoding="utf-8", errors="replace").read()
        code = [ln for ln in src.splitlines()
                if ln.strip() and not ln.lstrip().startswith("#")]
        # ⚠️ THE ASSIGNMENT, NOT THE MENTION. My first cut tested
        # `"wake_list" in ln and "UNIVERSE" in ln`, which flagged the perfectly
        # correct reporting line
        #     _unlisted = [s for s in wake_list if s not in config.UNIVERSE]
        # — a check that NAMES boxes missing from the brief. Creep means
        # wake_list is DERIVED from the universe, so the test is an assignment
        # to wake_list whose right-hand side mentions it. Fourth self-match of
        # this session; the lesson is that a substring is never a predicate.
        creep = bool(re.search(r"^\s*wake_list\s*=\s*[^#\n]*UNIVERSE",
                               "\n".join(code), re.M))
        if k and v and not creep:
            report("O3", True,
                   "CONTROL — config.py defines FLEET_TAG_KEY/FLEET_TAG_VALUE "
                   "and orchestrator does not derive wake_list from UNIVERSE")
        else:
            report("O3", False,
                   f"CONTROL — tag constants present={bool(k and v)}, "
                   f"UNIVERSE back in the wake path={creep}")
    except OSError as e:
        report("O3", False, f"CONTROL — config.py unreadable: {e}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
