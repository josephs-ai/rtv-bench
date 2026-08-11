"""Layer-1 metric math against synthetic ground truth (models injected)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from rtveval import quality_metrics as qm


def test_identity_slope_catches_drift_mean_hides():
    """0.9 falling to 0.6 linearly: mean 0.75 looks fine, slope says drifting."""
    sims = np.linspace(0.9, 0.6, 60)  # one per second over a minute
    s = qm.drift_slope(sims, fps=1.0)
    assert abs(s.slope_per_min - (-0.3)) < 0.01, s.slope_per_min
    assert s.mean > 0.74  # the mean that would have hidden it
    print("  slope -0.30/min recovered; mean 0.75 would have hidden the drift")


def test_anchor_score_positions():
    # lower-better metric (e.g. LPIPS flicker): anchor0=0.02 (source noise),
    # anchorR=0.005 (real footage)
    assert qm.anchor_score(0.004, 0.02, 0.005, lower_better=True) == 5
    assert qm.anchor_score(0.007, 0.02, 0.005, lower_better=True) == 4
    assert qm.anchor_score(0.012, 0.02, 0.005, lower_better=True) == 3
    assert qm.anchor_score(0.019, 0.02, 0.005, lower_better=True) == 2
    assert qm.anchor_score(0.05, 0.02, 0.005, lower_better=True) == 1
    # higher-better (CLIP): degenerate anchors -> mid
    assert qm.anchor_score(0.5, 0.3, 0.3, lower_better=False) == 3
    print("  anchor-relative 1-5 mapping correct both directions")


def test_static_mask_excludes_motion():
    flow = np.zeros((10, 10)); flow[:, 5:] = 8.0  # right half moving
    mask = qm.static_region_mask(flow)
    vals = np.ones((10, 10)); vals[:, 5:] = 99.0  # motion would pollute
    m = qm.masked_mean(vals, mask)
    assert abs(m - 1.0) < 1e-9
    tiny = qm.masked_mean(vals, np.zeros((10, 10), bool))
    assert tiny is None  # too little static area: refuse, don't invent
    print("  flicker masked to static regions; too-little-static refuses")


def test_blink_stats_mechanical_vs_natural():
    fps = 30.0
    n = int(fps * 60)
    def series(intervals):
        s = np.ones(n); t = 0
        for iv in intervals:
            t += int(iv * fps)
            if t >= n: break
            s[t:t+3] = 0.1
        return s
    mech = qm.blink_stats(series([3.0]*20), fps)
    nat = qm.blink_stats(series([2.0, 4.5, 2.8, 5.5, 3.2, 1.9, 4.1, 3.7,
                                 2.4, 5.0, 3.3, 2.1, 4.8, 3.9, 2.6]), fps)
    assert mech["interval_cv"] < 0.05 < nat["interval_cv"]
    assert 10 < mech["blinks_per_min"] < 25
    print("  metronomic blinks cv=%.3f vs natural cv=%.3f" %
          (mech["interval_cv"], nat["interval_cv"]))


def test_sweep_with_injected_models():
    rng = np.random.default_rng(3)
    frames = [rng.integers(0, 255, (36, 64, 3), dtype=np.uint8) for _ in range(600)]
    calls = {"lpips": 0}

    def fake_lpips(a, b, spatial=False):
        calls["lpips"] += 1
        return np.full((36, 64), 0.01) if spatial else 0.01

    def fake_flow(a, b):
        return np.zeros((36, 64))  # all static

    embs = iter([np.array([1.0, 0.0])] + [np.array([1.0, 0.02 * k])
                                          for k in range(1, 10)])
    def fake_face(f):
        return next(embs, np.array([1.0, 0.2]))

    m = qm.sweep_clip(frames, "r1", fps=30.0, prompt="a scene",
                      lpips_fn=fake_lpips, flow_fn=fake_flow,
                      face_embed_fn=fake_face,
                      clip_fn=lambda f, p: 0.3, sample_every=10)
    assert m.flicker_lpips is not None and abs(m.flicker_lpips - 0.01) < 1e-9
    assert m.identity is not None
    assert abs(m.clip_adherence - 0.3) < 1e-9  # fp-safe
    assert m.motion_epe is None  # no source frames given: legitimately absent
    print("  sweep runs on injected models; absent models -> None not fake")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        print(t.__name__)
        try:
            t()
        except Exception:
            failed += 1
            import traceback; traceback.print_exc(limit=3)
    print("\n%d/%d passed" % (len(tests) - failed, len(tests)))
    sys.exit(1 if failed else 0)
