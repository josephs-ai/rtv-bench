"""Netshape phases, reel sidecar, capture CFR, pilot gate, report constraints."""
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from PIL import Image

from rtveval import pilot, report
from rtveval.capture import integrity
from rtveval.latency.base import Interval, LatencyResult, Method
from rtveval.orchestrator import netshape
from rtveval.stats import Agreement, wilson

TMP = tempfile.mkdtemp(prefix="rig-test-")


# --- netshape ----------------------------------------------------------------

class FakeShaper:
    def __init__(self):
        self.applied = []

    def apply(self, cond):
        self.applied.append(cond.condition_id)
        return "pipe ok"

    def read_back(self):
        return "fake dnctl"

    def clear(self):
        self.applied.append("clear")


def test_phase_plan_must_tile_rounds():
    try:
        netshape.PhaseScheduler([netshape.PhasePlan("C0", range(0, 10)),
                                 netshape.PhasePlan("C2", range(12, 20))],
                                shaper=FakeShaper())
        raise AssertionError("gap in phase plan accepted")
    except ValueError as e:
        print("  gapped phase plan rejected: %s" % e)


def test_phase_change_only_between_rounds():
    s = netshape.PhaseScheduler([netshape.PhasePlan("C0", range(0, 3)),
                                 netshape.PhasePlan("C2", range(3, 6))],
                                shaper=FakeShaper())
    netshape.verify_orig = netshape.verify

    # C0 phase never applies shaping; entering round 3 mid-round-2 must refuse
    try:
        s.ensure(3, completed_rounds=2, baseline_rtt_ms=20.0)
        raise AssertionError("mid-round phase change accepted")
    except RuntimeError as e:
        print("  mid-round phase change refused: %s" % str(e)[:70])


def test_applied_state_not_schedule():
    """Row records what the probe measured, and an unverified phase fails."""
    fake = FakeShaper()
    good = netshape.verify(netshape.C2, baseline_rtt_ms=20.0, shaper=fake,
                           probe=lambda: 118.0)
    assert good.verified and abs(good.probe_rtt_ms - 118.0) < 1e-9
    bad = netshape.verify(netshape.C2, baseline_rtt_ms=20.0, shaper=fake,
                          probe=lambda: 21.0)  # shaping silently absent
    assert not bad.verified and "NOT IN FORCE" in bad.detail
    check = netshape.as_check(bad)
    assert not check.ok
    print("  applied-state verify: probe 118ms ok; probe 21ms -> '%s' -> rig "
          "evidence -> E" % bad.detail[-40:])


# --- reel sidecar ------------------------------------------------------------

def _render_test_reel(n=90, w=320, h=180, fps=30.0):
    from rtveval.reel import render

    frames_written = []

    def encoder(frame):
        if frame is not None:
            frames_written.append(frame)

    def frames():
        rng = np.random.default_rng(1)
        for i in range(n):
            base = np.full((h, w, 3), 60 + (i % 30), dtype=np.uint8)
            base += rng.integers(0, 8, (h, w, 3), dtype=np.uint8)
            yield Image.fromarray(base)

    spec = render.ReelSpec(width=w, height=h, fps=fps)
    clips = [render.ClipSpan("V1", 0, 45), render.ClipSpan("V2", 45, n)]
    out = os.path.join(TMP, "reel.mp4")
    truth = render.render_reel(frames(), n, spec, clips, out, encoder=encoder)
    return truth, frames_written, out


