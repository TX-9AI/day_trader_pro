#!/usr/bin/env python3
"""
day_trader_pro/tests/check_land_spec_parse.py  v1.0
v1.0  2026-09-20  dtp r392 / LAND.10 — A `NEG` WHOSE PATH DOES NOT RESOLVE
      PASSED SILENTLY, AND A NEG IS THE ONLY THING PROVING SUPERSEDED CODE IS
      GONE.

🔴 THE FAULT. `land.sh` stripped exactly ONE space per directive while the
format block in the same file documents COLUMN-ALIGNED examples, so a spec
written from the documentation yielded a path of "   path". The two directives
then failed in OPPOSITE directions:
  · POS greps with `!` — an unresolvable path FLAGS. Fails closed, loudly.
  · NEG greps WITHOUT `!` and swallows the error with 2>/dev/null, so
    file-not-found read as "the string is absent" and THE ASSERTION PASSED.
A vacuous NEG certifies a removal without looking. v1.3's own finding — "one
failed open and one failed closed ... a gate that can do either is unrelated
to the thing it claims to check" — recurring in the PARSER.

⚠️ THE SAFETY BIT IS NOT OPTIONAL AND IS CHECKED FIRST. `land.sh` finds its
target by scanning `$HOME/*/` for the spec's REPO markers, and the REAL
checkouts carry those markers — this is the script that COMMITS AND PUSHES. So
every case runs with HOME REDIRECTED into a scratch tree under a marker that
exists nowhere else, and L0 aborts the whole file if a run ever names a repo
outside it. A gate that can reach the live checkout is worse than no gate.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
LANDER = os.path.join(REPO_ROOT, "tools", "land.sh")

FAILS, RAN = [], []


def ck(n, ok, msg):
    RAN.append(n)
    print(f"  {n:<4} {'PASS' if ok else 'FAIL'}  {msg}")
    if not ok:
        FAILS.append(n)



def gate(out):
    """The CONTENT GATE's own verdict: 'pass', 'fail', or 'not reached'.

    🔑 THE ASSERTIONS ARE SCOPED TO THE STAGE r392 CHANGES, DELIBERATELY.
    Grading on the lander's overall exit code conflates the parser with every
    later stage: a synthetic half legitimately refuses at BUMP ("a land that
    changes no source is a land that did not happen") and at
    check_shell_parses, neither of which says anything about directive
    parsing. A red for the wrong reason is worse than no red — it reads as the
    fix not working. The full pipeline still RUNS; only the verdict read is
    narrowed, and it is narrowed in the open.
    """
    if "CONTENT GATE FAILED" in out:
        return "fail"
    if "content gate: pass" in out:
        return "pass"
    return "not reached"


MARKER = "LAND_SPEC_PARSE_MARKER.txt"     # exists in no real checkout


def run_case(spec_body, payload=None, marker_file=True):
    """Land a synthetic half inside a sandboxed HOME. Returns (rc, output)."""
    home = tempfile.mkdtemp(prefix="landspec_home_")
    repo = os.path.join(home, "target_repo")
    os.makedirs(repo)
    subprocess.run(["git", "init", "-q", repo], check=True)
    if marker_file:
        open(os.path.join(repo, MARKER), "w").write("marker\n")
    # ⚠️ THE REPO IS SEEDED WITH *DIFFERENT* CONTENT ON PURPOSE. Seeding it
    # with the payload made the land change nothing, and
    # `check_land_discipline`'s BUMP rule correctly refused it — so every
    # "this should land" case was failing for a reason that had nothing to do
    # with the parser. A red for the wrong reason is worse than no red: it
    # would have been read as the fix not working.
    for name in (payload or {}):
        p = os.path.join(repo, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").write("seed — superseded by the payload\n")
    subprocess.run(["git", "-C", repo, "add", "-A"], check=True,
                   capture_output=True)
    subprocess.run(["git", "-C", repo, "-c", "user.email=x@y", "-c",
                    "user.name=x", "commit", "-qm", "base"], check=True,
                   capture_output=True)
    # ⚠️ A BARE ORIGIN INSIDE THE SANDBOX. The lander pulls before it extracts
    # and pushes after it commits; with no remote it dies at "PULL FAILED"
    # and every case below would fail for the wrong reason — a red that says
    # nothing about the parser. The remote is a bare repo in the SAME temp
    # tree, so the full commit-and-push path is exercised end to end and
    # still cannot reach anything real.
    origin = os.path.join(home, "origin.git")
    subprocess.run(["git", "init", "-q", "--bare", origin], check=True)
    br = subprocess.run(["git", "-C", repo, "rev-parse", "--abbrev-ref", "HEAD"],
                        capture_output=True, text=True).stdout.strip()
    subprocess.run(["git", "-C", repo, "remote", "add", "origin", origin],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", repo, "push", "-q", "-u", "origin", br],
                   check=True, capture_output=True)
    base = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()

    stage = tempfile.mkdtemp(prefix="landspec_stage_")
    half = os.path.join(stage, "half")
    os.makedirs(half)
    for name, body in (payload or {}).items():
        p = os.path.join(half, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").write(body)
    # 🔑 THE REAL LANDER, END TO END — its own tail stages are copied in rather
    # than stubbed, so a PASS here means the whole pipeline ran and not just
    # the part under test. Without these the land refused at
    # "check_shell_parses.py NOT FOUND" while the content gate had already
    # passed, which would have graded the parser on an unrelated stage.
    tools = os.path.join(repo, "tools")
    os.makedirs(tools, exist_ok=True)
    for t in ("check_shell_parses.py", "check_land_discipline.py"):
        src = os.path.join(REPO_ROOT, "tools", t)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(tools, t))
    subprocess.run(["git", "-C", repo, "add", "-A"], capture_output=True)
    subprocess.run(["git", "-C", repo, "-c", "user.email=x@y", "-c",
                    "user.name=x", "commit", "-qm", "tools"],
                   capture_output=True)
    subprocess.run(["git", "-C", repo, "push", "-q", "origin", br],
                   capture_output=True)
    base = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    spec = spec_body.replace("@BASE@", base).replace("@MARKER@", MARKER)
    open(os.path.join(half, "land.spec"), "w").write(spec)
    shutil.copy(LANDER, os.path.join(stage, "land.sh"))

    env = dict(os.environ, HOME=home, GIT_AUTHOR_NAME="x",
               GIT_AUTHOR_EMAIL="x@y", GIT_COMMITTER_NAME="x",
               GIT_COMMITTER_EMAIL="x@y")
    env.pop("LAND_ARCHIVE", None)
    env.pop("LAND_STAGE", None)
    r = subprocess.run(["bash", os.path.join(stage, "land.sh"), "half"],
                       capture_output=True, text=True, env=env, timeout=180)
    out = r.stdout + r.stderr
    shutil.rmtree(home, ignore_errors=True)
    shutil.rmtree(stage, ignore_errors=True)
    return r.returncode, out, home


SPEC = """REPO @MARKER@
REV r999
DESC synthetic
BASE @BASE@
ORDER 1
{body}
"""

# ───────────────────────────────────────────────────────────── L0 (SAFETY)
rc, out, sandbox = run_case(SPEC.format(body="POS f.txt|hello"),
                            {"f.txt": "hello\n"})
named = re.findall(r"repo: (\S+)", out)
leaked = [p for p in named if not p.startswith("/tmp")]
ck("L0", not leaked,
   f"SAFETY — the lander only ever named a sandboxed repo: {named or 'none'}"
   + (f"  🔴 LEAKED {leaked}" if leaked else ""))
if leaked:
    print("\n  🔴 ABORTING: a case reached outside the sandbox. This script "
          "invokes the thing that commits and pushes.")
    sys.exit(1)

# ───────────────────────────────────────────────────────────── L1
ck("L1", gate(out) == "pass",
   f"a well-formed single-space spec still passes the content gate "
   f"({gate(out)})")

# ───────────────────────────────────────────────────────────── L2 — THE BUG
rc, out, _ = run_case(SPEC.format(body="NEG no_such_file.txt|anything"),
                      {"f.txt": "hello\n"})
ck("L2", gate(out) == "fail" and "UNRESOLVABLE NEG" in out,
   f"a NEG naming a NON-EXISTENT file REFUSES (rc={rc}) — before r392 it "
   f"passed in silence and certified a removal it never looked for")

# ───────────────────────────────────────────────────────────── L3 — alignment
rc, out, _ = run_case(SPEC.format(body="NEG    f.txt|gone_string"),
                      {"f.txt": "hello\n"})
ck("L3", gate(out) == "pass",
   f"the COLUMN-ALIGNED form the format block documents now parses and the "
   f"absent string genuinely passes ({gate(out)})")

rc, out, _ = run_case(SPEC.format(body="NEG    f.txt|hello"),
                      {"f.txt": "hello\n"})
ck("L3b", gate(out) == "fail" and "STILL PRESENT" in out,
   f"and the aligned form FLAGS when the string is really there (rc={rc}) — "
   f"so L3 is not passing because the directive was skipped")

# ───────────────────────────────────────────────────────────── L4 — POS too
rc, out, _ = run_case(SPEC.format(body="POS    f.txt|hello"),
                      {"f.txt": "hello\n"})
ck("L4", gate(out) == "pass", f"aligned POS parses ({gate(out)})")

rc, out, _ = run_case(SPEC.format(body="POS nope.txt|x"), {"f.txt": "hello\n"})
ck("L4b", gate(out) == "fail" and "UNRESOLVABLE POS" in out,
   f"an unresolvable POS path is named as unresolvable, not merely MISSING "
   f"(rc={rc})")

# ───────────────────────────────────────────────────────────── L5
# 🔑 THE LITERAL IS NEVER TRIMMED. r390 asserted on an EIGHT-SPACE-INDENTED
# code line precisely so a comment quoting the old code could not satisfy it.
# A normaliser that trimmed the literal would silently re-break that gate.
rc, out, _ = run_case(SPEC.format(body="NEG f.py|        rec_stop = 0.25"),
                      {"f.py": "# rec_stop = 0.25 was applied to every row\n"})
ck("L5", gate(out) == "pass",
   f"an INDENTED literal is preserved byte-for-byte, so a comment quoting the "
   f"old code does NOT satisfy the NEG ({gate(out)})")

rc, out, _ = run_case(SPEC.format(body="NEG f.py|        rec_stop = 0.25"),
                      {"f.py": "        rec_stop = 0.25\n"})
ck("L5b", gate(out) == "fail" and "STILL PRESENT" in out,
   f"and it DOES flag the real indented code line ({gate(out)}) — L5 is not "
   f"passing because the literal was mangled")

print()
if FAILS:
    print(f"FAILED: {', '.join(FAILS)}")
    sys.exit(1)
print(f"ALL PASS ({len(RAN)})")
