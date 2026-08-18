#!/usr/bin/env python3
"""Campaign G metrics - interaction-density analyzer (primary computational).

    .venv-metrics/bin/python tools/campaign_g_metrics.py

Per capture: sample a frame every 1 s and score three tracks:
  commits    for each edit in the meta's edit_schedule, CLIP text-image
             cosine between frames and the edit's instruction (open_clip
             ViT-B-32 / laion2b_s34b_b79k - the same stack as
             rtveval.metrics_models.load_clip_scorer), windowed
             pre [t-8..t] vs post [t+2..t+10];
             committed := post_mean - pre_mean > COMMIT_DELTA. The 0.02
             threshold is deliberate: raw CLIP cosines sit ~0.15-0.30 and a
             single-attribute edit moves them ~0.02-0.05, so 0.02 clears
             per-frame jitter without demanding a full scene change.
             Commit latency = first post-window second whose sim exceeds
             pre_mean + COMMIT_DELTA.
  identity   insightface largest-face sim to the t=2 reference frame every
             2 s -> identity_floor (min) and identity_slope (per minute)
             across the whole session.
  stability  per-sample frame pixel std -> level and per-minute trend (a
             flattening/collapsing stream drifts down).

Edit times on the capture timeline prefer t_sent_wall_offset_s (wall time
from first frame is the scheduling truth per the playbooks), then
frame_at_send / measured fps, then t_target_s.

Writes per-run json to data/campaign-g/metrics/<run>.json and a summary
with per-product aggregates to data/campaign-g/metrics/summary.json.
"""
import glob
import json
import os
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GDIR = os.path.join(REPO, "data", "campaign-g")
OUT = os.path.join(GDIR, "captures")
MET = os.path.join(GDIR, "metrics")
STEP_S = 1.0
ID_STEP_S = 2.0
COMMIT_DELTA = 0.02
PRE_W = (-8.0, 0.0)   # window around edit t, inclusive of t itself
POST_W = (2.0, 10.0)


def build_models():
    import numpy as np
    import open_clip
    import torch
    from insightface.app import FaceAnalysis
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    model, _, preprocess = open_clip.create_model_and_transforms(
        "ViT-B-32", pretrained="laion2b_s34b_b79k")
    model = model.to(dev).eval()
    tokenizer = open_clip.get_tokenizer("ViT-B-32")
    tcache = {}

    def clip_img(frame):
        from PIL import Image
        with torch.no_grad():
            v = model.encode_image(
                preprocess(Image.fromarray(frame)).unsqueeze(0).to(dev))
            v = v / v.norm(dim=-1, keepdim=True)
        return v.squeeze(0).cpu().numpy().astype(np.float64)

    def clip_txt(text):
        if text not in tcache:
            with torch.no_grad():
                t = model.encode_text(tokenizer([text]).to(dev))
                t = t / t.norm(dim=-1, keepdim=True)
            tcache[text] = t.squeeze(0).cpu().numpy().astype(np.float64)
        return tcache[text]

    app = FaceAnalysis(providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=-1, det_size=(640, 640))

    def face_emb(frame):
        fs = app.get(frame[..., ::-1])
        if not fs:
            return None
        e = max(fs, key=lambda f: (f.bbox[2] - f.bbox[0])
                * (f.bbox[3] - f.bbox[1])).normed_embedding
        return e / np.linalg.norm(e)

    return clip_img, clip_txt, face_emb, np


def frame_at(video, t, out):
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t),
                        "-i", video, "-frames:v", "1", out],
                       capture_output=True)
    return r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 0


