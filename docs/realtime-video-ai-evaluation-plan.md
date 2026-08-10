# Real-Time Video AI — Comparative Evaluation Plan

**Products under test (6, across 3 categories)**

| Category | Product |
|---|---|
| Real-time video-to-video | Xmax X2.0 |
| Real-time video-to-video | Decart Lucy 2.5 |
| Real-time video generation | Pixverse R1 |
| Real-time video generation | LingBot World 2 (Ant) |
| Real-time video generation | Happy Oyster (Alibaba) |
| Real-time digital human | Vidu S1 (Shengshu) |

**Document status:** plan of record. Sections marked **[LOCK]** must be decided and frozen *before* any test data is collected. Sections marked **[OPEN]** need input from you or your stakeholder.

---

## 1. Objective and scope

Produce a defensible, reproducible comparative review of six real-time video AI products, covering (a) whether they work, (b) how fast they work, and (c) how good the output is when they work.

**In scope:** output quality, latency and real-time behaviour, robustness under degraded network, reliability, cost and operational limits.

**Out of scope (state explicitly in the report):** model internals, training data provenance, long-term roadmap, enterprise SLA negotiation, and any capability only available under a contract you don't hold.

**Fairness constraint that governs everything below:** the three categories do **not** share a rubric. A digital human and a V2V model are not graded on the same axes, and no cross-category composite score is produced. Ranking happens *within* category only.

---

## 2. Governing principles

1. **Pre-registration.** Rubric dimensions, weights, and the anchored scale are written and frozen before the first test run. This is the single strongest defence against "you just preferred the one you liked." Version the rubric file and cite the version in the report.
2. **Identical inputs.** Every product in a category receives byte-identical source video, prompts, and audio. Delivered via virtual camera / virtual audio device.
3. **Quality is scored conditional on success.** Failed, timed-out, or refused runs are excluded from quality scoring and reported separately as a reliability figure. Never blend the two into one number.
4. **Blind, randomised rating.** Branding stripped, order randomised, raters do not know which product produced which clip.
5. **Everything is logged.** Raw captures, timestamps, network conditions, account tier, region, and time of day are retained so a third party could reproduce the run.

---

## 3. Timeline

Two variants. Pick one and tell the stakeholder which, because they imply very different confidence levels.

### 3A. Full plan — 15 working days (recommended)

| Days | Phase | Output |
|---|---|---|
| 1–2 | Phase 0 — Decisions, accounts, ToS review | Frozen rubric v1.0, accounts provisioned |
| 3–4 | Phase 1 — Harness build and validation | Working rig, calibration proof |
| 5 | Phase 2 — Stimulus corpus production | Test reel, prompt set, scripts |
| 6–9 | Phase 3 — Execution (all runs, all conditions) | Raw capture library |
| 10–11 | Phase 4 — Objective metric computation | Metrics table |
| 12–13 | Phase 5 — Blind human rating sessions | Rater scoresheets |
| 14 | Phase 6 — Analysis | Ranked results, agreement stats |
| 15 | Phase 7 — Report writing | Final deliverable |

### 3B. Compressed — 5 working days

Cut: repetitions from 3→2, degraded-network conditions from 3→1 (100 ms / 1% loss only), raters from 3→2, long-horizon tests from 60 s→30 s. Keep everything else. State the reduced scope in the report's methodology section as a stated limitation — do not quietly drop it.

---

## 4. Phase 0 — Decisions to lock **[LOCK]**

Complete this table before touching a product.

| Decision | Why it matters | Status |
|---|---|---|
| Rubric weights per category (§8) | Determines the ranking; must be set blind to results | **[OPEN]** |
| Test region / server proximity | Dominant latency confounder; hold constant or vary deliberately and report | **[OPEN]** |
| Account tier per product | Free vs. paid tiers differ in queue priority, resolution, concurrency. Match tiers or disclose the mismatch | **[OPEN]** |
| ToS review for automated access | Scripted UI access can breach terms and get accounts banned mid-evaluation | **[OPEN]** |
| Rater panel (≥3, ideally incl. one non-technical) | Inter-rater agreement is a reportable result | **[OPEN]** |
| Test window (time of day / weekday) | Shared inference capacity varies by load; hold constant | **[OPEN]** |

