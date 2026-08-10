"""Per-run execution: wall-clock kill, retry policy, E-adjudication, run rows.

The retry rule, stated precisely because getting it backwards is the single
most damaging error available here:

  - Only rig-attributable failures are retried: confirmed E (positive rig
    evidence), or a transport error (which *might* be ours). Cap: 3 attempts
    total per slot.
  - F, T, and R are NEVER retried. Those are the measurement.
  - The ORIGINAL attempt's row stays in the record - and, unless it is
    confirmed E, in the reliability denominator - ALWAYS. The retry attempt is
    flagged is_retry and is EXCLUDED from the denominator, whatever its
    outcome. Retries exist to recover capture data for a slot, not to give the
    product a second chance at the statistics. Excluding the original and
    counting the retry launders product failures into successes.

E-adjudication, decided now rather than at 3 a.m.:

  - Automatic E requires POSITIVE evidence: control ping failed or health
    check failed within the run window. RigEvidence is the only input.
  - Ambiguous failures (transport error with a healthy rig) go to the review
    queue and count as PRODUCT failure unless a human adjudicates them to E.
    Defaulting the other way lets ambiguity quietly improve every product's
    reliability number.

Every row carries wall-clock UTC so the time-of-day confound is testable in
analysis instead of assumed away.
"""
import asyncio
import dataclasses
import json
import os
import time
from typing import Dict, List, Optional

from ..adapters.base import Adapter, StopReason, StreamResult
from ..classify import CaptureQuality, Classification, classify
from .health import RigEvidence
from .queue import RunSpec
from .spend import SpendCap, estimate_max_cost_usd

MAX_ATTEMPTS_PER_SLOT = 3  # addendum Part 8


@dataclasses.dataclass
class RunRow:
    """One attempt. Append-only; adjudication updates land as new journal
    records, never edits (runs.csv is derived, the journal is the truth)."""

    run_id: str
    attempt: int
    is_retry: bool
    product_key: str
    product_version: str
    lens: str
    campaign: str
    condition_id: str
    round_index: int
    timestamp_utc: str  # wall clock, for the time-of-day confound
    outcome: str  # S | D | F | T | R | E
    outcome_reasons: List[str]
    e_evidence: List[str]  # positive rig evidence, empty unless outcome E
    needs_review: bool  # ambiguous - in the review queue
    adjudicated: Optional[str] = None  # reviewer's outcome, if any
    stop_reason: str = ""
    ttff_ms: Optional[float] = None
    fps_delivered: Optional[float] = None
    n_frames: int = 0
    duration_intended_s: Optional[float] = None
    capture_path: Optional[str] = None
    clip_id: Optional[str] = None
    prompt_id: Optional[str] = None
    # Which deterministic conform produced this run's input (reel/conform.py).
    # Two rows with different conform ids are not pixel-identical inputs.
    input_conform_id: Optional[str] = None

    @property
    def effective_outcome(self) -> str:
        """Adjudication wins; otherwise the recorded outcome (which for
        ambiguous rows is already the default-to-product-failure one)."""
        return self.adjudicated or self.outcome


def _utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def resolve_outcome(cls: Classification, result: StreamResult,
                    rig: Optional[RigEvidence]) -> tuple:
    """(outcome, reasons, e_evidence, needs_review) - the adjudication rule.

    Positive rig evidence overrides everything except R: a refusal is a
    policy response that arrived intact, rig state notwithstanding.
    """
    if cls.outcome == "R":
        return "R", cls.reasons, [], False

    if rig is not None and rig.rig_failed:
        evidence = ["%s: %s" % (c.name, c.detail) for c in rig.failures()]
        return "E", ["rig failure within run window"] + cls.reasons, evidence, False

    if cls.outcome == "F" and result.stop_reason is StopReason.TRANSPORT_ERROR:
        # Could be ours, could be theirs, rig looked healthy: product failure
        # by default, human review may overturn to E.
        return "F", cls.reasons + ["ambiguous transport error - queued for review"], [], True

    return cls.outcome, cls.reasons, [], False


def should_retry(outcome: str, needs_review: bool, attempt: int) -> bool:
    """Rig-attributable only, capped. F/T/R never retry - they are the
    measurement. Ambiguous transport-F retries (to recover the slot's data)
    but its original row stands in the denominator regardless."""
    if attempt >= MAX_ATTEMPTS_PER_SLOT:
        return False
    return outcome == "E" or needs_review


