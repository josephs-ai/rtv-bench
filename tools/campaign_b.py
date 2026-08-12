#!/usr/bin/env python3
"""Campaign B - reliability, V2V products, condition C0 (clean network).

    .venv/bin/python tools/campaign_b.py --rounds 300          # the real run
    .venv/bin/python tools/campaign_b.py --rounds 2 --smoke    # plumbing test

Products tonight: lucy-2.5 (Lens P, Decart) and xmax-x2.0 via Reactor
(Lens M). Duration mix per plan sec 2.5: 80% 15s / 15% 60s / 5% full-reel
(185s; the 10-min soak is capped by reel length - recorded as such).

Structure guarantees (all existing, tested machinery):
  - round-based queue, journaled, resumable; balanced N under truncation
  - spend reservation before every launch; hard cap aborts the campaign
  - vantage drift guard per slot -> E on positive evidence, never mislabeled
  - retry only on E; F/T/R are the measurement
"""
import argparse
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, "data")
OUT = os.path.join(DATA, "campaign-b")

PROMPT = "oil painting style, thick impasto brush strokes, warm palette"
REEL_DUR = 184.6


def load_env():
    for line in open(os.path.join(REPO, ".env")):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)


def duration_for(round_index: int) -> float:
    """Deterministic 80/15/5 mix, identical for every product."""
    m = round_index % 20
    if m < 16:
        return 15.0
    if m < 19:
        return 60.0
    return REEL_DUR  # full-reel "soak" (10-min soak capped by reel length)


def make_adapter(product_key: str):
    from rtveval.adapters.base import DurationSemantics
    if product_key == "lucy-2.5":
        from rtveval.adapters.decart_webrtc import DecartWebRTCAdapter
        return DecartWebRTCAdapter()
    from rtveval.adapters.reactor_webrtc import ReactorWebRTCAdapter
    return ReactorWebRTCAdapter("xmax-x2.0", "xmax/x2",
                                DurationSemantics.FIXED,
                                prompt_command="set_prompt",
                                first_frame_timeout_s=60.0)


CLIPS = {
    "lucy-2.5": os.path.join(DATA, "reel", "input-lucy-2.5.mp4"),
    "xmax-x2.0": os.path.join(DATA, "reel", "input-xmax-x2.0.mp4"),
}
USD_PER_S = {"lucy-2.5": 0.004, "xmax-x2.0": 0.004}   # reservation estimates; the cap is the guard


def upload_mbps():
    """Sustained-upstream probe: 1.5MB real upload through the tunnel."""
    import subprocess
    probe = "/tmp/tp-probe.bin"
    if not os.path.exists(probe):
        with open(probe, "wb") as f:
            f.write(os.urandom(1_500_000))
    r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{speed_upload}",
                        "--max-time", "25", "-X", "POST", "--data-binary",
                        "@" + probe, "https://speed.cloudflare.com/__up"],
                       capture_output=True, text=True)
    try:
        return float(r.stdout) * 8 / 1e6
    except ValueError:
        return 0.0


async def ensure_throughput(min_mbps=2.5, out_dir=None):
    """HOLD the campaign during tunnel-sag windows instead of burning slots
    into them (night-1 lesson: snapshots of RTT/loss cannot see sustained
    sag; 10 runs were adjudicated out after the fact - this is the
    before-the-fact version)."""
    import time as _t
    held = 0
    while True:
        mbps = await asyncio.get_event_loop().run_in_executor(None, upload_mbps)
        if out_dir:
            with open(os.path.join(out_dir, "throughput.jsonl"), "a") as f:
                f.write(json.dumps({"utc": _t.strftime("%Y-%m-%dT%H:%M:%SZ",
                        _t.gmtime()), "mbps": round(mbps, 2),
                        "held_min": held * 2}) + "\n")
        if mbps >= min_mbps:
            if held:
                print("  [sentinel] recovered: %.1f Mbps after %d min hold"
                      % (mbps, held * 2))
            return mbps
        held += 1
        print("  [sentinel] HOLD: upstream %.1f Mbps < %.1f needed - waiting "
              "2 min (total held %d min)" % (mbps, min_mbps, held * 2))
        await asyncio.sleep(120)


