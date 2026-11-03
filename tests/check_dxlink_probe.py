#!/usr/bin/env python3
"""
day_trader_pro/tests/check_dxlink_probe.py  v1.0
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
  X8  run() with zero boxes: writes the status file, enqueues the transition, and feed_triage's node gate reads it
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
import feed_triage as F  # noqa: E402

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
g1 = F.node_gate(status, "54.204.44.247", t + 150)
fake["54.204.44.247"] = UP
for k in (3, 4):
    P.run(prober=lambda ip: fake[ip], cand=cand, now=t + 60 * k + P.MSG_GAP_S, status_path=path,
          enqueue=lambda m, source=None: q.append(m))
g2 = F.node_gate(json.load(open(path)), "54.204.44.247", t + 240 + P.MSG_GAP_S + 5)
g3 = F.node_gate(json.load(open(path)), "129.153.134.53", t + 240 + P.MSG_GAP_S + 5)
ck("X8", status["nodes"]["129.153.134.53"]["state"] == "down" and len(q) == 2 and g1[0] is False and g2[0] is True
   and g3[0] is False,
   "status file written with no fleet; %d message(s); gate: all down -> %s, its node up -> %s, its node down -> %s"
   % (len(q), g1[0], g2[0], g3[0]))

print()
if FAILS:
    print(f"RED — {len(FAILS)} of {len(RAN)} check(s) failed: {' '.join(FAILS)}")
    sys.exit(1)
print(f"GREEN — {len(RAN)} checks")
