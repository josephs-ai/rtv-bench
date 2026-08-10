"""Classifier semantics and the shared streaming loop, against a fake socket.

The load-bearing distinctions:
  - FIXED: early teardown is F under the 95% rule.
  - OPEN_ENDED: the same teardown pattern is only F when it precedes the
    orchestrator's stop signal; there is no "ended early".
  - Stall (delivery gap) fails an open-ended stream even if the transport
    stays up.
  - Timestamps come from the receiving side, never the payload.
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rtveval.adapters.base import (DurationSemantics, FrameEvent, StopReason,
                                   StreamResult, ConnectionInfo,
                                   TimestampAuthority, delivered_fps,
                                   stall_events, ttff_ms)
from rtveval.classify import CaptureQuality, classify

INFO = ConnectionInfo(product_key="test", lens="P", resolved_version="v1",
                      endpoint="wss://x", timestamp_authority=TimestampAuthority.CAPTURE_BOUNDARY)


def mk_events(n, fps=30.0, t0=100.0, gap_at=None, gap_s=0.0):
    """n frames at fps, optionally with one long delivery gap."""
    events, t = [], t0
    for i in range(n):
        if gap_at is not None and i == gap_at:
            t += gap_s
        events.append(FrameEvent(wall_clock=t, frame_index=i, nbytes=1000))
        t += 1.0 / fps
    return events


def mk_result(events, semantics, stop_reason, intended=None, request_clock=99.5,
              detail=""):
    return StreamResult(info=INFO, events=events, request_clock=request_clock,
                        stop_clock=events[-1].wall_clock if events else request_clock,
                        stop_reason=stop_reason, duration_intended_s=intended,
                        semantics=semantics, error_detail=detail)


def test_fixed_early_teardown_is_F():
    events = mk_events(int(30 * 8))  # 8 s delivered of 15 intended
    r = mk_result(events, DurationSemantics.FIXED, StopReason.REMOTE_TEARDOWN,
                  intended=15.0)
    c = classify(r)
    assert c.outcome == "F", c
    print("  FIXED, 8s of 15s: F (%s)" % c.reasons[0])


def test_open_ended_same_pattern_needs_stop_signal():
    """Identical delivery, but generation semantics: remote teardown before our
    stop is F; teardown AT our stop is S."""
    events = mk_events(int(30 * 8))
    before_stop = mk_result(events, DurationSemantics.OPEN_ENDED,
                            StopReason.REMOTE_TEARDOWN)
    assert classify(before_stop).outcome == "F"

    at_stop = mk_result(events, DurationSemantics.OPEN_ENDED,
                        StopReason.ORCHESTRATOR)
    c = classify(at_stop)
    assert c.outcome == "S", c
    print("  OPEN_ENDED: teardown-before-stop F, stop-signal S - '95%% rule' never consulted")


def test_open_ended_stall_is_F_even_with_transport_up():
    events = mk_events(200, gap_at=100, gap_s=3.0)
    r = mk_result(events, DurationSemantics.OPEN_ENDED, StopReason.ORCHESTRATOR)
    c = classify(r)
    assert c.outcome == "F" and "stalled" in c.reasons[0], c
    print("  OPEN_ENDED, 3s gap mid-stream: F (%s)" % c.reasons[0])


def test_fixed_full_length_with_gap_is_D_not_F():
    """A FIXED stream that reaches full length despite a 1.5s delivery gap is
    degraded, not failed."""
    events = mk_events(int(30 * 15) + 60, gap_at=200, gap_s=1.5)
    r = mk_result(events, DurationSemantics.FIXED, StopReason.SOURCE_EXHAUSTED,
                  intended=15.0)
    c = classify(r)
    assert c.outcome == "D", c
    print("  FIXED, full length, 1.5s gap: D (%s)" % c.reasons[0])


def test_timeout_and_refusal():
    t = mk_result([], DurationSemantics.FIXED, StopReason.TIMEOUT_FIRST_FRAME,
                  intended=15.0)
    assert classify(t).outcome == "T"
    r = mk_result([], DurationSemantics.OPEN_ENDED, StopReason.REFUSED,
                  detail="content policy violation")
    c = classify(r)
    assert c.outcome == "R" and not c.enters_quality_scoring
    print("  T and R classified; R excluded from quality scoring")


def test_capture_quality_promotes_to_D():
    events = mk_events(int(30 * 16))
    r = mk_result(events, DurationSemantics.FIXED, StopReason.SOURCE_EXHAUSTED,
                  intended=15.0)
    assert classify(r).outcome == "S"
    c = classify(r, CaptureQuality(dropped_pct=7.2, longest_freeze_ms=1200))
    assert c.outcome == "D" and len(c.reasons) == 2, c
    print("  content-level defects promote S -> D: %s" % "; ".join(c.reasons))


def test_derived_series():
    events = mk_events(31, fps=30.0, t0=100.0)
    r = mk_result(events, DurationSemantics.FIXED, StopReason.SOURCE_EXHAUSTED,
                  intended=1.0, request_clock=99.8)
    fps = delivered_fps(events)
    assert abs(fps - 30.0) < 0.01, fps
    assert abs(ttff_ms(r) - 200.0) < 1e-6
    assert stall_events(events) == []
    print("  delivered_fps %.1f, ttff %.0f ms, no stalls" % (fps, ttff_ms(r)))


# ---------------------------------------------------------------------------
# The streaming loop against a fake websocket
# ---------------------------------------------------------------------------

class FakeWS:
    """Feeds a scripted message sequence; records nothing, blocks like a socket."""

    def __init__(self, script):
        # script: list of (delay_s, payload) - payload bytes/str, or Exception
        self._script = list(script)
        self.sent = []

    async def send(self, data):
        self.sent.append(data)

    async def recv(self):
        if not self._script:
            await asyncio.sleep(3600)  # silent socket: watchdogs must fire
        delay, payload = self._script.pop(0)
        await asyncio.sleep(delay)
        if isinstance(payload, Exception):
            raise payload
        return payload


def _session(ws, semantics):
    from rtveval.adapters.ws_common import StreamSession, make_refusal_matcher

    def classify_msg(raw):
        if isinstance(raw, bytes):
            return "frame", {"nbytes": len(raw)}
        msg = json.loads(raw)
        return ("error", msg) if msg.get("type") == "error" else ("control", msg)

    return StreamSession(ws, INFO, semantics, classify_msg,
                         make_refusal_matcher(("content policy",)),
                         first_frame_timeout_s=0.5, stall_timeout_s=0.2)


def test_session_stamps_on_receipt_and_stops_on_signal():
    async def go():
        ws = FakeWS([(0.01, b"x" * 100)] * 5)
        s = _session(ws, DurationSemantics.OPEN_ENDED)
        asyncio.get_event_loop().call_later(0.2, s.request_stop)
        result = await s.run(lambda: ws.send("start"), None)
        return result

    r = asyncio.run(go())
    assert r.stop_reason == StopReason.ORCHESTRATOR
    assert len(r.events) == 5
    gaps = [b.wall_clock - a.wall_clock for a, b in zip(r.events, r.events[1:])]
    assert all(0.005 < g < 0.1 for g in gaps), gaps
    print("  session: 5 frames stamped on receipt, clean stop on signal")


def test_session_first_frame_timeout():
    async def go():
        ws = FakeWS([])  # never sends anything
        s = _session(ws, DurationSemantics.OPEN_ENDED)
        return await s.run(lambda: ws.send("start"), None)

    r = asyncio.run(go())
    assert r.stop_reason == StopReason.TIMEOUT_FIRST_FRAME and not r.events
    print("  session: silent socket -> TIMEOUT_FIRST_FRAME")


def test_session_stall_watchdog():
    async def go():
        ws = FakeWS([(0.01, b"f1"), (0.01, b"f2")])  # then silence
        s = _session(ws, DurationSemantics.OPEN_ENDED)
        return await s.run(lambda: ws.send("start"), None)

    r = asyncio.run(go())
    assert r.stop_reason == StopReason.STALL and len(r.events) == 2
    print("  session: mid-stream silence -> STALL after watchdog")


def test_session_refusal_detection():
    async def go():
        ws = FakeWS([(0.01, json.dumps({"type": "error",
                                        "message": "Content Policy violation"}))])
        s = _session(ws, DurationSemantics.OPEN_ENDED)
        return await s.run(lambda: ws.send("start"), None)

    r = asyncio.run(go())
    assert r.stop_reason == StopReason.REFUSED, r.stop_reason
    assert classify(r).outcome == "R"
    print("  session: vendor policy string -> REFUSED -> outcome R")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        print(t.__name__)
        try:
            t()
        except Exception as e:
            failed += 1
            print("  FAIL: %s: %s" % (type(e).__name__, e))
    print("\n%d/%d passed" % (len(tests) - failed, len(tests)))
    sys.exit(1 if failed else 0)
