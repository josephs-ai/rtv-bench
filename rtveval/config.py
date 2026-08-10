"""Credential and endpoint configuration, read from the environment.

Keys are never written to disk or into any artifact this repo produces.
"""
import os
from typing import NamedTuple, Optional

_ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")


def load_env(path: str = _ENV_FILE) -> None:
    """Load KEY=value lines from .env without overriding a real environment.

    .env is gitignored. Keys live there and nowhere else.
    """
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = val


load_env()


class ProviderConfig(NamedTuple):
    name: str
    base_url: str
    api_key: Optional[str]
    key_env: str

    @property
    def ready(self) -> bool:
        return bool(self.api_key) and bool(self.base_url)


def _get(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip().rstrip("/")


def reactor() -> ProviderConfig:
    return ProviderConfig(
        name="reactor",
        base_url=_get("REACTOR_BASE_URL"),
        api_key=os.environ.get("REACTOR_API_KEY"),
        key_env="REACTOR_API_KEY",
    )


def decart() -> ProviderConfig:
    return ProviderConfig(
        name="decart",
        base_url=_get("DECART_BASE_URL", "https://api.decart.ai"),
        api_key=os.environ.get("DECART_API_KEY"),
        key_env="DECART_API_KEY",
    )


def xmax() -> ProviderConfig:
    return ProviderConfig(
        name="xmax",
        base_url=_get("XMAX_BASE_URL"),
        api_key=os.environ.get("XMAX_API_KEY"),
        key_env="XMAX_API_KEY",
    )
