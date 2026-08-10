# Metrics & Scoring Specification v1.0

Companion to *Real-Time Video AI — Comparative Evaluation Plan*. This document operationalises every metric: what is measured, with what instrument, in what units, and how a raw measurement becomes a score.

**Rule:** if a dimension in the plan does not have an entry here, it cannot be scored. No dimension is graded on impression alone.

---

## Part A — Run outcome taxonomy

Every run is classified into exactly one outcome before any scoring happens. This classification is what makes reliability measurable rather than assumed.

| Outcome | Definition | Enters quality scoring? |
|---|---|---|
| **S — Success** | Stream established, ran to intended duration, produced continuous output | Yes |
| **D — Degraded** | Completed, but with a defined defect: >5% dropped frames, resolution downgrade, or ≥1 s output freeze | Yes, **and** flagged |
| **F — Failed** | Stream never established, crashed, or terminated before intended duration | No |
| **T — Timeout** | No first frame within 30 s of request | No |
| **R — Refused** | Product declined the prompt/content on policy grounds | No — reported separately as policy finding |
| **E — Environment** | Failure attributable to your rig or local network, not the product | No — discarded, re-run |

Classification is done from logs, not memory, and is recorded before the clip enters the blind rating pool. Category E must be adjudicated honestly — when in doubt whether a failure is yours or theirs, re-run under a clean condition to disambiguate.

---

## Part B — Reliability metrics (measured, with error bars)

### B.1 Definitions

Let `N` = total runs attempted for a product under a given condition, excluding E.

- **Success rate** = `(S + D) / N`
- **Clean success rate** = `S / N`
- **Hard failure rate** = `(F + T) / N`
- **Refusal rate** = `R / N` *(reported separately — a policy characteristic, not a defect)*

### B.2 Confidence intervals — mandatory

Report every rate as a **Wilson score interval at 95%**, never as a bare percentage. Point estimates from small `N` are actively misleading here.

Illustrative width of the interval at `p̂ = 5%`:

| N runs | Observed failures | 95% Wilson CI |
|---|---|---|
| 20 | 1 | ~0.9% – 23.6% |
| 50 | 2.5 → 3 | ~2.1% – 16.5% |
| 100 | 5 | ~2.2% – 11.2% |
| 400 | 20 | ~3.3% – 7.6% |

**The consequence you need to plan around:** with `N = 20` you cannot distinguish a 5% failure rate from a 20% one. To claim "Product A is more reliable than Product B" when the true rates are 5% vs. 0.5%, you need runs in the high hundreds per product — which is almost certainly out of budget.

**Therefore, the honest reporting posture is:**

1. Report `N`, the raw counts, and the CI for every product.
2. Only claim a reliability *difference* between two products when their CIs do not overlap. Otherwise state: "no reliability difference detectable at this sample size."
3. Report the **failure-mode catalogue** — *what* breaks and *how it recovers* — as the primary reliability finding. With feasible `N`, qualitative failure characterisation is more decision-useful than a rate you can't resolve. "Fails by freezing the last frame indefinitely with no error" and "fails by dropping the stream and auto-reconnecting in 2 s" are the same rate and completely different products.

### B.3 Target sample sizes

| Tier | N per product per condition | Resolves |
|---|---|---|
| Minimum viable | 20 | Gross failure only (>25%) |
| Recommended | 50 | Order-of-magnitude differences |
| Strong | 150+ | Differences of ~10 percentage points |

Set `N` by budget, then state in the report what that `N` can and cannot resolve. **[LOCK]**

---

## Part C — Operational metrics

### C.1 Glass-to-glass latency

- **Instrument:** burned-in ms counter, input/output composited in one 60 fps recording
- **Procedure:** sample ≥30 frame-pairs per product per condition, spread across the clip (not consecutive)
- **Raw output:** ms per sample
- **Rig calibration:** subtract measured loopback offset of your capture chain (§5.2 of the plan); record the offset
- **Report:** mean, p50, **p95**, and jitter (σ). p95 is the headline figure — it is what users perceive as "laggy."

**Score mapping is use-case dependent.** Do not use a universal band. Pick one at Phase 0 **[LOCK]**:

| Score | Live interactive (conversation, avatar) | Live production (streaming, VJ) | Near-real-time (preview, offline-ish) |
|---|---|---|---|
| 5 | p95 ≤ 150 ms | p95 ≤ 300 ms | p95 ≤ 1 s |
| 4 | ≤ 250 ms | ≤ 500 ms | ≤ 2 s |
| 3 | ≤ 400 ms | ≤ 1 s | ≤ 4 s |
| 2 | ≤ 700 ms | ≤ 2 s | ≤ 8 s |
| 1 | > 700 ms | > 2 s | > 8 s |

These bands are a **proposal requiring pilot calibration**: run all six at baseline first, then confirm the bands actually separate the field. If every product lands in one band, the bands are wrong.

