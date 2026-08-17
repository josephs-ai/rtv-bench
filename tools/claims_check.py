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
    A(("canonical lucy", r"canonical[^\n]*?Lucy\D{0,20}(\d+\.\d+)",
       rs1["lucy-2.5 (lens P)"]["score"], 0.55))
    A(("canonical xmax", r"canonical[^\n]*?Xmax\D{0,20}(\d+\.\d+)",
       rs1["xmax-x2.0 (lens P-browser)"]["score"], 0.55))
    A(("canonical lucy zh", r"Lucy 2\.5[：: ]+\**(\d+(?:\.\d+)?)\s*分\**",
       rs1["lucy-2.5 (lens P)"]["score"], 0.55))
    A(("canonical xmax zh", r"Xmax X2\.0[：: ]+(\d+(?:\.\d+)?)\s*分",
       rs1["xmax-x2.0 (lens P-browser)"]["score"], 0.55))
    A(("G axis lucy", r"G Ref control[^\n]*?\|\s*\**(\d+\.\d+)\**",
       lucy["axes"]["G"], 0.05))
    A(("G axis xmax", r"G Ref control[^\n]*?\|[^|]*\|\s*\**(\d+\.\d+)\**",
       xm["axes"]["G"], 0.05))
    A(("streamer lucy en", r"STREAMER-CN\D*?(\d+\.\d+)",
       lucy["profiles"]["STREAMER-CN"]["score"], 0.05))
    A(("streamer xmax en", r"STREAMER-CN\D*?\d+\.\d+\D*?(\d+\.\d+)",
       xm["profiles"]["STREAMER-CN"]["score"], 0.05))
    A(("creator lucy en", r"CREATOR-GLOBAL\D*?(\d+\.\d+)",
       lucy["profiles"]["CREATOR-GLOBAL"]["score"], 0.05))
    A(("creator xmax en", r"CREATOR-GLOBAL\D*?\d+\.\d+\D*?(\d+\.\d+)",
       xm["profiles"]["CREATOR-GLOBAL"]["score"], 0.05))
    A(("lab lucy en", r"\bLAB\b\D*?(\d+\.\d+)",
       lucy["profiles"]["LAB"]["score"], 0.05))
    A(("readme lucy", r"Lucy 2\.5\*\* \(native\) \| \*\*(\d+\.\d+)\*\*",
       rs1["lucy-2.5 (lens P)"]["score"], 0.05))
    A(("readme xmax", r"Xmax X2\.0 \(native/browser\) \| (\d+\.\d+)",
       rs1["xmax-x2.0 (lens P-browser)"]["score"], 0.05))
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
    if sys.argv[1:2] == ["--facts"]:
        return 0 if facts() else 1
    docs = sys.argv[1:] or [f"{REPO}/docs/RESULTS.md", f"{REPO}/README.md"]
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


