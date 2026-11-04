#!/usr/bin/env python3
"""
day_trader_pro/tools/dxlink_probe.py — v1.1
v1.1  2026-11-04  dtp r523 / FEED.15 — THE ZONE'S OWN NAMESERVERS ARE ASKED TOO (as OTV5 r70 does on the boxes). On
      2026-11-02/03 the recursive resolvers answered one dxlink node at a time while the host's Route 53 nameservers
      (ns-313.awsdns-39.com and peers; the host itself is delegated, dxfeed.com sits on devexperts.com's servers)
      answered the set. auth_nodes(): the NS set through the system resolver (the host first, then its parents), each
      NS name resolved, each asked for the host's A records over UDP - stdlib only, bounded by AUTH_BUDGET_S, never
      raises; a new source "auth" in candidates() beside seed / s3 / dns. Still no websocket frame, SETUP, AUTH or
      token: DNS questions and the one upgrade status line only. The operator, 2026-11-03: "Yes to the proposal".
      Gate tests/check_dxlink_probe.py X9 (a local UDP server plays the resolver and the zone's nameserver).
v1.0  2026-11-02  dtp r521 / FEED.14 — CONTROL TESTS THE DXLINK NODES ITSELF, WITH NO BOX UP AND NO CREDENTIALS.
      The operator, 2026-11-02 ~14:55 ET: "we should have the probe capable of firing from control to 'test' the
      waters, even when no boxes are up to ascertain network availability." On 2026-11-02 the dxFeed node
      129.153.134.53 answered 502 to every new websocket upgrade from 14:19 ET; the only way to see it was a box
      failing, or a hand-run upgrade from control.

WHAT ONE PROBE IS (per node IP, all of it bounded by --timeout):
  1. TCP connect to <ip>:443.
  2. TLS with SNI tasty-openapi-dxlink-md-ws.dxfeed.com and FULL verification (system CA store, hostname checked).
  3. ONE bare websocket upgrade request, `GET /realtime HTTP/1.1` with Host / Upgrade / Connection /
     Sec-WebSocket-Key / Sec-WebSocket-Version, and the STATUS LINE ONLY is read back.
  4. The socket is closed at once. Nothing else is ever written: no websocket frame, no SETUP, no AUTH, no
     quote token. Control holds no TastyTrade credentials and this file never opens a DXLink session.
  Verdict: "101" -> up; 5xx -> down; any other status -> error; TCP/TLS failure (including a certificate that does
  not verify) -> unreachable.

THE NODE LIST: (a) the seed data/dxlink_nodes_seed.json in the OTV5 checkout (r70 / FEED.13), (b) the fleet book
  under s3://<bucket>/fleet/dxlink_nodes/ when control can read it (read-only; a failure is named, not fatal),
  (c) fresh DNS answers for the host (3 lookups), (e, v1.1) the zone's authoritative nameservers' A records,
  (d) every node already in the status file. Only IPv4 literals.

THE STATUS FILE (var/feed_triage/dxlink_nodes_status.json, read by tools/feed_triage.py):
  {"probed_at": epoch, "host": ..., "sources": {...}, "nodes": {ip: {"state", "code", "latency_ms", "at", "since",
   "detail", "pending", "pending_n", "announced", "announced_at"}}}
  `state` is the CONFIRMED state; a change must be seen on CONFIRM_N consecutive probes before it is adopted.

MESSAGES: one line into the triage outbox (feed_triage.enqueue) when a node's confirmed state crosses up <-> not-up,
  at most one per node per MSG_GAP_S. The first sight of a node is a baseline and sends nothing.

    venv/bin/python tools/dxlink_probe.py               # probe, write the status file, enqueue transitions
    venv/bin/python tools/dxlink_probe.py --dry-run     # probe and print; write nothing, enqueue nothing
    venv/bin/python tools/dxlink_probe.py --show        # print the status file

Proposed schedule (NOT installed): every 60 s 09:00-16:05 ET on trading days, every 15 min otherwise
(tools/dtp-dxlink-probe.{service,timer} carry the RTH cadence).
"""
import argparse
import base64
import glob
import json
import os
import socket
import ssl
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

