#!/usr/bin/env python3
"""
tests/check_scratch_purge.py  v1.0
v1.0  2026-09-20  r401 / OPS.27 — GATE FOR tools/scratch_purge.py AND ITS ONE
      CALL SITE.

Plain script with an exit code, NOT a pytest file: the land gate runs every
CHECK under bare `python3` and the active venv is not guaranteed to carry
pytest ([[CHK.9]], §36's own "it was the odd one out and it was the one that
broke").

🔑 EVERY FIXTURE IS BUILT FROM THE TOOL'S OWN DECLARED CONSTANTS AND FROM THE
REAL menu SOURCE, never from this author's belief about either (§0.4). The
directory layout is driven through the tool's documented env overrides, so a
rename of a constant fails the gate instead of silently testing nothing.

BORN RED AT 2ac0313: `tools/scratch_purge.py` does not exist there, so P1–P8
fail on import and P9 fails on the launch string. Verified by running this
file against that commit before the fix — see the delivery notes.
"""
from __future__ import annotations
import os, re, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOL = os.path.join(ROOT, "tools", "scratch_purge.py")
MENU = os.path.join(ROOT, "menu_functions.sh")
BOOT = os.path.join(ROOT, "tools", "claude_boot.py")

_res = []
def ck(name, ok, why=""):
    _res.append((name, bool(ok), why))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}  {'' if ok else why}")

def run(env_extra, *args, cwd=None):
    env = dict(os.environ); env.update(env_extra)
    return subprocess.run([sys.executable, TOOL, *args], capture_output=True,
                          text=True, env=env, timeout=120, cwd=cwd)

def mkscratch(base, project, sess, size_kb=64, age_sec=4000):
    d = os.path.join(base, project, sess)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "blob.bin"), "wb") as fh:
        fh.write(b"x" * (size_kb * 1024))
    old = time.time() - age_sec
    os.utime(d, (old, old))
    return d

# ── P1 · the tool runs at all and reports ────────────────────────────────────
if not os.path.exists(TOOL):
    ck("P1", False, f"{TOOL} does not exist")
else:
    with tempfile.TemporaryDirectory() as tmp:
        sr, ar = os.path.join(tmp, "scratch"), os.path.join(tmp, "arc")
        mkscratch(sr, "proj", "aaaaaaaa-1111-2222-3333-444444444444")
        r = run({"CLAUDE_SCRATCH_ROOT": sr, "CLAUDE_SCRATCH_ARCHIVE": ar}, "--dry-run")
        ck("P1", r.returncode == 0 and "scratch_purge" in r.stdout,
           f"rc={r.returncode} out={r.stdout[:200]!r}")

# ⚠️ EVERY TOOL-DEPENDENT CHECK FAILS RATHER THAN RAISES.
# The first cut of this file CRASHED at the born-red commit — `open(TOOL)`
# raised FileNotFoundError and took P2..P11 down with it, so nothing ran and
# "born red" could not be claimed for any of them. [[r400]] records the same
# mistake earlier the same day in check_map_accuracy's R1c. A gate that
# cannot report on the broken version is not a gate.
_TOOLCHECKS = ["P2", "P3", "P3b", "P4", "P5", "P6", "P7", "P8"]

def _unrun(reason):
    done = {n for n, _, _ in _res}
    for n in _TOOLCHECKS:
        if n not in done:
            ck(n, False, reason)

if not os.path.exists(TOOL):
    _unrun(f"{TOOL} does not exist")
