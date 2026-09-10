# 0011 — Known cloud REST API surface

- **Status:** approved
- **Scope:** documentation only — catalogue of the known cloud REST API surface
  and its implementation status in this repository; no source, test, fixture,
  or public API change

## Summary

A reference catalogue of the cloud REST API surface known to exist for the
Danalock ecosystem, grouped by domain, with a per-endpoint implementation
status for this repository. It is the single source of truth for *what exists*
and *what this library implements*: only a small subset is implemented, and
everything else is documented here so the boundary is explicit.

This catalogue is unofficial and is not affiliated with, endorsed by, or
sponsored by Danalock AS or Poly-Control. It describes observed API behavior
only, for interoperability with devices you own.

## Motivation

The library implements a narrow slice of a much larger cloud API. Without a
written catalogue, the implemented subset is indistinguishable from "the whole
API", and consumers (for example the Home Assistant integration) cannot tell
which operations are covered and which are not. This spec records the known
surface once, in one place, and points every other document at it so counts and
scope cannot drift.

Two rules keep the catalogue honest:

- It documents the surface as behavior; it does not claim or state how the
  surface was determined beyond the sanctioned phrase `observed on the wire`.
- It never contains real deployment data: only `<serial>`, `<username>`, and
  `<access_token>` placeholders appear; response fields are named, never filled
  with live values.

## Requirements

- R1 (MUST) This spec is the single source of truth in this repository for the
  known cloud REST API surface. Other documents (README included) summarise it
  and link here instead of maintaining independent lists.
- R2 (MUST) Only endpoints marked `✓` are implemented and tested in this
  repository today. An endpoint marked `—` must not be implemented without its
  own `approved` spec.
- R3 (MUST) Status semantics:
  - `✓` — implemented in `pydanalock-cloud`;
  - `partial ✓` — the row is implemented for the listed grants or sub-cases
    only;
  - `—` — not implemented.
- R4 (MUST) Documentation-only: no `src/`, test, fixture, packaging, or public
  API behavior change. The gate (§3 of AGENTS.md) stays green.
- R5 (MUST) Publication policy: English, method-neutral wording; no source or
  method claims beyond `observed on the wire`; no source outside this
  repository is named or cited; synthetic placeholders only (never a real
  serial, account datum, token, key, or live response value).
- R6 (SHOULD) When an endpoint becomes implemented, move it from `—` to `✓`
  and update the affected counts in the same change so README and spec stay
  consistent.

## Design

Legend: **✓** implemented; **partial ✓** implemented for the listed sub-cases;
**—** not implemented. Unless the Auth column says otherwise, the request
carries a `Bearer` access token.

Totals: **64** known API paths, **4** implemented. The domain breakdown below
is the authoritative source for the summary in the README.

### A. Authentication and tokens (`api.danalock.com`)

| Method(s) | Path | Auth | Purpose | Status |
|---|---|---|---|---|
| GET | `/oauth2/authorize` | none | Browser authorization-code redirect | — |
| POST | `/oauth2/token` | none | Token grants: `authorization_code` (—), `password` (✓), `refresh_token` (✓); form-encoded body | partial ✓ |
| POST | `/oauth/v2/user/token` | HTTP Basic | Legacy client-credentials sign-in (deprecated) | — |
| GET | `/oauth/v2/user/info` | Bearer | Legacy account profile | — |
| DELETE | `/oauth/v2/user/tokens/{access_token}` | Bearer | Invalidate one issued token | — |
| GET | `/oauth2/providers` | Bearer | List linked identity providers | — |
| GET, POST | `/oauth2/providers/{provider}/link` | Bearer | Link an identity provider to the account | — |

### B. Devices and key material (`devices/v1`)

| Method(s) | Path | Auth | Purpose | Status |
|---|---|---|---|---|
| GET | `/devices/v1/login_tokens` | Bearer (+`X-Assume-User`) | All device login tokens for the account; paginated with `?page` | ✓ |
| POST | `/devices/v1/login_tokens` | Bearer | Request or register device login tokens | — |
| GET | `/devices/v1/{serial}/login_token` | Bearer (+`X-Assume-User`) | Login token for one device | ✓ |
| GET | `/devices/v1/{serial}` | Bearer | Single device record | — |
| PATCH | `/devices/v1/{serial}` | Bearer | Update mutable device attributes (name, timezone) | — |
| GET | `/devices/v1/{serial}/paired_devices` | Bearer | List paired devices | — |
| POST | `/devices/v1/{serial}/paired_devices` | Bearer | Create a device pairing | — |
| DELETE | `/devices/v1/{serial}/paired_devices[/{paired_serial}]` | Bearer | Remove one pairing, or all of them | — |
| GET | `/devices/v1/{serial}/timezone_information` | Bearer | Timezone data for a device | — |

### C. Firmware

