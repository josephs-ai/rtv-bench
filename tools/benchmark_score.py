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

    composite(out)

    op = os.path.join(REPO, "data", "benchmark-scorecard.json")
    json.dump(out, open(op, "w"), indent=2)
    print(json.dumps({k: (v if not isinstance(v, dict) else "...")
                      for k, v in out.items()}, indent=1))
    print("full scorecard ->", op)
    return 0


# ============================ composite scoring ============================
# Design: 6 anchored axes -> declared-weight profiles -> hard floors.
# All opinions live in the three structures below; everything else is
# mechanical. Override with --weights <json> to re-editorialize.

AXIS_WEIGHTS = {   # sub-metric weights inside each axis
    "A": {"value_rate": 0.50, "long_value_rate": 0.35, "ttff": 0.15},
    "B": {"pairwise": 0.60, "artifact": 0.40},
    "C": {"drift": 0.55, "face_through_edits": 0.45},
    "D": {"apply": 0.30, "commit": 0.25, "precision": 0.20,
          "hold": 0.15, "transition": 0.10},
    # G Ref control (campaign F): adoption across the full input matrix
    # (crowd/wide/stylized failures pull it down by design), anchored-
    # identity hold, mid-video switch (best documented mechanism:
    # success rate x transition speed), text-edit-on-anchored-character.
    "G": {"adoption": 0.35, "hold": 0.20, "switch": 0.25, "compose": 0.20},
}
EDIT_RELEVANCE = {"garment": 20, "style": 20, "character": 20,
                  "hair": 15, "background": 15, "accessory": 10}
PROFILES = {
    "STREAMER-CN":   {"A": 20, "B": 10, "C": 15, "D": 20, "E": 5, "F": 10,
                      "G": 20},
    "CREATOR-GLOBAL": {"A": 15, "B": 35, "C": 10, "D": 15, "E": 10, "F": 0,
                       "G": 15},
    "LAB":           {"A": 20, "B": 25, "C": 10, "D": 20, "E": 10, "F": 0,
                      "G": 15},
}
FLOORS = [  # (axis, threshold, cap_fn(axis_score), profiles or None=all, label)
    ("A", 40, lambda a: a + 15, None, "reliability floor: total capped at A+15"),
    ("C", 35, lambda c: 55, ["STREAMER-CN"], "identity floor: capped at 55"),
]
# instrumented steady-state latency (ms) where measured; None = axis N/A
LATENCY_MS = {("xmax-x2.0", "P-browser"): 983}   # motion-xcorr, styled, native
# CN-market deployability: direct=100, VPN-viable=50, blocked=0
DEPLOY_CN = {("lucy-2.5", "P"): 50, ("xmax-x2.0", "M"): 50,
             ("xmax-x2.0", "P-browser"): 100}


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _lin(x, worst, best):
    """map x to 0-100 with absolute anchors (works for either direction)."""
    if x is None:
        return None
    return round(_clamp((x - worst) / (best - worst), 0, 1) * 100, 1)


def _log_latency(s, best, worst):
    import math
    if s is None:
        return None
    s = max(s, 1e-3)
    return round(_clamp((math.log(worst) - math.log(s))
                        / (math.log(worst) - math.log(best)), 0, 1) * 100, 1)


