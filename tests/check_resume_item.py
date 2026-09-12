#!/usr/bin/env python3
"""
tests/check_resume_item.py  v1.2
v1.2  2026-09-12  r375 / OPS.15 — THE ITEMS ARE DISCOVERED FROM THE REGISTRY,
      NOT LISTED HERE. A third SESSION item landed (`RESUME [other]`), and a
      checker that names its subjects has to be edited every time one is added
      — the item that gets forgotten being exactly the one nobody checks. It
      now reads the SESSION section and applies r368's three traps, the
      report-before-catch rule and the shared-directory rule to EACH item, so
      a fourth is covered the moment it is registered. R10 compares all of
      them at once, because the pairing is a relationship and pinning each
      value separately goes green on items pointing at different places.
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


def session_items(rg):
    """The SESSION section's function names, in registry order.

    🔑 DISCOVERED, NOT LISTED. Naming the items here would mean this file has
    to be edited every time one is added — and the item that gets forgotten is
    the one nobody checks. The registry already declares which items END the
    menu; that is the source of truth, so a fourth is covered the moment it is
    registered rather than the day somebody remembers the test.
    """
    out, inside = [], False
    for ln in rg.splitlines():
        if '"SECTION|' in ln:
            inside = "SESSION (" in ln
            continue
        if inside and '"ITEM|' in ln:
            out.append(ln.rsplit("|", 1)[1].strip().strip('"'))
    return out


def body_of(fn, name):
    part = fn.split(f"{name}() {{", 1)
    return part[1].split("\n}\n", 1)[0] if len(part) == 2 else ""


def main():
    print("check_resume_item — the SESSION items (handoff, resume, resume-pick)")
    fn = read("menu_functions.sh")
    rg = read("menu_registry.sh")

    items = session_items(rg)
    check("R0 the SESSION section declares its items", len(items) >= 3,
          ", ".join(items) or "none found")

    # ── the invariants EVERY session item shares, checked on EACH ──────────
    # r368's three traps, each silent in its own way: an API key that bills the
    # wrong account while working perfectly, a bare `claude` a venv's PATH can
    # hide, and a kill order that takes out the client before it has moved.
    for name in items:
        b = body_of(fn, name)
        tag = name.replace("mi_", "")
        check(f"R1[{tag}] the function exists", bool(b))
        check(f"R2[{tag}] the API key is unset — it bills the subscription",
              b.count("env -u ANTHROPIC_API_KEY") >= 1)
        launch = [l for l in b.splitlines() if "env -u ANTHROPIC_API_KEY" in l]
        check(f"R3[{tag}] claude is invoked by ABSOLUTE path on every launch",
              bool(launch) and all("$CLAUDE" in l for l in launch),
              f"{len(launch)} launch line(s)")
        i_sw, i_k = b.find("switch-client"), b.find("kill-session")
        check(f"R4[{tag}] the client switches BEFORE anything is killed",
              i_sw != -1 and i_k != -1 and i_sw < i_k, f"switch@{i_sw} kill@{i_k}")
        # the r368-note's lesson: a fallback that catches without reporting
        # converts a crash into a mystery. Every launch that ends in a shell
        # must explain itself first.
        bad = [l for l in launch
               if "exec bash -l" in l and l.find("echo") > l.find("exec bash -l")]
        noecho = [l for l in launch if "exec bash -l" in l and "echo" not in l]
        check(f"R8[{tag}] a failed launch REPORTS before `exec bash -l` catches it",
              not bad and not noecho, f"{len(bad) + len(noecho)} silent launch(es)")

    # ══ 🔴 R10 — EVERY SESSION ITEM POINTS AT THE SAME PLACE ══════════════
    # OPERATOR, 2026-09-12: *"the new session and the resume session need to
    # point to the same place. Because if I start a conversation with 37 that's
    # the one I want to resume with 38."*
    # ⚠️ ASSERTED AS A RELATIONSHIP ACROSS ALL OF THEM, NOT AS A VALUE EACH.
    # Pinning each item's path separately goes green on items pointing at
    # different directories, each "correct" alone — and `--continue` and
    # `--resume` are BOTH scoped to a directory, so a disagreement means the
    # picker offers a different set of threads than the handoff creates into.
    dirs = {}
    for name in items:
        got = set(re.findall(r'-c (\S+)', body_of(fn, name)))
        dirs[name] = got
    allsame = len({frozenset(v) for v in dirs.values()}) == 1 and all(dirs.values())
    check("R10 EVERY session item launches in the SAME directory",
          allsame,
          "; ".join(f"{k.replace('mi_','')}={sorted(v)}" for k, v in dirs.items()))
    check("R10b ...from a single definition, with no literal left to drift",
          fn.count("CLAUDE_SESSION_DIR=") == 1
          and not any("/home/ubuntu/options-trader-v4" in body_of(fn, n)
                      for n in items),
          f"definitions={fn.count('CLAUDE_SESSION_DIR=')}")

    # ── per-item specifics: the flag is what distinguishes them ────────────
    cont = body_of(fn, "mi_resume_claude_tmux")
    pick = body_of(fn, "mi_resume_pick_claude_tmux")
    check("R6 the RESUME item passes --continue (the most recent thread)",
          "$CLAUDE --continue" in cont)
    check("R11 the RESUME [other] item passes --resume (the picker)",
          "$CLAUDE --resume" in pick)
    # ⚠️ AND THEY MUST NOT BE THE SAME ITEM WEARING TWO LABELS. Two menu
    # entries that do the identical thing is the failure DEV.4 found when
    # RETIRE ran the byte-identical command to EMERGENCY STOP.
    check("R11b ...and the two resume items are genuinely different",
          ("--continue" in cont) != ("--continue" in pick)
          and ("--resume" in pick) != ("--resume" in cont))

    # R7 — no item may interpolate a document into its command string.
    for name in items:
        b = body_of(fn, name)
        if name == "mi_handoff_fresh_claude":
            continue          # it passes a PATH, checked by check_handoff_item
        check(f"R7[{name.replace('mi_','')}] no $(...) in the command string — "
              "OPS.9 cannot recur", "$(cat" not in b)

    check("R9 the SESSION heading is plural", 
          "SECTION|SESSION (these items END the menu)" in rg)
    for name in items:
        check(f"R5[{name.replace('mi_','')}] registered in the menu", name in rg)

    print()
    if _fails:
        print(f"FAILED {len(_fails)}: {', '.join(_fails)}")
        return 1
    print("check_resume_item: all checks pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
