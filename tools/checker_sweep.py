#!/usr/bin/env python3
"""
day_trader_pro/tools/checker_sweep.py — v1.1
v1.1  2026-11-08  dtp r531 / DOC.37 — comments only: the lander's store-path citation names the "r13 — CHECKS NEVER
      TOUCH THE BOX'S STORES" block of OTV5 tools/land.sh instead of :631 (OTV5 r76 RETIRE.1 moved it to 656-665).
v1.0  2026-10-31  dtp r520 / SAT.4 — THE SATURDAY CHECKER SWEEP, EACH CHECKER IN ITS OWN SCRATCH, DIFFED BY CHECK ID.
      The 2026-10-31 brief gave every OTV5 checker ONE shared scratch directory and ten of its thirteen OTV5 reds
      were that artefact (a trades.db created by one checker with another's schema); it also rebuilt the sweep and
      the ID diff by hand for the fourth week (its C4, C7). The lander gives each CHECK a fresh scratch
      (OTV5 tools/land.sh, the "r13 — CHECKS NEVER TOUCH THE BOX'S STORES" block); this does the same for every checker of every tree, and keeps the result as
      JSON so next week diffs file by file AND id by id.

  · interpreter: dtp's venv (numpy, pytz, tastytrade); a red under a bare python3 is an environment red.
  · each checker: cwd = its tree, a fresh mkdtemp scratch, the lander's OT_* store paths pointed into it, plus
    dtp's artefact paths (OT_FLEET_POWER_LOG, DTP_REPORTS_DIR, SATURDAY_BRIEF_LOG/LEDGER) and VERTIGO_UNATTENDED=1.
  · a red file always carries at least one ID: the FAIL ids it printed, else "rc=<n>" (124 = timed out).
  · a red whose log shows ModuleNotFoundError / ImportError is flagged env=true.
  · exit 0 when the sweep ran (a red checker is data, not a tool failure); 2 when it could not run.

Usage:
  venv/bin/python tools/checker_sweep.py --out DIR [--prior DIR] [--trees otv5,dtp] [--timeout 600]
  venv/bin/python tools/checker_sweep.py --out DIR --tree NAME=/path/to/root      # any tree (the gate uses this)
  venv/bin/python tools/checker_sweep.py --diff-only --out DIR --prior DIR
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HOME = os.path.expanduser("~")
DTP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GLOBS = ("tests/check_*.py", "tools/check_*.py", "tests/test_*.py")
TREES = {
    "otv5": os.environ.get("DTP_OTV5_DIR", os.path.join(HOME, "OTV5")),
    "dtp": DTP,
    # otv4 is frozen (docs only since r500); swept only when asked for by name.
    "otv4": os.environ.get("DTP_OTV4_DIR", os.path.join(HOME, "options-trader-v4")),
}
DEFAULT_TREES = ("otv5", "dtp")

FAIL_IDS = (
    re.compile(r"^\s*([A-Z][A-Za-z]*\d[\w.]*)\s+FAIL\b", re.M),         # "  S1   FAIL  msg"
    re.compile(r"\bFAIL(?:ED)?[:\s]+([A-Z][A-Za-z]*\d[\w.]*)\b"),       # "FAIL S1" / "FAILED: S1"
    re.compile(r"^FAILED: (.+)$", re.M),                                # "FAILED: S1, S2"
)
ENV_RED = re.compile(r"ModuleNotFoundError|ImportError: No module named")


def scratch_env(s: str) -> dict:
    """The lander's per-CHECK store paths (OTV5 tools/land.sh's r13 store block) and dtp's artefact paths, all under s."""
    os.makedirs(os.path.join(s, "tmp"), exist_ok=True)
    os.makedirs(os.path.join(s, "signal_journal"), exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k not in ("LAND_ARCHIVE", "LAND_STAGE")}
    env.update({
        "TMPDIR": os.path.join(s, "tmp"),
        "OT_TRADES_DB": os.path.join(s, "trades.db"),
        "OT_DERIVED_DB": os.path.join(s, "derived_store.db"),
        "OT_RESTING_DB": os.path.join(s, "resting_orders.db"),
        "OT_SIGNAL_JOURNAL_DIR": os.path.join(s, "signal_journal"),
        "OT_LOG_FILE": os.path.join(s, "bot.log"),
        "OT_COUNTERFACTUAL_DIR": os.path.join(s, "counterfactual"),
        "OT_FEED_DB": os.path.join(s, "feed_store.db"),
        "OT_RESTING_STOP_STATE": os.path.join(s, "resting_stop_state.json"),
        "OT_WAREHOUSE_STATE": os.path.join(s, "warehouse_state"),
        "OT_PLAN_STATES_FILE": os.path.join(s, "plan_states.json"),
        "OT_HEARTBEAT_FILE": os.path.join(s, "BOT_HEARTBEAT"),
        "OT_INSTRUMENT": os.environ.get("OT_INSTRUMENT", "QQQ"),
        "OT_FLEET_POWER_LOG": os.path.join(s, "fleet_power.log"),
        "DTP_REPORTS_DIR": os.path.join(s, "reports"),
        "SATURDAY_BRIEF_LOG": os.path.join(s, "sb.log"),
        "SATURDAY_BRIEF_LEDGER": os.path.join(s, "sb.ledger"),
        "VERTIGO_UNATTENDED": "1",
    })
    os.makedirs(env["DTP_REPORTS_DIR"], exist_ok=True)
    return env


