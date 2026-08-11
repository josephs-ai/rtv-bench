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

from .latency.base import CapturePath, Interval, LatencyResult
from .stats import Agreement, CONTESTED, Rate


class LensViolation(ValueError):
    pass


class ContestedDimension(ValueError):
    pass


class Cell(NamedTuple):
    text: str
    lens: Optional[str] = None
    interval: Optional[Interval] = None
    capture_path: Optional[CapturePath] = None


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
        self._capture_path: Optional[CapturePath] = None

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
            if c.capture_path is not None:
                if self._capture_path is None:
                    self._capture_path = c.capture_path
                elif c.capture_path is not self._capture_path:
                    raise LensViolation(
                        "table %r mixes capture paths %s and %s - composite and "
                        "SDK-path figures are different measurements and do not "
                        "share a table" % (self.title, self._capture_path.value,
                                           c.capture_path.value))
        self.rows.append(list(cells))

    def markdown(self) -> str:
        tag = " *(Lens %s)*" % self.lens if self.lens else ""
        iv = "\n*Latency interval: %s*\n" % self._interval.label if self._interval else ""
        head = "| " + " | ".join(self.columns) + " |"
        sep = "|" + "|".join("---" for _ in self.columns) + "|"
        body = "\n".join("| " + " | ".join(c.text for c in row) + " |" for row in self.rows)
        return "### %s%s\n%s\n%s\n%s\n%s" % (self.title, tag, iv, head, sep, body)


def latency_cell(res: LatencyResult) -> Cell:
    text = "p95 %.0f ms (p50 %.0f, sigma %.0f, n=%d)" % (
        res.p95_ms, res.p50_ms, res.jitter_ms, res.n)
    if res.capture_path is not CapturePath.SDK_CALLBACK:
        text += " [%s +-%.0f ms]" % (res.capture_path.value,
                                     res.residual_bound_ms or 0)
    return Cell(text=text, lens=res.lens, interval=res.interval,
                capture_path=res.capture_path)


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


def coverage_statement(evaluated: Dict[str, str], unreachable: Dict[str, str],
                       requested_total: int) -> str:
    """Front-matter, not a limitations appendix: 'we evaluated N of the M
    products requested' is the first thing the reader must see, with any
    empty category named in the same breath. Takes {product: category} maps.
    """
    lines = ["## Coverage", ""]
    n, m = len(evaluated), requested_total
    lines.append("**This report evaluates %d of the %d products requested.**" % (n, m))
    if unreachable:
        for product, why in sorted(unreachable.items()):
            lines.append("- **%s** was not evaluated: %s" % (product, why))
        evaluated_cats = set(evaluated.values())
        # A category with nothing reachable is a headline fact, not a footnote.
        missing_cats = {c for c in _requested_categories(unreachable)
                        if c not in evaluated_cats}
        for cat in sorted(missing_cats):
            lines.append("- **The %s category is empty**: no product in it was "
                         "reachable. No conclusions about this category appear "
                         "anywhere in this report." % cat.replace("_", " "))
    return "\n".join(lines)


def _requested_categories(unreachable: Dict[str, str]) -> set:
    from .routing import BY_KEY
    return {BY_KEY[p].category for p in unreachable if p in BY_KEY}


def lens_m_latency_section(floor, raw_p50s: Dict[str, float],
                           bridge: Optional[dict] = None) -> str:
    """The Lens M latency section - claims constrained to what survived the
    bridge cross-check.

    The echo floor FAILED as a subtractable baseline (echo runs on a CPU-only
    pod with software encode; its 1928 ms EXCEEDS the one GPU model's total
    round trip). So this section:
      - reports the floor as ITS OWN measurement with scope stated,
      - reports models as RAW Lens M figures (same substrate, comparable to
        each other and nothing else),
      - states platform dominance via the bridge (the one model with both
        legs), with its single-model caveat,
      - and explicitly says model-only figures are not recoverable.
    """
    lines = [
        "### Lens M latency: platform-dominated, model-only figures not recoverable",
        "",
        "**CPU-pipeline reference (echo): %.0f ms (95%% CI %.0f-%.0f, n=%d runs).**"
        % (floor.point_ms, floor.lo_ms, floor.hi_ms, floor.n_runs),
        "Scope: the cost of Reactor's session + transport + CPU software-encode "
        "pipeline. It is NOT a baseline for GPU-served products, whose hardware "
        "encode path differs - the bridge cross-check showed a GPU model's "
        "entire round trip below this figure.",
        "",
        "Raw Lens M figures (same substrate; comparable to each other only):",
        "",
    ]
    for product, p50 in sorted(raw_p50s.items()):
        lines.append("- **%s**: p50 %.0f ms [Lens M, raw]" % (product, p50))
    if bridge:
        lines += [
            "",
            "**Platform share, measured on the one dual-routed model (Xmax "
            "X2.0):** native %.0f ms vs via-Reactor %.0f ms - the platform "
            "accounts for ~%.0f%%%% of the Lens M figure (Reactor delta %.0f ms, "
            "n=%d runs). *Caveat: measured on one model at one load profile; "
            "transfer to other models is plausible but unverified.*"
            % (bridge["lens_p_native_p50_ms"], bridge["lens_m"]["p50_ms"],
               100.0 * bridge["reactor_delta_ms"] / bridge["lens_m"]["p50_ms"],
               bridge["reactor_delta_ms"], sum(1 for r in bridge["runs"]
                                               if r.get("n_lags"))),
        ]
    lines += ["", "Model-only latency figures for products without a native "
              "route are **not recoverable** from these measurements and are "
              "not reported."]
    return "\n".join(lines)


