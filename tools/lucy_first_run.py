#!/usr/bin/env python3
"""First live Lucy end-to-end run (item 2 of the work order).

Answers, on real output:
  - does the negotiation complete and do frames flow (adapter validity)
  - is Decart's delivery chunk-bursty like Reactor's, or true per-frame
    (changes TTFF/stall interpretation for Lens P)
  - does classify() produce a sane outcome on a real Lucy StreamResult
  - what do generation_ticks report vs wall time (billing sanity)

Cost: ~15 s of Lucy at ~$0.02/s = ~$0.30. One run, not a campaign.
The token-expiry question is already settled by docs (expiry blocks new
connections only); a >60 s confirmation ride-along happens in the pilot soak.
"""
import asyncio
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, "data")
CLIP = os.path.join(DATA, "lucy-clip", "lucy-720p.mp4")
CLIP_SECONDS = 15
FPS = 30.0

PROMPT = "subtle warm film grade, gentle vignette"  # mild transform (style a)


def ensure_clip():
    from PIL import Image
    from rtveval.reel import render

    if os.path.exists(CLIP):
        return render.load_truth(CLIP)
    os.makedirs(os.path.dirname(CLIP), exist_ok=True)
    n = int(CLIP_SECONDS * FPS)

    def frames():
        rng = np.random.default_rng(11)
        for i in range(n):
            # simple moving scene: gradient sky + drifting blocks, enough
            # structure for a V2V model to grab onto
            base = np.zeros((720, 1280, 3), dtype=np.uint8)
            sky = np.linspace(140, 60, 720)[:, None]
            base[..., 2] = np.clip(sky + 40, 0, 255).astype(np.uint8)
            base[..., 1] = np.clip(sky, 0, 255).astype(np.uint8)
            base[..., 0] = np.clip(sky - 30, 0, 255).astype(np.uint8)
            x = int(200 + 120 * np.sin(i / 20))
            base[400:600, x:x + 180] = (60, 70, 90)
            base += rng.integers(0, 5, base.shape, dtype=np.uint8)
            yield Image.fromarray(base)

    spec = render.ReelSpec(width=1280, height=720, fps=FPS)
    truth = render.render_reel(frames(), n, spec,
                               [render.ClipSpan("LUCY-TEST", 0, n)], CLIP)
    print("rendered %s" % CLIP)
    return truth


async def main() -> int:
    from rtveval.adapters.decart_webrtc import DecartWebRTCAdapter
    from rtveval.classify import classify

    truth = ensure_clip()
    a = DecartWebRTCAdapter()
    info = await a.connect()
    states = []

    _orig_neg = a._negotiate
    async def negotiate_logged(clip_path):
        await _orig_neg(clip_path)
        import time as _t
        t0 = _t.monotonic()
        @a.pc.on("iceconnectionstatechange")
        def _ice():
            states.append(("ice", a.pc.iceConnectionState, _t.monotonic() - t0))
            print("  [%.1fs] ICE -> %s" % (_t.monotonic() - t0, a.pc.iceConnectionState))
        @a.pc.on("connectionstatechange")
        def _conn():
            states.append(("conn", a.pc.connectionState, _t.monotonic() - t0))
            print("  [%.1fs] conn -> %s" % (_t.monotonic() - t0, a.pc.connectionState))
    a._negotiate = negotiate_logged
    print("connected: %s @ region %s" % (info.resolved_version, info.region))

    try:
        result = await asyncio.wait_for(
            a.run(CLIP, PROMPT, float(CLIP_SECONDS), "first-run"),
            timeout=CLIP_SECONDS + 45)
    finally:
        billed = a.generation_seconds
        sid = a.session_id
        await a.close()

    ev = result.events
    print("\nstop_reason: %s   frames: %d   session: %s" %
          (result.stop_reason.value, len(ev), sid))
    if not ev:
        print("NO FRAMES - negotiation succeeded but media did not flow")
        return 1

    ttff = (ev[0].wall_clock - result.request_clock) * 1000
    gaps = [(b.wall_clock - a_.wall_clock) * 1000 for a_, b in zip(ev, ev[1:])]
    gaps_sorted = sorted(gaps)
    p50 = statistics.median(gaps_sorted)
    p95 = gaps_sorted[max(0, int(0.95 * len(gaps_sorted)) - 1)]
    frame_period = 1000.0 / FPS

    delivery = ("frame-paced" if p95 <= 2.0 * frame_period else "chunk-bursty")
    c = classify(result)

    print("TTFF: %.0f ms" % ttff)
    print("delivery: %s (gap p50 %.1f ms, p95 %.1f ms vs %.1f ms period)"
          % (delivery, p50, p95, frame_period))
    print("resolution: %dx%d" % (ev[0].width, ev[0].height))
    print("classify: %s %s" % (c.outcome, c.reasons))
    print("generation_ticks billed: %s s (wall %.1f s)"
          % (billed, result.stop_clock - result.request_clock))

    os.makedirs(os.path.join(DATA, "traces"), exist_ok=True)
    out = os.path.join(DATA, "traces", "lucy-first-run.json")
    with open(out, "w") as f:
        json.dump({"info": info._asdict(), "stop_reason": result.stop_reason.value,
                   "ttff_ms": ttff, "delivery": delivery,
                   "gap_p50_ms": p50, "gap_p95_ms": p95,
                   "n_frames": len(ev), "billed_s": billed,
                   "classify": {"outcome": c.outcome, "reasons": c.reasons},
                   "events": [{"t": e.wall_clock - result.request_clock,
                               "i": e.frame_index, "b": e.nbytes} for e in ev]},
                  f, default=str)
    print("trace -> %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
