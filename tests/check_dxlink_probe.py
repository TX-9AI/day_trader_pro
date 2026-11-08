#!/usr/bin/env python3
"""
day_trader_pro/tests/check_dxlink_probe.py  v1.2
v1.2  2026-11-08  dtp r539 / TIMER.1 — feed_triage.py is deleted: X8 reads the confirmed node states from the status
      file itself (the reader left is dxlink_assign, gated by check_dxlink_assign); X10 (new): the default enqueue
      puts one "info" line in control's alert-router outbox and nothing else.
v1.1  2026-11-04  dtp r523 / FEED.15 — X9: the zone's authoritative nameservers are asked (a local UDP server plays the
      system resolver and the zone's nameserver, with a compressed answer name): the NS is found for the host, its A
      records come back as the "auth" source; with no server the answer is empty, named, and inside the budget.
v1.0  2026-11-02  dtp r521 / FEED.14 — THE CONTROL PROBE READS ONE STATUS LINE AND OPENS NO SESSION.

A local TLS server (a throwaway CA from `openssl`, a certificate for tasty-openapi-dxlink-md-ws.dxfeed.com) stands
in for a dxlink node and records every byte it receives.
  X1  101 Switching Protocols -> up
  X2  502 Bad Gateway -> down
  X3  a certificate for another name (same CA) -> unreachable (tls); an untrusted CA (system store) -> unreachable
  X4  nothing is sent after the upgrade request - the server reads to EOF after the headers and gets 0 bytes
  X5  no SETUP, AUTH or token ever leaves the probe (all received bytes; the module source sends once)
  X6  a closed port -> unreachable, quickly
  X7  the state machine: first sight is a baseline (no message); a change needs 2 probes; up->down and down->up
      each give ONE message; a repeat or a flap inside MSG_GAP_S gives none
  X8  run() with zero boxes: writes the status file, enqueues the transitions; the confirmed states follow them
  X10 the default enqueue writes one info line to the router outbox (alert_router.post_status)
"""
import json
import os
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)
import dxlink_probe as P  # noqa: E402
import alert_router as AR  # noqa: E402

FAILS, RAN = [], []
TMP = tempfile.mkdtemp(prefix="check_dxlink_probe_")


def ck(n, ok, msg):
    RAN.append(n)
    print(f"  {n:<4} {'PASS' if ok else 'FAIL'}  {msg}")
    if not ok:
        FAILS.append(n)


def sh(*a):
    subprocess.run(a, check=True, capture_output=True, cwd=TMP)


def make_certs():
    sh("openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", "ca.key", "-out", "ca.pem",
       "-days", "2", "-subj", "/CN=check-dxlink-ca", "-addext", "basicConstraints=critical,CA:TRUE",
       "-addext", "keyUsage=critical,keyCertSign,cRLSign")
    for name, cn in (("good", P.HOST), ("bad", "wrong.example.com")):
        sh("openssl", "req", "-newkey", "rsa:2048", "-nodes", "-keyout", name + ".key", "-out", name + ".csr",
           "-subj", "/CN=" + cn)
        with open(os.path.join(TMP, name + ".ext"), "w") as fh:
            fh.write("subjectAltName=DNS:%s\nbasicConstraints=CA:FALSE\nkeyUsage=digitalSignature,keyEncipherment\n"
                     "extendedKeyUsage=serverAuth\n" % cn)
        sh("openssl", "x509", "-req", "-in", name + ".csr", "-CA", "ca.pem", "-CAkey", "ca.key", "-CAcreateserial",
           "-out", name + ".pem", "-days", "2", "-extfile", name + ".ext")


class Node:
    """One fake dxlink node: TLS on 127.0.0.1, answers `status` to the first request, records what arrives."""

    def __init__(self, cert, status):
        self.got, self.after = b"", None
        self.ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.ctx.load_cert_chain(os.path.join(TMP, cert + ".pem"), os.path.join(TMP, cert + ".key"))
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        self.status = status
        self.th = threading.Thread(target=self.serve, daemon=True)
        self.th.start()

    def serve(self):
        try:
            c, _ = self.sock.accept()
            c.settimeout(5)
            try:
                s = self.ctx.wrap_socket(c, server_side=True)
            except (ssl.SSLError, OSError):
                c.close()
                return
            while b"\r\n\r\n" not in self.got:
                d = s.recv(4096)
                if not d:
                    break
                self.got += d
            s.sendall(("HTTP/1.1 %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n" % self.status).encode())
            tail = b""
            try:
                while True:
                    d = s.recv(4096)
                    if not d:
                        break
                    tail += d
            except (OSError, ssl.SSLError):
                pass
            self.after = tail
            self.got += tail
            s.close()
        except OSError:
            pass

    def join(self):
        self.th.join(6)
        self.sock.close()


