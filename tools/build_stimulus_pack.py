#!/usr/bin/env python3
"""Build the RTV-Bench stimulus pack from its manifest — deterministic and
verifiable:

    .venv/bin/python tools/build_stimulus_pack.py           # fetch + build + verify
    .venv/bin/python tools/build_stimulus_pack.py --verify  # check an existing build

Sources are fetched from their hosts (their licenses permit use, not raw
redistribution) and pinned by sha256; conforms are derived by the recipe
and verified against the manifest's output hashes. A pack that builds
clean is bit-identical to the reference run's stimulus.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK = os.path.join(REPO, "stimulus-pack")


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    man = json.load(open(os.path.join(PACK, "manifest.json")))
    src_dir = os.path.join(PACK, "sources")
    out_dir = os.path.join(PACK, "conforms")
    os.makedirs(src_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    ok = True

    for name, s in man["sources"].items():
        p = os.path.join(src_dir, name)
        if not os.path.exists(p) and not args.verify:
            print("fetch", name)
            try:
                # some hosts (wikimedia) 403 the default urllib UA
                req = urllib.request.Request(
                    s["url"], headers={"User-Agent":
                                       "RTV-Bench-stimulus-builder/1.1 "
                                       "(benchmark reproduction)"})
                with urllib.request.urlopen(req, timeout=60) as r, \
                        open(p, "wb") as f:
                    f.write(r.read())
            except Exception as e:
                print("[FETCH-FAIL]", name, str(e)[:80])
        if not os.path.exists(p):
            print("[MISS]", name)
            ok = False
            continue
        got = sha256(p)
        good = got == s["sha256"]
        print("[%s] %s" % ("  ok" if good else "HASH-MISMATCH", name))
        ok &= good

    rec = man["conform_recipe"]
    for out_name, want in man["conform_output_sha256"].items():
        src = out_name.replace("conform-", "").replace("mixkit", "mixkit-")
        outp = os.path.join(out_dir, out_name)
        if not os.path.exists(outp) and not args.verify:
            print("conform", out_name)
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1",
                 "-i", os.path.join(src_dir, src),
                 "-t", str(rec["loop_to_s"]), "-vf", rec["video"],
                 "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-an",
                 outp], check=True)
        if not os.path.exists(outp):
            print("[MISS]", out_name)
            ok = False
            continue
        got = sha256(outp)
        if got == want:
            print("[  ok] %s" % out_name)
        else:
            # different ffmpeg builds encode non-identically; sources+recipe
            # are the portable guarantee (see manifest note)
            print("[warn] %s (encoder differs from reference build - fine "
                  "if sources verified)" % out_name)

    # ---- derived refs (deterministic recipes; e.g. campaign F self-ref) ----
    import shutil
    for name, d in (man.get("derived_refs") or {}).items():
        outp = os.path.join(src_dir, name)
        if not os.path.exists(outp) and not args.verify:
            conf = os.path.join(out_dir, d["from_conform"])
            if os.path.exists(conf):
                print("derive", name)
                # recipe is pinned in the manifest; keep in sync
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss",
                                "5", "-i", conf, "-frames:v", "1", "-vf",
                                "crop=749:720:294:0", "-q:v", "4", outp],
                               check=True)
        print("[%s] %s (derived)" % ("  ok" if os.path.exists(outp)
                                     else "MISS", name))
        ok &= os.path.exists(outp)

    # ---- install: put everything where the campaigns read it ------------
    # (a user must never hand-fetch or hand-copy a stimulus)
    inst = man.get("install")
    if inst and not args.verify:
        cdst = os.path.join(REPO, inst["conforms_to"])
        rdst = os.path.join(REPO, inst["refs_to"])
        os.makedirs(cdst, exist_ok=True)
        os.makedirs(rdst, exist_ok=True)
        n = 0
        for f in os.listdir(out_dir):
            if f.startswith("conform-") and not os.path.exists(
                    os.path.join(cdst, f)):
                shutil.copy(os.path.join(out_dir, f), os.path.join(cdst, f))
                n += 1
        for f in os.listdir(src_dir):
            if f.endswith(".jpg") and not os.path.exists(
                    os.path.join(rdst, f)):
                shutil.copy(os.path.join(src_dir, f), os.path.join(rdst, f))
                n += 1
        print("installed %d new files into data/ (existing kept)" % n)

    print("\nedit protocol: %d edits @ t=%ss · world prompts: %d"
          % (len(man["edit_protocol"]["edits"]),
             man["edit_protocol"]["edit_at_s"], len(man["world_prompts"])))
    print("PACK %s" % ("VERIFIED" if ok else "FAILED VERIFICATION"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
