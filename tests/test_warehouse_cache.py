#!/usr/bin/env python3
# day_trader_pro/tests/test_warehouse_cache.py — v1.0
# v1.0 (2026-09-01) — dtp r238. THE CACHE CLEANS UP, ALWAYS.
#
# 🔴 THE LEAK THIS EXISTS TO PREVENT IS ALREADY IN THE REPO. `tools/report_parity.py`
#   calls `tempfile.mkdtemp` TWICE and removes neither directory, so every parity
#   run leaves scratch behind. §27's rule, in the operator's words: the temp file
#   goes and "just leaves the report in the folder behind".
#
# ⚠️ CLEANUP ON THE HAPPY PATH IS THE EASY HALF. C2 and C3 are the ones that
#   matter: an exception and an outright SIGTERM. A cleanup that only runs when
#   nothing went wrong is a cleanup that runs when it is not needed.

import os
import signal
import subprocess
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)

_fails = []


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + (f"   [{detail}]" if detail else ""))
    if not ok:
        _fails.append(name)


def main():
    import warehouse_cache as WC
    import config

    # ── C1 — scratch is DISK-backed, never tmpfs ────────────────────────
    # 🔑 On many Ubuntu images /tmp is tmpfs — RAM with a filesystem in front
    # of it — so caching there puts the OOM back wearing a different hat.
    scratch = WC.choose_scratch()
    check("C1 the scratch directory is disk-backed",
          os.path.isdir(scratch) and not WC._is_ram_backed(scratch), scratch)

    # ── C1b — the detector's REAL guarantee, re-derived ─────────────────
    # 🔴 THIS ASSERTED THAT AN UNKNOWN PATH READS AS RAM, AND IT DOES NOT — a
    # path under `/` resolves to `/`'s filesystem, which is disk, and saying so
    # is correct rather than a failure. The claim was in the code's docstring
    # too; the test caught the DOCSTRING, which is the good direction for that
    # to go. What the code actually guarantees is the case that matters: if
    # /proc/mounts is unreadable it assumes RAM, because choosing disk when
    # unsure is free and choosing RAM when unsure is the OOM being avoided.
    _real_open = open
    try:
        import builtins
        def _no_mounts(path, *a, **k):
            if str(path) == "/proc/mounts":
                raise OSError("unreadable")
            return _real_open(path, *a, **k)
        builtins.open = _no_mounts
        blind = WC._is_ram_backed(scratch)
    finally:
        builtins.open = _real_open
    check("C1b an unreadable /proc/mounts is treated as RAM-backed", blind)

    # ⚠️ AND A REAL tmpfs IS DETECTED. /dev/shm is tmpfs on every Linux this
    # fleet runs; without this C1 could pass by never detecting anything.
    check("C1c a genuine tmpfs is detected as RAM-backed",
          WC._is_ram_backed("/dev/shm") if os.path.isdir("/dev/shm") else True,
          "/dev/shm")

    # ── C2 — removed on a normal exit ───────────────────────────────────
    with WC.WarehouseCache("t") as c:
        root_ok, path = c.root, c.path
        c.conn.execute("CREATE TABLE t (a)")
        alive = os.path.isdir(root_ok)
    check("C2 the cache exists during the run and is gone after",
          alive and not os.path.isdir(root_ok))

    # ── C3 — removed when the body RAISES ───────────────────────────────
    try:
        with WC.WarehouseCache("t") as c:
            root_exc = c.root
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    check("C3 an exception still removes the cache",
          not os.path.isdir(root_exc))

    # ── C4 — removed on SIGTERM, from OUTSIDE the process ───────────────
    # 🔴 THE CASE A `finally` DOES NOT COVER. A killed report must not leave
    # gigabytes behind, and the boxes have already hit 100% disk once (r162).
    prog = ("import sys,time;sys.path.insert(0,%r);"
            "import warehouse_cache as W;c=W.WarehouseCache('kill');"
            "print(c.root,flush=True);time.sleep(30)" % _root)
    p = subprocess.Popen([sys.executable, "-c", prog],
                         stdout=subprocess.PIPE, text=True)
    root_kill = p.stdout.readline().strip()
    made = os.path.isdir(root_kill)
    p.send_signal(signal.SIGTERM)
    p.wait(timeout=15)
    check("C4 SIGTERM removes the cache",
          made and not os.path.isdir(root_kill), root_kill)

    # ── C5 — the REPORT is never inside the cache ───────────────────────
    # ⚠️ THE OTHER HALF OF THE RULE. Cleanup that took the deliverable with it
    # would be worse than a leak.
    rp = WC.report_path("x.txt")
    check("C5 reports are written under reports/, not the scratch dir",
          rp.startswith(config.REPORTS_DIR) and "reports" in rp
          and not rp.startswith(scratch), rp)

    # ── C6 — the probe writes there and nowhere else ────────────────────
    src = open(os.path.join(_root, "tools", "bfly_reach_probe.py"),
               encoding="utf-8").read()
    check("C6 the probe writes via report_path and closes in a finally",
          "report_path(" in src and "finally:" in src and "cache.close()" in src)

    print()
    if _fails:
        print(f"FAILED {len(_fails)}: " + ", ".join(_fails))
        return 1
    print("test_warehouse_cache: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
