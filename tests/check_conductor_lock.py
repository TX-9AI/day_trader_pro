#!/usr/bin/env python3
"""
day_trader_pro/tests/check_conductor_lock.py — v1.0
v1.0  2026-11-23  dtp r580 / LOCK.1 — new. On 2026-11-23 a wake_and_bake run at 16:12 ET restarted 13 boxes under the
      close (16:05-16:19). eod_conductor_v2 v2.21 holds /tmp/claude-fleet.lock (the lock wake_and_bake runs under) for
      its whole real run. Nothing here touches a box or the real lock: FLEET_LOCK is pointed at a scratch file and the
      fleet is a stand-in.

  K1  the close's lock is the fleet lock: eod_conductor_v2.FLEET_LOCK == tools/study_dispatch.FLEET_LOCK ==
      /tmp/claude-fleet.lock
  K2  a real run WAITS for a holder: with the lock held elsewhere, main() does not read the fleet; once released it does
  K3  the lock is HELD while the close works (a second LOCK_NB taker is refused inside the run)
  K4  a --dry-run takes no lock (it reads the fleet with the lock held elsewhere)
  K5  nothing in the repo flock-wraps the conductor or the study dispatcher (either would wait on itself): no .sh,
      .service or .timer line holds "flock" with eod_conductor_v2 or study_dispatch on it, and the dispatcher's
      friday_studies.sh lock is its own file, not the fleet lock
BORN RED on 613fb1d (r579): eod_conductor_v2 v2.20 has no FLEET_LOCK and takes no lock.

Run:  python3 tests/check_conductor_lock.py
"""
import fcntl
import glob
import io
import os
import sys
import tempfile
import threading
import time
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
FAILS, RAN = [], []


def ck(n, ok, msg=""):
    RAN.append(n)
    print(f"  {n:<3} {'PASS' if ok else 'FAIL'}  {msg if not ok else ''}")
    if not ok:
        FAILS.append(n)


def run_main(C, argv, seen, probe_path=None):
    def fake_get_fleet(only=None):
        held = None
        if probe_path:
            fh = open(probe_path, "a")
            try:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                held = False
                fcntl.flock(fh, fcntl.LOCK_UN)
            except BlockingIOError:
                held = True
            fh.close()
        seen.append(("fleet", time.time(), held))
        return []
    C.fleet.get_fleet = fake_get_fleet
    with redirect_stdout(io.StringIO()):
        rc = C.main(argv)
    seen.append(("rc", rc))


def main():
    try:
        import eod_conductor_v2 as C
        C.FLEET_LOCK, C.take_fleet_lock  # noqa: B018
    except (ImportError, AttributeError) as e:
        print(f"  K1  FAIL  eod_conductor_v2 has no fleet lock: {e}")
        print("\nFAILED: K1")
        return 1
    import study_dispatch as D
    ck("K1", C.FLEET_LOCK == D.FLEET_LOCK == "/tmp/claude-fleet.lock",
       f"{C.FLEET_LOCK!r} vs {D.FLEET_LOCK!r}")

    real_get_fleet = C.fleet.get_fleet
    tmp = tempfile.mkdtemp(prefix="cnd_lock_")
    lock = os.path.join(tmp, "fleet.lock")
    C.FLEET_LOCK = lock
    try:
        # K2/K3: hold the lock, start a real (non-dry) run, it must wait; release, it must proceed holding the lock
        holder = open(lock, "a")
        fcntl.flock(holder, fcntl.LOCK_EX)
        seen = []
        t = threading.Thread(target=run_main, args=(C, ["x", "--only", "QQQ"], seen, lock), daemon=True)
        t.start()
        time.sleep(1.5)
        waited = not any(s[0] == "fleet" for s in seen)
        released = time.time()
        fcntl.flock(holder, fcntl.LOCK_UN)
        holder.close()
        t.join(10)
        fl = [s for s in seen if s[0] == "fleet"]
        ck("K2", waited and fl and fl[0][1] >= released,
           f"the run read the fleet while the lock was held elsewhere: {seen}")
        ck("K3", bool(fl) and fl[0][2] is True, f"the lock was not held during the run: {seen}")

        # K4: a dry run never waits on the lock
        holder = open(lock, "a")
        fcntl.flock(holder, fcntl.LOCK_EX)
        seen = []
        t = threading.Thread(target=run_main, args=(C, ["x", "--dry-run", "--only", "QQQ"], seen), daemon=True)
        t.start()
        t.join(5)
        fcntl.flock(holder, fcntl.LOCK_UN)
        holder.close()
        ck("K4", any(s[0] == "fleet" for s in seen), f"a dry run waited on the lock: {seen}")
    finally:
        C.fleet.get_fleet = real_get_fleet

    # K5: nothing wraps the conductor or the dispatcher in flock
    bad = []
    for pat in ("**/*.sh", "**/*.service", "**/*.timer"):
        for f in glob.glob(os.path.join(ROOT, pat), recursive=True):
            if "/venv/" in f or "/.git/" in f:
                continue
            for i, line in enumerate(open(f, errors="replace"), 1):
                if line.lstrip().startswith("#"):
                    continue
                if "flock" in line and ("eod_conductor_v2" in line or "study_dispatch" in line):
                    bad.append(f"{os.path.relpath(f, ROOT)}:{i}")
    fs = open(os.path.join(ROOT, "tools", "friday_studies.sh")).read()
    ck("K5", not bad and "claude-fleet.lock" not in fs, f"flock-wrapped: {bad}")

    print()
    if FAILS:
        print(f"FAILED: {' '.join(FAILS)}")
        return 1
    print(f"ALL {len(RAN)} PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
