#!/usr/bin/env python3
"""Run this in YOUR terminal while switching Astrill servers:

    .venv/bin/python tools/udp_hunt.py

It probes Reactor's TURN relay every 5 s and prints OPEN/BLOCKED. Switch
servers in Astrill until you see OPEN, then leave the VPN alone and tell
Claude to launch the overnight run. Ctrl-C to stop.
"""
import socket
import time

HOST = "turn.us-east-1.aws.prod.reactor.inc"

while True:
    try:
        ip = socket.gethostbyname(HOST)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(3)
        s.sendto(b'\x00\x01\x00\x00!\x12\xa4B' + b'\x00' * 12, (ip, 3478))
        s.recvfrom(1024)
        print(time.strftime("%H:%M:%S"), "TURN UDP: *** OPEN *** - pin this server!")
    except socket.timeout:
        print(time.strftime("%H:%M:%S"), "TURN UDP: blocked - try another server")
    except Exception as e:
        print(time.strftime("%H:%M:%S"), "probe error:", type(e).__name__)
    time.sleep(5)
