#!/usr/bin/env python3
"""
tests/check_fleet_discovery.py  v1.0
v1.0  2026-09-24  dtp r423 / OPS.47 — THE FLEET IS DISCOVERED, NOT RECITED.
      Operator, 2026-09-24: *"I want that number to be based on however many
      are in the current instance map. If there's 15 in the instance map then
      wake 15, if there's 20 then wake 20"* and *"is it even important at all
      to have a universe — yes for the morning report, but no for the waking."*
      🔑 F2 IS THE CHECK THAT DECIDES WHETHER THIS SHIPS. Discovery by tag
      makes TAG HYGIENE LOAD-BEARING FOR WHAT TRADES: anything carrying
      Project=day_trader gets woken. The one machine that must never be woken
      is the control box, and it is refused BY NAME regardless of what it is
      tagged — because the failure being guarded against is precisely someone
      tagging it by mistake.
      ⚠️ F4 PINS THE POINT OF THE CHANGE: a box that carries the tag but is
      ABSENT from UNIVERSE is still woken, and is NAMED. If F4 ever goes green
      by dropping the box instead, the universe has crept back into the wake
      path and the operator's instruction has been quietly reversed.
      ⚠️ F3 IS THE FLOOR. A discovery that returns nothing — no credentials, an
      API failure, a fleet nobody tagged — must wake ALWAYS_ON rather than
      nothing. A zero-box morning that looks like a quiet one is the
      plausible-silence class this repo keeps paying for.
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


class _FakeEC2:
    """describe_instances that honours a tag Filter, like the real one."""

    def __init__(self, instances):
        self._inst = instances          # [(name, state, tags{})]

    def describe_instances(self, Filters=None):
        want = {}
        for f in (Filters or []):
            if f["Name"].startswith("tag:"):
                want[f["Name"][4:]] = set(f["Values"])
        out = []
        for name, state, tags in self._inst:
            if any(tags.get(k) not in v for k, v in want.items()):
                continue
            # ⚠️ THE `Name` TAG IS ALWAYS PRESENT, because the SYMBOL IS THE
            # NAME. My first fixture omitted it and every check returned an
            # empty fleet — the code was right and the fixture was wrong, which
            # is §0.4 and is why it is written down rather than quietly fixed.
            all_tags = dict(tags)
            all_tags.setdefault("Name", name)
            out.append({
                "InstanceId": "i-" + name.lower(),
                "State": {"Name": state},
                "PrivateIpAddress": "10.0.0.1",
                "PublicIpAddress": "1.2.3.4",
                "Tags": [{"Key": k, "Value": v} for k, v in all_tags.items()],
            })
        return {"Reservations": [{"Instances": out}]}


def main():
    try:
        import config
        import ec2ops
    except Exception as exc:                                  # noqa: BLE001
        ck("F0", False, f"cannot import config/ec2ops ({exc})")
        print("\nRED — 1 check(s) failed: F0")
        return 1

    KEY = getattr(config, "FLEET_TAG_KEY", None)
    VAL = getattr(config, "FLEET_TAG_VALUE", None)
    if not KEY or not VAL:
        for t in ("F1", "F2", "F3", "F4", "F5"):
            ck(t, False, "config.FLEET_TAG_KEY / FLEET_TAG_VALUE are absent")
        print(f"\nRED — {len(_fails)} check(s) failed: {' '.join(_fails)}")
        return 1

    dbt = getattr(ec2ops, "describe_by_tag", None)
    if dbt is None:
        for t in ("F1", "F2", "F3", "F4"):
            ck(t, False, "ec2ops.describe_by_tag is absent")
        print(f"\nRED — {len(_fails)} check(s) failed: {' '.join(_fails)}")
        return 1

    reporter = getattr(config, "REPORTER_TAG", "1-REPORTER")
    tagged = {KEY: VAL}
    real, mock = ec2ops._ec2, config.MOCK_AWS
    config.MOCK_AWS = False
    try:
        # ── F1 — only tagged, live instances come back ───────────────────
        ec2ops._ec2 = lambda: _FakeEC2([
            ("SPX", "running", tagged), ("QQQ", "stopped", tagged),
            ("NOPE", "running", {}),                 # untagged -> excluded
            ("GONE", "terminated", tagged),          # dead -> excluded
        ])
        got = dbt()
        ck("F1", set(got) == {"SPX", "QQQ"},
           f"discovered {sorted(got)} (want SPX,QQQ — untagged and terminated "
           f"must not appear)")

        # ── F2 — THE CONTROL BOX IS REFUSED BY NAME, EVEN IF TAGGED ──────
        ec2ops._ec2 = lambda: _FakeEC2([
            ("SPX", "running", tagged),
            (reporter, "running", tagged),           # mistagged control box
        ])
        got = dbt()
        ck("F2", reporter not in got and "SPX" in got,
           f"discovered {sorted(got)} — {reporter} carries the fleet tag and "
           f"MUST still be refused; it is the one box that must never wake")

        # ── F3 — an empty fleet is empty, and the CALLER floors it ───────
        ec2ops._ec2 = lambda: _FakeEC2([("NOPE", "running", {})])
        got = dbt()
        floor = list(getattr(config, "ALWAYS_ON", []))
        ck("F3", got == {} and len(floor) >= 1,
           f"discovery returned {sorted(got)} (want empty) and ALWAYS_ON floor "
           f"is {floor} (must be non-empty so a blind morning still trades)")

        # ── F4 — UNIVERSE DOES NOT GATE THE WAKE ─────────────────────────
        alien = "ZZZZ"
        assert alien not in config.UNIVERSE
        ec2ops._ec2 = lambda: _FakeEC2([
            ("SPX", "running", tagged), (alien, "running", tagged),
        ])
        got = dbt()
        ck("F4", alien in got,
           f"a tagged box ABSENT from UNIVERSE must still be discovered; "
           f"got {sorted(got)}. If this fails, the universe has crept back "
           f"into the wake path")
    finally:
        ec2ops._ec2, config.MOCK_AWS = real, mock

    # ── F5 — the reporting universe carries the new names ────────────────
    _uni = set(config.UNIVERSE)
    _have = sorted({"AAL", "SOFI"} & _uni)
    ck("F5", {"AAL", "SOFI"} <= _uni,
       f"UNIVERSE has {len(config.UNIVERSE)} names; of AAL/SOFI present: "
       f"{_have or 'neither'}")

    if _fails:
        print(f"\nRED — {len(_fails)} check(s) failed: {' '.join(_fails)}")
        return 1
    print("\nGREEN — the fleet is discovered by tag, and control is never in it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
