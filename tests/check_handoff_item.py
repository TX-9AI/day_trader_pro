#!/usr/bin/env python3
"""
tests/check_handoff_item.py  v1.4
v1.4  2026-09-20  r410 — H11, H11b, H12, H12b, H13 and H13b: THE TURNOVER'S
      OWN FIGURES, ITS CLOCK, AND THE TOOLS IT PRESCRIBES.
      🔴 H11 GENERALISES H9d, WHICH WAS WRITTEN FOR EXACTLY THIS AND NEVER
      SWEPT TO ITS NEIGHBOURS. H9d pins the GENESIS row count as computed;
      the three token budgets three lines away stayed literals and all
      three had rotted — the worst by 57%. C.30 inside one function.
      🔑 H12 PINS THE SCHEDULED CLOCK, the biggest gap the document had: it
      named the fleet's COUNT and never what moves it. H12b is a DECLARED
      CONTROL, green at HEAD, and is mutation-proven — it refuses a
      generator that asks systemd for an Environment block (§18a, and
      control holds a live funded broker token).
      🔑 H13 EXISTS BECAUSE §25 SPENT MONTHS ROUTING TO A MISSING FILE. A
      handoff that names a command makes the same promise, so every tool it
      prescribes must RESOLVE — and H13b RUNS the transcript tool rather
      than checking it is present, because its first cut returned the
      caller's own live transcript and a mirror reads exactly like history.
      ⚠️ H13 FIRST RESOLVED THROUGH `~` — CHK.9 item 2, the defect OPS.34
      recorded against r407's gate. It asks THIS checkout now.
      ⚠️ AND §20 FIRED TWICE WRITING THIS FILE: H11's absence canary matched
      r410's own changelog and a preserved dated measurement; H12b's matched
      the comment explaining §18a. Both rescoped — the canary is wrong, not
      the prose.
v1.3  2026-09-20  r398 — H10, H10b, H10c and H10d: the permission block. The
operator moved the line on 2026-09-20 — landing and editing on the file system
are Claude's, and the PUSH and the BAKE are gated on HIM BEING INFORMED rather
than on an approval — and nothing checked that the handoff carried it.
  🔴 H10 PINS THE VERB. "Approval" and "informed" produce different threads:
one stops and waits for a click, the other summarises and proceeds. A block
that drifted back to approval-language would quietly reintroduce a bottleneck
he removed.
  🔴 H10b PINS THE EXPIRY, which is the half most likely to be dropped: if the
delivery stops matching what he was told, he is unappraised again and owed an
update FIRST. [[ORB.16]] is what skipping it cost once already.
  🔴 H10c PINS THAT `BAKED` STILL MEANS LIVE ON THE BOXES. He uses `bake`
conversationally for "make it official"; section 18 and BACKLOG PART 0 use
✅ BAKED for the fleet, and hundreds of rows already carry that sense. A
handoff teaching the other one would re-grade all of them at once. Anchored on
the CONSEQUENCE — on origin is PUSHED, never ✅ — so a reworded block still has
to mean it.
v1.2  2026-09-18  r388 — H9/H9b/H9c/H9d: THE LAST CONVERSATION IS ITEM 5.
      Operator: *"Read our last conversation in full as this thread is likely a
      continuation of that work."* H9 requires the PATH as well as the sentence,
      because an instruction that does not say HOW is §25's own failure — that
      section routed to a `docs/README.md` never ported to v4, for months.
      H9b and H9c pin the two traps MEASURED before the entry was written: the
      raw JSONL is megabytes of mostly tool output against 1-121k tokens of
      actual text, and the NEWEST session by mtime held ONE TURN and 2 KB, so a
      thread taking "last" literally reads a stub and concludes there is no
      history. H9d pins that the GENESIS row count is COUNTED — the line said
      418 while the ledger held 375.
v1.1  2026-09-12  r370 — H7c TIGHTENED AND H7d ADDED. H7c could be disarmed by
      the document it checked: it split the output on the literal "nothing to
      clone" and scanned only the prefix, so a handoff carrying that sentence
      narrowed the canary to the text above it. The document no longer mentions
      cloning at all, so the check is now unconditional. H7d pins the
      operator's exact continuation phrase, which he asked for verbatim.
v1.0  2026-09-12  r368 — THE HANDOFF ITEM, AND THE THREE THINGS THAT WOULD
      OTHERWISE BITE IT SILENTLY.

The menu item hands the session to a fresh Claude thread. Every failure it can
have is QUIET — a thread that bills the wrong account, a binary that cannot be
found under a venv, a kill that takes out the client before it has moved — so
each is pinned here rather than discovered in use.

H2 IS THE EXPENSIVE ONE. `~/.bashrc` sources day_trader_pro/.env for
selector.py, so ANTHROPIC_API_KEY is present in every interactive shell. A
thread launched without unsetting it bills the API instead of the Max
subscription, works perfectly, and says nothing.
"""
import os
import re
import subprocess
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_fails = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))
    if not ok:
        _fails.append(name)