**Legal/compliance note:** review each product's terms before automating, and before publishing benchmark results — some providers restrict published comparative benchmarking. If this report will circulate outside your organisation, get that cleared early rather than at review stage.

---

## 5. Phase 1 — Test harness

### 5.1 Virtual camera (mandatory for V2V and digital human)

Feed a file, not a webcam, so every product sees the same pixels.

- **Linux:** `v4l2loopback` + `ffmpeg` piping the test reel to `/dev/video0`
- **macOS / Windows:** OBS Virtual Camera; audio via BlackHole (macOS) or VB-Cable (Windows)

Validate before use: record the virtual camera output directly and confirm it is frame-identical to the source file.

### 5.2 Latency instrumentation

- Burn a **running millisecond counter** into every frame of the source reel.
- Compose input and product output side by side in a single OBS canvas; record at 60 fps.
- Glass-to-glass latency = visible timestamp difference, read frame by frame.
- **Fallback for fully closed products:** film the screen at 240 fps on a phone, showing a hardware millisecond timer next to the display.
- **Calibrate the rig itself:** measure the loopback latency of your own capture chain (camera → canvas → recording, with no product in the path) and subtract it. Document this offset in the report.

### 5.3 Network shaping

`tc netem` (Linux), Network Link Conditioner (macOS), or Clumsy (Windows).

| Condition | RTT | Packet loss |
|---|---|---|
| C0 — Baseline | native | 0% |
| C1 — Good remote | 50 ms | 0.5% |
| C2 — Typical | 100 ms | 1% |
| C3 — Poor | 200 ms | 2% |

### 5.4 Do **not** test inside a VM

Guest-OS screen capture and compositing add variable delay and will corrupt latency figures. Use VMs only for account isolation or deliberate multi-region testing — never for timing measurement.

### 5.5 Automation

Split by API availability:

- **Products with a streaming API:** script end to end; log request/response timestamps directly.
- **UI-only products:** Playwright (web) or Appium (mobile), *subject to the ToS check in Phase 0*. If automation is disallowed, fall back to manual runs with a documented click-sequence checklist so runs stay consistent.

---

## 6. Phase 2 — Stimulus corpus

### 6.1 V2V test reel (~10–15 s per clip)

Each clip isolates one stressor:

| ID | Clip | Stresses |
|---|---|---|
| V1 | Static face close-up, even light | Baseline identity, skin texture |
| V2 | Fast head/body motion | Motion tracking, smear |
| V3 | Hand occluding face, then removed | Occlusion recovery |
| V4 | Hard lighting change mid-clip | Exposure adaptation |
| V5 | Second person enters frame | Multi-subject handling |
| V6 | Fine texture — hair, mesh fabric | Detail vs. hallucination |
| V7 | Printed text / logo held to camera | Structural fidelity (brutal test) |
| V8 | Rapid horizontal pan | Temporal coherence, background boiling |
| V9 | Hard scene cut | Re-lock time after discontinuity |
| V10 | **60 s sustained single take** | Long-horizon drift (the differentiator) |

Apply 3 style prompts per clip, spanning easy → hard: (a) modest grade/filter, (b) distinct stylisation, (c) aggressive domain transfer.

### 6.2 Generation prompt set

Write prompts with **checkable assertions** so adherence is scored objectively, not by vibes.

| ID | Prompt type | Example structure |
|---|---|---|
| G1 | Object count + colour + spatial relation | "Three red chairs to the left of a tall window" |
| G2 | Physical interaction | Object falls, bounces, settles |
| G3 | Object permanence | Subject exits frame right, re-enters after 5 s |
| G4 | Camera motion | Slow dolly-in on a fixed scene |
| G5 | Multi-entity scene | Several subjects, distinct attributes each |
| G6 | **60 s continuous** | Long-horizon scene consistency |
| G7 | **Mid-stream steer** | Change instruction at t=15 s (interactivity) |

### 6.3 Digital human scripts

- **S1** — Phoneme-dense passage, heavy on plosives (b/p/m) where lip-sync cheats become visible
- **S2** — Emotionally varied passage (neutral → warm → emphatic)
- **S3** — Long-form, 60 s+, for identity drift and idle behaviour between sentences
- **S4** — Second language (Mandarin and English both, if in scope) — sync quality often diverges sharply

