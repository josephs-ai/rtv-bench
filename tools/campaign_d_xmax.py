#!/usr/bin/env python3
"""Campaign D - Xmax native arm (browser lane + live session.set edits).

    .venv/bin/python tools/campaign_d_xmax.py            # 7 prompt-edits x 3 clips
    .venv/bin/python tools/campaign_d_xmax.py --smoke

Prompt edits only in phase 1 (ref-image path is a separate unverified
feature - phase 2). The canvas recording is wall-clocked at 30 fps, so the
edit lands at frame ~= (ttff + 15s) * 30; the analyzer's first-content
frame plus edit_at_s gives the judge its window anchor.
"""
import argparse
import json
import os
import subprocess
import sys
import threading
import time
import http.server

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DDIR = os.path.join(REPO, "data", "campaign-d")
OUT = os.path.join(DDIR, "captures")

import tools.xmax_native_lane as lane
from tools.campaign_d import CLIPS, EDITS, EDIT_AT_S, RECORD_S
from tools.live_ab import mint_xmax_temp_key

BASE_PROMPT = "photorealistic, natural colors"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="cap session count (core suite)")
    args = ap.parse_args()
    lane.load_env()
    os.makedirs(OUT, exist_ok=True)

    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    state = lane.State()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0),
                                          lane.make_handler(state))
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print("serving on %d" % port)

    jobs = []
    for i, e in enumerate(ed for ed in EDITS if ed[1] == "prompt"):
        for j in range(3):
            jobs.append((e, CLIPS[(i + j * 2) % len(CLIPS)]))
    if args.smoke:
        jobs = jobs[:1]
    elif args.limit:
        jobs = jobs[:args.limit]

    from urllib.parse import quote
    done = 0
    for (edit_id, kind, ref, instruction), clip in jobs:
        name = "D-xmax-x2.0-%s-%s" % (edit_id,
                                      clip.replace("conform-", "").replace(".mp4", ""))
        if os.path.exists(os.path.join(OUT, name + ".json")):
            print("skip (exists):", name)
            continue
        print("[%s] ..." % name)
        # point the lane's /clip.mp4 at this session's stimulus
        lane.CLIP = os.path.join(DDIR, clip)
        state.upload = None
        state.logs = []
        try:
            key = mint_xmax_temp_key(expire_s=int(RECORD_S + 300), points=2000)
        except Exception as e:
            print("  mint failed: %s" % str(e)[:100])
            time.sleep(30)
            continue
        url = ("http://127.0.0.1:%d/native_lane.html?key=%s&seconds=%g&run=%s"
               "&prompt=%s&edit=%s&edit_at=%g&edit_form=flat"
               % (port, key, RECORD_S, name, quote(BASE_PROMPT),
                  quote(instruction), EDIT_AT_S))
        import shutil
        prof = "/tmp/chrome-xmax-d"
        shutil.rmtree(prof, ignore_errors=True)
        proc = subprocess.Popen(
            [chrome, "--headless=new", "--no-first-run", "--mute-audio",
             "--autoplay-policy=no-user-gesture-required",
             "--use-fake-ui-for-media-stream",
             "--user-data-dir=" + prof, "--window-size=1400,800", url],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        t0 = time.monotonic()
        deadline = t0 + RECORD_S + 120
        try:
            while time.monotonic() < deadline and state.upload is None:
                time.sleep(1)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        edit_log = [m for _, m in state.logs if "EDIT" in m]
        if state.upload is None:
            print("  FAILED: no upload; %s" % "; ".join(
                m for _, m in state.logs if "FATAL" in m or "ERROR" in m)[:120])
            continue
        run, webm = state.upload
        webm_p = os.path.join(OUT, name + ".webm")
        with open(webm_p, "wb") as f:
            f.write(webm)
        mkv_p = os.path.join(OUT, name + ".mkv")
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                        "-i", webm_p, "-c:v", "ffv1", "-level", "3", mkv_p],
                       check=True)
        a = lane.analyze(mkv_p)
        meta = {"campaign": "D", "product": "xmax-x2.0", "lens": "P-browser",
                "clip": clip, "edit_id": edit_id, "kind": kind, "ref": None,
                "instruction": instruction, "base_prompt": BASE_PROMPT,
                "edit_at_s_from_streamup": EDIT_AT_S,
                "edit_ack": "; ".join(edit_log) or None,
                "fps": 30.0, "frames": a["frames"], "ttff_s": a["ttff_s"],
                "record_s": RECORD_S, "prompt": instruction}
        with open(os.path.join(OUT, name + ".json"), "w") as f:
            json.dump(meta, f, indent=2)
        done += 1
        print("  frames=%d ttff=%s edit=%s" % (a["frames"], a["ttff_s"],
                                               meta["edit_ack"]))
        time.sleep(2)
    print("%d xmax D sessions done" % done)
    return 0


if __name__ == "__main__":
    sys.exit(main())
