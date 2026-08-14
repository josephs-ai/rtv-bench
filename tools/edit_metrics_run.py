#!/usr/bin/env python3
"""Run the Campaign-D edit metrics over captures. RUN IN .venv-metrics:

    .venv-metrics/bin/python tools/edit_metrics_run.py data/campaign-d/captures
"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTD = os.path.join(REPO, "data", "edit-metrics")
REFS = os.path.join(REPO, "data", "campaign-d", "refs")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("capture_dir")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    import numpy as np
    from rtveval import edit_metrics as em
    from rtveval import vbench_metrics
    from rtveval.metrics_models import load_flow

    # face detector with bbox access (insightface app, not just embeddings)
    from insightface.app import FaceAnalysis
    app = FaceAnalysis(providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=-1, det_size=(640, 640))

    def face_embed(frame):
        faces = app.get(frame[..., ::-1])
        if not faces:
            return None
        return max(faces, key=lambda f: f.det_score).normed_embedding

    dino = vbench_metrics.load_dino_embedder()
    flow = load_flow()
    os.makedirs(OUTD, exist_ok=True)

    for mkv in sorted(glob.glob(os.path.join(args.capture_dir, "D-*.mkv"))):
        name = os.path.splitext(os.path.basename(mkv))[0]
        outp = os.path.join(OUTD, name + ".json")
        if os.path.exists(outp) and not args.force:
            continue
        metap = mkv.replace(".mkv", ".json")
        if not os.path.exists(metap):
            continue
        meta = json.load(open(metap))
        fps = float(meta.get("fps") or 15.0)
        if meta.get("edit_sent_frame") is not None:
            edit_frame = int(meta["edit_sent_frame"])
        elif meta.get("edit_at_s_from_streamup") is not None:
            # canvas captures are wall-clocked at their label rate
            fps = float(meta.get("fps") or 30.0)
            edit_frame = int(((meta.get("ttff_s") or 0.0)
                              + meta["edit_at_s_from_streamup"]) * fps)
        else:
            continue

        import av
        frames = []
        with av.open(mkv) as c:
            for f in c.decode(c.streams.video[0]):
                fr = f.to_ndarray(format="rgb24")
                if fr.shape[1] > 640:
                    fr = fr[::2, ::2]
                frames.append(fr)
        n = len(frames)
        if n < edit_frame + int(5 * fps):
            print(name, "too short after edit, skipped")
            continue
        get = lambda i: frames[i] if 0 <= i < n else None

        target, protected = em.region_for(meta["edit_id"])
        idxs = list(range(0, n, max(2, int(fps / 5))))
        sig_t = em.region_signal(idxs, get, app.get, dino, target)
        pre_t = em.centroid([e for i, e in sig_t.items() if i < edit_frame])
        post_t = em.centroid([e for i, e in sig_t.items()
                              if i > edit_frame + int(4 * fps)])
        t_delta = (1 - float(np.dot(pre_t, post_t))
                   if pre_t is not None and post_t is not None else 0.0)

        p_deltas = []
        for pr in protected:
            s = em.region_signal(idxs[::2], get, app.get, dino, pr)
            a = em.centroid([e for i, e in s.items() if i < edit_frame])
            b = em.centroid([e for i, e in s.items()
                             if i > edit_frame + int(4 * fps)])
            if a is not None and b is not None:
                p_deltas.append(1 - float(np.dot(a, b)))

        commit = (em.commit_latency_s(sig_t, edit_frame, fps, pre_t)
                  if pre_t is not None else None)
        is_char = meta["edit_id"].startswith("character")
        ref_path = (os.path.join(REFS, meta["ref"]) if meta.get("ref") else None)

        out = {
            "name": name, "product": meta["product"], "edit_id": meta["edit_id"],
            "clip": meta["clip"], "kind": meta["kind"], "fps": fps,
            "edit_frame": edit_frame, "frames": n,
            "target_region": target, "target_delta": round(t_delta, 3),
            "commit_latency_s": commit,
            "collateral_index": em.collateral_index(t_delta, p_deltas),
            "residue_index": em.residue_index(sig_t, edit_frame, fps, pre_t, commit),
            "transition": em.transition_cost(get, edit_frame, fps, n),
            "stability": em.commit_stability(sig_t, edit_frame, fps, pre_t, commit),
            "motion_continuity_break": em.motion_continuity_break(
                flow, get, edit_frame, fps, commit),
            "identity": em.identity_outcomes(app.get, face_embed, get,
                                             edit_frame, fps, n, is_char,
                                             ref_path),
        }
        with open(outp, "w") as f:
            json.dump(out, f, indent=2)
        print("%s: commit=%s collat=%s residue=%s hold=%s"
              % (name, out["commit_latency_s"], out["collateral_index"],
                 out["residue_index"], out["stability"]["hold"]))
    print("done ->", OUTD)
    return 0


if __name__ == "__main__":
    sys.exit(main())
