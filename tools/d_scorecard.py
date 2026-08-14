#!/usr/bin/env python3
"""Aggregate Campaign D edit metrics + edit judge into the scorecard.

    .venv/bin/python tools/d_scorecard.py
-> data/campaign-d/scorecard.json + docs/d-scorecard.md
"""
import collections
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def med(xs):
    xs = sorted(x for x in xs if x is not None)
    return round(xs[len(xs) // 2], 3) if xs else None


def main():
    rows = []
    for p in glob.glob(os.path.join(REPO, "data", "edit-metrics", "D-*.json")):
        rows.append(json.load(open(p)))
    judge = {}
    jp = os.path.join(REPO, "data", "edit-judge", "records.jsonl")
    if os.path.exists(jp):
        for line in open(jp):
            r = json.loads(line)
            judge[r["name"]] = r["verdict"]

    by = collections.defaultdict(list)
    for r in rows:
        etype = r["edit_id"].split("-")[0]
        by[(r["product"], etype)].append(r)

    card = {}
    for (prod, etype), rs in sorted(by.items()):
        js = [judge.get(r["name"]) for r in rs if judge.get(r["name"])]
        applied = [j["application"] for j in js]
        card.setdefault(prod, {})[etype] = {
            "n": len(rs),
            "commit_latency_s_med": med([r["commit_latency_s"] for r in rs]),
            "committed_frac": round(sum(1 for r in rs
                                        if r["commit_latency_s"] is not None)
                                    / max(len(rs), 1), 2),
            "collateral_med": med([r["collateral_index"] for r in rs]),
            "residue_med": med([r["residue_index"] for r in rs]),
            "hold_med": med([r["stability"]["hold"] for r in rs]),
            "transition_glitch_excess_med": med(
                [r["transition"]["transition_glitch_excess"] for r in rs]),
            "judged": len(js),
            "judge_full_apply": (round(applied.count("full") / len(applied), 2)
                                 if applied else None),
            "judge_residue_med": med([j["residue"] for j in js]),
            "judge_collateral_med": med([j["collateral"] for j in js]),
            "judge_transition_med": med([j["transition"] for j in js]),
            "judge_holds": (round(sum(1 for j in js
                                      if j["stability"] == "holds") / len(js), 2)
                            if js else None),
        }

    outp = os.path.join(REPO, "data", "campaign-d", "scorecard.json")
    json.dump(card, open(outp, "w"), indent=2)

    lines = ["# Campaign D scorecard - live mid-stream editing\n"]
    for prod in sorted(card):
        lines.append("\n## %s\n" % prod)
        lines.append("| edit type | n | commit s (med) | committed | collateral | residue | hold | judge: full-apply | judge: holds |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for etype, c in sorted(card[prod].items()):
            lines.append("| %s | %d | %s | %s | %s | %s | %s | %s | %s |" % (
                etype, c["n"], c["commit_latency_s_med"], c["committed_frac"],
                c["collateral_med"], c["residue_med"], c["hold_med"],
                c["judge_full_apply"], c["judge_holds"]))
    mdp = os.path.join(REPO, "docs", "d-scorecard.md")
    open(mdp, "w").write("\n".join(lines) + "\n")
    print("scorecard ->", outp, "and", mdp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