def reliability_table(title: str, rates: Dict[str, Rate]) -> Table:
    """Reliability is lens-free in presentation but each rate keeps its N and
    CI; separability is stated pairwise, never implied."""
    t = Table(title, lens=None, columns=["Product", "Clean success (95% CI)", "N"])
    for product, rate in sorted(rates.items()):
        t.add_row([Cell(product), Cell("%.1f%% (%.1f-%.1f%%)"
                                       % (rate.point * 100, rate.lo * 100, rate.hi * 100)),
                   Cell(str(rate.n))])
    return t


# Below this CI gap (in probability), a separability claim is one or two runs
# from flipping and must not carry weight in the executive summary.
KNIFE_EDGE_MARGIN = 0.005


def separability_notes(rates: Dict[str, Rate]) -> List[str]:
    """One sentence per pair, from the CI rule and nothing else.

    Separable pairs state their margin; a knife-edge margin (the 99%-vs-95%
    at N=300 case: intervals disjoint by ~0.15 pp, two runs either way flips
    it) is flagged inline so the summary cannot quietly lean on it.
    """
    notes = []
    items = sorted(rates.items())
    for i, (pa, ra) in enumerate(items):
        for pb, rb in items[i + 1:]:
            if ra.separable_from(rb):
                hi, lo = (ra, rb) if ra.point > rb.point else (rb, ra)
                better = pa if ra.point > rb.point else pb
                margin = hi.lo - lo.hi
                note = ("%s vs %s: intervals do not overlap (margin %.2f pp) - "
                        "%s is more reliable at this sample size."
                        % (pa, pb, margin * 100, better))
                if margin < KNIFE_EDGE_MARGIN:
                    note += (" KNIFE-EDGE: a shift of one or two runs flips "
                             "this; report it, but do not lean on it in the "
                             "executive summary.")
                notes.append(note)
            else:
                notes.append("%s vs %s: no reliability difference detectable at "
                             "this sample size." % (pa, pb))
    return notes


class ProductCard(NamedTuple):
    """Declared spec facts live here - and only here. Resolution and fps never
    enter aesthetic scores: rating clips are normalized to one display size,
    and the reader weighs 540p against 1080p with the facts in front of them
    rather than a rater doing it unconsciously as 'composition'."""

    product: str
    lens: str
    declared_resolution: str  # e.g. "960p"
    declared_fps: float
    resolved_version: str
    input_conform_id: Optional[str] = None
    # When the eval exercises a SUBSET of the product's interaction surface
    # (LingBot: text-directed mode only, movement/camera unexercised), the
    # reader learns it here - on the card - not in an evidence JSON.
    scope_note: Optional[str] = None

    def markdown(self) -> str:
        conform = (" | input conform `%s`" % self.input_conform_id
                   if self.input_conform_id else "")
        md = ("**%s** *(Lens %s, `%s`)* - Declared: %s @ %g fps%s\n"
              "*Resolution and fps are reported facts; rating clips were "
              "normalized to a common display size and these do not enter "
              "aesthetic scores.*"
              % (self.product, self.lens, self.resolved_version,
                 self.declared_resolution, self.declared_fps, conform))
        if self.scope_note:
            md += "\n*Scope: %s*" % self.scope_note
        return md
