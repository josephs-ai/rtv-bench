#!/usr/bin/env python3
"""RTV-Bench terminal dashboard - THE results surface.

    .venv/bin/python tools/dash.py            # full board
    .venv/bin/python tools/dash.py --no-color

The machine reads the records and hands the user the results here:
canonical scores, axes, profiles, campaign coverage, question-registry
status, and the claims-checker verdict - all computed from data/, never
hand-carried. If a number on this board disagrees with a doc, the board
is right and the doc failed claims_check.
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SC = os.path.join(REPO, "data", "benchmark-scorecard.json")

C = {"g": "\033[32m", "y": "\033[33m", "r": "\033[31m", "b": "\033[1m",
     "d": "\033[2m", "0": "\033[0m", "c": "\033[36m"}


def col(k, s):
    return "%s%s%s" % (C[k], s, C["0"])


def bar(v, width=20):
    if v is None:
        return col("d", "-" * width)
    n = int(round(v / 100.0 * width))
    k = "g" if v >= 60 else "y" if v >= 40 else "r"
    return col(k, "█" * n) + col("d", "░" * (width - n))


def count_lines(path):
    try:
        return sum(1 for _ in open(path))
    except OSError:
        return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-color", action="store_true")
    args = ap.parse_args()
    if args.no_color or not sys.stdout.isatty():
        for k in C:
            C[k] = ""

    if not os.path.exists(SC):
        print("no scorecard yet - run: .venv/bin/python tools/benchmark_score.py")
        return 1
    s = json.load(open(SC))
    spec = s.get("spec", "")
    rs = s.get("rtvbench_score", {})

    print(col("b", "\nRTV-Bench") + col("d", "  ·  spec v1.1  ·  "
          "reference run 2026-08  ·  vantage: mainland-CN"))
    print(col("d", "─" * 74))

    # ---- canonical ladders ----
    print(col("b", "CANONICAL RTV-SCORE") + col("d",
          "   100×√delivery×(0.40·exp + 0.25·edit + 0.20·ref + 0.15·lat)"))
    for track, rows in (("Track 1 · interactive video", rs.get("track1", {})),
                        ("Track 2 · interactive worlds", rs.get("track2", {}))):
        print(" " + col("c", track))
        for ent, v in sorted(rows.items(), key=lambda kv: -kv[1]["score"]):
            extra = ("delivery %.0f%%" % (100 * v["delivery"])
                     if "delivery" in v else
                     "build %.0f%%" % (100 * v.get("build_success", 1)))
            cov = v.get("coverage_pct")
            print("  %-34s %s %5.1f  %s%s" % (
                ent, bar(v["score"]), v["score"], col("d", extra),
                col("y", "  cov %d%%" % cov) if cov and cov < 100 else ""))

    # ---- axes ----
    ents = s.get("composite", {}).get("entities", {})
    # only entities with broad axis coverage (lens-M etc. live in RESULTS
    # with their own caveats; a 2-axis column here would mislead)
    main_ents = [(k, v) for k, v in ents.items()
                 if sum(x is not None for x in v["axes"].values()) >= 4]
    names = {"A": "reliability", "B": "pairwise*", "C": "identity",
             "D": "live editing", "E": "latency", "F": "deploy-CN",
             "G": "ref control"}
    print("\n" + col("b", "AXES") + col("d", "  (0-100 absolute; * = "
          "relative exhibit, not in canonical)"))
    def short(ent):
        prod, lens = ent.split(" (lens ")
        return "%s·%s" % (prod, lens.rstrip(")"))
    hdr = "  %-4s %-14s" + " %20s" * len(main_ents)
    print(col("d", hdr % (("ax", "") + tuple(short(e[0])
                                             for e in main_ents))))
    for ax in "ABCDEFG":
        row = "  %-4s %-14s" % (ax, names[ax])
        for _, v in main_ents:
            val = v["axes"].get(ax)
            row += " %20s" % ("-" if val is None else "%.1f" % val)
        print(row)
    g0 = main_ents[0][1]["subs"].get("G") if main_ents else None
    if g0:
        subline = "       " + col("d", "G subs (adoption/hold/switch/compose): ")
        for _, v in main_ents:
            g = v["subs"].get("G") or {}
            subline += col("c", "%s/%s/%s/%s  " % tuple(
                g.get(k, "-") for k in ("adoption", "hold", "switch",
                                        "compose")))
        print(subline)

    # ---- profiles ----
    print("\n" + col("b", "BUYER PROFILES") + col("d",
          "  (same measurements × declared weights)"))
    profs = sorted({p for _, v in main_ents for p in v.get("profiles", {})})
    for p in profs:
        row = "  %-16s" % p
        for _, v in main_ents:
            pv = v.get("profiles", {}).get(p)
            row += " %20s" % ("-" if not pv else "%.1f" % pv["score"])
        print(row)

    # ---- campaign coverage ----
    print("\n" + col("b", "CAMPAIGN COVERAGE") + col("d", "  (sessions on disk)"))
    cov = [
        ("B reliability", count_lines(f"{REPO}/data/campaign-b/runs.jsonl")
         + count_lines(f"{REPO}/data/campaign-b-native/runs.jsonl")),
        ("D live edits", len(glob.glob(f"{REPO}/data/campaign-d/captures/*.json"))),
        ("F ref control", len(glob.glob(f"{REPO}/data/campaign-f/captures/*.json"))
         + len(glob.glob(f"{REPO}/data/campaign-f/captures-probe/*.json"))),
        ("E hour-scale", count_lines(f"{REPO}/data/campaign-e/runs.jsonl")),
        ("C worlds", len(glob.glob(f"{REPO}/data/campaign-c-gen/*-r[123].json"))),
    ]
    for name, n in cov:
        print("  %-16s %s" % (name, col("g" if n else "r", str(n))))

    # ---- question registry ----
    qpath = os.path.join(REPO, "spec", "questions.md")
    if os.path.exists(qpath):
        rows = re.findall(r"^\| (Q[\d.]+) \|.*\| ([^|]+) \|$",
                          open(qpath).read(), re.M)
        n_ans = sum(1 for _, st in rows if st.strip().startswith("answered"))
        n_part = sum(1 for _, st in rows if st.strip().startswith("partial"))
        n_pend = len(rows) - n_ans - n_part
        print("\n" + col("b", "QUESTION REGISTRY") + col("d",
              "  (spec/questions.md)"))
        print("  %s answered   %s partial   %s pending" % (
            col("g", n_ans), col("y", n_part),
            col("r" if n_pend else "g", n_pend)))
        for q, st in rows:
            st = st.strip()
            if not st.startswith("answered"):
                print(col("y", "   %-6s %s" % (q, st[:64])))

    # ---- claims check ----
    print("\n" + col("b", "CLAIMS CHECK") + col("d",
          "  (every shipped number vs the records)"))
    r = subprocess.run([sys.executable, os.path.join(REPO, "tools",
                        "claims_check.py")], capture_output=True, text=True)
    okn = r.stdout.count("[ok]")
    bad = r.stdout.count("MISMATCH")
    verdict = ("%s  (%d checks)" % (col("g", "ALL CLAIMS VERIFIED"), okn)
               if r.returncode == 0 else
               col("r", "%d MISMATCHES - DO NOT SHIP" % bad))
    print("  " + verdict)
    print(col("d", "─" * 74))
    print(col("d", "  full evidence: docs/RESULTS.md · spec/questions.md · "
          "data/benchmark-scorecard.json\n"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
