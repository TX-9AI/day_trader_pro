#!/usr/bin/env python3
# day_trader_pro/tools/transcript_text.py — v1.0
# v1.0 (2026-09-20) — r410 / OPS.35. THE HANDOFF TOLD EVERY THREAD TO "EXTRACT
#   THE MESSAGE TEXT" AND GAVE IT NO MEANS, SO EVERY THREAD WROTE THIS AGAIN.
#   WORKING_AGREEMENT §25 entry 5 and the handoff both require the last
#   conversation to be read, and both warn that the raw JSONL is megabytes of
#   mostly tool output. Neither supplied a way to do it. Measured at r410 on
#   this box: 17 transcripts, the largest 14.6 MB, against 75 KB of actual
#   human/assistant text in the one that mattered — a 195:1 ratio.
#   🔑 IT IS A TOOL AND NOT A ONE-LINER IN THE HANDOFF, DELIBERATELY. The
#   first cut of this was a `python3 -c` with backslash continuations, which
#   §1 forbids outright ("NO line continuations") and which arrives mangled
#   through the menu's SSH wrapping (§2). A prescription that breaks on paste
#   is worse than none, because the reader assumes THEY got it wrong.
#   ⚠️ THE SELECTION RULE IS PART OF THE JOB. §25 records that "last" must mean
#   last SUBSTANTIVE — on 2026-09-18 the newest session by mtime held ONE TURN
#   and 2 KB, so a thread taking the newest wrongly concluded there was no
#   history. `--pick` applies that rule instead of leaving it to the reader.
"""Extract the human/assistant TEXT from a Claude Code transcript.

    python3 tools/transcript_text.py --pick          # newest SUBSTANTIVE
    python3 tools/transcript_text.py --list          # what is available
    python3 tools/transcript_text.py <file.jsonl>    # a named one
"""
import argparse
import glob
import json
import os
import sys
import time

DIR = os.path.expanduser("~/.claude/projects/-home-ubuntu-options-trader-v4")

# A transcript below this many bytes of EXTRACTED TEXT is a stub, not a
# conversation. Chosen from the measured case §25 records: the stub that cost a
# thread its history held one turn and ~2 KB of raw JSONL, which is far less
# than this once the tool output is stripped. C.44 — a constant nobody chose is
# a constant nobody can defend, so this one is named and its origin recorded.
STUB_BYTES = 8000

# A transcript touched within this window is being written RIGHT NOW, which
# on this box means it is the caller's own. Two minutes is generous: a
# handed-over thread is minutes old at most when it reads its predecessor.
LIVE_SECS = 120


def extract(path):
    """Message text only. Tool calls, tool results and thinking are dropped."""
    out = []
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError as e:
        sys.stderr.write(f"transcript_text: cannot open {path}: {e}\n")
        return ""
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue                      # a truncated tail is not fatal
            msg = d.get("message") or {}
            role = msg.get("role") or d.get("type") or "?"
            content = msg.get("content")
            if content is None:
                continue
            parts = []
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "text":
                        parts.append(b.get("text", ""))
            text = "\n".join(p for p in parts if p).strip()
            if text:
                out.append(f"### {str(role).upper()} ###\n{text}")
    return "\n\n".join(out)


def survey():
    """Every transcript with its EXTRACTED size — the number that matters."""
    rows = []
    for p in sorted(glob.glob(os.path.join(DIR, "*.jsonl")),
                    key=os.path.getmtime, reverse=True):
        rows.append((p, os.path.getsize(p), len(extract(p))))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?")
    ap.add_argument("--pick", action="store_true",
                    help="newest SUBSTANTIVE transcript, skipping stubs")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    if a.list:
        rows = survey()
        if not rows:
            print(f"NO TRANSCRIPTS FOUND under {DIR} — say so, do not assume "
                  "there is no history.")
            return 1
        print(f"{'transcript':<42}{'raw':>12}{'text':>12}  verdict")
        for p, raw, txt in rows:
            verdict = "STUB" if txt < STUB_BYTES else "substantive"
            print(f"{os.path.basename(p):<42}{raw:>12,}{txt:>12,}  {verdict}")
        return 0

    if a.pick:
        rows = survey()
        # ⚠️ SKIP THE CURRENT SESSION. The newest file is usually the thread
        # doing the reading; handing it its own transcript is a mirror, not
        # history. Identified by the live session id when the harness exports
        # it, and otherwise by being the single newest.
        # identified by the live session id when the harness exports it, and
        # otherwise by BEING ACTIVELY WRITTEN — a file touched seconds ago is
        # almost certainly the caller's.
        me = os.environ.get("CLAUDE_SESSION_ID", "")
        now = time.time()
        cand = []
        for path, raw, txt in rows:
            if txt < STUB_BYTES:
                continue
            if me and me in path:
                sys.stderr.write(
                    f"transcript_text: SKIPPING {os.path.basename(path)} — it "
                    "is this session (CLAUDE_SESSION_ID).\n")
                continue
            if not me and (now - os.path.getmtime(path)) < LIVE_SECS:
                # 🔴 SAID OUT LOUD, NEVER SKIPPED IN SILENCE (§0.5). Handing a
                # thread its own transcript is a MIRROR that reads exactly like
                # history, and it would confirm whatever the caller already
                # believes — the worst shape of wrong answer this repo finds.
                sys.stderr.write(
                    f"transcript_text: SKIPPING {os.path.basename(path)} — "
                    f"written {int(now - os.path.getmtime(path))}s ago, so it "
                    "is almost certainly THIS session. Pass it by name if you "
                    "really want it.\n")
                continue
            cand.append((path, raw, txt))
        if not cand:
            print(f"NO SUBSTANTIVE TRANSCRIPT under {DIR} "
                  f"(threshold {STUB_BYTES:,} bytes of text). "
                  "That is a finding, not an empty result.", file=sys.stderr)
            return 1
        path = cand[0][0]
        sys.stderr.write(f"transcript_text: reading {os.path.basename(path)} "
                         f"({cand[0][2]:,} bytes of text from "
                         f"{cand[0][1]:,} raw)\n")
        print(extract(path))
        return 0

    if not a.file:
        ap.print_help()
        return 2
    print(extract(a.file))
    return 0


if __name__ == "__main__":
    sys.exit(main())
