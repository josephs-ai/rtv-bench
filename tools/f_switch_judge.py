#!/usr/bin/env python3
"""Campaign F switch-QUALITY judge (Amendment 3 instrument).

    .venv/bin/python tools/f_switch_judge.py

The computational switch metric answers "did the new character take, how
fast" - this judges HOW WELL: the campaign-D 5-dim edit rubric
(application / residue / collateral / transition / stability) applied to
every switch-relevant campaign-F capture (F3 switch, F5 chain arms, and
the mechanism-probe captures incl. the working re-session switches).
Frame anchoring uses the recorded sent-frame where available (immune to
the Lucy wall/file trap); xmax probes anchor at apply_at_s x 30.
Records -> data/edit-judge/f-switch-records.jsonl (resumable).
"""
import base64
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from tools.edit_judge_run import PROMPT, SCHEMA, sample_groups
from tools.vlm_judge_run import load_env

OUTP = os.path.join(REPO, "data", "edit-judge", "f-switch-records.jsonl")
DEFAULT_INSTRUCTION = ("replace the person with the person from the "
                       "reference image, keeping the same pose and motion")


def switch_captures():
    """(meta_path, edit_frame, instruction) for every switch-relevant
    capture across the F arms and the mechanism probes."""
    out = []
    for metap in sorted(glob.glob(os.path.join(
            REPO, "data", "campaign-f", "captures", "*.json"))):
        meta = json.load(open(metap))
        if meta.get("arm") not in ("switch", "chain"):
            continue
        fps = float(meta.get("fps") or 30.0)
        if meta.get("apply_sent_frame") is not None:
            ef = int(meta["apply_sent_frame"])
        elif meta.get("apply_at_s") is not None:
            ef = int(float(meta["apply_at_s"]) * fps)
        else:
            continue
        out.append((metap, ef, meta.get("instruction")
                    or DEFAULT_INSTRUCTION, fps))
    for metap in sorted(glob.glob(os.path.join(
            REPO, "data", "campaign-f", "captures-probe", "*.json"))):
        meta = json.load(open(metap))
        fps = float(meta.get("fps") or 30.0)
        at = meta.get("apply_at_s") or 15.0
        # re-session probes: the switch lands after the settle; anchor the
        # transition window at apply + settle midpoint so the judge sees
        # the actual changeover, not the pre-teardown stream
        extra = 4.0 if "reconnect" in meta.get("arm", "") else 0.0
        out.append((metap, int((at + extra) * fps),
                    meta.get("instruction") or DEFAULT_INSTRUCTION, fps))
    return out


def main():
    load_env()
    import anthropic
    client = anthropic.Anthropic()
    os.makedirs(os.path.dirname(OUTP), exist_ok=True)
    done = set()
    if os.path.exists(OUTP):
        for line in open(OUTP):
            done.add(json.loads(line)["name"])
    n = 0
    for metap, ef, instruction, fps in switch_captures():
        name = os.path.splitext(os.path.basename(metap))[0]
        mkv = metap.replace(".json", ".mkv")
        if name in done or not os.path.exists(mkv):
            continue
        meta = json.load(open(metap))
        try:
            before, trans, after, total = sample_groups(mkv, ef, fps)
        except Exception as e:
            print(name, "sample failed:", str(e)[:80])
            continue
        content = []
        for label, group in (("BEFORE", before), ("TRANSITION", trans),
                             ("AFTER", after)):
            for k, j in enumerate(group):
                content.append({"type": "text",
                                "text": "%s frame %d:" % (label, k + 1)})
                content.append({"type": "image", "source": {
                    "type": "base64", "media_type": "image/jpeg",
                    "data": base64.standard_b64encode(j).decode()}})
        content.append({"type": "text",
                        "text": PROMPT.format(instruction=instruction)})
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
        rec = {"name": name, "product": meta.get("product"),
               "lens": meta.get("lens"), "arm": meta.get("arm"),
               "mechanism": meta.get("mechanism"),
               "edit_frame": ef, "verdict": v}
        with open(OUTP, "a") as f:
            f.write(json.dumps(rec) + "\n")
        n += 1
        print("%-46s %s trans=%s collat=%s %s" % (
            name, v["application"], v["transition"], v["collateral"],
            v["stability"]))
    print("\n%d new switch-quality judgments -> %s" % (n, OUTP))
    return 0


if __name__ == "__main__":
    sys.exit(main())
