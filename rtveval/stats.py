"""The statistics the Spec mandates: Wilson intervals, aggregation, agreement
gates, and the sensitivity sweep - extended to run across all three weighting
variants.
"""
import statistics
from typing import Dict, Iterable, List, NamedTuple, Optional, Sequence, Tuple

from . import rubrics

TIE_THRESHOLD = 0.3  # Spec Part F step 4
WORST_CASE_FLAG_AT = 2.0  # Spec Part F step 2


# --------------------------------------------------------------------------
# Reliability (Spec Part B)
# --------------------------------------------------------------------------

class Rate(NamedTuple):
    successes: int
    n: int
    point: float
    lo: float
    hi: float

    def __str__(self) -> str:
        return "%.1f%% (95%% CI %.1f-%.1f%%, N=%d)" % (
            self.point * 100, self.lo * 100, self.hi * 100, self.n)

    def separable_from(self, other: "Rate") -> bool:
        """Non-overlapping intervals. The only licence to claim a difference."""
        return self.hi < other.lo or other.hi < self.lo


def wilson(successes: int, n: int, confidence: float = 0.95) -> Rate:
    """Wilson score interval. Never report a bare percentage (Spec B.2)."""
    from statsmodels.stats.proportion import proportion_confint

    if n <= 0:
        raise ValueError("n must be positive")
    if not 0 <= successes <= n:
        raise ValueError("successes %d outside 0..%d" % (successes, n))

    lo, hi = proportion_confint(successes, n, alpha=1 - confidence, method="wilson")
    return Rate(successes, n, successes / n, float(lo), float(hi))


# --------------------------------------------------------------------------
# Quality aggregation (Spec Part F)
# --------------------------------------------------------------------------

class DimensionScore(NamedTuple):
    key: str
    mean: float
    min: float
    n_clips: int
    worst_case_flag: bool


def clip_score(rater_scores: Sequence[float]) -> float:
    """Median across raters - resists a single outlier rater (Part F step 1)."""
    if not rater_scores:
        raise ValueError("no rater scores")
    return float(statistics.median(rater_scores))


def dimension_score(clip_scores: Sequence[float], key: str = "") -> DimensionScore:
    """Mean across clips, plus the min and its worst-case flag (Part F step 2).

    The flag exists because a model that is excellent on eight clips and
    unusable on one is a specific product profile that a mean hides.
    """
    if not clip_scores:
        raise ValueError("no clip scores for dimension %r" % key)
    lo = float(min(clip_scores))
    return DimensionScore(key=key, mean=float(statistics.fmean(clip_scores)),
                          min=lo, n_clips=len(clip_scores),
                          worst_case_flag=lo <= WORST_CASE_FLAG_AT)


def category_score(dimension_means: Dict[str, float], category: str,
                   variant: str = rubrics.LIVE_PRODUCTION) -> float:
    """Weighted sum on the 1-5 scale (Part F step 3)."""
    weights = rubrics.WEIGHTS[category][variant]
    missing = set(weights) - set(dimension_means)
    if missing:
        raise ValueError("missing dimension scores: %s" % sorted(missing))
    return sum(w * dimension_means[k] for k, w in weights.items())


def is_tie(a: float, b: float) -> bool:
    """Differences below 0.3 are not meaningful (Part F step 4)."""
    return abs(a - b) < TIE_THRESHOLD


def rank(scores: Dict[str, float]) -> List[Tuple[str, float]]:
    return sorted(scores.items(), key=lambda kv: -kv[1])


# --------------------------------------------------------------------------
# Sensitivity (Spec Part F step 6, extended across variants)
# --------------------------------------------------------------------------

class Sensitivity(NamedTuple):
    stable: bool
    baseline_order: List[str]
    flips: List[str]  # human-readable description of each perturbation that flipped it
    deciding_weights: List[str]


