#!/usr/bin/env python3
"""day_trader_pro/tests/orb_budget_fleet.py — v1.1
SPOT AND THE ORB BUDGET ON EVERY RUNNING BOX.

v1.1  2026-09-01 — reads the systemd unit's Environment= lines before importing
      config. v1.0 read config's defaults and reported QQQ/200 on every box.
v1.0  2026-09-01 — read-only. Runs one command per box and prints a table.
      Staged as a standalone script before being wired into devtools.

🔴 v1.1 — v1.0 READ THE WRONG ENV LAYER. It imported `config` in a bare SSH
session, which sees none of the box's environment, so INSTRUMENT came back
"QQQ" on all fifteen boxes and the budget came back 200 — config.py's
OT_RISK_USD fallback — instead of the operator's 1050. The spots were right
(those are on disk) which made the table look plausible while every env-derived
figure was a default.

🔑 THE `Environment=` LINES IN THE UNIT FILE ARE THE TRUTH. That is what
configure.sh:97 writes and reads and what rotate_env_remote.sh:65 reads; this
uses the same reader rather than a new mechanism. They are injected into the
process environment and THEN config is imported, so config's own precedence
(OT_ORB_BUDGET_USD falling back to OT_RISK_USD) applies instead of being
reimplemented here and drifting.

⚠️ NO PATH IS SPELLED FOR THE STATE FILE — `orb_state.json` is derived from
`LOG_FILE`, which is an env-independent constant. Spelling a path is how the
r201 spot hint shipped broken (WORKING_AGREEMENT §0).

⚠️ `(DEFAULT)` IS THE POINT OF THE REPORT. A box nobody configured falls back
to one trade's risk, which on an index name is a 1-lot — it will look like a
broken strategy rather than an unset variable.

⚠️ THE BOX-SIDE PROGRAM EXITS 0 NO MATTER WHAT. A missing state file, an
unreadable config or a dead venv still prints a line. A non-zero rc would make
the fleet runner discard stdout, so one bad box would hide the other fourteen
— the `grep -c` lesson, in a different shape.

⚠️ IT IS INVOKED THROUGH `fleet._exec`, NOT THROUGH A SHELL STRING. Driving the
fleet directly removes bash, ssh and the remote shell as quoting layers; the
program text arrives exactly as written here.

Usage:
    python3 tests/orb_budget_fleet.py
    python3 tests/orb_budget_fleet.py --only SPX,QQQ,AMD
"""
import argparse
import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)

try:
    import fleet
except Exception as exc:                                        # noqa: BLE001
    print(f"FATAL: cannot import fleet from {_root}: {exc}")
    sys.exit(2)

# The program that runs ON EACH BOX. Kept as one string so what is verified
# here is exactly what executes there.
BOX_PROGRAM = r'''
import json, os, subprocess, sys

# 🔴 THE ENVIRONMENT IS NOT IN THIS SHELL. v1.0 imported `config` in a bare SSH
# session and got its DEFAULTS: INSTRUMENT read "QQQ" on all fifteen boxes and
# the budget read 200 (config.py's OT_RISK_USD fallback) instead of the
# operator's 1050. The bot inherits these from systemd; ssh does not.
# 🔑 THE TRUTH IS `Environment=` LINES IN THE UNIT FILE, which is what
# configure.sh:97 writes and reads, and what rotate_env_remote.sh:65 reads.
# Same reader, not a new mechanism.
# ⚠️ INJECT AND IMPORT, rather than reimplementing the precedence. config.py
# decides how OT_ORB_BUDGET_USD falls back to OT_RISK_USD and what the final
# default is; duplicating that logic here is how the two drift apart.
UNIT = "/etc/systemd/system/optionsbot.service"
try:
    out = subprocess.run(["sudo", "grep", "-h", "^Environment=", UNIT],
                         capture_output=True, text=True, timeout=15).stdout
    for line in out.splitlines():
        kv = line.split("=", 1)[1] if "=" in line else ""
        if "=" in kv:
            k, v = kv.split("=", 1)
            os.environ[k.strip()] = v.strip()
except Exception as e:
    print("UNIT_UNREADABLE|%s" % e)

try:
    from config import (ORB_BUDGET_USD as B, ORB_BUDGET_IS_DEFAULT as D,
                        LOG_FILE, INSTRUMENT as I, RISK_PER_TRADE_USD as R)
except Exception as e:
    print("CONFIG_UNREADABLE|%s" % e)
    sys.exit(0)

spot = None
err = ""
path = os.path.join(os.path.dirname(LOG_FILE), "orb_state.json")
try:
    spot = json.load(open(path)).get("price")
except FileNotFoundError:
    err = "no orb_state.json at %s" % path
except Exception as e:
    err = "state unreadable: %s" % e
print("OK|%s|%s|%.2f|%d|%.2f|%s" % (I, spot if spot else "", B,
                                    1 if D else 0, R, err))
sys.exit(0)
'''


