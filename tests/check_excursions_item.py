#!/usr/bin/env python3
"""
day_trader_pro/tests/check_excursions_item.py  v1.0
v1.0  2026-09-09  dtp r327 / RPT.19 — the land gate for the EXCURSIONS item.

  M1  the item is registered and names a function that EXISTS
  M2  the handler calls `_r_tool excursions.py`, the shared wrapper
  M3  `menu_extract.py --check` passes (no missing function, no dup label)
  M4  both files parse as shell

⚠️ THE OBVIOUS CHECK IS THE WRONG ONE. `python3 tools/menu_extract.py` with no
arguments EXITS 0 while merely printing a draft — a CHECK directive takes no
arguments, so naming it directly would have put a decorative green on the
board. `--check` is the mode that actually asserts, and it has to be invoked
as a subprocess to get it. Same family as the `; true` tally that reported
15/15 while every box failed.
"""
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILS = []


def check(name, ok, detail=""):
    print("  {:<4} {}  {}".format(name, "PASS" if ok else "FAIL", detail))
    if not ok:
        FAILS.append(name)


def main():
    reg = open(os.path.join(REPO, "menu_registry.sh")).read()
    fns = open(os.path.join(REPO, "menu_functions.sh")).read()

    item = [m for m in re.findall(r'"ITEM\|([^"]*)"', reg)
            if m.rsplit("|", 1)[-1] == "mi_r_excursions"]
    defined = "mi_r_excursions() {" in fns
    check("M1", len(item) == 1 and defined,
          "registered={} defined={}".format(len(item), defined))

    body = fns.split("mi_r_excursions() {", 1)[-1].split("\n}", 1)[0] if defined else ""
    check("M2", "_r_tool excursions.py" in body,
          "handler calls the shared wrapper" if "_r_tool excursions.py" in body
          else "handler does not call _r_tool")

    p = subprocess.run([sys.executable, "tools/menu_extract.py", "--check"],
                       cwd=REPO, capture_output=True, text=True)
    tail = (p.stdout or "").strip().splitlines()[-1:] or ["(no output)"]
    check("M3", p.returncode == 0 and "OK" in p.stdout,
          "menu_extract --check rc={} {}".format(p.returncode, tail[0].strip()))

    rcs = []
    for f in ("menu_registry.sh", "menu_functions.sh"):
        rcs.append(subprocess.run(["bash", "-n", f], cwd=REPO,
                                  capture_output=True).returncode)
    check("M4", rcs == [0, 0], "bash -n: {}".format(rcs))

    print("")
    if FAILS:
        print("FAILED: {}".format(", ".join(FAILS)))
        return 1
    print("ALL PASS (4)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
