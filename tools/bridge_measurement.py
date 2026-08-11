#!/usr/bin/env python3
"""The sec 2.1 bridge: Xmax on both routes -> the measured Reactor delta.

LOAD-PROFILE PIN (do not change without re-deriving the floor):
  - The Lens P leg (composite, data/xmax-lensP-composite.json) used a 640x360
    source. This leg therefore publishes the SAME 640x360 instrumented clip
    the standard floor arms used (data/echo-clip/echo-cal.mp4), and the delta
    is taken against the STANDARD-profile C0 floor. The floor is load-
    dependent (~967 ms between profiles, CIs separated) - a mismatched
    profile would measure load, not platform.

Output frames arrive via the SDK callback (Lens M, sdk_callback path);
lag by impulse xcorr against the clip's known flashes; N runs pooled.

    RTVEVAL_FORCE_TURN_TCP=1 .venv/bin/python tools/bridge_measurement.py --runs 6
"""
import argparse
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, "data")
CLIP = os.path.join(DATA, "echo-clip", "echo-cal.mp4")  # the floor's own clip
CLIP_SECONDS = 20
CLIP_FPS = 30.0

XMAX_REACTOR_MODEL = "xmax/x2"
PROMPT = "subtle warm cinematic grade"  # matches the Lens P run's prompt


async def one_run(idx, truth, in_lum):
    from rtveval.adapters.base import DurationSemantics
    from rtveval.adapters.reactor_webrtc import ReactorWebRTCAdapter
    from rtveval.latency import impulse

    lum = []
    a = ReactorWebRTCAdapter("xmax-x2.0", XMAX_REACTOR_MODEL,
                             DurationSemantics.FIXED,
                             prompt_command="set_prompt")
    a.frame_tap = lambda f: lum.append(float(f.mean()))
    await a.connect()
    try:
        result = await asyncio.wait_for(
            a.run(CLIP, PROMPT, float(CLIP_SECONDS), "bridge"),
            timeout=CLIP_SECONDS + 60)
    finally:
        await a.close()
    if len(lum) < 60:
        raise RuntimeError("only %d frames received" % len(lum))
    samples = impulse.measure(in_lum, np.array(lum), CLIP_FPS,
                              input_flash_frames=truth["flash"]["frames"])
    return samples, result


async def main_async(args):
    from rtveval.latency.base import summarise
    from rtveval.reel import render
    from rtveval.stats import FloorEstimate, decompose_lens_m
    import av

    # floor prerequisite: standard-profile C0, clean vantage
    analysis = json.load(open(os.path.join(DATA, "platform-floor-analysis.json")))
    c0 = analysis["conditions"]["C0"]["floor_p50_ms"]
    floor = FloorEstimate("p50", c0["point"], c0["ci95"][0], c0["ci95"][1],
                          analysis["conditions"]["C0"]["n_runs"], 0)
    print("standard-profile C0 floor: %.0f ms (CI %.0f-%.0f)"
          % (floor.point_ms, floor.lo_ms, floor.hi_ms))

    truth = render.load_truth(CLIP)
    in_lum = []
    with av.open(CLIP) as c:
        for frame in c.decode(video=0):
            in_lum.append(float(frame.to_ndarray(format="rgb24").mean()))
    in_lum = np.array(in_lum)

    pooled = []
    runs_meta = []
    for i in range(args.runs):
        try:
            samples, result = await one_run(i, truth, in_lum)
            good = [s for s in samples if s.confidence >= 0.3]
            pooled.extend(good)
            runs_meta.append({"run": i, "n_lags": len(good),
                              "stop": result.stop_reason.value,
                              "version": result.info.resolved_version})
            print("run %d: %d lags, stop=%s" % (i, len(good), result.stop_reason.value))
        except Exception as e:
            runs_meta.append({"run": i, "error": str(e)[:200]})
            print("run %d FAILED: %s" % (i, str(e)[:120]))
            if "credits_depleted" in str(e):
                print("credits gone - aborting")
                break
        await asyncio.sleep(2)

    if len(pooled) < 10:
        print("insufficient samples for a bridge figure", file=sys.stderr)
        return 1

    lens_m = summarise(pooled, lens="M")
    lens_p = json.load(open(os.path.join(DATA, "xmax-lensP-composite.json")))
    p50_native = float(lens_p["result"]["p50_ms"])

    deco = decompose_lens_m(lens_m.p50_ms, floor)
    delta_vs_native = lens_m.p50_ms - p50_native

    doc = {
        "measured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "load_profile_pin": "640x360 both legs; standard-profile C0 floor",
        "lens_m": {"p50_ms": round(lens_m.p50_ms, 1), "p95_ms": round(lens_m.p95_ms, 1),
                   "n": lens_m.n, "headline": lens_m.headline()},
        "lens_p_native_p50_ms": p50_native,
        "reactor_delta_ms": round(delta_vs_native, 1),
        "floor_prediction": deco.statement,
        "floor_crosscheck": {
            "floor_p50_ms": floor.point_ms,
            "model_contribution_via_floor": round(deco.point_ms, 1),
            "native_measured": p50_native,
            "agreement_ms": round(deco.point_ms - p50_native, 1),
            "note": ("if |agreement| is small, floor-subtraction is validated "
                     "as a proxy for products with no native route"),
        },
        "runs": runs_meta,
    }
    out = os.path.join(DATA, "bridge-measurement.json")
    with open(out, "w") as f:
        json.dump(doc, f, indent=2)
    print("\nBRIDGE: Lens M p50 %.0f ms | native p50 %.0f ms | Reactor delta %.0f ms"
          % (lens_m.p50_ms, p50_native, delta_vs_native))
    print("floor cross-check: model-via-floor %.0f ms vs native %.0f ms (diff %.0f)"
          % (deco.point_ms, p50_native, deco.point_ms - p50_native))
    print("-> %s" % out)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=6)
    return asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
