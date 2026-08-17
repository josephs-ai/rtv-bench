# RTV-Bench Question Registry

**This file is the benchmark.** Every question RTV-Bench asks, in one
place: what is asked, which campaign answers it, with what stimulus and
instrument, where the evidence lives, and its current answer status for
the reference run (2026-08). Campaign drivers are *executors* of this
registry — a question that isn't in this file isn't part of the
benchmark, and a registry question without a recorded answer must be
marked `pending`, never silently skipped.

Status legend: **answered** (recorded + scored) · **partial** (some
products/arms) · **pending** (designed, not run) · **n/a** (doesn't apply
to that track).

Products, reference run: Lucy 2.5 (lens P / P native), Xmax X2.0 (lens
P-browser; lens M = via-Reactor), LingBot-World 2, Happy Oyster.

---

## Track 1 — Interactive video (V2V)

### Q1. Reliability — does a live session deliver?

| # | question | campaign/arm | stimulus | instrument | metric | records | status |
|---|---|---|---|---|---|---|---|
| Q1.1 | Does a session survive 15 s / 60 s / 3 min? | B (300-round duration mix) | conform reel | outcome taxonomy | S/D/F/T/R/E rates + Wilson CIs | `data/campaign-b/runs.jsonl`, `data/campaign-b-native/runs.jsonl`, preserved-tally.json | answered (Lucy N=210, Xmax-browser N=91, Xmax-M N=85 tail pending) |
| Q1.2 | How fast does first content arrive (TTFF)? | B | conform reel | capture analyzer (first non-black frame) | ttff_s | same journals | answered |
| Q1.3 | Are failures the product's fault? | B adjudication | — | 3-layer attribution (sentinel, in-run guards, cross-product correlation) | E-class exclusions w/ evidence | `data/campaign-b/adjudications.json` | answered |
| Q1.4 | Does a session survive 10 / 30 / 60 minutes? | E (hour-scale) | 65-min single-shot loop | per-frame telemetry + net probes | survival_frac, mean_fps | `data/campaign-e/runs.jsonl` | partial (Lucy 10-min r1 only; 30/60 + Xmax pending) |

### Q2. Output quality — does it look right?

| # | question | campaign/arm | stimulus | instrument | metric | records | status |
|---|---|---|---|---|---|---|---|
| Q2.1 | Which product looks better on identical input? | B v2 (64 pairs) | same-input pairs | blinded pairwise VLM judge (forced choice, 4 dims) | win rates (relative exhibit, never in ladder) | `data/vlm-judge-*/records.jsonl` + per-run keys | answered (Lucy 64–0) |
| Q2.2 | How artifact-laden is output, absolutely? | B v2 audit | capture windows | 10-class artifact audit w/ onset times, schema-forced | median window burden /18 → B′ | `data/vlm-judge-audit/records.jsonl` | answered (12.3 vs 14.1) |
| Q2.3 | Temporal coherence / flicker? | quality metrics | captures | LPIPS frame-pair | flicker score | `data/quality-metrics/` | answered |
| Q2.4 | Motion fidelity + physics pops? | quality metrics | captures | RAFT flow comparison | motion corr, pop count | same | answered |
| Q2.5 | Is the face still the same person over time? | quality metrics + E stills | captures | ArcFace/insightface embedding drift | identity floor/median vs t=0 | same + `data/campaign-e/*/stills` | answered (morph finding: intermittent, r281 replayable; controls held in F7) |
| Q2.6 | Does output follow the prompt? | quality metrics | captures | CLIP adherence | adherence score | same | answered |
| Q2.7 | Scene drift over a session? | quality metrics | captures | DINOv2 drift | drift score | same | answered |
| Q2.8 | A/V sync? | quality metrics | corpus reads | FaceMesh mouth-offset | offset ms | same | answered (exhibit; scored axis is v1.1) |

### Q3. Live editing — does mid-stream direction land?

| # | question | campaign/arm | stimulus | instrument | metric | records | status |
|---|---|---|---|---|---|---|---|
| Q3.1 | Does a text edit at t=15 s commit, and how fast? | D (9 edit types × 3 clips) | conforms + 4 externals | edit metrics + 5-dim blinded edit judge | commit latency, application | `data/edit-metrics/`, `data/edit-judge/records.jsonl`, `data/campaign-d/scorecard.json` | answered |
| Q3.2 | Is the edit surgical or does it rewrite the world? | D | same | collateral index | collateral | same | answered |
| Q3.3 | Does the edit hold (residue / revert / oscillation)? | D | same | residue + stability | hold verdicts | same | answered (single-face clips; multi-person region-tracking unreliable — judge is primary) |
| Q3.4 | Does identity survive the edit? | D | same | direction-aware identity | identity-through-edit | same | answered |

### Q4. Reference-image control — the preset-character interaction

