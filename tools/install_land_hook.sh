#!/usr/bin/env bash
# day_trader_pro/tools/install_land_hook.sh — v1.0
# v1.0 (2026-08-29) — dtp r225. Installs tools/check_land_discipline.py as a
#   pre-commit hook in a named checkout, so a HAND-MADE commit gets the same
#   version/changelog/map discipline the land command applies.
#
# ⚠️ THIS IS THE SECOND NET, NOT THE FIRST. The land command runs the checker
#   in-band and FAILS CLOSED — nothing stages on a red. This hook exists only
#   for commits made outside that path. Installing it is optional; not
#   installing it changes nothing about a landed delivery.
#
# ⚠️ AND IT IS A PER-CLONE INSTALL, WHICH IS A COST WORTH NAMING. .git/hooks
#   is not tracked and not cloned, so a fresh checkout has no hook until this
#   runs again. That is exactly the "a step that must be remembered never
#   happens" failure (WORKING_AGREEMENT §34) — which is why the hook is the
#   backup and the land command is the gate, and never the other way round.
#
# Usage:  bash tools/install_land_hook.sh ~/options-trader-v4
#         bash tools/install_land_hook.sh ~/day_trader_pro
#         git commit --no-verify        # the escape hatch, when you mean it
set -u
T="$1"
[ -d "$T/.git" ] || { echo "not a git checkout: $T"; exit 1; }
DTP="$(cd "$(dirname "$0")/.." && pwd)"
H="$T/.git/hooks/pre-commit"
cat > "$H" <<HOOK
#!/usr/bin/env bash
# installed by day_trader_pro/tools/install_land_hook.sh v1.0
C="$DTP/tools/check_land_discipline.py"
if [ ! -f "\$C" ]; then
  # ⚠️ WARN AND ALLOW, DELIBERATELY. Blocking every commit because a helper in
  # another repo is missing would be a red that means ENVIRONMENT, not
  # CONTENT — the CV.1 failure that teaches you to skip red runs. The land
  # command still fails closed, so nothing reaches origin unverified.
  echo "pre-commit: check_land_discipline.py not found at \$C — NOT VERIFIED"
  exit 0
fi
python3 "\$C" --repo "$T" --hook || {
  echo
  echo "pre-commit: land discipline FAILED. Fix the header/changelog, or"
  echo "            'git commit --no-verify' if you mean to commit anyway."
  exit 1
}
HOOK
chmod +x "$H"
echo "installed: $H"
echo "  -> $DTP/tools/check_land_discipline.py --repo $T --hook"
