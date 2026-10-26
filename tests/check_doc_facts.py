#!/usr/bin/env python3
"""
day_trader_pro/tests/check_doc_facts.py  v1.0
v1.0  2026-10-25  DOC.7 / DOC.8 — THE README NAMES THE FLEET THE CODE RUNS; EVERY GATE HEADER IS DATED.

  F1  README's opening paragraph names OTV5 as the trading fleet, not options_trader_v3
  F2  the control checkout README names is orchestrator.CONTROL_REPO's default (read from the module, not retyped)
  F3  README offers no runnable command under ~/options-trader-v3 (a directory control does not have)
  F4  README's box path is the one fleet.py / wake_and_bake.py deploy to (INSTALL_DIR)
  F5  tests/check_ssh_decode.py carries a dated changelog line (`vX.Y  YYYY-MM-DD`) for its own version

BORN RED on dtp 4fec59e: F1 F3 F5   (F2 was GREEN there and wrong: README and orchestrator agreed on the absent ~/options-trader-v3 - CTL.1 moves both; F2 keeps them together)
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
FAILS = []


def check(name, ok, detail=""):
    print("  {:<3} {}  {}".format(name, "PASS" if ok else "FAIL", detail))
    if not ok:
        FAILS.append(name)


def main():
    readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    first = readme.split("\n\n---", 1)[0]
    opening = first.split("system.", 1)[0]
    check("F1", "OTV5" in opening and "options_trader_v3** trading fleet" not in opening,
          "opening names OTV5={} names v3 fleet={}".format("OTV5" in opening, "options_trader_v3** trading fleet" in opening))

    os.environ.pop("DTP_CONTROL_REPO", None)
    import orchestrator
    ctl = orchestrator.CONTROL_REPO
    check("F2", "`{}`".format(ctl) in first or "**`{}`**".format(ctl) in first,
          "orchestrator.CONTROL_REPO={!r} named in README's header={}".format(ctl, ctl in first))

    blocks = re.findall(r"```(.*?)```", readme, re.S)
    cmds = [ln for b in blocks for ln in b.splitlines()
            if ln.strip().startswith("~/options-trader-v3/") or ln.strip().startswith("cd ~/options-trader-v3")]
    check("F3", not cmds, "commands under ~/options-trader-v3: {}".format(cmds))

    import fleet
    check("F4", "`{}`".format(fleet.INSTALL_DIR) in readme, "fleet.INSTALL_DIR={!r}".format(fleet.INSTALL_DIR))

    src = open(os.path.join(ROOT, "tests", "check_ssh_decode.py"), encoding="utf-8").read()
    m = re.search(r"check_ssh_decode\.py — v(\d+\.\d+)", src)
    ver = m.group(1) if m else None
    dated = bool(ver) and re.search(r"^v%s\s+\d{4}-\d{2}-\d{2}\b" % re.escape(ver), src, re.M) is not None
    check("F5", dated, "title v{} has a dated changelog line={}".format(ver, dated))

    print("")
    if FAILS:
        print("FAILED: {}".format(", ".join(FAILS)))
        return 1
    print("ALL PASS (5)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
