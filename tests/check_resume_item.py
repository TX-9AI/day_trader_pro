#!/usr/bin/env python3
"""
tests/check_resume_item.py  v1.3
v1.3  2026-09-13  r381 / OPS.17 — THE SECTION IS `CLAUDE CODE`, IT HOLDS AN
      ITEM THAT LAUNCHES NOTHING, AND THE LAUNCH RULES STILL CANNOT BE DODGED.
      Operator, 2026-09-13: rename the section, shorten 38 so it stops wrapping
      on the phone, and add an item after 37 that *"exit[s] the menu and
      reattach[es] to the tmux session hosting our current conversation, which
      is not quite the same as resume conversation."*
      🔑 CLASSIFIED BY WHAT THE BODY DOES, NOT BY A LIST OF NAMES. An item whose
      body contains `new-session` is a LAUNCHER and gets every r368 launch rule
      (R1-R4, R8, R10); one that does not is an ATTACHER and gets RA1-RA5 — it
      must kill NOTHING, start NOTHING, and say so when there is nothing to
      attach to. So a future launcher that forgot its `env -u` cannot slip
      through by being mistaken for an attacher: it would have to stop
      launching to stop being checked as a launcher.
      🔴 RA3 IS DRIVEN, NOT READ (§21). tmux reports a Claude pane's command as
      `bash`, because the launch is `bash -c "env ... claude ..."` — measured on
      control on 2026-09-13, pane `claude-133147:0.0 cmd=bash` with `claude` its
      child. So `pane_current_command` cannot find the conversation. The finder
      walks each `claude` process up its parents to a pane, and RA3 runs THAT
      FUNCTION against a private tmux server holding a fake `claude` under
      `bash -c` and a decoy session that is not claude.
      ⚠️ RW pins the width: every label in the section is at most 71 chars, the
      longest the operator's screenshot showed fitting (39's) — 38 was 74 and
      wrapped.
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


SECTION_HEAD = "CLAUDE CODE ("
WIDTH_MAX = 71      # 39's label, the longest seen fitting on the phone


def session_labels(rg):
    out, inside = [], False
    for ln in rg.splitlines():
        if '"SECTION|' in ln:
            inside = SECTION_HEAD in ln
            continue
        if inside and '"ITEM|' in ln:
            out.append(ln.split('"ITEM|', 1)[1].rsplit("|", 1)[0])
    return out


def session_items(rg):
    """The CLAUDE CODE section's function names, in registry order.

    🔑 DISCOVERED, NOT LISTED. Naming the items here would mean this file has
    to be edited every time one is added — and the item that gets forgotten is
    the one nobody checks. The registry already declares which items END the
    menu; that is the source of truth, so a fourth is covered the moment it is
    registered rather than the day somebody remembers the test.
    """
    out, inside = [], False
    for ln in rg.splitlines():
        if '"SECTION|' in ln:
            inside = SECTION_HEAD in ln
            continue
        if inside and '"ITEM|' in ln:
            out.append(ln.rsplit("|", 1)[1].strip().strip('"'))
    return out


def body_of(fn, name):
    part = fn.split(f"{name}() {{", 1)
    return part[1].split("\n}\n", 1)[0] if len(part) == 2 else ""


def ra3(fn):
    """RA3 — drive `_claude_tmux_sessions` against a PRIVATE tmux server.

    ⚠️ A fake `claude` (a shebang script NAMED claude, so its comm IS `claude`)
    runs under
    `bash -c` — the real launch shape, which is exactly what makes tmux report
    the pane as `bash`. A decoy session runs plain `sleep`. The function must
    name the first and not the second. TMUX_TMPDIR isolates the server, so the
    real conversation on the default socket is invisible to it.
    """
    import shutil
    import subprocess
    import tempfile
    import time
    head = "_claude_tmux_sessions() {"
    if head not in fn:
        check("RA3 the finder locates claude by PROCESS, not pane command", False,
              "_claude_tmux_sessions is not defined")
        return
    src = head + fn.split(head, 1)[1].split("\n}\n", 1)[0] + "\n}\n"
    if not shutil.which("tmux"):
        check("RA3 the finder locates claude by PROCESS, not pane command", False,
              "tmux is not installed here — the check cannot run")
        return
    # ⚠️ TWO WAYS THIS FIXTURE FAILED ON ITS FIRST RUN, BOTH SILENTLY GREEN-ABLE:
    # a COPY of `sleep` does not run on this box (uutils coreutils is one
    # multi-call binary and refuses an unknown name), so the fake never started
    # and only RA3b's "finds nothing" could have passed; and a tmux socket under
    # a long scratch TMPDIR exceeds the socket-path limit. Hence a script, and a
    # short directory under /tmp, and RA3's detail prints the panes it saw.
    with tempfile.TemporaryDirectory(prefix="ra3", dir="/tmp") as td:
        fake = os.path.join(td, "claude")
        with open(fake, "w") as fh:
            fh.write("#!/bin/bash\nwhile :; do sleep 1; done\n")
        os.chmod(fake, 0o755)
        env = dict(os.environ, TMUX_TMPDIR=td)
        env.pop("TMUX", None)
        run = lambda *a: subprocess.run(["tmux"] + list(a), env=env,
                                        capture_output=True, text=True)
        try:
            run("new-session", "-d", "-s", "fake claude", f"bash -c '{fake}; true'")
            run("new-session", "-d", "-s", "decoy", "sleep 60")
            time.sleep(0.6)
            got = subprocess.run(["bash", "-c", src + "_claude_tmux_sessions"],
                                 env=env, capture_output=True, text=True)
            panes = run("list-panes", "-a", "-F", "#S cmd=#{pane_current_command}").stdout
            names = [l for l in got.stdout.splitlines() if l.strip()]
            check("RA3 the finder locates claude by PROCESS, not pane command",
                  names == ["fake claude"] and got.returncode == 0,
                  f"found={names} rc={got.returncode} panes={panes.split(chr(10))[:2]}")
            run("kill-session", "-t", "=fake claude")
            got2 = subprocess.run(["bash", "-c", src + "_claude_tmux_sessions"],
                                  env=env, capture_output=True, text=True)
            check("RA3b ...and finds NOTHING when no pane is running claude",
                  got2.stdout.strip() == "" and got2.returncode == 0,
                  f"found={got2.stdout.split()} rc={got2.returncode}")
        finally:
            run("kill-server")


def main():
    print("check_resume_item — the CLAUDE CODE items (handoff, reattach, resume, resume-pick)")
    fn = read("menu_functions.sh")
    rg = read("menu_registry.sh")

    every = session_items(rg)
    check("R0 the CLAUDE CODE section declares its items", len(every) >= 4,
          ", ".join(every) or "none found")
    # 🔑 LAUNCHERS vs ATTACHERS, decided by the body. See the v1.3 header.
    items = [n for n in every if "new-session" in body_of(fn, n)]
    attachers = [n for n in every if n not in items]
    check("R0b ...three launch a thread and one reattaches",
          len(items) >= 3 and "mi_reattach_claude_tmux" in attachers,
          f"launchers={len(items)} attachers={attachers}")

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

    check("R9 the section is named CLAUDE CODE, and the old name is gone",
          "SECTION|CLAUDE CODE (these items END the menu)" in rg
          and '"SECTION|SESSION (' not in rg)
    for name in every:
        check(f"R5[{name.replace('mi_','')}] registered in the menu", name in rg)

    # ── RW — nothing in the section wraps on the phone ─────────────────────
    labels = session_labels(rg)
    wide = [f"{len(l)}: {l}" for l in labels if len(l) > WIDTH_MAX]
    check(f"RW every CLAUDE CODE label is <= {WIDTH_MAX} chars",
          bool(labels) and not wide, "; ".join(wide) or f"{len(labels)} label(s)")
    check("RW2 REATTACH sits directly after HAND OFF",
          every[:2] == ["mi_handoff_fresh_claude", "mi_reattach_claude_tmux"],
          ", ".join(every[:2]))

    # ══ RA — THE ATTACHER ═════════════════════════════════════════════════
    ra = body_of(fn, "mi_reattach_claude_tmux")
    check("RA0 the reattach function exists", bool(ra))
    check("RA1 it kills NOTHING — no kill-session, no kill-server",
          bool(ra) and "kill-session" not in ra and "kill-server" not in ra)
    check("RA2 it starts NOTHING — no new-session, no claude launch",
          bool(ra) and "new-session" not in ra and "$CLAUDE" not in ra
          and "--continue" not in ra and "--resume" not in ra)
    i_none = ra.find("_claude_tmux_sessions")
    check("RA4 an empty result is REPORTED before returning to the menu",
          "No tmux session is running claude" in ra)
    check("RA5 outside tmux it ATTACHES; inside, it switches and EXITS the menu",
          "exec tmux attach-session" in ra and "switch-client" in ra
          and "exit 0" in ra, f"finder@{i_none}")
    ra3(fn)

    print()
    if _fails:
        print(f"FAILED {len(_fails)}: {', '.join(_fails)}")
        return 1
    print("check_resume_item: all checks pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
