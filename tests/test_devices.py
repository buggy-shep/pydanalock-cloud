"""Unit tests for device listing and key retrieval (spec 0002).

Responses come from the synthetic fixtures in tests/fixtures/; all serials
and key bytes there are fake. The `DeviceKey` layout (serial, login_blob,
broadcast_key, valid_from, valid_to, permissions) is the group contract.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime

import httpx
import pytest
from conftest import (
    SERIAL_NORMALIZED,
    SERIAL_RAW,
    RecordingStorage,
    form_fields,
    json_response,
    load_fixture,
    make_cloud,
    mutated_single_fixture,
    stored_token,
)

from pydanalock.cloud import (
    ApiError,
    AuthError,
    DanalockCloud,
    DeviceKey,
    DeviceNotFoundError,
    DeviceSummary,
    Permission,
)
from pydanalock.cloud.models import normalize_serial, serial_with_separators


def authorized_cloud(
    handler,
    storage: RecordingStorage | None = None,
    **kwargs,
) -> DanalockCloud:
    return make_cloud(handler, storage=storage or RecordingStorage(stored_token()), **kwargs)


def test_devices_parses_bare_array_fixture() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.method == "GET"
        assert request.url.path == "/devices/v1/login_tokens"
        assert request.headers["Authorization"] == "Bearer stored-access"
        return json_response(load_fixture("login_tokens_v1.json"))

    summaries = authorized_cloud(handler).devices()

    assert len(requests) == 1
    assert summaries == [
        DeviceSummary(serial=SERIAL_NORMALIZED, name="Fixture Lock", device_type="danalockv3")
    ]


def test_devices_parses_device_type() -> None:
    """device.device_type is exposed on the summary (spec 0002 R2)."""
    fx = load_fixture("login_tokens_v1.json")
    assert fx[0]["device"]["device_type"] == "danalockv3"

    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(fx)

    summaries = authorized_cloud(handler).devices()

    assert summaries[0].device_type == "danalockv3"


def test_devices_without_device_type_summarizes_none() -> None:
    """A response without device.device_type yields device_type None
    (spec 0002 R2)."""
    payload = load_fixture("login_tokens_v1.json")
    del payload[0]["device"]["device_type"]

    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(payload)

    summaries = authorized_cloud(handler).devices()

    assert summaries[0].device_type is None


def test_devices_accepts_camel_case_device_type_spelling() -> None:
    payload = load_fixture("login_tokens_v1.json")
    payload[0]["device"]["deviceType"] = payload[0]["device"].pop("device_type")

    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(payload)

    summaries = authorized_cloud(handler).devices()

    assert summaries[0].device_type == "danalockv3"


def test_get_key_decodes_base64_and_parses_metadata() -> None:
    fx = load_fixture("login_tokens_v1.json")
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return json_response(fx)

    cloud = authorized_cloud(handler)
    cloud.devices()
    key = cloud.get_key(SERIAL_RAW)

    assert isinstance(key, DeviceKey)
    assert key.serial == SERIAL_NORMALIZED
    assert key.login_blob == base64.b64decode(fx[0]["blob"])
    assert len(key.broadcast_key) == 16
    assert key.valid_from == datetime(2026, 1, 1, tzinfo=UTC)
    assert key.valid_to == datetime(2099, 1, 1, tzinfo=UTC)
    assert key.permissions == (
        Permission(id="0", name="owner", description="synthetic owner permission"),
        Permission(id="1", name="guest", description="synthetic guest permission"),
    )
    assert len(requests) == 1


def test_get_key_accepts_already_normalized_serial() -> None:
    fx = load_fixture("login_tokens_v1.json")

    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(fx)

    cloud = authorized_cloud(handler)
    cloud.devices()

    assert cloud.get_key(SERIAL_NORMALIZED).serial == SERIAL_NORMALIZED


@pytest.mark.parametrize("raw", ["00:11:22:33:44:55", "00-11-22-33-44-55", "00:11-22:33-44:55"])
def test_get_key_refetches_by_normalized_serial(raw: str) -> None:
    fx = load_fixture("login_token_single.json")
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        assert request.url.path == f"/devices/v1/{SERIAL_RAW}/login_token"
        return json_response(fx)

    cloud = authorized_cloud(handler)
    key = cloud.get_key(raw)

    assert key.serial == SERIAL_NORMALIZED
    assert paths == [f"/devices/v1/{SERIAL_RAW}/login_token"]


@pytest.mark.parametrize("raw", ["00:11:22:33:44:55", "00-11-22-33-44-55", "001122334455"])
def test_serial_wire_format_round_trip(raw: str) -> None:
    assert serial_with_separators(normalize_serial(raw)) == SERIAL_RAW


def test_get_key_serves_second_call_from_cache() -> None:
    fx = load_fixture("login_token_single.json")
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return json_response(fx)

    cloud = authorized_cloud(handler)
    first = cloud.get_key(SERIAL_RAW)
    second = cloud.get_key(SERIAL_NORMALIZED)

    assert first == second
    assert len(requests) == 1


def test_get_key_refetches_expired_cached_key() -> None:
    list_requests: list[httpx.Request] = []
    single_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/devices/v1/login_tokens":
            list_requests.append(request)
            return json_response(load_fixture("login_tokens_v1_expired.json"))
        single_requests.append(request)
        assert request.url.path == f"/devices/v1/{SERIAL_RAW}/login_token"
        return json_response(load_fixture("login_token_single.json"))

    cloud = authorized_cloud(handler)
    cloud.devices()
    key = cloud.get_key(SERIAL_RAW)
    again = cloud.get_key(SERIAL_RAW)

    assert key == again
    assert key.valid_to == datetime(2099, 1, 1, tzinfo=UTC)
    assert len(list_requests) == 1
    assert len(single_requests) == 1


def test_get_key_force_refetches_valid_cached_key() -> None:
    requests: list[httpx.Request] = []
    payloads = [load_fixture("login_token_single.json"), mutated_single_fixture()]

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return json_response(payloads.pop(0))

    cloud = authorized_cloud(handler)
    first = cloud.get_key(SERIAL_RAW)
    forced = cloud.get_key(SERIAL_RAW, force=True)

    assert first.serial == forced.serial == SERIAL_NORMALIZED
    assert first.login_blob != forced.login_blob
    assert len(requests) == 2
    assert requests[-1].url.path == f"/devices/v1/{SERIAL_RAW}/login_token"

    # the forced response is cached: a later non-forced call needs no request
    assert cloud.get_key(SERIAL_RAW) == forced
    assert len(requests) == 2


def test_get_key_force_fetches_without_cache() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return json_response(load_fixture("login_token_single.json"))

    cloud = authorized_cloud(handler)

    assert cloud.get_key(SERIAL_RAW, force=True).serial == SERIAL_NORMALIZED
    assert len(requests) == 1


def test_get_key_force_false_serves_valid_cached_key() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return json_response(load_fixture("login_token_single.json"))

    cloud = authorized_cloud(handler)
    first = cloud.get_key(SERIAL_RAW)

    assert cloud.get_key(SERIAL_RAW, force=False) is first
    assert len(requests) == 1


def test_get_key_force_maps_404_to_device_not_found() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response({"error": "not_found"}, status=404)

    cloud = authorized_cloud(handler)

    with pytest.raises(DeviceNotFoundError) as exc_info:
        cloud.get_key(SERIAL_RAW, force=True)

    assert exc_info.value.serial == SERIAL_NORMALIZED


def test_get_key_force_maps_malformed_body_to_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response({"unexpected": "shape"})

    with pytest.raises(ApiError):
        authorized_cloud(handler).get_key(SERIAL_RAW, force=True)


def test_get_key_with_invalid_serial_raises_value_error() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return json_response({})

    with pytest.raises(ValueError):
        authorized_cloud(handler).get_key("not-a-serial")

    assert requests == []


def test_devices_with_short_broadcast_key_raises_api_error() -> None:
    payload = load_fixture("login_tokens_v1.json")
    payload[0]["broadcast_key"] = base64.b64encode(bytes(8)).decode("ascii")

    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(payload)

    with pytest.raises(ApiError):
        authorized_cloud(handler).devices()


def test_unknown_serial_raises_device_not_found() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/devices/v1/{SERIAL_RAW}/login_token"
        return json_response({"error": "not_found"}, status=404)

    with pytest.raises(DeviceNotFoundError) as exc_info:
        authorized_cloud(handler).get_key(SERIAL_RAW)

    assert exc_info.value.serial == SERIAL_NORMALIZED


def test_devices_401_then_refresh_then_retry() -> None:
    fx_devices = load_fixture("login_tokens_v1.json")
    fx_token = load_fixture("oauth2_token_refresh.json")
    list_calls: list[httpx.Request] = []
    token_calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            list_calls.append(request)
            if len(list_calls) == 1:
                return httpx.Response(401, json={"error": "invalid_token"})
            return json_response(fx_devices)
        token_calls.append(request)
        assert form_fields(request)["grant_type"] == "refresh_token"
        return json_response(fx_token)

    summaries = authorized_cloud(handler).devices()

    assert summaries[0].serial == SERIAL_NORMALIZED
    assert len(list_calls) == 2
    assert len(token_calls) == 1


def test_devices_401_after_failed_refresh_raises_auth_error() -> None:
    list_calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            list_calls.append(request)
            return httpx.Response(401, json={"error": "invalid_token"})
        return json_response({"error": "invalid_grant"}, status=400)

    with pytest.raises(AuthError):
        authorized_cloud(handler).devices()

    assert len(list_calls) == 1


def test_devices_devices_error_status_raises_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response({"error": "boom"}, status=503)

    with pytest.raises(ApiError) as exc_info:
        authorized_cloud(handler).devices()

    assert exc_info.value.status == 503


def test_devices_malformed_json_body_raises_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>not json</html>")

    with pytest.raises(ApiError):
        authorized_cloud(handler).devices()


def test_devices_non_array_body_raises_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response({"devices": []})

    with pytest.raises(ApiError):
        authorized_cloud(handler).devices()


@pytest.mark.parametrize(
    ("mutation", "target"),
    [
        ("bad_base64", "blob"),
        ("missing_metadata", "metadata"),
        ("permissions_not_list", "permissions"),
    ],
)
def test_malformed_device_entry_raises_api_error(mutation: str, target: str) -> None:
    payload = load_fixture("login_tokens_v1.json")
    if mutation == "bad_base64":
        payload[0][target] = "!!!not-base64!!!"
    elif mutation == "missing_metadata":
        del payload[0][target]
    else:
        payload[0]["metadata"][target] = "owner"

    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(payload)

    with pytest.raises(ApiError):
        authorized_cloud(handler).devices()


def test_devices_accepts_camel_case_serial_spelling() -> None:
    payload = load_fixture("login_tokens_v1.json")
    payload[0]["device"]["serialNumber"] = payload[0]["device"].pop("serial_number")

    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(payload)

    summaries = authorized_cloud(handler).devices()

    assert summaries == [
        DeviceSummary(serial=SERIAL_NORMALIZED, name="Fixture Lock", device_type="danalockv3")
    ]


def test_single_endpoint_accepts_camel_case_serial_spelling() -> None:
    payload = load_fixture("login_token_single.json")
    payload["device"]["serialNumber"] = payload["device"].pop("serial_number")

    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(payload)

    key = authorized_cloud(handler).get_key(SERIAL_RAW)

    assert key.serial == SERIAL_NORMALIZED
