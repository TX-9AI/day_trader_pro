#!/usr/bin/env python3
"""
tests/check_handoff_item.py  v1.0
v1.0  2026-09-12  r368 — THE HANDOFF ITEM, AND THE THREE THINGS THAT WOULD
      OTHERWISE BITE IT SILENTLY.

The menu item hands the session to a fresh Claude thread. Every failure it can
have is QUIET — a thread that bills the wrong account, a binary that cannot be
found under a venv, a kill that takes out the client before it has moved — so
each is pinned here rather than discovered in use.

H2 IS THE EXPENSIVE ONE. `~/.bashrc` sources day_trader_pro/.env for
selector.py, so ANTHROPIC_API_KEY is present in every interactive shell. A
thread launched without unsetting it bills the API instead of the Max
subscription, works perfectly, and says nothing.
"""
import os
import re
import subprocess
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_fails = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))
    if not ok:
        _fails.append(name)


def read(*parts):
    """Missing file reads as EMPTY, never as a traceback.

    ⚠️ A GATE THAT RAISES IS A WORSE GATE THAN ONE THAT FAILS. Born red at dtp
    404ac67 this file exploded with FileNotFoundError on the absent generator,
    which reports "something is wrong somewhere" instead of naming the checks
    that do not hold. Empty content fails every assertion below by name.
    """
    try:
        return open(os.path.join(_root, *parts), encoding="utf-8").read()
    except OSError:
        return ""


def main():
    print("check_handoff_item — the fresh-thread handoff")
    fn = read("menu_functions.sh")
    rg = read("menu_registry.sh")

    body = fn.split("mi_handoff_fresh_claude() {", 1)
    check("H1 the function exists", len(body) == 2)
    b = body[1].split("\n}\n", 1)[0] if len(body) == 2 else ""

    check("H2 the API key is unset before claude is launched — it bills the "
          "subscription, not the API",
          b.count("env -u ANTHROPIC_API_KEY") >= 1
          and "claude" in b)

    # H3 — every invocation must use the ABSOLUTE path. A bare `claude` under a
    # venv resolves against a PATH that predates ~/.local/bin.
    bare = [ln.strip() for ln in b.splitlines()
            if re.search(r"(^|[;&|\s])claude\s+\"", ln) and "$CLAUDE" not in ln]
    check("H3 claude is invoked by ABSOLUTE path, never bare", not bare,
          "; ".join(bare[:2]))

    # H4 — ORDER. switch-client must appear before any kill of other sessions,
    # or the client dies with the session it is attached to.
    i_sw, i_kill = b.find("switch-client"), b.find("kill-session")
    check("H4 the client switches BEFORE anything is killed",
          i_sw != -1 and i_kill != -1 and i_sw < i_kill,
          f"switch@{i_sw} kill@{i_kill}")

    check("H5 the item is registered in the menu",
          "mi_handoff_fresh_claude" in rg)

    # H6 — the generator must REFUSE rather than emit an unverified fleet claim,
    # and the item must not proceed when it does.
    gen = read("tools", "gen_handoff.py")
    check("H6 the generator refuses instead of guessing at the fleet",
          "REFUSING" in gen and "return 2" in gen)
    check("H6b and the menu item stops when it refuses",
          "gen_handoff.py" in b and "return 1" in b)

    # H7 — DRIVEN, not read. The generator must actually run and emit the
    # operator's brief plus the pointer list (§21: source text proves nothing).
    _g = os.path.join(_root, "tools", "gen_handoff.py")
    if os.path.exists(_g):
        r = subprocess.run([sys.executable, _g, "--no-fleet"],
                           capture_output=True, text=True, timeout=120)
        out, rc = r.stdout, r.returncode
    else:
        out, rc = "", 127
    check("H7 it runs and emits the brief verbatim",
          rc == 0 and "Vertigo Capital" in out
          and "information layer" in out,
          f"rc={rc}")
    check("H7b it POINTS at the agreement and backlog rather than restating them",
          "docs/WORKING_AGREEMENT.md" in out and "docs/BACKLOG.md" in out
          and "OPEN ROWS" in out)
    check("H7c it does NOT tell an on-box thread to clone",
          "clone" not in out.lower().split("nothing to clone")[0])

    # H8 — open means the STATUS column. The first draft filtered on the 🔴
    # severity marker and listed long-closed rows as outstanding.
    check("H8 open rows are read from the status column, not the severity mark",
          '"⬜" in cols[3]' in gen)

    print()
    if _fails:
        print(f"FAILED {len(_fails)}: {', '.join(_fails)}")
        return 1
    print("check_handoff_item: all checks pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