| # | question | campaign/arm | stimulus | instrument | metric | records | status |
|---|---|---|---|---|---|---|---|
| Q4.1 | Does a ref portrait anchor the character at session start? | F1 (4 refs × 4 clips × 2) | conforms + 4 refs | face-sim timeline (2 s cadence) | sim-to-ref vs sim-to-input post-anchor | `data/campaign-f/metrics/summary.json` + per-run timelines | answered both (Xmax 16/16 dominant-face only; **Lucy also anchors crowds** — adoption 60.0 vs 37.5) |
| Q4.2 | Can a ref deliver an attribute text can't (hair)? | F1 blonde ref | blonde ref | same | sim + eyeball/judge | same | answered both (yes on both) |
| Q4.3 | Do stylized (non-photo) refs work? | F1/F2 styl | Vermeer PD portrait | same | sim | same | answered both (photo-only on both; 1 Lucy partial) |
| Q4.4 | Does anchored identity hold over minutes? | F2 (180 s ×3) | ref-woman/styl | hold slope | slope/min, last-30 s | same | answered both (Xmax flat 2/2; Lucy 1/2 + 1 no-data capture) |
| Q4.5 | Does self-ref anchoring prevent identity morph? | F7 (self-ref ×3 vs control ×3, 90 s) | self-crop ref | hold slope differential | selfref vs control slope | same | answered both (no differential claimable on either — controls held; morph intermittent) |
| Q4.6 | Can the character be switched mid-video, and how? | F3/F5 + probe series | 2 refs | face-sim + mechanism probes | switch latency, adoption, transition gap | same + `data/campaign-f/captures-probe/*.json` | answered Xmax (in-session events 0/16; **re-session works 2/2**, ~3.2 s gap + settle); Lucy running |
| Q4.7 | Do text edits work ON an anchored character? | F4 (D-taxonomy ×2) | ref-woman + 4 edits | face-sim + eyeball/judge | edit applied? anchor kept? | same | answered both (Xmax scene-level keeps anchor; **Lucy: any text edit evicts the anchor, 0/8**) |
| Q4.8 | Ref-image full character switch (legacy D arm) | D character-man/woman | 2 refs | edit judge | application/hold | `data/edit-judge/records.jsonl` | answered (Lucy 3.4 s applies+holds; Xmax superseded by Q4.6 mechanism map) |

### Q5. Latency

| # | question | campaign/arm | stimulus | instrument | metric | records | status |
|---|---|---|---|---|---|---|---|
| Q5.1 | Motion-to-glass latency, styled? | latency arm | flash-reel | motion cross-correlation | ms | `data/campaign-b/vantage.json` + latency records | answered Xmax-native (983 ms); Lucy vantage-bound (~2.6–2.7 s through tunnel — excluded from axis, needs clean vantage) |
| Q5.2 | What does an aggregator cost in ms? | bridge (dual-route) | same | same model dual-routed | overhead ms | `data/bridge-measurement.json` | answered |

### Q6. Market access

| # | question | campaign/arm | stimulus | instrument | metric | records | status |
|---|---|---|---|---|---|---|---|
| Q6.1 | Reachable from mainland China? | deploy probe | — | route/DNS/VPN matrix | direct / VPN-viable / blocked | vantage records | answered |

---

## Track 2 — Interactive worlds

| # | question | campaign/arm | stimulus | instrument | metric | records | status |
|---|---|---|---|---|---|---|---|
| Q7.1 | Did it build what was asked? | C (prompt battery) | world-prompts w/ checkable assertions | assertion checks + blinded judge | adherence | `data/campaign-c-gen/` | answered (HO via dedicated SDK; LingBot 19/21 frames) |
| Q7.2 | Is the physics plausible? | C | same | judge + computed physics | physics score | same | answered |
| Q7.3 | Object permanence? | C | same | judge | permanence | same | answered |
| Q7.4 | Same world after a minute? | C long-horizon | same | judged + computed blend | long-horizon hold | same | answered |
| Q7.5 | Does a text direction steer the story? | C steering (instruct) | steer prompts | judge | steering | same | answered |
| Q7.6 | Build speed? | C | — | wall-clock | s | same | answered (exhibited, not scored) |

Track 2 moves to **maintenance mode after boss sign-off** (user decision:
focus on realtime videogen).

---

## Cross-cutting (apply to every question above)

- Lens separation; vantage pinned; dated snapshots; blinding keys per run
  (`BENCHMARK.md` ground rules).
- Every shipped number passes `tools/claims_check.py` (regex claims +
  `--facts` machine assertions).
- **Completeness rule (to be enforced in claims_check, v1.2):** every row
  in this registry must be answered or explicitly `pending` — silent gaps
  fail the run.

## Open / pending queue (reference run)

2. Q1.4 hour-scale 30/60-min tiers + Xmax counterpart (browser chunked
   upload unbuilt).
3. Q1.1 Lens M tail (244 slots).
4. Q5.1 Lucy clean-vantage latency.
5. Campaign F blinded judge pass (content-drift/safety observations
   flagged 08-17: wide-shot attire render, beach re-dress).
6. HO final 10 captures (VPN-window dependent).
