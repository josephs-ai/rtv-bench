#!/usr/bin/env python3
"""Generation pilot captures: contamination evidence + first real quality data
+ first real frames through the generation capture path.

Content diversity is the point, not count: inter-frame LPIPS at CRF 12 vs
FFV1 differs by content (static compresses cleanly; heavy motion and fine
texture do not). One capture per content class per product spans the range the
verdict must hold over. If the verdict comes back marginal, the rule is
DEFAULT TO FFV1 - no hair-splitting.

Captures are written FFV1 (lossless master) directly from the frame callback,
so the contamination check re-encodes from a true source.

    .venv/bin/python tools/generation_pilot.py            # both products
    .venv/bin/python tools/generation_pilot.py --seconds 12

After it finishes:
  1. WATCH THE OUTPUTS (first real generation frames - this is where
     tools/eyeball.py earns its place):
        .venv/bin/python tools/eyeball.py capture data/pilot-captures
  2. Contamination check (in the metrics venv):
        .venv-metrics/bin/python tools/encoder_contamination.py data/pilot-captures/*.mkv
"""
import argparse
import asyncio
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(REPO, "data", "pilot-captures")

# One prompt per content class - the LPIPS-relevant axis.
PROMPTS = {
    "static": ("a still life of ceramic bowls on a wooden table, soft window "
               "light, completely still scene, nothing moves"),
    "motion": ("a crowded festival street at night, dancers spinning, fast "
               "camera movement, confetti falling everywhere"),
    "texture": ("extreme close-up of wind rippling through tall grass beside "
                "a knitted wool blanket, intricate fine detail"),
}

TARGETS = [
    # (product_key, model_name, drive_style)
    ("lingbot-world-2", "reactor/lingbot-world-2", "lingbot"),
    ("happy-oyster", "reactor/happy-oyster-director", "happy_oyster"),
]


class FFV1Writer:
    """Raw frames -> lossless FFV1 master. CFR label only; the contamination
    metric consumes frame SEQUENCE, not wall timing."""

    def __init__(self, path, fps=24.0):
        self.path = path
        self.fps = fps
        self.proc = None
        self.n = 0

    def write(self, frame):
        import numpy as np
        h, w = frame.shape[:2]
        if self.proc is None:
            self.proc = subprocess.Popen(
                ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                 "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (w, h),
                 "-r", "%g" % self.fps, "-i", "-",
                 "-c:v", "ffv1", "-level", "3", self.path],
                stdin=subprocess.PIPE)
        self.proc.stdin.write(np.ascontiguousarray(frame).tobytes())
        self.n += 1

    def close(self):
        if self.proc is not None:
            self.proc.stdin.close()
            self.proc.wait()
            self.proc = None


async def drive_lingbot(reactor, prompt):
    """set_prompt -> start (conditions_ready permitting; image defaults to auto)."""
    await reactor.send_command("set_prompt", {"prompt": prompt})
    await asyncio.sleep(1.0)
    await reactor.send_command("start", {})


async def drive_happy_oyster(reactor, prompt):
    await reactor.send_command("create_world",
                               {"prompt": prompt, "resolution": "480p"})


DRIVERS = {"lingbot": drive_lingbot, "happy_oyster": drive_happy_oyster}


async def one_capture(product_key, model_name, style, content, prompt, seconds):
    from rtveval.adapters.base import DurationSemantics
    from rtveval.adapters.reactor_webrtc import ReactorWebRTCAdapter

    out = os.path.join(OUTDIR, "%s-%s.mkv" % (product_key, content))
    writer = FFV1Writer(out)
    a = ReactorWebRTCAdapter(product_key, model_name, DurationSemantics.OPEN_ENDED)
    a.frame_tap = writer.write

    errors = []
    t0 = time.monotonic()
    await a.connect()
    try:
        await a._wait_ready()

        @a.reactor.on_error
        def _err(e):
            errors.append(str(e)[:200])

        await DRIVERS[style](a.reactor, prompt)

        # run() drives watchdogs; stop once we have `seconds` of frames or
        # a hard cap of 3x elapses.
        async def stopper():
            deadline = time.monotonic() + seconds * 3
            while time.monotonic() < deadline:
                await asyncio.sleep(0.5)
                if writer.n >= seconds * 16:  # ~16fps floor assumption
                    break
            a.request_stop()

        stop_task = asyncio.create_task(stopper())
        result = await a.run(None, "", None, "pilot")
        stop_task.cancel()
    finally:
        await a.close()
        writer.close()

    meta = {
        "product": product_key, "model": model_name, "content": content,
        "prompt": prompt, "frames": writer.n,
        "stop_reason": result.stop_reason.value,
        "resolved_version": result.info.resolved_version,
        "wall_s": round(time.monotonic() - t0, 1),
        "errors": errors[:5],
        "capture": out,
    }
    with open(out.replace(".mkv", ".json"), "w") as f:
        json.dump(meta, f, indent=2)
    return meta


async def main_async(args):
    os.makedirs(OUTDIR, exist_ok=True)
    results = []
    for product_key, model_name, style in TARGETS:
        for content, prompt in PROMPTS.items():
            print("capturing %s / %s ..." % (product_key, content))
            try:
                m = await one_capture(product_key, model_name, style, content,
                                      prompt, args.seconds)
                print("  %s frames=%d stop=%s errors=%s"
                      % (m["capture"].split("/")[-1], m["frames"],
                         m["stop_reason"], m["errors"] or "none"))
                results.append(m)
            except Exception as e:
                print("  FAILED: %s: %s" % (type(e).__name__, str(e)[:140]))
                results.append({"product": product_key, "content": content,
                                "error": str(e)[:200]})
            await asyncio.sleep(2.0)

    ok = [r for r in results if r.get("frames")]
    print("\n%d/%d captures produced frames" % (len(ok), len(results)))
    print("NEXT (human): .venv/bin/python tools/eyeball.py capture data/pilot-captures")
    print("NEXT (metrics venv): .venv-metrics/bin/python tools/encoder_contamination.py "
          + " ".join(r["capture"] for r in ok))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=12.0,
                    help="target content length per capture")
    return asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
