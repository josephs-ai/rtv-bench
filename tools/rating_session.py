#!/usr/bin/env python3
"""Blind rating session server - the dry run is a USABILITY test of this
tool, not of the rubric (a UI problem discovered during the alpha trial
wastes the trial).

    .venv/bin/python tools/rating_session.py --rater joseph

Pipeline (all existing, tested primitives):
  captures -> normalize_and_blind (uniform size, watermark crop, HMAC names,
  key OUTSIDE served dir) -> audit_no_leaks -> session_plan (seeded order +
  hidden repeat) -> this server (journal, resume, 45-min cap).

Scores land in data/rating-dryrun/journal.jsonl. Nothing in the served tree
or the DOM names a product; the key file maps back at analysis time.
"""
import argparse
import glob
import http.server
import json
import os
import sys
import threading
import urllib.parse
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAGE = """<!doctype html>
<meta charset="utf-8"><title>rating session</title>
<style>
 :root{--bg:#0b0d12;--panel:#161a24;--line:#262c3c;--txt:#e8ebf2;--acc:#7c9cff}
 body{margin:0;background:var(--bg);color:var(--txt);
   font:15px/1.5 -apple-system,system-ui,sans-serif;display:flex;
   flex-direction:column;height:100vh}
 #top{padding:10px 16px;color:#9aa3b8;font-size:13px}
 #main{display:flex;flex:1;min-height:0;gap:12px;padding:0 16px 16px}
 video{flex:1;min-width:0;background:#000;border-radius:12px;
   border:1px solid var(--line);object-fit:contain}
 #panel{width:430px;overflow-y:auto;background:var(--panel);
   border:1px solid var(--line);border-radius:12px;padding:16px}
 h3{margin:.2rem 0 .6rem;font-size:15px}
 #prompt{color:#9aa3b8;font-size:13px;margin-bottom:10px}
 .anchor{display:block;width:100%;text-align:left;margin:6px 0;padding:10px;
   background:#0e1119;color:var(--txt);border:1px solid var(--line);
   border-radius:9px;font:13px/1.45 inherit;cursor:pointer}
 .anchor:hover{border-color:var(--acc)}
 .anchor b{color:var(--acc);margin-right:8px}
 #done{padding:40px;text-align:center;font-size:17px}
</style>
<div id="top"></div>
<div id="main">
  <video id="v" autoplay loop muted playsinline controls></video>
  <div id="panel"></div>
</div>
<script>
async function load() {
  const r = await fetch("/state");
  const s = await r.json();
  document.getElementById("top").textContent = s.done ? "" :
    ("clip " + s.progress + " - " + s.dimension_name +
     " - elapsed " + s.elapsed_min.toFixed(0) + " min (cap 45)");
  if (s.done) {
    document.getElementById("main").innerHTML =
      "<div id=done>" + s.message + "</div>";
    return;
  }
  const v = document.getElementById("v");
  if (!v.src.endsWith(s.video)) { v.src = s.video; v.play().catch(()=>{}); }
  const p = document.getElementById("panel");
  p.innerHTML = "<h3>" + s.dimension_name + "</h3>" +
    (s.prompt ? "<div id=prompt>prompt: \\"" + s.prompt + "\\"</div>" : "") +
    "<div style='color:#9aa3b8;font-size:12.5px;margin-bottom:8px'>watch at " +
    "normal speed first; frame-step (video controls) allowed for 4 vs 5</div>";
  for (const [score, text] of s.anchors) {
    const b = document.createElement("button");
    b.className = "anchor";
    b.innerHTML = "<b>" + score + "</b>" + text;
    b.onclick = async () => {
      const rr = await fetch("/score", {method: "POST",
        body: JSON.stringify({order_index: s.order_index,
                              dimension: s.dimension, score: score})});
      if (!rr.ok) { alert(await rr.text()); return; }
      load();
    };
    p.appendChild(b);
  }
  document.onkeydown = e => {
    const k = parseInt(e.key);
    if (k >= 1 && k <= 5) p.querySelectorAll(".anchor")[
      [...s.anchors].findIndex(a => a[0] === k)]?.click();
  };
}
load();
</script>"""


