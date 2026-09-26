#!/usr/bin/env python3
"""
tests/check_fleet_power_log.py  v1.3
v1.3  2026-09-26  r439 / OPS.49 — P7 READ THE OPERATOR'S LIVE ACK FILE.
      `fleet_power_audit` defaults `--ack-file` to `logs/power_ack.txt`, and P7
      never overrode it. That file holds a REAL, DATED ack for AAL on
      2026-09-24 — the exact box and the exact date this fixture flags as
      unexplained — so the live ack suppressed it, `bad` fell from 2 to 1, and
      P7's assertion of "2 box(es)" failed. 🔴 THE CHECK WAS MEASURING THE
      OPERATOR'S STATE, NOT THE CODE'S: it went red on a Saturday because of
      something he did on Thursday, and nothing in the failure said so.
      ⚠️ SAME FAMILY AS r431-r433, WHERE A CHECKER WROTE INTO AN ARTEFACT A
      HUMAN READS. This one READ one, which is the quieter half — a writer
      leaves evidence, a reader just reports the wrong answer. Diagnosed in the
      2026-09-26 Saturday brief; I first blamed it on the ack file, tested that
      and found the fix had not applied, and only the second attempt (with the
      replace asserted) landed it.
v1.2  2026-09-25  r425 / OPS.49 — ADD A1-A3 for self-expiring acknowledgements.
      🔑 A2 IS THE ONE THAT MATTERS: an ack must DIE ON ITS OWN. A suppression
      that outlives its day is indistinguishable from a muted alert, and the
      whole reason this exists is that v1.0 would have nagged hourly about two
      boxes that were up on purpose (§17).
v1.1  2026-09-24  r424 — ADD P7 after two defects were found by RUNNING the
      tool: an undercounting `or`, and a test that sent a live Telegram.
v1.0  2026-09-24  r424 / OPS.48 — EVERY POWER CHANGE LEAVES A ROW, AND NO
      POWER CHANGE DEPENDS ON THE ROW SUCCEEDING.

      🔑 P4 IS THE CHECK THAT DECIDES WHETHER THIS SHIPS, and it is the
      inverse of what a logging gate usually asserts. A stop that FAILED
      because its log could not be written would strand a running box —
      exactly the cost this whole revision exists to prevent. So P4 makes the
      ledger unwritable and demands start() and stop() carry on regardless.
      A record that can take the fleet down is worse than no record.

      🔴 P5 IS THE ANTI-BYPASS CHECK AND IT IS THE ONE THAT OUTLIVES TODAY.
      The ledger is only worth what the chokepoint is worth: one module
      calling boto3 start_instances directly makes it a fiction. fleet.py did
      exactly that until r424.
      ⚠️ P5 PARSES THE AST AND DOES NOT GREP, deliberately. fleet.py's own
      docstring now QUOTES the retired call while explaining why it was
      removed, so a grep-based version of this check matches the prose that
      exists to document the fix and goes red on correct code. That is the
      third time this repo has recorded a checker matching its own subject
      (r420 P2, r417 §20); the AST cannot be fooled by prose.

      ⚠️ P1 CANNOT SEE AN AWS-CONSOLE START and does not pretend to. The
      ledger records what goes through ec2ops. §0.5: the audit tool names that
      blind spot out loud rather than reporting a confident "unknown".
"""
import ast
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_fails = []


