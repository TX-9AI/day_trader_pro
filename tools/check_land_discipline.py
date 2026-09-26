#!/usr/bin/env python3
# day_trader_pro/tools/check_land_discipline.py — v1.3
# v1.3 (2026-09-26) — dtp r435. NEW CHECK **LEDGER**, AND ITS ABSENCE HAD
#   ALREADY COST EIGHT ROWS. v1.1's capability detection is right in principle
#   — absent artifact => SKIP and say so by name, so dtp never cries wolf over
#   files it does not carry. ⚠️ BUT IT ASSUMED THE LEDGER IS A PER-REPO
#   ARTEFACT AND IT IS NOT: the revision sequence is SHARED across both trees
#   (dtp r431 and otv4 r430 are the same counter) while GENESIS.md lives only
#   in otv4. So dtp's GENESIS check SKIPPED on every run, structurally, and
#   nothing could ever notice a dtp revision landing with no ledger row.
#   📊 FOUND BY THE OPERATOR, NOT BY THIS FILE: *"how did you commit them
#   without adding to the Genesis? Don't you use a checker?"* — after r431,
#   r432 and r433 were committed with no rows. 🔴 AND ITS FIRST RUN FOUND FIVE
#   MORE, going back weeks: r316, r392, r394, r396 and r418. r394 IS THE
#   SATURDAY BRIEF ITSELF, the mechanism whose unreadable ledger produced a
#   false alarm to the operator the same night.
#   🔑 IT WORKS IN HOOK MODE, WHICH THE --rev CHECK CANNOT. A pre-commit hook
#   never knows the revision it is about to create, so the row for THIS commit
#   is genuinely uncheckable there — but every EARLIER revision is already in
#   the log, so COMPLETENESS is answerable at any time with no --rev. That is
#   why it is retrospective rather than one more assertion about the commit in
#   hand. Bounded by the ledger's own floor so revisions predating the ledger
#   are not flagged (the CV.1 wolf-cry this file exists to avoid).
# v1.2 (2026-09-11) — dtp r360 / LAND.8. ONE EXEMPTION TO THE NO-SOURCE RULE:
#   an index-only untrack of an ignored path. `git rm --cached <f>` diffs as
#   nothing but deletions, so the rule refused it, and the only way through was
#   `--no-verify` — which disables EVERY check, including the ones that matter.
#   A rule whose sole escape hatch is "turn off all the rules" gets used that
#   way. Measured on `logs/eod_conductor.log` (LAND.2). NARROW BY CONSTRUCTION:
#   every deleted path must ALSO be ignored now AND still exist on disk, so
#   removing a real module still fails and a deletion that also removes the
#   file is not an untrack.
# v1.1 (2026-08-30) — otv4 r194 / dtp r232. GENESIS ROWS MAY NOT CONTAIN A BARE
#   HTML TAG. Operator: "something broke & the new additions are nesting now."
#   🔴 TWO ROWS CONTAINED THE LITERAL STRING <table> — r184's
#   raw/derived_<table>/ and r191's raw/<table>/dt=/sym=/. GitHub renders raw
#   HTML inside table cells, so each one OPENED AN HTML TABLE that never
#   closed: r184 swallowed r185-r191, and r191 swallowed r192. The ledger's
#   own rows became children of the rows above them.
#   🔑 BOTH WERE MINE AND THE PROSE WAS CORRECT. Angle-bracket placeholders
#   are this project's idiom — <date>, <SYM>, <prefix>, <Strategy>. Only
#   SOME of them collide with a real element name, so the failure is
#   invisible in the source and shows only on the rendered page, which nobody
#   re-reads after landing.
#   ⚠️ THE SCAN COVERS EVERY ROW AND RUNS EVEN IN HOOK MODE. A ledger that is
#   already broken stays broken silently otherwise, and the row's own number
#   is not needed to see that the PAGE is malformed.
#   ⚠️ NON-HTML PLACEHOLDERS STAY LEGAL. Flagging <date> would make this cry
#   wolf on the repo's own idiom, and a check that cries wolf trains you to
#   skip red runs. Only names GitHub actually renders are refused; the fix is
#   a backtick.
# v1.0 (2026-08-29) — r183. Operator's instruction after r182 landed: "when
#   you're landing files, have a check that the Genesis line is added, the
#   write map is updated and the file map is updated ... Also check that each
#   file's versioning and changelog are being bumped each time."
#
#   ONE TOOL, BOTH REPOS. It lives here because day_trader_pro is the control
#   repo, is always present on control, and — unlike options-trader-v4 — has
#   NO land gate of its own, so its version headers have never been checked by
#   anything. Pointing one implementation at both beats two that drift.
#
#   ⚠️ IT DETECTS CAPABILITY, IT DOES NOT ASSUME IT. otv4 carries GENESIS.md,
#   FILE_MAP.md and WRITE_MAP.md; dtp carries none of the three. A checker that
#   demanded all three everywhere would fail dtp on every run for a reason that
#   is not a defect — the CV.1 failure, where a check that cries wolf trains
#   the reader to skip red runs. Absent artifact => that check reports SKIP and
#   says so by name. "Not applicable" and "passed" must never look alike.
#
# 🔴 THE CHECK THIS EXISTS FOR IS D (BUMP), AND IT IS THE ONE NOTHING COVERED.
#   The repo's standing rule since 2026-07-23 is that the version lives in TWO
#   places — the TITLE line and the newest dated CHANGELOG entry — and that the
#   two must agree. Both drifts have been seen for real: title lines stale
#   across the whole dtp repo while changelogs advanced, and the devtools
#   banner reading v1.14 against a v1.19 header. Nothing has ever verified it.
#
# ⚠️ A HEADER BUMP WITH NO EDIT IS NOT WHAT THIS PROVES, AND IT MUST NOT CLAIM
#   TO. This asserts the version MOVED and that a dated entry describes it. It
#   cannot tell whether the entry is TRUE. The land command's own content gate
#   (a positive grep for a distinctive line from the real change, plus a
#   negative grep that the superseded code is gone) is what proves the edit
#   happened; this proves the bookkeeping did. Two different claims — running
#   this one and calling the delivery verified would be exactly the laundered
#   green WORKING_AGREEMENT §18 warns about.
#
# Run:  python3 tools/check_land_discipline.py --repo ~/options-trader-v4 --rev r183
#       python3 tools/check_land_discipline.py --repo ~/day_trader_pro
#       python3 tools/check_land_discipline.py --selftest

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile

