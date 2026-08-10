"""Per-product input conformance: one canonical master, deterministic downscales.

"Identical pixels to every product" is impossible as stated: Lucy takes
1080p30, Reactor serves LingBot at 960p/16fps, Vidu S1 wants 540p25. What IS
achievable, and what this module enforces:

  - ONE canonical master, filmed high enough that every product path is a
    DOWNSCALE. Upscaling is refused outright - an upscaled input tests our
    interpolator, not their model.
  - One deterministic conform path per product: same scaler (lanczos, full
    chroma, accurate rounding), same fps resampler, same encoder settings,
    run by us. The alternative - handing every product the master and letting
    each SDK's internal resize do something undocumented - is a confound that
    cannot be reconstructed afterward.
  - The recipe is content-addressed: recipe_id = short hash of the exact
    filter chain + encoder args. It is recorded in the conform record, joined
    into the reel sidecar, and stamped on every run row (RunRow.
    input_conform_id), so any two rows are comparable-or-not by inspection.
"""
import hashlib
import json
import os
import subprocess
from typing import NamedTuple, Optional, Tuple

SCALE_FLAGS = "lanczos+accurate_rnd+full_chroma_int"


class InputSpec(NamedTuple):
    """What a product actually accepts. From vendor docs / probe, per product."""

    product_key: str
    width: int
    height: int
    fps: float


class MasterInfo(NamedTuple):
    path: str
    width: int
    height: int
    fps: float
    size_bytes: int
    quick_hash: str  # first MB + last MB + size; identity check, not integrity proof


class ConformRecord(NamedTuple):
    product_key: str
    recipe_id: str
    filter_chain: str
    encoder_args: Tuple[str, ...]
    master_quick_hash: str
    out_path: str
    width: int
    height: int
    fps: float


class UpscaleRefused(ValueError):
    pass


def probe_master(path: str) -> MasterInfo:
    import av

    with av.open(path) as c:
        s = c.streams.video[0]
        width, height = s.codec_context.width, s.codec_context.height
        fps = float(s.average_rate)
    return MasterInfo(path, width, height, fps, os.path.getsize(path),
                      quick_hash(path))


def quick_hash(path: str) -> str:
    h = hashlib.sha256()
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        h.update(f.read(1 << 20))
        if size > (2 << 20):
            f.seek(-(1 << 20), os.SEEK_END)
            h.update(f.read(1 << 20))
    h.update(str(size).encode())
    return h.hexdigest()[:16]


def build_recipe(spec: InputSpec) -> Tuple[str, Tuple[str, ...], str]:
    """(filter_chain, encoder_args, recipe_id). Pure - no I/O - so the id can
    be computed, compared, and audited without running anything.

    fps resample happens BEFORE scale: dropping frames first means the scaler
    never touches frames that won't be delivered, and the order is part of the
    recipe so it can never silently differ between products.
    """
    filter_chain = "fps=%g,scale=%d:%d:flags=%s" % (
        spec.fps, spec.width, spec.height, SCALE_FLAGS)
    encoder_args = ("-c:v", "libx264", "-crf", "12", "-preset", "slow",
                    "-pix_fmt", "yuv420p", "-fps_mode", "cfr")
    recipe_id = hashlib.sha256(
        (filter_chain + "|" + " ".join(encoder_args)).encode()).hexdigest()[:12]
    return filter_chain, encoder_args, recipe_id


def conform(master: MasterInfo, spec: InputSpec, out_path: str,
            runner=subprocess.run) -> ConformRecord:
    """Master -> product-conformant input. Refuses any upscale on any axis."""
    problems = []
    if spec.width > master.width or spec.height > master.height:
        problems.append("resolution %dx%d exceeds master %dx%d"
                        % (spec.width, spec.height, master.width, master.height))
    if spec.fps > master.fps + 1e-6:
        problems.append("fps %g exceeds master %g" % (spec.fps, master.fps))
    if problems:
        raise UpscaleRefused(
            "%s: %s - refilm the master higher; an upscaled input tests our "
            "interpolator, not their model" % (spec.product_key, "; ".join(problems)))

    filter_chain, encoder_args, recipe_id = build_recipe(spec)
    runner(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", master.path, "-vf", filter_chain, *encoder_args, "-an",
            out_path], check=True)

    return ConformRecord(product_key=spec.product_key, recipe_id=recipe_id,
                         filter_chain=filter_chain, encoder_args=encoder_args,
                         master_quick_hash=master.quick_hash, out_path=out_path,
                         width=spec.width, height=spec.height, fps=spec.fps)


def write_manifest(records, master: MasterInfo, path: str) -> None:
    """data/conform-manifest.json - joined into the reproduction appendix."""
    doc = {
        "master": master._asdict(),
        "scale_flags": SCALE_FLAGS,
        "conforms": [r._asdict() for r in records],
    }
    with open(path, "w") as f:
        json.dump(doc, f, indent=2)
