# 0006 — Latest firmware lookup

- **Status:** implemented
- **Scope:** `pydanalock.cloud` sync + async clients

## Summary

Adds a `FirmwareVersion` model and a `latest_firmware(serial)` method to
both clients. The method queries the firmware service
`GET /Firmware/v1/by-serial-number/{serial}/latest` on a dedicated base
host and returns the latest published firmware for a lock: the version
string, a firmware identifier, a maturity label, and a download URL.

## Motivation

Consumers need to know the newest available firmware version so they can
compare it against the version reported by the lock itself and surface
"update available". The firmware service is a separate host from
`api.danalock.com` and, unlike the devices API, answers without
credentials: no Authorization header is sent, and none is accepted.
Malformed serials are rejected by the service with HTTP 422 as a request
validation failure, not as an authentication failure.

## Requirements

- R1 (MUST) `FirmwareVersion` is a frozen dataclass with the string
  fields `firmware_identifier`, `maturity`, `url`, `version`. Parsing is
  strict: a non-object payload, a missing field, or a non-string value
  is malformed.
- R2 (MUST) `latest_firmware(serial)` on `DanalockCloud` and
  `AsyncDanalockCloud` (sync/async parity). The serial is normalized
  first; an invalid serial raises `ValueError` before any request. The
  request path uses the wire format (lowercase, colon-separated).
- R3 (MUST) The request carries no `Authorization` header.
- R4 (MUST) The firmware service has its own base URL, overridable with
  a `firmware_base_url` constructor keyword (default
  `https://firmware-upgrade.danalockservices.com`), served by a second
  httpx client per instance. The device API client is unchanged.
- R5 (MUST) Any non-200 response maps to `ApiError` with the HTTP status
  attached; a malformed body (non-JSON or wrong shape) also maps to
  `ApiError`.
- R6 (MUST) `close()` (sync) and `aclose()` (async) release both
  underlying clients and stay idempotent (spec 0004 semantics).
- R7 (SHOULD) The `url` field is a short-lived signed link; the model
  and README must document that consumers must not persist it.
- R8 (MUST) Additive change: SemVer-minor feature release; the public
  version moves to `0.4.0`.

## Design

- The constructor grows a `firmware_base_url` keyword and builds a
  second httpx client against it with the same injected transport,
  timeout, and test-injection rules as the main client. `latest_firmware`
  routes only through that client, so mock transports in tests see one
  request per call, routed by path (no device API paths collide).
- Error mapping reuses the existing helpers: non-200 and non-JSON bodies
  are `ApiError` via `json_body`; wrong-shaped JSON payloads are wrapped
  into `ApiError` with the response status attached.
- No changes to authentication, device listing, or key retrieval; no
  firmware-related state is cached (the service already answers cheaply
  and the download URL is short-lived).

## API

```python
@dataclass(frozen=True)
class FirmwareVersion:
    firmware_identifier: str
    maturity: str
    url: str
    version: str


class DanalockCloud:
    def __init__(
        self,
        *,
        client_id: str = DEFAULT_CLIENT_ID,
        base_url: str = DEFAULT_BASE_URL,
        firmware_base_url: str = DEFAULT_FIRMWARE_BASE_URL,
        storage: TokenStorage | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None: ...

    def latest_firmware(self, serial: str) -> FirmwareVersion: ...


class AsyncDanalockCloud:
    # mirrors DanalockCloud: firmware_base_url keyword, async def latest_firmware
```

## Test plan

MockTransport unit tests, synthetic fixtures only:

- Sync + async parity: a success fixture returns a parsed
  `FirmwareVersion`; the request hits
  `/Firmware/v1/by-serial-number/{serial}/latest` with the colon wire
  serial and no `Authorization` header.
- Malformed serial raises `ValueError` and sends no request.
- HTTP 422 maps to `ApiError` with `status == 422`; other error statuses
  (e.g. 500) map to `ApiError` with their status.
- A non-JSON 200 body and a wrong-shaped JSON body map to `ApiError`.
- `close()`/`aclose()` release both clients: after them, both a device
  request and a firmware request fail; a second close is a no-op.
- A custom `firmware_base_url` is honored.

## Acceptance criteria

- Unit tests green; full gate green (§3); skeptic review without
  `BLOCKING`.

## Out of scope

- Firmware download or installation; persisting the signed `url`.
- The firmware-tracker endpoints; installed-version reporting (the lock
  reports its own version over BLE).
- Any caching of the lookup result.

## Status

`implemented` (spec approved with a recorded decision in the group
planning 2026-09-09 conversation: installed version comes from the lock
over BLE, latest version from this endpoint; the lookup is
unauthenticated, the download URL is ephemeral and never persisted.
Implemented 2026-09-09: `latest_firmware` merged, version 0.4.0).
