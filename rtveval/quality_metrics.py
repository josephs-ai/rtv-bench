"""Layer-1 computed quality metrics (Spec Part D) - the sweep over Campaign C.

Architecture rule: the MATH is pure and tested against synthetic ground truth
today; the MODELS (LPIPS/ArcFace/CLIP/RAFT) are injected callables that load
lazily in .venv-metrics. This keeps the logic validated before any capture
exists - the placeholder-capture incident taught us what untested-on-real-data
code does - and keeps this module importable in the core venv.

Spec anchors honoured:
  D.1  anchor-relative scoring (Anchor-0 floor, Anchor-R reference), never
       absolute published thresholds
  D.2  flicker on STATIC regions only (motion masked out); identity scored on
       the SLOPE, not the mean ("0.9 falling to 0.6 can still average fine")
  D.3  computed metrics are supporting evidence; humans decide
"""
from typing import Callable, List, NamedTuple, Optional, Sequence, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Pure math (tested in .venv, no torch)
# ---------------------------------------------------------------------------


class Slope(NamedTuple):
    """Least-squares drift of a per-frame quantity. The TREND is the finding."""

    slope_per_min: float
    mean: float
    first: float
    last: float
    n: int


def drift_slope(values: Sequence[float], fps: float,
                sample_every: int = 1) -> Optional[Slope]:
    """Identity/quality drift over a clip. None if too short to trust."""
    vals = list(values)
    if len(vals) < 5:
        return None
    xs = np.arange(len(vals)) * sample_every / fps  # seconds
    if xs[-1] - xs[0] < 5.0:
        return None
    A = np.vstack([xs, np.ones_like(xs)]).T
    slope_s, _ = np.linalg.lstsq(A, np.array(vals), rcond=None)[0]
    return Slope(slope_per_min=float(slope_s * 60.0),
                 mean=float(np.mean(vals)), first=float(vals[0]),
                 last=float(vals[-1]), n=len(vals))


def anchor_score(value: float, anchor0: float, anchorR: float,
                 lower_better: bool) -> int:
    """Spec D.1: 1-5 by POSITION between anchors, not absolute thresholds.

    anchor0 = untransformed source (floor / our own pipeline noise);
    anchorR = real filmed reference. Content-specific by construction.
    """
    if lower_better:
        value, anchor0, anchorR = -value, -anchor0, -anchorR
    # normalise: 0 at anchor0-end, 1 at anchorR
    span = anchorR - anchor0
    if abs(span) < 1e-12:
        return 3  # anchors indistinguishable: mid-scale, flagged upstream
    pos = (value - anchor0) / span
    if pos >= 1.0:
        return 5   # at or better than the real reference (Spec D.1)
    if pos >= 0.75:
        return 4   # within 25% of the gap, good side
    if pos >= 0.4:
        return 3   # mid-range between anchors
    if pos >= 0.0:
        return 2   # closer to the degraded end than to Anchor-R
    return 1       # WORSE than the worst anchor - the Spec reserves 1 for this


def static_region_mask(flow_mag: np.ndarray, threshold: float = 1.0) -> np.ndarray:
    """Spec D.2: flicker is measured on static regions only - genuine motion
    is masked OUT using flow magnitude, else motion reads as flicker."""
    return flow_mag < threshold


def masked_mean(values: np.ndarray, mask: np.ndarray) -> Optional[float]:
    """Mean over the mask; None when the mask covers too little to trust
    (a fast pan leaves almost nothing static - report that, don't invent)."""
    if mask.sum() < 0.05 * mask.size:
        return None
    return float(values[mask].mean())


