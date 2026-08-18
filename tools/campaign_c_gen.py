#!/usr/bin/env python3
"""Campaign C (generation half): G1-G7 quality captures for LingBot + HO.

    .venv/bin/python tools/campaign_c_gen.py --reps 3

Per (product x G-prompt x rep): fresh session, drive the world, record
FFV1 lossless through the content-hardened gate (spatial structure AND
motion), write capture + meta. G6 records 60 s; G7 applies a mid-stream
steer at t=15 s (LingBot: set_prompt, proven; HO: 'instruct' best-effort,
ack recorded - unresolved channel is flagged, not hidden).

Prompts carry CHECKABLE assertions (plan sec 6.2). LingBot variants
CONTINUE the seed image (stimulus rule, dry-run finding #2).
"""
import argparse
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "data", "campaign-c-gen")

# (G id, HO prompt, LingBot seed-continuing variant, record_s, steer or None)
GPROMPTS = [
    ("G1", "three red lanterns hanging to the left of a tall wooden door",
     "three red lanterns hanging on the wooden structure, to the left of "
     "its dark doorway", 20, None),
    ("G2", "a large blue ball drops from the sky, bounces twice on the "
     "stone ground, and rolls to a stop",
     "a large blue ball drops from the sky in front of the wooden "
     "structure, bounces twice, and rolls to a stop", 20, None),
    ("G3", "a black dog walks out of frame to the right; the scene holds "
     "still; the same black dog re-enters from the right",
     "a black dog walks past the wooden structure and out of frame right; "
     "the scene holds; the same dog re-enters from the right", 25, None),
    ("G4", "the camera slowly pushes forward toward a stone fountain, "
     "nothing else moves",
     "the camera slowly pushes forward toward the wooden structure, "
     "nothing else moves", 20, None),
    ("G5", "a man in a yellow coat stands beside a woman in a green dress; "
     "a white bird perches between them",
     "a man in a yellow coat and a woman in a green dress stand in front "
     "of the wooden structure; a white bird perches between them", 20, None),
    ("G6", "a calm village square with a central fountain at golden hour",
     "the quiet landscape with the wooden structure under a hazy sky",
     60, None),
    ("G7", "a sunny meadow with a single oak tree",
     "the quiet landscape with the wooden structure on a sunny day",
     35, "heavy snow begins falling over the whole scene"),
]

PRODUCTS = [
    ("lingbot", "reactor/lingbot-world-2"),
    ("happy-oyster", "reactor/happy-oyster-director"),
]


def load_env():
    for line in open(os.path.join(REPO, ".env")):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)


