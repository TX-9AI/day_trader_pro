#!/usr/bin/env python3
"""
tools/check_shell_parses.py  v1.1
v1.1  2026-09-12  r373 / SH.2 — S0 IS FATAL ONLY IN SELF MODE. Wired into the
      lander with S0 fatal unconditionally, this refused EVERY land in
      `check_land_sh`, whose fixture repo carries no shell at all: 21 checks
      red for a property of the target rather than a defect in it, which is
      the CV.1 shape — a gate that goes red about the environment teaches the
      reader to skip reds. An empty sweep of THIS repo still means something
      moved; an empty sweep of a named --repo is a true answer about a real
      tree. Zero still prints as its own named outcome either way.
v1.0  2026-09-12  r372 / SH.2 — EVERY SHELL SCRIPT IN *ANY* REPO MUST PARSE,
      AND THE LANDER ASKS ON EVERY LAND RATHER THAN WAITING TO BE DECLARED.

🔴 THE ORIGINAL FAILURE (SH.1, otv4 r322). r65 wrote its changelog entry into
four shell headers WITHOUT the leading `#`, so three lines of prose became
three lines of shell and the parenthesis in "(delivery)" was a syntax error.
**A syntax error aborts the parse**, so `devtools.sh`, `check_versions.sh`,
`push.sh` and `install_tooling.sh` did NOTHING AT ALL for fourteen days — on
every box, at every revision — and it surfaced only because the operator ran
`./devtools.sh` by hand and read the error.

🔴 WHY THIS FILE EXISTS ON TOP OF THAT ONE, WHICH IS SH.2. r322's repair landed
in **otv4** and walks its OWN root, so it covered otv4's 18 scripts and could
not see day_trader_pro's 15 — among them `menu_functions.sh`, `menu_registry.sh`
and `land.sh` and `deploy.sh` themselves, **the entire delivery mechanism.**
The defect was fixed where it was found and the neighbouring tree was never
swept, which is §23 stated exactly. Found 2026-09-12 while shipping shell edits
to dtp under r371.

🔑 ONE IMPLEMENTATION, NOT TWO, AND THE PRECEDENT IS `check_land_discipline`.
The tempting fix was a second copy in `dtp/tests/`. Two copies of one checker is
the drift §7 and §25 name — whichever gets updated becomes the truth and the
other rots. So this lives in `tools/` beside `check_land_discipline.py`, takes
`--repo`, and is invoked BY `land.sh` for whichever repo is being landed, the
same way that one is. otv4's copy is retired in the same revision.

⚠️ AND THE REASON IT IS WIRED TO THE LANDER RATHER THAN DECLARED AS A `CHECK`.
A `CHECK` line has to be remembered by the author of every future `land.spec`.
SH.1's finding was not that a check failed — it was that **nothing was
looking**. A gate you must remember to declare is a gate that gets forgotten,
which is [[SHD.5]]'s lesson one file over: a checker with nothing scheduled to
invoke it is a log, not a gate. Wired here it runs on every land of either
repo, and an author cannot forget it.

⚠️ IT IS FATAL, AND THAT IS A NEW FAILURE MODE ON THE CRITICAL PATH — said out
loud because every delivery passes through the lander. From r372 an unparseable
`.sh` anywhere in the target repo REFUSES the land. That is the intent: the
alternative is the fourteen silent days above. It names the file and the first
line of bash's own error, never just a count (§0.5).

WHAT IT CHECKS: `bash -n` — parse, do not execute — over every `*.sh` in the
target tree. It cannot catch a script that parses and misbehaves; that is what
the callers' own checks are for. "Did not parse at all" is the whole of this
class and it is cheap to make impossible.

Run:  python3 tools/check_shell_parses.py [--repo <path>]
      (default: the repo this file lives in)
"""
import argparse
import os
import subprocess
import sys

SKIP_DIRS = {".git", "venv", "__pycache__", "node_modules", ".venv"}

FAILED = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))
    if not ok:
        FAILED.append(name)


