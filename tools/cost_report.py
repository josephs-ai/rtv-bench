#!/usr/bin/env python3
"""Cost & throughput report (v1.1 roadmap item) - EXHIBIT, not scored.

    .venv/bin/python tools/cost_report.py

Joins the spend journal (reserve/reconcile rows written during campaign
B) with the run journals to price streaming:

  $/attempted-minute   total reconciled USD / minutes of attempted stream
  $/delivered-minute   same USD / minutes of frames actually received
  $/value-minute       same USD / delivered minutes in S+D sessions
  delivery efficiency  delivered / attempted (the throughput tax)

Lens caveats (printed with the numbers, per ground rule 1):
  lucy-2.5 (P)        native metered billing (Decart) - true unit price
  xmax-x2.0 (M)       Reactor PLATFORM pricing - the aggregator's price,
                      not the vendor's
  xmax-x2.0 (P-browser) vendor-account points (not USD-metered here) - no
                      honest $ figure; excluded rather than guessed

Output: data/cost-report.json + stdout table. Not in the canonical score
(pricing changes faster than capability; an axis needs stable anchors) -
exhibited beside it, wired into dash layer 3.
"""
import json
import os
import sys
import collections

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    spend = collections.defaultdict(float)
    nrec = collections.Counter()
    for l in open(os.path.join(REPO, "data", "campaign-b", "spend.jsonl")):
        r = json.loads(l)
        if r["op"] != "reconcile":
            continue
        rid = r.get("run_id", "")
        base = rid.split("#")[0]
        pk = ("lucy-2.5 (lens P)" if "lucy" in rid else
              "xmax-x2.0 (lens M)" if "xmax" in rid else None)
        if pk:
            spend[pk] += r.get("usd", 0.0)
            nrec[(pk, base)] += 1

    runs = {}
    for l in open(os.path.join(REPO, "data", "campaign-b", "runs.jsonl")):
        r = json.loads(l)
        pk = ("lucy-2.5 (lens P)" if r.get("product_key") == "lucy-2.5"
              else "xmax-x2.0 (lens M)")
        runs[r["run_id"]] = (pk, r)

    agg = collections.defaultdict(lambda: {"att_s": 0.0, "del_s": 0.0,
                                           "val_s": 0.0, "n": 0})
    for (pk, base), _ in nrec.items():
        ent = runs.get(base)
        if not ent or ent[0] != pk:
            continue
        _, r = ent
        dur = r.get("duration_intended_s") or 0.0
        fps = r.get("fps_delivered") or 0
        deliv = (r.get("n_frames") or 0) / fps if fps else 0.0
        a = agg[pk]
        a["n"] += 1
        a["att_s"] += dur
        a["del_s"] += deliv
        if r.get("outcome") in ("S", "D"):
            a["val_s"] += deliv

    out = {"note": __doc__.split("\n\n")[1],
           "caveats": {
               "lucy-2.5 (lens P)": "native metered billing (Decart)",
               "xmax-x2.0 (lens M)": "Reactor platform pricing, not the "
                                     "vendor's unit price",
               "xmax-x2.0 (lens P-browser)": "vendor-account points, not "
                                             "USD-metered - excluded"},
           "entities": {}}
    print("COST & THROUGHPUT (exhibit - reconciled billing joined to "
          "run journals)")
    for pk, a in sorted(agg.items()):
        usd = spend[pk]
        row = {
            "reconciled_usd": round(usd, 2),
            "billed_sessions": a["n"],
            "attempted_min": round(a["att_s"] / 60, 1),
            "value_min": round(a["val_s"] / 60, 1),
            "delivered_min": round(a["del_s"] / 60, 1),
            "usd_per_attempted_min": (round(usd / (a["att_s"] / 60), 3)
                                      if a["att_s"] else None),
            "usd_per_delivered_min": (round(usd / (a["del_s"] / 60), 3)
                                      if a["del_s"] else None),
            "usd_per_value_min": (round(usd / (a["val_s"] / 60), 3)
                                  if a["val_s"] else None),
            "delivery_efficiency_pct": (round(100 * a["del_s"] / a["att_s"], 1)
                                        if a["att_s"] else None),
        }
        out["entities"][pk] = row
        print("  %-24s $%.2f / %d sessions | $/att-min %.3f | "
              "$/deliv-min %s | $/value-min %s | efficiency %s%%"
              % (pk, usd, a["n"], row["usd_per_attempted_min"] or 0,
                 row["usd_per_delivered_min"], row["usd_per_value_min"],
                 row["delivery_efficiency_pct"]))
    print("  %-24s %s" % ("xmax-x2.0 (P-browser)",
                          "vendor-account points - not USD-metered, "
                          "excluded rather than guessed"))
    op = os.path.join(REPO, "data", "cost-report.json")
    with open(op, "w") as f:
        json.dump(out, f, indent=1)
    print("-> %s" % op)
    return 0


if __name__ == "__main__":
    sys.exit(main())
