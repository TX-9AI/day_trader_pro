# day_trader_pro/instance_registry.py — v0.2.0
# v0.2.0 (2026-10-03) — r457 / OPS.64. THE FLEET IS THE INSTANCE MAP, FOR EVERY
#   READER. Operator: *"How can we reroute all those non-automatic tasks to also
#   consult the instance map so it truly is completely automatic?"* `discover()`
#   with NO symbol list now means the tagged fleet (discover_fleet), and
#   `fleet_members()` is the one answer to "which boxes exist". config.UNIVERSE
#   is the FALLBACK, used only when the map cannot be read or reads empty, and
#   that fallback is PRINTED every time — never silent. Every caller that passed
#   config.UNIVERSE now passes nothing, so untagging a box removes it from the
#   backfill, harvest, standings, the shutdown sweep and wake_and_bake's count
#   with no list edit. Pinned by tests/check_fleet_from_map.py.
# v0.1.1 (2026-09-24) — r423 / OPS.47. ADD `discover_fleet()`: the map with no
#   symbol list handed in. `discover(symbols)` survives for callers that want a
#   named subset; the morning wake and the close both use the new one so they
#   cannot disagree about who is out there. Operator pins still outrank
#   discovery, unchanged — a pin is an operator decision and a tag is not.
"""
Maps trading symbols -> EC2 instance IDs by reading the fleet's tag "Name".

The control server never hardcodes instance IDs. Every run it can rediscover
the fleet from tags. A local cache (data/instance_map.json) records the last
known-good mapping so we can:
  - detect drift (an instance ID changed => you retired/replaced a box), and
  - resolve quickly without a describe call on the hot path if desired.

Manual override ("swap"): if discovery is ever ambiguous, or you want to pin a
symbol to a specific instance ID, mark it pinned. Pinned entries are never
overwritten by discovery.

CLI:
    python instance_registry.py show
    python instance_registry.py reconcile
    python instance_registry.py swap
"""

import json
import os
import sys
from datetime import datetime, timezone

import config
import ec2ops


# --------------------------------------------------------------------------
# Cache load/save
# --------------------------------------------------------------------------
def load_map():
    try:
        with open(config.INSTANCE_MAP_PATH, "r") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"instances": {}, "updated_at": None}


def save_map(m):
    os.makedirs(config.DATA_DIR, exist_ok=True)
    m["updated_at"] = datetime.now(timezone.utc).isoformat()
    with open(config.INSTANCE_MAP_PATH, "w") as fh:
        json.dump(m, fh, indent=2)


# --------------------------------------------------------------------------
# Discovery
# --------------------------------------------------------------------------
def discover_fleet():
    """The live fleet, DISCOVERED BY TAG. -> {symbol: {...}}.

    🔑 r423 — the counterpart to `discover()`, which resolves a LIST. This asks
    AWS what carries `config.FLEET_TAG_KEY=FLEET_TAG_VALUE` and returns that.
    Pinned cache entries still win, so a hand-pinned replacement instance is
    honoured exactly as it is in `discover()`.
    ⚠️ A BOX WITH THE TAG BUT NO Name TAG IS SKIPPED BY ec2ops, because the
    symbol IS the Name and an unnamed box cannot be addressed.
    """
    cache = load_map()
    pinned = {s: r for s, r in cache["instances"].items() if r.get("pinned")}
    found = ec2ops.describe_by_tag()
    for sym, rec in pinned.items():
        found[sym] = rec                 # a pin outranks discovery
    return found


def discover(symbols=None):
    """
    Query EC2 for the given symbols (default: full universe) and return a
    fresh {symbol: {"instance_id","state"}} dict. Pinned entries from the
    cache are preserved and take precedence over discovery.
    """
    if not symbols:
        fleet = _fleet_or_none()
        if fleet:
            return fleet, {}
        symbols = list(config.UNIVERSE)
    cache = load_map()
    pinned = {s: r for s, r in cache["instances"].items() if r.get("pinned")}

    to_discover = [s for s in symbols if s not in pinned]
    discovered = ec2ops.describe_by_names(to_discover)
    ambiguous = discovered.pop("_ambiguous", {})

    result = {}
    for s in symbols:
        if s in pinned:
            result[s] = pinned[s]
        elif s in discovered:
            rec = discovered[s]
            rec["pinned"] = False
            if s in ambiguous:
                rec["ambiguous_candidates"] = ambiguous[s]
            result[s] = rec
    return result, ambiguous


def _fleet_or_none():
    """The tagged fleet, or None (with the reason printed) when it cannot be
    used — the caller then falls back to config.UNIVERSE BY NAME."""
    try:
        fleet = discover_fleet()
    except Exception as exc:                                     # noqa: BLE001
        print(f"  [fleet] instance map unavailable ({type(exc).__name__}); "
              f"falling back to config.UNIVERSE ({len(config.UNIVERSE)})")
        return None
    if not fleet:
        print(f"  [fleet] instance map returned NO tagged boxes; falling back "
              f"to config.UNIVERSE ({len(config.UNIVERSE)})")
        return None
    return fleet


