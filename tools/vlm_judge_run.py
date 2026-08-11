#!/usr/bin/env python3
"""Batch VLM-judge run over captures.

    .venv/bin/python tools/vlm_judge_run.py data/pilot-captures --category generation
    .venv/bin/python tools/vlm_judge_run.py data/pilot-captures --dry-run

Reads every .mkv with a sibling .json (capture metadata), samples 8 frames,
builds a blinded plan with hidden repeats, judges each item, and writes:
  data/vlm-judge/records.jsonl      (blind ids only)
  data/vlm-judge-key/key.json       (blind id -> item; OUTSIDE the records dir)
  data/vlm-judge/consistency.json   (hidden-repeat gate result)

Needs ANTHROPIC_API_KEY in the environment or .env. Auxiliary evidence only:
these scores never enter a ranking until validated against the human panel
(rtveval.vlm_judge.validate_against_humans).
"""
import argparse
import glob
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_env():
    envp = os.path.join(REPO, ".env")
    if os.path.exists(envp):
        for line in open(envp):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v)


def extract_frames_jpeg(path, k=8, max_side=768):
    """k evenly-spaced frames as JPEG bytes, via PyAV (no decord)."""
    import av
    import numpy as np
    from PIL import Image
    from rtveval.vlm_judge import sample_frame_indices

    frames = []
    with av.open(path) as c:
        stream = c.streams.video[0]
        for f in c.decode(stream):
            frames.append(f.to_ndarray(format="rgb24"))
    idx = sample_frame_indices(len(frames), k)
    out = []
    for i in idx:
        img = Image.fromarray(frames[i])
        if max(img.size) > max_side:
            img.thumbnail((max_side, max_side))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        out.append(buf.getvalue())
    return out, len(frames)


def windowed_audit(judge, path, n_windows, frames_per_window, total_secs):
    """Audit each time window separately -> first_artifact_window/second.

    The post-edit failure mode: the change looks right at first, then decays.
    A whole-clip audit says WHAT went wrong; the windowed audit says WHEN it
    started."""
    import av
    from rtveval.vlm_judge import sample_frame_indices
    import io as _io
    from PIL import Image

    all_frames = []
    with av.open(path) as c:
        for f in c.decode(c.streams.video[0]):
            all_frames.append(f.to_ndarray(format="rgb24"))
    n = len(all_frames)
    per = n // n_windows
    windows = []
    onset = None
    for w in range(n_windows):
        seg = all_frames[w * per:(w + 1) * per] or all_frames[-per:]
        idx = sample_frame_indices(len(seg), frames_per_window)
        jpgs = []
        for i in idx:
            img = Image.fromarray(seg[i])
            if max(img.size) > 768:
                img.thumbnail((768, 768))
            buf = _io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            jpgs.append(buf.getvalue())
        r = judge.audit(jpgs, total_secs / n_windows)
        worst = max([f["severity"] for f in r["findings"]], default=0)
        windows.append({"window": w, "t0_s": round(w * total_secs / n_windows, 1),
                        "findings": r["findings"], "clean": r["clean"],
                        "worst_severity": worst})
        if onset is None and worst >= 2:
            onset = round(w * total_secs / n_windows, 1)
    return {"windows": windows,
            "first_artifact_s": onset,   # None = clean throughout (censored)
            "clean": all(w["clean"] for w in windows),
            "findings": [f for w in windows for f in w["findings"]],
            "notes": "windowed audit x%d" % n_windows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("capture_dir")
    ap.add_argument("--category", default="generation",
                    choices=["generation", "v2v"])
    ap.add_argument("--frames", type=int, default=8)
    ap.add_argument("--seed", type=int, default=20260811)
    ap.add_argument("--dry-run", action="store_true",
                    help="build + print the plan, no API calls")
    ap.add_argument("--audit", action="store_true",
                    help="artifact-audit mode: taxonomy-constrained anomaly "
                         "findings instead of rubric scores")
    ap.add_argument("--windows", type=int, default=1,
                    help="audit mode: split the clip into N time windows and "
                         "audit each separately - yields artifact ONSET time "
                         "(errors mostly appear a while AFTER a live edit, "
                         "not at the moment of change)")
    args = ap.parse_args()
    load_env()

    from rtveval.vlm_judge import (DIMENSION_SETS, ClaudeJudge, JudgeItem,
                                   build_plan, journal_line)

    items = []
    for mkv in sorted(glob.glob(os.path.join(args.capture_dir, "*.mkv"))):
        metap = mkv.replace(".mkv", ".json")
        if not os.path.exists(metap):
            continue
        meta = json.load(open(metap))
        if not meta.get("frames"):
            continue
        items.append(JudgeItem(
            product_key=meta.get("product", "unknown"),
            run_id=os.path.basename(mkv), capture_path=mkv,
            category=args.category, prompt_text=meta.get("prompt")))
    if not items:
        print("no judgeable captures (need .mkv + .json with frames>0)")
        return 1

    secret = os.urandom(16)
    plan = build_plan(items, secret, seed=args.seed)
    dims = DIMENSION_SETS[args.category]
    print("%d items -> %d judgments (%d hidden repeats)"
          % (len(items), len(plan), sum(p.is_hidden_repeat for p in plan)))
    if args.dry_run:
        for p in plan:
            print("  %s repeat=%s" % (p.blind_id, p.is_hidden_repeat))
        return 0

    outdir = os.path.join(REPO, "data", "vlm-judge-audit" if args.audit else "vlm-judge")
    keydir = os.path.join(REPO, "data", "vlm-judge-key")
    os.makedirs(outdir, exist_ok=True)
    os.makedirs(keydir, exist_ok=True)
    with open(os.path.join(keydir, "key.json"), "w") as f:
        json.dump({p.blind_id: {"item": items[p.item_index]._asdict(),
                                "is_hidden_repeat": p.is_hidden_repeat}
                   for p in plan}, f, indent=2)

    judge = ClaudeJudge()
    n_ok = 0
    with open(os.path.join(outdir, "records.jsonl"), "a") as journal:
        for p in plan:
            item = items[p.item_index]
            frames, total = extract_frames_jpeg(item.capture_path, args.frames)
            secs = json.load(open(item.capture_path.replace(".mkv", ".json"))
                             ).get("wall_s", total / 16.0)
            try:
                if args.audit and args.windows > 1:
                    result = windowed_audit(judge, item.capture_path,
                                            args.windows, args.frames,
                                            float(secs))
                elif args.audit:
                    result = judge.audit(frames, float(secs))
                else:
                    result = judge.judge(frames, dims, float(secs), item.prompt_text)
            except Exception as e:
                print("  %s FAILED: %s" % (p.blind_id, str(e)[:120]))
                continue
            journal.write(journal_line(p, result) + "\n")
            n_ok += 1
            if args.audit:
                fs = ["%s(sev%d)" % (f["type"], f["severity"])
                      for f in result["findings"]]
                onset = result.get("first_artifact_s")
                print("  %s -> %s%s" % (p.blind_id,
                      "CLEAN" if result["clean"] else ", ".join(fs[:6]),
                      "" if onset is None else "  [first artifact at %.0fs]" % onset))
            else:
                scores = {d: v["score"] if v["assessable"] else None
                          for d, v in result["dimensions"].items()}
                print("  %s -> %s breakdown=%s" % (p.blind_id, scores,
                                                   result["breakdown_observed"]))
    print("%d/%d judgments recorded -> %s" % (n_ok, len(plan), outdir))
    return 0 if n_ok else 1


if __name__ == "__main__":
    sys.exit(main())
