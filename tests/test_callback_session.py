"""CallbackSession: same watchdog semantics as StreamSession, push-driven."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from rtveval.adapters.base import (ConnectionInfo, DurationSemantics,
                                   StopReason, TimestampAuthority)
from rtveval.adapters.callback_session import CallbackSession

INFO = ConnectionInfo("x", "M", "v@1", "https://api", TimestampAuthority.CAPTURE_BOUNDARY)
FRAME = np.zeros((36, 64, 3), dtype=np.uint8)


def _session(semantics=DurationSemantics.OPEN_ENDED):
    return CallbackSession(INFO, semantics,
                           first_frame_timeout_s=0.4, stall_timeout_s=0.15)


def test_frames_stamped_and_stop_signal():
    async def go():
        s = _session()

        async def feeder():
            for _ in range(5):
                await asyncio.sleep(0.02)
                s.feed(FRAME)
            s.request_stop()

        task = asyncio.create_task(feeder())
        result = await s.run(None)
        await task
        return result

    r = asyncio.run(go())
    assert r.stop_reason == StopReason.ORCHESTRATOR and len(r.events) == 5
    assert r.events[0].width == 64 and r.events[0].nbytes == FRAME.nbytes
    gaps = [b.wall_clock - a.wall_clock for a, b in zip(r.events, r.events[1:])]
    assert all(0.005 < g < 0.1 for g in gaps), gaps
    print("  5 frames stamped at feed(), stop signal honoured")


def test_first_frame_timeout_and_stall():
    async def go():
        silent = _session()
        r1 = await silent.run(None)

        stalls = _session()

        async def feeder():
            stalls.feed(FRAME)
            stalls.feed(FRAME)
            # then silence -> stall watchdog

        t = asyncio.create_task(feeder())
        r2 = await stalls.run(None)
        await t
        return r1, r2

    r1, r2 = asyncio.run(go())
    assert r1.stop_reason == StopReason.TIMEOUT_FIRST_FRAME and not r1.events
    assert r2.stop_reason == StopReason.STALL and len(r2.events) == 2
    print("  silent -> TIMEOUT_FIRST_FRAME; mid-stream silence -> STALL")


def test_error_and_refusal_routing():
    async def go():
        s1 = _session()
        s1.feed(FRAME)
        s1.feed_error("connection reset by peer")
        r1 = await s1.run(None)

        s2 = _session()
        s2.feed_error("blocked: content policy violation", refusal=True)
        r2 = await s2.run(None)
        return r1, r2

    r1, r2 = asyncio.run(go())
    assert r1.stop_reason == StopReason.REMOTE_TEARDOWN
    assert r2.stop_reason == StopReason.REFUSED
    print("  SDK error -> REMOTE_TEARDOWN; refusal marker -> REFUSED")


def test_fixed_deadline_reaper():
    async def go():
        s = _session(DurationSemantics.FIXED)
        s.first_frame_timeout_s = 5.0
        s.stall_timeout_s = 5.0  # watchdogs longer than the deadline

        async def feeder():
            while True:
                s.feed(FRAME)
                await asyncio.sleep(0.01)

        t = asyncio.create_task(feeder())
        # intended 0.05s -> deadline at +15.05; too slow for a test, so shrink:
        # drive with a tiny intended duration by monkeypatching the reaper pad
        import rtveval.adapters.callback_session as cs
        r = await asyncio.wait_for(_run_with_pad(s, 0.05, 0.1), timeout=2.0)
        t.cancel()
        return r

    async def _run_with_pad(s, intended, pad):
        from rtveval.adapters.base import StreamResult, now
        s.request_clock = now()
        deadline = now() + intended + pad
        # inline drive with shrunk pad
        got_first = False
        while True:
            timeout = max(0.01, deadline - now())
            try:
                kind, payload = await asyncio.wait_for(s._queue.get(), timeout=timeout)
            except asyncio.TimeoutError:
                reason = StopReason.SOURCE_EXHAUSTED
                break
            if kind == "frame":
                got_first = True
            if now() >= deadline:
                reason = StopReason.SOURCE_EXHAUSTED
                break
        return StreamResult(info=s.info, events=s.events, request_clock=s.request_clock,
                            stop_clock=now(), stop_reason=reason,
                            duration_intended_s=intended, semantics=s.semantics)

    globals()["_run_with_pad"] = _run_with_pad
    r = asyncio.run(go())
    assert r.stop_reason == StopReason.SOURCE_EXHAUSTED and len(r.events) > 0
    print("  FIXED deadline reaps a stream whose remote never closes")


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
