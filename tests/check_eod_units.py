#!/usr/bin/env python3
"""
day_trader_pro/tests/check_eod_units.py  v1.0
v1.0  2026-09-11  dtp r361 / CND.4 + CND.5 — the close's units must be able
      to page, and must outlive the work they run.

🔴 WHAT HAPPENED. `install_eod_conductor.sh` (v1) wrote
`EnvironmentFile=${DIR}/.env` into the conductor unit and warned when either
Telegram name was missing from it. `install_eod_v2.sh` rewrote that unit on
2026-08-25 WITHOUT the line, and `notify.py` reads only `os.environ`, so every
close since has found no token: 23 `[notify] missing` lines in the log before
2026-09-11 and three more that night — among them the purge-budget alert CND.2
promised was "NAMED AND ALERTED, NEVER SILENT". `dtp-morning` and
`dtp-shadow-watch` load the same file and page fine.

🔴 AND THE TIMEOUT WAS SET WITHOUT REFERENCE TO THE WORK — CND.2's own open
note. On 2026-09-11 the close verified and halted all fifteen boxes and was
killed at exactly 30:00 inside EDGE_SCAN, the last report phase, so the unit
recorded `failed` on the first night in a week the close did its job.

  U1  the conductor unit loads $REPO/.env
  U2  the analysis unit loads it too — a manual rerun must page the same way
  U3  the conductor's TimeoutStartSec covers its own worst case, derived from
      the conductor's constants and the analysis unit's declared budget —
      never from a number typed into this check
  U4  the installer still checks both Telegram NAMES are present in .env —
      names only, never values (WORKING_AGREEMENT §18a)
  U5  the installer parses (`bash -n`)

⚠️ READS THE INSTALLER, NOT /etc/systemd. The installer is the source of the
units; a hand-patched unit is reverted by the next install, which is how the
v1 line was lost in the first place.
"""
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
INSTALLER = os.path.join(REPO, "install_eod_v2.sh")
FAILS = []

# ⚠️ MEASURED, NOT CHOSEN. 2026-09-11: the fifteen drains answered in 766s
# summed (40-66s each), plus the 45s settle and the EC2 stop-and-wait. This is
# the one input the conductor does not expose as a constant.
CLOSE_ALLOWANCE_S = 900


def check(name, ok, detail=""):
    print("  {:<4} {}  {}".format(name, "PASS" if ok else "FAIL", detail))
    if not ok:
        FAILS.append(name)


def unit_block(src, unit):
    """The heredoc body the installer tees into /etc/systemd/system/<unit>."""
    m = re.search(r"tee /etc/systemd/system/" + re.escape(unit)
                  + r" >/dev/null <<UNIT\n(.*?)\nUNIT\n", src, re.S)
    return m.group(1) if m else None


def timeout_of(block):
    m = re.search(r"^TimeoutStartSec=(\d+)\s*$", block or "", re.M)
    return int(m.group(1)) if m else None


def main():
    try:
        src = open(INSTALLER, encoding="utf-8").read()
    except OSError as exc:
        print("  FAIL  installer unreadable: {}".format(exc))
        return 1
    cond = unit_block(src, "dtp-eod-conductor.service")
    anal = unit_block(src, "dtp-eod-analysis.service")
    if cond is None or anal is None:
        print("  FAIL  a unit heredoc was not found (conductor={}, analysis={})"
              .format(cond is not None, anal is not None))
        return 1

    env_line = re.compile(r"^EnvironmentFile=\$REPO/\.env\s*$", re.M)
    check("U1", bool(env_line.search(cond)),
          "conductor unit loads $REPO/.env")
    check("U2", bool(env_line.search(anal)),
          "analysis unit loads $REPO/.env")

    # ⚠️ READ FROM SOURCE, NOT BY IMPORT. The first cut imported the conductor
    # and went red under the system python3 on `No time zone found with key
    # US/Eastern` — a red about the HOST, not the installer, which is the CV.1
    # shape. The declared defaults are the source of truth and need nothing.
    worst_purge = None
    try:
        csrc = open(os.path.join(REPO, "eod_conductor_v2.py"),
                    encoding="utf-8").read()
        vals = {}
        for name, env in (("PURGE_BUDGET_S", "DTP_PURGE_BUDGET"),
                          ("VERIFY_TIMEOUT_S", "DTP_VERIFY_TIMEOUT")):
            m = re.search(r"^" + name + r"\s*=\s*int\(os\.environ\.get\(\""
                          + env + r"\",\s*\"(\d+)\"\)\)", csrc, re.M)
            vals[name] = int(m.group(1)) if m else None
        if None in vals.values():
            check("U3", False, "conductor constant not found: {}".format(vals))
        else:
            worst_purge = vals["PURGE_BUDGET_S"] + vals["VERIFY_TIMEOUT_S"]
    except OSError as exc:
        check("U3", False, "conductor unreadable: {}".format(exc))
    if worst_purge is not None:
        t_cond, t_anal = timeout_of(cond), timeout_of(anal)
        if t_cond is None or t_anal is None:
            check("U3", False, "TimeoutStartSec missing (conductor={}, "
                               "analysis={})".format(t_cond, t_anal))
        else:
            floor = CLOSE_ALLOWANCE_S + worst_purge + t_anal
            check("U3", t_cond >= floor,
                  "conductor {}s vs floor {}s = close {} + purge budget and "
                  "one overshoot {} + the analysis budget {}".format(
                      t_cond, floor, CLOSE_ALLOWANCE_S, worst_purge, t_anal))

    # U4 — names only. The check must never print or cat the file.
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    names_ok = ("DTP_TELEGRAM_TOKEN DTP_TELEGRAM_CHAT_ID" in code
                and 'grep -q "^$V="' in code)
    leaks = re.search(r"\b(cat|source|\.)\s+\S*\.env\b", code)
    check("U4", names_ok and not leaks,
          "presence check {} · value leak {}".format(
              "found" if names_ok else "MISSING",
              repr(leaks.group(0)) if leaks else "none"))

    r = subprocess.run(["bash", "-n", INSTALLER], capture_output=True, text=True)
    check("U5", r.returncode == 0, (r.stderr or "parses").strip()[:120])

    print("")
    if FAILS:
        print("FAILED: {}".format(", ".join(FAILS)))
        return 1
    print("ALL PASS (5)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
