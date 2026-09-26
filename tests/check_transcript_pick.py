#!/usr/bin/env python3
"""tests/check_transcript_pick.py — v1.0
`transcript_text.py --pick` HANDS A NEW THREAD ITS PREDECESSOR, NOT ITSELF AND NOT AN OLDER ONE.

v1.0  2026-09-26 — r446. `--pick` identified the caller's own session from
      CLAUDE_SESSION_ID, a variable the harness does not export — it exports
      CLAUDE_CODE_SESSION_ID (measured on control 2026-09-26: set, and equal to
      the caller's transcript id; CLAUDE_SESSION_ID unset). So identification
      ALWAYS fell through to "a file written in the last 120s is me". A handoff
      launches the next thread seconds after the previous one's last write, so
      on the first real handoff after r410 it skipped the previous thread
      (32460a16, 1.0 MB of text) as "almost certainly THIS session" and handed
      the new thread an 11 KB Saturday-brief session as its history.

  P1  id exported, predecessor written 5s ago  -> picks the PREDECESSOR (the defect)
  P2  id exported, caller already substantive  -> never picks the caller
  P3  id exported, skip names the id reason    -> said out loud, not silent (§0.5)
  P4  NO id exported                           -> the 120s guess still applies (control)
  P5  legacy CLAUDE_SESSION_ID still honoured  -> regression guard

Fixtures are built in the REAL transcript shape (type / message.role /
message.content as str or list of text blocks — read from a live transcript on
2026-09-26), in a scratch HOME, so the tool's own `~/.claude/projects` resolves
there and no real transcript is read or touched. The tool runs as a CHILD with
an explicit environment: no inherited CLAUDE_* variable can supply the answer.

Run:  cd ~/day_trader_pro && python3 tests/check_transcript_pick.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tools", "transcript_text.py")
PROJ = ".claude/projects/-home-ubuntu-options-trader-v4"
PROBLEMS: list[str] = []


def ck(tag, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {tag}" + (f"  — {detail}" if detail else ""))
    if not ok:
        PROBLEMS.append(tag)


def transcript(path, marker, nbytes, age_s):
    """A transcript in the real line shape, carrying `marker` so a pick can be
    identified by CONTENT, not by the file name the tool may echo."""
    lines = [
        {"type": "queue-operation", "operation": "enqueue", "sessionId": "x"},
        {"type": "user", "message": {"role": "user", "content": f"marker {marker}"}},
    ]
    filler = "x" * 200
    while sum(len(json.dumps(l)) for l in lines) < nbytes:
        lines.append({"type": "assistant", "message": {
            "role": "assistant", "content": [{"type": "text", "text": filler}]}})
    with open(path, "w") as fh:
        for l in lines:
            fh.write(json.dumps(l) + "\n")
    t = time.time() - age_s
    os.utime(path, (t, t))


def run(home, env_extra):
    env = {"HOME": home, "PATH": os.environ.get("PATH", "/usr/bin:/bin")}
    env.update(env_extra)          # NOTHING inherited: no CLAUDE_* can leak in
    p = subprocess.run([sys.executable, TOOL, "--pick"], capture_output=True,
                       text=True, env=env, timeout=60)
    return p.returncode, p.stdout, p.stderr


def scenario(self_bytes):
    home = tempfile.mkdtemp(prefix="check_transcript_pick_")
    d = os.path.join(home, PROJ)
    os.makedirs(d)
    transcript(os.path.join(d, "SELF0000-aaaa.jsonl"), "SELF", self_bytes, 1)
    transcript(os.path.join(d, "PREV1111-bbbb.jsonl"), "PREV", 40000, 5)
    transcript(os.path.join(d, "OLD22222-cccc.jsonl"), "OLD", 40000, 86400)
    return home


def picked(out):
    for m in ("SELF", "PREV", "OLD"):
        if f"marker {m}" in out:
            return m
    return "NONE"


def main():
    print("check_transcript_pick")
    # P1 — the defect: fresh caller (a stub), predecessor written seconds ago
    home = scenario(self_bytes=300)
    rc, out, err = run(home, {"CLAUDE_CODE_SESSION_ID": "SELF0000-aaaa"})
    ck("P1", picked(out) == "PREV",
       f"picked {picked(out)} (want PREV); stderr: {err.strip()[:160]}")

    # P2 — a caller late in its life is itself substantive and newest
    home = scenario(self_bytes=40000)
    rc, out, err = run(home, {"CLAUDE_CODE_SESSION_ID": "SELF0000-aaaa"})
    ck("P2", picked(out) == "PREV", f"picked {picked(out)} (want PREV)")

    # P3 — the skip of the caller is announced, and names WHY
    ck("P3", "SELF0000-aaaa" in err and "CLAUDE_CODE_SESSION_ID" in err,
       f"stderr: {err.strip()[:200]}")

    # P4 — control: no id at all, the mtime guess is the only thing left
    home = scenario(self_bytes=40000)
    rc, out, err = run(home, {})
    ck("P4", picked(out) == "OLD" and "SKIPPING" in err,
       f"picked {picked(out)} (want OLD, the guess skipping both fresh files)")

    # P5 — regression guard: the legacy variable still identifies the caller
    home = scenario(self_bytes=300)
    rc, out, err = run(home, {"CLAUDE_SESSION_ID": "SELF0000-aaaa"})
    ck("P5", picked(out) == "PREV", f"picked {picked(out)} (want PREV)")

    print("GREEN" if not PROBLEMS else f"RED — {len(PROBLEMS)} failed: {', '.join(PROBLEMS)}")
    return 1 if PROBLEMS else 0


if __name__ == "__main__":
    sys.exit(main())
