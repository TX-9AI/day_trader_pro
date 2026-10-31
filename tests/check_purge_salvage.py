#!/usr/bin/env python3
"""
tests/check_purge_salvage.py  v1.0
v1.0  2026-10-31  OPS.75 — born with tools/scratch_purge.py v1.3. Born red on v1.2 at S1, S2, S3.

A BUILD CLONE'S UNCOMMITTED WORK IS SALVAGED BEFORE IT IS PRUNED. 2026-10-31 00:30-01:30 ET the
scratch-purge timer deleted five OTV5 build clones in a live session as "reconstructible"; three
held approved, tested, uncommitted fixes. Operator: "Yes".

  S1  a dirty clone (a modified tracked file + an untracked file) is pruned only after its files,
      `git diff HEAD` and base sha are archived under $ARCHIVE/builds/, and the tombstone names it
  S2  a clone whose top directory is old but which holds a file edited NOW is skipped (age is the
      newest file in the tree)
  S3  a clone whose status cannot be read is NOT deleted (no salvage, no delete)
"""
from __future__ import annotations
import glob, os, subprocess, sys, tempfile, time
import tarfile as _tarfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), "tools", "scratch_purge.py")
_res = []


def ck(name, ok, why=""):
    _res.append((name, bool(ok), why))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  {why}"))


def run(env_extra, *args):
    env = dict(os.environ)
    _iso = os.path.dirname(env_extra["CLAUDE_SCRATCH_ARCHIVE"])     # the test's own tmp
    env["CLAUDE_HANDOFF_DIR"] = os.path.join(_iso, "handoffs")      # never the real folder
    env["CLAUDE_SCRATCH_LOG"] = os.path.join(_iso, "purge.log")
    env.update(env_extra)
    return subprocess.run([sys.executable, TOOL] + list(args), env=env,
                          capture_output=True, text=True, timeout=120)


def _mk_clone(root, rel):
    """v1.4 — a REAL git clone: v1.3 reads `git status` before it prunes."""
    d = os.path.join(root, rel)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "payload.txt"), "w") as fh:
        fh.write("from git")
    g = ["git", "-C", d, "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(g[:3] + ["init", "-q"], check=True)
    subprocess.run(g + ["add", "-A"], check=True)
    subprocess.run(g + ["commit", "-qm", "base"], check=True)
    return d


def _age(path, minutes):
    """v1.4 — ages the WHOLE tree: v1.3 reads the newest file, not the top dir."""
    old = time.time() - minutes * 60
    for r, ds, fs in os.walk(path):
        for n in ds + fs:
            os.utime(os.path.join(r, n), (old, old), follow_symlinks=False)
    os.utime(path, (old, old))



# ── P23-P25 · v1.3 (OPS.75) — dirty clones are salvaged; age is the newest file ─
with tempfile.TemporaryDirectory() as tmp:
    sr = os.path.join(tmp, "scratch"); ar = os.path.join(tmp, "arch")
    proj = os.path.join(sr, "proj", "sess", "scratchpad")
    os.makedirs(proj, exist_ok=True)
    dirty = _mk_clone(proj, "b_fix")
    with open(os.path.join(dirty, "payload.txt"), "w") as fh:
        fh.write("THE APPROVED FIX")                     # a modified tracked file
    os.makedirs(os.path.join(dirty, "tests"), exist_ok=True)
    with open(os.path.join(dirty, "tests", "check_new.py"), "w") as fh:
        fh.write("print('gate')")                        # an untracked new file
    _age(dirty, 600)
    deep = _mk_clone(proj, "b_live")
    _age(deep, 600)                                      # top dir and tree old ...
    os.makedirs(os.path.join(deep, "a", "b"), exist_ok=True)
    _age(deep, 600)
    with open(os.path.join(deep, "a", "b", "edit.py"), "w") as fh:
        fh.write("x = 1")                                # ... one file edited NOW
    os.utime(os.path.join(deep, "a", "b"), (time.time() - 36000,) * 2)
    os.utime(os.path.join(deep, "a"), (time.time() - 36000,) * 2)
    os.utime(deep, (time.time() - 36000,) * 2)
    fake = os.path.join(proj, "b_fake")
    os.makedirs(os.path.join(fake, ".git"), exist_ok=True)   # not a repository
    with open(os.path.join(fake, "work.py"), "w") as fh:
        fh.write("unreadable status")
    _age(fake, 600)
    env = {"CLAUDE_SCRATCH_ROOT": sr, "CLAUDE_SCRATCH_ARCHIVE": ar,
           "CLAUDE_BUILD_GRACE_MIN": "120"}
    run(env, "--prune-builds")
    sal = sorted(glob.glob(os.path.join(ar, "builds", "*.tar.gz"))) if os.path.isdir(os.path.join(ar, "builds")) else []
    names, fix_body, patch = [], "", ""
    if sal:
        with _tarfile.open(sal[0]) as tf:
            names = tf.getnames()
            try:
                fix_body = tf.extractfile("files/payload.txt").read().decode()
                patch = tf.extractfile("SALVAGE.patch").read().decode()
            except Exception:                                    # noqa: BLE001
                pass
    tomb = open(dirty + ".PRUNED.txt").read() if os.path.exists(dirty + ".PRUNED.txt") else ""
    ck("S1", (not os.path.isdir(dirty)) and len(sal) == 1
       and "files/tests/check_new.py" in names and fix_body == "THE APPROVED FIX"
       and "THE APPROVED FIX" in patch and "HEAD" in names
       and sal[0] in tomb and "NOTHING UNIQUE WAS LOST" not in tomb,
       f"removed={not os.path.isdir(dirty)} salvages={len(sal)} names={names} "
       f"— a dirty clone's modified AND untracked files, its diff and its base sha "
       f"must be archived before the delete, and the tombstone must name the archive")
    ck("S2", os.path.isfile(os.path.join(deep, "a", "b", "edit.py")),
       "a clone whose top directory is old but which holds a file edited NOW is "
       "in flight: its age is the newest file (the 2026-10-31 'touched 119m ago')")
    ck("S3", os.path.isfile(os.path.join(fake, "work.py")),
       "a clone whose status cannot be read cannot be salvaged, so it is NOT deleted")


bad = [n for n, ok, _ in _res if not ok]
print(f"\n  {len(_res) - len(bad)}/{len(_res)} passed")
if bad:
    print("  FAILED: " + ", ".join(bad))
sys.exit(1 if bad else 0)
