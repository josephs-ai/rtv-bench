"""Adapter contract: every product, native or Reactor-served, speaks this shape.

Three rules that exist because getting them wrong corrupts data silently:

1.  **Duration semantics are per-category, not global.** The Spec's F rule
    (teardown before `duration_intended x 0.95`) assumes a fixed intended
    duration. That holds for V2V (output is bounded by the input reel) and
    digital human (bounded by the script audio). It is not well-defined for
    generation: LingBot and Happy Oyster run until told to stop, so "ended
    early" has no meaning. For open-ended streams, failure is a *stall* (no new
    frame for STALL_TIMEOUT_S) or teardown before the orchestrator's own stop
    signal. `DurationSemantics` carries this; the classifier branches on it.

2.  **Every adapter emits the same frame-arrival event stream** -
    (wall_clock, frame_index, nbytes). Freeze detection, delivered fps, dropped
    frames, and generation divergence timing all derive from this one shape, so
    the classifier is written once, against one interface, instead of once per
    SDK. Adding Xmax next to Decart is then a connect() implementation, nothing
    downstream changes.

3.  **Timestamps are taken at the capture boundary.** `FrameEvent.wall_clock`
    is stamped by the process that receives the bytes - the Python websocket
    reader or the ffmpeg capture process - never by JavaScript inside a
    Playwright page. Anything crossing the browser bridge picks up event-loop
    delay, which lands inside sub-frame precision. If a UI-fallback adapter
    cannot stamp at the boundary, it must say so in `ConnectionInfo.
    timestamp_authority` so Campaign A can exclude it from timing entirely.
"""
import abc
import enum
import time
from typing import AsyncIterator, List, NamedTuple, Optional

from ..routing import DIGITAL_HUMAN, GENERATION, V2V

# Open-ended stream: no new frame for this long = the stream has died,
# whatever the transport thinks.
STALL_TIMEOUT_S = 2.0

# Spec Part A: no first frame within 30 s of request = Timeout.
FIRST_FRAME_TIMEOUT_S = 30.0


class DurationSemantics(enum.Enum):
    # Output duration is bounded by the input (V2V reel, digital-human audio).
    # Early teardown against duration_intended is meaningful and classifies F.
    FIXED = "fixed"
    # Stream runs until the orchestrator stops it. There is no "ended early";
    # failure is a stall or a teardown before OUR stop signal.
    OPEN_ENDED = "open_ended"


CATEGORY_SEMANTICS = {
    V2V: DurationSemantics.FIXED,
    DIGITAL_HUMAN: DurationSemantics.FIXED,
    GENERATION: DurationSemantics.OPEN_ENDED,
}


class TimestampAuthority(enum.Enum):
    CAPTURE_BOUNDARY = "capture_boundary"  # stamped where the bytes arrive
    BRIDGED = "bridged"  # crossed a browser/IPC bridge - EXCLUDED from timing


class FrameEvent(NamedTuple):
    """One frame arrival. The normalised shape everything downstream consumes."""

    wall_clock: float  # time.monotonic() at the capture boundary
    frame_index: int  # 0-based arrival index
    nbytes: int
    # Optional: set when the transport reports it (resolution change mid-stream
    # forces outcome D per addendum Part 5).
    width: Optional[int] = None
    height: Optional[int] = None


class ConnectionInfo(NamedTuple):
    """What connect() learned. Written into the run row verbatim."""

    product_key: str
    lens: str  # "P" | "M"
    # Resolved at connect time from the server handshake / catalog - NEVER
    # echoed from config. If the vendor updates the model mid-study, the run
    # rows disagree with each other, and that is exactly the signal wanted:
    # segment the analysis by version rather than discover the change later.
    resolved_version: str
    endpoint: str
    timestamp_authority: TimestampAuthority
    region: Optional[str] = None
    advertised_fps: Optional[float] = None
    advertised_resolution: Optional[str] = None


class StopReason(enum.Enum):
    ORCHESTRATOR = "orchestrator"  # we sent the stop signal (normal, open-ended)
    SOURCE_EXHAUSTED = "source_exhausted"  # input reel/audio finished (normal, fixed)
    REMOTE_TEARDOWN = "remote_teardown"  # server closed on us
    STALL = "stall"  # no frame within STALL_TIMEOUT_S
    TRANSPORT_ERROR = "transport_error"
    REFUSED = "refused"  # policy refusal recognised (Spec outcome R)
    TIMEOUT_FIRST_FRAME = "timeout_first_frame"


class StreamResult(NamedTuple):
    """Everything a finished (or dead) stream hands to the classifier."""

    info: ConnectionInfo
    events: List[FrameEvent]
    request_clock: float  # monotonic at request send - TTFF baseline
    stop_clock: float  # monotonic when the stream ended, either side
    stop_reason: StopReason
    duration_intended_s: Optional[float]  # None for OPEN_ENDED
    semantics: DurationSemantics
    error_detail: str = ""
    capture_path: Optional[str] = None


class Adapter(abc.ABC):
    """One per route. Native adapters carry Lens P, Reactor carries Lens M."""

    product_key: str
    lens: str
    semantics: DurationSemantics

    @abc.abstractmethod
    async def connect(self) -> ConnectionInfo:
        """Open the session and resolve the served model version.

        Must fail loudly if the version cannot be resolved - a run row without
        a resolved version violates hard rule 5.
        """

    @abc.abstractmethod
    async def run(self, clip_path: Optional[str], prompt: str,
                  duration_intended_s: Optional[float],
                  condition_id: str) -> StreamResult:
        """Execute one run and return the normalised result.

        Implementations stamp FrameEvents with time.monotonic() at the point
        bytes arrive, before any decode or disk write.
        """

    @abc.abstractmethod
    async def close(self) -> None: ...


def now() -> float:
    """The one clock. Monotonic - wall time appears only in run metadata."""
    return time.monotonic()


# ---------------------------------------------------------------------------
# Derived series - the reason the event shape exists. Everything here is pure
# and unit-tested; adapters never reimplement any of it.
# ---------------------------------------------------------------------------

def ttff_ms(result: StreamResult) -> Optional[float]:
    if not result.events:
        return None
    return (result.events[0].wall_clock - result.request_clock) * 1000.0


def delivered_fps(events: List[FrameEvent]) -> Optional[float]:
    if len(events) < 2:
        return None
    span = events[-1].wall_clock - events[0].wall_clock
    return (len(events) - 1) / span if span > 0 else None


def arrival_gaps_s(events: List[FrameEvent]) -> List[float]:
    return [b.wall_clock - a.wall_clock for a, b in zip(events, events[1:])]


def stall_events(events: List[FrameEvent], threshold_s: float = STALL_TIMEOUT_S
                 ) -> List[tuple]:
    """(index, gap_s) for every inter-frame gap over threshold.

    This is *delivery* stalling - distinct from content freeze (identical
    frames arriving on time), which the classifier detects from perceptual
    hashes of the capture. Both matter; they are different defects.
    """
    return [(i, g) for i, g in enumerate(arrival_gaps_s(events)) if g > threshold_s]


def resolution_changes(events: List[FrameEvent]) -> List[int]:
    """Frame indices where reported resolution changed (forces outcome D)."""
    out = []
    last = None
    for e in events:
        if e.width is None:
            continue
        cur = (e.width, e.height)
        if last is not None and cur != last:
            out.append(e.frame_index)
        last = cur
    return out
