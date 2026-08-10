# Final Execution Plan v1.0 — Real-Time Video AI Comparative Review

Supersedes the scoping sections of the earlier plan. The *Metrics & Scoring Spec* and *Automation & Scale Addendum* remain in force for measurement detail and orchestration detail respectively.

**Access status as of start:** Decart API ✓ · Reactor API ✓

---

## 1. Coverage and access routing

| Product | Category | Route | Status |
|---|---|---|---|
| Lucy 2.5 | V2V | Decart native API (`@decartai/sdk`) | **Ready** |
| LingBot-World 2 | Generation | Reactor | **Ready** |
| Happy Oyster | Generation | Reactor | **Ready** |
| Xmax X2.0 | V2V | Xmax native API (`@xmaxai/sdk`) | Self-serve — **obtain day 1** |
| PixVerse R1 | Generation | Partner waitlist | Gated — apply + UI fallback |
| Vidu S1 | Digital human | Enterprise beta | Gated — apply + UI fallback |

**First action:** query the Reactor model catalog. If Lucy, Xmax, PixVerse R1, or Vidu S1 are present there, routing changes and §2 gets easier. Do this before building anything.

**Category coverage risk:** if Vidu S1 stays gated and no digital-human product is reachable via API, that category has a sample of one on a manual path — or zero. Say so explicitly in the report rather than padding it.

---

## 2. Decision closed: measurement lens

Two products are Reactor-only, one is native-only. Reactor serves models on **its own GPUs with its own config** — Ant advertises LingBot-World 2 at 720p/60fps; Reactor lists it at 960p/16fps, sub-1s. These are not interchangeable measurements.

**Resolution — dual lens, never mixed in one table:**

- **Lens P (product-as-shipped)** — native vendor APIs. This is the report's **primary** lens; it answers "what does a customer get."
- **Lens M (model-on-common-substrate)** — Reactor. Infrastructure held constant, which *removes* the server-proximity confound. Secondary lens, and the **only** available lens for LingBot and Happy Oyster.

Every latency figure, table, and chart carries a Lens P / Lens M label. No composite spans lenses.

### 2.1 The bridge measurement (do this in the pilot)

If **any** model is reachable on both routes — most likely Lucy — run it identically on both and compute:

> **Reactor delta** = (Lens M latency) − (Lens P latency), plus any resolution/fps config difference

This single number lets you say, in the report, roughly what portion of the Reactor-only products' latency is platform overhead versus model. Without it, Lens M latency figures are uninterpretable next to Lens P ones. **If no model is dual-routed, state plainly that Lens M and Lens P latencies cannot be reconciled** and confine cross-lens claims to quality only.

Quality dimensions are largely lens-robust — a model that hallucinates hands does so on either substrate — with one exception: **resolution and fps differences directly affect perceived quality.** If Reactor serves at 16fps and native at 30fps, note it beside every quality score from that route.

---

## 3. Run matrix

### Campaign A — Timing (serial, isolated machine, Lens-labelled)

| Product | Lens | Conditions | N per condition |
|---|---|---|---|
| Lucy 2.5 | P (+ M if dual-routed → bridge) | C0, C2 | 40 |
| Xmax X2.0 | P | C0, C2 | 40 |
| LingBot-World 2 | M | C0, C2 | 40 |
| Happy Oyster | M | C0, C2 | 40 |

C1/C3 added for front-runners only, after a first pass. ~320–400 runs, ~6 h serial.

### Campaign B — Reliability (parallel, unattended, overnight)

- **N = 300 per product at C0**, plus 100 at C2
- Clip mix: 80% × 15 s, 15% × 60 s, 5% × 10 min soak
- Video retained **only for failed runs**
- Estimated Lucy spend: ~$90 at $0.02/sec. LingBot on Reactor ~$15 at $12/hr.

### Campaign C — Quality (capture-heavy, near-lossless, CRF ≤12, CFR)

- V2V: 10 clips × 3 style prompts × 3 reps
- Generation: 7 prompts × 3 reps
- Digital human: 4 scripts × 3 reps (if reachable)

---

## 4. The rating system — three independent layers

Layer 1 runs on everything. Layer 2 runs on a sample. Layer 3 never touches the quality score.

### Layer 1 — Computed metrics (100% of Campaign C, no human input)

LPIPS temporal flicker · optical-flow EPE · ArcFace identity **slope** · CLIP adherence · SyncNet LSE-C/LSE-D · blink rate and interval variance.

Scored by **position between two anchors** run through the identical pipeline — Anchor-0 (untransformed source) and Anchor-R (real filmed reference) — not against absolute published thresholds, which don't transfer across content.

**Status: supporting evidence.** Where Layer 1 and Layer 2 disagree, Layer 2 wins and the disagreement is reported.

### Layer 2 — Blind human rating (stratified sample)

