# day_trader_pro/ec2ops.py — v0.1.1
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
            rec = {"instance_id": iid, "state": state,
                   "private_ip": inst.get("PrivateIpAddress", "")}
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


def start(instance_ids):
    ids = [i for i in instance_ids if i]
    if not ids:
        return
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