# Generated or append-only: they carry no version header of their own and are
# rewritten wholesale by their generator or by the land command.
NO_BUMP = {
    "docs/FILE_MAP.md",
    "docs/WRITE_MAP.md",
    "docs/GENESIS.md",
    "FILE_MAP.md",
    "WRITE_MAP.md",
}

TEXT_EXT = {".py", ".sh", ".md"}

# A version token: v1.0, v4.26, v0.7.0
VER = r"v(\d+(?:\.\d+)+)"
DATE = r"\d{4}-\d{2}-\d{2}"

# A changelog entry names a version AND a date on the same line. Every idiom in
# both repos is covered by this pair, verified against the real trees:
#   otv4    "v4.4  2026-08-28  r180 — ..."
#   dtp     "# v1.3   (2026-08-03) — ..."
#   dtp     "# v0.7.0 (2026-08-18) — ..."
#   md      "**v1.21 · 2026-08-28 · r181 — ...**"
CHANGELOG = re.compile(r"(?:^|[\s*#|])" + VER + r"\s*[\s·(\[—-]\s*(" + DATE + r")")

# Names GitHub renders as an element inside a table cell. Kept DELIBERATELY
# SHORT: this repo writes <date>, <SYM>, <prefix>, <Strategy> constantly and
# none of those is HTML. Only a collision with a real element name breaks the
# page, so only those are refused.
HTML_TAGS = re.compile(r"<\s*/?\s*([a-zA-Z][a-zA-Z0-9]*)\s*/?\s*>")
HTML_ELEMENTS = {
    "table", "thead", "tbody", "tfoot", "tr", "td", "th", "caption", "colgroup",
    "col", "div", "span", "p", "ul", "ol", "li", "dl", "dt", "dd", "pre", "code",
    "blockquote", "a", "img", "br", "hr", "em", "strong", "b", "i", "u", "s",
    "sub", "sup", "kbd", "samp", "var", "details", "summary", "figure", "form",
    "input", "button", "select", "option", "label", "iframe", "script", "style",
    "h1", "h2", "h3", "h4", "h5", "h6",
}

