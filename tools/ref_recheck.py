#!/usr/bin/env python3
"""Ref-image RECHECK - definitive arms after the refImage/refImageUrl trap.

    .venv/bin/python tools/ref_recheck.py

Why this exists: the 2026-08-15 "ref channel has no effect" arms passed
`refImage`, but normalizeRealtimeContext (SDK session layer) only keeps
`refImageUrl` - the field was silently stripped and NEVER sent. Those 2
arms were invalid tests. This driver reruns both arms with the correct
key AND uploads the ref portrait to Xmax's own COS first via
client.files.uploadAndCheckImage (their app's real flow), killing the
external-URL-reachability confound too.

Arms (x1 clip each):
  connect-cos  ref at connect time (context.refImageUrl = COS url)
  live-cos     ref attached to a mid-stream session.set at t=15s
Captures -> data/campaign-d/captures-refcheck/
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
OUT = os.path.join(DDIR, "captures-refcheck")
REF = os.path.join(DDIR, "refs", "ref-woman.jpg")

import tools.xmax_native_lane as lane
from tools.live_ab import mint_xmax_temp_key

BASE_PROMPT = "photorealistic, natural colors"
# (arm_id, ref_jpg, flags, edit_instruction, record_s)
ARMS = [
    ("connect-cos", "ref-woman.jpg",
     {"ref_upload": "1", "ref_connect": "1"}, None, 25.0),
    ("live-cos", "ref-woman.jpg", {"ref_upload": "1", "ref_live": "1"},
     "change the person to look like the reference image", 35.0),
]
ARMS_CONFIRM = [
    ("connect-cos-man", "ref-man.jpg",
     {"ref_upload": "1", "ref_connect": "1"}, None, 25.0),
    ("live-cos-replace", "ref-woman.jpg",
     {"ref_upload": "1", "ref_live": "1"},
     "replace the speaker with the person from the reference image", 40.0),
]


def main():
    lane.load_env()
    os.makedirs(OUT, exist_ok=True)
    arms = ARMS_CONFIRM if "--confirm" in sys.argv else ARMS
    lane.CLIP = os.path.join(DDIR, "conform-mixkit2960.mp4")

    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    state = lane.State()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0),
                                          lane.make_handler(state))
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print("serving on %d" % port)

    for arm_id, ref_jpg, flags, edit, record_s in arms:
        name = "REFCHECK-xmax-x2.0-%s" % arm_id
        print("[%s] ..." % name)
        # the page fetches /ref.jpg from the lane's static dir
        shutil.copy(os.path.join(DDIR, "refs", ref_jpg),
                    os.path.join(REPO, "tools", "xmax_browser", "ref.jpg"))
        state.upload = None
        state.logs = []
        try:
            key = mint_xmax_temp_key(expire_s=int(record_s + 300), points=2000)
        except Exception as e:
            print("  mint failed: %s" % str(e)[:100])
            continue
        url = ("http://127.0.0.1:%d/native_lane.html?key=%s&seconds=%g&run=%s"
               "&prompt=%s" % (port, key, record_s, name, quote(BASE_PROMPT)))
        for k, v in flags.items():
            url += "&%s=%s" % (k, v)
        if edit:
            url += "&edit=%s&edit_at=15&edit_form=flat" % quote(edit)
        prof = "/tmp/chrome-xmax-refcheck"
        shutil.rmtree(prof, ignore_errors=True)
        proc = subprocess.Popen(
            [chrome, "--headless=new", "--no-first-run", "--mute-audio",
             "--autoplay-policy=no-user-gesture-required",
             "--use-fake-ui-for-media-stream",
             "--user-data-dir=" + prof, "--window-size=1400,800", url],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        t0 = time.monotonic()
        deadline = t0 + record_s + 120
        try:
            while time.monotonic() < deadline and state.upload is None:
                time.sleep(1)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        page_log = [m for _, m in state.logs]
        if state.upload is None:
            print("  FAILED: no upload; log tail: %s" % "; ".join(page_log[-4:])[:200])
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
        meta = {"campaign": "D-refcheck", "product": "xmax-x2.0",
                "lens": "P-browser", "arm": arm_id,
                "ref_source": "cos-upload (client.files.uploadAndCheckImage)",
                "ref_local": ref_jpg, "edit": edit,
                "base_prompt": BASE_PROMPT, "record_s": record_s,
                "field_used": "refImageUrl (session layer, post-trap fix)",
                "page_log": page_log, "fps": 30.0, **a,
                "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                               time.gmtime())}
        with open(os.path.join(OUT, name + ".json"), "w") as f:
            json.dump(meta, f, indent=2)
        print("  frames=%d ttff=%s; log tail: %s"
              % (a["frames"], a["ttff_s"], "; ".join(page_log[-4:])[:220]))
        time.sleep(2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
