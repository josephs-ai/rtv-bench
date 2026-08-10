#!/usr/bin/env python3
"""Composite-capture driver: the Xmax Lens P path and its residual bound.

Two subcommands:

  loopback --runs 8     In-page WebRTC loopback (canvas -> local peer pair ->
                        video), composited and recorded in-page. The measured
                        lag is the render+composite chain's own delay; its
                        RUN-TO-RUN variance is the residual bound that
                        summarise() requires before any composite figure can
                        exist. Writes data/composite-residual.json.

  xmax --seconds 25     The bridge path: canvas source -> Xmax X2.0 via their
                        SDK (temp key, direct China route) -> output pane ->
                        same composite recording. Lag extracted by impulse
                        xcorr between panes; reported with the residual bound.

Both record in-page (MediaRecorder on a canvas that draws BOTH panes in the
same rAF callback) - anything sharing a recorded frame was rendered at the
same instant, which is the plan sec 5.2 composite property without OBS.

Requires Google Chrome. Uses headless mode; falls back to opening a window.
"""
import argparse
import asyncio
import http.server
import json
import os
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE_DIR = os.path.join(REPO, "tools", "xmax_browser")
DATA = os.path.join(REPO, "data")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

FPS = 60.0  # composite recording rate


class UploadHandler(http.server.SimpleHTTPRequestHandler):
    uploads = {}

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=PAGE_DIR, **kw)

    def do_POST(self):
        if self.path.startswith("/upload"):
            length = int(self.headers["Content-Length"])
            body = self.rfile.read(length)
            key = self.path.split("?", 1)[1] if "?" in self.path else "run=0"
            path = os.path.join(tempfile.mkdtemp(prefix="composite-"),
                                key.replace("&", "_").replace("=", "-") + ".webm")
            with open(path, "wb") as f:
                f.write(body)
            UploadHandler.uploads[key] = path
            self.send_response(200)
            self.end_headers()

    def log_message(self, *a):
        pass


def serve():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), UploadHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def run_chrome(url, seconds, headless=True):
    args = [CHROME]
    if headless:
        args += ["--headless=new", "--mute-audio",
                 "--autoplay-policy=no-user-gesture-required",
                 "--use-fake-ui-for-media-stream"]
    args += ["--user-data-dir=" + tempfile.mkdtemp(prefix="chrome-prof-"), url]
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    return proc


def pane_luminance(webm_path):
    """Left/right pane mean-luminance series from the composite recording."""
    import av

    left, right = [], []
    with av.open(webm_path) as c:
        for frame in c.decode(video=0):
            arr = frame.to_ndarray(format="rgb24")
            h, w = arr.shape[:2]
            half = w // 2
            lum = arr.astype(np.float64) @ np.array((0.2126, 0.7152, 0.0722))
            left.append(float(lum[:, :half].mean()))
            right.append(float(lum[:, half:].mean()))
    return np.array(left), np.array(right)


def extract_lag(webm_path):
    """Impulse xcorr between panes; returns per-flash samples (composite path)."""
    from rtveval.latency import impulse
    from rtveval.latency.base import CapturePath

    left, right = pane_luminance(webm_path)
    if len(left) < 60:
        raise RuntimeError("recording too short: %d frames" % len(left))
    samples = impulse.measure(left, right, FPS)
    return [s._replace(capture_path=CapturePath.COMPOSITE_CAPTURE)
            for s in samples], len(left)


def one_run(mode, seconds, port, run_idx, extra=""):
    key = "run=%d&mode=%s" % (run_idx, mode)
    UploadHandler.uploads.pop(key, None)
    url = ("http://127.0.0.1:%d/session.html?mode=%s&seconds=%g&run=%d%s"
           % (port, mode, seconds, run_idx, extra))
    proc = run_chrome(url, seconds, headless=(mode == "loopback"))
    deadline = time.monotonic() + seconds + 45
    try:
        while time.monotonic() < deadline:
            if key in UploadHandler.uploads:
                return UploadHandler.uploads[key]
            time.sleep(1)
        raise TimeoutError("no upload from browser within window")
    finally:
        proc.terminate()


