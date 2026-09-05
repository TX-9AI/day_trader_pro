#!/usr/bin/env python3
"""check_conductor_purge.py — v1.1
v1.1  2026-09-05 — dtp r281. C9/C10 pin the v2.2 ordering: the writers are
      released BEFORE the purge, on the VERIFIED list only, by stopping and
      never disabling. ⚠️ C7 IS RE-DERIVED, NOT PATCHED — it asserted "no
      VACUUM at takedown", which stopped being true the moment `retention_purge`
      grew a gated one, and it would have passed forever because the conductor's
      own text never mentions vacuum either way. What survives is the real
      invariant: ONE implementation of the reclaim, and the conductor is not a
      second one (the r233/r234 trap).
v1.0  2026-08-27

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

    # ── C7 — RE-DERIVED 2026-09-05 (dtp r281) ────────────────────────────
    # 🔴 IT ASSERTED "NO VACUUM AT TAKEDOWN" AND THAT IS NO LONGER TRUE. A
    # gated vacuum now runs inside `retention_purge` at exactly this point, so
    # the old check would have gone on certifying a rule the system had stopped
    # following — the r233/r234 trap, and it would have passed forever because
    # the conductor's own text never mentions vacuum either way.
    # WHAT SURVIVES IS THE REAL INVARIANT: there is ONE implementation of the
    # reclaim and the conductor is not a second one. If a future edit puts a
    # VACUUM in the phase body, that is two answers to one question (§35) and
    # the box-side gate — free-disk against live size — is bypassed.
    # ⚠️ ANCHORED ON A CALL, NOT A MENTION (§20). This phase's docstring now
    # EXPLAINS the reclaim at length, so any string search for the word matches
    # the prose that documents the property — the trap this repo has tripped
    # four times in one week.
    check("C7 the conductor does not run VACUUM ITSELF; the gated one lives "
          "in retention_purge",
          'execute("vacuum' not in pbody.lower()
          and "vacuum()" not in pbody.lower())

    # ── 🔴 C9/C10 — v2.2, THE ORDER THAT MAKES THE RECLAIM WORTH ANYTHING ─
    # A checkpoint cannot truncate a WAL another connection is holding, so the
    # writers have to be released BEFORE the purge or the reclaim returns only
    # what the bot happened to let go of. Measured in otv4
    # check_purge_reclaim R2/R2b; the fleet's evidence is MU's 1.6 GB WAL.
    check("C9 stop_services() exists", "stop_services" in fns)
    i_stop = body.find("stop_services(")
    check("C9b services are released BEFORE the purge, and after the verdict",
          i_stop != -1 and i_ok < i_stop < i_p, f"{i_ok} < {i_stop} < {i_p}")
    # ⚠️ HELD BOXES KEEP THEIR SERVICES. A held box is up for the operator to
    # troubleshoot and holds the only copy of its day; taking its writers down
    # changes what he is looking at.
    check("C10 the stop is called on the VERIFIED list, never on held",
          "stop_services(ok" in body and "stop_services(held" not in body)
    sf = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "stop_services"),
              None)
    sbody = ast.unparse(sf) if sf else ""
    # ⚠️ STOP, NEVER DISABLE — the units must come back on the next wake.
    # ⚠️ SAME ANCHORING: the docstring says "NOT `disable`" on purpose, so the
    # check keys on the COMMAND that would do it.
    check("C10b it stops the units without disabling them",
          "systemctl stop" in sbody and "systemctl disable" not in sbody)

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