def fleet_members():
    """Which boxes exist — the tagged fleet, sorted. Never empty unless
    config.UNIVERSE is (the fallback, printed when used)."""
    fleet = _fleet_or_none()
    return sorted(fleet) if fleet else sorted(config.UNIVERSE)


def resolve(symbols):
    """
    Return {symbol: instance_id} for symbols we can map, plus a list of any
    symbols that could not be resolved (missing tag / terminated only).
    """
    mapping, _ = discover(symbols)
    resolved = {s: r["instance_id"] for s, r in mapping.items()}
    missing = [s for s in symbols if s not in resolved]
    return resolved, missing


def reconcile():
    """
    Rediscover the full universe, diff against the cache, persist, and return
    a human-readable summary of changes.
    """
    cache = load_map()
    old = cache["instances"]
    fresh, ambiguous = discover()        # r457: the map, not the list

    added, changed, removed = [], [], []
    for s, rec in fresh.items():
        if s not in old:
            added.append((s, rec["instance_id"]))
        elif old[s].get("instance_id") != rec["instance_id"]:
            changed.append((s, old[s].get("instance_id"), rec["instance_id"]))
    for s in old:
        if s not in fresh and not old[s].get("pinned"):
            removed.append((s, old[s].get("instance_id")))

    # Preserve pinned entries verbatim; merge the rest.
    merged = {s: r for s, r in old.items() if r.get("pinned")}
    merged.update(fresh)
    save_map({"instances": merged, "updated_at": None})
    return {"added": added, "changed": changed, "removed": removed,
            "ambiguous": ambiguous}


def swap(symbol, new_instance_id, pin=True):
    """
    Manually point a symbol's tag at a specific instance ID. Keeps the tag
    Name the same (the symbol key is unchanged). Pinned by default so future
    discovery won't override it.
    """
    cache = load_map()
    cache["instances"][symbol] = {
        "instance_id": new_instance_id,
        "state": "unknown",
        "pinned": pin,
    }
    save_map(cache)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def _cmd_show():
    cache = load_map()
    insts = cache.get("instances", {})
    if not insts:
        print("Instance map is empty. Run 'reconcile' to populate it.")
        return
    print(f"Instance map  (updated_at={cache.get('updated_at')})")
    print(f"{'SYMBOL':<8}{'INSTANCE ID':<26}{'STATE':<10}PINNED")
    for s in sorted(insts):
        r = insts[s]
        pin = "yes" if r.get("pinned") else ""
        print(f"{s:<8}{r.get('instance_id',''):<26}"
              f"{r.get('state','?'):<10}{pin}")


def _cmd_reconcile():
    if config.MOCK_AWS:
        print("[MOCK] scanning synthetic fleet by tag Name...")
    else:
        print(f"Scanning EC2 in {config.REGION} by tag Name...")
    d = reconcile()
    for s, iid in d["added"]:
        print(f"  + {s:<8} discovered  {iid}")
    for s, old, new in d["changed"]:
        print(f"  ~ {s:<8} changed     {old} -> {new}  (retired/replaced?)")
    for s, iid in d["removed"]:
        print(f"  - {s:<8} no live instance found  (was {iid})")
    if d["ambiguous"]:
        print("  ! AMBIGUOUS (multiple live instances share a tag):")
        for s, cands in d["ambiguous"].items():
            print(f"      {s}: {cands}  -> use 'swap' to pin one")
    if not any([d["added"], d["changed"], d["removed"], d["ambiguous"]]):
        print("  (no changes)")


def _cmd_swap():
    symbol = input("Which server to edit (tag Name, e.g. NVDA): ").strip().upper()
    if not symbol:
        print("Aborted.")
        return
    cache = load_map()
    current = cache["instances"].get(symbol, {}).get("instance_id", "(none)")
    print(f"Current instance ID for {symbol}: {current}")
    new_id = input("New instance ID: ").strip()
    if not new_id:
        print("Aborted.")
        return
    keep = input(f"Keep tag name '{symbol}' the same? [Y/n]: ").strip().lower()
    if keep in ("", "y", "yes"):
        swap(symbol, new_id, pin=True)
        print(f"Pinned {symbol} -> {new_id}")
    else:
        print("Only the instance ID can be swapped here; tag name is the key. "
              "Aborted.")


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "show"
    if cmd == "show":
        _cmd_show()
    elif cmd == "reconcile":
        _cmd_reconcile()
    elif cmd == "swap":
        _cmd_swap()
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python instance_registry.py [show|reconcile|swap]")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
