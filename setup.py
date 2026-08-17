#!/usr/bin/env python3
"""RTV-Bench setup wizard. Run with plain system Python (stdlib only):

    python3 setup.py           # checks + builds everything it can
    python3 setup.py --check   # report only, change nothing

Walks through: prerequisites -> virtualenvs -> dependencies -> .env keys
-> live key validation -> self-test -> which campaigns you can run today.
Safe to re-run any time; every step skips what's already done.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.request

REPO = os.path.dirname(os.path.abspath(__file__))
OK, BAD, SKIP = "\033[32m  ok\033[0m", "\033[31mFAIL\033[0m", "\033[33mskip\033[0m"


def say(tag, msg):
    print(" [%s] %s" % (tag, msg))


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def step_prereqs():
    print("\n== 1/6 prerequisites")
    good = True
    v = sys.version_info
    if v >= (3, 11):
        say(OK, "python %d.%d" % (v.major, v.minor))
    else:
        say(BAD, "python >= 3.11 required (found %d.%d)" % (v.major, v.minor))
        good = False
    for tool, why, hint in [
        ("ffmpeg", "capture transcoding", "brew install ffmpeg"),
        ("uv", "fast dependency install", "brew install uv (or pipx install uv)"),
    ]:
        if shutil.which(tool):
            say(OK, tool)
        else:
            say(BAD, "%s missing (%s) -> %s" % (tool, why, hint))
            good = False
    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if os.path.exists(chrome) or shutil.which("google-chrome"):
        say(OK, "chrome (browser-SDK lanes)")
    else:
        say(SKIP, "chrome not found - browser-SDK products (Xmax native, "
                  "Happy Oyster) won't run; everything else will")
    return good


def step_venvs(check_only):
    print("\n== 2/6 virtualenvs + dependencies")
    for venv, req in [(".venv", "requirements.txt"),
                      (".venv-metrics", "requirements-metrics.txt")]:
        py = os.path.join(REPO, venv, "bin", "python")
        if not os.path.exists(py):
            if check_only:
                say(BAD, "%s missing (run without --check to create)" % venv)
                continue
            say("....", "creating %s" % venv)
            r = run([sys.executable, "-m", "venv", os.path.join(REPO, venv)])
            if r.returncode:
                say(BAD, "venv create failed: %s" % r.stderr[-120:])
                continue
        probe = run([py, "-c", "import av" if venv == ".venv" else "import torch"])
        if probe.returncode == 0:
            say(OK, "%s (deps present)" % venv)
            continue
        if check_only:
            say(BAD, "%s exists but deps missing" % venv)
            continue
        say("....", "installing %s into %s (few minutes)" % (req, venv))
        r = run(["uv", "pip", "install", "--python", py, "-r",
                 os.path.join(REPO, req)])
        say(OK if r.returncode == 0 else BAD,
            "%s dependencies" % venv if r.returncode == 0
            else "install failed: %s" % r.stderr[-160:])


def step_env(check_only):
    print("\n== 3/6 provider keys (.env)")
    envp = os.path.join(REPO, ".env")
    if not os.path.exists(envp):
        if check_only:
            say(BAD, ".env missing")
            return {}
        shutil.copy(os.path.join(REPO, ".env.example"), envp)
        say(OK, "created .env from .env.example - open it and paste the "
                "keys you have, then re-run setup")
    keys = {}
    for line in open(envp):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            keys[k] = v.strip()
    for k in ["DECART_API_KEY", "XMAX_API_KEY", "REACTOR_API_KEY",
              "ANTHROPIC_API_KEY"]:
        say(OK if keys.get(k) else SKIP,
            "%s %s" % (k, "set" if keys.get(k) else
                       "empty - products behind it will be skipped"))
    return keys


def _http(url, method="GET", headers=None, body=None, timeout=15):
    req = urllib.request.Request(url, method=method, headers=headers or {},
                                 data=body)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()[:200]
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:200]
    except Exception as e:
        return None, str(e)[:120]


def step_validate(keys):
    print("\n== 4/6 live key validation (tiny requests, ~$0)")
    if keys.get("ANTHROPIC_API_KEY"):
        st, _ = _http("https://api.anthropic.com/v1/models",
                      headers={"x-api-key": keys["ANTHROPIC_API_KEY"],
                               "anthropic-version": "2023-06-01"})
        say(OK if st == 200 else BAD, "anthropic (judge): HTTP %s" % st)
    if keys.get("REACTOR_API_KEY"):
        st, _ = _http("https://api.reactor.inc/tokens", method="POST",
                      headers={"Reactor-API-Key": keys["REACTOR_API_KEY"]})
        say(OK if st == 200 else BAD, "reactor (aggregator): HTTP %s" % st)
    if keys.get("XMAX_API_KEY"):
        st, _ = _http("https://api.xmaxai.com/open/api/v1/temporary-api-key",
                      method="POST",
                      headers={"X-Api-Key": keys["XMAX_API_KEY"],
                               "Content-Type": "application/json"},
                      body=json.dumps({"expireSeconds": 300,
                                       "pointsLimit": 10}).encode())
        say(OK if st == 200 else BAD,
            "xmax native: HTTP %s%s" % (st, "" if st == 200 else
            "  (from outside China this may need routing - see docs)"))
    if keys.get("DECART_API_KEY"):
        say(SKIP, "decart validates on first session (websocket-only auth); "
                  "campaign B's first slot is the check")


def step_selftest(check_only):
    print("\n== 5/6 self-test")
    py = os.path.join(REPO, ".venv", "bin", "python")
    if not os.path.exists(py):
        say(SKIP, "core venv not ready")
        return
    r = run([py, "-m", "pytest", "tests/test_orchestrator.py", "-q"],
            cwd=REPO)
    tail = (r.stdout or r.stderr).strip().splitlines()
    say(OK if r.returncode == 0 else BAD,
        "orchestrator tests: %s" % (tail[-1] if tail else "?"))


def step_summary(keys):
    print("\n== 6/6 what you can run today")
    have = lambda k: bool(keys.get(k))
    rows = [
        ("reliability (campaign B, Lucy lane)", have("DECART_API_KEY")),
        ("reliability (Xmax via aggregator)", have("REACTOR_API_KEY")),
        ("reliability (Xmax native, browser)", have("XMAX_API_KEY")),
        ("quality pairs + audits (needs judge)", have("ANTHROPIC_API_KEY")),
        ("live editing (campaign D)",
         have("DECART_API_KEY") or have("XMAX_API_KEY")),
        ("worlds (campaign C: LingBot + HO)", have("REACTOR_API_KEY")),
    ]
    for name, ok in rows:
        say(OK if ok else SKIP, name)
    print("\nnext:  .venv/bin/python tools/benchmark_run.py --list")
    print("read:  BENCHMARK.md (ground rules)  ·  README.md (results)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    print("RTV-Bench setup%s" % (" (check only)" if args.check else ""))
    ok = step_prereqs()
    step_venvs(args.check)
    keys = step_env(args.check)
    if any(keys.values()):
        step_validate(keys)
    step_selftest(args.check)
    step_summary(keys)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
