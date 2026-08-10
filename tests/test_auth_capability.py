"""Token lifecycle, session version resolution, interaction-contract gate."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rtveval import auth, capability
from rtveval.providers import reactor_session


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


# --- token lifecycle ---------------------------------------------------------

def test_refreshes_only_near_expiry():
    clock = FakeClock()
    calls = {"n": 0}

    async def mint():
        calls["n"] += 1
        return "tok-%d" % calls["n"], 10.0  # 10 s TTL, like Decart

    tm = auth.TokenManager(mint, refresh_skew_s=2.5, clock=clock)

    async def go():
        t1 = await tm.bearer()          # mints
        clock.advance(5.0)
        t2 = await tm.bearer()          # still fresh (5s left > 2.5 skew)
        clock.advance(3.0)              # 2s left < skew -> refresh
        t3 = await tm.bearer()
        return t1, t2, t3

    t1, t2, t3 = asyncio.run(go())
    assert t1 == t2 == "tok-1", (t1, t2)
    assert t3 == "tok-2", t3
    assert calls["n"] == 2
    print("  10s token: 1 mint held across 5s, refreshed once near expiry")


def test_single_flight_under_concurrency():
    clock = FakeClock()
    calls = {"n": 0}

    async def mint():
        calls["n"] += 1
        await asyncio.sleep(0.02)  # simulate mint latency
        return "tok-%d" % calls["n"], 10.0

    tm = auth.TokenManager(mint, clock=clock)

    async def go():
        return await asyncio.gather(*[tm.bearer() for _ in range(8)])

    toks = asyncio.run(go())
    assert set(toks) == {"tok-1"} and calls["n"] == 1
    print("  8 concurrent callers during a cold mint -> single mint, one token")


def test_reactor_6h_vs_decart_10s_same_path():
    clock = FakeClock()

    async def go():
        rc = {"n": 0}

        async def reactor_mint():
            rc["n"] += 1
            return "r", 21600.0  # 6h

        dc = {"n": 0}

        async def decart_mint():
            dc["n"] += 1
            return "d-%d" % dc["n"], 10.0

        r = auth.TokenManager(reactor_mint, clock=clock)
        d = auth.TokenManager(decart_mint, clock=clock)
        # Over 30s: reactor mints once, decart several times - one code path.
        for _ in range(30):
            await r.bearer()
            await d.bearer()
            clock.advance(1.0)
        return r.mint_count, d.mint_count

    rn, dn = asyncio.run(go())
    assert rn == 1 and dn >= 3, (rn, dn)
    print("  same lifecycle: Reactor minted %dx, Decart %dx over 30s" % (rn, dn))


def test_ttl_at_or_below_skew_raises():
    async def mint():
        return "x", 2.0  # <= default skew 2.5

    tm = auth.TokenManager(mint, refresh_skew_s=2.5)
    try:
        asyncio.run(tm.bearer())
        raise AssertionError("unusably short TTL accepted")
    except ValueError as e:
        print("  TTL <= skew surfaced, not spun: %s" % str(e)[:60])


def test_seconds_remaining_drives_reconnect():
    clock = FakeClock()

    async def mint():
        return "tok", 10.0

    tm = auth.TokenManager(mint, clock=clock)
    asyncio.run(tm.bearer())
    assert abs(tm.seconds_remaining() - 10.0) < 1e-9
    clock.advance(7.0)
    assert abs(tm.seconds_remaining() - 3.0) < 1e-9
    print("  seconds_remaining tracks the live token for reconnect timing")


# --- session version resolution ---------------------------------------------

def test_version_from_session_response():
    # Shape as returned live by POST /sessions (2026-08-10).
    resp = {"session_id": "abc", "model": {"name": "reactor/happy-oyster-director",
            "version": "0.0.0"},
            "server_info": {"server_version": "1.20260805.20969"},
            "cluster": "sup.us-east"}
    v = reactor_session.resolve_version(resp)
    assert v == "0.0.0@1.20260805.20969", v
    print("  unlisted-model version resolved from session: %s" % v)


def test_ttl_from_expires_at():
    # expires_at 100s in the future -> ~100s TTL
    ttl = auth.ttl_from_expires_at(5000.0, now_epoch=lambda: 4900.0)
    assert abs(ttl - 100.0) < 1e-9
    # already past -> clamped to 0, never negative
    assert auth.ttl_from_expires_at(4900.0, now_epoch=lambda: 5000.0) == 0.0
    print("  expires_at -> TTL, clamped at 0")


# --- interaction-contract gate ----------------------------------------------

def test_same_contract_rankable():
    c = capability.assert_common_contract(["lucy-2.5", "xmax-x2.0"])
    assert c == "v2v_transform"
    print("  Lucy + Xmax share v2v_transform: rankable")


def test_cross_contract_ranking_refused():
    try:
        capability.assert_common_contract(["lingbot-world-2", "happy-oyster"])
        raise AssertionError("cross-contract ranking allowed")
    except capability.ContractViolation as e:
        assert "not performing the same task" in str(e)
        print("  LingBot(movement) vs Happy Oyster(text): ranking refused")


def test_generation_ranking_plan_splits():
    plan = capability.generation_ranking_plan(["lingbot-world-2", "happy-oyster"])
    assert not plan["single_ranking"]
    assert len(plan["groups"]) == 2
    assert "no ranking is made across groups" in plan["note"]
    print("  generation cohort splits into %d contract groups, no cross-rank"
          % len(plan["groups"]))

    # If PixVerse lands (text-directed), it groups WITH Happy Oyster.
    plan2 = capability.generation_ranking_plan(
        ["happy-oyster", "pixverse-r1", "lingbot-world-2"])
    groups = plan2["groups"]
    assert set(groups["text_directed"]) == {"happy-oyster", "pixverse-r1"}
    assert groups["movement_driven"] == ["lingbot-world-2"]
    print("  with PixVerse: text group {happy-oyster, pixverse}, movement {lingbot}")


def test_probe_record_flags_mismatch():
    ok = capability.probe_record("happy-oyster", "text_directed", True, "took G7 steer")
    assert ok.matches_declared and ok.accepts_text_steer
    bad = capability.probe_record("lingbot-world-2", "text_directed", True,
                                  "unexpectedly accepted text")
    assert not bad.matches_declared  # declared movement_driven, probe says text
    print("  probe record confirms match / surfaces mismatch vs declared")


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
            traceback.print_exc(limit=3)
    print("\n%d/%d passed" % (len(tests) - failed, len(tests)))
    sys.exit(1 if failed else 0)
