#!/usr/bin/env python3
"""
tests/check_no_undefined_names.py  v1.0
v1.0  2026-09-08  dtp r322 / CND.1 — NO MODULE MAY USE A NAME IT NEVER BOUND.

🔴 THE FAILURE THIS EXISTS FOR. On 2026-09-08 the fleet was still up at 16:35
because `dtp-eod-conductor.service` had failed at 16:05 — and had failed every
session since dtp r287 landed on 09-05. The cause:

    v2.1    2026-08-27  THE RETENTION PURGE IS A CONDUCTOR PHASE. It was called
    from warehouse/self_close.py, which fires at 16:45 — but this conductor stops
    import ettime                                            # noqa: E402
    the boxes by ~16:08, so on any NORMAL night that timer fired into a stopped

`import ettime` was pasted INTO THE MIDDLE OF A SENTENCE in the module
docstring. Python read it as prose, the name was never bound, and the failure
surfaced 436 lines later at first use — a `NameError`, not an `ImportError`, in
the same second the service started. The identical mistake landed in
`fit_readiness.py` in the same revision.

⚠️ EVERY GATE WAS SELF-CONSISTENT AND EVERY GATE PASSED. The file parses. It
imports. Its header is bumped and its changelog agrees. `check_land_discipline`
had nothing to object to. The defect was invisible until the code RAN, and the
one thing that runs it is a 16:05 timer nobody watches — the conductor's own
log even showed a healthy VERIFY/PURGE block, from the last night it worked.

🔑 THE SAME CLASS BIT THE OTHER REPO THE SAME DAY. otv4 SH.1: r65 wrote a
changelog entry into four shell headers without `#`, and those scripts aborted
on a syntax error for fourteen days. Both are one failure: **a header block and
executable code sharing a file, and the boundary getting lost.** §5 requires a
changelog entry in every edited file; nothing was checking that the entry stayed
inert.

WHAT THIS CHECKS: `pyflakes` over the tree, failing on `undefined name`. That is
a static answer to "would this raise NameError when it ran", and it needs no
credentials, no fleet and no market. It found four on the day it was written —
the two above, plus `rrows` in `consolidate_trades.py` (an orphaned loop whose
producer had been deleted, which raised past `except sqlite3.DatabaseError` and
broke consolidation outright) and `AUTO_LABEL_PY` in the v1 conductor, which is
the ROLLBACK TARGET `install_eod_v2.sh` seds back to.

⚠️ A MISSING pyflakes IS RED, NOT SKIP. A checker that goes quiet when its tool
is absent hands out a green light on an unchecked tree — the bootstrap lesson:
a tooling check must exercise the tooling's actual job.

⚠️ SCOPE: undefined names ONLY. pyflakes also reports unused imports and
f-strings without placeholders; those are style and this file does not fail on
them, because a gate that fires on things nobody intends to fix trains the
reader to skip its output.

Run:  python3 tests/check_no_undefined_names.py
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", "venv", "__pycache__", "node_modules", "logs", "reports"}

FAILED = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))
    if not ok:
        FAILED.append(name)


def modules():
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for n in sorted(files):
            if n.endswith(".py"):
                yield os.path.join(base, n)


def main():
    files = list(modules())
    check("C0 the sweep found python modules", len(files) > 0, f"{len(files)} found")

    probe = subprocess.run([sys.executable, "-m", "pyflakes", "--version"],
                           capture_output=True, text=True)
    if probe.returncode != 0:
        check("C1 pyflakes is available", False,
              f"install it: {os.path.basename(sys.executable)} -m pip install pyflakes")
        print("\nRED — the tool this check depends on is absent; the tree is UNCHECKED")
        return 1
    check("C1 pyflakes is available", True, probe.stdout.strip() or probe.stderr.strip())

    r = subprocess.run([sys.executable, "-m", "pyflakes"] + files,
                       capture_output=True, text=True)
    undefined = [l for l in (r.stdout + r.stderr).splitlines()
                 if "undefined name" in l]
    undefined = [os.path.relpath(l, ROOT) if l.startswith(ROOT) else l
                 for l in undefined]

    check("C2 no module uses a name it never bound", not undefined,
          f"{len(files)} module(s) clean" if not undefined
          else " | ".join(u.strip() for u in undefined[:6]))

    print()
    if FAILED:
        print(f"RED — {len(FAILED)} failed: {', '.join(FAILED)}")
        return 1
    print(f"GREEN — {len(files)} module(s), no undefined names")
    return 0


if __name__ == "__main__":
    sys.exit(main())
