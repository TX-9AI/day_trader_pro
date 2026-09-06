#!/usr/bin/env bash
# day_trader_pro/tools/land.sh — v1.7
# v1.7 (2026-09-06) — dtp r309 / LAND.5. A PROGRESS BAR OVER THE SLOW STRETCH.
#   Operator: "this part always takes a long time — can we add a clever progress
#   bar?" 🔑 IT COUNTS REAL STAGES RATHER THAN ESTIMATING TIME: the CHECK count
#   is read from the spec before anything slow runs, plus a fixed tail. A
#   timer-based bar would be inventing a number, and this repo has spent a day
#   removing things that report confidence they do not have.
#   ⚠️ IT NAMES THE STAGE — a bar says it is alive, the label says WHICH check
#   is slow, which is the part worth knowing on a phone.
#   ⚠️ NOT A TTY -> SILENT, or the escape codes land in a log; and the line is
#   cleared before every durable line so nothing printed is overwritten.
# v1.6 (2026-09-05) — dtp r298 / LAND.4. 🔴 `DEL` RAN AFTER THE MAPS WERE
#   REGENERATED, SO EVERY DELETION SHIPPED A STALE FILE_MAP. v1.4 put the
#   removal in the staging block, which sits BELOW `gen_file_map.py`. Landing
#   otv4 r278 — which deletes `tests/check_no_regime.py` — the map was rebuilt
#   while the file still existed, the file was then removed, and the repo's own
#   PRE-COMMIT hook regenerated, found drift and refused the commit. **The land
#   command's own artifact disagreed with the tree it was committing.**
#   ⚠️ AND THE SANDBOX COULD NOT SEE IT. `check_land_sh`'s fixtures are fresh
#   `git init` repos with NO pre-commit hook, so nothing regenerates after the
#   staging block and the drift never surfaces. The r269 docs purge did not
#   expose it either, because `.md` files are not in the import graph. The DEL
#   now runs BEFORE the maps, so they are generated against the tree that is
#   actually committed.
#   ⚠️ AND `die()`'s RECOVERY LINE IS FIXED HERE TOO. r293 corrected the
#   ROLLBACK message and left this one, on the reasoning that a gate refusal
#   stages nothing. A COMMIT failure stages everything — which is what r278
#   hit — so this line needed the unstage as much as the other did.
# v1.5 (2026-09-05) — dtp r293 / LAND.3. 🔴 A ROLLED-BACK HALF SAID "the files
#   are still in the tree, uncommitted" — TRUE, AND MISLEADING. `reset --soft`
#   leaves the payload STAGED, and the habitual cleanup `git checkout -- .`
#   copies the INDEX into the working tree, restoring exactly what it was meant
#   to discard. Observed on a real retry 2026-09-05: the tree read clean, the
#   files were still there, and the next land appended a SECOND GENESIS row for
#   the same revision — caught only by `check_land_discipline`'s duplicate-row
#   check. The message now says STAGED and prints a command that unstages
#   FIRST. ⚠️ The rollback itself is unchanged and stays `--soft`, so an
#   unrelated file the operator had mid-edit survives (§35): the defect was in
#   the sentence and the missing command, not in the mechanism.
# v1.4 (2026-09-05) — dtp r291. `DEL <path>` — A DELIVERY CAN REMOVE A FILE.
#   A payload only ever ADDED or overwrote, so retiring a document meant the
#   operator deleting it by hand after the land: outside the gate, outside the
#   commit, and outside the GENESIS row that is supposed to describe what the
#   revision did. otv4 r269 needed to remove eight spent thread contracts and
#   had nowhere to say so. One path per directive, never a glob, and a target
#   that is already absent is a REFUSAL rather than a no-op — a spec describing
#   a repo that does not exist must not land quietly.
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
#   DEL    <path>                            REMOVED from the repo (v1.4)
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
      # 🔴 v1.6 — `git reset HEAD --` FIRST, AND THE OMISSION WAS MEASURED.
      # I decided at r293 that this line was safe because a CONTENT-GATE
      # refusal stages nothing. **A COMMIT failure does** — the payload is
      # staged by then — and that is exactly what the r278 land hit. Without
      # the unstage, `git checkout -- .` copies the INDEX back into the tree
      # and restores what the operator meant to discard.
      echo "     To discard them:  cd $repo && git reset -q HEAD -- . && git checkout -- . && git clean -fd"
    fi
  fi
  FAILED=1
}


# ── PROGRESS BAR (v1.7) ──────────────────────────────────────────────────────
# 🔑 IT COUNTS REAL STAGES, IT DOES NOT ESTIMATE TIME. Operator: "this part
# always takes a long time — can we add a clever progress bar?" The honest
# version is a COUNT, because the stage list is known before the run starts:
# every CHECK named in the spec, plus a fixed tail. A timer-based bar would be
# inventing a number, and this repo has spent a day removing things that report
# confidence they do not have.
# ⚠️ IT NAMES THE STAGE. A bar alone says it is alive; the label says WHICH
# check is slow, which is the part worth knowing on a phone.
# ⚠️ NOT A TTY -> SILENT. Under a pipe the escape codes would land in a log, and
# a bar that corrupts a transcript is worse than no bar. The line is cleared
# before every durable line, so nothing printed is ever overwritten.
_PB_TOTAL=0
_PB_DONE=0

