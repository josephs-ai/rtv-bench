# RTV-Bench v1.1 — Realtime Video AI Benchmark

A repeatable benchmark for **live** video AI products, born from the 2026-08
six-product evaluation. It measures what realtime products actually sell:
staying up, looking right, reacting fast, and taking mid-stream direction.

This file is the methodology. The question list lives in
[`spec/questions.md`](spec/questions.md) (the registry — one row per
question the benchmark asks, with campaign, stimulus, instrument, metric,
record path, and answer status). Per-product invocation detail lives in
[`spec/invocation-playbooks.md`](spec/invocation-playbooks.md). Change
control lives in [`GOVERNANCE.md`](GOVERNANCE.md).

---

## 1. Architecture: how a session becomes a number

```
STIMULUS ──> SESSION ──> GUARDS ──> CAPTURE ──> INSTRUMENTS ──> SCORING
(hashed      (real        (network   (lossless    (4 independent   (axes ->
 pixels)      product      gates,     FFV1 +       readers of       profiles ->
              endpoint)    watchdogs) journals)    the same         canonical)
                                                   capture)
```

Every stage journals append-only. A result that can't be re-derived from
its journals isn't a result (`docs/SUBMITTING.md`).

**Stimulus.** All inputs are versioned and hash-pinned in
`stimulus-pack/manifest.json`. The builder
(`tools/build_stimulus_pack.py`) fetches sources, verifies sha256,
derives conforms deterministically, derives secondary assets by pinned
recipes (e.g. the self-identity ref crop), and installs everything where
campaigns read it — a user never hand-fetches anything. Source hashes are
the portable guarantee; encoder variance across ffmpeg builds is recorded,
not failed.

**Session.** Real streaming against real product endpoints: WebRTC
(aiortc) for native-API products, the vendor's own browser SDK driven in
headless Chrome when that is the only client (the capture then records the
raw remote track from a canvas so time-to-first-frame stays measurable —
leading black is the TTFF signal). No mocks, no offline renders.

**Guards.** A throughput sentinel refuses to launch into a sagged uplink;
long-session drivers gate on `--min-mbps` and hold rather than burn runs;
capture watchdogs (e.g. no-chunk-for-120 s) kill dead pages; spend is
reserved and reconciled per run (`spend.jsonl`).

**Capture.** Every delivered frame stored lossless (FFV1), every timing
journaled. Hour-scale sessions record in 10 s chunks so a crash loses
seconds, not the session.

**Instruments** — four independent readers per capture; agreement between
blind instruments is the evidence standard:

| instrument | what it reads |
|---|---|
| Outcome taxonomy | S (clean) / D (degraded) / F (failed) / T (timeout) / R (rig) / E (network-fault, excluded) — with Wilson CIs and 3-layer attribution (§3) |
| Computed metrics | LPIPS flicker · RAFT motion fidelity & physics pops · ArcFace/insightface identity timelines · CLIP adherence · DINOv2 drift · purpose-built edit metrics (commit latency, collateral, residue, stability) · face-similarity ref-adoption timelines |
| Blinded VLM judge | anchored rubric scores, pairwise forced choice, 10-class artifact audit with onset times, 5-dim edit judge — schema-forced, shuffled, re-blinded per run, trusted only where human agreement ≥ α 0.67 (`tools/alpha_report.py`) |
| Latency instruments | motion cross-correlation through the transform; the same model dual-routed to price an aggregator's overhead |

**Scoring** (§10): sub-metrics → seven 0–100 axes → declared-weight buyer
profiles → one canonical RTV-Score per product per track.

---

## 2. The lens system

A *lens* is the route a measurement took. Lenses **never** share a table:

- **P** — native API (e.g. Lucy via Decart WebRTC)
- **P-browser** — the vendor's own browser SDK, driven headlessly (e.g.
  Xmax; it is still the vendor's official client)
- **M** — via an aggregator/middleman (e.g. Xmax through Reactor); the
  middleman's latency and pricing are measured as their own numbers

A product measured through two lenses appears twice, separately. The
bridge measurement (§9) exists precisely to price the M-vs-native gap.

## 3. Outcome attribution (why failures are believable)

Every failed run is classified **product / network / rig** through three
layers: (1) the pre-launch throughput sentinel, (2) in-run drift/loss
guards, (3) post-hoc cross-product correlation adjudication (if both
products failed in the same wall-clock window, suspect the network).
Network-fault (E) runs are excluded from every denominator **with their
evidence**; all human overrides live in
`data/campaign-b/adjudications.json`. Silent exclusion voids a result.

## 4. Campaign B — reliability (Q1)

**Design.** 300 rounds per product-lens pair, round-robin, with a duration
mix (15 s / 60 s / 180 s slots) so short-session survival and long-session
survival separate. Each round: sentinel check → session → capture →
outcome classification → journal (`data/campaign-b*/runs.jsonl`,
queue state in `queue-journal.jsonl`, money in `spend.jsonl`).

