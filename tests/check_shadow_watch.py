#!/usr/bin/env python3
"""
day_trader_pro/tests/check_shadow_watch.py  v1.0
v1.0  2026-09-10  dtp r329 / SHD.3 — the land gate for the shadow guard.

🔴 WHAT IT CATCHES. v1.0's remote line interpolated `$OT_INSTRUMENT` into the
filename. That is a systemd `Environment=` value: it exists for the units and
NOT for the non-login shell `fleet._exec` opens, so it expanded to empty, the
path became `.../<date>/.jsonl`, and every box answered `rows=0 scored=0`.
The guard paged "the fitting corpus is empty" on 2026-09-10 while all fifteen
boxes held ~141 rows written that morning.

🔑 A BROKEN WATCHER AND A DARK BOX PRODUCED THE IDENTICAL STRING, which is why
five days of it looked like data. So this gate EXECUTES the remote line in a
real shell against a fixture tree — a grep of the source would have passed
against v1.0 too.

  W1  the remote line names no shell variable the units own (`OT_INSTRUMENT`)
  W2  executed against a fixture: file, rows and scored all parse correctly
  W3  `scored` counts only rows whose `scores` array is NOT empty
  W4  an EMPTY day directory yields `file=none`, distinct from `rows=0`
  W5  it exits 0 even when nothing matches — a non-zero exit discards stdout
      across the whole fan-out (the `grep -c` lesson, 29 boxes marked failed)
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILS = []


def check(name, ok, detail=""):
    print("  {:<4} {}  {}".format(name, "PASS" if ok else "FAIL", detail))
    if not ok:
        FAILS.append(name)


def _load():
    src = open(os.path.join(REPO, "tools", "shadow_watch.py"),
               encoding="utf-8").read()
    ns = {}
    exec(src[src.index("REMOTE = ("):src.index("def main")], {"re": re}, ns)
    return ns["REMOTE"], ns["_PAT"]


def _run(remote, home):
    env = dict(os.environ, HOME=home)
    return subprocess.run(["bash", "-c", remote], capture_output=True,
                          text=True, env=env)


def main():
    try:
        remote, pat = _load()
    except Exception as exc:                                    # noqa: BLE001
        print("  FAIL  could not load REMOTE/_PAT: {}".format(exc))
        return 1

    check("W1", "OT_INSTRUMENT" not in remote,
          "remote line references OT_INSTRUMENT" if "OT_INSTRUMENT" in remote
          else "no unit-owned variable")

    day = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    root = tempfile.mkdtemp()
    try:
        d = os.path.join(root, "options-trader", "data", "shadow", day)
        os.makedirs(d)
        with open(os.path.join(d, "NVDA.jsonl"), "w") as f:
            f.write('{"ts":"a","scores": []}\n')
            f.write('{"ts":"b","scores": [{"k":1}]}\n')
            f.write('{"ts":"c","scores": [{"k":2}]}\n')
        p = _run(remote, root)
        m = pat.search(p.stdout or "")
        check("W2", bool(m), "output: {!r}".format((p.stdout or "").strip()))
        g = m.groups() if m else ()
        if len(g) < 3:
            # ⚠️ NAMED, NOT A TRACEBACK. v1.0's _PAT captured two groups and
            # no filename at all, which is the defect — an IndexError here
            # would read as a broken checker instead of a broken guard.
            check("W3", False,
                  "_PAT captures {} group(s); file/rows/scored needs 3".format(len(g)))
        else:
            fname, rows, scored = g[0], int(g[1]), int(g[2])
            check("W3", fname == "NVDA.jsonl" and rows == 3 and scored == 2,
                  "file={} rows={} scored={}".format(fname, rows, scored))

        # W4 — an empty directory is NOT a file with no rows.
        shutil.rmtree(d)
        os.makedirs(d)
        p2 = _run(remote, root)
        m2 = pat.search(p2.stdout or "")
        check("W4", bool(m2) and len(m2.groups()) >= 3 and m2.group(1) == "none",
              "empty dir -> {!r}".format((p2.stdout or "").strip()))
        check("W5", p.returncode == 0 and p2.returncode == 0,
              "exit codes {} / {}".format(p.returncode, p2.returncode))
    finally:
        shutil.rmtree(root, ignore_errors=True)

    print("")
    if FAILS:
        print("FAILED: {}".format(", ".join(FAILS)))
        return 1
    print("ALL PASS (5)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
