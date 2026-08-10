"""Reactor adapter - Lens M, serving LingBot-World 2 and Happy Oyster
(generation, OPEN_ENDED), plus any dual-routed model for the bridge measurement.

Version resolution (hard rule 5): Reactor serves other vendors' models on its
own GPUs with its own config, so the row's version is *whatever Reactor's
catalog reports for the served model at connect time* - `lingbot-world-2@r47`
tells you more than `lingbot-world-2`, and if Reactor bumps the served build
mid-study, connect-time resolution puts the divergence in the rows where the
analysis can segment on it.

Duration semantics: generation models run until stopped. There is no intended
duration, `run()` accepts None, and a normal end is exactly one thing: the
orchestrator's stop signal. Everything else is F or R.
"""
import json
from typing import Any, Dict, Optional, Tuple

from .. import config
from ..providers import reactor as catalog
from .base import (Adapter, ConnectionInfo, DurationSemantics, StreamResult,
                   TimestampAuthority)
from .ws_common import StreamSession, make_refusal_matcher

REFUSAL_PATTERNS = ("content policy", "moderation", "flagged", "refused",
                    "prohibited content", "safety system")


class ReactorAdapter(Adapter):
    lens = "M"
    semantics = DurationSemantics.OPEN_ENDED

    def __init__(self, product_key: str, catalog_model_id: str,
                 cfg: Optional[config.ProviderConfig] = None,
                 semantics: DurationSemantics = DurationSemantics.OPEN_ENDED):
        """`catalog_model_id` comes from the probe (data/reactor-catalog.json),
        never guessed. `semantics` is overridable because a dual-routed V2V
        model (the sec 2.1 bridge) is FIXED even when served by Reactor."""
        self.product_key = product_key
        self.catalog_model_id = catalog_model_id
        self.semantics = semantics
        self.cfg = cfg or config.reactor()
        self.ws = None
        self.info: Optional[ConnectionInfo] = None
        self._refusals = make_refusal_matcher(REFUSAL_PATTERNS)

    async def _resolve_version(self) -> Dict[str, Any]:
        """Look the model up in the live catalog NOW - not in a cached probe
        result. The whole point is catching mid-study drift."""
        import asyncio
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, lambda: catalog.fetch_catalog(self.cfg.base_url, self.cfg.api_key))
        for entry in result["entries"]:
            if catalog.entry_id(entry) == self.catalog_model_id:
                return entry if isinstance(entry, dict) else {"id": entry}
        raise RuntimeError(
            "model %r no longer in the Reactor catalog - it was there at probe "
            "time. Halt and re-probe before running anything." % self.catalog_model_id)

    async def connect(self) -> ConnectionInfo:
        import websockets

        if not self.cfg.ready:
            raise RuntimeError("Reactor config incomplete: set %s and REACTOR_BASE_URL"
                               % self.cfg.key_env)

        entry = await self._resolve_version()
        # Prefer an explicit build/revision; fall back to the id itself, which
        # is still connect-time truth rather than config echo.
        version = str(entry.get("version") or entry.get("build")
                      or entry.get("revision") or catalog.entry_id(entry))

        url = self.cfg.base_url.replace("https://", "wss://") + "/v1/stream"
        self.ws = await websockets.connect(
            url, additional_headers={"Authorization": "Bearer %s" % self.cfg.api_key},
            max_size=32 * 1024 * 1024)
        await self.ws.send(json.dumps({"type": "session.start",
                                       "model": self.catalog_model_id}))
        ack = json.loads(await self.ws.recv())

        self.info = ConnectionInfo(
            product_key=self.product_key, lens=self.lens,
            resolved_version=version, endpoint=url,
            timestamp_authority=TimestampAuthority.CAPTURE_BOUNDARY,
            region=ack.get("region"),
            advertised_fps=ack.get("fps") or entry.get("fps"),
            advertised_resolution=ack.get("resolution") or entry.get("resolution"))
        return self.info

    @staticmethod
    def _classify(raw: Any) -> Tuple[str, Optional[Dict]]:
        if isinstance(raw, bytes):
            return "frame", {"nbytes": len(raw)}
        msg = json.loads(raw)
        t = msg.get("type", "")
        if t == "frame":
            return "frame", {"nbytes": len(msg.get("data", "")) * 3 // 4,
                             "width": msg.get("width"), "height": msg.get("height")}
        if t in ("error", "moderation", "policy"):
            return "error", msg
        return "control", msg

    async def run(self, clip_path: Optional[str], prompt: str,
                  duration_intended_s: Optional[float],
                  condition_id: str) -> StreamResult:
        if self.ws is None or self.info is None:
            raise RuntimeError("connect() first")
        if self.semantics is DurationSemantics.OPEN_ENDED and duration_intended_s is not None:
            # The orchestrator decides when to stop and calls request_stop();
            # passing a duration here would smuggle FIXED semantics back in.
            raise ValueError("open-ended stream: duration is the orchestrator's "
                             "stop signal, not a run parameter")

        self.session = StreamSession(self.ws, self.info, self.semantics,
                                     self._classify, self._refusals)

        async def send_request():
            await self.ws.send(json.dumps({"type": "run.start", "prompt": prompt}))

        return await self.session.run(send_request, duration_intended_s)

    def request_stop(self) -> None:
        """Exposed for the orchestrator - the normal end of an open-ended run."""
        if getattr(self, "session", None):
            self.session.request_stop()

    async def close(self) -> None:
        if self.ws is not None:
            await self.ws.close()
            self.ws = None
