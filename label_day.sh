#!/usr/bin/env bash
# label_day.sh v1.1 — 2026-08-19 (v1.0 2026-07-18) — EOD session labeling for Layer-1 Tier-B acceptance.
#
# WHY: REPLAY_VALIDATION.md §2 Tier B has sat at ❌ since 07-09 not for lack of
# tape but for lack of LABELS — each acceptance row needs a session whose type
# is known from independent evidence, tagged while the operator still remembers
# it. This is the 10-minute EOD habit that converts harvested tape from
# "stored" to "usable". Control-box only; touches nothing in the EOD conductor
# chain; append-only to its own file.
#
# USAGE:
#   ./label_day.sh                                  # interactive, today
#   ./label_day.sh 2026-07-20                       # interactive, a date
#   ./label_day.sh 2026-07-20 TREND:GOOGL,MU PIN:QQQ SWEEP:SPX NOTE:"fed day"
#   ./label_day.sh --show                           # print all labels
#   ./label_day.sh --gaps                           # Tier-B checklist vs labels so far
#
# TAGS (repeatable, SYMBOLS comma-separated):
#   TREND:SYMS   genuine trend day for these symbols     (Tier-B TRENDING — tape gap)
#   PIN:SYMS     coil-into-pin session                   (Tier-B COMPRESSION — partial)
#   BREAKOUT:SYMS clean breakout w/ momentum carry       (Tier-B BREAKOUT — partial)
#   SWEEP:SYMS   mapper-confirmed named-zone reclaim     (Tier-B SWEEP — tape gap)
#   CHOP         whole session is chop/flat (still useful: flat-angle base rates)
#   NOTE:"..."   freeform context
#
# OUTPUT: appends one JSON line per invocation to reports/session_labels.jsonl
# (latest line per date wins downstream). The offline calibration reads this
# file to select fit vs holdout sessions and to fill the Tier-B table.
set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$DIR/reports/session_labels.jsonl"
mkdir -p "$DIR/reports"

TODAY="$(TZ=America/New_York date +%F)"

show_labels() {
  [ -f "$OUT" ] || { echo "no labels yet ($OUT)"; return; }
  cat "$OUT"
}

show_gaps() {
  echo "── Tier-B shopping list (REPLAY_VALIDATION.md §2) ─────────────"
  for tag in TREND SWEEP PIN BREAKOUT; do
    local_n=0
    [ -f "$OUT" ] && { local_n=$(grep -c "\"$tag\"" "$OUT" 2>/dev/null); local_n=${local_n:-0}; }
    # ── v1.1 (2026-08-19) — THE STATUS WAS A CONSTANT ────────────────────
    # `need` was a hardcoded string per tag: TREND printed "tape gap — need
    # >=1 genuine trend day" whether the count was 0, 28 or 280. **The count
    # was computed; the verdict beside it was decoration.** The row therefore
    # looked permanently open, which sent three separate investigations
    # hunting for a code blocker (1h starvation, an A2 regression, an
    # architectural veto) — all real defects, none of them the reason this
    # line said ❌.
    # It now reports what the file actually holds.
    if [ "${local_n:-0}" -ge 1 ]; then
      case "$tag" in
        TREND)    need="✅ have ${local_n} — verify A2 PASSES on the session you rely on";;
        SWEEP)    need="✅ have ${local_n} — verify a mapper-confirmed reclaim in one";;
        PIN)      need="✅ have ${local_n} — a clean QQQ/SPX pin day is still the strongest";;
        BREAKOUT) need="✅ have ${local_n} — more symbol variety still welcome";;
      esac
    else
      case "$tag" in
        TREND)    need="❌ none labeled — need ≥1 genuine trend day";;
        SWEEP)    need="❌ none labeled — need ≥1 mapper-confirmed reclaim";;
        PIN)      need="❌ none labeled — need a clean QQQ/SPX pin day";;
        BREAKOUT) need="❌ none labeled — need ≥1 clean breakout with carry";;
      esac
    fi
    printf "  %-9s labeled sessions: %-3s  (%s)\n" "$tag" "$local_n" "$need"
  done
  echo "  Flat-angle sweep needs ≥ several distinct labeled sessions (any tag counts)."
  echo
  echo "  ⚠️ A LABEL IS NOT ACCEPTANCE. This counts what a human TAGGED; it does"
  echo "     not check that the session passes its Tier-B criterion. TRENDING"
  echo "     needs the label AND \"RANGING vetoed through it\" — measured by A2."
  echo "     Measured 2026-08-19 on three 97-100%-dominant sessions:"
  echo "       AVGO 08-14  RANGING p90 0.305  ->  A2  2.6%  PASS"
  echo "       META 08-18  RANGING p90 0.615  ->  A2 12.8%  FAIL"
  echo "       TSLA 08-04  RANGING p90 0.615  ->  A2 14.0%  FAIL"
  echo "     **DOMINANCE DOES NOT PREDICT THE VETO; RANGING p90 DOES.** Pick"
  echo "     candidates on p90 (~0.3, not ~0.6), then confirm with A2."
}

