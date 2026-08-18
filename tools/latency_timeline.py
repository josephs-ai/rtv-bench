#!/usr/bin/env python3
"""Closed-loop responsiveness over time - windowed motion-energy xcorr.

    .venv-metrics/bin/python tools/latency_timeline.py \
        --input data/reel/reel-master.mp4 --capture <run>.mkv [--window-s 30]

Where the single-number instruments (rtveval/latency/impulse.py) give one lag
per run, this tool asks whether that lag HOLDS: for each 30 s window the input
reel's motion-energy series (mean abs frame diff, per frame) is cross-
correlated against the capture's, and the per-window lag traces responsiveness
across the session. A product at 300 ms that creeps to 900 ms over a 5 min
take is a different real-time experience from one that holds - the timeline is
what a pooled p50/p95 cannot see.

Motion energy, not luminance: the reel's periodic timing flashes survive as
motion transients under styles (learned grades, hard restyles) that destroy
the global-luminance impulse - the impulse.motion_xcorr lesson, found live
2026-08-11. Motion is what a V2V product must preserve to be a V2V product.

Timing comes from container pts, never from the fps label - Lucy delivers
~15 fps in a capture labelled 30 (playbook trap). Both series are resampled
to a common 100 Hz grid (np.interp) before correlating, so differing and
drifting frame rates cannot bias the lag. Each file's clock is zeroed at its
own first frame; the rig convention (capture recording starts when the reel
starts playing, canvas path so frames are emitted unconditionally) is what
makes the two clocks comparable.

Leading black (TTFF) in the capture is handled by construction: a constant
segment has zero motion energy, so a window falling entirely in the black
lead-in correlates with nothing (peak_r ~ 0, reported honestly as a low-
confidence window) and later windows align on shared motion unaffected.
Callers must gate on peak_r before trusting any window's lag.

Standalone by design: numpy + av only, no rtveval / campaign imports.

Output json to stdout (and optional --out):
    {windows: [{t0, lag_ms, peak_r}], median_lag_ms,
     drift_ms = last_window_lag - first_window_lag}
"""
import argparse
import json
import os
import sys

import numpy as np

GRID_HZ = 100.0          # common resampling rate; 1 sample = 10 ms
DIFF_WIDTH = 160         # frames downscaled to this width before differencing
MIN_WINDOW_S = 10.0      # a trailing stub shorter than this is not a window
MIN_OVERLAP_S = 5.0      # least in/out overlap for a lag score to count


def motion_energy(path):
    """(times_s, energy) - mean abs frame diff per consecutive pair.

    Times are container pts (frame.time), attributed to the LATER frame of
    each pair; index/average_rate is only a fallback for pts-less frames.
    Frames are downscaled to ~DIFF_WIDTH px gray before differencing - motion
    energy is a global scalar, so this loses nothing and keeps a multi-minute
    FFV1 capture cheap. Downscaling also makes the series resolution-
    independent, so input mp4 and capture mkv need not match dimensions.
    """
    import av

    times, vals = [], []
    prev = None
    with av.open(path) as c:
        stream = c.streams.video[0]
        fallback_rate = float(stream.average_rate or 30.0)
        for i, frame in enumerate(c.decode(stream)):
            w2 = DIFF_WIDTH
            h2 = max(2, int(round(frame.height * w2 / max(frame.width, 1) / 2)) * 2)
            g = frame.reformat(width=w2, height=h2,
                               format="gray").to_ndarray().astype(np.float64)
            t = frame.time
            if t is None:
                t = i / fallback_rate
            if prev is not None and g.shape == prev.shape:
                vals.append(float(np.abs(g - prev).mean()))
                times.append(float(t))
            prev = g
    if len(vals) < 2:
        raise RuntimeError("%s: only %d motion samples decoded" % (path, len(vals)))
    return np.asarray(times), np.asarray(vals)


def resample_100hz(times, vals):
    """Uniform GRID_HZ series, clock zeroed at the file's first sample."""
    t = times - times[0]
    grid = np.arange(0.0, float(t[-1]), 1.0 / GRID_HZ)
    return np.interp(grid, t, vals)