__version__ = "1.1"

HOST = "tasty-openapi-dxlink-md-ws.dxfeed.com"
PORT = 443
PATH = "/realtime"
TIMEOUT_S = float(os.environ.get("DTP_DXPROBE_TIMEOUT_S", "5"))
CONFIRM_N = 2                       # consecutive probes in a new state before it is adopted
MSG_GAP_S = 600                     # at most one message per node per 10 minutes
FORGET_S = 14 * 86400               # a node not up for 14 days leaves the list (seed nodes never do)
VAR_DIR = os.environ.get("DTP_TRIAGE_VAR", os.path.join(ROOT, "var", "feed_triage"))
STATUS_PATH = os.environ.get("DTP_DXPROBE_STATUS", os.path.join(VAR_DIR, "dxlink_nodes_status.json"))
OTV5_DIR = os.environ.get("DTP_OTV5_DIR", os.path.expanduser("~/OTV5"))
SEED_PATH = os.environ.get("DTP_DXLINK_SEED", os.path.join(OTV5_DIR, "data", "dxlink_nodes_seed.json"))
NODES_PREFIX = "fleet/dxlink_nodes"
UP_STATES = ("up",)


def _v4(ip):
    try:
        socket.inet_aton(ip)
        return ip.count(".") == 3
    except (OSError, TypeError):
        return False


# ── the probe: the only part that touches the network ─────────────────────────────────────────────────────
def upgrade_request(host=HOST, path=PATH, key=None):
    """The exact bytes sent - one HTTP upgrade request and nothing else (pinned by the gate)."""
    key = key or base64.b64encode(os.urandom(16)).decode()
    return ("GET %s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
            "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\nUser-Agent: dtp-dxlink-probe/%s\r\n\r\n"
            % (path, host, key, __version__)).encode("ascii")


def classify_status(code):
    if code == 101:
        return "up"
    if code is not None and 500 <= code <= 599:
        return "down"
    return "error"


def probe(ip, host=HOST, port=PORT, timeout=TIMEOUT_S, cafile=None):
    """-> {"state", "code", "latency_ms", "detail"}. Never raises. The socket is closed before returning."""
    t0 = time.monotonic()
    ctx = ssl.create_default_context(cafile=cafile)       # verify_mode CERT_REQUIRED + check_hostname
    raw = tls = None
    try:
        try:
            raw = socket.create_connection((ip, port), timeout=timeout)
        except OSError as exc:
            return {"state": "unreachable", "code": None, "latency_ms": None, "detail": "connect: %s" % exc}
        try:
            tls = ctx.wrap_socket(raw, server_hostname=host)
        except (ssl.SSLError, ssl.CertificateError, OSError) as exc:
            return {"state": "unreachable", "code": None, "latency_ms": None, "detail": "tls: %s" % exc}
        tls.settimeout(timeout)
        tls.sendall(upgrade_request(host))
        buf = b""
        while b"\r\n" not in buf and len(buf) < 1024:
            chunk = tls.recv(1024 - len(buf))
            if not chunk:
                break
            buf += chunk
        ms = round((time.monotonic() - t0) * 1000.0, 1)
        line = buf.split(b"\r\n", 1)[0].decode("latin-1", "replace").strip()
        parts = line.split(" ", 2)
        code = None
        if len(parts) >= 2 and parts[0].startswith("HTTP/") and parts[1].isdigit():
            code = int(parts[1])
        if code is None:
            return {"state": "error", "code": None, "latency_ms": ms, "detail": "no status line: %r" % line[:80]}
        return {"state": classify_status(code), "code": code, "latency_ms": ms, "detail": line[:120]}
    except (OSError, ssl.SSLError) as exc:
        return {"state": "unreachable", "code": None, "latency_ms": None, "detail": "io: %s" % exc}
    finally:
        for s in (tls, raw):
            if s is not None:
                try:
                    s.close()
                except OSError:
                    pass


