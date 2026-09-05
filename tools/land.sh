#!/usr/bin/env bash
# day_trader_pro/tools/land.sh — v1.3
# v1.3 (2026-09-05) — dtp r289 / DEP.2. POS/NEG MATCH AS FIXED STRINGS. See the
#   block in the spec-format header: `grep -q` is a BRE, and it graded two
#   deliveries wrongly in one day — `**r247**` degenerated to `r24` and PASSED
#   against a file with no such row, and `[ "$GO" = "y" ]` read as a character
#   class and REFUSED a correct one. One failed open, one failed closed.
# v1.2 (2026-09-05) — dtp r279. ALL HALVES LAND, OR NONE REACH ORIGIN.
#   Operator, 2026-09-05: "make sure all will land or none."
#
#   🔴 THE FAILURE HE IS CLOSING, OBSERVED RATHER THAN IMAGINED. Landing
#   r277_r2 before r276_r2 in the sandbox: the dtp half passed its gate,
#   committed AND PUSHED, and only then did the otv4 half's gate correctly
#   refuse on a GENESIS row r276 had not yet written. Origin ended up holding
#   the code with no backlog entry — a half delivery, on the shared truth the
#   fleet pulls from — and re-running it then died at `git commit` with nothing
#   left to stage. v1.1 landed halves sequentially and stopped at the first
#   failure, which is one-at-a-time, not all-or-nothing.
#
#   🔑 WHY A PRE-FLIGHT OF EVERY GATE WOULD NOT HAVE WORKED, and this is the
#   whole design. The obvious fix is "verify every half before landing any" —
#   and it is WRONG here, because a half is ALLOWED to gate on an artifact an
#   EARLIER half produces. r277_r2's otv4 half asserts a GENESIS row that
#   r276_r2's otv4 land appends. Pre-flighting it before r276 landed would fail
#   a gate that is not actually failing. The dependency is real and the ordering
#   exists to serve it.
#
#   🔑 SO THE SPLIT IS COMMIT vs PUSH, WHICH IS WHERE THE IRREVERSIBILITY
#   ACTUALLY SITS. Phase 1 verifies and commits each half LOCALLY, in order, so
#   a later half still sees an earlier half's landed files. Nothing is pushed.
#   Phase 2 pushes every repo, and only runs if EVERY half reached a commit.
#   A failure anywhere in phase 1 rolls every repo this run committed to back
#   to the SHA it was on before the run started — so ORIGIN NEVER SEES A
#   PARTIAL DELIVERY, which is the property that matters when fifteen boxes
#   pull from it.
#
#   ⚠️ THE ROLLBACK IS `reset --soft`, NOT `--hard`, AND THAT IS DELIBERATE.
#   A hard reset would also revert an unrelated tracked file the operator had
#   edited — the exact reason §35 already refuses a blind `git checkout -- .`
#   on a failed gate. Soft moves HEAD back and leaves the tree, so a rolled-back
#   half looks EXACTLY like a half that failed its gate today: files present,
#   uncommitted, recovery printed. Nothing of his is destroyed to tidy up after
#   a delivery of mine.
#
#   ⚠️ AND THE HONEST LIMIT IS STATED RATHER THAN PAPERED OVER. Phase 2 pushes
#   to two independent remotes; that is not a transaction and cannot be made
#   one. What it CAN be is ordered last, back to back, with nothing between
#   them but network — and if one push fails the report names exactly which
#   repo is ahead of its remote and the one command that fixes it. A rolled-back
#   push is not attempted: reverting something already on origin is a decision
#   for a human, not a cleanup step.
# v1.1 (2026-09-05) — dtp r278. THREE GAPS BETWEEN WHAT THIS DID AND WHAT THE
#   OPERATOR ASKED A DEPLOY TO DO, plus the menu item LAND.1 refused and he has
#   now asked for. His list, 2026-09-05: unpack, stage, verify the write map,
#   the file map, the file versions, the changelog and the Genesis append,
#   "any smoke tests or canaries are verified", then commit and clean up.
#   v1.0 already did all of that EXCEPT the checks — so this adds the one
#   missing stage rather than rebuilding the nine that worked.
#
#   🔴 (1) IT RAN NO CHECKERS. The content gate greps for a distinctive line;
#   it never EXECUTES anything. That is precisely the r201 shape WA §0.6 names:
#   the gate asserted a function existed and that the file parsed, and both were
#   true of the broken version. `CHECK <path>` directives now RUN in the repo
#   and must exit 0.
#   ⚠️ AND A HALF THAT SHIPS CODE AND DECLARES NO CHECK IS REFUSED — detected,
#   not assumed: if the payload carries a `.py` outside `docs/` and the spec
#   names no check, nothing was executed and the delivery says so by failing.
#   A docs-only half legitimately has nothing to run and reports that out loud
#   rather than passing silently, because "not applicable" and "passed" must
#   never look alike (the CV.1 failure, and r183's own SKIP idiom).
#
#   🔴 (2) `git add -A` STAGED WHATEVER WAS IN THE TREE. The operator's own
#   standing rule is the opposite — "NEVER git add -A; stage shipped files by
#   name" — written after a stray `fit_report.py` was pushed off main. WA §33's
#   sketch of the land order says `git add -A`, so two documents disagreed and
#   the looser one was the one in the code. Now every path is named: the
#   payload's own file list, plus the two regenerated maps and the GENESIS row
#   when the repo has them. An unrelated local edit is no longer swept into a
#   delivery commit.
#
#   🔴 (3) THE ARCHIVE IT DELETED WAS A GUESS. `ls "$HOME"/*_r*.tar* | head -1`
#   takes the first glob match, and the operator routinely has two pending — on
#   2026-09-05 he had r276 and r277 in `/home/ubuntu` at once. The cleanup then
#   `rm -f`s that guess. `LAND_ARCHIVE` is now honoured and `tools/deploy.sh`
#   sets it to the file it actually extracted; without it, an AMBIGUOUS glob
#   deletes NOTHING and says so. Untidy is recoverable; deleting the wrong
#   tarball is not (r206: a derived figure must name the layer it came from).
#
#   ⚠️ NEW OPTIONAL DIRECTIVE `ORDER <n>` sorts the halves when `deploy.sh`
#   discovers them, so a two-repo delivery whose second half cites the first
#   cannot land backwards. Default 50; ties break on name.
# v1.0 (2026-09-01) — otv4 r207 / dtp r235. THE LANDER, GENERIC AND MULTI-REPO.
#   Operator, 2026-09-01: "why don't you package your land script as a generic
#   in the tarball & keep calling it every time we land a new update... we can
#   absolutely ship multi-repo file uploads in the same tarball with different
#   land commands."
#
#   🔴 WHY IT EXISTS. The same deploy was hand-built three times in one session
#   and hand-built wrong twice, both times on TRANSPORT rather than logic: one
#   carried `cd "$R" || exit 0` and CLOSED THE OPERATOR'S SHELL when the path
#   guess was wrong, the next was 4,400 characters and the mobile paste
#   truncated it mid-string at a `>` continuation prompt. WORKING_AGREEMENT §1
#   already said what to do — "if logic needs more than one line, write it as a
#   file, have the user download/stage it, and run it as a script" — and §13
#   says check whether the menu already does it before writing a one-off. A
#   deploy retyped every session is the definition of a one-off.
#
#   🔑 IT LIVES IN day_trader_pro, FOR THE REASON r183 ALREADY GAVE. Control is
#   always present, and one implementation beats two that drift. It also means
#   an otv4 archive can never overwrite the script that is extracting it —
#   bash reads a script incrementally by byte offset, so a delivery that
#   replaced its own running lander would execute garbage from wherever the
#   interpreter had reached. The staging copy in /tmp is what actually runs, so
#   even a dtp delivery that updates this file is safe.
#
# ⚠️ THE SPEC NEVER ENTERS A REPO. Each half of the archive carries its own
#   `land.spec` — the per-delivery content gate, which cannot be generic
#   because the only auto-derivable assertion is "the version moved", and that
#   is precisely the header-bump-with-no-edit the gate exists to catch. The
#   spec sits in the STAGING directory beside the payload and is never copied
#   in, so §27's "the archive carries no MANIFEST or scaffolding" holds by
#   construction rather than by a cleanup step someone has to remember.
#
# ⚠️ NO `exit` HAZARD FOR THE OPERATOR. This is run as `bash land.sh`, a child
#   process. Even so, nothing here assumes an interactive shell.
#
# Usage:
#   mkdir -p /tmp/land && tar xf "$HOME"/<archive>.tar* -C /tmp/land
#   bash /tmp/land/land.sh dtp otv4        # land both, in that order
#   bash /tmp/land/land.sh otv4            # or one at a time
#
# Spec format (one directive per line, `|` separates fields):
#   REPO   <marker-file> <marker-file>     files that identify the target repo
#   REV    r207                             revision id, for GENESIS + the gate
#   DESC   <one line>                       GENESIS row AND commit subject
#   POS    <path>|<literal string>          must be present after extraction
#   NEG    <path>|<literal string>          must be ABSENT after extraction
#
# 🔴 v1.3 — POS/NEG ARE FIXED STRINGS (`grep -qF`), NOT PATTERNS. They were
# `grep -q`, which is a BASIC REGULAR EXPRESSION, and the gate therefore
# passed twice on patterns it never actually matched:
#   · `POS docs/GENESIS.md|**r247**` — BRE reads `*` as "zero or more of the
#     preceding character", so `**r247**` degenerates to `r24`, and the gate
#     said PASS against a GENESIS with no r247 row in it.
#   · `NEG menu_functions.sh|[ "$GO" = "y" ]` — the brackets are a CHARACTER
#     CLASS, so it matched almost any line and REFUSED a correct delivery.
# ⚠️ ONE FAILED OPEN AND ONE FAILED CLOSED, WHICH IS THE POINT. A gate that
# can do either is not weaker in one direction, it is unrelated to the thing
# it claims to check.
# 🔑 AND THE ASSERTIONS ARE CONTENT, NOT PATTERNS, BY DESIGN — the operator's
# own rule is that a supersession check keys on a distinctive LINE from the
# real change. `**bold**`, `[brackets]`, `$vars`, `(parens)` and `.` are all
# ordinary characters in the text being asserted, so a regex engine here only
# ever misreads them. Nothing was gained by it and two deliveries were graded
# wrongly.
set -u

