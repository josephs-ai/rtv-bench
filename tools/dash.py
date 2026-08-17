#!/usr/bin/env python3
"""RTV-Bench terminal dashboard - THE results surface.

    .venv/bin/python tools/dash.py              # all three layers
    .venv/bin/python tools/dash.py --layer 3    # just the drill-down
    .venv/bin/python tools/dash.py --watch 10   # live mission control
    .venv/bin/python tools/dash.py --why G      # evidence chain for an axis
    .venv/bin/python tools/dash.py --weights my.json   # re-editorialize
    .venv/bin/python tools/dash.py --vendor xmax       # one product's cut
    .venv/bin/python tools/dash.py --md         # markdown export
    .venv/bin/python tools/dash.py --json       # machine export
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


# evidence map: axis -> where its numbers come from (the --why chain)
EVIDENCE = {
    "A": ["data/campaign-b/runs.jsonl", "data/campaign-b-native/runs.jsonl",
          "data/campaign-b/preserved-tally.json",
          "data/campaign-b/adjudications.json"],
    "B": ["data/vlm-judge-b-pairs/records.jsonl",
          "data/vlm-judge-audit/records.jsonl",
          "data/vlm-judge-key/ (per-run blinding keys)"],
    "C": ["data/quality-metrics/", "data/campaign-e/*/stills/"],
    "D": ["data/campaign-d/scorecard.json", "data/edit-judge/records.jsonl",
          "data/edit-metrics/"],
    "E": ["data/campaign-b/vantage.json", "data/bridge-measurement.json"],
    "F": ["vantage records (route/DNS/VPN matrix)"],
    "G": ["data/campaign-f/metrics/summary.json",
          "data/campaign-f/probe-verdicts.json",
          "data/campaign-f/runs.jsonl"],
}


def why(s, main_ents, ax):
    ax = ax.upper()
    print(col("b", "WHY · axis %s (%s)" % (ax, AXIS_NAMES.get(ax, "?"))))
    for ent, v in main_ents:
        subs = v["subs"].get(ax)
        print(" " + col("c", ent) + "  axis score: %s"
              % fmt(v["axes"].get(ax)))
        if isinstance(subs, dict):
            for k, sv in subs.items():
                if k == "detail":
                    for dk, dv in (sv or {}).items():
                        print(col("d", "     detail.%-22s %s" % (dk, dv)))
                else:
                    print("   %-26s %s" % (k, fmt(sv)))
    if ax == "G":
        fsum = os.path.join(REPO, "data", "campaign-f", "metrics",
                            "summary.json")
        if os.path.exists(fsum):
            print(" " + col("c", "underlying runs (campaign F)"))
            for r in json.load(open(fsum)):
                print(col("d", "   %-44s %-8s ref=%-6s input=%-6s %s" % (
                    r["run_id"], r["arm"],
                    fmt(r.get("sim_ref_post_mean"), 2),
                    fmt(r.get("sim_input_post_mean"), 2),
                    ("lat=%ss" % r.get("switch_latency_s")
                     if r.get("switch_latency_s") is not None else ""))))
    print(" " + col("c", "records"))
    for pth in EVIDENCE.get(ax, []):
        print("   " + pth)


def _core_parts(s, ent, v):
    """canonical components for one entity (mirrors benchmark_score)."""
    art = s.get("artifact_burden", {})
    a_s = (art.get(ent) or {}).get("score") if isinstance(art, dict) else None
    c_s = v["axes"].get("C")
    exp = (None if (a_s is None and c_s is None) else
           a_s if c_s is None else c_s if a_s is None
           else round((a_s + c_s) / 2, 1))
    return {"experience": exp, "interaction": v["axes"].get("D"),
            "ref_control": v["axes"].get("G"), "latency": v["axes"].get("E")}


def reweighted(s, main_ents, wspec):
    """re-render profiles/canonical under user weights (the printed
    weights are declared opinions - anyone may re-editorialize)."""
    import math
    print(col("b", "RE-EDITORIALIZED") + col("d",
          "  (your weights, same measurements: " + json.dumps(wspec) + ")"))
    core_w = wspec.get("core")
    prof_w = {k: v for k, v in wspec.items() if k != "core"}
    for ent, v in main_ents:
        line = " " + col("c", ent)
        if core_w:
            parts = _core_parts(s, ent, v)
            avail = {k: (parts[k], w) for k, w in core_w.items()
                     if parts.get(k) is not None}
            rsent = s.get("rtvbench_score", {}).get("track1", {}).get(ent)
            if avail and rsent:
                tot = sum(w for _, w in avail.values())
                core = sum(p / 100.0 * w / tot for p, w in avail.values())
                line += "  canonical: %.1f" % (
                    100 * math.sqrt(rsent["delivery"]) * core)
        for pname, pw in prof_w.items():
            avail = {a: w for a, w in pw.items()
                     if v["axes"].get(a) is not None and w > 0}
            if avail:
                tot = sum(avail.values())
                line += "  %s: %.1f" % (pname, sum(
                    v["axes"][a] * w / tot for a, w in avail.items()))
        print(line)


def deltas(s):
    hd = os.path.join(REPO, "data", "scorecard-history")
    hist = sorted(glob.glob(os.path.join(hd, "scorecard-*.json")))
    if len(hist) < 2:
        return
    prev = json.load(open(hist[-2]))
    pt1 = prev.get("rtvbench_score", {}).get("track1", {})
    ct1 = s.get("rtvbench_score", {}).get("track1", {})
    moves = []
    for ent, v in ct1.items():
        if ent in pt1:
            d = v["score"] - pt1[ent]["score"]
            if abs(d) >= 0.05:
                moves.append("%s %+.1f" % (ent.split(" (")[0], d))
    pax = prev.get("composite", {}).get("entities", {})
    cax = s.get("composite", {}).get("entities", {})
    for ent, v in cax.items():
        for ax, val in v["axes"].items():
            old = (pax.get(ent) or {}).get("axes", {}).get(ax)
            if val is not None and old is not None and abs(val - old) >= 0.5:
                moves.append("%s·%s %+.1f" % (ent.split(" (")[0], ax,
                                              val - old))
    if moves:
        print(col("d", "  Δ vs previous scoring run: ") +
              col("y", " · ".join(moves[:8])))


def ticker():
    """--watch header: what's running right now."""
    import time
    r = subprocess.run(["pgrep", "-fl",
                        "campaign_[a-z0-9_]*.py|xmax_native_lane|"
                        "ref_switch_probe|vlm_judge|edit_judge"],
                       capture_output=True, text=True)
    procs = [ln.split(None, 1)[1][:60] for ln in r.stdout.splitlines()
             if "pgrep" not in ln]
    caps = glob.glob(os.path.join(REPO, "data", "campaign-*", "captures",
                                  "*.json"))
    last = max(caps, key=os.path.getmtime) if caps else None
    print(col("b", "IN FLIGHT"))
    if procs:
        for pr in procs[:4]:
            print("  " + col("g", "▶ " + pr))
    else:
        print(col("d", "  nothing running"))
    if last:
        age = int(time.time() - os.path.getmtime(last))
        print(col("d", "  last capture: %s (%ds ago)" % (
            os.path.basename(last), age)))


