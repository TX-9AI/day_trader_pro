#!/usr/bin/env bash
# day_trader_pro/tools/deploy.sh — v1.0
# v1.0 (2026-09-05) — dtp r278. THE ONE THING THE OPERATOR STILL HAD TO TYPE.
#
#   Operator, 2026-09-05: a universal deploy invoked from a devtools option —
#   "it looks for a *tar* in /home/ubuntu; unpacks it, stages it, verifies that
#   the write map is bumped, the file map is bumped, the files' versioning is
#   bumped, changelog is bumped, and Genesis is appended, any smoke tests or
#   canaries are verified, and then the deployed files are git committed, and
#   upon successful ingestion, the deployment directory is cleaned up."
#
#   🔑 NINE OF THOSE TEN STAGES ALREADY EXIST IN `tools/land.sh` (dtp r235) and
#   are not rebuilt here. r278 adds the missing one (CHECK, executed) to that
#   file. THIS file is only the three things that stood between the lander and
#   a menu item, and each is a real gap rather than packaging:
#     1. FINDING the archive — the operator routinely has two pending, and
#        `land.sh`'s glob took whichever sorted first.
#     2. DISCOVERING the halves — `land.sh` takes them as arguments, so the
#        operator had to know that a given tarball was "dtp otv4" and in which
#        order. A menu item cannot ask him that.
#     3. ORDERING them — a two-repo delivery whose second half CITES the first
#        (r277's otv4 half gates on r247's GENESIS row) must not land backwards.
#
#   ⚠️ IT EXECS THE LANDER FROM THE TARBALL, NOT FROM THE REPO, when the
#   archive carries one. That is deliberate and it is r235's design: a delivery
#   that improves the lander must be landed BY the improved lander, or the
#   improvement can never be exercised on its own delivery. The repo copy is
#   the FALLBACK, which is also what makes every archive built before r278 —
#   including ones already sitting in /home/ubuntu — still land through this.
#
#   ⚠️ IT PROMPTS RATHER THAN GUESSING when more than one tarball is present.
#   The alternative is `head -1`, which is the defect r278 fixes one file over:
#   a deploy that silently picks one of two is a deploy that eventually lands
#   the wrong one and then deletes the other.
#
#   ⚠️ NOTHING HERE VERIFIES ANYTHING. Every gate lives in `land.sh` and
#   `check_land_discipline.py`. A wrapper that re-implemented one of them would
#   be a second answer to a question that already has one (WA §35), and the
#   copy people trust is the one they invoke.
#
# Usage:
#   bash tools/deploy.sh              # find, prompt if needed, land everything
#   bash tools/deploy.sh --dry        # show what it WOULD land, touch nothing
set -u

HOME_DIR="${HOME:-/home/ubuntu}"
# 🔴 A UNIQUE STAGING DIR PER RUN, AND THE REASON IS NOT TIDINESS. A fixed
# /tmp/land is shared state: the lander's own selftest invokes this script, and
# a nested run would `rm -rf` the staging of the delivery currently landing —
# destroying an in-flight deploy from inside its own verification. Same class as
# a self-replacing script, which r235 already had to solve once.
# LAND_STAGE overrides it so a caller can point somewhere it controls.
STAGE="${LAND_STAGE:-$(mktemp -d /tmp/land.XXXXXX)}"
DRY=0
[ "${1:-}" = "--dry" ] && DRY=1

say() { printf '  %s\n' "$*"; }

echo "======================================================"
echo " DEPLOY — land a tarball from $HOME_DIR"
echo "======================================================"

