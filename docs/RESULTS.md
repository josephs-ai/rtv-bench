# RTV-Bench — Reference Run Results (2026-08)

> Products: Lucy 2.5 (Decart) · Xmax X2.0 · LingBot-World 2 (Ant) · Happy
> Oyster (Alibaba). PixVerse R1 and Vidu S1 were access-gated: listed as
> not-evaluable, not guessed at.
> Vantage: mainland-China residential, pinned per campaign. All numbers
> re-derivable from `data/` journals; methodology in [`../BENCHMARK.md`](../BENCHMARK.md).

---

## Track 1 — Interactive video (Lucy 2.5 vs Xmax X2.0)

**RTV-Score (canonical, spec v1.1): Lucy 47.4 · Xmax 42.4** — formula
`100 × √delivery × (0.40·experience + 0.25·interaction + 0.20·ref-control + 0.15·latency)`;
experience = mean(identity integrity, artifact burden), all absolute;
ref-control is the new v1.1 axis from campaign F (see Amendment 2 in
`rubric-amendments.md` — v1.0 numbers Lucy 53.2 / Xmax 43.1 remain
re-derivable with the old weights); the pairwise sweep below is the
relative exhibit. The artifact component
(restored 08-17 from the re-audit) lowered both scores equally-ish — on
the hard full-restyle workload *both* products artifact heavily (median
window burden 12.3 vs 14.1 of a possible 18); the honest headline is that
nobody is close to ceiling on sustained transformed video.

### Composite scores (declared-weight profiles, per lens)

| Profile | asks | Lucy 2.5 (native) | Xmax X2.0 (native/browser) |
|---|---|---|---|
| **STREAMER-CN** | "power a China-market live-avatar product" | **67.1** | 59.5 |
| **CREATOR-GLOBAL** | "power a creative restyling tool" | **77.6** | 40.2 |
| **LAB** | "pure capability, no market weighting" | **74.1** | 45.9 |

**Lucy wins every profile, but the gap collapses from 37.4 points (creative
use) to 7.6 (China streaming use)** — Xmax's instant whole-scene restyle,
China-direct availability, edit-time identity stability, and its win on
the new reference-control axis are worth that much in its home market.

![Composite and axis scores](img/scores.png)

### Axis detail

| Axis (0–100) | Lucy 2.5 (P) | Xmax X2.0 (P-browser) | what it measures |
|---|---|---|---|
| A Reliability | 48.7 | 63.8 | session value rate (S + ½·D), long-session robustness, TTFF |
| B Head-to-head preference* | 97.9 | 2.1 | blinded same-input pairwise wins (relative, two-product field) |
| B′ Artifact burden (absolute) | 31.9 | 21.5 | audited median window burden 12.3 / 14.1 of max 18, inverted |
| C Identity | 92.7 | 84.7 | long-horizon embedding drift + face-through-edits |
| D Live editing | 84.8 | 54.0 | commit latency, application, precision, hold, transition |
| E Latency | n/a† | 58.0 | instrumented motion-to-glass (983 ms styled, Xmax native) |
| F Deploy-CN | 50 | 100 | China-market reachability (direct / VPN-viable / blocked) |
| **G Ref control (v1.1)** | 42.6 | **50.5** | campaign F: adoption 0.35 · hold 0.20 · switch 0.25 · compose 0.20 (sub-scores below) |

\* B is currently pairwise-only (its absolute artifact-burden component
awaits an audit re-run after a blinding-key incident) — read it as "how
often the blinded judge preferred this product over its rival on identical
input," not as absolute quality. In a two-product field the loser of a
lopsided matchup necessarily scores near zero.
† not instrumented on that lens; weights renormalize and coverage % prints
with the score.

### Same-input blinded quality (64 pairs)

**Lucy 64–0 at clip level** (temporal 64-0, structure 60-4, style 61-0-3,
detail 64-0). Adversarially verified in both directions — the judge's rare
Xmax wins map to real Lucy single-frame collapses; Lucy's wins include a
full identity replacement on the Xmax side within 12 s.

