#!/usr/bin/env python3
"""Judge calibration report - inter-rater agreement (Krippendorff alpha).

    .venv/bin/python tools/alpha_report.py

Computes, from the blinded rating journals (tools/rating_session.py) and
the VLM judge records:

  intra-rater alpha   each human vs themselves on hidden repeats
                      (attention check - a rater who disagrees with
                      themselves can't calibrate a judge)
  human-human alpha   between raters, where >= 2 raters exist
  judge-human alpha   the number the benchmark's trust gate needs
                      (BENCHMARK.md ground rule 3: judge trusted only
                      where alpha >= 0.67)

Prints an honest INSUFFICIENT DATA verdict until the rating study has
enough rows (>= 30 shared items per pair) - no alpha is fabricated from
a dry-run. Output: data/judge-calibration.json.
"""
import collections
import glob
import itertools
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIN_ITEMS = 30


def krippendorff_alpha(units):
    """units: {item: [values...]} - ordinal/interval data, simple
    interval-metric implementation (adequate for 1-5 rubric scores)."""
    vals = [v for vs in units.values() for v in vs if len(vs) >= 2]
    pairs = []
    for vs in units.values():
        if len(vs) >= 2:
            pairs += list(itertools.permutations(vs, 2))
    if not pairs:
        return None
    do = sum((a - b) ** 2 for a, b in pairs) / len(pairs)
    if len(vals) < 2:
        return None
    de_pairs = list(itertools.permutations(vals, 2))
    de = sum((a - b) ** 2 for a, b in de_pairs) / len(de_pairs)
    if de == 0:
        return 1.0
    return 1.0 - do / de


def main():
    # ---- human ratings (blind ids translated to run_ids via key files:
    # rating and judge runs blind independently, so the join is on the
    # underlying item, never on the blind name) ----
    human = collections.defaultdict(dict)   # (dim,run_id) -> {rater: [scores]}
    n_rows = 0
    raters = set()
    for jp in glob.glob(os.path.join(REPO, "data", "rating-*", "journal.jsonl")):
        if "dryrun" in jp:
            continue  # UI trial, pre-registered as non-evidence
        sess = os.path.basename(os.path.dirname(jp))
        kf = os.path.join(REPO, "data", sess + "-key", "key.json")
        rkey = {}
        if os.path.exists(kf):
            rkey = {b: v.get("run_id") for b, v in
                    json.load(open(kf)).items() if isinstance(v, dict)}
        for l in open(jp):
            r = json.loads(l)
            n_rows += 1
            raters.add(r["rater_id"])
            rid = rkey.get(r["blind_id"], r["blind_id"])
            key = (r["dimension"], rid)
            human[key].setdefault(r["rater_id"], []).append(r["score"])

    # ---- judge scores, translated to run_ids via the judge key files ----
    jkey = {}
    for kf in glob.glob(os.path.join(REPO, "data", "vlm-judge-key",
                                     "key*.json")):
        for b, v in json.load(open(kf)).items():
            if isinstance(v, dict):
                item = v.get("item", v)
                rid = item.get("run_id")
                if rid:
                    jkey[b] = rid
    judge = {}
    for jp in glob.glob(os.path.join(REPO, "data", "vlm-judge-*",
                                     "records.jsonl")):
        for l in open(jp):
            r = json.loads(l)
            res = r.get("result")
            rid = jkey.get(r.get("blind_id"), r.get("blind_id"))
            if isinstance(res, dict):
                for dim, v in res.items():
                    if isinstance(v, (int, float)):
                        judge[(dim, rid)] = v

    out = {"human_rows": n_rows, "raters": sorted(raters),
           "verdict": None, "alphas": {}}

    # intra-rater on hidden repeats
    for rater in raters:
        units = {}
        for key, per in human.items():
            vs = per.get(rater, [])
            if len(vs) >= 2:
                units[key] = vs
        a = krippendorff_alpha(units)
        out["alphas"]["intra:" + rater] = {
            "alpha": round(a, 3) if a is not None else None,
            "repeat_items": len(units)}

    # human-human
    if len(raters) >= 2:
        units = {k: [v for per in [p] for vs in per.values() for v in vs]
                 for k, p in human.items() if len(p) >= 2}
        a = krippendorff_alpha(units)
        out["alphas"]["human-human"] = {
            "alpha": round(a, 3) if a is not None else None,
            "shared_items": len(units)}

    # judge vs each human
    for rater in raters:
        units = {}
        for key, per in human.items():
            if rater in per and key in judge:
                units[key] = [per[rater][0], judge[key]]
        a = krippendorff_alpha(units) if len(units) >= MIN_ITEMS else None
        out["alphas"]["judge-vs-" + rater] = {
            "alpha": round(a, 3) if a is not None else None,
            "shared_items": len(units),
            "min_required": MIN_ITEMS}

    enough = any(v.get("alpha") is not None and "judge" in k
                 for k, v in out["alphas"].items())
    out["verdict"] = ("CALIBRATED" if enough else
                      "INSUFFICIENT DATA - run tools/rating_session.py "
                      "(>= %d shared items per judge-rater pair; the "
                      "existing journal is a UI dry-run and is excluded)"
                      % MIN_ITEMS)
    print("JUDGE CALIBRATION")
    print("  human rows: %d  raters: %s" % (n_rows, sorted(raters) or "-"))
    for k, v in out["alphas"].items():
        print("  %-18s alpha=%s  (n=%s)" % (
            k, v.get("alpha"), v.get("shared_items",
                                     v.get("repeat_items"))))
    print("  VERDICT: %s" % out["verdict"])
    op = os.path.join(REPO, "data", "judge-calibration.json")
    with open(op, "w") as f:
        json.dump(out, f, indent=1)
    print("-> %s" % op)
    return 0


if __name__ == "__main__":
    sys.exit(main())
