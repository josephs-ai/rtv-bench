"""Reactor adapter on the vendor's own SDK (reactor-sdk / aiortc).

Replaces the never-shipped websocket ReactorAdapter: the catalog descriptions
say WebRTC, the AUP says don't reverse the wire protocol, and vendor code
should own negotiation anyway.

- Version resolution: from the session response (get_session_info), which
  works for unlisted models (Happy Oyster). Hard rule 5 via
  providers/reactor_session.resolve_version.
- Frames: SDK frame callback -> CallbackSession.feed, stamped at entry.
- Input: publish_track with an aiortc MediaPlayer over the conformed clip
  (V2V / echo); text direction via send_command for text_directed models.
- ConnectionTimings (session_creation_ms / transport_connecting_ms) recorded
  for the run row - it is the SDK's own split of connect cost.
"""
from typing import Any, Dict, Optional

from .. import config
from ..providers.reactor_session import resolve_version
from .base import (Adapter, ConnectionInfo, DurationSemantics, StreamResult,
                   TimestampAuthority)
from .callback_session import CallbackSession

REFUSAL_MARKERS = ("content policy", "moderation", "flagged", "refused",
                   "prohibited", "safety")


class ReactorWebRTCAdapter(Adapter):
    lens = "M"

    def __init__(self, product_key: str, model_name: str,
                 semantics: DurationSemantics,
                 cfg: Optional[config.ProviderConfig] = None,
                 prompt_command: str = "prompt"):
        """`model_name` is the exact serving id (e.g. `reactor/echo`,
        `xmax/x2`, `reactor/lingbot-world-2`, `reactor/happy-oyster-director`)
        - from the probe or the vendor SDK, never guessed.
        `prompt_command` is the model's text-direction command name; confirmed
        per model in the pilot capability probe."""
        self.product_key = product_key
        self.model_name = model_name
        self.semantics = semantics
        self.cfg = cfg or config.reactor()
        self.prompt_command = prompt_command
        self.reactor = None
        self.info: Optional[ConnectionInfo] = None
        self.session: Optional[CallbackSession] = None
        self.timings: Optional[Dict[str, float]] = None
        self._player = None
        # Optional per-frame hook (e.g. the echo calibration's luminance
        # recorder). Runs in the dispatcher AFTER the session stamps.
        self.frame_tap = None

    def _dispatch_frame(self, frame) -> None:
        """The one callback the SDK ever sees. Registered BEFORE connect() -
        the transport only starts frame processing if a callback exists when
        the track event fires during connect; registering later means no
        frames, silently. Sessions come and go per run; this dispatcher is
        stable for the connection's life."""
        if self.session is not None:
            self.session.feed(frame)
        if self.frame_tap is not None:
            self.frame_tap(frame)

    async def connect(self) -> ConnectionInfo:
        from reactor_sdk import Reactor

        if not self.cfg.ready:
            raise RuntimeError("Reactor config incomplete: set %s and "
                               "REACTOR_BASE_URL" % self.cfg.key_env)

        # RTVEVAL_FORCE_TURN_TCP=1: keep ONLY the turns/tcp relay URI in the
        # fetched ICE list. aiortc uses the FIRST TURN uri per server entry -
        # on a UDP-blocked tunnel that is the dead turn:3478, so the working
        # TLS relay is never tried (verified live: allocation over :443
        # succeeds while every UDP probe dies). All Lens M media then rides
        # the same TCP relay: within-lens comparisons stay same-substrate,
        # and the floor calibration measures the same path the products use.
        import os
        if os.environ.get("RTVEVAL_FORCE_TURN_TCP") == "1":
            from reactor_sdk.transport import webrtc as _w
            if not getattr(_w, "_rtveval_tcp_patch", False):
                orig = _w._transform_ice_servers

                def tcp_only(response):
                    filtered = []
                    for entry in response.get("ice_servers", []):
                        uris = [u for u in entry.get("uris", [])
                                if "transport=tcp" in u]
                        if uris:
                            filtered.append({**entry, "uris": uris})
                    return orig({"ice_servers": filtered or
                                 response.get("ice_servers", [])})

                _w._transform_ice_servers = tcp_only
                _w._rtveval_tcp_patch = True
            self.turn_mode = "turn-tls-tcp-forced"
        else:
            self.turn_mode = "default"

        self.reactor = Reactor(self.model_name, api_key=self.cfg.api_key.strip(),
                               api_url=self.cfg.base_url)
        self.reactor.set_frame_callback(self._dispatch_frame)  # BEFORE connect
        await self.reactor.connect()

        raw = self._session_info_dict()
        version = resolve_version(raw) if raw else "unknown"
        t = None
        try:
            ct = self.reactor._connection_timings  # SDK exposes no public getter yet
            if ct is not None:
                t = {"session_creation_ms": ct.session_creation_ms,
                     "transport_connecting_ms": ct.transport_connecting_ms,
                     "total_ms": ct.total_ms}
        except AttributeError:
            pass
        self.timings = t

        self.info = ConnectionInfo(
            product_key=self.product_key, lens=self.lens,
            resolved_version=version, endpoint=self.cfg.base_url,
            timestamp_authority=TimestampAuthority.CAPTURE_BOUNDARY,
            region=(raw or {}).get("cluster"))
        return self.info

    def _session_info_dict(self) -> Optional[Dict[str, Any]]:
        get = getattr(self.reactor, "get_session_info", None)
        if get is None:
            return None
        info = get()
        if info is None:
            return None
        if isinstance(info, dict):
            return info
        # dataclass-ish: pull the fields resolve_version needs
        out: Dict[str, Any] = {}
        for field in ("model", "server_info", "cluster", "session_id"):
            v = getattr(info, field, None)
            if v is not None:
                out[field] = v if isinstance(v, (dict, str)) else getattr(v, "__dict__", str(v))
        return out

    async def _wait_ready(self, timeout_s: float = 90.0) -> None:
        """connect() returns before the transport reports CONNECTED; the SDK
        flips to READY asynchronously and publish/send_command require it.
        90 s default covers GPU pod scheduling; echo is seconds."""
        import asyncio

        from reactor_sdk import ReactorStatus

        deadline = asyncio.get_running_loop().time() + timeout_s
        while self.reactor.get_status() != ReactorStatus.READY:
            if asyncio.get_running_loop().time() > deadline:
                raise TimeoutError(
                    "Reactor session for %s not READY within %.0f s (status %s)"
                    % (self.model_name, timeout_s, self.reactor.get_status()))
            await asyncio.sleep(0.05)

    def _sendonly_video_track_name(self) -> str:
        caps = self.reactor.get_capabilities() or {}
        tracks = caps.get("tracks", []) if isinstance(caps, dict) else []
        for t in tracks:
            if t.get("kind") == "video" and t.get("direction") == "sendonly":
                return t["name"]
        raise RuntimeError(
            "%s declares no sendonly video track - it does not accept video "
            "input (tracks: %s). A V2V run against it is a category error."
            % (self.model_name, [t.get("name") for t in tracks]))

    async def run(self, clip_path: Optional[str], prompt: str,
                  duration_intended_s: Optional[float],
                  condition_id: str) -> StreamResult:
        if self.reactor is None or self.info is None:
            raise RuntimeError("connect() first")
        if self.semantics is DurationSemantics.OPEN_ENDED and duration_intended_s is not None:
            raise ValueError("open-ended stream: duration is the orchestrator's "
                             "stop signal, not a run parameter")

        await self._wait_ready()

        self.session = CallbackSession(self.info, self.semantics)

        @self.reactor.on_error
        def _on_error(err):  # SDK error event -> session
            detail = str(err)
            refusal = any(m in detail.lower() for m in REFUSAL_MARKERS)
            self.session.feed_error(detail, refusal=refusal)

        if clip_path is not None:
            from aiortc.contrib.media import MediaPlayer

            # The publish name comes from the model's own capabilities (the
            # sendonly video track - echo calls it "webcam"); hardcoding a name
            # fails with "no transceiver".
            name = self._sendonly_video_track_name()
            # aiortc handles pacing from the file's own timestamps; the clip is
            # already conformed to the product's input spec (reel/conform.py).
            self._player = MediaPlayer(clip_path)
            await self.reactor.publish_track(name, self._player.video)

        if prompt:
            await self.reactor.send_command(self.prompt_command, {"text": prompt})

        return await self.session.run(duration_intended_s)

    def request_stop(self) -> None:
        if self.session is not None:
            self.session.request_stop()

    async def close(self) -> None:
        if self._player is not None:
            try:
                self._player.video.stop()
            except Exception:
                pass
            self._player = None
        if self.reactor is not None:
            try:
                await self.reactor.disconnect()
            finally:
                self.reactor = None
