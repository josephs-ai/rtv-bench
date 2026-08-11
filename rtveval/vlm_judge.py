"""VLM judge: Layer-1 AUXILIARY scoring of captures against the Part-E rubric.

Position in the methodology (agreed before build):
  - Auxiliary evidence only. Humans decide (Spec D.3); the judge NEVER
    overrides the human panel and its scores are reported in a separate,
    clearly-labelled column.
  - Same discipline as the human panel: blinded items (no product identity in
    anything the model sees or the journal records), seeded order, hidden
    repeats for self-consistency, and a validation gate - Krippendorff alpha
    against the human panel on the overlap set must clear 0.67 before judge
    scores are extended to clips humans did not rate.
  - Scores are anchored to the frozen rubric's OBSERVABLE criteria (Spec E),
    not the model's taste. The prompt is the rubric verbatim.

Architecture rule (same as quality_metrics): everything except the actual
API call is pure and tested without network. `ClaudeJudge` is the one class
that talks to the Claude API and it is injected wherever it is consumed.
"""
import hashlib
import json
import random
import time
from typing import Dict, List, NamedTuple, Optional, Sequence

from .rating import blind_id
from .stats import krippendorff_alpha

# ---------------------------------------------------------------------------
# Rubric dimensions (Spec Part E, verbatim anchors)
# ---------------------------------------------------------------------------


class Dimension(NamedTuple):
    dim_id: str
    name: str
    weight: float
    anchors: Dict[int, str]  # score -> observable criterion, from the spec
    needs_prompt: bool = False  # scored against the written prompt intent


V2V_DIMENSIONS = [
    Dimension("E1", "Temporal coherence", 0.30, {
        5: "No visible flicker, crawl, or boiling on any surface; identity and style stable end to end.",
        4: "Artifacts detectable only when frame-stepping. Nothing visible at normal playback. No drift.",
        3: "Flicker or texture crawl visible on flat regions or hair. Mild style drift but subject remains recognisably the same.",
        2: "Persistent boiling or crawl across large areas. Identity or style noticeably shifts within the clip.",
        1: "Output unstable frame to frame; subject partially re-forms between frames."}),
    Dimension("E2", "Structural fidelity", 0.20, {
        5: "Anatomy, hands, and background geometry correct throughout. Held text/logo remains legible.",
        4: "One minor geometric error, self-correcting within ~5 frames.",
        3: "Recurring minor errors, or held text becomes illegible while remaining text-like.",
        2: "Persistent anatomical errors, or background architecture bends.",
        1: "Geometry unreliable; subject anatomy incoherent."}),
    Dimension("E3", "Style adherence", 0.15, {
        5: "All specified style attributes present and correctly applied.",
        4: "All attributes present; one applied weakly.",
        3: "Recognisably the requested style, but at least one specified attribute missing or misapplied.",
        2: "Generic transformation only loosely matching intent.",
        1: "Style not applied, or unrelated to the request."}, needs_prompt=True),
    Dimension("E4", "Detail retention vs hallucination", 0.15, {
        5: "Fine texture (hair strands, fabric weave) preserved and traceable to source.",
        4: "Texture preserved in structure, slightly smoothed.",
        3: "Texture plausibly re-synthesised but no longer matches source detail.",
        2: "Detail regions smoothed flat, or replaced with invented texture.",
        1: "Detail destroyed or replaced with unrelated content."}),
]

GENERATION_DIMENSIONS = [
    Dimension("E6", "Prompt adherence", 0.25, {
        5: "100% of the prompt's checkable assertions satisfied and held throughout.",
        4: "100% satisfied at some point; at least one lapses briefly.",
        3: "70-99% of assertions satisfied.",
        2: "40-69% satisfied.",
        1: "Under 40% satisfied."}, needs_prompt=True),
    Dimension("E7", "Physical plausibility", 0.20, {
        5: "Gravity, collisions, and object permanence all correct. Objects exiting and re-entering frame are unchanged.",
        4: "One minor violation (slight float, soft collision).",
        3: "Object permanence fails on re-entry, or repeated soft physics errors.",
        2: "Objects pass through each other, or appear/vanish without cause.",
        1: "No coherent physics."}),
    Dimension("E8", "Long-horizon consistency", 0.20, {
        5: "Late-clip scene identity, palette, and layout match the early state.",
        4: "Minor palette or lighting drift; layout and identity intact.",
        3: "Noticeable drift; still recognisably the same scene.",
        2: "Scene has substantially morphed; some original elements survive.",
        1: "Unrelated to the opening scene."}),
]

