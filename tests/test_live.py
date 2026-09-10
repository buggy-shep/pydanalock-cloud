"""Live tests against the production API. Run manually only:

    .venv/bin/pytest -m live

Credentials come from the environment (DANALOCK_USERNAME,
DANALOCK_PASSWORD). Never print or log tokens or key material here.
"""

from __future__ import annotations

import os

import pytest

from pydanalock.cloud import AsyncDanalockCloud, DanalockCloud

_USERNAME = os.environ.get("DANALOCK_USERNAME")
_PASSWORD = os.environ.get("DANALOCK_PASSWORD")

requires_credentials = pytest.mark.skipif(
    not (_USERNAME and _PASSWORD),
    reason="DANALOCK_USERNAME/DANALOCK_PASSWORD are not set",
)


@pytest.mark.live
@requires_credentials
def test_live_password_login() -> None:
    client = DanalockCloud()
    client.login_password(_USERNAME, _PASSWORD)
    assert client.access_token()


@pytest.mark.live
@requires_credentials
def test_live_devices_and_key() -> None:
    client = DanalockCloud()
    client.login_password(_USERNAME, _PASSWORD)
    summaries = client.devices()
    assert summaries
    key = client.get_key(summaries[0].serial)
    assert key.serial == summaries[0].serial
    assert key.login_blob
    assert len(key.broadcast_key) == 16


@pytest.mark.live
@requires_credentials
async def test_live_full_flow_async() -> None:
    client = AsyncDanalockCloud()
    await client.login_password(_USERNAME, _PASSWORD)
    summaries = await client.devices()
    assert summaries
    key = await client.get_key(summaries[0].serial)
    assert key.serial == summaries[0].serial
    assert key.login_blob
    assert len(key.broadcast_key) == 16
