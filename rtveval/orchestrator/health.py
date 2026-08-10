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


# The vantage is part of the rig. Discovered the hard way: the VPN tunnel
# rotated mid-calibration and its churn masqueraded as platform jitter for
# an entire dataset. Tolerance matches the overnight runner's.
VANTAGE_DRIFT_TOLERANCE_MS = 40.0
TURN_HOST = "turn.us-east-1.aws.prod.reactor.inc"


def turn_udp_check(host: str = TURN_HOST, port: int = 3478,
                   timeout_s: float = 4.0) -> CheckResult:
    """WebRTC media path liveness: a STUN binding request must get a reply.
    TCP-only reachability is NOT enough - media rides UDP, and a TCP-fine/
    UDP-dead tunnel produces sessions that establish and streams that never
    flow (observed live)."""
    t0 = time.monotonic()
    try:
        ip = socket.gethostbyname(host)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(timeout_s)
        s.sendto(b'\x00\x01\x00\x00!\x12\xa4B' + b'\x00' * 12, (ip, port))
        s.recvfrom(1024)
        return CheckResult("turn_udp", True, "%s:%d STUN reply" % (host, port),
                           t0, _utcnow())
    except Exception as e:
        return CheckResult("turn_udp", False,
                           "%s:%d no STUN reply (%s) - media path dead"
                           % (host, port, type(e).__name__), t0, _utcnow())


def vantage_drift_check(session_baseline_rtt_ms: float,
                        probe: Callable[[], Optional[float]] = None,
                        tolerance_ms: float = VANTAGE_DRIFT_TOLERANCE_MS) -> CheckResult:
    """The tunnel-churn guard: current baseline RTT vs the SESSION's pinned
    baseline. Drift beyond tolerance means the vantage moved - every affected
    run is E (rig), not data."""
    from . import netshape

    t0 = time.monotonic()
    rtt = (probe or netshape.probe_rtt_ms)()
    if rtt is None:
        return CheckResult("vantage_drift", False, "RTT probe failed", t0, _utcnow())
    drift = abs(rtt - session_baseline_rtt_ms)
    ok = drift <= tolerance_ms
    return CheckResult("vantage_drift", ok,
                       "rtt %.1f ms vs session baseline %.1f (drift %.1f, "
                       "tolerance %.0f)%s" % (rtt, session_baseline_rtt_ms, drift,
                                              tolerance_ms,
                                              "" if ok else " - VANTAGE MOVED"),
                       t0, _utcnow())


def preflight(grab_frame: Callable[[], Optional[np.ndarray]],
              ping_host: str = "1.1.1.1",
              session_baseline_rtt_ms: Optional[float] = None,
              check_turn_udp: bool = False, **kw) -> RigEvidence:
    """Run between runs (addendum Part 8). Cheap enough to be unconditional.

    Campaign runners pass session_baseline_rtt_ms (pinned at campaign start)
    and check_turn_udp=True for any WebRTC product, adding the vantage guards
    to rig evidence - a tunnel switch then classifies runs E instead of
    letting churn impersonate product behaviour."""
    checks = [playhead_check(grab_frame, **kw), control_ping(host=ping_host)]
    if session_baseline_rtt_ms is not None:
        checks.append(vantage_drift_check(session_baseline_rtt_ms))
    if check_turn_udp:
        checks.append(turn_udp_check())
    return RigEvidence(checks=checks)
