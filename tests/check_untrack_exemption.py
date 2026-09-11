#!/usr/bin/env python3
"""
day_trader_pro/tests/check_untrack_exemption.py  v1.0
v1.0  2026-09-11  dtp r360 / LAND.8 — an index-only untrack is a legitimate
      commit, and forcing it past the hook must not be the only way.

🔴 WHY. `git rm --cached <f>` diffs as nothing but deletions, so the BUMP rule
("a land that changes no source is a land that did not happen") refused it.
The only path through was `--no-verify`, which disables EVERY check — the
GENESIS row, the maps, the per-file bookkeeping. **A rule whose sole escape
hatch is "turn off all the rules" eventually gets used that way**, and that is
a worse outcome than the rule it was protecting.

Measured on `logs/eod_conductor.log`: a tracked runtime artifact whose
untracking (LAND.2) had to be forced.

  U1  an all-deletions commit of IGNORED paths still on disk is ALLOWED, and
      says so in the notes rather than passing silently
  U2  an all-deletions commit of a NON-ignored path is still REFUSED — a
      deleted module is a source change and needs its bookkeeping
  U3  a deletion that also removed the file is NOT an untrack, and is refused
  U4  a mixed commit (one deletion + one edit) is untouched by the exemption
      and still goes through the normal per-file checks
"""
import os
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILS = []


def check(name, ok, detail=""):
    print("  {:<4} {}  {}".format(name, "PASS" if ok else "FAIL", detail))
    if not ok:
        FAILS.append(name)


def git(args, cwd):
    return subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)


def scenario(make):
    """Build a throwaway repo, let `make` stage something, run the checker."""
    d = tempfile.mkdtemp()
    git(["init", "-q"], d)
    git(["config", "user.email", "t@t"], d)
    git(["config", "user.name", "t"], d)
    os.makedirs(os.path.join(d, "logs"), exist_ok=True)
    open(os.path.join(d, "mod.py"), "w").write("# mod.py  v1.0\nx = 1\n")
    open(os.path.join(d, "logs", "run.log"), "w").write("line\n")
    open(os.path.join(d, ".gitignore"), "w").write("logs/\n")
    git(["add", "-A", "-f"], d)
    git(["commit", "-q", "-m", "base"], d)
    make(d)
    p = subprocess.run([sys.executable,
                        os.path.join(REPO, "tools", "check_land_discipline.py"),
                        "--repo", d, "--hook"],
                       capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def main():
    rc, out = scenario(lambda d: git(["rm", "--cached", "-q", "logs/run.log"], d))
    check("U1", rc == 0 and "index-only untrack" in out,
          "ignored path untracked -> rc={} noted={}".format(
              rc, "index-only untrack" in out))

    rc2, _ = scenario(lambda d: git(["rm", "--cached", "-q", "mod.py"], d))
    check("U2", rc2 != 0, "non-ignored deletion still refused (rc={})".format(rc2))

    def gone(d):
        git(["rm", "-q", "-f", "--cached", "logs/run.log"], d)
        os.remove(os.path.join(d, "logs", "run.log"))
    rc3, _ = scenario(gone)
    check("U3", rc3 != 0,
          "file removed from disk is not an untrack (rc={})".format(rc3))

    def mixed(d):
        git(["rm", "--cached", "-q", "logs/run.log"], d)
        open(os.path.join(d, "mod.py"), "a").write("y = 2\n")
        git(["add", "mod.py"], d)
    rc4, out4 = scenario(mixed)
    check("U4", "index-only untrack" not in out4,
          "mixed commit not exempted; normal checks apply")

    print("")
    if FAILS:
        print("FAILED: {}".format(", ".join(FAILS)))
        return 1
    print("ALL PASS (4)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
