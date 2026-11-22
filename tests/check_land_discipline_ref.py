#!/usr/bin/env python3
"""
day_trader_pro/tests/check_land_discipline_ref.py — v1.0
v1.0  2026-11-22  dtp r573 / LAND.13 — new (OTV5's tests/check_land_discipline_ref.py v5.0, ported, plus D7-D8 for
      dtp's shape). A STANDALONE RUN CAN CHECK THE LAST LANDED REVISION. tools/check_land_discipline.py v1.3 read --rev
      only as a ledger label and kept --against at HEAD, so `--rev HEAD` on a clean dtp tree diffed the tree against
      itself and failed BUMP "nothing differs from HEAD"; the checker sweep's bare run failed the same way. Red on r572
      at D1, D2, D3, D5, D6, D7, D8 (D4, the label control, passes on both).

DRIVEN: the target tree's own tools/check_land_discipline.py main() runs against throwaway git repos built with its own
_mkrepo() fixture (one versioned module, docs/GENESIS.md), each landed commit a bumped module plus its ledger row,
committed with the lander's subject shape "rN: ...". HOME points at a temp dir, so the shared-ledger LEDGER check
(~/options-trader-v4/docs/GENESIS.md) is absent and never decides a case here.

  D1  --rev HEAD on a landed tip resolves to its rN label, diffs against HEAD~1, and PASSES
  D2  --rev HEAD~1 (not the tip) is refused, naming the tip rule, not reported as a missing ledger row
  D3  a tip whose subject carries no rN: label is refused, naming the subject, not "no row for HEAD"
  D4  CONTROL: a plain label (--rev r2) behaves exactly as before (PASS against HEAD~1)
  D5  a bare run (no --rev) on a clean tree fails BUMP and names the --rev HEAD form
  D6  a --rev that is neither a label nor a ref is refused by name
  D7  dtp's shape (no docs/GENESIS.md in the tree): --rev HEAD on a clean landed tip PASSES (GENESIS SKIP, BUMP PASS)
  D8  dtp's shape, a REAL fault: the tip edited a versioned file without bumping it -> --rev HEAD FAILS BUMP by name
"""
import contextlib
import importlib.util
import io
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILED, RAN = [], []
os.environ["HOME"] = tempfile.mkdtemp(prefix="cld_ref_home_")


def check(name, ok, detail=""):
    RAN.append(name)
    print("  %s  %s%s" % ("PASS" if ok else "FAIL", name, ("  — " + detail) if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


_sp = importlib.util.spec_from_file_location("_cld_ref", os.path.join(ROOT, "tools", "check_land_discipline.py"))
cld = importlib.util.module_from_spec(_sp)
_sp.loader.exec_module(cld)

BUMPED = ("#!/usr/bin/env python3\n# mod.py — v1.1\n"
          "# v1.1 (2026-02-01) — the change.\n# v1.0 (2026-01-01) — born.\nX = 2\n")
UNBUMPED = ("#!/usr/bin/env python3\n# mod.py — v1.0\n# v1.0 (2026-01-01) — born.\nX = 3\n")


def git(d, *a):
    subprocess.run(["git", *a], cwd=d, check=True, capture_output=True)


def landed(d, subject, body=BUMPED, ledger=True):
    cld._mkrepo(d)
    if not ledger:                                   # dtp's shape: the tree carries no ledger of its own
        git(d, "rm", "-q", "docs/GENESIS.md")
        git(d, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "r1: no ledger here")
    open(os.path.join(d, "mod.py"), "w").write(body)
    if ledger:
        open(os.path.join(d, "docs", "GENESIS.md"), "a").write("| **r2** | the change |\n")
    git(d, "add", "-A")
    git(d, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", subject)


def run(d, *args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cld.main(["check_land_discipline.py", "--repo", d, *args])
    return rc, buf.getvalue()


print("check_land_discipline_ref")
with tempfile.TemporaryDirectory() as d:
    landed(d, "r2: r2: the change")
    rc, out = run(d, "--rev", "HEAD")
    check("D1 --rev HEAD resolves r2 and passes", rc == 0 and "resolved to r2" in out and "\nPASS" in out, out[-400:])
    rc, out = run(d, "--rev", "HEAD~1")
    check("D2 a non-tip ref is refused by the tip rule", rc == 1 and "not the tip" in out and "no row for" not in out,
          out[-300:])
    rc, out = run(d, "--rev", "r2", "--against", "HEAD~1")
    check("D4 CONTROL: a plain label behaves as before", rc == 0 and "GENESIS   PASS" in out, out[-300:])
    rc, out = run(d)
    check("D5 a bare run fails BUMP and names --rev HEAD", rc == 1 and "nothing differs" in out and "--rev HEAD" in out,
          out[-300:])
    rc, out = run(d, "--rev", "nosuchref")
    check("D6 an unknown --rev is refused by name", rc == 1 and "neither a ledger label" in out, out[-300:])

with tempfile.TemporaryDirectory() as d:
    landed(d, "a hand commit with no label")
    rc, out = run(d, "--rev", "HEAD")
    check("D3 a subject with no rN: label is refused by name", rc == 1 and "does not start with a revision label" in out
          and "no row for HEAD" not in out, out[-300:])

with tempfile.TemporaryDirectory() as d:
    landed(d, "r2: r2: dtp shape", ledger=False)
    rc, out = run(d, "--rev", "HEAD")
    check("D7 dtp's shape: --rev HEAD on a clean landed tip passes", rc == 0 and "GENESIS   SKIP" in out
          and "BUMP      PASS" in out and "resolved to r2" in out, out[-400:])

with tempfile.TemporaryDirectory() as d:
    landed(d, "r2: r2: an edit with no bump", body=UNBUMPED, ledger=False)
    rc, out = run(d, "--rev", "HEAD")
    check("D8 dtp's shape, a real fault: an unbumped edit fails BUMP", rc == 1 and "BUMP mod.py: title still v1.0" in out,
          out[-400:])

print("\n%s — %d/%d" % ("FAIL" if FAILED else "PASS", len(RAN) - len(FAILED), len(RAN)))
sys.exit(1 if FAILED else 0)
