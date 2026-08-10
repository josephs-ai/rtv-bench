"""Block strip - the secondary V2V latency instrument, and primary for
unstyled passes.

Encodes the *frame index*, not a millisecond value: under CFR the conversion to
time is exact, and an index needs fewer bits.

Strip layout, left to right:

    [BLACK_REF][WHITE_REF][d0][d1]...[d19][PARITY]

The two reference blocks are the point. A restyle shifts and compresses the
luminance range, so a fixed threshold at 0.5 fails immediately; thresholding
adaptively at the midpoint of the two references survives moderate grading. The
parity bit turns an undetected misread into a detected one, which matters far
more here than the extra block costs - a silently wrong frame index produces a
plausible, wrong latency number.

The strip is still not trusted on heavily styled clips. It is cross-checked
against impulse cross-correlation on unstyled clips in the pilot; agreement
there is what licenses its use elsewhere. Where they disagree, impulse wins.
"""
from typing import NamedTuple, Optional, Sequence

import numpy as np

DATA_BITS = 20  # 2^20 frames = ~4.6 h at 60 fps
N_BLOCKS = DATA_BITS + 3  # + black ref, white ref, parity

IDX_BLACK_REF = 0
IDX_WHITE_REF = 1
IDX_DATA_START = 2
IDX_PARITY = IDX_DATA_START + DATA_BITS

# If the recovered white/black separation falls below this (on a 0-255 scale),
# the strip has been flattened by the restyle and is declared unreadable.
MIN_REF_CONTRAST = 25.0


class StripGeometry(NamedTuple):
    """Where the strip sits in the frame, in pixels."""

    x0: int
    y0: int
    block_w: int
    block_h: int
    n_blocks: int = N_BLOCKS

    @property
    def width(self) -> int:
        return self.block_w * self.n_blocks


class Decoded(NamedTuple):
    frame_index: Optional[int]
    readable: bool
    parity_ok: bool
    contrast: float
    reason: str = ""


def encode_bits(frame_index: int) -> Sequence[int]:
    """Frame index -> the full block pattern, as 0/1 per block.

    Reference blocks are emitted as 0 and 1 so the pattern can be rendered
    directly without special-casing them.
    """
    if not 0 <= frame_index < (1 << DATA_BITS):
        raise ValueError("frame_index %d out of range for %d bits" % (frame_index, DATA_BITS))

    data = [(frame_index >> i) & 1 for i in range(DATA_BITS)]  # LSB first
    parity = sum(data) & 1  # even parity
    return [0, 1] + data + [parity]


def _sample_blocks(frame: np.ndarray, geom: StripGeometry) -> Optional[np.ndarray]:
    """Mean luminance of the central region of each block.

    Sampling the centre 50% avoids block edges, where any resampling or codec
    ringing does its worst.
    """
    if frame.ndim == 3:
        lum = frame[..., :3].astype(np.float64) @ np.array((0.2126, 0.7152, 0.0722))
    else:
        lum = frame.astype(np.float64)

    h, w = lum.shape[:2]
    if geom.y0 + geom.block_h > h or geom.x0 + geom.width > w:
        return None

    inset_x = max(1, geom.block_w // 4)
    inset_y = max(1, geom.block_h // 4)

    out = np.empty(geom.n_blocks, dtype=np.float64)
    for i in range(geom.n_blocks):
        bx = geom.x0 + i * geom.block_w
        patch = lum[geom.y0 + inset_y: geom.y0 + geom.block_h - inset_y,
                    bx + inset_x: bx + geom.block_w - inset_x]
        if patch.size == 0:
            return None
        out[i] = float(patch.mean())
    return out


def decode(frame: np.ndarray, geom: StripGeometry) -> Decoded:
    """Recover the frame index from one frame's strip."""
    vals = _sample_blocks(frame, geom)
    if vals is None:
        return Decoded(None, False, False, 0.0, "strip geometry outside frame")

    black, white = vals[IDX_BLACK_REF], vals[IDX_WHITE_REF]
    contrast = float(white - black)
    if contrast < MIN_REF_CONTRAST:
        # Expected on aggressive restyling - this is the strip telling you
        # honestly that it cannot be read, rather than returning a wrong index.
        return Decoded(None, False, False, contrast,
                       "reference contrast %.1f below %.1f - restyled beyond recovery"
                       % (contrast, MIN_REF_CONTRAST))

    threshold = black + contrast / 2.0
    bits = (vals > threshold).astype(int)

    data = bits[IDX_DATA_START:IDX_DATA_START + DATA_BITS]
    parity_ok = bool((int(data.sum()) & 1) == int(bits[IDX_PARITY]))
    if not parity_ok:
        return Decoded(None, True, False, contrast, "parity check failed")

    index = int(sum(int(b) << i for i, b in enumerate(data)))
    return Decoded(index, True, True, contrast)


def decode_series(frames: Sequence[np.ndarray], geom: StripGeometry) -> list:
    """Decode a run of frames. Returns one Decoded per frame."""
    return [decode(f, geom) for f in frames]


def lag_samples(output_frames: Sequence[np.ndarray], geom: StripGeometry, fps: float,
                output_start_index: int = 0):
    """Lag per output frame, from the index the product's output still carries.

    The strip travels *through* the product: output frame k displays the index
    of whichever input frame produced it, so the lag is the difference between
    where we are and what we are seeing.
    """
    from .base import Interval, LatencySample, Method

    samples = []
    for k, frame in enumerate(output_frames):
        d = decode(frame, geom)
        if d.frame_index is None:
            continue
        out_index = output_start_index + k
        lag_frames = out_index - d.frame_index
        if lag_frames < 0:
            continue
        conf = float(np.clip(d.contrast / 255.0, 0.0, 1.0))
        samples.append(LatencySample(lag_ms=lag_frames * 1000.0 / fps,
                                     interval=Interval.V2V_FRAME_TO_FRAME,
                                     method=Method.BLOCK_STRIP,
                                     confidence=conf, event_index=k))
    return samples


def readability(frames: Sequence[np.ndarray], geom: StripGeometry) -> float:
    """Fraction of frames whose strip decoded with parity intact.

    Report this next to any block-strip latency figure. A style that drops
    readability to 0.3 has invalidated the method for that condition, and the
    impulse measurement is the only one left standing.
    """
    if not frames:
        return 0.0
    ok = sum(1 for d in decode_series(frames, geom) if d.frame_index is not None)
    return ok / len(frames)