### C.2 Frame delivery

| Metric | Procedure | Units | Score mapping |
|---|---|---|---|
| Delivered fps | Count output frames ÷ wall-clock duration | fps | Ratio to advertised: 5 = ≥95%, 4 = ≥85%, 3 = ≥70%, 2 = ≥50%, 1 = <50% |
| Dropped/duplicated | Perceptual hash consecutive frames; identical hash = duplicate | % of stream | 5 = <1%, 4 = <3%, 3 = <8%, 2 = <15%, 1 = ≥15% |
| Freeze events | Output frame unchanged ≥500 ms | count + total duration | Report raw; any freeze ≥1 s forces outcome **D** |
| Time-to-first-frame | Request → first output frame | ms, median | Report raw; contextual |

### C.3 Degradation under network stress

Not a single score — a **curve**. For each product, plot p95 latency and clean success rate across C0→C3.

Derived scalar, if a single number is needed:

**Degradation resilience** = `(clean success rate at C2) / (clean success rate at C0)`

| Score | Ratio |
|---|---|
| 5 | ≥ 0.95 |
| 4 | ≥ 0.85 |
| 3 | ≥ 0.70 |
| 2 | ≥ 0.50 |
| 1 | < 0.50 |

---

## Part D — Computed quality proxies

### D.1 The anchoring principle (read this before using any threshold)

Absolute values of LPIPS, CLIP score, and SyncNet are **not comparable across different source content**. A LPIPS of 0.15 means different things on a static face and a fast pan. Published thresholds from papers were calibrated on different datasets and should not be transplanted.

So every computed metric is reported against two **control anchors** run through the identical pipeline:

- **Anchor-0 (floor):** the untransformed source clip. For temporal flicker, this is the noise floor of your own capture chain.
- **Anchor-R (real reference):** a genuinely filmed video of comparable content. For digital humans, a real person reading the same script on camera.

Scores are assigned by **position between anchors**, not by absolute value:

| Score | Position relative to anchors |
|---|---|
| 5 | At or better than Anchor-R |
| 4 | Within 25% of the Anchor-0 → Anchor-R gap, on the good side |
| 3 | Mid-range between anchors |
| 2 | Closer to the degraded end than to Anchor-R |
| 1 | Worse than the worst anchor |

This removes the need for me to assert thresholds I can't defend, and it makes the numbers reproducible on your specific content.

### D.2 Metric definitions

| Metric | Tool | Formula / procedure | Direction |
|---|---|---|---|
| **Temporal flicker** | LPIPS (AlexNet backbone) | Mean LPIPS between frame *t* and *t+1* across the clip, on static regions only (mask out genuine motion using optical flow magnitude < threshold) | Lower better |
| **Motion fidelity** | RAFT optical flow | Mean endpoint error between input flow field and output flow field | Lower better |
| **Identity preservation** | ArcFace | Cosine similarity of face embedding vs. reference frame, computed every 30 frames; report **mean and slope** (slope = drift rate) | Higher better; slope ≈ 0 |
| **Prompt/style adherence** | CLIP ViT-L/14 | Cosine similarity between output frame embedding and prompt text embedding, averaged over clip | Higher better |
| **Lip-sync** | SyncNet | LSE-C (confidence) and LSE-D (distance) | LSE-C higher better, LSE-D lower better |

**Critical for identity preservation:** the *slope* matters more than the mean. A model that starts at 0.9 similarity and ends at 0.6 has drifted badly but may show an acceptable mean. Report both; score on slope.

### D.3 Status of computed metrics

These are **supporting evidence, not verdicts.** They correlate imperfectly with perceived quality and are gameable. Where a computed metric and the human panel disagree, the human panel decides and the disagreement is reported as a finding — it usually means the metric is missing something real.

---

## Part E — Human-rated dimensions: anchored descriptors

Each descriptor is written to be **observable**, so two raters can independently reach the same score. Viewing conditions are fixed: 100% zoom, normal playback speed first, then frame-step permitted for scores 4 vs. 5.

### E.1 V2V — Temporal coherence (weight 30%)

| Score | Observable criterion |
|---|---|
| 5 | No visible flicker, crawl, or boiling on any surface at normal playback across the full 60 s clip. Identity and style stable end to end. |
| 4 | Artifacts detectable only when frame-stepping or pausing. Nothing visible at normal playback. No drift. |
| 3 | Flicker or texture crawl visible at normal playback on flat regions or hair. Mild style drift over 60 s but subject remains recognisably the same. |
| 2 | Persistent boiling or crawl across large areas. Identity or style noticeably shifts within 30 s. |
| 1 | Output unstable frame to frame; subject partially re-forms between frames. |

### E.2 V2V — Structural fidelity (20%)

