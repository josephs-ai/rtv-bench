# RTV Arena — build handoff

Implementation companion to `docs/ARENA.md` (the design spec — read it
first). This document is everything a builder needs that ISN'T in the
spec: decided choices, repo assets to reuse, exact data sources, schemas,
gotchas, and the phase-1 cut. Written so a fresh session/dev can build
without the original conversation.

---

## 1. Decisions already made (do not relitigate without the owner)

| decision | choice | why |
|---|---|---|
| Visual style | **AA-light**: white, minimal chrome, the two videos ARE the page | owner rejected dark/console mocks twice; reference mock approved 08-19 (see §8) |
| Context placement | top-center strip (instruction quote + input-feed thumbnail) | symmetric = fair; doesn't steal width from players |
| Side labels | neutral color dots (teal/amber), never "A/B", never text-only left/right | A/B carries rank priming; left/right breaks on mobile stacking |
| Post-vote reveal | **NEVER reveal during voting** (session-end summary at most) | two-model field: per-vote reveal teaches house styles in ~5 pairs, silently unblinding everything after |
| Leaderboard CI display | inline dot+whisker beside each score | overlap visibility = the honest launch story |
| Vote options | Prefer left / Tie / Both bad / Prefer right | both products artifact heavily; forced choice manufactures signal |
| Below-threshold cells | shown as "collecting (n/100)" — never hidden | show uncertainty early, earn trust later |
| Taxonomy | 5 control-channel chips (spec §2); 3 live at launch, 2 dashed/coming-soon | complete usage partition of an interactive model |
| Categories are governance objects | new chip = amendment | GOVERNANCE.md |
| Human ladder | relative exhibit, never in canonical score | same rule as the 64:0 pairwise sweep |

## 2. What already exists in this repo (reuse, don't rebuild)

- **Blinding pipeline**: `rtveval/rating.py` —
  `normalize_and_blind(items, secret, out_dir, key_path, display,
  crop_margin)` re-encodes to uniform size, crops watermark margins
  (use `crop_margin=0.07`; Lucy stamps an "AI Generated" mark),
  HMAC-names files, writes `key.json` mapping blind_id →
  {product_key, run_id}; refuses to put the key inside the served dir.
  `audit_no_leaks(dir, product_keys)` greps the served tree for product
  strings — run it before every publish. `session_plan(rater, seed,
  clips, hidden_repeats)` gives a seeded order with hidden repeats.
  **Persist the HMAC secret** (`secret.bin` beside the key) — a
  regenerated secret orphans every journaled vote (this bug already bit
  the rating session once; the fix pattern is in
  `tools/rating_session.py`).
- **A working vote-ish UI**: `tools/rating_session.py` — inline HTML
  page, localhost server, journal-per-click, resume, 45-min cap. It is
  single-clip rubric scoring, not pairs, but its serve/journal/resume
  skeleton is the pattern. For the arena, move HTML out of the Python
  string into a static dir (suggest `arena/web/`).
- **α join machinery**: `tools/alpha_report.py` joins human rows to
  judge records via key files on (dimension, run_id). Arena votes join
  the same way through the pair manifest's `source_run_ids` (§5).
- **Screenshot-to-mock flow**: headless Chrome (`--headless=new
  --screenshot`) for design iterations; approved mock recipe in §8.

## 3. Pair sources — exact paths and matching rules

All captures are lossless FFV1 `.mkv` with a sidecar `.json` meta.
Transcode for web: H.264 720p, `-crf 23 -preset slow -movflags
+faststart`, poster frame at t=1s.

### 3.1 Live Transform chip
- **Source**: `data/vlm-judge-b-pairs/` records reference the pairing
  already used for the blinded judge — but re-cut fresh from raw
  captures: `data/campaign-b/captures/` + `data/campaign-b/captures-long/`
  (lucy) and same dirs for xmax (`B-xmax-*`), matched by `round_index`
  and `clip_id` in `data/campaign-b*/runs.jsonl`.
- Match rule: same `input_conform_id` + same `prompt_id` + same
  duration tier; both outcomes ∈ {S, D}.
- ~64 pairs.

