#!/usr/bin/env python3
"""
day_trader_pro/tests/check_power_halt.py  v1.0
v1.0  2026-11-08  dtp r530 / OPS.76. A BOX THAT STOPS ITSELF IS RECORDED AS ITS OWN CLASS. 2026-11-08 00:00 ET
      QQQ's midnight backstop powered it off from inside the OS; nothing went through ec2ops.stop(), so the power
      ledger kept a START with no stop. The audit now reads EC2's stop reason and appends HALT (self-halt) or XSTOP
      (stopped outside ec2ops). Every check drives the REAL ec2ops / fleet_power_audit on a scratch ledger and a
      scratch ack file (never the live logs/), with the clock and EC2 faked.
  H1  ec2ops.stop_class: Client.InstanceInitiatedShutdown -> HALT; Client.UserInitiatedShutdown, '' and an unknown
      code -> XSTOP
  H2  transition_time_et('User initiated (2026-11-08 05:00:33 GMT)') == '2026-11-08 00:00:33' (ET, DST-aware), and
      '' for a reason with no time
  H3  describe_by_tag carries state_reason_code and state_transition_reason from a fake EC2 client
  H4  the audit, on the 11-08 QQQ shape (stopped, InstanceInitiatedShutdown, ledger ends in START), appends ONE HALT row
      at the EC2 time with caller=ec2:<code>, prints SELF-HALTED, and still exits 0 (nothing running)
  H5  a second run writes nothing more (the HALT is now the last event)
  H6  a console stop (UserInitiatedShutdown) is recorded as XSTOP and names the code
  H7  a stopped box whose ledger ends in STOP, or has no rows, gets no row
  H8  after a HALT, a box found RUNNING with no new START is UNEXPLAINED, never attributed to the old START
  H9  --quiet still records (and prints) an observed stop
  H10 a RUNNING box whose ledger ends in START gets no row and stays an orphan of that START
Run:  python3 tests/check_power_halt.py
"""
import contextlib
import datetime
import io
import os
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

FAILS = []