HEAD_LINES = 12        # a title line lives at the very top or it is not a title
# 🔴 A CHANGELOG ENTRY LIVES IN THE HEADER BLOCK AND NOWHERE ELSE. v1.0
# scanned the first 400 lines, which swept in this file's OWN selftest
# fixtures — they write a `v1.1 (2026-02-01)` line because they are testing
# changelog parsing — and then refused a real v1.1 bump as "already existed
# at HEAD". A scanner whose window is a LINE COUNT reads code as
# documentation. The header ends at the first line that is neither shebang,
# comment, docstring nor blank.
BODY_LINES = 400       # hard ceiling only; _header_end() is the real bound


def sh(args, cwd, check=False):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if check and p.returncode != 0:
        raise RuntimeError(" ".join(args) + " -> " + (p.stderr or "")[:200])
    return p


def title_version(text: str, rel: str):
    """The version on the TITLE line: a line near the top naming this file.

    ⚠️ ANCHORED ON THE FILENAME, NOT ON A BARE `vX.Y` PATTERN. That is the r65
    lesson made mechanical: r65's bumper matched a version inside an
    ILLUSTRATIVE COMMENT — a quoted example header — took it for the module's
    own, and spliced a changelog into the middle of a comment line. Requiring
    the file's own basename on the line makes a quoted example unmatchable.
    """
    base = os.path.basename(rel)
    for ln in text.splitlines()[:HEAD_LINES]:
        if base in ln:
            m = re.search(VER, ln)
            if m:
                return m.group(1)
    return None


def _header_end(lines) -> int:
    """Index of the first line past the header block.

    The header is the leading run of shebang, comment, docstring and blank
    lines. Everything after it is code, and code is not a changelog however
    much a fixture string may look like one.
    """
    in_doc = False
    marks = ('"""', "'''")
    for i, ln in enumerate(lines[:BODY_LINES]):
        st = ln.strip()
        if i == 0 and st.startswith('#!'):
            continue
        if st.startswith(marks):
            in_doc = not (len(st) > 3 and st.endswith(marks))
            continue
        if in_doc or st.startswith('#') or not st:
            continue
        return i
    return min(len(lines), BODY_LINES)


def changelog_versions(text: str, rel: str = ""):
    """Every (version, date) pair in header order — newest first by convention.

    {W} THE WINDOW DEPENDS ON THE FILE KIND, and getting that wrong broke both
    ways in one rehearsal. A CODE file keeps its changelog in the header block,
    so scanning past it swept in this file's own selftest fixtures. A MARKDOWN
    doc keeps its changelog at the FOOT (BACKLOG's PART 4), so bounding it to
    the header found nothing at all. Code: header only. Docs: the whole file.
    """
    out = []
    _lines = text.splitlines()
    _end = len(_lines) if rel.endswith(".md") else _header_end(_lines)
    for ln in _lines[:_end]:
        m = CHANGELOG.search(ln)
        if m:
            out.append((m.group(1), m.group(2)))
    return out


def blob_at(repo, ref, rel):
    p = sh(["git", "show", "%s:%s" % (ref, rel)], repo)
    return p.stdout if p.returncode == 0 else None


def changed(repo, ref):
    """(status, path) for everything differing from `ref`, staged or not, plus
    untracked files. `git diff` alone misses untracked adds, and an untracked
    NEW module with no header is exactly what wants catching."""
    seen, out = set(), []
    for args, tag in ((["git", "diff", "--name-status", ref], None),
                      (["git", "diff", "--cached", "--name-status", ref], None)):
        for ln in sh(args, repo).stdout.splitlines():
            parts = ln.split("\t")
            if len(parts) >= 2 and parts[1] not in seen:
                seen.add(parts[1])
                out.append((parts[0][0], parts[1]))
    for ln in sh(["git", "ls-files", "--others", "--exclude-standard"], repo).stdout.splitlines():
        if ln and ln not in seen:
            seen.add(ln)
            out.append(("A", ln))
    return sorted(out, key=lambda x: x[1])


