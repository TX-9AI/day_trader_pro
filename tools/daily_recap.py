#!/usr/bin/env python3
"""
day_trader_pro/tools/daily_recap.py  v1.4
v1.4  2026-11-22  dtp r576 / BOXF.1 (control's half of OTV5 r148) — ONE "Box flags" LINE IN THE CONTEXT. OTV5 r148 gives
      each box a saved settings file (deploy/box_flags/<SYM>, read once at the bot's start; the schema and defaults in
      utils/box_flags.py) and one "[flags]" start line, which eod_conductor_v2 v2.19 copies with the day's errors. context
      reads each box's last [flags] line of the day (its EFFECTIVE values) and runs OTV5's own show tool once
      (python3 -I ~/OTV5/tools/box_flags_show.py --json; control keeps no copy of the parser) for what ~/OTV5 HEAD would
      start the same boxes with. The line says "all defaults" when every box that started ran on the defaults with no
      refusal, else per box: its differences, REFUSED (a refused line, named), PENDING (HEAD would start it on other
      values or another file hash: a land not yet baked or not yet started) and NOT SEEN (no [flags] line in its
      extract: a box that did not start today, or one not yet on r148). It reads bot-log extracts and the show tool's
      JSON only: never an env file, a unit or a credential.
v1.3  2026-11-22  dtp r575 / HALF.2 + RWATCH.1 — A HALF DAY IS A NON-TRADING DAY, AND THE RUNAWAY EQUITY WATCH.
      (1) HALF DAYS. The operator, 2026-11-22: "Yes, just treat them as bank holidays. No trading." OTV5 r145 opens
      nothing on a 13:00 half day (2026-11-27, 2026-12-24); the boxes still wake and record data. The recap still runs
      (13:40 due, the 17:00 timer as before): the boxes ran, their bot logs, the data capture, the C1-C4 board and the
      watch still deserve the day's page, and a trade OPENED on a half day is the one thing that would be a defect.
      context opens with a HALF DAY block saying so (zero trades expected, never a defect, never a study), and validate
      refuses every proposal on a half day by name (a non-trading day adds no evidence), so nothing is queued from it.
      (2) THE RUNAWAY EQUITY WATCH (the operator, 2026-11-22: "I would keep any poor performers on runaway on notice to
      potentially be cut"). context runs tools/runaway_watch.py (the one scorer; WATCH.md frozen and sealed) into
      WORK/runaway_watch.{md,json}; the notes' "runaway_watch" paragraph is the session's commentary on it, withheld
      (with --runaway-watch) when it quotes a dollar figure the scorer did not print or says "paper size", the cash_books
      rule.
v1.2v1.2  2026-11-22  dtp r572 / SD.3 + RECAP.2 + CASHBOOK.1 — FOUR ADDITIONS, ALL MECHANICAL.
      (1) PARK AND RUNAWAY FIRST (the operator, 2026-11-21: "Our studies going forward now should primarily focus on
      maximizing the PNL on those two trade set ups"). A proposal carries "setup" (the names study_dispatch.SETUP_NAMES
      knows, e.g. "PARK" or "Runaway, Hunt"); the appended item gets the dispatcher's `- Setup:` line right under its
      Status, so the nightly queue runs it in the right tier. A proposal with no setup or an unknown name is refused.
      When more than MAX_QUEUED_A_DAY are valid, the cap admits the PARK / Runaway ones first.
      (2) NO DUPLICATE STUDY. context lists every DONE item's id and title beside the OPEN / FORWARD ones, and the
      validator (with the queue) refuses a proposal whose title is a duplicate of ANY queue item, whatever its status.
      THE RULE (simple on purpose): a title is lowercased, a leading "WS.<n> —" dropped, every character that is not a
      letter or digit made a space, and its words of 3+ characters (less DUP_STOPWORDS: the, and, for, with, from,
      into, its, our, than, then) kept as a set; two titles are duplicates when the
      sets are equal or share at least DUP_JACCARD (0.8) of their union. The item an earlier run appended for the same
      proposal (its own "(daily recap DAY, Pn)" marker) is not a duplicate of itself, so a re-run still appends nothing.
      (3) BOT LOGS. context lists the day's bot-log extracts the conductor copied before the stop
      (~/reviews/daily_brief/botlogs/<date>/<SYM>.txt, eod_conductor_v2 v2.18), with each box's ERROR, CRITICAL,
      Traceback and restart counts, so the code section reads them instead of saying NOT READ.
      (4) THE CASH CANDIDATE BOOKS C1-C4 (the operator, 2026-11-22: "On C1-C4, I would like some commentary on the
      daily and weekly recaps as to how each of them is performing"). context runs tools/cash_books.py (the one
      scorer; PREREG frozen) into WORK/cash_books.{md,json}; the notes' "cash_books" paragraphs are the session's
      commentary on it, and the validator (with --cash-books) refuses a commentary that quotes a dollar figure the
      scorer did not print, or calls the paper dollars "paper size": the PDF then prints the scoreboard with the
      commentary withheld and the reason. AMENDMENT 1 (2026-11-22): a commentary that names the top-two exclusion
      (the two best / largest winners, "dependent on its best trades") without the two largest losers beside it is
      withheld too: both figures or neither.
v1.1  2026-11-21  dtp r571 / OTV4DEP.3 — THE CONTEXT READS ONE BACKLOG, OTV5's. v1.0 also read the frozen tree's
      docs/BACKLOG.md for open rows (check_no_otv4_deps N1 red since r569). It never yielded a row: the frozen tree's
      PART 1 marks open work ⬜, not 🔲, and its open rows MOVED to OTV5 at otv4 r510 (one backlog since 2026-10-25).
      The read, its --otv4-backlog flag and the "otv4" backlog label are gone; a maintenance proposal names OTV5.
v1.0  2026-11-21  dtp r569 / RECAP.1 — THE DAILY RECAP'S MECHANICAL HALF. The operator, 2026-11-21: "Yes, we are going to
      begin firming up our system, our trading & our analysis". Their process: (1) every trading day the recap proposes
      studies to improve P&L and ONE piece of code maintenance from the backlog for a yes (delicate / live-order-path
      items marked for Sunday); (2) Friday evening, after the recap and the drain, every study of the week runs
      (dtp-study-dispatch); (3) early Saturday the weekend brief compiles the results; (4) Sundays implement.
      tools/daily_recap.sh calls this file for everything that must not be left to the headless session:
        plan      which session the recap is for, or why it skips (weekend, holiday, not yet due)
        context   the session's inputs: the backlog's open rows, the open queue titles, the next free WS id, prior
                  maintenance proposals, the studies that reported since the last recap, the queue's item format
        validate  the notes JSON the session wrote: the PDF's keys, each proposal's queue fields, ONE maintenance
                  proposal; a proposal that breaks a rule is refused by name (never queued), the rest go on
        append    the accepted proposals as full WEEKEND_STUDIES.md items: status OPEN, the next free ids, a .bak
                  first, inserted before "## DONE", proven with study_dispatch.parse_queue before the write (every new
                  id parses as OPEN, every id unique) and idempotent (a re-run for the same day appends nothing)
        notice    the one-line "recap ready" text for control's alert router
      🔑 THE SESSION NEVER EDITS THE QUEUE: it writes proposals into its notes; this file appends them.
      Standard library and dtp modules only (the gate runs it under the lander's python3). Never prints an
      environment, never touches a box, OTV5 or S3.

Usage:
  python tools/daily_recap.py plan [--day D] [--now YYYY-MM-DDTHH:MM]
  python tools/daily_recap.py context --day D --work DIR [--queue Q] [--notes-dir N] [--botlogs B] [--trades T]
  python tools/daily_recap.py validate --day D --notes FILE [--queue Q] [--cash-books WORK/cash_books.json]
                                       [--runaway-watch WORK/runaway_watch.json]
  python tools/daily_recap.py append --day D --notes FILE [--queue Q] [--cash-books WORK/cash_books.json]
                                     [--runaway-watch WORK/runaway_watch.json]
  python tools/daily_recap.py notice --day D --notes FILE --summary FILE
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
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
import market_calendar        # noqa: E402
import study_dispatch as SD   # noqa: E402  (parse_queue: the dispatcher's own reader is the proof)
import cash_books as CB       # noqa: E402  (v1.2: the one C1-C4 scorer)
import runaway_watch as RW    # noqa: E402  (v1.3: the one Runaway equity watch scorer)

ET = ZoneInfo("America/New_York")
HOME = os.path.expanduser("~")
QUEUE = os.path.join(HOME, "reviews", "WEEKEND_STUDIES.md")
REVIEWS = os.path.join(HOME, "reviews")
OUT = os.path.join(REVIEWS, "daily_brief")
NOTES_DIR = os.path.join(OUT, "notes")
STUDIES = os.path.join(REVIEWS, "studies")
WEEKLY = os.path.join(REVIEWS, "weekly")
OTV5_BACKLOG = os.path.join(HOME, "OTV5", "docs", "BACKLOG.md")
OTV5 = os.path.join(HOME, "OTV5")            # v1.4: the box flags show tool runs from this tree's HEAD
HYGIENE = os.path.join(REVIEWS, "hygiene")
BOTLOGS = os.path.join(OUT, "botlogs")       # v1.2: eod_conductor_v2 v2.18 writes <date>/<SYM>.txt before the stop
DUP_JACCARD = 0.8                            # v1.2: the near-duplicate title bar (word sets), documented above
DUP_STOPWORDS = ("the", "and", "for", "with", "from", "into", "its", "our", "than", "then")   # not words of a title
DUE_AFTER_MIN = 40             # after the close, as the nightly review (review_kit.DUE_AFTER_MIN)
MAX_QUEUED_A_DAY = 3           # the Friday dispatch runs one item per box; five days x 3 fits the fleet
FREEZE_END = "2026-11-27"      # the benchmark's trading-code freeze (only BROKEN code changes before it)
WHEN = ("weekday", "Sunday")

# the queue fields an appended item carries, in the order WS.21-WS.24 print them
QFIELDS = (("why", "Why"), ("hypothesis", "Hypothesis"),
           ("arms", "Arms (frozen grid, nothing added after FROZEN.json)"), ("data", "Data"), ("model", "Model"),
           ("positive_control", "Positive control"), ("days", "Days"), ("pass_bar", "Pass bar (written now)"),
           ("outcome", "Outcome"))
QREQUIRED = ("why", "hypothesis", "arms", "data", "model", "positive_control", "days", "pass_bar", "outcome")
PRIORITY_NAMES = tuple(k for k, v in SD.SETUP_NAMES.items() if v in SD.PRIORITY_SETUPS)
PDF_KEYS = ("revision", "headline", "symbols", "studies_intro", "proposals", "code_intro", "cash_verdict")
PARA_KEYS = ("headline", "day_note", "section1_close", "studies_intro", "study_recs", "proposals_intro", "code_intro",
             "cash_verdict", "cash_books", "runaway_watch", "sources")   # daily_brief.normalize_notes: a string = one paragraph
MREQUIRED = ("id", "backlog", "title", "what", "risk", "when")
FORBIDDEN = (
    (re.compile(r"resting\s+(take[- ]?profit|tp)\b|\bresting\s+(limit\s+)?(exit|target)\s+order", re.I),
     "resting take-profit orders are a closed topic (the operator, 2026-11-14)"),
    (re.compile(r"\bconfigure\.sh\b|\b(study|config)\s+(toggle|knob|switch)\b|\bnew\s+(env|config)\s+(knob|var)", re.I),
     "no new config knobs or study toggles (the operator, 2026-10-31)"),
)
RETIRED = re.compile(r"\b(butterfl(y|ies)|BFLY|PARC|TCS|ORBStrategy|original ORB)\b", re.I)
TOP2 = re.compile(r"\b(top[- ](two|2)|(two|2) (best|biggest|largest) (trades|winners)|best (two|2)|largest winners|"
                  r"(depend\w*|lean\w*|rel\w*) on (its|their|the) (best|top|biggest))", re.I)
BOTTOM2 = re.compile(r"\b(bottom[- ](two|2)|(two|2) (worst|largest) (trades|losers)|worst (two|2)|largest losers)",
                     re.I)                      # amendment 1: the top-two figure only ever beside the bottom-two
LOGONLY = re.compile(r"\blog[- ]only\b|\bshadow\s+(mode|log|rule)\b", re.I)


HALF_DAY_RULING = ('the operator, 2026-11-22: "Yes, just treat them as bank holidays. No trading."')
HALF_DAY_REFUSAL = ("a 13:00 half day is a non-trading day (%s): no study is proposed from it" % HALF_DAY_RULING)


def is_half(day):
    """v1.3: the day is a 13:00 half day (dtp market_calendar), a non-trading day by the operator's ruling."""
    try:
        return bool(market_calendar.is_half_day(date.fromisoformat(str(day))))
    except (TypeError, ValueError):
        return False


