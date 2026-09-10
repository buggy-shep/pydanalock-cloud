# 0001 — OAuth2 authentication

- **Status:** implemented
- **Scope:** `pydanalock.cloud` authentication against the Danalock cloud API

## Summary

The Danalock cloud (base URL `https://api.danalock.com`) issues OAuth2
tokens. This spec defines the token flows the client supports, token storage,
and automatic refresh.

## Motivation

Every device/keys endpoint requires a bearer access token; keys are the
contract payload shared with the BLE library, so authentication is the cloud
client's first deliverable.

## Requirements

- R1 (MUST) Token endpoint: `POST /oauth2/token`,
  `application/x-www-form-urlencoded`. Supported grants:
  - `refresh_token` — used automatically;
  - `password` (resource-owner password credentials) — fallback for scripted
    or hosted use; requires username and password.

  The `authorization_code` grant is deferred to a future spec (recorded
  decision, 2026-09-06): obtaining the code requires a browser redirect
  owned by the host application, which no current consumer drives.
- R2 (MUST) `client_id` is required for every grant; the library default is
  `danalock-android` (a value observed working against the production API);
  it is configurable.
- R3 (MUST) Token response fields used: `access_token`, `refresh_token`,
  `expires_in`. The client computes `expires_at` locally (epoch seconds).
- R4 (MUST) Automatic refresh: a 401 response, or a token expiring within a
  60-second safety margin, triggers one `refresh_token` grant and one retry
  of the original request. Refresh failure surfaces as `AuthError`.
- R5 (MUST) Token storage is pluggable:

```python
class TokenStorage(Protocol):
    def load(self) -> TokenData | None: ...
    def save(self, token: TokenData) -> None: ...
    def clear(self) -> None: ...
```

  An in-memory implementation MUST be provided; host applications supply
  persistent ones. Tokens and credentials MUST NOT be logged or committed.
- R6 (MUST) Typed errors: `AuthError` (invalid credentials/grant), `ApiError`
  (unexpected HTTP status), transport errors propagated from httpx.
- R7 (SHOULD) All requests set `Accept: application/json` and use a
  configurable timeout (default 30 seconds).

## Design

- One httpx client instance per `DanalockCloud`; the base URL and transport
  are overridable for tests (MockTransport).
- The password grant exists because the authorization-code flow needs a
  browser/redirect endpoint that standalone scripts and servers do not have.

## API

```python
@dataclass(frozen=True)
class TokenData:
    access_token: str
    refresh_token: str
    expires_at: float  # epoch seconds


class DanalockCloud:
    def __init__(
        self,
        *,
        client_id: str = "danalock-android",
        base_url: str = "https://api.danalock.com",
        storage: TokenStorage | None = None,
    ) -> None: ...
    def login_password(self, username: str, password: str) -> None: ...
    def refresh(self) -> None: ...
    def access_token(self) -> str: ...  # valid token, refreshing as needed
```

(Async variants are defined in spec 0003.)

## Test plan

- httpx MockTransport fixtures: successful password grant; refresh grant;
  401 → refresh → retry; refresh failure → `AuthError`; storage save/load.
- Expired-token margin: a token within the 60-second margin triggers refresh
  before the request.
- No secrets in logged output (test asserts redaction).

## Acceptance criteria

- Unit tests green (mock transport); gate green; skeptic without `BLOCKING`.
- Live (manual, `live` marker): password login against the production API
  succeeds with real credentials from environment variables.

## Out of scope

- Authorization-code grant and its redirect UI (deferred to a future spec;
  see R1); key retrieval (spec 0002); public API surface (spec 0003).

## Status

`implemented` (2026-09-06: password-grant authentication with token
storage, refresh and expiry tracking merged, version 0.1.0).
