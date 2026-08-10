#!/usr/bin/env python3
"""Resume the killed overnight run: the arms that are missing or tainted.

The 03:09 kill (mid floor-C3) left C0/C0-minimal/C2 clean, C1 vantage-tainted,
C3 absent, generation pilot not started. This reruns exactly those, appending
to the same summary, with the same vantage bracketing.

    RTVEVAL_FORCE_TURN_TCP=1 caffeinate -is .venv/bin/python tools/overnight_resume.py
"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rtveval.orchestrator import netshape  # noqa: E402
from tools.overnight_calibration import (LOG, PY, REPO, _save, run_arm,  # noqa: E402
                                         shaped_arm, vantage)


def main() -> int:
    summary = json.load(open(LOG))
    summary["resumed_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    summary.setdefault("notes", []).append(
        "03:09 kill mid floor-C3 left C3 shaping armed (found + cleared on "
        "resume); C3 rerun, C1 rerun (was VANTAGE_TAINTED), pilot run here")

    pre = vantage()
    print("resume preflight: rtt=%s relay=%s" % (pre["baseline_rtt_ms"], pre["turn_udp"]))
    if not pre["turn_udp"]:
        print("relay unreachable - aborting resume", file=sys.stderr)
        return 1
    _save(summary)

    shaped_arm(netshape.C3, 30, summary)
    shaped_arm(netshape.C1, 30, summary)  # redo: first attempt drift-tainted

    run_arm("generation-pilot",
            [PY, os.path.join(REPO, "tools", "generation_pilot.py"),
             "--seconds", "12"], summary)

    subprocess.run([PY, os.path.join(REPO, "tools", "floor_analysis.py")])
    summary["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _save(summary)
    print("RESUME COMPLETE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