STAGE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# v1.1 — NAMED, NOT GUESSED. deploy.sh exports the file it actually extracted.
# Falling back to a glob is kept for a hand-run, but an ambiguous glob resolves
# to NOTHING rather than to whichever name sorts first, because the only thing
# this variable is used for is `rm -f`.
ARCHIVE="${LAND_ARCHIVE:-}"
if [ -z "$ARCHIVE" ]; then
  _n="$(ls "$HOME"/*_r*.tar* 2>/dev/null | wc -l)"
  if [ "$_n" = "1" ]; then ARCHIVE="$(ls "$HOME"/*_r*.tar* 2>/dev/null)"; fi
  AMBIGUOUS="$_n"
fi
FAILED=0
LANDED=""
declare -A PRE_SHA=()      # v1.2 — repo -> sha before this run touched it
declare -a COMMITTED=()    # v1.2 — repos this run committed to, in order

# ── re-exec from a private copy if we are running from inside a repo ───────
# A dtp delivery that ships a new tools/land.sh would otherwise overwrite this
# file while bash is still reading it.
if [ "${LAND_REEXEC:-}" != "1" ] && [ -d "$STAGE/../.git" ]; then
  cp "${BASH_SOURCE[0]}" /tmp/.land_running.sh 2>/dev/null || true
  LAND_REEXEC=1 exec bash /tmp/.land_running.sh "$@"
