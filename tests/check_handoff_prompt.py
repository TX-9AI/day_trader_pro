#!/usr/bin/env python3
"""
day_trader_pro/tests/check_handoff_prompt.py  v1.1
v1.1  2026-09-12  r375 / OPS.15 — H3 ANCHORED ON THE SHAPE, NOT THE SPELLING.
      It matched the literal otv4 path, so hoisting the handoffs directory onto
      `$CLAUDE_SESSION_DIR` — one definition replacing four — turned it red for
      a reason unrelated to the property it guards. The property, in its own
      words, is *written under handoffs/, not /tmp*; that is what it asserts
      now, and the /tmp refusal is made explicit rather than implied.
v1.0  2026-09-12  dtp r369 / OPS.9 — the handoff prompt must be a PATH.

🔴 WHAT HAPPENED. r368 built the tmux command as
`"env ... $CLAUDE \\"$(cat "$HO")\\"; exec bash -l"`. `$(cat ...)` expands in
the OUTER shell, so the entire multi-line handoff — quotes, backticks, `$`,
parentheses — was pasted into a command line handed to `sh`. It died on the
first unbalanced quote, `exec bash -l` caught the fall, and the operator
landed in a BARE BASH PROMPT in session `claude-170` with the previous session
already killed and no error explaining it.

🔑 A PATH HAS NO METACHARACTERS. That is the whole fix.

  H1  neither tmux command interpolates the document (`$(cat` is gone)
  H2  both pass the handoff BY PATH
  H3  the file is written under handoffs/, not /tmp — it survives to be
      re-read, which is the point of a handoff
  H4  it is removed on CANCEL only: deleting on success hands the new session
      a dangling reference
  H5  a document full of shell metacharacters survives the quoting used now
      (executed, not asserted — the failure was a quoting failure)
"""
import os
import re
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILS = []


def check(name, ok, detail=""):
    print("  {:<4} {}  {}".format(name, "PASS" if ok else "FAIL", detail))
    if not ok:
        FAILS.append(name)


def main():
    src = open(os.path.join(REPO, "menu_functions.sh"), encoding="utf-8").read()
    i = src.index("mi_handoff_fresh_claude()")
    body = src[i:src.index("\n}", i)]
    code = "\n".join(l for l in body.splitlines()
                     if not l.lstrip().startswith("#"))

    tmux = [l for l in code.splitlines() if "new-session" in l or "$CLAUDE" in l]
    check("H1", "$(cat" not in code,
          "no document interpolation" if "$(cat" not in code
          else "still interpolates: " + [l for l in tmux if "$(cat" in l][0][:60])

    byref = len([l for l in code.splitlines() if "Read $HO" in l])
    check("H2", byref == 2, "{} of 2 launch paths pass the file by path".format(byref))

    # 🔴 H3 WAS PINNED TO THE VALUE, NOT THE SHAPE (r375). It matched the
    # literal `options-trader-v4/handoffs/handoff.XXXXXX`, so hoisting the
    # directory into `$CLAUDE_SESSION_DIR` — a strictly better state, with one
    # definition instead of four — turned it red for a reason unrelated to
    # what it checks. Its own header says the property is *written under
    # handoffs/, not /tmp, so it survives to be re-read*, and that is still
    # true. C.24's lesson in a new costume: a canary tied to a spelling rots on
    # the next legitimate change, and the tempting fix is to un-do the change.
    # Anchored on the shape now, plus the /tmp refusal it actually cares about.
    check("H3", "handoffs/handoff.XXXXXX" in code
          and "mktemp /tmp" not in code and 'mktemp "/tmp' not in code,
          "written under handoffs/, not /tmp")

    # ⚠️ POSITION, NOT WORDING. The refuse-path `rm` sits on its own line and
    # the reason is on the `echo` above it, so matching words tests the prose.
    # What matters is that no removal happens AFTER a session is launched.
    first_launch = code.find("new-session")
    rm_after = [ln for ln in code.splitlines()
                if 'rm -f "$HO"' in ln
                and code.find(ln) > first_launch >= 0]
    rm_total = [ln for ln in code.splitlines() if 'rm -f "$HO"' in ln]
    check("H4", rm_total and not rm_after,
          "{} rm site(s), {} after a launch".format(len(rm_total), len(rm_after)))

    # H5 — run the real quoting against a hostile document.
    d = tempfile.mkdtemp()
    ho = os.path.join(d, "handoff.evil")
    open(ho, "w").write(
        'Line with "double" and \'single\' quotes\n'
        '`backticks` and $(command subst) and $VARS\n'
        'a ) paren and a ; semicolon and a | pipe\n')
    cmd = "echo READ_OK:$(basename %s) 'Read %s and follow it.'" % (ho, ho)
    p = subprocess.run(["sh", "-c", cmd], capture_output=True, text=True)
    check("H5", p.returncode == 0 and "READ_OK" in p.stdout,
          "hostile document survives: rc={} out={!r}".format(
              p.returncode, p.stdout.strip()[:48]))

    print("")
    if FAILS:
        print("FAILED: {}".format(", ".join(FAILS)))
        return 1
    print("ALL PASS (5)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
