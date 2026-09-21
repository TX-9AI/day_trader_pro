#!/usr/bin/env python3
"""
tools/gen_handoff.py  v1.5
v1.5  2026-09-20  r410 — THE TURNOVER MEASURES ITSELF, AND HANDS OVER THE
      TOOLS INSTEAD OF DESCRIBING THEM. Operator, after watching a thread
      struggle through its own onboarding: *"make a point to amend the
      turnover to better serve the next agent who takes the handoff."*
      🔴 EVERY HARDCODED SIZE IN THE READING LIST HAD ROTTED, in the same
      way `_genesis_rows` records the row count rotting three lines above
      them: WORKING_AGREEMENT said ~21k against ~30k, GENESIS ~148k against
      ~188k, and BACKLOG ~142k against ~223k — a 57% understatement in the
      one figure a fresh thread uses to plan how to read the biggest
      document in the repo. All three are now MEASURED at generation time.
      🔑 THE SCHEDULED CLOCK IS NEW AND IS THE BIGGEST GAP THIS FILE HAD.
      It stated the fleet's COUNT and never what moves it, so a thread could
      not tell whether `0/15 running` was normal. Read from systemd —
      ExecStart-adjacent properties only, NEVER the Environment block (§18a).
      🔑 AND TWO PRESCRIPTIONS BECOME TOOLS. §25 told every thread to
      "extract the message text" and supplied no means, so every thread
      wrote its own extractor; `tools/transcript_text.py --pick` now does it
      and REFUSES to hand a thread its own live transcript. The menu is
      named with `menu_extract --inventory` rather than described, which is
      r409/DOC.27's whole lesson applied to the document that sent the
      reader to §13 in the first place.
      ⚠️ AND THE INTERPRETER SPLIT IS STATED — it has cost two revisions.

v1.4  2026-09-20  r398 — THE PERMISSIONS BLOCK CARRIES THE VETO.
Operator, 2026-09-20: "You are allowed to stage, land, edit and present
proposed changes unprompted, but I must be given the opportunity to veto
anything before the change is committed to the codebase. Once expressly
approved, you may upload it GitHub and fan it out to the fleet." The block said
his approval came BEFORE THE LAND; landing is now unprompted and THE COMMIT is
what needs his yes.
  A VETO NEEDS AN OPPORTUNITY, WHICH MEANS A WAIT, and the block says so: a
summary sent and immediately acted on has not given him the chance.
  IT ALSO CARRIES ALL FIVE ANSWERS - yes, no, yes but, no and, hold off -
because the middle two get flattened, and flattening them drops the half of his
answer that is an instruction.
  THIS IS A POINTER AND NOT A SECOND AUTHORITY, which is r371's own rule for
this block: sections 38.9 and 38.10 are the authority and this must never grow
a rule they do not carry.
  AND IT PRESERVES THE LEDGER'S SENSE OF BAKED deliberately: his `bake` means
fan it out to the fleet, which IS section 18's meaning, so a revision on origin
that no box runs stays PUSHED and never gets the tick.
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

# The three documents the reading list budgets for. Named once, so the sizes
# printed to a fresh thread are MEASURED off these paths rather than recalled
# (see `_tok`).
WA_MD = os.path.join(OTV4, "docs", "WORKING_AGREEMENT.md")
GEN_MD = os.path.join(OTV4, "docs", "GENESIS.md")
BKL_MD = os.path.join(OTV4, "docs", "BACKLOG.md")

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


def _tok(path: str) -> str:
    """A reading budget, MEASURED at generation time rather than remembered.

    🔴 THREE HARDCODED ESTIMATES SAT BESIDE `_genesis_rows` AND ALL THREE HAD
    ROTTED THE SAME WAY IT DID. Measured at r410: the WORKING_AGREEMENT line
    said ~21k and the file is ~30k; GENESIS said ~148k against ~188k; BACKLOG
    said ~142k against ~223k — a 57% understatement in the one figure a fresh
    thread uses to decide HOW to read the largest document in the repo.
    🔑 THE FUNCTION DIRECTLY ABOVE THIS ONE EXISTS FOR EXACTLY THIS DEFECT —
    its own docstring records the row count reading a literal 418 while the
    ledger held 375. The lesson was learned for the count and not applied to
    the sizes three lines away, which is C.30 (*when a rule changes, sweep its
    readers*) inside a single function.
    ⚠️ IT IS AN ESTIMATE AND SAYS SO. Bytes/4 is a heuristic, not a tokenizer;
    what matters is that it TRACKS THE FILE instead of a memory of it. An
    unreadable file returns "?" rather than raising — the handoff must still
    emit, and an honest "?" beats a confident wrong number (§0.5).
    """
    try:
        return f"~{os.path.getsize(path) // 4000}k tokens"
    except Exception:                                           # noqa: BLE001
        return "size unreadable"


def _longest_line(path: str) -> int:
    """Longest line in a file, so the handoff can warn HOW to read it.

    `BACKLOG.md` carries single lines over 13,000 characters — one table row
    is a whole revision's reasoning — so a naive full read is refused by the
    tooling and a naive `head` shows one row. The next thread should know that
    before it starts, not after three failed reads.
    """
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return max((len(ln) for ln in f), default=0)
    except Exception:                                           # noqa: BLE001
        return 0


def _timers() -> str:
    """The SCHEDULED CLOCK, read from systemd rather than described.

    🔑 THE HANDOFF NAMED THE FLEET'S STATE AND NEVER WHAT MOVES IT. A thread
    told "0/15 running" cannot tell whether that is normal, whether anything
    will wake them, or what closes the session — and for an agent whose stated
    job is wrangling the fleet that is the most load-bearing fact there is.
    Establishing it by hand at r409 took the reading of four unit files.
    ⚠️ ExecStart ONLY, NEVER THE ENVIRONMENT BLOCK (§18a). Control holds a live
    funded broker token, GitHub write on both repos and the Telegram token;
    `systemctl show -p Environment` prints all of it. This asks for the one
    property it needs.
    ⚠️ AND IT FAILS OUT LOUD. If systemd cannot be read the block SAYS SO by
    name rather than printing nothing — an absent schedule must never render
    as "there is no schedule" (§0.5).
    """
    units = ("market-brief.timer", "dtp-morning.timer",
             "dtp-eod-conductor.timer", "dtp-shadow-watch.timer",
             "dtp-eod-analysis.timer")
    out = []
    for u in units:
        try:
            st = subprocess.run(["systemctl", "is-enabled", u],
                                capture_output=True, text=True,
                                timeout=10).stdout.strip() or "unknown"
            nxt = subprocess.run(
                ["systemctl", "show", u, "-p", "NextElapseUSecRealtime",
                 "--value"], capture_output=True, text=True,
                timeout=10).stdout.strip()
        except Exception as e:                                  # noqa: BLE001
            out.append(f"  {u:<26} COULD NOT READ ({e.__class__.__name__})")
            continue
        when = nxt if nxt and nxt != "n/a" else "-"
        flag = "" if st == "enabled" else f"   <-- {st.upper()}"
        out.append(f"  {u:<26} {st:<9} next: {when}{flag}")
    if not out:
        return "  TIMERS COULD NOT BE READ — say so rather than assuming none."
    return "\n".join(out)


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
    # 🔑 r410 — WHAT MOVES THE FLEET. A thread told "0/15 running" cannot tell
    # whether that is normal or a fault, and the fleet wrangler needs the clock
    # before it needs anything else. Read from systemd, never described.
    print("THE SCHEDULED CLOCK — what runs without anyone asking (measured)")
    print(_timers())
    print("  The fleet is NORMALLY DOWN overnight and outside RTH. Down is not a")
    print("  fault. The morning unit wakes config.ALWAYS_ON + MAX_DISCRETIONARY —")
    print("  read those constants, do not assume the count.")
    print()
    print("READ THESE, IN THIS ORDER — Rule #1: ALWAYS adhere to the WORKING AGREEMENT.")
    print("  1. docs/WORKING_AGREEMENT.md — IN FULL. It is the contract, and §0 and §38")
    print(f"     govern everything you are permitted to do on this box. {_tok(WA_MD)}.")
    print(f"  2. docs/GENESIS.md — the LAST {a.genesis} rows (`tail -{a.genesis}`), not all {_genesis_rows()}.")
    print(f"     The ledger is {_tok(GEN_MD)} whole and a few thousand at that depth, and")
    print("     the reason to read it is continuity, which the recent tail gives you.")
    print("     Older rows are there when a specific revision matters.")
    print("  3. docs/BACKLOG.md — the open work. PART 0-3 plus the open tail. It is")
    print(f"     THE BIGGEST DOCUMENT HERE ({_tok(BKL_MD)}) and the single record of what")
    print("     remains unresolved.")
    print(f"     ⚠️ ITS LINES RUN TO {_longest_line(BKL_MD):,} CHARACTERS — one row is")
    print("     a whole revision's reasoning, so a plain full read is REFUSED for")
    print("     size and a `head` shows you a single row. Read it TRUNCATED, which")
    print("     gives you every row's title and status in one pass:")
    print("         awk '/^## PART 1/,/^## PART 2/' docs/BACKLOG.md | cut -c1-400")
    print("     — ANCHORED ON THE HEADINGS, never on line numbers, which move every")
    print("     time a row is filed. Then read a row in full when it is the one that")
    print("     matters.")
    print("  4. docs/PLAN_SPEC.md — only when the task touches plans or levels.")
    print("     Also: §13 for the devtools menu — 78 items, and almost anything you")
    print("     are about to hand-write already exists there. CITE ITEMS BY LABEL,")
    print("     NEVER BY NUMBER; the numbers come from a render-time counter and")
    print("     r409 found all 53 in §13 wrong. Print the live list, never trust")
    print("     prose about it:")
    print("         python3 ~/day_trader_pro/tools/menu_extract.py --inventory")
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
    print("     fraction of that. THE TOOL EXISTS — every thread used to rewrite")
    print("     it, so it is given rather than described:")
    print("         python3 ~/day_trader_pro/tools/transcript_text.py --pick")
    print("     --pick applies the SUBSTANTIVE rule below for you and skips your")
    print("     own live transcript, saying so rather than handing you a mirror.")
    print("         ... --list   what is available, raw size against TEXT size")
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
    # 🔑 r410 — THE INTERPRETER SPLIT, because it has now cost two revisions.
    # r406 scored 7/7 under the venv and 6/7 under bare python3 on ONE import,
    # and OPS.22 is the open row behind it. A thread that does not know this
    # reads a green suite as proof of something the land gate will refuse.
    print("⚠️ TWO PYTHONS, AND THEY DISAGREE — [[OPS.22]], and it has cost two")
    print("   revisions already. `/usr/bin/python3` here CANNOT resolve the legacy")
    print("   zone `US/Eastern`, so anything importing `fleet` fails under it; the")
    print("   venvs carry the tzdata pip package and work. THE LAND GATE RUNS EVERY")
    print("   CHECK UNDER BARE python3 ([[CHK.9]]), so a gate that is green in your")
    print("   shell can still refuse the land. Run new checkers BOTH ways before")
    print("   you believe them.")
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
    print("    · BUILDING AND LANDING a package — moving it OUT of the")
    print("      scratchpad and onto the file system. No asking (2026-09-20).")
    print("    · Adding CHECKERS to the land sequence when a need is unmet.")
    print("  HIS, always:")
    print("    · THE VETO, and he states it in one line: ALL CHANGES MUST BE")
    print("      APPROVED BEFORE COMMITMENT TO THE REPO AND/OR THE FLEET.")
    print("      He must be given the OPPORTUNITY to refuse any")
    print("      change before it is committed to the codebase. Quote,")
    print("      2026-09-20: \"You are allowed to stage, land, edit and")
    print("      present proposed changes unprompted, but I must be given the")
    print("      opportunity to veto anything before the change is committed")
    print("      to the codebase. Once expressly approved, you may upload it")
    print("      GitHub and fan it out to the fleet.\"")
    print("  ⚠️ A VETO NEEDS AN OPPORTUNITY, WHICH MEANS A WAIT. A summary sent")
    print("     and immediately acted on has NOT given him the chance.")
    print("  ⚠️ HIS ANSWER IS NOT BINARY: yes / no / yes but / no and / hold")
    print("     off. \"yes but\" and \"no and\" each carry an instruction in the")
    print("     half that is not the verdict — do not flatten them. \"Hold")
    print("     off\" is not a no, and the silence after it is not consent.")
    print("  ⚠️ AND THE APPROVAL EXPIRES. It attaches to the contents he was")
    print("     SHOWN; if they move, it is void and a fresh one is owed FIRST.")
    print("  ⚠️ VOCABULARY: LAND/STAGE/EDIT/PRESENT = yours, unprompted. The")
    print("     COMMIT needs his yes, and that one yes releases BOTH GitHub")
    print("     and the fleet. The fleet LIFECYCLE (up/down/commands/restart)")
    print("     is unconditional; releasing a package to it is not. §38.10.")
    print("  🔑 AND HE WORKS FROM INTENT (§39): \"I prefer to work from intent.")
    print("     Operator's intent.\" Ask him any time what he is trying to")
    print("     achieve, and ask yourself before proposing anything: is this")
    print("     in the SPIRIT of his intent? He states that intent in nearly")
    print("     every message — read for it rather than parsing the wording.")
    print("     ⚠️ It does NOT license overriding a clear instruction (§0).")
    print("  ⚠️ `✅ BAKED` in the BACKLOG status column keeps §18's meaning —")
    print("     LIVE ON THE BOXES. A revision on origin no box runs is")
    print("     ◐ PUSHED, never ✅.")
    print("  ⚠️ land.sh COMMITS AND PUSHES IN ONE ATOMIC RUN, so in practice the")
    print("     summary precedes deploy.sh. There is no --no-push mode.")
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
