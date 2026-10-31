#!/usr/bin/env python3
"""
day_trader_pro/tests/check_checker_sweep.py  v1.0
v1.0  2026-10-31  dtp r520 / SAT.4 — THE SATURDAY SWEEP GIVES EVERY CHECKER ITS OWN SCRATCH AND DIFFS BY CHECK ID.

Driven on a fixture tree of real checker files, run by the real tool:
  W1  each checker gets a FRESH scratch: a checker that creates $OT_TRADES_DB and one that fails if it already
      exists are both green (one shared scratch, the 2026-10-31 brief's artefact, turns the second red)
  W2  no checker sees the live stores: OT_TRADES_DB, OT_LOG_FILE and DTP_REPORTS_DIR point into its own scratch, and
      VERTIGO_UNATTENDED=1 is set
  W3  a red file's IDs are the FAIL ids it printed; a red that printed none carries rc=<n>
  W4  a checker that overruns --timeout is red with rc=124, and the sweep goes on
  W5  ModuleNotFoundError marks a red env=true
  W6  week two against week one: NEWLY RED, GREEN THAT WAS RED, STILL RED with the new and cleared IDs, and NEW /
      GONE checkers, each in its own bucket
  W7  checker_sweep.py itself is not matched by the check_* glob (it would sweep itself)
"""
import json
import os
import subprocess
import sys
import tempfile
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOL = os.path.join(ROOT, "tools", "checker_sweep.py")
FAILS, RAN = [], []


def ck(n, ok, msg):
    RAN.append(n)
    print(f"  {n:<4} {'PASS' if ok else 'FAIL'}  {msg}")
    if not ok:
        FAILS.append(n)


def write(root, rel, body):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write(textwrap.dedent(body))


tree = tempfile.mkdtemp(prefix="chk_sweep_tree_")
write(tree, "tests/check_a_creates.py", """
    import os, sys
    open(os.environ["OT_TRADES_DB"], "w").write("schema A")
    print("  A1   PASS  created")
""")
write(tree, "tests/check_b_needs_fresh.py", """
    import os, sys
    if os.path.exists(os.environ["OT_TRADES_DB"]):
        print("  B1   FAIL  a store from another checker is here"); sys.exit(1)
    print("  B1   PASS  fresh")
""")
write(tree, "tests/check_c_ids.py", """
    import sys
    print("  C1   PASS  ok"); print("  C2   FAIL  two"); print("  C3   FAIL  three"); print("FAILED: C2, C3"); sys.exit(1)
""")
write(tree, "tests/test_d_silent.py", """
    import sys; sys.exit(3)
""")
write(tree, "tests/check_e_slow.py", """
    import time; time.sleep(30)
""")
write(tree, "tests/check_f_env.py", """
    import definitely_not_a_module_here
""")
write(tree, "tests/check_g_isolation.py", """
    import os, sys
    root = os.path.dirname(os.environ.get("TMPDIR", "/nonexistent/tmp"))   # the checker's own scratch
    bad = [k for k in ("OT_TRADES_DB", "OT_LOG_FILE", "DTP_REPORTS_DIR")
           if not os.environ.get(k, "").startswith(root + os.sep) or "options-trader" in os.environ.get(k, "")]
    if bad or os.environ.get("VERTIGO_UNATTENDED") != "1":
        print("  G1   FAIL  " + ",".join(bad)); sys.exit(1)
    print("  G1   PASS  isolated")
""")

out1 = tempfile.mkdtemp(prefix="chk_sweep_w1_")
r = subprocess.run([sys.executable, TOOL, "--out", out1, "--tree", f"fx={tree}", "--timeout", "5"],
                   capture_output=True, text=True, timeout=180)
j = json.load(open(os.path.join(out1, "sweep.json"))) if os.path.exists(os.path.join(out1, "sweep.json")) else {"results": []}
res = {x["file"]: x for x in j["results"]}
g = lambda f: res.get(f, {"rc": None, "ids": None, "env": None})

ck("W0", r.returncode == 0 and len(res) == 7, f"the sweep ran 7 fixture checkers (rc={r.returncode}, {len(res)})")
ck("W1", g("tests/check_a_creates.py")["rc"] == 0 and g("tests/check_b_needs_fresh.py")["rc"] == 0,
   "a store one checker created is not there for the next: each has a fresh scratch")
ck("W2", g("tests/check_g_isolation.py")["rc"] == 0,
   "store and report paths inside the checker's own scratch, VERTIGO_UNATTENDED=1")
ck("W3", g("tests/check_c_ids.py")["ids"] == ["C2", "C3"] and g("tests/test_d_silent.py")["ids"] == ["rc=3"],
   f"IDs: {g('tests/check_c_ids.py')['ids']} and a silent red {g('tests/test_d_silent.py')['ids']}")
ck("W4", g("tests/check_e_slow.py")["rc"] == 124, f"an overrun is rc=124 ({g('tests/check_e_slow.py')['rc']})")
ck("W5", g("tests/check_f_env.py")["env"] is True and g("tests/check_c_ids.py")["env"] is False,
   "an import failure is flagged env; an ordinary red is not")

# week two: c fixes C2 and breaks C4, a breaks, d is green, f removed, h added
write(tree, "tests/check_a_creates.py", "import sys\nprint('  A1   FAIL  broke'); sys.exit(1)\n")
write(tree, "tests/check_c_ids.py", "import sys\nprint('  C3   FAIL  x'); print('  C4   FAIL  y'); sys.exit(1)\n")
write(tree, "tests/test_d_silent.py", "pass\n")
os.remove(os.path.join(tree, "tests/check_f_env.py"))
write(tree, "tests/check_h_new.py", "print('  H1   PASS')\n")
out2 = tempfile.mkdtemp(prefix="chk_sweep_w2_")
r2 = subprocess.run([sys.executable, TOOL, "--out", out2, "--prior", out1, "--tree", f"fx={tree}", "--timeout", "5"],
                    capture_output=True, text=True, timeout=180)
d = json.load(open(os.path.join(out2, "diff.json"))) if os.path.exists(os.path.join(out2, "diff.json")) else {}
files = lambda k: [row[1] for row in d.get(k, [])]
changed = {row[1]: (row[2], row[3]) for row in d.get("still_red_ids_changed", [])}
ck("W6", files("newly_red") == ["tests/check_a_creates.py"]
   and files("green_that_was_red") == ["tests/test_d_silent.py"]
   and changed.get("tests/check_c_ids.py") == (["C4"], ["C2"])
   and files("new_checkers") == ["tests/check_h_new.py"]
   and [row[1] for row in d.get("gone_checkers", [])] == ["tests/check_f_env.py"]
   and "NEWLY RED: fx/tests/check_a_creates.py" in r2.stdout,
   f"the diff buckets: newly {files('newly_red')}, greened {files('green_that_was_red')}, "
   f"changed {changed}, new {files('new_checkers')}, gone {d.get('gone_checkers')}")

import fnmatch  # noqa: E402
ck("W7", not fnmatch.fnmatch("checker_sweep.py", "check_*.py"),
   "tools/checker_sweep.py is outside the tools/check_*.py glob")

print()
if FAILS:
    print(f"FAILED: {', '.join(FAILS)}")
    sys.exit(1)
print(f"ALL PASS ({len(RAN)})")
