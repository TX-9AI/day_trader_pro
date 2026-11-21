#!/usr/bin/env python3
"""
day_trader_pro/tools/daily_recap.py  v1.0
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
  python tools/daily_recap.py context --day D --work DIR [--queue Q] [--notes-dir N] [--reviews R]
  python tools/daily_recap.py validate --day D --notes FILE
  python tools/daily_recap.py append --day D --notes FILE [--queue Q]
  python tools/daily_recap.py notice --day D --notes FILE --summary FILE
"""
import argparse
import glob
import json
import os
import re
import shutil
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

ET = ZoneInfo("America/New_York")
HOME = os.path.expanduser("~")
QUEUE = os.path.join(HOME, "reviews", "WEEKEND_STUDIES.md")
REVIEWS = os.path.join(HOME, "reviews")
OUT = os.path.join(REVIEWS, "daily_brief")
NOTES_DIR = os.path.join(OUT, "notes")
STUDIES = os.path.join(REVIEWS, "studies")
WEEKLY = os.path.join(REVIEWS, "weekly")
OTV5_BACKLOG = os.path.join(HOME, "OTV5", "docs", "BACKLOG.md")
OTV4_BACKLOG = os.path.join(HOME, "options-trader-v4", "docs", "BACKLOG.md")
HYGIENE = os.path.join(REVIEWS, "hygiene")
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
PDF_KEYS = ("revision", "headline", "symbols", "studies_intro", "proposals", "code_intro", "cash_verdict")
PARA_KEYS = ("headline", "day_note", "section1_close", "studies_intro", "study_recs", "proposals_intro", "code_intro",
             "cash_verdict", "sources")       # daily_brief.normalize_notes reads a string as one paragraph
MREQUIRED = ("id", "backlog", "title", "what", "risk", "when")
FORBIDDEN = (
    (re.compile(r"resting\s+(take[- ]?profit|tp)\b|\bresting\s+(limit\s+)?(exit|target)\s+order", re.I),
     "resting take-profit orders are a closed topic (the operator, 2026-11-14)"),
    (re.compile(r"\bconfigure\.sh\b|\b(study|config)\s+(toggle|knob|switch)\b|\bnew\s+(env|config)\s+(knob|var)", re.I),
     "no new config knobs or study toggles (the operator, 2026-10-31)"),
)
RETIRED = re.compile(r"\b(butterfl(y|ies)|BFLY|PARC|TCS|ORBStrategy|original ORB)\b", re.I)
LOGONLY = re.compile(r"\blog[- ]only\b|\bshadow\s+(mode|log|rule)\b", re.I)


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
        for ln in backlog_rows(a.otv5_backlog, "OTV5") + backlog_rows(a.otv4_backlog, "otv4"):
            fh.write(ln + "\n")
    with open(os.path.join(a.work, "queue_format.md"), "w", encoding="utf-8") as fh:
        fh.write(item_format(qt) if qt else "(queue not found)\n")
    hyg = sorted(glob.glob(os.path.join(a.hygiene, "*.md")))
    lines = [
        "CONTEXT FOR THE DAILY RECAP OF %s (written by tools/daily_recap.py context)" % a.day,
        "",
        "Next free study id: WS.%d (the appender assigns ids; you never write one)." % next_ws_id(qt),
        "Queue items already OPEN or FORWARD (never propose a duplicate of one):",
    ]
    lines += ["  %s [%s] %s" % (it["id"], it["status"][:40], it["title"][:110]) for it in items
              if it["status"].upper().startswith(("OPEN", "FORWARD"))] or ["  (none)"]
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
    return out


def validate(notes):
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
    for i, p in enumerate(props):
        r = proposal_problems(p) if isinstance(p, dict) else ["not an object"]
        if not r and accepted >= MAX_QUEUED_A_DAY:
            r = ["over the daily cap of %d queued studies" % MAX_QUEUED_A_DAY]
        if r:
            refused[i] = r
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


def cmd_validate(a):
    try:
        notes = _load(a.notes)
    except (OSError, ValueError) as e:
        print("FATAL notes unreadable: %s" % e)
        return 2
    fatal, refused, mp = validate(notes)
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
             "scored)" % day]
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
    fatal, refused, _mp = validate(notes)
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
    _fatal, refused, _mp = validate(notes)
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
    p.add_argument("--otv4-backlog", default=OTV4_BACKLOG)
    p.add_argument("--hygiene", default=HYGIENE)
    p = sub.add_parser("validate")
    p.add_argument("--day", required=True)
    p.add_argument("--notes", required=True)
    p = sub.add_parser("append")
    p.add_argument("--day", required=True)
    p.add_argument("--notes", required=True)
    p.add_argument("--queue", default=QUEUE)
    p = sub.add_parser("notice")
    p.add_argument("--day", required=True)
    p.add_argument("--notes")
    p.add_argument("--summary", required=True)
    a = ap.parse_args(argv)
    return {"plan": cmd_plan, "context": cmd_context, "validate": cmd_validate, "append": cmd_append,
            "notice": cmd_notice}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
