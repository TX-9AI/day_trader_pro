#!/usr/bin/env python3
# day_trader_pro/tests/check_fleet_public_ip.py — v1.0
# v1.0 (2026-09-21) — r412 / OPS.37. THE PING BOARD CARRIES THE PUBLIC IP, AND
#   THE 3-TUPLE EVERY OTHER CALLER DEPENDS ON IS PINNED SO IT CANNOT FOLLOW.
#   🔴 P2 IS THE REASON THIS FILE EXISTS. `fleet.get_fleet` is unpacked as
#   `(symbol, ip, state)` at TWENTY-ONE call sites across EIGHT files —
#   `eod_conductor_v2` (the close), `orchestrator` (the morning wake),
#   `rotate_tokens`, `shadow_watch`, `tools/fleet_reconcile`,
#   `tests/orb_budget_fleet` and seven more inside fleet.py itself. Widening
#   that tuple to carry the public IP would have been ONE line here and a
#   ValueError in every one of them, at 09:15 or at the close. §23 exactly —
#   grep every READER, not just the writer you are editing — and the same
#   half-sweep [[SH.2]], [[DEP.11]] and [[CFG.2]] each record.
#   🔑 SO THE SHAPE IS THE INVARIANT, NOT THE FEATURE. P2 is mutation-proven
#   against precisely the edit a future author would make.
#   ⚠️ AND P4 IS §0.5 ON A FIELD THAT ALREADY TAUGHT IT. [[OPS.20]] put this
#   same address in the boot alert and recorded that *"no IP field"* and
#   *"lookup failed"* must not look alike. Three facts render differently
#   here: an address; `(none)` for a RUNNING box with none, which is a real
#   finding; and `-` for a stopped box, where AWS has released it by design.
"""Gate: the public IP reaches the ping board without breaking get_fleet.

P1   the EC2 record carries public_ip, from the reply it already reads
P2   CONTROL — get_fleet still yields 3-tuples (21 call sites depend on it)
P3   get_fleet_ext yields 4-tuples and carries the address
P4   an absent address is NAMED, never blank (§0.5)
P5   the ping header shows the column
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_fails = []


def ck(tag, ok, msg=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {tag}  {msg}")
    if not ok:
        _fails.append(tag)


def main():
    try:
        import ec2ops
        import fleet
        import instance_registry
    except Exception as e:                                      # noqa: BLE001
        # ⚠️ SCOPED VACUOUS-GREEN, NOT A BLANKET ONE. `fleet` resolves
        # `US/Eastern`, which bare python3 on control cannot ([[OPS.22]],
        # [[CHK.9]]) — and the land gate runs every CHECK under bare python3.
        # Excused for THAT cause only; any other import failure stays RED.
        if "US/Eastern" in str(e) or "ZoneInfoNotFound" in e.__class__.__name__:
            print(f"  GREEN (VACUOUS) — {e.__class__.__name__}: {e}")
            print("  OPS.22: the legacy zone link is unresolvable under this "
                  "interpreter. Scoped to that cause; nothing else is excused.")
            return 0
        ck("P1", False, f"import failed for an UNEXCUSED reason: {e}")
        print(f"\nFAILED {len(_fails)}: {', '.join(_fails)}")
        return 1

    # ── P1 — the record carries it, read from the SAME reply. Driven against
    # a stubbed describe_instances so the check needs no AWS and no network.
    # ⚠️ THE STUB MIRRORS THE REAL CALL, READ FROM SOURCE. `describe_by_names`
    # calls `_ec2().describe_instances(Filters=...)` directly — not a
    # paginator. A stub shaped from a guess passes against itself and proves
    # nothing (§0.4); this one was corrected after the first cut failed for
    # exactly that reason.
    class _Stub:
        def describe_instances(self, **_kw):
            return {"Reservations": [{"Instances": [{
                "InstanceId": "i-abc", "State": {"Name": "running"},
                "PrivateIpAddress": "172.31.0.1",
                "PublicIpAddress": "3.4.5.6",
                "Tags": [{"Key": "Name", "Value": "ZZZ"}]}]}]}

    _real = getattr(ec2ops, "_ec2", None)
    try:
        ec2ops._ec2 = lambda: _Stub()
        if getattr(ec2ops.config, "MOCK_AWS", False):
            ec2ops.config.MOCK_AWS = False   # drive the REAL branch
        rec = ec2ops.describe_by_names(["ZZZ"]).get("ZZZ", {})
        ck("P1", rec.get("public_ip") == "3.4.5.6",
           f"describe_by_names records public_ip={rec.get('public_ip')!r}")
    except Exception as e:                                      # noqa: BLE001
        ck("P1", False, f"could not drive describe_by_names: {e}")
    finally:
        if _real is not None:
            ec2ops._ec2 = _real

    # ── P2/P3 — the shapes, driven through a stubbed discover so no EC2 call
    # is made and the assertion is about ARITY rather than about AWS.
    _rd = instance_registry.discover
    try:
        instance_registry.discover = lambda syms=None: (
            {"ZZZ": {"instance_id": "i-abc", "state": "running",
                     "private_ip": "172.31.0.1", "public_ip": "3.4.5.6"}}, {})
        rows = fleet.get_fleet(["ZZZ"])
        ck("P2", all(len(r) == 3 for r in rows),
           f"CONTROL — get_fleet still yields 3-tuples "
           f"(len={[len(r) for r in rows]}); 21 call sites depend on it")
        ext = fleet.get_fleet_ext(["ZZZ"])
        ck("P3", all(len(r) == 4 for r in ext) and ext[0][3] == "3.4.5.6",
           f"get_fleet_ext yields 4-tuples carrying {ext[0][3]!r}")
    except Exception as e:                                      # noqa: BLE001
        # ⚠️ REPORTED AS P3, NOT P2. P2 has ALREADY reported by the time
        # get_fleet_ext is reached, so reusing its tag here printed the id
        # TWICE with opposite verdicts — [[CHK.5]]'s exact shape, where "R1d
        # failed" named two different assertions. Found by RUNNING the
        # born-red pass rather than by reading the file.
        ck("P3", False, f"get_fleet_ext missing or raised: {e}")
    finally:
        instance_registry.discover = _rd

    # ── P4 — §0.5. Three facts, three renderings, none of them blank.
    try:
        a = fleet._pub("running", "1.2.3.4")
        b = fleet._pub("running", "")
        c = fleet._pub("stopped", "")
        ok = a == "1.2.3.4" and b and c and b != c and "" not in (b, c)
        ck("P4", ok,
           f"running+addr={a!r} running+none={b!r} stopped={c!r} — distinct "
           f"and never blank")
    except Exception as e:                                      # noqa: BLE001
        ck("P4", False, f"_pub missing or raised: {e}")

    # ── P5 — the column is actually on the board the operator reads.
    src = open(os.path.join(ROOT, "fleet.py"),
               encoding="utf-8", errors="replace").read()
    ck("P5", "'PUBLIC IP':<18" in src,
       "cmd_ping's header carries the PUBLIC IP column")

    print()
    if _fails:
        print(f"FAILED {len(_fails)}: {', '.join(_fails)}")
        return 1
    print("check_fleet_public_ip: all checks pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
