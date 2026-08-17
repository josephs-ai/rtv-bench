#!/usr/bin/env python3
"""Probe: does mid-stream ref switching work via session.start() (restart
path) where session.set()/change_condition does not?

    .venv/bin/python tools/ref_switch_probe.py

Motivation: 0/6 mid-stream switches via set() -> change_condition. But the
START event is the proven ref-honoring path, and session.start(context) can
be called on a live session. If this works, the correct product claim is
"mid-stream character switch works via restart (with a transition cost we
measure)", not "impossible".

Runs concurrently with the campaign-F pass: own port, own chrome profile,
serves /ref.jpg,/ref2.jpg itself (the shared static dir is being
overwritten per-session by the main driver).
Arms:
  A plain->ref restart: connect no ref; t=15 session.start({refImageUrl})
  B chain restart: connect ref-woman; t=15 session.start(ref-man)
Captures -> data/campaign-f/captures-probe/
"""
import http.server
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DDIR = os.path.join(REPO, "data", "campaign-d")
OUT = os.path.join(REPO, "data", "campaign-f", "captures-probe")
REFS = os.path.join(DDIR, "refs")

import tools.xmax_native_lane as lane
from tools.campaign_f import ANCHOR_INSTRUCTION, BASE_PROMPT, load_env
from tools.live_ab import mint_xmax_temp_key

# (arm_id, form, connect_ref or None, live_ref, record_s)
ARMS = [
    ("restart-plain2woman", "restart", None, "ref-woman.jpg", 40.0),
    ("restart-woman2man", "restart", "ref-woman.jpg", "ref-man.jpg", 40.0),
    ("stopstart-plain2woman", "stopstart", None, "ref-woman.jpg", 40.0),
    ("stopstart-woman2man", "stopstart", "ref-woman.jpg", "ref-man.jpg", 40.0),
    ("reconnect-plain2woman", "reconnect", None, "ref-woman.jpg", 45.0),
    ("reconnect-woman2man", "reconnect", "ref-woman.jpg", "ref-man.jpg", 45.0),
]


def make_probe_handler(state, refmap):
    base = lane.make_handler(state)

    class H(base):
        def do_GET(self):
            p = self.path.split("?")[0]
            if p in refmap:
                data = open(refmap[p], "rb").read()
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            super().do_GET()
    return H


def main():
    load_env()
    os.makedirs(OUT, exist_ok=True)
    lane.CLIP = os.path.join(DDIR, "conform-mixkit2960.mp4")
    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

    for arm_id, form, cref, lref, record_s in ARMS:
        name = "PROBE-xmax-x2.0-%s" % arm_id
        if os.path.exists(os.path.join(OUT, name + ".json")):
            print("skip (exists):", name)
            continue
        print("[%s] ..." % name)
        state = lane.State()
        refmap = {"/ref.jpg": os.path.join(REFS, cref or lref),
                  "/ref2.jpg": os.path.join(REFS, lref)}
        srv = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), make_probe_handler(state, refmap))
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            key = mint_xmax_temp_key(expire_s=int(record_s + 300), points=4000)
            key2 = (mint_xmax_temp_key(expire_s=int(record_s + 300),
                                       points=4000)
                    if form == "reconnect" else None)
        except Exception as e:
            print("  mint failed: %s" % str(e)[:100])
            continue
        url = ("http://127.0.0.1:%d/native_lane.html?key=%s&seconds=%g&run=%s"
               "&prompt=%s&ref2_upload=1&ref_live=1"
               "&edit=%s&edit_at=15&edit_form=%s"
               % (port, key, record_s, name, quote(BASE_PROMPT),
                  quote(ANCHOR_INSTRUCTION), form))
        if cref:
            url += "&ref_upload=1&ref_connect=1"
        if key2:
            url += "&key2=%s" % key2
        prof = "/tmp/chrome-xmax-probe"
        shutil.rmtree(prof, ignore_errors=True)
        proc = subprocess.Popen(
            [chrome, "--headless=new", "--no-first-run", "--mute-audio",
             "--autoplay-policy=no-user-gesture-required",
             "--use-fake-ui-for-media-stream",
             "--user-data-dir=" + prof, "--window-size=1400,800", url],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        t0 = time.monotonic()
        deadline = t0 + record_s + 150
        try:
            while time.monotonic() < deadline and state.upload is None:
                time.sleep(1)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
            srv.shutdown()
        page_log = [m for _, m in state.logs]
        if state.upload is None:
            print("  FAILED: %s" % "; ".join(page_log[-4:])[:200])
            continue
        _, webm = state.upload
        webm_p = os.path.join(OUT, name + ".webm")
        with open(webm_p, "wb") as f:
            f.write(webm)
        mkv_p = os.path.join(OUT, name + ".mkv")
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                        "-i", webm_p, "-c:v", "ffv1", "-level", "3", mkv_p],
                       check=True)
        a = lane.analyze(mkv_p)
        meta = {"campaign": "F-probe", "product": "xmax-x2.0",
                "lens": "P-browser", "arm": arm_id,
                "mechanism": form + " @15s",
                "ref": cref, "ref2": lref,
                "clip": "conform-mixkit2960.mp4",
                "instruction": ANCHOR_INSTRUCTION,
                "apply_at_s": 15.0, "record_s": record_s,
                "page_log": page_log, "fps": 30.0, **a,
                "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                               time.gmtime())}
        with open(os.path.join(OUT, name + ".json"), "w") as f:
            json.dump(meta, f, indent=2)
        print("  frames=%d ttff=%s log tail: %s"
              % (a["frames"], a["ttff_s"], "; ".join(page_log[-3:])[:180]))
        time.sleep(2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