### 3.2 Text Direction chip
- **Source**: `data/campaign-d/captures/` — files
  `D-<product>-<edit_id>-<clip>.mkv`; match on identical
  (`edit_id`, `clip`). Meta has `instruction`, `edit_sent_frame`
  (lucy) / `edit_at_s_from_streamup` + `ttff_s` (xmax), `fps`.
- Sustained sub-chip: `data/campaign-g/captures/` (xmax only until
  Lucy's arm runs) — meta has full `edit_schedule`.
- ~24 pairs + sustained singles (single-product categories can't pair —
  hold sustained pairs until Lucy G exists).

### 3.3 Image Direction chip
- **Source**: `data/campaign-f/captures/` — match on identical
  (`job_id` base, i.e. same ref + same clip + same arm; reps pair
  across products by rep index). Meta: `arm` (anchor/hold/switch/
  chain/compose/control), `ref`, `ref2`, `apply_at_s`,
  `apply_sent_frame` (lucy).
- Show the ref portrait from `data/campaign-d/refs/<ref>` in the
  context strip.
- Sub-chips: anchor (F1/F2), mid-video switch (F3/F5 + the probe
  captures in `data/campaign-f/captures-probe/` — note the working
  Xmax switches are the `reconnect` probes).
- ~40 pairs.

### 3.4 EXCLUSION RULES (non-negotiable)
1. **Personal footage never enters the arena.** Any capture whose
   input conform derives from the filmed personal corpus
   (`data/corpus-edit/`, `data/source-footage/`, conform names
   containing `corpus`) is EXCLUDED from public pairs. Only
   mixkit/pexels-stimulus sessions are publishable. Check
   `clip`/`input_conform_id` fields against the stimulus-pack manifest.
2. LingBot rows `-r[123]` are invalidated (degenerate seed) — the
   filter pattern is in `tools/benchmark_score.py`; reuse it. (Only
   matters if worlds ever join the arena.)
3. E-class / `outcome:"F"` / zero-frame / `went_live:false` rows out.
4. Captures with `max_frozen_s` > half the clip = the frozen side of a
   golden pair (§6), never a normal pair.
5. **Wall/file time trap**: Lucy FFV1 captures are CFR-30-labelled at
   ~15 fps delivery — file seconds ≠ wall seconds (ratio ≈ 0.5). When
   cutting clips or placing the instruction marker on the seek bar,
   compute `ratio = ffprobe_duration / (frames / fps_measured)` and
   convert (the fix lives in `tools/campaign_f_metrics.py` and
   `tools/campaign_g_metrics.py` — copy it). Xmax webm→mkv is ~1.0.
6. Licensing check before public hosting (spec §10.3): stimulus clips
   are mixkit/pexels-licensed for use; product OUTPUT clips are
   believed publishable but verify both vendors' ToS on output
   redistribution. **Blocker for phase 2, not phase 1 (local).**

## 4. Repo layout for the build

```
arena/
  generate_pairs.py      # journals -> pair manifest + blinded clips
  compute_bt.py          # vote log -> leaderboard.json (BT + bootstrap CI)
  web/
    index.html           # vote page (approved AA-light layout, §8)
    leaderboard.html
    methodology.html
    sessions.html
    models.html
    app.js  style.css
  serve_local.py         # phase-1: localhost server + POST /vote -> votes.jsonl
data/arena/
  manifest.json          # pair manifest (public fields only)
  manifest-key.json      # source_run_ids + product mapping (NEVER served)
  secret.bin             # HMAC secret (NEVER served)
  clips/                 # blinded web-ready mp4s + posters
  votes.jsonl            # append-only vote log
  leaderboard.json       # computed, published
```

## 5. Schemas

**Pair manifest entry** (public part):
```json
{"pair_id": "tx-004", "category": "text-direction",
 "sub": "garment", "duration_tier": "15s",
 "clip_l": "clips/9f3a.mp4", "clip_r": "clips/1c77.mp4",
 "poster_l": "...", "poster_r": "...",
 "context": {"instruction": "the person now wears a bright red hooded sweatshirt",
              "sent_at_s": 15.0, "ref_image": null, "input_thumb": "clips/in-2960.jpg"},
 "golden": false}
```
Private key file adds: `{"pair_id": {"l": {"product":"...","run_id":"..."},
"r": {...}, "position_seed": 1234}}`. Position (which product is left)
is randomized **per presentation client-side** from a per-vote seed —
the manifest's l/r is canonical storage order only.

**Vote row** (`votes.jsonl`, append-only):
```json
{"t": 1787000000.0, "pair_id": "tx-004", "presented_swap": true,
 "vote": "left|right|tie|both_bad",   // as SEEN by the voter
 "resolved": "lucy-2.5|xmax-x2.0|tie|both_bad",  // after unswap, server-side
 "session_id": "anon-uuid", "rater_id": null,    // named mode optional
 "category": "text-direction", "ms_watched": 41000,
 "golden_ok": null}
```

**Leaderboard json**: per category: `{model, lens, bt, ci_lo, ci_hi,
votes, both_bad_rate, updated}` + `threshold: 100`.

## 6. Integrity mechanics (build order matters)

Phase-1 must-haves: blinding + position randomization per presentation +
append-only vote log + tie/both-bad. Phase-2 adds: golden pairs
(frozen/corrupted sessions vs clean — objective ground truth only, e.g.
the 60-min freeze captures), hidden swapped repeats (~1:12), session
vote cap + cooldown, exposure balancing in the sampler, quarantine of
raters failing goldens (down-weight silently, never block). BT excludes
both-bad votes; both-bad rate reported per model. Bootstrap CIs (1000
resamples). At N=2 models also print plain win-rate — BT adds little
until N≥3, and win-rate communicates better.

## 7. α synergy wiring

`arena/compute_bt.py` should also emit `data/arena/votes-by-run.jsonl`
(vote → source_run_ids via the private key). A follow-up to
`tools/alpha_report.py` can then join crowd preference vs the pairwise
judge verdicts (`data/vlm-judge-b-pairs/records.jsonl`) on run_id pairs
→ judge-vs-crowd agreement per category. This closes registry Q8.1 at
scale and directly answers the "not human-based" objection.

## 8. The approved look (regenerate the reference mock)

The owner approved this exact layout 08-19 (after rejecting two dark
mocks). Recipe: white bg; slim header "RTV Arena" + 5 pill chips
(active = purple #7c3aed outline w/ light fill; future chips dashed
grey); right-side "Input shown | Hidden" segmented toggle; context
strip top-center = input-feed thumbnail (~104×60) beside the quoted
instruction in ~21px bold with a grey one-liner under it; two 16:9
players side-by-side, rounded 14px, tiny teal/amber dot top-left of
each; ONE shared seek bar (purple fill, white-ringed dot marking the
instruction timestamp); vote row: big outlined "← Prefer left" (teal) /
small "Tie" / small "Both bad" / big "Prefer right →" (amber); grey
micro-footer "N votes this session · next pair preloaded". Mock source
survives at `/tmp/arena-mock.html` in the build session; if lost,
rebuild from this paragraph — it renders in one screen.

## 9. Phase-1 definition of done (local demo)

- `generate_pairs.py` builds ≥60 pairs across the 3 live chips from
  the journals, with exclusions (§3.4) enforced and `audit_no_leaks`
  passing
- `serve_local.py` serves the vote page; voting works end-to-end with
  keyboard; votes land in `votes.jsonl` with unswap resolution
- `compute_bt.py` produces a leaderboard page with win-rate + CI and
  "collecting" states
- Methodology + sessions pages render (static text, links into the
  repo)
- A 10-minute self-vote session produces a sane leaderboard
- NOTHING deployed publicly (licensing check §3.4.6 gates phase 2)

## 10. Open items owed to the owner

1. Brand/hosting decision (under RTV-Bench identity or standalone)
2. Phase-2 licensing verification of output-clip redistribution
3. Golden-pair curation sign-off (proposed: objective failures only)
4. Whether sustained-direction pairs wait for Lucy's campaign G arm
   (recommended: yes — single-product cells can't pair)
5. Arena directive + this handoff are NOT yet in ROADMAP (owner
   declined an earlier roadmap edit made under a misunderstanding; ask
   before adding)
