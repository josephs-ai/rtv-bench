"""Cluster bootstrap and Lens M decomposition honesty."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random

from rtveval import stats


def _clusters(spread):
    """Synthetic runs mimicking the observed structure: tight within-run,
    wide across runs (session-to-session)."""
    rng = random.Random(3)
    out = []
    for _ in range(30):
        centre = 1500 + rng.uniform(-spread, spread)
        out.append([centre + rng.gauss(0, 15) for _ in range(10)])
    return out


def test_cluster_ci_reflects_session_spread():
    tight = stats.cluster_bootstrap_floor(_clusters(50), "p50")
    wide = stats.cluster_bootstrap_floor(_clusters(400), "p50")
    assert wide.width_ms > tight.width_ms * 2, (tight.width_ms, wide.width_ms)
    print("  session spread 50ms -> CI width %.0f; spread 400ms -> %.0f"
          % (tight.width_ms, wide.width_ms))


def test_per_sample_bootstrap_would_lie():
    """The same data, bootstrapped per-sample, yields a far narrower interval -
    the reason run-level clustering is mandatory."""
    clusters = _clusters(400)
    pooled = sorted(x for c in clusters for x in c)
    rng = random.Random(4)
    boots = sorted(
        sorted(rng.choices(pooled, k=len(pooled)))[len(pooled) // 2]
        for _ in range(2000))
    naive_width = boots[int(0.975 * 2000)] - boots[int(0.025 * 2000)]
    cluster = stats.cluster_bootstrap_floor(clusters, "p50")
    assert cluster.width_ms > naive_width * 1.5, (cluster.width_ms, naive_width)
    print("  naive per-sample CI %.0f ms vs cluster CI %.0f ms" %
          (naive_width, cluster.width_ms))


def test_decomposition_resolvable():
    floor = stats.FloorEstimate("p50", 1700.0, 1550.0, 1850.0, 30, 312)
    d = stats.decompose_lens_m(2600.0, floor)
    assert d.resolvable and abs(d.point_ms - 900.0) < 1e-9
    assert d.lo_ms == 750.0 and d.hi_ms == 1050.0
    assert "CI 750-1050" in d.statement
    print("  2600ms model over 1700ms floor: %s" % d.statement[:60])


def test_decomposition_swallowed_by_variance():
    floor = stats.FloorEstimate("p50", 1700.0, 1300.0, 2050.0, 30, 312)
    d = stats.decompose_lens_m(2000.0, floor)
    assert not d.resolvable
    assert "platform variance exceeds" in d.statement
    print("  2000ms model, floor CI 1300-2050: %s" % d.statement[:70])


def test_min_meaningful_threshold():
    floor = stats.FloorEstimate("p50", 1700.0, 1650.0, 1750.0, 30, 312)
    ok = stats.decompose_lens_m(2600.0, floor, min_meaningful_ms=100.0)
    assert ok.resolvable
    marginal = stats.decompose_lens_m(1840.0, floor, min_meaningful_ms=100.0)
    assert not marginal.resolvable  # lo = 90ms < 100ms floor of meaning
    print("  min_meaningful gate: 850ms contribution passes, 90ms does not")


def test_survival_censoring_not_discarded():
    """30 runs: 5 die early, 25 survive to the 600s cap. Dropping censored
    runs would say 'median breakdown ~90s'; Kaplan-Meier says the truth."""
    obs = ([stats.SoakObservation(60.0 + i * 15, True, "stall") for i in range(5)]
           + [stats.SoakObservation(600.0, False) for _ in range(25)])
    b = stats.breakdown_summary(obs, cap_s=600.0)
    assert b.median_survival_s is None  # never fell below 50% alive
    assert b.n_deaths == 5
    assert abs(b.survival_at_cap.point - 25 / 30) < 1e-9
    assert "beyond the 600 s cap" in b.statement()
    print("  5 deaths + 25 censored: %s" % b.statement()[:70])


def test_survival_median_when_most_die():
    obs = ([stats.SoakObservation(t, True) for t in (30, 60, 90, 120, 150, 180)]
           + [stats.SoakObservation(600.0, False) for _ in range(2)])
    b = stats.breakdown_summary(obs, cap_s=600.0)
    assert b.median_survival_s == 120.0, b.median_survival_s
    curve = stats.survival_curve(obs)
    assert all(0.0 <= p.survival <= 1.0 for p in curve)
    assert [round(p.survival, 3) for p in curve][:2] == [0.875, 0.75]
    print("  6/8 die: median survival %.0fs, curve monotone" % b.median_survival_s)


def test_lag_drift_slope():
    from rtveval.latency.base import (Interval, LatencySample, Method,
                                      lag_drift_ms_per_min)
    fps = 30.0
    flashes = [int(t * fps) for t in range(2, 62, 3)]  # every 3s over a minute
    # lag grows 10 ms per flash = 200 ms/min
    samples = [LatencySample(300.0 + 10.0 * k, Interval.V2V_FRAME_TO_FRAME,
                             Method.IMPULSE_XCORR, 1.0, event_index=k)
               for k in range(len(flashes))]
    drift = lag_drift_ms_per_min(samples, fps, flashes)
    assert drift is not None and abs(drift - 200.0) < 5.0, drift
    flat = [s._replace(lag_ms=300.0) for s in samples]
    assert abs(lag_drift_ms_per_min(flat, fps, flashes)) < 1.0
    short = samples[:3]
    assert lag_drift_ms_per_min(short, fps, flashes) is None
    print("  drift: +200ms/min recovered; flat ~0; too-few samples -> None")


def test_lens_m_section_post_bridge_claims():
    from rtveval import report
    floor = stats.FloorEstimate("p50", 1927.7, 1894.4, 1961.0, 40, 350)
    bridge = {"lens_p_native_p50_ms": 367.0, "lens_m": {"p50_ms": 1695.0},
              "reactor_delta_ms": 1328.6,
              "runs": [{"n_lags": 10}, {"n_lags": 8}, {"error": "x"}]}
    md = report.lens_m_latency_section(floor, {"xmax-x2.0": 1695.0,
                                               "lingbot-world-2": 2100.0},
                                       bridge)
    assert "NOT a baseline for GPU-served products" in md
    assert "[Lens M, raw]" in md and "not recoverable" in md
    assert "one model at one load profile" in md  # single-model caveat
    assert "decompos" not in md.lower()  # no decomposition claims survive
    print("  post-bridge claims: floor scoped, raw figures, caveat, no decomposition")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        print(t.__name__)
        try:
            t()
        except Exception:
            failed += 1
            import traceback
            traceback.print_exc(limit=3)
    print("\n%d/%d passed" % (len(tests) - failed, len(tests)))
    sys.exit(1 if failed else 0)
