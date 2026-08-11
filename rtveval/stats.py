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
# Session survival: how long until the video breaks down
# --------------------------------------------------------------------------

class SoakObservation(NamedTuple):
    """One session's endurance. `died=False` means CENSORED - the session was
    still alive when the clip ended or the cap hit. Censored runs are not
    discarded: 'survived at least 600s' is information, and dropping it would
    bias time-to-breakdown catastrophically low (only deaths would count)."""

    duration_s: float
    died: bool
    cause: str = ""  # stall / teardown / quality_collapse (human-flagged) / ""


class SurvivalPoint(NamedTuple):
    t_s: float
    survival: float  # Kaplan-Meier estimate of P(alive at t)
    at_risk: int


def survival_curve(obs: Sequence[SoakObservation]) -> List[SurvivalPoint]:
    """Kaplan-Meier product-limit estimator. Handles censoring correctly:
    a run that ended alive leaves the risk set without counting as a death."""
    if not obs:
        return []
    events = sorted(obs, key=lambda o: o.duration_s)
    n_risk = len(events)
    s = 1.0
    curve: List[SurvivalPoint] = []
    i = 0
    while i < len(events):
        t = events[i].duration_s
        deaths = censored = 0
        while i < len(events) and events[i].duration_s == t:
            if events[i].died:
                deaths += 1
            else:
                censored += 1
            i += 1
        if deaths and n_risk:
            s *= (1.0 - deaths / n_risk)
            curve.append(SurvivalPoint(t_s=t, survival=s, at_risk=n_risk))
        n_risk -= deaths + censored
    return curve


class BreakdownSummary(NamedTuple):
    n: int
    n_deaths: int
    median_survival_s: Optional[float]  # None = never dropped below 50%
    survival_at_cap: Rate  # survived-to-cap fraction with Wilson CI
    cap_s: float

    def statement(self) -> str:
        med = ("median time-to-breakdown %.0f s" % self.median_survival_s
               if self.median_survival_s is not None else
               "median time-to-breakdown beyond the %.0f s cap (never reached "
               "50%% failures)" % self.cap_s)
        return "%s; %s of sessions survive the full %.0f s" % (
            med, self.survival_at_cap, self.cap_s)


def breakdown_summary(obs: Sequence[SoakObservation], cap_s: float) -> BreakdownSummary:
    """The reportable pair: median survival (if reached) + survive-to-cap rate.
    'In a perfect world it never breaks' makes survival_at_cap the headline:
    a perfect product scores 100% with the CI to prove it."""
    curve = survival_curve(obs)
    median = next((p.t_s for p in curve if p.survival <= 0.5), None)
    survived = sum(1 for o in obs if not o.died and o.duration_s >= cap_s * 0.99)
    return BreakdownSummary(n=len(obs), n_deaths=sum(1 for o in obs if o.died),
                            median_survival_s=median,
                            survival_at_cap=wilson(survived, len(obs)),
                            cap_s=cap_s)


# --------------------------------------------------------------------------
# Platform-floor uncertainty (Lens M decomposition)
# --------------------------------------------------------------------------

class FloorEstimate(NamedTuple):
    stat: str  # "p50" | "p95"
    point_ms: float
    lo_ms: float
    hi_ms: float
    n_runs: int
    n_samples: int

    @property
    def width_ms(self) -> float:
        return self.hi_ms - self.lo_ms


def cluster_bootstrap_floor(run_samples: Sequence[Sequence[float]],
                            stat: str = "p50", n_boot: int = 5000,
                            confidence: float = 0.95,
                            seed: int = 20260810) -> FloorEstimate:
    """CI for the platform floor by resampling RUNS, not samples.

    Lag samples within one run share a session (correlated); the observed
    1.6x session-to-session spread is the variance that matters. A naive
    per-sample bootstrap would understate the interval badly.
    """
    import random

    clusters = [list(c) for c in run_samples if c]
    if len(clusters) < 3:
        raise ValueError("need >=3 runs with samples for a run-level bootstrap")

    def statistic(pooled: List[float]) -> float:
        s = sorted(pooled)
        if stat == "p50":
            return s[len(s) // 2]
        if stat == "p95":
            return s[max(0, int(round(0.95 * len(s))) - 1)]
        raise ValueError(stat)

    rng = random.Random(seed)
    boots = []
    for _ in range(n_boot):
        chosen = [clusters[rng.randrange(len(clusters))] for _ in clusters]
        boots.append(statistic([x for c in chosen for x in c]))
    boots.sort()
    alpha = 1 - confidence
    lo = boots[int(alpha / 2 * n_boot)]
    hi = boots[min(n_boot - 1, int((1 - alpha / 2) * n_boot))]
    pooled = [x for c in clusters for x in c]
    return FloorEstimate(stat=stat, point_ms=statistic(pooled), lo_ms=lo,
                         hi_ms=hi, n_runs=len(clusters), n_samples=len(pooled))


class Decomposition(NamedTuple):
    """model latency minus platform floor, with the floor's uncertainty
    propagated. Interval arithmetic - conservative on purpose."""

    model_ms: float
    floor: FloorEstimate
    point_ms: float
    lo_ms: float
    hi_ms: float
    resolvable: bool
    statement: str


def decompose_lens_m(model_ms: float, floor: FloorEstimate,
                     min_meaningful_ms: float = 0.0) -> Decomposition:
    """The report's Lens M sentence, with honesty built in.

    `resolvable` is False when the propagated interval includes
    min_meaningful_ms or below - i.e. when platform variance swallows the
    model contribution. That is a legitimate finding and the statement says
    it, instead of publishing a decomposition that looks precise and isn't.
    """
    point = model_ms - floor.point_ms
    lo = model_ms - floor.hi_ms
    hi = model_ms - floor.lo_ms
    resolvable = lo > min_meaningful_ms
    if resolvable:
        statement = ("~%.0f ms model contribution (95%% CI %.0f-%.0f ms) after "
                     "subtracting the platform floor (%.0f ms, CI %.0f-%.0f, "
                     "n=%d runs)" % (point, lo, hi, floor.point_ms,
                                     floor.lo_ms, floor.hi_ms, floor.n_runs))
    else:
        statement = ("platform variance exceeds the model contribution that can "
                     "be resolved: measured %.0f ms against a floor of %.0f ms "
                     "(CI %.0f-%.0f); the model-only estimate spans %.0f-%.0f ms "
                     "and is not reportable as a number" %
                     (model_ms, floor.point_ms, floor.lo_ms, floor.hi_ms, lo, hi))
    return Decomposition(model_ms=model_ms, floor=floor, point_ms=point,
                         lo_ms=lo, hi_ms=hi, resolvable=resolvable,
                         statement=statement)


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
