"""VLM judge: every pure component tested against its failure mode, no network."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rtveval.vlm_judge import (DIMENSION_SETS, GENERATION_DIMENSIONS, JudgeItem,
                               JudgmentRecord, build_plan, build_prompt,
                               judge_schema, sample_frame_indices,
                               self_consistency, validate_against_humans)

SECRET = b"test-secret"


def _items(n):
    return [JudgeItem("prod-%d" % (i % 2), "run-%03d" % i,
                      "/cap/%d.mkv" % i, "generation", "a prompt") for i in range(n)]


def test_frame_sampling_deterministic_and_covering():
    idx = sample_frame_indices(300, 8)
    assert idx[0] == 0 and idx[-1] == 299 and len(idx) == 8
    assert idx == sample_frame_indices(300, 8)  # deterministic
    assert sample_frame_indices(5, 8) == [0, 1, 2, 3, 4]  # short clip: all
    assert sample_frame_indices(0, 8) == []
    print("  sampling: even, deterministic, first+last always included")


def test_plan_blinds_and_hides_repeats():
    items = _items(8)
    plan = build_plan(items, SECRET, seed=7)
    ids = [p.blind_id for p in plan]
    # no product/run identity in any blind id
    assert not any("prod" in b or "run" in b for b in ids)
    # repeats present, and a repeat's blind id differs from its original's
    reps = [p for p in plan if p.is_hidden_repeat]
    assert reps, "no hidden repeats scheduled"
    for r in reps:
        orig = next(p for p in plan
                    if p.item_index == r.item_index and not p.is_hidden_repeat)
        assert r.blind_id != orig.blind_id, "repeat is linkable by name"
    # same seed -> same plan; different seed -> different order
    assert plan == build_plan(items, SECRET, seed=7)
    assert plan != build_plan(items, SECRET, seed=8)
    print("  plan: blinded, %d unlinkable hidden repeats, seeded" % len(reps))


def test_self_consistency_gate():
    recs = [
        JudgmentRecord("a", "E7", 4, False, 0),
        JudgmentRecord("a2", "E7", 4, True, 0),   # consistent
        JudgmentRecord("b", "E8", 2, False, 1),
        JudgmentRecord("b2", "E8", 4, True, 1),   # deviates by 2 -> flag
    ]
    out = self_consistency(recs)
    assert out["n_pairs"] == 2 and out["max_deviation"] == 2 and out["flagged"]
    print("  consistency: 2-point repeat deviation flags the judge")


def test_validation_gate_blocks_low_alpha():
    # perfect agreement on 6 items -> usable
    vlm = {("r%d" % i, "E7"): (i % 5) + 1 for i in range(6)}
    ok = validate_against_humans(vlm, dict(vlm))
    assert ok["usable"] and ok["alpha"] is not None and ok["alpha"] > 0.9
    # anti-correlated -> not usable
    inv = {k: 6 - v for k, v in vlm.items()}
    bad = validate_against_humans(vlm, inv)
    assert not bad["usable"] and "0.67" in bad["reason"]
    # tiny overlap refuses to conclude anything
    tiny = validate_against_humans({("a", "E7"): 3}, {("a", "E7"): 3})
    assert not tiny["usable"] and "overlap" in tiny["reason"]
    print("  human gate: alpha>=0.67 usable, anti-correlated blocked, "
          "n<5 refused")


def test_schema_is_strict_and_matches_dimensions():
    schema = judge_schema(GENERATION_DIMENSIONS)
    dims = schema["properties"]["dimensions"]
    assert set(dims["required"]) == {"E6", "E7", "E8"}
    assert dims["additionalProperties"] is False
    for d in dims["properties"].values():
        assert d["properties"]["score"]["enum"] == [1, 2, 3, 4, 5]
        assert "assessable" in d["required"]
    json.dumps(schema)  # serialisable
    print("  schema: strict, per-dimension, scores locked to 1-5")


def test_prompt_carries_rubric_verbatim_and_no_identity():
    p = build_prompt(GENERATION_DIMENSIONS, 8, 12.0, "three red boats")
    for d in GENERATION_DIMENSIONS:
        assert d.anchors[5] in p and d.anchors[1] in p
    assert "three red boats" in p
    assert "do not know which product" in p
    assert "assessable=false" in p
    # frame-rate caveat present: judge must not invent flicker it can't see
    assert "sampling" in p.lower()
    print("  prompt: rubric anchors verbatim, blinded, non-assessable path")


def test_dimension_sets_weights():
    for name, dims in DIMENSION_SETS.items():
        assert all(1 <= s <= 5 for d in dims for s in d.anchors), name
        assert all(len(d.anchors) == 5 for d in dims), name
    print("  dimension sets: complete 1-5 anchors for %s"
          % ", ".join(DIMENSION_SETS))


def test_pair_side_is_pure_and_order_independent():
    from rtveval.vlm_judge import pair_side_swapped, unswap_winner
    s1 = pair_side_swapped(42, "clip-x", "clip-y")
    assert s1 == pair_side_swapped(42, "clip-y", "clip-x")  # order-free
    assert s1 == pair_side_swapped(42, "clip-x", "clip-y")  # pure
    # different seed reshuffles sides across many pairs (not all identical)
    sides = {pair_side_swapped(42, "a%d" % i, "b%d" % i) for i in range(64)}
    assert sides == {True, False}, "side stream degenerate"
    # unswap round-trips
    assert unswap_winner("A", swapped=False) == "first"
    assert unswap_winner("A", swapped=True) == "second"
    assert unswap_winner("B", swapped=True) == "first"
    assert unswap_winner("tie", swapped=True) is None
    print("  pair side: pure function of (seed, sorted pair); unswap correct")


def test_pair_schema_and_prompt():
    from rtveval.vlm_judge import build_pair_prompt, pair_schema
    schema = pair_schema(GENERATION_DIMENSIONS)
    dims = schema["properties"]["dimensions"]
    assert set(dims["required"]) == {"E6", "E7", "E8"}
    for d in dims["properties"].values():
        assert d["properties"]["winner"]["enum"] == ["A", "B", "tie"]
    p = build_pair_prompt(GENERATION_DIMENSIONS, 8, "boats", "trains")
    assert "boats" in p and "trains" in p and "may even be the same product" in p
    print("  pair mode: forced-choice schema, blinded comparative prompt")


def test_vbench_port_formulas():
    import numpy as np
    from rtveval.vbench_metrics import feature_consistency, temporal_flickering
    still = [np.full((8, 8, 3), 100, dtype=np.uint8)] * 10
    assert abs(temporal_flickering(still) - 1.0) < 1e-9
    flicky = [np.full((8, 8, 3), 100 + 40 * (i % 2), dtype=np.uint8)
              for i in range(10)]
    assert temporal_flickering(flicky) < temporal_flickering(still) - 0.1
    # consistency: stable embedding ~1.0, rotating embedding lower
    stable = feature_consistency(still, lambda f: np.array([1.0, 0.0]))
    rot = {"i": 0}
    def rot_fn(f):
        rot["i"] += 1
        a = rot["i"] * 0.35
        return np.array([np.cos(a), np.sin(a)])
    drifting = feature_consistency(still, rot_fn)
    assert stable > 0.999 and drifting < 0.9, (stable, drifting)
    assert temporal_flickering([still[0]]) is None  # too short: refuse
    print("  vbench port: flicker + consistency formulas behave; short "
          "clips refuse")


if __name__ == "__main__":
    for fn in [v for k, v in sorted(globals().items()) if k.startswith("test_")]:
        print(fn.__name__)
        fn()
    print("OK")