Xmax's two systematic failures: a **~2 s early-stream freeze** (nearly
every session) and **progressive identity morph** (within a single continuous shot the subject becomes a different person — replayable example completes in ~12 s; judge-confirmed across independent pairs; systematic onset timing deferred to the v1.1 long-session arm). Lucy's failures are rare single-frame
collapses that self-recover within a second.

### Live mid-stream editing (48 sessions, 9 edit types)

| edit type | Lucy 2.5 | Xmax X2.0 |
|---|---|---|
| whole-scene style flip | works, 4.6 s | **wins: 1.0 s, zero collateral** |
| garment swap | **1.4 s, clean, holds** | commits at 6.6 s, mostly partial |
| background swap | **works** | 3/6 full, 2 partial, 1 none; rewrites whole frame |
| accessory | **1.2 s clean** | partial-then-revert |
| hair | applies 3/3, holds (1 oscillation) | text-instructed: total failure (6 sessions, EN/ZH/global phrasings incl. fresh replicates). *The 2026-08-15 "ref-image channel dead" arms are RETRACTED — invalid tests (wrong SDK field, see below).* |
| ref-image character switch | **applies, 3.4 s, holds** | **connect-time: works 2/2** (image on vendor COS via SDK upload; character fully re-anchored to the ref portrait, scene preserved). Mid-stream ref switch: 0/2 replaced the speaker (1 inserted the ref person into the background instead, 1 no visible effect) |

**Correction (2026-08-17).** The earlier finding that Xmax's reference-image
channel "does nothing" was our invocation bug, not the product: the session
API accepts `refImageUrl`, while we passed `refImage` (an internal-layer
name), which `normalizeRealtimeContext` silently strips — the field never
reached the wire. Retested with the SDK's own COS upload flow
(`client.files.uploadAndCheckImage`) + the correct field: connect-time ref
works decisively (2/2, two different ref portraits). Mid-stream ref
injection via `session.set` does transmit (SDK-verified) but did not
re-anchor the live character in either attempt.

Pattern: Lucy edits *surgically* (moderate whole-scene collateral); Xmax
either restyles the entire world or does nothing. The style flip — Xmax's
one win — happens to be the core interaction of its own product plan.

![Outcomes by lens and edit matrix](img/outcomes-edits.png)

### Reliability (adjudicated, per lens — lenses never compared directly)

| entity | N | clean | degraded | failed | note |
|---|---|---|---|---|---|
| Lucy 2.5 · native | 210 | 36% | 37% | 26% | failures cluster in tunnel-sag windows; +356 runs excluded as network-fault |
| Xmax · via aggregator | 85 | 55% | 33% | 12% | tail still accruing |
| Xmax · native browser | 91 | 25% | 75% | 0% | the ~2 s start-freeze marks sessions degraded |

### Hour-scale preview (campaign E, v1.1 — first datapoint)

One 10-minute Lucy session on a single-shot looped face (telemetry +
identity stills every 10 s): **no identity drift over 9 continuous
minutes** — face similarity to t=0 median 0.86, never below 0.75, no
decay trend — and delivery held a flat 17.2 fps throughout. Session ended
at 536 s by provider credit exhaustion, not product failure. Xmax
counterpart + 30/60-min tiers pending credits.

### Reference-image control (Campaign F, v1.1 — BOTH ARMS COMPLETE 2026-08-17)

The dedicated ref-image campaign (the core interaction of preset-character
products): **65 Xmax sessions, 6 arms, 0 failures**, scored by
computational face-similarity timelines (sim-to-ref vs sim-to-input every
2 s; ~0.75+ = same person, ~0 = unrelated; clean-anchor band 0.33–0.46).
Plus a 12-session mechanism probe series for mid-video switching. The
Lucy mirror arm ran the identical 65-job matrix (2 parallel lanes,
64 usable + 9 no-face segments excluded as no-data).

**Axis G side-by-side (each product wins different sub-capabilities):**

