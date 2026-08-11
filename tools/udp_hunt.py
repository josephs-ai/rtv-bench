#!/usr/bin/env python3
"""Run this in YOUR terminal while switching Astrill servers:

    .venv/bin/python tools/udp_hunt.py

Each round fires a 30-probe UDP burst and prints the LOSS RATE - because
"UDP open" is not enough: single probes survive loss that kills sustained
video. Verdicts:

    CLEAN  (>=97% delivered)  - video will flow; pin this server
    LOSSY  (80-97%)           - video will stutter or starve; keep looking
    BLOCKED (<80%)            - move on

Switch servers in Astrill until you see CLEAN twice in a row, then leave
the VPN alone and tell Claude which server it is. Ctrl-C to stop.
"""
import os
import socket
import struct
import time

TARGETS = [("stun.cloudflare.com", 3478),
           ("turn.us-east-1.aws.prod.reactor.inc", 3478)]
BURST = 20


def burst(host, port):
    """Fire all probes, then collect replies - a blocked server costs ~1s,
    not BURST seconds of serial timeouts."""
    try:
        ip = socket.gethostbyname(host)
    except OSError:
        return None
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setblocking(False)
    for _ in range(BURST):
        req = struct.pack("!HHI12s", 0x0001, 0, 0x2112A442, os.urandom(12))
        try:
            s.sendto(req, (ip, port))
        except OSError:
            pass
        time.sleep(0.02)
    ok = 0
    deadline = time.time() + 1.5
    while time.time() < deadline and ok < BURST:
        try:
            s.recvfrom(1024)
            ok += 1
        except BlockingIOError:
            time.sleep(0.02)
        except OSError:
            break
    s.close()
    return ok / BURST


while True:
    parts = []
    worst = 1.0
    for host, port in TARGETS:
        r = burst(host, port)
        if r is None:
            parts.append("%s: DNS fail" % host.split(".")[1])
            worst = 0.0
            continue
        parts.append("%s: %d%%" % (host.split(".")[1], round(r * 100)))
        worst = min(worst, r)
    if worst >= 0.97:
        verdict = "*** CLEAN *** - pin this server!"
    elif worst >= 0.80:
        verdict = "LOSSY - video will starve, keep looking"
    else:
        verdict = "BLOCKED - try another server"
    print("%s  %s  -> %s" % (time.strftime("%H:%M:%S"), " | ".join(parts), verdict))
    time.sleep(2)
