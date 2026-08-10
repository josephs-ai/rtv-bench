"""Session driver for callback-based transports (Reactor SDK / WebRTC).

StreamSession pulls from a websocket; the Reactor SDK pushes decoded frames
into a callback. Same measurement semantics, different direction of flow - so
this driver keeps StreamSession's watchdog behaviour (first-frame timeout,
stall watchdog, orchestrator stop, deadline reaper) over an asyncio.Queue fed
by the callback.

Timestamping: `feed()` stamps `base.now()` as its first action. For WebRTC the
SDK has already depacketised and decoded by then - that IS the capture
boundary available to a WebRTC consumer, it is uniform across every
Reactor-served product, and it is stamped in-process with no bridge in the
path. The stamp's position (post-decode) is recorded per run so Lens M timing
is compared only within Lens M, which the lens rule already guarantees.
"""
import asyncio
from typing import List, Optional

import numpy as np

from .base import (FIRST_FRAME_TIMEOUT_S, STALL_TIMEOUT_S, ConnectionInfo,
                   DurationSemantics, FrameEvent, StopReason, StreamResult, now)


class CallbackSession:
    def __init__(self, info: ConnectionInfo, semantics: DurationSemantics,
                 first_frame_timeout_s: float = FIRST_FRAME_TIMEOUT_S,
                 stall_timeout_s: float = STALL_TIMEOUT_S):
        self.info = info
        self.semantics = semantics
        self.first_frame_timeout_s = first_frame_timeout_s
        self.stall_timeout_s = stall_timeout_s

        self.events: List[FrameEvent] = []
        self.request_clock: Optional[float] = None
        self._queue: asyncio.Queue = asyncio.Queue()
        self._stop_requested = asyncio.Event()
        self._error: Optional[str] = None
        self._refused: Optional[str] = None

    # -- callbacks (invoked by the SDK inside the event loop) ----------------

    def feed(self, frame: np.ndarray) -> None:
        """SDK frame callback. Stamp FIRST, everything else after."""
        stamp = now()
        h, w = frame.shape[:2]
        ev = FrameEvent(wall_clock=stamp, frame_index=len(self.events),
                        nbytes=int(frame.nbytes), width=int(w), height=int(h))
        self.events.append(ev)
        self._queue.put_nowait(("frame", ev))

    def feed_error(self, detail: str, refusal: bool = False) -> None:
        if refusal:
            self._refused = detail
        else:
            self._error = detail
        self._queue.put_nowait(("error", detail))

    def request_stop(self) -> None:
        self._stop_requested.set()
        self._queue.put_nowait(("stop", None))

    # -- the drive loop ------------------------------------------------------

    async def run(self, duration_intended_s: Optional[float],
                  capture_path: Optional[str] = None) -> StreamResult:
        self.request_clock = now()
        stop_reason, detail = await self._drive(duration_intended_s)
        return StreamResult(info=self.info, events=self.events,
                           request_clock=self.request_clock, stop_clock=now(),
                           stop_reason=stop_reason,
                           duration_intended_s=duration_intended_s,
                           semantics=self.semantics, error_detail=detail,
                           capture_path=capture_path)

    async def _drive(self, duration_intended_s: Optional[float]):
        deadline = None
        if self.semantics is DurationSemantics.FIXED and duration_intended_s:
            deadline = now() + duration_intended_s + 15.0

        got_first = False
        while True:
            timeout = self.stall_timeout_s if got_first else self.first_frame_timeout_s
            if deadline is not None:
                timeout = min(timeout, max(0.01, deadline - now()))
            try:
                kind, payload = await asyncio.wait_for(self._queue.get(), timeout=timeout)
            except asyncio.TimeoutError:
                if deadline is not None and now() >= deadline:
                    return StopReason.SOURCE_EXHAUSTED, "deadline reaper"
                if not got_first:
                    return StopReason.TIMEOUT_FIRST_FRAME, ""
                # A FIXED source that has already delivered its intended span
                # ends in silence naturally - that is exhaustion, not a stall.
                # (Observed live on echo: clip ends, output stops, watchdog
                # fires 2 s later. Without this, every normal V2V ending would
                # classify F.)
                if (self.semantics is DurationSemantics.FIXED
                        and duration_intended_s is not None
                        and now() - self.request_clock
                        >= duration_intended_s):
                    return StopReason.SOURCE_EXHAUSTED, "input exhausted, output ended"
                return StopReason.STALL, "no frame for %.1f s" % self.stall_timeout_s

            if kind == "stop":
                return StopReason.ORCHESTRATOR, ""
            if kind == "error":
                if self._refused is not None:
                    return StopReason.REFUSED, self._refused
                return StopReason.REMOTE_TEARDOWN, self._error or str(payload)
            got_first = True