class RunJournal:
    def __init__(self, path: str):
        self.path = path

    def append(self, row: RunRow) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "a") as f:
            f.write(json.dumps(dataclasses.asdict(row)) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def append_adjudication(self, run_id: str, attempt: int, outcome: str,
                            reviewer: str, note: str = "") -> None:
        with open(self.path, "a") as f:
            f.write(json.dumps({"adjudication": True, "run_id": run_id,
                                "attempt": attempt, "outcome": outcome,
                                "reviewer": reviewer, "note": note,
                                "timestamp_utc": _utcnow()}) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def load(self) -> List[RunRow]:
        rows: Dict[tuple, RunRow] = {}
        if not os.path.exists(self.path):
            return []
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec.get("adjudication"):
                    key = (rec["run_id"], rec["attempt"])
                    if key in rows:
                        rows[key].adjudicated = rec["outcome"]
                        rows[key].needs_review = False
                else:
                    row = RunRow(**{k: v for k, v in rec.items()})
                    rows[(row.run_id, row.attempt)] = row
        return list(rows.values())


def reliability_denominator(rows: List[RunRow]) -> List[RunRow]:
    """THE rule, in one place: original attempts only (never retries),
    excluding confirmed E. Ambiguous unadjudicated rows are in - as product
    failures - because their recorded outcome already defaults to F."""
    return [r for r in rows if not r.is_retry and r.effective_outcome != "E"]


def tally(rows: List[RunRow]) -> Dict[str, int]:
    """Outcome counts over the correct denominator, ready for stats.wilson."""
    denom = reliability_denominator(rows)
    counts = {"N": len(denom), "S": 0, "D": 0, "F": 0, "T": 0, "R": 0}
    for r in denom:
        counts[r.effective_outcome] += 1
    return counts


async def execute_slot(spec: RunSpec, adapter: Adapter, journal: RunJournal,
                       spend: SpendCap, usd_per_second: float,
                       wall_clock_kill_s: float,
                       preflight, postflight,
                       prompt: str, clip_path: Optional[str],
                       duration_intended_s: Optional[float],
                       capture_quality=None) -> List[RunRow]:
    """One queue slot: attempt, adjudicate, maybe retry. Returns all rows.

    The wall-clock kill is independent of the stall watchdog: it bounds the
    session in time even if frames keep trickling, which is what makes the
    spend reservation a true maximum.
    """
    rows: List[RunRow] = []
    attempt = 0
    while True:
        attempt += 1
        rig_before: RigEvidence = preflight()

        reservation_id = "%s#%d" % (spec.run_id, attempt)
        spend.reserve(reservation_id, estimate_max_cost_usd(
            duration_intended_s, usd_per_second, wall_clock_kill_s))

        started_utc = _utcnow()
        try:
            info = await adapter.connect()
            try:
                result = await asyncio.wait_for(
                    adapter.run(clip_path, prompt, duration_intended_s,
                                spec.condition_id),
                    timeout=wall_clock_kill_s)
            finally:
                await adapter.close()
            actual_s = min(result.stop_clock - result.request_clock, wall_clock_kill_s)
        except asyncio.TimeoutError:
            await adapter.close()
            spend.reconcile(reservation_id, wall_clock_kill_s * usd_per_second)
            rig_after = postflight()
            # A wall-clock kill is a hang - a PRODUCT failure, not an ambiguous
            # transport error. It is only E if the rig positively failed; it is
            # never queued for review and never retried (F is the measurement).
            rig = _merge(rig_before, rig_after)
            if rig.rig_failed:
                outcome, reasons, review = "E", ["rig failure within run window"], False
                evidence = ["%s: %s" % (c.name, c.detail) for c in rig.failures()]
            else:
                outcome, review, evidence = "F", False, []
                reasons = ["hung: wall-clock kill at %.0f s" % wall_clock_kill_s]
            row = _row(spec, attempt, outcome, reasons, evidence, review,
                       started_utc, version="(unresolved)", lens=adapter.lens,
                       stop_reason="wall_clock_kill",
                       duration_intended_s=duration_intended_s)
            journal.append(row)
            rows.append(row)
            if should_retry(outcome, review, attempt):
                continue
            return rows

        spend.reconcile(reservation_id, actual_s * usd_per_second)
        rig_after = postflight()

        cq = capture_quality(result) if capture_quality else None
        cls = classify(result, cq)
        outcome, reasons, evidence, review = resolve_outcome(
            cls, result, _merge(rig_before, rig_after))

        from ..adapters.base import delivered_fps, ttff_ms
        row = _row(spec, attempt, outcome, reasons, evidence, review,
                   started_utc, version=info.resolved_version, lens=info.lens,
                   stop_reason=result.stop_reason.value,
                   ttff=ttff_ms(result), fps=delivered_fps(result.events),
                   n_frames=len(result.events),
                   duration_intended_s=duration_intended_s,
                   capture_path=result.capture_path)
        journal.append(row)
        rows.append(row)

        if should_retry(outcome, review, attempt):
            continue
        return rows


def _row(spec: RunSpec, attempt: int, outcome, reasons, evidence, review,
         started_utc, version, lens, stop_reason, ttff=None, fps=None,
         n_frames=0, duration_intended_s=None, capture_path=None) -> RunRow:
    return RunRow(run_id=spec.run_id, attempt=attempt, is_retry=attempt > 1,
                  product_key=spec.product_key, product_version=version,
                  lens=lens, campaign=spec.campaign,
                  condition_id=spec.condition_id, round_index=spec.round_index,
                  timestamp_utc=started_utc, outcome=outcome,
                  outcome_reasons=reasons, e_evidence=evidence,
                  needs_review=review, stop_reason=stop_reason, ttff_ms=ttff,
                  fps_delivered=fps, n_frames=n_frames,
                  duration_intended_s=duration_intended_s,
                  capture_path=capture_path, clip_id=spec.clip_id,
                  prompt_id=spec.prompt_id)


def _merge(a: RigEvidence, b: RigEvidence) -> RigEvidence:
    return RigEvidence(checks=list(a.checks) + list(b.checks))
