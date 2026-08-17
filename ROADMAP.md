# RTV-Bench Roadmap

Direction decision (pending reference-run sign-off): **narrow to what we
can be the world's best at — realtime interactive video.** The worlds
track overlaps emerging academic suites (WorldMark, WBench et al.) with
more resources behind them; realtime V2V measured live from real vantages
has no serious owner. On sign-off, Track 2 goes to maintenance mode with
pointers to the academic suites, and every hour goes into Track 1 depth.

## v1.1 — deepen the realtime track

- **Hour-scale sessions as first-class**: add 10 / 30 / 60-minute tiers to
  the duration mix. Live-avatar reality is hour-scale; nobody measures it.
- **Absolute quality axis completion**: artifact-burden component restored
  (audit re-runs with per-run keys), so the canonical score's experience
  term stops leaning on identity alone; pairwise stays exhibit-only.
- **Cost & throughput axis**: $/streamed-minute and session overhead per
  product, measured from billing during runs (we already learned billing
  models the hard way).
- **Degradation behavior**: shaped-network arms (bandwidth drop mid-session)
  — the machinery (netshape) already exists from the floor studies.
- **Lip-sync / A/V as a scored axis**: instruments exist (FaceMesh offsets,
  missed-closure); needs speech-forward stimulus and anchors.
- **Finer edit taxonomy in scoring**: surgical vs global restyle split,
  post-edit identity drift, residue over time — the metrics already
  capture these; surface them as sub-scores.

## v1.2 — make it a public benchmark, not a bake-off

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
