"""Impulse cross-correlation - the primary V2V latency instrument.

A burned-in marker is destroyed by restyling: "transform into an oil painting"
will not leave a readable block strip. So the source reel carries hard luminance
flashes at known frame indices, and the lag is recovered by cross-correlating
global luminance between input and output.

This survives arbitrary restyling because a transient is still a transient no
matter what style is applied to it. A style may change the flash's amplitude,
colour, or shape - it does not move it in time.

Two stages:
  1. Global normalised cross-correlation for a coarse, robust lag estimate.
  2. Per-event refinement around that coarse lag, which yields one sample per
     flash - and therefore the >=30 samples, and the jitter figure, that
     Campaign A needs. A single global xcorr gives one number and no sigma.
"""
from typing import List, Optional, Sequence

import numpy as np

from .base import Interval, LatencySample, Method


def luminance_series(frames: Sequence[np.ndarray]) -> np.ndarray:
    """Mean luminance per frame. Accepts grayscale or HxWx3 RGB."""
    out = np.empty(len(frames), dtype=np.float64)
    for i, f in enumerate(frames):
        if f.ndim == 3:
            # Rec.709 luma; the exact coefficients matter less than consistency
            # between the input and output series.
            out[i] = float(np.dot(f.reshape(-1, f.shape[-1])[:, :3].mean(axis=0),
                                  (0.2126, 0.7152, 0.0722)))
        else:
            out[i] = float(f.mean())
    return out


def _emphasise_transients(x: np.ndarray) -> np.ndarray:
    """First difference, zero-mean, unit-variance.

    Differencing is what makes this style-robust: it discards the DC level (an
    oil-painting filter shifts overall brightness) and keeps the edges (it does
    not remove the flash).
    """
    d = np.diff(x.astype(np.float64), prepend=x[0])
    d -= d.mean()
    s = d.std()
    return d / s if s > 1e-9 else d


def estimate_lag_global(inp: np.ndarray, out: np.ndarray, fps: float,
                        max_lag_ms: float = 2000.0) -> tuple:
    """Coarse lag via normalised cross-correlation.

    Returns (lag_ms, confidence) where confidence is peak prominence: the ratio
    of the best peak to the next-best peak outside its immediate neighbourhood.
    A confidence near 1.0 means the correlogram has no clear winner and the
    measurement should not be trusted.
    """
    a, b = _emphasise_transients(inp), _emphasise_transients(out)
    max_lag = int(round(max_lag_ms * fps / 1000.0))
    max_lag = max(1, min(max_lag, len(a) - 1, len(b) - 1))

    lags = np.arange(0, max_lag + 1)
    scores = np.empty(len(lags), dtype=np.float64)
    for i, lag in enumerate(lags):
        n = min(len(a) - lag, len(b) - lag, len(a), len(b) - lag)
        if n <= 8:
            scores[i] = -np.inf
            continue
        seg_a, seg_b = a[:n], b[lag:lag + n]
        denom = np.linalg.norm(seg_a) * np.linalg.norm(seg_b)
        scores[i] = float(np.dot(seg_a, seg_b) / denom) if denom > 1e-12 else -np.inf

    best = int(np.argmax(scores))
    # Parabolic interpolation for sub-frame resolution. At 60 fps one frame is
    # 16.7 ms, which is coarse next to a 150 ms band boundary.
    offset = 0.0
    if 0 < best < len(scores) - 1:
        y0, y1, y2 = scores[best - 1], scores[best], scores[best + 1]
        denom = y0 - 2 * y1 + y2
        if abs(denom) > 1e-12:
            offset = float(np.clip(0.5 * (y0 - y2) / denom, -1.0, 1.0))

    # Prominence: exclude +-3 frames around the peak before taking the runner-up.
    mask = np.ones(len(scores), dtype=bool)
    mask[max(0, best - 3):best + 4] = False
    runner_up = float(np.max(scores[mask])) if mask.any() else 0.0
    peak = float(scores[best])
    confidence = 0.0 if peak <= 0 else float(np.clip(1.0 - max(runner_up, 0.0) / peak, 0.0, 1.0))

    return ((best + offset) * 1000.0 / fps, confidence)


def detect_impulses(lum: np.ndarray, fps: float, min_separation_ms: float = 400.0,
                    z_threshold: float = 4.0) -> np.ndarray:
    """Frame indices of luminance transients, strongest first, then sorted.

    Used to locate flashes in the *output* stream. Flash positions in the input
    are known by construction (see reel/overlay.py) and should be passed in
    rather than detected.
    """
    d = _emphasise_transients(lum)
    min_sep = max(1, int(round(min_separation_ms * fps / 1000.0)))

    candidates = np.where(d > z_threshold)[0]
    picked: List[int] = []
    for idx in candidates[np.argsort(-d[candidates])]:
        if all(abs(int(idx) - p) >= min_sep for p in picked):
            picked.append(int(idx))
    return np.array(sorted(picked), dtype=int)