def build(args):
    import numpy as np
    import av
    from rtveval.rating import (RatingItem, audit_no_leaks, normalize_and_blind,
                                session_plan)
    from rtveval.vlm_judge import DIMENSION_SETS

    outdir = os.path.join(REPO, "data", "rating-dryrun")
    keydir = os.path.join(REPO, "data", "rating-dryrun-key")
    clipdir = os.path.join(outdir, "clips")
    os.makedirs(keydir, exist_ok=True)

    items, prompts = [], {}
    for mkv in sorted(glob.glob(os.path.join(args.captures, "*.mkv"))):
        metap = mkv.replace(".mkv", ".json")
        if not os.path.exists(metap) or os.path.getsize(mkv) == 0:
            continue
        meta = json.load(open(metap))
        if not meta.get("frames"):
            continue
        # content check: exclude degenerate colour-field captures (the HO
        # placeholder class) - a usability dry run on empty clips tests nothing
        with av.open(mkv) as c:
            fr = None
            for i, f in enumerate(c.decode(c.streams.video[0])):
                fr = f.to_ndarray(format="rgb24")
                if i >= 5:
                    break
        if fr is None or float(fr.std(axis=(0, 1)).mean()) < 12.0:
            print("excluded (no spatial content): %s" % os.path.basename(mkv))
            continue
        run_id = os.path.basename(mkv)
        items.append(RatingItem(meta.get("product", "?"), run_id, mkv,
                                clip_id=meta.get("content", run_id)))
        prompts[run_id] = meta.get("prompt")
    if not items:
        print("no usable captures"); return None

    secret = os.urandom(16)
    clips = normalize_and_blind(items, secret, clipdir,
                                os.path.join(keydir, "key.json"),
                                display=(1280, 720), crop_margin=0.07)
    leaks = audit_no_leaks(clipdir, [i.product_key for i in items])
    if leaks:
        print("BLINDING LEAKS - refusing to serve:", leaks); return None
    # prompt text keyed by blind id (prompts are shared stimuli, not identity)
    blind_prompts = {}
    for it, bc in zip(items, clips):
        blind_prompts[bc.blind_id] = prompts.get(it.run_id)

    plan = session_plan(args.rater, args.seed, clips, hidden_repeats=1)
    dims = [(d.dim_id, d.name, [(s, d.anchors[s]) for s in (5, 4, 3, 2, 1)])
            for d in DIMENSION_SETS["generation"]]
    print("%d clips -> %d presentations (%d hidden repeat), %d dimensions"
          % (len(clips), len(plan.presentations),
             sum(p.is_hidden_repeat for p in plan.presentations), len(dims)))
    return plan, dims, clipdir, blind_prompts, outdir


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rater", required=True)
    ap.add_argument("--seed", type=int, default=20260811)
    ap.add_argument("--captures", default=os.path.join(REPO, "data", "pilot-captures"))
    args = ap.parse_args()

    built = build(args)
    if built is None:
        return 1
    plan, dims, clipdir, blind_prompts, outdir = built

    from rtveval.rating import SessionClosed, SessionJournal
    journal = SessionJournal(os.path.join(outdir, "journal.jsonl"))

    def state():
        for dim_id, dim_name, anchors in dims:
            p = journal.next_pending(plan, dim_id)
            if p is not None:
                total = len(plan.presentations)
                done = len(journal.completed(dim_id))
                return {"done": False, "order_index": p.order_index,
                        "video": "/clips/%s.mp4" % p.blind_id,
                        "prompt": blind_prompts.get(p.blind_id),
                        "dimension": dim_id, "dimension_name": "%s - %s" % (dim_id, dim_name),
                        "anchors": anchors,
                        "progress": "%d/%d" % (done + 1, total),
                        "elapsed_min": journal.elapsed_min()}
        return {"done": True, "message":
                "Session complete. Journal: data/rating-dryrun/journal.jsonl - "
                "thank you. Close the window."}

    pres_by_index = {p.order_index: p for p in plan.presentations}

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=clipdir, **kw)

        def do_GET(self):
            if self.path == "/" or self.path.startswith("/index"):
                body = PAGE.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers(); self.wfile.write(body); return
            if self.path.startswith("/state"):
                body = json.dumps(state()).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers(); self.wfile.write(body); return
            if self.path.startswith("/clips/"):
                self.path = self.path[len("/clips"):]
            super().do_GET()

        def log_message(self, *a):
            pass

        def do_POST(self):
            if not self.path.startswith("/score"):
                self.send_response(404); self.end_headers(); return
            n = int(self.headers.get("Content-Length", 0))
            doc = json.loads(self.rfile.read(n))
            try:
                journal.record(args.rater, pres_by_index[doc["order_index"]],
                               doc["dimension"], int(doc["score"]))
                self.send_response(204); self.end_headers()
            except SessionClosed as e:
                self.send_response(423); self.end_headers()
                self.wfile.write(str(e).encode())

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    port = srv.server_address[1]
    url = "http://127.0.0.1:%d/" % port
    print("rating session for %r at %s  (Ctrl-C to stop; resume any time - "
          "the journal remembers)" % (args.rater, url))
    webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
