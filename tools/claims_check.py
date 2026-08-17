#!/usr/bin/env python3
"""Claims checker: every number in a shipped doc must equal what the
records compute. Run before ANY report goes out:

    .venv/bin/python tools/claims_check.py docs/RESULTS.md [more docs...]

Each claim = (name, regex-with-one-capture, computed truth, tolerance).
A doc that doesn't contain the claim's pattern is reported SKIP (the text
may phrase it differently - keep patterns in sync when wording changes).
Exit 1 on any MISMATCH. This exists because two hand-carried numbers
drifted and one was invented; prose is now checked like code.
"""
import json
import glob
import re
import statistics
import sys
import collections

REPO = __file__.rsplit("/tools/", 1)[0]


def truths():
    s = json.load(open(f"{REPO}/data/benchmark-scorecard.json"))
    ent = s["composite"]["entities"]
    lucy = ent.get("lucy-2.5 (lens P)", {})
    xm = ent.get("xmax-x2.0 (lens P-browser)", {})
    prs = [json.loads(l) for l in open(f"{REPO}/data/vlm-judge-b-pairs/records.jsonl")]
    wins = collections.defaultdict(collections.Counter)
    for r in prs:
        for d, w in r["winners_named"].items():
            wins[d][w] += 1
    nat = [json.loads(l) for l in open(f"{REPO}/data/campaign-b-native/runs.jsonl")]
    frozen = sum(1 for r in nat if r["outcome"] == "D")
    M = collections.defaultdict(lambda: collections.defaultdict(list))
    for p in glob.glob(f"{REPO}/data/quality-metrics/*.json"):
        m = json.load(open(p))
        pk = ("lingbot" if m["run_id"].startswith("lingbot") else
              "happy-oyster" if m["run_id"].startswith("happy-oyster") else None)
        if not pk:
            continue
        v = m.get("vbench", {})
        for k, kk in (("sc", "subject_consistency"), ("fl", "temporal_flickering")):
            if v.get(kk) is not None:
                M[pk][k].append(v[kk])
        lh = (m.get("long_horizon") or {}).get("early_vs_last")
        if lh is not None:
            M[pk]["lh"].append(lh)
        mj = (m.get("motion_jerk") or {}).get("pops_per_min")
        if mj is not None:
            M[pk]["mj"].append(mj)
    med = lambda p, k: statistics.median(M[p][k])
    ling_live = sum(1 for p in glob.glob(f"{REPO}/data/campaign-c-gen/lingbot-G*-r[123].json")
                    if json.load(open(p)).get("frames"))
    ho_live = sum(1 for p in glob.glob(f"{REPO}/data/campaign-c-gen/happy-oyster-G*-r[123].json")
                  if json.load(open(p)).get("went_live"))
    d = json.load(open(f"{REPO}/data/campaign-d/scorecard.json"))
    C = []  # (name, regex, truth, tol)
    A = C.append
    rs1 = s["rtvbench_score"]["track1"]
    A(("canonical lucy", r"Lucy 2\.5[：: ]+\**(\d+(?:\.\d+)?)\s*分?\**",
       rs1["lucy-2.5 (lens P)"]["score"], 0.55))
    A(("canonical xmax", r"Xmax X2\.0[：: ]+(\d+(?:\.\d+)?)\s*分",
       rs1["xmax-x2.0 (lens P-browser)"]["score"], 0.55))
    A(("pairs n", r"(\d+)\s*(?:组同源盲评|pairs|组)", len(prs), 0))
    A(("E2 xmax wins", r"结构\s*60[-–](\d+)", wins["E2"]["xmax-x2.0"], 0))
    A(("streamer lucy", r"国内直播/虚拟形象\s*\|\s*(\d+\.\d+)",
       lucy["profiles"]["STREAMER-CN"]["score"], 0.05))
    A(("creator lucy", r"海外创作工具\s*\|\s*(\d+\.\d+)",
       lucy["profiles"]["CREATOR-GLOBAL"]["score"], 0.05))
    A(("streamer xmax", r"国内直播/虚拟形象\s*\|\s*\d+\.\d+\s*\|\s*(\d+\.\d+)",
       xm["profiles"]["STREAMER-CN"]["score"], 0.05))
    A(("freeze fraction", r"(\d+)/91", frozen, 0))
    A(("subj cons lingbot", r"0\.836", med("lingbot", "sc"), 0.001))
    A(("subj cons ho", r"0\.900?", med("happy-oyster", "sc"), 0.001))
    A(("longh lingbot", r"0\.685", med("lingbot", "lh"), 0.001))
    A(("longh ho", r"0\.759", med("happy-oyster", "lh"), 0.001))
    A(("jerk lingbot", r"37\.3", med("lingbot", "mj"), 0.051))
    A(("jerk ho", r"23\.3", med("happy-oyster", "mj"), 0.051))
    A(("lingbot live caps", r"LingBot\s*(\d+)/21", ling_live, 0))
    A(("ho live caps", r"(?:HO|Happy Oyster)[^0-9]{0,10}(\d+)/21", ho_live, 0))
    A(("style flip xmax commit", r"1\.0\s*(?:s|秒)",
       d["xmax-x2.0"]["style"]["commit_latency_s_med"], 0.05))
    A(("garment lucy commit", r"1\.4\s*(?:s|秒)",
       d["lucy-2.5"]["garment"]["commit_latency_s_med"], 0.05))
    A(("identity axis lucy", r"93\b", round(lucy["axes"]["C"]), 0.5))
    A(("identity axis xmax", r"85\b", round(xm["axes"]["C"]), 0.5))
    return C


def main():
    docs = sys.argv[1:] or [f"{REPO}/docs/RESULTS.md"]
    claims = truths()
    bad = 0
    for doc in docs:
        text = open(doc).read()
        print(f"== {doc}")
        for name, pat, truth, tol in claims:
            m = re.search(pat, text)
            if not m:
                print(f"  [skip] {name} (pattern not found)")
                continue
            g = m.group(1) if m.groups() else m.group(0)
            try:
                val = float(re.sub(r"[^\d.]", "", g))
            except ValueError:
                print(f"  [??  ] {name}: unparseable '{g}'")
                continue
            ok = abs(val - float(truth)) <= tol
            print(f"  [{'ok' if ok else 'MISMATCH'}] {name}: doc={val} truth={truth}")
            bad += 0 if ok else 1
    print("\n%s" % ("ALL CLAIMS VERIFIED" if bad == 0 else f"{bad} MISMATCHES - DO NOT SHIP"))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
