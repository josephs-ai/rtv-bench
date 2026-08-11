#!/usr/bin/env python3
"""World-model side-by-side: LingBot-World 2 (Ant) vs Happy Oyster (Alibaba).

    .venv/bin/python tools/worlds_ab.py

Two panes, two modes each:
  Director - type a prompt (LingBot: set_prompt live steer; HO: create_world)
  WASD     - drive the world (LingBot: set_move_*/set_look_* on the same
             session; HO: reconnects to the -adventure model, hold-style
             move commands resent while keys are held)

Browser cannot speak Reactor - this bridge runs the proven Python adapters
(TURN-TCP relay fix included) and relays JPEG frames to the page over a
websocket. Curiosity tool, NOT a measurement.
"""
import asyncio
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.environ.setdefault("RTVEVAL_FORCE_TURN_TCP", "1")

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PAGE = os.path.join(REPO, "tools", "xmax_browser", "worlds_ab.html")

PANES = {
    0: {"key": "lingbot", "director_model": "reactor/lingbot-world-2",
        "wasd_model": "reactor/lingbot-world-2"},
    1: {"key": "happy-oyster", "director_model": "reactor/happy-oyster-director",
        "wasd_model": "reactor/happy-oyster-adventure"},
}
DEFAULT_PROMPTS = {
    # lingbot is i2v: the default prompt must CONTINUE the seed image
    # (landscape + wooden structure) - dry-run finding #2
    0: "a quiet landscape with a wooden structure under a hazy sky, "
       "gentle wind, slow drifting clouds",
    1: "a sunlit coastal village with cobblestone streets, explorable",
}
ALLOWED_COMMANDS = {
    0: {"set_prompt", "set_move_longitudinal", "set_move_lateral",
        "set_look_horizontal", "set_look_vertical", "set_rotation_speed_deg",
        "pause", "resume", "reset"},
    1: {"create_world", "move", "get_state", "end_travel"},
}


class Pane:
    def __init__(self, idx, ws_broadcast, log):
        self.idx = idx
        self.cfg = PANES[idx]
        self.mode = "director"
        self.adapter = None
        self.broadcast = ws_broadcast
        self.log = log
        self.last_frame_at = 0.0
        self.frames = 0
        self._lock = asyncio.Lock()

    def _tap(self, frame):
        now = time.monotonic()
        if now - self.last_frame_at < 0.1:   # ~10 fps to the page
            return
        self.last_frame_at = now
        self.frames += 1
        try:
            from PIL import Image
            img = Image.fromarray(frame)
            if img.width > 640:
                img = img.resize((640, int(img.height * 640 / img.width)))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=70)
            self.broadcast(bytes([self.idx]) + buf.getvalue())
        except Exception:
            pass

    async def connect(self, model_name, first_prompt):
        from rtveval.adapters.base import DurationSemantics
        from rtveval.adapters.reactor_webrtc import ReactorWebRTCAdapter

        await self.disconnect()
        self.log(self.idx, "connecting %s ..." % model_name)
        a = ReactorWebRTCAdapter(self.cfg["key"], model_name,
                                 DurationSemantics.OPEN_ENDED,
                                 prompt_command="set_prompt",
                                 first_frame_timeout_s=300.0,
                                 # worlds pause between chunks while thinking;
                                 # the campaign-strict stall watchdog would
                                 # kill a healthy interactive session
                                 stall_timeout_s=600.0)
        a.frame_tap = self._tap
        try:
            # a hung pod must not wedge the pane forever (observed live:
            # -adventure sat in "connecting" indefinitely)
            await asyncio.wait_for(self._establish(a), timeout=90.0)
        except Exception as e:
            try:
                await a.close()
            except Exception:
                pass
            self.log(self.idx, "connect FAILED (%s) - send a prompt or "
                     "re-click the mode to retry"
                     % (type(e).__name__ if not str(e) else str(e)[:80]))
            return
        self.adapter = a
        self.log(self.idx, "session ready - starting world (can take a "
                           "minute or two)...")

        if self.cfg["key"] == "lingbot":
            from tools.generation_pilot import drive_lingbot
            await drive_lingbot(a.reactor, first_prompt)
        else:
            args = {"prompt": first_prompt, "resolution": "480p"}
            if model_name.endswith("adventure"):
                args["maxExperienceTimeSec"] = 300
            await a.reactor.send_command("create_world", args)
        run_task = asyncio.create_task(a.run(None, "", None, "worlds-ab"))

        def _done(t):
            reason = "?"
            try:
                r = t.result()
                reason = getattr(r.stop_reason, "value", str(r.stop_reason))
            except Exception as e:
                reason = type(e).__name__
            if self.adapter is a:
                self.adapter = None
            self.log(self.idx, "world ended (%s) after %d frames - send a "
                               "prompt to start a new one" % (reason, self.frames))

        run_task.add_done_callback(_done)
        self.log(self.idx, "world requested - waiting for frames")

    async def _establish(self, a):
        await a.connect()
        await a._wait_ready()

    async def disconnect(self):
        if self.adapter is not None:
            try:
                self.adapter.request_stop()
                await self.adapter.close()
            except Exception:
                pass
            self.adapter = None

    async def handle(self, msg):
        async with self._lock:
            kind = msg.get("kind")
            if kind == "director":
                prompt = (msg.get("prompt") or "").strip()
                if not prompt:
                    return
                if self.adapter is None:
                    await self.connect(self.cfg["%s_model" % self.mode], prompt)
                elif self.cfg["key"] == "lingbot":
                    await self.adapter.reactor.send_command(
                        "set_prompt", {"prompt": prompt})
                    self.log(self.idx, "prompt steered")
                else:
                    await self.adapter.reactor.send_command(
                        "create_world", {"prompt": prompt, "resolution": "480p"})
                    self.log(self.idx, "new world requested")
            elif kind == "mode":
                want = msg.get("mode")
                if want not in ("director", "wasd"):
                    return
                if want == self.mode and self.adapter is not None:
                    return
                self.mode = want
                if self.cfg["director_model"] != self.cfg["wasd_model"]:
                    self.log(self.idx, "switching model for %s mode" % want)
                    await self.connect(self.cfg["%s_model" % want],
                                       DEFAULT_PROMPTS[self.idx])
                else:
                    self.log(self.idx, "%s mode (same session)" % want)
            elif kind == "cmd":
                if self.adapter is None:
                    return
                name = msg.get("cmd")
                if name not in ALLOWED_COMMANDS[self.idx]:
                    self.log(self.idx, "refused command %r" % name)
                    return
                try:
                    await self.adapter.reactor.send_command(
                        name, msg.get("args") or {})
                except Exception as e:
                    self.log(self.idx, "cmd %s failed: %s" % (name, str(e)[:80]))


