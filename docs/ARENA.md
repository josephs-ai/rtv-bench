# RTV Arena — human-rated comparison arena for interactive video

Design specification. Reference model: `artificialanalysis.ai/video/arena`
(the VOD arena) — we borrow its mechanics where they work and replace its
taxonomy, because its three chips (Text-to-Video / Image-to-Video / Video
Editing) partition *what you feed* an offline model, and an interactive
model is defined by *how you steer it while it runs*.

Relationship to RTV-Bench: the arena is the **human layer** on top of the
same sessions the benchmark measures. Every clip pair comes from a
journaled benchmark session; every vote doubles as judge-calibration data
(Q8.1). The human ladder is a **relative exhibit** beside the machine
axes — same rule as the pairwise 64:0 — never inside the canonical score.

---

## 1. What we take from Artificial Analysis, and what we change

**Keep (proven mechanics):**
- Side-by-side blind pairs, instant next-pair flow
- Keyboard voting (← prefer left, → prefer right), play/pause/restart
- Category chips selected before voting
- A condition toggle in the header (theirs: With/No Audio)
- Per-category leaderboards fed by the votes

**Change:**
- **Taxonomy**: control channels, not input types (§2)
- **Votes**: add **Tie** and **Both bad** (our audit data says both
  products artifact heavily on hard workloads; forcing a winner on two
  failures manufactures signal)
- **Provenance**: their clips are generated for the arena; ours are
  journaled benchmark sessions with dated, vantage-declared, re-derivable
  histories — the About page makes this a feature
- **No user-submitted prompts at launch** (their "Submit a prompt"):
  our pairs must be *same input + same instruction* captures of live
  sessions; ad-hoc prompts would need live infrastructure per vote.
  Phase-3 option (§9).

## 2. Categories — the complete control-channel taxonomy

A live model's entire interface is: the stream itself, plus the channels
you can steer it through. One chip per channel primitive:

| chip | channel | what a voter judges | pairs from |
|---|---|---|---|
| **Live Transform** | the stream itself (no direction) | looks right? stays stable? stays *you*? | campaigns B, E (64 B-v2 pairs ready) |
| **Text Direction** | words, mid-stream | did the instruction land, cleanly, and hold? | campaigns D, G (48 + 12 sessions) |
| **Image Direction** | pixels as control (ref anchor / mid-video switch) | did they become the shown reference? scene preserved? switch clean? | campaign F (130 sessions) |
| **Direct Manipulation** | gesture/spatial: drag, camera, pose | did the world obey the hand? how tightly? | campaign H (to be built — Xmax SDK already ships drag surfaces) |
| **Audio Direction** | sound as control / lip-sync | — | placeholder chip until any product exposes the channel |

Rules: combinations (ref + text, drag + prompt) never get chips — they
vote inside their dominant channel. New channel primitive ⇒ new chip via
amendment (`GOVERNANCE.md`). If scope widens beyond Xmax/Lucy to world
models, **World Generation** (prompt → explorable world) slots in as the
Text-to-Video analog.

**Filters (the "With Audio" slot — conditions, not usages):**
- **Show input / Hide input** — with the source feed visible (side strip
  or PiP) you judge *fidelity to direction*; hidden, pure output quality.
  Default: shown for Text/Image/Manipulation chips, hidden for Live
  Transform.
- **Session length** — 15 s / 3 min / 30 min+ chips (duration is a
  stress condition on the same three usages)
- Within Text Direction: edit-type sub-chips (garment · hair ·
  background · style · **sustained 8-edit**)
- Within Image Direction: **anchor** · **mid-video switch**

## 3. Pages

### 3.1 `/` — Vote  (layout: AA-style, decided 08-19)
Design rule: **the two videos ARE the page.** Light, minimal chrome,
exactly like the AA arena — no instrumented side columns, no console
aesthetics. Everything that isn't the two players lives in a compact
top strip.

Top-to-bottom:
1. Slim header: category chips + filter toggles (one row)
2. **Context strip (top-center, symmetric)** — per category:
   - Text Direction: the instruction in large quoted text
     ("Change the jacket to red leather"), with a small marker on the
     shared seek bar showing when it was sent
   - Image Direction: the reference portrait as a modest thumbnail,
     center-top (click to enlarge)
   - Live Transform with input shown: small source-clip thumbnail,
     center-top, synced
   - Sustained: current instruction, updating as each fires
3. **Two large side-by-side players** — dominant, equal size,
   frame-synced (one play/pause/restart + shared scrub), loop on end;
   neutral-color side markers (no A/B)
4. One vote row directly beneath: **← Prefer left · Tie · Both bad ·
   Prefer right →**, auto-advance on vote
Center-top context placement keeps symmetry (equidistant from both
players) — the fairness property, without a middle column stealing
width from the videos.
- Keyboard-first (←/→/=/x, space to pause); large tap targets, players
  stack vertically on mobile with context strip persisting on top
- Preload next pair during current playback (10–90 s clips; without
  preload the arena feels broken)
- Quiet vote counter in the corner; never a running result tally
  (no per-vote reveal — two-model fields leak identity through reveals,
  see §5)

### 3.2 `/leaderboard`
- Tabs per category + Overall
- **Bradley-Terry** scores with bootstrap 95% CIs (BT handles ties;
  both-bad recorded but excluded from BT, reported as a per-model
  "both-bad rate" — itself a quality signal)
- Columns: model · lens (native / browser / via-aggregator — lenses
  never merge, same as the benchmark) · BT score ± CI · votes · both-bad
  rate · last-updated
- A cell publishes only past **minimum vote count** (launch: 100 votes
  per category-pair); below threshold shows "collecting"
- Built for N models from day one even though it launches with two