def test_sidecar_is_ground_truth():
    from rtveval.latency import blockstrip
    from rtveval.reel import render

    truth, frames, out = _render_test_reel()
    assert truth["flash"]["frames"] == [30, 60]  # 1s interval, 30fps, offset 30
    assert truth["fps_cfr"] == 30.0 and truth["n_frames"] == 90

    # extractors read the sidecar, not the video
    loaded = render.load_truth(out)
    rel, start = render.flash_frames_for_clip(loaded, "V2")
    assert rel == [15] and start == 45  # frame 60 within [45,90)

    # the rendered strip decodes to the sidecar's geometry
    geom = render.strip_geometry(loaded)
    got = blockstrip.decode(frames[42], geom)
    assert got.frame_index == 42 and got.parity_ok
    print("  sidecar: flashes %s, V2-relative %s; frame 42 strip decodes via "
          "sidecar geometry" % (truth["flash"]["frames"], rel))


def test_partial_reel_writes_no_sidecar():
    from rtveval.reel import render

    def frames():
        yield Image.new("RGB", (320, 180))  # only one frame of 90

    spec = render.ReelSpec(width=320, height=180, fps=30.0)
    out = os.path.join(TMP, "partial.mp4")
    try:
        render.render_reel(frames(), 90, spec, [render.ClipSpan("V1", 0, 90)],
                           out, encoder=lambda f: None)
        raise AssertionError("partial reel accepted")
    except RuntimeError as e:
        assert not os.path.exists(render.sidecar_path(out))
        print("  partial reel: %s" % e)


# --- capture CFR -------------------------------------------------------------

def _encode(path, vsync_args, n=60):
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=30",
                    "-frames:v", str(n), "-c:v", "libx264", "-preset", "ultrafast"]
                   + vsync_args + [path], check=True)


def test_cfr_capture_passes_vfr_fails():
    cfr = os.path.join(TMP, "cfr.mp4")
    _encode(cfr, ["-fps_mode", "cfr"])
    r = integrity.check_capture(cfr)
    assert r.ok, r.detail
    print("  CFR capture: %s" % r.detail)

    # synthesise VFR: random per-frame delay, amplitude below the frame period
    # so PTS stays monotonic but intervals scatter well outside 20%
    vfr = os.path.join(TMP, "vfr.mp4")
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-i", cfr, "-vf", "setpts=PTS+(random(0)*0.025)/TB",
                    "-fps_mode", "vfr", "-c:v", "libx264", "-preset", "ultrafast",
                    vfr], check=True)
    r2 = integrity.check_capture(vfr)
    assert not r2.ok, r2.detail
    check = integrity.as_check(r2)
    assert not check.ok and check.name == "capture_cfr"
    print("  VFR capture: FAILED as rig evidence - %s" % r2.detail[:80])


def test_zero_byte_capture_fails():
    empty = os.path.join(TMP, "empty.mp4")
    open(empty, "w").close()
    assert not integrity.check_capture(empty).ok
    print("  zero-byte capture fails")


# --- pilot gate --------------------------------------------------------------

def test_gate_blocks_without_evidence():
    d = tempfile.mkdtemp(prefix="gate-")
    r = pilot.evaluate(d)
    assert not r.passed and len(r.blockers) == 5
    try:
        pilot.require_for_campaign_c(d)
        raise AssertionError("gate passed with no evidence")
    except pilot.GateError as e:
        print("  empty data dir: BLOCKED with %d blockers" % len(r.blockers))


def test_gate_passes_and_dictates_capture_policy():
    d = tempfile.mkdtemp(prefix="gate-")

    def put(name, doc):
        with open(os.path.join(d, name), "w") as f:
            json.dump(doc, f)

    put("encoder-contamination.json", {"verdict": "lossless_required"})
    put("method-crosscheck.json", {"worst_abs_disagreement_ms": 9.1})
    put("band-separation.json", {"bands_occupied": 3})
    put("rater-trial.json", {"alpha": 0.74})
    put("interaction-contracts.json", {"probes": [
        {"product_key": "happy-oyster", "declared_contract": "text_directed",
         "confirmed_contract": "text_directed", "accepts_text_steer": True},
        {"product_key": "lingbot-world-2", "declared_contract": "movement_driven",
         "confirmed_contract": "movement_driven", "accepts_text_steer": False}]})

    policy = pilot.require_for_campaign_c(d)
    assert policy["capture"] == "ffv1_lossless"
    print("  full evidence: gate passes; contamination verdict dictates %s"
          % policy["capture"])

    put("rater-trial.json", {"alpha": 0.55})
    r = pilot.evaluate(d)
    assert not r.passed and "descriptors are ambiguous" in r.blockers[0]
    print("  alpha 0.55: blocked - %s" % r.blockers[0][:60])


