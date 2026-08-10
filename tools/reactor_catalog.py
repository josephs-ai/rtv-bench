#!/usr/bin/env python3
"""Reactor model-catalog probe.

The first action in final-execution-plan.md sec 1: find out which of the six
products Reactor actually serves. If Lucy or Xmax are there, we get a
dual-routed model and therefore the sec 2.1 bridge measurement, without which
Lens M and Lens P latency figures cannot be reconciled.

Usage:
    export REACTOR_API_KEY=...
    export REACTOR_BASE_URL=https://...
    python3 tools/reactor_catalog.py [--path /v1/models] [--all]

Writes data/reactor-catalog.json (raw, for the reproduction appendix) and
data/routing.md (the sec 1 table, updated with what was found).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rtveval import config, routing  # noqa: E402
from rtveval.providers import reactor  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, "data")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--path", help="catalog path, if you know it (skips discovery)")
    ap.add_argument("--all", action="store_true", help="print every catalog entry")
    ap.add_argument("--base-url", help="overrides REACTOR_BASE_URL")
    args = ap.parse_args()

    cfg = config.reactor()
    base = (args.base_url or cfg.base_url or "").rstrip("/")

    if not cfg.api_key:
        print("REACTOR_API_KEY is not set in this shell.", file=sys.stderr)
        return 2
    if not base:
        print("REACTOR_BASE_URL is not set, and no --base-url given.", file=sys.stderr)
        return 2

    print("probing %s ..." % base)
    try:
        result = reactor.fetch_catalog(base, cfg.api_key, path=args.path)
    except reactor.ProbeError as e:
        print("FAILED: %s" % e, file=sys.stderr)
        print("\nRe-run with --path once you know the catalog route.", file=sys.stderr)
        return 1

    entries = result["entries"]
    print("catalog: %s  ->  %d entries across %d page(s)\n"
          % (result["path"], len(entries), result["pages"]))

    hits = {}
    for e in entries:
        for p in routing.match(reactor.entry_text(e)):
            hits.setdefault(p.key, []).append(e)

    print("| Product | Category | Planned route | On Reactor? | Catalog id |")
    print("|---|---|---|---|---|")
    for p in routing.PRODUCTS:
        found = hits.get(p.key, [])
        ids = ", ".join("`%s`" % reactor.entry_id(e) for e in found[:3]) or "—"
        mark = "**yes**" if found else "no"
        print("| %s | %s | %s | %s | %s |" % (p.display, p.category, p.planned_route, mark, ids))

    dual = [k for k in ("lucy-2.5", "xmax-x2.0") if k in hits]
    print()
    if dual:
        names = ", ".join(routing.BY_KEY[k].display for k in dual)
        print("BRIDGE AVAILABLE: %s is reachable on both routes." % names)
        print("Run it identically on native and Reactor to get the Reactor delta")
        print("(final-execution-plan.md sec 2.1). Lens M latency becomes interpretable.")
    else:
        print("NO BRIDGE: no product is dual-routed via Reactor.")
        print("Lens M and Lens P latencies cannot be reconciled — the report must say so")
        print("plainly, and cross-lens claims are confined to quality only (sec 2.1).")

    if args.all:
        print("\n--- full catalog ---")
        for e in sorted(entries, key=reactor.entry_id):
            print("  %s" % reactor.entry_text(e))

    os.makedirs(DATA, exist_ok=True)
    raw_path = os.path.join(DATA, "reactor-catalog.json")
    with open(raw_path, "w") as f:
        json.dump({"base_url": base, "path": result["path"],
                   "pages": result["pages"], "attempts": result["attempts"],
                   "entries": entries}, f, indent=2, sort_keys=True)
    print("\nraw catalog -> %s" % raw_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
