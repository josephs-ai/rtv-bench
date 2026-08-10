#!/usr/bin/env python3
"""Platform-floor calibration against reactor/echo.

Echo returns the client's own video with no inference: output ~= input. So
glass-to-glass through echo measures the Reactor PLATFORM floor - negotiation,
transport, encode/decode, scheduling - with the model contribution zeroed.
Every Lens M latency figure can then be decomposed:

    "LingBot p95 X ms, of which ~Y ms is platform floor"

which makes Lens M interpretable without any dual-routed bridge model.

It also settles chunk-vs-frame delivery: echo's inter-arrival distribution
shows directly whether the frame callback receives paced frames (gaps ~= one
frame period) or chunk bursts (bimodal gaps) - which would bias TTFF and stall
detection on all three Reactor products if left unknown.

Run it as a proper sample, not a connectivity check:

    .venv/bin/python tools/echo_calibration.py --runs 30 --condition C0
    (re-run under C2 when the netshape phase is armed)

Writes data/platform-floor-<condition>.json.
"""
import argparse
import asyncio
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, "data")
CLIP_DIR = os.path.join(DATA, "echo-clip")
CLIP = os.path.join(CLIP_DIR, "echo-cal.mp4")  # overridden by --profile

CLIP_SECONDS = 20
CLIP_FPS = 30.0
CLIP_W, CLIP_H = 640, 360

# --profile minimal: strip the send side down - tiny frames, minimal encode
# load - to separate OUR rig's contribution from Reactor's platform.
PROFILES = {
    "standard": (640, 360, "echo-cal.mp4"),
    "minimal": (256, 144, "echo-cal-minimal.mp4"),
}


def ensure_clip():
    """Render the instrumented calibration clip once (flashes + strip)."""
    from PIL import Image
    from rtveval.reel import render

    if os.path.exists(CLIP) and os.path.exists(render.sidecar_path(CLIP)):
        return render.load_truth(CLIP)

    os.makedirs(CLIP_DIR, exist_ok=True)
    n = int(CLIP_SECONDS * CLIP_FPS)

    def frames():
        rng = np.random.default_rng(7)
        for i in range(n):
            base = np.full((CLIP_H, CLIP_W, 3), 90, dtype=np.uint8)
            # gentle moving gradient so the encoder has something real to do
            x = np.linspace(0, 40, CLIP_W, dtype=np.float64)
            base[..., :] = np.clip(90 + np.sin(x / 6 + i / 10) * 20, 0, 255
                                   ).astype(np.uint8)[None, :, None]
            base += rng.integers(0, 4, base.shape, dtype=np.uint8)
            yield Image.fromarray(base)

    spec = render.ReelSpec(width=CLIP_W, height=CLIP_H, fps=CLIP_FPS)
    clips = [render.ClipSpan("CAL", 0, n)]
    truth = render.render_reel(frames(), n, spec, clips, CLIP)
    print("rendered %s (%d frames)" % (CLIP, n))
    return truth


def input_luminance():
    """True input luminance series, decoded from the clip itself."""
    import av

    out = []
    with av.open(CLIP) as c:
        for frame in c.decode(video=0):
            arr = frame.to_ndarray(format="rgb24")
            out.append(float(arr.mean()))
    return np.array(out)


async def one_run(run_idx, truth, in_lum, timeout_s):
    from rtveval.adapters.base import DurationSemantics
    from rtveval.adapters.reactor_webrtc import ReactorWebRTCAdapter
    from rtveval.latency import impulse

    lum = []  # per received frame, computed at arrival (cheap at 640x360)

    adapter = ReactorWebRTCAdapter("platform-floor", "reactor/echo",
                                   DurationSemantics.FIXED)
    adapter.frame_tap = lambda frame: lum.append(float(frame.mean()))
    await adapter.connect()
    try:
        result = await asyncio.wait_for(
            adapter.run(CLIP, "", float(CLIP_SECONDS), "cal"), timeout=timeout_s)
    finally:
        await adapter.close()

    if not lum:
        raise RuntimeError("no frames received from echo - cannot calibrate")

    samples = impulse.measure(in_lum, np.array(lum), CLIP_FPS,
                              input_flash_frames=truth["flash"]["frames"])
    gaps = [b.wall_clock - a.wall_clock
            for a, b in zip(result.events, result.events[1:])]
    return {
        "run": run_idx,
        "stop_reason": result.stop_reason.value,
        "n_frames": len(result.events),
        "resolved_version": result.info.resolved_version,
        "connect_timings": adapter.timings,
        "lag_samples_ms": [round(s.lag_ms, 2) for s in samples],
        "lag_confidences": [round(s.confidence, 3) for s in samples],
        "gaps_ms": {"p50": round(1000 * statistics.median(gaps), 2) if gaps else None,
                    "p95": round(1000 * sorted(gaps)[int(0.95 * len(gaps)) - 1], 2) if len(gaps) >= 20 else None,
                    "max": round(1000 * max(gaps), 2) if gaps else None},
    }


