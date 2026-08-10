"""Conform determinism/upscale refusal; rating blinding, seeding, resume, cap."""
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rtveval import rating, report
from rtveval.reel import conform
from rtveval.stats import wilson

TMP = tempfile.mkdtemp(prefix="conform-test-")


# --- conform -----------------------------------------------------------------

def _master(w=1920, h=1080, fps=60.0):
    return conform.MasterInfo("/m.mp4", w, h, fps, 1000, "abc123")


def test_recipe_is_deterministic_and_content_addressed():
    a = conform.build_recipe(conform.InputSpec("lucy-2.5", 1920, 1080, 30.0))
    b = conform.build_recipe(conform.InputSpec("lucy-2.5", 1920, 1080, 30.0))
    c = conform.build_recipe(conform.InputSpec("lingbot-world-2", 1280, 960, 16.0))
    assert a == b and a[2] != c[2]
    assert "lanczos" in a[0] and a[0].startswith("fps=30")  # fps before scale
    print("  recipe stable, id differs across specs: %s vs %s" % (a[2], c[2]))


def test_upscale_refused_on_every_axis():
    m = _master(1920, 1080, 30.0)
    for spec in (conform.InputSpec("x", 3840, 2160, 30.0),   # resolution
                 conform.InputSpec("x", 1920, 1080, 60.0)):  # fps
        try:
            conform.conform(m, spec, "/dev/null", runner=lambda *a, **k: None)
            raise AssertionError("upscale accepted: %s" % (spec,))
        except conform.UpscaleRefused as e:
            pass
    print("  upscale refused on resolution and on fps")


def test_conform_real_ffmpeg_output_matches_spec():
    src = os.path.join(TMP, "master.mp4")
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30",
                    "-frames:v", "45", "-c:v", "libx264", "-preset", "ultrafast",
                    "-pix_fmt", "yuv420p", src], check=True)
    m = conform.probe_master(src)
    assert (m.width, m.height, m.fps) == (640, 360, 30.0)

    spec = conform.InputSpec("vidu-s1", 320, 180, 15.0)
    out = os.path.join(TMP, "vidu-input.mp4")
    rec = conform.conform(m, spec, out)

    import av
    with av.open(out) as c:
        s = c.streams.video[0]
        assert (s.codec_context.width, s.codec_context.height) == (320, 180)
        assert abs(float(s.average_rate) - 15.0) < 0.01
    manifest = os.path.join(TMP, "conform-manifest.json")
    conform.write_manifest([rec], m, manifest)
    doc = json.load(open(manifest))
    assert doc["conforms"][0]["recipe_id"] == rec.recipe_id
    print("  real conform: 640x360@30 -> 320x180@15, recipe %s in manifest"
          % rec.recipe_id)


# --- rating ------------------------------------------------------------------

SECRET = b"test-secret"
ITEMS = [rating.RatingItem("lucy-2.5", "C-lucy-2.5-C0-r%04d" % i,
                           "/cap/%d.mp4" % i, "V%d" % (i % 3 + 1))
         for i in range(6)] + \
        [rating.RatingItem("xmax-x2.0", "C-xmax-x2.0-C0-r%04d" % i,
                           "/cap/x%d.mp4" % i, "V%d" % (i % 3 + 1))
         for i in range(6)]


def _blind(out_dir, key_path):
    calls = []

    def fake_ffmpeg(cmd, check):
        out = cmd[-1]
        open(out, "w").write("video")
        calls.append(cmd)

    clips = rating.normalize_and_blind(ITEMS, SECRET, out_dir, key_path,
                                       runner=fake_ffmpeg)
    return clips, calls


def test_blinding_leaves_no_product_traces():
    out_dir = os.path.join(TMP, "served")
    key_path = os.path.join(TMP, "blinding-key.json")
    clips, calls = _blind(out_dir, key_path)

    assert len({c.blind_id for c in clips}) == len(ITEMS)
    violations = rating.audit_no_leaks(out_dir, ["lucy-2.5", "xmax-x2.0"])
    assert violations == [], violations
    # every clip went through the same normalization filter
    assert all("pad=" in " ".join(map(str, c)) for c in calls)
    key = json.load(open(key_path))
    assert key["key"][clips[0].blind_id]["product_key"] in ("lucy-2.5", "xmax-x2.0")
    print("  %d clips blinded, audit clean, key outside served tree" % len(clips))