else:
  try:
    # ── P2 · AN AUTHORED .md IS NEVER TOUCHED ───────────────────────────────────
    # The one that matters: handoffs/ holds saturday_*.md, the SAT.1 deliverables,
    # gitignored and single-copy on this box. Mutation-provable in one line.
    with tempfile.TemporaryDirectory() as tmp:
        sr, ar, hd = (os.path.join(tmp, x) for x in ("scratch", "arc", "ho"))
        os.makedirs(hd); os.makedirs(sr)
        keep = os.path.join(hd, "saturday_2026-09-19.md")
        open(keep, "w").write("the brief")
        gens = []
        for i in range(6):
            g = os.path.join(hd, f"handoff.aBcD{i}z")
            open(g, "w").write("stub"); gens.append(g)
            t = time.time() - (10 - i) * 86400
            os.utime(g, (t, t))
        src = open(TOOL).read().replace(
            'HANDOFF_DIRS = [os.path.join(HOME, "options-trader-v4", "handoffs")]',
            f'HANDOFF_DIRS = [{hd!r}]')
        alt = os.path.join(tmp, "alt_purge.py"); open(alt, "w").write(src)
        env = dict(os.environ); env.update({"CLAUDE_SCRATCH_ROOT": sr,
                                            "CLAUDE_SCRATCH_ARCHIVE": ar})
        r = subprocess.run([sys.executable, alt], capture_output=True, text=True,
                           env=env, timeout=120)
        ck("P2", os.path.exists(keep) and open(keep).read() == "the brief",
           "an authored .md was moved or altered — the Saturday briefs are "
           "single-copy and gitignored")
        # ── P3 · generated stubs beyond KEEP archive; the newest KEEP survive ──
        surv = [g for g in gens if os.path.exists(g)]
        ck("P3", len(surv) == 3 and all(g in surv for g in gens[3:]),
           f"expected the newest 3 stubs to survive, got {[os.path.basename(g) for g in surv]}")
        ck("P3b", os.path.isdir(os.path.join(ar, "handoffs")) and
           len(os.listdir(os.path.join(ar, "handoffs"))) == 3,
           "archived stubs did not land in the archive — a purge that deletes "
           "rather than moves is what nearly cost r401")

    # ── P4 · a LIVE scratch dir is skipped ──────────────────────────────────────
    with tempfile.TemporaryDirectory() as tmp:
        sr, ar = os.path.join(tmp, "scratch"), os.path.join(tmp, "arc")
        live = mkscratch(sr, "proj", "bbbbbbbb-1111-2222-3333-444444444444")
        dead = mkscratch(sr, "proj", "cccccccc-1111-2222-3333-444444444444")
        fh = open(os.path.join(live, "blob.bin"), "rb")   # a real open handle
        try:
            r = run({"CLAUDE_SCRATCH_ROOT": sr, "CLAUDE_SCRATCH_ARCHIVE": ar})
        finally:
            fh.close()
        ck("P4", os.path.isdir(live) and not os.path.isdir(dead),
           f"live kept={os.path.isdir(live)} dead removed={not os.path.isdir(dead)} "
           f"— an open handle must protect a directory")

    # ── P5 · ARCHIVE IS A MOVE, AND THE BYTES SURVIVE ───────────────────────────
    with tempfile.TemporaryDirectory() as tmp:
        sr, ar = os.path.join(tmp, "scratch"), os.path.join(tmp, "arc")
        d = mkscratch(sr, "proj", "dddddddd-1111-2222-3333-444444444444")
        open(os.path.join(d, "unlanded_build.txt"), "w").write("r401 lived here")
        # Backdate AFTER the last write: writing into the directory resets its
        # mtime, and the grace window would then correctly skip it. The first cut
        # of this fixture did exactly that and the gate caught it (§0.4).
        _old = time.time() - 4000
        os.utime(d, (_old, _old))
        run({"CLAUDE_SCRATCH_ROOT": sr, "CLAUDE_SCRATCH_ARCHIVE": ar})
        moved = os.path.join(ar, "proj", "dddddddd-1111-2222-3333-444444444444",
                             "unlanded_build.txt")
        ck("P5", os.path.exists(moved) and open(moved).read() == "r401 lived here",
           "the payload did not survive the archive — this is the exact near-miss "
           "of 2026-09-20, where the unlanded r401 build sat in the scratchpad of "
           "the session being handed off")

    # ── P6 · retention drops ONLY what is past the window ───────────────────────
    with tempfile.TemporaryDirectory() as tmp:
        sr, ar = os.path.join(tmp, "scratch"), os.path.join(tmp, "arc")
        os.makedirs(sr)
        fresh, stale = os.path.join(ar, "proj", "fresh"), os.path.join(ar, "proj", "stale")
        os.makedirs(fresh); os.makedirs(stale)
        old = time.time() - 30 * 86400
        os.utime(stale, (old, old))
        run({"CLAUDE_SCRATCH_ROOT": sr, "CLAUDE_SCRATCH_ARCHIVE": ar,
             "CLAUDE_SCRATCH_RETENTION_DAYS": "14"})
        ck("P6", os.path.isdir(fresh) and not os.path.isdir(stale),
           f"fresh kept={os.path.isdir(fresh)} stale dropped={not os.path.isdir(stale)}")

    # ── P7 · the grace window protects a just-created directory ─────────────────
    with tempfile.TemporaryDirectory() as tmp:
        sr, ar = os.path.join(tmp, "scratch"), os.path.join(tmp, "arc")
        new = mkscratch(sr, "proj", "eeeeeeee-1111-2222-3333-444444444444", age_sec=0)
        run({"CLAUDE_SCRATCH_ROOT": sr, "CLAUDE_SCRATCH_ARCHIVE": ar,
             "CLAUDE_SCRATCH_GRACE_SEC": "600"})
        ck("P7", os.path.isdir(new),
           "a directory inside the grace window was archived — a session can exist "
           "for a moment before it opens its first file")

    # ── P8 · IT CANNOT STOP THE AGENT STARTING ──────────────────────────────────
    with tempfile.TemporaryDirectory() as tmp:
        sr = os.path.join(tmp, "scratch")
        mkscratch(sr, "proj", "ffffffff-1111-2222-3333-444444444444")
        blocked = os.path.join(tmp, "blocked")
        os.makedirs(blocked); os.chmod(blocked, 0o500)
        try:
            r = run({"CLAUDE_SCRATCH_ROOT": sr,
                     "CLAUDE_SCRATCH_ARCHIVE": os.path.join(blocked, "arc")})
            ck("P8", r.returncode == 0,
               f"rc={r.returncode} — a failing purge must never block the launch "
               f"(§0.5: it says so, but it does not stop the agent)")
        finally:
            os.chmod(blocked, 0o700)


  except Exception as _exc:
    _unrun(f"check block raised: {_exc!r}")

