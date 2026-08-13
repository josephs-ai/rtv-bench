# Happy Oyster (Reactor SDK) — attach_world Regression Report

Date: 2026-08-13 · Context: real-time video product evaluation · Account: Reactor company key ([redacted], account_id [redacted])

## Summary

**The `attach_world` command has been a server-side no-op since Aug 12.** World generation itself succeeds on your servers (we receive the world ID and a CDN first-frame screenshot showing correct content), but the WebRTC video track never switches to world content — it stays on the flat solid-color placeholder indefinitely. Our SDK integration is unchanged; the identical code path worked on Aug 10–11. **This is not an integration error on our side and is unrelated to the separate credits issue.**

## Timeline (UTC+8)

| Time | Event |
|---|---|
| Aug 10–11 | HO director captures via reactor-sdk work normally (create_world → ready → attach_world → real world frames) |
| Aug 12 daytime | First failure observed: flat color field after attach; reproduced in 3 independent live probes same day |
| Aug 12 17:46 | Our browser-capture workaround (see below) collects real content successfully — proving the worlds exist and render on reactor.inc web |
| Aug 13 01:57 | Automated overnight captures reconfirm the SDK path is still broken: e.g. one session waited 365 s, 0 frames passed our content gate |
| Aug 13 ~01:45+ | All sessions rejected with 402 credits_depleted (separate issue) |

## Technical evidence (all archived, available on request)

1. **World generation succeeds** (full message log `ho-attach-proof.json`):
   - `world_state` progresses `creating → building (generating) → ready` in ~55–80 s;
   - The ready payload carries `encrypted_world_id=dHpmaEU0lINZtc81EZgHEr6q_8ZMxUX8rgtjL4WoCOc`, a first-frame CDN screenshot URL (cdn3.aorizon.cn — opens fine, correct content), and `api_base_url=https://ws-gp1v1hyjh3vn9ar2.ap-southeast-1.maas.aliyuncs.com/api/v2/apps/happyoyster-1.0`.
   - **The world is built and its content exists server-side.**
2. **attach_world has no effect**: sent after `phase=ready`, no error, no reply (fire-and-forget), and the video track content never changes. We sampled **434 consecutive raw frames in one session: per-frame pixel standard deviation 0.0 on every frame** (pure solid color).
3. **Both models affected**: `reactor/happy-oyster-director` and `reactor/happy-oyster-adventure` reproduce identically.
4. **Server build in failing sessions: `0.0.0@1.20260811.21506`.** We observed multiple server-side deploys during our study window (20260805 → 20260810 → 20260811.21506); the regression onset coincides with a deploy, while our client code did not change.
5. **Cost impact**: on the night of Aug 12–13, 7 capture sessions each held a billed session open for 286–365 s and produced 0 usable frames (`went_live=false` in every session meta), plus the 3 daytime verification probes.

## What we ruled out

- Same SDK, same network, same night: **LingBot-World 2 captures succeeded 19/21** → transport and integration are fine.
- Correct sequencing: we only send `attach_world` after `phase=ready`, matching observed platform behavior.
- Not a wrong command name: the platform sends no error for unknown commands, so we verified via full message logs.

## Current workaround on our side

We capture the reactor.inc web playground's WebGL canvas via Chrome DevTools Protocol screenshots. This works — which further isolates the bug to the SDK/WebRTC track routing, since the web client can display the same worlds.

## Requests

1. **Fix** the WebRTC track routing after `attach_world` (the world ID and timestamps above should locate it in your logs).
2. **Credit refund** for the zero-output billed session time on Aug 12–13 (~7 sessions × 5–6 min, plus 3 probes).
3. **An ETA** — we have paused all HO SDK captures until the fix to avoid burning further credits on flat frames.

Contact: happy to provide full message logs, session timestamps, and the flat-frame captures.
