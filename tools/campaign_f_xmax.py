#!/usr/bin/env python3
"""Campaign F - Xmax arm (browser lane; native ref mechanism).

    .venv/bin/python tools/campaign_f_xmax.py [--smoke|--limit N]

Anchor arms use connect-time context.refImageUrl; switch arms use
session.set({prompt, refImageUrl}) at t=15 s. Every session first uploads
the ref to the vendor's COS through client.files.uploadAndCheckImage
(the product's own flow - no reachability confound). See campaign_f.py
for the arm design.
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

import tools.xmax_native_lane as lane
from tools.campaign_f import (BASE_PROMPT, DDIR, OUT, REFS_DIR, SWITCH_AT_S,
                              jobs_for, journal, load_env)
from tools.live_ab import mint_xmax_temp_key


def main():
    load_env()
    os.makedirs(OUT, exist_ok=True)
    jobs = jobs_for("xmax-x2.0")
    if "--smoke" in sys.argv:
        jobs = jobs[:1]
    for i, a in enumerate(sys.argv):
        if a == "--limit":
            jobs = jobs[:int(sys.argv[i + 1])]

    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    state = lane.State()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0),
                                          lane.make_handler(state))
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print("serving on %d" % port)

    done = 0
    for job in jobs:
        job_id, arm, ref, clip, apply_at, record_s, instruction = job[:7]
        extra = job[7] if len(job) > 7 else {}
        name = "F-xmax-x2.0-%s" % job_id
        if os.path.exists(os.path.join(OUT, name + ".json")):
            print("skip (exists):", name)
            continue
        print("[%s] arm=%s ref=%s ..." % (name, arm, ref))
        if ref:
            shutil.copy(os.path.join(REFS_DIR, ref),
                        os.path.join(REPO, "tools", "xmax_browser", "ref.jpg"))
        if extra.get("ref2"):
            shutil.copy(os.path.join(REFS_DIR, extra["ref2"]),
                        os.path.join(REPO, "tools", "xmax_browser", "ref2.jpg"))
        lane.CLIP = os.path.join(DDIR, clip)
        state.upload = None
        state.logs = []
        try:
            key = mint_xmax_temp_key(expire_s=int(record_s + 300), points=4000)
        except Exception as e:
            print("  mint failed: %s" % str(e)[:100])
            time.sleep(30)
            continue
        url = ("http://127.0.0.1:%d/native_lane.html?key=%s&seconds=%g&run=%s"
               "&prompt=%s" % (port, key, record_s, name, quote(BASE_PROMPT)))
        if ref:
            url += "&ref_upload=1"
        if arm in ("anchor", "hold"):
            url += "&ref_connect=1"
        elif arm == "switch":
            url += ("&ref_live=1&edit=%s&edit_at=%g&edit_form=flat"
                    % (quote(instruction), SWITCH_AT_S))
        elif arm == "compose":   # anchored char + PLAIN text edit (no ref_live)
            url += ("&ref_connect=1&edit=%s&edit_at=%g&edit_form=flat"
                    % (quote(instruction), SWITCH_AT_S))
        elif arm == "chain":     # anchor ref A, switch to ref B at t=15
            url += ("&ref_connect=1&ref2_upload=1&ref_live=1"
                    "&edit=%s&edit_at=%g&edit_form=flat"
                    % (quote(instruction), SWITCH_AT_S))
        # control: no ref params at all
        prof = "/tmp/chrome-xmax-f"
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
        page_log = [m for _, m in state.logs]
        if state.upload is None:
            print("  FAILED: no upload; %s" % "; ".join(page_log[-3:])[:160])
            journal({"campaign": "F", "product": "xmax-x2.0",
                     "lens": "P-browser", "run_id": name, "job_id": job_id,
                     "arm": arm, "outcome": "F",
                     "error": "; ".join(page_log[-3:])[:200],
                     "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                    time.gmtime())})
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
        ref_ok = any("REF UPLOADED" in m for m in page_log)
        mech = {"anchor": "connect context.refImageUrl",
                "hold": "connect context.refImageUrl",
                "switch": "session.set refImageUrl @15s",
                "compose": "connect ref + plain session.set text @15s",
                "chain": "connect ref A + session.set ref B @15s",
                "control": "no ref (baseline)"}[arm]
        meta = {"campaign": "F", "product": "xmax-x2.0", "lens": "P-browser",
                "mechanism": mech,
                "job_id": job_id, "arm": arm, "ref": ref,
                "ref2": extra.get("ref2"), "clip": clip,
                "instruction": (instruction
                                if arm in ("switch", "compose", "chain")
                                else None),
                "base_prompt": BASE_PROMPT,
                "ref_cos_uploaded": ref_ok, "record_s": record_s,
                "apply_at_s": (0.0 if arm in ("anchor", "hold")
                               else None if arm == "control"
                               else SWITCH_AT_S),
                "page_log": page_log, "fps": 30.0, **a,
                "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                               time.gmtime())}
        with open(os.path.join(OUT, name + ".json"), "w") as f:
            json.dump(meta, f, indent=2)
        journal({"campaign": "F", "product": "xmax-x2.0", "lens": "P-browser",
                 "run_id": name, "job_id": job_id, "arm": arm, "ref": ref,
                 "clip": clip, "frames": a["frames"], "ttff_s": a["ttff_s"],
                 "ref_cos_uploaded": ref_ok,
                 "timestamp_utc": meta["timestamp_utc"]})
        done += 1
        print("  frames=%d ttff=%s ref_uploaded=%s"
              % (a["frames"], a["ttff_s"], ref_ok))
        time.sleep(2)
    print("%d xmax F sessions done" % done)
    return 0


if __name__ == "__main__":
    sys.exit(main())
