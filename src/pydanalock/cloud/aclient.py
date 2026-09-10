"""Asynchronous client mirroring DanalockCloud (spec 0003)."""

from __future__ import annotations

import asyncio
import logging
import time

import httpx

from .auth import (
    EXPIRY_MARGIN_SECONDS,
    GRANT_PASSWORD,
    GRANT_REFRESH,
    TOKEN_PATH,
    MemoryTokenStorage,
    TokenData,
    TokenStorage,
    password_grant_body,
    refresh_grant_body,
    token_from_response,
)
from .client import (
    DEFAULT_BASE_URL,
    DEFAULT_CLIENT_ID,
    DEFAULT_FIRMWARE_BASE_URL,
    DEFAULT_TIMEOUT_SECONDS,
    DEVICE_LOGIN_TOKEN_PATH,
    DEVICES_LIST_PATH,
    FIRMWARE_LATEST_PATH,
    json_body,
    parse_device_entry,
)
from .errors import ApiError, AuthError, DeviceNotFoundError
from .models import (
    DeviceKey,
    DeviceSummary,
    FirmwareVersion,
    key_expired,
    normalize_serial,
    parse_device_name,
    parse_device_type,
    parse_firmware_version,
    serial_with_separators,
)

LOGGER = logging.getLogger(__name__)


class AsyncDanalockCloud:
    """Asynchronous client for the Danalock cloud API (unofficial).

    Mirrors DanalockCloud method-for-method (same signatures, async def).
    Safe to share between coroutines: one httpx.AsyncClient and
    single-flight token refresh (spec 0003 R6).
    """

    def __init__(
        self,
        *,
        client_id: str = DEFAULT_CLIENT_ID,
        base_url: str = DEFAULT_BASE_URL,
        firmware_base_url: str = DEFAULT_FIRMWARE_BASE_URL,
        storage: TokenStorage | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._client_id = client_id
        self._client = httpx.AsyncClient(base_url=base_url, transport=transport, timeout=timeout)
        self._firmware_client = httpx.AsyncClient(
            base_url=firmware_base_url, transport=transport, timeout=timeout
        )
        self._storage: TokenStorage = storage if storage is not None else MemoryTokenStorage()
        self._keys: dict[str, DeviceKey] = {}
        self._refresh_lock = asyncio.Lock()

    async def aclose(self) -> None:
        """Release the underlying httpx clients (spec 0004); idempotent."""
        await self._client.aclose()
        await self._firmware_client.aclose()

    async def login_password(self, username: str, password: str) -> None:
        """Authenticate with the password grant and store the token pair."""
        response = await self._client.post(
            TOKEN_PATH,
            data=password_grant_body(
                client_id=self._client_id, username=username, password=password
            ),
            headers={"Accept": "application/json"},
        )
        self._storage.save(token_from_response(response, grant=GRANT_PASSWORD))

    async def refresh(self) -> None:
        """Exchange the stored refresh token for a new pair (single-flight)."""
        async with self._refresh_lock:
            await self._refresh_unlocked()

    async def access_token(self) -> str:
        """Return a valid access token, refreshing it when needed."""
        token = self._stored_token()
        if token.expires_at - time.time() < EXPIRY_MARGIN_SECONDS:
            LOGGER.debug("access token is within the refresh margin, refreshing")
            await self._ensure_fresh_token()
            token = self._stored_token()
        return token.access_token

    async def devices(self) -> list[DeviceSummary]:
        """List the account's devices (spec 0002); results seed the key cache."""
        response = await self._authed_request("GET", DEVICES_LIST_PATH)
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

    async def get_key(self, serial: str, *, force: bool = False) -> DeviceKey:
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
        response = await self._authed_request("GET", path)
        if response.status_code == 404:
            raise DeviceNotFoundError(normalized)
        payload = json_body(response, "GET", path)
        key = parse_device_entry(payload, response.status_code)
        self._keys[key.serial] = key
        return key

    async def latest_firmware(self, serial: str) -> FirmwareVersion:
        """Return the latest published firmware for a serial (spec 0006).

        The firmware service answers without credentials: the request
        carries no Authorization header. The `url` field of the result is
        a short-lived signed link and must not be persisted.
        """
        normalized = normalize_serial(serial)
        path = FIRMWARE_LATEST_PATH.format(serial=serial_with_separators(normalized))
        response = await self._firmware_client.get(path, headers={"Accept": "application/json"})
        payload = json_body(response, "GET", path)
        try:
            return parse_firmware_version(payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise ApiError(
                f"malformed firmware version: {exc}", status=response.status_code
            ) from exc

    async def _refresh_unlocked(self) -> None:
        current = self._storage.load()
        if current is None or not current.refresh_token:
            raise AuthError("no stored refresh token; log in first")
        response = await self._client.post(
            TOKEN_PATH,
            data=refresh_grant_body(client_id=self._client_id, refresh_token=current.refresh_token),
            headers={"Accept": "application/json"},
        )
        self._storage.save(token_from_response(response, grant=GRANT_REFRESH))

    async def _ensure_fresh_token(self) -> None:
        """Refresh once for all waiters; re-check under the lock (spec 0003 R6)."""
        async with self._refresh_lock:
            token = self._storage.load()
            if token is not None and token.expires_at - time.time() >= EXPIRY_MARGIN_SECONDS:
                return  # another coroutine refreshed while we waited
            await self._refresh_unlocked()

    async def _authed_request(self, method: str, path: str) -> httpx.Response:
        """Send an authenticated request; on 401 refresh once and retry once.

        Spec 0001 R4 with single-flight refresh: coroutines that race into a
        401 share one refresh_token grant, then each retries its own request
        once; a second 401 or a failed refresh is AuthError.
        """
        access = await self.access_token()
        response = await self._send(method, path, access)
        if response.status_code == 401:
            LOGGER.debug("received HTTP 401, refreshing token and retrying once")
            async with self._refresh_lock:
                current = self._stored_token()
                if current.access_token == access:
                    await self._refresh_unlocked()
                    current = self._stored_token()
            response = await self._send(method, path, current.access_token)
            if response.status_code == 401:
                raise AuthError("request rejected after token refresh (HTTP 401)")
        return response

    async def _send(self, method: str, path: str, access_token: str) -> httpx.Response:
        return await self._client.request(
            method,
            path,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        )

    def _stored_token(self) -> TokenData:
        token = self._storage.load()
        if token is None:
            raise AuthError("no stored token; log in first")
        return token
