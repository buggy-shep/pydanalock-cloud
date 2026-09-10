# 0002 — Devices and key retrieval

- **Status:** implemented
- **Scope:** `pydanalock.cloud` device list and login-token/broadcast-key
  retrieval

## Summary

After authentication the client fetches the user's devices and their key
material: a per-device login token blob (consumed by the BLE library for
session login) and a broadcast key (used to decrypt state advertisements).

## Motivation

Keys are the only coupling between the cloud and BLE layers (group contract
`DeviceKey`); this spec defines how they are fetched, parsed, and refreshed.

## Requirements

- R1 (MUST) Endpoints (Bearer token required):
  - `GET /devices/v1/login_tokens` — all devices;
  - `GET /devices/v1/{serial}/login_token` — one device.
- R2 (MUST) Response model (one entry per device):
  - `device.serial_number` — device identity;
  - `device.device_type` — device product type (observed value
    `danalockv3`); optional — exposed on the summary as `device_type`
    (`None` when the field is absent); consumers use it for the device
    model and to gate device-type-specific behavior; both `device_type`
    and `deviceType` spellings are accepted;
  - `blob` — base64-encoded login token blob;
  - `broadcast_key` — base64-encoded 16-byte advertisement key;
  - `metadata.permissions` — list of `{id, name, description}`;
  - `metadata.valid_from`, `metadata.valid_to` — validity window.
- R3 (MUST) Serial normalization: lowercase hex without separators
  (`1A:2B:3C:4D:5E:6F` → `1a2b3c4d5e6f`); the normalized form is the
  canonical identity everywhere in the group.
- R4 (MUST) `get_key(serial)` returns a `DeviceKey` (see spec 0003) and
  re-fetches automatically when the cached key is expired (`valid_to` in the
  past) or missing.
- R5 (MUST) Expired access token handling follows spec 0001 (401 → refresh →
  single retry).
- R6 (MUST) Typed errors: unknown serial → typed device-not-found error;
  malformed responses → `ApiError`.

## Design

- Keys are kept as opaque bytes end-to-end: base64 is decoded once at the
  boundary; the BLE library receives `bytes` and never inspects them.
- Response parsing accepts both `serial_number` and `serialNumber` spellings
  observed in the wild.
- The single-device path parameter uses the wire serial format (lowercase
  hex, colon-separated, as observed against the production API: the
  separator-free form is rejected with `422 validation_failed`). The
  normalized separator-free form stays the canonical identity (R3) for
  cache keys and `DeviceKey.serial`; the wire form is reconstructed from it.

## API

```python
@dataclass(frozen=True)
class DeviceSummary:
    serial: str
    name: str | None = None
    device_type: str | None = None


@dataclass(frozen=True)
class Permission:
    id: str
    name: str
    description: str


@dataclass(frozen=True)
class DeviceKey:
    serial: str
    login_blob: bytes
    broadcast_key: bytes
    valid_from: datetime | None
    valid_to: datetime | None
    permissions: tuple[Permission, ...]


class DanalockCloud:
    def devices(self) -> list[DeviceSummary]: ...
    def get_key(self, serial: str) -> DeviceKey: ...
```

## Test plan

- MockTransport fixtures: list response parsing (both serial spellings),
  single-device fetch, base64 decode, validity parsing, serial
  normalization.
- Expiry: a cached key past `valid_to` triggers a refetch.
- Negative: 401 after failed refresh → `AuthError`; unknown serial.

## Acceptance criteria

- Unit tests green; gate green; skeptic without `BLOCKING`.
- Live (manual, `live` marker): a real account returns at least one key
  (credentials via environment; key material stored only in `*.local.json`
  files that are gitignored).

## Out of scope

- Legacy key endpoints (`/ekey/v2/users/...`, `/ekey/v3/...`) — not needed
  for the current flow; enrollment — BLE-side, later spec.

## Status

`implemented` (spec approved 2026-09-06. Amended 2026-09-07 (recorded
decision in the group conversation): `device.device_type` is parsed and
exposed on `DeviceSummary` (observed value `danalockv3`, verified against
the production API). Implemented 2026-09-06/07: devices and key retrieval
merged; the wire serial format fix and the device_type exposure
followed).