fi

# ⚠️ A FAILED GATE DOES NOT LEAVE A CLEAN WORKING TREE, and §35 already
# records that: the payload is extracted BEFORE it is verified, so a refusal
# leaves the new files in place, uncommitted. That is the safe direction — the
# alternative is a blind `git checkout -- .`, which would also discard any
# unrelated local edit. So it is REPORTED with its recovery rather than
# tidied away, because a dirty tree nobody was told about is the next
# session's mystery.
die() {
  echo "  $1"
  echo "  NOTHING WAS COMMITTED OR PUSHED. Archive and staging kept in $HOME."
  if [ -n "${repo:-}" ] && [ -d "${repo:-}/.git" ]; then
    local n; n="$(cd "$repo" && git status --porcelain | wc -l)"
    if [ "$n" != "0" ]; then
      echo "  ⚠️ $repo has $n uncommitted file(s) from the extract."
      echo "     To discard them:  cd $repo && git checkout -- . && git clean -fd"
    fi
  fi
  FAILED=1
}

land_one() {
  local half="$1" d="$STAGE/$half" spec="$STAGE/$half/land.spec"
  echo
  echo "=============================================================="
  echo " LANDING: $half"
  echo "=============================================================="
  [ -d "$d" ]     || { die "no such half in the archive: $half"; return 1; }
  [ -f "$spec" ]  || { die "$half carries NO land.spec — refusing. A delivery with no content gate is the one you most want stopped."; return 1; }

  local rev desc markers repo=""
  rev="$(grep    '^REV '   "$spec" | head -1 | cut -d' ' -f2-)"
  desc="$(grep   '^DESC '  "$spec" | head -1 | cut -d' ' -f2-)"
  markers="$(grep '^REPO ' "$spec" | head -1 | cut -d' ' -f2-)"
  [ -n "$rev" ]     || { die "spec carries no REV"; return 1; }
  [ -n "$desc" ]    || { die "spec carries no DESC"; return 1; }
  [ -n "$markers" ] || { die "spec carries no REPO markers"; return 1; }

  # ── find the repo rather than guess the path (WORKING_AGREEMENT §3) ──────
  local cand ok
  for cand in "$HOME"/*/; do
    [ -d "${cand}.git" ] || continue
    ok=1
    for m in $markers; do [ -f "${cand}${m}" ] || ok=0; done
    [ "$ok" = "1" ] && { repo="${cand%/}"; break; }
  done
  if [ -z "$repo" ]; then
    die "no checkout under $HOME carries all of: $markers"; return 1
  fi
  echo "  repo: $repo"
  echo "  rev:  $rev"

  cd "$repo" || { die "cannot cd $repo"; return 1; }

  # v1.2 — WHERE THIS REPO WAS BEFORE WE TOUCHED IT. Captured BEFORE the pull,
  # so a rollback returns it to the operator's own starting point rather than
  # to whatever origin happened to hold mid-run.
  PRE_SHA["$repo"]="$(git rev-parse HEAD 2>/dev/null)"

  # ── pull FIRST so the extract lands on true HEAD (§15) ──────────────────
  git pull --ff-only || { die "PULL FAILED — nothing extracted."; return 1; }

  # ── copy the payload in, spec excluded by name ──────────────────────────
  ( cd "$d" && find . -type f ! -name land.spec -print0 \
      | tar cf - --null -T - ) | tar xf - -C "$repo" \
    || { die "EXTRACT FAILED"; return 1; }

  # ── THE CONTENT GATE: this delivery's own assertions (§15) ──────────────
  # Keyed on CONTENT, not version strings: a header bump with no real edit
  # must fail. On any flag: fail loudly, stage nothing, keep the archive.
  local g=0 f p
  while IFS= read -r line; do
    f="${line#POS }"; p="${f#*|}"; f="${f%%|*}"
    if ! grep -qF "$p" "$repo/$f" 2>/dev/null; then
      echo "  MISSING in $f: $p"; g=1
    fi
  done < <(grep '^POS ' "$spec")
  while IFS= read -r line; do
    f="${line#NEG }"; p="${f#*|}"; f="${f%%|*}"
    if grep -qF "$p" "$repo/$f" 2>/dev/null; then
      echo "  STILL PRESENT in $f: $p"; g=1
    fi
  done < <(grep '^NEG ' "$spec")
  if [ "$g" != "0" ]; then
    die "CONTENT GATE FAILED"; return 1
  fi
  echo "  content gate: pass"

  # ── THE CHECKS: EXECUTED, NOT GREPPED (v1.1) ────────────────────────────
  # WA §0.6 — "the land gate RUNS the thing and requires its output, not its
  # presence." §21 says the same one level up: a test that reads source text
  # proves nothing about runtime. Each CHECK runs with the repo as cwd, which
  # is how every checker in these trees expects to be invoked.
  local nchk=0 chk
  while IFS= read -r line; do
    chk="${line#CHECK }"
    nchk=$((nchk+1))
    # 🔴 A CHECK MUST NOT INHERIT THIS DELIVERY'S OWN CONTROL VARIABLES, and
    # this was found by the CHECK stage biting its own delivery: r279's
    # `check_land_sh.py` itself invokes a land, that nested run inherited
    # `LAND_ARCHIVE` from the outer one, and on success its cleanup would have
    # `rm -f`d THE TARBALL CURRENTLY BEING LANDED. It surfaced as a check that
    # failed under the lander and passed by hand — the worst shape of red,
    # because it looks like a flaky test rather than a leak.
    # The general rule: a CHECK is arbitrary code and gets a clean slate of
    # everything that names this delivery.
    if ( cd "$repo" && env -u LAND_ARCHIVE -u LAND_STAGE python3 "$chk" ) >/dev/null 2>&1; then
      echo "  check: $chk PASS"
    else
      echo "  🔴 CHECK FAILED: $chk"
      echo "     re-run it yourself:  cd $repo && python3 $chk"
      die "A DECLARED CHECK DID NOT PASS"; return 1
    fi
  done < <(grep '^CHECK ' "$spec")

  # ⚠️ A CODE HALF WITH NO CHECK IS REFUSED. Detected from the payload rather
  # than trusted to the author: if this half ships a .py outside docs/ and
  # declared nothing to run, then nothing ran, and a delivery that verified
  # nothing must not read the same as one that verified everything.
  local ncode
  ncode="$(cd "$d" && find . -name '*.py' -not -path './docs/*' | wc -l)"
  if [ "$nchk" = "0" ] && [ "$ncode" != "0" ]; then
    die "THIS HALF SHIPS $ncode .py FILE(S) AND DECLARES NO CHECK — nothing was executed. Add a CHECK line to land.spec."
    return 1
  fi
  [ "$nchk" = "0" ] && echo "  checks: NONE DECLARED (docs-only half — nothing was executed)"

  # ── generated maps regenerate INSIDE the land command (§33) ─────────────
  # Detected, not assumed: dtp carries neither, and "not applicable" must
  # never look like "passed" (the CV.1 failure).
  if [ -f "$repo/tests/gen_file_map.py" ]; then
    python3 tests/gen_file_map.py >/dev/null 2>&1 || { die "FILE MAP regeneration failed"; return 1; }
    echo "  file map: regenerated"
  fi
  if [ -f "$repo/tests/gen_write_map.py" ]; then
    python3 tests/gen_write_map.py >/dev/null 2>&1 || { die "WRITE MAP regeneration failed"; return 1; }
    echo "  write map: regenerated"
  fi

  # ── GENESIS is appended BEFORE git add, so the row ships inside the
  #    commit it describes (§35). One string becomes both.
  if [ -f "$repo/docs/GENESIS.md" ]; then
    printf '| **%s** | %s |\n' "$rev" "$desc" >> "$repo/docs/GENESIS.md"
    echo "  GENESIS: appended"
  fi

  # ── and a script confirms the bookkeeping (r183) ────────────────────────
  # It verifies exactly one GENESIS row for this rev AND that it is LAST,
  # that both maps regenerate identical, that every changed source file bumped
  # its TITLE version, and that the newest dated changelog entry AGREES with
  # that title. ⚠️ It proves the BOOKKEEPING, never the edit — the content
  # gate above is what proves that. Citing this one for both would be the
  # laundered green §18 names.
  local ld=""
  for cand in "$HOME"/day_trader_pro "$HOME"/*/; do
    [ -f "${cand%/}/tools/check_land_discipline.py" ] && { ld="${cand%/}"; break; }
  done
  if [ -z "$ld" ]; then
    die "check_land_discipline.py NOT FOUND — cannot confirm the bookkeeping."; return 1
  fi
  python3 "$ld/tools/check_land_discipline.py" --repo "$repo" --rev "$rev" \
    || { die "LAND DISCIPLINE FAILED"; return 1; }

  # ── STAGE BY NAME (v1.1) ────────────────────────────────────────────────
  # Operator's standing rule: "NEVER git add -A — stage shipped files by name",
  # written after a stray file was pushed off main. The set is the payload's
  # own file list plus the artifacts THIS command generated, and nothing else.
  local staged=0
  while IFS= read -r rel; do
    git add -- "$rel" && staged=$((staged+1))
  done < <(cd "$d" && find . -type f ! -name land.spec -printf '%P\n')
  for gen in docs/FILE_MAP.md docs/WRITE_MAP.md docs/GENESIS.md; do
    [ -f "$repo/$gen" ] && git add -- "$gen"
  done
  echo "  staged $staged payload file(s) by name"
  git commit -q -m "$rev: $desc" || { die "COMMIT FAILED"; return 1; }
  # v1.2 — COMMITTED, NOT PUSHED. Phase 2 pushes, and only if every half got
  # this far. Recording the repo and its PRE-RUN sha here is what makes the
  # rollback possible and what makes it precise: we can only undo what this
  # run did.
  COMMITTED+=("$repo")
  echo "  committed $rev locally — holding the push until every half is in"
  LANDED="$LANDED $half"
  return 0
}

