# RTV-Bench Roadmap

Direction decision (pending reference-run sign-off): **narrow to what we
can be the world's best at — realtime interactive video.** The worlds
track overlaps emerging academic suites (WorldMark, WBench et al.) with
more resources behind them; realtime V2V measured live from real vantages
has no serious owner. On sign-off, Track 2 goes to maintenance mode with
pointers to the academic suites, and every hour goes into Track 1 depth.

## v1.1 — deepen the realtime track

- **Reference-image control (Campaign F) — SHIPPED (Xmax arm)**: ref-driven
  character anchoring / 3-min identity hold / mid-stream switch, measured by
  computational face-similarity timelines against input-person baselines
  (4 refs incl. attribute-transfer and stylized probes). BOTH arms complete
  (65+65 sessions); scored as axis G in spec v1.1. `benchmark_run.py refs`.
- **Hour-scale sessions as first-class**: add 10 / 30 / 60-minute tiers to
  the duration mix. Live-avatar reality is hour-scale; nobody measures it.
- **Absolute quality axis completion**: artifact-burden component restored
  (audit re-runs with per-run keys), so the canonical score's experience
  term stops leaning on identity alone; pairwise stays exhibit-only.
- **Cost & throughput axis — SHIPPED as exhibit 2026-08-18**
  (`tools/cost_report.py`: $/delivered-minute, efficiency; registry Q5.3).
- **Degradation behavior**: shaped-network arms (bandwidth drop mid-session)
  — the machinery (netshape) already exists from the floor studies.
- **Lip-sync / A/V as a scored axis**: instruments exist (FaceMesh offsets,
  missed-closure) but ALL captures are video-only — needs an
  audio-capturing pipeline + speech sessions (registry Q8.2).
- **Finer edit taxonomy in scoring**: surgical vs global restyle split,
  post-edit identity drift, residue over time — the metrics already
  capture these; surface them as sub-scores.

## v1.2 — make it a public benchmark, not a bake-off

Critical path, dependency-ordered (external review concurs): **stimulus
pack → core suite → submission protocol → multi-vantage → governance.**

**FIRST after eval sign-off — consolidate the question registry (user
directive 2026-08-17: "no benchmark scatters their questions").** Today
the benchmark's questions and invocation protocols are scattered across
campaign drivers, code comments, and session notes. Build the single
canonical spec:

- `spec/questions.md` — every question the benchmark asks, one row each:
  question → campaign/arm → stimulus → instrument → metric → record path
  → current answer status. Campaign drivers become executors of this
  registry, not owners of the questions.
- `spec/invocation-playbooks.md` — per-product, the *correct* way to
  drive each capability, with every discovered trap inline (Xmax:
  refImageUrl not refImage, flat-form set(), re-session switch + 4 s
  settle + fresh key, serialize ref work, COS upload accessor; Lucy:
  set_image b64 channel, TURN-TCP; HO: dedicated SDK connect flow).
  A wrong-invocation "failure" is a benchmark bug, not a product finding
  — the playbook is what makes results defensible against that.
- claims_check gains a completeness assertion: every registry question
  either has a recorded answer or an explicit "unanswered" status — no
  silent gaps. **DONE 2026-08-17** (with `GOVERNANCE.md` shipped the same
  day; v1.2 critical path now: multi-vantage remains the only open gate).
Instrument maturation (absolute quality, judge calibration numbers,
hour-scale, A/V, edit taxonomy, cost/degradation) continues as a parallel
non-blocking track - the philosophy and evidence machinery are sound; the
work is making them durable and accessible.

**Status: stimulus pack v1.0 SHIPPED** (`stimulus-pack/manifest.json` +
deterministic builder; sources pinned by sha256, conforms recipe-derived,
edit protocol + world prompts included; the private-likeness reel excluded,
stock-built instrumented reel due in pack v1.1).

- **Frozen stimulus pack**: hashed videos + edit scripts + prompts,
  downloadable; version = part of the spec.
- **Core suite vs extended**: a ≤2-hour, ≤$50 core run anyone can afford;
  campaigns beyond that optional.
- **Submission protocol**: vendors/third parties run the same suite under
  declared vantage + lens rules and contribute results.
- **Multi-vantage**: at minimum CN-residential + one US/EU vantage per run;
  vantage becomes a results dimension instead of a caveat.
- **Public dashboard**: the scorecard JSON already regenerates the report;
  render it as a page that updates per contributed run.
- **Judge calibration in public**: publish inter-rater agreement (α) per
  batch alongside every judged result.

## Standing invariants (never change)

Lens separation · failure attribution with evidence · absolute-only
canonical scores, relative results as exhibits · per-run blinding keys ·
dated snapshots · declared vantage · amendments logged, never silent.

## Deliberately out of scope

- Worlds-track expansion (→ academic suites; our adapter + records remain
  for whoever wants them)
- Offline/non-realtime generation quality (VBench et al. own it)
