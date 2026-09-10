"""Unit tests for OAuth2 authentication (spec 0001).

The 401-retry behavior (spec 0001 R4) is exercised through the internal
request helper `DanalockCloud._authed_request`: the public surface it serves
(authenticated JSON endpoints) arrives with spec 0002.
"""

from __future__ import annotations

import logging
import time

import httpx
import pytest
from conftest import (
    PASSWORD,
    USERNAME,
    RecordingStorage,
    form_fields,
    json_response,
    load_fixture,
    make_cloud,
    stored_token,
)

from pydanalock.cloud import ApiError, AuthError, MemoryTokenStorage, TokenData


def test_password_grant_posts_form_and_stores_token() -> None:
    fx = load_fixture("oauth2_token_password.json")
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.method == "POST"
        assert request.url.path == "/oauth2/token"
        assert request.headers["Content-Type"] == "application/x-www-form-urlencoded"
        assert request.headers["Accept"] == "application/json"
        assert form_fields(request) == {
            "grant_type": "password",
            "username": USERNAME,
            "password": PASSWORD,
            "client_id": "danalock-android",
        }
        return json_response(fx)

    storage = RecordingStorage()
    make_cloud(handler, storage=storage).login_password(USERNAME, PASSWORD)

    assert len(requests) == 1
    token = storage.load()
    assert token is not None
    assert token.access_token == fx["access_token"]
    assert token.refresh_token == fx["refresh_token"]
    assert token.expires_at == pytest.approx(time.time() + fx["expires_in"], abs=30.0)


def test_password_grant_forwards_custom_client_id() -> None:
    fx = load_fixture("oauth2_token_password.json")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(form_fields(request))
        return json_response(fx)

    make_cloud(handler, client_id="my-client").login_password(USERNAME, PASSWORD)

    assert seen["client_id"] == "my-client"


def test_refresh_grant_posts_form_and_saves_new_token() -> None:
    fx = load_fixture("oauth2_token_refresh.json")
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert form_fields(request) == {
            "grant_type": "refresh_token",
            "refresh_token": "stored-refresh-token",
            "client_id": "danalock-android",
        }
        return json_response(fx)

    storage = RecordingStorage(stored_token("stored-access", "stored-refresh-token"))
    make_cloud(handler, storage=storage).refresh()

    assert len(requests) == 1
    updated = storage.load()
    assert updated is not None
    assert updated.access_token == fx["access_token"]
    assert updated.refresh_token == fx["refresh_token"]


def test_refresh_without_stored_token_raises_auth_error() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return json_response({})

    with pytest.raises(AuthError):
        make_cloud(handler, storage=RecordingStorage()).refresh()

    assert requests == []


def test_token_response_without_expires_in_raises_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(
            {"access_token": "fx-access-token", "refresh_token": "fx-refresh-token"}
        )

    with pytest.raises(ApiError) as exc_info:
        make_cloud(handler).login_password(USERNAME, PASSWORD)

    assert exc_info.value.status == 200


def test_token_response_without_refresh_token_is_tolerated() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if form_fields(request)["grant_type"] == "password":
            return json_response({"access_token": "fx-access-token", "expires_in": 3600})
        return json_response({"error": "invalid_grant"}, status=400)

    storage = RecordingStorage()
    cloud = make_cloud(handler, storage=storage)
    cloud.login_password(USERNAME, PASSWORD)

    token = storage.load()
    assert token is not None
    assert token.refresh_token == ""
    with pytest.raises(AuthError):
        cloud.refresh()


def test_refresh_failure_surfaces_auth_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response({"error": "server_error"}, status=500)

    storage = RecordingStorage(stored_token("stored-access", "stored-refresh"))
    with pytest.raises(AuthError):
        make_cloud(handler, storage=storage).refresh()

    assert storage.save_calls == []


def test_login_invalid_grant_raises_auth_error_and_keeps_storage() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(
            {"error": "invalid_grant", "error_description": "Bad credentials"},
            status=400,
        )

    storage = RecordingStorage()
    with pytest.raises(AuthError):
        make_cloud(handler, storage=storage).login_password(USERNAME, PASSWORD)

    assert storage.save_calls == []
    assert storage.load() is None


def test_login_server_error_raises_api_error_with_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response({"error": "server_error"}, status=500)

    with pytest.raises(ApiError) as exc_info:
        make_cloud(handler).login_password(USERNAME, PASSWORD)

    assert exc_info.value.status == 500


