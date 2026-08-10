# Automation & Scale Addendum v1.0

Companion to the *Evaluation Plan* and *Metrics & Scoring Spec*. Assumes a multi-day window and unattended automated execution.

**Headline change:** with automation, run count stops being the constraint. Four other things become the constraints, and the run matrix must be restructured around them.

---

## Part 1 — What actually gates scale

| Gate | Effect | Mitigation |
|---|---|---|
| **API availability** | Only products with a streaming API can be fully scripted. UI-only products need Playwright/Appium — slower, more fragile, higher ToS risk | Split the six by access mode; set separate `N` targets per mode |
| **ToS / anti-abuse** | Hundreds of automated runs can look like abuse and get accounts banned mid-study | **Request evaluation access from each vendor in writing before starting.** Many grant eval credits and explicit permission — this is the single highest-value action in this plan |
| **Rate limits & quota** | Hard ceiling regardless of your time budget | Discover limits in the pilot; design the queue to respect them with backoff |
| **Wall-clock** | Real-time products are duration-bound. A 60 s run takes 60 s — no way to speed it up | Shorten reliability clips; parallelise across lanes; run overnight |
| **Cost** | Hundreds of runs × 6 products is real money | Budget per product **[LOCK]**; instrument spend per run |

**Do the vendor outreach on day 1.** Getting written eval permission converts your biggest risk (mid-study ban destroying half your dataset) into a non-issue, and often gets you quota you'd otherwise have to buy.

---

## Part 2 — Split the run matrix into three campaigns

The single most important structural change. These have incompatible requirements and must not share runs.

### Campaign A — Timing (precision-critical, serial, small N)

- **Purpose:** glass-to-glass latency, jitter, fps
- **Constraint:** must run **serially on an isolated machine.** Any parallel load on the same host contaminates timing. This is non-negotiable — a parallelised latency number is a fiction.
- **N:** 30–50 samples per product per network condition. More adds nothing; precision here comes from isolation, not volume.
- **Capture:** high bitrate, side-by-side composite
- **Runtime:** ~4 conditions × 6 products × 40 runs × 80 s ≈ 21 h — but only ~6 h if you cut to conditions C0 and C2 for the full field and run C1/C3 on the front-runners only. Recommended.

### Campaign B — Reliability / soak (high volume, parallel, large N)

- **Purpose:** outcome classification only — success, degraded, failed, timeout, refused
- **Constraint:** does **not** need precise timing, so it parallelises freely
- **Clip length:** 15 s for the bulk. Failure modes can be duration-dependent, so include a mix: ~80% at 15 s, ~15% at 60 s, ~5% long-soak (10 min)
- **N:** 300–500 per product — this is where your multi-day window pays off
- **Capture:** low bitrate or metadata-only. Retain video **only for failed runs**, for the failure-mode catalogue
- **Runtime:** ~35 s cycle at 15 s clips ≈ 100 runs/hour/lane. 3 lanes × 12 unattended hours ≈ 3,600 runs. Quota and cost will bind long before time does.

### Campaign C — Quality (moderate N, capture-heavy)

- **Purpose:** produces the clips that get computed metrics and human rating
- **N:** full stimulus corpus × 3 style prompts × 3 repetitions per product
- **Capture:** **near-lossless** (see Part 4 — this matters more than it sounds)
- **Runtime:** modest; the corpus is the size it is

---

## Part 3 — Parallelism architecture

- **One container/VM per lane**, each with its own account credential and its own network namespace.
- **Per-lane network shaping:** `tc netem` applied inside each lane's netns, not globally — otherwise lanes interfere and you can't run different conditions concurrently.
- **Campaign A runs alone.** Schedule it in a window where no B or C lane is active on the same host. Enforce this in the orchestrator, not by discipline.
- **Do not run Campaign A in a VM at all** (per plan §5.5). Bare metal, isolated.
- **Stagger lane start times** by a few seconds so you don't send six simultaneous connection attempts and trip rate limiting on shared infrastructure.

---

## Part 4 — Capture policy (easy to get wrong)

**Compression artifacts contaminate temporal-flicker metrics.** If you capture Campaign C at typical streaming bitrates, inter-frame LPIPS will partly measure your encoder, not the product. Every product will look worse, unequally.

| Campaign | Capture setting | Rationale |
|---|---|---|
| A — Timing | CRF 18, 60 fps | Timestamps must be legible; flicker not measured here |
| B — Reliability | CRF 28, or discard video on success | Only outcome matters; retain failures only |
| C — Quality | **CRF 12 or lossless**, constant frame rate | LPIPS/ArcFace/CLIP run on these frames |

**Storage estimate:** Campaign C at near-lossless 1080p60 runs roughly 400–800 MB/min. A 200-run Campaign C at 60 s ≈ 80–160 GB. Provision the disk before you start; running out mid-campaign at hour 30 is a real and stupid way to lose a night.

Verify your capture chain is **constant frame rate**. Variable frame rate output silently breaks frame-index-based metrics.

---

## Part 5 — Automated outcome classification

Campaign B only works unattended if outcomes classify themselves. Rules:

| Outcome | Automated detection |
|---|---|
| **T — Timeout** | No first frame within 30 s of request |
| **F — Failed** | Connection error, non-2xx terminal response, process exit, or stream teardown before `duration_intended × 0.95` |
| **R — Refused** | Policy/moderation response code or known refusal string. Maintain a per-product refusal-pattern list from the pilot |
| **D — Degraded** | Dropped frames >5%, OR any freeze ≥1 s (consecutive identical perceptual hashes), OR resolution change mid-stream |
| **S — Success** | None of the above |
| **E — Environment** | Local network probe fails, or rig health check fails, within the run window. Run a continuous control ping to a known-good endpoint |

