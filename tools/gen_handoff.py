#!/usr/bin/env python3
"""
tools/gen_handoff.py  v1.3
v1.3  2026-09-18  r388 — ITEM 5: THE LAST CONVERSATION, AND THE OLDER ONES AS
      A SEARCHABLE CORPUS. Operator: *"Read our last conversation in full as
      this thread is likely a continuation of that work"*, and *"looking into
      other past threads if available is always an option for a word search or
      other reference."* WORKING_AGREEMENT §25 carries the same entry as the
      AUTHORITY; this is the pointer (§35) and must never say more than §25.
      🔑 FIFTH, AFTER THE DURABLE RECORD, ON PURPOSE. A transcript holds things
      SAID AND THEN REVERSED — r386's row retracts a finding reported
      confidently an hour earlier, after the operator had already approved it —
      so the backlog is read first and wins where the two disagree.
      ⚠️ THE ENTRY CARRIES ITS MECHANICS BECAUSE §25 HAS BEEN BITTEN BY EXACTLY
      THE OPPOSITE: it routed to a `docs/README.md` never ported to v4, for
      months. Both traps were MEASURED 2026-09-18 before the entry was written —
      the raw JSONL is 1.6-12.7 MB of mostly tool output against 1-121k tokens
      of real text, and the NEWEST session by mtime held ONE TURN and 2 KB, so a
      literal reading gets a stub and concludes there is no history.
      🔴 AND THE GENESIS COUNT IS NOW COUNTED. This file said "not all 418"
      while the ledger held 375 — a stale literal in the one document every
      fresh thread reads first, which is DOC.6 landing where it does most harm.
      `_genesis_rows()` reads the ledger and returns "?" rather than raising.
      GATE: check_handoff_item H9/H9b/H9c/H9d/H9e/H9f, born red at 28258dd.
v1.2  2026-09-12  r371 — THE HANDOFF DECLARES THE PERMISSIONS RATHER THAN
      LEAVING A FRESH THREAD TO INFER THEM. Operator: *"You are a part of this
      project, so I also want the handoff script to explicitly declare what
      your permissions are and not to assume anything not already covered."*
      🔑 THE GAP IT CLOSES WAS MEASURED, NOT IMAGINED: on 2026-09-12 a thread
      read §38, built an archive, took his yes, and only THEN discovered the
      land was refused — the harness rules OPS.2 records were not on the box.
      A permission a document describes and the machine does not hold is worse
      than an absent one, because it is discovered at the last step. So the
      block names what is granted, names that the operator always keeps
      approval of WHAT gets committed, names that the lander and its checkers
      are never bypassed, and states plainly that a grant is not a harness rule
      — if a listed command is refused, the RULE is missing and only he can add
      it. WORKING_AGREEMENT §38.9 is the authority; this is a pointer to it
      (§35), and it must never carry a rule §38.9 does not.
v1.1  2026-09-12  r370 — THE OPENING STOPS RETRACTING SOMETHING NOBODY SAID.
      Operator, on reading a generated handoff: the do-not-clone lines *"read
      like a correction or retraction. Take it out entirely. If the handoff
      doesn't mention cloning even better, so it doesn't need to be brought
      up."* The Task block now carries his exact phrase — "THIS is a
      continuation of that work." — and names the paths instead; every clone
      reference is gone from the emitted document. Pinned by check_handoff_item
      H7c (unconditional, no longer disarmable by the document) and H7d (the
      phrase, verbatim and case-sensitive).
v1.0  2026-09-12  r368 — THE HANDOFF IS A POINTER, NOT A NARRATIVE.

Emits the operator's standing intro prompt with the VOLATILE facts appended, so
a fresh Claude Code thread starts orientated instead of rebuilding context by
interrogating the box.

🔴 WHY IT POINTS RATHER THAN SUMMARISES, which is the operator's own call
(2026-09-12: *"the handoff should be a context document that points to the
working agreement and backlog"*). A generated narrative of "what we decided" is
a SECOND SOURCE OF TRUTH that begins rotting the moment BACKLOG moves, and this
project already has the rule for that — one answer per question (§35). So this
file emits POINTERS plus the handful of facts that cannot be read from a
document: what HEAD is, what the fleet is actually running, what is flagged.
Everything durable stays in the repo.

⚠️ THE READING SCOPE IS NARROWED ON PURPOSE, AND THE NUMBERS ARE WHY. Measured
2026-09-12: WORKING_AGREEMENT 87 KB (~21k tokens), BACKLOG 571 KB (~142k),
GENESIS 595 KB across 418 rows (~148k), every .md in both repos ~330k. The
prompt's own stated purpose for GENESIS is continuity — "this is a continuation
of that work" — and the RECENT TAIL serves that: the last 12 revisions are 29 KB
(~7k tokens) against 148k for the whole ledger. Older rows stay available on
demand. The agreement is still read IN FULL, because it is the contract.

⚠️ THE DOCUMENT NAMES THE PATHS AND SAYS NOTHING ABOUT CLONING, EITHER WAY.
Both repos are already on this box, so a clone would be a stale copy whose edits
go nowhere and which cannot see anything landed since the last push. That is
true, and v1.0 said it IN the handoff. The operator's read of those lines
(2026-09-12): *"it reads like a correction or retraction. Take it out entirely.
If the handoff doesn't mention cloning even better, so it doesn't need to be
brought up."* He is right that an opening which lists what not to do reads as a
correction being issued to someone who has not done anything yet. So the
POSITIVE fact stays — the repos are here, at these paths — and the prohibition
is gone. 🔑 DO NOT RE-ADD EITHER HALF: an instruction to clone would be
wrong, and a warning against cloning is the thing that was removed. The reason
lives here, where a maintainer reads it, rather than in the document the
operator reads — C.31's discipline, kept so the next editor does not restore a
line whose justification they cannot see. `check_handoff_item` H7c fails on the
word appearing in the output at all.

🔴 IT REFUSES RATHER THAN GUESSING ABOUT THE FLEET. If the fleet cannot be read
this exits NON-ZERO and says so, instead of emitting `fleet: unknown`. OPS.6 is
the precedent: a fan-out that named a wrong path returned fifteen blank fields
and printed `15/15 succeeded`, and a handoff that quietly reports an empty fleet
is that same failure in a different costume. `--no-fleet` skips the probe
deliberately and SAYS SO in the output.

Usage:
    python3 tools/gen_handoff.py                 # full, probes the fleet
    python3 tools/gen_handoff.py --no-fleet      # skip the probe, say so
    python3 tools/gen_handoff.py --genesis 20    # deeper ledger tail
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

OTV4 = os.path.expanduser("~/options-trader-v4")
DTP = os.path.expanduser("~/day_trader_pro")

# The operator's standing brief, VERBATIM. It states who this is and what the
# layering is; it is not generated and must not drift. Edit it here only when
# the operator restates it.
BRIEF = """Brief: Lone retail algo options trader "Vertigo Capital" attempting to build an
institutional grade day trading modular suite current iteration (otv4) with high
fidelity customization and expansive reporting and control functions to serve a
functioning semi-autonomous day trading platform that recognizes price action
signals and patterns on the near, medium and higher timeframe reference points to
identify opportune trade setups with some degree of certainty and scales entries
appropriately based on the quality of the setup conditions. We are using some
derived artifacts calculated from the feed (information layer) to co-inform our
trading "plans" (decision layer) that feed the strategies (execution layer)."""


def sh(args, cwd=None):
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=60)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:                                          # noqa: BLE001
        return None


def repo_line(path, name):
    head = sh(["git", "rev-parse", "--short", "HEAD"], cwd=path)
    subj = sh(["git", "log", "-1", "--format=%s"], cwd=path)
    dirty = sh(["git", "status", "--porcelain"], cwd=path)
    if head is None:
        return f"  {name:6s} {path}  — NOT A GIT REPO OR UNREADABLE"
    state = "clean" if not dirty else f"{len(dirty.splitlines())} uncommitted change(s)"
    return (f"  {name:6s} {path}\n"
            f"         HEAD {head} ({state})\n"
            f"         {(subj or '')[:96]}")


def fleet_block(skip):
    if skip:
        return ("  NOT PROBED — this handoff was generated with --no-fleet.\n"
                "  Run `python3 fleet.py list --all` before relying on any fleet claim.")
    out = sh([sys.executable, "fleet.py", "list", "--all"], cwd=DTP)
    if not out:
        return None
    rows = [l for l in out.splitlines() if l.strip()]
    running = [l for l in rows if " running" in l]
    stopped = [l for l in rows if " stopped" in l]
    tail = [l for l in rows if "/" in l and "running" in l]
    line = tail[-1] if tail else f"{len(running)}/{len(running) + len(stopped)} running"
    return f"  {line}\n  (per-box revision is NOT in this listing — see the note below)"


# ── r388 — the transcript location, named once. ─────────────────────────────
# A fresh thread cannot be told to "read the last conversation" without being
# told WHERE, which is §25's own failure mode: that section pointed at a
# `docs/README.md` that was never ported, for months, and the one rule whose job
# is to stop documents going unread was itself routing to a missing document.
TRANSCRIPTS = "~/.claude/projects/-home-ubuntu-options-trader-v4/*.jsonl"


def _genesis_rows(path: str = "/home/ubuntu/options-trader-v4/docs/GENESIS.md") -> str:
    """The ledger's real row count, COUNTED rather than remembered.

    🔴 THIS LINE USED TO BE THE LITERAL 418 AND THE LEDGER HELD 375. Nobody
    noticed because the handoff is read by a fresh thread that has no way to
    know better — which is precisely what DOC.6 is about, landing in the one
    document every new thread reads first. A hardcoded count is a claim with a
    shelf life; `wc` has none.
    Returns "?" rather than raising: the handoff must still emit if the ledger
    cannot be read, and an honest "?" beats a confident wrong number.
    """
    try:
        with open(path, encoding="utf-8") as f:
            return str(sum(1 for ln in f if ln.startswith("| **")))
    except Exception:                                           # noqa: BLE001
        return "?"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fleet", action="store_true")
    ap.add_argument("--genesis", type=int, default=12)
    a = ap.parse_args()

    fleet = fleet_block(a.no_fleet)
    if fleet is None:
        sys.stderr.write(
            "gen_handoff: REFUSING — the fleet could not be read, and a handoff that\n"
            "says 'unknown' is the OPS.6 failure in a different costume. Fix the probe\n"
            "or pass --no-fleet to state the omission deliberately.\n")
        return 2

    print(BRIEF)
    print()
    print("Task: THIS is a continuation of that work. You are running ON the control box —")
    print("both repos are already here, at the paths below.")
    print()
    print("REPOS")
    print(repo_line(OTV4, "otv4"))
    print(repo_line(DTP, "dtp"))
    print()
    print("FLEET")
    print(fleet)
    print()
    print("READ THESE, IN THIS ORDER — Rule #1: ALWAYS adhere to the WORKING AGREEMENT.")
    print("  1. docs/WORKING_AGREEMENT.md — IN FULL. It is the contract, and §0 and §38")
    print("     govern everything you are permitted to do on this box. ~21k tokens.")
    print(f"  2. docs/GENESIS.md — the LAST {a.genesis} rows (`tail -{a.genesis}`), not all {_genesis_rows()}.")
    print("     The ledger is ~148k tokens whole and ~7k at that depth, and the reason to")
    print("     read it is continuity, which the recent tail gives you. Older rows are")
    print("     there when a specific revision matters.")
    print("  3. docs/BACKLOG.md — the open work. PART 0-3 plus the open tail. It is large")
    print("     (~142k tokens) and it is the single record of what remains unresolved.")
    print("  4. docs/PLAN_SPEC.md — only when the task touches plans or levels.")
    # ── r388 — THE LAST CONVERSATION. Operator, 2026-09-18: *"Read our last
    # conversation in full as this thread is likely a continuation of that
    # work."* WORKING_AGREEMENT §25 carries the same entry as the AUTHORITY;
    # this is the pointer (§35), and it must never say more than §25 does.
    # 🔑 IT SITS AT 5, AFTER THE DURABLE RECORD, AND THAT ORDER IS LOAD-BEARING.
    # §25's own line is that anything not written in those files did not survive
    # the last thread. A transcript contains things that were SAID AND THEN
    # REVERSED — r386's own row is a retraction of a finding reported
    # confidently an hour earlier — so the backlog must be read first and wins
    # where the two disagree. Reading the chat first inverts that.
    print("  5. OUR LAST CONVERSATION — read it in full; this thread is likely a")
    print("     continuation of that work. Transcripts are on this box at")
    print(f"     {TRANSCRIPTS}")
    print("     ⚠️ READ THE TEXT, NOT THE FILE. The raw JSONL runs to megabytes and is")
    print("     mostly tool output; the human/assistant text inside it is a small")
    print("     fraction of that. Extract the message text and read that.")
    print("     ⚠️ NEWEST IS NOT ALWAYS THE RIGHT ONE. A session can be a stub — one")
    print("     has held a single turn — so taking the newest by mtime can read a")
    print("     couple of KB, find nothing, and wrongly conclude there is no history.")
    print("     Take the newest SUBSTANTIVE transcript.")
    print("     🔑 THE OLDER THREADS ARE SEARCHABLE — a different mode. Only the last")
    print("     one is READ; the rest are there to be SEARCHED when a question needs")
    print("     an origin (when a constant was chosen, what he actually said):")
    print(f"         grep -l \"<term>\" {TRANSCRIPTS}")
    print("     ⚠️ A transcript is evidence of what was SAID, never of what is true")
    print("     now. A quote found this way is a lead to verify against the repo.")
    print()
    print("⚠️ Anything not written in those files did not survive the last thread. If a")
    print("decision seems to be missing, it is missing — ask rather than reconstruct it.")
    print()
    # 🔴 THE PERMISSIONS ARE DECLARED, NOT INFERRED (operator, 2026-09-12).
    # WORKING_AGREEMENT §38.9 is the authority and this is a POINTER to it, in
    # his own terms — the §35 rule applies to permissions exactly as it does to
    # anything else, so this block must never grow a rule §38.9 does not carry.
    print("YOUR PERMISSIONS — DECLARED. Assume NOTHING beyond this list.")
    print("WORKING_AGREEMENT §38.9 is the authority; this is the short form.")
    print("  YOURS, no asking:")
    print("    · The FLEET. Bring boxes up and down, run commands, bake, start,")
    print("      stop and restart services — via fleet.py and its flags (--only,")
    print("      etc.), ec2ops.py and wake_and_bake.py.")
    print("    · S3 from control: studies, reports, comparisons, any read.")
    print("    · The COMMIT and the BAKE, once he has approved the contents —")
    print("      timed whenever it makes the most sense to synch everything.")
    print("    · Adding CHECKERS to the land sequence when a need is unmet.")
    print("  HIS, always:")
    print("    · WHAT GETS COMMITTED. You describe the file changes; that")
    print("      description is what he approves, BEFORE the land. Quote:")
    print("      \"I always retain approval over the land — you're responsible")
    print("      for the rest.\"")
    print("  NEVER:")
    print("    · Bypassing the landing script or the checkers. They exist for")
    print("      our protection. Add to them; do not go around them.")
    print("  ⚠️ A GRANT IS NOT A HARNESS RULE. These are the operator's terms;")
    print("     Claude Code enforces its own permission rules separately, from")
    print("     ~/.claude/settings.json. If a command ON this list is refused,")
    print("     the RULE is missing — say so and let him add it. Never grant")
    print("     yourself one: that is refused as self-modification, correctly.")
    print("  ⚠️ MORE WILL BE ADDED as new situations need them. Absent from this")
    print("     list means NOT GRANTED YET, not forbidden forever — ask.")
    print()
    # 🔴 OPEN IS THE STATUS COLUMN, NOT THE SEVERITY MARKER, and the first draft
    # of this got it wrong: it filtered on 🔴 and listed a dozen LONG-CLOSED rows
    # as outstanding work. 🔴 grades how bad a thing is; the third column carries
    # ⬜ for open and a revision number for done. A handoff that reports finished
    # work as open is the manufactured-answer failure this file exists to avoid.
    rows = open(os.path.join(OTV4, "docs", "BACKLOG.md"), encoding="utf-8").read()
    openrows = []
    for ln in rows.splitlines():
        if not ln.startswith("| **"):
            continue
        cols = ln.split("|")
        if len(cols) > 3 and "⬜" in cols[3]:
            openrows.append((cols[1].strip().strip("*"), cols[2].strip()))
    print(f"OPEN ROWS — {len(openrows)} carrying ⬜ in the status column")
    print("  The newest are listed; the rest are in BACKLOG. This is a POINTER, not a")
    print("  substitute for reading it.")
    for rid, title in openrows[:14]:
        clean = title.replace("**", "").replace("🔴", "").replace("⚠️", "")
        clean = clean.replace("🔑", "").replace("⬜", "").strip()
        print(f"  {rid:9s} {clean[:104]}")
    if not openrows:
        print("  (none found — verify by hand; an empty list is more likely a parse")
        print("   failure than a finished backlog)")
    print()
    print("Change nothing until you have read the agreement.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