def half_day_lines(day):
    """v1.3 -> the context's HALF DAY block (empty on a full session)."""
    if not is_half(day):
        return []
    return ["HALF DAY: %s is a 13:00 early close, a NON-TRADING day by the operator's ruling (%s). OTV5 r145 opens "
            "nothing all session; the boxes woke and recorded data only. ZERO TRADES IS EXPECTED: never a defect, "
            "never a study, never a gap in the window. Any trade OPENED today IS a defect (OTV5 HALF.1). Proposals are "
            "refused on a half day (the appender queues nothing); the maintenance proposal, the bot logs, the C1-C4 "
            "board and the Runaway watch are as on any day." % (day, HALF_DAY_RULING), ""]


# ── plan ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
def close_et(d):
    return datetime.combine(d, time(13, 0) if market_calendar.is_half_day(d) else time(16, 0), ET)


def plan(now, day=None):
    """-> ("DAY", D) for the session to recap, ("SKIP", reason) or ("REFUSED", reason).
    The timer's run (no day) recaps TODAY only: a weekend or holiday skips, and so does a session not yet due
    (close + 40 min, 16:40 ET or 13:40 on a half day). A named day must be a trading day whose recap is due."""
    now = now.astimezone(ET)
    if day:
        try:
            d = date.fromisoformat(day)
        except ValueError:
            return ("REFUSED", "not a date: %r" % day)
        if not market_calendar.is_trading_day(d):
            return ("REFUSED", "%s is not a trading day" % d)
        if now < close_et(d) + timedelta(minutes=DUE_AFTER_MIN):
            return ("REFUSED", "%s has not closed (due %s ET)" % (d, (close_et(d) + timedelta(minutes=DUE_AFTER_MIN))
                                                                  .strftime("%Y-%m-%d %H:%M")))
        return ("DAY", d.isoformat())
    d = now.date()
    if not market_calendar.is_trading_day(d):
        return ("SKIP", "not-a-trading-day %s (%s)" % (d, d.strftime("%a")))
    if now < close_et(d) + timedelta(minutes=DUE_AFTER_MIN):
        return ("SKIP", "not-due %s before %s ET" % (d, (close_et(d) + timedelta(minutes=DUE_AFTER_MIN)).strftime("%H:%M")))
    return ("DAY", d.isoformat())