DIMENSION_SETS = {"v2v": V2V_DIMENSIONS, "generation": GENERATION_DIMENSIONS}


# ---------------------------------------------------------------------------
# Artifact audit mode: hunt AI-edit anomalies against a FIXED taxonomy
# ---------------------------------------------------------------------------

ARTIFACT_TAXONOMY = [
    ("identity_morph", "subject gradually becomes a different person/object"),
    ("boundary_halo", "halo, seam, or matte line around an edited subject"),
    ("texture_boiling", "surfaces churn or crawl between frames"),
    ("anatomy_error", "hands/fingers/limbs wrong in count or pose"),
    ("object_popping", "objects appear, vanish, or teleport without cause"),
    ("temporal_warp", "background or geometry bends/swims with motion"),
    ("style_flicker", "style strength pulses on and off"),
    ("text_gibberish", "signage or text rendered as garbled glyphs"),
    ("lighting_inconsistency", "shadows or lighting contradict the scene"),
    ("frozen_patch", "a region stops updating while the rest moves"),
]


def audit_schema() -> dict:
    ids = [t[0] for t in ARTIFACT_TAXONOMY]
    return {
        "type": "object",
        "properties": {
            "findings": {"type": "array", "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ids},
                    "frames": {"type": "string"},
                    "severity": {"type": "integer", "enum": [1, 2, 3]},
                    "description": {"type": "string"},
                },
                "required": ["type", "frames", "severity", "description"],
                "additionalProperties": False,
            }},
            "clean": {"type": "boolean"},
            "notes": {"type": "string"},
        },
        "required": ["findings", "clean", "notes"],
        "additionalProperties": False,
    }


def build_audit_prompt(n_frames: int, clip_seconds: float) -> str:
    lines = [
        "You are auditing a video produced or transformed by an AI video "
        "model, shown as %d frames sampled evenly across %.0f seconds in "
        "temporal order. You do not know which product made it."
        % (n_frames, clip_seconds),
        "Hunt ONLY for the artifact classes listed below. For each one you "
        "actually observe, report the frame numbers, a severity (1 subtle - "
        "visible when looking for it; 2 clear - a viewer would notice; "
        "3 severe - breaks the content), and a concrete description.",
        "Report NOTHING outside this taxonomy. If the sampled frames show "
        "none of these, return an empty findings list with clean=true - an "
        "empty audit of a clean clip is the correct answer, not a failure "
        "to find something.",
        "Frame-sampling caveat: per-frame flicker is not observable at this "
        "sampling rate - only report classes whose evidence is visible in "
        "the frames you were given.",
        "",
        "Artifact classes:",
    ]
    for aid, desc in ARTIFACT_TAXONOMY:
        lines.append("  %s: %s" % (aid, desc))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pure logic: frame sampling, blinded plan with hidden repeats, gates
# ---------------------------------------------------------------------------


def sample_frame_indices(n_frames: int, k: int) -> List[int]:
    """Deterministic even coverage including first and last frame. The judge
    sees the SAME frames a re-run would - no sampling randomness to launder
    disagreement through."""
    if n_frames <= 0 or k <= 0:
        return []
    if n_frames <= k:
        return list(range(n_frames))
    return sorted({round(i * (n_frames - 1) / (k - 1)) for i in range(k)})


class JudgeItem(NamedTuple):
    product_key: str
    run_id: str
    capture_path: str
    category: str                  # key into DIMENSION_SETS
    prompt_text: Optional[str]     # for needs_prompt dimensions


class PlannedJudgment(NamedTuple):
    blind_id: str
    item_index: int        # into the original items list (key file only)
    is_hidden_repeat: bool