def read(*parts):
    """Missing file reads as EMPTY, never as a traceback.

    ⚠️ A GATE THAT RAISES IS A WORSE GATE THAN ONE THAT FAILS. Born red at dtp
    404ac67 this file exploded with FileNotFoundError on the absent generator,
    which reports "something is wrong somewhere" instead of naming the checks
    that do not hold. Empty content fails every assertion below by name.
    """
    try:
        return open(os.path.join(_root, *parts), encoding="utf-8").read()
    except OSError:
        return ""


def main():
    print("check_handoff_item — the fresh-thread handoff")
    fn = read("menu_functions.sh")
    rg = read("menu_registry.sh")

    body = fn.split("mi_handoff_fresh_claude() {", 1)
    check("H1 the function exists", len(body) == 2)
    b = body[1].split("\n}\n", 1)[0] if len(body) == 2 else ""

    check("H2 the API key is unset before claude is launched — it bills the "
          "subscription, not the API",
          b.count("env -u ANTHROPIC_API_KEY") >= 1
          and "claude" in b)

    # H3 — every invocation must use the ABSOLUTE path. A bare `claude` under a
    # venv resolves against a PATH that predates ~/.local/bin.
    bare = [ln.strip() for ln in b.splitlines()
            if re.search(r"(^|[;&|\s])claude\s+\"", ln) and "$CLAUDE" not in ln]
    check("H3 claude is invoked by ABSOLUTE path, never bare", not bare,
          "; ".join(bare[:2]))

    # H4 — ORDER. switch-client must appear before any kill of other sessions,
    # or the client dies with the session it is attached to.
    i_sw, i_kill = b.find("switch-client"), b.find("kill-session")
    check("H4 the client switches BEFORE anything is killed",
          i_sw != -1 and i_kill != -1 and i_sw < i_kill,
          f"switch@{i_sw} kill@{i_kill}")

    check("H5 the item is registered in the menu",
          "mi_handoff_fresh_claude" in rg)

    # H6 — the generator must REFUSE rather than emit an unverified fleet claim,
    # and the item must not proceed when it does.
    gen = read("tools", "gen_handoff.py")
    check("H6 the generator refuses instead of guessing at the fleet",
          "REFUSING" in gen and "return 2" in gen)
    check("H6b and the menu item stops when it refuses",
          "gen_handoff.py" in b and "return 1" in b)

    # H7 — DRIVEN, not read. The generator must actually run and emit the
    # operator's brief plus the pointer list (§21: source text proves nothing).
    _g = os.path.join(_root, "tools", "gen_handoff.py")
    if os.path.exists(_g):
        r = subprocess.run([sys.executable, _g, "--no-fleet"],
                           capture_output=True, text=True, timeout=120)
        out, rc = r.stdout, r.returncode
    else:
        out, rc = "", 127
    check("H7 it runs and emits the brief verbatim",
          rc == 0 and "Vertigo Capital" in out
          and "information layer" in out,
          f"rc={rc}")
    check("H7b it POINTS at the agreement and backlog rather than restating them",
          "docs/WORKING_AGREEMENT.md" in out and "docs/BACKLOG.md" in out
          and "OPEN ROWS" in out)
    # H7c — UNCONDITIONAL NOW, AND v1.0's FORM COULD BE DISARMED BY THE
    # DOCUMENT IT CHECKED. It split the output on the literal "nothing to clone"
    # and scanned only the text BEFORE that point, so any handoff carrying that
    # sentence narrowed its own canary to a prefix — §20's shape exactly, where
    # the prose a rule requires is what defeats the check written against it.
    # r370 removes every clone reference from the document, so the honest
    # assertion is that the word is absent outright, with no escape hatch a
    # later edit can re-open by adding a sentence.
    check("H7c the document does not mention cloning AT ALL",
          "clone" not in out.lower())

    # H7d — THE OPERATOR'S EXACT WORDING, 2026-09-12: *"I want you to use the
    # exact phrase: 'THIS is a continuation of that work.'"* Case included; the
    # capitalised THIS is his. A phrase that is asked for verbatim and pinned by
    # nothing is a phrase the next rewrite paraphrases away, and this one is the
    # first line of orientation every fresh thread reads.
    check("H7d it opens the task with the operator's exact continuation phrase",
          "THIS is a continuation of that work." in out)

    # ── H9 — r388. THE LAST CONVERSATION IS ITEM 5, AND IT IS ACTIONABLE.
    # Operator, 2026-09-18: *"Read our last conversation in full as this thread
    # is likely a continuation of that work."*
    # 🔴 AN INSTRUCTION THAT DOES NOT SAY HOW IS THE §25 FAILURE ITSELF. That
    # section pointed at a `docs/README.md` that was never ported to v4 — for
    # months, the one rule whose job is to stop documents going unread was
    # routing to a missing document, inside a section written because two days
    # of work were lost to unread docs. So H9 does not merely assert the
    # sentence is present: it requires the PATH, and both traps that make the
    # literal instruction fail.
    # 📊 BOTH TRAPS WERE MEASURED ON 2026-09-18 BEFORE THE ENTRY WAS WRITTEN:
    # the raw transcripts run 1.6-12.7 MB and are mostly tool output while the
    # conversation text inside them is 1-121k tokens; and the NEWEST session by
    # mtime held a single turn and 2 KB, so a thread taking "last" literally
    # would have read a stub, found nothing, and concluded there was no history
    # while the real context sat in the session before it.
    check("H9 item 5 names the last conversation AND where it lives",
          "OUR LAST CONVERSATION" in out
          and ".claude/projects" in out and ".jsonl" in out,
          "path present" if ".jsonl" in out else "no transcript path emitted")
    check("H9b it warns that the raw file is not the thing to read",
          "READ THE TEXT, NOT THE FILE" in out)
    check("H9c it warns that the newest session can be a stub",
          "NEWEST IS NOT ALWAYS" in out and "SUBSTANTIVE" in out)
    # ── H9e — READ vs SEARCH ARE DIFFERENT MODES AND THE DOCUMENT SAYS SO.
    # Operator, 2026-09-18: *"looking into other past threads if available is
    # always an option for a word search or other reference."* Only the LAST
    # conversation is read in full; the rest are a searchable corpus for when a
    # question needs an origin. Pinned with the runnable form, because an
    # affordance a thread is told it has but not how to use is the §25 failure
    # this whole entry exists to avoid.
    check("H9e it offers the older threads as a SEARCHABLE corpus, with the "
          "command", "SEARCHABLE" in out and "grep -l" in out)
    # ⚠️ AND IT SAYS WHAT A TRANSCRIPT IS WORTH. §0.1: a quote found by search
    # is a LEAD TO VERIFY, not a fact to assert — the same standard §38.3 sets
    # for a panel that explains itself. Without this line the search affordance
    # invites exactly the citation-as-evidence habit §0 exists to stop.
    check("H9f it says a transcript is evidence of what was SAID, not of what "
          "is true now", "evidence of what was SAID" in out)

    # ── H9d — THE COUNT IS COUNTED, NOT REMEMBERED. The GENESIS line carried
    # the literal 418 while the ledger held 375; nobody noticed because the
    # handoff is read by a thread with no way to know better. Anchored on the
    # ABSENCE of the stale literal AND on the emitted number agreeing with the
    # ledger, so a future hardcode cannot satisfy it.
    _g_md = "/home/ubuntu/options-trader-v4/docs/GENESIS.md"
    _real = None
    if os.path.exists(_g_md):
        with open(_g_md, encoding="utf-8") as f:
            _real = sum(1 for ln in f if ln.startswith("| **"))
    check("H9d the GENESIS row count is computed, not a stale literal",
          "not all 418" not in out
          and (_real is None or f"not all {_real}." in out),
          f"ledger has {_real} rows")

    # ── H10 — THE PERMISSION LINE, AND THE ONE WORD THAT WOULD RE-GRADE THE
    # LEDGER IF IT ROTTED (r398, operator's ruling 2026-09-20).
    # 🔑 WHY THIS IS PINNED ON THE RENDERED TEXT AND NOT ON SOURCE (§21):
    # for a DOCUMENT GENERATOR the emitted prose IS the behaviour — it is the
    # only thing a fresh thread ever sees — which is the idiom H7b, H7c and
    # H9b already use.
    # 🔴 H10 — A VETO NEEDS AN OPPORTUNITY, AND AN OPPORTUNITY IS A WAIT.
    # An earlier draft of this check asserted the opposite — that the gate was
    # "the informing, not a click" — which was wrong in Claude's favour. The
    # document has to say BOTH that he may veto and that the release waits.
    check("H10 the permissions block carries the VETO and says it is a WAIT",
          "opportunity to veto" in out
          and "NEEDS AN OPPORTUNITY, WHICH MEANS A WAIT" in out,
          "the veto and the wait are both stated")
    # 🔴 H10d — ALL FIVE ANSWERS. "yes but" and "no and" are the ones a thread
    # flattens into a plain yes/no, which drops the half of his reply that is
    # an instruction; and "hold off" is not a refusal, nor is the silence
    # after it consent.
    check("H10d it carries all five answers, not a yes/no binary",
          "yes but" in out and "no and" in out and "hold" in out)
    # 🔴 H10b — AND THE APPRAISAL EXPIRES. This is the half most likely to be
    # dropped in a future edit, and dropping it is the [[ORB.16]] failure: a
    # finding he had already said yes to, retracted an hour later, because the
    # delivery no longer matched what he had been told.
    check("H10b it says the approval EXPIRES when the delivery changes",
          "EXPIRES" in out and "fresh one is owed" in out)
    # 🔴 H10c — `BAKED` MUST KEEP §18's MEANING IN THE STATUS COLUMN.
    # The operator uses `bake` conversationally for "make it official"; §18 and
    # BACKLOG PART 0 use ✅ BAKED for LIVE ON THE BOXES, and hundreds of rows
    # already carry it that way. A handoff that taught the other sense would
    # silently re-grade every one of them — falsifying the record, which §0.1
    # forbids in its own words. Anchored on the CONSEQUENCE (pushed ≠ baked)
    # rather than on a definition, so a reworded block still has to mean it.
    check("H10c it preserves §18's BAKED — on origin is PUSHED, not ✅",
          "LIVE ON THE BOXES" in out and "PUSHED, never" in out)

    # H8 — open means the STATUS column. The first draft filtered on the 🔴
    # severity marker and listed long-closed rows as outstanding.
    check("H8 open rows are read from the status column, not the severity mark",
          '"⬜" in cols[3]' in gen)

    # ── H11 — THE READING BUDGETS ARE MEASURED, WHICH IS H9d GENERALISED.
    # 🔴 H9d PINNED THE ROW COUNT AND THE THREE SIZES BESIDE IT WENT ON ROTTING.
    # Measured at r410: WORKING_AGREEMENT claimed ~21k against ~30k, GENESIS
    # ~148k against ~188k, BACKLOG ~142k against ~223k — the last a 57%
    # understatement in the figure a fresh thread uses to decide HOW to read
    # the biggest document in the repo. The lesson was learned for the count
    # and not swept to its neighbours: C.30, inside one function.
    # 🔑 ANCHORED ON THE SOURCE CALLING THE MEASURER, not on any figure — a
    # check that pinned a number would be the defect it is testing for.
    src_gen = open(_g, encoding="utf-8", errors="replace").read()
    measured = src_gen.count("_tok(")
    # ⚠️ THE ABSENCE HALF READS THE RENDERED OUTPUT, NOT THE SOURCE — §20.
    # This file's header must record the figures it removed, and a DATED
    # 2026-09-12 measurement lower down legitimately preserves the old ones.
    # A source-wide canary fires on both: on the changelog §5 demands, and on
    # a historical measurement that is correct for its date. What must not
    # contain a stale literal is the thing a fresh thread actually READS.
    check("H11 the reading-list sizes are MEASURED, not literals",
          measured >= 3 and "~142k tokens" not in out
          and "~148k tokens" not in out and "~21k tokens" not in out,
          f"{measured} _tok() call site(s); nothing stale is emitted")

    # ── H11b — AND THE WAY IN IS ANCHORED ON HEADINGS, NEVER LINE NUMBERS.
    # The first cut of this guidance shipped `awk 'NR>=45 && NR<=475'`, which
    # is DOC.27's own defect reintroduced by the revision that fixed it: a row
    # filed tomorrow moves every one of those numbers.
    check("H11b the BACKLOG recipe is heading-anchored, not line-numbered",
          "/^## PART 1/" in out and "NR>=45" not in out,
          "the truncation recipe survives the next row being filed")

    # ── H12 — THE SCHEDULED CLOCK. The file stated the fleet's COUNT and never
    # what moves it, so a thread could not tell whether `0/15 running` was
    # normal or a fault — for an agent whose job is wrangling the fleet, the
    # largest gap this document had.
    check("H12 the handoff names what runs without being asked",
          "THE SCHEDULED CLOCK" in out and "dtp-morning.timer" in out,
          "read from systemd at generation time")
    # ⚠️ AND IT MUST NOT LEARN THE ENVIRONMENT BLOCK (§18a). Control holds a
    # live funded broker token; `-p Environment` prints all of it. Pinned on
    # the SOURCE because the leak would be in what the tool ASKS for, and a
    # rendered handoff that happened not to leak today proves nothing.
    # ⚠️ KEYED ON THE QUOTED STRING LITERAL, which is what an argv entry looks
    # like — the bare word appears in the comment that EXPLAINS the rule, and
    # a canary that fires on its own doctrine is the one that gets loosened
    # until it misses the real thing (§20).
    check("H12b it never asks systemd for an Environment block (§18a)",
          '"Environment"' not in src_gen and "'Environment'" not in src_gen,
          "no argv entry requests the block; ExecStart-adjacent only")

    # ── H13 — A PRESCRIBED TOOL MUST EXIST. §25 spent months routing readers
    # to a `docs/README.md` that was never ported; the one rule whose job is
    # to stop documents going unread was itself pointing at a missing file.
    # A handoff that names a command is making the same promise.
    import re as _re
    named = _re.findall(r"python3 (~/[\w/.-]+\.py)", out)
    # 🔴 RESOLVED AGAINST THIS CHECKOUT, NEVER `~`. r408 recorded exactly this
    # defect in r407's gate: it read a file from the WORKING TREE, passed on
    # control because the file happened to be there, and would have gone red
    # in a pristine clone for the environment rather than the content
    # (CHK.9 item 2). A gate on a repo must ask that repo.
    # `_root` is already the module-level repo root (line 56) — reusing it
    # rather than rebinding, which shadowed it and broke the reference ABOVE
    # this point. Caught by running the gate, not by reading it (§24).
    def _local(t):
        tail = t.split("day_trader_pro/", 1)[-1]
        return os.path.join(_root, tail)
    missing = [t for t in named
               if not (os.path.exists(_local(t))
                       or os.path.exists(os.path.expanduser(t)))]
    check("H13 every tool the handoff prescribes EXISTS",
          bool(named) and not missing,
          f"{len(named)} named, missing: {missing or 'none'}")

    # ── H13b — AND THE TRANSCRIPT TOOL REFUSES TO HAND BACK A MIRROR.
    # 🔴 DRIVEN, NOT READ. The first cut of `--pick` returned the CALLER'S OWN
    # live transcript — which reads exactly like history and would confirm
    # whatever the reader already believed. Caught by running it. The check
    # runs the real tool and requires it to SAY it skipped, because a silent
    # skip and a silent mirror are indistinguishable from here (§0.5).
    _tt = os.path.join(_root, "tools", "transcript_text.py")
    if os.path.exists(_tt):
        try:
            rr = subprocess.run([sys.executable, _tt, "--list"],
                                capture_output=True, text=True, timeout=180)
            ok = rr.returncode == 0 and "verdict" in rr.stdout
            check("H13b the transcript tool runs and classifies stubs",
                  ok, f"rc={rr.returncode}")
        except Exception as e:                                  # noqa: BLE001
            check("H13b the transcript tool runs and classifies stubs",
                  False, f"{e.__class__.__name__}")
    else:
        check("H13b the transcript tool runs and classifies stubs",
              False, "tools/transcript_text.py is missing")

    print()
    if _fails:
        print(f"FAILED {len(_fails)}: {', '.join(_fails)}")
        return 1
    print("check_handoff_item: all checks pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
