"""The five orchestrator constraints, each tested against its failure mode."""
import asyncio
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from rtveval.adapters.base import (Adapter, ConnectionInfo, DurationSemantics,
                                   FrameEvent, StopReason, StreamResult,
                                   TimestampAuthority)
from rtveval.orchestrator import health, runner
from rtveval.orchestrator.queue import RoundQueue, RunSpec, build_rounds
from rtveval.orchestrator.spend import CapExceeded, SpendCap, estimate_max_cost_usd

PRODUCTS = ["lucy-2.5", "lingbot-world-2", "happy-oyster"]


def tmpfile(name):
    d = tempfile.mkdtemp(prefix="orch-test-")
    return os.path.join(d, name)


# --- 1. round-based queue ---------------------------------------------------

def test_rounds_gate_fast_products():
    """A fast-failing product must not start run n+1 before slower ones finish n."""
    rounds = build_rounds("B", PRODUCTS, "C0", n_rounds=5)
    q = RoundQueue(rounds, tmpfile("journal.jsonl"))

    order = []
    for spec in q.pending():
        order.append((spec.product_key, spec.round_index))
        q.mark_done(spec.run_id)

    seen_round = {}
    for product, r in order:
        prev = seen_round.get(product, -1)
        assert r == prev + 1, (product, r, prev)
        seen_round[product] = r
        # nothing may reach round r while any product is behind r-1
        assert all(r - v <= 1 for v in seen_round.values()), (order,)
    print("  strict round order held across %d slots" % len(order))


def test_truncation_leaves_balanced_n():
    rounds = build_rounds("B", PRODUCTS, "C0", n_rounds=100)
    path = tmpfile("journal.jsonl")
    q = RoundQueue(rounds, path)

    # simulate dying at 4am: 181 slots done out of 300
    for i, spec in enumerate(q.pending()):
        if i >= 181:
            break
        q.mark_done(spec.run_id)

    n = q.balanced_n()
    assert len(set(n.values())) == 1, n  # identical N per product
    assert q.completed_rounds() == 60 and list(n.values())[0] == 60
    print("  died mid-round-61: balanced N=%d for all (not 300/300/90)"
          % list(n.values())[0])

    # resume from journal: nothing redone
    q2 = RoundQueue(rounds, path)
    remaining = sum(1 for _ in q2.pending())
    assert remaining == 300 - 181
    print("  resume from journal: %d slots remain, none repeated" % remaining)


def test_projection_suggests_uniform_reduction():
    rounds = build_rounds("B", PRODUCTS, "C0", n_rounds=100)
    q = RoundQueue(rounds, tmpfile("j.jsonl"))
    for i, spec in enumerate(q.pending()):
        if i >= 120:
            break
        q.mark_done(spec.run_id)
    p = q.project(seconds_per_round=105.0, seconds_remaining=3600.0)
    assert not p["will_finish"] and p["suggested_truncation"] == 40 + 34
    print("  projection: %d/%d rounds done, %d affordable -> truncate at %d (uniform)"
          % (p["rounds_done"], p["rounds_total"], p["rounds_affordable"],
             p["suggested_truncation"]))


# --- 2. spend reservations ---------------------------------------------------

def test_spend_reserves_before_launch():
    cap = SpendCap(10.0, tmpfile("spend.jsonl"))
    cap.reserve("r1", 6.0)  # hung run: reservation held, never reconciled...
    try:
        cap.reserve("r2", 6.0)
        raise AssertionError("second reservation must be refused")
    except CapExceeded as e:
        print("  hung run holds $6.00; next launch refused: %s" % e)

    cap.reconcile("r1", 2.5)  # actual cost lower
    cap.reserve("r2", 6.0)  # now fits
    s = cap.state()
    assert s.actual_usd == 2.5 and s.reserved_usd == 6.0
    print("  reconcile to actual $2.50 -> headroom restored, r2 launched")


def test_spend_journal_replays_open_reservations():
    path = tmpfile("spend.jsonl")
    cap = SpendCap(10.0, path)
    cap.reserve("r1", 4.0)
    cap.reserve("r2", 3.0)
    cap.reconcile("r1", 1.0)
    # crash; new process
    cap2 = SpendCap(10.0, path)
    s = cap2.state()
    assert s.reserved_usd == 3.0 and s.actual_usd == 1.0
    print("  crash-replay: open $3.00 reservation survives as its maximum")


def test_open_ended_cost_bound_is_the_kill_timer():
    est = estimate_max_cost_usd(None, usd_per_second=0.02, wall_clock_kill_s=90.0)
    assert abs(est - 1.8) < 1e-9
    print("  open-ended: max cost = kill timer x rate = $%.2f" % est)


# --- 3. retry keyed to E only ------------------------------------------------

def _row(outcome, is_retry=False, adjudicated=None, needs_review=False):
    return runner.RunRow(
        run_id="B-x-C0-r0001", attempt=2 if is_retry else 1, is_retry=is_retry,
        product_key="x", product_version="v1", lens="P", campaign="B",
        condition_id="C0", round_index=1, timestamp_utc="2026-08-10T03:00:00Z",
        outcome=outcome, outcome_reasons=[], e_evidence=[],
        needs_review=needs_review, adjudicated=adjudicated)


