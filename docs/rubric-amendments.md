# Rubric Amendment Log

The rubric is pre-registered. It CAN be amended — a rater trial proving the
descriptors ambiguous is a legitimate reason — but never silently: every
change is an entry here, with reasoning, and bumps `RUBRIC_VERSION`.
`tests/test_stats.py::test_amendment_log_matches_code` fails if the code's
version has no matching entry, so a silent edit cannot pass CI.

Format per entry (newest first):

## v<version> — <YYYY-MM-DD>

- **What changed:**
- **Why:** (the evidence that forced it — e.g. rater-trial alpha, band collapse)
- **What had already been collected under the previous version:** (and whether
  it is re-scored or reported under the old version)

---

## v1.1 — 2026-08-11

- **What changed:** AV lip-sync measurement (global offset + missed-closure
  rate, `rtveval/av_sync.py`) extended beyond the digital-human category to
  V2V products, as **supporting evidence only** — E-dimension weights are
  untouched, and no V2V dimension is scored from it. Anchor framing per D.1:
  Anchor-0 = untransformed source through our capture chain, Anchor-R = real
  filmed reading. Also added as supporting metrics: VLM-judge scores (gated
  on Krippendorff alpha >= 0.67 vs the human panel, auxiliary column only),
  VBench-protocol flicker/subject-consistency, motion-jerk (E.7 proxy),
  long-horizon embedding consistency (E.8 proxy), steer-commitment (E.9
  proxy).
- **Why:** V2V inputs are speaking-person clips (S1 script); a restyle that
  destroys plosive closures reads as dubbed even at zero offset, and nothing
  in the frozen v1.0 metric set could catch it. Digital-human access (Vidu,
  PixVerse) remains gated, but the failure mode exists in products we CAN
  test. Supporting-evidence placement keeps hard rule 1 intact: no weight or
  descriptor changed.
- **What had already been collected under the previous version:** All latency
  and floor data - unaffected (different layer). No human ratings collected
  yet, so no re-scoring arises.

---

## v1.0 — 2026-08-10

- **What changed:** Initial pre-registration. Dimensions, weights (all three
  use-case variants), anchored descriptors per Spec Part E.
- **Why:** Frozen before first run, per hard rule 1.
- **What had already been collected under the previous version:** Nothing —
  this is the freeze point.

## Amendment 2 — 2026-08-17 — Benchmark v1.0 → v1.1: reference-image control axis (G)

- **What changed:** New scored axis **G — Reference-image control**
  (campaign F), computed from face-similarity timelines: adoption 0.35
  (full input matrix: 4 refs × 4 framings; crowd/wide/stylized failures
  count against), hold 0.20, mid-video switch 0.25 (best documented
  mechanism: success rate × transition-speed factor, anchor 1 s→15 s),
  compose 0.20 (text edit on anchored character, anchor-kept, strict
  machine version). Canonical Track-1 core reweighted:
  `0.45·experience + 0.35·interaction + 0.20·latency` →
  `0.40·experience + 0.25·interaction + 0.20·ref_control + 0.15·latency`.
  Profiles rebalanced to include G (STREAMER-CN 20, CREATOR-GLOBAL 15,
  LAB 15).
- **Why:** Reference-driven character control is the selling interaction
  of the preset-character product sector; the 2026-08-17 dedicated
  campaign (65 sessions/product) made it measurable with absolute
  anchors. Leaving it out of the score would misrepresent the sector.
- **What had already been collected under the previous version:** The
  full reference run. v1.0 scores (Lucy 53.2 / Xmax 43.1; profiles
  73.9/85.8/79.2 vs 62.4/39.9/48.7) remain re-derivable from the same
  journals by reverting the weights; v1.1 scores supersede them in all
  shipped docs.

## Amendment 3 — 2026-08-19 — Benchmark v1.1 → v1.2: switch quality weighs equal to switch success

- **What changed:** Axis G's mid-video-switch sub-metric becomes
  `0.5·(success × transition-speed) + 0.5·judged-quality`, where quality
  is the campaign-D 5-dim edit judge applied to switch captures
  (transition .5 / collateral .3 / stability .2, over switches that
  succeeded). Division of labour is explicit: face-similarity verifies
  the RIGHT character took (the judge never sees the ref portrait); the
  judge scores how CLEANLY it happened. New instrument:
  `tools/f_switch_judge.py` → `data/edit-judge/f-switch-records.jsonl`
  (32 blinded judgments over F3/F5 + mechanism probes).
- **Why:** User directive — a switch that lands but visibly breaks the
  stream is not equal to a clean one; "did it" without "how well" is
  half a measurement. First data confirms the gap matters: Lucy's
  in-session switches apply but rough (transition severity to 3/3);
  Xmax's re-session switches are clean (1–2).
- **What had already been collected:** all v1.1 numbers remain
  re-derivable (drop the quality term). v1.1→v1.2 deltas: Lucy switch
  43.4→44.8, axis G 40.7→41.0; Xmax switch 56.1→58.0, axis G 50.5→51.0;
  canonical 47.0→47.1 / 42.5→42.6.