def scripts(root):
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for n in sorted(files):
            if n.endswith(".sh"):
                yield os.path.join(base, n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=None,
                    help="tree to sweep (default: the repo this file lives in)")
    a = ap.parse_args()
    root = os.path.abspath(a.repo) if a.repo else os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))

    # ⚠️ A MISSING TARGET IS A NAMED FAILURE, NOT AN EMPTY SWEEP. Handed a path
    # that does not exist, a walk yields nothing and "0 checked, all pass" is
    # the laundered green this file exists to prevent — the same shape as the
    # fan-out that printed `15/15 succeeded` over fifteen blank fields (OPS.6).
    if not os.path.isdir(root):
        print(f"check_shell_parses — REFUSING: {root} is not a directory")
        return 2

    self_mode = a.repo is None
    print(f"check_shell_parses — {root}" + ("" if self_mode else "  (--repo)"))
    found = list(scripts(root))

    # 🔴 S0 IS FATAL ONLY IN SELF MODE, AND THE DISTINCTION IS THE WHOLE POINT.
    # An empty sweep of THIS repo means something moved or an extension was
    # renamed — the laundered green SH.1's gate exists to refuse. But handed an
    # explicit --repo, zero scripts is a legitimate answer about a legitimate
    # tree, and "every shell script parses" is then vacuously TRUE.
    # ⚠️ FOUND BY BREAKING 21 CHECKS. Wired into the lander with S0 fatal
    # unconditionally, this refused every land in `check_land_sh`, whose
    # fixture repo carries no shell at all — a gate failing for a property of
    # the target rather than a defect in it, which is the CV.1 shape §36 names:
    # a red about the environment teaches the reader to ignore reds.
    # 🔑 IT IS STILL NOT SILENT. Zero prints as its own named outcome, so
    # "nothing to check" can never be mistaken for "everything checked".
    if found or self_mode:
        check("S0 the sweep actually found shell scripts", len(found) > 0,
              f"{len(found)} found")
    else:
        print("  NONE  this tree carries no shell scripts — nothing to parse")

    bad = []
    for path in found:
        r = subprocess.run(["bash", "-n", path], capture_output=True, text=True)
        if r.returncode != 0:
            first = (r.stderr.strip().splitlines() or ["(no stderr)"])[0]
            bad.append(f"{os.path.relpath(path, root)}: {first.strip()}")

    check("S1 every shell script parses (bash -n)", not bad,
          f"{len(found)} checked" if not bad else "; ".join(bad))

    # S2 — the SPECIFIC shape that caused SH.1: a version/changelog line in a
    # header that lost its `#`. Narrower and faster than a parse error, and it
    # names the actual mistake rather than bash's downstream complaint.
    shape = []
    for path in found:
        try:
            lines = open(path, encoding="utf-8").read().splitlines()[:20]
        except Exception:                                        # noqa: BLE001
            continue
        for i, ln in enumerate(lines[:12], 1):
            s = ln.strip()
            if not s or s.startswith("#") or s.startswith("set ") or i == 1:
                continue
            if s[:1] == "v" and len(s) > 3 and s[1].isdigit():
                shape.append(f"{os.path.relpath(path, root)}:{i}: {s[:48]}")
            break
    check("S2 no uncommented changelog line in a shell header", not shape,
          "; ".join(shape) if shape else "")

    print()
    if FAILED:
        print(f"RED — {len(FAILED)} failed: {', '.join(FAILED)}")
        return 1
    # ⚠️ THE SUMMARY MUST NOT SAY "GREEN — 0 parse", WHICH READS AS A RESULT
    # WHEN IT IS AN ABSENCE. "nothing to check" and "everything checked" are
    # different facts and this project keeps finding them conflated.
    if not found:
        print("GREEN (VACUOUS) — no shell scripts in this tree; nothing was parsed")
    else:
        print(f"GREEN — {len(found)} shell script(s) parse")
    return 0


if __name__ == "__main__":
    sys.exit(main())
