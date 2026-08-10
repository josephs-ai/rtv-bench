#!/usr/bin/env python3
"""Eyeball sampling: put human eyes on actual video at every stage, auditably.

The failure that survives all 66 tests is the one where every number is
internally consistent and the output is visibly wrong - a conform that
letterboxed everything, a capture that is green garbage with perfect CFR, a
blinded clip encoding at the wrong level. No code check catches "visibly
wrong"; this tool makes the human check cheap, sampled, and LOGGED, so "did
anyone actually watch the conform outputs?" has an answer in the appendix.

Usage:
    python3 tools/eyeball.py conform    captures/conform/  --n 4
    python3 tools/eyeball.py capture    captures/campaign-c/
    python3 tools/eyeball.py blinded    rating/served/

Opens a random sample (seeded by date so a re-run shows the same set), waits
for a verdict, appends to data/eyeball-log.jsonl. Stages with no log entry
show up in the pilot gate's warnings.
"""
import argparse
import json
import os
import random
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(REPO, "data", "eyeball-log.jsonl")
STAGES = ("reel", "conform", "capture", "blinded")
VIDEO_EXT = (".mp4", ".mkv", ".mov", ".webm")


def sample(directory: str, n: int, seed: str):
    files = sorted(
        os.path.join(r, f) for r, _, fs in os.walk(directory)
        for f in fs if f.lower().endswith(VIDEO_EXT))
    if not files:
        return []
    rng = random.Random(seed)
    return rng.sample(files, min(n, len(files)))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=STAGES)
    ap.add_argument("directory")
    ap.add_argument("--n", type=int, default=4)
    ap.add_argument("--seed", default=time.strftime("%Y-%m-%d"),
                    help="sampling seed (default: today, so re-runs repeat)")
    args = ap.parse_args()

    picks = sample(args.directory, args.n, "%s:%s" % (args.seed, args.stage))
    if not picks:
        print("no video files under %s" % args.directory, file=sys.stderr)
        return 1

    print("stage %r - watching %d of the clips under %s:" % (args.stage, len(picks),
                                                             args.directory))
    for p in picks:
        print("  %s" % os.path.relpath(p, REPO))
        subprocess.run(["open", p])  # QuickTime; blocks nothing

    print("\nWatch for: wrong framing/letterboxing, colour garbage, strip "
          "unreadable,\nflash missing, stutter, identity leaks (blinded stage).")
    verdict = ""
    while verdict not in ("ok", "problem"):
        verdict = input("verdict [ok/problem]: ").strip().lower()
    notes = input("notes (required if problem): ").strip()
    if verdict == "problem" and not notes:
        print("a problem with no notes is not reviewable", file=sys.stderr)
        return 1

    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps({
            "stage": args.stage, "directory": args.directory,
            "files": [os.path.relpath(p, REPO) for p in picks],
            "seed": args.seed, "verdict": verdict, "notes": notes,
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }) + "\n")
    print("logged -> %s" % os.path.relpath(LOG, REPO))
    return 0 if verdict == "ok" else 2


if __name__ == "__main__":
    sys.exit(main())
