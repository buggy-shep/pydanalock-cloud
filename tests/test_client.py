"""Unit tests for the public client API (spec 0003).

Covers sync/async parity against the same MockTransport fixtures,
single-flight token refresh between coroutines, the typed error
hierarchy, and constructor dependency injection.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime

import httpx
import pytest
from conftest import (
    PASSWORD,
    SERIAL_NORMALIZED,
    SERIAL_RAW,
    USERNAME,
    RecordingStorage,
    form_fields,
    json_response,
    load_fixture,
    make_async_cloud,
    make_cloud,
    mutated_single_fixture,
    stored_token,
)

from pydanalock.cloud import (
    ApiError,
    AsyncDanalockCloud,
    AuthError,
    DanalockCloud,
    DanalockCloudError,
    DeviceKey,
    DeviceNotFoundError,
    TokenData,
)


async def test_async_password_login_matches_sync() -> None:
    fx = load_fixture("oauth2_token_password.json")

    def handler(request: httpx.Request) -> httpx.Response:
        assert form_fields(request)["grant_type"] == "password"
        return json_response(fx)

    sync_storage = RecordingStorage()
    make_cloud(handler, storage=sync_storage).login_password(USERNAME, PASSWORD)

    async_storage = RecordingStorage()
    await make_async_cloud(handler, storage=async_storage).login_password(USERNAME, PASSWORD)

    sync_token = sync_storage.load()
    async_token = async_storage.load()
    assert async_token is not None and sync_token is not None
    assert async_token.access_token == sync_token.access_token == fx["access_token"]
    assert async_token.refresh_token == sync_token.refresh_token
    assert async_token.expires_at == pytest.approx(sync_token.expires_at, abs=30.0)


async def test_async_refresh_matches_sync() -> None:
    fx = load_fixture("oauth2_token_refresh.json")

    def handler(request: httpx.Request) -> httpx.Response:
        assert form_fields(request)["grant_type"] == "refresh_token"
        return json_response(fx)

    sync_storage = RecordingStorage(stored_token())
    make_cloud(handler, storage=sync_storage).refresh()

    async_storage = RecordingStorage(stored_token())
    await make_async_cloud(handler, storage=async_storage).refresh()

    sync_token = sync_storage.load()
    async_token = async_storage.load()
    assert async_token is not None and sync_token is not None
    assert async_token.access_token == sync_token.access_token == fx["access_token"]
    assert async_token.refresh_token == sync_token.refresh_token
    assert async_token.expires_at == pytest.approx(sync_token.expires_at, abs=30.0)


async def test_async_devices_and_get_key_match_sync() -> None:
    fx_list = load_fixture("login_tokens_v1.json")
    fx_single = load_fixture("login_token_single.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/devices/v1/login_tokens":
            return json_response(fx_list)
        return json_response(fx_single)

    sync_cloud = make_cloud(handler, storage=RecordingStorage(stored_token()))
    async_cloud = make_async_cloud(handler, storage=RecordingStorage(stored_token()))

    sync_summaries = sync_cloud.devices()
    async_summaries = await async_cloud.devices()
    assert async_summaries == sync_summaries

    sync_key = sync_cloud.get_key(SERIAL_RAW)
    async_key = await async_cloud.get_key(SERIAL_RAW)
    assert isinstance(async_key, DeviceKey)
    assert async_key == sync_key


async def test_async_access_token_refreshes_within_margin() -> None:
    fx = load_fixture("oauth2_token_refresh.json")
    token_calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        token_calls.append(request)
        return json_response(fx)

    soon = TokenData(
        access_token="old-access",
        refresh_token="stored-refresh",
        expires_at=time.time() + 30.0,
    )
    storage = RecordingStorage(soon)
    cloud = make_async_cloud(handler, storage=storage)

    assert await cloud.access_token() == fx["access_token"]
    assert len(token_calls) == 1


async def test_async_single_flight_margin_refresh() -> None:
    fx = load_fixture("oauth2_token_refresh.json")
    token_calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        token_calls.append(request)
        return json_response(fx)

    soon = TokenData(
        access_token="old-access",
        refresh_token="stored-refresh",
        expires_at=time.time() + 30.0,
    )
    storage = RecordingStorage(soon)
    cloud = make_async_cloud(handler, storage=storage)

    tokens = await asyncio.gather(*[cloud.access_token() for _ in range(8)])

    assert tokens == [fx["access_token"]] * 8
    assert len(token_calls) == 1


async def test_async_single_flight_401_refresh_and_retry() -> None:
    fx_devices = load_fixture("login_tokens_v1.json")
    fx_token = load_fixture("oauth2_token_refresh.json")
    token_calls: list[httpx.Request] = []
    state = {"refreshed": False}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            token_calls.append(request)
            state["refreshed"] = True
            return json_response(fx_token)
        if not state["refreshed"]:
            return httpx.Response(401, json={"error": "invalid_token"})
        return json_response(fx_devices)

    storage = RecordingStorage(stored_token("stored-access", "stored-refresh"))
    cloud = make_async_cloud(handler, storage=storage)

    results = await asyncio.gather(*[cloud.devices() for _ in range(5)])

    assert len(token_calls) == 1
    assert [s[0].serial for s in results] == ["001122334455"] * 5
    updated = storage.load()
    assert updated is not None
    assert updated.access_token == fx_token["access_token"]


async def test_async_401_after_failed_refresh_raises_auth_error() -> None:
    device_calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            device_calls.append(request)
            return httpx.Response(401, json={"error": "invalid_token"})
        return json_response({"error": "invalid_grant"}, status=400)

    cloud = make_async_cloud(
        handler, storage=RecordingStorage(stored_token("stored-access", "stored-refresh"))
    )

    with pytest.raises(AuthError):
        await cloud.devices()

    assert len(device_calls) == 1


async def test_async_unknown_serial_raises_device_not_found() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/devices/v1/ff:ee:dd:cc:bb:aa/login_token"
        return json_response({"error": "not_found"}, status=404)

    cloud = make_async_cloud(handler, storage=RecordingStorage(stored_token()))

    with pytest.raises(DeviceNotFoundError) as exc_info:
        await cloud.get_key("ff:ee:dd:cc:bb:aa")

    assert exc_info.value.serial == "ffeeddccbbaa"


async def test_async_devices_error_status_raises_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response({"error": "boom"}, status=500)

    cloud = make_async_cloud(handler, storage=RecordingStorage(stored_token()))

    with pytest.raises(ApiError) as exc_info:
        await cloud.devices()

    assert exc_info.value.status == 500


def test_error_hierarchy() -> None:
    assert issubclass(AuthError, DanalockCloudError)
    assert issubclass(ApiError, DanalockCloudError)
    assert issubclass(DeviceNotFoundError, DanalockCloudError)
    assert not issubclass(ApiError, AuthError)
    assert not issubclass(DeviceNotFoundError, ApiError)


async def test_async_no_secrets_in_logs(caplog: pytest.LogCaptureFixture) -> None:
    fx_login = load_fixture("oauth2_token_password.json")
    fx_refresh = load_fixture("oauth2_token_refresh.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            if form_fields(request)["grant_type"] == "password":
                return json_response(fx_login)
            return json_response(fx_refresh)
        return httpx.Response(401, json={"error": "invalid_token"})

    cloud = make_async_cloud(handler, storage=RecordingStorage())

    with caplog.at_level(logging.DEBUG):
        await cloud.login_password(USERNAME, PASSWORD)
        with pytest.raises(AuthError):
            await cloud.devices()

    text = caplog.text
    for secret in (
        PASSWORD,
        USERNAME,
        fx_login["access_token"],
        fx_login["refresh_token"],
        fx_refresh["access_token"],
        fx_refresh["refresh_token"],
        "Bearer",
    ):
        assert secret not in text


def test_dependency_injection_transport_and_base_url() -> None:
    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        return json_response(load_fixture("login_tokens_v1.json"))

    sync_cloud = DanalockCloud(
        base_url="https://sync.example.test",
        transport=httpx.MockTransport(handler),
        storage=RecordingStorage(stored_token()),
    )
    sync_cloud.devices()
    assert urls[-1].startswith("https://sync.example.test/devices/v1/login_tokens")


async def test_async_dependency_injection_transport_and_base_url() -> None:
    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        return json_response(load_fixture("login_tokens_v1.json"))

    async_cloud = AsyncDanalockCloud(
        base_url="https://async.example.test",
        transport=httpx.MockTransport(handler),
        storage=RecordingStorage(stored_token()),
    )
    await async_cloud.devices()
    assert urls[-1].startswith("https://async.example.test/devices/v1/login_tokens")


async def test_async_password_grant_forwards_custom_client_id() -> None:
    fx = load_fixture("oauth2_token_password.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(form_fields(request))
        return json_response(fx)

    await make_async_cloud(handler, client_id="my-client").login_password(USERNAME, PASSWORD)

    assert seen["client_id"] == "my-client"


def test_timeout_injection_on_both_clients() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(load_fixture("login_tokens_v1.json"))

    sync_cloud = make_cloud(handler, storage=RecordingStorage(stored_token()), timeout=12.5)
    async_cloud = make_async_cloud(handler, storage=RecordingStorage(stored_token()), timeout=12.5)

    assert sync_cloud._client.timeout == httpx.Timeout(12.5)
    assert async_cloud._client.timeout == httpx.Timeout(12.5)


async def test_async_get_key_refetches_expired_cached_key() -> None:
    list_calls: list[httpx.Request] = []
    single_calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/devices/v1/login_tokens":
            list_calls.append(request)
            return json_response(load_fixture("login_tokens_v1_expired.json"))
        single_calls.append(request)
        assert request.url.path == "/devices/v1/00:11:22:33:44:55/login_token"
        return json_response(load_fixture("login_token_single.json"))

    cloud = make_async_cloud(handler, storage=RecordingStorage(stored_token()))
    await cloud.devices()
    key = await cloud.get_key(SERIAL_RAW)
    again = await cloud.get_key(SERIAL_RAW)

    assert key == again
    assert key.valid_to == datetime(2099, 1, 1, tzinfo=UTC)
    assert len(list_calls) == 1
    assert len(single_calls) == 1


async def test_async_get_key_force_refetches_valid_cached_key() -> None:
    requests: list[httpx.Request] = []
    payloads = [load_fixture("login_token_single.json"), mutated_single_fixture()]

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return json_response(payloads.pop(0))

    cloud = make_async_cloud(handler, storage=RecordingStorage(stored_token()))
    first = await cloud.get_key(SERIAL_RAW)
    forced = await cloud.get_key(SERIAL_RAW, force=True)

    assert first.serial == forced.serial == SERIAL_NORMALIZED
    assert first.login_blob != forced.login_blob
    assert len(requests) == 2
    assert requests[-1].url.path == "/devices/v1/00:11:22:33:44:55/login_token"

    # the forced response is cached: a later non-forced call needs no request
    assert await cloud.get_key(SERIAL_RAW) == forced
    assert len(requests) == 2


async def test_async_get_key_force_fetches_without_cache() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return json_response(load_fixture("login_token_single.json"))

    cloud = make_async_cloud(handler, storage=RecordingStorage(stored_token()))

    key = await cloud.get_key(SERIAL_RAW, force=True)
    assert key.serial == SERIAL_NORMALIZED
    assert len(requests) == 1


async def test_async_get_key_force_false_serves_valid_cached_key() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return json_response(load_fixture("login_token_single.json"))

    cloud = make_async_cloud(handler, storage=RecordingStorage(stored_token()))
    first = await cloud.get_key(SERIAL_RAW)

    assert await cloud.get_key(SERIAL_RAW, force=False) is first
    assert len(requests) == 1


async def test_async_get_key_force_maps_404_to_device_not_found() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response({"error": "not_found"}, status=404)

    cloud = make_async_cloud(handler, storage=RecordingStorage(stored_token()))

    with pytest.raises(DeviceNotFoundError) as exc_info:
        await cloud.get_key(SERIAL_RAW, force=True)

    assert exc_info.value.serial == SERIAL_NORMALIZED