# ── the node list ─────────────────────────────────────────────────────────────────────────────────────────
def seed_nodes(path=None):
    try:
        with open(path or SEED_PATH, encoding="utf-8") as fh:
            return [ip for ip in (json.load(fh).get("nodes") or {}) if _v4(ip)], None
    except (OSError, ValueError, AttributeError) as exc:
        return [], "seed unreadable (%s)" % exc


def s3_nodes():
    """The fleet book in S3, read-only. Control's role may lack List/Get here; that is reported, not raised."""
    try:
        import boto3
        from botocore.config import Config
        bucket = os.environ.get("OT_S3_BUCKET", "vertigo-warehouse-tx9ai")
        s3 = boto3.client("s3", config=Config(connect_timeout=5, read_timeout=10, retries={"max_attempts": 1}))
        out = set()
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=NODES_PREFIX + "/"):
            for obj in page.get("Contents", []) or []:
                d = json.loads(s3.get_object(Bucket=bucket, Key=obj["Key"])["Body"].read())
                out.update(ip for ip in (d.get("nodes") or {}) if _v4(ip))
        return sorted(out), None
    except Exception as exc:                                                   # noqa: BLE001
        return [], "s3 fleet list unreadable (%s)" % type(exc).__name__


def dns_nodes(host=HOST, lookups=3):
    out = set()
    err = None
    for _ in range(lookups):
        try:
            for fam, _t, _p, _c, sa in socket.getaddrinfo(host, PORT, socket.AF_INET, socket.SOCK_STREAM):
                out.add(sa[0])
        except OSError as exc:
            err = "dns: %s" % exc
    return sorted(out), (None if out else err)


# ── v1.1 (r523) — the authoritative nameservers (stdlib DNS over UDP; the same reading OTV5 candle_feed v5.6 does) ──
AUTH_BUDGET_S = 5.0
AUTH_NS_MAX = 4
DNS_PORT = 53


def _dns_query(name, qtype, qid):
    import struct
    q = b"".join(bytes([len(lab)]) + lab.encode("ascii") for lab in name.strip(".").split(".") if lab) + b"\0"
    return struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0) + q + struct.pack(">HH", qtype, 1)


def _dns_name(buf, off):
    labels, jumped, end, hops = [], False, off, 0
    while True:
        if off >= len(buf) or hops > 64:
            raise ValueError("bad name")
        n = buf[off]
        if n & 0xC0 == 0xC0:
            if off + 1 >= len(buf):
                raise ValueError("bad pointer")
            if not jumped:
                end = off + 2
            off = ((n & 0x3F) << 8) | buf[off + 1]
            jumped, hops = True, hops + 1
            continue
        if n == 0:
            return ".".join(labels), (end if jumped else off + 1)
        labels.append(buf[off + 1:off + 1 + n].decode("ascii", "replace"))
        off += 1 + n


def _dns_answers(buf, qid, qtype):
    """The answer records of qtype: A -> dotted IPv4, NS -> the nameserver name. [] on a bad or foreign reply."""
    import struct
    try:
        if len(buf) < 12:
            return []
        rid, flags, qd, an, _ns, _ar = struct.unpack(">HHHHHH", buf[:12])
        if rid != qid or not flags & 0x8000 or flags & 0x000F:
            return []
        off = 12
        for _ in range(qd):
            _, off = _dns_name(buf, off)
            off += 4
        out = []
        for _ in range(an):
            _, off = _dns_name(buf, off)
            if off + 10 > len(buf):
                break
            rtype, _c, _t, rdlen = struct.unpack(">HHIH", buf[off:off + 10])
            off += 10
            rd = off
            off += rdlen
            if rtype != qtype:
                continue
            if qtype == 1 and rdlen == 4:
                out.append(".".join(str(b) for b in buf[rd:rd + 4]))
            elif qtype == 2:
                out.append(_dns_name(buf, rd)[0])
        return out
    except (ValueError, IndexError):
        return []


