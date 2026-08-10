"""Generation latency: API send timestamp -> first output frame that visibly
diverges from the pre-steer baseline.

There is no input frame to correlate against, so neither impulse nor block strip
applies. What is measurable is the moment the stream stops being what it was.

The subtlety is the noise floor. A generative stream is never static - it
evolves frame to frame even with no new instruction - so "diverges" has to mean
"departs from its own ongoing rate of change", not "differs from a fixed
reference". The pre-steer window establishes that rate; divergence is the first
sustained excursion above it.

Sustained is load-bearing. A single frame over threshold is noise. The default
requires the excursion to hold for `sustain_frames`, which is what separates a
real steer from a flicker.
"""
from typing import NamedTuple, Optional, Sequence

import numpy as np

from .base import Interval, LatencySample, Method


class Divergence(NamedTuple):
    frame_index: Optional[int]
    lag_ms: Optional[float]
    threshold: float
    baseline_mean: float
    baseline_sd: float
    confidence: float
    reason: str = ""


def frame_distances(frames: Sequence[np.ndarray]) -> np.ndarray:
    """Per-frame distance from the preceding frame.

    Mean absolute difference on luminance. Cheap, and adequate because we are
    detecting a change in the *rate* of change, not characterising it. Swap in a
    CLIP embedding distance if a steer is semantic but photometrically subtle
    (e.g. "make the car a truck" at constant palette).
    """
    def lum(f: np.ndarray) -> np.ndarray:
        if f.ndim == 3:
            return f[..., :3].astype(np.float64) @ np.array((0.2126, 0.7152, 0.0722))
        return f.astype(np.float64)

    out = np.zeros(len(frames), dtype=np.float64)
    if len(frames) < 2:
        return out
    prev = lum(frames[0])
    for i in range(1, len(frames)):
        cur = lum(frames[i])
        out[i] = float(np.abs(cur - prev).mean())
        prev = cur
    return out


def find_divergence(distances: np.ndarray, steer_frame: int, fps: float,
                    baseline_frames: int = 30, k_sigma: float = 4.0,
                    sustain_frames: int = 3,
                    search_limit_ms: float = 10000.0) -> Divergence:
    """First sustained departure from the pre-steer rate of change.

    `steer_frame` is the output-stream frame index corresponding to the API send
    timestamp; the caller derives it from the run log and the capture's start
    time. Everything before it defines the baseline.
    """
    lo = max(0, steer_frame - baseline_frames)
    baseline = distances[lo:steer_frame]
    if len(baseline) < 5:
        return Divergence(None, None, 0.0, 0.0, 0.0, 0.0,
                          "pre-steer window too short (%d frames)" % len(baseline))

    mu = float(baseline.mean())
    sd = float(baseline.std())
    # A perfectly static baseline would give sd=0 and a threshold equal to the
    # mean, which fires on the first dither. Floor it.
    sd = max(sd, 1e-3)
    threshold = mu + k_sigma * sd

    limit = min(len(distances), steer_frame + int(round(search_limit_ms * fps / 1000.0)))
    run = 0
    for i in range(steer_frame, limit):
        if distances[i] > threshold:
            run += 1
            if run >= sustain_frames:
                first = i - sustain_frames + 1
                lag_ms = (first - steer_frame) * 1000.0 / fps
                peak = float(distances[first:i + 1].max())
                conf = float(np.clip((peak - threshold) / max(threshold - mu, 1e-6), 0.0, 1.0))
                return Divergence(first, lag_ms, threshold, mu, sd, conf)
        else:
            run = 0

    return Divergence(None, None, threshold, mu, sd, 0.0,
                      "no sustained divergence within %.0f ms - steer ignored?"
                      % search_limit_ms)


def measure(frames: Sequence[np.ndarray], steer_frame: int, fps: float,
            **kwargs) -> Optional[LatencySample]:
    """One sample per steer event. Returns None if the steer never landed.

    A None here is itself a finding: Spec E.9 scores 1 for "steer ignored".
    """
    d = find_divergence(frame_distances(frames), steer_frame, fps, **kwargs)
    if d.lag_ms is None:
        return None
    return LatencySample(lag_ms=d.lag_ms, interval=Interval.GEN_SEND_TO_DIVERGENCE,
                         method=Method.FRAME_DIVERGENCE, confidence=d.confidence,
                         event_index=steer_frame)
