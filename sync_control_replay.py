# day_trader_pro/sync_control_replay.py — v1.0
"""
Sync the control-side replay checkout to origin/main.

The trading fleet's ~/options-trader engine checkouts are resolved to
origin/main by wake_and_bake's BAKE stage. The control box also keeps a
SEPARATE, inert checkout at ~/options-trader-v3 that the Layer-1 replay
harness (validate_regime.sh) reads so its regime telemetry matches what the
live bots compute. BAKE deliberately never touches that path, so it drifts
out of parity until pulled by hand — this script is that hand.

Scope, on purpose:
  - Local only. Runs on control, operates on a local directory. No SSH.
  - git pull and nothing else. No venv activation, no pip install, no
    systemctl. The bot service does NOT run on control and this script
    never references it — the checkout is an inert code library, and it
    stays that way.

Exit codes: 0 = up to date / fast-forwarded cleanly; non-zero = something
needs a human (dirty tree, conflict, wrong branch, missing dir).
"""

import argparse
import subprocess
import sys
from pathlib import Path

# The control-side inert replay checkout. Real path on control, not a clone
# name — the engine fleet uses ~/options-trader; this is its read-only twin.
REPLAY_DIR = Path("/home/ubuntu/options-trader-v3")
EXPECTED_BRANCH = "main"


def _log(stage, msg):
    print(f"[{stage:<8}] {msg}", flush=True)


def _git(args, cwd):
    """Run a git command in cwd; return (rc, stdout, stderr) with text output."""
    p = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True, text=True,
    )
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def sync(repo_dir=REPLAY_DIR, allow_dirty=False):
    _log("START", f"sync control replay checkout → origin/{EXPECTED_BRANCH}")
    _log("DIR", str(repo_dir))

    # 1. The directory exists and is actually a git repo.
    if not repo_dir.is_dir():
        _log("ERROR", f"{repo_dir} does not exist — nothing to sync.")
        return 2
    rc, _, _ = _git(["rev-parse", "--is-inside-work-tree"], repo_dir)
    if rc != 0:
        _log("ERROR", f"{repo_dir} is not a git working tree.")
        return 2

    # 2. On the expected branch (parity means main; refuse to pull a detached
    #    HEAD or a stray branch into the harness silently).
    rc, branch, _ = _git(["rev-parse", "--abbrev-ref", "HEAD"], repo_dir)
    if rc != 0:
        _log("ERROR", "could not read current branch.")
        return 2
    if branch != EXPECTED_BRANCH:
        _log("ERROR", f"on '{branch}', expected '{EXPECTED_BRANCH}'. "
                      f"Not pulling — switch it by hand first.")
        return 3

    # 3. Clean working tree. This is an inert read-only checkout; local edits
    #    mean something is off, so stop rather than clobber or merge them.
    rc, dirty, _ = _git(["status", "--porcelain"], repo_dir)
    if dirty and not allow_dirty:
        _log("ERROR", "working tree has local changes — refusing to pull. "
                      "This checkout is meant to be untouched. Inspect with "
                      "`git -C {} status`, or re-run with --allow-dirty to "
                      "stash-and-pull.".format(repo_dir))
        return 4

    before_rc, before, _ = _git(["rev-parse", "HEAD"], repo_dir)

    stashed = False
    if dirty and allow_dirty:
        _log("STASH", "local changes present; stashing before pull.")
        rc, _, err = _git(["stash", "push", "-u", "-m",
                           "sync_control_replay auto-stash"], repo_dir)
        if rc != 0:
            _log("ERROR", f"stash failed: {err}")
            return 4
        stashed = True

    # 4. Fast-forward-only pull. Parity is a mirror of origin/main, never a
    #    merge commit — if it can't fast-forward, a human needs to look.
    _log("PULL", "git pull --ff-only origin main")
    rc, out, err = _git(["pull", "--ff-only", "origin", EXPECTED_BRANCH], repo_dir)
    if rc != 0:
        _log("ERROR", f"pull failed:\n{err or out}")
        if stashed:
            _log("HINT", "your stashed changes are safe: `git stash pop`.")
        return 5

    if stashed:
        _log("STASH", "restoring stashed changes: git stash pop")
        rc, _, err = _git(["stash", "pop"], repo_dir)
        if rc != 0:
            _log("WARN", f"stash pop needs attention: {err}")

    # 5. Confirm — show what moved so parity is verifiable at a glance.
    after_rc, after, _ = _git(["rev-parse", "HEAD"], repo_dir)
    _, oneline, _ = _git(["log", "--oneline", "-1"], repo_dir)

    if before == after:
        _log("DONE", f"already up to date at {after[:7]} — {oneline}")
    else:
        _, count, _ = _git(["rev-list", "--count", f"{before}..{after}"], repo_dir)
        _log("DONE", f"fast-forwarded {before[:7]} → {after[:7]} "
                     f"({count} commit(s)) — now matches origin/{EXPECTED_BRANCH}")
    _log("DONE", "control replay checkout in parity with the trading fleet.")
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="Pull the control-side inert replay checkout "
                    "(~/options-trader-v3) up to origin/main for parity with "
                    "the trading fleet. git pull only — never touches the bot "
                    "service (which does not run on control).")
    ap.add_argument("--dir", default=str(REPLAY_DIR),
                    help=f"checkout path (default: {REPLAY_DIR})")
    ap.add_argument("--allow-dirty", action="store_true",
                    help="stash local changes, pull, then pop them back")
    args = ap.parse_args()
    sys.exit(sync(Path(args.dir), allow_dirty=args.allow_dirty))


if __name__ == "__main__":
    main()