make_certs()
CA = os.path.join(TMP, "ca.pem")

n1 = Node("good", "101 Switching Protocols")
r1 = P.probe("127.0.0.1", port=n1.port, cafile=CA, timeout=5)
n1.join()
ck("X1", r1["state"] == "up" and r1["code"] == 101, "101 -> %s %s" % (r1["state"], r1["code"]))

n2 = Node("good", "502 Bad Gateway")
r2 = P.probe("127.0.0.1", port=n2.port, cafile=CA, timeout=5)
n2.join()
ck("X2", r2["state"] == "down" and r2["code"] == 502, "502 -> %s %s" % (r2["state"], r2["code"]))

n3 = Node("bad", "101 Switching Protocols")
r3 = P.probe("127.0.0.1", port=n3.port, cafile=CA, timeout=5)
n3.join()
n3b = Node("good", "101 Switching Protocols")
r3b = P.probe("127.0.0.1", port=n3b.port, cafile=None, timeout=5)      # the system store does not trust the test CA
n3b.join()
ck("X3", r3["state"] == "unreachable" and "tls" in r3["detail"] and r3b["state"] == "unreachable"
   and n3.got == b"" and n3b.got == b"",
   "wrong name -> %s (%s); untrusted CA -> %s; nothing sent to either" % (r3["state"], r3["detail"][:60],
                                                                         r3b["state"]))

ck("X4", n1.after == b"" and n2.after == b"" and n1.got.endswith(b"\r\n\r\n") and n1.got.count(b"\r\n\r\n") == 1,
   "after the upgrade request the probe sent %r / %r and closed" % (n1.after, n2.after))

allb = n1.got + n2.got
src = open(P.__file__, encoding="utf-8").read()
ck("X5", all(w not in allb for w in (b"SETUP", b"AUTH", b"token", b"Authorization", b"Cookie"))
   and allb.startswith(b"GET /realtime HTTP/1.1\r\nHost: " + P.HOST.encode()) and src.count(".sendall(") == 1
   and "quote-token" not in src and "api-quote-tokens" not in src,
   "received only the upgrade GET; one sendall in the module; no token endpoint")

s = socket.socket()
s.bind(("127.0.0.1", 0))
dead = s.getsockname()[1]
s.close()
t0 = time.monotonic()
r6 = P.probe("127.0.0.1", port=dead, cafile=CA, timeout=3)
ck("X6", r6["state"] == "unreachable" and time.monotonic() - t0 < 3.5, "closed port -> %s" % r6["state"])

UP = {"state": "up", "code": 101, "latency_ms": 10.0, "detail": "HTTP/1.1 101"}
DOWN = {"state": "down", "code": 502, "latency_ms": 10.0, "detail": "HTTP/1.1 502"}
t = 1_000_000.0
st, m0 = P.update({}, {"1.1.1.1": UP, "2.2.2.2": DOWN}, t)
st, m1 = P.update(st, {"1.1.1.1": DOWN, "2.2.2.2": DOWN}, t + 60)             # 1st down probe: pending
st, m2 = P.update(st, {"1.1.1.1": DOWN, "2.2.2.2": DOWN}, t + 120)            # confirmed: one message
st, m3 = P.update(st, {"1.1.1.1": DOWN, "2.2.2.2": DOWN}, t + 180)            # repeat: none
st, m4 = P.update(st, {"1.1.1.1": UP, "2.2.2.2": DOWN}, t + 240)
st, m5 = P.update(st, {"1.1.1.1": UP, "2.2.2.2": DOWN}, t + 300)              # up confirmed but inside the gap
st, m6 = P.update(st, {"1.1.1.1": UP, "2.2.2.2": DOWN}, t + 120 + P.MSG_GAP_S)
ck("X7", m0 == [] and m1 == [] and len(m2) == 1 and "1.1.1.1 DOWN" in m2[0] and m3 == [] and m4 == [] and m5 == []
   and len(m6) == 1 and "1.1.1.1 UP" in m6[0] and st["nodes"]["2.2.2.2"]["state"] == "down",
   "baseline silent; down after 2 probes (1 msg); no repeat; flap inside the gap silent; up after the gap (1 msg)")

path = os.path.join(TMP, "status.json")
q = []
fake = {"129.153.134.53": DOWN, "54.204.44.247": UP}
cand = ({ip: ["seed"] for ip in fake}, {"seed": "2 node(s)"})
P.run(prober=lambda ip: fake[ip], cand=cand, now=t, status_path=path, enqueue=lambda m, source=None: q.append(m))
fake["54.204.44.247"] = DOWN
for k in (1, 2):
    P.run(prober=lambda ip: fake[ip], cand=cand, now=t + 60 * k, status_path=path,
          enqueue=lambda m, source=None: q.append(m))
