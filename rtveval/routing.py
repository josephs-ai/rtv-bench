"""The six products under test, their categories, and how to recognise them
in a third-party model catalog.

Lens P = product-as-shipped (native vendor API).
Lens M = model-on-common-substrate (Reactor).
Per final-execution-plan.md sec 2, a figure carries exactly one lens label and
lenses never share a table.
"""
from typing import List, NamedTuple, Tuple

V2V = "v2v"
GENERATION = "generation"
DIGITAL_HUMAN = "digital_human"

# Interaction contract: HOW a product is driven. Within the generation
# category, LingBot-World 2 is driven by keyboard movement / view control
# (WASD world exploration) while Happy Oyster Director takes text scene
# direction. G1-G7 (and especially G7's mid-stream TEXT steer) assume the
# text-directed contract and may be structurally inexpressible in a
# movement-driven world model. Products with different contracts are not doing
# the same task; per the same logic as lenses and categories, they are scored
# against the contract each supports and NOT ranked across. capability.py gates
# this before Campaign C.
TEXT_DIRECTED = "text_directed"      # prompt / text scene direction (Happy Oyster Director)
MOVEMENT_DRIVEN = "movement_driven"  # WASD / camera-pose control (LingBot-World 2)
V2V_TRANSFORM = "v2v_transform"      # source video in, restyled video out (Lucy, Xmax)
SCRIPT_DRIVEN = "script_driven"      # audio/script -> avatar (Vidu)


class Product(NamedTuple):
    key: str
    display: str
    category: str
    vendor: str
    # Substrings (lowercased) that identify this product in a catalog listing.
    # Deliberately loose: the probe reports candidates for human confirmation,
    # it does not auto-commit a routing decision.
    aliases: Tuple[str, ...]
    # Routing as recorded in final-execution-plan.md sec 1, before the probe runs.
    planned_route: str
    planned_lens: str
    # How the product is driven. Products with different contracts are scored
    # against their own contract and never ranked across (see capability.py).
    # Confirmed for generation in the pilot capability probe before Campaign C.
    interaction_contract: str = ""


PRODUCTS: List[Product] = [
    Product(
        key="lucy-2.5",
        display="Lucy 2.5",
        category=V2V,
        vendor="Decart",
        aliases=("lucy",),
        planned_route="decart-native",
        planned_lens="P",
        interaction_contract=V2V_TRANSFORM,
    ),
    # DECISION (2026-08-10, final): Xmax runs via Reactor only; no native key.
    # Probe confirmed `xmax/x2` (75b9886b-...) in the catalog; Lucy is NOT on
    # Reactor, so no dual-routed bridge exists. Instead, the echo platform-
    # floor calibration (tools/echo_calibration.py, data/platform-floor-*.json)
    # decomposes every Lens M latency into platform + model. Consequence for
    # the report: Lucy-vs-Xmax latency is a DERIVED-APPROXIMATE comparison
    # (Xmax minus floor vs Lucy measured), labelled as such - never presented
    # as a measured head-to-head. Within Lens M (Xmax/LingBot/Happy Oyster)
    # comparisons are same-substrate and clean.
    Product(
        key="xmax-x2.0",
        display="Xmax X2.0",
        category=V2V,
        vendor="Xmax",
        aliases=("xmax", "x2.0", "x2-0", "x2"),
        planned_route="reactor",
        planned_lens="M",
        interaction_contract=V2V_TRANSFORM,
    ),
    # Probe 2026-08-10: catalog id `reactor/lingbot-world-2`
    # (356908d6-a8d5-470f-9a28-3c99a7b0c074). NOTE: v1 (`reactor/lingbot`) is
    # ALSO served - the alias here is deliberately exact so v1 can never
    # match; pinning the wrong generation would violate hard rule 5 silently.
    Product(
        key="lingbot-world-2",
        display="LingBot-World 2",
        category=GENERATION,
        vendor="Ant",
        aliases=("lingbot-world-2", "lingbot world 2", "lingbot-world-v2"),
        planned_route="reactor",
        planned_lens="M",
        interaction_contract=MOVEMENT_DRIVEN,
    ),
    # Resolved 2026-08-10: served on Reactor but UNLISTED - GET /models omits
    # it, yet POST /sessions creates fine (201, session verified + deleted).
    # Ids from the @reactor-models/happy-oyster SDK bundle:
    #   reactor/happy-oyster-adventure  (exploration / camera control)
    #   reactor/happy-oyster-director   (text-steered, pause/rewind)
    # Eval target: DIRECTOR - the generation prompt set (G1-G7, incl. the G7
    # mid-stream steer) is text-driven, which is director mode's contract.
    # Session response carries model.version + server_version + cluster: use
    # those for the run row (hard rule 5). NOTE the catalog re-check in
    # ReactorAdapter._resolve_version will NOT find unlisted models - resolve
    # via session response instead for this product.
    Product(
        key="happy-oyster",
        display="Happy Oyster",
        category=GENERATION,
        vendor="Alibaba",
        aliases=("happy-oyster-director", "happy-oyster-adventure",
                 "happy oyster", "happy-oyster"),
        planned_route="reactor",
        planned_lens="M",
        interaction_contract=TEXT_DIRECTED,
    ),
    Product(
        key="pixverse-r1",
        display="PixVerse R1",
        category=GENERATION,
        vendor="PixVerse",
        aliases=("pixverse", "pix-verse"),
        planned_route="partner-waitlist",
        planned_lens="P",
        interaction_contract=TEXT_DIRECTED,
    ),
    Product(
        key="vidu-s1",
        display="Vidu S1",
        category=DIGITAL_HUMAN,
        vendor="Shengshu",
        aliases=("vidu", "shengshu"),
        planned_route="enterprise-beta",
        planned_lens="P",
        interaction_contract=SCRIPT_DRIVEN,
    ),
]

BY_KEY = {p.key: p for p in PRODUCTS}


def match(text: str) -> List[Product]:
    """Return every product whose aliases appear in `text`."""
    low = text.lower()
    return [p for p in PRODUCTS if any(a in low for a in p.aliases)]
