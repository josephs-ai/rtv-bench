"""Xmax native adapter - Xmax X2.0, Lens P, V2V (FIXED duration).

Deliberately a near-copy of DecartAdapter: same connect/run shape, same
capture-boundary stamping via StreamSession. Only the endpoint path, pinned
model id, and refusal vocabulary differ - which is the payoff of rule 2.
Protocol specifics await the day-1 key and docs (self-serve per plan sec 1).
"""
import json
from typing import Any, Dict, Optional, Tuple

from .. import config
from .base import (Adapter, ConnectionInfo, DurationSemantics, StreamResult,
                   TimestampAuthority)
from .ws_common import StreamSession, make_refusal_matcher

PINNED_MODEL = "xmax-x2.0"

REFUSAL_PATTERNS = ("content policy", "moderation", "refused", "risk control",
                    "sensitive content")


class XmaxAdapter(Adapter):
    product_key = "xmax-x2.0"
    lens = "P"
    semantics = DurationSemantics.FIXED

    def __init__(self, cfg: Optional[config.ProviderConfig] = None):
        self.cfg = cfg or config.xmax()
        self.ws = None
        self.info: Optional[ConnectionInfo] = None
        self._refusals = make_refusal_matcher(REFUSAL_PATTERNS)

    async def connect(self) -> ConnectionInfo:
        import websockets

        if not self.cfg.ready:
            raise RuntimeError("Xmax config incomplete: set %s and XMAX_BASE_URL "
                               "(key is self-serve - obtain day 1)" % self.cfg.key_env)

        url = self.cfg.base_url.replace("https://", "wss://") + "/v1/realtime"
        self.ws = await websockets.connect(
            url, additional_headers={"Authorization": "Bearer %s" % self.cfg.api_key},
            max_size=32 * 1024 * 1024)
        await self.ws.send(json.dumps({"type": "session.start", "model": PINNED_MODEL}))
        ack = json.loads(await self.ws.recv())

        served = ack.get("model") or ack.get("model_version")
        if not served:
            raise RuntimeError("Xmax ack carries no model version (hard rule 5). "
                               "Ack keys: %s" % sorted(ack))

        self.info = ConnectionInfo(
            product_key=self.product_key, lens=self.lens,
            resolved_version=str(served), endpoint=url,
            timestamp_authority=TimestampAuthority.CAPTURE_BOUNDARY,
            region=ack.get("region"), advertised_fps=ack.get("fps"),
            advertised_resolution=ack.get("resolution"))
        return self.info

    _classify = staticmethod(lambda raw: (
        ("frame", {"nbytes": len(raw)}) if isinstance(raw, bytes)
        else (lambda msg: (
            ("frame", {"nbytes": len(msg.get("data", "")) * 3 // 4,
                       "width": msg.get("width"), "height": msg.get("height")})
            if msg.get("type") == "frame"
            else ("error", msg) if msg.get("type") in ("error", "moderation")
            else ("control", msg)))(json.loads(raw))))

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

        return await session.run(send_request, duration_intended_s)

    async def close(self) -> None:
        if self.ws is not None:
            await self.ws.close()
            self.ws = None
