"""Aggregation, agreement gates, and the sensitivity/variant sweeps."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rtveval import rubrics, stats
from rtveval.routing import GENERATION, V2V


def test_worked_example_from_the_plan():
    """Reproduces final-execution-plan sec 6 end to end."""
    assert stats.clip_score([4, 3, 4]) == 4.0
    dim = stats.dimension_score([5, 4, 5, 4, 3, 4, 4, 5, 4, 4], "temporal_coherence")
    assert abs(dim.mean - 4.2) < 1e-9, dim.mean
    assert dim.min == 3 and not dim.worst_case_flag
    contribution = dim.mean * rubrics.WEIGHTS[V2V][rubrics.LIVE_PRODUCTION]["temporal_coherence"]
    assert abs(contribution - 1.26) < 1e-9, contribution
    print("  clip median 4, dim mean 4.2, contribution %.2f - matches plan" % contribution)


def test_worst_case_flag():
    flagged = stats.dimension_score([5, 5, 5, 5, 5, 5, 5, 5, 2], "structural_fidelity")
    assert flagged.worst_case_flag, "min=2 must raise the flag despite mean 4.67"
    print("  excellent-on-eight-unusable-on-one correctly flagged (mean %.2f, min %.0f)"
          % (flagged.mean, flagged.min))


def test_wilson_matches_addendum_table():
    """Addendum Part 7: N=300 at 5% -> roughly 3.1-8.0%."""
    r = stats.wilson(15, 300)  # 15 failures out of 300
    assert 0.030 < r.lo < 0.033 and 0.079 < r.hi < 0.082, r
    print("  N=300 at 5%%: %s" % (r,))

    good, bad = stats.wilson(2, 400), stats.wilson(20, 400)
    assert good.separable_from(bad), "0.5%% vs 5%% must be separable at N=400"
    close_a, close_b = stats.wilson(15, 300), stats.wilson(9, 300)
    assert not close_a.separable_from(close_b), "5%% vs 3%% must NOT be separable"
    print("  0.5%% vs 5%% separable; 5%% vs 3%% correctly not")


def test_tie_rule():
    assert stats.is_tie(4.1, 4.35) and not stats.is_tie(4.1, 4.45)
    print("  tie rule: <0.3 declared a tie")


def test_variant_sweep_consistent():
    """Ordering that survives all three weightings - the question wasn't load-bearing."""
    means = {
        "lucy-2.5": {"temporal_coherence": 4.5, "structural_fidelity": 4.3,
                     "style_adherence": 4.2, "detail_retention": 4.4,
                     "occlusion_reentry": 4.1, "aesthetic_quality": 4.3},
        "xmax-x2.0": {"temporal_coherence": 3.4, "structural_fidelity": 3.3,
                      "style_adherence": 3.5, "detail_retention": 3.2,
                      "occlusion_reentry": 3.1, "aesthetic_quality": 3.4},
    }
    sweep = stats.variant_sweep(means, V2V)
    assert sweep.consistent, sweep.orders
    print("  %s" % sweep.note)


def test_variant_sweep_flips():
    """A steer-strong, composition-weak product wins only under `interactive`."""
    means = {
        "steer-strong": {"prompt_adherence": 3.8, "physical_plausibility": 3.8,
                         "long_horizon": 3.8, "composition": 2.5,
                         "interactive_responsiveness": 5.0},
        "pretty-slow": {"prompt_adherence": 3.9, "physical_plausibility": 3.9,
                        "long_horizon": 3.9, "composition": 4.8,
                        "interactive_responsiveness": 2.2},
    }
    sweep = stats.variant_sweep(means, GENERATION)
    assert not sweep.consistent, sweep.orders
    for variant, order in sweep.orders.items():
        print("    %-18s %s" % (variant, " > ".join(order)))
    print("  %s" % sweep.note)


def test_weight_sensitivity_detects_instability():
    means = {
        "a": {"temporal_coherence": 4.0, "structural_fidelity": 4.6,
              "style_adherence": 4.0, "detail_retention": 4.0,
              "occlusion_reentry": 4.0, "aesthetic_quality": 4.0},
        "b": {"temporal_coherence": 4.14, "structural_fidelity": 4.0,
              "style_adherence": 4.0, "detail_retention": 4.0,
              "occlusion_reentry": 4.0, "aesthetic_quality": 4.0},
    }
    s = stats.weight_sensitivity(means, V2V)
    print("  baseline %s | stable=%s" % (" > ".join(s.baseline_order), s.stable))
    if not s.stable:
        print("    hinges on: %s" % ", ".join(s.deciding_weights))
        print("    e.g. %s" % s.flips[0])


def test_krippendorff_gate():
    agreeing = [[5, 4, 3, 2, 1, 4], [5, 4, 3, 2, 1, 4], [5, 4, 3, 2, 2, 4]]
    a = stats.krippendorff_alpha(agreeing)
    assert a.gate == stats.NORMAL and a.may_claim_ranking, a
    print("  agreeing raters: alpha %.3f -> %s" % (a.alpha, a.gate))

    split = [[5, 1, 4, 2, 5, 1], [1, 5, 2, 4, 1, 5], [3, 3, 5, 1, 3, 3]]
    c = stats.krippendorff_alpha(split)
    assert c.gate == stats.CONTESTED and not c.may_claim_ranking, c
    print("  split raters: alpha %.3f -> %s (no ranking claim)" % (c.alpha, c.gate))


def test_bradley_terry():
    # item 0 beats everyone, item 2 loses to everyone
    pairs = [(0, 1)] * 7 + [(1, 0)] * 2 + [(0, 2)] * 8 + [(1, 2)] * 6 + [(2, 1)] * 1
    strengths = stats.bradley_terry(pairs, n_items=3)
    assert strengths[0] > strengths[1] > strengths[2], strengths
    print("  Bradley-Terry strengths: %s" % ["%.2f" % s for s in strengths])


def test_amendment_log_matches_code():
    """A silent edit to the pre-registered rubric must fail here: every
    RUBRIC_VERSION needs a matching entry in the amendment log."""
    import re
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_path = os.path.join(repo, rubrics.AMENDMENT_LOG)
    assert os.path.exists(log_path), "amendment log missing: %s" % rubrics.AMENDMENT_LOG
    with open(log_path) as f:
        versions = re.findall(r"^## v([\d.]+) ", f.read(), re.M)
    assert versions, "amendment log has no entries"
    assert versions[0] == rubrics.RUBRIC_VERSION, (
        "rubric code is v%s but the newest amendment entry is v%s - a rubric "
        "change without a logged amendment is a silent edit to a pre-registered "
        "document" % (rubrics.RUBRIC_VERSION, versions[0]))
    print("  rubric v%s has a matching amendment-log entry (newest of %d)"
          % (rubrics.RUBRIC_VERSION, len(versions)))


def test_intra_rater():
    dev, flag = stats.intra_rater_deviation(4, 2)
    assert flag and dev == 2
    print("  hidden repeat deviating by %.0f correctly flags the rater" % dev)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        print(t.__name__)
        try:
            t()
        except Exception as e:
            failed += 1
            print("  FAIL: %s: %s" % (type(e).__name__, e))
    print("\n%d/%d passed" % (len(tests) - failed, len(tests)))
    sys.exit(1 if failed else 0)
