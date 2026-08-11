"""Model callables for the Layer-1 sweep. .venv-metrics ONLY.

Each loader returns a callable matching the signature `quality_metrics.sweep_clip`
expects, or None when the backend is unavailable - a partial sweep is
legitimate (the sweep records which metrics ran; absent models mean None
fields, never fake numbers).

Import cost is paid at load time, per process, once; frames are numpy RGB24.
"""
from typing import Callable, Optional

import numpy as np


def _device():
    import torch
    return "mps" if torch.backends.mps.is_available() else "cpu"


def load_lpips() -> Optional[Callable]:
    """lpips_fn(a, b, spatial) -> per-pixel map (spatial=True) or scalar."""
    try:
        import lpips
        import torch
    except ImportError:
        return None
    dev = _device()
    net = lpips.LPIPS(net="alex", spatial=True, verbose=False).to(dev).eval()

    def to_t(f):
        x = torch.from_numpy(f.astype(np.float32) / 127.5 - 1.0)
        return x.permute(2, 0, 1).unsqueeze(0).to(dev)

    def fn(a, b, spatial=False):
        import torch
        with torch.no_grad():
            m = net(to_t(a), to_t(b)).squeeze().cpu().numpy()
        return m if spatial else float(np.mean(m))

    return fn


def load_flow() -> Optional[Callable]:
    """flow_fn(a, b) -> flow magnitude (H x W), RAFT-small."""
    try:
        import torch
        from torchvision.models.optical_flow import (Raft_Small_Weights,
                                                     raft_small)
    except ImportError:
        return None
    dev = _device()
    model = raft_small(weights=Raft_Small_Weights.DEFAULT).to(dev).eval()

    def prep(f):
        import torch
        h, w = f.shape[:2]
        h8, w8 = (h // 8) * 8, (w // 8) * 8
        x = torch.from_numpy(f[:h8, :w8].astype(np.float32) / 127.5 - 1.0)
        return x.permute(2, 0, 1).unsqueeze(0).to(dev)

    def fn(a, b):
        import torch
        with torch.no_grad():
            flow = model(prep(a), prep(b))[-1].squeeze(0).cpu().numpy()
        return np.sqrt(flow[0] ** 2 + flow[1] ** 2)

    return fn


def load_face_embedder() -> Optional[Callable]:
    """face_embed_fn(frame) -> embedding or None (no face). insightface."""
    try:
        from insightface.app import FaceAnalysis
        app = FaceAnalysis(providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=-1, det_size=(640, 640))
    except Exception:
        return None

    def fn(frame):
        faces = app.get(frame[..., ::-1])  # BGR in
        if not faces:
            return None
        best = max(faces, key=lambda f: f.det_score)
        return np.asarray(best.normed_embedding, dtype=np.float64)

    return fn


def load_clip_scorer() -> Optional[Callable]:
    """clip_fn(frame, prompt) -> cosine in [-1, 1]."""
    try:
        import open_clip
        import torch
    except ImportError:
        return None
    dev = _device()
    model, _, preprocess = open_clip.create_model_and_transforms(
        "ViT-B-32", pretrained="laion2b_s34b_b79k")
    model = model.to(dev).eval()
    tokenizer = open_clip.get_tokenizer("ViT-B-32")
    cache = {}

    def fn(frame, prompt):
        import torch
        from PIL import Image
        with torch.no_grad():
            if prompt not in cache:
                t = model.encode_text(tokenizer([prompt]).to(dev))
                cache[prompt] = t / t.norm(dim=-1, keepdim=True)
            img = preprocess(Image.fromarray(frame)).unsqueeze(0).to(dev)
            v = model.encode_image(img)
            v = v / v.norm(dim=-1, keepdim=True)
            return float((v @ cache[prompt].T).item())

    return fn


def load_face_mesh():
    """(mouth_openness_fn, eye_openness_fn) via mediapipe FaceMesh, or
    (None, None). Both are normalised by inter-ocular distance so subject
    scale/framing cancels - the SERIES shape is what av_sync consumes."""
    try:
        import mediapipe as mp
    except ImportError:
        return None, None
    mesh = mp.solutions.face_mesh.FaceMesh(
        static_image_mode=True, max_num_faces=1, refine_landmarks=False)

    def landmarks(frame):
        res = mesh.process(frame)
        if not res.multi_face_landmarks:
            return None
        return res.multi_face_landmarks[0].landmark

    def _dist(lm, i, j):
        a, b = lm[i], lm[j]
        return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5

    def mouth_openness(frame) -> Optional[float]:
        lm = landmarks(frame)
        if lm is None:
            return None
        scale = max(_dist(lm, 33, 263), 1e-9)      # outer eye corners
        return _dist(lm, 13, 14) / scale           # inner-lip gap

    def eye_openness(frame) -> Optional[float]:
        lm = landmarks(frame)
        if lm is None:
            return None
        scale = max(_dist(lm, 33, 263), 1e-9)
        left = _dist(lm, 159, 145)                 # upper/lower lid
        right = _dist(lm, 386, 374)
        return (left + right) / (2 * scale)

    return mouth_openness, eye_openness


def load_all() -> dict:
    """Everything available, keyed by sweep_clip kwarg name. DINO comes from
    vbench_metrics (subject consistency uses its own loader)."""
    _, eye_fn = load_face_mesh()
    out = {"lpips_fn": load_lpips(), "flow_fn": load_flow(),
           "face_embed_fn": load_face_embedder(), "clip_fn": load_clip_scorer(),
           "eye_openness_fn": eye_fn}
    return {k: v for k, v in out.items() if v is not None}
