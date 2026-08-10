"""Classifier audit against REAL delivery shapes, not synthetic fakes.

The SOURCE_EXHAUSTED bug appeared the moment real frames arrived; this suite
replays the actual echo delivery shape (observed live 2026-08-10: chunk-bursty
4-frame groups at ~133 ms, first frame ~1.9 s after request, 555/600 frames,
natural end via input exhaustion) and walks every branch against it.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rtveval.adapters.base import (ConnectionInfo, DurationSemantics,
                                   FrameEvent, StopReason, StreamResult,
                                   TimestampAuthority)
from rtveval.classify import CaptureQuality, classify

INFO = ConnectionInfo("echo", "M", "0.0.0@1.20260805", "https://api",
                      TimestampAuthority.CAPTURE_BOUNDARY)


def echo_trace(n_frames=555, ttff_s=1.93, burst=4, burst_gap_s=0.1333,
               t0=100.0, mid_stall_at=None, mid_stall_s=0.0):
    """The real echo delivery shape: frames arrive in bursts, not paced."""
    events, t, i = [], t0 + ttff_s, 0
    while i < n_frames:
        for j in range(min(burst, n_frames - i)):
            events.append(FrameEvent(wall_clock=t + j * 0.002, frame_index=i, nbytes=90000,
                                     width=640, height=360))
            i += 1
        t += burst_gap_s
        if mid_stall_at is not None and i >= mid_stall_at and mid_stall_s > 0:
            t += mid_stall_s
            mid_stall_at = None
    return events


def result(events, stop_reason, intended=20.0, request=100.0,
           stop_clock=None):
    return StreamResult(info=INFO, events=events, request_clock=request,
                        stop_clock=stop_clock if stop_clock is not None
                        else (events[-1].wall_clock + 2.0 if events else request),
                        stop_reason=stop_reason, duration_intended_s=intended,
                        semantics=DurationSemantics.FIXED)


def test_real_echo_run_is_not_F():
    """The exact observed run: 555/600 frames, full wall duration, natural
    end. Span (18.5s) < 95% of 20s - the OLD classifier called this F."""
    r = result(echo_trace(), StopReason.SOURCE_EXHAUSTED)
    c = classify(r)
    assert c.outcome == "S", (c.outcome, c.reasons)
    print("  real echo shape (555/600, full wall run): S, not F")


def test_startup_loss_reaches_D_via_dropped_frames():
    """The 45 missing startup frames = 7.5% dropped -> D through the Spec's
    own criterion, from capture quality."""
    r = result(echo_trace(), StopReason.SOURCE_EXHAUSTED)
    c = classify(r, CaptureQuality(dropped_pct=7.5))
    assert c.outcome == "D" and "dropped" in c.reasons[0], c
    print("  startup loss -> D via dropped%% (%s)" % c.reasons[0])


def test_genuinely_early_teardown_still_F():
    """A stream that STOPS at 12s of 20 is still F - wall-clock based."""
    ev = echo_trace(n_frames=300)  # ~10s of delivery
    r = result(ev, StopReason.REMOTE_TEARDOWN, stop_clock=ev[-1].wall_clock + 0.1)
    c = classify(r)
    assert c.outcome == "F" and "output ended" in c.reasons[0], c
    print("  stopped at ~12s of 20s: F (%s)" % c.reasons[0])


def test_burst_gaps_do_not_promote_to_D():
    """133ms burst gaps are normal chunked delivery - far under the 1s freeze
    threshold; a bursty but complete run must stay S."""
    r = result(echo_trace(), StopReason.SOURCE_EXHAUSTED)
    c = classify(r)
    assert c.outcome == "S" and not c.reasons, c
    print("  chunk-bursty delivery alone: S, no D-promotion")


def test_mid_stream_delivery_gap_promotes_to_D():
    """A 1.5s delivery gap mid-run on a full-length FIXED stream: D."""
    ev = echo_trace(mid_stall_at=250, mid_stall_s=1.5)
    r = result(ev, StopReason.SOURCE_EXHAUSTED)
    c = classify(r)
    assert c.outcome == "D" and "delivery gap" in c.reasons[0], c
    print("  1.5s mid-stream gap on full run: D (%s)" % c.reasons[0])


def test_stall_vs_freeze_are_distinct_paths():
    """Delivery stall (no frames arriving) vs content freeze (frames arriving,
    identical content) - different defects, both D on a complete FIXED run."""
    ev = echo_trace()
    frozen = classify(result(ev, StopReason.SOURCE_EXHAUSTED),
                      CaptureQuality(longest_freeze_ms=1400))
    assert frozen.outcome == "D" and "freeze" in frozen.reasons[0]
    gap = classify(result(echo_trace(mid_stall_at=250, mid_stall_s=1.2),
                          StopReason.SOURCE_EXHAUSTED))
    assert gap.outcome == "D" and "delivery gap" in gap.reasons[0]
    print("  freeze (content) and gap (delivery) promote via separate reasons")


def test_open_ended_same_trace_stalls_to_F():
    """The identical mid-stream gap on an OPEN_ENDED stream (>2s) is F."""
    ev = echo_trace(mid_stall_at=250, mid_stall_s=2.5)
    r = StreamResult(info=INFO, events=ev, request_clock=100.0,
                     stop_clock=ev[-1].wall_clock, stop_reason=StopReason.ORCHESTRATOR,
                     duration_intended_s=None,
                     semantics=DurationSemantics.OPEN_ENDED)
    c = classify(r)
    assert c.outcome == "F" and "stalled" in c.reasons[0], c
    print("  same gap, OPEN_ENDED: F (stall)")


def test_reaped_hang_is_F_despite_full_wall_time():
    """Output dies at ~8s, connection idles until the deadline reaper ends the
    run at 35s wall. Wall time says 'full duration'; the output says F. The
    output wins."""
    ev = echo_trace(n_frames=240)  # ~8s of frames
    r = StreamResult(info=INFO, events=ev, request_clock=100.0,
                     stop_clock=135.0, stop_reason=StopReason.SOURCE_EXHAUSTED,
                     duration_intended_s=20.0, semantics=DurationSemantics.FIXED)
    c = classify(r)
    assert c.outcome == "F" and "output ended" in c.reasons[0], c
    print("  8s of output + idle-to-reaper: F (%s)" % c.reasons[0])


def test_wall_clock_kill_shape():
    """Hung stream killed at 35s wall with frames trickling: ran full wall,
    but for a 15s-intended FIXED run frames stopped at 8s -> F."""
    ev = echo_trace(n_frames=240)  # ~8s
    r = StreamResult(info=INFO, events=ev, request_clock=100.0,
                     stop_clock=135.0, stop_reason=StopReason.TRANSPORT_ERROR,
                     duration_intended_s=15.0, semantics=DurationSemantics.FIXED)
    c = classify(r)
    assert c.outcome == "F", c
    print("  transport-errored hang: F")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        print(t.__name__)
        try:
            t()
        except Exception:
            failed += 1
            import traceback
            traceback.print_exc(limit=4)
    print("\n%d/%d passed" % (len(tests) - failed, len(tests)))
    sys.exit(1 if failed else 0)
