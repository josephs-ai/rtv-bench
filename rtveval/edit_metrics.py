"""Campaign D - purpose-built live-edit metrics.

Every metric is anchored to the edit-send instant and to the edit type's
declaration of TARGET vs PROTECTED regions. Nothing here is a renamed
generation metric: the concepts (intent, commit, residue, collateral,
stability) only exist because an instruction landed mid-stream.

Regions (v1, face-anchored geometry - segmentation-free so both products'
captures are treated identically):
    face       detected face box
    head       face box grown 1.6x (hair)
    torso      below face box, 2.6x face width, to 2.2x face heights down
    person     head + torso union
    background frame minus person column

REGION_MAP declares, per edit type, which region must change (target) and
which must not (protected).
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

REGION_MAP = {
    # edit_id prefix -> (target, protected...)
    "garment":    ("torso", ("face", "background")),
    "hair":       ("head", ("face", "background")),
    "accessory":  ("face", ("torso", "background")),   # sunglasses/cap live on face/head
    "background": ("background", ("face", "torso")),
    "style":      ("frame", ()),                        # everything may change
    "character":  ("person", ("background",)),
}


def region_for(edit_id: str) -> Tuple[str, Tuple[str, ...]]:
    for k, v in REGION_MAP.items():
        if edit_id.startswith(k):
            return v
    return ("frame", ())


def face_box(app_get, frame) -> Optional[Tuple[int, int, int, int]]:
    """(x0,y0,x1,y1) of the best face, or None."""
    faces = app_get(frame[..., ::-1])
    if not faces:
        return None
    b = max(faces, key=lambda f: f.det_score).bbox.astype(int)
    h, w = frame.shape[:2]
    return (max(0, b[0]), max(0, b[1]), min(w, b[2]), min(h, b[3]))


def regions_from_face(frame, fb) -> Dict[str, np.ndarray]:
    """Crop dict; background is the frame with the person column zeroed."""
    h, w = frame.shape[:2]
    out = {"frame": frame}
    if fb is None:
        # no face: fall back to center-column person assumption
        cx0, cx1 = int(w * 0.25), int(w * 0.75)
        out["face"] = frame[0:1, 0:1]
        out["head"] = frame[: h // 3, cx0:cx1]
        out["torso"] = frame[h // 3:, cx0:cx1]
        person_x = (cx0, cx1)
        person_y0 = 0
    else:
        x0, y0, x1, y1 = fb
        fw, fh = x1 - x0, y1 - y0
        out["face"] = frame[y0:y1, x0:x1]
        hx0 = max(0, int(x0 - 0.3 * fw))
        hx1 = min(w, int(x1 + 0.3 * fw))
        hy0 = max(0, int(y0 - 0.6 * fh))
        out["head"] = frame[hy0:min(h, y1 + int(0.1 * fh)), hx0:hx1]
        tx0 = max(0, int(x0 - 0.8 * fw))
        tx1 = min(w, int(x1 + 0.8 * fw))
        out["torso"] = frame[y1:min(h, y1 + int(2.2 * fh)), tx0:tx1]
        person_x = (min(hx0, tx0), max(hx1, tx1))
        person_y0 = hy0
    person = frame[person_y0:, person_x[0]:person_x[1]]
    out["person"] = person
    bg = frame.copy()
    bg[person_y0:, person_x[0]:person_x[1]] = 0
    out["background"] = bg
    return out


def _norm(e):
    n = np.linalg.norm(e)
    return e / n if n > 1e-12 else e


def region_signal(frames_idx: Sequence[int], get_frame: Callable,
                  app_get, embed: Callable, region: str) -> Dict[int, np.ndarray]:
    """index -> normalized embedding of the region crop."""
    out = {}
    for i in frames_idx:
        fr = get_frame(i)
        if fr is None:
            continue
        fb = face_box(app_get, fr)
        crop = regions_from_face(fr, fb).get(region)
        if crop is None or crop.size < 3000:
            continue
        e = embed(crop)
        if e is not None:
            out[i] = _norm(np.asarray(e, dtype=np.float64))
    return out


def centroid(embs: List[np.ndarray]) -> Optional[np.ndarray]:
    if not embs:
        return None
    return _norm(np.mean(np.stack(embs), axis=0))


def commit_latency_s(sig: Dict[int, np.ndarray], edit_frame: int, fps: float,
                     pre_centroid: np.ndarray,
                     sustain_n: int = 3, drop: float = 0.10) -> Optional[float]:
    """First index after the edit where similarity-to-pre drops by `drop`
    below the pre-window's own similarity floor, sustained for sustain_n
    consecutive samples. None = never committed."""
    pre_sims = [float(np.dot(pre_centroid, e))
                for i, e in sorted(sig.items()) if i < edit_frame]
    if not pre_sims:
        return None
    floor = np.percentile(pre_sims, 10)
    run = 0
    for i, e in sorted(sig.items()):
        if i < edit_frame:
            continue
        if float(np.dot(pre_centroid, e)) < floor - drop:
            run += 1
            if run >= sustain_n:
                return round((i - edit_frame) / fps, 2)
        else:
            run = 0
    return None


def collateral_index(target_delta: float, protected_deltas: List[float]) -> Optional[float]:
    """protected change / target change; ~0 = surgical, >=1 = the edit hit
    everything as hard as its target."""
    if target_delta <= 1e-6:
        return None
    if not protected_deltas:
        return 0.0
    return round(float(np.mean(protected_deltas)) / target_delta, 3)


def residue_index(sig: Dict[int, np.ndarray], edit_frame: int, fps: float,
                  pre_centroid: np.ndarray, commit_s: Optional[float]) -> Optional[float]:
    """Similarity of the SETTLED post-edit target region back to its pre-edit
    appearance, rescaled so 1.0 = unchanged (edit failed / full residue) and
    0.0 = fully replaced."""
    if pre_centroid is None:
        return None
    settle = edit_frame + int(((commit_s or 2.0) + 3.0) * fps)
    post = [e for i, e in sorted(sig.items()) if i >= settle]
    if len(post) < 3:
        return None
    sim = float(np.dot(pre_centroid, centroid(post)))
    return round(max(0.0, min(1.0, sim)), 3)


def transition_cost(get_frame: Callable, edit_frame: int, fps: float,
                    n_frames: int, window_s: float = 5.0) -> Dict:
    """Frozen + glitch frames inside the commit window, in EXCESS of the
    session's own pre-edit baseline rate. Glitch = blockiness spike
    (patch-variance kurtosis) or extreme frame-diff."""
    def rate(lo, hi):
        frozen = glitch = total = 0
        prev = None
        for i in range(lo, min(hi, n_frames), 2):
            fr = get_frame(i)
            if fr is None:
                continue
            g = fr.mean(axis=2).astype(np.float64)
            if prev is not None:
                d = float(np.abs(g - prev).mean())
                if d < 0.25:
                    frozen += 1
                ph, pw = g.shape[0] // 8, g.shape[1] // 8
                pv = g[: ph * 8, : pw * 8].reshape(ph, 8, pw, 8).var(axis=(1, 3))
                if d > 40.0 or (pv.max() > 50 * max(pv.mean(), 1e-6)):
                    glitch += 1
                total += 1
            prev = g
        return frozen, glitch, max(total, 1)

    w = int(window_s * fps)
    pf, pg, pt = rate(max(0, edit_frame - w), edit_frame)
    tf, tg, tt = rate(edit_frame, edit_frame + w)
    return {
        "baseline_frozen_rate": round(pf / pt, 3),
        "transition_frozen_excess": round(max(0.0, tf / tt - pf / pt), 3),
        "baseline_glitch_rate": round(pg / pt, 3),
        "transition_glitch_excess": round(max(0.0, tg / tt - pg / pt), 3),
    }


def commit_stability(sig: Dict[int, np.ndarray], edit_frame: int, fps: float,
                     pre_centroid, commit_s: Optional[float]) -> Dict:
    """Post-commit frames classified nearer old-state vs new-state; the new
    state anchor is the first settled second after commit. hold = fraction
    staying new; flips = state oscillations (blend-back detector)."""
    if commit_s is None or pre_centroid is None:
        return {"hold": None, "flips": None}
    c0 = edit_frame + int(commit_s * fps)
    new_anchor = centroid([e for i, e in sorted(sig.items())
                           if c0 <= i < c0 + int(1.5 * fps)])
    if new_anchor is None:
        return {"hold": None, "flips": None}
    states = []
    for i, e in sorted(sig.items()):
        if i < c0 + int(1.5 * fps):
            continue
        states.append(float(np.dot(new_anchor, e)) >= float(np.dot(pre_centroid, e)))
    if not states:
        return {"hold": None, "flips": None}
    flips = sum(1 for a, b in zip(states, states[1:]) if a != b)
    return {"hold": round(sum(states) / len(states), 3), "flips": flips}


def motion_continuity_break(flow_fn, get_frame, edit_frame: int, fps: float,
                            commit_s: Optional[float]) -> Optional[float]:
    """Flow-magnitude discontinuity across the commit boundary, as a ratio
    to the pre-edit typical inter-frame flow. ~1 = seamless motion."""
    if flow_fn is None or commit_s is None:
        return None
    c = edit_frame + int(commit_s * fps)
    mags = []
    for i in range(max(0, edit_frame - int(3 * fps)), edit_frame, 4):
        a, b = get_frame(i), get_frame(i + 2)
        if a is not None and b is not None:
            mags.append(float(flow_fn(a, b).mean()))
    if not mags:
        return None
    base = max(float(np.median(mags)), 1e-3)
    a, b = get_frame(max(0, c - 1)), get_frame(min(c + 2, c + 2))
    if a is None or b is None:
        return None
    return round(float(flow_fn(a, b).mean()) / base, 2)


def identity_outcomes(app_get, face_embed, get_frame, edit_frame: int,
                      fps: float, n_frames: int, is_character: bool,
                      ref_path: Optional[str]) -> Dict:
    """Direction-aware identity: same-person for non-character edits;
    person-switch (+ ref fidelity) for character edits."""
    def face_of(lo, hi):
        embs = []
        for i in range(lo, min(hi, n_frames), max(2, int(fps / 3))):
            fr = get_frame(i)
            if fr is None:
                continue
            e = face_embed(fr)
            if e is not None:
                embs.append(_norm(np.asarray(e)))
        return centroid(embs)

    pre = face_of(max(0, edit_frame - int(6 * fps)), edit_frame)
    post = face_of(edit_frame + int(4 * fps), n_frames)
    out = {"pre_post_face_sim": None, "ref_fidelity": None}
    if pre is not None and post is not None:
        out["pre_post_face_sim"] = round(float(np.dot(pre, post)), 3)
    if is_character and ref_path:
        import av
        try:
            with av.open(ref_path) as c:
                ref_fr = next(c.decode(c.streams.video[0])).to_ndarray(format="rgb24")
        except Exception:
            import PIL.Image
            ref_fr = np.asarray(__import__("PIL.Image", fromlist=["Image"])
                                .open(ref_path).convert("RGB"))
        re_ = face_embed(ref_fr)
        if re_ is not None and post is not None:
            out["ref_fidelity"] = round(float(np.dot(_norm(np.asarray(re_)), post)), 3)
    return out