# ── P9 · HAND OFF calls it BEFORE claude, separated by `;` not `&&` ─────────
menu = open(MENU).read() if os.path.exists(MENU) else ""
sites = re.findall(r'"([^"]*\$CLAUDE \'Read \$HO and follow it\.\'[^"]*)"', menu)
ok9 = bool(sites) and all(
    "scratch_purge.py" in s
    and s.index("scratch_purge.py") < s.index("$CLAUDE")
    and re.search(r"scratch_purge\.py[^;&]*;", s)
    and not re.search(r"scratch_purge\.py[^;]*&&", s)
    for s in sites)
ck("P9", ok9, f"{len(sites)} HAND OFF launch site(s); each must run the purge "
              f"BEFORE claude and chain with `;` so a failure cannot stop it")

# ── P10 · RESUME AND RESUME [other] DO NOT PURGE — the operator's spec ──────
res_sites = re.findall(r'"(env -u ANTHROPIC_API_KEY \$CLAUDE --(?:continue|resume)[^"]*)"', menu)
ck("P10", bool(res_sites) and not any("scratch_purge" in s for s in res_sites),
   f"{len(res_sites)} resume launch site(s) — a --continue session must NEVER "
   f"purge: it exists to preserve continuity, which is the worst moment to "
   f"remove working artifacts")

# ── P11 · the boot raiser does not purge either ─────────────────────────────
boot = open(BOOT).read() if os.path.exists(BOOT) else ""
ck("P11", bool(boot) and "scratch_purge" not in boot,
   "the boot unit is --continue by design and must not purge")

# ── P12 · handoffs/ HOLDS GENERATED FILES ONLY — WITH A DEBT REGISTER ──────
# 🔑 IT SHIPS GREEN AND FAILS ONLY IF THE DEBT GROWS, which is [[r395]]/DISC.2's
# precedent exactly: landing this red would refuse every future delivery until
# 13 documents were rehomed, and that is how a gate gets deleted. The register
# is NAMES and not a COUNT — a pinned number rots the moment one is repaired
# ([[CHK.6]]) — and it PRINTS EVERY RUN so the debt cannot go quiet (§0.5).
#
# ⚠️ WHY THIS IS A GATE AT ALL. `handoffs/` is gitignored (.gitignore:100, zero
# tracked files), so anything AUTHORED there is untracked, single-copy and
# invisible to `check_land_discipline`. Measured 2026-09-20: 10 identifiers
# (ENT.1, FU.1, FU.2, FU.3, FU.6, FU.7, FU.8, PRE.5, SAT.2, SAT.3) exist in
# those documents and in no row of BACKLOG.md, and `saturday_2026-09-19.md`
# (87KB) exists nowhere else on the box. Authored documents belong in `docs/`;
# unresolved items belong in BACKLOG. One handoff, one backlog.
KNOWN_DEBT = {
    "ASSISTANT_PERMISSIONS.md", "HANDOFF_2026-09-11.md",
    "LEVELS_FORK_SPEC_2026-09-12.md", "OTV4TEST_ADVISORY_r383.md",
    "OVERNIGHT_2026-09-15.md", "PRE_RUN_FIXES.md", "SATURDAY_BRIEF.md",
    "SATURDAY_RUNBOOK.md", "SATURDAY_TIMER_PROPOSAL.md",
    "THREAD_CLOSE_2026-09-19.md", "THREAD_CLOSE_2026-09-20.md",
    "saturday_2026-09-19.md", "saturday_2026-09-20.md",
    # Found by this gate on its FIRST run — the author's own survey used
    # `ls -1 *.md` and did not see them. Registered as existing debt rather
    # than judged disposable: a bake log is evidence of a bake.
    "bake_r386.log", "bake_r386_noon.log",
}
_hd = os.path.join(os.path.expanduser("~"), "options-trader-v4", "handoffs")
if not os.path.isdir(_hd):
    ck("P12", True, "")
    print(f"  [P12] {_hd} absent on this machine — nothing to register")
