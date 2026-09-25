# day_trader_pro/ec2ops.py — v0.1.4
# v0.1.4 (2026-09-24) — r424 / OPS.48. THE POWER LEDGER, WRITTEN AT THE
#   CHOKEPOINT RATHER THAN AT THE ERGONOMIC PATH. Every start and stop now
#   appends who/what/when/scope to logs/fleet_power.log.
#   🔴 THE FIRST SCOPING OF THIS ROW WOULD NOT HAVE CAUGHT THE INCIDENT THAT
#   PRODUCED IT. OPS.48 was first proposed as a log inside wake_and_bake; but
#   on 2026-09-24 SPX was woken by an ad-hoc `python -c` calling ec2ops.start()
#   directly, bypassing wake_and_bake entirely. A gate on the convenient path
#   never binds the improvised one — the same failure shape r420's P4 and
#   r417's reader gate both record. start()/stop() are where orchestrator,
#   wake_and_bake, eod_backfill, fleet.py and any throwaway one-liner all
#   converge, so this is the ONLY place a record binds all of them.
#   ⚠️ THE LEDGER CAN NEVER RAISE. A stop that failed because its LOG could not
#   be written would strand a running box — the precise cost this module exists
#   to avoid — so every logging failure is swallowed and the power operation
#   proceeds regardless. Pinned by check_fleet_power_log.py P4.
# v0.1.3 (2026-09-24) — r423 / OPS.47. ADD `describe_by_tag()`, the fleet's
#   single source of truth for WHO EXISTS. Filters on config.FLEET_TAG_KEY /
#   FLEET_TAG_VALUE and on running-or-stopped state, so a terminated box can
#   never be woken. 🔑 THE CONTROL BOX IS REFUSED BY NAME AND SAYS SO. The
#   guard does not ask whether control is tagged, because the failure being
#   defended against IS someone tagging it by mistake — a tag test would
#   authorise exactly the accident it is meant to stop. Pinned by
#   tests/check_fleet_discovery.py F2, which is the ship-blocker.
# v0.1.2 (2026-09-21) — r412 / OPS.37. THE INSTANCE RECORD CARRIES
#   `public_ip`, READ FROM THE REPLY IT ALREADY PARSES. `describe_instances`
#   returns `PublicIpAddress` in the same object the private IP comes from,
#   so the ping board gains the address an operator actually SSHes to from
#   outside the VPC at the cost of ZERO extra API calls and ZERO SSH.
#   🔑 ADDITIVE BY DESIGN. This dict reaches the close, the morning wake,
#   rotate_tokens and shadow_watch; a new KEY breaks no reader, whereas
#   widening fleet.get_fleet's tuple would have broken 21 call sites across
#   8 files (§23). Gated by tests/check_fleet_public_ip.py P1.
"""
Thin EC2 wrapper. Every AWS call in the project goes through here so that
mock mode is a single, well-contained switch.

Real mode uses boto3 with the default credential chain (instance role
preferred — attach an IAM role to the reporter; do NOT drop access keys on
disk). Mock mode uses a small JSON-backed state machine so the full
start -> running -> stop -> stopped lifecycle behaves realistically in the
devtools spool-up without touching AWS.

Public surface:
    describe_by_names(names)   -> {name: {"instance_id","state"}}
    start(instance_ids)        -> None
    stop(instance_ids)         -> None   (orderly stop, never terminate)
    wait_state(ids, state, timeout, interval) -> {id: reached_bool}
"""

import json
import os
import sys
import time

import config

_TERMINAL_STATES = ("terminated", "shutting-down")


# --------------------------------------------------------------------------
# boto3 client (lazy; only created in real mode)
# --------------------------------------------------------------------------
_client = None


def _ec2():
    global _client
    if _client is None:
        import boto3  # imported lazily so mock mode needs no boto3 installed
        _client = boto3.client("ec2", region_name=config.REGION)
    return _client


# --------------------------------------------------------------------------
# Mock state machine
# --------------------------------------------------------------------------
def _mock_load():
    try:
        with open(config.MOCK_STATE_PATH, "r") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _mock_save(state):
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(config.MOCK_STATE_PATH, "w") as fh:
        json.dump(state, fh, indent=2)


def _mock_instance_id(name):
    # Deterministic, obviously-fake id derived from the tag name.
    h = abs(hash(name)) % (16 ** 12)
    return "i-mock" + format(h, "012x")


