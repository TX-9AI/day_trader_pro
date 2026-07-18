#!/usr/bin/env bash
# rotate_env_remote.sh — RUNS ON EACH TRADING BOX (pushed + executed by the
# control-side rotate_tokens.py). v1.1 — 2026-07-18.
#
# TWO MODES:
#   (default, reads stdin)  rotate: update the Environment= lines for the vars
#                           supplied as KEY=VALUE on stdin; restart services.
#   --audit                 report which vars are set (non-secrets shown in full;
#                           secrets shown as SET/MISSING + len/last-4 fingerprint,
#                           never the value) and flag bot/feed cred drift.
#
# WHY THIS DESIGN:
#   Secrets are stored as inline `Environment=` lines in two systemd units:
#     - optionsbot.service    (TT_*, TELEGRAM_*, GITHUB_TOKEN, GITHUB_REPO)
#     - candle-feed.service   (TT_* only)
#   This script updates ONLY the vars it is given NEW values for, leaving every
#   other line (WorkingDirectory, ExecStart, OT_*, unchanged secrets) byte-exact.
#
#   SECRETS NEVER TOUCH ARGV. The new values arrive on STDIN as KEY=VALUE lines
#   (one per var being rotated). Nothing sensitive is a command argument, so
#   nothing shows in `ps`, the journal, or shell history on either side.
#   The values are held in shell variables for the life of this process only.
#
#   ATOMIC + SAFE: each unit is rewritten to a temp file, mode 600, then moved
#   into place. If sed produces an empty/short file we abort before moving, so a
#   botched edit can never leave a truncated unit. daemon-reload + restart last.
set -uo pipefail

BOT_UNIT="/etc/systemd/system/optionsbot.service"
FEED_UNIT="/etc/systemd/system/candle-feed.service"

# All variables the fleet provisions (must match bootstrap.example.sh).
ALL_VARS=(OT_INSTRUMENT TT_CLIENT_SECRET TT_REFRESH_TOKEN TT_ACCOUNT_NUMBER \
          TELEGRAM_TOKEN TELEGRAM_CHAT_ID GITHUB_REPO GITHUB_TOKEN)

# ── AUDIT MODE ────────────────────────────────────────────────────────────────
# Invoked with a single arg "--audit". Reports, per variable, whether it is SET
# in the bot unit and (for TT_* creds) the feed unit — NAMES AND PRESENCE ONLY,
# never values. Non-secret vars (OT_INSTRUMENT, TELEGRAM_CHAT_ID, GITHUB_REPO)
# ARE shown in full since they are not sensitive and their value is the useful
# audit fact (which symbol is this box? which repo?). Secrets show SET/MISSING
# plus a short fingerprint (length + last 4 chars) so you can tell whether a
# rotation took without ever exposing the secret.
if [ "${1:-}" = "--audit" ]; then
    [ -f "$BOT_UNIT" ] || { echo "AUDIT_ERR: $BOT_UNIT absent"; exit 1; }
    for var in "${ALL_VARS[@]}"; do
        line="$(grep "^Environment=${var}=" "$BOT_UNIT" 2>/dev/null | head -1)"
        val="${line#Environment=${var}=}"
        case "$var" in
            OT_INSTRUMENT|TELEGRAM_CHAT_ID|GITHUB_REPO)
                # non-secret — show the value
                if [ -n "$line" ]; then echo "  ${var}=${val}"
                else echo "  ${var}: MISSING"; fi ;;
            *)
                # secret — show presence + fingerprint only
                if [ -n "$line" ] && [ -n "$val" ]; then
                    len="${#val}"; last4="${val: -4}"
                    echo "  ${var}: SET (len=${len}, …${last4})"
                else
                    echo "  ${var}: MISSING"
                fi ;;
        esac
    done
    # Flag drift: TT_* creds must match between the two units or the feed and
    # bot authenticate differently. Compare fingerprints, not values.
    if [ -f "$FEED_UNIT" ]; then
        for var in TT_CLIENT_SECRET TT_REFRESH_TOKEN TT_ACCOUNT_NUMBER; do
            b="$(grep "^Environment=${var}=" "$BOT_UNIT"  2>/dev/null | head -1)"; b="${b#Environment=${var}=}"
            f="$(grep "^Environment=${var}=" "$FEED_UNIT" 2>/dev/null | head -1)"; f="${f#Environment=${var}=}"
            if [ "$b" != "$f" ]; then
                echo "  DRIFT: ${var} differs between bot and feed units"
            fi
        done
    else
        echo "  NOTE: $FEED_UNIT absent (no candle-feed on this box?)"
    fi
    exit 0
