"""Test-reel instrumentation: impulse flashes and the block strip.

Rendered with PIL rather than ffmpeg's drawtext, because the Homebrew ffmpeg
bottle on this machine is built without libfreetype. That turns out to be the
better path anyway - the strip needs exact, known block geometry, which is
easier to guarantee by drawing rectangles ourselves than by parsing back text we
asked a filter to draw.

Two instruments go into the reel:

  Impulse  A brief full-frame luminance flash at known frame indices. Primary
           for V2V, because it survives restyling - a transient stays a
           transient under any style.
  Strip    Frame index in adaptive-threshold blocks. Secondary; readable on
           unstyled and lightly styled passes, and it says so when it isn't.

Both are present in every reel. They cost one frame of content per flash and a
thin band at the top, and having both is what makes the pilot cross-check
possible.
"""
from typing import List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from ..latency.blockstrip import N_BLOCKS, StripGeometry, encode_bits

# One frame is enough for a detectable transient at 60 fps and minimises the
# content the flash obscures. Two if a product's encoder is dropping frames.
FLASH_FRAMES = 1
FLASH_INTENSITY = 90  # additive, 0-255 scale
DEFAULT_FLASH_INTERVAL_MS = 1000.0


def flash_schedule(n_frames: int, fps: float,
                   interval_ms: float = DEFAULT_FLASH_INTERVAL_MS,
                   start_offset_frames: int = 30) -> List[int]:
    """Frame indices carrying an impulse.

    A 60 s clip at 1 s spacing yields ~59 flashes, comfortably above the >=30
    samples Campaign A needs per condition, with headroom for flashes the
    product swallows.

    The offset keeps the first flash clear of stream start-up, where products
    are still ramping and the measurement would be unrepresentative.
    """
    if interval_ms <= 0:
        raise ValueError("interval_ms must be positive")
    step = max(1, int(round(interval_ms * fps / 1000.0)))
    return list(range(start_offset_frames, n_frames, step))


def apply_flash(img: Image.Image, intensity: int = FLASH_INTENSITY) -> Image.Image:
    """Additive full-frame brighten, clipped.

    Full-frame because the recovery method is *global* mean luminance: a flash
    confined to a corner would be diluted by the rest of the frame, and could be
    cropped away entirely by a product that changes aspect ratio.
    """
    arr = np.asarray(img.convert("RGB"), dtype=np.int16)
    return Image.fromarray(np.clip(arr + int(intensity), 0, 255).astype(np.uint8))


def default_geometry(width: int, height: int, n_blocks: int = N_BLOCKS) -> StripGeometry:
    """A strip across the top of the frame, sized to the resolution.

    Blocks are made as large as the width allows, because block size is what
    determines survival through downscaling and compression.
    """
    block_w = max(4, width // (n_blocks + 2))
    block_h = max(8, height // 20)
    x0 = (width - block_w * n_blocks) // 2
    return StripGeometry(x0=x0, y0=0, block_w=block_w, block_h=block_h, n_blocks=n_blocks)


def render_strip(img: Image.Image, frame_index: int, geom: Optional[StripGeometry] = None,
                 draw_digits: bool = True) -> Image.Image:
    """Draw the block strip, and optionally human-readable digits beneath it.

    The digits are for a human debugging a capture by eye; nothing parses them.
    """
    if geom is None:
        geom = default_geometry(img.width, img.height)

    out = img.convert("RGB").copy()
    d = ImageDraw.Draw(out)

    for i, bit in enumerate(encode_bits(frame_index)):
        x = geom.x0 + i * geom.block_w
        d.rectangle([x, geom.y0, x + geom.block_w - 1, geom.y0 + geom.block_h - 1],
                    fill=(255, 255, 255) if bit else (0, 0, 0))

    # A hairline border so the strip's extent stays findable if a restyle
    # softens the block edges.
    d.rectangle([geom.x0 - 1, geom.y0, geom.x0 + geom.width, geom.y0 + geom.block_h],
                outline=(128, 128, 128))

    if draw_digits:
        try:
            font = ImageFont.load_default(size=max(12, geom.block_h // 2))
        except TypeError:  # Pillow < 10.1
            font = ImageFont.load_default()
        d.text((geom.x0, geom.y0 + geom.block_h + 2), "f%07d" % frame_index,
               fill=(255, 255, 0), font=font)

    return out


def instrument_frame(img: Image.Image, frame_index: int,
                     flash_frames: Sequence[int],
                     geom: Optional[StripGeometry] = None) -> Image.Image:
    """Apply both instruments to one frame.

    Order matters: flash first, strip second. The strip's reference blocks must
    stay at true black and true white, so the flash must not lift them - if it
    did, the adaptive threshold would be calibrated on a moving target.
    """
    out = apply_flash(img) if frame_index in set(flash_frames) else img
    return render_strip(out, frame_index, geom)


def verify_roundtrip(width: int = 1920, height: int = 1080,
                     indices: Sequence[int] = (0, 1, 12345, 999999)) -> List[Tuple[int, bool]]:
    """Render then decode, with no codec in between.

    A sanity check on the codec itself, not on style robustness: if this fails,
    the geometry or bit order is wrong and nothing downstream can work.
    """
    from ..latency.blockstrip import decode

    geom = default_geometry(width, height)
    results = []
    for idx in indices:
        img = Image.new("RGB", (width, height), (40, 90, 140))
        rendered = render_strip(img, idx, geom, draw_digits=False)
        got = decode(np.asarray(rendered), geom)
        results.append((idx, got.frame_index == idx and got.parity_ok))
    return results
