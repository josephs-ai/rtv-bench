"""Digital-human latency: audio onset -> first lip movement.

Neither a frame correspondence nor a send timestamp. The measurable interval is
between the audio driving the avatar and the face responding to it.

Uses the same script that Spec S1 already specifies - phoneme-dense and heavy on
plosives. Plosives are the right stimulus for both purposes: /b/, /p/, /m/
require a full lip closure and release, which is a sharp transient in the audio
envelope *and* the largest, most unambiguous excursion in mouth aperture.

Note this is only reachable if Vidu S1 unblocks. Written now so it is not a
day-3 dependency hunt.
"""
from typing import List, NamedTuple, Optional, Sequence, Tuple

import numpy as np

from .base import Interval, LatencySample, Method


class ROI(NamedTuple):
    """Mouth region in pixels. From landmarks where available, else fixed."""

    x0: int
    y0: int
    w: int
    h: int


def audio_envelope(samples: np.ndarray, sample_rate: int, fps: float) -> np.ndarray:
    """RMS energy per video frame, so audio and video share a time base."""
    if samples.ndim > 1:
        samples = samples.mean(axis=1)
    per_frame = max(1, int(round(sample_rate / fps)))
    n = len(samples) // per_frame
    if n == 0:
        return np.zeros(0)
    trimmed = samples[:n * per_frame].reshape(n, per_frame).astype(np.float64)
    return np.sqrt((trimmed ** 2).mean(axis=1))


def onsets(signal: np.ndarray, k_sigma: float = 3.0, min_separation: int = 6,
           quiet_quantile: float = 0.25) -> np.ndarray:
    """Indices where a signal jumps sharply.

    The threshold is set from the quiet portion of the signal rather than the
    whole of it - otherwise loud passages inflate sigma and swallow the onsets
    we are trying to find.
    """
    if len(signal) < 3:
        return np.array([], dtype=int)

    d = np.diff(signal, prepend=signal[0])
    quiet = d[d <= np.quantile(d, quiet_quantile)] if len(d) > 4 else d
    mu, sd = float(quiet.mean()), max(float(quiet.std()), 1e-9)
    threshold = mu + k_sigma * sd

    picked: List[int] = []
    for i in np.where(d > threshold)[0]:
        if not picked or int(i) - picked[-1] >= min_separation:
            picked.append(int(i))
    return np.array(picked, dtype=int)


def mouth_aperture(frames: Sequence[np.ndarray], roi: ROI) -> np.ndarray:
    """Per-frame motion energy in the mouth region.

    A proxy for aperture, not a measurement of it: frame-to-frame absolute
    difference inside the ROI. It responds to opening and closing alike, which
    is all that is needed to timestamp the *first* movement. If landmarks are
    available, replace with true vertical lip distance - strictly better, but it
    adds a landmark model to the critical path.
    """
    def crop(f: np.ndarray) -> np.ndarray:
        patch = f[roi.y0:roi.y0 + roi.h, roi.x0:roi.x0 + roi.w]
        if patch.ndim == 3:
            return patch[..., :3].astype(np.float64) @ np.array((0.2126, 0.7152, 0.0722))
        return patch.astype(np.float64)

    out = np.zeros(len(frames), dtype=np.float64)
    if len(frames) < 2:
        return out
    prev = crop(frames[0])
    for i in range(1, len(frames)):
        cur = crop(frames[i])
        out[i] = float(np.abs(cur - prev).mean())
        prev = cur
    return out


def measure(frames: Sequence[np.ndarray], audio: np.ndarray, sample_rate: int,
            fps: float, roi: ROI, max_lag_ms: float = 1500.0,
            k_sigma: float = 3.0) -> List[LatencySample]:
    """Pair each audio onset with the next mouth-movement onset.

    Unpaired audio onsets are dropped rather than assigned a default lag - a
    missed plosive closure is a lip-sync quality defect (Spec E.10), and it
    should be scored there, not smuggled into the latency figure.
    """
    env = audio_envelope(audio, sample_rate, fps)
    a_onsets = onsets(env, k_sigma=k_sigma)
    aperture = mouth_aperture(frames, roi)
    v_onsets = onsets(aperture, k_sigma=k_sigma)

    if len(a_onsets) == 0 or len(v_onsets) == 0:
        return []

    max_lag_frames = max_lag_ms * fps / 1000.0
    samples: List[LatencySample] = []
    for k, a in enumerate(a_onsets):
        later = v_onsets[(v_onsets >= a) & (v_onsets - a <= max_lag_frames)]
        if len(later) == 0:
            continue
        v = int(later[0])
        # Confidence falls off as the pairing gets ambiguous - i.e. as another
        # audio onset closes in on this one.
        nxt = a_onsets[a_onsets > a]
        gap = float(nxt[0] - a) if len(nxt) else float(max_lag_frames)
        conf = float(np.clip(1.0 - (v - a) / max(gap, 1e-6), 0.0, 1.0))
        samples.append(LatencySample(lag_ms=(v - a) * 1000.0 / fps,
                                     interval=Interval.DH_AUDIO_TO_LIP,
                                     method=Method.AUDIO_ONSET,
                                     confidence=conf, event_index=k))
    return samples