def export_json(s, main_ents):
    out = {"spec": "v1.1", "canonical": s.get("rtvbench_score", {}),
           "entities": {k: {"axes": v["axes"], "subs": v["subs"],
                            "profiles": v.get("profiles", {})}
                        for k, v in main_ents}}
    print(json.dumps(out, indent=1))


def export_md(s, main_ents):
    rs = s.get("rtvbench_score", {})
    print("## RTV-Bench results (spec v1.1, machine-rendered)\n")
    print("| Track 1 | RTV-Score | | Track 2 | RTV-Score |")
    print("|---|---|---|---|---|")
    t1 = sorted(rs.get("track1", {}).items(), key=lambda kv: -kv[1]["score"])
    t2 = sorted(rs.get("track2", {}).items(), key=lambda kv: -kv[1]["score"])
    for i in range(max(len(t1), len(t2))):
        a = "%s | %.1f" % (t1[i][0], t1[i][1]["score"]) if i < len(t1) else " | "
        b = "%s | %.1f" % (t2[i][0], t2[i][1]["score"]) if i < len(t2) else " | "
        print("| %s | | %s |" % (a, b))
    print("\n| axis | " + " | ".join(short(e[0]) for e in main_ents) + " |")
    print("|---|" + "---|" * len(main_ents))
    for ax in "ABCDEFG":
        print("| %s %s | " % (ax, AXIS_NAMES[ax]) + " | ".join(
            fmt(v["axes"].get(ax)) for _, v in main_ents) + " |")
    print("\n| profile | " + " | ".join(short(e[0]) for e in main_ents) + " |")
    print("|---|" + "---|" * len(main_ents))
    profs = sorted({p for _, v in main_ents for p in v.get("profiles", {})})
    for p in profs:
        print("| %s | " % p + " | ".join(
            fmt((v.get("profiles", {}).get(p) or {}).get("score"))
            for _, v in main_ents) + " |")
    # layer 3: every sub-metric
    art = s.get("artifact_burden", {})
    print("\n### Sub-metric drill-down\n")
    print("| axis | sub-metric | " + " | ".join(short(e[0])
                                                for e in main_ents) + " |")
    print("|---|---|" + "---|" * len(main_ents))
    def row(ax, name, get):
        cells = []
        for _, v in main_ents:
            try:
                cells.append(fmt(get(v)))
            except Exception:
                cells.append("-")
        print("| %s | %s | " % (ax, name) + " | ".join(cells) + " |")
    gg = lambda v: v["subs"].get("G") or {}
    row("A", "value rate (S+½D)", lambda v: v["subs"]["A"].get("value_rate"))
    row("A", "long-session value", lambda v: v["subs"]["A"].get("long_value_rate"))
    row("A", "time-to-first-frame score", lambda v: v["subs"]["A"].get("ttff"))
    row("B", "pairwise wins (exhibit)", lambda v: v["subs"]["B"].get("pairwise"))
    row("B'", "artifact score", lambda v: (art.get([k for k,_ in main_ents if _ is v][0]) or {}).get("score"))
    row("B'", "artifact burden /18 (lower better)", lambda v: (art.get([k for k,_ in main_ents if _ is v][0]) or {}).get("burden_med"))
    row("C", "scene/identity drift", lambda v: v["subs"]["C"].get("drift"))
    row("C", "face through edits", lambda v: v["subs"]["C"].get("face_through_edits"))
    row("D", "aggregate", lambda v: v["subs"]["D"].get("aggregate"))
    row("E", "motion-to-glass score", lambda v: v["subs"]["E"].get("motion_to_glass"))
    row("F", "CN-market", lambda v: v["subs"]["F"].get("cn_market"))
    row("G", "adoption (full matrix)", lambda v: gg(v).get("adoption"))
    row("G", "anchored hold", lambda v: gg(v).get("hold"))
    row("G", "mid-video switch", lambda v: gg(v).get("switch"))
    row("G", "· switch in-session", lambda v: (gg(v).get("detail") or {}).get("switch_in_session"))
    row("G", "· switch re-session mech", lambda v: (gg(v).get("detail") or {}).get("switch_mechanism"))
    row("G", "edit on anchored character", lambda v: gg(v).get("compose"))
    # D per edit type
    dsc_p = os.path.join(REPO, "data", "campaign-d", "scorecard.json")
    if os.path.exists(dsc_p):
        dsc = json.load(open(dsc_p))
        prods = [e[0].split(" (")[0] for e in main_ents]
        types = sorted({ty for p2 in prods for ty in dsc.get(p2, {})})
        print("\n### Live editing by edit type (campaign D)\n")
        print("| edit type | metric | " + " | ".join(prods) + " |")
        print("|---|---|" + "---|" * len(prods))
        for ty in types:
            for label, key, nd in (
                    ("commit latency s (med)", "commit_latency_s_med", 1),
                    ("committed fraction", "committed_frac", 2),
                    ("judged full-apply", "judge_full_apply", 2),
                    ("judged holds", "judge_holds", 2),
                    ("collateral (med, lower better)", "collateral_med", 2)):
                cells = [fmt((dsc.get(p2, {}).get(ty) or {}).get(key), nd)
                         for p2 in prods]
                print("| %s | %s | " % (ty, label) + " | ".join(cells) + " |")
    print("\n*Auto-generated by `tools/dash.py --md` from "
          "`data/benchmark-scorecard.json` + campaign records; "
          "per-run rows live in `data/` (walkable via `dash.py --why`).*")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-color", action="store_true")
    ap.add_argument("--color", action="store_true",
                    help="force ANSI color even when not a tty")
    ap.add_argument("--layer", type=int, default=0, choices=(0, 1, 2, 3),
                    help="1=canonical 2=axes/profiles 3=drill-down "
                         "(default 0: everything)")
    ap.add_argument("--watch", type=int, metavar="SECS", default=0,
                    help="live mode: re-render every SECS with an "
                         "in-flight ticker")
    ap.add_argument("--why", metavar="AXIS",
                    help="evidence chain for one axis (A-G)")
    ap.add_argument("--weights", metavar="JSON",
                    help="re-editorialize: file or inline JSON, e.g. "
                         '\'{"core":{"experience":0.5,"interaction":0.5},'
                         '"MYVIEW":{"A":50,"G":50}}\'')
    ap.add_argument("--vendor", metavar="NAME",
                    help="show only entities matching NAME")
    ap.add_argument("--md", action="store_true",
                    help="export the board as markdown")
    ap.add_argument("--json", action="store_true", dest="as_json",
                    help="export the board as JSON")
    args = ap.parse_args()
    if args.no_color or (not sys.stdout.isatty() and not args.color):
        for k in C:
            C[k] = ""

    # fresh-setup detection: hand the user to the wizard, not to errors
    envp = os.path.join(REPO, ".env")
    keys = {}
    if os.path.exists(envp):
        for line in open(envp):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, val = line.split("=", 1)
                keys[k] = bool(val.strip())
    missing = [k for k in ("DECART_API_KEY", "XMAX_API_KEY",
                           "REACTOR_API_KEY", "ANTHROPIC_API_KEY")
               if not keys.get(k)]
    if not os.path.exists(os.path.join(REPO, ".venv")) or missing:
        print(col("b", "\nRTV-Bench") + col("d", " · first-run"))
        print(col("y", "  setup incomplete: ") + col("d",
              ("missing keys: " + ", ".join(missing)) if missing
              else "no .venv"))
        print(col("b", "  run the setup wizard: ") +
              col("c", "python3 setup.py"))
        print(col("d", "  it walks you through prerequisites, venvs, "
              "provider API keys (.env),\n  live key validation, and "
              "self-test - then tells you which campaigns\n  your keys "
              "unlock. Safe to re-run any time."))
        if not os.path.exists(SC):
            return 1
        print(col("d", "  (showing last scorecard below - scores may "
              "predate your setup)"))
    if not os.path.exists(SC):
        print(col("y", "no scorecard yet") + col("d",
              " - run campaigns, then: .venv/bin/python "
              "tools/benchmark_run.py score"))
        return 1
    s = json.load(open(SC))
    rs = s.get("rtvbench_score", {})
    ents = s.get("composite", {}).get("entities", {})
    # only entities with broad axis coverage (lens-M etc. live in RESULTS
    # with their own caveats; a 2-axis column here would mislead)
    main_ents = [(k, v) for k, v in ents.items()
                 if sum(x is not None for x in v["axes"].values()) >= 4]
    if args.vendor:
        main_ents = [(k, v) for k, v in main_ents
                     if args.vendor.lower() in k.lower()]
        if not main_ents:
            print("no entity matches --vendor %r" % args.vendor)
            return 1

    if args.as_json:
        export_json(s, main_ents)
        return 0
    if args.md:
        export_md(s, main_ents)
        return 0
    if args.why:
        why(s, main_ents, args.why)
        return 0
    if args.weights:
        wspec = (json.load(open(args.weights))
                 if os.path.exists(args.weights)
                 else json.loads(args.weights))
        reweighted(s, main_ents, wspec)
        return 0

    def render():
        print(col("b", "\nRTV-Bench") + col("d", "  ·  spec v1.1  ·  "
          "reference run 2026-08  ·  vantage: mainland-CN"))
        print(col("d", "─" * 74))
        if args.watch:
            ticker()
            print(col("d", "─" * 74))
        L = args.layer
        if L in (0, 1):
            layer1(rs)
            deltas(s)
        if L in (0, 2):
            layer2(main_ents)
        if L in (0, 3):
            layer3(s, main_ents)
        if L == 0 and not args.watch:
            footer()
        print(col("d", "─" * 74))
        print(col("d", "  full evidence: docs/RESULTS.md · "
              "spec/questions.md · data/benchmark-scorecard.json\n"))

    if not args.watch:
        render()
        return 0
    import time
    try:
        while True:
            sys.stdout.write("\033[2J\033[H")
            render()
            time.sleep(args.watch)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