def run(only, install_dir="~/options-trader"):
    cmd = (f"cd {install_dir} && venv/bin/python - <<'PYEOF'\n"
           f"{BOX_PROGRAM}\nPYEOF")
    try:
        boxes = fleet.get_fleet(only=only)
    except Exception as exc:                                    # noqa: BLE001
        print(f"FATAL: cannot enumerate the fleet: {exc}")
        return 2

    running = [(s, ip) for s, ip, st in boxes if st == "running"]
    down = [s for s, _, st in boxes if st != "running"]
    if not running:
        print("  no running boxes.")
        return 1

    print(f"\n  ORB BUDGET AND SPOT — {len(running)} running box(es)")
    print(f"  {'sym':<6} {'spot':>9} {'budget':>9} {'bud/spot':>9}  note")
    print("  " + "-" * 52)

    rows, problems = [], []
    for sym, ip in running:
        rc, out, err = fleet._exec(sym, ip, cmd)
        line = (out or "").strip().splitlines()
        line = line[-1] if line else ""
        if line.startswith("OK|"):
            _, inst, spot, budget, isdef, risk, note = (line.split("|") + [""] * 7)[:7]
            rows.append((inst or sym, spot, float(budget), isdef == "1",
                         float(risk), note))
        elif line.startswith("CONFIG_UNREADABLE|"):
            problems.append((sym, line.split("|", 1)[1]))
        elif line.startswith("UNIT_UNREADABLE|"):
            # ⚠️ Distinct from a config failure: the unit exists but could not
            # be read, so every figure below would be a default. Say which.
            problems.append((sym, "unit unreadable (figures would be "
                                  "DEFAULTS): " + line.split("|", 1)[1]))
        else:
            # ⚠️ Never silent. rc and stderr are shown so a failure is
            # distinguishable from a box with nothing to say.
            problems.append((sym, f"rc={rc} out={line[:60]!r} err={(err or '')[:60]!r}"))

    for inst, spot, budget, isdef, risk, note in sorted(rows):
        if spot:
            s = float(spot)
            print(f"  {inst:<6} {s:>9.2f} {budget:>9.0f} {budget / s:>8.1f}x"
                  f"  {'(DEFAULT - not set)' if isdef else ''}{note}")
        else:
            print(f"  {inst:<6} {'n/a':>9} {budget:>9.0f} {'':>9}"
                  f"  {'(DEFAULT - not set)' if isdef else ''}{note}")

    n_def = sum(1 for r in rows if r[3])
    print()
    if n_def:
        print(f"  ⚠️  {n_def} of {len(rows)} box(es) are on the DEFAULT budget "
              f"(one trade's risk).")
        print("      Those will size a 1-lot on an expensive underlying. "
              "configure.sh -> 8.")
    else:
        print(f"  all {len(rows)} box(es) have an explicit ORB budget.")
    if problems:
        print()
        for sym, why in problems:
            print(f"  !! {sym}: {why}")
    if down:
        print(f"\n  not running ({len(down)}): {', '.join(sorted(down))}")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description="ORB budget and spot per box")
    ap.add_argument("--only", default=None,
                    help="comma-separated symbols (default: whole universe)")
    ap.add_argument("--install-dir", default="~/options-trader")
    a = ap.parse_args(argv)
    only = ([s.strip().upper() for s in a.only.split(",") if s.strip()]
            if a.only else None)
    return run(only, a.install_dir)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
