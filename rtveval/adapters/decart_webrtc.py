"""Decart adapter - Lucy 2.5, Lens P, on the DOCUMENTED signaling protocol.

The /v1/stream websocket is the signaling plane only; media is WebRTC,
peer-to-peer after negotiation. Protocol from docs.platform.decart.ai
(integrations/signaling-proxy-ws, 2026-08-10):

  client -> {"type": "offer", "sdp": ...}
            {"type": "ice-candidate", "candidate": {...}}
            {"type": "prompt", "prompt": ..., "enhance_prompt": bool}
            {"type": "set_image", "image_data": b64|null,
             "prompt": ..., "enhance_prompt": bool}   # reference image
             (verified in docs 2026-08-11; try-on is a documented use case)
  server -> {"type": "answer", "sdp": ...}
            {"type": "ice-candidate", ...}
            {"type": "session_id", "session_id": ...}
            {"type": "prompt_ack", "success": bool}
            {"type": "generation_tick", "seconds": n}   (usage/billing)
            {"type": "generation_ended", "reason": ...}

Auth: ?api_key= query (validated live earlier); &model= selects the model and
is server-validated (unknown and retired ids produce distinct errors), which
remains the version-of-record mechanism: an open, answering session confirms
the exact pinned id. Client-token expiry does NOT kill live sessions (docs:
"Expiration blocks new connections, but does not disconnect active realtime
sessions") - so no mid-soak reconnect logic exists here on purpose.

Frames arrive via aiortc track.recv -> CallbackSession.feed, the same capture
boundary as the Reactor adapter: post-decode, in-process, no bridge.
"""
import asyncio
import json
from typing import Optional
from urllib.parse import quote

from .. import config
from .base import (Adapter, ConnectionInfo, DurationSemantics, StreamResult,
                   TimestampAuthority)
from .callback_session import CallbackSession

PINNED_MODEL = "lucy-2.5"  # never lucy-latest (hard rule 5; docs confirm

# 720p30 per docs.platform.decart.ai/models/realtime/lucy-2.5
ADVERTISED_FPS = 30.0
ADVERTISED_RESOLUTION = "1280x720"

REFUSAL_MARKERS = ("content policy", "moderation", "unsafe", "refused",
                   "not permitted", "blocked by safety")