def weight_sensitivity(dimension_means: Dict[str, Dict[str, float]], category: str,
                       variant: str = rubrics.LIVE_PRODUCTION,
                       delta: float = 0.10) -> Sensitivity:
    """Perturb each weight by +-delta (relative), renormalise, re-rank.

    `dimension_means` is {product_key: {dimension_key: mean}}.
    """
    weights = rubrics.WEIGHTS[category][variant]
    baseline = [p for p, _ in rank({p: category_score(d, category, variant)
                                    for p, d in dimension_means.items()})]

    flips: List[str] = []
    deciding: List[str] = []
    for key in weights:
        for sign in (+1, -1):
            perturbed = dict(weights)
            perturbed[key] = max(0.0, perturbed[key] * (1 + sign * delta))
            total = sum(perturbed.values())
            perturbed = {k: v / total for k, v in perturbed.items()}

            order = [p for p, _ in rank({
                p: sum(w * d[k] for k, w in perturbed.items())
                for p, d in dimension_means.items()})]
            if order != baseline:
                flips.append("%s %+d%%: %s" % (key, int(sign * delta * 100), " > ".join(order)))
                if key not in deciding:
                    deciding.append(key)

    return Sensitivity(stable=not flips, baseline_order=baseline,
                       flips=flips, deciding_weights=deciding)


class VariantSweep(NamedTuple):
    orders: Dict[str, List[str]]  # variant -> ranking
    consistent: bool
    note: str


def variant_sweep(dimension_means: Dict[str, Dict[str, float]],
                  category: str) -> VariantSweep:
    """Rank under every distinct weighting variant.

    This is what replaces the primary-use-case blocker. Publish the whole set.
    """
    orders: Dict[str, List[str]] = {}
    for variant in rubrics.distinct_variants(category):
        scores = {p: category_score(d, category, variant)
                  for p, d in dimension_means.items()}
        orders[variant] = [p for p, _ in rank(scores)]

    distinct = {tuple(o) for o in orders.values()}
    consistent = len(distinct) == 1
    if consistent:
        note = ("Ordering holds across all weighting variants; the primary "
                "use case is not load-bearing for this ranking.")
    else:
        note = ("Ordering depends on the weighting variant - report the decision "
                "rule, not a single winner.")
    return VariantSweep(orders=orders, consistent=consistent, note=note)


# --------------------------------------------------------------------------
# Rater reliability (Spec Part G)
# --------------------------------------------------------------------------

NORMAL, TENTATIVE, CONTESTED = "normal", "tentative", "contested"


class Agreement(NamedTuple):
    alpha: float
    gate: str

    @property
    def may_claim_ranking(self) -> bool:
        return self.gate != CONTESTED


def krippendorff_alpha(reliability_data: Sequence[Sequence[Optional[float]]]) -> Agreement:
    """Ordinal alpha, with the Spec's interpretation gate applied.

    `reliability_data` is raters x units, None for unrated.
    """
    import krippendorff as kd
    import numpy as np

    arr = np.array([[np.nan if v is None else float(v) for v in row]
                    for row in reliability_data], dtype=float)
    alpha = float(kd.alpha(reliability_data=arr, level_of_measurement="ordinal"))

    if alpha >= 0.80:
        gate = NORMAL
    elif alpha >= 0.67:
        gate = TENTATIVE
    else:
        gate = CONTESTED
    return Agreement(alpha=alpha, gate=gate)


def bradley_terry(pairs: Iterable[Tuple[int, int]], n_items: int) -> List[float]:
    """Strength parameters from forced-choice data. `pairs` are (winner, loser)."""
    import choix

    data = list(pairs)
    if not data:
        raise ValueError("no pairwise comparisons")
    return list(choix.ilsr_pairwise(n_items, data, alpha=0.01))


def intra_rater_deviation(first: float, repeat: float) -> Tuple[float, bool]:
    """Hidden-repeat check. Deviation >1 point flags the rater (Spec Part G)."""
    dev = abs(first - repeat)
    return dev, dev > 1.0
