#!/usr/bin/env python3
"""
day_trader_pro/tests/check_cache_scratch_sweep.py  v1.0
v1.0  2026-10-25  S3.29 — SCRATCH A SIGKILLED RUN LEFT IS RECLAIMED BY THE NEXT RUN, AND NOTHING ELSE IS.

  K1  a REAL SIGKILL: a child opens a WarehouseCache and is killed -9; its scratch survives the kill;
      aged past the window, the next WarehouseCache() in another process removes it
  K2  the pre-v1.9 shape (a directory holding only cache.db*, the 2026-09-02 450 MB leak) aged -> removed
  K3  an orphan inside the window (it may be a live run) -> kept
  K4  an aged scratch whose marker pid is ALIVE -> kept
  K5  foreign directories in the root, aged (a file of someone else's, an empty dir, cache.db beside another
      file, a symlink) -> all kept
  K6  each removal is named on stderr
  K7  the new cache still works and still removes its OWN directory on close
  K8  DTP_CACHE_SWEEP=0 sweeps nothing

DTP_CACHE_DIR points at a fresh DISK-backed temp root under this repo's var/, or /var/tmp when var/ is tmpfs
(a scratch clone under /tmp), each a NEW subdirectory only this gate uses (a tmpfs root such as /tmp is
skipped by choose_scratch, which would put the run in /var/tmp), and K0 REFUSES to run anything unless the module
really resolves to that root - so the operator's var/ and /var/tmp are never swept by this gate.

  K0  isolation: warehouse_cache.choose_scratch() under the gate's env IS the temp root (else nothing runs)

BORN RED on dtp 4fec59e: K1 K2 K6
"""
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILS = []
OLD = time.time() - 3 * 86400


def check(name, ok, detail=""):
    print("  {:<3} {}  {}".format(name, "PASS" if ok else "FAIL", detail))
    if not ok:
        FAILS.append(name)


def age(path):
    for dp, dn, fn in os.walk(path):
        for f in fn:
            os.utime(os.path.join(dp, f), (OLD, OLD))
    os.utime(path, (OLD, OLD))


def mk(root, name, files, aged=True):
    p = os.path.join(root, name)
    os.makedirs(p)
    for f, body in files.items():
        open(os.path.join(p, f), "w").write(body)
    if aged:
        age(p)
    return p


CHILD_OPEN = ("import sys,time; sys.path.insert(0, %r); import warehouse_cache as W; c = W.WarehouseCache('bflystudy'); "
              "c.conn.execute('create table t(x)'); c.conn.commit(); print(c.root, flush=True); time.sleep(60)" % ROOT)
CHILD_NEW = ("import sys; sys.path.insert(0, %r); import warehouse_cache as W\n"
             "with W.WarehouseCache('next') as c:\n"
             "    c.conn.execute('create table t(x)'); r = c.root; print(r)\n"
             "import os; print('GONE' if not os.path.exists(r) else 'LEFT')\n" % ROOT)


def main():
    os.makedirs(os.path.join(ROOT, "var"), exist_ok=True)
    base = next((c for c in (os.path.join(ROOT, "var"), "/var/tmp")
                 if subprocess.run(["findmnt", "-n", "-o", "FSTYPE", "-T", c], capture_output=True,
                                   text=True).stdout.strip() not in ("tmpfs", "ramfs", "")), None)
    if base is None:
        print("REFUSED: no disk-backed base for the temp root; nothing was run.")
        return 1
    root = tempfile.mkdtemp(prefix="cachesweep_", dir=base)
    env = dict(os.environ, DTP_CACHE_DIR=root)
    env.pop("DTP_CACHE_SWEEP", None)
    try:
        return _run(root, env)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _run(root, env):
    iso = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, %r); import warehouse_cache as W; "
                          "print(W.choose_scratch())" % ROOT], env=env, capture_output=True, text=True, timeout=60)
    isolated = iso.stdout.strip() == root
    check("K0", isolated, "choose_scratch()={!r} root={!r}".format(iso.stdout.strip(), root))
    if not isolated:
        print("\nREFUSED: the gate cannot isolate the scratch root; nothing was run.")
        return 1

    ch = subprocess.Popen([sys.executable, "-c", CHILD_OPEN], env=env, stdout=subprocess.PIPE, text=True)
    killed = ch.stdout.readline().strip()
    os.kill(ch.pid, signal.SIGKILL)
    ch.wait(timeout=30)
    survived = bool(killed) and os.path.isdir(killed)
    if survived:
        age(killed)

    legacy = mk(root, "sweepfx_p_1j2k5z", {"cache.db": "x" * 100, "cache.db-journal": ""})
    fresh = mk(root, "wh_fresh123", {"cache.db": "x"}, aged=False)
    live = mk(root, "wh_live1234", {".warehouse_cache": "%d\n" % os.getpid(), "cache.db": "x"})
    foreign = [mk(root, "cf_00fz3ji5", {"hunt_stop.jsonl": "{}"}), mk(root, "cf_empty", {}),
               mk(root, "wh_mixed12", {"cache.db": "x", "notes.txt": "keep"})]
    link = os.path.join(root, "wh_link")
    os.symlink(legacy if os.path.isdir(legacy) else root, link)

    off = subprocess.run([sys.executable, "-c", CHILD_NEW], env=dict(env, DTP_CACHE_SWEEP="0"),
                         capture_output=True, text=True, timeout=120)
    k8 = os.path.isdir(legacy) and survived and os.path.isdir(killed)

    p = subprocess.run([sys.executable, "-c", CHILD_NEW], env=env, capture_output=True, text=True, timeout=120)
    check("K1", survived and not os.path.exists(killed),
          "SIGKILLed scratch {} survived the kill={} gone after the next run={}".format(
              os.path.basename(killed), survived, not os.path.exists(killed)))
    check("K2", not os.path.exists(legacy), "pre-v1.9 cache.db-only dir removed={}".format(not os.path.exists(legacy)))
    check("K3", os.path.isdir(fresh), "fresh orphan kept={}".format(os.path.isdir(fresh)))
    check("K4", os.path.isdir(live), "live-pid scratch kept={}".format(os.path.isdir(live)))
    check("K5", all(os.path.isdir(f) for f in foreign) and os.path.islink(link),
          "foreign kept={} symlink kept={}".format([os.path.isdir(f) for f in foreign], os.path.islink(link)))
    check("K6", killed and killed in p.stderr and legacy in p.stderr, "stderr={!r}".format(p.stderr.strip()[-160:]))
    check("K7", p.returncode == 0 and p.stdout.strip().endswith("GONE"), "rc={} out={!r}".format(p.returncode, p.stdout.strip()[-40:]))
    check("K8", k8 and off.returncode == 0, "DTP_CACHE_SWEEP=0 left the orphans={} rc={}".format(k8, off.returncode))

    print("")
    if FAILS:
        print("FAILED: {}".format(", ".join(FAILS)))
        return 1
    print("ALL PASS (8)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