fi

# ── read KEY=VALUE lines from stdin into an assoc array ───────────────────────
declare -A NEW
while IFS= read -r line; do
    [ -z "$line" ] && continue
    key="${line%%=*}"
    val="${line#*=}"
    NEW["$key"]="$val"
done
# stdin is now exhausted; values live only in NEW[] for this process.

if [ ${#NEW[@]} -eq 0 ]; then
    echo "NOCHANGE: no values supplied"
    exit 0
fi

# ── replace one Environment= line in a file, preserving everything else ───────
# Uses a python one-liner for the substitution so we never have to escape sed
# metacharacters that appear in tokens (/, &, +, =). Reads the secret from an
# env var passed to python's os.environ (NOT argv), value gone when python exits.
replace_var() {
    local file="$1" var="$2" value="$3"
    [ -f "$file" ] || { echo "SKIP: $file absent"; return 0; }
    # Only act if the unit actually declares this var.
    if ! grep -q "^Environment=${var}=" "$file"; then
        return 0
    fi
    local tmp; tmp="$(mktemp)"
    # shellcheck disable=SC2016
    RV_VALUE="$value" python3 - "$file" "$var" > "$tmp" <<'PYEOF'
import os, sys
path, var = sys.argv[1], sys.argv[2]
new = os.environ["RV_VALUE"]
out = []
prefix = f"Environment={var}="
for ln in open(path):
    if ln.startswith(prefix):
        out.append(f"{prefix}{new}\n")
    else:
        out.append(ln)
sys.stdout.write("".join(out))
PYEOF
    # Safety: refuse to install a suspiciously small result.
    if [ ! -s "$tmp" ] || [ "$(wc -l < "$tmp")" -lt 5 ]; then
        echo "ABORT: rewrite of $file looked truncated; leaving original"
        rm -f "$tmp"
        return 1
    fi
    sudo cp "$tmp" "$file"
    sudo chmod 600 "$file"
    rm -f "$tmp"
    return 0
}

CHANGED=0
FAIL=0

# Map each rotated key to the units that carry it.
for key in "${!NEW[@]}"; do
    val="${NEW[$key]}"
    case "$key" in
        TT_CLIENT_SECRET|TT_REFRESH_TOKEN|TT_ACCOUNT_NUMBER)
            replace_var "$BOT_UNIT"  "$key" "$val" || FAIL=1
            replace_var "$FEED_UNIT" "$key" "$val" || FAIL=1
            CHANGED=1 ;;
        TELEGRAM_TOKEN|TELEGRAM_CHAT_ID|GITHUB_TOKEN|GITHUB_REPO)
            replace_var "$BOT_UNIT"  "$key" "$val" || FAIL=1
            CHANGED=1 ;;
        *)
            echo "WARN: unknown key $key ignored" ;;
    esac
done

if [ "$FAIL" -ne 0 ]; then
    echo "ERROR: at least one unit rewrite aborted; NOT restarting services"
    exit 1
fi

if [ "$CHANGED" -eq 1 ]; then
    sudo systemctl daemon-reload
    # Restart feed first (bot Wants= it), then the bot.
    sudo systemctl restart candle-feed.service 2>/dev/null || echo "WARN: candle-feed restart returned nonzero"
    sudo systemctl restart optionsbot.service  2>/dev/null || echo "WARN: optionsbot restart returned nonzero"
    # Report health without leaking anything.
    sleep 2
    bot_state="$(systemctl is-active optionsbot.service 2>/dev/null)"
    feed_state="$(systemctl is-active candle-feed.service 2>/dev/null)"
    echo "OK: rotated=${#NEW[@]} bot=${bot_state} feed=${feed_state}"
else
    echo "NOCHANGE"
fi
