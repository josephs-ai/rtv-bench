"""Rig health: positive controls, not existence checks.

A frozen virtual camera passes "device exists" and "device readable" while
serving one identical frame forever - the failure mode that silently produces
300 confident garbage runs overnight. The playhead check grabs two frames a
second apart and requires them to DIFFER. Existence is never the assertion;
advancement is.

The same module owns the control ping. Together they produce RigEvidence,
which is the only thing allowed to justify an automatic E classification
(see runner.py): E on positive evidence of rig failure, never on ambiguity.
"""
import socket
import time
from typing import Callable, List, NamedTuple, Optional

import numpy as np

# Two frames of a playing source should differ by at least this mean absolute
# luminance. Calibrate in the pilot against the actual reel; a static-scene
# reel segment with only the strip advancing still clears ~0.5 comfortably
# because the frame-index bits flip.
MIN_PLAYHEAD_DELTA = 0.5


class CheckResult(NamedTuple):
    name: str
    ok: bool
    detail: str
    at_monotonic: float
    at_utc: str


class RigEvidence(NamedTuple):
    """Positive evidence of rig failure inside a window. This - and only
    this - licenses an automatic E."""
    checks: List[CheckResult]

    @property
    def rig_failed(self) -> bool:
        return any(not c.ok for c in self.checks)

    def failures(self) -> List[CheckResult]:
        return [c for c in self.checks if not c.ok]


def _utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def playhead_check(grab_frame: Callable[[], Optional[np.ndarray]],
                   interval_s: float = 1.0,
                   min_delta: float = MIN_PLAYHEAD_DELTA,
                   _sleep: Callable[[float], None] = time.sleep) -> CheckResult:
    """The positive control: the source must be *advancing*.

    grab_frame() returns the virtual camera's current frame or None. Two grabs
    `interval_s` apart must differ in mean absolute luminance by min_delta.
    """
    t0 = time.monotonic()
    a = grab_frame()
    if a is None:
        return CheckResult("playhead", False, "first grab returned no frame", t0, _utcnow())
    _sleep(interval_s)
    b = grab_frame()
    if b is None:
        return CheckResult("playhead", False, "second grab returned no frame", t0, _utcnow())
    if a.shape != b.shape:
        # A resolution flap on the rig side is also a failure - the vcam is
        # not serving what it was configured to serve.
        return CheckResult("playhead", False,
                           "frame shape changed %s -> %s" % (a.shape, b.shape),
                           t0, _utcnow())

    delta = float(np.abs(a.astype(np.float64) - b.astype(np.float64)).mean())
    ok = delta >= min_delta
    return CheckResult("playhead", ok,
                       "mean abs delta %.3f (floor %.3f)%s"
                       % (delta, min_delta, "" if ok else " - SOURCE FROZEN"),
                       t0, _utcnow())


def control_ping(host: str = "1.1.1.1", port: int = 443,
                 timeout_s: float = 3.0) -> CheckResult:
    """TCP reachability to a known-good endpoint. Its failure inside a run
    window is what distinguishes 'our network died' from 'their service died'."""
    t0 = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            pass
        return CheckResult("control_ping", True, "%s:%d reachable" % (host, port),
                           t0, _utcnow())
    except OSError as e:
        return CheckResult("control_ping", False, "%s:%d unreachable: %s"
                           % (host, port, e), t0, _utcnow())


def preflight(grab_frame: Callable[[], Optional[np.ndarray]],
              ping_host: str = "1.1.1.1", **kw) -> RigEvidence:
    """Run between runs (addendum Part 8). Cheap enough to be unconditional."""
    return RigEvidence(checks=[playhead_check(grab_frame, **kw),
                               control_ping(host=ping_host)])
