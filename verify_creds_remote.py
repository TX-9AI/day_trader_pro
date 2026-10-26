#!/usr/bin/env python3
"""
verify_creds_remote.py — RUNS ON EACH TRADING BOX. Pushed + executed by the
control-side rotate_tokens.py (--verify, or auto after a rotation). v1.1 —
2026-10-26 (VER.1).

v1.1  2026-10-26  dtp (VER.1) — THE GITHUB CHECK KNOWS AN OTV5 BOX NEVER PUSHES. The
      operator's run at 10:20 ET on the first OTV5 paper day: 13 of 14 boxes
      "GITHUB: FAIL — GitHub vars missing" and the one SUCCESS (SOFI) was the box
      still carrying a stale GITHUB_REPO=TX-9AI/OTV4TEST and a token. An OTV5 box
      holds NO token by design (bootstrap: GITHUB_TOKEN empty unless OT_GIT_PUSH=1),
      so the check now reads the box's own origin and grades:
        no token, GITHUB_REPO absent or == origin, origin public + reachable  -> SUCCESS
        GITHUB_REPO set and != origin                                     -> FAIL (stale)
        a token on a box without OT_GIT_PUSH=1                            -> FAIL (a box never pushes)
        token + push box -> the authenticated call, as v1.0.
      Also: the Telegram probe names the box (it read only the ambient env and sent
      "creds verify — ?"), and `_env` reads quoted Environment="VAR=..." unit lines.
v1.0  2026-07-18.

WHAT IT PROVES (functional, not just "landed"):
  Landing-verification (rotate_tokens --audit) shows a var is SET with the right
  length/last-4. This goes further: it proves the landed values actually WORK,
  by exercising each credential against its real service — READ-ONLY, no trades,
  no messages that matter, nothing that can move money.

  TASTYTRADE (client_secret + refresh_token + account_number):
    Mirrors data/tasty_client.py EXACTLY — Session(client_secret, refresh_token)
    then Account.get(session, account_number). That is the bot's ENTIRE auth
    path (it makes no balances call), so a pass means the OAuth refresh
    handshake succeeded, the account number is valid, and the token has account
    scope. Then confirm the returned account number matches the unit. If the
    refresh token was rotated to a dead value, THIS is where you find out — now,
    not at the next trade. No balances read: the bot never makes one, and
    guessing the SDK's balances method across versions only invents false
    failures.

  TELEGRAM (token + chat_id):
    getMe (proves the bot token is live) + a single sendMessage to chat_id
    (proves the chat id is reachable). One real message: "✅ creds verify".

  GITHUB (token + repo):
    One authenticated API call to /repos/<owner>/<repo>. 200 = token valid and
    has access to the repo the box pulls from. 401/404 = dead or wrong scope.

  Reads the vars from THIS PROCESS'S ENVIRONMENT — which systemd populates from
  the same Environment= lines the bot uses — so it tests exactly what the bot
  will get. (The service manager env is inherited when this runs under the same
  user; if a var is missing from the ambient env we read it from the unit.)

OUTPUT CONTRACT:
  Prints one line per credential group: "<GROUP>: SUCCESS" or "<GROUP>: FAIL —
  <reason>". Final line is "VERIFY: SUCCESS" iff every checked group passed,
  else "VERIFY: FAIL". Never prints a secret value. Exit 0 on all-pass, 1 on any
  fail, 2 on setup error.

  --skip-telegram / --skip-github / --skip-tt let the caller narrow the check to
  only the creds that were actually rotated.
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error

REPO_DIR = os.path.expanduser("~/options-trader")
BOT_UNIT = "/etc/systemd/system/optionsbot.service"


def _env(var):
    """Value from ambient env, falling back to the bot unit's Environment= line
    (so this works whether or not systemd exported it to our process).
    v1.1: the unit writes both Environment=VAR=v and Environment="VAR=v"."""
    v = os.environ.get(var)
    if v:
        return v
    try:
        out = subprocess.run(
            ["sudo", "grep", "-E", f'^Environment="?{var}=', BOT_UNIT],
            capture_output=True, text=True, timeout=10).stdout.strip()
        if out:
            line = out.splitlines()[0]
            return line.split("=", 2)[2].rstrip('"') or None
    except Exception:
        pass
    return None


def _origin_repo():
    """owner/repo of the box's own checkout origin (credentials stripped), or None."""
    try:
        url = subprocess.run(["git", "-C", REPO_DIR, "remote", "get-url", "origin"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return None
    import re
    m = re.search(r"github\.com[:/]+([^/]+/[^/]+?)(?:\.git)?/?$", url)
    return m.group(1) if m else None


def check_tastytrade():
    """Mirror data/tasty_client.py: Session -> Account.get (the bot's full auth path)."""
    cs = _env("TT_CLIENT_SECRET")
    rt = _env("TT_REFRESH_TOKEN")
    acct = _env("TT_ACCOUNT_NUMBER")
    if not (cs and rt and acct):
        return False, "TT vars missing from env/unit"
    # Import the SDK from the box's venv (this script runs under that python).
    try:
        from tastytrade import Session, Account
    except Exception as e:
        return False, f"tastytrade SDK import failed: {e}"
    # 1) OAuth refresh handshake — the exact bot path.
    try:
        session = Session(cs, rt)
    except Exception as e:
        return False, f"OAuth handshake failed (client_secret/refresh_token): {type(e).__name__}"
    # 2) Account fetch — proves the account number is valid for this session.
    #    This is the FULL proof the bot relies on: data/tasty_client.py does
    #    exactly Session(...) -> Account.get(...) and nothing more. If both
    #    succeed, the client_secret authenticated, the refresh token was
    #    accepted, and the account number is valid with read scope. We do NOT
    #    add a balances call — the bot never makes one, and guessing the SDK's
    #    balances method across versions only invents false failures.
    try:
        account = Account.get(session, acct)
    except Exception as e:
        return False, f"account {acct[-4:]} fetch failed (number or scope): {type(e).__name__}"
    # 3) Confirm the account number the session returns matches what we set.
    got = getattr(account, "account_number", None) or acct
    if str(got) != str(acct):
        return False, f"account mismatch: unit={acct[-4:]} broker={str(got)[-4:]}"
    return True, f"handshake + account fetch OK, acct …{acct[-4:]}"


def check_telegram():
    token = _env("TELEGRAM_TOKEN")
    chat = _env("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return False, "Telegram vars missing"
    # getMe — token liveness
    try:
        with urllib.request.urlopen(
                f"https://api.telegram.org/bot{token}/getMe", timeout=15) as r:
            if json.loads(r.read()).get("ok") is not True:
                return False, "getMe not ok (bad token)"
    except urllib.error.HTTPError as e:
        return False, f"getMe HTTP {e.code} (bad token)"
    except Exception as e:
        return False, f"getMe failed: {type(e).__name__}"
    # sendMessage — chat_id reachability
    try:
        data = urllib.parse.urlencode({
            "chat_id": chat,
            "text": f"✅ creds verify — {_env('OT_INSTRUMENT') or '?'}",
        }).encode()
        with urllib.request.urlopen(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data=data, timeout=15) as r:
            if json.loads(r.read()).get("ok") is not True:
                return False, "sendMessage not ok (bad chat_id)"
    except urllib.error.HTTPError as e:
        return False, f"sendMessage HTTP {e.code} (chat_id?)"
    except Exception as e:
        return False, f"sendMessage failed: {type(e).__name__}"
    return True, "getMe + sendMessage OK"


def check_github():
    token = _env("GITHUB_TOKEN")
    repo = _env("GITHUB_REPO")   # "owner/repo"
    origin = _origin_repo()
    if not origin:
        return False, "origin is not a github.com repo (or unreadable)"
    if repo and repo.lower() != origin.lower():
        return False, f"GITHUB_REPO {repo} != origin {origin} (stale)"
    if token and _env("OT_GIT_PUSH") != "1":
        return False, f"a GitHub token is stored on a pull-only box (OT_GIT_PUSH != 1); origin {origin}"
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "vertigo-creds-verify"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"https://api.github.com/repos/{origin}", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            body = json.loads(r.read())
            if body.get("full_name", "").lower() != origin.lower():
                return True, f"reachable (GitHub names it {body.get('full_name')})"
            if token:
                return True, f"repo {origin} reachable (push box, token valid)"
            return True, f"pull-only, no token (by design); origin {origin} reachable"
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, "401 — token invalid/expired"
        if e.code == 404:
            return False, (f"404 — {origin} not reachable"
                           + ("" if token else " without a token (private?)"))
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, f"request failed: {type(e).__name__}"


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-tt", action="store_true")
    ap.add_argument("--skip-telegram", action="store_true")
    ap.add_argument("--skip-github", action="store_true")
    args = ap.parse_args(argv)

    checks = []
    if not args.skip_tt:
        checks.append(("TASTYTRADE", check_tastytrade))
    if not args.skip_telegram:
        checks.append(("TELEGRAM", check_telegram))
    if not args.skip_github:
        checks.append(("GITHUB", check_github))

    if not checks:
        print("VERIFY: SUCCESS (nothing to check)")
        return 0

    all_ok = True
    for name, fn in checks:
        try:
            ok, detail = fn()
        except Exception as e:  # noqa: BLE001 — a check must never crash the run
            ok, detail = False, f"unexpected: {type(e).__name__}"
        print(f"  {name}: {'SUCCESS' if ok else 'FAIL'} — {detail}")
        all_ok = all_ok and ok

    print(f"VERIFY: {'SUCCESS' if all_ok else 'FAIL'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    # urllib.parse used in telegram check
    import urllib.parse  # noqa: E402
    sys.exit(main(sys.argv[1:]))
