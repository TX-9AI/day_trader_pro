#!/usr/bin/env python3
"""
tests/check_resume_item.py  v1.1
v1.1  2026-09-12  r374 / OPS.14 — R10/R10b PIN THE PAIRING ITSELF. The operator
      asked that items 37 and 38 point at the same place: *"if I start a
      conversation with 37 that's the one I want to resume with 38."* They did
      — by coincidence of three literals agreeing, with nothing comparing them.
      R10 asserts the RELATIONSHIP rather than either value, because pinning
      each item's path separately goes green on two items pointing at two
      different directories, each correct alone. R10b requires the name be
      defined once, so there is no second copy left to drift.
v1.0  2026-09-12  r371 — THE RESUME ITEM, AND THE TWO WAYS A RESUME LIES ABOUT
      HAVING WORKED.

`RESUME -> continue the last Claude thread` hands the session to a Claude
process started with `--continue`. It shares three traps with the handoff item
(R2/R3/R4, pinned there as H2/H3/H4 and pinned again here because the failure
is per-item, not per-file), and it adds two that are its own:

🔴 R6 — THE CWD IS LOAD-BEARING. `--continue` resumes the most recent
conversation FOR A DIRECTORY. Launched from anywhere else it finds no prior
conversation and opens a FRESH thread — with no context and no handoff, which
is indistinguishable from a successful resume until the operator notices the
model knows nothing. A wrong directory here is a silent wrong answer, not an
error, which is the class this repo keeps finding.

🔴 R8 — THE FALLBACK MUST REPORT BEFORE IT CATCHES. `exec bash -l` is exactly
what turned r368's dead launch into a bare prompt nobody could explain, and the
r368-note states the lesson: a fallback that catches a failure without
reporting it converts a crash into a mystery. A resume LEGITIMATELY fails when
there is no prior conversation for the directory, so that path must print why.
R8 asserts the report sits between the launch and the `exec`.

⚠️ R3's FIRST CUT WENT RED ON THIS FILE'S OWN SIBLING PROSE — it searched for
`claude --` anywhere and matched the echo that TELLS the operator the item runs
`claude --continue`. That is §20: good display text tripping a string canary.
It is anchored on the launch shape now (the mandatory `env -u` prefix), not on
the word, because the alternative — rewording the echo to keep a grep green —
degrades the thing the operator reads in order to protect the test.
"""
import os
import re
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_fails = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))
    if not ok:
        _fails.append(name)


def read(*parts):
    """Missing file reads as EMPTY, never as a traceback (check_handoff_item's
    own lesson: a gate that raises names nothing)."""
    try:
        return open(os.path.join(_root, *parts), encoding="utf-8").read()
    except OSError:
        return ""


