#!/usr/bin/env python3
"""Unattended overnight recalibration from a PINNED vantage.

Prior floor data was contaminated by mid-run VPN tunnel switching (discovered
2026-08-10 evening; quarantined in data/stale-vantage/). This runner rebuilds
everything from one vantage, and this time the vantage is MONITORED:

  - Preflight refuses to start unless TURN UDP passes (no media = wasted night)
  - Baseline RTT probed before and after every arm; drift > DRIFT_TOLERANCE_MS
    taints the arm (recorded, not silently kept)
  - TURN reachability re-checked between arms; loss of UDP aborts the rest
    rather than producing another contaminated dataset

Sequence (all echo = free; captures = a few dollars):
  1. C0 standard      N=40
  2. C0 minimal-rig   N=40      (rig decomposition, properly powered this time)
  3. C1 / C2 / C3     N=30 each (full platform degradation curve, shaped+verified)
  4. Generation pilot captures  (6 short GPU sessions)
  5. floor_analysis + summary

Run under caffeinate so macOS cannot sleep mid-night:
    caffeinate -is .venv/bin/python tools/overnight_calibration.py
"""
import json
import os
import socket
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rtveval.orchestrator import netshape  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(REPO, ".venv", "bin", "python")
DATA = os.path.join(REPO, "data")
LOG = os.path.join(DATA, "overnight-summary.json")

TURN_HOST = "turn.us-east-1.aws.prod.reactor.inc"
DRIFT_TOLERANCE_MS = 40.0


def turn_udp_ok() -> bool:
    try:
        ip = socket.gethostbyname(TURN_HOST)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(4)
        s.sendto(b'\x00\x01\x00\x00!\x12\xa4B' + b'\x00' * 12, (ip, 3478))
        s.recvfrom(1024)
        return True
    except Exception:
        return False


def vantage() -> dict:
    rtt = netshape.probe_rtt_ms()
    return {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "baseline_rtt_ms": rtt, "turn_udp": turn_udp_ok()}


def run_arm(label, argv, summary):
    """One calibration arm with vantage bracketing."""
    before = vantage()
    print("\n=== %s ===\n    vantage before: rtt=%s turn_udp=%s"
          % (label, before["baseline_rtt_ms"], before["turn_udp"]))
    if not before["turn_udp"]:
        summary["arms"].append({"label": label, "skipped": "TURN UDP lost"})
        return False
    t0 = time.monotonic()
    rc = subprocess.run(argv).returncode
    after = vantage()
    drift = None
    if before["baseline_rtt_ms"] and after["baseline_rtt_ms"]:
        drift = abs(after["baseline_rtt_ms"] - before["baseline_rtt_ms"])
    tainted = bool(drift and drift > DRIFT_TOLERANCE_MS) or not after["turn_udp"]
    summary["arms"].append({
        "label": label, "rc": rc, "minutes": round((time.monotonic() - t0) / 60, 1),
        "vantage_before": before, "vantage_after": after,
        "rtt_drift_ms": round(drift, 1) if drift is not None else None,
        "VANTAGE_TAINTED": tainted,
    })
    _save(summary)
    if tainted:
        print("    !! VANTAGE DRIFT/LOSS during %s - arm marked tainted" % label)
    return rc == 0 and not tainted


def shaped_arm(cond, n, summary):
    """Arm a verified condition, run the calibration under it, always clear."""
    shaper = netshape.DummynetShaper()
    base = netshape.probe_rtt_ms()
    if base is None:
        summary["arms"].append({"label": "floor-%s" % cond.condition_id,
                                "skipped": "no baseline RTT"})
        return
    try:
        shaper.apply(cond)
        state = netshape.verify(cond, base, shaper)
        if not state.verified:
            summary["arms"].append({"label": "floor-%s" % cond.condition_id,
                                    "skipped": "shaping unverified: " + state.detail})
            return
        run_arm("floor-%s" % cond.condition_id,
                [PY, os.path.join(REPO, "tools", "echo_calibration.py"),
                 "--runs", str(n), "--condition", cond.condition_id], summary)
    finally:
        shaper.clear()
        time.sleep(2)


def _save(summary):
    with open(LOG, "w") as f:
        json.dump(summary, f, indent=2)


def main() -> int:
    summary = {"started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "purpose": ("full recalibration from pinned vantage after "
                           "tunnel-switch contamination"), "arms": []}

    pre = vantage()
    print("preflight: rtt=%s ms, TURN UDP=%s" % (pre["baseline_rtt_ms"], pre["turn_udp"]))
    if not pre["turn_udp"]:
        print("REFUSING TO START: TURN UDP blocked - fix the tunnel first, or "
              "the whole night is wasted.", file=sys.stderr)
        return 1
    summary["preflight"] = pre
    _save(summary)

    ec = os.path.join(REPO, "tools", "echo_calibration.py")
    run_arm("floor-C0", [PY, ec, "--runs", "40"], summary)
    run_arm("floor-C0-minimal", [PY, ec, "--runs", "40", "--profile", "minimal"],
            summary)
    for cond, n in ((netshape.C1, 30), (netshape.C2, 30), (netshape.C3, 30)):
        shaped_arm(cond, n, summary)

    run_arm("generation-pilot",
            [PY, os.path.join(REPO, "tools", "generation_pilot.py"),
             "--seconds", "12"], summary)

    subprocess.run([PY, os.path.join(REPO, "tools", "floor_analysis.py")])
    summary["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _save(summary)
    print("\nOVERNIGHT COMPLETE -> %s" % LOG)
    tainted = [a["label"] for a in summary["arms"] if a.get("VANTAGE_TAINTED")]
    if tainted:
        print("tainted arms (vantage drift): %s - rerun these" % ", ".join(tainted))
    return 0


if __name__ == "__main__":
    sys.exit(main())