Use **identical rendered audio** across products so TTS quality is not confounded with lip-sync quality. If a product only accepts text, note that as a confound in the report.

---

## 7. Phase 4 — Objective metrics

Computed offline from recordings; no subjective input.

### 7.1 Operational

| Metric | Method | Report as |
|---|---|---|
| Glass-to-glass latency | Timestamp diff, ≥30 samples/condition | Mean, p50, **p95**, jitter (σ) |
| Delivered fps vs. advertised | Frame counting | Ratio + shortfall |
| Dropped / duplicated frames | Perceptual frame hashing | % of stream |
| Time-to-first-frame | Request → first output frame | Median |
| Reliability | Failed / timed-out / refused runs ÷ total | **Reported separately, never blended into quality** |
| Degraded-network behaviour | Repeat across C0–C3 | Degradation curve per product |
| Max session length | Run until failure or 10 min cap | Minutes |
| Concurrency limit | Parallel streams until refusal | N streams |

### 7.2 Computed quality proxies

| Metric | Tool | Applies to |
|---|---|---|
| Temporal flicker | LPIPS between consecutive output frames | V2V, generation |
| Motion fidelity | Optical flow endpoint error, input vs. output | V2V |
| Identity preservation | ArcFace cosine similarity to reference, tracked over the full clip | V2V, digital human |
| Prompt/style adherence | CLIP score | V2V, generation |
| Lip-sync | SyncNet LSE-C / LSE-D | Digital human |

Treat these as **supporting evidence, not verdicts.** They correlate imperfectly with perceived quality; the human panel decides aesthetic questions.

---

## 8. Phase 5 — Quality rubrics (conditional on success)

Anchored 1–5 scale. Write anchors out *before* viewing any output.

**Universal anchor definitions:**

| Score | Meaning |
|---|---|
| 5 | Indistinguishable from a competent professional result; ship as-is |
| 4 | Minor artifacts visible only on close inspection; client-deliverable |
| 3 | Visible artifacts on normal viewing; acceptable for social/internal, not client delivery |
| 2 | Obvious failure modes; usable only as rough preview |
| 1 | Unusable output |

### 8.1 Real-time V2V (Xmax X2.0, Lucy 2.5)

| Dimension | Definition | Weight **[OPEN]** |
|---|---|---|
| Style adherence | Executed the requested transformation vs. approximated it | 15% |
| Structural fidelity | Geometry survives — anatomy, hands, architecture, text | 20% |
| **Temporal coherence** | No crawl, boiling, flicker, or identity drift over sustained clips | **30%** |
| Detail retention vs. hallucination | Preserves fine texture rather than smoothing and re-inventing | 15% |
| Occlusion / re-entry handling | Style holds through occlusion and scene cuts | 10% |
| Aesthetic quality | Overall polish, lighting and colour coherence | 10% |

*Temporal coherence carries the largest weight because nearly every model looks acceptable for two seconds; V10 (60 s) is the decisive clip.*

### 8.2 Real-time generation (Pixverse R1, LingBot World 2, Happy Oyster)

| Dimension | Definition | Weight **[OPEN]** |
|---|---|---|
| Prompt adherence | Checkable assertions satisfied (count, colour, spatial relation) | 25% |
| Physical plausibility | Gravity, collisions, object permanence | 20% |
| Long-horizon consistency | Scene remains the same scene at 60 s | 20% |
| Interactive responsiveness | Mid-stream steer is committed to, not blended into mush | 15% |
| Composition & aesthetic | Framing, lighting coherence, colour | 20% |

### 8.3 Digital human (Vidu S1)

| Dimension | Definition | Weight **[OPEN]** |
|---|---|---|
| Lip-sync accuracy | Especially on plosives and phoneme-dense passages | 25% |
| Identity stability | Face embedding similarity held across the full clip | 20% |
| Expressiveness | Face carries emotional intent vs. talking mask | 15% |
| Micro-behaviour | Blink rate/naturalness, gaze, head micro-movement, idle motion | 20% |
| Body & hands | Gesture-to-speech alignment, hand artifacting | 10% |
| Multilingual consistency | Quality parity across languages tested | 10% |

