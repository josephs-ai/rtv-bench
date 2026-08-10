"""Shared websocket streaming loop - the machinery every adapter reuses.

The adapters differ in handshake, message vocabulary, and how the served
version is resolved. They do not differ in the run loop, and keeping the loop
here is what makes rule 2 (one normalised event stream) true by construction
rather than by review.

Timestamping: `base.now()` is called in `_receive_loop` immediately on
`recv()` returning, before JSON parsing, decode, or disk write. That is the
capture boundary for a websocket transport. Nothing here ever accepts a
timestamp provided by the remote end or by a browser context.
"""
import asyncio
import json
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import websockets

from .base import (FIRST_FRAME_TIMEOUT_S, STALL_TIMEOUT_S, ConnectionInfo,
                   DurationSemantics, FrameEvent, StopReason, StreamResult, now)


class RefusalDetected(Exception):
    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


def make_refusal_matcher(patterns: Sequence[str]) -> Callable[[str], Optional[str]]:
    """Per-product refusal-pattern list, maintained from the pilot
    (addendum Part 5). Case-insensitive substring match is deliberate - these
    are vendor error strings, not a stable API."""
    lowered = [p.lower() for p in patterns]

    def match(text: str) -> Optional[str]:
        low = text.lower()
        for p in lowered:
            if p in low:
                return p
        return None

    return match


class StreamSession:
    """One live websocket run. Adapter supplies protocol callbacks; the loop,
    watchdogs, and event stamping live here."""

    def __init__(self, ws, info: ConnectionInfo, semantics: DurationSemantics,
                 classify_message: Callable[[Any], Tuple[str, Optional[Dict]]],
                 refusal_matcher: Callable[[str], Optional[str]],
                 first_frame_timeout_s: float = FIRST_FRAME_TIMEOUT_S,
                 stall_timeout_s: float = STALL_TIMEOUT_S):
        """`classify_message(raw)` -> (kind, meta) where kind is one of
        "frame" | "control" | "error", and meta for frames may carry
        nbytes/width/height. This is the only protocol-specific seam."""
        self.ws = ws
        self.info = info
        self.semantics = semantics
        self.classify_message = classify_message
        self.refusal_matcher = refusal_matcher
        self.first_frame_timeout_s = first_frame_timeout_s
        self.stall_timeout_s = stall_timeout_s

        self.events: List[FrameEvent] = []
        self.request_clock: Optional[float] = None
        self._stop_requested = asyncio.Event()

    def request_stop(self) -> None:
        """The orchestrator's stop signal. For OPEN_ENDED streams this is the
        only *normal* way a run ends - teardown before it is a failure."""
        self._stop_requested.set()

    async def run(self, send_request: Callable[[], Any],
                  duration_intended_s: Optional[float],
                  capture_path: Optional[str] = None) -> StreamResult:
        self.request_clock = now()
        await send_request()

        stop_reason = StopReason.ORCHESTRATOR
        error_detail = ""
        try:
            stop_reason, error_detail = await self._receive_loop(duration_intended_s)
        except RefusalDetected as e:
            stop_reason, error_detail = StopReason.REFUSED, e.detail
        except (websockets.ConnectionClosedError, OSError) as e:
            stop_reason, error_detail = StopReason.TRANSPORT_ERROR, str(e)

        return StreamResult(
            info=self.info, events=self.events,
            request_clock=self.request_clock, stop_clock=now(),
            stop_reason=stop_reason,
            duration_intended_s=duration_intended_s,
            semantics=self.semantics,
            error_detail=error_detail, capture_path=capture_path,
        )

    async def _receive_loop(self, duration_intended_s: Optional[float]
                            ) -> Tuple[StopReason, str]:
        frame_index = 0
        deadline_task: Optional[asyncio.Task] = None
        if self.semantics is DurationSemantics.FIXED and duration_intended_s:
            # Safety margin: the source drives the length; this only reaps a
            # stream whose remote end forgot to close.
            deadline_task = asyncio.create_task(asyncio.sleep(duration_intended_s + 15.0))

        try:
            while True:
                timeout = (self.first_frame_timeout_s if frame_index == 0
                           else self.stall_timeout_s)
                recv_task = asyncio.create_task(self.ws.recv())
                stop_task = asyncio.create_task(self._stop_requested.wait())
                waiters = {recv_task, stop_task} | ({deadline_task} if deadline_task else set())
                done, _ = await asyncio.wait(waiters, timeout=timeout,
                                             return_when=asyncio.FIRST_COMPLETED)

                if not done:  # timeout fired
                    recv_task.cancel(); stop_task.cancel()
                    if frame_index == 0:
                        return StopReason.TIMEOUT_FIRST_FRAME, ""
                    return StopReason.STALL, ("no frame for %.1f s" % timeout)

                if stop_task in done:
                    recv_task.cancel()
                    return StopReason.ORCHESTRATOR, ""
                if deadline_task and deadline_task in done:
                    recv_task.cancel(); stop_task.cancel()
                    return StopReason.SOURCE_EXHAUSTED, "deadline reaper"

                stop_task.cancel()
                try:
                    raw = recv_task.result()
                except websockets.ConnectionClosedOK:
                    return StopReason.REMOTE_TEARDOWN, "clean close"

                stamp = now()  # capture boundary: before parse, before decode

                kind, meta = self.classify_message(raw)
                if kind == "frame":
                    meta = meta or {}
                    self.events.append(FrameEvent(
                        wall_clock=stamp, frame_index=frame_index,
                        nbytes=meta.get("nbytes", len(raw) if isinstance(raw, (bytes, str)) else 0),
                        width=meta.get("width"), height=meta.get("height")))
                    frame_index += 1
                elif kind == "error":
                    detail = json.dumps(meta) if meta else str(raw)[:500]
                    hit = self.refusal_matcher(detail)
                    if hit:
                        raise RefusalDetected("matched %r in: %s" % (hit, detail[:200]))
                    return StopReason.REMOTE_TEARDOWN, detail
                # "control" messages fall through silently
        finally:
            if deadline_task:
                deadline_task.cancel()
