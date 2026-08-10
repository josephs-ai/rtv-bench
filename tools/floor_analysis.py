#!/usr/bin/env python3
"""Consolidate the platform-floor evidence: CIs, substrate reliability,
rig decomposition. Reads data/platform-floor-*.json (written by
echo_calibration.py), writes data/platform-floor-analysis.json.

Three questions, answered with uncertainty attached:

1. What is the floor, with its own CI? Run-level (cluster) bootstrap, because
   the per-run p50 spread (1194-1961 ms observed) makes a per-sample CI a lie.
2. What does the substrate fail at, on a zero-inference model? Early-death
   echo runs are a reliability floor under every Lens M product: a product at
   8% is only (8% - substrate%) attributable to the model, and only claimable
   when the intervals separate.
3. How much of the floor is OUR rig? standard vs minimal profile comparison.

Usage:
    .venv/bin/python tools/floor_analysis.py
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rtveval import stats  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, "data")

CONFIDENCE_FLOOR = 0.3  # lag samples below this were low-trust extractions


def load_floors():
    docs = {}
    for path in sorted(glob.glob(os.path.join(DATA, "platform-floor-*.json"))):
        name = os.path.basename(path)[len("platform-floor-"):-len(".json")]
        if name == "analysis":
            continue
        with open(path) as f:
            docs[name] = json.load(f)
    return docs


def account_exhausted(r):
    """402 credits_depleted is OUR account, not the product: E-class,
    excluded from every denominator (same logic as rig evidence)."""
    return "credits_depleted" in (r.get("error") or "")


def run_clusters(doc):
    """Per-run lists of trusted lag samples."""
    out = []
    for r in doc.get("runs", []):
        if account_exhausted(r):
            continue
        lags = [l for l, c in zip(r.get("lag_samples_ms", []),
                                  r.get("lag_confidences", []))
                if c >= CONFIDENCE_FLOOR]
        out.append(lags)
    return out


def substrate_reliability(doc):
    """Early-death rate on the zero-inference model, with Wilson CI.

    An echo run 'died early' if it stalled with under half the expected
    frames - the observed failure shape (35 and 141 of ~575)."""
    runs = [r for r in doc.get("runs", []) if not account_exhausted(r)]
    excluded_402 = len(doc.get("runs", [])) - len(runs)
    if not runs:
        return {"early_deaths": 0, "n_runs": 0, "excluded_credits_depleted": excluded_402,
                "meaning": "no billable attempts - arm did not run"}
    expected = max((r.get("n_frames", 0) for r in runs), default=0)
    deaths = sum(1 for r in runs
                 if r.get("n_frames", 0) < expected * 0.5
                 or r.get("stop_reason") == "exception")
    n = len(runs)
    rate = stats.wilson(deaths, n)
    return {
        "early_deaths": deaths, "n_runs": n,
        "excluded_credits_depleted": excluded_402,
        "rate_pct": round(rate.point * 100, 1),
        "wilson_ci_pct": [round(rate.lo * 100, 1), round(rate.hi * 100, 1)],
        "meaning": ("substrate failure floor under every Lens M product's "
                    "reliability figure: a product's own contribution is only "
                    "claimable where its interval separates from this one"),
        "attribution_caveat": (
            "NOT yet attributable to the platform: the death signature "
            "(~1-2s of output then stall) matches the rig-side send "
            "starvation bug found on the Decart path (slow VP8 encode). "
            "The minimal-rig profile comparison discriminates: near-zero "
            "early deaths there implicates rig load; ~equal rate implicates "
            "the substrate. Until then this is a rig+substrate combined rate."),
    }


def main() -> int:
    docs = load_floors()
    if not docs:
        print("no platform-floor-*.json found - run tools/echo_calibration.py first",
              file=sys.stderr)
        return 1

    analysis = {"confidence_floor": CONFIDENCE_FLOOR, "conditions": {}}

    for name, doc in docs.items():
        clusters = run_clusters(doc)
        entry = {"n_runs": len(clusters)}
        try:
            p50 = stats.cluster_bootstrap_floor(clusters, "p50")
            p95 = stats.cluster_bootstrap_floor(clusters, "p95")
            entry["floor_p50_ms"] = {"point": round(p50.point_ms, 1),
                                     "ci95": [round(p50.lo_ms, 1), round(p50.hi_ms, 1)],
                                     "ci_width": round(p50.width_ms, 1)}
            entry["floor_p95_ms"] = {"point": round(p95.point_ms, 1),
                                     "ci95": [round(p95.lo_ms, 1), round(p95.hi_ms, 1)]}
            # What model-side difference can this floor resolve? Anything
            # smaller than the CI width disappears into platform variance.
            entry["min_resolvable_model_difference_ms"] = round(p50.width_ms, 1)
        except ValueError as e:
            entry["error"] = str(e)
        entry["substrate_reliability"] = substrate_reliability(doc)
        entry["delivery"] = doc.get("delivery")
        analysis["conditions"][name] = entry
        print("[%s] %s" % (name, json.dumps(
            {k: v for k, v in entry.items() if k != "substrate_reliability"},
            default=str)[:220]))
        sr = entry.get("substrate_reliability") or {}
        if "rate_pct" in sr:
            print("      substrate failures: %d/%d = %.1f%% (CI %s-%s%%)%s"
                  % (sr["early_deaths"], sr["n_runs"], sr["rate_pct"],
                     sr["wilson_ci_pct"][0], sr["wilson_ci_pct"][1],
                     " [+%d runs excluded: credits_depleted]"
                     % sr["excluded_credits_depleted"]
                     if sr.get("excluded_credits_depleted") else ""))
        elif sr:
            print("      %s" % sr.get("meaning", ""))

    # Rig decomposition: standard vs minimal at the same condition.
    for name in list(analysis["conditions"]):
        minimal = analysis["conditions"].get(name + "-minimal")
        std = analysis["conditions"].get(name)
        if minimal and std and "floor_p50_ms" in minimal and "floor_p50_ms" in std:
            delta = std["floor_p50_ms"]["point"] - minimal["floor_p50_ms"]["point"]
            overlap = not (std["floor_p50_ms"]["ci95"][0] > minimal["floor_p50_ms"]["ci95"][1]
                           or minimal["floor_p50_ms"]["ci95"][0] > std["floor_p50_ms"]["ci95"][1])
            analysis["rig_decomposition"] = {
                "standard_p50": std["floor_p50_ms"],
                "minimal_p50": minimal["floor_p50_ms"],
                "rig_sensitivity_ms": round(delta, 1),
                "cis_overlap": overlap,
                # Three verdicts, not two: separated CIs attribute; overlapping
                # CIs with a small point delta exonerate the rig; overlapping
                # CIs with a LARGE point delta are indeterminate - saying
                # "platform-dominated" there would overstate the data.
                "verdict": (
                    "rig-side load contributes ~%.0f ms of the floor (CIs "
                    "separated)" % delta
                    if not overlap else
                    ("indeterminate: point delta ~%.0f ms is suggestive of a "
                     "rig component but CIs overlap at this N - more minimal-"
                     "profile runs would resolve it" % delta
                     if abs(delta) > 200 else
                     "no meaningful rig contribution: the floor is platform-"
                     "dominated and every Lens M product is latency-bound by "
                     "Reactor rather than by rig or model choices")),
            }
            # Early-death attribution: the other half of the rig question.
            sr_std = std.get("substrate_reliability") or {}
            sr_min = minimal.get("substrate_reliability") or {}
            if sr_std and sr_min:
                analysis["early_death_attribution"] = {
                    "standard": "%s/%s" % (sr_std["early_deaths"], sr_std["n_runs"]),
                    "minimal": "%s/%s" % (sr_min["early_deaths"], sr_min["n_runs"]),
                    "verdict": (
                        "consistent with rig-load attribution (zero deaths at "
                        "minimal send load; signature matches the known VP8 "
                        "send-starvation bug) but NOT conclusive: intervals "
                        "overlap at these Ns. Treat the standard-profile rate "
                        "as rig+substrate combined until a larger minimal "
                        "sample separates them."
                        if sr_min["early_deaths"] == 0 else
                        "early deaths persist at minimal load - substrate-"
                        "attributed"),
                }
            print("\nrig decomposition: %s" % analysis["rig_decomposition"]["verdict"])

    out = os.path.join(DATA, "platform-floor-analysis.json")
    with open(out, "w") as f:
        json.dump(analysis, f, indent=2)
    print("\n-> %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