def probe_duration(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", video],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None


def edit_list(meta, fps):
    """Normalize edit_schedule defensively; the campaign_g driver may not
    exist yet, so accept any subset of the specced fields."""
    out = []
    for e in meta.get("edit_schedule") or []:
        if not isinstance(e, dict):
            continue
        t = e.get("t_sent_wall_offset_s")
        if t is None and e.get("frame_at_send") is not None and fps:
            t = float(e["frame_at_send"]) / fps
        if t is None:
            t = e.get("t_target_s")
        instr = e.get("instruction")
        if t is None or not instr:
            continue
        out.append({"t": float(t), "instruction": instr})
    return out


def slope_per_min(np, rows, key):
    pts = [(s["t"], s[key]) for s in rows if s.get(key) is not None]
    if len(pts) < 3:
        return None
    ts = np.array([p[0] for p in pts])
    ys = np.array([p[1] for p in pts])
    return round(float(np.polyfit(ts, ys, 1)[0]) * 60.0, 4)


def main():
    os.makedirs(MET, exist_ok=True)
    clip_img, clip_txt, face_emb, np = build_models()
    td = tempfile.mkdtemp()
    from PIL import Image

    summary = []
    all_edits = []   # (product, edit_row) for product-level latency medians
    for mp in sorted(glob.glob(os.path.join(OUT, "*.json"))):
        meta = json.load(open(mp))
        run = os.path.basename(mp)[:-5]
        mkv = mp[:-5] + ".mkv"
        if not os.path.exists(mkv):
            continue
        outp = os.path.join(MET, run + ".json")
        if os.path.exists(outp):
            prev = json.load(open(outp))
            summary.append(prev["summary"])
            for er in prev.get("edits", []):
                all_edits.append((prev["summary"]["product"], er))
            continue
        fps = meta.get("fps") or 30.0
        n_frames = meta.get("frames", 0)
        rec_s = meta.get("record_s") or 0.0
        file_dur = probe_duration(mkv) or 0.0
        # WALL vs FILE timelines diverge per product (verified 08-18):
        # lucy FFV1 is CFR-30-labelled at ~15 fps delivery, so the file
        # plays compressed (file_s = wall_s * fps_measured/30); xmax
        # webm->mkv keeps real-time pts (ratio ~1). Edit times, windows and
        # sample t stay in WALL seconds (the scheduling truth); only the
        # ffmpeg -ss seek converts via this ratio.
        wall_ext = (n_frames / fps if (n_frames and fps)
                    else (file_dur or rec_s))
        ratio = (file_dur / wall_ext) if (file_dur and wall_ext) else 1.0
        span = min(wall_ext, rec_s) if rec_s else wall_ext
        edits = edit_list(meta, fps)

        # one decode pass: every 1 s -> CLIP emb + pixel std; every 2 s -> face
        samples = []      # {"t", "emb", "std"}
        id_tl = []        # {"t", "sim"} vs t=2 reference face
        ref_face = None
        t = 1.0
        while t < span - 0.5:
            f = os.path.join(td, "f.png")
            if frame_at(mkv, t * ratio, f):
                fr = np.asarray(Image.open(f).convert("RGB"))
                samples.append({"t": round(t, 1), "emb": clip_img(fr),
                                "std": round(float(fr.std()), 3)})
                if abs(t / ID_STEP_S - round(t / ID_STEP_S)) < 1e-6:
                    e = face_emb(fr)
                    if e is not None and ref_face is None and t >= 2.0:
                        ref_face = e  # first detectable face at/after t=2
                    if e is not None and ref_face is not None:
                        id_tl.append({"t": round(t, 1),
                                      "sim": round(float(np.dot(e, ref_face)),
                                                   4)})
            t += STEP_S

        edit_rows = []
        for i, e in enumerate(edits):
            txt = clip_txt(e["instruction"])
            sims = [{"t": s["t"], "sim": round(float(np.dot(s["emb"], txt)), 4)}
                    for s in samples
                    if e["t"] + PRE_W[0] <= s["t"] <= e["t"] + POST_W[1]]
            pre = [s["sim"] for s in sims
                   if e["t"] + PRE_W[0] <= s["t"] <= e["t"] + PRE_W[1]]
            post = [s["sim"] for s in sims
                    if e["t"] + POST_W[0] <= s["t"] <= e["t"] + POST_W[1]]
            row = {"idx": i, "t": round(e["t"], 1),
                   "instruction": e["instruction"],
                   "n_pre": len(pre), "n_post": len(post),
                   "pre_mean": round(sum(pre) / len(pre), 4) if pre else None,
                   "post_mean": round(sum(post) / len(post), 4) if post else None,
                   "committed": None, "commit_latency_s": None,
                   "window_sims": sims}
            if pre and post:
                delta = row["post_mean"] - row["pre_mean"]
                row["delta"] = round(delta, 4)
                row["committed"] = delta > COMMIT_DELTA
                thresh = row["pre_mean"] + COMMIT_DELTA
                lat = next((s["t"] - e["t"] for s in sims
                            if s["t"] >= e["t"] + POST_W[0]
                            and s["sim"] > thresh), None)
                row["commit_latency_s"] = (round(lat, 1)
                                           if lat is not None else None)
            edit_rows.append(row)
            all_edits.append((meta.get("product", "unknown"), row))

        scored = [r for r in edit_rows if r["committed"] is not None]
        committed = [r for r in scored if r["committed"]]
        std_tl = [{"t": s["t"], "std": s["std"]} for s in samples]
        id_sims = [s["sim"] for s in id_tl]
        stds = [s["std"] for s in std_tl]
        row = {"run_id": run, "product": meta.get("product", "unknown"),
               "lens": meta.get("lens"), "arm": meta.get("arm"),
               "n_samples": len(samples), "n_edits": len(edits),
               "edits_scored": len(scored), "edits_committed": len(committed),
               "edits_committed_frac": (round(len(committed) / len(scored), 3)
                                        if scored else None),
               "identity_floor": (round(min(id_sims), 4) if id_sims else None),
               "identity_slope_per_min": slope_per_min(np, id_tl, "sim"),
               "frame_std_mean": (round(sum(stds) / len(stds), 2)
                                  if stds else None),
               "frame_std_slope_per_min": slope_per_min(np, std_tl, "std")}
        with open(outp, "w") as f:
            json.dump({"summary": row, "edits": edit_rows,
                       "identity_timeline": id_tl, "std_timeline": std_tl},
                      f, indent=2)
        summary.append(row)
        print("%-44s edits=%s/%s frac=%s id_floor=%s std_slope=%s"
              % (run, len(committed), len(scored),
                 row["edits_committed_frac"], row["identity_floor"],
                 row["frame_std_slope_per_min"]))

    # per-product aggregates
    products = {}
    for r in summary:
        products.setdefault(r["product"], []).append(r)
    aggs = {}
    for prod, rows in sorted(products.items()):
        fracs = [r["edits_committed_frac"] for r in rows
                 if r["edits_committed_frac"] is not None]
        floors = [r["identity_floor"] for r in rows
                  if r["identity_floor"] is not None]
        lats = sorted(er["commit_latency_s"] for p, er in all_edits
                      if p == prod and er.get("committed")
                      and er.get("commit_latency_s") is not None)
        aggs[prod] = {
            "n_runs": len(rows),
            "n_edits_scored": sum(r["edits_scored"] for r in rows),
            "edits_committed_frac_mean": (round(sum(fracs) / len(fracs), 3)
                                          if fracs else None),
            "commit_latency_median_s": (round(lats[len(lats) // 2], 1)
                                        if lats else None),
            "identity_floor_mean": (round(sum(floors) / len(floors), 4)
                                    if floors else None)}
    with open(os.path.join(MET, "summary.json"), "w") as f:
        json.dump({"runs": summary, "products": aggs,
                   "commit_delta_threshold": COMMIT_DELTA}, f, indent=2)

    print("\n%-16s %5s %6s %10s %10s %10s"
          % ("product", "runs", "edits", "commit_frac", "lat_med_s",
             "id_floor"))
    for prod, a in sorted(aggs.items()):
        print("%-16s %5d %6d %10s %10s %10s"
              % (prod, a["n_runs"], a["n_edits_scored"],
                 a["edits_committed_frac_mean"], a["commit_latency_median_s"],
                 a["identity_floor_mean"]))
    print("\n%d runs -> %s" % (len(summary), os.path.join(MET, "summary.json")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
