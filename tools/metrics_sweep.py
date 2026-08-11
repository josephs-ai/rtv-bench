#!/usr/bin/env python3
"""Layer-1 computed-metrics sweep over captures. RUN IN .venv-metrics:

    .venv-metrics/bin/python tools/metrics_sweep.py data/pilot-captures
    .venv-metrics/bin/python tools/metrics_sweep.py data/pilot-captures --no-dino

Per capture (.mkv + sibling .json) writes data/quality-metrics/<name>.json:
  - sweep_clip results (flicker/identity/adherence/EPE, models injected)
  - VBench-protocol temporal_flickering + DINO subject consistency
  - motion_jerk / long_horizon_consistency (E.7 / E.8 proxies)

These are SUPPORTING evidence (Spec D.3) - raw values live next to the
anchor-relative scoring, which needs Anchor-0/Anchor-R footage to exist.
"""
import argparse
import glob
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(REPO, "data", "quality-metrics")


def load_frames(path, max_frames=400):
    import av
    frames = []
    with av.open(path) as c:
        for f in c.decode(c.streams.video[0]):
            frames.append(f.to_ndarray(format="rgb24"))
            if len(frames) >= max_frames:
                break
    return frames


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("capture_dir")
    ap.add_argument("--no-dino", action="store_true")
    ap.add_argument("--max-frames", type=int, default=400)
    args = ap.parse_args()

    from rtveval import vbench_metrics
    from rtveval.metrics_models import load_all
    from rtveval.quality_metrics import (long_horizon_consistency, motion_jerk,
                                         sweep_clip)

    models = load_all()
    print("models loaded: %s" % ", ".join(sorted(models)) or "NONE")
    dino = None
    if not args.no_dino:
        try:
            dino = vbench_metrics.load_dino_embedder()
            print("dino loaded")
        except Exception as e:
            print("dino unavailable: %s" % str(e)[:120])

    os.makedirs(OUTDIR, exist_ok=True)
    done = 0
    for mkv in sorted(glob.glob(os.path.join(args.capture_dir, "*.mkv"))):
        metap = mkv.replace(".mkv", ".json")
        if not os.path.exists(metap) or os.path.getsize(mkv) == 0:
            continue
        meta = json.load(open(metap))
        name = os.path.splitext(os.path.basename(mkv))[0]
        t0 = time.monotonic()
        frames = load_frames(mkv, args.max_frames)
        if len(frames) < 10:
            print("%s: only %d frames, skipped" % (name, len(frames)))
            continue
        fps = meta.get("fps", 16.0)

        m = sweep_clip(frames, run_id=name, fps=fps,
                       prompt=meta.get("prompt"), sample_every=15, **models)
        out = {"run_id": name, "n_frames": len(frames), "fps_assumed": fps,
               "sweep": {"flicker_lpips": m.flicker_lpips,
                         "flicker_masked_out": m.flicker_masked_out,
                         "identity": m.identity._asdict() if m.identity else None,
                         "clip_adherence": m.clip_adherence,
                         "motion_epe": m.motion_epe,
                         "blink": m.blink},
               "vbench": {"temporal_flickering":
                          vbench_metrics.temporal_flickering(frames)},
               "models_present": sorted(models),
               "note": ("raw supporting values; anchor-relative 1-5 scoring "
                        "requires Anchor-0/Anchor-R footage (Spec D.1)")}

        if "flow_fn" in models:
            flow = models["flow_fn"]
            mags = [float(flow(frames[i - 1], frames[i]).mean())
                    for i in range(1, len(frames), 2)]
            out["motion_jerk"] = motion_jerk(mags, fps / 2.0)
        if dino is not None:
            out["vbench"]["subject_consistency"] = vbench_metrics.feature_consistency(
                frames, dino, sample_every=8)
            out["long_horizon"] = long_horizon_consistency(frames, dino, fps,
                                                           sample_every=8)
            # post-edit coherence (E.9): when the capture logged a mid-stream
            # steer, measure whether the change COMMITTED or blends back -
            # per-frame similarity to the pre-steer reference, fed to
            # steer_commitment. Recording started at content-live, and
            # steer_sent_at_s is seconds after live, so the index maps 1:1.
            steer_s = meta.get("steer_sent_at_s")
            if steer_s is not None:
                import numpy as _np
                from rtveval.quality_metrics import steer_commitment
                steer_idx = int(steer_s * fps)
                pre_lo = max(0, steer_idx - int(5 * fps))
                if steer_idx > pre_lo + 3 and steer_idx < len(frames) - 5:
                    embs = []
                    for fr in frames[pre_lo:steer_idx:4]:
                        e = dino(fr)
                        if e is not None:
                            embs.append(e / max(_np.linalg.norm(e), 1e-12))
                    if embs:
                        ref = _np.mean(_np.stack(embs), axis=0)
                        ref /= max(_np.linalg.norm(ref), 1e-12)
                        sims = []
                        for fr in frames:
                            e = dino(fr)
                            sims.append(float(_np.dot(ref, e / max(
                                _np.linalg.norm(e), 1e-12)))
                                if e is not None else 1.0)
                        out["steer"] = {
                            "steer_at_s": steer_s,
                            "commitment": steer_commitment(sims, steer_idx, fps),
                        }
        out["wall_s"] = round(time.monotonic() - t0, 1)

        with open(os.path.join(OUTDIR, name + ".json"), "w") as f:
            json.dump(out, f, indent=2)
        print("%s: %d frames in %.0fs -> flicker=%s subj_cons=%s jerk=%s"
              % (name, len(frames), out["wall_s"],
                 "%.4f" % m.flicker_lpips if m.flicker_lpips else m.flicker_lpips,
                 out["vbench"].get("subject_consistency"),
                 (out.get("motion_jerk") or {}).get("pops_per_min")))
        done += 1
    print("%d captures swept -> %s" % (done, OUTDIR))
    return 0 if done else 1


if __name__ == "__main__":
    sys.exit(main())
