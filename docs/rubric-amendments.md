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
