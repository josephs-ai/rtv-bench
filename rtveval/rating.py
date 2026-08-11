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
                        crop_margin: float = 0.0,
                        runner=subprocess.run) -> List[BlindClip]:
    """Re-encode every clip to one display size + codec under a blinded name.

    `key_path` (the blind_id -> product mapping) MUST be outside `out_dir`;
    refused otherwise - the mapping must never sit in the served tree.

    `crop_margin` crops that fraction off EVERY edge before scaling. Found
    live 2026-08-11: at least one provider stamps a moving "AI generated"
    watermark near the frame edge - a naked provider label that defeats
    blinding. Campaign rating runs use ~0.07; the margin is identical for
    every product (uniform treatment), recorded in the key file, and a
    watermark that wanders INTO the interior still requires the eyeball
    audit to catch - cropping is mitigation, not proof.
    """
    if os.path.commonpath([os.path.abspath(key_path), os.path.abspath(out_dir)]) \
            == os.path.abspath(out_dir):
        raise ValueError("blinding key inside the served directory")

    os.makedirs(out_dir, exist_ok=True)
    w, h = display
    # optional uniform edge crop (watermark margin), then scale to fit + pad:
    # aspect preserved, size identical for every product.
    vf = ("scale=%d:%d:force_original_aspect_ratio=decrease:flags=lanczos,"
          "pad=%d:%d:(ow-iw)/2:(oh-ih)/2" % (w, h, w, h))
    if crop_margin > 0:
        if not 0 < crop_margin < 0.25:
            raise ValueError("crop_margin out of sane range")
        vf = ("crop=iw*%.4f:ih*%.4f:(iw-ow)/2:(ih-oh)/2,"
              % (1 - 2 * crop_margin, 1 - 2 * crop_margin)) + vf

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
                   "crop_margin": crop_margin, "key": key}, f, indent=2)
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

class PairPresentation(NamedTuple):
    order_index: int
    left_blind_id: str
    right_blind_id: str
    # Which side each product landed on is logged so side bias is checkable
    # afterward: if raters favour a side, that is a finding about the tool.
    side_seed: int


def pair_plan(rater_id: str, shuffle_seed: int, side_seed: int,
              pairs: Sequence[Tuple[str, str]]) -> List[PairPresentation]:
    """Pairwise session plan with per-pair side randomization.

    Two INDEPENDENT random streams by design:
      - shuffle_seed orders the pairs (shared shape with session_plan);
      - side_seed decides left/right per pair, independently - so re-seeding
        the shuffle never silently changes side assignments, and the side
        stream can be audited on its own.
    Both seeds are logged in every presentation row.
    """
    order_rng = random.Random("%d:%s:pairs" % (shuffle_seed, rater_id))

    ordered = list(pairs)
    order_rng.shuffle(ordered)
    out = []
    for i, (a, b) in enumerate(ordered):
        # Side is a pure function of (side_seed, rater, THE PAIR) - never of
        # its position. A sequential side stream over shuffled order would
        # couple the two seeds: reshuffling silently reassigns sides. (Caught
        # by test before it could bias anything.)
        pair_rng = random.Random("%d:%s:%s" % (side_seed, rater_id,
                                               "|".join(sorted((a, b)))))
        left, right = (a, b) if pair_rng.random() < 0.5 else (b, a)
        out.append(PairPresentation(i, left, right, side_seed))
    return out


def side_bias(records: Sequence[dict]) -> dict:
    """Post-session check: wins by side, with the Wilson interval. A CI that
    excludes 0.5 is a tool finding, reported before any product conclusion."""
    from .stats import wilson

    left_wins = sum(1 for r in records if r.get("winner_side") == "left")
    decided = sum(1 for r in records if r.get("winner_side") in ("left", "right"))
    if decided == 0:
        return {"decided": 0}
    rate = wilson(left_wins, decided)
    biased = rate.hi < 0.5 or rate.lo > 0.5
    return {"decided": decided, "left_wins": left_wins,
            "left_rate": round(rate.point, 3),
            "ci95": [round(rate.lo, 3), round(rate.hi, 3)],
            "side_bias_detected": biased}


PAIR_VIEWER_HTML = """<!doctype html>
<meta charset="utf-8">
<title>pairwise</title>
<style>
 body{font-family:system-ui;margin:1rem;background:#111;color:#eee}
 .row{display:flex;gap:8px}.row video{width:49%%;background:#000}
 .bar{margin:12px 0;display:flex;gap:12px;align-items:center}
 button{font-size:1.1rem;padding:8px 20px}
 #seek{flex:1}
</style>
<h3 id="title"></h3>
<div class="row">
  <video id="L" muted preload="auto"></video>
  <video id="R" muted preload="auto"></video>
</div>
<div class="bar">
  <button id="play">play</button>
  <input type="range" id="seek" min="0" max="1000" value="0">
  <span id="t">0.0s</span>
</div>
<div class="bar">
  <button data-w="left">LEFT is better</button>
  <button data-w="tie">no preference</button>
  <button data-w="right">RIGHT is better</button>
</div>
<script>
// SYNCHRONIZED playback: one transport drives both videos. Two independent
// players would let raters compare different moments, turning temporal-
// coherence judgments into noise. L is the clock; R chases it.
const plan = %(plan_json)s;
let idx = 0, records = [];
const L = document.getElementById('L'), R = document.getElementById('R');
const play = document.getElementById('play'), seek = document.getElementById('seek');
function load() {
  const p = plan[idx];
  document.getElementById('title').textContent = 'pair ' + (idx+1) + ' / ' + plan.length;
  L.src = p.left_blind_id + '.mp4'; R.src = p.right_blind_id + '.mp4';
  L.currentTime = 0; R.currentTime = 0;
}
function syncR() { if (Math.abs(R.currentTime - L.currentTime) > 0.05) R.currentTime = L.currentTime; }
setInterval(() => { if (!L.paused) syncR(); }, 200);
play.onclick = () => { if (L.paused) { L.play(); R.play(); play.textContent='pause'; }
                       else { L.pause(); R.pause(); play.textContent='play'; } };
L.ontimeupdate = () => { seek.value = 1000 * L.currentTime / (L.duration || 1);
                         document.getElementById('t').textContent = L.currentTime.toFixed(1) + 's'; };
seek.oninput = () => { L.currentTime = seek.value / 1000 * (L.duration || 0); syncR(); };
document.querySelectorAll('[data-w]').forEach(b => b.onclick = () => {
  const p = plan[idx];
  records.push({order_index: p.order_index, left: p.left_blind_id,
                right: p.right_blind_id, winner_side: b.dataset.w,
                t: Date.now() / 1000});
  idx += 1;
  if (idx >= plan.length) { done(); } else { load(); }
});
function done() {
  document.body.innerHTML = '<h3>done - copy this into the journal:</h3><pre>' +
    JSON.stringify(records, null, 1) + '</pre>';
}
load();
</script>
"""


def write_pair_viewer(plan: Sequence[PairPresentation], out_dir: str) -> str:
    """Static pairwise viewer next to the blinded clips. No product name can
    appear here - the plan carries blind ids only (audit_no_leaks covers the
    whole served tree, this file included)."""
    doc = [p._asdict() for p in plan]
    html = PAIR_VIEWER_HTML % {"plan_json": json.dumps(doc)}
    path = os.path.join(out_dir, "pairwise.html")
    with open(path, "w") as f:
        f.write(html)
    return path
