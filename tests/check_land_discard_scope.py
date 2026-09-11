#!/usr/bin/env python3
"""
day_trader_pro/tests/check_land_discard_scope.py  v1.0
v1.0  2026-09-11  dtp r360 / LAND.2 — a failed land must not tell the operator
      to discard his whole tree.

🔴 WHAT IT COST. `logs/eod_conductor.log` was git-TRACKED and every close
appends to it. On a failed land, `die()` counted it as "uncommitted file(s)
from the extract" and printed
`git reset -q HEAD -- . && git checkout -- . && git clean -fd`, which restored
it to its 2026-09-03 committed version. Two nights of conductor output gone —
and the file was later read as though it were the record of those runs.

🔑 The command already walks its own payload list to stage by name; on the
rollback path the `--soft` reset leaves exactly the payload in the INDEX. Both
scopes were available the whole time.

  L1  no live `git checkout -- .` remains in either recipe
  L2  no live `git clean -fd` remains — it deletes untracked files anywhere,
      the operator inbox included
  L3  the die() recipe names the payload from the extract directory
  L4  the rollback recipe names the payload from the index (`--cached`)
  L5  the wording no longer asserts every dirty file came from the extract
"""
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILS = []


def check(name, ok, detail=""):
    print("  {:<4} {}  {}".format(name, "PASS" if ok else "FAIL", detail))
    if not ok:
        FAILS.append(name)


def main():
    src = open(os.path.join(REPO, "tools", "land.sh"), encoding="utf-8").read()
    # comments explain the old behaviour by quoting it — judge CODE only.
    code = "\n".join(l for l in src.splitlines()
                     if not l.lstrip().startswith("#"))

    bad_co = [l.strip()[:70] for l in code.splitlines()
              if "git checkout -- ." in l]
    check("L1", not bad_co, bad_co[0] if bad_co else "no unscoped checkout")

    bad_cl = [l.strip()[:70] for l in code.splitlines() if "clean -fd" in l]
    check("L2", not bad_cl, bad_cl[0] if bad_cl else "no clean -fd in code")

    check("L3", "! -name land.spec -printf" in code and "_pay" in code,
          "die() names the payload from the extract dir")

    check("L4", "git diff --cached --name-only" in code,
          "rollback names the payload from the index")

    check("L5", "SOME MAY NOT BE FROM THE EXTRACT" in code,
          "wording no longer asserts provenance")

    print("")
    if FAILS:
        print("FAILED: {}".format(", ".join(FAILS)))
        return 1
    print("ALL PASS (5)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
