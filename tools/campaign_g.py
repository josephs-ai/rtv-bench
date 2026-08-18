#!/usr/bin/env python3
"""Campaign G - interaction density (sustained edit cadence).

    .venv/bin/python tools/campaign_g.py --product lucy-2.5 [--smoke|--limit N]

Campaigns D/F fire one or two edits per session. Campaign G asks the
throughput question: a clip streams live and a text edit fires EVERY
10 s (wall-clock from first delivered frame) for the whole 90 s session
- edits at t=10,20,...,80. The fixed ordered edit sequence (EDITS_G)
walks garment -> background -> accessory -> style -> style-revert ->
garment -> background and loops if the session outlasts it, so every
session hits identical instructions in identical order.

What the captures answer (metrics/judge pass is downstream):
  - does edit N still commit when edit N-1 is only 10 s old?
  - does quality/identity degrade cumulatively under sustained editing?
  - do later edits silently drop (rate limiting / prompt-queue saturation)?

Wall-time scheduling, never frame counts: Lucy's delivered fps is 15-17,
not the 30 the capture label says (playbook trap). Credit exhaustion
("Insufficient credits") is an env fault - journaled as an E-class row,
never a crash of the loop.

Jobs: 2 clips x 3 reps = 6 sessions per product. Skip-if-exists by meta
path. Journal: data/campaign-g/runs.jsonl
Captures: data/campaign-g/captures/
"""
import argparse
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DDIR = os.path.join(REPO, "data", "campaign-d")
GDIR = os.path.join(REPO, "data", "campaign-g")
OUT = os.path.join(GDIR, "captures")

BASE_PROMPT = "photorealistic, natural colors"
RECORD_S = 90.0
EDIT_EVERY_S = 10.0

# Fixed ordered sequence; loops if the session needs more edits than it
# has entries (90 s => 8 edits => entry 1 fires again at t=80).
EDITS_G = [
    "the person now wears a bright red hooded sweatshirt",
    "the background is now a sunny tropical beach with ocean waves",
    "the person now wears dark aviator sunglasses",
    "everything becomes Japanese anime style, cel-shaded, vibrant",
    "everything returns to photorealistic, natural colors",
    "the person now wears a formal black business suit",
    "the background is now a neon-lit cyberpunk city street at night",
]

# close-up single / wide full-body small-face (the campaign-D conforms)
CLIPS_G = ["conform-mixkit2960.mp4", "conform-mixkit50117.mp4"]


def _short(name):
    return name.replace("conform-", "").replace(".mp4", "")


def edit_times(record_s=RECORD_S, every_s=EDIT_EVERY_S):
    """Edit fire times in wall seconds from first delivered frame:
    every 10 s for the whole session, none at t=0 or at the very end
    (90 s => 10, 20, ..., 80)."""
    n = int(record_s / every_s)
    return [every_s * (i + 1) for i in range(n)
            if every_s * (i + 1) < record_s]


def jobs_for(product):
    """(job_id, clip, record_s). 2 clips x 3 reps = 6 sessions. Rep 1
    keeps the bare job id so any existing captures are reused; later
    reps append -rN (same convention as campaign F)."""
    out = []
    for clip in CLIPS_G:
        for r in range(1, 4):
            jid = "G-%s" % _short(clip)
            out.append((jid if r == 1 else jid + "-r%d" % r, clip, RECORD_S))
    return out


def load_env():
    for line in open(os.path.join(REPO, ".env")):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)


def journal(row):
    os.makedirs(GDIR, exist_ok=True)
    with open(os.path.join(GDIR, "runs.jsonl"), "a") as f:
        f.write(json.dumps(row) + "\n")


