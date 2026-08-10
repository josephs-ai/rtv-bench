"""Frozen rubrics and the three weighting variants.

The plan treats the primary use case as a blocking decision. It needn't be: a
sensitivity sweep is already mandated, so the cheaper and more informative move
is to compute the ranking under *all three* weightings and publish the set.

  - If the ordering holds across all three, the question was never load-bearing,
    and the report can say so with evidence.
  - If it flips, that is one of the most useful findings available: which
    product wins depends on your use case, and here is the decision rule.

So `WEIGHTS` carries every variant, and analysis reports all of them. A variant
is still recorded per run for provenance, but nothing waits on it.

Weights are frozen on first import of a dated rubric version. Any change means a
new version string, per hard rule 1.
"""
from typing import Dict, List, NamedTuple

from .routing import DIGITAL_HUMAN, GENERATION, V2V

RUBRIC_VERSION = "1.0"
RUBRIC_FROZEN_DATE = "2026-08-10"

# Any change to this module's dimensions, weights, or descriptors bumps
# RUBRIC_VERSION and adds an entry to docs/rubric-amendments.md - the test
# suite cross-checks the two, so a silent edit to a pre-registered document
# fails CI rather than passing review. Amending is legitimate (a rater trial
# proving descriptors ambiguous is exactly the case); amending silently is not.
AMENDMENT_LOG = "docs/rubric-amendments.md"

# Variants, in report order.
LIVE_PRODUCTION = "live_production"
OFFLINE_STYLISED = "offline_stylised"
INTERACTIVE = "interactive"
VARIANTS = (LIVE_PRODUCTION, OFFLINE_STYLISED, INTERACTIVE)


class Dimension(NamedTuple):
    key: str
    display: str
    # Human-rated dimensions are scored by the panel; computed ones are Layer 1
    # supporting evidence and never carry weight on their own.
    human_rated: bool = True


DIMENSIONS: Dict[str, List[Dimension]] = {
    V2V: [
        Dimension("temporal_coherence", "Temporal coherence"),
        Dimension("structural_fidelity", "Structural fidelity"),
        Dimension("style_adherence", "Style adherence"),
        Dimension("detail_retention", "Detail retention vs. hallucination"),
        Dimension("occlusion_reentry", "Occlusion / re-entry"),
        Dimension("aesthetic_quality", "Aesthetic quality"),
    ],
    GENERATION: [
        Dimension("prompt_adherence", "Prompt adherence"),
        Dimension("physical_plausibility", "Physical plausibility"),
        Dimension("long_horizon", "Long-horizon consistency"),
        Dimension("composition", "Composition & aesthetic"),
        Dimension("interactive_responsiveness", "Interactive responsiveness"),
    ],
    DIGITAL_HUMAN: [
        Dimension("lip_sync", "Lip-sync accuracy"),
        Dimension("identity_stability", "Identity stability"),
        Dimension("micro_behaviour", "Micro-behaviour"),
        Dimension("expressiveness", "Expressiveness"),
        Dimension("body_hands", "Body & hands"),
        Dimension("multilingual", "Multilingual consistency"),
    ],
}


# category -> variant -> {dimension_key: weight}
WEIGHTS: Dict[str, Dict[str, Dict[str, float]]] = {
    V2V: {
        LIVE_PRODUCTION: {
            "temporal_coherence": 0.30, "structural_fidelity": 0.20,
            "style_adherence": 0.15, "detail_retention": 0.15,
            "occlusion_reentry": 0.10, "aesthetic_quality": 0.10,
        },
        # Plan sec 5: drop temporal coherence to 20%, raise detail retention to 25%.
        OFFLINE_STYLISED: {
            "temporal_coherence": 0.20, "structural_fidelity": 0.20,
            "style_adherence": 0.15, "detail_retention": 0.25,
            "occlusion_reentry": 0.10, "aesthetic_quality": 0.10,
        },
        # The plan states no V2V adjustment for interactive/gaming - its rule
        # addresses generation only. Left identical to the default rather than
        # invented, and flagged as such in the report.
        INTERACTIVE: {
            "temporal_coherence": 0.30, "structural_fidelity": 0.20,
            "style_adherence": 0.15, "detail_retention": 0.15,
            "occlusion_reentry": 0.10, "aesthetic_quality": 0.10,
        },
    },
    GENERATION: {
        LIVE_PRODUCTION: {
            "prompt_adherence": 0.25, "physical_plausibility": 0.20,
            "long_horizon": 0.20, "composition": 0.20,
            "interactive_responsiveness": 0.15,
        },
        # No stated generation adjustment for offline stylised.
        OFFLINE_STYLISED: {
            "prompt_adherence": 0.25, "physical_plausibility": 0.20,
            "long_horizon": 0.20, "composition": 0.20,
            "interactive_responsiveness": 0.15,
        },
        # Plan sec 5: responsiveness to 25%, composition to 10%.
        INTERACTIVE: {
            "prompt_adherence": 0.25, "physical_plausibility": 0.20,
            "long_horizon": 0.20, "composition": 0.10,
            "interactive_responsiveness": 0.25,
        },
    },
    DIGITAL_HUMAN: {
        v: {
            "lip_sync": 0.25, "identity_stability": 0.20, "micro_behaviour": 0.20,
            "expressiveness": 0.15, "body_hands": 0.10, "multilingual": 0.10,
        } for v in VARIANTS
    },
}

# Variants that are genuinely distinct from the default, per category. Used by
# the report so it does not present three identical tables as if they were three
# findings.
def distinct_variants(category: str) -> List[str]:
    seen: Dict[tuple, str] = {}
    out: List[str] = []
    for v in VARIANTS:
        sig = tuple(sorted(WEIGHTS[category][v].items()))
        if sig not in seen:
            seen[sig] = v
            out.append(v)
    return out


def validate() -> None:
    """Every variant's weights must sum to 1.0 and cover exactly its dimensions."""
    for category, variants in WEIGHTS.items():
        expected = {d.key for d in DIMENSIONS[category]}
        for variant, weights in variants.items():
            if set(weights) != expected:
                missing = expected - set(weights)
                extra = set(weights) - expected
                raise ValueError("%s/%s dimension mismatch (missing=%s extra=%s)"
                                 % (category, variant, sorted(missing), sorted(extra)))
            total = sum(weights.values())
            if abs(total - 1.0) > 1e-9:
                raise ValueError("%s/%s weights sum to %.4f, not 1.0"
                                 % (category, variant, total))


validate()
