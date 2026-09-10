"""Shared helpers for unit tests: fixture loading and mock transport wiring.

All fixtures under tests/fixtures/ are synthetic; no real device or account
data may ever be committed here.
"""

from __future__ import annotations

import base64
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

import httpx

from pydanalock.cloud import AsyncDanalockCloud, DanalockCloud, TokenData, TokenStorage

FIXTURES_DIR = Path(__file__).parent / "fixtures"

USERNAME = "user@example.com"
PASSWORD = "correct-horse-battery-staple"

SERIAL_RAW = "00:11:22:33:44:55"
SERIAL_NORMALIZED = "001122334455"


def load_fixture(name: str) -> Any:
    """Load a recorded synthetic API fixture by file name."""
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def mutated_single_fixture() -> dict[str, Any]:
    """A single-device payload with different key material (synthetic)."""
    payload = load_fixture("login_token_single.json")
    payload["blob"] = base64.b64encode(bytes(range(40))).decode("ascii")
    payload["broadcast_key"] = base64.b64encode(bytes(range(16))).decode("ascii")
    return payload


def stored_token(access: str = "stored-access", refresh: str = "stored-refresh") -> TokenData:
    """A stored token valid for the next hour (outside the refresh margin)."""
    return TokenData(
        access_token=access,
        refresh_token=refresh,
        expires_at=time.time() + 3600.0,
    )


def json_response(payload: Any, status: int = 200) -> httpx.Response:
    """Build a JSON httpx.Response for a mock handler."""
    return httpx.Response(status_code=status, json=payload)


def form_fields(request: httpx.Request) -> dict[str, str]:
    """Decode an application/x-www-form-urlencoded request body."""
    return dict(parse_qsl(request.content.decode("utf-8")))


class RecordingStorage:
    """TokenStorage test double that records every call."""

    def __init__(self, token: TokenData | None = None) -> None:
        self._token = token
        self.save_calls: list[TokenData] = []
        self.load_calls = 0
        self.clear_calls = 0

    def load(self) -> TokenData | None:
        self.load_calls += 1
        return self._token

    def save(self, token: TokenData) -> None:
        self.save_calls.append(token)
        self._token = token

    def clear(self) -> None:
        self.clear_calls += 1
        self._token = None


def make_cloud(
    handler: Callable[[httpx.Request], httpx.Response],
    storage: TokenStorage | None = None,
    **kwargs: Any,
) -> DanalockCloud:
    """Build a DanalockCloud wired to an httpx.MockTransport handler."""
    return DanalockCloud(
        transport=httpx.MockTransport(handler),
        storage=storage,
        **kwargs,
    )


def make_async_cloud(
    handler: Callable[[httpx.Request], httpx.Response],
    storage: TokenStorage | None = None,
    **kwargs: Any,
) -> AsyncDanalockCloud:
    """Build an AsyncDanalockCloud wired to an httpx.MockTransport handler."""
    return AsyncDanalockCloud(
        transport=httpx.MockTransport(handler),
        storage=storage,
        **kwargs,
    )
