"""Unit tests for the latest firmware lookup (spec 0006).

The firmware service is a separate host that answers without
credentials; responses come from the synthetic fixtures in
tests/fixtures/. The signed download URL in the fixture is fake and
never used.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from conftest import (
    PASSWORD,
    SERIAL_NORMALIZED,
    SERIAL_RAW,
    USERNAME,
    json_response,
    load_fixture,
    make_async_cloud,
    make_cloud,
)

from pydanalock.cloud import ApiError, AsyncDanalockCloud, DanalockCloud, FirmwareVersion

FIRMWARE_LATEST_PATH = f"/Firmware/v1/by-serial-number/{SERIAL_RAW}/latest"

FIRMWARE_VERSION = FirmwareVersion(
    firmware_identifier="DanalockV3_101-025_D1_1.2.3_20990101120000",
    maturity="production",
    url="https://s3.example.com/danalock-v3/app.bin?X-Amz-Expires=120&X-Amz-Signature=synthetic",
    version="1.2.3",
)


def _serve_firmware(request: httpx.Request) -> httpx.Response:
    assert request.method == "GET"
    assert request.url.path == FIRMWARE_LATEST_PATH
    return json_response(load_fixture("firmware_latest.json"))


def _token_or_firmware_handler(request: httpx.Request) -> httpx.Response:
    """Token fixture for any path, firmware fixture for the latest path."""
    if request.url.path == FIRMWARE_LATEST_PATH:
        return _serve_firmware(request)
    return json_response(load_fixture("oauth2_token_password.json"))


def test_latest_firmware_parses_fixture() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _serve_firmware(request)

    cloud: DanalockCloud = make_cloud(handler)

    assert cloud.latest_firmware(SERIAL_RAW) == FIRMWARE_VERSION
    assert len(requests) == 1


async def test_latest_firmware_async_parity() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _serve_firmware(request)

    cloud: AsyncDanalockCloud = make_async_cloud(handler)

    assert await cloud.latest_firmware(SERIAL_RAW) == FIRMWARE_VERSION
    assert len(requests) == 1


def test_latest_firmware_sends_no_authorization_header() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "Authorization" not in request.headers
        assert request.headers["Accept"] == "application/json"
        return _serve_firmware(request)

    cloud: DanalockCloud = make_cloud(handler)

    assert cloud.latest_firmware(SERIAL_RAW) == FIRMWARE_VERSION


async def test_latest_firmware_async_sends_no_authorization_header() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "Authorization" not in request.headers
        assert request.headers["Accept"] == "application/json"
        return _serve_firmware(request)

    cloud: AsyncDanalockCloud = make_async_cloud(handler)

    assert await cloud.latest_firmware(SERIAL_RAW) == FIRMWARE_VERSION


def test_latest_firmware_accepts_normalized_serial() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return _serve_firmware(request)

    cloud: DanalockCloud = make_cloud(handler)

    assert cloud.latest_firmware(SERIAL_NORMALIZED) == FIRMWARE_VERSION
    assert paths == [FIRMWARE_LATEST_PATH]


def test_latest_firmware_invalid_serial_raises_value_error() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _serve_firmware(request)

    with pytest.raises(ValueError):
        make_cloud(handler).latest_firmware("not-a-serial")

    assert requests == []


def test_latest_firmware_422_maps_to_api_error() -> None:
    """422 is a serial validation failure, not an auth failure."""
    payload: dict[str, Any] = {
        "errors": [
            {
                "field": "serial_number",
                "message": "SerialNumber is not a valid serial number.",
            }
        ],
        "message": "Validation Failed",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(payload, status=422)

    with pytest.raises(ApiError) as exc_info:
        make_cloud(handler).latest_firmware(SERIAL_RAW)

    assert exc_info.value.status == 422


def test_latest_firmware_error_status_maps_to_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response({"error": "boom"}, status=503)

    with pytest.raises(ApiError) as exc_info:
        make_cloud(handler).latest_firmware(SERIAL_RAW)

    assert exc_info.value.status == 503


def test_latest_firmware_non_json_body_maps_to_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>not json</html>")

    with pytest.raises(ApiError):
        make_cloud(handler).latest_firmware(SERIAL_RAW)


@pytest.mark.parametrize(
    "payload",
    [
        {"unexpected": "shape"},
        {"firmware_identifier": "x", "maturity": "production", "url": "u"},
        {
            "firmware_identifier": "x",
            "maturity": "production",
            "url": "u",
            "version": 123,
        },
        "not-an-object",
    ],
)
def test_latest_firmware_malformed_payload_maps_to_api_error(payload: Any) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(payload)

    with pytest.raises(ApiError):
        make_cloud(handler).latest_firmware(SERIAL_RAW)


def test_custom_firmware_base_url_is_honored() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "firmware.example.test"
        return _serve_firmware(request)

    cloud: DanalockCloud = make_cloud(
        handler,
        base_url="https://api.example.test",
        firmware_base_url="https://firmware.example.test",
    )

    assert cloud.latest_firmware(SERIAL_RAW) == FIRMWARE_VERSION


def test_close_releases_both_clients() -> None:
    cloud: DanalockCloud = make_cloud(_token_or_firmware_handler)
    cloud.login_password(USERNAME, PASSWORD)
    cloud.close()

    with pytest.raises(RuntimeError):
        cloud.devices()
    with pytest.raises(RuntimeError):
        cloud.latest_firmware(SERIAL_RAW)
    cloud.close()  # a second close() after use is a no-op


async def test_aclose_releases_both_clients() -> None:
    cloud: AsyncDanalockCloud = make_async_cloud(_token_or_firmware_handler)
    await cloud.login_password(USERNAME, PASSWORD)
    await cloud.aclose()

    with pytest.raises(RuntimeError):
        await cloud.devices()
    with pytest.raises(RuntimeError):
        await cloud.latest_firmware(SERIAL_RAW)
    await cloud.aclose()  # a second aclose() after use is a no-op
