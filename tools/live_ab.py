#!/usr/bin/env python3
"""Live side-by-side: your real camera into Lucy 2.5 and Xmax X2.0 at once.

    .venv/bin/python tools/live_ab.py

Curiosity tool, NOT a measurement: nothing is recorded, timestamped, or
written to data/. Sides are randomized and hidden until you hit 'reveal'.
Needs: DECART_API_KEY + XMAX_API_KEY in .env; VPN able to reach
api.decart.ai; *.xmaxai.com split-routing exclusion in place.
"""
import http.server
import os
import subprocess
import sys
import tempfile
import threading
import urllib.parse

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
WEBROOT = os.path.join(REPO, "tools", "xmax_browser")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def load_env():
    for line in open(os.path.join(REPO, ".env")):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)


def mint_xmax_temp_key(expire_s=3600, points=500):
    import json
    import urllib.request
    req = urllib.request.Request(
        "https://api.xmaxai.com/open/api/v1/temporary-api-key",
        data=json.dumps({"expireSeconds": expire_s,
                         "pointsLimit": points}).encode(),
        headers={"X-Api-Key": os.environ["XMAX_API_KEY"].strip(),
                 "Content-Type": "application/json"})
    doc = json.loads(urllib.request.urlopen(req, timeout=20).read())
    if not doc.get("data", {}).get("temporaryApiKey"):
        raise RuntimeError("temp key mint failed: %s" % doc)
    return doc["data"]["temporaryApiKey"]


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=WEBROOT, **kw)

    def do_POST(self):
        if self.path.startswith("/snap"):
            n = int(self.headers.get("Content-Length", 0))
            with open("/tmp/liveab-snap.png", "wb") as f:
                f.write(self.rfile.read(n))
            print("  [snap] pane screenshot -> /tmp/liveab-snap.png")
            self.send_response(204); self.end_headers()

    def do_GET(self):
        if self.path.startswith("/log"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            print("  [page] %s" % q.get("m", ["?"])[0])
            self.send_response(204); self.end_headers(); return
        super().do_GET()

    def log_message(self, *a):
        pass


def main():
    load_env()
    decart = os.environ.get("DECART_API_KEY", "").strip()
    if not decart:
        print("DECART_API_KEY missing from .env"); return 1
    try:
        xmax = mint_xmax_temp_key()
        print("xmax temp key minted (%s...)" % xmax[:6])
    except Exception as e:
        xmax = ""
        print("xmax temp key mint FAILED (%s) - Lucy-only mode" % str(e)[:120])

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    url = ("http://127.0.0.1:%d/live_ab.html?decart=%s&xmax=%s%s"
           % (port, urllib.parse.quote(decart), urllib.parse.quote(xmax),
              "&snap=1" if "--debug" in sys.argv else ""))
    print("serving on port %d - launching Chrome (camera permission "
          "auto-granted; close the window to end the sessions)" % port)
    args = [CHROME, "--autoplay-policy=no-user-gesture-required",
            "--use-fake-ui-for-media-stream",
            "--user-data-dir=" + tempfile.mkdtemp(prefix="chrome-ab-"),
            "--window-size=1400,600"]
    if "--debug" in sys.argv:
        # headless smoke test with a synthetic camera - shows page logs here
        args += ["--headless=new", "--use-fake-device-for-media-stream"]
    args.append(url)
    proc = subprocess.Popen(args,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("NOTE: both sessions bill while the window is open "
          "(Lucy generation ticks + Xmax points). Ctrl-C here also stops.")
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
