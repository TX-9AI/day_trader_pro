#!/usr/bin/env python3
"""
tests/test_menu_banner.py  v1.0
The rendered banner matches devtools.sh's header version.

v1.0  2026-08-25  Written after the menu rendered "v1.35 Service Menu" against
a v1.39 header — FOUR revisions stale, and it had drifted before: the file's
own v1.28 note records the banner reading v1.26 while the header had moved on.

🔴 THE CAUSE IS THAT THE BANNER LIVED IN A DIFFERENT FILE FROM THE HEADER IT
QUOTED. The version is written in devtools.sh; the banner literal was typed in
menu_registry.sh. Bumping the header could not move it, so the operator's
standing rule — "title == newest changelog entry" — was being followed to the
letter while the OUTPUT still lied.

⚠️ A RULE A CAREFUL PERSON CAN OBEY WHILE THE RESULT STAYS WRONG IS NOT A RULE,
IT IS A TRAP. r202 made the banner DERIVE its version. This test is what keeps
it derived: reintroduce a hardcoded version and it goes red.

Run:  cd ~/day_trader_pro && python3 tests/test_menu_banner.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBLEMS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  - {detail}" if (detail and not ok) else ""))
    if not ok:
        PROBLEMS.append(name)


def main() -> int:
    print("=" * 62)
    print("MENU BANNER: rendered version == devtools.sh header")
    print("=" * 62)

    dev = open(os.path.join(ROOT, "devtools.sh"), encoding="utf-8").read()
    m = re.search(r"^# day_trader_pro/devtools\.sh — (v[0-9.]+)", dev, re.M)
    check("B1 devtools.sh header carries a version", bool(m),
          "no '# day_trader_pro/devtools.sh — vX.Y' line")
    if not m:
        return 1
    header = m.group(1)

    # ⚠️ RENDER IT, DO NOT READ IT. A regex over menu_registry.sh would pass
    # against a hardcoded literal that happened to match today and drift
    # tomorrow — which is precisely how this bug survived.
    out = subprocess.run(
        ["bash", "-c", f"cd {ROOT} && source ./menu_registry.sh && menu_render"],
        capture_output=True, text=True, timeout=30).stdout
    check("B2 the menu renders", "Service Menu" in out, out[:120])
    banner = next((l for l in out.splitlines() if "Service Menu" in l), "")
    check(f"B3 banner shows {header}", header in banner,
          f"banner reads: {banner.strip()!r}")

    # ⚠️ AND IT MUST BE DERIVED, NOT COINCIDENTALLY EQUAL.
    reg = open(os.path.join(ROOT, "menu_registry.sh"), encoding="utf-8").read()
    hard = re.findall(r"Service Menu", reg)
    literal = re.search(r"v[0-9]+\.[0-9]+ Service Menu", reg)
    check("B4 no hardcoded version in the banner string", literal is None,
          "menu_registry.sh types a version literal again — it will drift")

    print("=" * 62)
    if PROBLEMS:
        print(f"  {len(PROBLEMS)} problem(s): {PROBLEMS}")
        return 1
    print(f"  ALL GREEN — banner and header both {header}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