if [ "$#" -eq 0 ]; then
  echo "usage: bash $0 <half> [half ...]   (halves present: $(cd "$STAGE" && ls -d */ 2>/dev/null | tr -d / | tr '\n' ' '))"
  exit 1
fi

# ── PHASE 1 — VERIFY AND COMMIT EVERY HALF, LOCALLY ────────────────────────
for half in "$@"; do
  land_one "$half" || break
done

# ── ROLLBACK — nothing reaches origin unless everything got here ───────────
# 🔑 THIS IS THE POINT OF v1.2. A half that failed leaves the others' commits
# undone, so the operator is never left reconciling a delivery that half
# happened on a remote fifteen boxes pull from.
if [ "$FAILED" != "0" ]; then
  if [ "${#COMMITTED[@]}" -gt 0 ]; then
    echo
    echo "ROLLING BACK ${#COMMITTED[@]} half/halves that had already committed —"
    echo "NOTHING WAS PUSHED, so origin is untouched."
    for r in "${COMMITTED[@]}"; do
      sha="${PRE_SHA[$r]:-}"
      if [ -n "$sha" ] && ( cd "$r" && git reset --soft "$sha" ); then
        echo "  $r -> $sha (soft: the files are still in the tree, uncommitted)"
      else
        # ⚠️ NAMED, NEVER SWALLOWED. A rollback that fails silently is worse
        # than no rollback, because the operator would believe origin and his
        # checkout agree when they do not.
        echo "  🔴 $r — COULD NOT ROLL BACK. It holds a commit that is NOT on"
        echo "     origin. Inspect it: cd $r && git log --oneline -3"
      fi
    done
  fi
  echo
  echo "INCOMPLETE. Archive and staging KEPT so nothing has to be re-downloaded."
  exit 1
