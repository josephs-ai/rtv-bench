"""AV lip-sync math against synthetic ground truth (no models, no network)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from rtveval.av_sync import (global_av_offset, measure, missed_closure_rate,
                             versus_anchors)
from rtveval.latency.digital_human import audio_envelope

FPS = 25.0
SR = 16000
rng = np.random.default_rng(11)


def _speech_audio(n_frames, onset_frames):
    """Quiet audio with plosive bursts at known video-frame positions."""
    per = SR // int(FPS)
    audio = rng.normal(0, 0.01, n_frames * per)
    for f in onset_frames:
        audio[f * per:(f + 2) * per] += rng.normal(0, 0.8, 2 * per)
    return audio


def _mouth_from_env(env, lag_frames, drop=()):
    """Mouth aperture tracking the audio envelope, delayed; optionally with
    some articulations destroyed (restyle failure)."""
    m = np.concatenate([np.full(lag_frames, env[0]), env[:len(env) - lag_frames]])
    m = m + rng.normal(0, 0.002, len(m))
    for f in drop:
        lo, hi = max(0, f + lag_frames - 8), min(len(m), f + lag_frames + 8)
        m[lo:hi] = m.mean()  # mouth stays neutral through this plosive
    return m


ONSETS = [40, 90, 140, 190, 240, 290, 340, 390]


def test_offset_recovered():
    audio = _speech_audio(450, ONSETS)
    env = audio_envelope(audio, SR, FPS)
    mouth = _mouth_from_env(env, lag_frames=4)
    off = global_av_offset(env, mouth, FPS)
    assert abs(off["offset_frames"] - 4) <= 1, off
    assert off["confidence"] > 4.0, off
    print("  offset: true 4 frames, recovered %d (conf %.1f)"
          % (off["offset_frames"], off["confidence"]))


def test_no_confident_offset_from_unrelated_mouth():
    audio = _speech_audio(450, ONSETS)
    env = audio_envelope(audio, SR, FPS)
    mouth = rng.normal(0.2, 0.05, 450)  # mouth unrelated to speech
    off = global_av_offset(env, mouth, FPS)
    assert off["confidence"] < 4.0, off
    print("  unrelated mouth: confidence %.1f (correctly not certain)"
          % off["confidence"])


def test_missed_closures_catch_destroyed_articulation():
    audio = _speech_audio(450, ONSETS)
    env = audio_envelope(audio, SR, FPS)
    good = _mouth_from_env(env, 2)
    ok = missed_closure_rate(env, good, FPS, offset_frames=2)
    assert ok["rate"] <= 0.2, ok
    bad = _mouth_from_env(env, 2, drop=ONSETS[::2])  # half the plosives dead
    br = missed_closure_rate(env, bad, FPS, offset_frames=2)
    assert br["rate"] >= 0.3, br
    print("  closures: intact %.0f%% missed; destroyed-articulation %.0f%%"
          % (ok["rate"] * 100, br["rate"] * 100))


def test_full_measure_and_anchor_framing():
    audio = _speech_audio(450, ONSETS)
    env = audio_envelope(audio, SR, FPS)
    product = measure(_mouth_from_env(env, 6), audio, SR, FPS)
    anchor0 = measure(_mouth_from_env(env, 1), audio, SR, FPS)   # capture chain
    anchorR = measure(_mouth_from_env(env, 0), audio, SR, FPS)   # real footage
    assert product is not None and anchor0 is not None
    vs = versus_anchors(product, anchor0, anchorR)
    assert 120 <= vs["added_offset_ms"] <= 280, vs  # ~5 frames at 25fps = 200ms
    assert "Anchor-0" in vs["note"]
    print("  anchors: product +%.0fms beyond capture chain; framing recorded"
          % vs["added_offset_ms"])


def test_short_or_empty_inputs_refuse():
    assert global_av_offset([1, 2], [1, 2], FPS) is None
    assert missed_closure_rate(np.zeros(50), np.zeros(50), FPS) is None
    print("  short/flat inputs: refused, not invented")


if __name__ == "__main__":
    for fn in [v for k, v in sorted(globals().items()) if k.startswith("test_")]:
        print(fn.__name__)
        fn()
    print("OK")
