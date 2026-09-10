"""Unit tests for client lifecycle close methods (spec 0004).

Both clients must expose a supported way to release the underlying httpx
client; the methods are idempotent and additive.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from conftest import (
    PASSWORD,
    USERNAME,
    json_response,
    load_fixture,
    make_async_cloud,
    make_cloud,
)

from pydanalock.cloud import AsyncDanalockCloud, DanalockCloud


def _token_handler(request: httpx.Request) -> httpx.Response:
    """Serve the password-grant token fixture for any request."""
    payload: Any = load_fixture("oauth2_token_password.json")
    return json_response(payload)


def test_close_releases_the_sync_client() -> None:
    """After close(), the httpx client is closed and requests fail."""
    client: DanalockCloud = make_cloud(_token_handler)
    client.login_password(USERNAME, PASSWORD)
    client.close()
    with pytest.raises(RuntimeError):
        client.devices()
    client.close()  # a second close() after use is a no-op


def test_close_is_idempotent() -> None:
    """Repeated close() calls are safe no-ops (spec 0004 R2)."""
    client: DanalockCloud = make_cloud(_token_handler)
    client.close()
    client.close()


async def test_aclose_releases_the_async_client() -> None:
    """After aclose(), the httpx client is closed and requests fail."""
    client: AsyncDanalockCloud = make_async_cloud(_token_handler)
    await client.login_password(USERNAME, PASSWORD)
    await client.aclose()
    with pytest.raises(RuntimeError):
        await client.devices()
    await client.aclose()  # a second aclose() after use is a no-op


async def test_aclose_is_idempotent() -> None:
    """Repeated aclose() calls are safe no-ops (spec 0004 R1)."""
    client: AsyncDanalockCloud = make_async_cloud(_token_handler)
    await client.aclose()
    await client.aclose()
