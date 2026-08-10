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


PRODUCTS: List[Product] = [
    Product(
        key="lucy-2.5",
        display="Lucy 2.5",
        category=V2V,
        vendor="Decart",
        aliases=("lucy",),
        planned_route="decart-native",
        planned_lens="P",
    ),
    # Routing changed 2026-08-10: user elected to run Xmax via Reactor rather
    # than obtain the self-serve native key. Probe confirmed `xmax/x2`
    # (75b9886b-1fb5-4bb3-873a-6a44f5b8c70d) in the catalog.
    # Probe also showed Lucy is NOT on Reactor - so Xmax-on-both-routes is now
    # the ONLY possible sec 2.1 bridge. Without the self-serve native key,
    # Lens M and Lens P latencies cannot be reconciled and the Lucy-vs-Xmax
    # latency head-to-head cannot be made.
    Product(
        key="xmax-x2.0",
        display="Xmax X2.0",
        category=V2V,
        vendor="Xmax",
        aliases=("xmax", "x2.0", "x2-0", "x2"),
        planned_route="reactor",
        planned_lens="M",
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
    ),
    Product(
        key="pixverse-r1",
        display="PixVerse R1",
        category=GENERATION,
        vendor="PixVerse",
        aliases=("pixverse", "pix-verse"),
        planned_route="partner-waitlist",
        planned_lens="P",
    ),
    Product(
        key="vidu-s1",
        display="Vidu S1",
        category=DIGITAL_HUMAN,
        vendor="Shengshu",
        aliases=("vidu", "shengshu"),
        planned_route="enterprise-beta",
        planned_lens="P",
    ),
]

BY_KEY = {p.key: p for p in PRODUCTS}


def match(text: str) -> List[Product]:
    """Return every product whose aliases appear in `text`."""
    low = text.lower()
    return [p for p in PRODUCTS if any(a in low for a in p.aliases)]
