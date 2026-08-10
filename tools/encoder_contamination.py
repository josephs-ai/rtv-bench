#!/usr/bin/env python3
"""Does CRF 12 contaminate the temporal-flicker metric?

Addendum Part 4 asserts that compression artifacts leak into inter-frame LPIPS.
If true, every temporal-coherence score is skewed - and unequally, since the
skew depends on each product's output characteristics. If false, CRF 12 saves
roughly an order of magnitude of disk over FFV1.

This settles it with evidence before 100+ GB is committed, by encoding the same
clips both ways and computing the metric on each.

FFV1 at 1080p60 runs several GB/min, so this deliberately runs on a small
subset - three or four clips, not the corpus.

Runs in .venv-metrics (needs torch + lpips):
    .venv-metrics/bin/python tools/encoder_contamination.py clip1.mp4 clip2.mp4
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Below this, the encoder's contribution is immaterial next to the differences
# between products we are trying to resolve.
NEGLIGIBLE_RELATIVE_DELTA = 0.02  # 2% of the lossless LPIPS value


def encode(src: str, dst: str, mode: str) -> float:
    """Encode src->dst. Returns output size in MB."""
    if mode == "lossless":
        codec = ["-c:v", "ffv1", "-level", "3"]
    elif mode == "crf12":
        codec = ["-c:v", "libx264", "-crf", "12", "-preset", "slow"]
    else:
        raise ValueError(mode)

    cmd = (["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", src]
           + codec + ["-pix_fmt", "yuv420p", "-fps_mode", "cfr", "-an", dst])
    subprocess.run(cmd, check=True)
    return os.path.getsize(dst) / 1e6


def frames_of(path: str, max_frames: int):
    """Decode to RGB numpy frames with PyAV."""
    import av
    import numpy as np

    out = []
    with av.open(path) as container:
        for frame in container.decode(video=0):
            out.append(frame.to_ndarray(format="rgb24"))
            if len(out) >= max_frames:
                break
    return out


def temporal_lpips(frames, device: str) -> float:
    """Mean LPIPS between consecutive frames - the Spec D.2 flicker metric."""
    import lpips
    import numpy as np
    import torch

    net = lpips.LPIPS(net="alex").to(device)
    net.eval()

    def to_tensor(f):
        t = torch.from_numpy(f).float().permute(2, 0, 1)[None] / 127.5 - 1.0
        return t.to(device)

    total, count = 0.0, 0
    with torch.no_grad():
        prev = to_tensor(frames[0])
        for f in frames[1:]:
            cur = to_tensor(f)
            total += float(net(prev, cur).item())
            count += 1
            prev = cur
    return total / max(count, 1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clips", nargs="+", help="source clips (3-4 is enough)")
    ap.add_argument("--max-frames", type=int, default=300,
                    help="frames per clip to measure (default 300 = 5 s at 60 fps)")
    ap.add_argument("--keep", help="directory to keep the encodes in")
    args = ap.parse_args()

    try:
        import torch
        device = "mps" if torch.backends.mps.is_available() else "cpu"
    except ImportError:
        print("Run this with .venv-metrics/bin/python (needs torch + lpips).",
              file=sys.stderr)
        return 2

    workdir = args.keep or tempfile.mkdtemp(prefix="enc-contam-")
    os.makedirs(workdir, exist_ok=True)
    print("device: %s   workdir: %s\n" % (device, workdir))

    rows = []
    for clip in args.clips:
        if not os.path.exists(clip):
            print("missing: %s" % clip, file=sys.stderr)
            return 2
        stem = os.path.splitext(os.path.basename(clip))[0]
        print("%s" % stem)

        ll_path = os.path.join(workdir, stem + ".lossless.mkv")
        crf_path = os.path.join(workdir, stem + ".crf12.mp4")
        ll_mb = encode(clip, ll_path, "lossless")
        crf_mb = encode(clip, crf_path, "crf12")

        ll = temporal_lpips(frames_of(ll_path, args.max_frames), device)
        crf = temporal_lpips(frames_of(crf_path, args.max_frames), device)
        delta = crf - ll
        rel = delta / ll if ll > 1e-9 else float("inf")

        print("  lossless  LPIPS %.6f   %7.1f MB" % (ll, ll_mb))
        print("  CRF 12    LPIPS %.6f   %7.1f MB" % (crf, crf_mb))
        print("  delta     %+.6f (%+.2f%%)   size ratio %.1fx\n"
              % (delta, rel * 100, ll_mb / max(crf_mb, 1e-9)))

        rows.append({"clip": stem, "lossless_lpips": ll, "crf12_lpips": crf,
                     "delta": delta, "relative_delta": rel,
                     "lossless_mb": ll_mb, "crf12_mb": crf_mb})

    worst = max(rows, key=lambda r: abs(r["relative_delta"]))
    print("=" * 68)
    print("worst-case relative delta: %+.2f%% (%s)"
          % (worst["relative_delta"] * 100, worst["clip"]))

    if abs(worst["relative_delta"]) <= NEGLIGIBLE_RELATIVE_DELTA:
        print("VERDICT: CRF 12 is safe for Campaign C. The encoder contributes")
        print("  <=%.0f%% of measured flicker - immaterial next to between-product"
              % (NEGLIGIBLE_RELATIVE_DELTA * 100))
        print("  differences. Cite this check in the methodology.")
        verdict = "crf12_safe"
    else:
        print("VERDICT: CRF 12 CONTAMINATES the flicker metric. Capture Campaign C")
        print("  lossless (FFV1), or the encoder skews every temporal-coherence")
        print("  score - and unequally across products. Re-provision storage.")
        verdict = "lossless_required"

    out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "data", "encoder-contamination.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"verdict": verdict, "threshold": NEGLIGIBLE_RELATIVE_DELTA,
                   "max_frames": args.max_frames, "device": device, "clips": rows},
                  f, indent=2)
    print("\nevidence -> %s" % out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
