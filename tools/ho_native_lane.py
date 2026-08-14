#!/usr/bin/env python3
"""Campaign C - Happy Oyster captures via the DEDICATED SDK (browser lane).

    .venv/bin/python tools/ho_native_lane.py --smoke      # one G1 capture
    .venv/bin/python tools/ho_native_lane.py --reps 3     # full G-matrix

Reactor team's guidance: HO streams on a SECOND WebRTC (Aliyun RTC)
connection that only @reactor-models/happy-oyster opens - so we run their
official SDK in headless Chrome (ho_lane.html + vendor/ho-sdk.bundle.js),
record the bound <video> via canvas, and ship webm home. Flow per capture:
connect(jwt) -> createWorld({prompt}) -> startTravel() -> record; G7 steers
mid-travel with instruct() (directing mode, accept/reject recorded).

Outputs land in data/campaign-c-gen/ in the standard capture format
(FFV1 + meta) -> metrics/judge/audit run unchanged. Lens: browser-capture.
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
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(REPO, "tools", "xmax_browser")
OUT = os.path.join(REPO, "data", "campaign-c-gen")

from tools.campaign_c_gen import GPROMPTS  # same prompts, same assertions


def load_env():
    for line in open(os.path.join(REPO, ".env")):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)


def mint_jwt():
    req = urllib.request.Request(
        "https://api.reactor.inc/tokens", method="POST",
        headers={"Reactor-API-Key": os.environ["REACTOR_API_KEY"].strip()})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["jwt"]


class State:
    upload = None
    logs = []


def make_handler(state):
    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=WEB, **k)

        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path.startswith("/log"):
                from urllib.parse import parse_qs, urlparse
                m = parse_qs(urlparse(self.path).query).get("m", [""])[0]
                state.logs.append((time.monotonic(), m))
                print("  [page]", m[:120])
                self.send_response(204)
                self.end_headers()
                return
            try:
                super().do_GET()
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_POST(self):
            if self.path.startswith("/upload"):
                from urllib.parse import parse_qs, urlparse
                run = parse_qs(urlparse(self.path).query).get("run", ["0"])[0]
                n = int(self.headers.get("Content-Length", 0))
                state.upload = (run, self.rfile.read(n))
                self.send_response(204)
                self.end_headers()

    return H


def one_capture(gid, prompt, record_s, steer, rep, port, state, chrome):
    from urllib.parse import quote
    name = "happy-oyster-%s-r%d" % (gid, rep)
    state.upload = None
    state.logs = []
    jwt = mint_jwt()
    url = ("http://127.0.0.1:%d/ho_lane.html?jwt=%s&mode=directing"
           "&seconds=%g&run=%s&prompt=%s" % (port, quote(jwt), record_s,
                                             name, quote(prompt)))
    if steer:
        url += "&steer=%s&steer_at=15" % quote(steer)
    prof = "/tmp/chrome-ho-lane"
    shutil.rmtree(prof, ignore_errors=True)
    proc = subprocess.Popen(
        [chrome, "--headless=new", "--no-first-run", "--mute-audio",
         "--autoplay-policy=no-user-gesture-required",
         "--use-fake-ui-for-media-stream",
         "--user-data-dir=" + prof, "--window-size=1400,800", url],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.monotonic()
    # world build ~30-80s + travel + upload
    deadline = t0 + 240 + record_s
    try:
        while time.monotonic() < deadline and state.upload is None:
            time.sleep(1)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    steer_log = [m for _, m in state.logs if "STEER" in m]
    if state.upload is None:
        fatal = [m for _, m in state.logs if "FATAL" in m or "ERROR" in m
                 or "REJECTION" in m]
        print("  FAILED: no upload; page said: %s" % "; ".join(fatal[-2:]))
        return False

    run, webm = state.upload
    webm_p = os.path.join(OUT, name + ".webm")
    with open(webm_p, "wb") as f:
        f.write(webm)
    mkv_p = os.path.join(OUT, name + ".mkv")
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-i", webm_p, "-c:v", "ffv1", "-level", "3", mkv_p],
                   check=True)
    import av
    with av.open(mkv_p) as c:
        frames = sum(1 for _ in c.decode(c.streams.video[0]))
    meta = {"product": "happy-oyster", "model": "happy-oyster-director",
            "lens": "browser-capture (dedicated SDK)", "g": gid, "rep": rep,
            "prompt": prompt, "steer": steer,
            "steer_sent_at_s": 15.0 if steer else None,
            "steer_ack": "; ".join(steer_log) or None,
            "frames": frames, "went_live": frames > 30, "fps": 30.0,
            "wall_s": round(time.monotonic() - t0, 1),
            "capture": mkv_p}
    with open(os.path.join(OUT, name + ".json"), "w") as f:
        json.dump(meta, f, indent=2)
    print("  frames=%d wall=%.0fs steer=%s" % (frames, meta["wall_s"],
                                               meta["steer_ack"]))
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    load_env()
    os.makedirs(OUT, exist_ok=True)

    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    state = State()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0),
                                          make_handler(state))
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print("serving on %d" % port)

    if args.smoke:
        gid, ho_prompt, _, secs, steer = GPROMPTS[0]
        one_capture(gid, ho_prompt, secs, steer, 99, port, state, chrome)
        return 0

    for rep in range(1, args.reps + 1):
        for gid, ho_prompt, _, secs, steer in GPROMPTS:
            name = "happy-oyster-%s-r%d" % (gid, rep)
            if os.path.exists(os.path.join(OUT, name + ".json")):
                mp = json.load(open(os.path.join(OUT, name + ".json")))
                if mp.get("went_live"):
                    print("skip (live capture exists):", name)
                    continue
            print("capture %s (%gs)..." % (name, secs))
            try:
                one_capture(gid, ho_prompt, secs, steer, rep, port,
                            state, chrome)
            except Exception as e:
                print("  FAILED %s: %s" % (type(e).__name__, str(e)[:140]))
            time.sleep(3)
    return 0


if __name__ == "__main__":
    sys.exit(main())
