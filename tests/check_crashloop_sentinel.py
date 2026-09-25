#!/usr/bin/env python3
# day_trader_pro/tests/check_crashloop_sentinel.py — v1.1
# v1.1 (2026-09-25) — r429 / OPS.53. C9's FIXTURE WAS BUILT ON AN UNMEASURED
#   ASSUMPTION AND IS CORRECTED, NOT DELETED (r240). It was written as "three
#   hourly BAKES" and asserts silence — but A BAKE DOES NOT INCREMENT
#   NRestarts. Measured 2026-09-25: AAL had FOUR manual starts (boot, wake, the
#   operator's bake) plus THREE automatic restarts and NRestarts read exactly
#   3; SOFI was baked in the same window, never crashed, and reads 0. So C9
#   actually models a SLOW CRASH LOOP — AAL's incident — and its silence is
#   correct only for the BURST rule. §0.4: a fixture nobody had measured.
#   ⚠️ AND C7 EARNED ITS KEEP THIS REVISION. r429's first cut placed the new
#   session rule as an `elif` above the recovery branch and swallowed the
#   RECOVERED alert; C7 went red and caught it. Checks themselves unchanged.
# v1.0 (2026-09-23) — dtp r418 / OPS.41. THE ALARM MUST FIRE ON A LOOP AND STAY
#   SILENT ON MAINTENANCE, AND BOTH HALVES ARE CHECKS.
#   🔴 WHAT IT IS WRITTEN FROM: QQQ's optionsbot restarted 41 times on a corrupt
#   feed_store.db and every restart emitted the bot's ordinary
#   `🚀 STARTED | QQQ | service restart` line. The operator read six of them on
#   his phone and could not tell a loop from a bake — one of them literally said
#   "bake — restarting on a new revision".
#   🔑 C1 IS THE CHECK THAT DECIDES WHETHER THIS SHIPS. A sentinel that fires on
#   every bake is worse than none: it trains the reader to swipe the channel
#   away, and then the real loop arrives and is swiped too (§17). One restart
#   must be SILENT.
#   ⚠️ C5 EXISTS BECAUSE SILENCE IS THE FAILURE MODE THIS PROJECT KEEPS PAYING
#   FOR. A box that cannot be read must NOT render as a healthy box — but one
#   ssh blip must not page either, so the alarm waits for the SECOND miss.
"""Gate: the crash-loop sentinel's decision rule.

C1  ONE restart (a bake) does NOT alert                        [control]
C2  THRESHOLD restarts in the window DO alert, WITH the error
C3  a still-burning loop does not re-alert until RENOTIFY_S
C4  ...and re-alerts once the cooldown passes
C5  an unreachable box alerts on the SECOND miss, not the first
C6  a counter that goes BACKWARDS invents no restarts          [control]
C7  recovery emits an all-clear
C8  the SHIPPED defaults detect a realistic 9-min-spaced loop
C9  ...and still ignore an hourly bake                          [control]
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_fails = []


def ck(tag, ok, msg=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {tag}  {msg}")
    if not ok:
        _fails.append(tag)


def _obs(n, err="boom"):
    return {"QQQ": {"restarts": n, "sub": "running", "err": err}}


def main():
    try:
        import crashloop_sentinel as CS
    except Exception as exc:                                  # noqa: BLE001
        ck("C0", False, f"cannot import crashloop_sentinel ({exc})")
        print("\nRED — 1 check(s) failed: C0")
        return 1

    ev = getattr(CS, "evaluate", None)
    if ev is None:
        for t in ("C1", "C2", "C3", "C4", "C5", "C6", "C7"):
            ck(t, False, "evaluate() is absent")
        print(f"\nRED — {len(_fails)} check(s) failed: {' '.join(_fails)}")
        return 1

    thr = getattr(CS, "THRESHOLD", 3)
    renot = getattr(CS, "RENOTIFY_S", 1800)
    t0 = 1_000_000.0

    # ── C1 — CONTROL: a single restart (a bake) is SILENT ────────────────
    st, _a = ev({}, _obs(0), t0)                      # baseline observation
    st, alerts = ev(st, _obs(1), t0 + 60)             # one restart: a bake
    ck("C1", not alerts, f"alerts on a single restart: {len(alerts)} (want 0)")

    # ── C2 — THRESHOLD restarts in-window DO alert, and carry the cause ──
    st, _a = ev({}, _obs(0), t0)
    st, alerts = ev(st, _obs(thr, err="database disk image is malformed"),
                    t0 + 60)
    loop = [a for a in alerts if a.get("kind") == "loop"]
    has_cause = bool(loop) and "malformed" in loop[0]["text"]
    ck("C2", len(loop) == 1 and has_cause,
       f"loop alerts={len(loop)} carries-cause={has_cause}")

    # ── C3 — a still-burning loop does NOT re-alert immediately ──────────
    st2, alerts2 = ev(st, _obs(thr + 1), t0 + 120)
    ck("C3", not [a for a in alerts2 if a.get("kind") == "loop"],
       f"re-alerts inside cooldown: {len(alerts2)} (want 0)")

    # ── C4 — ...and DOES re-alert once the cooldown has passed ───────────
    # ⚠️ THE LOOP MUST KEEP BURNING FOR THIS TO MEAN ANYTHING. My first cut
    # jumped the clock straight past RENOTIFY_S with no restarts in between,
    # so the in-window history aged out and there was nothing left to alert
    # about — the CHECK was wrong and the CODE was right, found by running it
    # (r413's E2, same shape). A real loop restarts every poll, so poll it.
    stx, n_alerts, count = st2, 0, thr + 1
    t = t0 + 120
    while t < t0 + 120 + renot + 120:
        t += 60
        count += 1
        stx, al = ev(stx, _obs(count), t)
        n_alerts += len([a for a in al if a.get("kind") == "loop"])
    ck("C4", n_alerts == 1,
       f"re-alerts across {renot + 120}s of continuous looping: {n_alerts} "
       f"(want exactly 1 — one per cooldown, not one per restart)")

    # ── C5 — unreachable: silent on the first miss, alarm on the second ──
    blind = {"QQQ": {"restarts": None, "sub": "", "err": ""}}
    sA, a1 = ev({}, blind, t0)
    sB, a2 = ev(sA, blind, t0 + 60)
    ck("C5", not a1 and len([a for a in a2
                             if a.get("kind") == "unreachable"]) == 1,
       f"first miss alerts={len(a1)} (want 0), second={len(a2)} (want 1)")

    # ── C6 — CONTROL: a counter reset invents nothing ────────────────────
    st, _a = ev({}, _obs(50), t0)
    st, alerts = ev(st, _obs(0), t0 + 60)             # reset-failed
    ck("C6", not alerts,
       f"alerts after a counter reset: {len(alerts)} (want 0)")

    # ── C7 — recovery emits an all-clear ─────────────────────────────────
    st, _a = ev({}, _obs(0), t0)
    st, _a = ev(st, _obs(thr), t0 + 60)               # loop, alerted
    win = getattr(CS, "WINDOW_S", 900)
    st, alerts = ev(st, _obs(thr), t0 + 60 + win + 1)  # quiet past the window
    ck("C7", len([a for a in alerts if a.get("kind") == "recovered"]) == 1,
       f"recovery alerts="
       f"{len([a for a in alerts if a.get('kind') == 'recovered'])} (want 1)")

    # ── C8 — THE SHIPPED DEFAULTS MUST DETECT A REAL LOOP ────────────────
    # 🔴 THE CHECK THIS FILE WAS MISSING, AND THE ONE THAT CAUGHT A USELESS
    # TOOL. Every check above drove `evaluate()` with whatever spacing suited
    # the fixture, so all seven passed while the SHIPPED defaults
    # (THRESHOLD=3 over a 900s window) could never fire on the real incident:
    # systemd's backoff spaced QQQ's restarts 8-10 minutes apart, and fifteen
    # minutes only ever holds two. A gate that never uses the real constants
    # is a gate on a tool nobody ships.
    # ⚠️ DRIVEN AT MODULE DEFAULTS, NOT AT OVERRIDES — if the env is set, this
    # check says so and refuses rather than passing on someone else's numbers.
    if (os.environ.get("DTP_CRASHLOOP_THRESHOLD")
            or os.environ.get("DTP_CRASHLOOP_WINDOW_S")):
        ck("C8", False, "env overrides THRESHOLD/WINDOW_S — cannot judge the "
                        "shipped defaults; unset them to run C8")
    else:
        st8, fired, count, t = {}, 0, 0, t0
        st8, _a = ev(st8, _obs(0), t)
        for _ in range(8):                       # 8 restarts at 9-min spacing
            t += 540
            count += 1
            st8, al = ev(st8, _obs(count), t)
            fired += len([a for a in al if a.get("kind") == "loop"])
        ck("C8", fired >= 1,
           f"a 9-min-spaced loop over 72 min fired {fired} alert(s) at the "
           f"SHIPPED defaults (THRESHOLD={thr}, WINDOW_S={win}) — want >=1")

        # and the same defaults must still ignore an hourly bake
        st9, fired9, c9, t9 = {}, 0, 0, t0
        st9, _a = ev(st9, _obs(0), t9)
        for _ in range(3):                       # one restart per hour
            t9 += 3600
            c9 += 1
            st9, al = ev(st9, _obs(c9), t9)
            fired9 += len([a for a in al if a.get("kind") == "loop"])
        # 🔴 r429 — THIS FIXTURE'S PREMISE WAS WRONG AND IS CORRECTED HERE
        # RATHER THAN DELETED (r240). It was written as "three hourly BAKES"
        # and asserts they stay quiet — but a bake does NOT increment
        # NRestarts, so this scenario cannot be a bake. MEASURED 2026-09-25:
        # AAL had FOUR manual starts (boot, wake, operator bake) plus THREE
        # automatic restarts after exit-1, and NRestarts read exactly 3; SOFI
        # was baked in the same window, never crashed, and reads 0. NRestarts
        # counts ONLY restarts the Restart= policy performed.
        # ⚠️ SO WHAT THIS ACTUALLY MODELS IS A SLOW CRASH LOOP — three
        # automatic restarts an hour apart — which is precisely AAL's incident.
        # It correctly stays quiet for the BURST rule (kind="loop"), which is
        # all it ever asserted; the new session rule (kind="session_loop") is
        # what catches it, and check_crashloop_session S1 pins that.
        # §0.4: the fixture was built from an assumption nobody had measured.
        ck("C9", fired9 == 0,
           f"three hourly automatic restarts fire {fired9} BURST alert(s) — "
           f"want 0; the slow-loop rule catches them instead (see "
           f"check_crashloop_session S1)")

    if _fails:
        print(f"\nRED — {len(_fails)} check(s) failed: {' '.join(_fails)}")
        return 1
    print("\nGREEN — the sentinel fires on loops and stays quiet on bakes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