**Reads.** Value rate = (S + ½·D)/N with Wilson CIs; TTFF from first
non-black frame; long-session value rate from the 180 s slots **plus**
campaign E rows (content-freeze-aware: a permanent freeze ends a session
at its onset regardless of frames still arriving).

## 5. Campaign B v2 — blinded quality (Q2)

**Pairs.** Same-input captures from the two products are cut into
matched clips, shuffled, and re-blinded per run (per-run key files —
judgments must re-link or the run voids). The judge makes forced choices
on four dimensions (temporal coherence, structure, style adherence,
detail) with required evidence text. Pairwise results are a **relative
exhibit** — published beside the ladder, never inside it.

**Artifact audit (absolute).** Windows of each capture go through a
10-class artifact taxonomy with severities and **onset times**,
schema-forced. Median window burden (max 18 = 6 findings × severity 3)
inverts to the absolute artifact score that enters the experience term.
Extreme judge calls get human eyeball verification before entering any
report.

## 6. Campaign D — live mid-stream editing (Q3)

**Protocol.** A clip streams; at t = 15 s (wall-clock from first delivered
frame — delivered fps varies, so frame-count clocks are wrong) an edit
instruction lands through the product's own channel. Capture continues to
35 s. 9 edit types (garment ×2, hair, accessory, background ×2, style,
ref-character ×2) × 3 clips per product.

**Reads.** Purpose-built edit metrics (commit latency, targeting
precision/collateral, residue, stability, direction-aware identity) plus
a 5-dimension blinded edit judge. The judge is primary on multi-person
clips where region tracking is unreliable (documented limitation).
Scorecard: `data/campaign-d/scorecard.json`.

## 7. Campaign F — reference-image control (Q4)

The preset-character interaction, measured as a 65-job matrix per product
through each product's native ref mechanism (URL-on-COS for Xmax,
base64 `set_image` for Lucy — see playbooks):

| arm | design | question |
|---|---|---|
| F1 anchor | 4 refs (3 photo + 1 stylized) × 4 input framings (close-up / 5-person crowd / over-shoulder / wide small-face) × 2 reps | does the character become the ref, and on which inputs? |
| F2 hold | 180 s anchored sessions | does anchored identity drift? |
| F3 switch | ref injected mid-stream at t=15 | can the character be switched in-session? |
| F4 compose | campaign-D text edits ON an anchored character | do text edits coexist with a ref anchor? |
| F5 chain | ref A at connect, ref B at t=15 | sequential switching |
| F7 anti-morph | self-ref 90 s ×3 vs no-ref control ×3 | does anchoring prevent identity morph? |

**Primary metric is computational**: insightface face-similarity
timelines sampled every 2 s against (a) the ref portrait and (b) the
input person. Adoption = sim-to-ref ≥ 0.25 **and** sim-to-input ≤ 0.30
(the clean-anchor band observed is 0.33–0.46; input-person baseline ~0).
Rows with no detectable face are excluded as no-data (counted, never
silently dropped) — except in F4, where a vanished face means the anchor
did not survive. Switch mechanisms that fail in-session are re-tested
through every documented product mechanism before any "cannot" claim
ships (the probe series lives in `data/campaign-f/captures-probe/` and
`probe-verdicts.json`) — a wrong invocation is a benchmark bug, per rule
zero of the playbooks.

## 8. Campaign E — hour-scale sessions (Q1.4)

Live-avatar reality is hour-scale; nobody measures it. Tiers of 10/30/60
minutes on a single-shot looped face (65-min pre-built file — runtime
looping stalls at clip boundaries), with per-frame telemetry (native
lane) or 10 s chunked recording (browser lane), identity stills every
10 s, and network probes every 5 min for post-hoc attribution. Drivers
gate on uplink health (`--min-mbps`) and **hold instead of burning
sessions**. Analysis is content-aware: a permanent freeze (identical
frames to end-of-capture) ends the session at its onset — delivered
frames of a frozen image are not survival. Confound controls are part of
the method: the 60-min freeze finding shipped only after a 20×
points-budget control excluded temp-key exhaustion.

## 8b. Campaign G — interaction density (Q3.5)

The moat arm: a clip streams 90 s while an edit fires **every 10 s** —
8 edits, a fixed ordered sequence (garment → background → accessory →
style flip → revert-to-photoreal → suit → background) through each
product's native channel, every send logged with wall-time offset and
frame index. The analyzer (`tools/campaign_g_metrics.py`) computes
per-edit commit via CLIP-similarity windows (8 s pre vs post, threshold
+0.02, first-crossing = commit latency), an identity-to-start timeline
across the whole session (floor + slope — does the face survive eight
consecutive redirections?), and a frame-detail trend. Wall/file
time-base correction applied per product (Lucy FFV1 is CFR-labelled at
~half delivery rate). Exhibit first; scoring requires an amendment.
**Closed-loop responsiveness** (Q5.4, `tools/latency_timeline.py`)
complements it: motion-energy cross-correlation in 30 s windows over any
input/capture pair → per-window lag and drift.