def cmd_loopback(args):
    srv, port = serve()
    per_run_p50 = []
    all_n = 0
    for i in range(args.runs):
        try:
            path = one_run("loopback", args.seconds, port, i)
            samples, nframes = extract_lag(path)
            good = [s.lag_ms for s in samples if s.confidence >= 0.3]
            if not good:
                print("run %d: no confident flashes (%d frames)" % (i, nframes))
                continue
            p50 = statistics.median(good)
            per_run_p50.append(p50)
            all_n += len(good)
            print("run %d: p50 %.1f ms over %d flashes" % (i, p50, len(good)))
        except Exception as e:
            print("run %d FAILED: %s" % (i, str(e)[:120]))
    srv.shutdown()

    if len(per_run_p50) < 3:
        print("not enough successful runs for a bound", file=sys.stderr)
        return 1
    spread = max(per_run_p50) - min(per_run_p50)
    bound = {
        "measured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "method": ("in-page WebRTC loopback through the identical composite "
                   "chain; per-run p50s"),
        "runs": len(per_run_p50),
        "per_run_p50_ms": [round(x, 1) for x in per_run_p50],
        "chain_delay_p50_ms": round(statistics.median(per_run_p50), 1),
        "residual_bound_ms": round(max(spread / 2,
                                       statistics.pstdev(per_run_p50) * 2), 1),
        "note": ("chain_delay is SUBTRACTED as the rig offset; residual_bound "
                 "is the +- carried by every composite figure (summarise() "
                 "refuses composite results without it)"),
    }
    out = os.path.join(DATA, "composite-residual.json")
    with open(out, "w") as f:
        json.dump(bound, f, indent=2)
    print("\nchain delay p50 %.1f ms; residual bound +-%.1f ms -> %s"
          % (bound["chain_delay_p50_ms"], bound["residual_bound_ms"], out))
    return 0


def mint_temp_key(expire_s=1800, points=500):
    from rtveval import config

    k = config.xmax().api_key.strip()
    req = urllib.request.Request(
        "https://api.xmaxai.com/open/api/v1/temporary-api-key",
        data=json.dumps({"expireSeconds": expire_s, "pointsLimit": points}).encode(),
        headers={"X-Api-Key": k, "Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        doc = json.loads(r.read().decode())
    if not doc.get("success"):
        raise RuntimeError("temp key mint failed: %s" % doc)
    return doc["data"]["temporaryApiKey"]


def cmd_xmax(args):
    bound_path = os.path.join(DATA, "composite-residual.json")
    if not os.path.exists(bound_path):
        print("no composite-residual.json - run `loopback` first; composite "
              "figures cannot exist without the measured bound", file=sys.stderr)
        return 1
    bound = json.load(open(bound_path))

    key = mint_temp_key()
    print("temp key minted (%s...)" % key[:6])
    srv, port = serve()
    try:
        path = one_run("xmax", args.seconds, port, 0, extra="&key=" + key)
    finally:
        srv.shutdown()
    samples, nframes = extract_lag(path)

    from rtveval.latency.base import summarise
    res = summarise(samples, lens="P",
                    rig_offset_ms=bound["chain_delay_p50_ms"],
                    min_confidence=0.3,
                    residual_bound_ms=bound["residual_bound_ms"])
    print("\nXMAX X2.0 Lens P (composite): %s" % res.headline())
    out = os.path.join(DATA, "xmax-lensP-composite.json")
    with open(out, "w") as f:
        json.dump({"headline": res.headline(), "result": res._asdict(),
                   "n_recorded_frames": nframes, "capture": path},
                  f, indent=2, default=str)
    print("-> %s" % out)
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    lp = sub.add_parser("loopback")
    lp.add_argument("--runs", type=int, default=8)
    lp.add_argument("--seconds", type=float, default=15.0)
    xm = sub.add_parser("xmax")
    xm.add_argument("--seconds", type=float, default=25.0)
    args = ap.parse_args()
    return cmd_loopback(args) if args.cmd == "loopback" else cmd_xmax(args)


if __name__ == "__main__":
    sys.exit(main())
