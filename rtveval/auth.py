"""One token-refresh path for every provider.

Decart mints a short-lived JWT (~10 s) from the api_key; Reactor mints a
~6 h JWT via POST /tokens. Same lifecycle, wildly different TTLs, so the logic
belongs in one place rather than duplicated per adapter with two different bugs.

Design decisions that matter:

- **The mint function reports its own TTL.** Reactor's /tokens returns
  `expires_at` (epoch); Decart's is fixed. Either way `mint()` returns
  (token, ttl_seconds) and TokenManager tracks expiry on a MONOTONIC clock -
  never epoch - so a wall-clock adjustment mid-study can't make a live token
  look expired or an expired one look live.
- **Refresh is single-flight.** A 10 s Decart token under a few concurrent
  callers must mint once, not once per caller. An async lock guarantees the
  losers await the winner's result.
- **Refresh happens before expiry, by a skew margin** sized to cover the mint
  round-trip plus clock jitter. A token that expires mid-request is a failure
  the caller can't distinguish from a real auth error.

Transports that carry the token IN the connection (Decart's api_key/JWT in the
wss URL) cannot swap it on a live socket: for those, a refresh means the
adapter reconnects. TokenManager surfaces `seconds_remaining()` so the adapter
can decide to reconnect a long run (the 10-min soak) before its token lapses.
The exact Decart mid-stream mechanism (reconnect vs in-band re-auth) is a
pilot-confirm item - not fabricated here.
"""
import asyncio
import time
from typing import Awaitable, Callable, NamedTuple, Optional, Tuple

# Cover the mint round-trip + clock jitter. For a 10 s token this is large
# relative to TTL by necessity - it forces a refresh at ~7.5 s, which is
# correct: better an early refresh than a request that lands post-expiry.
DEFAULT_SKEW_S = 2.5

MintFn = Callable[[], Awaitable[Tuple[str, float]]]  # -> (token, ttl_seconds)


class _Token(NamedTuple):
    value: str
    expires_at_mono: float  # monotonic deadline


class TokenManager:
    def __init__(self, mint: MintFn, name: str = "token",
                 refresh_skew_s: float = DEFAULT_SKEW_S,
                 clock: Callable[[], float] = time.monotonic):
        self._mint = mint
        self.name = name
        self._skew = refresh_skew_s
        self._clock = clock
        self._token: Optional[_Token] = None
        self._lock = asyncio.Lock()
        self.mint_count = 0  # observability: how often we actually minted

    def _fresh(self) -> bool:
        return (self._token is not None
                and self._clock() + self._skew < self._token.expires_at_mono)

    def seconds_remaining(self) -> float:
        """Time until the CURRENT token lapses (ignoring skew). <=0 if none/expired.
        Adapters use this to reconnect a long run before its token dies."""
        if self._token is None:
            return 0.0
        return max(0.0, self._token.expires_at_mono - self._clock())

    async def bearer(self) -> str:
        """A valid token, refreshing if within the skew of expiry.
        Single-flight: concurrent callers during a refresh share one mint."""
        if self._fresh():
            return self._token.value
        async with self._lock:
            # Re-check under the lock: a concurrent caller may have refreshed.
            if self._fresh():
                return self._token.value
            token, ttl_s = await self._mint()
            if ttl_s <= self._skew:
                # A TTL at or under the skew can never satisfy _fresh() and
                # would loop. Surface it rather than spin.
                raise ValueError(
                    "%s: minted TTL %.1fs <= refresh skew %.1fs - lower the skew "
                    "or the token is unusably short" % (self.name, ttl_s, self._skew))
            self._token = _Token(token, self._clock() + ttl_s)
            self.mint_count += 1
            return self._token.value

    def invalidate(self) -> None:
        """Force the next bearer() to re-mint - e.g. after a 401 that slipped
        through the skew, or a server-side revocation."""
        self._token = None


def ttl_from_expires_at(expires_at_epoch: float,
                        now_epoch: Callable[[], float] = time.time) -> float:
    """Convert a server `expires_at` (epoch seconds) to a TTL at mint time.
    Used by mint functions so TokenManager only ever sees TTLs, keeping all
    deadline math on the monotonic clock."""
    return max(0.0, expires_at_epoch - now_epoch())
