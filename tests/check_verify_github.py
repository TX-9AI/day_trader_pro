#!/usr/bin/env python3
"""
day_trader_pro/tests/check_verify_github.py  v1.0
v1.0  2026-10-26  dtp (VER.1) — the credential check grades an OTV5 box's GitHub
      setup by what an OTV5 box IS: pull-only, no token, origin = OTV5.

🔴 WHY. The operator's run at 10:20 ET on the first OTV5 paper day: 13 of 14
boxes "GITHUB: FAIL — GitHub vars missing" (every correctly built box), and the
only SUCCESS was SOFI, the box still carrying GITHUB_REPO=TX-9AI/OTV4TEST and a
token. The verdict was exactly upside down. The Telegram probe also sent
"creds verify — ?" fourteen times: no box name.

  G1  no token, no GITHUB_REPO, public origin reachable          -> SUCCESS
  G2  no token, GITHUB_REPO == origin                            -> SUCCESS
  G3  GITHUB_REPO != origin (SOFI's OTV4TEST)                    -> FAIL, says stale
  G4  a token without OT_GIT_PUSH=1                              -> FAIL, names it
  G5  token + OT_GIT_PUSH=1 -> the authenticated call carries the token
  G6  the no-token call carries NO Authorization header
  G7  _env reads a quoted Environment="VAR=v" unit line
  G8  the Telegram probe text names the box from _env, not only os.environ
  G9  no secret value is ever in a verdict string
"""
import importlib.util
import io
import json
import os
import sys
import types

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILS = []


def check(name, ok, detail=""):
    print("  {:<4} {}  {}".format(name, "PASS" if ok else "FAIL", detail))
    if not ok:
        FAILS.append(name)


def load():
    spec = importlib.util.spec_from_file_location(
        "vcr", os.path.join(REPO, "verify_creds_remote.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


SECRET = "ghp_SECRETVALUE1234567890"


def run(m, env, origin="https://github.com/TX-9AI/OTV5.git", http=200,
        full_name="TX-9AI/OTV5"):
    seen = {}
    m._env = lambda v: env.get(v)

    class P:
        def __init__(self, out): self.stdout = out
    m.subprocess = types.SimpleNamespace(
        run=lambda cmd, **k: P(origin if "remote" in cmd else ""))

    class R(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def urlopen(req, timeout=None):
        seen["url"] = req.full_url
        seen["auth"] = req.get_header("Authorization")
        if http != 200:
            raise m.urllib.error.HTTPError(req.full_url, http, "x", {}, None)
        return R(json.dumps({"full_name": full_name}).encode())
    m.urllib.request.urlopen = urlopen
    ok, detail = m.check_github()
    return ok, detail, seen


def main():
    print("check_verify_github")
    m = load()
    if not hasattr(m, "_origin_repo"):
        check("G0", False, "verify_creds_remote has no _origin_repo (v1.0: GitHub graded by vars only)")
    ok, d, s = run(m, {})
    check("G1", ok and "pull-only" in d, d)
    ok, d, s = run(m, {"GITHUB_REPO": "TX-9AI/OTV5"})
    check("G2", ok, d)
    ok, d, s = run(m, {"GITHUB_REPO": "TX-9AI/OTV4TEST", "GITHUB_TOKEN": SECRET})
    check("G3", (not ok) and "stale" in d and "OTV4TEST" in d, d)
    ok, d, s = run(m, {"GITHUB_TOKEN": SECRET})
    check("G4", (not ok) and "pull-only" in d, d)
    ok, d, s = run(m, {"GITHUB_TOKEN": SECRET, "OT_GIT_PUSH": "1"})
    check("G5", ok and s.get("auth") == "Bearer " + SECRET, d)
    ok, d, s = run(m, {})
    check("G6", s.get("auth") is None, "auth header on no-token call: {}".format(s.get("auth") is not None))

    m2 = load()

    class P2:
        def __init__(self, out): self.stdout = out
    os.environ.pop("ZZ_TEST_VAR", None)
    m2.subprocess = types.SimpleNamespace(
        run=lambda cmd, **k: P2('Environment="ZZ_TEST_VAR=SPX"\n'))
    check("G7", m2._env("ZZ_TEST_VAR") == "SPX", repr(m2._env("ZZ_TEST_VAR")))

    src = open(os.path.join(REPO, "verify_creds_remote.py"), encoding="utf-8").read()
    probe = src.split("\"text\": f\"✅ creds verify —", 1)[-1][:80]
    check("G8", "_env('OT_INSTRUMENT')" in probe or '_env("OT_INSTRUMENT")' in probe, probe.strip()[:60])

    leaks = []
    for env in ({"GITHUB_TOKEN": SECRET}, {"GITHUB_TOKEN": SECRET, "OT_GIT_PUSH": "1"},
                {"GITHUB_TOKEN": SECRET, "GITHUB_REPO": "x/y"}):
        for http in (200, 401, 404, 500):
            ok, d, s = run(load(), env, http=http)
            if SECRET in d or SECRET[-6:] in d:
                leaks.append(d)
    check("G9", not leaks, "{} verdicts carried the secret".format(len(leaks)))

    print("")
    if FAILS:
        print("FAILED: {}".format(", ".join(FAILS)))
        return 1
    print("ALL PASS (9)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
