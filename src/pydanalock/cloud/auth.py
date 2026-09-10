"""Token model, pluggable storage, and token-endpoint plumbing (spec 0001)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from .errors import ApiError, AuthError

LOGGER = logging.getLogger(__name__)

TOKEN_PATH = "/oauth2/token"
EXPIRY_MARGIN_SECONDS = 60.0


@dataclass(frozen=True)
class TokenData:
    """OAuth2 token pair with a locally computed expiry (epoch seconds)."""

    access_token: str
    refresh_token: str
    expires_at: float


class TokenStorage(Protocol):
    """Pluggable token persistence; hosts supply persistent implementations."""

    def load(self) -> TokenData | None: ...

    def save(self, token: TokenData) -> None: ...

    def clear(self) -> None: ...


class MemoryTokenStorage:
    """Process-local TokenStorage implementation."""

    def __init__(self) -> None:
        self._token: TokenData | None = None

    def load(self) -> TokenData | None:
        return self._token

    def save(self, token: TokenData) -> None:
        self._token = token

    def clear(self) -> None:
        self._token = None


def parse_token_payload(payload: Any, status: int) -> TokenData:
    """Build TokenData from a token-endpoint JSON body (spec 0001 R3)."""
    if not isinstance(payload, dict):
        raise ApiError("token response is not a JSON object", status=status)
    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise ApiError("token response is missing access_token", status=status)
    refresh_token = payload.get("refresh_token")
    expires_in = payload.get("expires_in")
    if not isinstance(refresh_token, str):
        refresh_token = ""
    if not isinstance(expires_in, (int, float)) or isinstance(expires_in, bool):
        raise ApiError("token response is missing a numeric expires_in", status=status)
    return TokenData(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=time.time() + float(expires_in),
    )


def _post_token(client: httpx.Client, data: dict[str, str]) -> httpx.Response:
    LOGGER.debug("requesting token grant from %s", TOKEN_PATH)
    return client.post(TOKEN_PATH, data=data, headers={"Accept": "application/json"})


def _raise_for_token_status(response: httpx.Response) -> None:
    if response.status_code == 400:
        raise AuthError("token endpoint rejected the grant (HTTP 400)")
    if response.status_code != 200:
        raise ApiError(
            f"token endpoint returned HTTP {response.status_code}",
            status=response.status_code,
        )


def _token_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError as exc:
        raise ApiError("token response is not valid JSON", status=response.status_code) from exc


GRANT_PASSWORD = "password"
GRANT_REFRESH = "refresh_token"


def password_grant_body(*, client_id: str, username: str, password: str) -> dict[str, str]:
    """Form fields for the password grant; no client_secret is used."""
    return {
        "grant_type": GRANT_PASSWORD,
        "username": username,
        "password": password,
        "client_id": client_id,
    }


def refresh_grant_body(*, client_id: str, refresh_token: str) -> dict[str, str]:
    """Form fields for the refresh_token grant."""
    return {
        "grant_type": GRANT_REFRESH,
        "refresh_token": refresh_token,
        "client_id": client_id,
    }


def token_from_response(response: httpx.Response, *, grant: str) -> TokenData:
    """Map a token-endpoint response to TokenData (spec 0001 R3/R4).

    A 400 is AuthError for both grants; any other failure of the refresh
    grant is AuthError as well, so refresh never surfaces ApiError.
    """
    try:
        _raise_for_token_status(response)
        return parse_token_payload(_token_json(response), status=response.status_code)
    except ApiError as exc:
        if grant == GRANT_REFRESH:
            raise AuthError(f"token refresh failed: {exc}") from exc
        raise


def request_password_token(
    client: httpx.Client,
    *,
    client_id: str,
    username: str,
    password: str,
) -> TokenData:
    """Exchange username and password for a token pair (password grant)."""
    response = _post_token(
        client,
        password_grant_body(client_id=client_id, username=username, password=password),
    )
    return token_from_response(response, grant=GRANT_PASSWORD)


def request_refresh_token(
    client: httpx.Client,
    *,
    client_id: str,
    refresh_token: str,
) -> TokenData:
    """Exchange a refresh token for a new pair; every failure is AuthError."""
    response = _post_token(
        client,
        refresh_grant_body(client_id=client_id, refresh_token=refresh_token),
    )
    return token_from_response(response, grant=GRANT_REFRESH)
