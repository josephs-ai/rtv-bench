#!/usr/bin/env python3
"""Source-footage intake: probe everything the shoot delivered.

    .venv/bin/python tools/footage_intake.py

Scans data/source-footage/, probes each file (ffprobe), and reports:
  - resolution / framerate / duration / codec / audio presence
  - HARD flags: below 1440p master spec, mixed framerates across files,
    variable frame rate (phones love VFR - conform handles it, but it must
    be known), missing audio on reading files
  - a guess at which shot each file is (by name/duration) with the gaps

Nothing is modified; this is the look-before-editing step.
"""
import glob
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, "data", "source-footage")

EXPECT = (["V%d" % i for i in range(1, 11)] + ["S%d" % i for i in range(1, 5)])


def probe(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_streams", "-show_format", path],
        capture_output=True, text=True)
    if r.returncode != 0:
        return None
    doc = json.loads(r.stdout)
    v = next((s for s in doc["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in doc["streams"] if s["codec_type"] == "audio"), None)
    if v is None:
        return None
    num, den = (v.get("avg_frame_rate") or "0/1").split("/")
    fps = float(num) / float(den) if float(den) else 0.0
    rnum, rden = (v.get("r_frame_rate") or "0/1").split("/")
    rfps = float(rnum) / float(rden) if float(rden) else 0.0
    return {
        "w": v.get("width"), "h": v.get("height"),
        "fps": round(fps, 2), "vfr": abs(fps - rfps) > 0.5,
        "dur_s": round(float(doc["format"].get("duration", 0)), 1),
        "vcodec": v.get("codec_name"), "audio": a is not None,
        "size_mb": round(os.path.getsize(path) / 1e6, 1),
    }


def main():
    os.makedirs(SRC, exist_ok=True)
    files = sorted(f for f in glob.glob(os.path.join(SRC, "*"))
                   if os.path.isfile(f) and not f.endswith((".json", ".md")))
    if not files:
        print("drop the shoot files into %s and rerun" % SRC)
        return 1

    rows, fpss, problems = [], set(), []
    for f in files:
        name = os.path.basename(f)
        p = probe(f)
        if p is None:
            problems.append("%s: not a video / unreadable" % name)
            continue
        rows.append((name, p))
        fpss.add(round(p["fps"]))
        if p["h"] and p["h"] < 1440 and p["w"] < 2560:
            problems.append("%s: below 1440p master spec (%dx%d)"
                            % (name, p["w"], p["h"]))
        if p["vfr"]:
            problems.append("%s: VARIABLE frame rate (phone default) - "
                            "conform must resample; noted, not fatal" % name)

    print("%-34s %9s %6s %7s %7s %6s %6s" % (
        "file", "res", "fps", "dur_s", "codec", "audio", "MB"))
    for name, p in rows:
        print("%-34s %4dx%-4d %6.2f %7.1f %7s %6s %6.1f" % (
            name, p["w"], p["h"], p["fps"], p["dur_s"], p["vcodec"],
            "yes" if p["audio"] else "NO", p["size_mb"]))

    if len(fpss) > 1:
        problems.append("MIXED FRAMERATES across files: %s - violates the "
                        "one-setup rule; discuss before conform" % sorted(fpss))
    readings = [(n, p) for n, p in rows
                if any(k in n.upper() for k in ("S1", "S2", "S3", "S4"))]
    for n, p in readings:
        if not p["audio"]:
            problems.append("%s: reading file has NO AUDIO - lip-sync needs it" % n)

    named = {k: any(k in n.upper() for n, _ in rows) for k in EXPECT}
    missing = [k for k, ok in named.items() if not ok]
    print("\nshot coverage (by filename): %d/%d recognised"
          % (sum(named.values()), len(EXPECT)))
    if missing:
        print("  not identified by name (may still exist under other names): "
              + ", ".join(missing))
        print("  -> rename files to include V1..V10 / S1..S4, or tell Claude "
              "which is which")
    print("\n%s" % ("PROBLEMS:\n  " + "\n  ".join(problems) if problems
                    else "no blocking problems found"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
