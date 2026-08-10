#!/usr/bin/env python3
"""Pre-stage SyncNet: fetch the repo and weights now, integrate nothing.

If Vidu S1 unblocks on day 3, a half-day dependency hunt must not stand between
that and the only digital-human data the study will get. This clones and
downloads; it does not wire SyncNet into the metrics pipeline.

Worth keeping in proportion: SyncNet is not the backstop for lip-sync. Spec E.10
anchors that dimension on observable plosive closure - jaw/lip closure landing
on-frame for /b/, /p/, /m/ - which three raters can score with no model at all.
SyncNet is the cross-check on the human scores, not the source of truth. If this
script fails entirely, the lip-sync dimension still gets measured.

    python3 tools/prestage_syncnet.py
"""
import os
import subprocess
import sys
import urllib.request

REPO = "https://github.com/joonson/syncnet_python.git"
THIRD_PARTY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "third_party")
DEST = os.path.join(THIRD_PARTY, "syncnet_python")

# The upstream download_model.sh fetches these.
WEIGHTS = [
    ("http://www.robots.ox.ac.uk/~vgg/software/lipsync/data/syncnet_v2.model",
     "data/syncnet_v2.model"),
    ("http://www.robots.ox.ac.uk/~vgg/software/lipsync/data/sfd_face.pth",
     "detectors/s3fd/weights/sfd_face.pth"),
]


def run(cmd, **kw) -> int:
    print("$ %s" % " ".join(cmd))
    return subprocess.run(cmd, **kw).returncode


def fetch(url: str, dest: str) -> bool:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        print("  already present: %s (%.1f MB)" % (dest, os.path.getsize(dest) / 1e6))
        return True
    print("  downloading %s" % url)
    try:
        urllib.request.urlretrieve(url, dest)
    except Exception as e:
        print("  FAILED: %s" % e, file=sys.stderr)
        return False
    print("  -> %s (%.1f MB)" % (dest, os.path.getsize(dest) / 1e6))
    return True


def main() -> int:
    os.makedirs(THIRD_PARTY, exist_ok=True)

    if os.path.isdir(os.path.join(DEST, ".git")):
        print("repo already cloned at %s" % DEST)
    elif run(["git", "clone", "--depth", "1", REPO, DEST]) != 0:
        print("clone failed - check network access", file=sys.stderr)
        return 1

    print("\nweights:")
    ok = all(fetch(url, os.path.join(DEST, rel)) for url, rel in WEIGHTS)

    print("\n" + "=" * 68)
    if ok:
        print("SyncNet staged at %s" % DEST)
        print("NOT integrated - wire it up only if Vidu S1 becomes reachable.")
        print("Its deps (scenedetect, python_speech_features) install into")
        print(".venv-metrics at that point, not now.")
    else:
        print("Weights incomplete. The VGG host is often slow or down; retry, or")
        print("mirror the files manually into %s" % DEST)
        print("Not urgent: Spec E.10 scores lip-sync on plosive closure by eye,")
        print("and SyncNet only cross-checks that.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