def next_trading_day(d):
    x = d + timedelta(days=1)
    while not market_calendar.is_trading_day(x):
        x += timedelta(days=1)
    return x


def prev_trading_day(d):
    x = d - timedelta(days=1)
    while not market_calendar.is_trading_day(x):
        x -= timedelta(days=1)
    return x


# ── context ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def next_ws_id(text):
    """The next WS number: one past the highest WS.<n> anywhere in the file (QUEUE, DONE, prose). Never reused."""
    nums = [int(n) for n in re.findall(r"\bWS\.(\d+)", text)]
    return (max(nums) + 1) if nums else 1


def backlog_rows(path, label, limit=400):
    """Open rows (a 🔲 cell, not closed or dead) of a backlog's PART 1 as 'ID | text' lines."""
    if not os.path.exists(path):
        return ["(%s backlog not found at %s)" % (label, path)]
    txt = open(path, encoding="utf-8").read()
    m = re.search(r"^## PART 1.*?(?=^## PART 2)", txt, re.M | re.S)
    part = m.group(0) if m else ""
    out, cat = [], ""
    for ln in part.splitlines():
        if ln.startswith("### "):
            cat = ln[4:].strip()
            continue
        mm = re.match(r"^\| \*\*([^*|]+)\*\* \|(.*)\|\s*$", ln)
        if not mm:
            continue
        cells = [c.strip() for c in mm.group(2).split("|")]
        if not any(c.startswith("🔲") for c in cells) or any(c.startswith(("✅", "⬛", "➡️")) for c in cells):
            continue
        body = re.sub(r"\s+", " ", " | ".join(cells))
        out.append("%s %s [%s] %s" % (label, mm.group(1).strip(), cat, body[:limit]))
    return out


def prior_maintenance(notes_dir, day):
    rows = []
    for p in sorted(glob.glob(os.path.join(notes_dir, "20??-??-??.json"))):
        d = os.path.basename(p)[:10]
        if d >= day:
            continue
        try:
            m = (json.load(open(p, encoding="utf-8")) or {}).get("maintenance") or {}
        except (OSError, ValueError):
            continue
        if m.get("id"):
            rows.append("%s %s (%s) %s" % (d, m.get("id"), m.get("when", "?"), str(m.get("title", ""))[:120]))
    return rows