def test_access_token_returns_stored_token_without_requests() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return json_response({})

    storage = RecordingStorage(stored_token("stored-access", "stored-refresh"))
    cloud = make_cloud(handler, storage=storage)

    assert cloud.access_token() == "stored-access"
    assert requests == []


def test_access_token_without_login_raises_auth_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response({})

    with pytest.raises(AuthError):
        make_cloud(handler).access_token()


def test_access_token_refreshes_within_expiry_margin() -> None:
    fx = load_fixture("oauth2_token_refresh.json")
    token_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        token_requests.append(request)
        assert form_fields(request)["grant_type"] == "refresh_token"
        return json_response(fx)

    soon = TokenData(
        access_token="old-access",
        refresh_token="stored-refresh",
        expires_at=time.time() + 30.0,
    )
    storage = RecordingStorage(soon)
    cloud = make_cloud(handler, storage=storage)

    assert cloud.access_token() == fx["access_token"]
    assert len(token_requests) == 1
    updated = storage.load()
    assert updated is not None
    assert updated.access_token == fx["access_token"]


def test_401_triggers_single_refresh_and_single_retry() -> None:
    fx_devices = load_fixture("login_tokens_v1.json")
    fx_token = load_fixture("oauth2_token_refresh.json")
    device_requests: list[httpx.Request] = []
    token_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/devices/v1/login_tokens":
            device_requests.append(request)
            if len(device_requests) == 1:
                assert request.headers["Authorization"] == "Bearer stored-access"
                return httpx.Response(401, json={"error": "invalid_token"})
            assert request.headers["Authorization"] == f"Bearer {fx_token['access_token']}"
            assert request.headers["Accept"] == "application/json"
            return json_response(fx_devices)
        assert request.method == "POST" and request.url.path == "/oauth2/token"
        token_requests.append(request)
        return json_response(fx_token)

    storage = RecordingStorage(stored_token("stored-access", "stored-refresh"))
    cloud = make_cloud(handler, storage=storage)

    response = cloud._authed_request("GET", "/devices/v1/login_tokens")

    assert response.status_code == 200
    assert len(device_requests) == 2
    assert len(token_requests) == 1
    updated = storage.load()
    assert updated is not None
    assert updated.access_token == fx_token["access_token"]


def test_401_with_failed_refresh_raises_auth_error_without_retry() -> None:
    device_requests: list[httpx.Request] = []
    token_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            device_requests.append(request)
            return httpx.Response(401, json={"error": "invalid_token"})
        token_requests.append(request)
        return json_response({"error": "invalid_grant"}, status=400)

    storage = RecordingStorage(stored_token("stored-access", "stored-refresh"))
    cloud = make_cloud(handler, storage=storage)

    with pytest.raises(AuthError):
        cloud._authed_request("GET", "/devices/v1/login_tokens")

    assert len(device_requests) == 1
    assert len(token_requests) == 1


def test_storage_receives_save_after_login_and_refresh() -> None:
    fx_login = load_fixture("oauth2_token_password.json")
    fx_refresh = load_fixture("oauth2_token_refresh.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if form_fields(request)["grant_type"] == "password":
            return json_response(fx_login)
        return json_response(fx_refresh)

    storage = RecordingStorage()
    cloud = make_cloud(handler, storage=storage)
    cloud.login_password(USERNAME, PASSWORD)
    cloud.refresh()

    assert [t.access_token for t in storage.save_calls] == [
        fx_login["access_token"],
        fx_refresh["access_token"],
    ]


def test_memory_token_storage_round_trip() -> None:
    storage = MemoryTokenStorage()
    assert storage.load() is None

    token = TokenData(access_token="a", refresh_token="b", expires_at=123.0)
    storage.save(token)
    assert storage.load() == token

    storage.clear()
    assert storage.load() is None


def test_no_secrets_in_logs(caplog: pytest.LogCaptureFixture) -> None:
    fx_login = load_fixture("oauth2_token_password.json")
    fx_refresh = load_fixture("oauth2_token_refresh.json")
    device_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            if form_fields(request)["grant_type"] == "password":
                return json_response(fx_login)
            return json_response(fx_refresh)
        device_requests.append(request)
        if len(device_requests) == 1:
            return httpx.Response(401, json={"error": "invalid_token"})
        return json_response(load_fixture("login_tokens_v1.json"))

    storage = RecordingStorage()
    cloud = make_cloud(handler, storage=storage)

    with caplog.at_level(logging.DEBUG):
        cloud.login_password(USERNAME, PASSWORD)
        cloud._authed_request("GET", "/devices/v1/login_tokens")

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
