#!/usr/bin/env python3
"""check_conductor_purge.py — v1.0

🔴 THE PURGE RUNS IN THE CONDUCTOR, AFTER VERIFY, BEFORE TAKEDOWN.

Operator, 2026-08-27: *"It needs to be immediately after the s3 drain is
confirmed & BEFORE the go down command."*

⚠️ WHY IT COULD NOT STAY IN `self_close`. The purge was called from
`warehouse/self_close.py`, which fires at **16:45** — but the conductor stops
the boxes by ~**16:08**. On any normal night the 16:45 timer fires into a
STOPPED MACHINE and the purge NEVER RUNS. It executed only on nights the
conductor had already failed.

**So two months of "dry runs" were also two months of no runs at all.** Arming
the flag (r162) was necessary and not sufficient — the path it lived on did not
execute. The fleet reached 100% disk and went blind mid-session on 2026-08-27.

⚠️ THE ORDERING IS THE SAFETY PROPERTY, not a preference. `takedown()` builds
`ok` from the boxes whose data is CONFIRMED IN S3. Purging that list means
nothing is ever deleted from a box whose day exists only locally. A HELD box
keeps everything until its next wake proves the push.
"""
import ast
import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_fails = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + (f"  — {detail}" if detail else ""))
    if not cond:
        _fails.append(label)


def main():
    src = open(os.path.join(_root, "eod_conductor_v2.py"),
               encoding="utf-8").read()
    tree = ast.parse(src)

    # ── C1 — the phase exists ────────────────────────────────────────────
    fns = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    check("C1 purge_verified() exists in the conductor",
          "purge_verified" in fns)

    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "takedown"), None)
    body = ast.unparse(fn) if fn else ""

    # ── 🔴 C2/C3 — THE ORDERING THE OPERATOR SPECIFIED ───────────────────
    i_ok = body.rfind("held.append(s)")      # the verify list is complete here
    i_p = body.find("purge_verified(")
    i_s = body.find("ec2ops.stop(")
    check("C2 the purge runs AFTER the verified list is built",
          i_ok != -1 and i_p != -1 and i_ok < i_p, f"{i_ok} < {i_p}")
    check("C3 the purge runs BEFORE the boxes are stopped",
          i_p != -1 and i_s != -1 and i_p < i_s, f"{i_p} < {i_s}")

    # ── 🔴 C4 — ONLY VERIFIED BOXES ARE PURGED ───────────────────────────
    # ⚠️ Purging a HELD box would delete the only copy of a day that never
    # reached S3. `ok` is the verified list; `held` is not.
    check("C4 the purge is called on the VERIFIED list, never on held",
          "purge_verified(ok" in body and "purge_verified(held" not in body)

    # ── C5 — it arms the purge ───────────────────────────────────────────
    pf = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "purge_verified"),
              None)
    pbody = ast.unparse(pf) if pf else ""
    check("C5 the remote command passes --apply",
          "--apply" in pbody)

    # ── 🔴 C6 — AND IT REPORTS PER BOX ───────────────────────────────────
    # The two-month failure was a log line that never changed. A per-box row
    # count is what would have made "WOULD remove" visible on night one.
    check("C6 a dry result is called out explicitly",
          "WOULD remove" in pbody and "RAN DRY" in pbody)

    # ── C7 — NO VACUUM at takedown ───────────────────────────────────────
    # ⚠️ It rewrites the whole file and would stall the halt for minutes.
    check("C7 the phase does not run VACUUM",
          "VACUUM" not in pbody.upper().replace("NO VACUUM", "")
          .replace("VACUUM STAYS", "").replace("A VACUUM", ""))

    # ── C8 — a long timeout, or it dies at 22 seconds ────────────────────
    # ⚠️ ssh_util gives subprocess `SSH_CONNECT_TIMEOUT + 10` = 22s by default.
    # A 1.7M-row purge takes minutes; without an explicit timeout the phase
    # would report failure on every box while the work completed anyway.
    check("C8 the phase passes a long ssh timeout",
          "timeout=VERIFY_TIMEOUT_S" in pbody)

    print()
    if _fails:
        print(f"FAILED {len(_fails)}: " + ", ".join(_fails))
        return 1
    print("check_conductor_purge: all checks pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
