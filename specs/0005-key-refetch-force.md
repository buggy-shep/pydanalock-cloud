# 0005 — Forced key refetch

- **Status:** implemented
- **Scope:** `pydanalock.cloud` sync + async clients

## Summary

Adds a `force` keyword to `DanalockCloud.get_key` and
`AsyncDanalockCloud.get_key`. With `force=True` the client always requests
`GET /devices/v1/{serial}/login_token`, ignoring a still-valid cache entry;
the response is stored in the key cache as before. The default
`force=False` keeps the existing behavior unchanged.

## Motivation

`get_key` refetches only when the cached key is missing or past its
`valid_to` window. Consumers need a way to replace a key that the lock
rejects even though it has not expired locally (cloud-side key rotation,
host clock drift): a forced fetch is the only way to obtain fresh key
material. The single-device response carries the login blob and the
broadcast key together, so one forced request refreshes both.

## Requirements

- R1 (MUST) `get_key(serial, *, force: bool = False)` on both clients.
  `force=True` always performs the single-device request, bypassing the
  cache check.
- R2 (MUST) The fetched key is stored in the key cache exactly as in the
  non-forced path, so subsequent non-forced calls are served from cache.
- R3 (MUST) `force=False` (the default) behaves exactly as before; no
  existing call sites change.
- R4 (MUST) Error mapping (404 → `DeviceNotFoundError`, malformed or
  failed responses → `ApiError`, auth failures → `AuthError`) is
  identical for forced and non-forced fetches.
- R5 (MUST) Additive change only: SemVer-minor feature release; the
  public version moves to `0.3.0`.

## Design

- The keyword turns the cache lookup into a no-op short-circuit: with
  `force=True` the cached entry is not returned and the request always
  runs; the response overwrites the cache entry under the same normalized
  serial as usual.
- No changes to `devices()`, authentication, or the models.

## API

```python
class DanalockCloud:
    def get_key(self, serial: str, *, force: bool = False) -> DeviceKey: ...


class AsyncDanalockCloud:
    async def get_key(self, serial: str, *, force: bool = False) -> DeviceKey: ...
```

## Test plan

- Sync + async parity (MockTransport): `force=True` on a valid cached key
  performs a second single-device request and returns the newly fetched
  key; a later non-forced call serves the new key from cache without a
  request.
- `force=True` without any cached key fetches normally.
- `force=False` on a valid cached key performs no request (unchanged
  default).
- Existing suite stays green.

## Acceptance criteria

- Unit tests green; gate green; skeptic without `BLOCKING`.

## Out of scope

- TTL-based or push-driven cache invalidation; the caller decides when to
  force a refetch.
- Batch refresh of several keys in one call.

## Status

`implemented` (spec approved with a recorded decision in the group planning
2026-09-09 conversation: a forced refetch is the shared precondition for
periodic key refresh in the Home Assistant integration. Implemented
2026-09-09: `force` keyword merged, version 0.3.0).
