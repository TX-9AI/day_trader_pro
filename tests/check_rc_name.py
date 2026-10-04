#!/usr/bin/env python3
"""tests/check_rc_name.py  v1.0
OPS.66 — EVERY CLAUDE LAUNCH ON CONTROL IS NAMED ✨1-REPORTER.

v1.0  2026-10-04  dtp r469. Operator: "I want to make your OT_RC_NAME sticky. It
      should be ✨1-REPORTER." The menu's HAND OFF / RESUME / RESUME [other]
      launch lines and the boot service's launch_cmd started claude unnamed,
      so Remote Control titled the session from its first prompt.

  R1  every code line in menu_functions.sh that launches `$CLAUDE` passes
      --remote-control '$RC_NAME' (comment lines are not launches)
  R2  the menu's RC_NAME assignment, EXECUTED in bash: unset -> ✨1-REPORTER,
      OT_RC_NAME=X -> X
  R3  claude_boot.launch_cmd, the REAL function: names ✨1-REPORTER before the
      resume mode, in a fresh interpreter with OT_RC_NAME unset
  R3b ... and OT_RC_NAME overrides it
  R4  the two defaults are the same string

Run:  python3 tests/check_rc_name.py
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WANT = "✨1-REPORTER"
PROBLEMS = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  — {detail}"))
    if not ok:
        PROBLEMS.append(name)


def boot_launch(env_extra):
    env = {k: v for k, v in os.environ.items() if k != "OT_RC_NAME"}
    env.update(env_extra)
    code = ("import sys; sys.path.insert(0, %r); sys.path.insert(0, %r)\n"
            "import claude_boot as b\n"
            "print(b.launch_cmd('/x/claude', '--continue'))\n"
            "print('RC=' + str(getattr(b, 'RC_NAME', None)))\n") % (ROOT, os.path.join(ROOT, "tools"))
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                       env=env, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(f"rc={r.returncode}: {r.stderr[-300:]}")
    return r.stdout


def main():
    print("check_rc_name")
    src = open(os.path.join(ROOT, "menu_functions.sh"), encoding="utf-8").read().splitlines()
    launches = [l for l in src if not l.lstrip().startswith("#")
                and re.search(r"env -u ANTHROPIC_API_KEY \$CLAUDE\b", l)]
    named = [l for l in launches if "$CLAUDE --remote-control '$RC_NAME' " in l]
    check("R1 every $CLAUDE launch line passes --remote-control '$RC_NAME'",
          len(launches) >= 6 and len(named) == len(launches),
          f"{len(named)} of {len(launches)} launch lines named")

    assign = [l for l in src if re.match(r'^RC_NAME=', l)]
    menu_default = None
    if len(assign) != 1:
        check("R2 one RC_NAME assignment in menu_functions.sh", False, f"found {len(assign)}")
    else:
        env = {k: v for k, v in os.environ.items() if k != "OT_RC_NAME"}
        r1 = subprocess.run(["bash", "-c", assign[0] + '; printf %s "$RC_NAME"'],
                            capture_output=True, text=True, env=env).stdout
        r2 = subprocess.run(["bash", "-c", assign[0] + '; printf %s "$RC_NAME"'],
                            capture_output=True, text=True, env=dict(env, OT_RC_NAME="X")).stdout
        menu_default = r1
        check("R2 menu RC_NAME executed: unset -> ✨1-REPORTER, OT_RC_NAME=X -> X",
              r1 == WANT and r2 == "X", f"unset={r1!r} override={r2!r}")

    boot_default = None
    try:
        out = boot_launch({})
        boot_default = out.split("RC=")[-1].strip()
        check("R3 claude_boot.launch_cmd names ✨1-REPORTER before the resume mode",
              f"--remote-control '{WANT}' --continue" in out, out.strip()[:200])
        out2 = boot_launch({"OT_RC_NAME": "X"})
        check("R3b OT_RC_NAME overrides the boot name",
              "--remote-control 'X' --continue" in out2, out2.strip()[:200])
    except Exception as exc:                                    # noqa: BLE001
        check("R3 (did not run)", False, f"{type(exc).__name__}: {exc}")

    check("R4 menu and boot carry the same default",
          menu_default is not None and menu_default == boot_default == WANT,
          f"menu={menu_default!r} boot={boot_default!r}")

    print()
    if PROBLEMS:
        print(f"RED — {len(PROBLEMS)} failed: {', '.join(p.split()[0] for p in PROBLEMS)}")
        return 1
    print("GREEN — every check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
