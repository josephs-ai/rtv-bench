# RTV-Bench v1.1 — Realtime Video AI Benchmark

A repeatable benchmark for **live** video AI products, born from the 2026-08
six-product evaluation. It measures what realtime products actually sell:
staying up, looking right, reacting fast, and taking mid-stream direction.

## What it measures

| Track | Campaign | Question |
|---|---|---|
| V2V reliability | B | Does a live session survive 15 s / 60 s / 3 min? (S/D/F/T/R/E outcomes, Wilson CIs) |
| V2V quality | B v2 | Same-input blinded pairs: temporal coherence, structure, style adherence, detail (+ artifact audit with onset times) |
| Live editing | D | Mid-stream instruction at t=15 s: commit latency, targeting precision (collateral), residue, transition cost, stability, direction-aware identity |
| Reference-image control | F | Does a ref portrait anchor the live character (adoption, attribute transfer, stylized refs), hold identity over minutes, and switch mid-stream? Computational face-similarity timelines vs input-person baselines |
| World generation | C | Prompt battery with checkable assertions: adherence, physics, permanence, long-horizon hold, steering |
| Platform overhead | bridge | Same model native vs via aggregator → the middleman's ms tax |

## Ground rules (what makes results defensible)

1. **Lens separation** — native-API results (Lens P) and aggregator-routed
   results (Lens M) NEVER share a table. Browser-captured lanes carry their
   own lens label.
2. **Outcome attribution** — every failed run is classified product / network
   / rig, with network-fault (E) runs excluded from all denominators. Three
   layers: pre-launch throughput sentinel, in-run drift/loss guards,
   post-hoc cross-product correlation adjudication (all overrides logged
   with evidence in `data/campaign-b/adjudications.json`).
3. **Blinded judging** — the VLM judge sees shuffled, re-blinded frames with
   schema-forced output and required evidence; trusted only where validated
   against human ratings (Krippendorff α ≥ 0.67). Extreme calls get human
   eyeball verification before entering any report.
4. **Fixed stimulus** — inputs are versioned and hashed; conforms are
   deterministic. Rerunning the benchmark uses bit-identical pixels.
5. **Dated snapshots** — providers hot-deploy. Every run records server
   build strings; results are dated claims, not permanent truths.
6. **Vantage declaration** — results are measured *from somewhere*. The
   vantage (region, exit, protocol) is pinned per campaign and recorded in
   `vantage.json`; comparisons require matching vantage.

## The core suite (affordable reproduction)

`benchmark_run.py core` is the ≤2-hour, ~$40 run that reproduces the
benchmark's shape end-to-end: a 15-round reliability mini (30 sessions),
12 live-edit sessions per product, then the full metrics → judging →
scorecard chain over what it captured. Wider CIs than the full campaigns,
same instruments, same evidence chain, same output format. Use it to
verify a setup, sanity-check a new product adapter, or contribute a
low-cost datapoint from a new vantage. Full campaigns remain the
official-scorecard tier.

## Running it

```bash
# stage list + status
.venv/bin/python tools/benchmark_run.py --list

# individual stages (each resumable, journaled)
.venv/bin/python tools/benchmark_run.py reliability   # campaign B
.venv/bin/python tools/benchmark_run.py quality       # metrics+pairs+audit
.venv/bin/python tools/benchmark_run.py editing       # campaign D (all arms)
.venv/bin/python tools/benchmark_run.py worlds        # campaign C

# consolidated scorecard from all journals
.venv/bin/python tools/benchmark_score.py
```

Requirements: `.venv` (core) + `.venv-metrics` (torch/MPS) as in repo;
provider keys in `.env` (see `.env.example`); for products behind
region/VPN constraints read `docs/` network notes — the harness guards
will hold rather than corrupt when the network is unfit.

## First official scorecard

The 2026-08-15 evaluation (Lucy 2.5, Xmax X2.0, LingBot-World 2, Happy
Oyster) is this benchmark's reference run: results in
`docs/final-report.md`, editing detail in `docs/d-scorecard.md`, all raw
records under `data/`.

## Versioning

Benchmark spec version: **1.1** (adds scored axis G — reference-image
control — see `docs/rubric-amendments.md` Amendment 2; amendments require an
entry in `docs/rubric-amendments.md`). Stimulus recipes and prompt sets are
part of the version — changing either bumps the minor version.
