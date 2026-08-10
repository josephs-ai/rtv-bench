"""Validation of the three latency instruments against synthetic ground truth.

The point of the impulse method is that it survives restyling. That claim is
testable without any product access: apply an aggressive non-linear luminance
transform to a delayed copy of the input and check the recovered lag is still
right. This is the bench version of the pilot cross-check.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from PIL import Image

from rtveval.latency import blockstrip, digital_human, generation, impulse
from rtveval.latency.base import Interval, summarise
from rtveval.reel import overlay

FPS = 60.0
rng = np.random.default_rng(7)


def _synth_input(n_frames: int, flashes):
    """Slowly drifting scene luminance with hard flashes at known frames."""
    base = 110 + 12 * np.sin(np.arange(n_frames) / 40.0)
    base += rng.normal(0, 0.7, n_frames)
    for f in flashes:
        if f < n_frames:
            base[f] += overlay.FLASH_INTENSITY
    return base


def _restyle(x, gamma=2.2, scale=0.35, offset=45.0):
    """Stand-in for 'transform into an oil painting'.

    Compresses dynamic range hard, shifts the black level, applies a non-linear
    gamma, and adds texture noise. This is what kills a fixed-threshold marker.
    """
    norm = np.clip(x / 255.0, 0, 1) ** gamma
    return norm * 255.0 * scale + offset + rng.normal(0, 1.5, len(x))


def test_impulse_recovers_lag_unstyled():
    lag_frames, n = 9, 600
    flashes = overlay.flash_schedule(n, FPS, interval_ms=1000)
    inp = _synth_input(n, flashes)
    out = np.concatenate([np.full(lag_frames, inp[0]), inp[:-lag_frames]])

    samples = impulse.measure(inp, out, FPS, input_flash_frames=flashes)
    res = summarise(samples, lens="P")
    expected = lag_frames * 1000.0 / FPS
    assert abs(res.p50_ms - expected) < 8.0, (res.p50_ms, expected)
    assert res.n >= 8, res.n
    print("  unstyled: p50 %.1f ms (true %.1f), n=%d, jitter %.1f"
          % (res.p50_ms, expected, res.n, res.jitter_ms))


def test_impulse_survives_restyle():
    """The load-bearing claim: the same lag, through an aggressive restyle."""
    lag_frames, n = 14, 900
    flashes = overlay.flash_schedule(n, FPS, interval_ms=1000)
    inp = _synth_input(n, flashes)
    delayed = np.concatenate([np.full(lag_frames, inp[0]), inp[:-lag_frames]])
    out = _restyle(delayed)

    samples = impulse.measure(inp, out, FPS, input_flash_frames=flashes)
    res = summarise(samples, lens="P")
    expected = lag_frames * 1000.0 / FPS
    assert abs(res.p50_ms - expected) < 8.0, (res.p50_ms, expected)
    print("  restyled: p50 %.1f ms (true %.1f), n=%d, jitter %.1f"
          % (res.p50_ms, expected, res.n, res.jitter_ms))


def test_impulse_reports_low_confidence_when_no_signal():
    """No flashes in the output at all - must not invent a confident answer."""
    n = 400
    inp = _synth_input(n, overlay.flash_schedule(n, FPS))
    out = rng.normal(120, 3, n)  # unrelated noise
    samples = impulse.measure(inp, out, FPS,
                              input_flash_frames=overlay.flash_schedule(n, FPS))
    conf = max(s.confidence for s in samples)
    assert conf < 0.9, conf
    print("  no-signal: max confidence %.2f (correctly not certain)" % conf)


def test_blockstrip_roundtrips_clean():
    for idx, ok in overlay.verify_roundtrip():
        assert ok, idx
    print("  strip roundtrip: clean at all tested indices")


def test_blockstrip_survives_mild_grade_but_reports_hard_restyle():
    """Adaptive thresholding earns its keep on a mild grade; on a hard restyle
    the strip must return unreadable rather than a wrong index."""
    geom = overlay.default_geometry(1280, 720)
    img = Image.new("RGB", (1280, 720), (60, 80, 100))
    rendered = np.asarray(overlay.render_strip(img, 4242, geom, draw_digits=False))

    mild = np.clip(rendered.astype(np.float64) * 0.75 + 30, 0, 255).astype(np.uint8)
    got = blockstrip.decode(mild, geom)
    assert got.frame_index == 4242 and got.parity_ok, got
    print("  strip under mild grade: recovered %d" % got.frame_index)

    # Flatten the range below the reference-contrast floor.
    hard = np.clip(rendered.astype(np.float64) * 0.05 + 120, 0, 255).astype(np.uint8)
    got = blockstrip.decode(hard, geom)
    assert got.frame_index is None and not got.readable, got
    print("  strip under hard restyle: unreadable, reason=%r" % got.reason)


def test_generation_divergence():
    n, steer, lag_frames = 300, 150, 11
    d = rng.normal(4.0, 0.35, n)          # baseline rate of change
    d[steer + lag_frames:] += 9.0          # the steer lands
    got = generation.find_divergence(d, steer, FPS)
    expected = lag_frames * 1000.0 / FPS
    assert got.lag_ms is not None and abs(got.lag_ms - expected) < 40.0, got
    print("  generation: %.1f ms (true %.1f)" % (got.lag_ms, expected))


def test_generation_reports_ignored_steer():
    n, steer = 300, 150
    d = rng.normal(4.0, 0.35, n)  # nothing ever happens
    got = generation.find_divergence(d, steer, FPS)
    assert got.lag_ms is None, got
    print("  generation, steer ignored: %r" % got.reason)


def test_digital_human_audio_to_lip():
    sr, n_frames, lag_frames = 16000, 400, 7
    per_frame = int(sr / FPS)
    audio = rng.normal(0, 0.01, n_frames * per_frame)
    onsets_at = [60, 150, 240, 330]
    for f in onsets_at:  # plosive bursts
        audio[f * per_frame:(f + 3) * per_frame] += rng.normal(0, 0.9, 3 * per_frame)

    frames = [np.full((40, 60, 3), 100, dtype=np.uint8) for _ in range(n_frames)]
    for f in onsets_at:  # mouth opens `lag_frames` later
        for j in range(f + lag_frames, min(n_frames, f + lag_frames + 4)):
            frames[j] = np.full((40, 60, 3), 190, dtype=np.uint8)

    samples = digital_human.measure(frames, audio, sr, FPS,
                                    digital_human.ROI(0, 0, 60, 40))
    assert samples, "no audio/lip pairs found"
    res = summarise(samples, lens="P")
    expected = lag_frames * 1000.0 / FPS
    assert abs(res.p50_ms - expected) < 35.0, (res.p50_ms, expected)
    print("  digital human: p50 %.1f ms (true %.1f), n=%d" % (res.p50_ms, expected, res.n))


def test_summarise_refuses_to_mix_intervals():
    from rtveval.latency.base import LatencySample, Method
    mixed = [
        LatencySample(100.0, Interval.V2V_FRAME_TO_FRAME, Method.IMPULSE_XCORR, 1.0),
        LatencySample(100.0, Interval.GEN_SEND_TO_DIVERGENCE, Method.FRAME_DIVERGENCE, 1.0),
    ]
    try:
        summarise(mixed, lens="P")
    except ValueError as e:
        print("  mixing intervals correctly refused: %s" % e)
        return
    raise AssertionError("summarise() allowed two intervals in one result")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        print("%s" % t.__name__)
        try:
            t()
        except Exception as e:
            failed += 1
            print("  FAIL: %s: %s" % (type(e).__name__, e))
    print("\n%d/%d passed" % (len(tests) - failed, len(tests)))
    sys.exit(1 if failed else 0)
