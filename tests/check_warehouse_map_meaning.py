#!/usr/bin/env python3
"""tests/check_warehouse_map_meaning.py — v1.0
v1.0 (2026-11-08) — dtp r541 / CAP.1 (OTV5 r94). OFFLINE (no bucket call): the warehouse map's MEANING table names
  every prefix OTV5 tools/capture_all.py writes, each row cites its writer, and docs/WAREHOUSE_MAP.md (generated from the
  bucket) carries a row for each of them.

  W1  MEANING has raw/market_metrics, raw/chain_rest, raw/chain_listing, raw/corporate_events, raw/candles_full
  W2  each of those rows cites OTV5 tools/capture_all.py as its writer and says what it holds
  W3  docs/WAREHOUSE_MAP.md has a table row for each of the five prefixes
"""
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAP = ["raw/market_metrics", "raw/chain_rest", "raw/chain_listing", "raw/corporate_events", "raw/candles_full"]
FAILED = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  -- {detail}"))
    if not ok:
        FAILED.append(name.split()[0])


def main():
    src = open(os.path.join(ROOT, "tools", "warehouse_map.py")).read()
    tree = ast.parse(src)
    meaning = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "MEANING" for t in node.targets):
            meaning = ast.literal_eval(node.value)
    check("W1 MEANING names the five capture prefixes", meaning is not None and all(k in meaning for k in CAP),
          str([k for k in CAP if not meaning or k not in meaning]))
    check("W2 each cites OTV5 tools/capture_all.py and says what it holds",
          meaning is not None and all("tools/capture_all.py" in meaning[k][0] and len(meaning[k][1]) > 20
                                      for k in CAP if k in meaning))
    doc = open(os.path.join(ROOT, "docs", "WAREHOUSE_MAP.md")).read()
    check("W3 docs/WAREHOUSE_MAP.md has a row for each", all(f"| `{k}` |" in doc for k in CAP),
          str([k for k in CAP if f"| `{k}` |" not in doc]))
    print()
    print(("RED — " + ", ".join(FAILED)) if FAILED else "GREEN — 3 of 3")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
