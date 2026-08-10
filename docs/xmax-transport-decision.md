# Xmax Native Transport — Investigation & Decision (2026-08-10)

## Question

Xmax's native media plane is a VolcEngine ByteRTC room (session response
carries `rtc_app_id` / `room_token` / `bot_name`). ByteRTC has no official
Python SDK. If the native path had to be browser-based and browser timestamps
are BRIDGED (excluded from Campaign A timing), the §2.1 bridge would lose its
latency leg — and with Lucy absent from Reactor there is no other bridge
candidate.

## Investigation

- `~/.bytertc` on this machine: Lark call telemetry (ByteRTC v3.61 logs),
  nothing scriptable.
- PyPI: no ByteRTC / VolcEngine RTC Python bindings under any plausible name.
- Native C++ SDK wrapping: feasible, days of effort, platform-fragile.
- Xmax docs: no alternate realtime transport (no WHIP/RTMP/websocket egress).
  `/offline-task` exists but is non-realtime (Campaign C quality only).
  Docs note their next-gen realtime model is expected September 2026 —
  X2.0 is the current product (report context).

## Decision: browser client + plan §5.2 composite capture

The BRIDGED rule excludes **SDK-callback timestamps** that cross a browser
bridge. It does not exclude **content-based** measurement. The impulse method
measures latency from frame content (flash in → flash out, recovered by
cross-correlation), which is exactly the plan's original §5.2 design for
closed products:

    virtual camera (instrumented reel) → Xmax browser client (ByteRTC)
    → input + rendered output composited in OBS, one recording
    → impulse extraction from the composite
    → minus the loopback-calibrated rig offset

- Timestamp authority: the OBS capture process — a genuine capture boundary.
- Rig offset: measured with no product in the path (vcam → browser local
  preview → OBS), subtracted, and reported (plan §5.2 calibration rule).
- The composite adds browser-render + capture latency; the calibration
  subtracts its measurable part and the residual is stated as a bound.

## Consequences

- The §2.1 bridge stands: same instrumented clip through Xmax-native
  (composite path, Lens P) and Xmax-on-Reactor (SDK path, Lens M) yields a
  measured Reactor delta, which cross-validates the echo platform floor.
- Lens P Xmax timing carries a "composite-capture method" annotation and its
  calibration offset wherever it appears; it is never silently mixed with
  SDK-path timing.
- Engineering deferred until after the shoot: OBS scene + vcam feed + a
  browser session driver (temp-key minting via POST with expireSeconds /
  pointsLimit is already documented for exactly this client-side use).
