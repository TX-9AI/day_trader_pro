#!/usr/bin/env python3
# day_trader_pro/tools/check_land_discipline.py — v1.0
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

HEAD_LINES = 12        # a title line lives at the very top or it is not a title
BODY_LINES = 400       # changelog entries sit near the top; do not scan a whole file


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


def changelog_versions(text: str):
    """Every (version, date) pair in header order — newest first by convention."""
    out = []
    for ln in text.splitlines()[:BODY_LINES]:
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
    if not os.path.exists(gpath):
        notes.append("GENESIS   SKIP  — docs/GENESIS.md not present in this repo")
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
        entries = changelog_versions(new)
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
            for v, d in changelog_versions(old):
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