def reported_studies(day, studies=STUDIES, weekly=WEEKLY, queue_text=""):
    """Study results that reported since the previous trading day's recap (its close + 40 min) up to now, and queue
    items whose status names a DONE / FORWARD date in that span."""
    d = date.fromisoformat(day)
    since = close_et(prev_trading_day(d)) + timedelta(minutes=DUE_AFTER_MIN)
    until = close_et(next_trading_day(d)) + timedelta(minutes=DUE_AFTER_MIN)   # a backfill sees only its own span
    t0, t1 = since.timestamp(), until.timestamp()
    found = []
    for p in sorted(glob.glob(os.path.join(studies, "*", "RESULT.json"))
                    + glob.glob(os.path.join(weekly, "saturday_*_work", "study_dispatch*", "*", "RESULT.json"))
                    + glob.glob(os.path.join(weekly, "saturday_*_work", "study_dispatch*", "*", "*", "RESULT.json"))):
        try:
            if t0 <= os.path.getmtime(p) < t1:
                found.append(os.path.dirname(p))
        except OSError:
            continue
    span = set()
    x = since.date()
    while x <= d:
        span.add(x.isoformat())
        x += timedelta(days=1)
    closed = []
    for it in SD.parse_queue(queue_text) if queue_text else []:
        m = re.match(r"(DONE|FORWARD to)\s+(\d{4}-\d\d-\d\d)", it["status"])
        if m and (m.group(1) == "FORWARD to" or m.group(2) in span):
            closed.append("%s: %s" % (it["id"], it["status"][:400]))
    return since, found, closed


def _words(title):
    t = re.sub(r"^\s*WS\.\d+[a-z]?\s*[—-]\s*", "", str(title or "").lower())
    return {w for w in re.sub(r"[^a-z0-9]+", " ", t).split() if len(w) >= 3 and w not in DUP_STOPWORDS}


def dup_of(title, queue_text, own_marker=None):
    """v1.2 -> the id of a queue item whose title duplicates `title` (the rule in the header), or None. Every item
    under ## QUEUE counts, OPEN, FORWARD or DONE; an item carrying `own_marker` (this proposal's earlier append) does
    not."""
    if not queue_text:
        return None
    mine = _words(title)
    if not mine:
        return None
    q = queue_text.split("## QUEUE", 1)[-1]
    heads = list(re.finditer(r"^### (WS\.\d+[a-z]?)\b[^\n]*$", q, re.M))
    for i, m in enumerate(heads):
        body = q[m.start(): heads[i + 1].start() if i + 1 < len(heads) else len(q)]
        if own_marker and own_marker in body:
            continue
        theirs = _words(m.group(0)[4:])
        if not theirs:
            continue
        if mine == theirs or len(mine & theirs) / len(mine | theirs) >= DUP_JACCARD:
            return m.group(1)
    return None


def setup_names(p):
    """v1.2 -> (the `- Setup:` text, problem) for a proposal's "setup" field, checked by the dispatcher's own reader."""
    v = p.get("setup")
    if isinstance(v, list):
        v = ", ".join(str(x).strip() for x in v)
    v = re.sub(r"\s+", " ", str(v or "").strip())
    if not v:
        return "", "missing setup (the `- Setup:` line: %s)" % ", ".join(SD.SETUP_NAMES)
    _got, why = SD.item_setups({"text": "- Setup: " + v})
    return (v, "") if not why else ("", "setup: " + why)


def botlog_summary(day, root=BOTLOGS):
    """v1.2 -> lines 'SYM: N ERROR, N CRITICAL, N Traceback, N restart marker(s) (path)' for the day's extracts."""
    d = os.path.join(root, day)
    if not os.path.isdir(d):
        return ["(no bot-log extracts for %s in %s: the conductor copied none; say NOT READ)" % (day, d)]
    out = []
    for p in sorted(glob.glob(os.path.join(d, "*.txt"))):
        try:
            t = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        sym = os.path.basename(p)[:-4]
        if " NOT READ" in t.split("\n", 1)[0]:
            out.append("%s: NOT READ (%s)" % (sym, t.split("\n", 1)[0][2:160]))
            continue
        c = lambda pat: len(re.findall(pat, t, re.M))   # noqa: E731
        out.append("%s: %d ERROR, %d CRITICAL, %d Traceback, %d restart marker(s) (%s)" % (
            sym, c(r" \[ERROR"), c(r" \[CRITICAL"), c(r"Traceback \(most recent call last\)"),
            c(r"OptionsBot \[[^\]]*\] STARTED|OptionsBot STOPPED|Main process exited|Scheduled restart"), p))
    return out or ["(the folder %s is empty)" % d]


FLAGS_RX = re.compile(r"\[flags\] (\S+) source=(.+?) sha256=(\S+) commit=(\S+) \u00b7 (.+?) \u00b7 differs: (.+?)"
                      r"(?: \u00b7 REFUSED: (.+))?$")


def _flag_values(txt):
    """v1.4 -> {key: value} from a [flags] line's values part ("schema v1: no keys" -> {})."""
    if txt.startswith("schema v"):
        return {}
    return dict(kv.split("=", 1) for kv in txt.split() if "=" in kv)


def head_flags(symbols, otv5=OTV5):
    """v1.4 -> ({SYM: {"sha256", "values"}}, problem) from OTV5's own show tool at HEAD (one call, read only)."""
    tool = os.path.join(otv5, "tools", "box_flags_show.py")
    if not os.path.exists(tool):
        return {}, "the show tool is not in %s (OTV5 before r148)" % otv5
    cmd = [sys.executable, "-I", tool, "--json"]
    for s_ in symbols:
        cmd += ["--symbol", s_]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                           env={"PATH": "/usr/bin:/bin", "HOME": HOME, "LANG": "C.UTF-8"})
        doc = json.loads(r.stdout)
        return {b["symbol"]: {"sha256": b["sha256"], "values": b["values"]} for b in doc.get("boxes", [])}, ""
    except Exception as e:                       # noqa: BLE001 - the recap goes on; the line says HEAD NOT READ
        return {}, "%s: %s" % (type(e).__name__, str(e)[:120])


