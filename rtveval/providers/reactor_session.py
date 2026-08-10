"""Reactor coordinator client: mint -> create session -> resolve version.

Split from the catalog probe (providers/reactor.py) because this is the run
path, not discovery. All HTTP/JSON, so it is fully unit-testable and was
validated against the live coordinator with a single create-then-delete per
model (no GPU loop - honouring the vendor condition).

Session-create body shape recovered from the vendor's own @reactor-team/js-sdk:

    {"model": {"name": "reactor/..."},
     "client_info": {"sdk_version", "sdk_type"},
     "supported_transports": [{"protocol": "webrtc", "version": ...}]}

The 201 response carries `model.version`, `server_info.server_version`, and
`cluster`. That is the version-of-record for hard rule 5 - and critically it
works for UNLISTED models (Happy Oyster), which never appear in GET /models and
so cannot be version-resolved by catalog re-read.
"""
import json
import urllib.error
import urllib.request
from typing import Any, Dict, NamedTuple, Optional

from ..auth import TokenManager, ttl_from_expires_at

USER_AGENT = "rtv-eval/0.1"
TIMEOUT_S = 30
SDK_TYPE = "rtv-eval"
SDK_VERSION = "0.1.0"


class SessionInfo(NamedTuple):
    session_id: str
    model_name: str
    resolved_version: str  # model.version @ server_version, cluster-tagged
    cluster: Optional[str]
    raw: Dict[str, Any]  # full response, retained for the appendix


def _post(url: str, body: dict, bearer: str) -> Any:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer %s" % bearer,
                 "Content-Type": "application/json",
                 "Accept": "application/json", "User-Agent": USER_AGENT},
        method="POST")
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        return json.loads(resp.read().decode())


def make_token_manager(base_url: str, api_key: str) -> TokenManager:
    """A TokenManager whose mint hits POST /tokens and honours the server's
    own expires_at, so the ~6 h Reactor token refreshes on the shared path."""
    async def mint():
        import asyncio
        loop = asyncio.get_running_loop()

        def _do():
            req = urllib.request.Request(
                base_url + "/tokens", data=b"{}",
                headers={"Reactor-API-Key": api_key.strip(),
                         "Content-Type": "application/json",
                         "Accept": "application/json", "User-Agent": USER_AGENT},
                method="POST")
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                return json.loads(resp.read().decode())

        body = await loop.run_in_executor(None, _do)
        jwt = body.get("jwt") or body.get("token")
        if not jwt:
            raise RuntimeError("token mint returned no jwt: %s" % sorted(body))
        exp = body.get("expires_at")
        # If the server gives no expiry, fall back to a conservative 5 min so
        # the token still refreshes rather than being trusted forever.
        ttl = ttl_from_expires_at(float(exp)) if exp else 300.0
        return jwt, ttl

    return TokenManager(mint, name="reactor")


def resolve_version(session_response: Dict[str, Any]) -> str:
    """model.version @ server_version (+cluster). The version-of-record for
    unlisted and listed models alike - the session always reports it, the
    catalog does not always list the model."""
    model = session_response.get("model", {}) or {}
    mv = model.get("version") or "unknown"
    server = (session_response.get("server_info", {}) or {}).get("server_version", "?")
    return "%s@%s" % (mv, server)


def create_session(base_url: str, bearer: str, model_name: str,
                   transports=(("webrtc", "1"),)) -> SessionInfo:
    """POST /sessions. Returns a SessionInfo whose version comes from the
    response, never from config."""
    body = {
        "model": {"name": model_name},
        "client_info": {"sdk_version": SDK_VERSION, "sdk_type": SDK_TYPE},
        "supported_transports": [{"protocol": p, "version": v} for p, v in transports],
    }
    try:
        resp = _post(base_url + "/sessions", body, bearer)
    except urllib.error.HTTPError as e:
        detail = e.read(300).decode("utf-8", "replace")
        raise RuntimeError("Reactor session create failed (%d) for %r: %s"
                           % (e.code, model_name, detail))

    sid = resp.get("session_id") or resp.get("id")
    if not sid:
        raise RuntimeError("session response has no session_id: %s" % sorted(resp))
    return SessionInfo(
        session_id=str(sid),
        model_name=(resp.get("model", {}) or {}).get("name", model_name),
        resolved_version=resolve_version(resp),
        cluster=resp.get("cluster"),
        raw=resp)


def delete_session(base_url: str, bearer: str, session_id: str) -> int:
    req = urllib.request.Request(
        base_url + "/sessions/" + session_id,
        headers={"Authorization": "Bearer %s" % bearer, "User-Agent": USER_AGENT},
        method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return resp.getcode()
    except urllib.error.HTTPError as e:
        return e.code