def udp_loss_check():
    """Tunnel loss burst: >12% loss is rig evidence (E), not product data."""
    import socket, struct, time as _t
    from rtveval.orchestrator.health import CheckResult
    try:
        ip = socket.gethostbyname("stun.cloudflare.com")
        sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sk.setblocking(False)
        for _ in range(20):
            try:
                sk.sendto(struct.pack("!HHI12s", 1, 0, 0x2112A442,
                                      os.urandom(12)), (ip, 3478))
            except OSError:
                pass
            _t.sleep(0.02)
        ok = 0
        deadline = _t.time() + 1.2
        while _t.time() < deadline and ok < 20:
            try:
                sk.recvfrom(1024); ok += 1
            except BlockingIOError:
                _t.sleep(0.02)
        sk.close()
        loss = 1 - ok / 20
        return CheckResult("udp_loss", loss <= 0.12,
                           "burst loss %d%%" % round(loss * 100),
                           _t.monotonic(), "")
    except Exception as e:
        from rtveval.orchestrator.health import CheckResult
        return CheckResult("udp_loss", False, "probe error %s" % e, 0.0, "")


async def run_product_slot(spec, journal, spend, baseline_rtt, args):
    from rtveval.orchestrator import health, runner

    def preflight():
        checks = [health.vantage_drift_check(baseline_rtt), udp_loss_check()]
        return health.RigEvidence(checks=checks)

    adapter = make_adapter(spec.product_key)
    dur = duration_for(spec.round_index)
    return await runner.execute_slot(
        spec, adapter, journal, spend,
        usd_per_second=USD_PER_S[spec.product_key],
        wall_clock_kill_s=dur + 120.0,
        preflight=preflight, postflight=preflight,
        prompt=PROMPT, clip_path=CLIPS[spec.product_key],
        duration_intended_s=dur)


async def main_async(args):
    from rtveval.orchestrator.netshape import probe_rtt_ms
    from rtveval.orchestrator.queue import RoundQueue, build_rounds
    from rtveval.orchestrator.runner import RunJournal, tally
    from rtveval.orchestrator.spend import CapExceeded, SpendCap

    os.makedirs(OUT, exist_ok=True)
    products = ["lucy-2.5", "xmax-x2.0"]
    for p in products:
        if not os.path.exists(CLIPS[p]):
            print("missing conform input for %s: %s" % (p, CLIPS[p]))
            return 1

    baseline = None
    for _ in range(4):
        baseline = probe_rtt_ms()
        if baseline is not None:
            break
        await asyncio.sleep(5)
    if baseline is None:
        print("no network baseline - refusing to start")
        return 1
    print("vantage baseline RTT %.0f ms (recorded; drift -> E)" % baseline)
    json.dump({"baseline_rtt_ms": baseline, "utc": time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "vpn_exit": "singapore-pinned",
        "condition": "C0"},
        open(os.path.join(OUT, "vantage.json"), "w"), indent=2)

    rounds = build_rounds("B", products, "C0", n_rounds=args.rounds)
    q = RoundQueue(rounds, os.path.join(OUT, "queue-journal.jsonl"))
    journal = RunJournal(os.path.join(OUT, "runs.jsonl"))
    spend = SpendCap(args.cap_usd, os.path.join(OUT, "spend.jsonl"))

    # group pending specs by round; lanes run products of a round in parallel
    pending = list(q.pending())
    print("%d slots pending (resume-aware)" % len(pending))
    by_round = {}
    for spec in pending:
        by_round.setdefault(spec.round_index, []).append(spec)

    done = 0
    t0 = time.monotonic()
    for r in sorted(by_round):
        specs = by_round[r]
        await ensure_throughput(out_dir=OUT)
        # SERIAL lanes: two simultaneous 720p upstreams starve each other
        # through the single VPN tunnel (smoke r000: Lucy first-frame starved
        # while Xmax ran). Reliability must not measure our own uplink.
        results = []
        try:
            for spec in specs:
                results.append(await run_product_slot(
                    spec, journal, spend, baseline, args))
        except CapExceeded as e:
            print("SPEND CAP: %s - stopping cleanly at round boundary" % e)
            break
        for s, rows in zip(specs, results):
            q.mark_done(s.run_id)
            done += 1
            last = rows[-1]
            print("[r%03d] %-10s %s %s ttff=%s (%d/%d, %.1f min elapsed)"
                  % (r, s.product_key, last.outcome,
                     ",".join(last.outcome_reasons)[:40] or "-",
                     getattr(last, "ttff_ms", None), done, len(pending),
                     (time.monotonic() - t0) / 60))
        if args.smoke and r >= min(by_round) + args.rounds - 1:
            break

    rows = journal.load()
    for p in products:
        prows = [x for x in rows if x.product_key == p]
        print(p, tally(prows))
    print("journals -> %s" % OUT)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=300)
    ap.add_argument("--cap-usd", type=float, default=60.0)
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    load_env()
    os.environ.setdefault("RTVEVAL_FORCE_TURN_TCP", "1")
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
