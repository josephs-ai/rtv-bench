#!/usr/bin/env python3
"""RTV-Bench entry point - thin dispatcher over the campaign drivers.

    .venv/bin/python tools/benchmark_run.py --list
    .venv/bin/python tools/benchmark_run.py reliability
    .venv/bin/python tools/benchmark_run.py quality
    .venv/bin/python tools/benchmark_run.py editing
    .venv/bin/python tools/benchmark_run.py worlds

Each stage shells the existing journaled, resumable driver so a benchmark
run is exactly the evaluated machinery - no parallel code path to drift.
See BENCHMARK.md for ground rules; results consolidate via
benchmark_score.py.
"""
import argparse
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(REPO, ".venv", "bin", "python")
PYM = os.path.join(REPO, ".venv-metrics", "bin", "python")

STAGES = {
    "reliability": [
        [PY, "tools/campaign_b.py", "--rounds", "300", "--cap-usd", "150"],
    ],
    "quality": [
        [PYM, "tools/metrics_sweep.py", "data/campaign-b/captures"],
        [PY, "tools/campaign_b_v2.py"],
        [PY, "tools/vlm_judge_run.py", "data/campaign-b/captures-long",
         "--audit", "--windows", "4"],
    ],
    "editing": [
        [PY, "tools/campaign_d.py", "--product", "lucy-2.5"],
        [PY, "tools/campaign_d_xmax.py"],
        [PYM, "tools/edit_metrics_run.py", "data/campaign-d/captures"],
        [PY, "tools/edit_judge_run.py", "data/campaign-d/captures"],
        [PY, "tools/d_scorecard.py"],
    ],
    # CORE SUITE: the affordable reproduction run (~2h, ~$40 at current
    # provider pricing): 30-round reliability mini, 12 live-edit sessions
    # per product, metrics+judging over what it captured, scorecard.
    "core": [
        [PY, "tools/campaign_b.py", "--rounds", "15", "--cap-usd", "20"],
        [PY, "tools/campaign_d.py", "--product", "lucy-2.5", "--limit", "12"],
        [PY, "tools/campaign_d_xmax.py", "--limit", "12"],
        [PYM, "tools/metrics_sweep.py", "data/campaign-b/captures"],
        [PYM, "tools/edit_metrics_run.py", "data/campaign-d/captures"],
        [PY, "tools/campaign_b_v2.py"],
        [PY, "tools/edit_judge_run.py", "data/campaign-d/captures"],
        [PY, "tools/d_scorecard.py"],
        [PY, "tools/benchmark_score.py"],
        [PY, "tools/benchmark_report.py"],
    ],
    # Campaign F: reference-image control (anchor / hold / mid-stream
    # switch) - the core interaction of preset-character products.
    "refs": [
        [PY, "tools/campaign_f.py", "--product", "lucy-2.5"],
        [PY, "tools/campaign_f_xmax.py"],
        [PYM, "tools/campaign_f_metrics.py"],
    ],
    "score": [
        [PY, "tools/benchmark_score.py"],
        [PY, "tools/cost_report.py"],
        [PY, "tools/benchmark_report.py"],
        [PY, "tools/claims_check.py", "docs/RESULTS.md"],
        [PY, "tools/dash.py"],
    ],
    # the terminal results surface - the machine hands you the results
    "dash": [
        [PY, "tools/dash.py"],
    ],
    "rate": [
        [PY, "tools/rating_session.py"],
    ],
    "worlds": [
        [PY, "tools/campaign_c_gen.py", "--reps", "3"],
        [PY, "tools/ho_native_lane.py", "--reps", "3"],
        [PYM, "tools/metrics_sweep.py", "data/campaign-c-gen"],
        [PY, "tools/vlm_judge_run.py", "data/campaign-c-gen",
         "--category", "generation"],
        [PY, "tools/vlm_judge_run.py", "data/campaign-c-gen",
         "--audit", "--windows", "4"],
    ],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", nargs="?", choices=sorted(STAGES))
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    if args.list or not args.stage:
        for s, cmds in STAGES.items():
            print("%-12s %d steps" % (s, len(cmds)))
        return 0
    os.chdir(REPO)
    for cmd in STAGES[args.stage]:
        print(">>", " ".join(cmd))
        rc = subprocess.call(cmd)
        if rc != 0:
            print("step exited %d - stage continues (journals are the truth)"
                  % rc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