**Validate the classifier.** Have a human hand-label a random 10% sample and report classifier accuracy in the methodology. An unvalidated auto-classifier is exactly the kind of thing a reviewer will attack, and rightly — if it systematically miscounts one product's failure mode, your headline reliability numbers are wrong.

---

## Part 6 — Human rating is now the bottleneck

Automation scales runs and computed metrics. It does **not** scale human judgment, and quality scores still depend on it.

Rough capacity: a pairwise comparison takes ~15 s, absolute anchored scoring ~30 s per clip-dimension. A 45-minute session yields ~150 pairwise judgments or ~80 absolute scores. Three raters across a few sessions each is on the order of **1,000–1,500 judgments total.** You cannot rate 500 clips per product.

**So sample deliberately:**

1. Computed metrics run on **100%** of Campaign C.
2. Human rating uses a **stratified subsample**: for each product × dimension, select clips spanning the computed-metric range (best, median, worst by the relevant proxy) rather than at random. This is more informative per unit of rater time and surfaces disagreements between metric and perception.
3. Cap at ~10–15 clips per product for absolute scoring, plus a pairwise round on the head-to-head decisive clips (V10, G6, S3).
4. Keep the hidden-repeat and blinding protocol unchanged.

**Report the sampling method explicitly.** "Human ratings drawn from a stratified sample of n=72 clips selected across the computed-metric range" is defensible; an unexplained subset is not.

---

## Part 7 — Revised sample sizes and what they now resolve

Wilson 95% intervals at `p̂ = 5%`:

| N | 95% CI at 5% | Resolves |
|---|---|---|
| 50 | ~1.7% – 13.7% | Order-of-magnitude only |
| 150 | ~2.5% – 9.8% | ~10 pp differences |
| **300** | ~3.1% – 8.0% | **5% vs. 0.5% cleanly separable** |
| 500 | ~3.4% – 7.2% | ~4 pp differences |
| 2,000 | ~4.1% – 6.1% | ~2 pp differences |

**At N=300 per product, the comparison you originally cared about becomes real:** a product at 5% (CI 3.1–8.0%) and one at 0.5% (CI 0.1–1.9%) have non-overlapping intervals, so the difference is defensible. Distinguishing 5% from 3% still needs thousands and is not worth the quota.

**Target: N = 300 per product for Campaign B, at baseline condition.** Add N = 100 at C2 for the degradation comparison.

---

## Part 8 — Orchestration engineering

Non-negotiable for unattended multi-day runs:

- **Durable queue** with per-run idempotent IDs; resumable after crash without duplicating or losing runs
- **Health check between runs** — verify virtual camera is alive and source file is playing. A dead vcam silently produces 300 identical garbage runs overnight
- **Retry policy:** exponential backoff on transport errors, capped at 3 attempts. **Retried runs are logged separately and excluded from the reliability denominator** — otherwise you launder failures into successes
- **Per-run metadata capture:** product version/build string, timestamp, account, region, network profile. Models get updated mid-study; without version stamps you can't detect or segment it
- **Spend counter** with a hard cap that halts the queue
- **Interleave products** rather than running one to completion — protects against time-of-day load effects confounding the comparison. This matters: running Product A at 2 a.m. and Product B at 2 p.m. makes the comparison meaningless
- **Nightly integrity check:** confirm capture files are non-zero, correct duration, and CFR

---

## Part 9 — Risks specific to running at scale

| Risk | Mitigation |
|---|---|
| Account ban mid-study | Written vendor eval permission (Part 1); spread across accounts; respect rate limits |
| Model silently updated mid-run | Version-stamp every run; segment analysis by version; re-run affected cells |
| Time-of-day load confound | Interleave products; record timestamps; check for drift in analysis |
| Silent rig failure producing garbage at scale | Inter-run health checks; nightly integrity check |
| Auto-classifier systematically wrong for one product | 10% human-labelled validation sample |
| Cost overrun | Hard spend cap in orchestrator |
| Storage exhaustion | Provision ahead; Campaign B discards video on success |

---

## Part 10 — Revised schedule (5 working days)

| Day | Activity |
|---|---|
| **1** | **Vendor eval-access requests sent (first task of the day).** Accounts provisioned, ToS review, rubric frozen, harness built |
| **2 AM** | Pilot calibration (Spec Part I): band separation, rater-agreement trial, metric pipelines, rate-limit discovery |
| **2 PM** | Campaign C (quality) runs — capture-heavy, supervised |
| **2 night** | **Campaign B launches unattended** — the overnight window is where your N comes from |
| **3 AM** | Integrity check; Campaign A (timing) on isolated machine, serial |
| **3 PM–night** | Campaign B continues; computed metrics run on Campaign C in parallel |
| **4 AM** | Campaign B closes; auto-classification + 10% human validation |
| **4 PM** | Blind human rating sessions on stratified subsample |
| **5** | Analysis, sensitivity check, report |

Two unattended overnight windows are what make N=300 achievable. Protect them — a rig failure at 11 p.m. on night one costs you a third of your dataset.

---

## Part 11 — Decisions this adds **[OPEN]**

1. **Vendor eval access** — send requests day 1; changes the risk profile more than anything else here
2. **Per-product spend cap**
3. **Which products get C1/C3 network conditions** (recommend: front-runners only after a C0/C2 first pass)
4. **Lane count and hardware** — how many isolated machines/containers available, and is there one bare-metal box reservable for Campaign A
5. **Storage provisioned** for Campaign C at near-lossless
