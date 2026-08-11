#!/usr/bin/env python3
"""One-shot network verdict for this rig. Run after ANY VPN change:

    .venv/bin/python tools/net_verify.py

Explains, in plain language, which products can work on the current
connection and why.
"""
import os
import socket
import struct
import subprocess
import sys


def stun(host, port, timeout=4):
    req = struct.pack("!HHI12s", 0x0001, 0, 0x2112A442, os.urandom(12))
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(req, (host, port))
        s.recvfrom(1024)
        return True
    except Exception:
        return False
    finally:
        s.close()


def https(host, timeout=12):
    r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                        "--max-time", str(timeout), "https://%s/" % host],
                       capture_output=True, text=True)
    code = r.stdout.strip()
    return code not in ("", "000"), code


def main():
    print("=== network verdict ===\n")

    udp_tunnel = stun("stun.cloudflare.com", 3478) or stun("stun.l.google.com", 19302)
    udp_china = stun("stun.miwifi.com", 3478)
    print("UDP through VPN tunnel : %s" % ("PASS" if udp_tunnel else "BLOCKED"))
    print("UDP direct (China)     : %s" % ("PASS" if udp_china else "BLOCKED"))

    results = {}
    for host in ("api.decart.ai", "api.reactor.inc", "platform.xmaxai.com"):
        ok, code = https(host)
        results[host] = ok
        print("%-22s : %s (HTTP %s)" % (host, "reachable" if ok else "UNREACHABLE", code))

    print("\n=== what this means ===")
    if udp_tunnel:
        print("* Lucy (Decart) video CAN flow - this VPN exit forwards UDP.")
        print("  -> note this server name; it is a 'Lucy works here' exit.")
    else:
        print("* Lucy (Decart) video CANNOT flow: signaling will connect but the")
        print("  pane stays black. This exit blocks UDP - try another server")
        print("  (protocol says WireGuard, but the EXIT decides UDP forwarding).")
    if not results["platform.xmaxai.com"]:
        print("* Xmax unreachable - the China split-route/DNS is broken again.")
    elif udp_china:
        print("* Xmax fully OK (API reachable, direct UDP passes).")
    else:
        print("* Xmax API reachable; direct UDP shaky - media may still work")
        print("  (ByteRTC can fall back), try it.")
    if not results["api.reactor.inc"]:
        print("* Reactor unreachable - LingBot/Happy Oyster runs would fail.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