async def main_async():
    import websockets

    clients = set()
    loop = asyncio.get_running_loop()

    def broadcast(data):
        for ws in list(clients):
            asyncio.run_coroutine_threadsafe(ws.send(data), loop) \
                if threading.current_thread() is not threading.main_thread() \
                else asyncio.ensure_future(ws.send(data))

    def log(pane, text):
        print("  [pane %d] %s" % (pane, text))
        broadcast(json.dumps({"pane": pane, "status": text}))

    panes = {i: Pane(i, broadcast, log) for i in PANES}

    async def on_ws(ws):
        clients.add(ws)
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except ValueError:
                    continue
                pane = panes.get(int(msg.get("pane", -1)))
                if pane is not None:
                    asyncio.create_task(pane.handle(msg))
        finally:
            clients.discard(ws)

    ws_server = await websockets.serve(on_ws, "127.0.0.1", 0)
    ws_port = ws_server.sockets[0].getsockname()[1]

    import http.server
    web = os.path.dirname(PAGE)

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=web, **kw)

        def log_message(self, *a):
            pass

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = ("http://127.0.0.1:%d/worlds_ab.html?ws=%d"
           % (httpd.server_address[1], ws_port))
    print("serving %s" % url)
    print("NOTE: Reactor GPU sessions bill while connected; worlds can take "
          "1-3 minutes to generate before frames appear. Ctrl-C stops.")

    args = [CHROME, "--autoplay-policy=no-user-gesture-required",
            "--user-data-dir=" + tempfile.mkdtemp(prefix="chrome-worlds-"),
            "--window-size=1500,800"]
    if "--debug" in sys.argv:
        args += ["--headless=new"]
    args.append(url)
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)

    # connect both panes in director mode immediately
    for i, pane in panes.items():
        asyncio.create_task(pane.handle(
            {"kind": "director", "prompt": DEFAULT_PROMPTS[i]}))

    try:
        while proc.poll() is None:
            await asyncio.sleep(1)
    finally:
        for pane in panes.values():
            await pane.disconnect()
        proc.terminate()


def load_env():
    for line in open(os.path.join(REPO, ".env")):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)


if __name__ == "__main__":
    load_env()
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        pass
