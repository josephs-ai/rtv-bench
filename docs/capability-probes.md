# Capability probes — reference-instruction compliance ladder

Registered 2026-08-11 (user proposal). Separate from the frozen E-rubric:
these are CAPABILITY facts ("can it do X at all / how often"), reported in
the product capability matrix with success rates + Wilson CIs, never blended
into quality scores.

## Why

Reference-image support is not binary. Products cluster into tiers, and the
interesting tier is the top one — compositional transfer ("take the clothes
off the man in the picture and put them on ME") — which anecdotally fails
~half the time on products that pass the lower tiers. A graded ladder turns
that anecdote into a measured rate.

## The ladder (each tier scored pass/fail per attempt, N>=10 per tier)

| Tier | Stimulus | Instruction pattern | Passes when |
|---|---|---|---|
| L1 global restyle | text only | "oil painting style" | style visibly applied |
| L2 ref as style | image (style exemplar) | "make it look like this image" | palette/style adopts the ref |
| L3 direct try-on | image (garment, flat) | "put this jacket on me" | garment appears on the live subject |
| L4 cross-subject transfer | image (PERSON WEARING the garment) | "take the jacket off the man in this picture and put it on me" | garment extracted from ref subject and applied to live subject; ref subject NOT copied in |
| L5 negative control | unrelated image | "put this jacket on me" (image contains no jacket) | model refuses/asks/no-ops rather than hallucinating a jacket |

## Protocol

- Fixed reference set (checked into `data/ref-probe/`), fixed instruction
  wordings, both languages (EN + ZH per product's home language finding).
- Same live-session plumbing as `tools/live_ab.py`; each attempt is a fresh
  apply on a running session; outcome judged by a human from the recorded
  pane (pass/fail/partial), VLM judge as the auxiliary second opinion.
- Known per-product paths: Lucy `set_image` (b64 + instruction, docs list
  try-on as a use case); Xmax `context.refImageUrl` (accepted silently but
  NO observable effect in 4-variant probe 2026-08-11 - L2+ likely all-fail
  until that changes; the all-fail row IS the finding).
- Success rates with Wilson 95% CIs; knife-edge rule applies to any
  cross-product comparison.

## Status

- Designed, not yet run. Needs: ref image set (~6 images), ~30 min of live
  sessions per product, human pass/fail judging (fast).