def build_plan(items: Sequence[JudgeItem], secret: bytes, seed: int,
               hidden_repeat_every: int = 4) -> List[PlannedJudgment]:
    """Seeded order + hidden repeats. A repeat is re-blinded with a salt so
    nothing in the journal links the two presentations; matching them back up
    for the consistency stat requires the key file, exactly like the human
    panel. One repeat per `hidden_repeat_every` items, minimum one."""
    rng = random.Random(seed)
    order = list(range(len(items)))
    rng.shuffle(order)
    plan = [PlannedJudgment(
        blind_id(secret, items[i].product_key, items[i].run_id), i, False)
        for i in order]
    n_rep = max(1, len(items) // hidden_repeat_every) if items else 0
    for victim_pos in rng.sample(range(len(plan)), min(n_rep, len(plan))):
        v = plan[victim_pos]
        item = items[v.item_index]
        rep = PlannedJudgment(
            blind_id(secret, item.product_key, item.run_id + "|repeat"),
            v.item_index, True)
        plan.insert(rng.randrange(len(plan) + 1), rep)
    return plan


def judge_schema(dimensions: Sequence[Dimension]) -> dict:
    """Structured-output schema: per-dimension score + frame-cited evidence.
    `assessable` exists so the judge can decline a dimension the frames don't
    exercise instead of inventing a number."""
    dim_props = {}
    for d in dimensions:
        dim_props[d.dim_id] = {
            "type": "object",
            "properties": {
                "assessable": {"type": "boolean"},
                "score": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
                "evidence": {"type": "string"},
            },
            "required": ["assessable", "score", "evidence"],
            "additionalProperties": False,
        }
    return {
        "type": "object",
        "properties": {
            "dimensions": {"type": "object", "properties": dim_props,
                           "required": list(dim_props), "additionalProperties": False},
            "breakdown_observed": {"type": "boolean"},
            "notes": {"type": "string"},
        },
        "required": ["dimensions", "breakdown_observed", "notes"],
        "additionalProperties": False,
    }


def build_prompt(dimensions: Sequence[Dimension], n_frames: int,
                 clip_seconds: float, prompt_text: Optional[str]) -> str:
    """The instruction block. The rubric anchors go in verbatim; the judge is
    told what it does NOT know (product, source) and what to do when frames
    cannot support a judgment."""
    lines = [
        "You are scoring a video clip from a real-time video generation system "
        "against a frozen evaluation rubric. You are shown %d frames sampled "
        "evenly across a %.0f-second clip, in temporal order." % (n_frames, clip_seconds),
        "You do not know which product made this clip. Score only what is "
        "observable in these frames.",
        "",
        "For each dimension below, pick the ONE score whose observable "
        "criterion best matches the frames. Quote frame numbers as evidence. "
        "If the sampled frames genuinely cannot support a judgment on a "
        "dimension (e.g. no re-entry event occurs), set assessable=false and "
        "explain; do not guess.",
        "Frame-sampling caveat: flicker between adjacent frames is NOT "
        "observable at this sampling rate - never score temporal dimensions "
        "below 3 on suspicion alone; only on evidence visible across the "
        "sampled frames (identity/style/layout changes).",
        "",
    ]
    if prompt_text:
        lines += ["The generation prompt was:", "  \"%s\"" % prompt_text, ""]
    for d in dimensions:
        lines.append("%s - %s:" % (d.dim_id, d.name))
        for s in (5, 4, 3, 2, 1):
            lines.append("  %d: %s" % (s, d.anchors[s]))
        lines.append("")
    lines.append("Also report breakdown_observed=true if any frame shows the "
                 "output collapsing (dissolving geometry, colour field, frozen "
                 "corruption).")
    return "\n".join(lines)


class JudgmentRecord(NamedTuple):
    blind_id: str
    dim_id: str
    score: Optional[int]   # None when not assessable
    is_hidden_repeat: bool
    item_index: int


def self_consistency(records: Sequence[JudgmentRecord]) -> dict:
    """Max deviation between a hidden repeat and its original, per dimension.
    Same gate as the human panel: deviation > 1 point flags the judge as
    inconsistent on that dimension (Spec: intra-rater gate)."""
    base: Dict[tuple, int] = {}
    rep: Dict[tuple, int] = {}
    for r in records:
        if r.score is None:
            continue
        key = (r.item_index, r.dim_id)
        (rep if r.is_hidden_repeat else base)[key] = r.score
    devs = {k: abs(rep[k] - base[k]) for k in rep if k in base}
    if not devs:
        return {"n_pairs": 0, "max_deviation": None, "flagged": False}
    mx = max(devs.values())
    return {"n_pairs": len(devs), "max_deviation": mx, "flagged": mx > 1}


def validate_against_humans(vlm: Dict[tuple, int],
                            human_median: Dict[tuple, int]) -> dict:
    """The extension gate. Krippendorff alpha (ordinal) between the judge and
    the human panel median on the overlap set. Below 0.67 the judge is NOT
    extended beyond the overlap - reported as failed-validation, full stop."""
    overlap = sorted(set(vlm) & set(human_median))
    if len(overlap) < 5:
        return {"n_overlap": len(overlap), "alpha": None,
                "usable": False, "reason": "overlap too small (<5 items)"}
    matrix = [[vlm[k] for k in overlap], [human_median[k] for k in overlap]]
    agreement = krippendorff_alpha(matrix)  # Agreement(alpha, gate)
    usable = agreement.alpha >= 0.67
    return {"n_overlap": len(overlap), "alpha": agreement.alpha,
            "gate": agreement.gate, "usable": usable,
            "reason": None if usable
            else "alpha %.3f below 0.67 gate" % agreement.alpha}


# ---------------------------------------------------------------------------
# Pairwise (side-by-side) mode - parallel to the human forced-choice flow
# ---------------------------------------------------------------------------


def pair_side_swapped(side_seed: int, id_a: str, id_b: str) -> bool:
    """Side assignment as a PURE function of (side_seed, sorted pair) - the
    same rule as rating.pair_plan, and for the same reason: re-running or
    re-ordering the batch can never silently change which clip is 'A', and
    the side stream audits on its own. True = the sorted-second item goes
    first (A)."""
    lo, hi = sorted((id_a, id_b))
    h = hashlib.sha256(b"%d|%s|%s" % (side_seed, lo.encode(), hi.encode()))
    return h.digest()[0] % 2 == 1


def pair_schema(dimensions: Sequence[Dimension]) -> dict:
    """Forced choice per dimension. 'tie' allowed only with evidence - the
    Bradley-Terry feed drops ties, matching the human forced-choice rule."""
    dim_props = {}
    for d in dimensions:
        dim_props[d.dim_id] = {
            "type": "object",
            "properties": {
                "winner": {"type": "string", "enum": ["A", "B", "tie"]},
                "evidence": {"type": "string"},
            },
            "required": ["winner", "evidence"],
            "additionalProperties": False,
        }
    return {
        "type": "object",
        "properties": {
            "dimensions": {"type": "object", "properties": dim_props,
                           "required": list(dim_props), "additionalProperties": False},
            "notes": {"type": "string"},
        },
        "required": ["dimensions", "notes"],
        "additionalProperties": False,
    }


def build_pair_prompt(dimensions: Sequence[Dimension], n_frames: int,
                      prompt_a: Optional[str], prompt_b: Optional[str]) -> str:
    lines = [
        "You are comparing two video clips, A and B, from real-time video "
        "generation systems. Each is shown as %d frames sampled evenly in "
        "temporal order. You do not know which products made them; they may "
        "even be the same product twice." % n_frames,
        "For each dimension, choose which clip is BETTER on that dimension's "
        "criterion alone (not overall). Cite frame numbers from both clips as "
        "evidence. Choose 'tie' only when you can articulate why neither is "
        "distinguishably better.",
        "Frame-sampling caveat: per-frame flicker is not observable at this "
        "sampling rate; judge only what the sampled frames show.",
        "",
    ]
    if prompt_a:
        lines.append("Clip A's generation prompt: \"%s\"" % prompt_a)
    if prompt_b:
        lines.append("Clip B's generation prompt: \"%s\"" % prompt_b)
    lines.append("")
    for d in dimensions:
        lines.append("%s - %s: %s" % (d.dim_id, d.name, d.anchors[5]))
    return "\n".join(lines)


def unswap_winner(winner: str, swapped: bool) -> Optional[str]:
    """Map the judge's A/B verdict back to the sorted-first/second item.
    Returns 'first'/'second' (sorted order) or None for a tie."""
    if winner == "tie":
        return None
    if swapped:
        return "second" if winner == "A" else "first"
    return "first" if winner == "A" else "second"


# ---------------------------------------------------------------------------
# The one networked class
# ---------------------------------------------------------------------------


class JudgeRefusal(RuntimeError):
    pass


class ClaudeJudge:
    """Scores one blinded item per call. Frames go in as JPEG bytes; the
    response is schema-constrained so parsing cannot silently drift."""

    def __init__(self, model: str = "claude-opus-5", max_tokens: int = 16000):
        import anthropic  # lazy: core venv imports this module without the SDK
        self._anthropic = anthropic
        self.client = anthropic.Anthropic()
        self.model = model
        self.max_tokens = max_tokens

    def judge(self, frames_jpeg: Sequence[bytes], dimensions: Sequence[Dimension],
              clip_seconds: float, prompt_text: Optional[str]) -> dict:
        import base64
        content = []
        for i, jpg in enumerate(frames_jpeg):
            content.append({"type": "text", "text": "Frame %d:" % (i + 1)})
            content.append({"type": "image", "source": {
                "type": "base64", "media_type": "image/jpeg",
                "data": base64.standard_b64encode(jpg).decode()}})
        content.append({"type": "text", "text": build_prompt(
            dimensions, len(frames_jpeg), clip_seconds, prompt_text)})

        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            output_config={"format": {"type": "json_schema",
                                      "schema": judge_schema(dimensions)}},
            messages=[{"role": "user", "content": content}],
        )
        if response.stop_reason == "refusal":
            raise JudgeRefusal("judge request refused (category=%s)" % (
                response.stop_details.category if response.stop_details else None))
        text = next(b.text for b in response.content if b.type == "text")
        out = json.loads(text)
        out["_model"] = response.model
        out["_usage"] = {"in": response.usage.input_tokens,
                         "out": response.usage.output_tokens}
        return out

    def audit(self, frames_jpeg: Sequence[bytes], clip_seconds: float) -> dict:
        """Artifact audit: taxonomy-constrained anomaly findings."""
        import base64
        content = []
        for i, jpg in enumerate(frames_jpeg):
            content.append({"type": "text", "text": "Frame %d:" % (i + 1)})
            content.append({"type": "image", "source": {
                "type": "base64", "media_type": "image/jpeg",
                "data": base64.standard_b64encode(jpg).decode()}})
        content.append({"type": "text",
                        "text": build_audit_prompt(len(frames_jpeg), clip_seconds)})
        response = self.client.messages.create(
            model=self.model, max_tokens=self.max_tokens,
            output_config={"format": {"type": "json_schema",
                                      "schema": audit_schema()}},
            messages=[{"role": "user", "content": content}],
        )
        if response.stop_reason == "refusal":
            raise JudgeRefusal("audit refused")
        out = json.loads(next(b.text for b in response.content if b.type == "text"))
        out["_model"] = response.model
        return out

    def judge_pair(self, frames_a: Sequence[bytes], frames_b: Sequence[bytes],
                   dimensions: Sequence[Dimension],
                   prompt_a: Optional[str], prompt_b: Optional[str]) -> dict:
        """Side-by-side forced choice. Callers assign A/B via
        pair_side_swapped() and map back with unswap_winner()."""
        import base64

        def blocks(label, frames):
            out = []
            for i, jpg in enumerate(frames):
                out.append({"type": "text",
                            "text": "Clip %s, frame %d:" % (label, i + 1)})
                out.append({"type": "image", "source": {
                    "type": "base64", "media_type": "image/jpeg",
                    "data": base64.standard_b64encode(jpg).decode()}})
            return out

        content = blocks("A", frames_a) + blocks("B", frames_b)
        content.append({"type": "text", "text": build_pair_prompt(
            dimensions, len(frames_a), prompt_a, prompt_b)})
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            output_config={"format": {"type": "json_schema",
                                      "schema": pair_schema(dimensions)}},
            messages=[{"role": "user", "content": content}],
        )
        if response.stop_reason == "refusal":
            raise JudgeRefusal("pair judgment refused (category=%s)" % (
                response.stop_details.category if response.stop_details else None))
        text = next(b.text for b in response.content if b.type == "text")
        out = json.loads(text)
        out["_model"] = response.model
        out["_usage"] = {"in": response.usage.input_tokens,
                         "out": response.usage.output_tokens}
        return out


def journal_line(plan_entry: PlannedJudgment, result: dict) -> str:
    """One JSONL line per judgment. Blind id only - the item_index mapping
    lives in the key file, never here."""
    row = {"blind_id": plan_entry.blind_id,
           "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "result": {k: v for k, v in result.items() if not k.startswith("_")},
           "model": result.get("_model"), "usage": result.get("_usage")}
    return json.dumps(row, sort_keys=True)


def key_fingerprint(secret: bytes) -> str:
    return hashlib.sha256(secret).hexdigest()[:12]
