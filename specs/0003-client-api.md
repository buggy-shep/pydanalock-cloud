# 0003 — Public client API

- **Status:** implemented
- **Scope:** `pydanalock.cloud` public surface (sync + async)

## Summary

Defines the complete public API of the cloud client: `DanalockCloud` (sync)
and `AsyncDanalockCloud` (async), the `DeviceKey` group contract type, and
error types.

## Motivation

Home Assistant integrations need asyncio; scripts prefer sync. Both faces
must stay in lockstep to keep the group contract stable.

## Requirements

- R1 (MUST) `DeviceKey` is the canonical group contract type (identical field
  names in `pydanalock.cloud` and its consumers):

```python
@dataclass(frozen=True)
class DeviceKey:
    serial: str  # normalized hex, no separators
    login_blob: bytes  # login token blob (opaque)
    broadcast_key: bytes  # advertisement key (opaque)
    valid_from: datetime | None
    valid_to: datetime | None
    permissions: tuple[Permission, ...]
```

- R2 (MUST) Sync API: `login_password`, `refresh`, `devices`, `get_key`,
  `access_token` (see specs 0001/0002).
- R3 (MUST) Async API mirrors R2 exactly (`AsyncDanalockCloud`, same
  signatures, `async def`).
- R4 (MUST) Dependency injection: httpx transport/storage/base URL/client_id
  are constructor parameters; defaults per specs 0001/0002.
- R5 (MUST) Error hierarchy: `DanalockCloudError` base; `AuthError`;
  `ApiError` (carries the HTTP status); typed device-not-found error.
- R6 (SHOULD) The async client is safe to share between coroutines (single
  httpx client, single-flight token refresh).
- R7 (MUST) `get_key` auto-refreshes expired keys (spec 0002 R4).

## Test plan

- Parity tests: sync and async variants produce identical results against the
  same MockTransport fixtures.
- Error mapping tests; concurrency test (parallel `get_key` calls trigger at
  most one refresh).

## Acceptance criteria

- Unit tests green; gate green; skeptic without `BLOCKING`.
- Live (manual, `live` marker): full flow login → devices → key with real
  credentials from the environment.

## Out of scope

- BLE usage of the keys (`pydanalock-ble` spec 0004); HA config flow.

## Status

`implemented` (2026-09-06: public client API — async and sync clients,
typed errors — merged, version 0.1.0).
