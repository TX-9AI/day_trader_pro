#!/usr/bin/env bash
# day_trader_pro/tools/preflight.sh — v1.0
# v1.0 (2026-09-07) — dtp r320 / LAND.8. REHEARSE THE LAND BEFORE THE OPERATOR
#   RUNS IT. Fresh-clones each repo at its declared BASE, applies each half in
#   ORDER, then runs exactly what the lander runs and in the same sequence:
#   BASE match -> content gate -> every declared CHECK -> DEL -> map regen ->
#   check_land_discipline. Green here means green there.
#
# 🔴 WHY IT EXISTS. On 2026-09-07 six land cycles were spent on failures the
#   operator had to discover by running the deploy: an unbumped file, a
#   checker with no changelog entry, a half ordered before the one it reads, a
#   CHECK asserting a state the lander had not reached. Every one was caught by
#   a gate that already existed — the gates worked, and the cost still landed on
#   the operator, because a caught failure is still a download, a paste, a
#   cleanup and a re-land. §0.6: instructions change the odds, a gate changes
#   the outcome.
#
# ⚠️ IT REPRODUCES THE LANDER'S SEQUENCING, WHICH IS THE WHOLE TRICK.
#   WORKING_AGREEMENT §15 said a pre-flight "would NOT have worked" because a
#   half may gate on an artifact an earlier half produces. True — and the answer
#   is ORDER, not surrender. Halves are applied in `ORDER` into clones that can
#   SEE each other, so a cross-repo check reads the extracted sibling rather
#   than origin. Rehearsing in isolation reports SKIP where the real land
#   reports FAIL, which is worse than no rehearsal.
#
# ⚠️ AND IT REFUSES TO CERTIFY WHAT IT CANNOT CHECK. `check_land_discipline`
#   lives in day_trader_pro; an earlier cut skipped it for a single-otv4-half
#   archive and still printed GREEN. It now fetches the checker and exits
#   non-zero if it cannot. A rehearsal that silently omits a gate manufactures
#   confidence.
#
# ⚠️ WHAT IT CANNOT CATCH: a SUPERSEDED archive built against a repo that has
#   not moved. Deleting a replaced tarball is still manual.
#
# Run:  bash tools/preflight.sh /path/to/archive.tar.gz
# preflight.sh — REHEARSE THE LAND BEFORE THE OPERATOR RUNS IT.
# Fresh-clones each repo at the declared BASE, extracts the half exactly as
# land_one does, then runs: BASE match -> content gate -> every declared CHECK
# -> check_land_discipline. If this is green, the real land is green.
set -u
ARC="$1"; RC=0
W=$(mktemp -d); tar xzf "$ARC" -C "$W"
REPO_otv4=""; REPO_dtp=""
# 🔴 HALVES ARE REHEARSED IN `ORDER`, INTO CLONES THAT CAN SEE EACH OTHER.
# WORKING_AGREEMENT §15 says a pre-flight "would NOT have worked" because a
# half may gate on an artifact an EARLIER half produces - verifying half two
# first fails a gate that is not failing. That is right, and it is exactly the
# r318 refusal: dtp's D5 reads otv4's calendar off disk. The answer is not to
# abandon the rehearsal but to reproduce the land's own sequencing - apply each
# half in ORDER, and point the cross-repo env at the sibling CLONE so the check
# reads what it will actually read. A rehearsal that clones repos in isolation
# reports SKIP where the real land reports FAIL, which is worse than no
# rehearsal.
order_halves() {
  for h in $(ls "$W" | grep -v '^land.sh$'); do
    [ -f "$W/$h/land.spec" ] || continue
    o=$(grep -m1 '^ORDER ' "$W/$h/land.spec" | awk '{print $2}')
    echo "${o:-99} $h"
  done | sort -n | awk '{print $2}'
}
for half in $(order_halves); do
  spec="$W/$half/land.spec"; [ -f "$spec" ] || continue
  case "$half" in
    dtp)  URL=https://github.com/TX-9AI/day_trader_pro.git ;;
    otv4) URL=https://github.com/TX-9AI/options_trader_v4.git ;;
    *) echo "  ?? unknown half $half"; RC=1; continue ;;
  esac
  echo "=== $half  rev=$(grep '^REV ' "$spec"|awk '{print $2}') ==="
  R="$W/repo_$half"; git clone -q "$URL" "$R"
  B=$(grep -m1 '^BASE ' "$spec"|awk '{print $2}')
  H=$(git -C "$R" rev-parse HEAD)
  if [ -z "$B" ]; then echo "  BASE: MISSING — would be refused"; RC=1
  elif [ "${H:0:${#B}}" != "$B" ]; then
    echo "  BASE: STALE — spec ${B:0:7} vs origin ${H:0:7}"; RC=1
  else echo "  BASE: matches origin ${B:0:7}"; fi
  ( cd "$W/$half" && find . -type f ! -name land.spec -print0 | tar cf - --null -T - ) \
    | tar xf - -C "$R"
  # so a later half's cross-repo check reads the EXTRACTED sibling, not origin
  eval "REPO_$half=\"$R\""
  bad=0
  while IFS= read -r l; do f="${l#POS }"; p="${f#*|}"; f="${f%%|*}"
    grep -qF "$p" "$R/$f" 2>/dev/null || { echo "  POS FAIL: $p"; bad=1; }
  done < <(grep '^POS ' "$spec" 2>/dev/null || true)
  while IFS= read -r l; do f="${l#NEG }"; p="${f#*|}"; f="${f%%|*}"
    grep -qF "$p" "$R/$f" 2>/dev/null && { echo "  NEG FAIL: $p"; bad=1; }
  done < <(grep '^NEG ' "$spec" 2>/dev/null || true)
  [ $bad -eq 0 ] && echo "  content gate: pass" || RC=1
  # CHECKs run BEFORE staging — same point in the pipeline as land.sh (line 371)
  while IFS= read -r l; do c="${l#CHECK }"
    sib="${REPO_otv4:-}"
    if ( cd "$R" && DTP_OTV4_DIR="${sib:-/nonexistent}" python3 "$c" >/dev/null 2>&1 ); then echo "  check: $c PASS"
    else echo "  🔴 check: $c FAILED"; RC=1; fi
  done < <(grep '^CHECK ' "$spec" 2>/dev/null || true)
  # DEL is applied in the STAGING block, AFTER the checks
  while IFS= read -r l; do t="${l#DEL }"
    [ -e "$R/$t" ] && git -C "$R" rm -q -- "$t" || { echo "  DEL MISSING: $t"; RC=1; }
  done < <(grep '^DEL ' "$spec" 2>/dev/null || true)
  [ -f "$R/tests/gen_file_map.py" ] && ( cd "$R" && python3 tests/gen_file_map.py >/dev/null 2>&1 )
  [ -f "$R/tests/gen_write_map.py" ] && ( cd "$R" && python3 tests/gen_write_map.py >/dev/null 2>&1 )
  # 🔴 THE DISCIPLINE CHECKER LIVES IN dtp AND MUST BE FETCHED, NOT SKIPPED.
  # The first cut only looked for it inside the half being rehearsed and in a
  # dtp clone that existed by luck, so a single-otv4-half archive printed
  # "(no discipline checker available)" and still said GREEN. That is the gate
  # which caught the unbumped orchestrator.py - a preflight that silently omits
  # it is worse than no preflight, because it reports confidence it has not
  # earned.
  D=""
  [ -f "$R/tools/check_land_discipline.py" ] && D="$R/tools/check_land_discipline.py"
  if [ -z "$D" ]; then
    [ -d "$W/dtp_tools" ] || git clone -q --depth 1 https://github.com/TX-9AI/day_trader_pro.git "$W/dtp_tools"
    [ -f "$W/dtp_tools/tools/check_land_discipline.py" ] && D="$W/dtp_tools/tools/check_land_discipline.py"
  fi
  if [ -n "$D" ]; then
    out=$( cd "$R" && python3 "$D" --repo . --hook 2>&1 )
    echo "$out" | grep -E 'BUMP|CHANGELOG|✗|^PASS|^FAIL' | sed 's/^/  /'
    echo "$out" | grep -q '^PASS' || RC=1
  else echo "  🔴 DISCIPLINE CHECKER UNAVAILABLE - cannot certify $half"; RC=1; fi
  echo
done
rm -rf "$W"
[ $RC -eq 0 ] && echo "PREFLIGHT GREEN — safe to land" || echo "🔴 PREFLIGHT RED — do not ship"
exit $RC
