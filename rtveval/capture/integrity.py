"""Capture integrity: CFR verified on the CAPTURE, not just the source.

A CFR source recorded through a VFR-tolerant path (OBS with variable output,
avfoundation under load, a screen-capture fallback) yields VFR output, and VFR
silently breaks every frame-index-based metric downstream: block-strip lag,
per-flash windows, freeze detection by consecutive index, LPIPS frame pairing.

So `check_capture` runs at write-close on every capture, and a VFR verdict is
POSITIVE rig evidence: the run classifies E and re-runs. A re-run costs
minutes; a corrupted row costs the analysis.
"""
import fractions
import os
from typing import List, NamedTuple, Optional

from ..orchestrator.health import CheckResult, _utcnow

# A capture is CFR if the observed inter-frame intervals stay within this
# fraction of the nominal interval. 20% catches genuine VFR while tolerating
# container timestamp rounding.
PTS_JITTER_TOLERANCE = 0.20
# ...and at least this share of intervals must be present at all (a capture
# with gaps in its timeline is not CFR whatever the average says).
MIN_INTERVAL_CONFORMANCE = 0.99


class CaptureReport(NamedTuple):
    path: str
    ok: bool
    nominal_fps: Optional[float]
    n_frames: int
    conforming_intervals: float  # fraction within tolerance
    worst_interval_ratio: float  # worst observed / nominal
    duration_s: float
    nonzero: bool
    detail: str


def probe_intervals(path: str, video_stream: int = 0) -> tuple:
    """(nominal_fps, sorted PTS seconds) via PyAV. Decodes headers + packets,
    not pixels - cheap enough for every capture."""
    import av

    with av.open(path) as container:
        stream = container.streams.video[video_stream]
        nominal = float(stream.average_rate) if stream.average_rate else None
        tb = stream.time_base or fractions.Fraction(1, 90000)
        pts: List[float] = []
        for packet in container.demux(stream):
            if packet.pts is not None:
                pts.append(float(packet.pts * tb))
    return nominal, sorted(pts)


def check_capture(path: str, expected_fps: Optional[float] = None,
                  min_duration_s: Optional[float] = None) -> CaptureReport:
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return CaptureReport(path, False, None, 0, 0.0, 0.0, 0.0, False,
                             "capture missing or zero bytes")

    try:
        nominal, pts = probe_intervals(path)
    except Exception as e:
        return CaptureReport(path, False, None, 0, 0.0, 0.0, 0.0, True,
                             "unreadable capture: %s" % e)

    if expected_fps is not None:
        nominal = expected_fps
    if not nominal or len(pts) < 10:
        return CaptureReport(path, False, nominal, len(pts), 0.0, 0.0, 0.0, True,
                             "too few frames (%d) or unknown rate" % len(pts))

    target = 1.0 / nominal
    intervals = [b - a for a, b in zip(pts, pts[1:])]
    conforming = sum(1 for iv in intervals
                     if abs(iv - target) <= target * PTS_JITTER_TOLERANCE)
    frac = conforming / len(intervals)
    worst = max(intervals) / target
    duration = pts[-1] - pts[0]

    ok = frac >= MIN_INTERVAL_CONFORMANCE
    detail = ("%d frames @ %.6g fps nominal; %.1f%% intervals within %.0f%%; "
              "worst %.2fx" % (len(pts), nominal, frac * 100,
                               PTS_JITTER_TOLERANCE * 100, worst))
    if not ok:
        detail += " - VFR CAPTURE, frame-index metrics unsafe"
    if min_duration_s is not None and duration < min_duration_s:
        ok = False
        detail += "; duration %.1fs < required %.1fs" % (duration, min_duration_s)

    return CaptureReport(path, ok, nominal, len(pts), frac, worst, duration,
                         True, detail)


def as_check(report: CaptureReport) -> CheckResult:
    """Plug into RigEvidence: a bad capture is the rig's fault, so the run is
    E on positive evidence and gets re-run - never a corrupted row."""
    import time
    return CheckResult("capture_cfr", report.ok, report.detail,
                       time.monotonic(), _utcnow())
