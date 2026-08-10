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
    Product(
        key="xmax-x2.0",
        display="Xmax X2.0",
        category=V2V,
        vendor="Xmax",
        aliases=("xmax", "x2.0", "x2-0"),
        planned_route="xmax-native",
        planned_lens="P",
    ),
    Product(
        key="lingbot-world-2",
        display="LingBot-World 2",
        category=GENERATION,
        vendor="Ant",
        aliases=("lingbot", "ling-bot", "lingguang", "world 2", "world-2"),
        planned_route="reactor",
        planned_lens="M",
    ),
    Product(
        key="happy-oyster",
        display="Happy Oyster",
        category=GENERATION,
        vendor="Alibaba",
        aliases=("happy oyster", "happy-oyster", "oyster", "kuaile", "haoshi"),
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
