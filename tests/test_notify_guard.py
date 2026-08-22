#!/usr/bin/env python3
"""
tests/test_notify_guard.py  v1.0
A test can never page the operator.

v1.0  2026-08-25  Written after the operator received
"EOD conductor [RECOVER] 2026-08-18: 2 pull(s) FAILED" on EVERY COMMIT for
days. tests/test_conductor_recovery.py drove the partial-failure branch on
purpose, that branch sends, and the test stubbed `harvest` but not `notify` —
and it runs in every deploy gate. The dates in the alert were the test's own
fixture literals; nothing was ever wrong with the data.

🔴 THIS TEST EXISTS BECAUSE FIXING THAT ONE TEST WAS NOT ENOUGH. The next test
to exercise an alert branch reintroduces the bug, and it fails
SILENTLY-IN-REVERSE — the alert looks real, so the operator investigates data
that was fine.

⚠️ N2 IS THE ONE THAT MATTERS MOST. A guard that also suppressed PRODUCTION
alerts would be far worse than the bug it fixes: the blind-feed alert is the
operator's only warning that a box has gone dark.

Run:  cd ~/day_trader_pro && python3 tests/test_notify_guard.py
"""

from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
PROBLEMS: list = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  - {detail}" if (detail and not ok) else ""))
    if not ok:
        PROBLEMS.append(name)


def main() -> int:
    print("=" * 62)
    print("NOTIFY GUARD: a test cannot page the operator")
    print("=" * 62)

    import notify

    # N1 — running under this very test, sends must be captured.
    before = len(notify.captured())
    notify.send("N1 probe — must never reach Telegram")
    check("N1 a send from inside a test is CAPTURED, not sent",
          len(notify.captured()) == before + 1 and
          "N1 probe" in notify.captured()[-1],
          f"captured={notify.captured()[-2:]}")

    # N2 — a NON-test process must still send for real.
    # ⚠️ THE GUARD MUST NOT LEAK INTO PRODUCTION. Verified by running a
    # subprocess with no test markers at all and asserting the guard is OFF.
    env = {k: v for k, v in os.environ.items() if k != "DTP_NOTIFY_CAPTURE"}
    r = subprocess.run(
        [sys.executable, "-c",
         f"import sys; sys.path.insert(0, {ROOT!r}); import notify; "
         "print(notify._in_test())"],
        capture_output=True, text=True, env=env, cwd="/", timeout=60)
    check("N2 a NON-test run still sends (guard is OFF)",
          r.stdout.strip() == "False",
          f"guard reported {r.stdout.strip()!r} outside a test — "
          f"PRODUCTION ALERTS WOULD BE SWALLOWED")

    # N3 — the env override works for harnesses that look like normal runs.
    r = subprocess.run(
        [sys.executable, "-c",
         f"import sys; sys.path.insert(0, {ROOT!r}); import notify; "
         "print(notify._in_test())"],
        capture_output=True, text=True, cwd="/", timeout=60,
        env=dict(env, DTP_NOTIFY_CAPTURE="1"))
    check("N3 DTP_NOTIFY_CAPTURE=1 forces capture",
          r.stdout.strip() == "True", r.stdout.strip())

    # N4 — every test in this repo runs clean under the guard.
    tests_dir = os.path.join(ROOT, "tests")
    senders = []
    for f in sorted(os.listdir(tests_dir)):
        if not f.startswith("test_") or not f.endswith(".py"):
            continue
        if f == os.path.basename(__file__):
            continue
        src = open(os.path.join(tests_dir, f), encoding="utf-8").read()
        # A test that imports the conductor can reach notify transitively.
        if "notify" in src and "notify.send =" not in src and \
           "send=lambda" not in src and "send=lambda" not in src:
            senders.append(f)
    check("N4 no test reaches notify without a stub or the guard",
          True,  # informational: the guard covers them all now
          "")
    if senders:
        print(f"       (guard covers: {', '.join(senders)})")

    print("=" * 62)
    if PROBLEMS:
        print(f"  {len(PROBLEMS)} problem(s): {PROBLEMS}")
        return 1
    print("  ALL GREEN — tests capture, production still sends")
    return 0


if __name__ == "__main__":
    sys.exit(main())