class DecartWebRTCAdapter(Adapter):
    product_key = "lucy-2.5"
    lens = "P"
    semantics = DurationSemantics.FIXED

    def __init__(self, cfg: Optional[config.ProviderConfig] = None,
                 model: str = PINNED_MODEL):
        self.cfg = cfg or config.decart()
        self.model = model
        self.ws = None
        self.pc = None
        self.info: Optional[ConnectionInfo] = None
        self.session: Optional[CallbackSession] = None
        self.session_id: Optional[str] = None
        self.generation_seconds = 0  # from generation_tick - the billing truth
        self._player = None
        self._signal_task: Optional[asyncio.Task] = None
        self._frame_task: Optional[asyncio.Task] = None

    def _url(self) -> str:
        return (self.cfg.base_url.replace("https://", "wss://")
                + "/v1/stream?api_key=%s&model=%s"
                % (quote(self.cfg.api_key.strip()), quote(self.model)))

    async def connect(self) -> ConnectionInfo:
        import websockets

        if not self.cfg.ready:
            raise RuntimeError("Decart config incomplete: set %s" % self.cfg.key_env)

        self.ws = await websockets.connect(self._url(), max_size=16 * 1024 * 1024)

        # Silence = (key, model) validated; an early message here is a
        # rejection (verified live: invalid key / invalid model / retired all
        # answer within 1s).
        try:
            raw = await asyncio.wait_for(self.ws.recv(), timeout=2.0)
            msg = raw if isinstance(raw, str) else raw.decode("utf-8", "replace")
            await self.ws.close()
            self.ws = None
            raise RuntimeError("Decart rejected the session: %s"
                               % msg[:300].replace(self.cfg.api_key.strip(), "<KEY>"))
        except asyncio.TimeoutError:
            pass

        region = None
        resp = getattr(self.ws, "response", None)
        if resp is not None:
            region = resp.headers.get("x-decart-rgn")

        self.info = ConnectionInfo(
            product_key=self.product_key, lens=self.lens,
            resolved_version="%s#validated-open" % self.model,
            endpoint="wss://api.decart.ai/v1/stream?api_key=<KEY>&model=%s" % self.model,
            timestamp_authority=TimestampAuthority.CAPTURE_BOUNDARY,
            region=region, advertised_fps=ADVERTISED_FPS,
            advertised_resolution=ADVERTISED_RESOLUTION)
        return self.info

    async def _negotiate(self, clip_path: str) -> None:
        """Documented flow: publish our track, offer over the ws, apply the
        answer, trickle ICE both ways."""
        from aiortc import RTCPeerConnection, RTCSessionDescription
        from aiortc.contrib.media import MediaPlayer

        self.pc = RTCPeerConnection()
        self._player = MediaPlayer(clip_path)
        self.pc.addTrack(self._player.video)
        # Decart's SDK connects a webcam+mic MediaStream; a video-only offer
        # negotiated fine but output died ~2s in (observed live, twice, while
        # echo at the same resolution ran full-length). Match the SDK's shape:
        # include an audio m-line (silence) alongside the video.
        from aiortc.mediastreams import AudioStreamTrack
        self.pc.addTrack(AudioStreamTrack())

        # Force H.264 for our upstream. Diagnosed live: with VP8 negotiated,
        # aiortc's software encoder produced ZERO packets for 6 s at 720p30
        # (sender stats), the server got no input to transform and halted
        # after ~2 s of startup output. aiortc's H.264 (libx264) keeps pace.
        # Decart accepts H.264 or VP8 (docs), so this changes only OUR side.
        from aiortc.rtcrtpsender import RTCRtpSender
        h264 = [c for c in RTCRtpSender.getCapabilities("video").codecs
                if c.mimeType.lower() == "video/h264"]
        if h264:
            for tr in self.pc.getTransceivers():
                if tr.sender and tr.sender.track and tr.sender.track.kind == "video":
                    tr.setCodecPreferences(h264)

        @self.pc.on("track")
        def on_track(track):
            if track.kind == "video":
                self._frame_task = asyncio.create_task(self._consume(track))

        offer = await self.pc.createOffer()
        await self.pc.setLocalDescription(offer)
        # aiortc completes ICE gathering during setLocalDescription (no
        # trickle on our side): one offer message carries everything.
        await self.ws.send(json.dumps({"type": "offer",
                                       "sdp": self.pc.localDescription.sdp}))

        # Wait for the answer. Server ICE candidates can arrive BEFORE the
        # answer - dropping them leaves the peer path half-built and media
        # dies seconds in (observed live: 3.6s of frames then stall). Buffer
        # them and apply after setRemoteDescription.
        answer_sdp = None
        pending_candidates = []
        deadline = asyncio.get_running_loop().time() + 20.0
        while answer_sdp is None:
            timeout = deadline - asyncio.get_running_loop().time()
            if timeout <= 0:
                raise TimeoutError("no SDP answer within 20s")
            raw = await asyncio.wait_for(self.ws.recv(), timeout=timeout)
            msg = json.loads(raw)
            t = msg.get("type")
            if t == "answer":
                answer_sdp = msg["sdp"]
            elif t == "ice-candidate":
                pending_candidates.append(msg.get("candidate") or {})
            elif t == "session_id":
                self.session_id = msg.get("session_id")
            elif t == "error":
                raise RuntimeError("signaling error before answer: %s" % msg)
        await self.pc.setRemoteDescription(
            RTCSessionDescription(sdp=answer_sdp, type="answer"))
        for cand in pending_candidates:
            await self._add_remote_candidate(cand)

    async def _consume(self, track) -> None:
        """Track frames -> session. Same post-decode capture boundary as the
        Reactor path."""
        while True:
            try:
                frame = await track.recv()
            except Exception:
                return
            if self.session is not None:
                arr = frame.to_ndarray(format="rgb24")
                if getattr(self, "frame_tap", None) is not None:
                    self.frame_tap(arr)
                self.session.feed(arr)

    async def _signal_loop(self) -> None:
        """Post-negotiation signaling: ticks, acks, ended, refusals."""
        import websockets as wslib

        try:
            while True:
                raw = await self.ws.recv()
                msg = json.loads(raw)
                t = msg.get("type")
                if t == "generation_tick":
                    self.generation_seconds = msg.get("seconds", self.generation_seconds)
                elif t == "ice-candidate":
                    await self._add_remote_candidate(msg.get("candidate") or {})
                elif t == "session_id":
                    self.session_id = msg.get("session_id")
                elif t == "generation_ended":
                    reason = str(msg.get("reason", ""))
                    if self.session is not None:
                        refusal = any(m in reason.lower() for m in REFUSAL_MARKERS)
                        self.session.feed_error("generation_ended: %s" % reason,
                                                refusal=refusal)
                    return
                elif t == "prompt_ack" and not msg.get("success", True):
                    if self.session is not None:
                        self.session.feed_error("prompt rejected", refusal=True)
                elif t == "error":
                    detail = json.dumps(msg)[:300]
                    if self.session is not None:
                        refusal = any(m in detail.lower() for m in REFUSAL_MARKERS)
                        self.session.feed_error(detail, refusal=refusal)
        except (wslib.ConnectionClosed, asyncio.CancelledError):
            return

    async def _add_remote_candidate(self, cand: dict) -> None:
        from aiortc import RTCIceCandidate
        from aiortc.sdp import candidate_from_sdp

        raw = cand.get("candidate") or ""
        if not raw:
            return
        try:
            ice = candidate_from_sdp(raw.removeprefix("candidate:"))
            ice.sdpMid = cand.get("sdpMid")
            ice.sdpMLineIndex = cand.get("sdpMLineIndex")
            await self.pc.addIceCandidate(ice)
        except Exception:
            pass  # non-fatal: aiortc usually completes from the answer alone

    async def run(self, clip_path: Optional[str], prompt: str,
                  duration_intended_s: Optional[float],
                  condition_id: str) -> StreamResult:
        if self.ws is None or self.info is None:
            raise RuntimeError("connect() first")
        if clip_path is None or duration_intended_s is None:
            raise ValueError("V2V requires a source clip and intended duration")

        self.session = CallbackSession(self.info, self.semantics)
        await self._negotiate(clip_path)
        self._signal_task = asyncio.create_task(self._signal_loop())

        if prompt:
            await self.ws.send(json.dumps({"type": "prompt", "prompt": prompt,
                                           "enhance_prompt": False}))

        return await self.session.run(duration_intended_s)

    def request_stop(self) -> None:
        if self.session is not None:
            self.session.request_stop()

    async def close(self) -> None:
        for task in (self._signal_task, self._frame_task):
            if task is not None:
                task.cancel()
        self._signal_task = self._frame_task = None
        if self._player is not None:
            try:
                self._player.video.stop()
            except Exception:
                pass
            self._player = None
        if self.pc is not None:
            await self.pc.close()
            self.pc = None
        if self.ws is not None:
            await self.ws.close()
            self.ws = None
