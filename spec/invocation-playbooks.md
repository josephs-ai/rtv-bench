# Invocation Playbooks

**Rule zero: a wrong-invocation "failure" is a benchmark bug, not a
product finding.** Before any capability-failure claim ships, the exact
invocation must be traced against the product's own client (vendor
source, not docs or recall) and listed here. Every trap below was found
the hard way in the 2026-08 reference run; several briefly produced
false "product broken" findings before being caught.

---

## Xmax X2.0 (browser SDK, lens P-browser)

Client: official browser SDK, `tools/xmax_browser/vendor/index.js`,
driven headlessly (`native_lane.html` + campaign drivers). The SDK
**silently drops unknown fields** — wrong names never error.

**Session lifecycle**
- Connect: `client.realtime.connect(stream, {model, context, onRemoteStream})`.
  Context is normalized by `normalizeRealtimeContext` — it keeps ONLY
  `prompt` and `refImageUrl`. Anything else is stripped without error.
- Mid-stream text edit: `session.set({prompt})` **flat form**;
  `{context:{prompt}}` silently no-ops. (Mirror of the connect-time trap.)
- Temp keys (`mint_xmax_temp_key`): treat as **single-generation** — a
  reused key on a second session in one page produced degraded/failed
  ref application. Mint per session.

**Reference images**
- Field name is **`refImageUrl`** at the session API layer. `refImage` /
  `refImagePath` are internal names (event-builder layer) — passing them
  from app code = silently stripped = the retracted 08-15 "ref channel
  dead" finding.
- Upload via the SDK's own flow: `client.files.uploadAndCheckImage(file)`
  → safety-checked vendor-COS URL. (NOT `client.uploadImage` — not a
  function.) Requires the real `cos-js-sdk-v5` UMD loaded as a **classic
  script** (`vendor/cos-umd.js`); as an ES import its `this`-global write
  fails.
- Anchoring is **session-scoped**. No in-session event re-anchors:
  `change_condition` (set) transmits the ref but the backend ignores it;
  mid-session re-`start` / `stopGeneration`+`start` revert to input
  identity. **Mid-video character switch = re-session**: disconnect →
  **~4 s settle** → fresh `captureStream` → fresh temp key → connect with
  `context:{prompt: BASE_PROMPT, refImageUrl}`. Without the settle or
  with a reused key it fails or partials. Measured gap ≈3.2 s frozen.
- **Serialize all Xmax work**: concurrent sessions on one account poison
  ref anchoring (proven confound — a probe running beside a campaign
  made proven-good anchors fail). Never run probes beside a pass.
- Ref channel boundaries (product behavior, not traps): photo-portrait
  refs only; needs a dominant visible face; person-targeted text edits
  reset the anchor.

**Capture rig**
- Record from a canvas (frames emitted unconditionally) so leading black
  = TTFF signal; `<video>` captureStream would start at first real frame.
- After `session.disconnect()` the published tracks are stopped — any new
  session needs a **fresh** `srcv.captureStream(30)`.

## Lucy 2.5 / Decart (native WebRTC, lens P)

Client: `rtveval/adapters/decart_webrtc.py` (aiortc), frames via
`frame_tap`.
- Force TURN-TCP (`RTVEVAL_FORCE_TURN_TCP=1`) from this vantage; latency
  measured through tunnel is vantage-bound and must not enter axis
  scoring.
- Text edit: WS `{"type":"prompt","prompt",...,"enhance_prompt":false}`.
- Ref image: WS `{"type":"set_image","image_data":<b64>,"prompt":...}` —
  works mid-stream (anchor-at-start = send it at t≈1 s). No URL channel.
- Output carries an "AI Generated" watermark (frame-region caveat for
  pixel metrics).
- Delivered fps ≈15–17, not the 30 the capture label says — schedule
  edits on **wall time from first frame**, never frame counts.
- Runtime stimulus looping is unreliable (stall at clip boundary):
  pre-build long stimuli with `-stream_loop` into a single file.
- Credit exhaustion presents as session reject `Insufficient credits` —
  it is an env fault (E-class), not a product failure.

## Happy Oyster (dedicated SDK, browser lane)

- Use the dedicated `@reactor-models/happy-oyster` SDK:
  `connect → createWorld → startTravel` opens the second Aliyun RTC
  connection; `instruct()` = steering. Placeholder frames pass weak
  gates — verify content visually before calling a capture real.
- WebRTC path is VPN-window dependent from this vantage.

## LingBot-World 2

- **`set_image` is REQUIRED before `start`** — the model is image-anchored
  ("a reference image establishes visual identity", Reactor model guide).
  The 2026-08 reference run drove it text-only: out of contract, output
  degenerates into macroblock garbage. ALL of that run's LingBot rows are
  invalid tests (caught 08-18 during the human rating session — a rater
  flagged the corruption; the docs check took 10 minutes). Correct flow:
  connect → set_image → set_prompt → start. Streams 1664×960@48 fps —
  budget decode accordingly.
- Frames polled; count frames delivered vs promised — never assume the
  manifest.

## Cross-product rules

- One product, one lens, one journal — never mixed.
- Every capture's meta must name: lens, mechanism (exact call path),
  stimulus, and any invocation deviation from this playbook.
- New trap discovered → add it here in the same PR as the fix; a trap
  that only lives in a commit message is scattered knowledge (the thing
  this file exists to prevent).