def ck(cid, ok, why=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {cid}" + ("" if ok else f"  {why}"))
    if not ok:
        FAILS.append(cid)


class _FakeEC2:
    def describe_instances(self, Filters=None):
        return {"Reservations": [{"Instances": [{
            "InstanceId": "i-qqq", "State": {"Name": "stopped"},
            "StateReason": {"Code": "Client.InstanceInitiatedShutdown",
                            "Message": "Client.InstanceInitiatedShutdown: Instance initiated shutdown"},
            "StateTransitionReason": "User initiated (2026-11-08 05:00:33 GMT)",
            "PrivateIpAddress": "10.0.0.1", "Tags": [{"Key": "Name", "Value": "QQQ"}]}]}]}


def run_audit(fpa, fleet, led, ack, args=()):
    real_now, real_desc = fpa._now_et, fpa.ec2ops.describe_by_tag
    fpa._now_et = lambda: datetime.datetime(2026, 11, 8, 1, 5, tzinfo=ZoneInfo("America/New_York"))
    fpa.ec2ops.describe_by_tag = lambda *a, **k: fleet
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = fpa.main(["--log", led, "--ack-file", ack] + list(args))
    finally:
        fpa._now_et, fpa.ec2ops.describe_by_tag = real_now, real_desc
    return rc, buf.getvalue()


def rows(led):
    return [l for l in open(led, encoding="utf-8").read().splitlines() if l.strip()]


def main():
    import config
    import ec2ops
    import fleet_power_audit as fpa

    ck("H1", ec2ops.stop_class("Client.InstanceInitiatedShutdown") == "HALT"
       and ec2ops.stop_class("Client.UserInitiatedShutdown") == "XSTOP"
       and ec2ops.stop_class("") == "XSTOP" and ec2ops.stop_class("Server.SpotInstanceTermination") == "XSTOP",
       "stop_class mapping")
    ck("H2", ec2ops.transition_time_et("User initiated (2026-11-08 05:00:33 GMT)") == "2026-11-08 00:00:33"
       and ec2ops.transition_time_et("User initiated (2026-07-01 04:00:00 GMT)") == "2026-07-01 00:00:00"
       and ec2ops.transition_time_et("") == "", "transition time")

    real_ec2, mock = ec2ops._ec2, config.MOCK_AWS
    try:
        config.MOCK_AWS = False
        ec2ops._ec2 = lambda: _FakeEC2()
        d = ec2ops.describe_by_tag()
    finally:
        ec2ops._ec2, config.MOCK_AWS = real_ec2, mock
    q = d.get("QQQ", {})
    ck("H3", q.get("state_reason_code") == "Client.InstanceInitiatedShutdown"
       and q.get("state_transition_reason") == "User initiated (2026-11-08 05:00:33 GMT)", q)

    tmp = tempfile.mkdtemp(prefix="powhalt_")
    led, ack = os.path.join(tmp, "fleet_power.log"), os.path.join(tmp, "ack.txt")
    start = ("2026-11-07 22:31:06 ET  START  i-qqq  caller=wake_and_bake.py:257:stage_wake  "
             "pid=3085966  argv=wake_and_bake.py --wake-only --only QQQ --yes\n")
    open(led, "w", encoding="utf-8").write(start)
    qqq_halted = {"QQQ": {"instance_id": "i-qqq", "state": "stopped",
                          "state_reason_code": "Client.InstanceInitiatedShutdown",
                          "state_transition_reason": "User initiated (2026-11-08 05:00:33 GMT)"}}
    rc, out = run_audit(fpa, qqq_halted, led, ack)
    r = rows(led)
    ck("H4", rc == 0 and len(r) == 2 and r[1].startswith("2026-11-08 00:00:33 ET  HALT ")
       and "caller=ec2:Client.InstanceInitiatedShutdown" in r[1] and "i-qqq" in r[1] and "SELF-HALTED" in out,
       (rc, r[-1:], out[-300:]))
    rc2, out2 = run_audit(fpa, qqq_halted, led, ack)
    ck("H5", len(rows(led)) == 2 and "SELF-HALTED" not in out2, (len(rows(led)), out2[-200:]))

    led2 = os.path.join(tmp, "l2.log")
    open(led2, "w", encoding="utf-8").write(start)
    rc, out = run_audit(fpa, {"QQQ": {"instance_id": "i-qqq", "state": "stopped",
                                      "state_reason_code": "Client.UserInitiatedShutdown",
                                      "state_transition_reason": "User initiated (2026-11-08 05:30:00 GMT)"}},
                        led2, ack)
    r = rows(led2)
    ck("H6", len(r) == 2 and " XSTOP " in r[1] and "Client.UserInitiatedShutdown" in out and "STOPPED OUTSIDE" in out,
       (r[-1:], out[-200:]))

    led3 = os.path.join(tmp, "l3.log")
    open(led3, "w", encoding="utf-8").write(
        start + "2026-11-07 23:00:00 ET  STOP   i-qqq  caller=wake_and_bake.py:1:x  pid=1  argv=x\n")
    run_audit(fpa, {"QQQ": qqq_halted["QQQ"],
                    "SPX": {"instance_id": "i-spx", "state": "stopped",
                            "state_reason_code": "Client.InstanceInitiatedShutdown",
                            "state_transition_reason": "User initiated (2026-11-08 05:00:01 GMT)"}}, led3, ack)
    ck("H7", len(rows(led3)) == 2, rows(led3))

    rc, out = run_audit(fpa, {"QQQ": {"instance_id": "i-qqq", "state": "running"}}, led, ack)
    ck("H8", rc == 1 and "NOT IN THE LEDGER" in out and "no stop since it was woken" not in out, out[-300:])

    led4 = os.path.join(tmp, "l4.log")
    open(led4, "w", encoding="utf-8").write(start)
    rc, out = run_audit(fpa, qqq_halted, led4, ack, ["--quiet"])
    ck("H9", rc == 0 and len(rows(led4)) == 2 and "SELF-HALTED" in out, (rc, rows(led4), out[-200:]))

    led5 = os.path.join(tmp, "l5.log")
    open(led5, "w", encoding="utf-8").write(start)
    rc, out = run_audit(fpa, {"QQQ": {"instance_id": "i-qqq", "state": "running",
                                      "state_reason_code": "Client.InstanceInitiatedShutdown",
                                      "state_transition_reason": "User initiated (2026-11-08 05:00:33 GMT)"}},
                        led5, ack)
    ck("H10", rc == 1 and len(rows(led5)) == 1 and "no stop since it was woken" in out, (rows(led5), out[-200:]))

    print(f"\n{'GREEN' if not FAILS else 'RED'}: {10 - len(FAILS)}/10")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