case "${1:-}" in
  --show) show_labels; exit 0;;
  --gaps) show_gaps;  exit 0;;
esac

# ── date argument ─────────────────────────────────────────────
DATE="$TODAY"
if [[ "${1:-}" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then DATE="$1"; shift; fi

declare -A TAGS
NOTE=""
CHOP="false"

parse_tag() {
  local t="$1"
  case "$t" in
    TREND:*|PIN:*|BREAKOUT:*|SWEEP:*)
      local k="${t%%:*}"; local v="${t#*:}"
      TAGS[$k]="${v}";;
    CHOP) CHOP="true";;
    NOTE:*) NOTE="${t#NOTE:}";;
    *) echo "unrecognized tag: $t (see header)"; exit 1;;
  esac
}

if [ $# -gt 0 ]; then
  for a in "$@"; do parse_tag "$a"; done
else
  # ── interactive: prompt against the checklist ───────────────
  echo "Labeling $DATE — enter comma-separated symbols per class (empty = none)."
  show_gaps; echo ""
  read -rp "  TREND symbols:    " v; [ -n "$v" ] && TAGS[TREND]="$v"
  read -rp "  SWEEP symbols:    " v; [ -n "$v" ] && TAGS[SWEEP]="$v"
  read -rp "  PIN symbols:      " v; [ -n "$v" ] && TAGS[PIN]="$v"
  read -rp "  BREAKOUT symbols: " v; [ -n "$v" ] && TAGS[BREAKOUT]="$v"
  read -rp "  Whole day chop? [y/N]: " v; [[ "$v" =~ ^[Yy] ]] && CHOP="true"
  read -rp "  Note (optional):  " NOTE
fi

# ── build the JSON row (no jq dependency) ─────────────────────
json_syms() {  # "A,B, C" -> ["A","B","C"]
  local s="${1// /}"; local out="["; local first=1
  IFS=',' read -ra arr <<< "$s"
  for x in "${arr[@]}"; do
    [ -z "$x" ] && continue
    [ $first -eq 0 ] && out+=","
    out+="\"${x^^}\""; first=0
  done
  echo "${out}]"
}

ROW="{\"date\":\"$DATE\",\"labeled_at\":\"$(TZ=America/New_York date -Is)\""
for k in TREND SWEEP PIN BREAKOUT; do
  [ -n "${TAGS[$k]:-}" ] && ROW+=",\"$k\":$(json_syms "${TAGS[$k]}")"
done
ROW+=",\"CHOP\":$CHOP"
[ -n "$NOTE" ] && ROW+=",\"note\":\"${NOTE//\"/\\\"}\""
ROW+="}"

echo "$ROW" >> "$OUT"
echo ""
echo "labeled: $ROW"
echo "-> $OUT"
show_gaps