def ck(tag, ok, msg=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {tag}  {msg}")
    if not ok:
        _fails.append(tag)


def main():
    try:
        import config
        import ec2ops
    except Exception as exc:                                   # noqa: BLE001
        ck("P0", False, f"cannot import config/ec2ops ({exc})")
        print(f"\nRED — 1 check(s) failed: P0")
        return 1

    plog = getattr(ec2ops, "_power_log", None)
    if plog is None or not hasattr(ec2ops, "POWER_LOG"):
        for t in ("P1", "P2", "P3", "P4"):
            ck(t, False, "ec2ops._power_log / POWER_LOG are absent")
    else:
        tmp = tempfile.mkdtemp(prefix="powerlog_")
        real_log, real_mock = ec2ops.POWER_LOG, config.MOCK_AWS
        config.MOCK_AWS = True                 # never touch real AWS
        try:
            # ── P1 — a start writes a START row naming the instance ────────
            ec2ops.POWER_LOG = os.path.join(tmp, "p1", "fleet_power.log")
            ec2ops.start(["i-deadbeef01"])
            body = ""
            if os.path.exists(ec2ops.POWER_LOG):
                body = open(ec2ops.POWER_LOG, encoding="utf-8").read()
            ck("P1", "START" in body and "i-deadbeef01" in body,
               f"start() wrote {len(body)} byte(s); "
               f"row={body.strip()[:110] or '(nothing)'}")

            # ── P2 — a stop writes a STOP row ──────────────────────────────
            ec2ops.POWER_LOG = os.path.join(tmp, "p2", "fleet_power.log")
            ec2ops.stop(["i-deadbeef02"])
            body2 = ""
            if os.path.exists(ec2ops.POWER_LOG):
                body2 = open(ec2ops.POWER_LOG, encoding="utf-8").read()
            ck("P2", "STOP" in body2 and "i-deadbeef02" in body2,
               f"stop() wrote row={body2.strip()[:110] or '(nothing)'}")

            # ── P3 — the row names the CALLER, which is the entire point ───
            # "ec2ops" as the caller would be useless: the question is never
            # which module flipped the switch, it is who asked it to.
            caller_ok = ("caller=" in body
                         and "caller=ec2ops.py" not in body
                         and "pid=" in body)
            got = ""
            for tok in body.split():
                if tok.startswith("caller="):
                    got = tok
            ck("P3", caller_ok,
               f"row carries an attributable caller outside ec2ops — {got or 'ABSENT'}")

            # ── P4 — SHIP-BLOCKER: a broken ledger must NOT break power ────
            ec2ops.POWER_LOG = os.path.join(tmp, "p4-file", "fleet_power.log")
            open(os.path.join(tmp, "p4-file"), "w").close()   # a FILE, not a dir
            survived = True
            try:
                ec2ops.start(["i-deadbeef03"])
                ec2ops.stop(["i-deadbeef03"])
            except Exception as exc:                           # noqa: BLE001
                survived = False
                err = f"{type(exc).__name__}: {exc}"
            ck("P4", survived,
               "start()/stop() SURVIVE an unwritable ledger — a record that can "
               "strand a box is worse than no record"
               if survived else f"power operation RAISED: {err}")
        finally:
            ec2ops.POWER_LOG, config.MOCK_AWS = real_log, real_mock

    # ── P5 — ANTI-BYPASS, asked of the AST and never of the text ──────────
    offenders = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames
                       if d not in (".git", "venv", "__pycache__", "node_modules")]
        for fn in filenames:
            if not fn.endswith(".py") or fn == "ec2ops.py":
                continue
            fp = os.path.join(dirpath, fn)
            try:
                tree = ast.parse(open(fp, encoding="utf-8", errors="replace").read())
            except Exception:                                  # noqa: BLE001
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    f = node.func
                    name = getattr(f, "attr", None) or getattr(f, "id", None)
                    if name in ("start_instances", "stop_instances"):
                        offenders.append(f"{os.path.relpath(fp, ROOT)}:{node.lineno}")
    ck("P5", not offenders,
       f"no module outside ec2ops CALLS start_instances/stop_instances"
       + (f" — BYPASS AT {', '.join(offenders)}" if offenders else
          " (AST-checked, so fleet.py's docstring quoting the retired call "
          "cannot red it)"))

    # ── P6 — the audit flags a box running out of window with a START row ──
    try:
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import fleet_power_audit as fpa
        import datetime
        from zoneinfo import ZoneInfo

        tmp2 = tempfile.mkdtemp(prefix="powaudit_")
        led = os.path.join(tmp2, "fleet_power.log")
        with open(led, "w", encoding="utf-8") as fh:
            fh.write("2026-09-24 19:49:20 ET  START  i-abc123  "
                     "caller=<string>:4:<module>  pid=1234  argv=-c\n")

        real_now, real_desc = fpa._now_et, fpa.ec2ops.describe_by_tag
        fpa._now_et = lambda: datetime.datetime(
            2026, 9, 24, 20, 30, tzinfo=ZoneInfo("America/New_York"))
        fpa.ec2ops.describe_by_tag = lambda *a, **k: {
            "SPX": {"instance_id": "i-abc123", "state": "running"},
            "QQQ": {"instance_id": "i-def456", "state": "stopped"}}
        try:
            rc = fpa.main(["--log", led])
        finally:
            fpa._now_et, fpa.ec2ops.describe_by_tag = real_now, real_desc
        ck("P6", rc == 1,
           f"audit returns {rc} (want 1) for a box running at 20:30 ET whose "
           f"ledger shows a START and no STOP")
    except Exception as exc:                                   # noqa: BLE001
        ck("P6", False, f"audit tool unusable ({type(exc).__name__}: {exc})")

    # ── P7 — THE ALERT IS COMPOSED, AND ITS COUNT IS RIGHT ────────────────
    # 🔴 BOTH HALVES OF THIS WERE BORN FROM DEFECTS FOUND BY RUNNING THE TOOL:
    #   (a) `bad = orphans or unexplained` returned the FIRST TRUTHY LIST, so
    #       an audit printing two boxes announced "1 box(es)" — a true number
    #       about the wrong object (OPS.43's shape);
    #   (b) exercising --notify from a heredoc SENT A LIVE TELEGRAM naming
    #       fabricated boxes, because notify._in_test() infers test-ness from
    #       argv[0]. This check sets DTP_NOTIFY_CAPTURE=1 EXPLICITLY and
    #       asserts capture is active BEFORE composing anything (§17).
    try:
        os.environ["DTP_NOTIFY_CAPTURE"] = "1"
        import notify
        import datetime
        from zoneinfo import ZoneInfo
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import fleet_power_audit as fpa

        if not notify._in_test():
            ck("P7", False, "capture switch NOT honoured — refusing to compose "
                            "an alert that could reach a real phone")
        else:
            tmp3 = tempfile.mkdtemp(prefix="powalert_")
            led = os.path.join(tmp3, "l.log")
            with open(led, "w", encoding="utf-8") as fh:
                fh.write("2026-09-24 19:49:20 ET  START  i-abc123  "
                         "caller=<string>:4:<module>  pid=1234  argv=-c\n")
            rn, rd = fpa._now_et, fpa.ec2ops.describe_by_tag
            fpa._now_et = lambda: datetime.datetime(
                2026, 9, 24, 20, 30, tzinfo=ZoneInfo("America/New_York"))
            fpa.ec2ops.describe_by_tag = lambda *a, **k: {
                "SPX": {"instance_id": "i-abc123", "state": "running"},
                "AAL": {"instance_id": "i-zzz999", "state": "running"}}
            before = len(notify.captured())
            try:
                # 🔴 r437 — `--ack-file` INTO SCRATCH. Without it the audit
                # read the operator's LIVE logs/power_ack.txt, which holds a
                # real dated ack for AAL on 2026-09-24 — the exact box and the
                # exact date this FIXTURE flags as unexplained. The live ack
                # suppressed it, `bad` fell from 2 to 1, and P7's assertion of
                # "2 box(es)" failed. The check was measuring the OPERATOR'S
                # STATE, not the code's.
                # ⚠️ Same family as r431/r432/r433, where a checker WROTE into
                # an artefact a human reads. This one READ one, which is the
                # quieter half: it goes red on a Saturday because of something
                # the operator did on Thursday, and nothing in the failure
                # says so.
                fpa.main(["--log", led, "--notify",
                          "--ack-file", os.path.join(tmp3, "ack.txt")])
            finally:
                fpa._now_et, fpa.ec2ops.describe_by_tag = rn, rd
            msgs = notify.captured()[before:]
            body = msgs[0] if msgs else ""
            ck("P7", bool(msgs) and "2 box(es)" in body,
               f"alert composed and counts BOTH flagged boxes (1 orphan + 1 "
               f"unexplained) — got {body.splitlines()[0] if body else 'NO ALERT'}")
    except Exception as exc:                                   # noqa: BLE001
        ck("P7", False, f"alert path unusable ({type(exc).__name__}: {exc})")

    # ── A1-A3 — acknowledgements suppress TODAY and die by themselves ─────
    try:
        import datetime
        from zoneinfo import ZoneInfo
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import fleet_power_audit as fpa

        tmp4 = tempfile.mkdtemp(prefix="powack_")
        ack = os.path.join(tmp4, "ack.txt")
        led2 = os.path.join(tmp4, "l.log")
        open(led2, "w").close()
        FIXED = datetime.datetime(2026, 9, 24, 22, 0,
                                  tzinfo=ZoneInfo("America/New_York"))
        rn, rd = fpa._now_et, fpa.ec2ops.describe_by_tag
        fpa._now_et = lambda: FIXED
        fpa.ec2ops.describe_by_tag = lambda *a, **k: {
            "AAL": {"instance_id": "i-aaa", "state": "running"},
            "SPX": {"instance_id": "i-xxx", "state": "running"}}
        try:
            # A1 — a live ack suppresses that box and only that box
            with open(ack, "w", encoding="utf-8") as fh:
                fh.write("AAL 2026-09-24 provisioning\n")
            live, exp = fpa.read_acks(ack, "2026-09-24")
            rc_a1 = fpa.main(["--log", led2, "--ack-file", ack])
            ck("A1", "AAL" in live and "SPX" not in live and rc_a1 == 1,
               f"ack covers AAL only (live={sorted(live)}); SPX still flags "
               f"(rc={rc_a1}) — an ack must never suppress a box nobody acked")

            # A2 — 🔑 AN ACK DIES ON ITS OWN, and the lapse is reported
            with open(ack, "w", encoding="utf-8") as fh:
                fh.write("AAL 2026-09-23 stale\n")
            live2, exp2 = fpa.read_acks(ack, "2026-09-24")
            ck("A2", not live2 and exp2 == [("AAL", "2026-09-23")],
               f"yesterday's ack does NOT suppress (live={sorted(live2)}) and "
               f"is returned as lapsed {exp2} so it can be said out loud")

            # A3 — DECLARED CONTROL: no ack file at all changes nothing
            live3, exp3 = fpa.read_acks(os.path.join(tmp4, "nope.txt"),
                                        "2026-09-24")
            ck("A3", live3 == {} and exp3 == [],
               "a missing ack file is not an error and suppresses nothing")
        finally:
            fpa._now_et, fpa.ec2ops.describe_by_tag = rn, rd
    except Exception as exc:                                   # noqa: BLE001
        for t in ("A1", "A2", "A3"):
            ck(t, False, f"ack path unusable ({type(exc).__name__}: {exc})")

    if _fails:
        print(f"\nRED — {len(_fails)} check(s) failed: {' '.join(_fails)}")
        return 1
    print("\nGREEN — every power change is attributable, and none depends on "
          "the ledger succeeding")
    return 0


if __name__ == "__main__":
    sys.exit(main())
