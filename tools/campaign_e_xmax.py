#!/usr/bin/env python3
"""Campaign E - Xmax hour-scale arm (browser lane, chunked recording).

    .venv/bin/python tools/campaign_e_xmax.py --tiers 10,30,60 --reps 2
    .venv/bin/python tools/campaign_e_xmax.py --smoke      # 2-min shakedown

Mirrors the Lucy hour-scale arm through the browser lane: the 65-min
single-shot looped face streams in, the raw output track records in 10 s
chunks (memory-flat; a crash loses seconds, not the session). Xmax routes
domestically (no VPN), so this arm runs even when the tunnel is sagged.
Offline analysis (survival/fps from the capture; identity stills every
10 s via ffmpeg) matches the Lucy arm's readouts.
Journal: data/campaign-e/runs.jsonl (product_key xmax-x2.0, lens
P-browser - never merged with the Lucy rows).
"""
import argparse
import http.server
import json
import os
import shutil
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDIR = os.path.join(REPO, "data", "campaign-e")
STIM = os.path.join(EDIR, "stimulus-65min.mp4")

import tools.xmax_native_lane as lane
from tools.campaign_f import load_env
from tools.live_ab import mint_xmax_temp_key

PROMPT = "photorealistic, natural colors"


def make_chunk_handler(state):
    base = lane.make_handler(state)

    class H(base):
        def do_POST(self):
            if self.path.startswith("/upload_chunk"):
                from urllib.parse import parse_qs, urlparse
                qs = parse_qs(urlparse(self.path).query)
                run = qs.get("run", ["0"])[0]
                seq = int(qs.get("seq", ["0"])[0])
                n = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(n)
                if seq == -1:
                    state.final = True
                else:
                    with open(state.chunk_path, "ab") as f:
                        f.write(body)
                    state.nchunks += 1
                    state.last_chunk = time.monotonic()
                self.send_response(204)
                self.end_headers()
                return
            super().do_POST()
    return H


def run_tier(minutes, rep, chrome, state, port):
    name = "E-xmax-x2.0-%dmin-r%d" % (minutes, rep)
    sdir = os.path.join(EDIR, name)
    if os.path.exists(sdir):
        print("skip (exists):", name)
        return None
    os.makedirs(sdir, exist_ok=True)
    record_s = minutes * 60.0
    state.chunk_path = os.path.join(sdir, "capture.webm")
    state.nchunks = 0
    state.final = False
    state.last_chunk = time.monotonic()
    state.logs = []
    key = mint_xmax_temp_key(expire_s=int(record_s + 600), points=100000)
    url = ("http://127.0.0.1:%d/native_lane.html?key=%s&seconds=%g&run=%s"
           "&prompt=%s&chunk=1"
           % (port, key, record_s, name, PROMPT.replace(" ", "%20")))
    prof = "/tmp/chrome-xmax-e"
    shutil.rmtree(prof, ignore_errors=True)
    proc = subprocess.Popen(
        [chrome, "--headless=new", "--no-first-run", "--mute-audio",
         "--autoplay-policy=no-user-gesture-required",
         "--use-fake-ui-for-media-stream",
         "--user-data-dir=" + prof, "--window-size=1400,800", url],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.monotonic()
    deadline = t0 + record_s + 300
    try:
        while time.monotonic() < deadline and not state.final:
            time.sleep(5)
            # watchdog: no chunk for 120 s mid-run = dead page
            if (state.nchunks and not state.final
                    and time.monotonic() - state.last_chunk > 120):
                print("  chunk watchdog fired")
                break
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    wall = time.monotonic() - t0
    if not os.path.exists(state.chunk_path) or not state.nchunks:
        row = {"run_id": name, "product_key": "xmax-x2.0",
               "lens": "P-browser", "campaign": "E", "tier_min": minutes,
               "intended_s": record_s, "survived_s": 0.0,
               "survival_frac": 0.0, "frames": 0, "mean_fps": None,
               "stop_reason": "no chunks; " + "; ".join(
                   m for _, m in state.logs if "FATAL" in m)[:120],
               "stimulus": os.path.basename(STIM), "single_shot": True,
               "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                              time.gmtime())}
    else:
        mkv = os.path.join(sdir, "capture.mkv")
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel",
                        "error", "-i", state.chunk_path, "-c:v", "ffv1",
                        "-level", "3", mkv], check=True)
        a = lane.analyze(mkv)
        os.makedirs(os.path.join(sdir, "stills"), exist_ok=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mkv,
                        "-vf", "fps=1/10", os.path.join(
                            sdir, "stills", "t%04d.jpg")], check=True)
        surv = a["delivered_s"]
        row = {"run_id": name, "product_key": "xmax-x2.0",
               "lens": "P-browser", "campaign": "E", "tier_min": minutes,
               "intended_s": record_s, "survived_s": round(surv, 1),
               "survival_frac": round(surv / record_s, 3),
               "frames": a["frames"], "mean_fps": 30.0,
               "ttff_s": a["ttff_s"], "max_frozen_s": a["max_frozen_s"],
               "chunks": state.nchunks,
               "stop_reason": "completed" if state.final else "watchdog",
               "stimulus": os.path.basename(STIM), "single_shot": True,
               "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                              time.gmtime())}
    row["wall_s"] = round(wall, 1)
    with open(os.path.join(EDIR, "runs.jsonl"), "a") as f:
        f.write(json.dumps(row) + "\n")
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tiers", default="10,30,60")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    load_env()
    if not os.path.exists(STIM):
        print("build the 65-min stimulus first (campaign_e_hourscale.py)")
        return 1
    lane.CLIP = STIM
    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    state = lane.State()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0),
                                          make_chunk_handler(state))
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print("serving on %d" % port)
    tiers = [2] if args.smoke else [float(x) for x in args.tiers.split(",")]
    for rep in range(1, args.reps + 1):
        for m in tiers:
            r = run_tier(m, rep, chrome, state, port)
            if r:
                print("  %s survival=%.0f%% frames=%s stop=%s wall=%.0fs"
                      % (r["run_id"], 100 * r["survival_frac"],
                         r["frames"], r["stop_reason"], r["wall_s"]))
            time.sleep(5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