def flags_summary(day, root=BOTLOGS, otv5=OTV5):
    """v1.4 -> lines for the context's "Box flags" block: each box's EFFECTIVE flags (its last [flags] start line in
    the day's extract) against what ~/OTV5 HEAD would start it with."""
    d = os.path.join(root, day)
    if not os.path.isdir(d):
        return ["(no bot-log extracts for %s: box flags NOT SEEN on any box)" % day]
    seen, unseen = {}, []
    for p in sorted(glob.glob(os.path.join(d, "*.txt"))):
        sym = os.path.basename(p)[:-4]
        try:
            t = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            unseen.append(sym)
            continue
        last = None
        for ln in t.splitlines():
            i = ln.find("[flags] ")
            if i >= 0:
                m = FLAGS_RX.match(ln[i:].rstrip())
                if m:
                    last = m
        if last is None:
            unseen.append(sym)
            continue
        seen[sym] = {"source": last.group(2), "sha256": last.group(3), "commit": last.group(4),
                     "values": _flag_values(last.group(5)), "differs": last.group(6), "refused": last.group(7) or ""}
    head, why = head_flags(sorted(seen), otv5) if seen else ({}, "")
    out, plain = [], []
    for sym in sorted(seen):
        e = seen[sym]
        h = head.get(sym)
        notes = []
        if e["differs"] != "none":
            notes.append("differs: " + e["differs"])
        if e["refused"]:
            notes.append("REFUSED: " + e["refused"])
        if h is not None and (h["values"] != e["values"] or h["sha256"] != e["sha256"]):
            notes.append("PENDING: HEAD would start it with %s (file %s)"
                         % (" ".join("%s=%s" % kv for kv in sorted(h["values"].items())) or "no keys", h["sha256"]))
        if notes:
            out.append("%s: %s (%s, commit %s)" % (sym, "; ".join(notes), e["source"], e["commit"]))
        else:
            plain.append(sym)
    if plain:
        out.insert(0, "all defaults on %d box(es) (%s)" % (len(plain), ", ".join(plain)) if not out else
                   "defaults, as HEAD: %s" % ", ".join(plain))
    if unseen:
        out.append("NOT SEEN (no [flags] line in the day's extract: not started today, or not yet on OTV5 r148): %s"
                   % ", ".join(unseen))
    if why:
        out.append("HEAD NOT READ (%s): PENDING cannot be judged" % why)
    return out


def watch_problems(notes, sc):
    """v1.3 -> [reason] the Runaway watch commentary is withheld: a dollar figure the scorer did not print (within $1),
    or the paper dollars called "paper size"."""
    txt = _txt(notes.get("runaway_watch"))
    if not txt.strip():
        return []
    out = []
    if re.search(r"paper[- ]siz", txt, re.I):
        out.append('calls the paper dollars "paper size" (paper is sized as cash, on purpose)')
    figs = RW.figures(sc)
    for m in re.finditer(r"\$\s?([0-9][0-9,]*(?:\.[0-9]+)?)", txt):
        v = round(float(m.group(1).replace(",", "")))
        if not any(abs(v - f) <= 1 for f in figs):
            out.append("quotes $%s, which the scorer did not print" % m.group(1))
    return out


def cash_problems(notes, sc):
    """v1.2 -> [reason] the C1-C4 commentary is withheld: a dollar figure the scorer did not print (within $1), or the
    paper dollars called "paper size"."""
    txt = _txt(notes.get("cash_books"))
    if not txt.strip():
        return []
    out = []
    if re.search(r"paper[- ]siz", txt, re.I):
        out.append('calls the paper dollars "paper size" (paper is sized as cash, on purpose)')
    if TOP2.search(txt) and not BOTTOM2.search(txt):
        out.append("names the two best trades without the two worst beside them (amendment 1: both or neither)")
    figs = CB.figures(sc)
    for m in re.finditer(r"\$\s?([0-9][0-9,]*(?:\.[0-9]+)?)", txt):
        v = round(float(m.group(1).replace(",", "")))
        if not any(abs(v - f) <= 1 for f in figs):
            out.append("quotes $%s, which the scorer did not print" % m.group(1))
    return out


def item_format(text):
    """HOW + ADDING + the newest full item, as the model of an appended item."""
    how = SD.how_block(text)
    m = re.search(r"^## ADDING AN ITEM.*?(?=^---|^## )", text, re.M | re.S)
    secs = [it for it in SD.parse_queue(text) if it["parent"] is None]
    last = secs[-1]["text"] if secs else ""
    return "%s\n\n%s\n\nTHE NEWEST ITEM, THE MODEL OF THE FIELDS:\n%s\n" % (how, m.group(0).strip() if m else "", last)


