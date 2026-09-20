#!/usr/bin/env python3
"""
tools/scratch_purge.py  v1.0
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
SCRATCH_ROOT = os.environ.get("CLAUDE_SCRATCH_ROOT", f"/tmp/claude-{UID}")
ARCHIVE = os.environ.get("CLAUDE_SCRATCH_ARCHIVE",
                         os.path.join(HOME, "claude_scratch_archive"))
RETENTION_DAYS = int(os.environ.get("CLAUDE_SCRATCH_RETENTION_DAYS", "14"))
# Generated hand-off stubs to keep regardless of age. The newest is the one the
# session being launched is about to READ BY PATH, so removing it hands the new
# thread a dangling reference — the failure mi_handoff_fresh_claude's own
# comment records from its first cut.
HANDOFF_KEEP = int(os.environ.get("CLAUDE_HANDOFF_KEEP", "3"))
HANDOFF_DIRS = [os.path.join(HOME, "options-trader-v4", "handoffs")]
# A directory younger than this is left alone even when nothing holds it open —
# a session can exist for a moment before it opens its first file.
GRACE_SEC = int(os.environ.get("CLAUDE_SCRATCH_GRACE_SEC", "600"))

# A generated stub is `handoff.` plus exactly the six characters mktemp's
# XXXXXX template produces. Anything else in that folder is a human's document.
import re
GENERATED = re.compile(r"^handoff\.[A-Za-z0-9]{6}$")


def _log(msg: str) -> None:
    print(f"  [scratch_purge] {msg}", flush=True)


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


def dir_bytes(path: str) -> int:
    total = 0
    for root, _dirs, files in os.walk(path, onerror=lambda e: None):
        for f in files:
            try:
                total += os.lstat(os.path.join(root, f)).st_size
            except OSError:
                pass
    return total


def _contained(path: str, root: str) -> bool:
    """Refuse to act on anything outside the root, resolved. A purge tool that
    can be argued into `$HOME` is worse than no purge tool."""
    rp = os.path.realpath(path)
    rr = os.path.realpath(root)
    return rp == rr or rp.startswith(rr + os.sep)


def archive_scratch(dry: bool) -> tuple:
    if not os.path.isdir(SCRATCH_ROOT):
        _log(f"no scratch root at {SCRATCH_ROOT} — nothing to do")
        return 0, 0
    live = live_paths()
    now = time.time()
    moved = freed = 0
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
            size = dir_bytes(sdir)
            if size == 0:
                if not dry:
                    try:
                        shutil.rmtree(sdir)
                    except OSError:
                        pass
                continue
            dest = os.path.join(ARCHIVE, project, sess)
            _log(f"{'WOULD ARCHIVE' if dry else 'ARCHIVE'} {project}/{sess[:8]} "
                 f"({size // (1 << 20)} MB) -> {dest}")
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
    return moved, freed


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
            _log(f"{'WOULD ARCHIVE' if dry else 'ARCHIVE'} handoff {n} ({size} B)")
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would move; change nothing")
    ap.add_argument("--wait", type=int, default=0,
                    help="seconds to wait for other claude processes to exit")
    a = ap.parse_args(argv)

    _log(f"root={SCRATCH_ROOT} archive={ARCHIVE} retention={RETENTION_DAYS}d")
    _log(f"before: {quota_state()}")
    if a.wait:
        if wait_quiet(a.wait):
            _log(f"other claude processes have exited (waited up to {a.wait}s)")
        else:
            _log(f"still {len(other_claude_pids())} claude process(es) after {a.wait}s "
                 f"— their scratch is SKIPPED, not forced")

    sm, sf = archive_scratch(a.dry_run)
    hm, hf = archive_handoffs(a.dry_run)
    dropped = sweep_retention(a.dry_run)

    _log(f"{'would archive' if a.dry_run else 'archived'}: "
         f"{sm} scratch dir(s) {sf // (1 << 20)} MB, {hm} generated handoff(s) {hf} B; "
         f"{dropped} archive entr{'y' if dropped == 1 else 'ies'} past {RETENTION_DAYS}d")
    _log(f"after:  {quota_state()}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # never able to stop the agent from starting
        print(f"  [scratch_purge] FAILED: {exc} — nothing was changed by the "
              f"failing step; the agent starts regardless", flush=True)
        sys.exit(0)
