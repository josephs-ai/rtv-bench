#!/usr/bin/env python3
"""Campaign F metrics - computational ref-adoption timelines (primary).

    .venv-metrics/bin/python tools/campaign_f_metrics.py

Per capture: sample a frame every 2 s, embed the largest face (insightface
buffalo_l), and score cosine similarity to (a) the ref portrait and (b) the
input clip's person. Writes per-run timelines to
data/campaign-f/metrics/<run>.json and a summary table to
data/campaign-f/metrics/summary.json.

Readouts per arm:
  anchor  adoption = mean sim-to-ref over the post-anchor span; adopted if
          well above the input-person baseline band
  hold    sim-to-ref trend over 180 s (slope; does anchoring pin identity?)
  switch  latency = first sample after apply_at where sim-to-ref exceeds
          the pre-switch level midway to the anchor-arm adoption level
"""
import glob
import json
import os
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FDIR = os.path.join(REPO, "data", "campaign-f")
OUT = os.path.join(FDIR, "captures")
MET = os.path.join(FDIR, "metrics")
DDIR = os.path.join(REPO, "data", "campaign-d")
STEP_S = 2.0


def build_embedder():
    import numpy as np
    from insightface.app import FaceAnalysis
    from PIL import Image
    app = FaceAnalysis(providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=-1, det_size=(640, 640))

    def emb_img(path):
        fr = np.asarray(Image.open(path).convert("RGB"))
        fs = app.get(fr[..., ::-1])
        if not fs:
            return None
        e = max(fs, key=lambda f: (f.bbox[2] - f.bbox[0])
                * (f.bbox[3] - f.bbox[1])).normed_embedding
        return e / np.linalg.norm(e)
    return emb_img, np


def frame_at(video, t, out):
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t),
                        "-i", video, "-frames:v", "1", out],
                       capture_output=True)
    return r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 0


def main():
    os.makedirs(MET, exist_ok=True)
    emb, np = build_embedder()
    ref_embs = {}
    for p in glob.glob(os.path.join(DDIR, "refs", "*.jpg")):
        ref_embs[os.path.basename(p)] = emb(p)
    clip_embs = {}

    td = tempfile.mkdtemp()
    summary = []
    for mp in sorted(glob.glob(os.path.join(OUT, "*.json"))):
        meta = json.load(open(mp))
        run = os.path.basename(mp)[:-5]
        mkv = mp[:-5] + ".mkv"
        if not os.path.exists(mkv):
            continue
        outp = os.path.join(MET, run + ".json")
        if os.path.exists(outp):
            summary.append(json.load(open(outp))["summary"])
            continue
        ref = meta.get("ref")
        ref2 = meta.get("ref2")
        clip = meta["clip"]
        if clip not in clip_embs:
            f = os.path.join(td, "clip.png")
            frame_at(os.path.join(DDIR, clip), 5, f)
            clip_embs[clip] = emb(f)
        r_emb = ref_embs.get(ref) if ref else None
        r2_emb = ref_embs.get(ref2) if ref2 else None
        c_emb = clip_embs[clip]
        dur = meta.get("record_s", 35.0)
        # capture timeline starts at connect (xmax) / first frame (lucy)
        fps = meta.get("fps") or 30.0
        n_frames = meta.get("frames", 0)
        span = n_frames / fps if fps else dur
        tl = []
        t = 1.0
        while t < min(span, dur) - 0.5:
            f = os.path.join(td, "f.png")
            if frame_at(mkv, t, f):
                e = emb(f)
                if e is not None:
                    s = {"t": round(t, 1),
                         "sim_input": round(float(np.dot(e, c_emb)), 4)}
                    if r_emb is not None:
                        s["sim_ref"] = round(float(np.dot(e, r_emb)), 4)
                    if r2_emb is not None:
                        s["sim_ref2"] = round(float(np.dot(e, r2_emb)), 4)
                    tl.append(s)
            t += STEP_S
        apply_at = meta.get("apply_at_s",
                            meta.get("apply_wall_offset_s", 0.0)) or 0.0
        post = [s for s in tl if s["t"] >= apply_at + 2.0]
        pre = [s for s in tl if s["t"] < apply_at]

        def mean(key, rows):
            v = [s[key] for s in rows if key in s]
            return round(sum(v) / len(v), 4) if v else None
        row = {"run_id": run, "product": meta["product"],
               "lens": meta.get("lens"), "arm": meta["arm"],
               "ref": ref, "ref2": ref2, "clip": clip, "n_samples": len(tl),
               "apply_at_s": apply_at,
               "sim_ref_post_mean": mean("sim_ref", post),
               "sim_ref2_post_mean": mean("sim_ref2", post),
               "sim_input_post_mean": mean("sim_input", post),
               "sim_ref_pre_mean": mean("sim_ref", pre)}
        if meta["arm"] in ("hold", "control") and len(post) > 10:
            key = "sim_ref" if r_emb is not None else "sim_input"
            rows = [s for s in post if key in s]
            ts = np.array([s["t"] for s in rows])
            ys = np.array([s[key] for s in rows])
            row["hold_key"] = key
            row["hold_slope_per_min"] = round(
                float(np.polyfit(ts, ys, 1)[0]) * 60.0, 4)
            row["hold_last30s_mean"] = mean(key, rows[-15:])
        if meta["arm"] in ("switch", "chain") and pre and post:
            key = "sim_ref2" if r2_emb is not None else "sim_ref"
            pre_vals = [s.get(key) for s in pre if s.get(key) is not None]
            pre_lvl = (sum(pre_vals) / len(pre_vals)) if pre_vals else 0.0
            thresh = pre_lvl + 0.10
            lat = next((s["t"] - apply_at for s in post
                        if s.get(key, -1) > thresh), None)
            row["switch_key"] = key
            row["switch_latency_s"] = round(lat, 1) if lat is not None else None
        with open(outp, "w") as f:
            json.dump({"summary": row, "timeline": tl}, f, indent=2)
        summary.append(row)
        print("%-44s %s sim_ref_post=%s sim_input_post=%s %s"
              % (run, row["arm"], row.get("sim_ref_post_mean"),
                 row["sim_input_post_mean"],
                 ("lat=%ss" % row.get("switch_latency_s")
                  if row["arm"] == "switch" else "")))
    with open(os.path.join(MET, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print("\n%d runs -> %s" % (len(summary), os.path.join(MET, "summary.json")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