def _mock_describe(names):
    state = _mock_load()
    out = {}
    changed = False
    for name in names:
        rec = state.get(name)
        if rec is None:
            # deterministic fake private ip in the 10.0.x.y space
            h = abs(hash(name))
            rec = {"instance_id": _mock_instance_id(name), "state": "stopped",
                   "private_ip": f"10.0.{h % 254}.{(h // 254) % 254}"}
            state[name] = rec
            changed = True
        rec.setdefault("private_ip", "10.0.0.0")
        out[name] = dict(rec)
    if changed:
        _mock_save(state)
    return out


def _mock_set_state(instance_ids, new_state):
    state = _mock_load()
    id_to_name = {v["instance_id"]: k for k, v in state.items()}
    for iid in instance_ids:
        name = id_to_name.get(iid)
        if name:
            state[name]["state"] = new_state
    _mock_save(state)


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------
def describe_by_tag(key=None, value=None):
    """Every live instance carrying tag `key`=`value` -> {Name: {...}}.

    🔑 r423 — THE FLEET IS WHAT AWS HOLDS, NOT WHAT A LIST REMEMBERS. Until
    now every fleet operation resolved `config.UNIVERSE` through
    `describe_by_names`, so a box that existed but was not in the list was
    invisible, and a symbol in the list with no box was a "missing instance"
    alert. Discovery by tag inverts that: the environment is the source of
    truth and the list becomes what it always should have been — a REPORTING
    universe, not an inventory of machines.
    ⚠️ THE CONVENTION ALREADY EXISTED AND ONLY THE CODE LAGGED. All fifteen
    trading boxes carry `Project=day_trader`; the control box and QQQ-TEST do
    not. `eod_report.py`'s docstring has claimed "every RUNNING box tagged
    Project=day_trader" since v0.3 while its code called
    `instance_registry.discover(config.UNIVERSE)`, and `check_iam.py` is the
    only file that genuinely reads the tag. This makes the code true.
    ⚠️ THE CONTROL BOX IS EXCLUDED BY NAME, NOT BY TAG. `config.REPORTER_TAG`
    was declared with the comment "It is never woken or stopped" and was read
    by NOTHING. Tag hygiene is now load-bearing for what trades, so the one
    machine that must never be woken is refused on its name regardless of what
    anybody tags it.
    """
    key = key or config.FLEET_TAG_KEY
    value = value or config.FLEET_TAG_VALUE
    if config.MOCK_AWS:
        return _mock_describe_by_tag(key, value)
    resp = _ec2().describe_instances(
        Filters=[{"Name": "tag:%s" % key, "Values": [value]}])
    out = {}
    for reservation in resp.get("Reservations", []):
        for inst in reservation.get("Instances", []):
            st = (inst.get("State") or {}).get("Name", "?")
            if st in ("terminated", "shutting-down"):
                continue
            name = _name_tag(inst)
            if not name:
                continue
            if name == config.REPORTER_TAG:
                # ⚠️ NAMED, NOT SILENT. If control ever acquires the fleet tag
                # the operator needs to see it, not have it quietly dropped.
                print("  ⚠️ %s carries %s=%s and is the CONTROL box — refusing "
                      "to include it" % (name, key, value))
                continue
            out[name] = {
                "instance_id": inst.get("InstanceId"),
                "state": st,
                "private_ip": inst.get("PrivateIpAddress", ""),
                "public_ip": inst.get("PublicIpAddress", ""),
                "pinned": False,
            }
    return out


def _mock_describe_by_tag(key, value):
    """Offline: every mock instance is treated as tagged."""
    state = _mock_load()
    return {n: {"instance_id": _mock_instance_id(n), "state": st,
                "private_ip": "", "public_ip": "", "pinned": False}
            for n, st in state.items() if n != config.REPORTER_TAG}


