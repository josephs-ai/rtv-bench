"""Report assembly with the constraints in the types, not in day-5 memory.

Three structural rules, enforced at construction so a violating artefact
cannot exist, let alone render:

  1. Every table declares its lens, and rows of the other lens are rejected.
     No composite spans lenses (final plan sec 2).
  2. Every ranking claim carries its Agreement. A contested dimension
     (alpha < 0.67) CANNOT be rendered as a ranking - constructing the claim
     raises ContestedDimension, whose message is the sentence the report
     prints instead.
  3. Latency cells carry their Interval, and a table refuses to mix
     intervals, mirroring rtveval.latency.base.summarise().
"""
from typing import Dict, List, NamedTuple, Optional, Sequence

from .latency.base import Interval, LatencyResult
from .stats import Agreement, CONTESTED, Rate


class LensViolation(ValueError):
    pass


class ContestedDimension(ValueError):
    pass


class Cell(NamedTuple):
    text: str
    lens: Optional[str] = None
    interval: Optional[Interval] = None


class Table:
    """A report table bound to exactly one lens (or lens=None for lens-free
    content such as rater statistics)."""

    def __init__(self, title: str, lens: Optional[str], columns: Sequence[str]):
        if lens not in (None, "P", "M"):
            raise LensViolation("lens must be P, M, or None, not %r" % lens)
        self.title = title
        self.lens = lens
        self.columns = list(columns)
        self.rows: List[List[Cell]] = []
        self._interval: Optional[Interval] = None

    def add_row(self, cells: Sequence[Cell]) -> None:
        if len(cells) != len(self.columns):
            raise ValueError("row has %d cells for %d columns" % (len(cells), len(self.columns)))
        for c in cells:
            if c.lens is not None and c.lens != self.lens:
                raise LensViolation(
                    "cell measured under Lens %s cannot enter table %r (Lens %s) - "
                    "lenses never share a table" % (c.lens, self.title, self.lens))
            if c.interval is not None:
                if self._interval is None:
                    self._interval = c.interval
                elif c.interval is not self._interval:
                    raise LensViolation(
                        "table %r mixes latency intervals %s and %s - these are "
                        "different measurements" % (self.title, self._interval.value,
                                                    c.interval.value))
        self.rows.append(list(cells))

    def markdown(self) -> str:
        tag = " *(Lens %s)*" % self.lens if self.lens else ""
        iv = "\n*Latency interval: %s*\n" % self._interval.label if self._interval else ""
        head = "| " + " | ".join(self.columns) + " |"
        sep = "|" + "|".join("---" for _ in self.columns) + "|"
        body = "\n".join("| " + " | ".join(c.text for c in row) + " |" for row in self.rows)
        return "### %s%s\n%s\n%s\n%s\n%s" % (self.title, tag, iv, head, sep, body)


def latency_cell(res: LatencyResult) -> Cell:
    return Cell(text="p95 %.0f ms (p50 %.0f, sigma %.0f, n=%d)"
                % (res.p95_ms, res.p50_ms, res.jitter_ms, res.n),
                lens=res.lens, interval=res.interval)


class RankingClaim(NamedTuple):
    """A within-category ordering. Cannot be constructed contested."""

    dimension: str
    order: List[str]
    agreement: Agreement
    qualifier: str  # "" | "tentative"

    @staticmethod
    def make(dimension: str, order: List[str], agreement: Agreement) -> "RankingClaim":
        if agreement.gate == CONTESTED:
            raise ContestedDimension(
                "Raters did not agree on %r (alpha=%.2f < 0.67): no ranking is "
                "claimed for this dimension. Report the disagreement itself - "
                "'trained raters could not agree' is the finding." % (dimension, agreement.alpha))
        qualifier = "tentative" if agreement.gate == "tentative" else ""
        return RankingClaim(dimension, list(order), agreement, qualifier)

    def markdown(self) -> str:
        tag = " *(tentative, alpha=%.2f)*" % self.agreement.alpha if self.qualifier \
            else " (alpha=%.2f)" % self.agreement.alpha
        return "**%s:** %s%s" % (self.dimension, " > ".join(self.order), tag)


def dimension_block(dimension: str, order: List[str], agreement: Agreement) -> str:
    """The only path from a dimension to report text: a ranking when allowed,
    the contested sentence when not. There is no third branch."""
    try:
        return RankingClaim.make(dimension, order, agreement).markdown()
    except ContestedDimension as e:
        return "**%s:** %s" % (dimension, e)


class ProductTriple(NamedTuple):
    """Spec Part F step 5: the presentation is always the triple."""

    product: str
    quality: float
    reliability: Rate
    latency: LatencyResult

    def markdown(self) -> str:
        return ("**%s** - Quality %.1f/5 | Clean success %s | %s"
                % (self.product, self.quality, self.reliability,
                   self.latency.headline()))


def reliability_table(title: str, rates: Dict[str, Rate]) -> Table:
    """Reliability is lens-free in presentation but each rate keeps its N and
    CI; separability is stated pairwise, never implied."""
    t = Table(title, lens=None, columns=["Product", "Clean success (95% CI)", "N"])
    for product, rate in sorted(rates.items()):
        t.add_row([Cell(product), Cell("%.1f%% (%.1f-%.1f%%)"
                                       % (rate.point * 100, rate.lo * 100, rate.hi * 100)),
                   Cell(str(rate.n))])
    return t


def separability_notes(rates: Dict[str, Rate]) -> List[str]:
    """One sentence per pair, from the CI rule and nothing else."""
    notes = []
    items = sorted(rates.items())
    for i, (pa, ra) in enumerate(items):
        for pb, rb in items[i + 1:]:
            if ra.separable_from(rb):
                better = pa if ra.point > rb.point else pb
                notes.append("%s vs %s: intervals do not overlap - %s is more "
                             "reliable at this sample size." % (pa, pb, better))
            else:
                notes.append("%s vs %s: no reliability difference detectable at "
                             "this sample size." % (pa, pb))
    return notes
