#!/usr/bin/env python3
"""RTV-Bench terminal dashboard - THE results surface.

    .venv/bin/python tools/dash.py              # all three layers
    .venv/bin/python tools/dash.py --layer 3    # just the drill-down
    .venv/bin/python tools/dash.py --no-color

The machine reads the records and hands the user the results here, in
three layers:
  LAYER 1  canonical RTV-Score ladders (the one number, per track)
  LAYER 2  axes + buyer profiles (where the number comes from)
  LAYER 3  sub-metric drill-down (what each axis is made of)
plus campaign coverage, question-registry status, and the live
claims-check verdict - all computed from data/, never hand-carried. If a
number on this board disagrees with a doc, the board is right and the
doc failed claims_check.
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


def fmt(v, nd=1):
    if v is None:
        return "-"
    return ("%." + str(nd) + "f") % v if isinstance(v, float) else str(v)


def count_lines(path):
    try:
        return sum(1 for _ in open(path))
    except OSError:
        return 0


def short(ent):
    prod, lens = ent.split(" (lens ")
    return "%s·%s" % (prod, lens.rstrip(")"))


def layer1(rs):
    print(col("b", "LAYER 1 · CANONICAL RTV-SCORE") + col("d",
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


AXIS_NAMES = {"A": "reliability", "B": "pairwise*", "C": "identity",
              "D": "live editing", "E": "latency", "F": "deploy-CN",
              "G": "ref control"}


def layer2(main_ents):
    print("\n" + col("b", "LAYER 2 · AXES") + col("d",
          "  (0-100 absolute; * = relative exhibit, not in canonical)"))
    hdr = "  %-4s %-14s" + " %20s" * len(main_ents)
    print(col("d", hdr % (("ax", "") + tuple(short(e[0])
                                             for e in main_ents))))
    for ax in "ABCDEFG":
        row = "  %-4s %-14s" % (ax, AXIS_NAMES[ax])
        for _, v in main_ents:
            row += " %20s" % fmt(v["axes"].get(ax))
        print(row)
    print("\n" + col("b", "LAYER 2 · BUYER PROFILES") + col("d",
          "  (same measurements × declared weights)"))
    profs = sorted({p for _, v in main_ents for p in v.get("profiles", {})})
    for p in profs:
        row = "  %-20s" % p
        for _, v in main_ents:
            pv = v.get("profiles", {}).get(p)
            row += " %14s" % ("-" if not pv else "%.1f" % pv["score"])
            if pv and pv.get("caps_applied"):
                row += col("y", " [capped]")
        print(row)


def layer3(s, main_ents):
    print("\n" + col("b", "LAYER 3 · SUB-METRIC DRILL-DOWN") + col("d",
          "  (what each axis is made of)"))
    art = s.get("artifact_burden", {})
    dsc_p = os.path.join(REPO, "data", "campaign-d", "scorecard.json")
    dsc = json.load(open(dsc_p)) if os.path.exists(dsc_p) else {}

    def g(v):
        return v["subs"].get("G") or {}

    sub_rows = [
        ("A", "value rate (S+½D)", lambda v: v["subs"]["A"].get("value_rate")),
        ("A", "long-session value", lambda v: v["subs"]["A"].get("long_value_rate")),
        ("A", "time-to-first-frame", lambda v: v["subs"]["A"].get("ttff")),
        ("B", "pairwise wins*", lambda v: v["subs"]["B"].get("pairwise")),
        ("C", "scene/identity drift", lambda v: v["subs"]["C"].get("drift")),
        ("C", "face through edits", lambda v: v["subs"]["C"].get("face_through_edits")),
        ("E", "motion-to-glass", lambda v: v["subs"]["E"].get("motion_to_glass")),
        ("G", "adoption (full matrix)", lambda v: g(v).get("adoption")),
        ("G", "anchored hold", lambda v: g(v).get("hold")),
        ("G", "mid-video switch", lambda v: g(v).get("switch")),
        ("G", " · in-session", lambda v: (g(v).get("detail") or {}).get("switch_in_session")),
        ("G", " · re-session mech", lambda v: (g(v).get("detail") or {}).get("switch_mechanism")),
        ("G", "edit on anchored char", lambda v: g(v).get("compose")),
    ]
    hdr = "  %-4s %-22s" + " %20s" * len(main_ents)
    print(col("d", hdr % (("ax", "sub-metric") + tuple(short(e[0])
                                                       for e in main_ents))))
    last_ax = None
    for ax, name, get in sub_rows:
        row = "  %-4s %-22s" % (ax if ax != last_ax else "", name)
        for _, v in main_ents:
            try:
                row += " %20s" % fmt(get(v))
            except Exception:
                row += " %20s" % "-"
        print(row)
        last_ax = ax

    # artifact audit (feeds B' and the experience term)
    for label, key, note in (("artifact score (B')", "score", ""),
                             ("artifact burden /18", "burden_med",
                              "   (lower better; both far from ceiling)")):
        line = "  %-4s %-22s" % ("B'", label)
        for ent, _ in main_ents:
            a = art.get(ent) if isinstance(art, dict) else None
            line += " %20s" % (fmt(a.get(key)) if isinstance(a, dict)
                               else "-")
        print(line + col("d", note))

    # D: per-edit-type breakdown from the campaign-D scorecard
    prods = [e[0].split(" (")[0] for e in main_ents]
    types = sorted({t for p in prods for t in dsc.get(p, {})})
    if types:
        print("\n  " + col("c", "D · live editing by edit type") +
              col("d", "  (commit-latency s med · judged full-apply rate)"))
        hdr2 = "  %-14s" + " %20s" * len(prods)
        print(col("d", hdr2 % (("edit type",) + tuple(prods))))
        for ty in types:
            row = "  %-14s" % ty
            for p in prods:
                d = dsc.get(p, {}).get(ty)
                row += " %20s" % ("-" if not d else "%s · %s" % (
                    fmt(d.get("commit_latency_s_med")),
                    fmt(d.get("judge_full_apply"), 2)))
            print(row)


def footer():
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-color", action="store_true")
    ap.add_argument("--layer", type=int, default=0, choices=(0, 1, 2, 3),
                    help="1=canonical 2=axes/profiles 3=drill-down "
                         "(default 0: everything)")
    args = ap.parse_args()
    if args.no_color or not sys.stdout.isatty():
        for k in C:
            C[k] = ""

    if not os.path.exists(SC):
        print("no scorecard yet - run: .venv/bin/python tools/benchmark_score.py")
        return 1
    s = json.load(open(SC))
    rs = s.get("rtvbench_score", {})
    ents = s.get("composite", {}).get("entities", {})
    # only entities with broad axis coverage (lens-M etc. live in RESULTS
    # with their own caveats; a 2-axis column here would mislead)
    main_ents = [(k, v) for k, v in ents.items()
                 if sum(x is not None for x in v["axes"].values()) >= 4]

    print(col("b", "\nRTV-Bench") + col("d", "  ·  spec v1.1  ·  "
          "reference run 2026-08  ·  vantage: mainland-CN"))
    print(col("d", "─" * 74))
    L = args.layer
    if L in (0, 1):
        layer1(rs)
    if L in (0, 2):
        layer2(main_ents)
    if L in (0, 3):
        layer3(s, main_ents)
    if L == 0:
        footer()
    print(col("d", "─" * 74))
    print(col("d", "  full evidence: docs/RESULTS.md · spec/questions.md · "
          "data/benchmark-scorecard.json\n"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