def check(repo, rev, ref, problems, notes, hook=False):
    repo = os.path.abspath(os.path.expanduser(repo))
    if not os.path.isdir(os.path.join(repo, ".git")):
        problems.append("not a git checkout: %s" % repo)
        return

    # ── A. GENESIS ────────────────────────────────────────────────────────
    gpath = os.path.join(repo, "docs", "GENESIS.md")
    if os.path.exists(gpath):
        # v1.1 — always, hook mode included. See the header.
        _bad = []
        for _ln in open(gpath, encoding="utf-8").read().splitlines():
            if not _ln.startswith("| **r"):
                continue
            # ⚠️ STRIP CODE SPANS FIRST. Backticking the placeholder IS the
            # fix, and GitHub does not render HTML inside a code span. A guard
            # that still flags the repaired row is one the repair can never
            # satisfy — caught in rehearsal when the fix and the check
            # deadlocked on the same line.
            _clean = re.sub(r"`[^`]*`", "", _ln)
            for _t in HTML_TAGS.findall(_clean):
                if _t.lower() in HTML_ELEMENTS:
                    _bad.append((_ln.split("|")[1].strip().strip("*"), _t))
        if _bad:
            problems.append(
                "GENESIS: %d row(s) carry a bare HTML tag, which GitHub renders "
                "as an ELEMENT and nests every later row inside it — %s. Wrap "
                "the placeholder in backticks."
                % (len(_bad), ", ".join("%s: <%s>" % (r, t) for r, t in _bad[:6])))
    # ── A2. LEDGER COMPLETENESS — THE SHARED SEQUENCE, THE SINGLE LEDGER ──
    # 🔴 THIS IS THE CHECK THAT WAS MISSING, AND ITS ABSENCE COST THREE ROWS.
    # v1.1's capability detection is right in principle — "absent artifact =>
    # SKIP, and say so by name" is what keeps this from crying wolf on dtp.
    # ⚠️ BUT IT ASSUMED THE LEDGER IS A PER-REPO ARTEFACT AND IT IS NOT. The
    # revision sequence is SHARED across both trees — dtp r431 and otv4 r430
    # are the same counter — while GENESIS.md lives only in otv4. So dtp's
    # GENESIS check SKIPPED on every run, structurally, and on 2026-09-26
    # r431, r432 and r433 were committed in dtp with NO LEDGER ROW AT ALL and
    # nothing could notice. The operator found it by asking "how did you commit
    # them without adding to the Genesis? Don't you use a checker?"
    # 🔑 AND IT WORKS IN HOOK MODE, WHICH THE --rev CHECK CANNOT. A pre-commit
    # hook never knows the revision it is about to create, so the row for THIS
    # commit is genuinely uncheckable there. But every EARLIER revision is
    # already in the log, so completeness is answerable at any time, with no
    # --rev, in either tree. That is why this is retrospective rather than
    # another assertion about the current commit.
    _shared = os.path.expanduser("~/options-trader-v4/docs/GENESIS.md")
    if os.path.exists(_shared):
        _rows = set(re.findall(r"^\|\s*\*\*(r\d+)\*\*", 
                               open(_shared, encoding="utf-8").read(), re.M))
        if _rows:
            _floor = min(int(x[1:]) for x in _rows)
            _subj = subprocess.run(
                ["git", "-C", repo, "log", "--format=%s", "-400"],
                capture_output=True, text=True).stdout
            _used = {m for m in re.findall(r"^(r\d+):", _subj, re.M)}
            # ⚠️ BOUNDED BY THE LEDGER'S OWN FLOOR. Revisions older than the
            # first row predate the ledger and are not defects; flagging them
            # would be the CV.1 wolf-cry this file exists to avoid.
            _miss = sorted({r for r in _used if int(r[1:]) >= _floor} - _rows,
                           key=lambda r: int(r[1:]))
            if _miss:
                problems.append(
                    "LEDGER: %d revision(s) in this repo's log have NO row in "
                    "the shared ledger %s — %s. WA §35: a revision absent from "
                    "the ledger did not happen. The sequence is shared across "
                    "both trees; the ledger is not."
                    % (len(_miss), _shared, " ".join(_miss)))
            else:
                notes.append("LEDGER    PASS  — every revision in this log "
                             "(>= %s) has a row in the shared ledger" % ("r%d" % _floor))

    if not os.path.exists(gpath):
        notes.append("GENESIS   SKIP  — docs/GENESIS.md not present in this "
                     "repo (the shared ledger is checked separately — see "
                     "LEDGER)")
    elif not rev:
        if hook:
            # ⚠️ NOT A PASS, AND IT MUST NOT READ AS ONE. A pre-commit hook has
            # no way to know the revision number — that string is authored by
            # the land command. So the hook covers the per-file discipline and
            # the maps, and says plainly that the ledger row is unchecked here.
            notes.append("GENESIS   SKIP  — hook mode: the revision is not "
                         "known at commit time; the land command checks it")
        else:
            problems.append("GENESIS: this repo has a GENESIS ledger but no "
                            "--rev was given, so the row cannot be verified. "
                            "Pass --rev rNNN, or --hook if this is a hand commit")
    else:
        rows = re.findall(r"^\|\s*\*\*(r\d+[a-z]?)\*\*\s*\|", open(gpath, encoding="utf-8").read(), re.M)
        n = rows.count(rev)
        if n == 0:
            problems.append("GENESIS: no row for %s. WA §35 — a revision absent "
                            "from the ledger did not happen." % rev)
        elif n > 1:
            problems.append("GENESIS: %d rows for %s. One row per revision; a "
                            "duplicate reads as authoritative." % (n, rev))
        elif rows[-1] != rev:
            # WA §35: the append must be the LAST thing, or every later entry
            # is off by one against the commit it describes.
            problems.append("GENESIS: %s is not the last row (last is %s). The "
                            "append must land at the end of the table."
                            % (rev, rows[-1]))
        else:
            notes.append("GENESIS   PASS  — one row for %s, last in the table" % rev)

    # ── B/C. the generated maps ───────────────────────────────────────────
    for gen, doc, label in (("tests/gen_file_map.py", "docs/FILE_MAP.md", "FILE_MAP "),
                            ("tests/gen_write_map.py", "docs/WRITE_MAP.md", "WRITE_MAP")):
        if not os.path.exists(os.path.join(repo, gen)):
            notes.append("%s SKIP  — %s not present in this repo" % (label, gen))
            continue
        p = sh([sys.executable, gen, "--check"], repo)
        if p.returncode != 0:
            tail = [l.strip() for l in (p.stdout + p.stderr).splitlines() if l.strip()][-3:]
            problems.append("%s: %s --check exited %d -> %s"
                            % (label.strip(), gen, p.returncode, " | ".join(tail)))
        else:
            notes.append("%s PASS  — %s regenerates identical" % (label, doc))

    # ── D. per-file version + changelog ───────────────────────────────────
    files = [(st, rel) for st, rel in changed(repo, ref)
             if rel not in NO_BUMP and os.path.splitext(rel)[1] in TEXT_EXT]
    # ⚠️ THE FILTER RUNS FIRST, AND THAT IS THE POINT. A delivery whose only
    # diff is docs/GENESIS.md changed the LEDGER and no code — the ledger
    # describing a change that does not exist. Counting the raw diff would let
    # that through, because the ledger row is itself a diff.
    if not any(st != "D" for st, _ in files):
        # 🔑 r360 — ONE EXEMPTION: AN INDEX-ONLY UNTRACK OF AN IGNORED PATH.
        # `git rm --cached <f>` produces a diff of nothing but deletions, so
        # this rule refuses it — correct by its own words (no source changed)
        # and wrong in effect, because the ONLY way through was `--no-verify`,
        # which disables EVERY check including the ones that matter. A rule
        # whose sole escape hatch is "turn off all the rules" gets used that
        # way.
        # ⚠️ MEASURED: `logs/eod_conductor.log` was a tracked runtime artifact
        # (LAND.2), and untracking it had to be forced past this hook.
        # ⚠️ NARROW ON PURPOSE. Every deleted path must ALSO be ignored now,
        # so removing a real module still fails — a deleted `.py` that
        # `.gitignore` does not cover is a source change and needs its
        # bookkeeping. It must also still EXIST ON DISK: a deletion that
        # removes the file is not an untrack.
        # ⚠️ THE RAW DIFF, NOT `files`. `files` is already narrowed to
        # TEXT_EXT, so a `.log` — the exact case this exists for — is filtered
        # out before it gets here and the scan would see nothing. Read the
        # whole change set and require EVERY entry in it to be an untrack.
        _all = list(changed(repo, ref))
        _dels = [rel for st, rel in _all if st == "D"]
        if len(_dels) != len(_all):
            _dels = []          # something in the commit is not a deletion
        _ignored = []
        for _rel in _dels:
            _chk = sh(["git", "check-ignore", "-q", "--", _rel], repo)
            if _chk.returncode == 0 and os.path.exists(os.path.join(repo, _rel)):
                _ignored.append(_rel)
        if _dels and len(_ignored) == len(_dels):
            notes.append("BUMP      note  — index-only untrack of %d ignored "
                         "path(s), still on disk: %s. No source differs, and "
                         "that is correct for this shape."
                         % (len(_ignored), ", ".join(_ignored[:4])))
            return
        problems.append("BUMP: nothing differs from %s except generated or "
                        "append-only files. A land that changes no source is a "
                        "land that did not happen." % ref)
        return
    checked = unversioned = 0
    for status, rel in files:
        if status == "D":
            continue
        path = os.path.join(repo, rel)
        if not os.path.exists(path):
            continue
        new = open(path, encoding="utf-8", errors="replace").read()
        nv = title_version(new, rel)
        old = blob_at(repo, ref, rel)
        ov = title_version(old, rel) if old else None

        if nv is None:
            if ov is not None:
                problems.append("BUMP %s: had a title version (v%s) at %s and "
                                "has none now — the header was lost, not bumped"
                                % (rel, ov, ref))
            else:
                unversioned += 1
                notes.append("BUMP      note  — %s carries no version header "
                             "(none before either; not treated as a failure)" % rel)
            continue

        checked += 1
        # D1 — it moved
        if old is not None and ov == nv:
            problems.append("BUMP %s: title still v%s. WORKING_AGREEMENT §5 — "
                            "every edited file bumps its header." % (rel, nv))
        # D2 — a dated changelog entry names the NEW version
        entries = changelog_versions(new, rel)
        if not any(v == nv for v, _ in entries):
            problems.append("CHANGELOG %s: no dated entry for v%s. A version "
                            "with no entry is a version nobody can read."
                            % (rel, nv))
            continue
        # D3 — title == newest entry (the 2026-07-23 drift, made mechanical)
        top = entries[0][0]
        if top != nv:
            problems.append("DRIFT %s: title says v%s, newest changelog entry "
                            "says v%s. The two must agree." % (rel, nv, top))
        # D4 — the new entry is not a copy of an older date
        if old is not None:
            for v, d in changelog_versions(old, rel):
                if v == nv:
                    problems.append("CHANGELOG %s: v%s already existed at %s "
                                    "(dated %s) — the entry was not written for "
                                    "this delivery" % (rel, nv, ref, d))
                    break
    # ⚠️ THE SUMMARY MUST NOT SAY PASS WHILE THE PROBLEM LIST SAYS OTHERWISE.
    # The first version printed "BUMP PASS" unconditionally and then listed
    # BUMP failures three lines below it — output that renders cleanly and
    # means something else, which is the exact class this repo keeps finding
    # in its own instruments.
    bad = sum(1 for p in problems
              if p.startswith(("BUMP ", "CHANGELOG ", "DRIFT ")))
    notes.append("BUMP      %s  — %d versioned file(s) checked, %d carry no "
                 "header by design%s"
                 % ("PASS" if not bad else "FAIL", checked, unversioned,
                    "" if not bad else ", %d PROBLEM(S) BELOW" % bad))


