#!/usr/bin/env python3
"""
day_trader_pro/tests/check_menu_diff_refuses.py  v1.0
v1.0  2026-10-25  DEV.13 — `menu_extract --diff` REFUSES INPUT THAT IS NOT AN INVENTORY.

  N1  two menu_registry.sh files (the 2026-09-13 misuse)  -> rc 2, REFUSED, never ✅
  N2  a real inventory vs a registry file                 -> rc 2, the bad file named
  N3  rows but no `# source:` header                      -> rc 2
  N4  a `# source:` header and 0 rows                     -> rc 2
  N5  `--inventory` writes `# source:` as its FIRST STDOUT line (so `> FILE` carries it)
  N6  control: two real `--inventory > FILE` outputs diff clean -> rc 0, ✅
  N7  control: a removed label in a real inventory is still caught -> rc 1, ❌

All through the CLI (`python tools/menu_extract.py ...`) on temp files; the live menu is only read.

BORN RED on dtp 4fec59e: N1 N2 N3 N4 N5
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILS = []


def check(name, ok, detail=""):
    print("  {:<3} {}  {}".format(name, "PASS" if ok else "FAIL", detail))
    if not ok:
        FAILS.append(name)


def tool(*args):
    return subprocess.run([sys.executable, "tools/menu_extract.py"] + list(args), cwd=ROOT,
                          capture_output=True, text=True, timeout=120)


def main():
    d = tempfile.mkdtemp(prefix="menudiff_")
    try:
        reg1 = os.path.join(d, "reg_old.sh")
        reg2 = os.path.join(d, "reg_new.sh")
        shutil.copy(os.path.join(ROOT, "menu_registry.sh"), reg1)
        shutil.copy(os.path.join(ROOT, "menu_registry.sh"), reg2)
        inv = tool("--inventory")
        good = os.path.join(d, "inv.tsv")
        open(good, "w").write(inv.stdout)
        good2 = os.path.join(d, "inv2.tsv")
        open(good2, "w").write(inv.stdout)
        rows = [ln for ln in inv.stdout.splitlines() if ln.count("\t") == 2]
        nohdr = os.path.join(d, "nohdr.tsv")
        open(nohdr, "w").write("\n".join(rows) + "\n")
        empty = os.path.join(d, "empty.tsv")
        open(empty, "w").write("# source: registry\n")
        lost = os.path.join(d, "lost.tsv")
        open(lost, "w").write("# source: registry\n" + "\n".join(rows[1:]) + "\n")

        r = tool("--diff", reg1, reg2)
        check("N1", r.returncode == 2 and "REFUSED" in r.stdout and "✅" not in r.stdout,
              "rc={} {!r}".format(r.returncode, r.stdout.strip().splitlines()[-1:]))
        r = tool("--diff", good, reg2)
        check("N2", r.returncode == 2 and reg2 in r.stdout and "✅" not in r.stdout,
              "rc={} {!r}".format(r.returncode, r.stdout.strip().splitlines()[-1:]))
        r = tool("--diff", nohdr, good)
        check("N3", r.returncode == 2 and "header" in r.stdout, "rc={} {!r}".format(r.returncode, r.stdout.strip()[-90:]))
        r = tool("--diff", good, empty)
        check("N4", r.returncode == 2 and "0 inventory rows" in r.stdout,
              "rc={} {!r}".format(r.returncode, r.stdout.strip()[-90:]))
        first = (inv.stdout.splitlines() or [""])[0]
        check("N5", inv.returncode == 0 and first.startswith("# source:") and len(rows) > 50,
              "first stdout line={!r} rows={}".format(first, len(rows)))
        r = tool("--diff", good, good2)
        check("N6", r.returncode == 0 and "✅" in r.stdout, "rc={} {!r}".format(r.returncode, r.stdout.strip()[-60:]))
        r = tool("--diff", good, lost)
        check("N7", r.returncode == 1 and "❌" in r.stdout, "rc={}".format(r.returncode))
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print("")
    if FAILS:
        print("FAILED: {}".format(", ".join(FAILS)))
        return 1
    print("ALL PASS (7)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
