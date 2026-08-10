"""Reactor client — catalog discovery only, for now.

Written against stdlib so it runs on the system Python with nothing installed.
The catalog response shape is not assumed: the parser accepts a bare list, or a
dict wrapping the list under any of the usual keys, and follows cursor- or
page-style pagination if it is offered.
"""
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

USER_AGENT = "rtv-eval/0.1 (model catalog probe)"
TIMEOUT_S = 30

# Tried in order until one returns a parseable list of models.
CANDIDATE_PATHS = (
    "/models",  # live-confirmed 2026-08-10
    "/v1/models",
    "/api/v1/models",
    "/v1/model/list",
    "/v1/catalog",
    "/catalog/models",
)

LIST_KEYS = ("data", "models", "items", "results", "list", "records")
NAME_KEYS = ("id", "model", "model_id", "name", "slug", "key")
LABEL_KEYS = ("name", "display_name", "title", "label", "description")


class ProbeError(RuntimeError):
    pass


def mint_token(base_url: str, api_key: str) -> str:
    """Exchange the long-lived rk_ API key for a short-lived JWT.

    Live-verified 2026-08-10: POST /tokens with header `Reactor-API-Key`
    returns {"jwt", "expires_at"}. The raw API key is NEVER a valid Bearer
    token - sending it yields "Invalid or expired token", which reads like a
    bad key but is actually a missing exchange step.
    """
    req = urllib.request.Request(
        base_url + "/tokens", data=b"{}",
        headers={"Reactor-API-Key": api_key.strip(),
                 "Content-Type": "application/json",
                 "Accept": "application/json",
                 "User-Agent": USER_AGENT},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise ProbeError("token mint failed: HTTP %d %s"
                         % (e.code, e.read(200).decode("utf-8", "replace")))
    except urllib.error.URLError as e:
        raise ProbeError("cannot reach %s/tokens: %s" % (base_url, e.reason))
    jwt = body.get("jwt") or body.get("token")
    if not jwt:
        raise ProbeError("token mint returned no jwt field: %s" % sorted(body))
    return jwt


def _request(url: str, bearer_token: str) -> Tuple[int, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": "Bearer %s" % bearer_token,
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            body = resp.read().decode("utf-8", "replace")
            status = resp.getcode()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        status = e.code
    except urllib.error.URLError as e:
        raise ProbeError("cannot reach %s: %s" % (url, e.reason))
    try:
        return status, json.loads(body)
    except ValueError:
        return status, body


def _extract_list(payload: Any) -> Optional[List[Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for k in LIST_KEYS:
            v = payload.get(k)
            if isinstance(v, list):
                return v
            # one level of nesting, e.g. {"data": {"models": [...]}}
            if isinstance(v, dict):
                inner = _extract_list(v)
                if inner is not None:
                    return inner
    return None


def _next_page_url(base: str, path: str, payload: Any) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    for k in ("next", "next_url", "next_page_url"):
        v = payload.get(k)
        if isinstance(v, str) and v:
            return v if v.startswith("http") else urllib.parse.urljoin(base, v)
    for k in ("next_cursor", "cursor", "page_token", "next_page_token"):
        v = payload.get(k)
        if isinstance(v, str) and v:
            return "%s%s?%s" % (base, path, urllib.parse.urlencode({"cursor": v}))
    return None


def fetch_catalog(base_url: str, api_key: str, path: Optional[str] = None,
                  max_pages: int = 20) -> Dict[str, Any]:
    """Return {"path", "entries", "pages", "attempts"}.

    Mints a JWT from the API key first (see mint_token), then walks candidate
    catalog paths with it. `attempts` records every path tried and what came
    back, so a failed probe is still a reportable result rather than a shrug.
    """
    api_key = mint_token(base_url, api_key)  # exchange; Bearer wants the JWT
    attempts: List[Dict[str, Any]] = []
    paths = (path,) if path else CANDIDATE_PATHS

    for p in paths:
        url = base_url + p
        try:
            status, payload = _request(url, api_key)
        except ProbeError as e:
            attempts.append({"path": p, "error": str(e)})
            continue

        entries = _extract_list(payload) if 200 <= status < 300 else None
        note = None
        if entries is None and isinstance(payload, (dict, str)):
            note = json.dumps(payload)[:300] if isinstance(payload, dict) else payload[:300]
        attempts.append({"path": p, "status": status,
                         "count": len(entries) if entries is not None else None,
                         "body_head": note})

        if entries is None:
            continue

        pages = 1
        nxt = _next_page_url(base_url, p, payload)
        while nxt and pages < max_pages:
            status, payload = _request(nxt, api_key)
            more = _extract_list(payload) if 200 <= status < 300 else None
            if not more:
                break
            entries.extend(more)
            pages += 1
            nxt = _next_page_url(base_url, p, payload)

        return {"path": p, "entries": entries, "pages": pages, "attempts": attempts}

    raise ProbeError(
        "no catalog endpoint responded with a model list. Tried: %s"
        % ", ".join(a["path"] for a in attempts)
    )


def entry_text(entry: Any) -> str:
    """Flatten a catalog entry to searchable text."""
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        parts = []
        for k in set(NAME_KEYS + LABEL_KEYS):
            v = entry.get(k)
            if isinstance(v, str):
                parts.append(v)
        return " | ".join(parts) if parts else json.dumps(entry)[:500]
    return str(entry)


def entry_id(entry: Any) -> str:
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        for k in NAME_KEYS:
            v = entry.get(k)
            if isinstance(v, str) and v:
                return v
    return "<unnamed>"