### 3.3 `/methodology`
- How pairs are made: same input clip + same instruction + same session
  protocol, from journaled RTV-Bench sessions; link to the registry row
  and capture journals
- Blinding: renamed files, uniform watermark crop, no product-revealing
  UI, position randomized per vote
- Vote statistics: BT model, tie handling, CI method, thresholds
- Voter screening (§5) described honestly
- What the arena does NOT claim: absolute quality, latency numbers
  (instrumented separately), anything below vote thresholds

### 3.4 `/sessions` (About the clips)
- The provenance page: every clip pair links to its session metadata
  (date, vantage, product version string, instruction, journal row).
  This is the anti-"cherry-picked demos" page and our biggest
  differentiator over generated-for-arena content.

### 3.5 `/models`
- Per-model card: lens(es), version strings observed, category BT
  scores, link to the benchmark's machine axes for the same product —
  the "human ladder vs machine axes" side-by-side is the whole story
  in one view

### 3.6 Non-public
- `/admin`: pair inventory & exposure balance, vote stream, screening
  flags, golden-pair accuracy dashboards
- Pair generator (CLI, in-repo): builds the arena manifest from
  benchmark journals (§4)

## 4. Pair pipeline (in-repo, deterministic)

1. **Match**: from journals, select capture pairs with identical
   (input clip, instruction/ref, protocol, duration tier) across
   products; exclude E-class/invalid rows automatically (the LingBot
   r1–r3 filter pattern generalizes)
2. **Blind**: existing `rtveval/rating.py` pipeline — re-encode to
   uniform size/codec, uniform edge crop (watermarks), HMAC filenames,
   key file kept server-side only, leak audit before publish
3. **Package**: web-ready transcode (H.264 720p + poster frame),
   pair manifest row: `{pair_id, category, filters, clip_a, clip_b,
   context (instruction/ref/edit timeline), source_run_ids (private
   side), created_at}`
4. **Publish** to CDN/static hosting; manifest hash journaled so the
   served set is auditable

Launch inventory from existing captures: ~64 Live Transform pairs,
~24 Text Direction (+6 sustained), ~40 Image Direction — enough for
weeks of casual voting before repeats.

## 5. Vote integrity (the bias machinery)

- **Blinding** as above; **position randomized** per presentation
- **Golden pairs**: a small set with unambiguous ground truth (e.g. one
  side is a frozen/corrupted session) mixed in ~1:15; raters who fail
  goldens get their votes down-weighted/quarantined, silently
- **Hidden repeats**: same pair re-shown swapped later in a session →
  intra-rater consistency (the rating-session mechanism, generalized)
- **Rate limits & dedup**: per-session vote cap before a cooldown,
  IP+device heuristics, no login required (friction kills arenas) but
  optional named-rater mode for contributors who want their votes to
  count toward judge-α with attribution
- **Exposure balancing**: pair sampler keeps per-category and per-model
  exposure even; no model gets soft-hidden
- **Tie / Both bad** always available — forced-choice-only inflates
  noise into signal
- All raw votes journaled append-only; leaderboard re-derivable from the
  vote log (same evidence standard as the benchmark)

## 6. The α synergy (why the arena feeds the benchmark)

Arena pairs are the same captures the VLM judge scored pairwise. A vote
therefore joins to judge verdicts through `source_run_ids` exactly like
`alpha_report.py` joins rating journals today:
- judge-vs-crowd agreement per category → the α ≥ 0.67 trust gate gets
  its human baseline **at scale**, closing Q8.1 as a side effect
- disagreement clusters (humans prefer A, judge prefers B) become the
  judge's error taxonomy — reviewable, publishable
- named-rater votes additionally feed human-human α

## 7. Architecture (launch-grade, boring on purpose)

- **Frontend**: static site (any framework), clips + manifest from CDN;
  no server rendering needed
- **Vote backend**: one serverless endpoint (`POST /vote`) appending to
  a vote log + a scheduled job recomputing BT + publishing a static
  leaderboard JSON the frontend reads. No database bigger than that at
  launch
- **Media**: object storage + CDN; ~130 pairs × 2 clips × ~15 MB ≈
  4 GB — trivial
- **Privacy**: no accounts, no PII beyond standard abuse telemetry;
  named-rater mode is opt-in
- Cost order-of-magnitude: static hosting + CDN egress, tens of
  dollars/month at hobby scale

## 8. Governance

- Category set changes via amendment (like axes)
- Model/lens inclusion: same rules as the benchmark (real sessions,
  declared lens, journaled); vendors may submit sessions via
  `docs/SUBMITTING.md` — pairs only enter after verification
- Human ladder = relative exhibit; never in canonical; the site says so
- Vote log + manifest hashes are the audit trail

## 9. Phasing

- **Phase 1 (prototype, ~days)**: local/static arena from existing
  pairs, three live chips, vote log to a file — enough to demo the
  boss and validate the UX
- **Phase 2 (public)**: hosting, vote backend, screening, leaderboard
  publication, the five-chip layout with Direct Manipulation marked
  "campaign H in progress" and Audio "awaiting vendor support"
- **Phase 3 (optional)**: live-prompt mode (voter types an instruction,
  both products execute it live, capture becomes a new pair) — the
  AA "Submit a prompt" analog; needs per-vote session infrastructure
  and spend controls, so explicitly out of launch scope

## 10. Open questions

1. Hosting/brand: under the benchmark's identity or its own?
2. Vote threshold and BT prior at N=2 models (pairwise win-rate + CI
   may communicate better than BT until N≥3)
3. Whether Lucy-side captures need re-consent review before public
   hosting (stimulus clips are licensed stock; outputs are product
   renders — believed fine, verify licenses before Phase 2)
4. Who moderates golden-pair selection (must not encode our own bias —
   candidates: sessions with objective failures like permanent freezes)
