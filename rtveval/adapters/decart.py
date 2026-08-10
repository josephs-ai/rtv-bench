"""Decart native adapter - Lucy 2.5, Lens P, V2V (FIXED duration).

Protocol as verified against the live service on 2026-08-10 (not guessed):

  - Endpoint: wss://api.decart.ai/v1/stream
  - Auth: `?api_key=` QUERY PARAMETER. The Authorization header is ignored -
    the upgrade succeeds with no auth at all, and validation happens at
    session level. Consequence: the URL contains the key, so no adapter log
    line may ever print the URL unredacted (see _redact).
  - Model: `&model=` query parameter. No session.start message, no ack.
  - Validation is active and specific: a bad key errors "Invalid API key",
    an unknown model errors "Invalid or unsupported model for streaming",
    a retired model errors "This model has been retired ...". A valid
    (key, model) pair produces silence: the stream is open, awaiting frames.
  - Region arrives in the upgrade response header `x-decart-rgn` (e.g. usw2).

Version resolution (hard rule 5): the server has no version handshake, but it
does actively reject unknown AND retired model ids - so an open stream is
server-side confirmation that the exact pinned id is being served. We record
`lucy-2.5#validated-open` plus the region header. The docs' `-latest` aliases
are exactly the trap rule 5 names; never use them here.

Catalog per docs.platform.decart.ai (2026-08-10): lucy-2.5 (V2V, 720p),
lucy-vton-3, lucy-restyle-2, oasis-3-preview, lucy-image-2. Input: MP4
H.264/VP8, 16:9 or 9:16, <=200 MB.
"""
import asyncio
import json
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote

import websockets

from .. import config
from .base import (Adapter, ConnectionInfo, DurationSemantics, StreamResult,
                   TimestampAuthority)
from .ws_common import StreamSession, make_refusal_matcher

PINNED_MODEL = "lucy-2.5"  # never "lucy-latest" (hard rule 5)

# How long silence-after-connect must last before we call the pair validated.
# Every observed rejection arrived well under 1 s; 2 s is conservative.
VALIDATION_SILENCE_S = 2.0

# Observed error vocabulary (live-verified), plus policy guesses to refine in
# the pilot per addendum Part 5.
FATAL_ERRORS = ("invalid api key", "invalid or unsupported model",
                "has been retired")
REFUSAL_PATTERNS = ("content policy", "moderation", "unsafe", "refused",
                    "not permitted", "blocked by safety")


def _redact(url: str, key: str) -> str:
    return url.replace(key, "<KEY>") if key else url


class DecartAdapter(Adapter):
    product_key = "lucy-2.5"
    lens = "P"
    semantics = DurationSemantics.FIXED

    def __init__(self, cfg: Optional[config.ProviderConfig] = None,
                 model: str = PINNED_MODEL):
        self.cfg = cfg or config.decart()
        self.model = model
        self.ws = None
        self.info: Optional[ConnectionInfo] = None
        self._refusals = make_refusal_matcher(REFUSAL_PATTERNS)

    def _url(self) -> str:
        return (self.cfg.base_url.replace("https://", "wss://")
                + "/v1/stream?api_key=%s&model=%s"
                % (quote(self.cfg.api_key.strip()), quote(self.model)))

    async def connect(self) -> ConnectionInfo:
        if not self.cfg.ready:
            raise RuntimeError("Decart config incomplete: set %s" % self.cfg.key_env)

        url = self._url()
        self.ws = await websockets.connect(url, max_size=32 * 1024 * 1024)

        # Silence = validated; an early message is a rejection to surface.
        try:
            raw = await asyncio.wait_for(self.ws.recv(), timeout=VALIDATION_SILENCE_S)
            msg = raw if isinstance(raw, str) else raw.decode("utf-8", "replace")
            await self.ws.close()
            self.ws = None
            raise RuntimeError("Decart rejected the session: %s"
                               % _redact(msg[:300], self.cfg.api_key))
        except asyncio.TimeoutError:
            pass  # open and silent - (key, model) validated by the server

        region = None
        resp = getattr(self.ws, "response", None)
        if resp is not None:
            region = resp.headers.get("x-decart-rgn")

        self.info = ConnectionInfo(
            product_key=self.product_key, lens=self.lens,
            # No version handshake exists; the server rejecting unknown and
            # retired ids makes an open stream the strongest available
            # confirmation that this exact id is served.
            resolved_version="%s#validated-open" % self.model,
            endpoint=_redact(url, self.cfg.api_key),
            timestamp_authority=TimestampAuthority.CAPTURE_BOUNDARY,
            region=region,
            advertised_fps=None,
            advertised_resolution="720p")
        return self.info

    def _classify(self, raw: Any) -> Tuple[str, Optional[Dict]]:
        if isinstance(raw, bytes):
            return "frame", {"nbytes": len(raw)}
        msg = json.loads(raw)
        t = msg.get("type", "")
        if t == "frame":
            return "frame", {"nbytes": len(msg.get("data", "")) * 3 // 4,
                             "width": msg.get("width"), "height": msg.get("height")}
        if t == "error":
            return "error", msg
        return "control", msg

    async def run(self, clip_path: Optional[str], prompt: str,
                  duration_intended_s: Optional[float],
                  condition_id: str) -> StreamResult:
        if self.ws is None or self.info is None:
            raise RuntimeError("connect() first")
        if clip_path is None or duration_intended_s is None:
            raise ValueError("V2V requires a source clip and intended duration")

        session = StreamSession(self.ws, self.info, self.semantics,
                                self._classify, self._refusals)

        async def send_request():
            # Prompt accompanies the stream; frame feed is pushed by the
            # orchestrator's feeder task, decoupled from measurement.
            await self.ws.send(json.dumps({"type": "prompt", "text": prompt}))

        return await session.run(send_request, duration_intended_s)

    async def close(self) -> None:
        if self.ws is not None:
            await self.ws.close()
            self.ws = None