def window_lag(a, b, i0, wlen, max_lag, min_overlap):
    """(lag_ms, peak_r) for input window a[i0:i0+wlen] against output b.

    Output lags input, so only non-negative lags are searched: score(lag) is
    the Pearson r between the input window and b shifted by lag. Sub-sample
    refinement by parabolic interpolation of the peak (10 ms per sample is
    coarse next to a 150 ms band boundary). peak_r is the raw peak Pearson r -
    a flat (leading-black) or unrelated segment scores near 0 and the window
    is reported with that low confidence rather than dropped.
    """
    scores = []
    for lag in range(0, max_lag + 1):
        j = i0 + lag
        n = min(wlen, len(b) - j)
        if n < min_overlap:
            break
        x = a[i0:i0 + n]
        y = b[j:j + n]
        x = x - x.mean()
        y = y - y.mean()
        denom = float(np.linalg.norm(x)) * float(np.linalg.norm(y))
        scores.append(float(np.dot(x, y) / denom) if denom > 1e-12 else 0.0)
    if not scores:
        return None, 0.0

    scores = np.asarray(scores)
    best = int(np.argmax(scores))
    offset = 0.0
    if 0 < best < len(scores) - 1:
        y0, y1, y2 = scores[best - 1], scores[best], scores[best + 1]
        denom = y0 - 2 * y1 + y2
        if abs(denom) > 1e-12:
            offset = float(np.clip(0.5 * (y0 - y2) / denom, -1.0, 1.0))
    lag_ms = (best + offset) * 1000.0 / GRID_HZ
    return lag_ms, float(max(scores[best], 0.0))


def timeline(in_series, out_series, window_s, max_lag_ms):
    """Per-window lags over the whole overlap; non-overlapping windows."""
    wlen = max(1, int(round(window_s * GRID_HZ)))
    max_lag = max(1, int(round(max_lag_ms / 1000.0 * GRID_HZ)))
    min_win = int(MIN_WINDOW_S * GRID_HZ)
    min_overlap = int(MIN_OVERLAP_S * GRID_HZ)

    windows = []
    i0 = 0
    while i0 < len(in_series):
        wlen_eff = min(wlen, len(in_series) - i0)
        if wlen_eff < min_win:
            break  # trailing stub, not a window
        lag_ms, peak_r = window_lag(in_series, out_series, i0, wlen_eff,
                                    max_lag, min_overlap)
        if lag_ms is None:
            break  # capture ended before this window; later ones are worse
        windows.append({"t0": round(i0 / GRID_HZ, 2),
                        "lag_ms": round(lag_ms, 1),
                        "peak_r": round(peak_r, 3)})
        i0 += wlen
    return windows


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--input", required=True, help="input reel (mp4)")
    ap.add_argument("--capture", required=True, help="output capture (mkv)")
    ap.add_argument("--window-s", type=float, default=30.0)
    ap.add_argument("--max-lag-ms", type=float, default=3000.0)
    ap.add_argument("--out", help="also write the json here")
    args = ap.parse_args()

    for p in (args.input, args.capture):
        if not os.path.exists(p):
            print("missing: %s" % p, file=sys.stderr)
            return 1

    in_t, in_e = motion_energy(args.input)
    out_t, out_e = motion_energy(args.capture)
    in_series = resample_100hz(in_t, in_e)
    out_series = resample_100hz(out_t, out_e)

    windows = timeline(in_series, out_series, args.window_s, args.max_lag_ms)
    if not windows:
        print("no usable window: input %.1fs / capture %.1fs overlap too short"
              % (len(in_series) / GRID_HZ, len(out_series) / GRID_HZ),
              file=sys.stderr)
        return 1

    lags = [w["lag_ms"] for w in windows]
    doc = {
        "windows": windows,
        "median_lag_ms": round(float(np.median(lags)), 1),
        "drift_ms": round(lags[-1] - lags[0], 1),
        # provenance - measured fps is n pairs / pts span, never the label
        "input": args.input,
        "capture": args.capture,
        "window_s": args.window_s,
        "max_lag_ms": args.max_lag_ms,
        "grid_hz": GRID_HZ,
        "input_measured_fps": round(len(in_e) / max(in_t[-1] - in_t[0], 1e-9), 2),
        "capture_measured_fps": round(len(out_e) / max(out_t[-1] - out_t[0], 1e-9), 2),
    }
    text = json.dumps(doc, indent=2)
    print(text)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
