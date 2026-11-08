#!/usr/bin/env python3
"""
day_trader_pro/tests/check_ramp_top_report.py  v1.0
v1.0  2026-11-08  dtp r529 / MENU.1 (the 11-07 brief section 5 item 6 / R5 half; hygiene queue item 5). THE FLEET
      ITEM IS THE RAMP TOP, AND ITS UNIT READER READS THE UNITS THE FLEET HAS. The ORB trade is retired (OTV5 r76
      RETIRE.1); OT_ORB_BUDGET_USD is the live Breakout ramp top (configure.sh item 7 "Ramp TOP (MAX)"). The report's
      box program split each `Environment=` line on its first "=", so the quoted form (`Environment="K=V"`, what the
      fleet's units carry) became the key `"K` and every such box read (DEFAULT). Every check runs the REAL box
      program's parser (exec'd out of tests/orb_budget_fleet.BOX_PROGRAM, nothing re-typed here).
  T1  bare `Environment=K=V` reads K=V
  T2  double-quoted `Environment="K=V"` reads K=V (the v1.1 reader made it `"K`)
  T3  single-quoted with a space `Environment='K=a b'` reads K=a b
  T4  several assignments on one line all read
  T5  a line shlex refuses is COUNTED (UNPARSED) and contributes no pair
  T6  the registry label is "Ramp TOP (OT_ORB_BUDGET_USD) & spot", wired to mi_orb_budget_fleet, and no menu label
      names an "ORB budget"
  T7  the report's printed text says Ramp TOP and points at configure.sh item 7, never "ORB budget" or "-> 8"
Run:  python3 tests/check_ramp_top_report.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DTP = os.path.dirname(HERE)
SCRIPT = os.path.join(HERE, "orb_budget_fleet.py")
REGISTRY = os.path.join(DTP, "menu_registry.sh")
FAILS = []


def check(cid, ok, why=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {cid}" + ("" if ok else f"  {why}"))
    if not ok:
        FAILS.append(cid)


def box_program():
    src = open(SCRIPT).read()
    ns = {}
    # Pull BOX_PROGRAM out of the module text without importing fleet.
    start = src.index("BOX_PROGRAM = r'''") + len("BOX_PROGRAM = r'''")
    end = src.index("'''", start)
    prog = src[start:end]
    # Only the parser half: everything before the UNIT read runs nothing on this host.
    head = prog[:prog.index('UNIT = "/etc/systemd/system/optionsbot.service"')]
    exec(compile(head, "BOX_PROGRAM", "exec"), ns)
    return ns, prog


def main():
    ns, prog = box_program()
    unit_env, unparsed = ns["unit_env"], ns["UNPARSED"]

    check("T1", unit_env("Environment=OT_RISK_USD=1050\n") == [("OT_RISK_USD", "1050")],
          unit_env("Environment=OT_RISK_USD=1050\n"))
    got = unit_env('Environment="OT_ORB_BUDGET_USD=2500"\n')
    check("T2", got == [("OT_ORB_BUDGET_USD", "2500")], got)
    got = unit_env("Environment='OT_BOT_NAME=Options Trader'\n")
    check("T3", got == [("OT_BOT_NAME", "Options Trader")], got)
    got = unit_env('Environment="OT_A=1" OT_B=2 \'OT_C=x y\'\n')
    check("T4", got == [("OT_A", "1"), ("OT_B", "2"), ("OT_C", "x y")], got)
    before = unparsed[0]
    got = unit_env('Environment="OT_BROKEN=1\nEnvironment=OT_OK=1\n')
    check("T5", got == [("OT_OK", "1")] and unparsed[0] == before + 1, (got, unparsed[0] - before))

    reg = open(REGISTRY).read()
    check("T6", '"ITEM|Ramp TOP (OT_ORB_BUDGET_USD) & spot|mi_orb_budget_fleet"' in reg
          and "ITEM|ORB budget" not in reg, "registry label")

    src = open(SCRIPT).read()
    body = src[src.index("def run("):]
    check("T7", "RAMP TOP (OT_ORB_BUDGET_USD) AND SPOT" in body and "configure.sh -> 7 (Ramp TOP)" in body
          and "ORB BUDGET" not in body and "ORB budget" not in body and "-> 8" not in body, "report text")

    print(f"\n{'GREEN' if not FAILS else 'RED'}: {7 - len(FAILS)}/7")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