def describe_by_names(names):
    """
    Resolve a list of tag Names to {name: {"instance_id", "state"}}.
    Names with no live (non-terminated) instance are omitted from the result.
    On duplicate live matches for one name, the first non-terminated match is
    used and a warning dict is attached under key "_ambiguous".
    """
    if not names:
        return {}
    if config.MOCK_AWS:
        return _mock_describe(names)

    resp = _ec2().describe_instances(
        Filters=[{"Name": "tag:Name", "Values": list(names)}]
    )
    found = {}
    ambiguous = {}
    for reservation in resp.get("Reservations", []):
        for inst in reservation.get("Instances", []):
            state = inst["State"]["Name"]
            if state in _TERMINAL_STATES:
                continue
            name = _name_tag(inst)
            if name is None:
                continue
            iid = inst["InstanceId"]
            # 🔑 r412 — PUBLIC IP RIDES ALONG FREE. It is in the SAME
            # `describe_instances` reply the private IP is read from, so no
            # second API call and no SSH buys it. AWS RELEASES IT ON STOP and
            # assigns a new one on start, which is [[OPS.20]]'s whole reason
            # for putting it in the boot alert — reaching a misbehaving box
            # otherwise means the console and its two-factor login at exactly
            # the moment you need to be ON the box.
            # ⚠️ ADDITIVE, AND THAT IS DELIBERATE. This dict reaches the close,
            # the morning wake, rotate_tokens and shadow_watch; a new KEY
            # breaks no reader, where changing a shape would break 21 call
            # sites across 8 files (§23 — grep every reader, not just the one
            # you are editing).
            rec = {"instance_id": iid, "state": state,
                   "private_ip": inst.get("PrivateIpAddress", ""),
                   "public_ip": inst.get("PublicIpAddress", "")}
            if name in found:
                ambiguous.setdefault(name, [found[name]["instance_id"]]).append(iid)
                # Prefer running > pending > stopped; keep first otherwise.
                if _rank(state) > _rank(found[name]["state"]):
                    found[name] = rec
            else:
                found[name] = rec
    if ambiguous:
        found["_ambiguous"] = ambiguous
    return found


HERE = os.path.dirname(os.path.abspath(__file__))
POWER_LOG = os.environ.get("OT_FLEET_POWER_LOG",
                           os.path.join(HERE, "logs", "fleet_power.log"))


def _caller():
    """The first frame OUTSIDE this module — who actually asked for the power
    change. An ad-hoc `python -c` resolves to <string>, which is itself the
    answer worth having: it says no tool did this, a person or an agent typed
    it."""
    try:
        import traceback
        for fr in reversed(traceback.extract_stack()[:-2]):
            if os.path.basename(fr.filename) != "ec2ops.py":
                return f"{os.path.basename(fr.filename)}:{fr.lineno}:{fr.name}"
    except Exception:                                          # noqa: BLE001
        pass
    return "unknown"


def _power_log(action, ids, note=""):
    """Append one row to the power ledger. NEVER raises — see the v0.1.4 note."""
    try:
        try:
            import ettime
            ts = ettime.now_et().strftime("%Y-%m-%d %H:%M:%S")
        except Exception:                                      # noqa: BLE001
            import datetime
            from zoneinfo import ZoneInfo
            ts = datetime.datetime.now(
                ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S")
        argv = " ".join(sys.argv)[:200] or "-"
        mock = " MOCK" if config.MOCK_AWS else ""
        row = (f"{ts} ET  {action:<5}{mock}  {','.join(ids)}  "
               f"caller={_caller()}  pid={os.getpid()}  argv={argv}{note}\n")
        d = os.path.dirname(POWER_LOG)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(POWER_LOG, "a", encoding="utf-8") as fh:
            fh.write(row)
    except Exception:                                          # noqa: BLE001
        pass


def start(instance_ids):
    ids = [i for i in instance_ids if i]
    if not ids:
        return
    _power_log("START", ids)
    if config.MOCK_AWS:
        _mock_set_state(ids, "pending")
        # Simulate the transition to running immediately for the demo.
        _mock_set_state(ids, "running")
        return
    _ec2().start_instances(InstanceIds=ids)


def stop(instance_ids):
    """Orderly stop. Never terminate."""
    ids = [i for i in instance_ids if i]
    if not ids:
        return
    _power_log("STOP", ids)
    if config.MOCK_AWS:
        _mock_set_state(ids, "stopping")
        _mock_set_state(ids, "stopped")
        return
    _ec2().stop_instances(InstanceIds=ids)


def wait_state(instance_ids, desired, timeout=None, interval=None):
    """Poll until each id reaches `desired` or timeout. Returns {id: bool}."""
    ids = [i for i in instance_ids if i]
    timeout = config.START_CONFIRM_TIMEOUT if timeout is None else timeout
    interval = config.START_POLL_INTERVAL if interval is None else interval
    if config.MOCK_AWS:
        return {iid: True for iid in ids}

    reached = {iid: False for iid in ids}
    deadline = time.time() + timeout
    while time.time() < deadline and not all(reached.values()):
        resp = _ec2().describe_instances(InstanceIds=ids)
        for reservation in resp.get("Reservations", []):
            for inst in reservation.get("Instances", []):
                if inst["State"]["Name"] == desired:
                    reached[inst["InstanceId"]] = True
        if all(reached.values()):
            break
        time.sleep(interval)
    return reached


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _name_tag(inst):
    for tag in inst.get("Tags", []):
        if tag.get("Key") == "Name":
            return tag.get("Value")
    return None


def _rank(state):
    order = {"running": 3, "pending": 2, "stopping": 1, "stopped": 1}
    return order.get(state, 0)
