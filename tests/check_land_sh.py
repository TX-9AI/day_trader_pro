#!/usr/bin/env python3
# day_trader_pro/tests/check_land_sh.py — v1.4
# v1.4 (2026-09-05) — dtp r291. D1-D3 pin the `DEL` directive: a delivery can
#   REMOVE a file, the removal is committed with the rest, and a target that is
#   already absent is a REFUSAL. Until r291 a payload could only add or
#   overwrite, so retiring a document meant a manual `rm` after the land —
#   outside the gate, the commit and the GENESIS row.
# v1.3 (2026-09-05) — dtp r289 / DEP.2. F1-F3 PIN THAT POS/NEG MATCH AS FIXED
#   STRINGS. `grep -q` is a BASIC REGULAR EXPRESSION and it graded two
#   deliveries wrongly in one day, in OPPOSITE directions: `**r247**`
#   degenerated to `r24` and PASSED against a GENESIS with no such row (failed
#   OPEN), and `[ "$GO" = "y" ]` read as a character class and REFUSED a
#   correct delivery (failed CLOSED). A gate that can do both is not weak — it
#   is unrelated to what it claims to check.
#   ⚠️ F1/F2 DRIVE A REAL LAND rather than grepping the source for `-qF`: a
#   string check would pass against the flag sitting in a comment and prove
#   nothing, which is the same defect one level up. F3 exists because
#   loosening a check that misfires is the easy wrong fix.
# v1.2 (2026-09-05) — dtp r279. ALL OR NONE, DRIVEN AGAINST A REAL SECOND REPO.
#   A1-A1d are the cases the operator asked for after watching a real one:
#   r277_r2 landed out of order, its dtp half passed and PUSHED, and only then
#   did the otv4 half refuse — origin left holding code with no backlog entry.
#   🔑 A1 IS THE CHECK THAT CARRIES THE WEIGHT AND IT ASSERTS ON THE REMOTE,
#   not on the checkout. "The local HEAD moved back" is a weaker claim than
#   "origin never saw it", and origin is the thing fifteen boxes pull from —
#   so A1b reads the BARE REPO directly.
#   ⚠️ A1c IS THE ONE THAT WOULD CATCH A LAZY ROLLBACK. `reset --hard` would
#   pass every other case here and silently revert an unrelated tracked file
#   the operator had edited. A1c plants exactly that and requires it to survive,
#   which is §35's reason for refusing a blind `git checkout -- .` applied to
#   the undo path.
# v1.1 (2026-09-05) — dtp r278. THE THREE NEW STAGES, EACH DRIVEN BOTH WAYS.
#   C1/C1b — a declared CHECK is EXECUTED and its exit code decides. C1 lands a
#   delivery whose check passes; C1b re-runs the identical world with a check
#   that exits 1 and requires the land to be REFUSED with HEAD unmoved. A gate
#   that only ever passes is indistinguishable from one that never runs, which
#   is the r201 shape §0.6 names.
#   C2 — a half shipping a .py and declaring NO check is refused. That is the
#   case a spec author will actually hit: not a broken check, a forgotten one,
#   and "nothing was executed" must not read like "everything passed".
#   C2b — a DOCS-ONLY half with no check still lands, and says out loud that
#   nothing ran. "Not applicable" and "passed" must never look alike (r183).
#   C3 — 🔴 THE ONE THAT WOULD HAVE BEEN CAUGHT ONLY IN PRODUCTION. v1.0 ran
#   `git add -A`, against the operator's own standing rule ("NEVER git add -A;
#   stage shipped files by name", written after a stray file was pushed off
#   main). C3 plants an UNRELATED dirty file in the repo and requires the
#   delivery commit not to contain it. A test that only checked the payload
#   landed would pass against both versions.
#   C4 — an ambiguous archive glob deletes NOTHING. The cleanup `rm -f`s
#   whatever the glob matched first, and the operator routinely has two
#   tarballs pending; untidy is recoverable, deleting the wrong one is not.
#   D1-D4 — tools/deploy.sh, the thing the MENU actually invokes. Driven end to
#   end against a real tarball in a real $HOME: it finds the archive, discovers
#   both halves from their land.spec files, ORDERS them, and hands off. D2 is
#   the one worth having: a two-half delivery whose SECOND half gates on an
#   artifact the FIRST produces lands only in the right order, which is exactly
#   r277's otv4 half gating on r247's GENESIS row. D4 proves --dry commits
#   nothing, because a preview that changes the tree is not a preview.
# v1.0 (2026-09-01) — otv4 r207 / dtp r235. THE LANDER'S OWN GATE.
#
# 🔴 WHY THIS IS NOT OPTIONAL. tools/land.sh is now the only thing standing
#   between a tarball and origin, and a lander that lands a BAD delivery is
#   worse than no lander, because it carries the authority of having checked.
#   Every case below builds a throwaway world with EXACTLY ONE defect and
#   asserts the lander refuses it and leaves the repo untouched — the same
#   shape check_land_discipline's own selftest uses.
#
# ⚠️ EACH REFUSAL MUST ALSO STAGE NOTHING. "It printed an error" and "it
#   changed nothing" are different claims, and only the second is the one that
#   matters at 09:31 on a Monday. Every negative case asserts a clean tree.
#
# ⚠️ AND THE HAPPY PATH IS TESTED TOO. A gate that only ever refuses is a gate
#   nobody can distinguish from broken (§17: an alarm that has never fired is
#   one nobody knows works). P1 lands a real delivery end to end against a
#   real bare remote and asserts the commit, the push and the self-cleanup.
#
# Run: python3 tests/check_land_sh.py

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAND = os.path.join(_root, "tools", "land.sh")
DEPLOY = os.path.join(_root, "tools", "deploy.sh")

