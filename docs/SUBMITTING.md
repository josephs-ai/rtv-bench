# Submitting results to RTV-Bench

Anyone — vendor, lab, or third party — can run the suite and contribute a
datapoint. The design principle: **you submit evidence, not numbers.** Our
scorer re-derives your scores from your journals; a submission that can't
be re-derived isn't a result.

## What you run

1. `python3 setup.py` until green.
2. Build the stimulus pack: `tools/build_stimulus_pack.py` — sources must
   hash-verify; note your ffmpeg build (encoder variance is expected and
   recorded, source hashes are the guarantee).
3. Run **`benchmark_run.py core`** (≈2 h, ≈$40) or any full campaign.
4. `benchmark_run.py score`.

## What you submit (a PR or archive)

```
submission/
  vantage.json          region, network type, exit, protocol — honest and
                        specific; "cloud us-east-1 direct" is fine
  environment.json      ffmpeg build, product/SDK versions, run dates
  data/                 the journals + records your run produced
                        (runs.jsonl, adjudications if any, judge records
                        WITH their per-run blinding keys, metric records)
  notes.md              anything you excluded or adjudicated, with reasons
```

No capture videos required (they may contain likenesses; keep them, we may
ask for samples during verification). No scores — we compute those.

## What we do with it

1. Re-run `benchmark_score.py` over your journals — scores must reproduce.
2. Spot-verify: sample judge records against their blinding keys; check
   adjudications carry evidence; sanity-check outcome rates against your
   declared vantage.
3. Published with your vantage as a first-class dimension — never merged
   with other vantages, exactly as lenses never merge.

## Rules that void a submission

- Missing or altered blinding keys (judgments must be re-linkable)
- Journals that don't reproduce the claimed scores
- Undeclared exclusions — excluding runs is *fine* (networks fail), silent
  exclusion is not
- Mixed lenses or mixed vantages in one journal
- A stimulus that doesn't hash-verify

## Adding a product with your submission

Follow "Add a product" in the README; include the adapter in the PR.
Declare the lens honestly (native / aggregator / browser-capture). First
submissions for a new product get extra verification attention — expect
questions.

## Status of this protocol

v0 — accepted via GitHub PRs to this repo, manually verified by the
maintainers. Automation (verification CI, a public dashboard that ingests
accepted submissions) is roadmap v1.2.
