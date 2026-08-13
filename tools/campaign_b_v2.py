#!/usr/bin/env python3
"""Campaign B v2 - quality stack over B's persisted captures.

    .venv/bin/python tools/campaign_b_v2.py                # pairwise judge
    .venv/bin/python tools/campaign_b_v2.py --min-frames 120

Pairs lucy vs xmax captures from the SAME round (identical reel conform +
identical prompt), samples matched frames, and runs the blinded pairwise
judge (V2V dimensions). Side assignment is a pure function of
(seed, sorted run ids) - rerunning can never flip sides silently.

Results -> data/vlm-judge-b-pairs/records.jsonl (resumable: pairs already
judged are skipped). Metrics sweep + windowed audit run separately via
metrics_sweep.py / vlm_judge_run.py --audit on the same captures dir.
"""
import argparse
import collections
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPS = os.path.join(REPO, "data", "campaign-b", "captures")
OUTD = os.path.join(REPO, "data", "vlm-judge-b-pairs")

from tools.vlm_judge_run import extract_frames_jpeg, load_env


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-frames", type=int, default=120,
                    help="both sides need at least this many frames")
    ap.add_argument("--seed", type=int, default=20260813)
    ap.add_argument("--frames", type=int, default=8)
    args = ap.parse_args()
    load_env()

    from rtveval.vlm_judge import (V2V_DIMENSIONS, ClaudeJudge,
                                   pair_side_swapped, unswap_winner)

    by_round = collections.defaultdict(dict)
    for mp in glob.glob(os.path.join(CAPS, "*.json")):
        m = json.load(open(mp))
        if m.get("frames", 0) >= args.min_frames:
            by_round[m["round_index"]][m["product"]] = m

    pairs = [(r, d["lucy-2.5"], d["xmax-x2.0"])
             for r, d in sorted(by_round.items())
             if "lucy-2.5" in d and "xmax-x2.0" in d]
    print("%d complete pairs (min %d frames)" % (len(pairs), args.min_frames))
    if not pairs:
        return 0

    os.makedirs(OUTD, exist_ok=True)
    recp = os.path.join(OUTD, "records.jsonl")
    done = set()
    if os.path.exists(recp):
        for line in open(recp):
            done.add(json.loads(line)["round_index"])

    judge = ClaudeJudge()
    n = 0
    for r, lm, xm in pairs:
        if r in done:
            continue
        fl, _ = extract_frames_jpeg(
            os.path.join(CAPS, lm["run_id"] + ".mkv"), k=args.frames)
        fx, _ = extract_frames_jpeg(
            os.path.join(CAPS, xm["run_id"] + ".mkv"), k=args.frames)
        swapped = pair_side_swapped(args.seed, lm["run_id"], xm["run_id"])
        lo_first = sorted((lm["run_id"], xm["run_id"]))[0] == lm["run_id"]
        # sorted-first is A unless swapped; map lucy/xmax onto A/B
        lucy_is_a = (lo_first != swapped)
        fa, fb = (fl, fx) if lucy_is_a else (fx, fl)
        try:
            v = judge.judge_pair(fa, fb, V2V_DIMENSIONS,
                                 lm["prompt"], xm["prompt"])
        except Exception as e:
            print("r%03d FAILED %s: %s" % (r, type(e).__name__, str(e)[:120]))
            continue
        rec = {"round_index": r, "lucy": lm["run_id"], "xmax": xm["run_id"],
               "duration_s": lm.get("duration_intended_s"),
               "lucy_is_a": lucy_is_a, "verdict_raw": v}
        # translate per-dimension winners back to product names
        named = {}
        for dim, obj in (v.get("dimensions") or {}).items():
            w = obj.get("winner")
            named[dim] = ("tie" if w == "tie" else
                          ("lucy-2.5" if (w == "A") == lucy_is_a
                           else "xmax-x2.0"))
        rec["winners_named"] = named
        with open(recp, "a") as f:
            f.write(json.dumps(rec) + "\n")
        n += 1
        print("r%03d judged (%d/%d)" % (r, n, len(pairs) - len(done)))
    print("%d new pair judgments -> %s" % (n, recp))
    return 0


if __name__ == "__main__":
    sys.exit(main())
