#!/usr/bin/env python3
"""Campaign D - live mid-stream editing (HIGH PRIORITY arm).

    .venv/bin/python tools/campaign_d.py --product lucy-2.5
    .venv/bin/python tools/campaign_d.py --product lucy-2.5 --smoke

A clip streams live; at t=EDIT_AT an edit lands (prompt text or reference
image + instruction); capture continues to RECORD_S. The meta logs the
EXACT frame index at which the edit was sent (writer.n at send), so the
edit-judge's before/transition/after windows are precise.

Edits cover: garment, hair, accessory, background swap, full style flip,
and reference-image character switches. Stimuli: corpus + 4 external
clips (different people/framing/lighting; mixkit license).
"""
import argparse
import asyncio
import base64
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DDIR = os.path.join(REPO, "data", "campaign-d")
OUT = os.path.join(DDIR, "captures")
REFS = os.path.join(DDIR, "refs")

RECORD_S = 35.0
EDIT_AT_S = 15.0
BASE_PROMPT = "photorealistic, natural colors"

# (edit_id, kind, payload, instruction)
EDITS = [
    ("garment-hoodie", "prompt", None,
     "the person now wears a bright red hooded sweatshirt"),
    ("garment-suit", "prompt", None,
     "the person now wears a formal black business suit with a tie"),
    ("hair-blonde", "prompt", None,
     "the person now has long blonde hair"),
    ("accessory-sunglasses", "prompt", None,
     "the person now wears dark aviator sunglasses"),
    ("background-beach", "prompt", None,
     "the background is now a sunny tropical beach with ocean waves"),
    ("background-cyberpunk", "prompt", None,
     "the background is now a neon-lit cyberpunk city street at night"),
    ("style-anime", "prompt", None,
     "everything becomes Japanese anime style, cel-shaded, vibrant"),
    ("character-man", "ref", "ref-man.jpg",
     "replace the person with the man from the reference image, keeping "
     "the same pose and motion"),
    ("character-woman", "ref", "ref-woman.jpg",
     "replace the person with the woman from the reference image, keeping "
     "the same pose and motion"),
]

CLIPS = ["conform-corpus.mp4", "conform-mixkit2960.mp4",
         "conform-mixkit23117.mp4", "conform-mixkit50117.mp4",
         "conform-mixkit12892.mp4"]


def load_env():
    for line in open(os.path.join(REPO, ".env")):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)


def pairing():
    """Each edit runs on 3 clips, round-robin -> 27 sessions, all clips used."""
    out = []
    for i, e in enumerate(EDITS):
        for j in range(3):
            out.append((e, CLIPS[(i + j * 2) % len(CLIPS)]))
    return out


async def lucy_session(edit, clip, name):
    from rtveval.adapters.decart_webrtc import DecartWebRTCAdapter
    from tools.generation_pilot import FFV1Writer

    edit_id, kind, ref, instruction = edit
    a = DecartWebRTCAdapter()
    w = FFV1Writer(os.path.join(OUT, name + ".mkv"), fps=30.0)
    state = {"edit_frame": None, "edit_wall": None, "first_wall": None,
             "last_wall": None}

    def tap(fr):
        t = time.monotonic()
        if state["first_wall"] is None:
            state["first_wall"] = t
        state["last_wall"] = t
        w.write(fr)
    a.frame_tap = tap

    await a.connect()

    async def do_edit():
        # EDIT_AT_S of WALL time after the first delivered frame (delivered
        # fps varies - the smoke run measured ~15 fps, so a frame-count
        # clock would fire the edit twice too late)
        while state["first_wall"] is None:
            await asyncio.sleep(0.2)
        await asyncio.sleep(max(0.0, EDIT_AT_S
                                - (time.monotonic() - state["first_wall"])))
        msg = {"type": "prompt", "prompt": instruction,
               "enhance_prompt": False}
        if kind == "ref":
            b64 = base64.b64encode(
                open(os.path.join(REFS, ref), "rb").read()).decode()
            msg = {"type": "set_image", "image_data": b64,
                   "prompt": instruction}
        state["edit_frame"] = w.n
        state["edit_wall"] = time.monotonic()
        await a.ws.send(json.dumps(msg))
        print("    edit sent at frame %d (%.1fs)" % (w.n, w.n / 30.0))

    ed = asyncio.create_task(do_edit())
    try:
        r = await asyncio.wait_for(
            a.run(os.path.join(DDIR, clip), BASE_PROMPT, RECORD_S, "C0"),
            timeout=RECORD_S + 90)
        stop = r.stop_reason.value
    finally:
        ed.cancel()
        await a.close()
        w.close()

    span = ((state["last_wall"] - state["first_wall"])
            if state["first_wall"] and state["last_wall"] else None)
    fps_measured = round(w.n / span, 2) if span and span > 1 else None
    meta = {"campaign": "D", "product": "lucy-2.5", "lens": "P",
            "clip": clip, "edit_id": edit_id, "kind": kind, "ref": ref,
            "instruction": instruction, "base_prompt": BASE_PROMPT,
            "edit_sent_frame": state["edit_frame"],
            "edit_wall_offset_s": (round(state["edit_wall"]
                                         - state["first_wall"], 2)
                                   if state["edit_wall"] and state["first_wall"]
                                   else None),
            "fps": fps_measured or 15.0, "fps_capture_label": 30.0,
            "frames": w.n, "record_s": RECORD_S, "stop_reason": stop,
            "prompt": instruction}
    with open(os.path.join(OUT, name + ".json"), "w") as f:
        json.dump(meta, f, indent=2)
    return meta


async def main_async(args):
    os.makedirs(OUT, exist_ok=True)
    jobs = pairing()
    if args.smoke:
        jobs = jobs[:1]
    elif args.limit:
        jobs = jobs[:args.limit]
    done = n = 0
    for edit, clip in jobs:
        name = "D-%s-%s-%s" % (args.product, edit[0],
                               clip.replace("conform-", "").replace(".mp4", ""))
        if os.path.exists(os.path.join(OUT, name + ".json")):
            print("skip (exists):", name)
            continue
        n += 1
        print("[%d] %s ..." % (n, name))
        try:
            m = await lucy_session(edit, clip, name)
            ok = (m["frames"] > 20 * (m["fps"] or 15)
                  and m["edit_sent_frame"] is not None)
            done += 1 if ok else 0
            print("    frames=%d edit@%s stop=%s %s"
                  % (m["frames"], m["edit_sent_frame"], m["stop_reason"],
                     "OK" if ok else "SHORT/NO-EDIT"))
        except Exception as e:
            print("    FAILED %s: %s" % (type(e).__name__, str(e)[:140]))
        await asyncio.sleep(3)
    print("%d good sessions" % done)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", default="lucy-2.5")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="cap session count (core suite)")
    args = ap.parse_args()
    if args.product != "lucy-2.5":
        print("xmax arm runs via the browser lane (blocked on VPN mode)")
        return 1
    load_env()
    os.environ.setdefault("RTVEVAL_FORCE_TURN_TCP", "1")
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
