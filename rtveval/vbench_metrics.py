"""VBench-protocol metrics, ported decord-free for this rig.

Why a port and not `pip install vbench`: the released package hard-depends on
`decord`, which ships no arm64/macOS wheels. The metric DEFINITIONS are what
carry the citation value, and they are small; video loading is ours (PyAV).

Definitions follow VBench (Huang et al., CVPR 2024):
  - temporal_flickering: mean absolute frame difference over consecutive
    pairs, mapped to [0,1] as 1 - MAE/255 (higher = less flicker). VBench
    applies this to static scenes; for our captures the static-region mask
    from quality_metrics is the analogous guard - pass masked frames or
    interpret alongside flow.
  - subject_consistency: DINO ViT features; per-frame score is the mean of
    cosine(first, t) and cosine(t-1, t), averaged over the clip.
  - background_consistency: same formula on CLIP image features.

The embedding models are injected callables (loaded in .venv-metrics); the
formulas below are pure and tested in the core venv.
"""
from typing import Callable, Optional, Sequence

import numpy as np


def temporal_flickering(frames: Sequence[np.ndarray]) -> Optional[float]:
    """1 - mean(|frame_t - frame_{t+1}|)/255 over consecutive pairs."""
    if len(frames) < 2:
        return None
    maes = [float(np.abs(a.astype(np.float64) - b.astype(np.float64)).mean())
            for a, b in zip(frames[:-1], frames[1:])]
    return 1.0 - float(np.mean(maes)) / 255.0


def _cos(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) /
                 max(np.linalg.norm(a) * np.linalg.norm(b), 1e-12))


def feature_consistency(frames: Sequence[np.ndarray],
                        embed_fn: Callable[[np.ndarray], Optional[np.ndarray]],
                        sample_every: int = 1) -> Optional[float]:
    """VBench subject/background consistency: mean over t of
    (cos(f_1, f_t) + cos(f_{t-1}, f_t)) / 2. The embed_fn decides which
    metric this is (DINO -> subject, CLIP -> background)."""
    embs = []
    for i in range(0, len(frames), sample_every):
        e = embed_fn(frames[i])
        if e is not None:
            embs.append(np.asarray(e, dtype=np.float64))
    if len(embs) < 2:
        return None
    first = embs[0]
    scores = [( _cos(first, embs[t]) + _cos(embs[t - 1], embs[t]) ) / 2.0
              for t in range(1, len(embs))]
    return float(np.mean(scores))


def load_dino_embedder():
    """DINO ViT-S/16 image embedder (subject consistency). .venv-metrics only;
    downloads the torch.hub checkpoint on first use."""
    import torch
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model = torch.hub.load("facebookresearch/dino:main", "dino_vits16")
    model.eval().to(device)

    def embed(frame: np.ndarray) -> Optional[np.ndarray]:
        from PIL import Image
        import torchvision.transforms as T
        tf = T.Compose([T.Resize(224), T.CenterCrop(224), T.ToTensor(),
                        T.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225))])
        x = tf(Image.fromarray(frame)).unsqueeze(0).to(device)
        with torch.no_grad():
            return model(x).squeeze(0).cpu().numpy()

    return embed