def _dns_udp(server, name, qtype, timeout, port=None):
    import random
    qid = random.randint(1, 0xFFFF)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(max(0.2, timeout))
            s.sendto(_dns_query(name, qtype, qid), (server, port or DNS_PORT))
            buf, _ = s.recvfrom(4096)
        return _dns_answers(buf, qid, qtype)
    except OSError:
        return []


def _system_resolvers():
    out = []
    try:
        with open("/etc/resolv.conf", encoding="utf-8") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) >= 2 and parts[0] == "nameserver" and _v4(parts[1]):
                    out.append(parts[1])
    except OSError:
        pass
    return out


def _ns_lookup(name):
    try:
        for info in socket.getaddrinfo(name, DNS_PORT, socket.AF_INET, socket.SOCK_DGRAM):
            return [info[4][0]]
    except OSError:
        pass
    return []


def auth_nodes(host=HOST, budget=AUTH_BUDGET_S, resolvers=None, ns_lookup=None, port=None):
    """(ips, err): host's A records as its zone's authoritative nameservers answer them. Never raises."""
    try:
        deadline = time.monotonic() + budget
        res = resolvers if resolvers is not None else _system_resolvers()
        labels = host.strip(".").split(".")
        names = []
        for i in range(0, max(1, len(labels) - 1)):          # the host itself first (it is delegated)
            zone = ".".join(labels[i:])
            for r in res:
                left = deadline - time.monotonic()
                if left <= 0:
                    return [], "auth dns: out of time"
                names = _dns_udp(r, zone, 2, min(1.5, left), port=port)
                if names:
                    break
            if names:
                break
        if not names:
            return [], "auth dns: no NS found"
        out = []
        for nm in sorted(set(names))[:AUTH_NS_MAX]:
            for ns in (ns_lookup or _ns_lookup)(nm):
                left = deadline - time.monotonic()
                if left <= 0:
                    break
                for ip in _dns_udp(ns, host, 1, min(1.5, left), port=port):
                    if _v4(ip) and ip not in out:
                        out.append(ip)
        return sorted(out), (None if out else "auth dns: no A records")
    except Exception as exc:                                                   # noqa: BLE001
        return [], "auth dns: %s" % type(exc).__name__


def candidates(prev, seed=None, s3=None, dns=None, auth=None):
    """{ip: [sources]} - the union, deterministic. `seed/s3/dns/auth` are (list, err) pairs (injected by the gate)."""
    seed = seed if seed is not None else seed_nodes()
    s3 = s3 if s3 is not None else s3_nodes()
    dns = dns if dns is not None else dns_nodes()
    auth = auth if auth is not None else auth_nodes()
    found, notes = {}, {}
    for name, (ips, err) in (("seed", seed), ("s3", s3), ("dns", dns), ("auth", auth)):
        notes[name] = err or "%d node(s)" % len(ips)
        for ip in ips:
            found.setdefault(ip, []).append(name)
    now = time.time()
    for ip, n in ((prev or {}).get("nodes") or {}).items():
        if not _v4(ip):
            continue
        last_up = n.get("last_up") or n.get("since") or 0
        if ip in found or now - float(last_up or 0) <= FORGET_S:
            found.setdefault(ip, []).append("status")
    return dict(sorted(found.items())), notes


# ── the state machine (pure) ──────────────────────────────────────────────────────────────────────────────
def _updown(state):
    return "up" if state in UP_STATES else "not-up"