| Score | Observable criterion |
|---|---|
| 5 | Anatomy, hands, and background geometry correct throughout. Held text/logo remains legible. |
| 4 | One minor geometric error in the clip (e.g. brief finger merge), self-correcting within ~5 frames. |
| 3 | Recurring minor errors, or held text becomes illegible while remaining text-like. |
| 2 | Persistent anatomical errors (wrong finger count sustained >1 s), or background architecture bends. |
| 1 | Geometry unreliable; subject anatomy incoherent. |

### E.3 V2V — Style adherence (15%)

Rated against the **written prompt intent**, recorded before the run.

| Score | Observable criterion |
|---|---|
| 5 | All specified style attributes present and correctly applied. |
| 4 | All attributes present; one applied weakly. |
| 3 | Recognisably the requested style, but ≥1 specified attribute missing or misapplied. |
| 2 | Generic transformation only loosely matching intent. |
| 1 | Style not applied, or unrelated to the request. |

### E.4 V2V — Detail retention vs. hallucination (15%)

| Score | Observable criterion |
|---|---|
| 5 | Fine texture (individual hair strands, fabric weave) preserved and traceable to source. |
| 4 | Texture preserved in structure, slightly smoothed. |
| 3 | Texture plausibly re-synthesised but no longer matches source detail. |
| 2 | Detail regions smoothed to flat areas, or replaced with invented texture. |
| 1 | Detail destroyed or replaced with unrelated content. |

### E.5 V2V — Occlusion / re-entry (10%)

| Score | Observable criterion |
|---|---|
| 5 | Style holds through occlusion and scene cut with no visible re-lock. |
| 4 | Brief re-lock ≤5 frames, cosmetically minor. |
| 3 | Visible re-lock 5–15 frames; style returns correctly. |
| 2 | Re-lock >15 frames, or style returns altered. |
| 1 | Fails to recover; style lost after occlusion. |

### E.6 Generation — Prompt adherence (25%)

Scored against the **checkable assertions** written into each prompt (count, colour, spatial relation).

| Score | Observable criterion |
|---|---|
| 5 | 100% of assertions satisfied and held throughout. |
| 4 | 100% satisfied at some point; ≥1 lapses briefly. |
| 3 | 70–99% of assertions satisfied. |
| 2 | 40–69% satisfied. |
| 1 | <40% satisfied. |

*Record assertion pass/fail individually — this makes the dimension near-objective and audit-proof.*

### E.7 Generation — Physical plausibility (20%)

| Score | Observable criterion |
|---|---|
| 5 | Gravity, collisions, and object permanence all correct. Objects exiting and re-entering frame are unchanged. |
| 4 | One minor violation (slight float, soft collision). |
| 3 | Object permanence fails on re-entry (object returns altered), or repeated soft physics errors. |
| 2 | Objects pass through each other, or appear/vanish without cause. |
| 1 | No coherent physics. |

### E.8 Generation — Long-horizon consistency (20%)

| Score | Observable criterion |
|---|---|
| 5 | At 60 s, scene identity, palette, and layout match the 5 s state. |
| 4 | Minor palette or lighting drift; layout and identity intact. |
| 3 | Noticeable drift; still recognisably the same scene. |
| 2 | Scene has substantially morphed; some original elements survive. |
| 1 | Unrelated to the opening scene. |

### E.9 Generation — Interactive responsiveness (15%)

| Score | Observable criterion |
|---|---|
| 5 | Mid-stream steer takes effect within 1 s, cleanly committed, prior scene coherence retained. |
| 4 | Takes effect within 2 s with a brief transition artifact. |
| 3 | Takes effect within 4 s, or transition visibly blends old and new. |
| 2 | >4 s, or result is a muddled blend of both instructions. |
| 1 | Steer ignored, or stream degrades on steer. |

### E.10 Digital human — Lip-sync (25%)

| Score | Observable criterion |
|---|---|
| 5 | Jaw/lip closure lands on-frame for every /b/, /p/, /m/. No perceptible offset. |
| 4 | Offset ≤1 frame, detectable only on frame-step. |
| 3 | Offset 2–3 frames, noticeable on close viewing; occasional missed plosive closure. |
| 2 | Offset >3 frames, or frequent missed closures — reads as dubbed. |
| 1 | Mouth motion largely unrelated to audio. |

Cross-check against SyncNet LSE-C/LSE-D positioned against Anchor-R (real filmed reference reading the same script).

### E.11 Digital human — Identity stability (20%)

| Score | Observable criterion |
|---|---|
| 5 | Face identical to reference at 60 s; ArcFace slope ≈ 0. |
| 4 | Imperceptible drift; slope shallow, no visible change. |
| 3 | Subtle drift visible only on A/B against frame 1. |
| 2 | Face visibly different by end of clip. |
| 1 | Identity not maintained. |

### E.12 Digital human — Micro-behaviour (20%)

