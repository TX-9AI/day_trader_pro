# day_trader_pro/instance_registry.py — v0.1.0
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
def discover(symbols=None):
    """
    Query EC2 for the given symbols (default: full universe) and return a
    fresh {symbol: {"instance_id","state"}} dict. Pinned entries from the
    cache are preserved and take precedence over discovery.
    """
    symbols = symbols or config.UNIVERSE
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
    fresh, ambiguous = discover(config.UNIVERSE)

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