def cmd_context(a):
    os.makedirs(a.work, exist_ok=True)
    qt = open(a.queue, encoding="utf-8").read() if os.path.exists(a.queue) else ""
    items = SD.parse_queue(qt) if qt else []
    since, found, closed = reported_studies(a.day, a.studies, a.weekly, qt)
    with open(os.path.join(a.work, "backlog_open.txt"), "w", encoding="utf-8") as fh:
        fh.write("OPEN backlog rows (a cell starting 🔲; built-but-unproven ◐ rows and closed/dead rows left out).\n"
                 "One row a line: <backlog> <ID> [<category>] <cells>, cut at 400 characters; read the file for more.\n\n")
        for ln in backlog_rows(a.otv5_backlog, "OTV5"):
            fh.write(ln + "\n")
    with open(os.path.join(a.work, "queue_format.md"), "w", encoding="utf-8") as fh:
        fh.write(item_format(qt) if qt else "(queue not found)\n")
    hyg = sorted(glob.glob(os.path.join(a.hygiene, "*.md")))
    lines = [
        "CONTEXT FOR THE DAILY RECAP OF %s (written by tools/daily_recap.py context)" % a.day,
        "",
    ] + half_day_lines(a.day) + [
        "Next free study id: WS.%d (the appender assigns ids; you never write one)." % next_ws_id(qt),
        "Queue items already OPEN or FORWARD (never propose a duplicate of one):",
    ]
    lines += ["  %s [%s] %s" % (it["id"], it["status"][:40], it["title"][:110]) for it in items
              if it["status"].upper().startswith(("OPEN", "FORWARD"))] or ["  (none)"]
    lines += ["Queue items already DONE (never propose one again; the validator refuses a title that duplicates ANY "
              "queue item):"]
    lines += ["  %s %s" % (it["id"], it["title"][:110]) for it in items
              if it["status"].upper().startswith("DONE")] or ["  (none)"]
    lines += ["Each proposal names its setup (\"setup\": %s); PARK and Runaway studies come first (the operator, "
              "2026-11-21)." % " / ".join(SD.SETUP_NAMES)]
    lines += ["", "Bot-log extracts the conductor copied before the stop (ERROR / CRITICAL / Traceback / restarts):"]
    lines += ["  " + b for b in botlog_summary(a.day, a.botlogs)]
    lines += ["Box flags (each box's [flags] start line, the EFFECTIVE values, against ~/OTV5 HEAD; OTV5 r148):"]
    lines += ["  " + b for b in flags_summary(a.day, a.botlogs, a.otv5)]
    try:
        sc = CB.score(a.day, day=a.day, trades_dir=a.trades)
        with open(os.path.join(a.work, "cash_books.json"), "w", encoding="utf-8") as fh:
            json.dump(sc, fh, indent=1)
        with open(os.path.join(a.work, "cash_books.md"), "w", encoding="utf-8") as fh:
            fh.write(CB.render_md(sc))
        lines += ["", "Cash candidate books C1-C4 (tools/cash_books.py, PREREG frozen): %s"
                  % os.path.join(a.work, "cash_books.md")]
    except Exception as e:                       # noqa: BLE001 - the recap goes on; the PDF says NOT MEASURED
        lines += ["", "Cash candidate books C1-C4: NOT MEASURED (%s: %s)" % (type(e).__name__, e)]
    try:                                         # v1.3: the Runaway equity watch (WATCH.md frozen)
        rw = RW.score(a.day, trades_dir=a.trades)
        with open(os.path.join(a.work, "runaway_watch.json"), "w", encoding="utf-8") as fh:
            json.dump(rw, fh, indent=1, ensure_ascii=False)
        with open(os.path.join(a.work, "runaway_watch.md"), "w", encoding="utf-8") as fh:
            fh.write(RW.render_md(rw))
        lines += ["Runaway equity watch (tools/runaway_watch.py, WATCH.md frozen): %s — %s"
                  % (os.path.join(a.work, "runaway_watch.md"),
                     "; ".join("%s %s (forward n %d)" % (s, st, n) for s, n, _nt, _ev, _b, st in RW.watch_rows(rw)))]
    except Exception as e:                       # noqa: BLE001 - the recap goes on; the PDF says NOT MEASURED
        lines += ["Runaway equity watch: NOT MEASURED (%s: %s)" % (type(e).__name__, e)]
    lines += ["", "Studies that reported since %s ET (RESULT.json folders):" % since.strftime("%Y-%m-%d %H:%M")]
    lines += ["  " + f for f in found] or ["  (none)"]
    lines += ["", "Queue items closed or carried forward in that span (their status lines):"]
    lines += ["  " + c for c in closed] or ["  (none)"]
    lines += ["", "Maintenance already proposed by earlier recaps (do not repeat an id):"]
    lines += ["  " + r for r in prior_maintenance(a.notes_dir, a.day)] or ["  (none)"]
    lines += ["", "Open backlog rows: %s" % os.path.join(a.work, "backlog_open.txt"),
              "Hygiene maps: " + (", ".join(hyg) if hyg else "(none)"),
              "Queue item format (HOW, ADDING, newest item): %s" % os.path.join(a.work, "queue_format.md"),
              "Trading-code freeze ends %s (before it, trading code changes only when BROKEN)." % FREEZE_END]
    with open(os.path.join(a.work, "context.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(os.path.join(a.work, "context.md"))
    return 0


# ── validate ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _txt(v):
    if isinstance(v, list):
        return " ".join(_txt(x) for x in v)
    if isinstance(v, dict):
        return " ".join(_txt(x) for x in v.values())
    return str(v if v is not None else "")


def proposal_problems(p):
    """-> [reason] that keep a proposal out of the queue (it stays in the PDF, marked not queued)."""
    bad = [k for k in ("title",) + QREQUIRED if not str(p.get(k) or "").strip()]
    out = ["missing " + ", ".join(bad)] if bad else []
    allt = _txt({k: p.get(k) for k in ("title",) + QREQUIRED + ("evidence", "change", "blind")})
    for rx, why in FORBIDDEN:
        if rx.search(allt):
            out.append(why)
    if LOGONLY.search(re.sub(r"(?i)\b(never|not|no)\s+(becomes\s+)?log[- ]only\b", "", allt)):
        out.append("a study's outcome is never log-only or a shadow (HOW 4; the operator, 2026-11-07)")
    if RETIRED.search(_txt({k: p.get(k) for k in ("title", "hypothesis", "arms")})):
        out.append("names a retired strategy (butterfly, PARC, TCS, the original ORB)")
    if not re.search(r"\b(TUNE|TRIM|KEEP)\b", str(p.get("outcome") or "")):
        out.append("outcome names none of TUNE / TRIM / KEEP")
    _v, why = setup_names(p)
    if why:
        out.append(why)
    return out


def is_priority(p):
    v, _why = setup_names(p) if isinstance(p, dict) else ("", "")
    return bool(v) and any(x.strip() in PRIORITY_NAMES for x in v.split(","))


def validate(notes, queue_text=None, day=None):
    """-> (fatal, refused, mproblems): fatal = the notes cannot build the PDF; refused = {index: [reasons]};
    mproblems = what is wrong with the maintenance proposal (empty when it is good)."""
    if not isinstance(notes, dict):
        return (["the notes are not a JSON object"], {}, [])
    fatal = ["missing key %s" % k for k in PDF_KEYS if k not in notes]
    fatal += ["%s is neither a list of paragraphs nor a string" % k for k in PARA_KEYS
              if k in notes and not isinstance(notes[k], (list, str))]
    if not isinstance(notes.get("symbols", {}), dict):
        fatal.append("symbols is not an object")
    props = notes.get("proposals")
    if not isinstance(props, list):
        fatal.append("proposals is not a list")
        props = []
    refused, accepted = {}, 0
    half = is_half(day) if day else False
    for i, p in enumerate(props):
        r = proposal_problems(p) if isinstance(p, dict) else ["not an object"]
        if half:                                   # v1.3: a half day is a non-trading day; nothing is queued from it
            r = [HALF_DAY_REFUSAL] + r
        if not r and queue_text:
            d = dup_of(p.get("title"), queue_text, marker(day, i) if day else None)
            if d:
                r = ["duplicates %s's title (the near-duplicate rule, DUP_JACCARD %.1f)" % (d, DUP_JACCARD)]
        if r:
            refused[i] = r
    # v1.2: the daily cap admits PARK / Runaway proposals first, then the rest, each in the order written
    for i in sorted((i for i in range(len(props)) if i not in refused), key=lambda i: 0 if is_priority(props[i]) else 1):
        if accepted >= MAX_QUEUED_A_DAY:
            refused[i] = ["over the daily cap of %d queued studies" % MAX_QUEUED_A_DAY]
        else:
            accepted += 1
    m = notes.get("maintenance")
    mp = []
    if not isinstance(m, dict):
        mp.append("no maintenance proposal (one object under 'maintenance')")
    else:
        mp += ["maintenance missing " + k for k in MREQUIRED if not str(m.get(k) or "").strip()]
        if str(m.get("when", "")).strip() not in WHEN:
            mp.append("maintenance 'when' must be one of %s" % " / ".join(WHEN))
        for rx, why in FORBIDDEN:
            if rx.search(_txt(m)):
                mp.append(why)
    return (fatal, refused, mp)


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _dump_atomic(obj, path):
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".recap_", dir=d)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)


