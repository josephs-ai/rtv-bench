"""AV lip-sync measurement - applies to ANY product whose input or driver is a
speaking person, not just digital humans.

V2V case (Lucy, Xmax): the source clip has a speaking performer with audio.
The transformed output should keep the mouth articulating in sync with the
source audio. Two failure modes, measured separately:
  - global offset: whole-stream AV desynchronisation (pipeline delay or a
    product that re-times video without re-timing audio);
  - missed closures: restyle destroys articulation - audio has a plosive,
    the rendered mouth never closes. Offset can be zero while speech reads
    as dubbed.

Digital-human case (if access lands): same math, audio is the driving signal.

Scoring is ANCHOR-RELATIVE (Spec D.1): the same measurement runs on Anchor-R
(real filmed reading, ceiling) and Anchor-0 (untransformed source, floor =
our own capture-chain sync error). A product is scored on where it lands
between them, never against an absolute ms threshold. SyncNet LSE-C/LSE-D
remains the published cross-check if syncnet_python is ever installed; the
mouth-landmark path below has no exotic dependencies and runs today.

Pure math here; the mouth/eye landmark extractor is an injected callable
(mediapipe FaceMesh, loaded in .venv-metrics via metrics_models).
"""
from typing import NamedTuple, Optional, Sequence

import numpy as np

from .latency.digital_human import audio_envelope, onsets  # shared instrument


class AVSyncResult(NamedTuple):
    offset_ms: float          # + means mouth lags audio
    offset_frames: float
    confidence: float         # xcorr peak z-score vs off-peak field
    missed_closure_rate: Optional[float]
    n_onsets: int
    n_frames: int


def _zn(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    return (x - x.mean()) / max(x.std(), 1e-12)


def global_av_offset(audio_env: Sequence[float], mouth: Sequence[float],
                     fps: float, max_lag_s: float = 1.0) -> Optional[dict]:
    """Whole-stream offset by normalised cross-correlation of the audio
    envelope against mouth aperture. Searches +-max_lag_s; confidence is the
    peak's z-score against the rest of the lag field (same reporting idea as
    the impulse instrument - never a confident answer from a flat field)."""
    a, m = _zn(audio_env), _zn(mouth)
    n = min(len(a), len(m))
    if n < int(3 * fps):
        return None
    a, m = a[:n], m[:n]
    max_lag = int(max_lag_s * fps)
    lags = range(-max_lag, max_lag + 1)
    scores = []
    for lag in lags:
        if lag >= 0:
            s = float(np.dot(a[:n - lag], m[lag:])) / (n - lag)
        else:
            s = float(np.dot(a[-lag:], m[:n + lag])) / (n + lag)
        scores.append(s)
    scores = np.asarray(scores)
    best = int(np.argmax(scores))
    rest = np.delete(scores, best)
    conf = float((scores[best] - rest.mean()) / max(rest.std(), 1e-12))
    lag_frames = list(lags)[best]
    return {"offset_frames": lag_frames,
            "offset_ms": lag_frames * 1000.0 / fps,
            "confidence": conf}


def missed_closure_rate(audio_env: Sequence[float], mouth: Sequence[float],
                        fps: float, offset_frames: int = 0,
                        window_s: float = 0.25,
                        excursion_k: float = 0.8) -> Optional[dict]:
    """Fraction of audio onsets with NO corresponding mouth excursion after
    the global offset is removed. This is the 'reads as dubbed' signal that a
    zero offset cannot catch. An excursion counts when the local mouth range
    within the window exceeds excursion_k * the clip's overall std."""
    a = np.asarray(audio_env, dtype=np.float64)
    m = np.asarray(mouth, dtype=np.float64)
    ons = onsets(a)
    if len(ons) < 3:
        return None
    w = max(2, int(window_s * fps))
    sd = max(float(m.std()), 1e-12)
    missed = 0
    used = 0
    for o in ons:
        c = o + offset_frames
        lo, hi = max(0, c - w), min(len(m), c + w + 1)
        if hi - lo < 3:
            continue
        used += 1
        if float(m[lo:hi].max() - m[lo:hi].min()) < excursion_k * sd:
            missed += 1
    if used == 0:
        return None
    return {"missed": missed, "n_onsets": used, "rate": missed / used}


def measure(frames_mouth: Sequence[float], audio_samples: np.ndarray,
            sample_rate: int, fps: float) -> Optional[AVSyncResult]:
    """Full lip-sync measurement from a mouth-openness series + raw audio."""
    env = audio_envelope(audio_samples, sample_rate, fps)
    off = global_av_offset(env, frames_mouth, fps)
    if off is None:
        return None
    mc = missed_closure_rate(env, frames_mouth, fps,
                             offset_frames=int(off["offset_frames"]))
    return AVSyncResult(offset_ms=off["offset_ms"],
                        offset_frames=off["offset_frames"],
                        confidence=off["confidence"],
                        missed_closure_rate=mc["rate"] if mc else None,
                        n_onsets=mc["n_onsets"] if mc else 0,
                        n_frames=len(frames_mouth))


def versus_anchors(product: AVSyncResult, anchor0: AVSyncResult,
                   anchorR: AVSyncResult) -> dict:
    """Anchor-relative framing: the product's ADDED offset and ADDED missed
    closures beyond what our own capture chain (Anchor-0) exhibits, with
    Anchor-R as the real-footage ceiling. Raw values stay reported."""
    def rate(r):
        return r.missed_closure_rate if r.missed_closure_rate is not None else 0.0
    return {
        "added_offset_ms": product.offset_ms - anchor0.offset_ms,
        "added_missed_rate": rate(product) - rate(anchor0),
        "anchorR_offset_ms": anchorR.offset_ms,
        "anchorR_missed_rate": rate(anchorR),
        "note": ("added_* are relative to Anchor-0 (untransformed source "
                 "through the same capture chain); anchorR_* is the real-"
                 "footage reference the anchored 1-5 scale is pinned to"),
    }