_fails = []


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + (f"   [{detail}]" if detail else ""))
    if not ok:
        _fails.append(name)


def _clean_env(**over):
    """Child env with this delivery's own control variables stripped.

    ⚠️ BELT AND BRACES BESIDE land.sh's `env -u`. If a future caller runs these
    cases some other way, inheriting `LAND_ARCHIVE` would point a nested land at
    the OUTER delivery's tarball and its cleanup would delete it. The case that
    caught it, C4c, failed under the lander and passed by hand — which reads as
    a flaky test and is actually a leak.
    """
    e = dict(os.environ)
    for k in ("LAND_ARCHIVE", "LAND_STAGE"):
        e.pop(k, None)
    e.update(over)
    return e


def _run(cmd, cwd=None, env=None):
    return subprocess.run(cmd, cwd=cwd, env=env, shell=isinstance(cmd, str),
                          capture_output=True, text=True)


def _world(tmp, spec_lines, payload="v2\n", extra=None, docs_only=False):
    """A home with one git repo, a bare remote, and a staged delivery.

    ⚠️ BUILT FROM THE LANDER'S OWN CONTRACT, not from a belief about it: the
    marker file, the spec directives and the layout are exactly what the
    usage block in tools/land.sh documents. A fixture written from the same
    assumption as the code under test cannot fail (§0.4).
    """
    home = os.path.join(tmp, "home")
    repo = os.path.join(home, "myrepo")
    bare = os.path.join(tmp, "bare")
    stage = os.path.join(tmp, "stage")
    os.makedirs(os.path.join(repo, "docs"))
    os.makedirs(os.path.join(stage, "half"))
    with open(os.path.join(repo, "MARKER"), "w") as f:
        f.write("marker\n")
    with open(os.path.join(repo, "thing.py"), "w") as f:
        f.write("# thing.py — v1.0\n# v1.0 (2026-08-01) — base.\nOLD_LINE = 1\n")
    _run("git init -q -b main .", cwd=repo)
    _run('git config user.email t@t; git config user.name t', cwd=repo)
    _run("git add -A; git commit -q -m base", cwd=repo)
    _run(f'git init -q --bare "{bare}"')
    _run(f'git remote add origin "{bare}"; git push -q origin main; '
         f'git branch -q --set-upstream-to=origin/main main', cwd=repo)
    # ⚠️ THE FIXTURE CARRIES A DATED CHANGELOG ENTRY BECAUSE THE REAL RULE
    # DEMANDS ONE. The first draft of this file omitted it and the lander
    # correctly refused the "happy path" — the tool was right and the fixture
    # was wrong, which is the good direction for that to go.
    if docs_only:
        # v1.1 — a half with no .py at all. The lander must still land it and
        # must SAY that nothing was executed rather than implying it verified.
        os.makedirs(os.path.join(stage, "half", "docs"), exist_ok=True)
        with open(os.path.join(stage, "half", "docs", "NOTE.md"), "w") as f:
            f.write("# NOTE.md — v1.1\nv1.1 (2026-09-05) — the edit. NEW_LINE = 2\n")
    else:
        with open(os.path.join(stage, "half", "thing.py"), "w") as f:
            f.write("# thing.py — v1.1\n# v1.1 (2026-09-01) — the edit.\nNEW_LINE = 2\n")
    for rel, body in (extra or {}).items():
        dst = os.path.join(stage, "half", rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "w") as f:
            f.write(body)
    with open(os.path.join(stage, "half", "land.spec"), "w") as f:
        f.write("\n".join(spec_lines) + "\n")
    shutil.copy(LAND, os.path.join(stage, "land.sh"))
    # the bookkeeping tool the lander insists on finding
    dtp = os.path.join(home, "day_trader_pro", "tools")
    os.makedirs(dtp)
    shutil.copy(os.path.join(_root, "tools", "check_land_discipline.py"), dtp)
    os.makedirs(os.path.join(home, "day_trader_pro", ".git"))
    with open(os.path.join(home, ".gitconfig"), "w") as f:
        f.write("[user]\n\temail = t@t\n\tname = t\n")
    return home, repo, stage


