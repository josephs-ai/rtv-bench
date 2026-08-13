#!/usr/bin/env python3
"""Campaign B - NATIVE Xmax lane (Lens P-browser).

    .venv/bin/python tools/xmax_native_lane.py --smoke     # one 15s slot
    .venv/bin/python tools/xmax_native_lane.py             # mirror pending rounds

Drives Xmax x2.0 through its OFFICIAL browser SDK (the only client for its
ByteRTC media plane) in headless Chrome: the conform reel plays as the input
track, the raw output track is recorded and shipped back. Runs on the native
XMAX_API_KEY - no Reactor, no tunnel (xmaxai.com is split-routed direct).

Outputs mirror campaign-B rounds so the pairwise judge can match lucy/xmax
captures by round_index (same duration mix, same prompt, same conform).
Captures -> data/campaign-b/captures/  (product xmax-x2.0, lens P-browser)
Journal  -> data/campaign-b-native/runs.jsonl (kept SEPARATE from the Lens M
journal - browser-lane reliability is its own lens, never mixed).
"""
import argparse
import glob
import http.server
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(REPO, "tools", "xmax_browser")
CLIP = os.path.join(REPO, "data", "reel", "input-xmax-x2.0.mp4")
CAPS = os.path.join(REPO, "data", "campaign-b", "captures")
OUTD = os.path.join(REPO, "data", "campaign-b-native")
PROMPT = "oil painting style, thick impasto brush strokes, warm palette"
REEL_DUR = 184.6

from tools.campaign_b import duration_for
from tools.live_ab import mint_xmax_temp_key


def load_env():
    for line in open(os.path.join(REPO, ".env")):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)


class State:
    upload = None          # (run, bytes)
    logs = []