status = json.load(open(path))
g1 = (status["nodes"]["54.204.44.247"]["state"] == "up",)
fake["54.204.44.247"] = UP
for k in (3, 4):
    P.run(prober=lambda ip: fake[ip], cand=cand, now=t + 60 * k + P.MSG_GAP_S, status_path=path,
          enqueue=lambda m, source=None: q.append(m))
_st2 = json.load(open(path))
g2 = (_st2["nodes"]["54.204.44.247"]["state"] == "up",)
g3 = (_st2["nodes"]["129.153.134.53"]["state"] == "up",)
ck("X8", status["nodes"]["129.153.134.53"]["state"] == "down" and len(q) == 2 and g1[0] is False and g2[0] is True
   and g3[0] is False,
   "status file written with no fleet; %d message(s); 54.204 up after all down -> %s, after recovery -> %s, 129.153 up -> %s"
   % (len(q), g1[0], g2[0], g3[0]))

# ── X10 (v1.2): the default enqueue is the router outbox ─────────────────────────────────────────────────────
_ar_dir = os.path.join(TMP, "alert_router")
_old_sd, AR.STATE_DIR = AR.STATE_DIR, _ar_dir
try:
    P.enqueue("DXLINK NODE 1.1.1.1 DOWN (test)")
finally:
    AR.STATE_DIR = _old_sd
_ob = os.path.join(_ar_dir, "outbox")
_files = sorted(os.listdir(_ob)) if os.path.isdir(_ob) else []
_rec = json.load(open(os.path.join(_ob, _files[0]))) if len(_files) == 1 else {}
ck("X10", len(_files) == 1 and _rec.get("kind") == "info" and "1.1.1.1 DOWN" in _rec.get("text", ""),
   "router outbox: %d file(s), kind %r" % (len(_files), _rec.get("kind")))

# ── X9 (v1.1): the authoritative nameservers ──────────────────────────────────────────────────────────────────
import struct  # noqa: E402


def _dns_reply(q, answers):
    """A reply to query q carrying `answers` = [(qtype, rdata bytes)], each owner name a pointer to the question."""
    qid = struct.unpack(">H", q[:2])[0]
    qend = 12
    while q[qend] != 0:
        qend += 1 + q[qend]
    question = q[12:qend + 5]
    body = b""
    for qt, rd in answers:
        body += b"\xc0\x0c" + struct.pack(">HHIH", qt, 1, 60, len(rd)) + rd
    return struct.pack(">HHHHHH", qid, 0x8180, 1, len(answers), 0, 0) + question + body


def _enc(name):
    return b"".join(bytes([len(x)]) + x.encode() for x in name.split(".")) + b"\0"


usock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
usock.bind(("127.0.0.1", 0))
uport = usock.getsockname()[1]
asked = []


def _dns_serve():
    usock.settimeout(8)
    try:
        while True:
            q, addr = usock.recvfrom(4096)
            qt = struct.unpack(">H", q[-4:-2])[0]
            asked.append(qt)
            if qt == 2:
                usock.sendto(_dns_reply(q, [(2, _enc("ns.local"))]), addr)
            elif qt == 1:
                usock.sendto(_dns_reply(q, [(1, bytes([10, 1, 1, 1])), (1, bytes([10, 1, 1, 2]))]), addr)
    except OSError:
        pass


threading.Thread(target=_dns_serve, daemon=True).start()
a9 = P.auth_nodes(budget=3.0, resolvers=["127.0.0.1"], ns_lookup=lambda n: ["127.0.0.1"] if n == "ns.local" else [],
                  port=uport)
usock.close()
t0 = time.monotonic()
s9 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s9.bind(("127.0.0.1", 0))
dead9 = s9.getsockname()[1]
s9.close()
b9 = P.auth_nodes(budget=1.0, resolvers=["127.0.0.1"], port=dead9)
el9 = time.monotonic() - t0
c9, n9 = P.candidates({}, seed=([], None), s3=([], None), dns=(["10.1.1.1"], None), auth=a9)
ck("X9", a9 == (["10.1.1.1", "10.1.1.2"], None) and asked[:1] == [2] and 1 in asked and b9[0] == [] and b9[1]
   and el9 < 1.6 and c9.get("10.1.1.2") == ["auth"] and c9.get("10.1.1.1") == ["dns", "auth"] and "auth" in n9,
   "auth=%s asked=%s; dead=%s in %.1fs; candidates=%s" % (a9, asked, b9, el9, c9))

print()
if FAILS:
    print(f"RED — {len(FAILS)} of {len(RAN)} check(s) failed: {' '.join(FAILS)}")
    sys.exit(1)
print(f"GREEN — {len(RAN)} checks")
