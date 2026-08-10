"""Interaction-contract capability gate (before Campaign C).

The category problem, one level down: two products in the *same* category can
have incompatible interaction contracts. LingBot-World 2 is movement-driven
(WASD/camera); Happy Oyster Director is text-driven. G1-G7 assume text
direction - G7's mid-stream text steer may be structurally inexpressible in a
movement-driven world model. Scoring LingBot a 1 for failing a prompt set it
cannot express is a measurement error, not a product finding.

So, before Campaign C, each generation product is probed for what it actually
accepts, and the harness enforces the consistent rule already applied to lenses
and categories: score each product against the contract it supports, and never
rank across contracts.

`capability_probe_record()` documents the confirmed contract per product (from
a real, minimal session - not assumed). `rankable_groups()` partitions a
category by contract so the report can only ever rank within a compatible set.
`assert_common_contract()` is the guard the ranking path calls; it refuses a
cross-contract ranking the same way report.Table refuses a cross-lens row.
"""
from typing import Dict, List, NamedTuple, Sequence

from . import routing


class ContractViolation(ValueError):
    pass


class ContractProbe(NamedTuple):
    product_key: str
    declared_contract: str      # from routing.py
    confirmed_contract: str     # from the capability probe
    accepts_text_steer: bool    # can it express G7's mid-stream text steer?
    evidence: str               # what the probe observed

    @property
    def matches_declared(self) -> bool:
        return self.confirmed_contract == self.declared_contract


def rankable_groups(product_keys: Sequence[str]) -> Dict[str, List[str]]:
    """Partition products by interaction contract. Ranking is allowed WITHIN a
    group and forbidden ACROSS groups. A group of one is a legitimate result -
    'evaluated, but no contract-compatible peer to rank against'."""
    groups: Dict[str, List[str]] = {}
    for k in product_keys:
        c = routing.BY_KEY[k].interaction_contract or "unspecified"
        groups.setdefault(c, []).append(k)
    return groups


def assert_common_contract(product_keys: Sequence[str]) -> str:
    """Guard for the ranking path. Returns the shared contract or raises with
    the sentence the report prints instead of a ranking."""
    contracts = {routing.BY_KEY[k].interaction_contract for k in product_keys}
    if len(contracts) > 1:
        by_contract = rankable_groups(product_keys)
        raise ContractViolation(
            "Cannot rank across interaction contracts: %s. These products are "
            "driven differently (%s) and are not performing the same task; each "
            "is scored against the contract it supports and reported separately, "
            "not ranked against the other." % (
                ", ".join("%s=%s" % (c, "/".join(ks)) for c, ks in by_contract.items()),
                ", ".join(sorted(contracts))))
    return contracts.pop() if contracts else ""


def generation_ranking_plan(product_keys: Sequence[str]) -> Dict[str, object]:
    """What the report can and cannot claim for a generation cohort.

    If all products share a contract, one ranking. If not, one ranking PER
    contract group, and an explicit statement that no cross-group ranking is
    made - the same posture as no-cross-category composite.
    """
    groups = rankable_groups(product_keys)
    return {
        "groups": groups,
        "single_ranking": len(groups) == 1,
        "note": (
            "All generation products share the %s contract; one within-category "
            "ranking applies." % next(iter(groups)) if len(groups) == 1 else
            "Generation products split across %d interaction contracts (%s). "
            "Each group is ranked and reported on its own; no ranking is made "
            "across groups, because the products are not doing the same task."
            % (len(groups), ", ".join(sorted(groups)))),
    }


def probe_record(product_key: str, confirmed_contract: str,
                 accepts_text_steer: bool, evidence: str) -> ContractProbe:
    """Build a probe record, checking the confirmation against what routing.py
    declared. A mismatch is not silently accepted - the caller sees it."""
    declared = routing.BY_KEY[product_key].interaction_contract
    return ContractProbe(product_key, declared, confirmed_contract,
                         accepts_text_steer, evidence)