def make_handler(state):
    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=WEB, **k)

        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path.startswith("/clip.mp4"):
                with open(CLIP, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
                self.wfile.write(data)
                return
            if self.path.startswith("/log"):
                from urllib.parse import parse_qs, urlparse
                m = parse_qs(urlparse(self.path).query).get("m", [""])[0]
                state.logs.append((time.monotonic(), m))
                print("  [page]", m[:110])
                self.send_response(204)
                self.end_headers()
                return
            super().do_GET()

        def do_POST(self):
            if self.path.startswith("/upload"):
                from urllib.parse import parse_qs, urlparse
                run = parse_qs(urlparse(self.path).query).get("run", ["0"])[0]
                n = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(n)
                state.upload = (run, body)
                self.send_response(204)
                self.end_headers()

    return H


def analyze(mkv_path, fps=30.0):
    """First non-black frame -> ttff; inter-frame stalls; delivered span."""
    import av
    import numpy as np
    first_live = None
    n = 0
    prev = None
    frozen_run = 0
    max_frozen = 0
    with av.open(mkv_path) as c:
        for f in c.decode(c.streams.video[0]):
            arr = f.to_ndarray(format="rgb24")
            n += 1
            if first_live is None and float(arr.mean()) > 8.0 \
                    and float(arr.std()) > 5.0:
                first_live = n
            if prev is not None:
                d = float(np.abs(arr.astype(np.int16)
                                 - prev.astype(np.int16)).mean())
                if d < 0.3:
                    frozen_run += 1
                    max_frozen = max(max_frozen, frozen_run)
                else:
                    frozen_run = 0
            prev = arr
    return {"frames": n,
            "ttff_s": round(first_live / fps, 2) if first_live else None,
            "delivered_s": round(n / fps, 2),
            "max_frozen_s": round(max_frozen / fps, 2)}


def run_slot(round_index, dur, chrome, port, state, temp_key):
    run_id = "B-xmax-x2.0-C0-r%04d" % round_index
    state.upload = None
    state.logs = []
    url = ("http://127.0.0.1:%d/native_lane.html?key=%s&seconds=%g&run=%s"
           "&prompt=%s" % (port, temp_key, dur, run_id,
                           PROMPT.replace(" ", "%20").replace(",", "%2C")))
    prof = "/tmp/chrome-xmax-native"
    shutil.rmtree(prof, ignore_errors=True)
    proc = subprocess.Popen(
        [chrome, "--headless=new", "--no-first-run", "--mute-audio",
         "--autoplay-policy=no-user-gesture-required",
         "--use-fake-ui-for-media-stream",
         "--user-data-dir=" + prof, "--window-size=1400,800", url],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.monotonic()
    deadline = t0 + dur + 120
    try:
        while time.monotonic() < deadline and state.upload is None:
            time.sleep(1)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    if state.upload is None:
        page_fatal = [m for _, m in state.logs if "FATAL" in m or "ERROR" in m]
        return {"run_id": run_id, "outcome": "F",
                "outcome_reasons": ["no output uploaded within window"]
                + page_fatal[:2], "wall_s": round(time.monotonic() - t0, 1)}

    run, webm = state.upload
    os.makedirs(CAPS, exist_ok=True)
    os.makedirs(OUTD, exist_ok=True)
    webm_p = os.path.join(OUTD, run_id + ".webm")
    with open(webm_p, "wb") as f:
        f.write(webm)
    mkv_p = os.path.join(CAPS, run_id + ".mkv")
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-i", webm_p, "-c:v", "ffv1", "-level", "3", mkv_p],
                   check=True)
    a = analyze(mkv_p)
    # Outcome under the P-browser lens: honest but coarse - S needs content
    # promptly and no long freezes; D = degraded; F = never went live.
    if a["ttff_s"] is None:
        outcome, reasons = "F", ["stream never showed content"]
        os.remove(mkv_p)  # no content -> not a capture
    elif a["max_frozen_s"] > 2.0:
        outcome, reasons = "D", ["frozen %.1fs" % a["max_frozen_s"]]
    elif a["ttff_s"] > 15.0:
        outcome, reasons = "D", ["ttff %.1fs" % a["ttff_s"]]
    else:
        outcome, reasons = "S", []
    if outcome != "F":
        with open(mkv_p.replace(".mkv", ".json"), "w") as f:
            json.dump({"run_id": run_id, "product": "xmax-x2.0",
                       "lens": "P-browser", "prompt": PROMPT, "fps": 30.0,
                       "frames": a["frames"], "clip": CLIP,
                       "duration_intended_s": dur,
                       "round_index": round_index}, f, indent=2)
    row = {"run_id": run_id, "product_key": "xmax-x2.0", "lens": "P-browser",
           "campaign": "B-native", "condition_id": "C0",
           "round_index": round_index, "outcome": outcome,
           "outcome_reasons": reasons, "duration_intended_s": dur,
           "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "wall_s": round(time.monotonic() - t0, 1), **a}
    with open(os.path.join(OUTD, "runs.jsonl"), "a") as f:
        f.write(json.dumps(row) + "\n")
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--rounds-from", type=int, default=None)
    ap.add_argument("--rounds-to", type=int, default=300)
    args = ap.parse_args()
    load_env()

    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    state = State()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0),
                                          make_handler(state))
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print("serving on %d" % port)

    done = set()
    for p in glob.glob(os.path.join(CAPS, "B-xmax-x2.0-*.json")):
        done.add(json.load(open(p))["round_index"])
    for p in glob.glob(os.path.join(OUTD, "runs.jsonl")):
        for line in open(p):
            r = json.loads(line)
            done.add(r["round_index"])  # F rows too: no retry spiral

    if args.smoke:
        rounds = [9999]
    else:
        start = args.rounds_from
        if start is None:
            # first round not yet journaled in the native lane
            start = 0
        rounds = [r for r in range(start, args.rounds_to) if r not in done]

    for r in rounds:
        dur = 15.0 if args.smoke else duration_for(r)
        print("slot r%04d (%gs)..." % (r, dur))
        try:
            temp_key = mint_xmax_temp_key(
                expire_s=int(dur + 300), points=2000)
        except Exception as e:
            print("  temp key mint failed: %s" % str(e)[:120])
            time.sleep(60)
            continue
        row = run_slot(r, dur, chrome, port, state, temp_key)
        print("  %s %s ttff=%s frames=%s wall=%.0fs"
              % (row["outcome"], ",".join(row["outcome_reasons"])[:50] or "-",
                 row.get("ttff_s"), row.get("frames"), row["wall_s"]))
        time.sleep(2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