else:
    _present = {n for n in os.listdir(_hd)
                if not re.match(r"^handoff\.[A-Za-z0-9]{6}$", n)
                and os.path.isfile(os.path.join(_hd, n))}
    _new = sorted(_present - KNOWN_DEBT)
    _fixed = sorted(KNOWN_DEBT - _present)
    print(f"  [P12] handoffs/ debt register: {len(_present & KNOWN_DEBT)} known, "
          f"{len(_fixed)} rehomed, {len(_new)} NEW")
    for _n in sorted(_present & KNOWN_DEBT):
        print(f"        debt  {_n}")
    for _n in _fixed:
        print(f"        gone  {_n}  (rehomed — remove it from KNOWN_DEBT)")
    ck("P12", not _new,
       f"NEW authored file(s) in handoffs/: {_new} — that folder is gitignored, "
       f"so an authored document there is untracked and single-copy. Put it in "
       f"docs/, or its open items in BACKLOG.md.")

# ── P13 · THE ARCHIVE CAN NEVER BE MISTAKEN FOR A CHECKOUT BY THE LANDER ───
# 🔑 RAISED BY THE OTV4TEST FORK ON REVIEW OF THIS DELIVERY, and it is a real
# hazard rather than a theoretical one: `tools/land.sh` resolves its target by
# globbing `$HOME/*/`, taking any candidate that has `.git` at its own top
# level and carries the spec's REPO markers — it takes the FIRST match and
# never reports ambiguity (§3, and r371's first cut resolved an otv4 half into
# market-brief on exactly that). We archive whole session trees that CONTAIN
# git clones — 19 of them at the time of writing — so if the archive root were
# ever a direct child of $HOME holding a clone at depth 1, the lander could
# commit into it.
# ⚠️ IT IS SAFE BY SHAPE, NOT BY LUCK: scratch_purge writes to
# <ARCHIVE>/<project>/<session>/..., so a clone is at least three levels down
# and invisible to a one-level glob. This check pins that shape, so a future
# change to ARCHIVE that flattens it fails here instead of at a land.
_arc = os.environ.get("CLAUDE_SCRATCH_ARCHIVE",
                      os.path.join(os.path.expanduser("~"), "claude_scratch_archive"))
_home = os.path.expanduser("~")
_direct_child = os.path.dirname(os.path.realpath(_arc)) == os.path.realpath(_home)
_root_is_repo = os.path.isdir(os.path.join(_arc, ".git"))
_depth1_repo = []
if os.path.isdir(_arc):
    for _n in os.listdir(_arc):
        if os.path.isdir(os.path.join(_arc, _n, ".git")):
            _depth1_repo.append(_n)
ck("P13", not _root_is_repo and not _depth1_repo,
   f"the archive root is resolvable as a checkout (root .git={_root_is_repo}, "
   f"depth-1 repos={_depth1_repo}) — land.sh globs $HOME/*/ and takes the "
   f"first match without reporting ambiguity")
print(f"  [P13] archive={_arc} direct_child_of_home={_direct_child} "
      f"root_is_repo={_root_is_repo} depth1_repos={len(_depth1_repo)}")

bad = [n for n, ok, _ in _res if not ok]
print(f"\n  {len(_res) - len(bad)}/{len(_res)} passed")
if bad:
    print(f"  FAILED: {', '.join(bad)}")
sys.exit(1 if bad else 0)
