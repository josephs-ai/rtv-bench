"""Reel rendering with a machine-readable ground-truth sidecar.

The sidecar is the contract between the reel and the extractors: exact flash
frame indices, block-strip geometry and encoding parameters, CFR rate, and
clip boundaries. Extractors read it - they never re-derive flash positions
from the rendered video, which would make the instrument circular (detecting
flashes with the same code whose accuracy is under test) and would break the
moment a restyle attenuates a flash the sidecar knows is there.

It also makes the bench validation reproducible against the real reel: the
same test that ran on synthetic series runs on (reel, sidecar) pairs.

Encoding is piped to ffmpeg as raw RGB; the encoder is forced CFR. The
renderer refuses to write a sidecar for a reel it did not fully render - a
partial reel with a full sidecar is worse than no reel.
"""
import json
import os
import subprocess
from typing import Callable, Iterator, List, NamedTuple, Optional, Tuple

import numpy as np
from PIL import Image

from ..latency.blockstrip import DATA_BITS, MIN_REF_CONTRAST, StripGeometry
from . import overlay

SIDECAR_VERSION = 1


class ClipSpan(NamedTuple):
    clip_id: str
    start_frame: int  # inclusive
    end_frame: int  # exclusive


class ReelSpec(NamedTuple):
    width: int
    height: int
    fps: float
    flash_interval_ms: float = overlay.DEFAULT_FLASH_INTERVAL_MS
    flash_intensity: int = overlay.FLASH_INTENSITY


def sidecar_path(reel_path: str) -> str:
    return os.path.splitext(reel_path)[0] + ".truth.json"


def render_reel(frames: Iterator[Image.Image], n_frames: int, spec: ReelSpec,
                clips: List[ClipSpan], out_path: str,
                geom: Optional[StripGeometry] = None,
                encoder: Optional[Callable] = None) -> dict:
    """Instrument `frames` and encode to `out_path` (CFR), writing the sidecar.

    `encoder` is injectable for tests; default pipes raw RGB to ffmpeg/libx264
    at CRF 12 with an explicit CFR clamp.
    """
    if geom is None:
        geom = overlay.default_geometry(spec.width, spec.height)
    flashes = overlay.flash_schedule(n_frames, spec.fps,
                                     interval_ms=spec.flash_interval_ms)
    flash_set = set(flashes)

    spans = sorted(clips, key=lambda c: c.start_frame)
    covered = [f for c in spans for f in (c.start_frame, c.end_frame)]
    if covered != sorted(covered) or (spans and spans[-1].end_frame != n_frames) \
            or (spans and spans[0].start_frame != 0):
        raise ValueError("clip spans must tile [0, %d) in order" % n_frames)

    write = encoder or _ffmpeg_encoder(out_path, spec)
    rendered = 0
    try:
        for idx, img in enumerate(frames):
            if idx >= n_frames:
                break
            if img.size != (spec.width, spec.height):
                img = img.resize((spec.width, spec.height))
            out = overlay.apply_flash(img, spec.flash_intensity) if idx in flash_set else img
            out = overlay.render_strip(out, idx, geom)
            write(np.asarray(out.convert("RGB"), dtype=np.uint8))
            rendered += 1
    finally:
        write(None)  # close

    if rendered != n_frames:
        # No sidecar for a partial reel.
        raise RuntimeError("rendered %d of %d frames - reel incomplete, "
                           "sidecar NOT written" % (rendered, n_frames))

    truth = {
        "sidecar_version": SIDECAR_VERSION,
        "reel_path": os.path.basename(out_path),
        "n_frames": n_frames,
        "fps_cfr": spec.fps,
        "width": spec.width,
        "height": spec.height,
        "flash": {
            "frames": flashes,
            "interval_ms": spec.flash_interval_ms,
            "intensity": spec.flash_intensity,
            "duration_frames": overlay.FLASH_FRAMES,
        },
        "block_strip": {
            "geometry": geom._asdict(),
            "data_bits": DATA_BITS,
            "bit_order": "lsb_first",
            "parity": "even",
            "min_ref_contrast": MIN_REF_CONTRAST,
            "encodes": "frame_index",
        },
        "clips": [c._asdict() for c in spans],
    }
    with open(sidecar_path(out_path), "w") as f:
        json.dump(truth, f, indent=2)
    return truth


def load_truth(reel_path: str) -> dict:
    with open(sidecar_path(reel_path)) as f:
        truth = json.load(f)
    if truth.get("sidecar_version") != SIDECAR_VERSION:
        raise ValueError("sidecar version %r != %d - re-render the reel rather "
                         "than guessing at compatibility"
                         % (truth.get("sidecar_version"), SIDECAR_VERSION))
    return truth


def flash_frames_for_clip(truth: dict, clip_id: str) -> Tuple[List[int], int]:
    """(flash frames relative to clip start, clip start) - what impulse.measure
    wants for a single-clip capture."""
    for c in truth["clips"]:
        if c["clip_id"] == clip_id:
            rel = [f - c["start_frame"] for f in truth["flash"]["frames"]
                   if c["start_frame"] <= f < c["end_frame"]]
            return rel, c["start_frame"]
    raise KeyError(clip_id)


def strip_geometry(truth: dict) -> StripGeometry:
    return StripGeometry(**truth["block_strip"]["geometry"])


def _ffmpeg_encoder(out_path: str, spec: ReelSpec) -> Callable:
    """Raw RGB pipe -> libx264 CRF 12, explicit CFR."""
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", "%dx%d" % (spec.width, spec.height), "-r", "%g" % spec.fps,
         "-i", "-",
         "-c:v", "libx264", "-crf", "12", "-preset", "medium",
         "-pix_fmt", "yuv420p", "-fps_mode", "cfr", "-r", "%g" % spec.fps,
         out_path],
        stdin=subprocess.PIPE)

    def write(frame: Optional[np.ndarray]) -> None:
        if frame is None:
            proc.stdin.close()
            if proc.wait() != 0:
                raise RuntimeError("ffmpeg exited %d" % proc.returncode)
        else:
            proc.stdin.write(frame.tobytes())

    return write