Anchored 1–5 descriptors per dimension (Spec Part E), plus pairwise forced choice on aesthetic dimensions. Sample selected to span the Layer 1 range — best, median, worst — not at random, and the selection method is stated in the report.

- ≥3 raters, one non-technical
- Branding stripped, order randomised, re-encoded to identical settings so encoding artifacts don't leak identity
- Hidden repeat per rater for intra-rater consistency
- Krippendorff's α gates the strength of every claim: ≥0.80 normal, 0.67–0.80 tentative, <0.67 **contested** and no ranking claim made

### Layer 3 — Reliability (separate, adjacent, never blended)

Success / degraded / failed / timeout / refused, auto-classified, with a 10% human-labelled validation sample to establish classifier accuracy. Reported as a rate with **Wilson 95% CI**. At N=300 the CI at 5% is roughly 3.1–8.0%, so a 5%-vs-0.5% difference is defensible and a 5%-vs-3% one is not. Differences are claimed only when intervals don't overlap.

---

## 5. Rubrics — pre-registered, frozen before first run

### 5.1 V2V — Lucy 2.5, Xmax X2.0

| Dimension | Weight |
|---|---|
| Temporal coherence | **30%** |
| Structural fidelity | 20% |
| Style adherence | 15% |
| Detail retention vs. hallucination | 15% |
| Occlusion / re-entry | 10% |
| Aesthetic quality | 10% |

### 5.2 Generation — LingBot-World 2, Happy Oyster, (PixVerse R1)

| Dimension | Weight |
|---|---|
| Prompt adherence | 25% |
| Physical plausibility | 20% |
| Long-horizon consistency | 20% |
| Composition & aesthetic | 20% |
| Interactive responsiveness | 15% |

### 5.3 Digital human — Vidu S1

| Dimension | Weight |
|---|---|
| Lip-sync accuracy | 25% |
| Identity stability | 20% |
| Micro-behaviour | 20% |
| Expressiveness | 15% |
| Body & hands | 10% |
| Multilingual consistency | 10% |

**Weight adjustment rule (apply once, before testing, then freeze):** these defaults assume a **live-production** use case. If the primary use case is **offline stylised content**, drop V2V temporal coherence to 20% and raise detail retention to 25%. If it is **interactive/gaming**, raise generation interactive responsiveness to 25% and drop composition to 10%. Record which variant was used and the date.

---

## 6. How a score is actually produced — worked example

Lucy 2.5, temporal coherence:

1. **Clip level.** Clip V10 (60 s sustained) rated by 3 raters: 4, 3, 4 → **median 4**.
2. **Dimension level.** Same across all 10 V2V clips → scores 5,4,5,4,3,4,4,5,4,**4** → mean **4.2**, min **3**. Min > 2, so no worst-case flag.
3. **Weighted contribution.** 4.2 × 0.30 = **1.26** toward the category total.
4. **Category total.** Sum across all six dimensions → e.g. **C = 4.1 / 5**.
5. **Sensitivity.** Recompute with each weight ±10%. If Lucy and Xmax swap order, the ranking is reported as unstable and the deciding weight named.
6. **Tie rule.** Differences below 0.3 are declared a tie.
7. **Final presentation** — always the triple, never a single number:

> **Lucy 2.5 — Quality 4.1/5 · Clean success 96.3% (95% CI 93.5–98.0%, N=300) · p95 latency 180 ms [Lens P]**

---

## 7. Schedule

| Day | Work |
|---|---|
| **1** | Reactor catalog query · Xmax key · PixVerse + Vidu applications sent · rubric frozen and dated · harness build |
| **2 AM** | Pilot: bridge measurement, band separation check, rater-agreement trial on 3 clips, metric pipelines, rate-limit discovery |
| **2 PM** | Campaign C (quality captures) |
| **2 night** | **Campaign B unattended — spend cap armed** |
| **3 AM** | Integrity check · Campaign A serial on isolated box |
| **3 PM/night** | Campaign B continues · Layer 1 metrics computed on Campaign C |
| **4 AM** | Campaign B closes · auto-classification + 10% human validation |
| **4 PM** | Blind rating sessions |
| **5** | Analysis, sensitivity check, report |

---

## 8. Hard rules (the ones that break the report if violated)

1. Rubric frozen and dated **before** the first run.
2. Lens P and Lens M never share a table.
3. Reliability never enters the quality score.
4. Retried runs excluded from the reliability denominator.
5. Model version string pinned explicitly (`lucy-2.5`, never `lucy-latest`) and logged per run.
6. Campaign A runs with nothing else on the host.
7. Spend cap armed before any unattended window.
8. No cross-category composite score.

---

## 9. Remaining opens

1. Primary use case → confirms or adjusts §5 weights (**needed before day 1 ends**)
2. Report audience → internal, executive, or external publication (affects legal review)
3. Rater panel confirmed (3 people, one non-technical)
4. Isolated machine reserved for Campaign A
5. Storage provisioned (~100–160 GB for Campaign C)