| Score | Observable criterion |
|---|---|
| 5 | Blink rate in natural range with varied intervals; gaze shifts naturally; continuous head micro-movement; idle motion between sentences. |
| 4 | All present; one element slightly mechanical (e.g. metronomic blink interval). |
| 3 | Blinks present but regular; limited gaze variation; head still between sentences. |
| 2 | Rare or absent blinking, fixed stare, or frozen posture during pauses. |
| 1 | Static face outside mouth region. |

*Also compute blink rate (blinks/min) and blink-interval variance — mechanical regularity is a strong uncanny-valley signal and is easy to measure.*

### E.13 Digital human — Expressiveness (15%) and Body/hands (10%)

| Score | Expressiveness | Body & hands |
|---|---|---|
| 5 | Emotional intent readable from face alone, matching script | Gestures aligned to speech emphasis; hands anatomically stable |
| 4 | Intent readable, slightly muted | Minor gesture/speech timing slip |
| 3 | Some expression variation, weakly tied to content | Generic gestures unrelated to emphasis, or brief hand artifacting |
| 2 | Near-constant expression | Frequent hand distortion, or unnaturally static |
| 1 | Talking mask | Hands unusable |

---

## Part F — Aggregation mathematics

**Step 1 — Clip score.** Each rater assigns a 1–5 score per dimension per clip. Clip dimension score = **median** across raters (median, not mean — resists a single outlier rater).

**Step 2 — Dimension score.** `D_i = mean(clip scores for dimension i)` across all clips exercising that dimension. **Also record `min`** across clips. If `min ≤ 2`, the dimension carries a **worst-case flag** in the report, regardless of the mean — a model that is excellent on eight clips and unusable on one is a specific and important product profile.

**Step 3 — Category score.** `C = Σ (w_i × D_i)` where weights sum to 1.0. Result is on the 1–5 scale. Multiply by 20 for a 0–100 presentation if stakeholders prefer it, but keep 1–5 as canonical.

**Step 4 — Rounding.** Report `C` to one decimal place. **Differences below 0.3 are not treated as meaningful** — declare a tie and say so.

**Step 5 — Reliability is reported adjacent, never inside `C`.** Final presentation per product is always the triple:

> **Quality `C` (1–5) | Clean success rate with 95% CI | p95 latency**

**Step 6 — Sensitivity check.** Recompute the ranking with each weight perturbed ±10%. If the ordering changes, report the ranking as unstable and say which weight it hinges on.

---

## Part G — Rater reliability

| Statistic | Method | Interpretation gate |
|---|---|---|
| Inter-rater agreement | Krippendorff's α (ordinal) | α ≥ 0.80 → conclusions stated normally; 0.67–0.80 → stated as tentative; <0.67 → dimension reported as **contested**, no ranking claim |
| Intra-rater consistency | Hidden repeat clip per rater | Deviation >1 point → flag rater, consider re-training on anchors |
| Pairwise ranking | Bradley–Terry on forced-choice data | Produces ordering + confidence for aesthetic dimensions |

Contested dimensions are a legitimate result. "Three trained raters could not agree which of these looked better" tells a decision-maker something true and useful.

---

## Part H — Data schema

One row per run, in `runs.csv`:

```
run_id, timestamp_utc, product, product_version, category, condition_id,
clip_id, prompt_id, account_tier, test_region, network_profile,
outcome (S/D/F/T/R/E), duration_intended_s, duration_actual_s,
ttff_ms, latency_p50_ms, latency_p95_ms, latency_jitter_ms,
fps_delivered, fps_advertised, dropped_pct, freeze_count, freeze_total_ms,
lpips_temporal, flow_epe, arcface_mean, arcface_slope, clip_score,
lse_c, lse_d, blink_rate, blink_interval_var,
capture_path, notes
```

One row per rating, in `ratings.csv`:

```
rating_id, rater_id, session_id, presentation_order, run_id (blinded via hash),
dimension_id, score_1_5, is_hidden_repeat, pairwise_opponent_run_id,
pairwise_winner, timestamp_utc, comment
```

Blinding is enforced by joining on a hash; raters never see `product` until analysis is complete.

---

## Part I — Pilot calibration (do this before the real run) **[LOCK]**

Half a day, and it prevents the most common way this kind of study fails:

1. Run 2 clips × all 6 products at baseline.
2. Check that latency bands (C.1) actually separate the field. If all six land in one band, rewrite the bands.
3. Check that anchored descriptors (Part E) produce rater agreement ≥0.67 on a 3-clip trial. If not, the descriptors are ambiguous — rewrite before spending the real budget.
4. Confirm computed-metric pipelines run end to end and Anchor-0/Anchor-R values are sane.
5. Time one full run cycle, multiply out, and confirm the run matrix fits the schedule. Adjust `N` now, not mid-study.
