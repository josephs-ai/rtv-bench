#!/usr/bin/env python3
"""Footage-to-campaign pipeline: master in, everything Campaign C needs out.

    .venv/bin/python tools/conform_reel.py MASTER.mov --shots shots.json

Steps (all recorded, nothing silent):
  1. Probe the master; refuse if any product path would be an upscale.
  2. Render the instrumented reel (flashes + block strip) at master
     resolution, with clip spans from the shot manifest -> ground-truth
     sidecar.
  3. Conform the reel per product input spec (deterministic recipe,
     content-addressed recipe_id).
  4. Write data/conform-manifest.json for the reproduction appendix, and
     eyeball-sample stubs (tools/eyeball.py reel/conform are the next
     human steps - the pilot gate warns if they're skipped).

Shot manifest (shots.json): [{"clip_id": "V1", "start_s": 0, "end_s": 12}, ...]
Spans must tile the master.

Product input specs below: CONFIRMED means from vendor docs/probe; PENDING
means awaiting the pilot capability probe - those products are skipped with a
loud note rather than conformed to a guess.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rtveval.reel import conform, render  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, "data")

# Who needs conformed VIDEO input at all: V2V (and digital human, when
# reachable). Generation models take text/image seeds, not our reel.
INPUT_SPECS = {
    "lucy-2.5": {"spec": conform.InputSpec("lucy-2.5", 1280, 720, 30.0),
                 "status": "CONFIRMED (docs.platform.decart.ai: 720p30)"},
    "xmax-x2.0": {"spec": conform.InputSpec("xmax-x2.0", 1280, 720, 30.0),
                  "status": "CONFIRMED empirically (live sessions 2026-08-11: "
                            "720p30 camera ingested for minutes, output "
                            "1280x736; native path)"},
    "vidu-s1": {"spec": None,
                "status": "PENDING enterprise-beta access"},
}


def load_shots(path, fps, n_frames):
    with open(path) as f:
        shots = json.load(f)
    spans = [render.ClipSpan(s["clip_id"], int(round(s["start_s"] * fps)),
                             int(round(s["end_s"] * fps))) for s in shots]
    if spans:
        spans[-1] = spans[-1]._replace(end_frame=n_frames)  # absorb rounding
    return spans


def master_frames(path):
    import av
    from PIL import Image

    with av.open(path) as c:
        for frame in c.decode(video=0):
            yield Image.fromarray(frame.to_ndarray(format="rgb24"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("master")
    ap.add_argument("--shots", required=True, help="shot manifest json")
    ap.add_argument("--out-dir", default=os.path.join(DATA, "reel"))
    args = ap.parse_args()

    info = conform.probe_master(args.master)
    print("master: %dx%d @ %g fps, %.1f MB, hash %s"
          % (info.width, info.height, info.fps, info.size_bytes / 1e6,
             info.quick_hash))

    # 1. upscale refusal BEFORE any work
    blockers = []
    for key, entry in INPUT_SPECS.items():
        spec = entry["spec"]
        if spec is None:
            continue
        if spec.width > info.width or spec.height > info.height or spec.fps > info.fps:
            blockers.append("%s needs %dx%d@%g - master is smaller/slower"
                            % (key, spec.width, spec.height, spec.fps))
    if blockers:
        print("REFUSED - refilm or re-export the master:\n  " +
              "\n  ".join(blockers), file=sys.stderr)
        return 1

    # 2. instrumented reel at master resolution
    os.makedirs(args.out_dir, exist_ok=True)
    import av
    with av.open(args.master) as c:
        stream = c.streams.video[0]
        n_frames = stream.frames or int(float(stream.duration * stream.time_base)
                                        * float(stream.average_rate))
    spans = load_shots(args.shots, info.fps, n_frames)
    reel_path = os.path.join(args.out_dir, "reel-master.mp4")
    spec = render.ReelSpec(width=info.width, height=info.height, fps=info.fps)
    truth = render.render_reel(master_frames(args.master), n_frames, spec,
                               spans, reel_path)
    print("reel: %s (%d frames, %d clips, %d flashes)"
          % (reel_path, truth["n_frames"], len(truth["clips"]),
             len(truth["flash"]["frames"])))

    # 3. per-product conforms
    records, skipped = [], []
    reel_info = conform.probe_master(reel_path)
    for key, entry in INPUT_SPECS.items():
        if entry["spec"] is None:
            skipped.append((key, entry["status"]))
            continue
        out = os.path.join(args.out_dir, "input-%s.mp4" % key)
        rec = conform.conform(reel_info, entry["spec"], out)
        records.append(rec)
        print("conform %-12s -> %s (recipe %s)" % (key, out, rec.recipe_id))

    conform.write_manifest(records, reel_info,
                           os.path.join(DATA, "conform-manifest.json"))
    for key, why in skipped:
        print("SKIPPED %-12s %s" % (key, why))
    print("\nnext human steps: tools/eyeball.py reel %s ; tools/eyeball.py "
          "conform %s" % (args.out_dir, args.out_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