pb_init() { _PB_TOTAL="${1:-0}"; _PB_DONE=0; }

pb_step() {
  _PB_DONE=$((_PB_DONE+1))
  [ -t 1 ] || return 0
  [ "$_PB_TOTAL" -gt 0 ] || return 0
  local pct=$(( _PB_DONE * 100 / _PB_TOTAL ))
  [ "$pct" -gt 100 ] && pct=100
  local fill=$(( pct * 24 / 100 )) bar="" i=0
  while [ "$i" -lt "$fill" ]; do bar="${bar}="; i=$((i+1)); done
  [ "$fill" -lt 24 ] && bar="${bar}>"
  while [ ${#bar} -lt 24 ]; do bar="${bar}."; done
  printf '\r  [%s] %3d%%  %-26.26s' "$bar" "$pct" "${1:-}"
}

pb_clear() { [ -t 1 ] && printf '\r%*s\r' 58 ''; return 0; }

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

  # ⚠️ SIZED FROM THE SPEC, BEFORE ANYTHING SLOW RUNS. The CHECK count is known
  # here; the tail is fixed (maps, GENESIS, staging, commit).
  # ⚠️ `|| true`, NOT `|| echo 0`. `grep -c` PRINTS 0 AND EXITS 1 on no match,
  # so `|| echo 0` appended a SECOND zero and the arithmetic died — taking the
  # docs-only path with it. The same grep-counts-are-not-exit-codes trap the
  # fleet commands have, in a new costume.
  _nc=$(grep -c '^CHECK ' "$spec" 2>/dev/null || true); _nc=${_nc:-0}
  pb_init $(( _nc + 4 ))

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
    pb_step "$(basename "$chk")"
    if ( cd "$repo" && env -u LAND_ARCHIVE -u LAND_STAGE python3 "$chk" ) >/dev/null 2>&1; then
      pb_clear
      echo "  check: $chk PASS"
    else
      pb_clear
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
  # ── DEL (v1.4) — A DELIVERY CAN REMOVE A FILE ───────────────────────────
  # 🔴 UNTIL NOW IT COULD NOT. A payload only ADDS or overwrites, so retiring a
  # document meant the operator deleting it by hand afterwards — outside the
  # gate, outside the commit, and outside the record. r269 needed to remove
  # eight spent thread contracts and had nowhere to say so.
  # ⚠️ ONE PATH PER DIRECTIVE, NEVER A GLOB. A pattern here would delete
  # whatever happened to match at land time, which is the same class as the
  # `ls | head -1` archive guess v1.1 removed and the BRE gate v1.3 removed.
  # ⚠️ AND A MISSING TARGET IS A REFUSAL, NOT A NO-OP. If the file is already
  # gone the spec is describing a repo that does not exist, and landing it
  # would record a deletion that never happened.
  local deleted=0
  while IFS= read -r line; do
    local target="${line#DEL }"
    [ -z "$target" ] && continue
    if [ ! -e "$repo/$target" ]; then
      die "DEL $target — not present in $repo. The spec describes a repo this is not."
      return 1
    fi
    git rm -q -- "$target" || { die "DEL $target failed"; return 1; }
    deleted=$((deleted+1))
  done < <(grep '^DEL ' "$spec" 2>/dev/null || true)
  [ "$deleted" -gt 0 ] && echo "  removed $deleted file(s) named by DEL"

  if [ -f "$repo/tests/gen_file_map.py" ]; then
    python3 tests/gen_file_map.py >/dev/null 2>&1 || { die "FILE MAP regeneration failed"; return 1; }
    pb_step "file map"; pb_clear
    echo "  file map: regenerated"
  fi
  if [ -f "$repo/tests/gen_write_map.py" ]; then
    python3 tests/gen_write_map.py >/dev/null 2>&1 || { die "WRITE MAP regeneration failed"; return 1; }
    pb_step "write map"; pb_clear
    echo "  write map: regenerated"
  fi

  # ── GENESIS is appended BEFORE git add, so the row ships inside the
  #    commit it describes (§35). One string becomes both.
  if [ -f "$repo/docs/GENESIS.md" ]; then
    printf '| **%s** | %s |\n' "$rev" "$desc" >> "$repo/docs/GENESIS.md"
    pb_step "GENESIS"; pb_clear
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
  pb_step "staging"; pb_clear
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
        # 🔴 v1.5 — "IN THE TREE, UNCOMMITTED" WAS TRUE AND MISLEADING. After
        # `reset --soft` the payload is still STAGED IN THE INDEX, and the
        # operator's habitual cleanup — `git checkout -- .` — copies the INDEX
        # back into the working tree, restoring exactly what he meant to
        # discard. Observed 2026-09-05: the tree read clean, the files were
        # still there, and the next attempt appended a SECOND GENESIS row for
        # the same revision. `check_land_discipline` caught the duplicate,
        # which is the only reason it was not silent.
        # ⚠️ THE ROLLBACK STAYS `--soft` — that is deliberate, so an unrelated
        # file the operator had mid-edit survives (§35). The defect was in what
        # the operator was TOLD, and in the absence of a command to act on.
        echo "  $r -> $sha (soft: the payload is STAGED, not discarded)"
        echo "     re-land as-is, or discard with:"
        echo "     cd $r && git reset -q HEAD -- . && git checkout -- . && git clean -fd"
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
