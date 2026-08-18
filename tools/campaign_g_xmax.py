#!/usr/bin/env python3
"""Campaign G - Xmax arm (browser lane; interaction density).

    .venv/bin/python tools/campaign_g_xmax.py [--smoke|--limit N]

A clip streams live for 90 s and an edit fires EVERY 10 s (wall-clock
from first delivered frame): t=10,20,...,80, cycling the fixed 7-step
sequence (so edit 8 wraps to instruction 1). Every edit goes through the
PROVEN flat-form session.set({prompt}) - {context:{prompt}} silently
no-ops mid-stream (playbook). Temp keys are single-generation: minted
PER session. Sessions run STRICTLY serialized (concurrent xmax poisons
- playbook); never shard this driver.

Journal: data/campaign-g/runs.jsonl   Captures: data/campaign-g/captures/
"""
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import tools.xmax_native_lane as lane
from tools.live_ab import mint_xmax_temp_key

DDIR = os.path.join(REPO, "data", "campaign-d")
GDIR = os.path.join(REPO, "data", "campaign-g")
OUT = os.path.join(GDIR, "captures")

from tools.campaign_g import (BASE_PROMPT, RECORD_S,
                              EDIT_EVERY_S,
                              CLIPS_G as CLIPS,
                              EDITS_G as EDITS)

REPS = 3
CAPTURE_FPS = 30.0   # canvas recorder rate (capture label, not delivery)

# density_lane.html per-edit log lines:
#   EDIT <k> SENT at <t>s rec=<r>s: <text>
#   EDIT <k> FAILED at <t>s rec=<r>s: <msg>
EDIT_RE = re.compile(r"^EDIT (\d+) (SENT|FAILED) at ([0-9.]+)s "
                     r"rec=(-?[0-9.]+)s: (.*)$")


def _short(name):
    return name.replace("conform-", "").replace(".mp4", "")


def schedule_for(record_s):
    """[{at, text}] - t=10,20,... strictly inside the record window."""
    out = []
    k = 0
    t = EDIT_EVERY_S
    while t < record_s:
        out.append({"at": t, "text": EDITS[k % len(EDITS)]})
        k += 1
        t += EDIT_EVERY_S
    return out


def edit_schedule_meta(sched, page_log):
    """Join the planned schedule against the page's per-edit log lines.
    t_sent is wall from stream-up (the page's send clock); frame_at_send
    maps the rec-clock offset onto the 30 fps capture timeline."""
    parsed = {}
    for m in page_log:
        g = EDIT_RE.match(m)
        if g:
            parsed[int(g.group(1))] = g
    rows = []
    for k, ed in enumerate(sched):
        g = parsed.get(k)
        if g is None:
            rows.append({"t_target_s": ed["at"], "t_sent_wall_offset_s": None,
                         "frame_at_send": None, "instruction": ed["text"],
                         "ack_or_error": "no log line (never fired)"})
            continue
        rec_s = float(g.group(4))
        rows.append({
            "t_target_s": ed["at"],
            "t_sent_wall_offset_s": float(g.group(3)),
            "frame_at_send": (int(round(rec_s * CAPTURE_FPS))
                              if rec_s >= 0 else None),
            "instruction": ed["text"],
            "ack_or_error": ("acked (set resolved)" if g.group(2) == "SENT"
                             else "error: " + g.group(5)[:120]),
        })
    return rows


def journal(row):
    os.makedirs(GDIR, exist_ok=True)
    with open(os.path.join(GDIR, "runs.jsonl"), "a") as f:
        f.write(json.dumps(row) + "\n")


def main():
    lane.load_env()
    os.makedirs(OUT, exist_ok=True)
    jobs = []
    for clip in CLIPS:
        for rep in range(1, REPS + 1):
            jobs.append(("G1-%s-rep%d" % (_short(clip), rep), clip, rep))
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

    sched = schedule_for(RECORD_S)
    done = 0
    for job_id, clip, rep in jobs:
        name = "G-xmax-x2.0-%s" % job_id
        if os.path.exists(os.path.join(OUT, name + ".json")):
            print("skip (exists):", name)
            continue
        print("[%s] clip=%s rep=%d (%d edits)..."
              % (name, clip, rep, len(sched)))
        lane.CLIP = os.path.join(DDIR, clip)
        state.upload = None
        state.logs = []
        try:
            key = mint_xmax_temp_key(expire_s=int(RECORD_S + 300),
                                     points=4000)
        except Exception as e:
            print("  mint failed: %s" % str(e)[:100])
            time.sleep(30)
            continue
        url = ("http://127.0.0.1:%d/density_lane.html?key=%s&seconds=%g"
               "&run=%s&prompt=%s&edits=%s"
               % (port, key, RECORD_S, name, quote(BASE_PROMPT),
                  quote(json.dumps(sched))))
        prof = "/tmp/chrome-xmax-g"
        shutil.rmtree(prof, ignore_errors=True)
        proc = subprocess.Popen(
            [chrome, "--headless=new", "--no-first-run", "--mute-audio",
             "--autoplay-policy=no-user-gesture-required",
             "--use-fake-ui-for-media-stream",
             "--user-data-dir=" + prof, "--window-size=1400,800", url],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        t0 = time.monotonic()
        deadline = t0 + RECORD_S + 150
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
            journal({"campaign": "G", "product": "xmax-x2.0",
                     "lens": "P-browser", "run_id": name, "job_id": job_id,
                     "clip": clip, "rep": rep, "outcome": "F",
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
        ed_rows = edit_schedule_meta(sched, page_log)
        sent = sum(1 for r in ed_rows if r["ack_or_error"].startswith("acked"))
        meta = {"campaign": "G", "product": "xmax-x2.0", "lens": "P-browser",
                "mechanism": ("session.set({prompt}) flat form every 10s, "
                              "wall-clock from stream-up"),
                "job_id": job_id, "clip": clip, "rep": rep,
                "base_prompt": BASE_PROMPT,
                "edit_schedule": ed_rows, "edit_every_s": EDIT_EVERY_S,
                "edits_sent": sent, "record_s": RECORD_S,
                # measured: capture window is exactly record_s of wall time
                "fps": round(a["frames"] / RECORD_S, 2),
                "fps_capture_label": CAPTURE_FPS,
                "page_log": page_log, **a,
                "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                               time.gmtime())}
        with open(os.path.join(OUT, name + ".json"), "w") as f:
            json.dump(meta, f, indent=2)
        journal({"campaign": "G", "product": "xmax-x2.0", "lens": "P-browser",
                 "run_id": name, "job_id": job_id, "clip": clip, "rep": rep,
                 "frames": a["frames"], "ttff_s": a["ttff_s"],
                 "max_frozen_s": a["max_frozen_s"], "edits_sent": sent,
                 "edits_planned": len(sched),
                 "timestamp_utc": meta["timestamp_utc"]})
        done += 1
        print("  frames=%d ttff=%s edits=%d/%d"
              % (a["frames"], a["ttff_s"], sent, len(sched)))
        time.sleep(2)   # serialize + settle between sessions
    print("%d xmax G sessions done" % done)
    return 0


if __name__ == "__main__":
    sys.exit(main())
