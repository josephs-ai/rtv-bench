#!/usr/bin/env python3
"""Auto-assembled benchmark report: journals -> markdown, no hand-editing.

    .venv/bin/python tools/benchmark_score.py    # refresh scorecard first
    .venv/bin/python tools/benchmark_report.py
-> docs/report-generated.md

The hand-written docs/final-report.md is the editorial narrative for the
2026-08 reference run; THIS file is the mechanical one that stays correct
on every rerun. Numbers here always re-derive from the scorecard.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    sp = os.path.join(REPO, "data", "benchmark-scorecard.json")
    if not os.path.exists(sp):
        print("run benchmark_score.py first")
        return 1
    s = json.load(open(sp))
    L = []
    L.append("# RTV-Bench report (auto-generated)")
    L.append("")
    L.append("Generated: %s · spec %s · numbers re-derived from journals"
             % (time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
                s.get("spec")))
    L.append("")

    comp = s.get("composite", {})
    ents = comp.get("entities", {})
    if ents:
        L.append("## Composite scores (per lens - lenses never merge)")
        L.append("")
        profs = list(comp.get("profiles", {}))
        L.append("| entity | " + " | ".join(profs) + " |")
        L.append("|---" * (len(profs) + 1) + "|")
        for ent, d in ents.items():
            cells = []
            for p in profs:
                r = d["profiles"].get(p)
                if not r:
                    cells.append("-")
                else:
                    c = "%.1f" % r["score"]
                    if r["coverage_pct"] < 100:
                        c += " (cov %d%%)" % r["coverage_pct"]
                    if r["caps_applied"]:
                        c += " [capped]"
                    cells.append(c)
            L.append("| %s | %s |" % (ent, " | ".join(cells)))
        L.append("")
        L.append("### Axis detail")
        L.append("")
        L.append("| entity | A rel | B qual | C ident | D edit | E lat | F deploy |")
        L.append("|---|---|---|---|---|---|---|")
        for ent, d in ents.items():
            a = d["axes"]
            L.append("| %s | %s | %s | %s | %s | %s | %s |" % (
                ent, *(a.get(x, "-") if a.get(x) is not None else "-"
                       for x in "ABCDEF")))
        L.append("")
        notes = sorted({n for d in ents.values() for n in d.get("notes", [])})
        if notes:
            L.append("Coverage notes: " + "; ".join(notes))
        L.append("")
        L.append("Weights (override with benchmark_score.py --weights):")
        L.append("```json")
        L.append(json.dumps({"profiles": comp.get("profiles"),
                             "floors": comp.get("floors")}, indent=1))
        L.append("```")
        L.append("")

    rel = s.get("reliability", {})
    if rel:
        L.append("## Reliability (adjudicated, network-fault runs excluded)")
        L.append("")
        L.append("| entity | N | S | D | F | clean rate (95% CI) | fail rate (95% CI) | excluded E |")
        L.append("|---|---|---|---|---|---|---|---|")
        for ent, r in rel.items():
            L.append("| %s | %d | %d | %d | %d | %.1f%% (%s) | %.1f%% (%s) | %d |" % (
                ent, r["N"], r["S"], r["D"], r["F"],
                r["clean_rate"] * 100, r["clean_ci95"],
                r["fail_rate"] * 100, r["fail_ci95"], r["excluded_E"]))
        L.append("")

    pq = s.get("pairwise_quality")
    if pq:
        L.append("## Same-input blinded pairs (n=%d)" % pq["pairs"])
        L.append("")
        L.append("Clip-level majority: `%s`" % json.dumps(pq["clip_majority"]))
        for d, c in sorted(pq["dimensions"].items()):
            L.append("- %s: `%s`" % (d, json.dumps(c)))
        L.append("")

    le = s.get("live_editing")
    if le:
        L.append("## Live editing (campaign D)")
        L.append("")
        for prod, types in le.items():
            L.append("### %s" % prod)
            L.append("")
            L.append("| edit type | n | commit s | committed | collateral | residue | hold | judge full-apply |")
            L.append("|---|---|---|---|---|---|---|---|")
            for t, c in sorted(types.items()):
                L.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
                    t, c["n"], c["commit_latency_s_med"], c["committed_frac"],
                    c["collateral_med"], c["residue_med"], c["hold_med"],
                    c["judge_full_apply"]))
            L.append("")

    L.append("---")
    L.append(s.get("platform_overhead_note", ""))
    L.append("")
    L.append("Ground rules and methodology: see BENCHMARK.md. Raw journals "
             "and adjudication log under data/.")

    op = os.path.join(REPO, "docs", "report-generated.md")
    open(op, "w").write("\n".join(L) + "\n")
    print("report ->", op)
    return 0


if __name__ == "__main__":
    sys.exit(main())