## 9. Latency & platform tax (Q5)

Motion-to-glass: a reel with timing flashes baked into its pixels is
cross-correlated against the styled output — measurable through any
transform. Only direct-route numbers enter scoring; tunnel-bound
measurements are exhibited with their vantage caveat, never compared
against direct routes. The **bridge**: the same model driven natively and
through an aggregator prices the middleman in ms. **Cost/throughput**
(Q5.3) joins reconciled billing to run journals ($ per attempted /
delivered / value minute) — exhibited, not scored, because pricing moves
faster than capability.

## 10. Scoring: sub-metrics → axes → profiles → canonical

**Axes** (0–100, absolute anchors, per product-lens):

| axis | built from (sub-weights in `benchmark_score.AXIS_WEIGHTS`) |
|---|---|
| A reliability | value rate .50 · long-session value .35 · TTFF .15 |
| B pairwise* | blinded pairwise wins (*relative exhibit — excluded from canonical) |
| B′ artifact | audit burden inverted (absolute; feeds experience) |
| C identity | drift .55 · face-through-edits .45 |
| D live editing | apply .30 · commit .25 · precision .20 · hold .15 · transition .10, weighted across edit types by declared relevance |
| E latency | log-anchored motion-to-glass (0.5 s → 100, 2.5 s → 0) |
| F deploy-CN | direct 100 / VPN-viable 50 / blocked 0 |
| G ref control | adoption .35 · hold .20 · switch .25 · compose .20 |

**Profiles** — the same measurements under declared buyer weights
(STREAMER-CN, CREATOR-GLOBAL, LAB; printed in the scorecard, overridable
with `--weights` in both scorer and dashboard). Hard floors stop a
product averaging away a disqualifying flaw (e.g. reliability floor caps
the total). Missing axes renormalize and print coverage %.

**Canonical RTV-Score** (per track — tracks never share a ladder):

```
RTV-Score = 100 × √delivery × (0.40·experience + 0.25·editing
                               + 0.20·ref-control + 0.15·latency)
  delivery   = (S + ½D)/N, adjudicated, E-excluded  (√ damps vantage)
  experience = mean(identity C, artifact B′)        (absolute only)
```

Weight changes are amendments (`docs/rubric-amendments.md`) — v1.0
numbers stay re-derivable from the same journals.

## 11. Verification machinery

- **claims_check** (`tools/claims_check.py`): every number in a shipped
  doc regex-matched against the recomputed truth; `--facts` machine-
  asserts qualitative findings (freeze rates, morph face-sim, ref
  retraction); a registry question without an explicit status fails the
  run. Exit 1 blocks shipping.
- **Blinding keys** per judge run; judgments that can't re-link void.
- **Dated snapshots**: providers hot-deploy; server build strings are
  recorded; results are dated claims.
- **Vantage declaration**: pinned per campaign in `vantage.json`;
  comparisons require matching vantage (`docs/MULTI-VANTAGE.md` is the
  second-vantage runbook).
- **Self-applied honesty**: our own mistakes (field-name traps, retracted
  claims, zombie supervisors) are documented in-repo, not scrubbed.

## 12. Running it

```bash
python3 setup.py                      # wizard: prereqs, venvs, keys,
                                      # live validation, self-test
.venv/bin/python tools/dash.py run    # pick a stage from the menu -
                                      # launches detached, logs to
                                      # data/logs/, readiness-checked
.venv/bin/python tools/dash.py --watch 15   # live mission control
.venv/bin/python tools/dash.py        # results, three layers deep
```

The dashboard launcher (`dash.py run`) is the intended way to start
campaigns: it checks your keys and the stimulus pack, launches the stage
detached, and tells you where the log is. The raw stage commands
(`tools/benchmark_run.py <stage>`) remain for scripting; every stage is
resumable and journaled, so rerunning is always safe.

**The core suite** (`dash.py run core`) is the ≤2-hour, ~$40 reproduction:
a 15-round reliability mini, 12 live-edit sessions per product, then the
full metrics → judging → scorecard chain. Wider CIs, same instruments,
same evidence chain — the affordable datapoint for a new vantage or a
setup sanity-check. Full campaigns are the official-scorecard tier.

## 13. First official scorecard

The 2026-08 evaluation (Lucy 2.5, Xmax X2.0, LingBot-World 2, Happy
Oyster) is the reference run: results in `docs/RESULTS.md` (headline →
axis → sub-metric, with a machine-rendered stat appendix), editing detail
in `docs/d-scorecard.md`, every raw record under `data/`.

## 14. Versioning

Benchmark spec version: **1.1** (adds scored axis G — reference-image
control — see `docs/rubric-amendments.md` Amendment 2; amendments require
an entry there). Stimulus recipes, prompt sets, and the question registry
are part of the version — changing any bumps the minor version; changing
what an existing score *means* bumps the major version.