# ── 1. FIND ────────────────────────────────────────────────────────────────
# ⚠️ `.tar` AND `.tar.gz` BOTH, because the `.gz` is stripped in transit
# sometimes and not others (WA §15, amended 2026-08-24: the strip is not an
# invariant). Newest first, so the prompt's default is the obvious one.
mapfile -t ARCS < <(ls -1t "$HOME_DIR"/*.tar "$HOME_DIR"/*.tar.gz 2>/dev/null)
if [ "${#ARCS[@]}" -eq 0 ]; then
  say "no .tar or .tar.gz in $HOME_DIR — nothing to land."
  exit 1
fi

ARCHIVE="${ARCS[0]}"
if [ "${#ARCS[@]}" -gt 1 ]; then
  echo
  say "${#ARCS[@]} archives present. Which one?"
  i=0
  for a in "${ARCS[@]}"; do
    i=$((i+1)); printf '    %d) %s  (%s)\n' "$i" "$(basename "$a")" \
      "$(date -r "$a" '+%b %d %H:%M' 2>/dev/null)"
  done
  printf '    0) cancel\n'
  read -r -p "  choice [1]: " pick
  pick="${pick:-1}"
  [ "$pick" = "0" ] && { say "cancelled — nothing touched."; exit 1; }
  case "$pick" in
    ''|*[!0-9]*) say "not a number — cancelled."; exit 1 ;;
  esac
  [ "$pick" -ge 1 ] && [ "$pick" -le "${#ARCS[@]}" ] || { say "out of range — cancelled."; exit 1; }
  ARCHIVE="${ARCS[$((pick-1))]}"
fi
say "archive: $ARCHIVE"

# ── 2. UNPACK ──────────────────────────────────────────────────────────────
# `tar xf`, never `xzf` — it sniffs the compression, and the arriving NAME may
# lie about it. The 2026-07-25 breakage was the extract flag, not the payload.
# A stale staging dir is removed first: `tar xf` over one silently leaves the
# previous delivery's files beside the new ones, which is the shape of "the fix
# appears not to have shipped".
# The dir may already exist (mktemp made it, or LAND_STAGE named it); empty it
# so a previous delivery's files cannot sit beside this one's — that is the
# shape of "the fix appears not to have shipped".
rm -rf "${STAGE:?}"/* "${STAGE:?}"/.[!.]* 2>/dev/null
mkdir -p "$STAGE"
tar xf "$ARCHIVE" -C "$STAGE" || { say "EXTRACT FAILED — nothing staged."; exit 1; }

# ── 3. DISCOVER AND ORDER THE HALVES ───────────────────────────────────────
# A half is a directory carrying a land.spec. Anything else in the archive is
# not a half — the lander itself, most obviously — and saying so beats assuming
# every directory is one.
declare -a HALVES=()
for dir in "$STAGE"/*/; do
  [ -f "${dir}land.spec" ] || continue
  h="$(basename "$dir")"
  ord="$(grep -m1 '^ORDER ' "${dir}land.spec" 2>/dev/null | cut -d' ' -f2)"
  case "$ord" in ''|*[!0-9]*) ord=50 ;; esac
  HALVES+=("$ord|$h")
done
if [ "${#HALVES[@]}" -eq 0 ]; then
  say "this archive carries no half with a land.spec."
  say "A delivery with no content gate is the one you most want stopped."
  say "staging KEPT at $STAGE so nothing has to be re-downloaded."
  exit 1
fi
mapfile -t ORDERED < <(printf '%s\n' "${HALVES[@]}" | sort -t'|' -k1,1n -k2,2 | cut -d'|' -f2)
say "halves: ${ORDERED[*]}"
for h in "${ORDERED[@]}"; do
  rev="$(grep -m1 '^REV ' "$STAGE/$h/land.spec" | cut -d' ' -f2-)"
  say "  $h -> ${rev:-<no REV — this half will be refused>}"
done

# ── 4. HAND OFF ────────────────────────────────────────────────────────────
# 🔑 THE LANDER FROM THE ARCHIVE WINS. A delivery that improves land.sh has to
# be landed by the improved copy or the improvement is never exercised on the
# one delivery that could prove it. The repo copy is the fallback, which is
# what keeps archives cut before r278 landing through this item unchanged.
LANDER="$STAGE/land.sh"
SRC="the archive"
if [ ! -f "$LANDER" ]; then
  LANDER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/land.sh"
  SRC="this checkout (the archive carries none)"
fi
say "lander: $SRC"

if [ "$DRY" = "1" ]; then
  echo
  say "--dry: nothing extracted into a repo, nothing committed, nothing deleted."
  say "staging left at $STAGE for inspection."
  exit 0
fi

# LAND_ARCHIVE names the file so the lander's cleanup deletes the one that was
# actually landed rather than whichever its own glob happens to match first.
echo
LAND_ARCHIVE="$ARCHIVE" bash "$LANDER" "${ORDERED[@]}"
exit $?