def blink_stats(eye_openness: Sequence[float], fps: float,
                closed_threshold: float = 0.3) -> dict:
    """Blink rate + interval variance from a per-frame eye-openness series.
    Mechanical regularity (low interval variance) is the uncanny signal."""
    closed = np.asarray(eye_openness) < closed_threshold
    # blink = transition open->closed
    onsets = np.where(closed[1:] & ~closed[:-1])[0] + 1
    duration_min = len(eye_openness) / fps / 60.0
    out = {"blinks_per_min": len(onsets) / duration_min if duration_min > 0 else 0.0,
           "n_blinks": int(len(onsets))}
    if len(onsets) >= 3:
        intervals = np.diff(onsets) / fps
        out["interval_cv"] = float(np.std(intervals) / max(np.mean(intervals), 1e-9))
    else:
        out["interval_cv"] = None
    return out


# ---------------------------------------------------------------------------
# The sweep - model callables injected, loaded lazily in .venv-metrics
# ---------------------------------------------------------------------------


class ClipMetrics(NamedTuple):
    run_id: str
    flicker_lpips: Optional[float]      # masked static regions, mean over clip
    flicker_masked_out: bool            # True when too little static area
    identity: Optional[Slope]           # ArcFace cosine vs reference frame
    clip_adherence: Optional[float]     # CLIP(text, frame) mean
    motion_epe: Optional[float]         # RAFT endpoint error vs source
    blink: Optional[dict]


def sweep_clip(frames: Sequence[np.ndarray], run_id: str, fps: float,
               prompt: Optional[str] = None,
               source_frames: Optional[Sequence[np.ndarray]] = None,
               lpips_fn: Optional[Callable] = None,
               flow_fn: Optional[Callable] = None,
               face_embed_fn: Optional[Callable] = None,
               clip_fn: Optional[Callable] = None,
               eye_openness_fn: Optional[Callable] = None,
               sample_every: int = 30) -> ClipMetrics:
    """One capture through every applicable metric. Any metric whose model
    callable is absent returns None - partial sweeps are legitimate (audio
    metrics don't apply to V2V, RAFT needs source frames, etc.)."""
    flicker = None
    masked_out = False
    if lpips_fn is not None and len(frames) > 2:
        vals = []
        for a, b in zip(frames[:-1], frames[1:]):
            if flow_fn is not None:
                mag = flow_fn(a, b)
                mask = static_region_mask(mag)
                per_px = lpips_fn(a, b, spatial=True)
                m = masked_mean(per_px, mask)
                if m is None:
                    continue
                vals.append(m)
            else:
                vals.append(lpips_fn(a, b, spatial=False))
        if vals:
            flicker = float(np.mean(vals))
        else:
            masked_out = True

    identity = None
    if face_embed_fn is not None and len(frames) > sample_every:
        ref = face_embed_fn(frames[0])
        sims = []
        if ref is not None:
            for i in range(sample_every, len(frames), sample_every):
                emb = face_embed_fn(frames[i])
                if emb is not None:
                    sims.append(float(np.dot(ref, emb)
                                      / (np.linalg.norm(ref) * np.linalg.norm(emb))))
        identity = drift_slope(sims, fps / sample_every) if sims else None

    adherence = None
    if clip_fn is not None and prompt:
        scores = [clip_fn(frames[i], prompt)
                  for i in range(0, len(frames), sample_every)]
        scores = [s for s in scores if s is not None]
        adherence = float(np.mean(scores)) if scores else None

    epe = None
    if flow_fn is not None and source_frames is not None:
        n = min(len(frames), len(source_frames))
        errs = []
        for i in range(1, n, sample_every):
            f_out = flow_fn(frames[i - 1], frames[i])
            f_src = flow_fn(source_frames[i - 1], source_frames[i])
            errs.append(float(np.abs(f_out - f_src).mean()))
        epe = float(np.mean(errs)) if errs else None

    blink = None
    if eye_openness_fn is not None:
        series = [eye_openness_fn(f) for f in frames]
        series = [s for s in series if s is not None]
        if len(series) > fps * 5:
            blink = blink_stats(series, fps)

    return ClipMetrics(run_id=run_id, flicker_lpips=flicker,
                       flicker_masked_out=masked_out, identity=identity,
                       clip_adherence=adherence, motion_epe=epe, blink=blink)