*Micro-behaviour is weighted heavily: it is where uncanny valley actually lives, and it is routinely under-tested.*

---

## 9. Phase 5 — Blind rating protocol

1. **Anonymise.** Strip branding, watermarks, and filenames. Re-encode all clips to identical codec/bitrate/resolution so encoding artifacts don't leak product identity.
2. **Randomise** presentation order per rater.
3. **Pairwise forced choice** for aesthetic dimensions ("A or B") — humans are markedly more reliable at this than at absolute 1–5 scoring. Convert to a ranking with Bradley–Terry if a single ordering is needed.
4. **Anchored absolute scoring** for the technical dimensions (structural fidelity, lip-sync, identity stability), where anchors are concrete enough to be reliable.
5. **≥3 raters.** Include at least one who is not on the technical team.
6. **Report inter-rater agreement** (Krippendorff's α or similar). Disagreement is a finding — "raters split on which of these looks better" is a legitimate and useful result, not something to average away.
7. Include a **hidden repeat** clip per rater to measure intra-rater consistency.

---

## 10. Phase 6 — Analysis

- Per-dimension scores per product; **no cross-category composite**.
- Within-category weighted totals using the frozen weights.
- Reliability reported alongside, never inside, the quality score.
- Latency reported as mean **and p95** — p95 is what users actually feel.
- Degradation curves across C0–C3.
- Sensitivity check: re-run the weighted ranking under ±10% weight perturbation. If the ranking flips easily, say so — that is important information for the reader.
- Flag any dimension where inter-rater agreement was poor and mark those conclusions as low-confidence.

---

## 11. Phase 7 — Report structure

1. **Executive summary** — recommendation per use case, one page
2. **Methodology** — harness, corpus, rubric v1.0, stated limitations
3. **Scoring rubric and weights** (as pre-registered)
4. **Per-product cards** — one page each: strengths, failure modes, scores, representative stills
5. **Within-category head-to-head matrices** (3 tables, no cross-category ranking)
6. **Latency and real-time behaviour** — including degraded-network curves
7. **Reliability and failure-mode catalogue** — the ~5%: what fails, how, and how it recovers
8. **Cost, limits, concurrency** table
9. **Recommendations by use case** — e.g. live streaming vs. offline stylisation vs. avatar presenter
10. **Limitations and threats to validity** — region, tier, test window, sample size, ToS constraints
11. **Appendix** — raw data, per-run logs, full method detail sufficient for reproduction

---

## 12. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Server proximity confounds latency | Hold region constant; disclose test location |
| Account tiers differ across products | Match tiers or disclose the mismatch prominently |
| Automated access breaches ToS → mid-test ban | Phase 0 legal review; manual fallback checklist ready |
| Model updated mid-evaluation | Record product version/build and test date per run; re-test affected runs |
| Rater fatigue skews later scores | Cap sessions at 45 min; randomise order per rater |
| Products refuse certain prompts | Log as refusal, not failure; report content-policy differences as a finding |
| Cherry-picked-looking results | Pre-registration + full raw data appendix |

---

## 13. Deliverables checklist

- [ ] Frozen rubric v1.0 (pre-registered, dated)
- [ ] Validated test harness + calibration record
- [ ] Stimulus corpus (reel, prompt set, scripts, rendered audio)
- [ ] Raw capture library, organised by product × condition × run
- [ ] Objective metrics table (CSV)
- [ ] Rater scoresheets + agreement statistics
- [ ] Final report (§11)
- [ ] Reproduction appendix

---

## 14. Open decisions needed from you **[OPEN]**

1. **Weights** — the §8 figures are a defensible starting proposal, not a decision. They must reflect *your* use case and be signed off before testing.
2. **Primary use case** — live streaming, offline content production, or avatar/presenter? This drives the weights and the final recommendation framing.
3. **Timeline** — full 15-day or compressed 5-day.
4. **Audience** — internal technical team, executive stakeholder, or external publication? Changes tone, length, and the legal review requirement.
5. **Budget** — determines account tiers and how many paid runs are affordable.
6. **Languages** — English only, or Mandarin and English both (materially affects the digital-human section).