def analyse(runs, condition):
    all_lags = [l for r in runs for l, c in
                zip(r["lag_samples_ms"], r["lag_confidences"]) if c >= 0.3]
    ok_runs = [r for r in runs if r["n_frames"] > 0]
    gaps_p50 = [r["gaps_ms"]["p50"] for r in ok_runs if r["gaps_ms"]["p50"]]
    gaps_p95 = [r["gaps_ms"]["p95"] for r in ok_runs if r["gaps_ms"]["p95"]]

    frame_period_ms = 1000.0 / CLIP_FPS
    med_gap = statistics.median(gaps_p50) if gaps_p50 else None
    med_p95_gap = statistics.median(gaps_p95) if gaps_p95 else None
    # Chunked delivery: typical gap near 0 with bursts, or p95 >> frame period.
    delivery = "unknown"
    if med_gap is not None and med_p95_gap is not None:
        if med_p95_gap <= 2.0 * frame_period_ms:
            delivery = "frame-paced (gaps ~ frame period; FrameEvent semantics valid as-is)"
        else:
            delivery = ("chunk-bursty (p95 gap %.0f ms vs %.1f ms frame period; "
                        "TTFF/stall interpretation must account for chunking)"
                        % (med_p95_gap, frame_period_ms))

    doc = {
        "condition": condition,
        "model": "reactor/echo",
        "lens": "M",
        "n_runs": len(runs),
        "n_ok_runs": len(ok_runs),
        "n_lag_samples": len(all_lags),
        "platform_floor_ms": {
            "p50": round(statistics.median(all_lags), 1) if all_lags else None,
            "p95": round(sorted(all_lags)[max(0, int(0.95 * len(all_lags)) - 1)], 1) if all_lags else None,
            "mean": round(statistics.fmean(all_lags), 1) if all_lags else None,
            "jitter_sigma": round(statistics.pstdev(all_lags), 1) if len(all_lags) > 1 else None,
        },
        "delivery": delivery,
        "gap_stats_ms": {"median_p50": med_gap, "median_p95": med_p95_gap,
                         "frame_period": frame_period_ms},
        "note": ("Floor includes SDK decode before the timestamp - identical "
                 "treatment for every Lens M product, so subtraction is valid "
                 "within Lens M."),
        "runs": runs,
    }
    return doc


async def main_async(args):
    truth = ensure_clip()
    in_lum = input_luminance()
    runs = []
    for i in range(args.runs):
        try:
            r = await one_run(i, truth, in_lum, timeout_s=CLIP_SECONDS + 40)
            ok = "%d lags, p50 %.0f ms" % (len(r["lag_samples_ms"]),
                statistics.median(r["lag_samples_ms"])) if r["lag_samples_ms"] else "no lags"
            print("run %02d: %s frames=%d %s" % (i, r["stop_reason"], r["n_frames"], ok))
        except Exception as e:
            if "credits_depleted" in str(e):
                print("CREDITS DEPLETED - aborting arm (no point burning "
                      "attempts against an empty account)")
                runs.append({"run": i, "error": "RuntimeError: credits_depleted",
                             "n_frames": 0, "lag_samples_ms": [],
                             "lag_confidences": [], "stop_reason": "exception",
                             "gaps_ms": {"p50": None, "p95": None, "max": None}})
                break
            r = {"run": i, "error": "%s: %s" % (type(e).__name__, e),
                 "n_frames": 0, "lag_samples_ms": [], "lag_confidences": [],
                 "stop_reason": "exception", "gaps_ms": {"p50": None, "p95": None, "max": None}}
            print("run %02d: EXCEPTION %s" % (i, str(e)[:120]))
        runs.append(r)
        await asyncio.sleep(args.pause)

    doc = analyse(runs, args.condition)
    os.makedirs(DATA, exist_ok=True)
    out = os.path.join(DATA, "platform-floor-%s.json" % args.condition)
    with open(out, "w") as f:
        json.dump(doc, f, indent=2)
    print("\nplatform floor [%s]: p50 %s ms, p95 %s ms over %d samples / %d runs"
          % (args.condition, doc["platform_floor_ms"]["p50"],
             doc["platform_floor_ms"]["p95"], doc["n_lag_samples"], doc["n_ok_runs"]))
    print("delivery: %s" % doc["delivery"])
    print("-> %s" % out)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", type=int, default=30)
    ap.add_argument("--condition", default="C0")
    ap.add_argument("--pause", type=float, default=2.0,
                    help="seconds between runs - do not hammer the platform")
    ap.add_argument("--profile", choices=sorted(PROFILES), default="standard")
    args = ap.parse_args()
    global CLIP_W, CLIP_H, CLIP
    CLIP_W, CLIP_H, fname = PROFILES[args.profile]
    CLIP = os.path.join(CLIP_DIR, fname)
    args.condition = "%s-%s" % (args.condition, args.profile) \
        if args.profile != "standard" else args.condition
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
