#!/usr/bin/env python3
"""
tests/check_no_brief_prior.py  v1.0
v1.0  2026-09-26  dtp r431 / OPS.55 — THE MORNING PATH STOPS CARRYING A PRIOR
      NOTHING READS.
      Operator, 2026-09-25: *"the market brief never actually correlated with
      the days Trading — it was Information, but there was no edge to be gained
      and no morning bias ended up correlating."*
      🔑 IT NEVER CORRELATED BECAUSE IT WAS NEVER CONNECTED, AND THAT IS
      MEASURED RATHER THAN ASSUMED. The chain ran: brief scores -> orchestrator
      `_load_selection()` -> `selector.select()` -> `brief_strength` ->
      `_push_brief_flags()` SSHes `~/brief_flags.json` onto EVERY running box
      -> and there the chain ENDS. otv4's `risk/setup_scorer.py`, the only
      thing that ever applied the nudge, was DELETED at OTV4 r152, and
      `config.BRIEF_CONVICTION_WEIGHT` has had exactly one occurrence in that
      tree ever since — its own definition. otv4 r382 recorded it as an orphan
      on 2026-09-14. So for months the fleet has spent an LLM classification
      pass, a selector run and one SSH per box to deliver a number that no
      process on the far end opens.
      ⚠️ B1 IS THE SHIP-BLOCKER AND IT IS AN ALARM CHECK, NOT A CLEANUP CHECK.
      `_load_selection` AUDITS report.json and Telegrams when the `move_ranked`
      sidecar is missing. The information brief (market_brief v1.7.0) emits no
      such sidecar BY DESIGN, so leaving the call in place would have paged the
      operator at 09:15 on the first morning of the new brief — a false alarm
      manufactured by our own change, which is §17 exactly.
      ⚠️ B3 IS A DECLARED REGRESSION GUARD, NOT A BORN-RED FINDING. The wake
      already worked. It is here because this edit touches the path that starts
      the trading day, and r429 proved a new gate going green says nothing
      about what the edit broke one branch over.
      🔑 THE FUNCTIONS ARE STRUCK, NOT DELETED (r240). B4 pins that they still
      exist and are simply unreferenced: they are the only remaining record of
      how the scores C.46 ruled on were assembled.
"""
import io
import json
import os
import sys
import contextlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_fails = []


def ck(tag, ok, msg=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {tag}  {msg}")
    if not ok:
        _fails.append(tag)


def main():
    os.environ["DTP_NOTIFY_CAPTURE"] = "1"
    # ⚠️ REDIRECT THE POWER LEDGER BEFORE IMPORTING ec2ops. B2 drives
    # `run(dry_run=False)` under MOCK, which reaches `ec2ops.start()` and
    # therefore `_power_log()`. The first cut of this file wrote FOUR
    # `START MOCK` rows into the PRODUCTION ledger at logs/fleet_power.log —
    # a checker manufacturing entries in the audit trail another checker
    # reads. Same shape as the peer's §40.1 (a check may assert only what its
    # OWN child could have done) and as otv4 OPS.6, where checkers resolving
    # `~`-expanded defaults built a month of stray bot.log on control.
    os.environ["OT_FLEET_POWER_LOG"] = os.path.join(
        __import__("tempfile").mkdtemp(prefix="power_gate_"), "fleet_power.log")
    import config
    import notify
    import orchestrator

    # A report.json shaped like the INFORMATION brief: no move_ranked, no
    # scores. Under the old code this is exactly what trips the audit.
    import tempfile
    tmp = tempfile.mkdtemp(prefix="brief_prior_")
    rp = os.path.join(tmp, "report.json")
    with open(rp, "w") as fh:
        json.dump({"date": "1999-01-01", "brief_kind": "information",
                   "universe": [], "headlines": {}, "prices": {}}, fh)
    os.environ["DTP_REPORT_JSON"] = rp

    sent = []
    real_send = notify.send
    notify.send = lambda text, silent=False: sent.append(text)

    pushed = []
    real_push = getattr(orchestrator, "_push_brief_flags", None)
    if real_push is not None:
        orchestrator._push_brief_flags = lambda *a, **k: pushed.append(a)

    config.set_mock(True)
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            # ⚠️ dry_run=False, under MOCK. `_push_brief_flags` sits behind
            # `if not dry_run:`, so a dry run never reaches it and B2 would
            # have passed at HEAD while the push was still wired — a check
            # that cannot fail is not a check. MOCK_AWS makes this offline:
            # ec2ops short-circuits and _push_brief_flags has its own mock
            # guard (orchestrator v0.3.2), so nothing is started and no SSH
            # leaves this box.
            rc = orchestrator.run(dry_run=False, gate=False)
        err = ""
    except Exception as exc:                                      # noqa: BLE001
        rc, err = 1, f"{type(exc).__name__}: {exc}"
    finally:
        notify.send = real_send
        if real_push is not None:
            orchestrator._push_brief_flags = real_push
        os.environ.pop("DTP_REPORT_JSON", None)
    out = buf.getvalue()

    # ── B1 — NO ALARM FOR A BRIEF THAT CARRIES NO SIDECAR ───────────────
    noisy = [m for m in sent
             if "move_ranked" in m or "selection" in m.lower()
             or "sidecar" in m.lower() or "discretionary" in m.lower()]
    ck("B1", not noisy,
       "an information-shaped report.json raises no alert"
       if not noisy else f"would page the operator: {noisy[:1]}")

    # ── B2 — NO PRIOR IS DELIVERED TO ANY BOX ───────────────────────────
    ck("B2", not pushed,
       "no brief_flags pushed to any box"
       if not pushed else f"_push_brief_flags still called {len(pushed)}x")

    # ── B3 — THE WAKE STILL HAPPENS (declared regression guard) ─────────
    # Declared: this passed before the edit and is here to catch what the
    # edit breaks one branch over, which is r429's lesson.
    ck("B3", rc == 0 and "Wake list" in out and err == "",
       f"rc={rc}; wake list printed: {'Wake list' in out}"
       + (f" · {err}" if err else ""))

    # ── B4 — THE STRUCK FUNCTIONS SURVIVE, UNREFERENCED (r240) ──────────
    src = open(os.path.join(ROOT, "orchestrator.py")).read()
    import ast
    tree = ast.parse(src)
    defined = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    called = {n.func.id for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    struck = {"_load_selection", "_push_brief_flags"}
    ck("B4", struck <= defined and not (struck & called),
       f"present={sorted(struck & defined)} still-called="
       f"{sorted(struck & called) or 'none'} (must be defined, never called)")

    if _fails:
        print(f"\nRED — {len(_fails)} check(s) failed: {' '.join(_fails)}")
        return 1
    print("\nGREEN — the morning path carries no prior and pages nobody for it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