# --- report constraints ------------------------------------------------------

def _latres(lens, interval=Interval.V2V_FRAME_TO_FRAME):
    return LatencyResult(interval=interval, method=Method.IMPULSE_XCORR,
                         lens=lens, n=40, mean_ms=180, p50_ms=175, p95_ms=210,
                         jitter_ms=12, rig_offset_ms=8, dropped_low_confidence=1)


def test_table_rejects_cross_lens_row():
    t = report.Table("V2V latency", lens="P", columns=["Product", "Latency"])
    t.add_row([report.Cell("Lucy 2.5"), report.latency_cell(_latres("P"))])
    try:
        t.add_row([report.Cell("LingBot"), report.latency_cell(_latres("M"))])
        raise AssertionError("cross-lens row accepted")
    except report.LensViolation as e:
        print("  Lens M cell into Lens P table: refused - %s" % str(e)[:60])


def test_table_rejects_mixed_intervals():
    t = report.Table("Latency", lens="P", columns=["Product", "Latency"])
    t.add_row([report.Cell("Lucy"), report.latency_cell(_latres("P"))])
    try:
        t.add_row([report.Cell("Vidu"),
                   report.latency_cell(_latres("P", Interval.DH_AUDIO_TO_LIP))])
        raise AssertionError("mixed intervals accepted")
    except report.LensViolation as e:
        print("  audio-to-lip into frame-to-frame table: refused")


def test_table_rejects_mixed_capture_paths():
    from rtveval.latency.base import CapturePath
    t = report.Table("V2V latency", lens="P", columns=["Product", "Latency"])
    sdk = _latres("P")
    comp = sdk._replace(capture_path=CapturePath.COMPOSITE_CAPTURE,
                        residual_bound_ms=85.0)
    t.add_row([report.Cell("Lucy"), report.latency_cell(sdk)])
    try:
        t.add_row([report.Cell("Xmax native"), report.latency_cell(comp)])
        raise AssertionError("mixed capture paths accepted in table")
    except report.LensViolation:
        print("  composite cell into sdk-path table: refused")


def test_contested_dimension_cannot_rank():
    contested = Agreement(alpha=0.41, gate="contested")
    try:
        report.RankingClaim.make("aesthetic_quality", ["a", "b"], contested)
        raise AssertionError("contested ranking constructed")
    except report.ContestedDimension:
        pass
    block = report.dimension_block("aesthetic_quality", ["a", "b"], contested)
    assert "no ranking is claimed" in block and " > " not in block
    ok = report.dimension_block("lip_sync", ["a", "b"], Agreement(0.85, "normal"))
    assert "a > b" in ok
    print("  contested dimension renders the disagreement sentence, never a ranking")


def test_separability_notes_from_ci_only():
    rates = {"lucy-2.5": wilson(295, 300), "xmax-x2.0": wilson(290, 300)}
    notes = report.separability_notes(rates)
    assert "no reliability difference detectable" in notes[0]
    rates2 = {"a": wilson(298, 400), "b": wilson(380, 400)}
    notes2 = report.separability_notes(rates2)
    assert "do not overlap" in notes2[0]
    print("  separability: overlapping CIs -> 'not detectable'; disjoint -> claimed")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        print(t.__name__)
        try:
            t()
        except Exception as e:
            failed += 1
            import traceback
            traceback.print_exc(limit=4)
    print("\n%d/%d passed" % (len(tests) - failed, len(tests)))
    sys.exit(1 if failed else 0)