def per_event_lags(input_flash_frames: Sequence[int], out_lum: np.ndarray, fps: float,
                   coarse_lag_ms: float, search_window_ms: float = 250.0,
                   z_threshold: float = 3.0) -> List[LatencySample]:
    """One lag sample per flash, searched in a window around the coarse estimate.

    This is what produces the distribution. Flashes with no detectable output
    transient in their window are skipped and reported as dropped, not silently
    filled - a product that swallows a flash entirely is telling you something.
    """
    d = _emphasise_transients(out_lum)
    coarse_frames = coarse_lag_ms * fps / 1000.0
    half = max(1, int(round(search_window_ms * fps / 1000.0)))

    samples: List[LatencySample] = []
    for k, f_in in enumerate(input_flash_frames):
        centre = int(round(f_in + coarse_frames))
        lo, hi = max(0, centre - half), min(len(d), centre + half + 1)
        if hi - lo < 3:
            continue

        window = d[lo:hi]
        rel = int(np.argmax(window))
        if window[rel] < z_threshold:
            continue

        # Sub-frame refinement on the response peak.
        offset = 0.0
        if 0 < rel < len(window) - 1:
            y0, y1, y2 = window[rel - 1], window[rel], window[rel + 1]
            denom = y0 - 2 * y1 + y2
            if abs(denom) > 1e-12:
                offset = float(np.clip(0.5 * (y0 - y2) / denom, -1.0, 1.0))

        f_out = lo + rel + offset
        lag_ms = (f_out - f_in) * 1000.0 / fps
        if lag_ms < 0:
            continue  # output cannot precede input; a negative lag is a detection error

        # Confidence: how far the peak stands above the rest of its window.
        others = np.delete(window, slice(max(0, rel - 2), rel + 3))
        bg = float(np.max(others)) if others.size else 0.0
        conf = float(np.clip(1.0 - max(bg, 0.0) / float(window[rel]), 0.0, 1.0))

        samples.append(LatencySample(lag_ms=lag_ms, interval=Interval.V2V_FRAME_TO_FRAME,
                                     method=Method.IMPULSE_XCORR, confidence=conf,
                                     event_index=k))
    return samples


def measure(input_lum: np.ndarray, output_lum: np.ndarray, fps: float,
            input_flash_frames: Optional[Sequence[int]] = None,
            max_lag_ms: float = 2000.0) -> List[LatencySample]:
    """Full V2V impulse measurement: coarse align, then per-flash samples."""
    coarse_ms, coarse_conf = estimate_lag_global(input_lum, output_lum, fps,
                                                 max_lag_ms=max_lag_ms)
    if input_flash_frames is None:
        input_flash_frames = detect_impulses(input_lum, fps)

    samples = per_event_lags(input_flash_frames, output_lum, fps, coarse_ms)
    if not samples:
        # Fall back to the global estimate as a single low-trust sample rather
        # than returning nothing.
        return [LatencySample(lag_ms=coarse_ms, interval=Interval.V2V_FRAME_TO_FRAME,
                              method=Method.IMPULSE_XCORR, confidence=coarse_conf * 0.5)]
    return samples


def motion_xcorr(input_frames_lum, output_frames_lum, fps: float,
                 max_lag_ms: float = 2000.0):
    """Global lag from MOTION-energy cross-correlation between panes.

    Why it exists (found live, 2026-08-11): a learned cinematic grade applies
    LOCAL tone mapping - the global luminance impulse that survives synthetic
    gamma restyles is destroyed, and per-flash matching locks onto noise at
    physically impossible lags. Motion is what a V2V product must preserve to
    be a V2V product, so the frame-difference energy signal survives styles
    that kill luminance transients.

    Returns (lag_ms, z_confidence) for the whole clip - ONE sample per run;
    N runs give N samples. Callers must treat z < 4 as unusable.
    """
    import numpy as np

    def motion(frames):
        return np.array([np.abs(np.asarray(frames[i], dtype=np.float64)
                                - np.asarray(frames[i - 1], dtype=np.float64)).mean()
                         for i in range(1, len(frames))])

    def zn(x):
        return (x - x.mean()) / max(x.std(), 1e-9)

    a, b = zn(motion(input_frames_lum)), zn(motion(output_frames_lum))
    max_lag = max(2, int(max_lag_ms * fps / 1000.0))
    scores = []
    for lag in range(0, min(max_lag, len(a) - 8)):
        n = len(a) - lag
        scores.append(float(np.dot(a[:n], b[lag:lag + n]) / n))
    scores = np.asarray(scores)
    k = int(np.argmax(scores))
    rest = np.delete(scores, range(max(0, k - 3), min(len(scores), k + 4)))
    z = float((scores[k] - rest.mean()) / max(rest.std(), 1e-9))
    return k * 1000.0 / fps, z
