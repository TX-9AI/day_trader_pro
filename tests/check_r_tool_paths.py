#!/usr/bin/env python3
"""
day_trader_pro/tests/check_r_tool_paths.py  v1.0
v1.0  2026-11-08  dtp r528 / RSUITE.1 (the 11-07 brief section 5 carried item; hygiene queue item 3). THE R SUITE
      RUNS OTV5'S TOOLS. menu_functions.sh `_r_tool` resolved ${DTP_OTV4_DIR:-~/options-trader-v4}/tests/<tool>, so the
      four R SUITE items ran the FROZEN otv4 copies (no r75 streaming replay, no stop_sweep None fix, and an
      excursions.py OTV5 did not have). Every check DRIVES the real shell functions: menu_functions.sh is sourced
      in bash with `pause` and `$PY` stubbed, a fixture tree stands in for ~/OTV5, and each fake tool prints the
      path it was run from and its argv.
  R1  each of the four items (mi_r_excursions, mi_r_stop_sweep, mi_r_ledger, mi_r_exit_replay) runs
      $DTP_OTV5_DIR/tests/<its tool>
  R2  with DTP_OTV5_DIR unset the default is $HOME/OTV5/tests (HOME pointed at a fixture)
  R3  DTP_OTV4_DIR pointed at a decoy tree holding the same four tools is NEVER run
  R4  a missing tool prints the path fault naming DTP_OTV5_DIR and runs nothing
  R5  the date prompts still map: ENTER -> no flag, a date -> --date, a pair -> --from/--to, 'all' -> --all-history
  R6  the item -> tool-file map is the one OTV5 ships (excursions.py, stop_sweep.py, r_ledger.py, exit_replay.py
      all exist in the OTV5 tree this check is pointed at, default ~/OTV5; SKIPPED with a reason when absent)
Run:  python3 tests/check_r_tool_paths.py
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DTP = os.path.dirname(HERE)
MENU = os.path.join(DTP, "menu_functions.sh")
ITEMS = {"mi_r_excursions": "excursions.py", "mi_r_stop_sweep": "stop_sweep.py",
         "mi_r_ledger": "r_ledger.py", "mi_r_exit_replay": "exit_replay.py"}
FAILS, RAN = [], []

FAKE = 'import sys, os\nprint("RAN " + os.path.realpath(__file__) + " ARGS " + " ".join(sys.argv[1:]))\n'


def ck(n, ok, msg):
    RAN.append(n)
    print("  {:<4} {}  {}".format(n, "PASS" if ok else "FAIL", msg))
    if not ok:
        FAILS.append(n)


def tree(root, tools=ITEMS.values()):
    os.makedirs(os.path.join(root, "tests"), exist_ok=True)
    for t in tools:
        with open(os.path.join(root, "tests", t), "w") as f:
            f.write(FAKE)
    return root


SAFE_HOME = None   # set in main(): a fixture HOME, so a regression can never reach the REAL ~/OTV5 or ~/options-trader-v4


def drive(fn, stdin="\n", env=None):
    """Source the real menu_functions.sh and call one item; returns stdout+stderr.
    ⚠️ HOME is ALWAYS a fixture: a mutant that ignored DTP_OTV5_DIR once ran the real tools against S3 from here."""
    script = ('pause() { :; }\nPY="%s"\nsource "%s" >/dev/null 2>&1\n%s\n'
              % (sys.executable, MENU, fn))
    e = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": SAFE_HOME}
    e.update(env or {})
    p = subprocess.run(["bash", "-c", script], input=stdin, capture_output=True, text=True, env=e, timeout=60)
    return p.stdout + p.stderr


def main():
    global SAFE_HOME
    with tempfile.TemporaryDirectory() as tmp:
        SAFE_HOME = os.path.join(tmp, "nohome")
        os.makedirs(SAFE_HOME)
        otv5 = tree(os.path.join(tmp, "otv5"))
        decoy = tree(os.path.join(tmp, "otv4"))
        home = os.path.join(tmp, "home")
        tree(os.path.join(home, "OTV5"))

        ok, bad = True, []
        for fn, tool in ITEMS.items():
            out = drive(fn, env={"DTP_OTV5_DIR": otv5})
            want = "RAN " + os.path.realpath(os.path.join(otv5, "tests", tool))
            if want not in out:
                ok, bad = False, bad + [fn]
        ck("R1", ok, "all four items ran $DTP_OTV5_DIR/tests/<tool>" if ok else "wrong path: " + ", ".join(bad))

        out = drive("mi_r_ledger", env={"HOME": home})
        want = "RAN " + os.path.realpath(os.path.join(home, "OTV5", "tests", "r_ledger.py"))
        ck("R2", want in out, "default $HOME/OTV5/tests" if want in out else "got: " + out.strip()[-160:])

        out = "".join(drive(fn, env={"DTP_OTV5_DIR": otv5, "DTP_OTV4_DIR": decoy}) for fn in ITEMS)
        hit = os.path.realpath(decoy) in out
        ck("R3", not hit, "the otv4 decoy was never run" if not hit else "ran a tool from DTP_OTV4_DIR")

        empty = os.path.join(tmp, "empty")
        os.makedirs(os.path.join(empty, "tests"))
        out = drive("mi_r_stop_sweep", env={"DTP_OTV5_DIR": empty})
        ok4 = "missing" in out and "DTP_OTV5_DIR" in out and "path fault" in out and "RAN " not in out
        ck("R4", ok4, "path fault named, nothing run" if ok4 else "got: " + out.strip()[-160:])

        cases = [("\n", ""), ("2026-11-06\n\n", "--date 2026-11-06"),
                 ("2026-11-02\n2026-11-06\n", "--from 2026-11-02 --to 2026-11-06"), ("all\n", "--all-history")]
        bad5 = []
        for stdin, args in cases:
            out = drive("mi_r_exit_replay", stdin=stdin, env={"DTP_OTV5_DIR": otv5})
            line = [l for l in out.splitlines() if l.startswith("RAN ")]
            got = line[0].split(" ARGS ", 1)[1].strip() if line and " ARGS " in line[0] else None
            if got != args:
                bad5.append("%r -> %r" % (stdin, got))
        ck("R5", not bad5, "ENTER / date / pair / all map as before" if not bad5 else "; ".join(bad5))

    real = os.environ.get("DTP_OTV5_DIR", os.path.expanduser("~/OTV5"))
    if os.path.isdir(os.path.join(real, "tests")):
        missing = [t for t in ITEMS.values() if not os.path.isfile(os.path.join(real, "tests", t))]
        ck("R6", not missing, "all four tools exist in %s/tests" % real if not missing
           else "missing in %s/tests: %s" % (real, ", ".join(missing)))
    else:
        print("  R6   SKIP  no OTV5 tree at %s (the map is checked where the tree exists)" % real)

    print("")
    if FAILS:
        print("FAILED: " + ", ".join(FAILS))
        sys.exit(1)
    print("ALL PASS ({})".format(len(RAN)))


if __name__ == "__main__":
    main()