async def one_capture(product, model, gid, prompt, record_s, steer, rep):
    import numpy as np
    from rtveval.adapters.base import DurationSemantics
    from rtveval.adapters.reactor_webrtc import ReactorWebRTCAdapter
    from tools.generation_pilot import FFV1Writer, drive_lingbot

    name = "%s-%s-r%d" % (product, gid, rep)
    out = os.path.join(OUT, name + ".mkv")
    writer = FFV1Writer(out)
    state = {"prev": None, "live": False, "waited": 0, "live_at": None,
             "steer_sent_at": None, "steer_ack": None}

    def gated(frame):
        if not state["live"]:
            prev = state["prev"]
            state["prev"] = frame.copy()
            state["waited"] += 1
            moving = (prev is not None and prev.shape == frame.shape and
                      float(np.abs(frame.astype(np.int16)
                                   - prev.astype(np.int16)).mean()) > 1.0)
            detailed = float(frame.std(axis=(0, 1)).mean()) > 12.0 and \
                float(np.abs(np.diff(frame.mean(axis=2).astype(np.float64),
                                     axis=1)).mean()) > 1.5
            if moving and detailed:
                state["live"] = True
                state["live_at"] = time.monotonic()
            else:
                return
        writer.write(frame)

    a = ReactorWebRTCAdapter(product, model, DurationSemantics.OPEN_ENDED,
                             prompt_command="set_prompt",
                             first_frame_timeout_s=300.0,
                             stall_timeout_s=240.0)
    a.frame_tap = gated
    errors = []
    t0 = time.monotonic()
    await a.connect()
    try:
        await a._wait_ready()

        @a.reactor.on_error
        def _e(err):
            errors.append(str(err)[:160])

        if product == "lingbot":
            await drive_lingbot(a.reactor, prompt, seed_path=os.path.join(
                REPO, "data", "pilot-captures", "seed-lingbot-real.jpg"))
        else:
            attached = {"done": False}

            @a.reactor.on_message
            def _m(msg):
                try:
                    if isinstance(msg, dict) and msg.get("type") == "world_state":
                        d = msg.get("data", {})
                        if (d.get("phase") == "ready" and not attached["done"]
                                and d.get("encrypted_world_id")):
                            attached["done"] = True
                            asyncio.create_task(a.reactor.send_command(
                                "attach_world",
                                {"encrypted_world_id": d["encrypted_world_id"]}))
                except Exception:
                    pass

            await a.reactor.send_command(
                "create_world", {"prompt": prompt, "resolution": "480p"})

        async def driver():
            deadline = time.monotonic() + 330 + record_s
            while time.monotonic() < deadline:
                await asyncio.sleep(0.5)
                if state["live_at"] is not None:
                    lived = time.monotonic() - state["live_at"]
                    if (steer and state["steer_sent_at"] is None
                            and lived >= 15.0):
                        state["steer_sent_at"] = lived
                        try:
                            if product == "lingbot":
                                await a.reactor.send_command(
                                    "set_prompt", {"prompt": steer})
                                state["steer_ack"] = "set_prompt sent"
                            else:
                                await a.reactor.send_command(
                                    "instruct", {"content": steer})
                                state["steer_ack"] = "instruct sent (channel unverified)"
                        except Exception as e:
                            state["steer_ack"] = "steer FAILED: %s" % str(e)[:100]
                    if lived >= record_s:
                        break
            a.request_stop()

        drv = asyncio.create_task(driver())
        result = await a.run(None, "", None, "campaign-c")
        drv.cancel()
    finally:
        await a.close()
        writer.close()

    meta = {"product": product, "model": model, "g": gid, "rep": rep,
            "prompt": prompt, "steer": steer,
            "steer_sent_at_s": state["steer_sent_at"],
            "steer_ack": state["steer_ack"],
            "frames": writer.n, "went_live": state["live"],
            "placeholder_frames_skipped": state["waited"],
            "stop_reason": result.stop_reason.value,
            "resolved_version": result.info.resolved_version,
            "wall_s": round(time.monotonic() - t0, 1),
            "errors": errors[:4], "capture": out}
    with open(out.replace(".mkv", ".json"), "w") as f:
        json.dump(meta, f, indent=2)
    return meta


async def main_async(args):
    os.makedirs(OUT, exist_ok=True)
    results = []
    for rep in range(args.rep_from, args.reps + 1):
        for product, model in PRODUCTS:
            if args.product and product != args.product:
                continue
            for gid, ho_prompt, lb_prompt, secs, steer in GPROMPTS:
                name = "%s-%s-r%d" % (product, gid, rep)
                if os.path.exists(os.path.join(OUT, name + ".json")):
                    print("skip (exists):", name)
                    continue
                prompt = lb_prompt if product == "lingbot" else ho_prompt
                # uplink gate: the 48fps 1664x960 stream smears into
                # macroblock garbage on a sagged tunnel (08-18 finding) -
                # hold rather than capture corruption
                if args.min_mbps:
                    from tools.campaign_b import upload_mbps
                    while True:
                        mbps = upload_mbps()
                        if mbps >= args.min_mbps:
                            break
                        print("uplink %.1f < %.0f Mbps - holding 5 min"
                              % (mbps, args.min_mbps), flush=True)
                        await asyncio.sleep(300)
                print("capture %s ..." % name)
                try:
                    m = await one_capture(product, model, gid, prompt,
                                          secs, steer, rep)
                    print("  frames=%d live=%s stop=%s steer=%s"
                          % (m["frames"], m["went_live"], m["stop_reason"],
                             m["steer_ack"]))
                    results.append(m)
                except Exception as e:
                    print("  FAILED %s: %s" % (type(e).__name__, str(e)[:140]))
                await asyncio.sleep(3)
    ok = [r for r in results if r.get("frames")]
    print("\n%d captures with frames this session" % len(ok))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--rep-from", type=int, default=1)
    ap.add_argument("--product", default=None,
                    help="lingbot | happy-oyster (default both)")
    ap.add_argument("--min-mbps", type=float, default=0,
                    help="uplink gate before each capture")
    args = ap.parse_args()
    load_env()
    os.environ.setdefault("RTVEVAL_FORCE_TURN_TCP", "1")
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