def composite(out):
    import glob
    import statistics
    ents = {}   # (product, lens) -> {axis: score or None, subs, coverage notes}

    # ---------- axis A: reliability ----------
    adj = {}
    ap = os.path.join(REPO, "data", "campaign-b", "adjudications.json")
    if os.path.exists(ap):
        adj = {a["run_id"]: a for a in json.load(open(ap))}
    rows_by = collections.defaultdict(list)
    rp = os.path.join(REPO, "data", "campaign-b", "runs.jsonl")
    if os.path.exists(rp):
        for line in open(rp):
            r = json.loads(line)
            o = r["outcome"]
            if r["run_id"] in adj and adj[r["run_id"]]["from"] == o:
                o = adj[r["run_id"]]["to"]
            r["_o"] = o
            rows_by[(r["product_key"], r.get("lens", "?"))].append(r)
    np_ = os.path.join(REPO, "data", "campaign-b-native", "runs.jsonl")
    if os.path.exists(np_):
        for line in open(np_):
            r = json.loads(line)
            r["_o"] = r["outcome"]
            r["ttff_ms"] = (r.get("ttff_s") or 0) * 1000 or None
            rows_by[("xmax-x2.0", "P-browser")].append(r)

    for key, rs in rows_by.items():
        meas = [r for r in rs if r["_o"] in "SDFT"]
        if len(meas) < 10:
            continue
        def vrate(sub):
            n = len(sub)
            return (sum(1 for r in sub if r["_o"] == "S")
                    + 0.5 * sum(1 for r in sub if r["_o"] == "D")) / n if n else None
        longs = [r for r in meas if (r.get("duration_intended_s") or 0) >= 60]
        ttffs = [r["ttff_ms"] for r in meas if r.get("ttff_ms")]
        subs = {"value_rate": _lin(vrate(meas), 0, 1),
                "long_value_rate": _lin(vrate(longs), 0, 1) if longs else None,
                "ttff": _log_latency((statistics.median(ttffs) / 1000)
                                     if ttffs else None, 2.0, 8.0)}
        ents.setdefault(key, {"subs": {}, "notes": []})
        ents[key]["subs"]["A"] = subs
        ents[key]["A_n"] = len(meas)
        ents[key]["A_S"] = sum(1 for r in meas if r["_o"] == "S")

    # ---------- axis B: quality ----------
    pp = os.path.join(REPO, "data", "vlm-judge-b-pairs", "records.jsonl")
    if os.path.exists(pp):
        RW = {"E1": 0.30, "E2": 0.25, "E3": 0.25, "E4": 0.20}
        tal = collections.defaultdict(lambda: collections.defaultdict(
            lambda: [0, 0]))   # prod -> dim -> [wins, total]
        for line in open(pp):
            r = json.loads(line)
            for d, w in r.get("winners_named", {}).items():
                for p in ("lucy-2.5", "xmax-x2.0"):
                    tal[p][d][1] += 1
                    if w == p:
                        tal[p][d][0] += 1
                    elif w == "tie":
                        tal[p][d][0] += 0.5
        for p, lens in (("lucy-2.5", "P"), ("xmax-x2.0", "P-browser")):
            score = sum(RW[d] * (tal[p][d][0] / tal[p][d][1]) * 100
                        for d in RW if tal[p][d][1])
            ents.setdefault((p, lens), {"subs": {}, "notes": []})
            ents[(p, lens)]["subs"].setdefault("B", {})["pairwise"] = round(score, 1)
            ents[(p, lens)]["subs"]["B"]["artifact"] = None
            ents[(p, lens)]["notes"].append(
                "B.artifact N/A (audit blinding key overwritten); B=pairwise only")

    # ---------- axis C: identity ----------
    drift = collections.defaultdict(list)
    for p_ in glob.glob(os.path.join(REPO, "data", "quality-metrics", "B-*.json")):
        m = json.load(open(p_))
        lh = (m.get("long_horizon") or {}).get("early_vs_last")
        if lh is None:
            continue
        if "lucy" in m["run_id"]:
            drift[("lucy-2.5", "P")].append(lh)
        elif "xmax" in m["run_id"]:
            drift[("xmax-x2.0", "P-browser")].append(lh)
    face = collections.defaultdict(list)
    for p_ in glob.glob(os.path.join(REPO, "data", "edit-metrics", "D-*.json")):
        m = json.load(open(p_))
        if m["edit_id"].startswith("character"):
            continue
        s = (m.get("identity") or {}).get("pre_post_face_sim")
        if s is None:
            continue
        lens = "P" if m["product"] == "lucy-2.5" else "P-browser"
        face[(m["product"], lens)].append(s)
    for key in set(list(drift) + list(face)):
        ents.setdefault(key, {"subs": {}, "notes": []})
        ents[key]["subs"]["C"] = {
            "drift": _lin(statistics.median(drift[key]), 0.60, 0.95)
            if drift.get(key) else None,
            "face_through_edits": _lin(statistics.median(face[key]), 0.40, 0.85)
            if face.get(key) else None}

    # ---------- axis D: editing ----------
    em = collections.defaultdict(list)
    for p_ in glob.glob(os.path.join(REPO, "data", "edit-metrics", "D-*.json")):
        m = json.load(open(p_))
        lens = "P" if m["product"] == "lucy-2.5" else "P-browser"
        em[(m["product"], lens)].append(m)
    jrec = {}
    jp = os.path.join(REPO, "data", "edit-judge", "records.jsonl")
    if os.path.exists(jp):
        for line in open(jp):
            r = json.loads(line)
            jrec[r["name"]] = r["verdict"]
    for key, ms in em.items():
        per_type = collections.defaultdict(list)
        for m in ms:
            per_type[m["edit_id"].split("-")[0]].append(m)
        tw = 0.0
        acc = 0.0
        for etype, w in EDIT_RELEVANCE.items():
            rs = per_type.get(etype)
            if not rs:
                continue   # untested type: excluded (weights renormalize)
            js = [jrec.get(r["name"]) for r in rs if jrec.get(r["name"])]
            apply_f = (sum(1 for j in js if j["application"] == "full")
                       / len(js) * 100) if js else None
            commits = [r["commit_latency_s"] for r in rs]
            commit_meds = [c for c in commits if c is not None]
            frac_committed = len(commit_meds) / len(commits)
            commit_score = (_log_latency(statistics.median(commit_meds), 1.5, 8.0)
                            * frac_committed) if commit_meds else 0.0
            prec = [1 - min(r["collateral_index"], 1.0) for r in rs
                    if r.get("collateral_index") is not None]
            holds = [r["stability"]["hold"] for r in rs
                     if r["stability"]["hold"] is not None]
            trans = [1 - min(r["transition"]["transition_glitch_excess"]
                             + r["transition"]["transition_frozen_excess"], 1.0)
                     for r in rs]
            subs = {"apply": apply_f, "commit": commit_score,
                    "precision": statistics.median(prec) * 100 if prec else None,
                    "hold": statistics.median(holds) * 100 if holds else 0.0,
                    "transition": statistics.median(trans) * 100 if trans else None}
            wts = {k: v for k, v in AXIS_WEIGHTS["D"].items()
                   if subs.get(k) is not None}
            if not wts:
                continue
            tot = sum(wts.values())
            tscore = sum(subs[k] * v / tot for k, v in wts.items())
            acc += w * tscore
            tw += w
        ents.setdefault(key, {"subs": {}, "notes": []})
        ents[key]["subs"]["D"] = {"aggregate": round(acc / tw, 1) if tw else None}

    # ---------- axes E, F ----------
    for key, e in ents.items():
        ms = LATENCY_MS.get(key)
        e["subs"]["E"] = {"motion_to_glass":
                          _log_latency(ms / 1000.0, 0.5, 2.5) if ms else None}
        if ms is None:
            e["notes"].append("E N/A (not instrumented on this lens); renormalized")
        e["subs"]["F"] = {"cn_market": DEPLOY_CN.get(key)}

    # ---------- axis G: reference-image control (campaign F) ----------
    # Rows with no usable face samples are no-data (excluded, coverage
    # noted) for adoption/hold/switch; for compose they count as
    # "anchor not kept" (the anchored character is not visibly present).
    ADOPT = lambda r: (r.get("sim_ref_post_mean") is not None
                       and r["sim_ref_post_mean"] >= 0.25
                       and (r.get("sim_input_post_mean") is None
                            or r["sim_input_post_mean"] <= 0.30))
    fsum = os.path.join(REPO, "data", "campaign-f", "metrics", "summary.json")
    fpv = os.path.join(REPO, "data", "campaign-f", "probe-verdicts.json")
    if os.path.exists(fsum):
        frows = json.load(open(fsum))
        pv = json.load(open(fpv)) if os.path.exists(fpv) else {}
        for key, e in ents.items():
            prod, lens = key
            rows = [r for r in frows
                    if r["product"] == prod and r.get("lens") == lens]
            if not rows:
                e["notes"].append("G N/A (campaign F not run on this lens);"
                                  " renormalized")
                continue
            nodata = [r for r in rows if r.get("sim_ref_post_mean") is None
                      and r.get("sim_input_post_mean") is None]
            anch = [r for r in rows if r["arm"] == "anchor"
                    and r not in nodata]
            adoption = (100.0 * sum(ADOPT(r) for r in anch) / len(anch)
                        if anch else None)
            holds = [r for r in rows if r["arm"] == "hold"
                     and not str(r.get("ref", "")).startswith("ref-self")
                     and r not in nodata]
            held = [r for r in holds if ADOPT(r)
                    and (r.get("hold_slope_per_min") is None
                         or r["hold_slope_per_min"] >= -0.05)]
            hold = 100.0 * len(held) / len(holds) if holds else None
            sw = [r for r in rows if r["arm"] in ("switch", "chain")
                  and r not in nodata]
            def swrow(r):
                tgt = (r.get("sim_ref2_post_mean")
                       if r.get("ref2") else r.get("sim_ref_post_mean"))
                lat = r.get("switch_latency_s")
                if tgt is None or tgt < 0.25 or lat is None:
                    return 0.0
                return 100.0 * _clamp((15.0 - lat) / 14.0, 0, 1)
            in_session = (sum(swrow(r) for r in sw) / len(sw)
                          if sw else None)
            mech = None
            pve = pv.get("%s (lens %s)" % (prod, lens))
            if isinstance(pve, dict) and pve.get("runs"):
                mech = sum(
                    (100.0 * _clamp((15.0 - m["transition_s"]) / 14.0, 0, 1)
                     if m.get("success") else 0.0)
                    for m in pve["runs"]) / len(pve["runs"])
            switch = (None if in_session is None and mech is None
                      else max(x for x in (in_session, mech)
                               if x is not None))
            comp = [r for r in rows if r["arm"] == "compose"]
            compose = (100.0 * sum(ADOPT(r) for r in comp) / len(comp)
                       if comp else None)
            e["subs"]["G"] = {k: (round(v, 1) if v is not None else None)
                              for k, v in [("adoption", adoption),
                                           ("hold", hold),
                                           ("switch", switch),
                                           ("compose", compose)]}
            e["subs"]["G"]["detail"] = {
                "n_rows": len(rows), "n_nodata_excluded": len(nodata),
                "switch_in_session": (round(in_session, 1)
                                      if in_session is not None else None),
                "switch_mechanism": (round(mech, 1)
                                     if mech is not None else None)}

    # ---------- roll up ----------
    def axis_score(e, ax):
        subs = e["subs"].get(ax)
        if not subs:
            return None
        if ax == "D":
            return subs.get("aggregate")
        if ax in ("E",):
            return subs.get("motion_to_glass")
        if ax == "F":
            return subs.get("cn_market")
        wts = {k: v for k, v in AXIS_WEIGHTS[ax].items()
               if isinstance(subs.get(k), (int, float))}
        if not wts:
            return None
        tot = sum(wts.values())
        return round(sum(subs[k] * v / tot for k, v in wts.items()), 1)

    result = {}
    for key, e in sorted(ents.items()):
        prod, lens = key
        axes = {ax: axis_score(e, ax) for ax in "ABCDEFG"}
        profs = {}
        for pname, pw in PROFILES.items():
            avail = {ax: w for ax, w in pw.items()
                     if axes.get(ax) is not None and w > 0}
            if not avail:
                continue
            tot = sum(avail.values())
            score = sum(axes[ax] * w / tot for ax, w in avail.items())
            caps = []
            for fax, thr, capfn, plist, label in FLOORS:
                if plist and pname not in plist:
                    continue
                if axes.get(fax) is not None and axes[fax] < thr:
                    capped = capfn(axes[fax])
                    if score > capped:
                        score = capped
                        caps.append(label)
            profs[pname] = {"score": round(score, 1),
                            "coverage_pct": round(100 * tot / sum(
                                w for w in pw.values() if w > 0), 0),
                            "caps_applied": caps}
        result["%s (lens %s)" % (prod, lens)] = {
            "axes": axes, "profiles": profs,
            "subs": e["subs"], "notes": e["notes"]}
    # ---------- Track 2 capability composite (canonical score) ----------
    # declared weights: adherence 30 / physics 20 / long-horizon 25 /
    # steering 15 / build-speed 10. Judged medians (1-5 -> 0-100) blended
    # 50/50 with computed metrics where both exist.
    t2 = {}
    try:
        import glob as _g, statistics as _s
        keyf = sorted(_g.glob(os.path.join(REPO, "data", "vlm-judge-key",
                                           "key-*.json")))
        jkey = {}
        for kf in keyf:
            try:
                jkey.update({k: v["item"] for k, v in
                             json.load(open(kf)).items() if "item" in v})
            except Exception:
                pass
        jlat = {}
        jp2 = os.path.join(REPO, "data", "vlm-judge", "records.jsonl")
        if os.path.exists(jp2):
            for line in open(jp2):
                r = json.loads(line)
                jlat[r["blind_id"]] = r
        jsc = collections.defaultdict(lambda: collections.defaultdict(list))
        for bid, r in jlat.items():
            it = jkey.get(bid)
            if not it:
                continue
            for d, obj in (r["result"].get("dimensions") or {}).items():
                if obj.get("assessable") and isinstance(obj.get("score"),
                                                        (int, float)):
                    jsc[it["product_key"]][d].append(obj["score"])
        comp_m = collections.defaultdict(lambda: collections.defaultdict(list))
        for p_ in _g.glob(os.path.join(REPO, "data", "quality-metrics",
                                       "*.json")):
            m = json.load(open(p_))
            rid = m["run_id"]
            pk = ("lingbot" if rid.startswith("lingbot") else
                  "happy-oyster" if rid.startswith("happy-oyster") else None)
            if not pk:
                continue
            lh = (m.get("long_horizon") or {}).get("early_vs_last")
            if lh is not None:
                comp_m[pk]["lh"].append(lh)
        STEER = {"lingbot": 40, "happy-oyster": 90}   # receipts+transport vs fire-and-forget
        BUILD_S = {"lingbot": 55, "happy-oyster": 138}
        import math
        for pk in set(list(jsc) + list(comp_m)):
            def jmed(d):
                v = jsc[pk].get(d)
                return ( _s.median(v) - 1) / 4 * 100 if v else None
            lh_c = (_s.median(comp_m[pk]["lh"]) if comp_m[pk].get("lh")
                    else None)
            lh_c = None if lh_c is None else max(0, min(1, (lh_c - 0.5)
                                                        / 0.4)) * 100
            lh_j = jmed("E8")
            lh = (_s.mean([x for x in (lh_c, lh_j) if x is not None])
                  if (lh_c is not None or lh_j is not None) else None)
            bs = BUILD_S.get(pk)
            bs_score = None if bs is None else max(0, min(1,
                (math.log(240) - math.log(bs)) / (math.log(240)
                                                  - math.log(60)))) * 100
            parts = {"adherence": (jmed("E6"), 0.30),
                     "physics": (jmed("E7"), 0.20),
                     "long_horizon": (lh, 0.25),
                     "steering": (STEER.get(pk), 0.15),
                     "build_speed": (bs_score, 0.10)}
            avail = {k: v for k, v in parts.items() if v[0] is not None}
            tot = sum(w for _, w in avail.values())
            score = sum(s * w / tot for s, w in avail.values())
            t2[pk] = {"score": round(score, 1),
                      "parts": {k: round(v[0], 1) for k, v in avail.items()},
                      "coverage_pct": round(100 * tot / 1.0, 0)}
    except Exception as e:
        t2 = {"error": str(e)[:120]}
    out["track2_composite"] = t2
    # ---------- canonical RTV-Score (per track, absolute-only) ----------
    # Score = 100 * sqrt(D) * (0.40*E + 0.25*I + 0.20*G + 0.15*L)  [v1.1]
    #   D = delivery rate (S + 0.5*Deg)/N, adjudicated, E-excluded (the gate;
    #       sqrt damps vantage influence). Absolute components only - the
    #       pairwise head-to-head is published separately, never in here.
    import math as _m
    # absolute artifact burden per entity from the B-capture audit
    # (latest audit run + its own per-run key)
    art = {}
    try:
        import glob as _g, statistics as _s2
        kf = sorted(_g.glob(os.path.join(REPO, "data", "vlm-judge-key",
                                         "key-*.json")))[-1]
        akey = {k: v["item"] for k, v in json.load(open(kf)).items()
                if "item" in v}
        alat = {}
        for line in open(os.path.join(REPO, "data", "vlm-judge-audit",
                                      "records.jsonl")):
            r = json.loads(line)
            alat[r["blind_id"]] = r
        burden = collections.defaultdict(list)
        for bid, r in alat.items():
            it = akey.get(bid)
            if not it or not isinstance(r.get("result"), dict):
                continue
            rid = it.get("run_id", "")
            ent = ("lucy-2.5 (lens P)" if rid.startswith("B-lucy") else
                   "xmax-x2.0 (lens P-browser)" if rid.startswith("B-xmax")
                   else None)
            if not ent:
                continue
            ws = r["result"].get("windows") or []
            if ws:
                b = _s2.mean(sum(f.get("severity", 0) for f in
                                 w.get("findings", [])) for w in ws)
            else:
                b = sum(f.get("severity", 0)
                        for f in r["result"].get("findings", []))
            burden[ent].append(b)
        for ent, v in burden.items():
            med = _s2.median(v)
            # anchor: 0 burden -> 100; 18 (schema max: 6 findings x sev3
            # per window) -> 0. Observed meds ~12-14 on the hard reel
            # workload - both products artifact heavily there; that is a
            # finding, not a bug in the anchor.
            art[ent] = {"burden_med": round(med, 2), "n": len(v),
                        "score": round(max(0.0, min(1.0, 1 - med / 18.0))
                                       * 100, 1)}
    except Exception as e:
        art = {"error": str(e)[:120]}
    out["artifact_burden"] = art
    out["rtvbench_score"] = {"track1": {}, "track2": {},
        "formula": "100*sqrt(delivery)*(0.40*experience+0.25*interaction"
                   "+0.20*ref_control+0.15*latency); experience = mean("
                   "identity, artifact-burden); absolute components only;"
                   " v1.1 adds ref_control (campaign F)"}
    preserved = {}
    pt = os.path.join(REPO, "data", "campaign-b", "preserved-tally.json")
    if os.path.exists(pt):
        preserved = {k: v for k, v in json.load(open(pt)).items()
                     if isinstance(v, dict)}
    for ent, d in result.items():
        ax = d["axes"]
        rel = preserved.get(ent) or out["reliability"].get(ent)
        if not rel:
            continue
        Dv = (rel["S"] + 0.5 * rel["D"]) / rel["N"]
        a_s = art.get(ent, {}).get("score") if isinstance(art, dict) else None
        c_s = ax.get("C")
        exp = (None if (a_s is None and c_s is None) else
               a_s if c_s is None else c_s if a_s is None
               else round((a_s + c_s) / 2, 1))
        parts = {"experience": (exp, 0.40),
                 "interaction": (ax.get("D"), 0.25),
                 "ref_control": (ax.get("G"), 0.20),
                 "latency": (ax.get("E"), 0.15)}
        avail = {k: v for k, v in parts.items() if v[0] is not None}
        if not avail:
            continue
        tot = sum(w for _, w in avail.values())
        core = sum(s / 100.0 * w / tot for s, w in avail.values())
        out["rtvbench_score"]["track1"][ent] = {
            "score": round(100 * _m.sqrt(Dv) * core, 1),
            "delivery": round(Dv, 3),
            "coverage_pct": round(100 * tot, 0)}
    if isinstance(t2, dict):
        BUILD_OK = {"lingbot": 21 / 23, "happy-oyster": 11 / 13}
        for pk, v in t2.items():
            if not isinstance(v, dict) or "parts" in v is None:
                pass
            if not isinstance(v, dict) or "parts" not in v:
                continue
            pr = v["parts"]
            w = {"adherence": 0.35, "long_horizon": 0.25,
                 "physics": 0.20, "steering": 0.20}
            avail = {k: pr[k] for k in w if pr.get(k) is not None}
            tot = sum(w[k] for k in avail)
            core = sum(pr[k] / 100.0 * w[k] / tot for k in avail)
            B = BUILD_OK.get(pk, 1.0)
            out["rtvbench_score"]["track2"][pk] = {
                "score": round(100 * _m.sqrt(B) * core, 1),
                "build_success": round(B, 2),
                "build_speed_s_exhibited": (55 if pk == "lingbot" else 138),
                "coverage_pct": round(100 * tot, 0)}

    out["composite"] = {"axis_weights": AXIS_WEIGHTS,
                        "edit_relevance": EDIT_RELEVANCE,
                        "profiles": PROFILES,
                        "floors": [f[4] for f in FLOORS],
                        "entities": result}
    return out


if __name__ == "__main__":
    sys.exit(main())
