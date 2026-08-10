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
