#!/usr/bin/env python3
# day_trader_pro/tests/check_land_sh.py — v1.0
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

_fails = []


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + (f"   [{detail}]" if detail else ""))
    if not ok:
        _fails.append(name)


def _run(cmd, cwd=None, env=None):
    return subprocess.run(cmd, cwd=cwd, env=env, shell=isinstance(cmd, str),
                          capture_output=True, text=True)


def _world(tmp, spec_lines, payload="v2\n"):
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
    with open(os.path.join(stage, "half", "thing.py"), "w") as f:
        f.write("# thing.py — v1.1\n# v1.1 (2026-09-01) — the edit.\nNEW_LINE = 2\n")
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
        "POS thing.py|NEW_LINE = 2", "NEG thing.py|OLD_LINE = 1"]


def _land(home, stage, half="half"):
    env = dict(os.environ, HOME=home)
    return _run(f'bash "{stage}/land.sh" {half}', env=env)


def _dirty(repo):
    return _run("git status --porcelain", cwd=repo).stdout.strip()


def _head(repo):
    """The newest commit subject. A refused land must not move it."""
    return _run("git log --format=%s -1", cwd=repo).stdout.strip()


def main():
    # ── P1 — the happy path lands, pushes and cleans up ──────────────────
    with tempfile.TemporaryDirectory() as tmp:
        home, repo, stage = _world(tmp, GOOD)
        r = _land(home, stage)
        subj = _run("git log --oneline -1", cwd=repo).stdout
        check("P1 a clean delivery lands, commits and pushes",
              r.returncode == 0 and "r999" in subj and not _dirty(repo),
              f"rc={r.returncode} subj={subj.strip()[:40]!r} dirty={_dirty(repo)!r}")
        check("P1b the staging directory is removed on success",
              not os.path.exists(stage), f"stage exists={os.path.exists(stage)}")

    # ── L1 — no spec is a REFUSAL, not a fallthrough ─────────────────────
    with tempfile.TemporaryDirectory() as tmp:
        home, repo, stage = _world(tmp, GOOD)
        os.remove(os.path.join(stage, "half", "land.spec"))
        r = _land(home, stage)
        check("L1 a half with no land.spec is refused outright",
              r.returncode != 0 and "NO land.spec" in r.stdout and not _dirty(repo),
              f"rc={r.returncode} dirty={_dirty(repo)!r}")

    # ── L2 — a POS that does not match stops the land ────────────────────
    # This is the header-bump-with-no-edit case: the file arrived, the version
    # moved, and the actual change is not in it.
    with tempfile.TemporaryDirectory() as tmp:
        home, repo, stage = _world(tmp, GOOD)
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
        home, repo, stage = _world(tmp, GOOD)
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
        home, repo, stage = _world(tmp, GOOD)
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

    print()
    if _fails:
        print(f"FAILED {len(_fails)}: " + ", ".join(_fails))
        return 1
    print("check_land_sh: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