async def lucy_session(job, name):
    from rtveval.adapters.decart_webrtc import DecartWebRTCAdapter
    from tools.generation_pilot import FFV1Writer

    job_id, clip, record_s = job
    a = DecartWebRTCAdapter()
    w = FFV1Writer(os.path.join(OUT, name + ".mkv"), fps=30.0)
    state = {"first_wall": None, "last_wall": None}
    schedule = []

    def tap(fr):
        t = time.monotonic()
        if state["first_wall"] is None:
            state["first_wall"] = t
        state["last_wall"] = t
        w.write(fr)
    a.frame_tap = tap

    await a.connect()

    async def drive_edits():
        while state["first_wall"] is None:
            await asyncio.sleep(0.2)
        for i, t_target in enumerate(edit_times(record_s)):
            instr = EDITS_G[i % len(EDITS_G)]
            await asyncio.sleep(max(0.0, t_target
                                    - (time.monotonic()
                                       - state["first_wall"])))
            row = {"t_target_s": t_target,
                   "t_sent_wall_offset_s": round(time.monotonic()
                                                 - state["first_wall"], 2),
                   "frame_at_send": w.n, "instruction": instr}
            try:
                await a.ws.send(json.dumps({"type": "prompt",
                                            "prompt": instr,
                                            "enhance_prompt": False}))
                row["ack_or_error"] = "sent"
            except Exception as e:
                row["ack_or_error"] = "%s: %s" % (type(e).__name__,
                                                  str(e)[:120])
            schedule.append(row)
            print("    edit %d/%d t=%ss frame=%d %s"
                  % (i + 1, len(edit_times(record_s)), t_target, w.n,
                     row["ack_or_error"]))

    ed = asyncio.create_task(drive_edits())
    stop = "?"
    try:
        r = await asyncio.wait_for(
            a.run(os.path.join(DDIR, clip), BASE_PROMPT, record_s, "C0"),
            timeout=record_s + 90)
        stop = r.stop_reason.value
    finally:
        ed.cancel()
        try:
            await a.close()
        except Exception:
            pass
        w.close()

    span = ((state["last_wall"] - state["first_wall"])
            if state["first_wall"] and state["last_wall"] else None)
    meta = {"campaign": "G", "product": "lucy-2.5", "lens": "P",
            "mechanism": "ws prompt (text), 10 s cadence", "job_id": job_id,
            "clip": clip, "base_prompt": BASE_PROMPT,
            "edit_every_s": EDIT_EVERY_S, "edit_schedule": schedule,
            "edits_sent": sum(1 for s in schedule
                              if s["ack_or_error"] == "sent"),
            "fps": round(w.n / span, 2) if span and span > 1 else None,
            "fps_capture_label": 30.0, "frames": w.n, "record_s": record_s,
            "stop_reason": stop,
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                           time.gmtime())}
    with open(os.path.join(OUT, name + ".json"), "w") as f:
        json.dump(meta, f, indent=2)
    journal({k: meta[k] for k in ("campaign", "product", "lens", "job_id",
                                  "clip", "edits_sent", "frames", "fps",
                                  "stop_reason", "timestamp_utc")}
            | {"run_id": name})
    return meta


async def main_async(args):
    os.makedirs(OUT, exist_ok=True)
    jobs = jobs_for(args.product)
    if args.shard:
        k, n = (int(x) for x in args.shard.split("/"))
        jobs = [j for i, j in enumerate(jobs) if i % n == k]
    if args.smoke:
        jobs = jobs[:1]
    elif args.limit:
        jobs = jobs[:args.limit]
    done = 0
    for job in jobs:
        name = "G-%s-%s" % (args.product, job[0])
        if os.path.exists(os.path.join(OUT, name + ".json")):
            print("skip (exists):", name)
            continue
        print("[%s] clip=%s record_s=%s" % (name, job[1], job[2]))
        try:
            m = await lucy_session(job, name)
            print("    frames=%s fps=%s edits_sent=%s stop=%s"
                  % (m["frames"], m["fps"], m["edits_sent"],
                     m["stop_reason"]))
            done += 1
        except Exception as e:
            err = str(e)
            # Credit exhaustion is an env fault (playbook): E-class row,
            # keep looping.
            outcome = ("E" if "insufficient credits" in err.lower()
                       else "E?")
            print("    FAILED (%s): %s %s"
                  % (outcome, type(e).__name__, err[:120]))
            journal({"campaign": "G", "product": args.product, "run_id": name,
                     "job_id": job[0], "clip": job[1], "outcome": outcome,
                     "error": err[:200],
                     "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                    time.gmtime())})
            await asyncio.sleep(10)
        await asyncio.sleep(3)
    print("%d sessions done" % done)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", default="lucy-2.5")
    ap.add_argument("--shard", default=None,
                    help="k/n - run every n-th job starting at k "
                         "(parallel lanes; Lucy only, Xmax must serialize)")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    load_env()
    os.environ.setdefault("RTVEVAL_FORCE_TURN_TCP", "1")
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