| Method(s) | Path | Auth | Purpose | Status |
|---|---|---|---|---|
| GET | `/Firmware/v1/by-serial-number/{serial}/latest` (host `firmware-upgrade.danalockservices.com`) | none | Latest published firmware for a serial | ✓ |
| GET | `/firmware-tracker/v1/{serial}` (host `api.danalock.com`) | Bearer | Firmware version last reported for a device | — |
| GET | `/firmware-tracker/v1/outdated` | Bearer | Devices behind the latest firmware (observed on the wire: HTTP 500, unreliable) | — |
| PUT | `/firmware-tracker/v1/{serial}` | Bearer | Report the installed firmware identifier | — |

### D. Enrollment, discovery, and device management (`ekey/v3`)

| Method(s) | Path | Auth | Purpose | Status |
|---|---|---|---|---|
| POST | `/ekey/v3/discoveries` | Bearer | Discover enrollable devices | — |
| GET | `/ekey/v3/nodes` | Bearer | Client node address | — |
| GET | `/ekey/v3/devices/types` | Bearer | Enrollable device types | — |
| GET | `/ekey/v3/devices/{serial}/types` | Bearer | Device types supported by one device | — |
| POST | `/ekey/v3/devices/{serial}/enrollment_token` | Bearer | Begin enrollment | — |
| POST | `/ekey/v3/devices/{serial}/enrollment_confirmation_token` | Bearer | Confirm enrollment | — |
| DELETE | `/ekey/v3/devices/{serial}` | Bearer | Disenroll a device | — |
| PUT | `/ekey/v3/devices/{serial}` | Bearer | Update a device | — |
| GET | `/ekey/v3/devices/{serial}/key` | Bearer | Legacy device key | — |
| GET, POST | `/ekey/v3/devices/{serial}/activities` | Bearer | Device activity log | — |

### E. Users and account

| Method(s) | Path | Auth | Purpose | Status |
|---|---|---|---|---|
| GET | `/ekey/v3/users/keys` | Bearer | Key list | — |
| GET | `/ekey/v3/users/{email}/keys` | Bearer | Key list for one user (legacy metadata, includes `product`) | — |
| GET | `/ekey/v3/users/{email}` | Bearer | User record | — |
| POST | `/ekey/v3/users/{email}/register` | Bearer | Register a user | — |
| PUT | `/ekey/v3/users/{email}/password` | Bearer | Change a password | — |
| GET | `/user/v1` | Bearer | Current user | — |
| GET | `/user/v1/devices[/{id}][/notify]` | Bearer | Account devices and notification target | — |
| GET | `/user/v1/identities` | Bearer | Linked identities | — |
| POST | `/user/v1/reset_password/email` | none or Bearer | Start a password reset | — |
| POST | `/user/v1/reset_password/token` | none or Bearer | Complete a password reset | — |
| GET, POST | `/user/v1/invitations/{token}[/accept]` | Bearer | Invitations | — |

### F. Legacy platform (`ekey/v2`)

| Method(s) | Path | Auth | Purpose | Status |
|---|---|---|---|---|
| GET, POST | `/ekey/v2/users` | Bearer | Users collection | — |
| GET | `/ekey/v2/users/{username}` | Bearer | User record | — |
| POST | `/ekey/v2/users/{email}/register` | Bearer | Register a user | — |
| POST | `/ekey/v2/users/{username}/keys` | Bearer | All keys (legacy V2/V3 key bundle) | — |
| GET, POST | `/ekey/v2/locks` | Bearer | Locks collection | — |
| POST | `/ekey/v2/locks/{serial}` | Bearer | Include a lock | — |
| GET, POST | `/ekey/v2/locks/{serial}/users[/{idstr}]` | Bearer | Users of a lock | — |
| GET, POST | `/ekey/v2/groups/{name}[/members]` | Bearer | Groups | — |

### G. Legacy locks and advertisements (`ekey/v3`)

| Method(s) | Path | Auth | Purpose | Status |
|---|---|---|---|---|
| POST | `/ekey/v3/locks/{serial}/unlock` | Bearer | Remote unlock | — |
| POST | `/ekey/v3/locks/{serial}/lock` | Bearer | Remote lock | — |
| GET, POST | `/ekey/v3/locks/{serial}/users` | Bearer | Users of a lock | — |
| GET, POST | `/ekey/v3/locks/{serial}/groups` | Bearer | Groups of a lock | — |
| GET | `/ekey/v3/locks/{serial}/logs` | Bearer | Lock logs | — |
| GET, POST | `/ekey/v3/advertisements` | Bearer | Broadcast/advertisement records | — |
| GET | `/ekey/v3/advertisements/{token}`, plus a misspelled twin of the same path | Bearer | One advertisement record | — |

### H. Bridge

| Method(s) | Path | Auth | Purpose | Status |
|---|---|---|---|---|
| POST | `/bridge/v1/execute` | Bearer (+`X-Assume-User`) | Execute an operation through a bridge | — |
| POST | `/bridge/v1/poll` | Bearer | Poll bridge results | — |

### I. Invitations