def update(prev, results, now, sources=None, notes=None):
    """(new_status, messages). `results` = {ip: probe()}. A change is adopted after CONFIRM_N probes; a
    message is produced only when the adopted state crosses up <-> not-up, at most once per MSG_GAP_S."""
    old = dict((prev or {}).get("nodes") or {})
    nodes, msgs = {}, []
    for ip in sorted(results):
        r = results[ip]
        o = dict(old.get(ip) or {})
        seen = r["state"]
        if not o.get("state"):                       # first sight: a baseline, never a message
            n = {"state": seen, "since": now, "pending": None, "pending_n": 0,
                 "announced": _updown(seen), "announced_at": 0}
        else:
            n = dict(o)
            if seen == o["state"]:
                n["pending"], n["pending_n"] = None, 0
            else:
                n["pending_n"] = (o.get("pending_n", 0) + 1) if o.get("pending") == seen else 1
                n["pending"] = seen
                if n["pending_n"] >= CONFIRM_N:
                    n["state"], n["since"], n["pending"], n["pending_n"] = seen, now, None, 0
            ud = _updown(n["state"])
            if ud != n.get("announced") and now - float(n.get("announced_at") or 0) >= MSG_GAP_S:
                was = n.get("announced")
                msgs.append("DXLINK NODE %s %s | %s -> %s (%s%s) | probed from control, no session opened"
                            % (ip, "UP" if ud == "up" else "DOWN", was, ud, n["state"],
                               (" " + str(r.get("code"))) if r.get("code") else ""))
                n["announced"], n["announced_at"] = ud, now
        n.update({"code": r.get("code"), "latency_ms": r.get("latency_ms"), "at": now,
                  "detail": str(r.get("detail") or "")[:160], "sources": (sources or {}).get(ip, [])})
        if n["state"] in UP_STATES:
            n["last_up"] = now
        elif o.get("last_up"):
            n["last_up"] = o["last_up"]
        nodes[ip] = n
    return {"probed_at": now, "host": HOST, "version": __version__, "sources": notes or {},
            "nodes": nodes}, msgs


def load_status(path=None):
    try:
        with open(path or STATUS_PATH, encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_status(d, path=None):
    p = path or STATUS_PATH
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=1, sort_keys=True)
    os.replace(tmp, p)


def run(dry=False, prober=probe, cand=None, now=None, status_path=None, enqueue=None):
    prev = load_status(status_path)
    found, notes = cand if cand is not None else candidates(prev)
    now = now or time.time()
    results = {ip: prober(ip) for ip in found}
    new, msgs = update(prev, results, now, sources=found, notes=notes)
    for ip in sorted(results):
        r = results[ip]
        print("[dxprobe] %-16s %-11s code=%-4s %8s  (%s)  %s" % (
            ip, r["state"], r.get("code") or "-",
            ("%.0fms" % r["latency_ms"]) if r.get("latency_ms") is not None else "-",
            ",".join(found[ip]), new["nodes"][ip]["detail"][:70]))
    print("[dxprobe] %d node(s): %d up | sources: %s" % (
        len(results), sum(1 for r in results.values() if r["state"] == "up"),
        "; ".join("%s %s" % kv for kv in sorted(notes.items()))))
    if dry:
        for m in msgs:
            print("[dxprobe] DRY RUN - would enqueue: %s" % m)
        print("[dxprobe] DRY RUN - status file not written")
        return 0, new, msgs
    save_status(new, status_path)
    if msgs:
        if enqueue is None:
            import feed_triage
            enqueue = feed_triage.enqueue
        for m in msgs:
            enqueue(m, source="dxlink_probe")
    return 0, new, msgs


def main(argv=None):
    ap = argparse.ArgumentParser(description="control-side dxlink node probe (no session, no credentials)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args(argv)
    if a.show:
        print(json.dumps(load_status(), indent=1, sort_keys=True))
        return 0
    return run(dry=a.dry_run)[0]


if __name__ == "__main__":
    sys.exit(main())