fi

if [ -z "$LANDED" ]; then
  echo
  echo "INCOMPLETE — nothing landed."
  exit 1
fi

# ── PHASE 2 — PUSH, LAST, BACK TO BACK ─────────────────────────────────────
# ⚠️ TWO REMOTES ARE NOT A TRANSACTION and this does not pretend otherwise.
# What it can do is leave nothing but network between the pushes, and name the
# exact recovery if one of them fails.
PUSHED=""
for r in "${COMMITTED[@]}"; do
  if ( cd "$r" && git push -q ); then
    PUSHED="$PUSHED $r"
    echo "  pushed $r"
  else
    echo
    echo "🔴 PUSH FAILED for $r."
    [ -n "$PUSHED" ] && echo "   ALREADY ON ORIGIN:$PUSHED"
    echo "   This one is committed locally and ahead of its remote."
    echo "   Fix the remote, then:  cd $r && git push"
    echo "   ⚠️ NOT rolled back — reverting something already pushed is a"
    echo "      decision for you, not a cleanup step."
    echo
    echo "INCOMPLETE. Archive and staging KEPT."
    exit 1
  fi
done

echo
# ── delivery scaffolding cleans itself up (§27) ────────────────────────────
rm -rf "$STAGE" /tmp/.land_running.sh
if [ -n "$ARCHIVE" ]; then
  rm -f "$ARCHIVE"
  echo "ALL LANDED:$LANDED — archive and staging removed."
else
  echo "ALL LANDED:$LANDED — staging removed."
  echo "⚠️ ${AMBIGUOUS:-0} tarball(s) matched in \$HOME and none was named, so"
  echo "   NOTHING was deleted. Remove the one you landed by hand."
fi
exit 0
