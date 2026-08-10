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
rtveval/config.py              credentials and endpoints (env / .env)
rtveval/routing.py             the six products, categories, lens tags
rtveval/rubrics.py             frozen rubric v1.0 + all three weighting variants
rtveval/stats.py               Wilson CIs, aggregation, alpha gate, BT, sweeps
rtveval/latency/base.py        latency as THREE metrics; refuses to mix them
rtveval/latency/impulse.py     V2V primary: impulse cross-correlation
rtveval/latency/blockstrip.py  V2V secondary: frame-index blocks + refs + parity
rtveval/latency/generation.py  generation: send -> first sustained divergence
rtveval/latency/digital_human.py  audio onset -> first lip movement
rtveval/reel/overlay.py        reel instrumentation (PIL; no drawtext needed)
rtveval/providers/reactor.py   Reactor client
tools/reactor_catalog.py       step 1 probe
tools/encoder_contamination.py CRF12-vs-FFV1 LPIPS check (run before Campaign C)
tools/prestage_syncnet.py      clone SyncNet + weights, integrate nothing
tests/                         19 tests against synthetic ground truth
```

## Latency is three metrics, not one

"Glass-to-glass" only literally means anything for V2V. Each category measures
a different interval with a different instrument, and results are not
comparable across categories:

| Category | Interval | Primary instrument |
|---|---|---|
| V2V | input frame -> corresponding output frame | impulse cross-correlation |
| Generation | API send -> first sustained divergence | baseline-relative divergence |
| Digital human | audio onset -> first lip movement | onset pairing |

For V2V, a burned-in marker is destroyed by restyling; a luminance transient is
not. The block strip (frame index, adaptive-threshold references, parity bit) is
the secondary method, trusted on styled clips only after the pilot shows the two
agree on unstyled ones. Validated in `tests/test_latency.py`: impulse recovers a
known lag to within one frame through a gamma-2.2, range-crushed restyle, and
the strip reports *unreadable* rather than a wrong index under the same class of
transform.

## Use-case weights: swept, not blocked

The rubric carries all three weighting variants (live production / offline
stylised / interactive). `stats.variant_sweep()` ranks under each; if the
ordering holds, the use-case question was never load-bearing — if it flips,
the decision rule is the finding.

## Before Campaign C

Run `tools/encoder_contamination.py` on 3–4 pilot clips. It encodes each both
FFV1-lossless and CRF 12, computes inter-frame LPIPS on both, and rules whether
CRF 12 contaminates the flicker metric — with the evidence saved for the
methodology section.

## Environments

- `.venv` — core harness (PyAV, no OpenCV: their bundled ffmpegs conflict in
  one process). `uv venv --python 3.12 .venv && VIRTUAL_ENV=.venv uv pip
  install -r requirements.txt`
- `.venv-metrics` — torch (MPS), LPIPS, RAFT, open_clip, insightface.
  `requirements-metrics.txt`, same pattern.
- Homebrew ffmpeg 8.1.2 has **no drawtext** (built without freetype) — reel
  instrumentation uses PIL instead, which the block strip needs anyway.
- SyncNet is not on PyPI: `tools/prestage_syncnet.py` stages it under
  `third_party/`; integration waits on Vidu S1 access.

## Network conditions on macOS

`tc netem` is Linux; macOS has no netns, so per-lane shaping is replaced by
**time-blocked global phases** (dnctl/pfctl dummynet), with phase boundaries
landing on round boundaries — every product gets identical exposure to every
condition, at the cost of concurrent multi-condition lanes. The condition
recorded per run is the **applied state** (dnctl read-back + live RTT probe
against a session baseline), never the schedule's intention; a failed
verification is rig evidence → E. Day-1 checklist: grant NOPASSWD sudo for
exactly `dnctl` and `pfctl`.

## Overnight caveat (verify day 1)

The virtual camera on macOS is OBS Virtual Camera — GUI-launched. Before the
first unattended window, verify it survives hours without the session dying
(screen lock, App Nap, sleep all disabled). If it freezes, the playhead
positive control catches it (two grabs 1 s apart must differ) and runs
classify E rather than producing garbage.

## Not built yet

Rating tool (blinded presentation, hidden repeats), campaign drivers wiring
queue+adapters+capture together, report document assembly. Routing decisions
wait on the catalog probe.