def run(repo, rev, ref, hook=False):
    problems, notes = [], []
    check(repo, rev, ref, problems, notes, hook)
    print("check_land_discipline — %s%s" % (repo, (" @ " + rev) if rev else ""))
    for n in notes:
        print("  " + n)
    if problems:
        print("\n  PROBLEMS (%d):" % len(problems))
        for p in problems:
            print("   ✗ " + p)
        print("\nFAIL")
        return 1
    print("\nPASS")
    return 0


# ── selftest ──────────────────────────────────────────────────────────────
# WA §20/§21: a check that has never gone red is one nobody knows works. Each
# case below is BORN RED — it builds a repo exhibiting exactly one defect and
# asserts this tool names it. A case that passes is a broken case.
def _git(d, *a):
    subprocess.run(["git"] + list(a), cwd=d, capture_output=True, text=True)


def _mkrepo(d):
    os.makedirs(os.path.join(d, "docs"))
    _git(d, "init", "-q")
    _git(d, "config", "user.email", "t@t")
    _git(d, "config", "user.name", "t")
    open(os.path.join(d, "docs", "GENESIS.md"), "w").write(
        "| **r1** | first |\n")
    open(os.path.join(d, "mod.py"), "w").write(
        "#!/usr/bin/env python3\n# mod.py — v1.0\n# v1.0 (2026-01-01) — born.\nX = 1\n")
    _git(d, "add", "-A")
    _git(d, "commit", "-qm", "base")


