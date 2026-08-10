# rtv-eval

Harness for the real-time video AI comparative review. Implements the plan of
record in `docs/`:

| Doc | Governs |
|---|---|
| `final-execution-plan.md` | Scoping, routing, dual-lens rule, run matrix, frozen rubrics |
| `metrics-and-scoring-spec.md` | Every measurement and how it becomes a score |
| `automation-and-scale-addendum.md` | Campaign split, orchestration, capture policy |
| `realtime-video-ai-evaluation-plan.md` | Original full plan (superseded on scoping only) |

## Setup

```sh
cp .env.example .env    # then fill in the keys
```

Nothing to install yet — the catalog probe is stdlib-only and runs on the system
Python 3.9.

## Step 1 — Reactor catalog probe

The first action in the execution plan. Determines routing for all six products
and, critically, whether any model is dual-routed (native + Reactor). A
dual-routed model gives us the sec 2.1 **bridge measurement**; without one, Lens
M and Lens P latency figures cannot be reconciled and the report has to say so.

```sh
python3 tools/reactor_catalog.py          # discovers the catalog path
python3 tools/reactor_catalog.py --all    # also dumps every entry
python3 tools/reactor_catalog.py --path /v1/models
```

Writes `data/reactor-catalog.json` for the reproduction appendix.

## Layout

```
rtveval/config.py            credentials and endpoints (env / .env)
rtveval/routing.py           the six products, categories, lens tags
rtveval/providers/reactor.py Reactor client
tools/reactor_catalog.py     step 1 probe
```

## Not built yet

Adapters, orchestrator, capture rig, auto-classifier, metrics pipeline, rating
tool, analysis. Build order depends on what the probe returns.

## Environment notes

- `ffmpeg` is **not installed** — required for the capture rig and the burned-in
  ms counter (plan sec 5.2).
- System Python is 3.9; the metrics pipeline (LPIPS, RAFT, ArcFace, CLIP,
  SyncNet) will want its own 3.11+ venv.