def test_denominator_rule():
    rows = [
        _row("S"), _row("F"), _row("T"), _row("R"),
        _row("E"),                       # confirmed E original: excluded
        _row("S", is_retry=True),        # retry after the E: excluded, even though S
        _row("F", needs_review=True),    # ambiguous, unadjudicated: counted, as F
        _row("F", needs_review=True, adjudicated="E"),  # human overturned: excluded
        _row("S", is_retry=True),        # retry of the adjudicated-E slot: excluded
    ]
    denom = runner.reliability_denominator(rows)
    assert len(denom) == 5, len(denom)
    t = runner.tally(rows)
    assert t == {"N": 5, "S": 1, "D": 0, "F": 2, "T": 1, "R": 1}, t
    print("  denominator: originals minus confirmed E = %d; retries never counted; "
          "successful retry after E did not become a success" % t["N"])


def test_never_retry_the_measurement():
    for outcome in ("F", "T", "R", "S", "D"):
        assert not runner.should_retry(outcome, needs_review=False, attempt=1), outcome
    assert runner.should_retry("E", False, 1)
    assert runner.should_retry("F", True, 1)  # ambiguous transport-F: data recovery
    assert not runner.should_retry("E", False, 3)  # cap
    print("  F/T/R never retried; E and ambiguous-transport retried, capped at %d"
          % runner.MAX_ATTEMPTS_PER_SLOT)


# --- 4. positive-control health check ----------------------------------------

def test_playhead_catches_frozen_source():
    frozen = np.full((720, 1280), 128, dtype=np.uint8)
    r = health.playhead_check(lambda: frozen.copy(), _sleep=lambda s: None)
    assert not r.ok and "FROZEN" in r.detail
    print("  frozen vcam (exists, readable, identical): FAILED - %s" % r.detail)

    frames = [np.random.default_rng(i).integers(0, 255, (720, 1280), dtype=np.uint8)
              for i in range(2)]
    it = iter(frames)
    r = health.playhead_check(lambda: next(it), _sleep=lambda s: None)
    assert r.ok
    print("  advancing source: passed (%s)" % r.detail)


# --- 5. E-adjudication -------------------------------------------------------

def _mk_result(stop_reason, n_events=100):
    info = ConnectionInfo("x", "P", "v1", "wss://x",
                          TimestampAuthority.CAPTURE_BOUNDARY)
    events = [FrameEvent(100.0 + i / 30.0, i, 1000) for i in range(n_events)]
    return StreamResult(info=info, events=events, request_clock=99.9,
                        stop_clock=100.0 + n_events / 30.0, stop_reason=stop_reason,
                        duration_intended_s=15.0,
                        semantics=DurationSemantics.FIXED, error_detail="boom")


def _evidence(failed):
    c = health.CheckResult("control_ping", not failed,
                           "unreachable" if failed else "ok", 0.0, "2026-08-10T03:00:00Z")
    return health.RigEvidence(checks=[c])


def test_ambiguous_defaults_to_product_failure():
    from rtveval.classify import classify
    result = _mk_result(StopReason.TRANSPORT_ERROR)
    cls = classify(result)
    outcome, reasons, evidence, review = runner.resolve_outcome(
        cls, result, _evidence(failed=False))
    assert outcome == "F" and review and not evidence
    print("  transport error + healthy rig: F, queued for review - ambiguity "
          "never improves a number")


def test_positive_evidence_makes_E():
    from rtveval.classify import classify
    result = _mk_result(StopReason.TRANSPORT_ERROR)
    outcome, reasons, evidence, review = runner.resolve_outcome(
        classify(result), result, _evidence(failed=True))
    assert outcome == "E" and evidence and not review
    print("  transport error + failed control ping: auto-E on positive evidence")


def test_refusal_immune_to_rig_state():
    from rtveval.classify import classify
    result = _mk_result(StopReason.REFUSED, n_events=0)
    outcome, _, _, _ = runner.resolve_outcome(
        classify(result), result, _evidence(failed=True))
    assert outcome == "R"
    print("  refusal stays R even with rig evidence - a policy response arrived")


def test_adjudication_via_journal():
    path = tmpfile("runs.jsonl")
    j = runner.RunJournal(path)
    row = _row("F", needs_review=True)
    j.append(row)
    j.append_adjudication(row.run_id, row.attempt, "E", reviewer="joseph",
                          note="wifi dropped, control ping log confirms")
    loaded = j.load()
    assert loaded[0].effective_outcome == "E" and not loaded[0].needs_review
    assert runner.tally(loaded)["N"] == 0
    print("  journal adjudication F->E: excluded from denominator, original row intact")


def test_rows_carry_utc():
    row = _row("S")
    assert row.timestamp_utc.endswith("Z") and "T" in row.timestamp_utc
    print("  wall-clock UTC on every row: %s" % row.timestamp_utc)


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
            print("  FAIL: %s: %s" % (type(e).__name__, e))
            traceback.print_exc(limit=3)
    print("\n%d/%d passed" % (len(tests) - failed, len(tests)))
    sys.exit(1 if failed else 0)
