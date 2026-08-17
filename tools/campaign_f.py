#!/usr/bin/env python3
"""Campaign F - reference-image control (v1.1 arm; core product interaction).

    .venv/bin/python tools/campaign_f.py --product lucy-2.5 [--smoke|--limit N]

Ref-driven character control is THE selling interaction of preset-character
live products (and the channel our 08-15 arms tested wrongly - retracted,
see claims_check fact 4). Campaign F measures it properly, per product,
through each product's own native mechanism:

  Xmax x2.0  connect-time context.refImageUrl (image pre-uploaded to the
             vendor's COS via client.files.uploadAndCheckImage) and
             mid-stream session.set({prompt, refImageUrl})
  Lucy 2.5   WebSocket {"type":"set_image", image_data: b64, prompt} sent
             at t~1s (anchor emulation) or t=15s (switch)

Arms:
  F1 anchor  ref applied at stream start; 4 refs x 2 clips, 35 s
             (adoption: does the character become the ref? attribute
             transfer: does ref-blonde deliver the hair that text edits
             could not? stylized: does a painting ref work?)
  F2 hold    ref-woman, 1 clip, 180 s (does ref anchoring beat the
             identity-morph defect? sim-to-ref trend over 3 min)
  F3 switch  ref at t=15 s mid-stream; 2 refs x 2 clips, 40 s
             (commit latency + does the speaker actually get replaced)

Primary metric is computational (insightface sim-to-ref vs sim-to-input
timelines - tools/campaign_f_metrics.py); blinded judge pass is secondary.
Journal: data/campaign-f/runs.jsonl   Captures: data/campaign-f/captures/
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
FDIR = os.path.join(REPO, "data", "campaign-f")
OUT = os.path.join(FDIR, "captures")
REFS_DIR = os.path.join(DDIR, "refs")

BASE_PROMPT = "photorealistic, natural colors"
SWITCH_AT_S = 15.0
ANCHOR_INSTRUCTION = ("replace the person with the person from the "
                      "reference image, keeping the same pose and motion")

REFS_F1 = ["ref-woman.jpg", "ref-man.jpg", "ref-blonde.jpg", "ref-styl.jpg"]
# full clip dimension: close-up single / 5-person crowd / over-shoulder
# 2-person / wide full-body small-face
CLIPS_ALL = ["conform-mixkit2960.mp4", "conform-mixkit12892.mp4",
             "conform-mixkit50117.mp4", "conform-mixkit23117.mp4"]
# campaign-D edit taxonomy rerun ON an anchored character (direct
# comparison against the D text-edit results on raw input)
EDITS_F4 = [
    ("sunglasses", "she now wears dark aviator sunglasses"),
    ("hoodie", "she now wears a bright red hooded sweatshirt"),
    ("bg-beach", "the background is now a sunny tropical beach with ocean waves"),
    ("style-anime", "everything becomes Japanese anime style, cel-shaded, vibrant"),
]


def _short(name):
    return name.replace("ref-", "").replace(".jpg", "") \
               .replace("conform-", "").replace(".mp4", "")


def jobs_for(product):
    """The ~2-hour full pass (user-directed scale-up from the 13-session
    wave 1). (job_id, arm, ref, clip, apply_at_s, record_s, instruction,
    extra). Rep 1 keeps the wave-1 job ids so existing captures are
    reused; later reps append -rN.

      F1 anchor   4 refs x 4 clips x 2 reps       (adoption, attribute
                  transfer, stylized ref, framing/multi-person boundary)
      F2 hold     ref-woman x2 + ref-styl x1, 180 s (anchored-identity hold)
      F3 switch   2 refs x 3 clips x 2 reps        (mid-stream ref switch)
      F4 compose  4 D-taxonomy text edits ON an anchored character x 2 reps
      F5 chain    ref->ref switch, both directions x 2 reps
      F7 morph    self-ref 90 s x3 vs no-ref control 90 s x3 (does
                  anchoring cure the identity-morph defect?)
    """
    c2960 = "conform-mixkit2960.mp4"
    out = []

    def add(reps, jid, *rest):
        for r in range(1, reps + 1):
            out.append((jid if r == 1 else jid + "-r%d" % r, *rest))

    for ref in REFS_F1:
        for clip in CLIPS_ALL:
            add(2, "F1-%s-%s" % (_short(ref), _short(clip)),
                "anchor", ref, clip, 1.0, 35.0, ANCHOR_INSTRUCTION, {})
    add(2, "F2-woman-2960-hold", "hold", "ref-woman.jpg", c2960,
        1.0, 180.0, ANCHOR_INSTRUCTION, {})
    add(1, "F2-styl-2960-hold", "hold", "ref-styl.jpg", c2960,
        1.0, 180.0, ANCHOR_INSTRUCTION, {})
    for ref in ["ref-woman.jpg", "ref-man.jpg"]:
        for clip in CLIPS_ALL[:3]:
            add(2, "F3-%s-%s" % (_short(ref), _short(clip)),
                "switch", ref, clip, SWITCH_AT_S, 40.0,
                ANCHOR_INSTRUCTION, {})
    for eid, text in EDITS_F4:
        add(2, "F4-compose-%s-2960" % eid, "compose", "ref-woman.jpg",
            c2960, SWITCH_AT_S, 40.0, text, {})
    add(2, "F5-chain-woman2man-2960", "chain", "ref-woman.jpg", c2960,
        SWITCH_AT_S, 40.0, ANCHOR_INSTRUCTION, {"ref2": "ref-man.jpg"})
    add(2, "F5-chain-man2woman-2960", "chain", "ref-man.jpg", c2960,
        SWITCH_AT_S, 40.0, ANCHOR_INSTRUCTION, {"ref2": "ref-woman.jpg"})
    add(3, "F7-selfref-2960", "hold", "ref-self2960.jpg", c2960,
        1.0, 90.0, ANCHOR_INSTRUCTION, {})
    add(3, "F7-control-2960", "control", None, c2960, None, 90.0, None, {})
    return out


def load_env():
    for line in open(os.path.join(REPO, ".env")):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)


def journal(row):
    os.makedirs(FDIR, exist_ok=True)
    with open(os.path.join(FDIR, "runs.jsonl"), "a") as f:
        f.write(json.dumps(row) + "\n")


async def lucy_session(job, name):
    from rtveval.adapters.decart_webrtc import DecartWebRTCAdapter
    from tools.generation_pilot import FFV1Writer

    job_id, arm, ref, clip, apply_at, record_s, instruction = job[:7]
    extra = job[7] if len(job) > 7 else {}
    a = DecartWebRTCAdapter()
    w = FFV1Writer(os.path.join(OUT, name + ".mkv"), fps=30.0)
    state = {"apply_frame": None, "apply_wall": None, "first_wall": None,
             "last_wall": None}

    def tap(fr):
        t = time.monotonic()
        if state["first_wall"] is None:
            state["first_wall"] = t
        state["last_wall"] = t
        w.write(fr)
    a.frame_tap = tap

    await a.connect()

    async def send_at(t_target, msg, label):
        while state["first_wall"] is None:
            await asyncio.sleep(0.2)
        await asyncio.sleep(max(0.0, t_target
                                - (time.monotonic() - state["first_wall"])))
        state["apply_frame"] = w.n
        state["apply_wall"] = time.monotonic()
        await a.ws.send(json.dumps(msg))
        print("    %s sent at frame %d" % (label, w.n))

    def img_msg(jpg, prompt):
        b64 = base64.b64encode(
            open(os.path.join(REFS_DIR, jpg), "rb").read()).decode()
        return {"type": "set_image", "image_data": b64, "prompt": prompt}

    async def do_apply():
        if arm == "control":
            return
        if arm == "compose":
            await send_at(1.0, img_msg(ref, ANCHOR_INSTRUCTION), "anchor-ref")
            await send_at(apply_at, {"type": "prompt", "prompt": instruction,
                                     "enhance_prompt": False}, "text-edit")
        elif arm == "chain":
            await send_at(1.0, img_msg(ref, ANCHOR_INSTRUCTION), "ref-A")
            await send_at(apply_at, img_msg(extra["ref2"],
                                            ANCHOR_INSTRUCTION), "ref-B")
        else:
            await send_at(apply_at, img_msg(ref, instruction), "ref")

    ap = asyncio.create_task(do_apply())
    stop = "?"
    try:
        r = await asyncio.wait_for(
            a.run(os.path.join(DDIR, clip), BASE_PROMPT, record_s, "C0"),
            timeout=record_s + 90)
        stop = r.stop_reason.value
    finally:
        ap.cancel()
        try:
            await a.close()
        except Exception:
            pass
        w.close()

    span = ((state["last_wall"] - state["first_wall"])
            if state["first_wall"] and state["last_wall"] else None)
    meta = {"campaign": "F", "product": "lucy-2.5", "lens": "P",
            "mechanism": "ws set_image (b64)", "job_id": job_id, "arm": arm,
            "ref": ref, "ref2": extra.get("ref2"), "clip": clip,
            "instruction": instruction,
            "base_prompt": BASE_PROMPT,
            "apply_sent_frame": state["apply_frame"],
            "apply_wall_offset_s": (round(state["apply_wall"]
                                          - state["first_wall"], 2)
                                    if state["apply_wall"] and state["first_wall"]
                                    else None),
            "fps": round(w.n / span, 2) if span and span > 1 else None,
            "fps_capture_label": 30.0, "frames": w.n, "record_s": record_s,
            "stop_reason": stop,
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                           time.gmtime())}
    with open(os.path.join(OUT, name + ".json"), "w") as f:
        json.dump(meta, f, indent=2)
    journal({k: meta[k] for k in ("campaign", "product", "lens", "job_id",
                                  "arm", "ref", "clip", "frames", "fps",
                                  "stop_reason", "timestamp_utc")}
            | {"run_id": name})
    return meta


async def main_async(args):
    os.makedirs(OUT, exist_ok=True)
    jobs = jobs_for(args.product)
    if args.smoke:
        jobs = jobs[:1]
    elif args.limit:
        jobs = jobs[:args.limit]
    done = 0
    for job in jobs:
        name = "F-%s-%s" % (args.product, job[0])
        if os.path.exists(os.path.join(OUT, name + ".json")):
            print("skip (exists):", name)
            continue
        print("[%s] arm=%s ref=%s ..." % (name, job[1], job[2]))
        try:
            m = await lucy_session(job, name)
            print("    frames=%s fps=%s stop=%s"
                  % (m["frames"], m["fps"], m["stop_reason"]))
            done += 1
        except Exception as e:
            print("    FAILED: %s %s" % (type(e).__name__, str(e)[:120]))
            journal({"campaign": "F", "product": args.product, "run_id": name,
                     "job_id": job[0], "arm": job[1], "outcome": "E?",
                     "error": str(e)[:200],
                     "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                    time.gmtime())})
            await asyncio.sleep(10)
        await asyncio.sleep(3)
    print("%d sessions done" % done)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", default="lucy-2.5")
    ap.add_argument("--wave", type=int, default=1)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    load_env()
    os.environ.setdefault("RTVEVAL_FORCE_TURN_TCP", "1")
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
