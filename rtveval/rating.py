"""Blind rating sessions: blinding, seeded order, resume, and the 45-minute cap.

Threat model is friendly but real: the raters are colleagues, and at least one
will look. So product identity is kept out of everything the rater's machine
touches - filenames, manifest, DOM, network tab:

  - Clip names are HMAC-SHA256(secret, product|run) truncated - unguessable
    without the secret, stable across sessions.
  - The blinding key (blind_id -> product) lives in a separate file OUTSIDE
    the session directory; nothing served ever contains a product string.
    `audit_no_leaks()` greps the whole served tree for product identifiers and
    is run before every session.
  - All rating clips are re-encoded to ONE display size and codec before
    blinding: output resolution both leaks identity and is itself a quality
    confound (raters score sharpness as "composition"). Resolution/fps are
    reported as declared spec facts in the product cards instead - the reader
    weighs 540p against 1080p; the rater never gets the chance to do it
    unconsciously.

Sessions are seeded per rater (seed logged in the plan), journalled per score
(resume = replay), and capped at 45 minutes from first score - a fatigued
rater's scores are noise, and the cap is enforced by the journal clock rather
than by discipline.
"""
import hashlib
import hmac
import json
import os
import random
import subprocess
import time
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

SESSION_CAP_MIN = 45.0
NORMALIZE_ARGS = ("-c:v", "libx264", "-crf", "18", "-preset", "medium",
                  "-pix_fmt", "yuv420p", "-fps_mode", "cfr", "-an")


class RatingItem(NamedTuple):
    product_key: str
    run_id: str
    capture_path: str
    clip_id: str


class BlindClip(NamedTuple):
    blind_id: str
    path: str
    clip_id: str  # clip content id is NOT identity-leaking; raters may know V10


def blind_id(secret: bytes, product_key: str, run_id: str) -> str:
    return hmac.new(secret, ("%s|%s" % (product_key, run_id)).encode(),
                    hashlib.sha256).hexdigest()[:12]


def normalize_and_blind(items: Sequence[RatingItem], secret: bytes,
                        out_dir: str, key_path: str,
                        display: Tuple[int, int] = (1920, 1080),
                        runner=subprocess.run) -> List[BlindClip]:
    """Re-encode every clip to one display size + codec under a blinded name.

    `key_path` (the blind_id -> product mapping) MUST be outside `out_dir`;
    refused otherwise - the mapping must never sit in the served tree.
    """
    if os.path.commonpath([os.path.abspath(key_path), os.path.abspath(out_dir)]) \
            == os.path.abspath(out_dir):
        raise ValueError("blinding key inside the served directory")

    os.makedirs(out_dir, exist_ok=True)
    w, h = display
    # scale to fit + pad to canvas: aspect preserved, size identical, no crop.
    vf = ("scale=%d:%d:force_original_aspect_ratio=decrease:flags=lanczos,"
          "pad=%d:%d:(ow-iw)/2:(oh-ih)/2" % (w, h, w, h))

    clips, key = [], {}
    for item in items:
        bid = blind_id(secret, item.product_key, item.run_id)
        out = os.path.join(out_dir, bid + ".mp4")
        runner(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", item.capture_path, "-vf", vf, *NORMALIZE_ARGS, out],
               check=True)
        clips.append(BlindClip(bid, out, item.clip_id))
        key[bid] = {"product_key": item.product_key, "run_id": item.run_id}

    with open(key_path, "w") as f:
        json.dump({"display": list(display), "normalize_args": NORMALIZE_ARGS,
                   "key": key}, f, indent=2)
    return clips


def audit_no_leaks(out_dir: str, product_keys: Sequence[str]) -> List[str]:
    """Grep the served tree for product identifiers. Run before every session.
    Returns violations; empty list = clean."""
    tokens = set()
    for k in product_keys:
        tokens.add(k.lower())
        tokens.update(part for part in k.lower().replace("_", "-").split("-")
                      if len(part) > 3 and not part.replace(".", "").isdigit())
    violations = []
    for root, _, files in os.walk(out_dir):
        for name in files:
            path = os.path.join(root, name)
            low_name = name.lower()
            for t in tokens:
                if t in low_name:
                    violations.append("filename %s contains %r" % (name, t))
            if name.endswith((".json", ".html", ".txt", ".csv", ".js")):
                with open(path, "r", errors="replace") as f:
                    content = f.read().lower()
                for t in tokens:
                    if t in content:
                        violations.append("%s content contains %r" % (name, t))
    return violations


class Presentation(NamedTuple):
    order_index: int
    blind_id: str
    is_hidden_repeat: bool


class SessionPlan(NamedTuple):
    rater_id: str
    seed: int  # logged - the whole point
    presentations: List[Presentation]


def session_plan(rater_id: str, seed: int, clips: Sequence[BlindClip],
                 hidden_repeats: int = 1) -> SessionPlan:
    """Deterministic per-rater order: Random(f'{seed}:{rater_id}'). Hidden
    repeats are drawn deterministically and re-inserted in the second half so
    intra-rater consistency is measured at distance, not adjacency."""
    rng = random.Random("%d:%s" % (seed, rater_id))
    order = list(clips)
    rng.shuffle(order)

    pres = [Presentation(i, c.blind_id, False) for i, c in enumerate(order)]
    n = len(pres)
    for _ in range(min(hidden_repeats, n)):
        victim = rng.choice(pres[: max(1, n // 2)])
        slot = rng.randrange(max(1, n // 2), n)
        pres.insert(slot, Presentation(-1, victim.blind_id, True))
    pres = [Presentation(i, p.blind_id, p.is_hidden_repeat)
            for i, p in enumerate(pres)]
    return SessionPlan(rater_id, seed, pres)


class SessionClosed(RuntimeError):
    pass


class SessionJournal:
    """Append-only scores; resume and the 45-minute cap both derive from it."""

    def __init__(self, path: str):
        self.path = path

    def _load(self) -> List[dict]:
        if not os.path.exists(self.path):
            return []
        with open(self.path) as f:
            return [json.loads(l) for l in f if l.strip()]

    def elapsed_min(self, now: Optional[float] = None) -> float:
        recs = self._load()
        if not recs:
            return 0.0
        return ((now if now is not None else time.time()) - recs[0]["t"]) / 60.0

    def record(self, rater_id: str, presentation: Presentation, dimension: str,
               score: int, now: Optional[float] = None) -> None:
        t = now if now is not None else time.time()
        if self.elapsed_min(t) > SESSION_CAP_MIN:
            raise SessionClosed(
                "session exceeded %.0f min - fatigued scores are noise; "
                "resume in a fresh session" % SESSION_CAP_MIN)
        if not 1 <= score <= 5:
            raise ValueError("score %r outside 1-5" % score)
        rec = {"t": t, "rater_id": rater_id,
               "order_index": presentation.order_index,
               "blind_id": presentation.blind_id,
               "is_hidden_repeat": presentation.is_hidden_repeat,
               "dimension": dimension, "score": score}
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "a") as f:
            f.write(json.dumps(rec) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def completed(self, dimension: str) -> set:
        return {r["order_index"] for r in self._load()
                if r["dimension"] == dimension}

    def next_pending(self, plan: SessionPlan, dimension: str
                     ) -> Optional[Presentation]:
        done = self.completed(dimension)
        for p in plan.presentations:
            if p.order_index not in done:
                return p
        return None
