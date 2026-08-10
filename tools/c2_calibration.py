#!/usr/bin/env python3
"""Echo platform-floor calibration under condition C2 (100 ms RTT / 1% loss).

Sequence, with teardown guaranteed even on failure:
  1. Measure the UNSHAPED baseline RTT (this is what verification compares to).
  2. Apply C2 via dummynet (dnctl/pfctl - requires the NOPASSWD grant).
  3. Verify the APPLIED state with a live probe - the schedule's intention is
     never what gets recorded (netshape rule 2).
  4. Run the standard-profile echo calibration as a subprocess.
  5. Clear all shaping in a finally block.

The C0 floor (p50 1694 ms, CI 1561-1894) against this run's numbers is the
platform floor's own degradation curve - the baseline every Lens M product's
C2 figure gets read against.

    .venv/bin/python tools/c2_calibration.py --runs 30
"""
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rtveval.orchestrator import netshape  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(REPO, ".venv", "bin", "python")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=30)
    ap.add_argument("--pause", type=float, default=2.0)
    args = ap.parse_args()

    shaper = netshape.DummynetShaper()

    print("1) unshaped baseline RTT...")
    baseline = netshape.probe_rtt_ms()
    if baseline is None:
        print("baseline probe failed - no ICMP? aborting before shaping",
              file=sys.stderr)
        return 1
    print("   baseline %.1f ms" % baseline)

    try:
        print("2) applying C2 (%d ms RTT, %.1f%% loss)..."
              % (netshape.C2.rtt_ms, netshape.C2.loss_pct))
        shaper.apply(netshape.C2)

        print("3) verifying applied state...")
        state = netshape.verify(netshape.C2, baseline, shaper)
        print("   %s" % state.detail)
        if not state.verified:
            print("SHAPING NOT IN FORCE - refusing to run a mislabelled "
                  "calibration (this is the netshape E rule)", file=sys.stderr)
            return 1

        # Applied state goes into the evidence next to the results.
        with open(os.path.join(REPO, "data", "netshape-C2-applied.json"), "w") as f:
            json.dump(state._asdict(), f, indent=2)

        print("4) running %d-run calibration under C2..." % args.runs)
        rc = subprocess.run(
            [PY, os.path.join(REPO, "tools", "echo_calibration.py"),
             "--runs", str(args.runs), "--condition", "C2",
             "--pause", str(args.pause)]).returncode
        return rc
    finally:
        print("5) clearing shaping...")
        shaper.clear()
        after = netshape.probe_rtt_ms()
        print("   post-teardown RTT: %s ms (baseline was %.1f)"
              % ("%.1f" % after if after else "?", baseline))


if __name__ == "__main__":
    sys.exit(main())