GOOD = ["REPO MARKER", "REV r999", "DESC a real sentence about why",
        "POS thing.py|NEW_LINE = 2", "NEG thing.py|OLD_LINE = 1",
        # v1.1 — a code half must declare a check, so the baseline world does.
        "CHECK tests/ok.py"]
PASS_CHK = {"tests/ok.py": "import sys; sys.exit(0)\n"}
FAIL_CHK = {"tests/ok.py": "import sys; sys.exit(1)\n"}


def _land(home, stage, half="half"):
    env = _clean_env(HOME=home)
    return _run(f'bash "{stage}/land.sh" {half}', env=env)


def _dirty(repo):
    return _run("git status --porcelain", cwd=repo).stdout.strip()


def _head(repo):
    """The newest commit subject. A refused land must not move it."""
    return _run("git log --format=%s -1", cwd=repo).stdout.strip()


def main():
    # ── P1 — the happy path lands, pushes and cleans up ──────────────────
    with tempfile.TemporaryDirectory() as tmp:
        home, repo, stage = _world(tmp, GOOD, extra=PASS_CHK)
        r = _land(home, stage)
        subj = _run("git log --oneline -1", cwd=repo).stdout
        check("P1 a clean delivery lands, commits and pushes",
              r.returncode == 0 and "r999" in subj and not _dirty(repo),
              f"rc={r.returncode} subj={subj.strip()[:40]!r} dirty={_dirty(repo)!r}")
        check("P1b the staging directory is removed on success",
              not os.path.exists(stage), f"stage exists={os.path.exists(stage)}")

    # ── L1 — no spec is a REFUSAL, not a fallthrough ─────────────────────
    with tempfile.TemporaryDirectory() as tmp:
        home, repo, stage = _world(tmp, GOOD, extra=PASS_CHK)
        os.remove(os.path.join(stage, "half", "land.spec"))
        r = _land(home, stage)
        check("L1 a half with no land.spec is refused outright",
              r.returncode != 0 and "NO land.spec" in r.stdout and not _dirty(repo),
              f"rc={r.returncode} dirty={_dirty(repo)!r}")

    # ── L2 — a POS that does not match stops the land ────────────────────
    # This is the header-bump-with-no-edit case: the file arrived, the version
    # moved, and the actual change is not in it.
    with tempfile.TemporaryDirectory() as tmp:
        home, repo, stage = _world(tmp, GOOD, extra=PASS_CHK)
        with open(os.path.join(stage, "half", "thing.py"), "w") as f:
            f.write("# thing.py — v1.1\n# v1.1 (2026-09-01) — the edit.\n"
                    "OLD_LINE = 1\n")                          # bumped, not edited
        r = _land(home, stage)
        # ⚠️ THE CLAIM IS "NOTHING WAS COMMITTED", NOT "THE TREE IS CLEAN".
        # §15 extracts before it verifies, so a refused gate DOES leave a dirty
        # working tree — §35 records that and records the manual recovery. The
        # thing that must never happen is a commit or a push.
        check("L2 a header bump with no real edit fails the content gate",
              r.returncode != 0 and "MISSING" in r.stdout and _head(repo) == "base",
              f"rc={r.returncode} head={_head(repo)!r}")

    # ── L3 — a NEG that still matches stops the land ─────────────────────
    with tempfile.TemporaryDirectory() as tmp:
        home, repo, stage = _world(tmp, GOOD, extra=PASS_CHK)
        with open(os.path.join(stage, "half", "thing.py"), "w") as f:
            f.write("# thing.py — v1.1\nNEW_LINE = 2\nOLD_LINE = 1\n")
        r = _land(home, stage)
        check("L3 superseded code left behind fails the content gate",
              r.returncode != 0 and "STILL PRESENT" in r.stdout and _head(repo) == "base",
              f"rc={r.returncode} head={_head(repo)!r}")

    # ── L4 — an unfindable repo touches nothing and says so ──────────────
    with tempfile.TemporaryDirectory() as tmp:
        home, repo, stage = _world(tmp, ["REPO NOT_A_REAL_MARKER", "REV r999",
                                         "DESC x", "POS thing.py|NEW_LINE = 2"])
        r = _land(home, stage)
        check("L4 no matching checkout is a named refusal, not a guess",
              r.returncode != 0 and "no checkout under" in r.stdout
              and not _dirty(repo),
              f"rc={r.returncode}")

    # ── L5 — the archive and staging SURVIVE any failure ─────────────────
    # ⚠️ THE POINT: a failed land must never cost the operator a re-download.
    with tempfile.TemporaryDirectory() as tmp:
        home, repo, stage = _world(tmp, GOOD, extra=PASS_CHK)
        os.remove(os.path.join(stage, "half", "land.spec"))
        _land(home, stage)
        check("L5 a failed land keeps the staging directory",
              os.path.exists(stage),
              "" if os.path.exists(stage) else "staging was removed on failure")

    # ── L6 — a spec missing REV or DESC is refused ───────────────────────
    # Without them there is no GENESIS row and no commit subject, and §35 is
    # explicit that the two come from ONE string so they cannot diverge.
    with tempfile.TemporaryDirectory() as tmp:
        home, repo, stage = _world(tmp, ["REPO MARKER", "DESC x",
                                         "POS thing.py|NEW_LINE = 2"])
        r = _land(home, stage)
        check("L6 a spec with no REV is refused",
              r.returncode != 0 and "no REV" in r.stdout and not _dirty(repo),
              f"rc={r.returncode}")

    # ══ C1 — A DECLARED CHECK IS EXECUTED, AND ITS EXIT CODE DECIDES ══════
    # C1's pass arm is P1 above (the baseline world now declares one). This is
    # the arm that proves it RUNS: identical world, check exits 1.
    with tempfile.TemporaryDirectory() as tmp:
        home, repo, stage = _world(tmp, GOOD, extra=FAIL_CHK)
        before = _head(repo)
        r = _land(home, stage)
        check("C1b a declared CHECK that fails refuses the land",
              r.returncode != 0 and "CHECK FAILED" in (r.stdout + r.stderr),
              (r.stdout + r.stderr).strip().splitlines()[-1:] and
              (r.stdout + r.stderr).strip().splitlines()[-1] or "")
        check("C1c ...and HEAD did not move", _head(repo) == before)

    # ══ C2 — A CODE HALF THAT DECLARES NOTHING IS REFUSED ═════════════════
    # 🔑 The realistic failure is a FORGOTTEN check, not a broken one. Without
    # this, a delivery that verified nothing lands looking exactly like one
    # that verified everything.
    with tempfile.TemporaryDirectory() as tmp:
        NOCHK = [l for l in GOOD if not l.startswith("CHECK ")]
        home, repo, stage = _world(tmp, NOCHK)
        before = _head(repo)
        r = _land(home, stage)
        check("C2 a half shipping .py with no CHECK is refused",
              r.returncode != 0 and "DECLARES NO CHECK" in (r.stdout + r.stderr))
        check("C2b ...and HEAD did not move", _head(repo) == before)

    # ══ C2c — BUT A DOCS-ONLY HALF STILL LANDS, AND SAYS SO ═══════════════
    with tempfile.TemporaryDirectory() as tmp:
        DOCS = ["REPO MARKER", "REV r999", "DESC a docs-only sentence",
                "POS docs/NOTE.md|NEW_LINE = 2"]
        home, repo, stage = _world(tmp, DOCS, docs_only=True)
        r = _land(home, stage)
        out = r.stdout + r.stderr
        check("C2c a docs-only half lands with no check declared",
              r.returncode == 0, out.strip().splitlines()[-1:] and
              out.strip().splitlines()[-1] or "")
        check("C2d ...and states plainly that nothing was executed",
              "NONE DECLARED" in out)

    # ══ C3 — STAGE BY NAME: AN UNRELATED EDIT IS NOT SWEPT IN ═════════════
    # 🔴 v1.0 ran `git add -A`. The operator's standing rule is the opposite,
    # written after a stray file was pushed off main, and only a dirty-tree
    # fixture can tell the two versions apart.
    with tempfile.TemporaryDirectory() as tmp:
        home, repo, stage = _world(tmp, GOOD, extra=PASS_CHK)
        with open(os.path.join(repo, "STRAY.txt"), "w") as f:
            f.write("an unrelated local edit\n")
        r = _land(home, stage)
        files = _run("git show --name-only --format= HEAD", cwd=repo).stdout
        check("C3 the delivery commit does not contain an unrelated file",
              r.returncode == 0 and "STRAY.txt" not in files,
              files.replace("\n", " ").strip())
        check("C3b ...and the stray edit is still there, untouched",
              os.path.exists(os.path.join(repo, "STRAY.txt")))

    # ══ C4 — AN AMBIGUOUS ARCHIVE GLOB DELETES NOTHING ════════════════════
    with tempfile.TemporaryDirectory() as tmp:
        home, repo, stage = _world(tmp, GOOD, extra=PASS_CHK)
        a1 = os.path.join(home, "one_r1.tar.gz")
        a2 = os.path.join(home, "two_r2.tar.gz")
        for a in (a1, a2):
            with open(a, "w") as f:
                f.write("not really a tarball\n")
        r = _land(home, stage)
        check("C4 two candidate archives: the land still succeeds",
              r.returncode == 0)
        check("C4b ...and NEITHER archive is deleted",
              os.path.exists(a1) and os.path.exists(a2))
        check("C4c ...and it says so rather than cleaning up silently",
              "NOTHING was deleted" in (r.stdout + r.stderr))

    # ══ D — tools/deploy.sh, END TO END THROUGH A REAL TARBALL ════════════
    # 🔑 THIS IS WHAT THE MENU ITEM RUNS. Testing land.sh and calling the menu
    # verified would be the laundered green §18 names: the discovery, the
    # half-detection and the ordering all live here and nowhere else.
    def _two_half_world(tmp, second_check="import sys; sys.exit(0)\n"):
        """A home with TWO repos and one archive containing both halves.

        The second half's content gate requires a file the FIRST half's land
        creates, so landing them backwards is REFUSED rather than merely odd —
        the same shape as r277's otv4 half gating on r247's GENESIS row.
        """
        home, repo, stage = _world(tmp, GOOD + ["ORDER 1"], extra=PASS_CHK)
        # a second repo, with its own marker
        r2 = os.path.join(home, "otherrepo")
        b2 = os.path.join(tmp, "bare2")
        os.makedirs(r2)
        for n, body in (("MARKER2", "m\n"),
                        ("other.py", "# other.py — v1.0\n# v1.0 (2026-08-01) — base.\nOLD2 = 1\n")):
            with open(os.path.join(r2, n), "w") as f:
                f.write(body)
        _run("git init -q -b main .", cwd=r2)
        _run('git config user.email t@t; git config user.name t', cwd=r2)
        _run("git add -A; git commit -q -m base", cwd=r2)
        _run(f'git init -q --bare "{b2}"')
        _run(f'git remote add origin "{b2}"; git push -q origin main; '
             f'git branch -q --set-upstream-to=origin/main main', cwd=r2)
        h2 = os.path.join(stage, "second")
        os.makedirs(os.path.join(h2, "tests"))
        with open(os.path.join(h2, "other.py"), "w") as f:
            f.write("# other.py — v1.1\n# v1.1 (2026-09-05) — the edit.\nNEW2 = 2\n")
        with open(os.path.join(h2, "tests", "ok2.py"), "w") as f:
            f.write(second_check)
        with open(os.path.join(h2, "land.spec"), "w") as f:
            f.write("\n".join([
                "REPO MARKER2", "REV r1000", "DESC the second half",
                "ORDER 2",
                "POS other.py|NEW2 = 2", "NEG other.py|OLD2 = 1",
                # ⚠️ THE ORDERING GATE: this file only exists once half one has
                # landed, so a backwards run is refused rather than tolerated.
                "POS ../myrepo/thing.py|NEW_LINE = 2",
                "CHECK tests/ok2.py"]) + "\n")
        arc = os.path.join(home, "delivery_r1000.tar.gz")
        _run(f'tar czf "{arc}" -C "{stage}" .')
        shutil.rmtree(stage)
        return home, repo, r2, arc, os.path.join(tmp, "bare"), b2

    with tempfile.TemporaryDirectory() as tmp:
        home, repo, r2, arc, bare1, bare2 = _two_half_world(tmp)
        # ⚠️ NAME THE STAGING DIR RATHER THAN SCANNING /tmp FOR ONE. The first
        # draft globbed `/tmp/land.*` and went RED against CORRECT code, because
        # --dry leaves its staging behind BY DESIGN and other cases had left
        # theirs too. A check that fires on a sibling's residue is a check that
        # gets distrusted — and LAND_STAGE exists precisely so a caller can
        # assert on the directory it actually chose.
        mine = os.path.join(tmp, "stagedir")
        env = _clean_env(HOME=home, LAND_STAGE=mine)
        r = _run(f'bash "{DEPLOY}"', env=env)
        out = r.stdout + r.stderr
        check("D1 deploy.sh finds the archive and discovers both halves",
              "halves: half second" in out, out.strip().splitlines()[:1])
        check("D2 both repos land, in ORDER",
              _head(repo).startswith("r999") and _head(r2).startswith("r1000"),
              f"{_head(repo)!r} / {_head(r2)!r}")
        check("D2b the second half's gate on the first half's artifact passed",
              r.returncode == 0)
        check("D3 the archive it actually landed is the one deleted",
              not os.path.exists(arc))
        # 🔴 THE STAGING DIR IS UNIQUE PER RUN AND THIS CASE IS WHY. A fixed
        # /tmp/land is shared state, and THIS SELFTEST invokes deploy.sh — a
        # nested run would have deleted the staging of a delivery landing at
        # the same moment, from inside its own verification.
        check("D3b ...and its own staging directory is gone",
              not os.path.isdir(mine), mine)

    # ══ D2c — AND BACKWARDS IS REFUSED, WHICH IS WHAT MAKES `ORDER` REAL ══
    # An ordering that is never tested against the wrong order is an ordering
    # nobody knows works (§17). Driven through land.sh directly, since deploy.sh
    # exists precisely to make this order impossible to get wrong by hand.
    with tempfile.TemporaryDirectory() as tmp:
        home, repo, r2, arc, bare1, bare2 = _two_half_world(tmp)
        st = os.path.join(tmp, "unpack"); os.makedirs(st)
        _run(f'tar xf "{arc}" -C "{st}"')
        env = _clean_env(HOME=home)
        r = _run(f'bash "{st}/land.sh" second half', env=env)
        check("D2c landing the halves BACKWARDS is refused",
              r.returncode != 0 and _head(r2) == "base",
              f"rc={r.returncode} head={_head(r2)!r}")

    with tempfile.TemporaryDirectory() as tmp:
        home, repo, r2, arc, bare1, bare2 = _two_half_world(tmp)
        env = _clean_env(HOME=home)
        r = _run(f'bash "{DEPLOY}" --dry', env=env)
        check("D4 --dry names the halves and their revisions",
              "r999" in r.stdout and "r1000" in r.stdout)
        check("D4b --dry commits nothing, deletes nothing",
              _head(repo) == "base" and _head(r2) == "base"
              and os.path.exists(arc), f"{_head(repo)!r} archive={os.path.exists(arc)}")

    with tempfile.TemporaryDirectory() as tmp:
        empty = os.path.join(tmp, "home"); os.makedirs(empty)
        r = _run(f'bash "{DEPLOY}"', env=_clean_env(HOME=empty))
        check("D5 no tarball at all is a named refusal, not a traceback",
              r.returncode != 0 and "nothing to land" in (r.stdout + r.stderr))

    # ══ A — ALL HALVES LAND, OR NONE REACHES ORIGIN ═══════════════════════
    # The second half's CHECK exits 1. The first half is otherwise perfect and
    # WOULD have landed and pushed under v1.1 — that is the observed failure
    # this case exists for, not a hypothetical.
    def _remote_head(bare):
        return _run(f'git --git-dir="{bare}" log --format=%s -1 main').stdout.strip()

    with tempfile.TemporaryDirectory() as tmp:
        home, repo, r2, arc, bare1, bare2 = _two_half_world(
            tmp, second_check="import sys; sys.exit(1)\n")
        # An unrelated edit to a TRACKED file that is NOT in the payload — a
        # `--hard` rollback would revert it. ⚠️ THE FIRST DRAFT EDITED
        # `thing.py`, WHICH THE DELIVERY LEGITIMATELY OVERWRITES, so it asserted
        # a property no lander could have and went red against correct code. The
        # claim is about files the delivery does not ship, and MARKER is one.
        with open(os.path.join(repo, "MARKER"), "a") as f:
            f.write("the operator was mid-edit\n")
        before1, before2 = _head(repo), _head(r2)
        env = _clean_env(HOME=home, LAND_STAGE=os.path.join(tmp, "sd"))
        r = _run(f'bash "{DEPLOY}"', env=env)
        out = r.stdout + r.stderr

        check("A1 a failure in the SECOND half rolls back the first",
              _head(repo) == before1 and _head(r2) == before2,
              f"{_head(repo)!r} / {_head(r2)!r}")
        check("A1b ...and ORIGIN never saw either half",
              _remote_head(bare1) == "base" and _remote_head(bare2) == "base",
              f"{_remote_head(bare1)!r} / {_remote_head(bare2)!r}")
        check("A1c ...and the operator's own unrelated edit SURVIVED the "
              "rollback (soft, never hard)",
              "mid-edit" in open(os.path.join(repo, "MARKER")).read())
        check("A1d ...and it says so rather than tidying up silently",
              "ROLLING BACK" in out and "origin is untouched" in out)
        check("A1e ...and the archive is KEPT so nothing is re-downloaded",
              os.path.exists(arc))

    # ══ A2 — AND THE HAPPY PATH STILL PUSHES BOTH ═════════════════════════
    # A rollback that fires on a good delivery is worse than none. D1-D3 above
    # already land the two-half world; this asserts the REMOTES specifically,
    # because the whole claim of v1.2 is about what origin ends up holding.
    with tempfile.TemporaryDirectory() as tmp:
        home, repo, r2, arc, bare1, bare2 = _two_half_world(tmp)
        env = _clean_env(HOME=home, LAND_STAGE=os.path.join(tmp, "sd"))
        r = _run(f'bash "{DEPLOY}"', env=env)
        check("A2 a clean two-half delivery reaches BOTH remotes",
              r.returncode == 0
              and _remote_head(bare1).startswith("r999")
              and _remote_head(bare2).startswith("r1000"),
              f"{_remote_head(bare1)!r} / {_remote_head(bare2)!r}")
        check("A2b ...and the pushes come after every commit, not between them",
              "holding the push until every half is in" in (r.stdout + r.stderr))

    # ══ 🔴 F1-F3 — POS/NEG ARE FIXED STRINGS (dtp r289 / DEP.2) ═══════════
    # Both shapes below were REAL spec lines this gate graded wrongly on
    # 2026-09-05, in OPPOSITE directions. A gate that can fail open and closed
    # is not a weak gate — it is unrelated to what it claims to check.

    # F1 — FAILED OPEN. In a BRE `**r247**` is "r24" then "zero or more 7s",
    # so it matched a GENESIS containing r24 and no r247, and the delivery
    # landed on a ledger that did not have the row it asserted.
    with tempfile.TemporaryDirectory() as tmp:
        spec = [l for l in GOOD if not l.startswith("POS")] + \
               ["POS thing.py|**NEW_LINE = 2**"]
        home, repo, stage = _world(tmp, spec, extra=PASS_CHK)
        r = _land(home, stage)
        check("F1 a POS whose LITERAL text is absent is refused, even though "
              "it would match as a regex",
              r.returncode != 0 and _head(repo) == "base",
              f"rc={r.returncode} head={_head(repo)!r}")

    # F2 — FAILED CLOSED. Brackets are a character class, so a NEG naming a
    # string the file does not contain matched anyway and refused a correct
    # delivery. This is the one that cost a re-cut earlier today.
    with tempfile.TemporaryDirectory() as tmp:
        spec = [l for l in GOOD if not l.startswith("NEG")] + \
               ['NEG thing.py|[ "$GO" = "y" ]']
        home, repo, stage = _world(tmp, spec, extra=PASS_CHK)
        r = _land(home, stage)
        check("F2 a NEG whose LITERAL text is absent does not trip, though "
              "its characters would match as a class",
              r.returncode == 0, f"rc={r.returncode} out={r.stdout[-120:]!r}")

    # ⚠️ F3 — AND THE GATE STILL BITES. Loosening a check that misfires is the
    # easy wrong fix; the literal form must still refuse a delivery whose
    # asserted content really is missing.
    with tempfile.TemporaryDirectory() as tmp:
        spec = [l for l in GOOD if not l.startswith("POS")] + \
               ["POS thing.py|a string that is genuinely not there"]
        home, repo, stage = _world(tmp, spec, extra=PASS_CHK)
        r = _land(home, stage)
        check("F3 ...and a genuinely absent string is still refused",
              r.returncode != 0 and _head(repo) == "base",
              f"rc={r.returncode}")

    # ══ 🔴 D1-D3 — `DEL` (dtp r291) ══════════════════════════════════════
    # A payload only ever ADDED or overwrote. Retiring a file meant the
    # operator deleting it by hand AFTER the land — outside the gate, outside
    # the commit, and outside the row that is supposed to say what changed.
    with tempfile.TemporaryDirectory() as tmp:
        spec = GOOD + ["DEL MARKER"]
        home, repo, stage = _world(tmp, spec, extra=PASS_CHK)
        r = _land(home, stage)
        check("D1 a DEL target is removed from the working tree",
              r.returncode == 0 and not os.path.exists(os.path.join(repo, "MARKER")),
              f"rc={r.returncode}")
        # ⚠️ AND IT IS IN THE COMMIT, not merely gone from disk. A file deleted
        # but unstaged leaves the repo dirty and the removal unrecorded.
        tracked = _run("git ls-files MARKER", cwd=repo).stdout.strip()
        check("D1b ...and the removal is committed, not left dirty",
              tracked == "" and not _dirty(repo),
              f"tracked={tracked!r} dirty={_dirty(repo)!r}")

    # 🔴 D2 — AN ALREADY-ABSENT TARGET IS A REFUSAL. The spec would be
    # describing a repo that does not exist, and landing it would record a
    # deletion that never happened.
    with tempfile.TemporaryDirectory() as tmp:
        spec = GOOD + ["DEL no_such_file.md"]
        home, repo, stage = _world(tmp, spec, extra=PASS_CHK)
        r = _land(home, stage)
        check("D2 a DEL naming a file that is not there is REFUSED",
              r.returncode != 0 and _head(repo) == "base",
              f"rc={r.returncode} head={_head(repo)!r}")

    # ⚠️ D3 — AND A SPEC WITH NO DEL IS UNAFFECTED. The directive is optional;
    # every existing delivery must behave exactly as before.
    with tempfile.TemporaryDirectory() as tmp:
        home, repo, stage = _world(tmp, GOOD, extra=PASS_CHK)
        r = _land(home, stage)
        check("D3 a delivery with no DEL still lands and deletes nothing",
              r.returncode == 0 and os.path.exists(os.path.join(repo, "MARKER")),
              f"rc={r.returncode}")

    print()
    if _fails:
        print(f"FAILED {len(_fails)}: " + ", ".join(_fails))
        return 1
    print("check_land_sh: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