def main():
    print("check_resume_item — RESUME -> continue the last Claude thread")
    fn = read("menu_functions.sh")
    rg = read("menu_registry.sh")

    body = fn.split("mi_resume_claude_tmux() {", 1)
    check("R1 the function exists", len(body) == 2)
    b = body[1].split("\n}\n", 1)[0] if len(body) == 2 else ""

    check("R2 the API key is unset before claude is launched — it bills the "
          "subscription, not the API",
          b.count("env -u ANTHROPIC_API_KEY") >= 1 and "claude" in b.lower())

    # 🔴 R3 IS ANCHORED ON THE LAUNCH SHAPE, NOT ON THE WORD "claude", AND ITS
    # FIRST CUT WAS §20 VERBATIM. It searched every line for `claude --` and
    # went red on `echo "  RESUME: claude --continue in $DIR"` — a DISPLAY
    # string, telling the operator what the item is about to do. The tempting
    # fix is to reword the echo so the grep stays quiet; §20's corollary says
    # the opposite, that a canary tripping on prose is a broken canary, and the
    # loosened version is the one that misses the real regression. So a LAUNCH
    # is identified by the thing that makes it one — the mandatory
    # `env -u ANTHROPIC_API_KEY` prefix (R2) — and every launch must carry
    # $CLAUDE. An echo can never match, because an echo has no env prefix.
    launch_env = [ln for ln in b.splitlines() if "env -u ANTHROPIC_API_KEY" in ln]
    bare = [ln.strip() for ln in launch_env if "$CLAUDE" not in ln]
    check("R3 claude is invoked by ABSOLUTE path on every launch, never bare",
          bool(launch_env) and not bare,
          "; ".join(x[:60] for x in bare[:2]) or f"{len(launch_env)} launch line(s)")

    i_sw, i_kill = b.find("switch-client"), b.find("kill-session")
    check("R4 the client switches BEFORE anything is killed",
          i_sw != -1 and i_kill != -1 and i_sw < i_kill,
          f"switch@{i_sw} kill@{i_kill}")

    check("R5 the item is registered in the menu",
          "mi_resume_claude_tmux" in rg)

    # R6 — the flag and the directory, together. Either alone is not a resume:
    # the flag without the right cwd silently starts a fresh thread.
    launches = [ln for ln in b.splitlines() if "$CLAUDE --continue" in ln]
    check("R6 every launch passes --continue", len(launches) >= 1,
          f"{len(launches)} launch line(s)")
    check("R6b and every launch runs in the shared session directory — "
          "--continue is scoped to a directory, so the wrong cwd opens a "
          "FRESH thread",
          b.count('-c "$CLAUDE_SESSION_DIR"') >= 2,
          f'launches: {b.count(chr(45) + chr(99) + " " + chr(34) + "$CLAUDE_SESSION_DIR" + chr(34))}')

    # ══ 🔴 R10 — 37 AND 38 MUST POINT AT THE SAME PLACE ═══════════════════
    # OPERATOR'S REQUIREMENT, 2026-09-12: *"the new session and the resume
    # session need to point to the same place. Because if I start a
    # conversation with 37 that's the one I want to resume with 38."*
    # 🔑 THAT PAIRING IS THE WHOLE FEATURE, AND UNTIL r374 NOTHING HELD IT.
    # The two items agreed only because three separate literals happened to
    # match — 37 hardcoded the path twice inline, 38 kept its own `local DIR`.
    # Change one and `--continue` finds no conversation for the new directory
    # and opens a FRESH thread, which is indistinguishable from a successful
    # resume until the model turns out to know nothing.
    # ⚠️ ASSERTED AS A RELATIONSHIP, NOT AS A VALUE. Pinning each item's path
    # separately would go green on two items pointing at two different places,
    # each "correct" on its own — so this compares the `-c` arguments of BOTH
    # function bodies and requires them to be the same non-empty set.
    hand = fn.split("mi_handoff_fresh_claude() {", 1)
    hb = hand[1].split("\n}\n", 1)[0] if len(hand) == 2 else ""
    cs_resume = set(re.findall(r'-c (\S+)', b))
    cs_hand = set(re.findall(r'-c (\S+)', hb))
    check("R10 the handoff item and the resume item launch in the SAME "
          "directory — 37 starts the thread 38 must find",
          bool(cs_hand) and cs_hand == cs_resume,
          f"37={sorted(cs_hand)} 38={sorted(cs_resume)}")
    # R10b — and the shared name is defined ONCE, above both, so there is no
    # second copy for a future edit to drift.
    check("R10b ...from a single definition, not two literals that agree",
          fn.count("CLAUDE_SESSION_DIR=") == 1
          and "/home/ubuntu/options-trader-v4" not in b,
          f"definitions={fn.count('CLAUDE_SESSION_DIR=')} "
          f"literals_in_38={b.count('/home/ubuntu/options-trader-v4')}")

    # R7 — this item must NOT generate or pass a handoff. A resume that also
    # hands over a document is two mechanisms disagreeing about what the new
    # thread should read, and it reintroduces the interpolation OPS.9 removed.
    check("R7 it neither generates nor interpolates a handoff — no $(...) in "
          "the command string, so OPS.9's defect cannot recur",
          "gen_handoff" not in b and "$(cat" not in b)

    # R8 — the r368-note's lesson, enforced on its sibling. The report must sit
    # between the launch and the exec, or a failed resume is a bare prompt.
    ok8 = True
    detail8 = ""
    for ln in launches:
        i_launch = ln.find("$CLAUDE --continue")
        i_rep = ln.find("RESUME FAILED")
        i_exec = ln.find("exec bash -l")
        if not (i_launch < i_rep < i_exec) or i_rep == -1:
            ok8 = False
            detail8 = f"launch@{i_launch} report@{i_rep} exec@{i_exec}"
            break
    check("R8 a failed resume REPORTS before `exec bash -l` catches it — a "
          "fallback that catches without reporting turns a crash into a mystery",
          ok8 and bool(launches), detail8)

    # R9 — the section heading. It read "this item ENDS the menu" when there
    # was one; two items under a singular heading is the drift §5 catches.
    check("R9 the SESSION heading is plural now that two items end the menu",
          "SECTION|SESSION (these items END the menu)" in rg)

    print()
    if _fails:
        print(f"FAILED {len(_fails)}: {', '.join(_fails)}")
        return 1
    print("check_resume_item: all checks pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
