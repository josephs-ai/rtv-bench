# RTV-Bench Governance

How the benchmark changes, who decides, and what a number means over time.

## Versioning

- Spec version lives in `BENCHMARK.md` (currently **v1.2**). The version
  covers: axes and their weights, the canonical formula, stimulus recipes
  and hashes, prompt sets, and the question registry (`spec/questions.md`).
  Changing any of these bumps the minor version; changing what an existing
  score *means* bumps the major version.
- Every scored result carries its spec version. Scores from different
  spec versions are never compared silently — the dashboard and docs
  label the version, and superseded numbers stay re-derivable from the
  same journals with the old weights (see Amendment 2 for the worked
  example: v1.0 → v1.1).

## Amendments

- Any change to rubric, weights, axes, or stimulus goes through
  `docs/rubric-amendments.md`: what changed, why, and what had already
  been measured under the previous version. No silent edits.
- Weights are **declared opinions, structurally overridable**: the scorer
  and dashboard both accept `--weights`, so a disputant re-renders the
  entire board under their own weighting without touching a measurement.
  The measurements are the benchmark; the weights are an editorial layer
  with a byline.

## What makes a result official

1. Produced by the registered campaign drivers executing
   `spec/questions.md` (the registry is the benchmark; drivers are
   executors).
2. Invocations conform to `spec/invocation-playbooks.md` — a
   wrong-invocation failure is a benchmark bug, not a product finding,
   and is retracted the way the 2026-08-15 ref-channel claim was
   (visibly, with the correction machine-verified).
3. Journals reproduce the scores (`benchmark_score.py` re-derivation),
   claims pass `claims_check.py`, blinding keys intact, vantage declared.
4. Failures attributed (product / network / rig) with evidence; network
   faults excluded with their evidence, never silently.

## Submissions & disputes

- Third-party results follow `docs/SUBMITTING.md`: submit evidence, not
  numbers; scores are re-derived, spot-verified against blinding keys,
  and published with vantage as a first-class dimension.
- Disputes about a number: walk the chain (composite → axis → sub-metric
  → run records → blinded verdicts, `tools/dash.py --why <axis>`). If the
  chain doesn't support the number, the number changes and the correction
  is logged — the benchmark's own history contains such retractions on
  purpose (rule: our mistakes are documented in-repo, not scrubbed).
- Disputes about a *question* (what should be measured): propose a
  registry row change via PR; accepted rows enter the next minor version.

## Vendor interaction

- Vendors get defect details privately before publication where a defect
  is fixable (as done with the reference run's SDK trap reports); results
  publish on the benchmark's schedule regardless.
- Vendors may submit under `docs/SUBMITTING.md` like anyone else; their
  first submissions get extra verification attention.

## Maintainers

Current maintainer: the reference-run team. Decisions requiring judgment
(adjudications, amendment acceptance, dispute resolution) are logged with
evidence in-repo. As the contributor base grows, this section is the
place where a steering group and review rotation get defined — governance
grows with the benchmark rather than being invented after a dispute.
