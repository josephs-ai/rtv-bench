"""Decart native adapter - Lucy 2.5, Lens P, V2V (FIXED duration).

Protocol note: the message vocabulary below (session_ack fields, frame framing)
is written against Decart's realtime websocket docs as understood pre-pilot and
MUST be confirmed during day-1 harness validation. All protocol assumptions sit
in this file; nothing downstream depends on them.

Version pinning (hard rule 5): we REQUEST `lucy-2.5` but RECORD whatever the
server handshake says it is serving. If the ack omits a version string, connect
fails loudly rather than writing an unverifiable row.
"""
import base64
import json
from typing import Any, Dict, Optional, Tuple

import websockets

from .. import config
from ..routing import V2V
from .base import (Adapter, ConnectionInfo, DurationSemantics, StreamResult,
                   TimestampAuthority)
from .ws_common import StreamSession, make_refusal_matcher

PINNED_MODEL = "lucy-2.5"  # never "lucy-latest"

# Grown from the pilot per addendum Part 5; these are starting guesses.
REFUSAL_PATTERNS = ("content policy", "moderation", "unsafe", "refused",
                    "not permitted", "blocked by safety")


class DecartAdapter(Adapter):
    product_key = "lucy-2.5"
    lens = "P"
    semantics = DurationSemantics.FIXED

    def __init__(self, cfg: Optional[config.ProviderConfig] = None):
        self.cfg = cfg or config.decart()
        self.ws = None
        self.info: Optional[ConnectionInfo] = None
        self._refusals = make_refusal_matcher(REFUSAL_PATTERNS)

    async def connect(self) -> ConnectionInfo:
        if not self.cfg.ready:
            raise RuntimeError("Decart config incomplete: set %s" % self.cfg.key_env)

        url = self.cfg.base_url.replace("https://", "wss://") + "/v1/stream"
        self.ws = await websockets.connect(
            url, additional_headers={"Authorization": "Bearer %s" % self.cfg.api_key},
            max_size=32 * 1024 * 1024)

        await self.ws.send(json.dumps({"type": "session.start",
                                       "model": PINNED_MODEL}))
        ack = json.loads(await self.ws.recv())

        served = ack.get("model") or ack.get("model_version")
        if not served:
            raise RuntimeError(
                "Decart session ack carries no model version - refusing to run "
                "an unverifiable row (hard rule 5). Ack keys: %s" % sorted(ack))
        if served != PINNED_MODEL:
            # Not fatal - but it must be the ROW's truth, and worth a loud log.
            print("WARNING: requested %s, server is serving %s" % (PINNED_MODEL, served))

        self.info = ConnectionInfo(
            product_key=self.product_key, lens=self.lens,
            resolved_version=str(served), endpoint=url,
            timestamp_authority=TimestampAuthority.CAPTURE_BOUNDARY,
            region=ack.get("region"),
            advertised_fps=ack.get("fps"),
            advertised_resolution=ack.get("resolution"))
        return self.info

    @staticmethod
    def _classify(raw: Any) -> Tuple[str, Optional[Dict]]:
        if isinstance(raw, bytes):  # binary frames: the video path
            return "frame", {"nbytes": len(raw)}
        msg = json.loads(raw)
        t = msg.get("type", "")
        if t == "frame":  # JSON-wrapped frame variant
            data = msg.get("data", "")
            return "frame", {"nbytes": len(data) * 3 // 4,
                             "width": msg.get("width"), "height": msg.get("height")}
        if t in ("error", "session.error", "moderation"):
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
            await self.ws.send(json.dumps({"type": "run.start", "prompt": prompt}))
            # Frame feed is pushed by the virtual-camera pipeline / a feeder
            # task in the orchestrator, not here: the adapter measures, the
            # feeder feeds, and neither blocks the other.

        return await session.run(send_request, duration_intended_s)

    async def close(self) -> None:
        if self.ws is not None:
            await self.ws.close()
            self.ws = None