def test_key_inside_served_tree_refused():
    out_dir = os.path.join(TMP, "served2")
    os.makedirs(out_dir, exist_ok=True)
    try:
        rating.normalize_and_blind(ITEMS, SECRET, out_dir,
                                   os.path.join(out_dir, "key.json"),
                                   runner=lambda *a, **k: None)
        raise AssertionError("key inside served dir accepted")
    except ValueError as e:
        print("  key inside served tree: refused")


def test_seeded_plan_reproducible_and_differs_per_rater():
    out_dir = os.path.join(TMP, "served3")
    clips, _ = _blind(out_dir, os.path.join(TMP, "k3.json"))
    p1 = rating.session_plan("rater-a", 42, clips)
    p2 = rating.session_plan("rater-a", 42, clips)
    p3 = rating.session_plan("rater-b", 42, clips)
    assert [x.blind_id for x in p1.presentations] == [x.blind_id for x in p2.presentations]
    assert [x.blind_id for x in p1.presentations] != [x.blind_id for x in p3.presentations]
    assert p1.seed == 42  # logged
    repeats = [x for x in p1.presentations if x.is_hidden_repeat]
    assert len(repeats) == 1
    first = next(i for i, x in enumerate(p1.presentations)
                 if x.blind_id == repeats[0].blind_id and not x.is_hidden_repeat)
    again = p1.presentations.index(repeats[0])
    assert again - first >= 2, "repeat adjacent to original"
    print("  plan reproducible per (seed, rater), differs across raters; "
          "hidden repeat at distance %d" % (again - first))


def test_resume_and_session_cap():
    out_dir = os.path.join(TMP, "served4")
    clips, _ = _blind(out_dir, os.path.join(TMP, "k4.json"))
    plan = rating.session_plan("rater-a", 7, clips)
    j = rating.SessionJournal(os.path.join(TMP, "scores.jsonl"))

    t0 = 1000000.0
    for k in range(3):
        p = j.next_pending(plan, "temporal_coherence")
        j.record("rater-a", p, "temporal_coherence", 4, now=t0 + k * 30)
    # resume: a fresh journal object sees 3 done
    j2 = rating.SessionJournal(j.path)
    nxt = j2.next_pending(plan, "temporal_coherence")
    assert nxt.order_index == 3
    print("  resume mid-session: next pending is #%d" % nxt.order_index)

    try:
        j2.record("rater-a", nxt, "temporal_coherence", 3, now=t0 + 46 * 60)
        raise AssertionError("score accepted after cap")
    except rating.SessionClosed as e:
        print("  46 min in: %s" % e)


# --- report additions --------------------------------------------------------

def test_knife_edge_margin_flagged():
    notes = report.separability_notes({"a": wilson(297, 300), "b": wilson(285, 300)})
    assert "KNIFE-EDGE" in notes[0] and "margin" in notes[0]
    wide = report.separability_notes({"a": wilson(398, 400), "b": wilson(340, 400)})
    assert "do not overlap" in wide[0] and "KNIFE-EDGE" not in wide[0]
    print("  99%% vs 95%% at N=300: separable but flagged - %s"
          % notes[0][notes[0].index("KNIFE-EDGE"):][:60])


def test_coverage_statement_is_front_matter():
    evaluated = {"Lucy 2.5": "v2v", "Xmax X2.0": "v2v",
                 "LingBot-World 2": "generation", "Happy Oyster": "generation"}
    unreachable = {"pixverse-r1": "partner waitlist not granted by day 3",
                   "vidu-s1": "enterprise beta application unanswered"}
    md = report.coverage_statement(evaluated, unreachable, requested_total=6)
    assert "4 of the 6 products" in md
    assert "digital human category is empty" in md
    assert "No conclusions about this category" in md
    print("  coverage: '4 of 6' + empty digital-human category stated up front")


def test_product_card_declares_spec_facts():
    card = report.ProductCard("Vidu S1", "P", "540p", 25.0, "vidu-s1@beta3",
                              input_conform_id="9f2a1c04d7e1")
    md = card.markdown()
    assert "540p @ 25 fps" in md and "do not enter aesthetic scores" in md
    assert "9f2a1c04d7e1" in md
    print("  product card: declared spec + conform id, confound statement inline")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        print(t.__name__)
        try:
            t()
        except Exception:
            failed += 1
            import traceback
            traceback.print_exc(limit=4)
    print("\n%d/%d passed" % (len(tests) - failed, len(tests)))
    sys.exit(1 if failed else 0)