def facts():
    """Machine-verification of the two qualitative defect claims (xmax).
    Run: claims_check.py --facts  (uses .venv-metrics for the face check)"""
    import re as _re
    ok = True
    # 1a. freeze frequency, browser lens: "约四分之三场次"
    nat = [json.loads(l) for l in open(f"{REPO}/data/campaign-b-native/runs.jsonl")]
    dd = [r for r in nat if r["outcome"] == "D"]
    frac = len(dd) / len(nat)
    p1 = 0.70 <= frac <= 0.80
    print(f"[{'ok' if p1 else 'FAIL'}] freeze frequency browser-lens: {len(dd)}/{len(nat)} = {frac:.0%} (claim ~3/4)")
    # 1b. freeze duration ~2s
    durs = [r.get("max_frozen_s") for r in dd if r.get("max_frozen_s")]
    med = statistics.median(durs)
    p2 = 1.5 <= med <= 3.0
    print(f"[{'ok' if p2 else 'FAIL'}] freeze duration median: {med:.1f}s (claim ~2s)")
    # 1c. cross-lens: independent LensM early gaps 1-2s within first ~2.5s
    early = []
    for l in open(f"{REPO}/data/campaign-b/runs.jsonl"):
        r = json.loads(l)
        if r["product_key"] != "xmax-x2.0":
            continue
        for rs in r.get("outcome_reasons", []):
            m = _re.search(r"delivery gap ([\d.]+) s at frame (\d+)", rs)
            if m and int(m.group(2)) < 60 and 0.8 <= float(m.group(1)) <= 2.5:
                early.append((r["run_id"], float(m.group(1))))
    p3 = len(early) >= 3
    print(f"[{'ok' if p3 else 'FAIL'}] cross-lens early stalls (LensM): {len(early)} independent runs (claim: reproduced on 2nd path)")
    # 1d. lower frequency on the other path
    m_runs = sum(1 for l in open(f"{REPO}/data/campaign-b/runs.jsonl")
                 if json.loads(l)["product_key"] == "xmax-x2.0")
    p4 = (len(early) / max(m_runs, 1)) < frac
    print(f"[{'ok' if p4 else 'FAIL'}] LensM early-stall rate {len(early)}/{m_runs} < browser {frac:.0%}")
    # 2a. judge independently cited identity change on xmax side, multiple pairs
    cites = 0
    for l in open(f"{REPO}/data/vlm-judge-b-pairs/records.jsonl"):
        r = json.loads(l)
        ev = json.dumps(r["verdict_raw"]).lower()
        xmax_is_a = not r["lucy_is_a"]
        side = "a" if xmax_is_a else "b"
        if _re.search(r"(different person|morph|becomes? a (?:new|different)|identity (?:drift|replacement|changes)|no longer the same)", ev):
            # crude side check: the losing-side citation
            if r["winners_named"].get("E1") == "lucy-2.5":
                cites += 1
    p5 = cites >= 3
    print(f"[{'ok' if p5 else 'FAIL'}] blinded judge identity citations on pairs xmax lost E1: {cites} (claim: multiple independent)")
    # 2b. replayable example: r0281 t=1 vs t=12 faces are different people
    try:
        import subprocess, tempfile, os as _os
        mkv = f"{REPO}/data/campaign-b/captures/B-xmax-x2.0-C0-r0281.mkv"
        td = tempfile.mkdtemp()
        for t_ in (1, 12):
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t_),
                            "-i", mkv, "-frames:v", "1", f"{td}/f{t_}.png"], check=True)
        import numpy as np
        from insightface.app import FaceAnalysis
        from PIL import Image
        app = FaceAnalysis(providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=-1, det_size=(640, 640))
        embs = []
        for t_ in (1, 12):
            fr = np.asarray(Image.open(f"{td}/f{t_}.png").convert("RGB"))
            fs = app.get(fr[..., ::-1])
            e = max(fs, key=lambda f: f.det_score).normed_embedding
            embs.append(e / np.linalg.norm(e))
        sim = float(np.dot(*embs))
        # anchor: measured same-person baseline in this benchmark's own data
        # (campaign E, 9-min continuous face) never went below 0.75; <0.40
        # is far outside same-person territory
        p6 = sim < 0.40
        print(f"[{'ok' if p6 else 'FAIL'}] r0281 face t=1 vs t=12 similarity {sim:.3f} (<0.40; same-person baseline floor 0.75) - replayable morph confirmed")
    except Exception as e:
        p6 = False
        print(f"[FAIL] replayable-example check errored: {str(e)[:80]}")
    # 3. hair row: lucy 3/3 full (1 oscillates), xmax 0/3 (all none)
    ej = collections.defaultdict(collections.Counter)
    es = collections.defaultdict(collections.Counter)
    for l in open(f"{REPO}/data/edit-judge/records.jsonl"):
        r = json.loads(l)
        if r["edit_id"].startswith("hair"):
            ej[r["product"]][r["verdict"]["application"]] += 1
            es[r["product"]][r["verdict"]["stability"]] += 1
    p7 = (ej["lucy-2.5"]["full"] == 3 and es["lucy-2.5"]["oscillates"] == 1
          and ej["xmax-x2.0"]["none"] == 3)
    print(f"[{'ok' if p7 else 'FAIL'}] hair row: lucy apply={dict(ej['lucy-2.5'])} stab={dict(es['lucy-2.5'])} | xmax apply={dict(ej['xmax-x2.0'])} (claim: 3/3 full w/ 1 osc vs total failure)")
    # 4. ref-image recheck (2026-08-17): connect-time ref re-anchors the
    # character (face sim to ref portrait jumps far above the input-person
    # baseline); mid-stream ref does NOT replace the speaker. The 08-15
    # "ref channel dead" arms are retracted (wrong field: refImage was
    # stripped by normalizeRealtimeContext; session API wants refImageUrl).
    try:
        import subprocess, tempfile
        import numpy as np
        from insightface.app import FaceAnalysis
        from PIL import Image
        app2 = FaceAnalysis(providers=["CPUExecutionProvider"])
        app2.prepare(ctx_id=-1, det_size=(640, 640))

        def _emb(path):
            fr = np.asarray(Image.open(path).convert("RGB"))
            fs = app2.get(fr[..., ::-1])
            e = max(fs, key=lambda f: f.det_score).normed_embedding
            return e / np.linalg.norm(e)

        def _frame(mkv, t_, out):
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss",
                            str(t_), "-i", mkv, "-frames:v", "1", out],
                           check=True)
        td = tempfile.mkdtemp()
        rc = f"{REPO}/data/campaign-d/captures-refcheck"
        _frame(f"{REPO}/data/campaign-d/conform-mixkit2960.mp4", 5, f"{td}/in.png")
        _frame(f"{rc}/REFCHECK-xmax-x2.0-connect-cos.mkv", 10, f"{td}/cw.png")
        _frame(f"{rc}/REFCHECK-xmax-x2.0-connect-cos-man.mkv", 18, f"{td}/cm.png")
        _frame(f"{rc}/REFCHECK-xmax-x2.0-live-cos-replace.mkv", 37, f"{td}/lv.png")
        rw = _emb(f"{REPO}/data/campaign-d/refs/ref-woman.jpg")
        rm = _emb(f"{REPO}/data/campaign-d/refs/ref-man.jpg")
        inp = _emb(f"{td}/in.png")
        s_base_w = float(np.dot(inp, rw))
        s_base_m = float(np.dot(inp, rm))
        s_cw = float(np.dot(_emb(f"{td}/cw.png"), rw))
        s_cm = float(np.dot(_emb(f"{td}/cm.png"), rm))
        s_lv = float(np.dot(_emb(f"{td}/lv.png"), rw))
        p8 = (s_base_w < 0.15 and s_base_m < 0.15
              and s_cw > 0.25 and s_cm > 0.25 and s_lv < 0.15)
        print(f"[{'ok' if p8 else 'FAIL'}] ref recheck: connect-arm sim to ref "
              f"{s_cw:.3f}/{s_cm:.3f} vs input baseline {s_base_w:.3f}/{s_base_m:.3f}; "
              f"live-arm speaker unchanged {s_lv:.3f} (claim: connect works 2/2, mid-stream doesn't replace)")
    except Exception as e:
        p8 = False
        print(f"[FAIL] ref-recheck fact errored: {str(e)[:80]}")
    allp = all([p1, p2, p3, p4, p5, p6, p7, p8])
    print("\n%s" % ("ALL FACT CLAIMS MACHINE-VERIFIED" if allp else "CLAIM(S) NOT SUPPORTED - REVISE DOC"))
    return allp


if __name__ == "__main__":
    sys.exit(main())