def failing_ids(text: str, rc: int) -> list:
    ids = set()
    for rx in FAIL_IDS[:2]:
        ids.update(rx.findall(text))
    for m in FAIL_IDS[2].findall(text):
        ids.update(x.strip() for x in m.split(",") if re.fullmatch(r"[A-Z][A-Za-z]*\d[\w.]*", x.strip()))
    if rc != 0 and not ids:
        ids.add(f"rc={rc}")
    return sorted(ids) if rc != 0 else []


def interpreter() -> str:
    py = os.path.join(DTP, "venv", "bin", "python")
    return py if os.path.exists(py) else sys.executable


def sweep(trees: dict, out: str, timeout: int, keep: bool = False) -> dict:
    logs = os.path.join(out, "logs")
    os.makedirs(logs, exist_ok=True)
    py = interpreter()
    res = {"started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "py": py, "results": []}
    for name, root in trees.items():
        if not os.path.isdir(root):
            res["results"].append({"tree": name, "file": "(tree)", "rc": 2, "ids": ["TREE_MISSING"],
                                   "env": False, "secs": 0})
            continue
        files = sorted({f for g in GLOBS for f in glob.glob(os.path.join(root, g))})
        for path in files:
            rel = os.path.relpath(path, root)
            s = tempfile.mkdtemp(prefix=f"sweep-{name}-")
            t0 = time.time()
            try:
                r = subprocess.run([py, rel], cwd=root, env=scratch_env(s), capture_output=True, text=True,
                                   timeout=timeout)
                rc, text = r.returncode, (r.stdout or "") + (r.stderr or "")
            except subprocess.TimeoutExpired as e:
                rc = 124
                text = ((e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or ""))
            finally:
                if not keep:
                    shutil.rmtree(s, ignore_errors=True)
            with open(os.path.join(logs, f"{name}__{rel.replace('/', '_')}.log"), "w") as fh:
                fh.write(text)
            res["results"].append({"tree": name, "file": rel, "rc": rc, "ids": failing_ids(text, rc),
                                   "env": bool(rc and ENV_RED.search(text)), "secs": round(time.time() - t0, 1)})
    res["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(os.path.join(out, "sweep.json"), "w") as fh:
        json.dump(res, fh, indent=1, sort_keys=True)
    return res


def diff(now: dict, prior: dict) -> dict:
    a = {(r["tree"], r["file"]): r for r in now["results"]}
    b = {(r["tree"], r["file"]): r for r in prior["results"]}
    red = lambda r: r is not None and r["rc"] != 0
    d = {"newly_red": [], "green_that_was_red": [], "still_red_ids_changed": [], "still_red_same": [],
         "new_checkers": [], "gone_checkers": []}
    for k, r in sorted(a.items()):
        p = b.get(k)
        if p is None:
            d["new_checkers"].append([*k, r["rc"], r["ids"]])
        if red(r) and not red(p):
            d["newly_red"].append([*k, r["ids"], r["env"]])
        elif red(r) and red(p):
            new_ids, cleared = sorted(set(r["ids"]) - set(p["ids"])), sorted(set(p["ids"]) - set(r["ids"]))
            (d["still_red_ids_changed"] if (new_ids or cleared) else d["still_red_same"]).append(
                [*k, new_ids, cleared] if (new_ids or cleared) else [*k, r["ids"]])
        elif not red(r) and red(p):
            d["green_that_was_red"].append([*k, p["ids"]])
    d["gone_checkers"] = [list(k) for k in sorted(set(b) - set(a))]
    return d


def report(now: dict, d: dict = None) -> None:
    by = {}
    for r in now["results"]:
        t = by.setdefault(r["tree"], [0, 0])
        t[0] += 1
        t[1] += r["rc"] != 0
    print("CHECKER SWEEP " + " · ".join(f"{t}: {n} run, {rd} red" for t, (n, rd) in sorted(by.items()))
          + f"   (py {now['py']})")
    if d is None:
        print("  no prior sweep.json: every red below is listed, none can be called new")
        for r in now["results"]:
            if r["rc"]:
                print(f"  RED  {r['tree']}/{r['file']}  {','.join(r['ids'])}{'  [env]' if r['env'] else ''}")
        return
    for label, key in (("NEWLY RED", "newly_red"), ("GREEN THAT WAS RED", "green_that_was_red"),
                       ("STILL RED, IDS CHANGED", "still_red_ids_changed")):
        for row in d[key]:
            print(f"  {label}: {row[0]}/{row[1]}  " + "  ".join(
                (",".join(x) if isinstance(x, list) else ("[env]" if x is True else ""))
                for x in row[2:]).strip())
    print(f"  still red, same ids: {len(d['still_red_same'])} · new checkers: {len(d['new_checkers'])}"
          f" · gone: {len(d['gone_checkers'])}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--prior", default=None)
    ap.add_argument("--trees", default=",".join(DEFAULT_TREES))
    ap.add_argument("--tree", action="append", default=[], help="NAME=ROOT, replaces --trees")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--keep-scratch", action="store_true")
    ap.add_argument("--diff-only", action="store_true")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    if a.diff_only:
        now = json.load(open(os.path.join(a.out, "sweep.json")))
    else:
        trees = dict(t.split("=", 1) for t in a.tree) if a.tree else \
            {n: TREES[n] for n in a.trees.split(",") if n in TREES}
        if not trees:
            print("no tree to sweep", file=sys.stderr)
            return 2
        now = sweep(trees, a.out, a.timeout, a.keep_scratch)
    d = None
    pj = os.path.join(a.prior, "sweep.json") if a.prior else None
    if pj and os.path.exists(pj):
        d = diff(now, json.load(open(pj)))
        with open(os.path.join(a.out, "diff.json"), "w") as fh:
            json.dump(d, fh, indent=1)
    report(now, d)
    return 0


if __name__ == "__main__":
    sys.exit(main())
