#!/usr/bin/env python3
"""Consolidated RTV-Bench scorecard from the journals.

    .venv/bin/python tools/benchmark_score.py
-> data/benchmark-scorecard.json (+ prints summary)

Applies the ground rules mechanically: adjudication overrides, E-exclusion,
lens separation (results keyed by lens, never merged).
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return [round(max(0, c - h), 3), round(min(1, c + h), 3)]


def main():
    out = {"benchmark": "RTV-Bench", "spec": "1.0"}

    # --- reliability (adjudicated, E-excluded, keyed by lens) ---
    adj = {}
    ap = os.path.join(REPO, "data", "campaign-b", "adjudications.json")
    if os.path.exists(ap):
        adj = {a["run_id"]: a for a in json.load(open(ap))}
    rel = collections.defaultdict(collections.Counter)
    rp = os.path.join(REPO, "data", "campaign-b", "runs.jsonl")
    if os.path.exists(rp):
        for line in open(rp):
            r = json.loads(line)
            o = r["outcome"]
            if r["run_id"] in adj and adj[r["run_id"]]["from"] == o:
                o = adj[r["run_id"]]["to"]
            rel[(r["product_key"], r.get("lens", "?"))][o] += 1
    out["reliability"] = {}
    for (prod, lens), c in sorted(rel.items()):
        n = sum(v for k, v in c.items() if k in "SDFT")
        if not n:
            continue
        out["reliability"]["%s (lens %s)" % (prod, lens)] = {
            "N": n, "S": c["S"], "D": c["D"], "F": c["F"], "T": c["T"],
            "excluded_E": c["E"],
            "clean_rate": round(c["S"] / n, 3), "clean_ci95": wilson(c["S"], n),
            "fail_rate": round(c["F"] / n, 3), "fail_ci95": wilson(c["F"], n)}
    # native browser lane journal (separate lens by construction)
    np_ = os.path.join(REPO, "data", "campaign-b-native", "runs.jsonl")
    if os.path.exists(np_):
        c = collections.Counter(json.loads(l)["outcome"] for l in open(np_))
        n = sum(c.values())
        out["reliability"]["xmax-x2.0 (lens P-browser)"] = {
            "N": n, "S": c["S"], "D": c["D"], "F": c["F"], "T": c.get("T", 0),
            "excluded_E": 0, "clean_rate": round(c["S"] / n, 3),
            "clean_ci95": wilson(c["S"], n),
            "fail_rate": round(c["F"] / n, 3), "fail_ci95": wilson(c["F"], n)}

    # --- pairwise quality ---
    pp = os.path.join(REPO, "data", "vlm-judge-b-pairs", "records.jsonl")
    if os.path.exists(pp):
        wins = collections.defaultdict(collections.Counter)
        clip = collections.Counter()
        n = 0
        for line in open(pp):
            r = json.loads(line)
            n += 1
            v = collections.Counter(r.get("winners_named", {}).values())
            for d, w in r.get("winners_named", {}).items():
                wins[d][w] += 1
            if v:
                clip[v.most_common(1)[0][0]] += 1
        out["pairwise_quality"] = {"pairs": n,
                                   "clip_majority": dict(clip),
                                   "dimensions": {d: dict(c)
                                                  for d, c in wins.items()}}

    # --- editing (campaign D) ---
    sp = os.path.join(REPO, "data", "campaign-d", "scorecard.json")
    if os.path.exists(sp):
        out["live_editing"] = json.load(open(sp))

    # --- platform overhead ---
    out["platform_overhead_note"] = ("xmax native vs via-Reactor delta "
                                     "~650-710 ms; see docs/final-report.md")

    op = os.path.join(REPO, "data", "benchmark-scorecard.json")
    json.dump(out, open(op, "w"), indent=2)
    print(json.dumps({k: (v if not isinstance(v, dict) else "...")
                      for k, v in out.items()}, indent=1))
    print("full scorecard ->", op)
    return 0


if __name__ == "__main__":
    sys.exit(main())