| G component (weight) | Lucy 2.5 | Xmax X2.0 | reading |
|---|---|---|---|
| Adoption across full input matrix (.35) | **60.0** | 37.5 | Lucy anchors even on the 5-person crowd (0.39–0.76) and hits higher sims (up to 0.76); both fail wide-shot small-face; stylized refs mostly fail on both |
| Anchored-identity hold (.20) | 50.0 | **66.7** | Xmax 180 s holds are flat both reps; one Lucy hold capture lost to a no-face segment |
| Mid-video switch (.25) | 46.4 | **56.1** | Lucy switches **in-session in ~2 s** via `set_image` but only ~58% reliably; Xmax cannot switch in-session (0/16) but its re-session mechanism is 2/2 with a ~7 s transition |
| Text edit on anchored character (.20) | 0.0 | **50.0** | Xmax scene-level edits keep the character (person-level edits reset it); ANY Lucy text edit evicts her anchor |
| **Axis G** | 42.6 | **50.5** | Xmax's first capability-axis win — on its sector's core interaction |

**Confirmed working (Xmax X2.0, native browser lens):**

- **Connect-time character anchoring: 16/16** on inputs with a dominant
  visible face (close-up and over-shoulder two-person; both replicates,
  all three photo refs). sim-to-ref 0.36–0.46, sim-to-input ~0 — the
  character becomes the ref; scene, pose, motion preserved.
- **Attribute transfer**: the long-blonde-hair ref delivers the hairstyle
  that failed 6/6 as a text instruction. For appearance control, the ref
  channel works where text does not.
- **Identity hold under anchor: no drift** — 180 s holds flat in both
  replicates (slope +0.02/min); 90 s self-ref sessions hold 0.84 (3/3).
  (No-ref 90 s controls also held 0.85 in this pass — the historical
  ~12 s morph is intermittent and did not reproduce here, so no
  anchoring-vs-morph differential can be claimed yet.)