def _queue_text(path):
    try:
        return open(path, encoding="utf-8").read() if path and os.path.exists(path) else None
    except OSError:
        return None


def cmd_validate(a):
    try:
        notes = _load(a.notes)
    except (OSError, ValueError) as e:
        print("FATAL notes unreadable: %s" % e)
        return 2
    fatal, refused, mp = validate(notes, _queue_text(a.queue), a.day)
    if a.cash_books and os.path.exists(a.cash_books):
        for c in cash_problems(notes, _load(a.cash_books)):
            print("CASHBOOKS commentary withheld: " + c)
    if a.runaway_watch and os.path.exists(a.runaway_watch):
        for c in watch_problems(notes, _load(a.runaway_watch)):
            print("RUNAWAYWATCH commentary withheld: " + c)
    for f in fatal:
        print("FATAL " + f)
    for i, r in sorted(refused.items()):
        print("REFUSED P%d %s: %s" % (i + 1, str((notes.get("proposals") or [{}])[i].get("title", "?"))[:80]
                                      if isinstance(notes["proposals"][i], dict) else "?", "; ".join(r)))
    for m in mp:
        print("MAINTENANCE " + m)
    ok_n = len(notes.get("proposals") or []) - len(refused) if not fatal else 0
    print("VALID %s proposals=%d queueable=%d maintenance=%s" % ("no" if fatal else "yes",
                                                                 len(notes.get("proposals") or []), ok_n,
                                                                 "ok" if not mp else "bad"))
    return 2 if fatal else 0


# ── append ───────────────────────────────────────────────────────────────────────────────────────────────────────────
def marker(day, i):
    return "(daily recap %s, P%d)" % (day, i + 1)


def render(ws, day, i, p):
    title = re.sub(r"\s+", " ", str(p["title"]).strip())
    lines = ["### WS.%d — %s" % (ws, title),
             "- Status: OPEN (added %s by the daily recap; freeze the rule in FROZEN.json before any sealed day is "
             "scored)" % day,
             "- Setup: %s" % setup_names(p)[0]]
    for k, lab in QFIELDS:
        v = re.sub(r"\s*\n\s*", " ", _txt(p.get(k)).strip())
        if k == "outcome" and "log-only" not in v.lower():
            v = v.rstrip(".") + ". Never log-only."
        lines.append("- %s: %s" % (lab, v))
        if k == "pass_bar":
            lines.append("- Basis (HOW 3b): at the mark, the ladder's fill (mark or better); fees beside EV, never in "
                         "it; OTV4TEST rows filtered out (OTV5 tests/warehouse_source.mainline()).")
    if str(p.get("evidence") or "").strip():
        lines.append("- What %s showed: %s" % (day[5:], re.sub(r"\s+", " ", str(p["evidence"]).strip())))
    if str(p.get("run_budget") or "").strip():
        lines.append("- Run budget: %s" % str(p["run_budget"]).strip())
    lines.append("- Source: %s ~/reviews/daily_brief/daily_brief_%s.pdf section 3." % (marker(day, i), day))
    return "\n".join(lines) + "\n"


def append(text, day, notes):
    """-> (new_text, {index: ws_id}, skipped_reason) for the accepted proposals; text unchanged when there is nothing
    to add. Raises ValueError when the result does not parse as the dispatcher reads it."""
    fatal, refused, _mp = validate(notes, text, day)
    if fatal:
        return text, {}, "notes fatal: " + "; ".join(fatal)
    if "## QUEUE" not in text:
        raise ValueError("the queue has no '## QUEUE' section")
    props = notes.get("proposals") or []
    done = {i for i in range(len(props)) if marker(day, i) in text}
    want = [i for i in range(len(props)) if i not in refused and i not in done]
    if not want:
        return text, {}, ("already appended" if done else "nothing to queue")
    before = SD.parse_queue(text)
    n0 = next_ws_id(text)
    ids = {i: "WS.%d" % (n0 + k) for k, i in enumerate(want)}
    block = "\n".join(render(n0 + k, day, i, props[i]) for k, i in enumerate(want))
    cut = text.find("\n## DONE")
    if cut < 0:
        new = text.rstrip("\n") + "\n\n" + block
    else:
        head = text[:cut].rstrip("\n")
        new = head + "\n\n" + block + text[cut:]
    after = SD.parse_queue(new)
    got = {it["id"]: it for it in after}
    heads = re.findall(r"^### (WS\.\d+)\b", new, re.M)
    probs = []
    if len(heads) != len(set(heads)):
        probs.append("duplicate item headings %s" % sorted({h for h in heads if heads.count(h) > 1}))
    for i, w in ids.items():
        if w not in got or not got[w]["status"].upper().startswith("OPEN"):
            probs.append("%s does not parse as OPEN" % w)
    if len(after) != len(before) + len(ids):
        probs.append("parse_queue count %d -> %d, expected +%d" % (len(before), len(after), len(ids)))
    if [it["id"] for it in before] != [it["id"] for it in after][:len(before)]:
        probs.append("the existing items no longer parse in order")
    if probs:
        raise ValueError("; ".join(probs))
    return new, ids, ""


