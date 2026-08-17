#!/usr/bin/env python3
"""Campaign E - hour-scale reliability & identity (v1.1 flagship).

    .venv/bin/python tools/campaign_e_hourscale.py --smoke        # 2-min shakedown
    .venv/bin/python tools/campaign_e_hourscale.py --tiers 10,30,60

Live-avatar reality is hour-scale; nobody measures it. Per session:
  - stimulus: a SINGLE-SHOT talking-head clip looped seamlessly (one face
    throughout -> identity drift is measurable without shot-cut confounds;
    the multi-shot reel lesson is why)
  - full per-frame telemetry sidecar: arrival wall-time, motion energy,
    mean luminance (latency/gap/freeze analysis possible offline)
  - sparse visual record: one JPEG every 10 s (identity embeddings offline;
    ~360 stills/hour instead of 20 GB of FFV1)
  - network probes every 5 min into the sidecar (post-hoc attribution:
    a death that coincides with a probe collapse is vantage, not product)
Journal: data/campaign-e/runs.jsonl. Lucy lane (native python) first;
the browser lane needs chunked upload for hour-long recordings (designed,
not yet built - see ROADMAP).
"""
import argparse
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "data", "campaign-e")
STIM = os.path.join(REPO, "data", "campaign-e", "stimulus-65min.mp4")
STIM_SRC = os.path.join(REPO, "data", "campaign-d", "conform-mixkit2960.mp4")
PROMPT = "photorealistic, natural colors"


def load_env():
    for line in open(os.path.join(REPO, ".env")):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)


async def session(minutes: float, rep: int):
    import numpy as np
    from PIL import Image
    from rtveval.adapters.decart_webrtc import DecartWebRTCAdapter
    from tools.campaign_b import upload_mbps

    name = "E-lucy-2.5-%dmin-r%d" % (minutes, rep)
    sdir = os.path.join(OUT, name)
    os.makedirs(os.path.join(sdir, "stills"), exist_ok=True)
    tele = open(os.path.join(sdir, "telemetry.jsonl"), "w")

    a = DecartWebRTCAdapter()
    st = {"prev": None, "n": 0, "last_still": 0.0, "first": None, "last": None}

    def tap(fr):
        t = time.monotonic()
        g = fr.mean(axis=2).astype(np.float32)
        e = float(np.abs(g - st["prev"]).mean()) if st["prev"] is not None else None
        st["prev"] = g
        st["n"] += 1
        st["first"] = st["first"] or t
        st["last"] = t
        tele.write(json.dumps({"t": t, "e": e, "lum": round(float(g.mean()), 2)}) + "\n")
        if t - st["last_still"] >= 10.0:
            st["last_still"] = t
            Image.fromarray(fr).save(
                os.path.join(sdir, "stills", "t%07.1f.jpg" % (t - st["first"])),
                quality=88)
    a.frame_tap = tap

    async def net_probe():
        while True:
            await asyncio.sleep(300)
            mbps = await asyncio.get_event_loop().run_in_executor(None, upload_mbps)
            tele.write(json.dumps({"t": time.monotonic(), "net_mbps": mbps}) + "\n")
            tele.flush()

    t0 = time.monotonic()
    stop_reason = "?"
    probe_task = None
    try:
        await a.connect()
        probe_task = asyncio.create_task(net_probe())
        r = await asyncio.wait_for(
            a.run(STIM, PROMPT, minutes * 60.0, "C0"),
            timeout=minutes * 60.0 + 180)
        stop_reason = r.stop_reason.value
    except Exception as e:
        stop_reason = "crash: %s %s" % (type(e).__name__, str(e)[:100])
    finally:
        if probe_task:
            probe_task.cancel()
        try:
            await a.close()
        except Exception:
            pass
        tele.close()

    survived = (st["last"] - st["first"]) if st["first"] else 0.0
    row = {"run_id": name, "product_key": "lucy-2.5", "lens": "P",
           "campaign": "E", "tier_min": minutes,
           "intended_s": minutes * 60.0,
           "survived_s": round(survived, 1),
           "survival_frac": round(survived / (minutes * 60.0), 3),
           "frames": st["n"],
           "mean_fps": round(st["n"] / survived, 1) if survived > 1 else None,
           "stop_reason": stop_reason,
           "stimulus": os.path.basename(STIM), "single_shot": True,
           "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "telemetry": os.path.join(sdir, "telemetry.jsonl")}
    with open(os.path.join(OUT, "runs.jsonl"), "a") as f:
        f.write(json.dumps(row) + "\n")
    return row


async def main_async(args):
    os.makedirs(OUT, exist_ok=True)
    if not os.path.exists(STIM):
        # pre-built long stimulus: runtime looping proved unreliable
        # (smoke session stalled at exactly the clip boundary)
        import subprocess
        print("building 65-min looped stimulus (one-time)...")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop",
                        "-1", "-i", STIM_SRC, "-t", "3900", "-c", "copy",
                        STIM], check=True)
    tiers = ([2] if args.smoke else
             [float(x) for x in args.tiers.split(",")])
    est_min = sum(tiers) * args.reps
    print("plan: tiers %s x%d reps = ~%.0f min of Lucy streaming"
          % (tiers, args.reps, est_min))
    from tools.campaign_b import upload_mbps
    for rep in range(1, args.reps + 1):
        for m in tiers:
            name = "E-lucy-2.5-%dmin-r%d" % (m, rep)
            if os.path.exists(os.path.join(OUT, name)):
                print("skip (exists):", name)
                continue
            # throughput gate: hour-scale sessions are worthless on a
            # sagged uplink (2026-08-18: 1.2 Mbps produced 1-3% survival
            # stalls) - hold until the window is healthy, don't burn runs
            while True:
                mbps = upload_mbps()
                if mbps >= args.min_mbps:
                    print("uplink %.1f Mbps >= %.0f - go" % (mbps,
                                                             args.min_mbps))
                    break
                print("uplink %.1f Mbps < %.0f - holding 5 min" % (
                    mbps, args.min_mbps), flush=True)
                import time as _t
                _t.sleep(300)
            print("session %s ..." % name)
            row = await session(m, rep)
            print("  survived %.0f%% (%.0fs of %.0fs) fps=%s stop=%s"
                  % (row["survival_frac"] * 100, row["survived_s"],
                     row["intended_s"], row["mean_fps"], row["stop_reason"]))
            await asyncio.sleep(10)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tiers", default="10,30,60")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--min-mbps", type=float, default=8.0,
                    help="uplink gate: hold until throughput >= this")
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    load_env()
    os.environ.setdefault("RTVEVAL_FORCE_TURN_TCP", "1")
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
