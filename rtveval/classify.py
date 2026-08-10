"""Automated outcome classification (Spec Part A, addendum Part 5).

Consumes the normalised StreamResult - one code path for every product, because
adapters all emit the same FrameEvent shape. The classifier never touches an
SDK type.

Branches on duration semantics:

  FIXED       (V2V, digital human)  "ended early" is meaningful: teardown
              before duration_intended x 0.95 is F.
  OPEN_ENDED  (generation)          there is no "ended early". F is a stall
              (no frame for STALL_TIMEOUT_S) or a remote teardown before the
              orchestrator's own stop signal.

Content-level defects (freeze = identical frames arriving on time; dropped
frames >5%) come from the capture, not the transport, and are supplied by the
caller as CaptureQuality. The classifier combines both views.

E (environment) is decided by the orchestrator's health checks, outside this
module: a classifier that can quietly blame the rig would launder product
failures.
"""
from typing import List, NamedTuple, Optional

from .adapters.base import (DurationSemantics, FIRST_FRAME_TIMEOUT_S,
                            STALL_TIMEOUT_S, StopReason, StreamResult,
                            resolution_changes, stall_events)

S, D, F, T, R = "S", "D", "F", "T", "R"

EARLY_TEARDOWN_FRACTION = 0.95  # Spec: teardown before intended x 0.95 = F
DROPPED_PCT_DEGRADED = 5.0
FREEZE_MS_DEGRADED = 1000.0


class CaptureQuality(NamedTuple):
    """Content-level measurements from the capture file (perceptual hashes)."""

    dropped_pct: Optional[float] = None
    freeze_count: int = 0
    freeze_total_ms: float = 0.0
    longest_freeze_ms: float = 0.0


class Classification(NamedTuple):
    outcome: str  # S | D | F | T | R
    reasons: List[str]

    @property
    def enters_quality_scoring(self) -> bool:
        return self.outcome in (S, D)


def classify(result: StreamResult,
             capture: Optional[CaptureQuality] = None) -> Classification:
    reasons: List[str] = []

    # --- R: policy refusal, reported separately, never a defect -------------
    if result.stop_reason is StopReason.REFUSED:
        return Classification(R, ["policy refusal: %s" % (result.error_detail or "unspecified")])

    # --- T: no first frame within 30 s --------------------------------------
    if not result.events:
        if result.stop_reason is StopReason.TIMEOUT_FIRST_FRAME:
            return Classification(T, ["no first frame within %.0f s" % FIRST_FRAME_TIMEOUT_S])
        return Classification(F, ["stream never produced a frame (%s: %s)"
                                  % (result.stop_reason.value, result.error_detail)])

    first_gap = result.events[0].wall_clock - result.request_clock
    if first_gap > FIRST_FRAME_TIMEOUT_S:
        return Classification(T, ["first frame after %.1f s (limit %.0f s)"
                                  % (first_gap, FIRST_FRAME_TIMEOUT_S)])

    # --- F: branch on duration semantics ------------------------------------
    if result.stop_reason is StopReason.TRANSPORT_ERROR:
        return Classification(F, ["transport error: %s" % result.error_detail])

    if result.semantics is DurationSemantics.FIXED:
        if result.duration_intended_s is None:
            raise ValueError("FIXED semantics require duration_intended_s")
        actual_s = result.events[-1].wall_clock - result.events[0].wall_clock
        if actual_s < result.duration_intended_s * EARLY_TEARDOWN_FRACTION:
            return Classification(F, [
                "ended at %.1f s of %.1f s intended (%.0f%% rule)"
                % (actual_s, result.duration_intended_s, EARLY_TEARDOWN_FRACTION * 100)])
    else:  # OPEN_ENDED - generation
        # Failure is a stall or the server hanging up before OUR stop signal.
        stalls = stall_events(result.events)
        if result.stop_reason is StopReason.STALL or stalls:
            worst = max((g for _, g in stalls), default=STALL_TIMEOUT_S)
            return Classification(F, [
                "stream stalled: %.1f s without a frame (threshold %.1f s)"
                % (worst, STALL_TIMEOUT_S)])
        if result.stop_reason is StopReason.REMOTE_TEARDOWN:
            return Classification(F, [
                "remote teardown before orchestrator stop: %s"
                % (result.error_detail or "no detail")])

    # --- D: degraded but complete -------------------------------------------
    # Mid-run delivery stalls on FIXED streams that still reached full length
    # count as freezes at delivery level.
    for idx, gap in stall_events(result.events, threshold_s=FREEZE_MS_DEGRADED / 1000.0):
        reasons.append("delivery gap %.1f s at frame %d" % (gap, idx))

    for idx in resolution_changes(result.events):
        reasons.append("resolution change mid-stream at frame %d" % idx)

    if capture is not None:
        if capture.dropped_pct is not None and capture.dropped_pct > DROPPED_PCT_DEGRADED:
            reasons.append("dropped frames %.1f%% > %.0f%%"
                           % (capture.dropped_pct, DROPPED_PCT_DEGRADED))
        if capture.longest_freeze_ms >= FREEZE_MS_DEGRADED:
            reasons.append("content freeze %.0f ms (>= %.0f ms)"
                           % (capture.longest_freeze_ms, FREEZE_MS_DEGRADED))

    if reasons:
        return Classification(D, reasons)
    return Classification(S, [])