def cmd_append(a):
    notes = _load(a.notes)
    text = open(a.queue, encoding="utf-8").read()
    try:
        new, ids, why = append(text, a.day, notes)
    except ValueError as e:
        print("REFUSED the queue append would not parse: %s (queue untouched)" % e)
        return 1
    _fatal, refused, _mp = validate(notes, text, a.day)
    if a.cash_books and os.path.exists(a.cash_books):
        cp = cash_problems(notes, _load(a.cash_books))
        if cp:                                          # the PDF prints the scoreboard and says why there is no comment
            notes["cash_books_withheld"] = "; ".join(cp)
            notes.pop("cash_books", None)
    if a.runaway_watch and os.path.exists(a.runaway_watch):
        wp = watch_problems(notes, _load(a.runaway_watch))
        if wp:                                          # v1.3: the PDF prints the watch and says why there is no comment
            notes["runaway_watch_withheld"] = "; ".join(wp)
            notes.pop("runaway_watch", None)
    for i, p in enumerate(notes.get("proposals") or []):
        if not isinstance(p, dict):
            continue
        if i in ids:
            p["ws_id"] = ids[i]
            p.pop("queue_refused", None)
        elif i in refused:
            p["queue_refused"] = "; ".join(refused[i])
    if new != text:
        bak = "%s.bak_recap_%s" % (a.queue, a.day.replace("-", ""))
        shutil.copy2(a.queue, bak)                      # the .bak first
        d = os.path.dirname(os.path.abspath(a.queue))
        fd, tmp = tempfile.mkstemp(prefix=".queue_", dir=d)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(new)
        shutil.copymode(a.queue, tmp)
        os.replace(tmp, a.queue)
        print("APPENDED %s (backup %s)" % (" ".join(ids[i] for i in sorted(ids)), bak))
    else:
        print("APPENDED none (%s)" % why)
    _dump_atomic(notes, a.notes)
    return 0


# ── notice ───────────────────────────────────────────────────────────────────────────────────────────────────────────
def _m(x):
    x = float(x or 0)
    return ("+" if x > 0 else "-" if x < 0 else "") + "${:,.2f}".format(abs(x))


def notice(day, notes, summ):
    ids = [p.get("ws_id") for p in (notes or {}).get("proposals") or [] if isinstance(p, dict) and p.get("ws_id")]
    m = (notes or {}).get("maintenance") or {}
    s = "Daily recap %s ready: %s. Day %s at the mark, fees %s beside, %s trades." % (
        day, summ.get("pdf", "?"), _m(summ.get("paper")), _m(summ.get("fees")).lstrip("+"), summ.get("trades", "?"))
    s += " Studies queued: %s." % (", ".join(ids) if ids else "none")
    if m.get("id"):
        s += " Maintenance %s (%s) awaits your yes." % (m["id"], m.get("when", "?"))
    return s


def cmd_notice(a):
    notes = _load(a.notes) if a.notes and os.path.exists(a.notes) else {}
    summ = _load(a.summary)
    print(notice(a.day, notes, summ))
    return 0


def cmd_plan(a):
    now = datetime.fromisoformat(a.now).replace(tzinfo=ET) if a.now else datetime.now(ET)
    k, v = plan(now, a.day)
    print("%s %s" % (k, v))
    return {"DAY": 0, "SKIP": 0}.get(k, 2)


def main(argv=None):
    ap = argparse.ArgumentParser(description="the daily recap's mechanical half (dtp r569)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--day")
    p.add_argument("--now")
    p = sub.add_parser("context")
    p.add_argument("--day", required=True)
    p.add_argument("--work", required=True)
    p.add_argument("--queue", default=QUEUE)
    p.add_argument("--notes-dir", default=NOTES_DIR)
    p.add_argument("--studies", default=STUDIES)
    p.add_argument("--weekly", default=WEEKLY)
    p.add_argument("--otv5-backlog", default=OTV5_BACKLOG)
    p.add_argument("--hygiene", default=HYGIENE)
    p.add_argument("--botlogs", default=BOTLOGS)
    p.add_argument("--otv5", default=OTV5)
    p.add_argument("--trades", default=CB.TRADES)
    p = sub.add_parser("validate")
    p.add_argument("--day", required=True)
    p.add_argument("--notes", required=True)
    p.add_argument("--queue", default=QUEUE)
    p.add_argument("--cash-books", default=None)
    p.add_argument("--runaway-watch", default=None)
    p = sub.add_parser("append")
    p.add_argument("--day", required=True)
    p.add_argument("--notes", required=True)
    p.add_argument("--queue", default=QUEUE)
    p.add_argument("--cash-books", default=None)
    p.add_argument("--runaway-watch", default=None)
    p = sub.add_parser("notice")
    p.add_argument("--day", required=True)
    p.add_argument("--notes")
    p.add_argument("--summary", required=True)
    a = ap.parse_args(argv)
    return {"plan": cmd_plan, "context": cmd_context, "validate": cmd_validate, "append": cmd_append,
            "notice": cmd_notice}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
