#!/usr/bin/env python3
"""
tools/scratch_purge.py  v1.2
v1.2  2026-09-23  r422 / OPS.46 — `--prune-builds` AND `--if-over`, BECAUSE THE
      THING THAT FILLS THE QUOTA LIVES WHERE THIS TOOL CORRECTLY REFUSED TO GO.
      Operator, 2026-09-23: *"Your scratchpad has a limit. We've reached it
      before. You can't get a shell when we hit it. And you take up RAM too."*
      🔴 `archive_scratch` SKIPS LIVE SESSIONS, rightly — deleting a live
      session's working files mid-task breaks it. But on 2026-09-23 the 1.4 GB
      that exhausted the quota was ENTIRELY the live session, so a timer built
      on the old behaviour would have skipped the only directory that mattered
      and logged "nothing to do". Checked before building, not after.
      📊 MEASURED: 169 MB of a 176 MB scratchpad — 96% — was six `git clone`
      directories from revisions that had ALREADY LANDED; one was 130 MB.
      🔑 A CLONE IS ALWAYS SAFE TO DELETE: its contents either came from git or
      were copied in from `stage/`, which is the payload and is never a clone.
      So `--prune-builds` keys on `.git` alone and runs INSIDE live sessions.
      There is deliberately no "is it clean" test — a build clone is dirty ON
      PURPOSE, because gates run against patched files copied into it.
      ⚠️ `--if-over MB` makes it cheap to run on a timer, and it SAYS what it
      measured and what it decided either way (§0.5).
      ⚠️ `/tmp` IS tmpfs, so every byte pruned is host RAM returned, not disk.
v1.1  2026-09-20  r404 / OPS.27 — THREE DEFECTS, ALL FOUND BY VERIFYING THE
      FIRST LIVE RUN RATHER THAN BY ACCEPTING THAT IT HAD WORKED.
      🔴 (1) IT DELETED, SILENTLY, IN THE TOOL WHOSE STATED PRINCIPLE IS THAT
      IT NEVER DOES. `dir_bytes()` summed FILE SIZES, and a directory summing
      to zero was `rmtree`d with **no log line and no tally** — so "nothing to
      do" and "I removed three directories" rendered identically. And the test
      was the wrong one: a tree of ZERO-LENGTH files has no bytes and is not
      empty (this fleet's own `data/DRILL_DISK` idiom is a zero-byte
      sentinel). The question is now "does it contain any FILE at all", a
      directory with files is ARCHIVED whatever they weigh, and a genuinely
      empty one is removed **with a line and a count**.
      🔴 (2) `HANDOFF_DIRS` WAS A CONSTANT WITH NO OVERRIDE, so every check in
      `check_scratch_purge` that invoked this tool for real swept the LIVE
      `handoffs/` directory — a gate mutating production, and it runs inside
      the land gate on every delivery. `CLAUDE_HANDOFF_DIR` now overrides it
      and P14/P15 pin both halves.
      🔴 (3) THE RUN LEFT NO DURABLE RECORD (§38.5). Output went to the
      hand-off pane's stdout and scrolled away, so what the first live purge
      did had to be reconstructed from surviving artefacts. It now appends to
      `logs/scratch_purge.log`, ET-stamped.
v1.0  2026-09-20  r401 / OPS.27 — ARCHIVE STALE CLAUDE SCRATCH AT THE HAND-OFF
      BOUNDARY, BECAUSE A FULL /tmp QUOTA SILENTLY KILLS THE Bash TOOL.

🔴 WHAT THIS EXISTS TO PREVENT, MEASURED 2026-09-20 ON CONTROL.
`/tmp` is tmpfs mounted `usrquota`. Claude Code writes every Bash command's
stdout and stderr under `/tmp/claude-<uid>/<project>/<session>/`, and two
build-heavy sessions had accumulated 1.5 GB of 1.9 GB across 57,304 files.
With the user's block quota exhausted EVERY Bash call returned **exit 1 with no
stdout and no stderr** — including `true`. Read/Write/Edit kept working because
they never spawn, so the agent looked healthy and could not run one command.
Two consecutive threads were lost to it.

⚠️ AND `df` REPORTED 384 MB FREE THE WHOLE TIME. Filesystem free space and a
user's block quota are different numbers and only one of them was binding. A
`touch` probe returned success, because `touch` consumes an inode and no
blocks — a test that could not fail (§0.4). The quota is the number that
matters here and it is the one this tool reports.

🔑 THE OPERATOR'S SPECIFICATION, 2026-09-20, AND IT IS NARROWER THAN THE FIRST
DESIGN ON PURPOSE:
    boot unit        --continue, NO purge  — in-flight work may exist
    RESUME / RESUME [other]   NO purge     — same reason
    HAND OFF (he initiates)   PURGE        — a deliberate clean break
*"The boot should always be a continue session, by design, in case critical
work was being accomplished before we restarted… A new session will always be
handled from the devtools menu, initiated by me. The new session is where the
purge of our project space needs to happen. I don't need a purge on a
--continue session."*
🔑 THE REASONING IS SOUND AND IS WHY IT IS NOT WIRED ANYWHERE ELSE: a resume
exists to preserve continuity, so it is the worst moment to remove working
artifacts. A hand-off starts from the durable record, so the old scratch is no
longer load-bearing.

🔴 IT ARCHIVES. IT DOES NOT DELETE. THIS IS NOT FASTIDIOUSNESS — IT IS TODAY'S
NEAR-MISS. `r401` itself (`claude_boot.py`, its unit and its gate) was BUILT
and never landed, and it lived in the scratchpad of the session that was handed
off at 17:37. Had this tool existed and deleted, r401 would have been destroyed
by the very hand-off that was meant to be a clean break, and the transcript
describes the build without containing it. The constraint that actually binds
is the 1.9 GB tmpfs QUOTA, and moving the bytes to `/` (12 GB, no quota)
relieves it completely. [[S3.13]] is the same lesson at fleet scale: this
project deleted 492,945 objects once on a reading that was wrong.

⚠️ `*.md` IN `handoffs/` IS NEVER TOUCHED, AND THE REASON IS SPECIFIC.
That folder mixes two kinds of file: 8 generated `handoff.XXXXXX` stubs from
`mktemp`, and 13 HAND-AUTHORED documents — including `saturday_2026-09-19.md`
(87 KB) and `saturday_2026-09-20.md` (48 KB), which are the SAT.1 deep-dive
deliverables. `handoffs/` is gitignored (`.gitignore:100`, zero tracked files)
and those briefs exist NOWHERE ELSE on the box — verified by a `find` over
`$HOME`. A blanket purge of the folder destroys the only copy. So the match is
the GENERATOR'S OWN PATTERN and nothing else, which is §20's rule exactly:
key on the shape of the thing, never on the folder it sits in.

⚠️ IT NEVER EXITS NON-ZERO. This runs immediately before `claude` in the
hand-off pane's command string. A purge that fails must not be able to stop the
agent from starting — the worst case is the behaviour the box already had.
Same reasoning as `claude_boot.py`'s B7.

Run:  python3 tools/scratch_purge.py              # archive + retention sweep
      python3 tools/scratch_purge.py --dry-run    # report, change nothing
      python3 tools/scratch_purge.py --wait 20    # settle window, seconds
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time

HOME = os.path.expanduser("~")
UID = os.getuid()
_DTP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 🔴 THE ONE ET DEFINITION, IMPORTED (dtp r287/TZ.1), AND GUARDED BECAUSE THIS
# TOOL MAY NOT FAIL. The house shim `tools/shadow_watch.py` uses, with a
# try/except because a raise here would stop the agent starting — which is the
# one thing this file promises it cannot do.
sys.path.insert(0, _DTP)
try:
    import ettime as _ettime                                    # noqa: E402
except Exception:                                               # noqa: BLE001
    _ettime = None
SCRATCH_ROOT = os.environ.get("CLAUDE_SCRATCH_ROOT", f"/tmp/claude-{UID}")
ARCHIVE = os.environ.get("CLAUDE_SCRATCH_ARCHIVE",
                         os.path.join(HOME, "claude_scratch_archive"))
RETENTION_DAYS = int(os.environ.get("CLAUDE_SCRATCH_RETENTION_DAYS", "14"))
# Generated hand-off stubs to keep regardless of age. The newest is the one the
# session being launched is about to READ BY PATH, so removing it hands the new
# thread a dangling reference — the failure mi_handoff_fresh_claude's own
# comment records from its first cut.
HANDOFF_KEEP = int(os.environ.get("CLAUDE_HANDOFF_KEEP", "3"))

# ── 🔴 r422 / OPS.46 — BUILD CLONES ARE THE GROWTH, AND THEY LIVE INSIDE THE
# LIVE SESSION WHERE `archive_scratch` CORRECTLY REFUSES TO GO.
# Measured 2026-09-23 on this box: 169 MB of a 176 MB scratchpad — 96% — was
# six `git clone` directories from revisions that had already landed. One was
# 130 MB. On 2026-09-23 the same accumulation reached ~1.4 GB and a clone
# failed with `Disk quota exceeded` while `df` still showed 540 MB free: the
# filesystem had room and the USER did not, so no shell, no clone, no land.
# 🔑 A CLONE IS THE ONE THING HERE THAT IS ALWAYS SAFE TO DELETE. Everything in
# it either came from git (reconstructible in seconds) or was copied IN from
# `stage/`, which is the payload and is never a clone. So the rule keys on the
# presence of `.git` and nothing else — no "is it clean" test, because a build
# clone is DELIBERATELY dirty (gates run against patched files copied into it).
# ⚠️ AND IT RESPECTS A GRACE WINDOW, because an in-flight build is a clone too.
BUILD_GRACE_MIN = int(os.environ.get("CLAUDE_BUILD_GRACE_MIN", "120"))
# ⚠️ SIX, NOT FOUR, AND THE DRY RUN IS WHY. The real layout is
#   <root>/<project>/<session>/scratchpad/<rev>/<clone>
# which puts a build clone at DEPTH 5. The first cut capped the walk at 4 and
# reported "no build clones found" against a scratchpad holding six of them —
# a confident zero, which is the worst kind. Found by running it against the
# live tree rather than reasoning about the path.
BUILD_SCAN_DEPTH = int(os.environ.get("CLAUDE_BUILD_SCAN_DEPTH", "6"))
_VERSION = "v1.2"
HANDOFF_DIRS = [os.environ.get(
    "CLAUDE_HANDOFF_DIR", os.path.join(HOME, "options-trader-v4", "handoffs"))]
# A directory younger than this is left alone even when nothing holds it open —
# a session can exist for a moment before it opens its first file.
GRACE_SEC = int(os.environ.get("CLAUDE_SCRATCH_GRACE_SEC", "600"))
# 🔴 v1.1 — OVERRIDABLE, AND IT WAS NOT. Until now this was a bare constant,
# so every `check_scratch_purge` case that ran the real tool swept the LIVE
# `handoffs/` folder: a gate mutating the thing it checks, on a path the land
# gate takes for every delivery. Eight generated stubs became three that way,
# and only the `GENERATED` pattern kept the authored documents out of it.
# ⚠️ THE DEFAULT IS UNCHANGED, so production behaviour is identical; what
# changes is that a test can point it somewhere harmless — which is what
# `check_scratch_purge` P14/P15 now require of every invocation.
LOG_PATH = os.environ.get("CLAUDE_SCRATCH_LOG",
                          os.path.join(_DTP, "logs", "scratch_purge.log"))

# A generated stub is `handoff.` plus exactly the six characters mktemp's
# XXXXXX template produces. Anything else in that folder is a human's document.
import re
GENERATED = re.compile(r"^handoff\.[A-Za-z0-9]{6}$")


def _et_stamp() -> str:
    """`YYYY-MM-DD HH:MM:SS ET`, or an HONESTLY LABELLED UTC stamp.

    Same rule as `claude_boot._et_now` and for the same reason: a time
    labelled with a zone it is not in is worse than an unlabelled one. This
    box's `/etc/localtime` is `Etc/UTC`, and the sibling tool shipped a four-
    hour error to the operator's phone by taking local time and calling it ET.
    """
    if _ettime is not None:
        try:
            return _ettime.now_et().strftime("%Y-%m-%d %H:%M:%S ET")
        except Exception:                                       # noqa: BLE001
            pass
    return time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())


def _log(msg: str) -> None:
    """Print, AND append to a durable log.

    🔴 §38.5: *"anything Claude runs unattended writes what it did, what it
    found and what it changed — to a log the operator can read after the fact,
    not only to the session that is gone when the window closes."* v1.0 printed
    to the hand-off pane's stdout and nothing else, so when the first live
    purge ran on 2026-09-20 the only way to establish what it had done was to
    infer it from what survived. **A run nobody can reconstruct is
    indistinguishable from a run that never happened**, which is the failure
    that section names.
    ⚠️ THE FILE WRITE CANNOT FAIL THE TOOL. A log is a record, not a
    prerequisite; if it cannot be written the purge still runs and the pane
    still shows the line.
    """
    line = f"  [scratch_purge] {msg}"
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(f"{_et_stamp()} {msg}\n")
    except Exception:                                           # noqa: BLE001
        pass


def _sz(n: int) -> str:
    """Bytes a human can act on.

    ⚠️ v1.0 REPORTED WHOLE MEGABYTES VIA `n // (1 << 20)`, so every directory
    under a megabyte read as `0 MB` — including the one the summary said it
    had archived. A report that renders a real quantity as zero is the
    plausible-silence class in miniature.
    """
    n = int(n)
    for unit, div in (("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)):
        if n >= div:
            return f"{n / div:.1f} {unit}"
    return f"{n} B"


def quota_state() -> str:
    """The number that actually binds, not `df`'s. Best effort and silent on
    failure — a missing `quota` binary must not colour the report."""
    try:
        out = subprocess.run(["quota", "-u", os.environ.get("USER", "ubuntu")],
                             capture_output=True, text=True, timeout=5).stdout
        for line in out.splitlines():
            if "/tmp" in line or "tmpfs" in line:
                return line.strip()
    except Exception:
        pass
    try:
        st = os.statvfs("/tmp")
        used = (st.f_blocks - st.f_bfree) * st.f_frsize
        tot = st.f_blocks * st.f_frsize
        return f"/tmp {used // (1 << 20)}M used of {tot // (1 << 20)}M (filesystem, NOT the quota)"
    except Exception:
        return "unavailable"


def live_paths() -> set:
    """Every path under SCRATCH_ROOT held open, or used as a cwd, by any
    process this user owns. Read from /proc directly: stdlib only, no lsof,
    and it cannot be fooled by a process name."""
    live = set()
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        base = f"/proc/{pid}"
        try:
            if os.stat(base).st_uid != UID:
                continue
        except OSError:
            continue
        cands = [os.path.join(base, "cwd")]
        try:
            fdd = os.path.join(base, "fd")
            cands += [os.path.join(fdd, f) for f in os.listdir(fdd)]
        except OSError:
            pass
        for c in cands:
            try:
                tgt = os.readlink(c)
            except OSError:
                continue
            if tgt.startswith(SCRATCH_ROOT):
                live.add(tgt)
    return live


def other_claude_pids() -> list:
    """Claude processes that are not us and not our ancestors."""
    mine = {os.getpid(), os.getppid()}
    out = []
    for pid in os.listdir("/proc"):
        if not pid.isdigit() or int(pid) in mine:
            continue
        try:
            if os.stat(f"/proc/{pid}").st_uid != UID:
                continue
            with open(f"/proc/{pid}/cmdline", "rb") as fh:
                cl = fh.read().decode("utf-8", "replace")
        except OSError:
            continue
        if "/.local/bin/claude" in cl or cl.startswith("claude\x00"):
            out.append(int(pid))
    return out


def wait_quiet(seconds: int) -> bool:
    """HAND OFF starts the new pane BEFORE it kills the old tmux sessions, so
    at this instant the outgoing agent may still be alive and holding the
    largest directory on the box. Poll for it to go, bounded — and say so
    rather than hang if it does not."""
    if seconds <= 0:
        return True
    deadline = time.time() + seconds
    while time.time() < deadline:
        if not other_claude_pids():
            return True
        time.sleep(0.5)
    return not other_claude_pids()


def dir_stats(path: str) -> tuple:
    """(file count, byte total).

    🔴 THE COUNT IS WHAT DECIDES WHETHER A DIRECTORY IS EMPTY, AND v1.0 USED
    THE BYTES. A tree of zero-length files sums to zero and is NOT empty — a
    sentinel file is an artefact, and this fleet's own `data/DRILL_DISK`,
    `data/NO_MIDNIGHT_HALT` and `data/FEED_MAINTENANCE` idiom is exactly that
    shape. Deciding "there is nothing here" from a byte total deletes real
    things that happen to weigh nothing.
    ⚠️ AND THE BYTES ARE STILL RETURNED, because they are what the quota
    measures and what the report is about.
    """
    files_n = total = 0
    for root, _dirs, files in os.walk(path, onerror=lambda e: None):
        for f in files:
            files_n += 1
            try:
                total += os.lstat(os.path.join(root, f)).st_size
            except OSError:
                pass
    return files_n, total


def _contained(path: str, root: str) -> bool:
    """Refuse to act on anything outside the root, resolved. A purge tool that
    can be argued into `$HOME` is worse than no purge tool."""
    rp = os.path.realpath(path)
    rr = os.path.realpath(root)
    return rp == rr or rp.startswith(rr + os.sep)


def archive_scratch(dry: bool) -> tuple:
    if not os.path.isdir(SCRATCH_ROOT):
        _log(f"no scratch root at {SCRATCH_ROOT} — nothing to do")
        return 0, 0, 0
    live = live_paths()
    now = time.time()
    moved = freed = emptied = 0
    for project in sorted(os.listdir(SCRATCH_ROOT)):
        pdir = os.path.join(SCRATCH_ROOT, project)
        if not os.path.isdir(pdir):
            continue
        for sess in sorted(os.listdir(pdir)):
            sdir = os.path.join(pdir, sess)
            if not os.path.isdir(sdir) or not _contained(sdir, SCRATCH_ROOT):
                continue
            if any(p == sdir or p.startswith(sdir + os.sep) for p in live):
                _log(f"SKIP {project}/{sess[:8]} — live (open handle)")
                continue
            try:
                age = now - os.lstat(sdir).st_mtime
            except OSError:
                continue
            if age < GRACE_SEC:
                _log(f"SKIP {project}/{sess[:8]} — modified {int(age)}s ago, inside the grace window")
                continue
            nfiles, size = dir_stats(sdir)
            # 🔴 NOT SILENT, AND NOT KEYED ON BYTES. v1.0 asked whether the
            # files summed to zero and `rmtree`d on yes, printing NOTHING and
            # counting nothing — in the one tool whose header says it archives
            # and does not delete. Two changes: the question is now whether it
            # holds any FILE at all (a zero-length file is an artefact), and
            # whatever is removed SAYS SO and is tallied. *Nothing to do* and
            # *I removed three directories* must not render identically (§0.5).
            if nfiles == 0:
                _log(f"{'WOULD REMOVE' if dry else 'REMOVE'} {project}/{sess[:8]} "
                     f"— no files at any depth, nothing to preserve")
                if not dry:
                    try:
                        shutil.rmtree(sdir)
                    except OSError as exc:
                        _log(f"  remove FAILED for {sess[:8]}: {exc}")
                        continue
                emptied += 1
                continue
            dest = os.path.join(ARCHIVE, project, sess)
            _log(f"{'WOULD ARCHIVE' if dry else 'ARCHIVE'} {project}/{sess[:8]} "
                 f"({_sz(size)} in {nfiles} file(s)) -> {dest}")
            if not dry:
                try:
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    if os.path.exists(dest):
                        dest += "." + time.strftime("%H%M%S")
                    shutil.move(sdir, dest)
                except Exception as exc:
                    _log(f"  archive FAILED for {sess[:8]}: {exc} — left in place")
                    continue
            moved += 1
            freed += size
    return moved, freed, emptied


def archive_handoffs(dry: bool) -> tuple:
    moved = freed = 0
    for hdir in HANDOFF_DIRS:
        if not os.path.isdir(hdir):
            continue
        try:
            names = [n for n in os.listdir(hdir) if GENERATED.match(n)]
        except OSError:
            continue
        # Newest first; the newest HANDOFF_KEEP survive, one of which is the
        # stub the session being launched is about to read.
        names.sort(key=lambda n: os.lstat(os.path.join(hdir, n)).st_mtime,
                   reverse=True)
        for n in names[HANDOFF_KEEP:]:
            src = os.path.join(hdir, n)
            try:
                size = os.lstat(src).st_size
            except OSError:
                continue
            dest = os.path.join(ARCHIVE, "handoffs", n)
            _log(f"{'WOULD ARCHIVE' if dry else 'ARCHIVE'} handoff {n} ({_sz(size)}) "
             f"from {hdir}")
            if not dry:
                try:
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    shutil.move(src, dest)
                except Exception as exc:
                    _log(f"  archive FAILED for {n}: {exc} — left in place")
                    continue
            moved += 1
            freed += size
    return moved, freed


def sweep_retention(dry: bool) -> int:
    """The only path in this file that DELETES, and it deletes only from the
    archive, only entries older than the retention window, and only inside
    ARCHIVE — checked, not assumed."""
    if not os.path.isdir(ARCHIVE):
        return 0
    cutoff = time.time() - RETENTION_DAYS * 86400
    dropped = 0
    for root, dirs, files in os.walk(ARCHIVE):
        if root != ARCHIVE and os.path.dirname(root) != ARCHIVE:
            continue
        for name in list(dirs) + list(files):
            p = os.path.join(root, name)
            if not _contained(p, ARCHIVE) or os.path.realpath(p) == os.path.realpath(ARCHIVE):
                continue
            try:
                if os.lstat(p).st_mtime >= cutoff:
                    continue
            except OSError:
                continue
            _log(f"{'WOULD DROP' if dry else 'DROP'} {p} — older than {RETENTION_DAYS}d")
            if not dry:
                try:
                    shutil.rmtree(p) if os.path.isdir(p) else os.unlink(p)
                except OSError as exc:
                    _log(f"  drop FAILED: {exc}")
                    continue
            dropped += 1
    return dropped


def _tombstone(path: str, size: int) -> None:
    """Leave the explanation WHERE THE DIRECTORY WAS.

    🔴 THE OPERATOR'S OBJECTION, AND IT IS THE RIGHT ONE: *"I don't want future
    agents wondering why their files are getting deleted."* A log in
    `logs/scratch_purge.log` is a durable record and it is NOT where a confused
    agent looks — it looks at the path that used to hold its build. An absence
    with no note at the scene is the plausible-silence class this project keeps
    paying for (§0.5): the tool knows exactly what happened and the person who
    needs that knowledge never meets it.
    ⚠️ SO THE NOTE GOES AT THE PATH, carries the RECREATE COMMAND, and points
    at the full log. It is a few hundred bytes standing in for hundreds of
    megabytes, and it is never itself pruned — it holds no `.git`.
    """
    try:
        with open(path + ".PRUNED.txt", "w", encoding="utf-8") as fh:
            fh.write(
                "This directory was a GIT CLONE and was removed by\n"
                "  tools/scratch_purge.py " + _VERSION + "\n"
                "at " + _et_stamp() + ", freeing " + _sz(size) + ".\n"
                "\n"
                "WHY: /tmp is a tmpfs, so scratch bytes are HOST RAM, and the\n"
                "scratch root is under a per-user quota. When that quota is hit\n"
                "nothing can be written at all — no shell, no clone, no land\n"
                "(observed 2026-09-23).\n"
                "\n"
                "NOTHING UNIQUE WAS LOST. A build clone's contents come either\n"
                "from git or from the sibling stage/ directory, which is the\n"
                "payload and is NEVER pruned. Recreate with:\n"
                "    git clone --depth 1 file:///home/ubuntu/options-trader-v4 "
                + path + "\n"
                "  (or .../day_trader_pro for the dtp half)\n"
                "\n"
                "Full record: " + LOG_PATH + "\n"
                "Delete this note freely; it is only here to answer the\n"
                "question 'where did my build directory go'.\n")
    except OSError as exc:
        _log(f"  WARN could not write tombstone for {path}: {exc}")


def prune_builds(dry: bool, grace_min: int = None) -> tuple:
    """Remove git clones under SCRATCH_ROOT. -> (removed, bytes_freed).

    Runs INSIDE live sessions on purpose — that is the whole point, because the
    live session is where build clones accumulate and it is the one
    `archive_scratch` must not touch wholesale.
    """
    grace = (BUILD_GRACE_MIN if grace_min is None else grace_min) * 60
    if not os.path.isdir(SCRATCH_ROOT):
        _log(f"no scratch root at {SCRATCH_ROOT} — no builds to prune")
        return 0, 0
    now = time.time()
    removed = freed = 0
    stack = [(SCRATCH_ROOT, 0)]
    found = []
    while stack:
        d, depth = stack.pop()
        if depth > BUILD_SCAN_DEPTH:
            continue
        try:
            entries = os.listdir(d)
        except OSError:
            continue
        if ".git" in entries:
            found.append(d)
            continue                      # do not descend into a clone
        for e in sorted(entries):
            sub = os.path.join(d, e)
            if os.path.isdir(sub) and not os.path.islink(sub):
                stack.append((sub, depth + 1))
    if not found:
        _log("no build clones found")
        return 0, 0
    for d in sorted(found):
        rel = d[len(SCRATCH_ROOT):].lstrip(os.sep)
        try:
            age = now - os.lstat(d).st_mtime
        except OSError:
            continue
        if age < grace:
            _log(f"SKIP build {rel} — touched {int(age / 60)}m ago, inside the "
                 f"{grace // 60}m grace window (may be an in-flight build)")
            continue
        _, size = dir_stats(d)
        if not _contained(d, SCRATCH_ROOT):
            _log(f"SKIP build {rel} — outside {SCRATCH_ROOT}, refusing")
            continue
        _log(f"{'WOULD PRUNE' if dry else 'PRUNE'} build {rel} {_sz(size)} "
             f"(git clone — reconstructible)")
        if not dry:
            try:
                shutil.rmtree(d)
            except OSError as exc:
                _log(f"  FAILED to remove {rel}: {exc}")
                continue
            _tombstone(d, size)
        removed += 1
        freed += size
    return removed, freed


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would move; change nothing")
    ap.add_argument("--wait", type=int, default=0,
                    help="seconds to wait for other claude processes to exit")
    ap.add_argument("--prune-builds", action="store_true",
                    help="also remove git clones under the scratch root, "
                         "INCLUDING inside live sessions (a clone is derived)")
    ap.add_argument("--if-over", type=int, default=0, metavar="MB",
                    help="do nothing unless the scratch root exceeds MB; "
                         "for a timer, so a healthy box costs one log line")
    a = ap.parse_args(argv)

    # ⚠️ THE THRESHOLD CHECK REPORTS WHAT IT MEASURED AND WHAT IT DECIDED.
    # A guard that exits silently is indistinguishable from one that never
    # ran, which is the plausible-silence class this repo keeps paying for.
    if a.if_over:
        _, cur = dir_stats(SCRATCH_ROOT)
        if cur < a.if_over * (1 << 20):
            _log(f"scratch {_sz(cur)} is under the {a.if_over} MB threshold "
                 f"— nothing to do")
            return 0
        _log(f"scratch {_sz(cur)} EXCEEDS the {a.if_over} MB threshold "
             f"— proceeding")

    _log(f"root={SCRATCH_ROOT} archive={ARCHIVE} retention={RETENTION_DAYS}d")
    _log(f"before: {quota_state()}")
    if a.wait:
        if wait_quiet(a.wait):
            _log(f"other claude processes have exited (waited up to {a.wait}s)")
        else:
            _log(f"still {len(other_claude_pids())} claude process(es) after {a.wait}s "
                 f"— their scratch is SKIPPED, not forced")

    pruned = pfreed = 0
    if a.prune_builds:
        pruned, pfreed = prune_builds(a.dry_run)

    sm, sf, se = archive_scratch(a.dry_run)
    hm, hf = archive_handoffs(a.dry_run)
    dropped = sweep_retention(a.dry_run)

    # ⚠️ THE REMOVED COUNT IS ON THE SUMMARY LINE, NOT ONLY IN THE PER-ITEM
    # LOG. v1.0's summary counted archives alone, so a run that removed
    # directories reported the same line as a run that did nothing.
    _log(f"{'would archive' if a.dry_run else 'archived'}: "
         f"{sm} scratch dir(s) {_sz(sf)}, {hm} generated handoff(s) {_sz(hf)}; "
         f"removed {se} empty scratch dir(s); "
         f"{dropped} archive entr{'y' if dropped == 1 else 'ies'} past {RETENTION_DAYS}d; "
         f"{'would prune' if a.dry_run else 'pruned'} {pruned} build clone(s) {_sz(pfreed)}")
    _log(f"handoff dir: {HANDOFF_DIRS[0]} (keep newest {HANDOFF_KEEP})")
    _log(f"log: {LOG_PATH}")
    _log(f"after:  {quota_state()}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # never able to stop the agent from starting
        print(f"  [scratch_purge] FAILED: {exc} — nothing was changed by the "
              f"failing step; the agent starts regardless", flush=True)
        sys.exit(0)