| Method(s) | Path | Auth | Purpose | Status |
|---|---|---|---|---|
| GET | `/invitations/v1/received` | Bearer | Invitations received by the account | — |
| POST | `/invitations/v1/received` | Bearer | Act on a received invitation | — |

### J. PIN-code aliases

| Method(s) | Path | Auth | Purpose | Status |
|---|---|---|---|---|
| GET | `/pin_codes/alias/v1/{serial}` | Bearer | List PIN aliases for a device | — |
| PUT | `/pin_codes/alias/v1/{serial}/{index}` | Bearer | Set a PIN alias | — |
| DELETE | `/pin_codes/alias/v1/{serial}/{index}` | Bearer | Delete a PIN alias | — |

### K. Support

| Method(s) | Path | Auth | Purpose | Status |
|---|---|---|---|---|
| DELETE | `/support/user` | Bearer | Delete account/support data | — |

### Known request/response details

Field names only; values are always synthetic in examples and tests.

- **Hosts.** `api.danalock.com` serves the OAuth, `devices/v1`,
  `firmware-tracker`, `ekey/v2`, `ekey/v3`, `bridge`, `invitations`,
  `pin_codes`, `support`, and `user/v1` paths. The published-firmware lookup
  uses the separate host `firmware-upgrade.danalockservices.com`.
- **Serial wire format.** Lowercase `xx:xx:xx:xx:xx:xx`. A separator-free or
  uppercase form is rejected with `422` on the single-device and latest-firmware
  paths.
- **OAuth token.** The request body is form-encoded; `client_id` is required
  and no `client_secret` is sent for the supported grants. The response carries
  `access_token`, `refresh_token`, and `expires_in`.
- **Delegated access.** Some device and bridge endpoints accept an
  `X-Assume-User` header to act on behalf of another account.
- **UserDevices** (`/devices/v1/*login_token*`). Object shape:
  `{device{serial_number, name, timezone, device_type}, blob, broadcast_key,
  metadata{permissions[{id, name, description}], valid_from, valid_to}}`.
  `blob` and `broadcast_key` are base64; `broadcast_key` is 16 bytes. Both
  `serial_number` and `serialNumber` spellings occur on the wire. The
  `valid_from`/`valid_to` window drives when the key must be refetched.
- **FirmwareVersion** (`/Firmware/v1/by-serial-number/{serial}/latest`):
  `{firmware_identifier, maturity, url, version}`. `url` is a short-lived
  signed link and must not be persisted. The request succeeds without
  credentials.
- **Firmware tracker** (`/firmware-tracker/v1/{serial}`):
  `{serialNumber, product, pcb_version, firmware_version, firmware_timestamp,
  firmware_identifier}`; populated by the `PUT`. The `/outdated` path was
  observed on the wire to return HTTP 500.
- **Enrollment.** The enrollment-token response is
  `{serial_number, enrollment_token, server_public_key}`; the confirmation
  request body is `{enrollment_result_token}` and the response is
  `{enrollment_confirmation_token, serial_number}`.
- **Node.** `/ekey/v3/nodes` returns `{serialNumber}`, the client node address.
- **Paired devices.** Responses use `{device}` and `{child, parent, type}`.
- **Discovery.** `/ekey/v3/discoveries` returns
  `{devices[{serial_number, display_name, enrolled,
  product{firmware, version}}]}`.
- **User.** `/user/v1` returns `{id, alias, display_name, domain,
  email_address, "2fa"}`.
- **Legacy key list.** `/ekey/v3/users/{email}/keys` returns
  `product{name, type, version, firmware{firmware_version, pcb_version,
  updates, variation}}`. Its `firmware_version` is product metadata, not the
  lock's installed firmware version.
- **Bridge execute result.** `/bridge/v1/execute` returns `{operation,
  results[{afi_status, afi_status_text, dmi_status*, lock_status,
  battery_level, firmware_*, pin_codes*, ...}]}`.
- **Pagination.** `/devices/v1/login_tokens` accepts a `?page` query parameter.

## API

No public API change. This spec is a reference catalogue; it introduces no
runtime symbol, endpoint implementation, or behavior change.

## Test plan

- No new tests: documentation-only change.
- Gate (AGENTS.md §3) must be green: `.venv/bin/ruff check .`,
  `.venv/bin/ruff format --check .`, `.venv/bin/mypy`,
  `.venv/bin/pytest -m "not live"`.
- Publication-policy check on the changed files: no source or
  application/version names, no method or provenance claims, no real serials,
  account data, tokens, or live values.

## Acceptance criteria

- This spec lists every known API path from the inventory with an explicit
  status, plus the known request/response field details.
- Totals in this spec match the README summary and the README links here.
- R1–R6 hold; the gate is green; skeptic review returns no `BLOCKING`.

## Out of scope

- Implementing any endpoint marked `—` (each requires its own `approved`
  spec).
- Tests or fixtures for unimplemented endpoints.
- New runtime code, packaging, or public API changes.
- Research notes, provenance, and source material.

## Status

`approved` (documentation-only catalogue; no behavior change).
