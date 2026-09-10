"""Synchronous client for the Danalock cloud API."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from .auth import (
    EXPIRY_MARGIN_SECONDS,
    MemoryTokenStorage,
    TokenData,
    TokenStorage,
    request_password_token,
    request_refresh_token,
)
from .errors import ApiError, AuthError, DeviceNotFoundError
from .models import (
    DeviceKey,
    DeviceSummary,
    FirmwareVersion,
    key_expired,
    normalize_serial,
    parse_device_key,
    parse_device_name,
    parse_device_type,
    parse_firmware_version,
    serial_with_separators,
)

LOGGER = logging.getLogger(__name__)

# Defaults for the public API: the base host, the public OAuth2 client id,
# and the device/firmware endpoint paths — observed protocol constants of
# the public service, functionally required for the client to work.
DEFAULT_BASE_URL = "https://api.danalock.com"
DEFAULT_CLIENT_ID = "danalock-android"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_FIRMWARE_BASE_URL = "https://firmware-upgrade.danalockservices.com"

DEVICES_LIST_PATH = "/devices/v1/login_tokens"
DEVICE_LOGIN_TOKEN_PATH = "/devices/v1/{serial}/login_token"
FIRMWARE_LATEST_PATH = "/Firmware/v1/by-serial-number/{serial}/latest"


def json_body(response: httpx.Response, method: str, path: str) -> Any:
    """Strict JSON body of a 200 response; any other outcome is ApiError."""
    if response.status_code != 200:
        raise ApiError(
            f"{method} {path} returned HTTP {response.status_code}",
            status=response.status_code,
        )
    try:
        return response.json()
    except ValueError as exc:
        raise ApiError(
            f"{method} {path} returned a malformed body",
            status=response.status_code,
        ) from exc


def parse_device_entry(entry: Any, status: int) -> DeviceKey:
    """Parse one device response object; malformed input is ApiError."""
    try:
        return parse_device_key(entry)
    except (KeyError, TypeError, ValueError) as exc:
        raise ApiError(f"malformed device entry: {exc}", status=status) from exc


class DanalockCloud:
    """Synchronous client for the Danalock cloud API (unofficial).

    One httpx client per instance; the transport is injectable for tests
    (httpx.MockTransport). No client_secret is used or sent.
    """

    def __init__(
        self,
        *,
        client_id: str = DEFAULT_CLIENT_ID,
        base_url: str = DEFAULT_BASE_URL,
        firmware_base_url: str = DEFAULT_FIRMWARE_BASE_URL,
        storage: TokenStorage | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._client_id = client_id
        self._client = httpx.Client(base_url=base_url, transport=transport, timeout=timeout)
        self._firmware_client = httpx.Client(
            base_url=firmware_base_url, transport=transport, timeout=timeout
        )
        self._storage: TokenStorage = storage if storage is not None else MemoryTokenStorage()
        self._keys: dict[str, DeviceKey] = {}

    def close(self) -> None:
        """Release the underlying httpx clients (spec 0004); idempotent."""
        self._client.close()
        self._firmware_client.close()

    def login_password(self, username: str, password: str) -> None:
        """Authenticate with the password grant and store the token pair."""
        token = request_password_token(
            self._client,
            client_id=self._client_id,
            username=username,
            password=password,
        )
        self._storage.save(token)

    def refresh(self) -> None:
        """Exchange the stored refresh token for a new token pair."""
        current = self._storage.load()
        if current is None or not current.refresh_token:
            raise AuthError("no stored refresh token; log in first")
        token = request_refresh_token(
            self._client,
            client_id=self._client_id,
            refresh_token=current.refresh_token,
        )
        self._storage.save(token)

    def access_token(self) -> str:
        """Return a valid access token, refreshing it when needed."""
        token = self._stored_token()
        if token.expires_at - time.time() < EXPIRY_MARGIN_SECONDS:
            LOGGER.debug("access token is within the refresh margin, refreshing")
            self.refresh()
            token = self._stored_token()
        return token.access_token

    def devices(self) -> list[DeviceSummary]:
        """List the account's devices (spec 0002); results seed the key cache."""
        response = self._authed_request("GET", DEVICES_LIST_PATH)
        payload = json_body(response, "GET", DEVICES_LIST_PATH)
        if not isinstance(payload, list):
            raise ApiError("devices response is not a JSON array", status=response.status_code)
        summaries: list[DeviceSummary] = []
        for entry in payload:
            key = parse_device_entry(entry, response.status_code)
            summaries.append(
                DeviceSummary(
                    serial=key.serial,
                    name=parse_device_name(entry),
                    device_type=parse_device_type(entry),
                )
            )
            self._keys[key.serial] = key
        return summaries

    def get_key(self, serial: str, *, force: bool = False) -> DeviceKey:
        """Return the key for a serial, refetching it when expired or missing.

        Identity is the normalized serial (lowercase hex, no separators,
        spec 0002 R3/R4); single-device requests use the wire format
        (colon-separated) reconstructed from it. `force=True` skips the
        cache check and always refetches (spec 0005); the response is
        stored in the cache as usual.
        """
        normalized = normalize_serial(serial)
        cached = self._keys.get(normalized)
        if not force and cached is not None and not key_expired(cached):
            return cached
        path = DEVICE_LOGIN_TOKEN_PATH.format(serial=serial_with_separators(normalized))
        response = self._authed_request("GET", path)
        if response.status_code == 404:
            raise DeviceNotFoundError(normalized)
        payload = json_body(response, "GET", path)
        key = parse_device_entry(payload, response.status_code)
        self._keys[key.serial] = key
        return key

    def latest_firmware(self, serial: str) -> FirmwareVersion:
        """Return the latest published firmware for a serial (spec 0006).

        The firmware service answers without credentials: the request
        carries no Authorization header. The `url` field of the result is
        a short-lived signed link and must not be persisted.
        """
        normalized = normalize_serial(serial)
        path = FIRMWARE_LATEST_PATH.format(serial=serial_with_separators(normalized))
        response = self._firmware_client.get(path, headers={"Accept": "application/json"})
        payload = json_body(response, "GET", path)
        try:
            return parse_firmware_version(payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise ApiError(
                f"malformed firmware version: {exc}", status=response.status_code
            ) from exc

    def _stored_token(self) -> TokenData:
        token = self._storage.load()
        if token is None:
            raise AuthError("no stored token; log in first")
        return token

    def _authed_request(self, method: str, path: str) -> httpx.Response:
        """Send an authenticated request; on 401 refresh once and retry once.

        Spec 0001 R4: at most one refresh_token grant and one retry of the
        original request; a second 401 or a failed refresh is AuthError.
        """
        access_token = self.access_token()
        response = self._send(method, path, access_token)
        if response.status_code == 401:
            LOGGER.debug("received HTTP 401, refreshing token and retrying once")
            self.refresh()
            response = self._send(method, path, self._stored_token().access_token)
            if response.status_code == 401:
                raise AuthError("request rejected after token refresh (HTTP 401)")
        return response

    def _send(self, method: str, path: str, access_token: str) -> httpx.Response:
        return self._client.request(
            method,
            path,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        )
