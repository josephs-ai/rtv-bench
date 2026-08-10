"""The pilot gate: Campaign C cannot dispatch until the pilot's evidence exists.

Spec Part I lists the calibration steps; this module makes them a GATE rather
than a checklist - the same enforcement posture as the lens rule and the
denominator rule. Each requirement names the evidence file it expects under
data/ and validates its content, not just its existence.

Requirements:

  encoder_contamination   data/encoder-contamination.json (the CRF-12 vs FFV1
                          LPIPS check). Campaign C's capture CRF is DECIDED by
                          its verdict, so the evidence must exist before the
                          first quality capture, not alongside it.
  method_crosscheck       data/method-crosscheck.json - impulse vs block strip
                          on unstyled pilot clips. Agreement there is what
                          licenses the impulse method on styled clips.
  band_separation         data/band-separation.json - the C.1 latency bands
                          actually separate the field.
  rater_agreement         data/rater-trial.json - anchored descriptors reach
                          alpha >= 0.67 on the 3-clip trial.
"""
import json
import os
from typing import Callable, Dict, List, NamedTuple, Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

CROSSCHECK_MAX_DISAGREEMENT_MS = 17.0  # ~1 frame at 60 fps
RATER_TRIAL_MIN_ALPHA = 0.67  # Spec Part I.3


class GateResult(NamedTuple):
    passed: bool
    blockers: List[str]
    evidence: Dict[str, dict]
    warnings: List[str] = []

    def __str__(self) -> str:
        w = "".join("\n  ! %s" % x for x in self.warnings)
        if self.passed:
            return "pilot gate PASSED (%d evidence files)%s" % (len(self.evidence), w)
        return "pilot gate BLOCKED:\n" + "\n".join("  - %s" % b for b in self.blockers) + w


class GateError(RuntimeError):
    pass


def _load(name: str, data_dir: str) -> Optional[dict]:
    path = os.path.join(data_dir, name)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def _check_encoder(doc: Optional[dict]) -> Optional[str]:
    if doc is None:
        return ("encoder-contamination.json missing - run "
                "tools/encoder_contamination.py on 3-4 pilot clips; Campaign C's "
                "capture CRF depends on its verdict")
    if doc.get("verdict") not in ("crf12_safe", "lossless_required"):
        return "encoder-contamination.json has no usable verdict: %r" % doc.get("verdict")
    return None


def _check_crosscheck(doc: Optional[dict]) -> Optional[str]:
    if doc is None:
        return ("method-crosscheck.json missing - run impulse and block strip on "
                "the unstyled pilot captures; agreement is what licenses impulse "
                "on styled clips")
    worst = doc.get("worst_abs_disagreement_ms")
    if worst is None:
        return "method-crosscheck.json lacks worst_abs_disagreement_ms"
    if worst > CROSSCHECK_MAX_DISAGREEMENT_MS:
        return ("impulse vs strip disagree by %.1f ms (> %.1f) on unstyled clips - "
                "neither latency method is validated; investigate before any "
                "styled measurement" % (worst, CROSSCHECK_MAX_DISAGREEMENT_MS))
    return None


def _check_bands(doc: Optional[dict]) -> Optional[str]:
    if doc is None:
        return "band-separation.json missing - run all reachable products at C0"
    bands = doc.get("bands_occupied")
    if not isinstance(bands, int) or bands < 2:
        return ("latency bands do not separate the field (bands_occupied=%r) - "
                "rewrite the C.1 bands, they carry no information as-is" % bands)
    return None


def _check_raters(doc: Optional[dict]) -> Optional[str]:
    if doc is None:
        return "rater-trial.json missing - run the 3-clip anchored-descriptor trial"
    alpha = doc.get("alpha")
    if not isinstance(alpha, (int, float)):
        return "rater-trial.json lacks alpha"
    if alpha < RATER_TRIAL_MIN_ALPHA:
        return ("rater trial alpha %.2f < %.2f - the descriptors are ambiguous; "
                "rewrite them before spending the real budget" % (alpha, RATER_TRIAL_MIN_ALPHA))
    return None


def _check_contracts(doc: Optional[dict]) -> Optional[str]:
    """Each generation product's interaction contract confirmed by a real
    probe (capability.probe_record), not assumed. G1-G7 presume text
    direction; running a movement-driven model through them unprobed scores
    measurement error as product failure."""
    if doc is None:
        return ("interaction-contracts.json missing - probe what each "
                "generation product actually accepts (text direction? G7 "
                "mid-stream steer?) before any Campaign C generation run")
    probes = doc.get("probes")
    if not probes:
        return "interaction-contracts.json has no probes"
    # Compare the probe's finding against CURRENT routing - routing is the
    # living truth and is expected to be updated when a probe surprises us
    # (the probe file keeps declared_contract as the historical record of
    # what was believed at probe time).
    from . import routing
    mismatched = [p["product_key"] for p in probes
                  if p["product_key"] in routing.BY_KEY
                  and p.get("confirmed_contract")
                  != routing.BY_KEY[p["product_key"]].interaction_contract]
    if mismatched:
        return ("probed contract differs from routing.py for: %s - update "
                "routing (and the ranking groups) before Campaign C"
                % ", ".join(mismatched))
    return None


CHECKS: Dict[str, tuple] = {
    "encoder_contamination": ("encoder-contamination.json", _check_encoder),
    "method_crosscheck": ("method-crosscheck.json", _check_crosscheck),
    "band_separation": ("band-separation.json", _check_bands),
    "rater_agreement": ("rater-trial.json", _check_raters),
    "interaction_contracts": ("interaction-contracts.json", _check_contracts),
}


# Stages a human should have watched by eye before quality capture starts.
# Non-blocking - the point is that skipping eyes-on-video is a VISIBLE choice.
EYEBALL_STAGES_BEFORE_C = ("reel", "conform")


def _eyeball_warnings(data_dir: str) -> List[str]:
    path = os.path.join(data_dir, "eyeball-log.jsonl")
    seen = set()
    problems = []
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line)
                    seen.add(rec["stage"])
                    if rec.get("verdict") == "problem":
                        problems.append("eyeball log has an UNRESOLVED problem at "
                                        "stage %r: %s" % (rec["stage"], rec["notes"]))
    warnings = list(problems)
    for stage in EYEBALL_STAGES_BEFORE_C:
        if stage not in seen:
            warnings.append("no human has watched %r-stage video by eye "
                            "(tools/eyeball.py %s <dir>) - every number can be "
                            "internally consistent while the output is visibly "
                            "wrong" % (stage, stage))
    return warnings


def evaluate(data_dir: str = DATA_DIR) -> GateResult:
    blockers: List[str] = []
    evidence: Dict[str, dict] = {}
    for key, (fname, check) in CHECKS.items():
        doc = _load(fname, data_dir)
        problem = check(doc)
        if problem:
            blockers.append(problem)
        elif doc is not None:
            evidence[key] = doc
    return GateResult(passed=not blockers, blockers=blockers, evidence=evidence,
                      warnings=_eyeball_warnings(data_dir))


def require_for_campaign_c(data_dir: str = DATA_DIR) -> dict:
    """Call at Campaign C dispatch. Raises with the full blocker list, and
    returns the capture policy the evidence dictates."""
    result = evaluate(data_dir)
    if not result.passed:
        raise GateError(str(result))
    verdict = result.evidence["encoder_contamination"]["verdict"]
    return {
        "capture": "crf12" if verdict == "crf12_safe" else "ffv1_lossless",
        "evidence": {k: CHECKS[k][0] for k in result.evidence},
    }