def selftest():
    cases = []

    def case(name, mutate, expect):
        with tempfile.TemporaryDirectory() as d:
            _mkrepo(d)
            rev = mutate(d)
            probs, notes = [], []
            check(d, rev, "HEAD", probs, notes)
            hit = any(expect in p for p in probs)
            cases.append((name, hit, probs))

    def w(d, rel, s):
        open(os.path.join(d, rel), "w").write(s)

    # 1 — edited, header NOT bumped
    def m1(d):
        w(d, "mod.py", "#!/usr/bin/env python3\n# mod.py — v1.0\n"
                       "# v1.0 (2026-01-01) — born.\nX = 2\n")
        open(os.path.join(d, "docs", "GENESIS.md"), "a").write("| **r2** | x |\n")
        return "r2"
    case("no bump", m1, "title still v1.0")

    # 2 — bumped, but no changelog entry for the new version
    def m2(d):
        w(d, "mod.py", "#!/usr/bin/env python3\n# mod.py — v1.1\n"
                       "# v1.0 (2026-01-01) — born.\nX = 2\n")
        open(os.path.join(d, "docs", "GENESIS.md"), "a").write("| **r2** | x |\n")
        return "r2"
    case("no changelog entry", m2, "no dated entry for v1.1")

    # 3 — title/changelog drift
    def m3(d):
        w(d, "mod.py", "#!/usr/bin/env python3\n# mod.py — v1.1\n"
                       "# v1.2 (2026-02-02) — newer.\n# v1.1 (2026-02-01) — x.\nX = 2\n")
        open(os.path.join(d, "docs", "GENESIS.md"), "a").write("| **r2** | x |\n")
        return "r2"
    case("title/changelog drift", m3, "title says v1.1")

    # 4 — GENESIS row missing
    def m4(d):
        w(d, "mod.py", "#!/usr/bin/env python3\n# mod.py — v1.1\n"
                       "# v1.1 (2026-02-01) — x.\n# v1.0 (2026-01-01) — born.\nX = 2\n")
        return "r2"
    case("genesis missing", m4, "no row for r2")

    # 5 — GENESIS row present but not last (off-by-one against its commit)
    def m5(d):
        w(d, "mod.py", "#!/usr/bin/env python3\n# mod.py — v1.1\n"
                       "# v1.1 (2026-02-01) — x.\n# v1.0 (2026-01-01) — born.\nX = 2\n")
        open(os.path.join(d, "docs", "GENESIS.md"), "a").write(
            "| **r2** | x |\n| **r3** | later |\n")
        return "r2"
    case("genesis not last", m5, "is not the last row")

    # 6 — nothing changed at all
    def m6(d):
        open(os.path.join(d, "docs", "GENESIS.md"), "a").write("| **r2** | x |\n")
        return "r2"
    case("empty delivery", m6, "nothing differs")

    # 7 — POSITIVE CONTROL. A correct delivery must produce NO problems, or
    #     every red above is meaningless.
    with tempfile.TemporaryDirectory() as d:
        _mkrepo(d)
        open(os.path.join(d, "mod.py"), "w").write(
            "#!/usr/bin/env python3\n# mod.py — v1.1\n"
            "# v1.1 (2026-02-01) — the change.\n# v1.0 (2026-01-01) — born.\nX = 2\n")
        open(os.path.join(d, "docs", "GENESIS.md"), "a").write("| **r2** | x |\n")
        probs, notes = [], []
        check(d, "r2", "HEAD", probs, notes)
        cases.append(("clean delivery passes", not probs, probs))

    ok = True
    for name, hit, probs in cases:
        print("  %s  %s" % ("PASS" if hit else "FAIL", name))
        if not hit:
            ok = False
            for p in probs:
                print("        got: " + p)
    print("\n%s — %d/%d" % ("PASS" if ok else "FAIL", sum(1 for c in cases if c[1]), len(cases)))
    return 0 if ok else 1


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--rev", default="")
    ap.add_argument("--against", default="HEAD")
    ap.add_argument("--hook", action="store_true",
                    help="pre-commit mode: the revision is unknown, so the "
                         "GENESIS row is reported SKIP instead of failing")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv[1:])
    if a.selftest:
        return selftest()
    return run(a.repo, a.rev, a.against, a.hook)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
