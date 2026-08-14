#!/usr/bin/env python3
"""Campaign D edit-judge: the 5 edit dimensions, blinded, frame-anchored.

    .venv/bin/python tools/edit_judge_run.py data/campaign-d/captures

Per capture: BEFORE (3 frames), TRANSITION (4 frames around the commit
window), AFTER (5 frames) + the instruction text. Output schema:
  application  full | partial | none
  residue      0-3   (0 none ... 3 old appearance clearly persists)
  collateral   0-3   (0 surgical ... 3 untargeted content visibly broken)
  transition   0-3   (0 clean ... 3 stream visibly breaks during switch)
  stability    holds | oscillates | reverts
Records -> data/edit-judge/records.jsonl (resumable by capture name).
"""
import argparse
import glob
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTD = os.path.join(REPO, "data", "edit-judge")

from tools.vlm_judge_run import load_env

SCHEMA = {
    "type": "object",
    "properties": {
        "application": {"type": "string", "enum": ["full", "partial", "none"]},
        # API's json_schema subset rejects integer min/max - enum instead
        "residue": {"type": "integer", "enum": [0, 1, 2, 3]},
        "collateral": {"type": "integer", "enum": [0, 1, 2, 3]},
        "transition": {"type": "integer", "enum": [0, 1, 2, 3]},
        "stability": {"type": "string",
                      "enum": ["holds", "oscillates", "reverts"]},
        "evidence": {"type": "string"},
    },
    "required": ["application", "residue", "collateral", "transition",
                 "stability", "evidence"],
    "additionalProperties": False,
}

PROMPT = """You are auditing a LIVE mid-stream edit of a realtime video model.
While the video streamed, this instruction was sent at a known instant:

INSTRUCTION: {instruction}

You see three labeled groups of frames from the SAME continuous stream:
BEFORE (pre-instruction), TRANSITION (the seconds right after the
instruction), AFTER (settled, several seconds later).

Judge ONLY these five things:
- application: did the instructed change fully apply by the AFTER group?
- residue (0-3): does the OLD appearance persist anywhere it should have
  been replaced (ghosting, half-switched subject, old garment bleeding
  through)?
- collateral (0-3): did things the instruction did NOT mention visibly
  change or break (background warps on a garment edit, face identity
  changes on a clothing edit, scene damage around the subject)?
- transition (0-3): visible breakage DURING the switch - tearing, blocky
  glitches, freezes, flicker storm.
- stability: across TRANSITION -> AFTER, does the edit hold, oscillate,
  or revert toward the old appearance?
Cite frame labels in your evidence. Judge only what is visible."""


def sample_groups(mkv, edit_frame, fps):
    import av
    from PIL import Image
    frames = []
    with av.open(mkv) as c:
        for f in c.decode(c.streams.video[0]):
            frames.append(f.to_ndarray(format="rgb24"))
    n = len(frames)

    def jpg(i):
        img = Image.fromarray(frames[max(0, min(n - 1, i))])
        if max(img.size) > 768:
            img.thumbnail((768, 768))
        b = io.BytesIO()
        img.save(b, format="JPEG", quality=85)
        return b.getvalue()

    w = int(5 * fps)
    before = [jpg(i) for i in [max(0, edit_frame - w),
                               max(0, edit_frame - w // 2),
                               max(0, edit_frame - int(fps))]]
    trans = [jpg(edit_frame + int(k * fps)) for k in (0.5, 1.5, 2.5, 4)]
    lo = edit_frame + int(6 * fps)
    hi = n - 1
    after = [jpg(int(lo + (hi - lo) * k / 4)) for k in range(5)]
    return before, trans, after, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("capture_dir")
    args = ap.parse_args()
    load_env()

    import anthropic
    client = anthropic.Anthropic()
    os.makedirs(OUTD, exist_ok=True)
    recp = os.path.join(OUTD, "records.jsonl")
    done = set()
    if os.path.exists(recp):
        for line in open(recp):
            done.add(json.loads(line)["name"])

    n_new = 0
    for metap in sorted(glob.glob(os.path.join(args.capture_dir, "D-*.json"))):
        meta = json.load(open(metap))
        name = os.path.splitext(os.path.basename(metap))[0]
        mkv = metap.replace(".json", ".mkv")
        if name in done or not os.path.exists(mkv):
            continue
        fps = float(meta.get("fps") or 15.0)
        if meta.get("edit_sent_frame") is not None:
            ef = int(meta["edit_sent_frame"])
        elif meta.get("edit_at_s_from_streamup") is not None:
            fps = float(meta.get("fps") or 30.0)
            ef = int(((meta.get("ttff_s") or 0.0)
                      + meta["edit_at_s_from_streamup"]) * fps)
        else:
            continue
        try:
            before, trans, after, n = sample_groups(mkv, ef, fps)
        except Exception as e:
            print(name, "sample failed:", str(e)[:80])
            continue
        if n < ef + int(6 * fps):
            print(name, "too short, skipped")
            continue

        content = []
        for label, group in (("BEFORE", before), ("TRANSITION", trans),
                             ("AFTER", after)):
            for k, j in enumerate(group):
                content.append({"type": "text",
                                "text": "%s frame %d:" % (label, k + 1)})
                import base64
                content.append({"type": "image", "source": {
                    "type": "base64", "media_type": "image/jpeg",
                    "data": base64.standard_b64encode(j).decode()}})
        content.append({"type": "text",
                        "text": PROMPT.format(instruction=meta["instruction"])})
        try:
            resp = client.messages.create(
                model="claude-opus-5", max_tokens=8000,
                output_config={"format": {"type": "json_schema",
                                          "schema": SCHEMA}},
                messages=[{"role": "user", "content": content}])
            v = json.loads("".join(b.text for b in resp.content
                                   if b.type == "text"))
        except Exception as e:
            print(name, "judge failed:", str(e)[:100])
            continue
        rec = {"name": name, "product": meta["product"],
               "edit_id": meta["edit_id"], "clip": meta["clip"],
               "kind": meta["kind"], "verdict": v}
        with open(recp, "a") as f:
            f.write(json.dumps(rec) + "\n")
        n_new += 1
        print("%s: %s residue=%d collat=%d trans=%d %s"
              % (name, v["application"], v["residue"], v["collateral"],
                 v["transition"], v["stability"]))
    print("%d new edit judgments -> %s" % (n_new, recp))
    return 0


if __name__ == "__main__":
    sys.exit(main())
