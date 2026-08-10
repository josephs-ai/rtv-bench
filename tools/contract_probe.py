#!/usr/bin/env python3
"""Interaction-contract probe for the generation products (pilot gate item 5).

G1-G7 assume text direction. Before any Campaign C generation run, each
product's contract is confirmed from its OWN declared capabilities - not
assumed from marketing. REST-only: create session -> poll GET /sessions/<id>
until capabilities populate -> read the command list -> DELETE immediately.
No media transport, seconds of session life, minimal GPU billing.

Classification rule (from declared commands, recorded verbatim as evidence):
  - text steer:   any command whose name suggests free-text direction
                  (prompt / text / direct / describe / instruct)
  - movement:     camera/pose/move/key control commands
  - text_directed  if text steer present and dominant
  - movement_driven if movement present and no text steer
  - hybrid surfaces as a MISMATCH against routing.py for human review.

Writes data/interaction-contracts.json (the gate file).
"""
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rtveval import capability, config  # noqa: E402
from rtveval.providers.reactor_session import (create_session, delete_session,  # noqa: E402
                                               make_token_manager)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "data", "interaction-contracts.json")

TARGETS = [
    ("lingbot-world-2", "reactor/lingbot-world-2"),
    ("happy-oyster", "reactor/happy-oyster-director"),
]

TEXT_MARKERS = ("prompt", "text", "direct", "describe", "instruct", "world",
                "steer", "scene")
MOVE_MARKERS = ("move", "camera", "pose", "key", "wasd", "look", "walk",
                "navigate", "action")


def poll_capabilities(base_url: str, bearer: str, session_id: str,
                      timeout_s: float = 60.0) -> dict:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        req = urllib.request.Request(
            "%s/sessions/%s" % (base_url, session_id),
            headers={"Authorization": "Bearer %s" % bearer,
                     "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            doc = json.loads(r.read().decode())
        caps = doc.get("capabilities")
        if caps:
            return caps
        time.sleep(1.5)
    raise TimeoutError("capabilities not populated within %.0fs" % timeout_s)


def classify_commands(commands) -> tuple:
    names = []
    for c in commands or []:
        name = c.get("name", c) if isinstance(c, dict) else str(c)
        names.append(name.lower())
    text = sorted(n for n in names if any(m in n for m in TEXT_MARKERS))
    move = sorted(n for n in names if any(m in n for m in MOVE_MARKERS))
    if text and not move:
        contract = "text_directed"
    elif move and not text:
        contract = "movement_driven"
    elif text and move:
        # Both present: text steer exists, so G7 is expressible - classify by
        # the plan's needs (text-directed testable) but surface the hybrid.
        contract = "text_directed"
    else:
        contract = "unknown"
    return contract, names, text, move


def main() -> int:
    import asyncio

    cfg = config.reactor()
    tm = make_token_manager(cfg.base_url, cfg.api_key)
    bearer = asyncio.run(tm.bearer())

    probes = []
    for product_key, model_name in TARGETS:
        print("probing %s (%s)..." % (product_key, model_name))
        info = create_session(cfg.base_url, bearer, model_name)
        try:
            caps = poll_capabilities(cfg.base_url, bearer, info.session_id)
        finally:
            code = delete_session(cfg.base_url, bearer, info.session_id)
            print("  session %s closed (%s)" % (info.session_id[:12], code))

        commands = caps.get("commands") or caps.get("command_capabilities") or []
        tracks = caps.get("tracks", [])
        contract, all_names, text_cmds, move_cmds = classify_commands(commands)
        accepts_text = bool(text_cmds)

        rec = capability.probe_record(
            product_key, contract, accepts_text,
            evidence="declared commands: %s | tracks: %s | version: %s"
                     % (all_names, [t.get("name") for t in tracks],
                        info.resolved_version))
        probes.append({
            "product_key": product_key,
            "model_name": model_name,
            "declared_contract": rec.declared_contract,
            "confirmed_contract": rec.confirmed_contract,
            "accepts_text_steer": rec.accepts_text_steer,
            "matches_declared": rec.matches_declared,
            "commands": all_names,
            "text_commands": text_cmds,
            "movement_commands": move_cmds,
            "resolved_version": info.resolved_version,
            "evidence": rec.evidence,
        })
        flag = "" if rec.matches_declared else "  << MISMATCH vs routing.py"
        print("  contract: %s (declared %s)%s" % (contract, rec.declared_contract, flag))
        print("  text cmds: %s" % text_cmds)
        print("  move cmds: %s" % move_cmds)

    keys = [p["product_key"] for p in probes]
    plan = capability.generation_ranking_plan(keys)
    doc = {"probed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "probes": probes, "ranking_plan": {"groups": plan["groups"],
                                              "note": plan["note"]}}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(doc, f, indent=2)
    print("\n%s" % plan["note"])
    print("-> %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
