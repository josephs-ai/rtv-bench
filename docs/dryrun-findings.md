# Rating-tool dry run — findings log (2026-08-11)

Purpose of the dry run: usability of the rating tool and sanity of the
stimulus protocol — NOT rubric calibration. Rater: joseph (author; his
scores never enter any product analysis).

## Finding 1 — dead server is invisible
Killed server left the rating page silently frozen (no error, no hint).
**Fixed same day**: page shows "SERVER NOT RUNNING - rerun ..." and polls
for the server's return; progress resumes from the journal.

## Finding 2 — contradictory i2v stimulus
LingBot static clip prompted "ceramic bowls on a wooden table" over a
LANDSCAPE seed image (i2v: seed pins content). Rater correctly reported
"the bowl part didn't make sense - it was just a brown box" - that box is
our seed's structure. Consequences:
- E6 (prompt adherence) on that clip is an artefact of our protocol, not a
  product measurement — excluded from any interpretation;
- pilot prompts for i2v products now describe continuations of the seed
  (`PROMPTS_I2V` in tools/generation_pilot.py);
- **Campaign C stimulus design rule**: every i2v prompt ships with a
  matching seed image, and the seed+prompt pair is the stimulus of record
  (identical policy for every i2v product). Text-only products keep
  text-only stimuli; cross-contract comparison already prohibited.

## Finding 3 — candidate rubric gap (generation visual fidelity)
Severe mosaic/patchy blur has no dedicated generation dimension (V2V has
E4; generation routes it indirectly through E7/E8). If raters keep
reaching for a missing "visual fidelity" axis, propose a v1.2 amendment
BEFORE the alpha trial.