- **Mid-video character switching: works via re-session — 2/2 clean**
  (the app\'s own switch pattern). New session with the new ref after a
  ~4 s teardown settle: full adoption (0.33/0.43 to new ref, input ~0.05),
  measured transition gap ≈3.2 s frozen + settle (≈7 s end-to-end in our
  conservative harness; an app pipelining teardown can be faster).
- **Text edits on an anchored character execute 8/8** (campaign-D
  taxonomy): style flip and background swap apply **while keeping the
  anchored character** (sim-to-ref 0.32–0.37 maintained).

**Capability boundaries (machine-scored, replicated):**

- **Person-targeted text edits break the anchor**: garment and accessory
  edits apply cleanly (red hoodie, aviators — visibly committed) but
  reset the character to the input person (sim-to-input 0.59–0.85).
  Scene-level edits keep the character; person-level edits trade it away.
- **In-session ref events do NOT re-anchor**: `change_condition`
  transmits but ignores refs; mid-session re-`start` / stop+start revert
  to input identity; ref→ref chains fail (0/16 across F3+F5). Re-session
  is the working switch mechanism; anchoring is session-scoped.
- **Stylized (non-photographic) refs fail everywhere** (0/9 incl. a 180 s
  hold): the realtime ref channel appears photo-only.
- **Multi-person input (5 faces)**: anchoring silently no-ops (8/8).
- **Wide-shot small-face input**: identity collapses to neither ref nor
  input (8/8); one session rendered the small-scale subject in
  inappropriate attire, and a beach background edit re-dressed the
  anchored character in beachwear and added an unrequested bystander
  (content-drift observations flagged for the judge pass).
- **Concurrent sessions on one account poison ref anchoring** — proven
  by a controlled confound during probing; ref work must serialize.

*History note:* an earlier (2026-08-15) claim that the ref channel "does
nothing" was our invocation bug (wrong SDK field name, silently stripped)
— retracted and corrected the same day the correct field was traced; see
the correction note above and `tools/claims_check.py --facts` item 4,
which machine-verifies the working-channel finding.

### Latency & platform tax

- Xmax native styled motion-to-glass: **~983 ms** (instrumented, direct
  domestic route).
- Lucy styled motion-to-glass **measured ≈2.6–2.7 s from this vantage**
  (two concordant timestamped probes, z≈3.7) — but that path rides the VPN
  tunnel + TCP relay, so it is **not comparable** to Xmax's direct-route
  figure and is excluded from axis scoring; her clean-route latency needs a
  non-tunneled vantage (v1.1).
- Same model through the Reactor aggregator: **+650–710 ms** — the
  measured cost of the middleman, and the reason lenses never share tables.

### Market access (often the deciding row)

Lucy is unreachable from mainland China without a well-behaved VPN — and
this run *measured* how fragile that path is. Xmax connects domestically
with zero ceremony and sailed through the same network weather untouched.
For a China-market product, the V2V field effectively has one entrant.

---

## Track 2 — Interactive worlds (LingBot-World 2 vs Happy Oyster)

**Track-2 RTV-Score** = 100 × √(build-success) × (adherence 35 /
long-horizon 25 / physics 20 / steering 20): **Happy Oyster 50.5 ·
LingBot 29.3** — HO's adherence, hold, and steering outweigh LingBot's
2.5× build speed (speed is exhibited beside the score, not inside it).

Frame-computed metrics (direct measurement, no judging involved):

| metric | LingBot-World 2 | Happy Oyster | edge |
|---|---|---|---|
| subject consistency (same scene stays same) | 0.836 | **0.900** | HO |
| long-horizon hold (start vs 1 min later) | 0.685 | **0.759** | HO |
| motion pops (teleports/min, lower better) | 37.3 | **23.3** | HO |
| temporal flicker score (higher steadier) | **0.997** | 0.985 | LingBot |
| world build+capture time (median) | **~55 s** | ~138 s | LingBot 2.5× faster |


Blinded-judge medians (1–5 anchored scale, re-run with clean keys):

| dimension | LingBot | Happy Oyster |
|---|---|---|
| prompt adherence (E6) | 2 | **3** |
| physical plausibility (E7) | 2 | 2 |
| long-horizon consistency (E8) | 2 | **3** |

Two independent instruments — per-frame math and a blinded judge — agree
on the direction. That's the benchmark's redundancy doing its job.

**Steerability — HO's clear win:** `instruct()` returns explicit
accept/reject receipts and supports pause/resume/rewind; LingBot's steering
is fire-and-forget.

The trade-off, plainly: **Happy Oyster builds better, steadier, more
steerable worlds; LingBot builds worlds 2.5× faster.** Samples: LingBot
19/21, HO 11/21 (remainder limited by the vantage's network, not the
product).

---

## Engineering findings (vendor-actionable)

- **Two mirror-image silent traps in the Xmax SDK**: connect requires
  `context.prompt` (flat ignored); live update requires flat `prompt`
  (context form ignored). Both "succeed" silently when wrong.
- **Happy Oyster's second-connection architecture**: the main session track
  is a placeholder by design; real frames ride a second Aliyun RTC
  connection only the dedicated SDK opens.
- **Aggregator billing** is dominated by session time (world-builds,
  connect overhead), not streamed video.

## Known limitations of this run

- Absolute reliability rates carry the measured-from-this-vantage caveat;
  same-lens comparisons are the robust readout.
- Lucy's captures are lossless taps while Xmax's browser lane re-encodes
  (VP8) — partially discharged by the judge crediting Xmax where deserved.
- The computed edit metrics (region-tracked commit/hold) are unreliable on
  multi-person or occluded clips — the blinded edit-judge is primary for
  application/stability claims and caught three such misreads (documented
  2026-08-17); single-face region tracking is a v1.1 fix.
- Campaign-B journal row-tails were lost to a git incident after aggregates
  were computed and committed (`data/campaign-b/JOURNAL-LOSS-NOTE.md`);
  affected slots re-run.
- Track 2's judge layer re-running post key-incident; B-axis audit
  component pending the same restoration.
