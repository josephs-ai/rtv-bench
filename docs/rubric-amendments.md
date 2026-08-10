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

## v1.0 — 2026-08-10

- **What changed:** Initial pre-registration. Dimensions, weights (all three
  use-case variants), anchored descriptors per Spec Part E.
- **Why:** Frozen before first run, per hard rule 1.
- **What had already been collected under the previous version:** Nothing —
  this is the freeze point.
