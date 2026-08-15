# RTV-Bench — a benchmark for realtime video AI products

Live products, live measurements: does a realtime video model **stay up,
look right, react fast, and take mid-stream direction?** RTV-Bench runs
real sessions against real product endpoints — no offline renders, no
cherry-picking — and turns the journals into defensible scores.

**First official scorecard (2026-08): Lucy 2.5 · Xmax X2.0 · LingBot-World 2
· Happy Oyster** — results in [`docs/final-report.md`](docs/final-report.md),
live-editing detail in [`docs/d-scorecard.md`](docs/d-scorecard.md),
consolidated numbers in `data/benchmark-scorecard.json`.

## Composite results (declared-weight profiles, per lens)

| Profile | Lucy 2.5 (native) | Xmax X2.0 (native/browser) |
|---|---|---|
| STREAMER-CN | **74.1** | 62.4 |
| CREATOR-GLOBAL | **86.0** | 39.9 |
| LAB (pure capability) | **79.4** | 48.7 |

Weights are printed with every score and overridable — see
[`BENCHMARK.md`](BENCHMARK.md) for the axes, profiles, floors, and ground
rules (lens separation, outcome adjudication, blinding, vantage
declaration).

## Quickstart

```bash
# environments (two venvs: core streaming vs torch metrics)
python3.12 -m venv .venv && uv pip install --python .venv/bin/python -r requirements.txt
python3.12 -m venv .venv-metrics && uv pip install --python .venv-metrics/bin/python -r requirements-metrics.txt

cp .env.example .env         # add your provider keys

.venv/bin/python tools/benchmark_run.py --list
.venv/bin/python tools/benchmark_run.py reliability   # or quality / editing / worlds
.venv/bin/python tools/benchmark_score.py             # consolidated scorecard
.venv/bin/python tools/benchmark_report.py            # auto-assembled report
```

Every stage is journaled and resumable; rerunning is always safe. The
harness holds rather than corrupts when the network is unfit (throughput
sentinel + in-run guards + post-hoc adjudication).

## Human validation (the judge's leash)

The VLM judge is only trusted where it agrees with humans. The blinded
rating tool serves shuffled clips with hidden repeats to human raters:

```bash
.venv/bin/python tools/rating_session.py   # then open the printed URL
```

Agreement gates (Krippendorff α ≥ 0.67 vs human medians) are enforced by
`rtveval.vlm_judge.validate_against_humans` before judge scores extend
beyond the human-rated sample.

## Adding a product

1. Implement an adapter (`rtveval/adapters/`) satisfying `Adapter`:
   `connect() / run(clip, prompt, duration, condition) / close()`, frames
   surfaced through `frame_tap`. Browser-SDK-only products follow the
   pattern in `tools/xmax_native_lane.py` + `tools/xmax_browser/`.
2. Register it in the relevant campaign driver (`tools/campaign_*.py`).
3. Declare its **lens** honestly (native / middleman / browser-capture) —
   scores never cross lenses.

## Repo map

```
rtveval/     adapters, judges (absolute/pairwise/audit/edit), metrics,
             orchestrator (queue/spend/health/runner)
tools/       campaign drivers, browser lanes, benchmark_{run,score,report},
             rating_session (human panel), conform/stimulus prep
docs/        final report, scorecards, methods, incident reports
data/        append-only journals, adjudications, all analysis records
```

## Provenance

Built 2026-08-10 → 08-15 during a six-product commercial evaluation from a
mainland-China vantage. Everything here was battle-tested against real
provider outages, credit depletions, SDK traps, and VPN weather — the
ground rules exist because each one caught a real mistake.
