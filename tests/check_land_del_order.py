#!/usr/bin/env python3
# day_trader_pro/tests/check_land_del_order.py — v1.0
# v1.0 (2026-11-08) — dtp r532 / OTV4DEP.1. land.sh v1.19 RUNS DEL BEFORE THE CHECKS. At v1.18 the DEL block ran
#   after the CHECK loop, so r532's own gate (check_no_otv4_deps) refused its land on tools/build_level_history.py,
#   the file the same spec deletes. Mirrors OTV5 land.sh v5.3 (r76 / RETIRE.1). Driven through REAL lands on
#   fixture repos (check_land_sh's own world builder), never read out of land.sh. BORN RED on land.sh v1.18 at O1.
#
#   O1   a spec that DELETES a file one of its CHECKs forbids LANDS, and the file is gone from the commit
#   O1b  ...and the tree is clean after (the removal is committed, not left staged)
#   O2   a DEL naming a file that is not there is still REFUSED, and HEAD does not move
#   O3   a refused land whose spec DELETES a file leaves HEAD where it was
#   O3b  ...and die()'s printed discard-the-payload recipe RESTORES the DEL'd file and leaves the tree clean
#
# ⚠️ RUNS UNDER THE UNATTENDED GUARD LIKE check_land_sh: every land here is a child with VERTIGO_UNATTENDED removed
#   from ITS environment only if the caller is attended; under an unattended caller the lander exits 9 and these
#   cases report that by name (they do not pass vacuously).
# Run:  venv/bin/python tests/check_land_del_order.py
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_land_sh as H                                       # noqa: E402

_fails = []


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + (f"   [{detail}]" if detail else ""))
    if not ok:
        _fails.append(name)


# A CHECK that fails while the doomed file is still on disk: exactly the shape that refused r532 at v1.18.
FORBID = {"tests/ok.py": "import os, sys\nsys.exit(1 if os.path.exists('doomed.txt') else 0)\n"}
ALWAYS_FAIL = {"tests/ok.py": "import sys\nsys.exit(1)\n"}


def _world_with_doomed(tmp, spec, extra):
    home, repo, stage = H._world(tmp, spec, extra=extra)
    with open(os.path.join(repo, "doomed.txt"), "w") as f:
        f.write("this file is deleted by the delivery\n")
    H._run("git add doomed.txt; git commit -q -m 'add doomed'; git push -q origin main", cwd=repo)
    H._restamp_base(os.path.join(stage, "half", "land.spec"), repo)
    return home, repo, stage


def _unattended(r):
    return r.returncode == 9 and "UNATTENDED" in (r.stdout + r.stderr).upper()


def main():
    print("check_land_del_order — land.sh runs DEL before the CHECKs (v1.19)")
    if not os.path.exists(H.LAND):
        check("O0 tools/land.sh exists", False, H.LAND)
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        spec = H.GOOD + ["DEL doomed.txt"]
        home, repo, stage = _world_with_doomed(tmp, spec, FORBID)
        r = H._land(home, stage)
        if _unattended(r):
            check("O1 (not run: the lander refuses an UNATTENDED caller, exit 9)", False, "run it attended")
            return 1
        tracked = H._run("git ls-files doomed.txt", cwd=repo).stdout.strip()
        check("O1 a spec that deletes a file its CHECK forbids LANDS",
              r.returncode == 0 and tracked == "" and not os.path.exists(os.path.join(repo, "doomed.txt")),
              f"rc={r.returncode} tracked={tracked!r} tail={(r.stdout or '')[-160:]!r}")
        check("O1b ...and the removal is committed, the tree clean", r.returncode == 0 and not H._dirty(repo),
              f"dirty={H._dirty(repo)!r}")

    with tempfile.TemporaryDirectory() as tmp:
        home, repo, stage = H._world(tmp, H.GOOD + ["DEL no_such_file.md"], extra=H.PASS_CHK)
        r = H._land(home, stage)
        check("O2 a DEL of a missing file is still REFUSED, HEAD unmoved",
              r.returncode != 0 and H._head(repo) == "base" and "not present" in (r.stdout + r.stderr),
              f"rc={r.returncode} head={H._head(repo)!r}")

    with tempfile.TemporaryDirectory() as tmp:
        home, repo, stage = _world_with_doomed(tmp, H.GOOD + ["DEL doomed.txt"], ALWAYS_FAIL)
        before = H._head(repo)
        r = H._land(home, stage)
        out = r.stdout + r.stderr
        check("O3 a refused land that deletes a file leaves HEAD where it was",
              r.returncode != 0 and H._head(repo) == before, f"rc={r.returncode} head={H._head(repo)!r}")
        m = re.search(r"^\s+(cd .+ && git reset -q HEAD -- .+)$", out, re.M)
        ok3b, why = False, "no recipe printed"
        if m:
            fix = H._run(m.group(1), cwd=repo)
            back = os.path.exists(os.path.join(repo, "doomed.txt"))
            ok3b = fix.returncode == 0 and back and not H._dirty(repo)
            why = f"recipe rc={fix.returncode} restored={back} dirty={H._dirty(repo)!r}"
        check("O3b ...and die()'s discard recipe restores the DEL'd file, tree clean", ok3b, why)

    print()
    if _fails:
        print(f"RED — {len(_fails)} failed: {', '.join(_fails)}")
        return 1
    print("GREEN — check_land_del_order")
    return 0


if __name__ == "__main__":
    sys.exit(main())
