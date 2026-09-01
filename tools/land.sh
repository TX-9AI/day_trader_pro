#!/usr/bin/env bash
# day_trader_pro/tools/land.sh — v1.0
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
#   POS    <path>|<grep pattern>            must be present after extraction
#   NEG    <path>|<grep pattern>            must be ABSENT after extraction
set -u

STAGE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARCHIVE="$(ls "$HOME"/*_r*.tar* 2>/dev/null | head -1)"
FAILED=0
LANDED=""

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
    if ! grep -q "$p" "$repo/$f" 2>/dev/null; then
      echo "  MISSING in $f: $p"; g=1
    fi
  done < <(grep '^POS ' "$spec")
  while IFS= read -r line; do
    f="${line#NEG }"; p="${f#*|}"; f="${f%%|*}"
    if grep -q "$p" "$repo/$f" 2>/dev/null; then
      echo "  STILL PRESENT in $f: $p"; g=1
    fi
  done < <(grep '^NEG ' "$spec")
  if [ "$g" != "0" ]; then
    die "CONTENT GATE FAILED"; return 1
  fi
  echo "  content gate: pass"

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

  git add -A
  git commit -q -m "$rev: $desc" || { die "COMMIT FAILED"; return 1; }
  if git push -q; then
    echo "  LANDED $rev — pushed."
    LANDED="$LANDED $half"
    return 0
  fi
  echo "  PUSH FAILED — committed locally, archive KEPT."
  echo "  Fix the remote, then: cd $repo && git push"
  FAILED=1
  return 1
}

if [ "$#" -eq 0 ]; then
  echo "usage: bash $0 <half> [half ...]   (halves present: $(cd "$STAGE" && ls -d */ 2>/dev/null | tr -d / | tr '\n' ' '))"
  exit 1
fi

for half in "$@"; do
  land_one "$half" || break
done

echo
if [ "$FAILED" = "0" ] && [ -n "$LANDED" ]; then
  # ── delivery scaffolding cleans itself up (§27) ─────────────────────────
  rm -rf "$STAGE" /tmp/.land_running.sh
  [ -n "$ARCHIVE" ] && rm -f "$ARCHIVE"
  echo "ALL LANDED:$LANDED — archive and staging removed."
  exit 0
fi
echo "INCOMPLETE. Archive and staging KEPT so nothing has to be re-downloaded."
exit 1
